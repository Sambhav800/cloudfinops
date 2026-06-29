"""
In-memory token-bucket rate limiter middleware for FastAPI.

Limits are applied per authenticated user_id (from JWT sub claim) or per
client IP for unauthenticated requests. Expensive endpoints (scan, upload,
agent chat) get tighter per-minute budgets.
"""

import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.time)


@dataclass
class _RateLimit:
    requests_per_minute: int
    burst: int


_DEFAULT_LIMIT = _RateLimit(requests_per_minute=60, burst=15)

_TIGHT_LIMITS: dict[str, _RateLimit] = {
    "/api/scan/upload-bill": _RateLimit(requests_per_minute=5, burst=3),
    "/api/scan/trigger": _RateLimit(requests_per_minute=3, burst=2),
    "/api/agent/chat": _RateLimit(requests_per_minute=20, burst=8),
    "/api/scan/validate-automated-sync": _RateLimit(requests_per_minute=10, burst=5),
    "/api/reports/generate": _RateLimit(requests_per_minute=5, burst=3),
    "/api/architecture/propose": _RateLimit(requests_per_minute=5, burst=3),
}

_EXEMPT_PREFIXES = ("/docs", "/openapi.json", "/ws/", "/api/health")
_MAX_BUCKETS = 10_000
_CLEANUP_INTERVAL_SECONDS = 300


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(tokens=_DEFAULT_LIMIT.burst))
        self._last_cleanup = time.time()

    def _get_client_key(self, request: Request) -> str:
        auth_header = request.headers.get("authorization") or ""
        if auth_header.lower().startswith("bearer "):
            import jwt as pyjwt
            try:
                token = auth_header[7:].strip()
                payload = pyjwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass

        # Use request.client.host (set by the ASGI server / reverse proxy).
        # X-Forwarded-For is client-spoofable; only trust it behind Cloud Run
        # or a known load balancer that overwrites it. We use the direct
        # connection IP as the authoritative source.
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"

    def _get_limit(self, path: str) -> _RateLimit:
        for prefix, limit in _TIGHT_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return _DEFAULT_LIMIT

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)

    def _try_consume(self, key: str, limit: _RateLimit) -> tuple[bool, float]:
        now = time.time()
        bucket_key = f"{key}:{limit.requests_per_minute}"
        bucket = self._buckets[bucket_key]

        elapsed = now - bucket.last_refill
        refill_rate = limit.requests_per_minute / 60.0
        bucket.tokens = min(float(limit.burst), bucket.tokens + elapsed * refill_rate)
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, bucket.tokens
        else:
            retry_after = (1.0 - bucket.tokens) / refill_rate
            return False, retry_after

    def _maybe_cleanup(self) -> None:
        now = time.time()
        if now - self._last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        if len(self._buckets) <= _MAX_BUCKETS:
            self._last_cleanup = now
            return

        stale_threshold = now - 600
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for key in stale_keys:
            del self._buckets[key]
        self._last_cleanup = now
        logger.debug("Rate limiter cleanup: removed %d stale buckets", len(stale_keys))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if self._is_exempt(path) or request.method == "OPTIONS":
            return await call_next(request)

        client_key = self._get_client_key(request)
        limit = self._get_limit(path)
        allowed, remaining_or_retry = self._try_consume(client_key, limit)

        self._maybe_cleanup()

        if not allowed:
            retry_after = int(remaining_or_retry) + 1
            logger.warning(
                "Rate limit exceeded: %s on %s (limit: %d/min)",
                client_key, path, limit.requests_per_minute,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(remaining_or_retry))
        return response
