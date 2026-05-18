import json
import logging
from typing import Any, Callable
from functools import wraps
import os

try:
    from redis.asyncio import Redis, ConnectionPool
except Exception:  # pragma: no cover - environment-dependent optional dependency
    Redis = None
    ConnectionPool = None

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# In-memory fallback cache (used when Redis is unavailable)
_local_cache: TTLCache = TTLCache(maxsize=512, ttl=60)

# Redis Connection Pool
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
try:
    if Redis is None or ConnectionPool is None:
        raise RuntimeError("redis package not available")
    pool = ConnectionPool.from_url(redis_url, decode_responses=True)
    redis_client = Redis(connection_pool=pool)
except Exception as e:
    logger.warning(f"Failed to initialize Redis pool: {e}. Using in-memory cache fallback.")
    redis_client = None


def _cache_variant(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    safe_kwargs = {
        key: value
        for key, value in kwargs.items()
        if key not in {"user", "db", "request"}
    }
    return json.dumps(
        {
            "args": args,
            "kwargs": safe_kwargs,
        },
        sort_keys=True,
        default=str,
    )


def cache_response(expire_seconds: int = 900):
    """
    Decorator to cache FastAPI endpoint responses.
    Uses Redis when available, falls back to in-memory TTL cache.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            user_id = getattr(user, "id", "anonymous")
            variant = _cache_variant(args, kwargs)
            cache_key = f"cache:{func.__name__}:{user_id}:{variant}"

            # Try Redis first
            if redis_client:
                try:
                    cached_data = await redis_client.get(cache_key)
                    if cached_data:
                        return json.loads(cached_data)
                except Exception as e:
                    logger.error(f"Redis get error: {e}")
            else:
                # Fallback: in-memory cache
                cached = _local_cache.get(cache_key)
                if cached is not None:
                    return cached

            response_data = await func(*args, **kwargs)

            if response_data:
                if redis_client:
                    try:
                        await redis_client.setex(
                            name=cache_key,
                            time=expire_seconds,
                            value=json.dumps(response_data, default=str),
                        )
                    except Exception as e:
                        logger.error(f"Redis set error: {e}")
                else:
                    _local_cache[cache_key] = response_data

            return response_data

        return wrapper
    return decorator
