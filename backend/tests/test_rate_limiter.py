"""
Tests for the in-memory rate limiter middleware.
"""

import time

import pytest

from app.core.rate_limiter import RateLimiterMiddleware, _Bucket, _RateLimit


class TestTokenBucket:
    """Unit tests for the token bucket consumption logic."""

    def test_allows_requests_within_limit(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = _RateLimit(requests_per_minute=10, burst=5)

        for i in range(5):
            allowed, _ = middleware._try_consume("test-user", limit)
            assert allowed, f"Request {i+1} should be allowed within burst"

    def test_rejects_after_burst_exhausted(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = _RateLimit(requests_per_minute=10, burst=3)

        for _ in range(3):
            middleware._try_consume("test-user", limit)

        allowed, retry_after = middleware._try_consume("test-user", limit)
        assert not allowed
        assert retry_after > 0

    def test_refills_over_time(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = _RateLimit(requests_per_minute=60, burst=2)

        middleware._try_consume("refill-test", limit)
        middleware._try_consume("refill-test", limit)
        allowed, _ = middleware._try_consume("refill-test", limit)
        assert not allowed

        bucket_key = f"refill-test:{limit.requests_per_minute}"
        middleware._buckets[bucket_key].last_refill -= 2.0

        allowed, _ = middleware._try_consume("refill-test", limit)
        assert allowed

    def test_different_users_have_separate_buckets(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = _RateLimit(requests_per_minute=10, burst=1)

        allowed_a, _ = middleware._try_consume("user-a", limit)
        allowed_b, _ = middleware._try_consume("user-b", limit)
        assert allowed_a
        assert allowed_b

        rejected_a, _ = middleware._try_consume("user-a", limit)
        assert not rejected_a

        allowed_b_2, _ = middleware._try_consume("user-b", limit)
        assert not allowed_b_2

    def test_tight_limit_endpoints_have_lower_burst(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = middleware._get_limit("/api/scan/upload-bill")
        assert limit.requests_per_minute == 5
        assert limit.burst == 3

    def test_default_limit_for_normal_endpoints(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = middleware._get_limit("/api/resources")
        assert limit.requests_per_minute == 60
        assert limit.burst == 15

    def test_exempt_paths_not_rate_limited(self):
        middleware = RateLimiterMiddleware(app=None)
        assert middleware._is_exempt("/docs")
        assert middleware._is_exempt("/ws/user-123")
        assert middleware._is_exempt("/api/health")
        assert not middleware._is_exempt("/api/scan/trigger")

    def test_cleanup_removes_stale_buckets(self):
        middleware = RateLimiterMiddleware(app=None)
        limit = _RateLimit(requests_per_minute=60, burst=10)

        for i in range(100):
            middleware._try_consume(f"stale-user-{i}", limit)

        now = time.time()
        for key in list(middleware._buckets.keys())[:50]:
            middleware._buckets[key].last_refill = now - 700

        middleware._last_cleanup = now - 400
        middleware._maybe_cleanup()
