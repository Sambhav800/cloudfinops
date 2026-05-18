"""
Daily pricing sync worker.

Runs at 3:30 AM UTC via APScheduler to refresh live cloud pricing multipliers.
"""

from __future__ import annotations

import logging

from ..core.live_pricing_engine import compute_live_multipliers
from ..db.mongo_client import get_db_client

logger = logging.getLogger(__name__)


async def sync_live_pricing():
    """Daily job: refresh live pricing multipliers from APIs."""
    logger.info("Starting scheduled live pricing sync...")
    try:
        db = get_db_client()
        result = await compute_live_multipliers(db, force_refresh=True)

        live_count = result.get("live_count", 0)
        partial_count = result.get("partial_count", 0)
        static_count = result.get("static_count", 0)
        elapsed = result.get("computation_time_seconds", 0)

        logger.info(
            "Live pricing sync completed in %.2fs: %d live, %d partial, %d static",
            elapsed, live_count, partial_count, static_count,
        )

        # Invalidate Redis cache for discount endpoints
        try:
            from ..core.cache import redis_client
            if redis_client:
                keys = await redis_client.keys("cache:calculate*")
                if keys:
                    await redis_client.delete(*keys)
                    logger.info("Invalidated %d Redis cache keys for discount endpoints", len(keys))
        except Exception as e:
            logger.warning("Redis cache invalidation failed (non-critical): %s", e)

    except Exception as e:
        logger.error("Live pricing sync FAILED: %s", e, exc_info=True)
