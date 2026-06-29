"""
API Intelligence Tools — ADK tool functions for the API Intelligence Agent.
Provides scanning, classification, cache analysis, and optimization recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def api_scan_resources(user_id: str = "") -> dict:
    """
    Scan all API resources across AWS, Azure, and GCP from the database.
    Returns a summary of all API Gateways with their traffic and cost metrics.
    """
    import asyncio
    from ...db.mongo_client import get_db_client
    from ...core.api_intelligence import ApiIntelligenceService

    async def _scan():
        db = get_db_client()
        resources = await db.get_resources(user_id)
        service = ApiIntelligenceService()
        return service.get_api_summary(resources)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _scan()).result()
        else:
            result = asyncio.run(_scan())
        return result
    except Exception as e:
        logger.error(f"API scan failed: {e}")
        return {"error": str(e), "api_resources": [], "ghost_apis": []}


def api_classify_usage(resource_id: str, invocations_7d: int, error_rate: float = 0) -> dict:
    """
    Classify API usage pattern: production, dev-only, ghost, high-traffic.
    """
    if invocations_7d == 0:
        usage_type = "ghost"
        confidence = 0.95
        reason = "Zero invocations in 7 days — completely idle."
    elif invocations_7d < 100:
        usage_type = "dev_only"
        confidence = 0.75
        reason = f"Very low traffic ({invocations_7d} calls/week) — likely a dev/test endpoint."
    elif invocations_7d < 10000:
        usage_type = "low_traffic"
        confidence = 0.70
        reason = f"Moderate traffic ({invocations_7d} calls/week) — internal or low-use API."
    elif invocations_7d < 1000000:
        usage_type = "production"
        confidence = 0.85
        reason = f"Significant traffic ({invocations_7d:,} calls/week) — production API."
    else:
        usage_type = "high_traffic"
        confidence = 0.90
        reason = f"High traffic ({invocations_7d:,} calls/week) — critical production API."

    if error_rate > 20:
        reason += f" WARNING: High error rate ({error_rate:.1f}%) — may indicate issues."

    return {
        "resource_id": resource_id,
        "usage_type": usage_type,
        "confidence": confidence,
        "reason": reason,
        "invocations_7d": invocations_7d,
        "error_rate": error_rate,
    }


def api_recommend_optimization(
    resource_id: str,
    usage_type: str,
    cache_hit_rate: float | None = None,
    monthly_cost: float = 0,
) -> dict:
    """
    Generate optimization recommendation for an API resource.
    """
    recommendations = []

    if usage_type == "ghost":
        recommendations.append({
            "action": "delete_or_disable",
            "priority": "critical",
            "description": "API is completely idle. Delete the stage or disable the API to stop charges.",
            "estimated_savings_pct": 100,
        })
    elif usage_type == "dev_only":
        recommendations.append({
            "action": "schedule_or_consolidate",
            "priority": "high",
            "description": "Dev/test API with minimal traffic. Consider auto-shutdown schedules or consolidating dev environments.",
            "estimated_savings_pct": 70,
        })
    elif usage_type == "low_traffic":
        recommendations.append({
            "action": "rightsize_throttle",
            "priority": "medium",
            "description": "Low-traffic API — reduce burst/rate limits to prevent accidental cost spikes.",
            "estimated_savings_pct": 20,
        })

    if cache_hit_rate is not None and cache_hit_rate < 5.0:
        recommendations.append({
            "action": "disable_cache",
            "priority": "high",
            "description": f"Cache hit rate is {cache_hit_rate:.1f}% — essentially useless. Disable to save cache tier costs.",
            "estimated_savings_pct": 15,
        })
    elif cache_hit_rate is not None and cache_hit_rate > 80:
        recommendations.append({
            "action": "keep_cache",
            "priority": "info",
            "description": f"Cache is performing well ({cache_hit_rate:.1f}% hit rate). No changes needed.",
            "estimated_savings_pct": 0,
        })

    return {
        "resource_id": resource_id,
        "usage_type": usage_type,
        "recommendations": recommendations,
        "recommendation_count": len(recommendations),
    }


def api_cache_analysis(
    resource_id: str,
    cache_enabled: bool,
    hit_rate: float,
    monthly_cost: float = 0,
) -> dict:
    """
    Analyze cache efficiency and recommend enable/disable/resize.
    """
    if not cache_enabled:
        return {
            "resource_id": resource_id,
            "cache_enabled": False,
            "recommendation": "no_cache",
            "detail": "Cache is not enabled. Consider enabling if API serves repeated identical requests.",
        }

    if hit_rate < 5:
        return {
            "resource_id": resource_id,
            "cache_enabled": True,
            "hit_rate": hit_rate,
            "recommendation": "disable",
            "detail": f"Cache hit rate ({hit_rate:.1f}%) is extremely low. Disable to save ~$14-58/month per stage.",
            "estimated_monthly_savings": min(monthly_cost * 0.15, 58),
        }
    elif hit_rate < 30:
        return {
            "resource_id": resource_id,
            "cache_enabled": True,
            "hit_rate": hit_rate,
            "recommendation": "optimize",
            "detail": f"Cache hit rate ({hit_rate:.1f}%) is suboptimal. Review cache key configuration and TTL settings.",
            "estimated_monthly_savings": 0,
        }
    else:
        return {
            "resource_id": resource_id,
            "cache_enabled": True,
            "hit_rate": hit_rate,
            "recommendation": "keep",
            "detail": f"Cache is healthy ({hit_rate:.1f}% hit rate). Consider increasing size if latency is still high.",
            "estimated_monthly_savings": 0,
        }
