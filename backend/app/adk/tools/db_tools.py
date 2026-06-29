"""
Database Tools for ADK — Fast-path data access from MongoDB.
These tools query the existing CloudFinOps database instead of hitting live cloud APIs,
providing sub-second responses for common questions.
Uses synchronous pymongo (not motor) because ADK tool functions run in sync context.
"""
import os
from typing import Optional

from pymongo import MongoClient


_DEFAULT_USER_ID = "user_38tM3l1kGfp1ohHSRhrmWMLYHFR"


def _get_db():
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/cloudfinops")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client["cloudfinops"]


def _resolve_user_id(user_id: str) -> str:
    """Use default test user if no valid Clerk user_id provided."""
    if user_id and len(user_id) > 20 and user_id.startswith("user_"):
        return user_id
    return _DEFAULT_USER_ID


def get_portfolio_summary(user_id: str) -> dict:
    """
    Get the user's complete cloud portfolio summary from the database.
    This is FAST (sub-second) because it reads from cached scan results.
    Use this for questions like "what's my cloud spend?" or "how many resources do I have?"

    Args:
        user_id: The authenticated user's ID

    Returns:
        dict with total_spend, total_savings, resource_count, providers, last_scan_time
    """
    try:
        db = _get_db()
        user_id = _resolve_user_id(user_id)
        stats = db.dashboard_stats.find_one({"user_id": user_id})
        if not stats:
            return {"status": "no_data", "message": "No scan data available. Run a scan first."}

        integrations = list(db.cloud_integrations.find({"user_id": user_id, "status": "active"}))
        providers = list(set(i.get("provider", "") for i in integrations))

        return {
            "status": "success",
            "source": "database_cache",
            "total_monthly_spend_usd": stats.get("total_spend", 0),
            "potential_savings_usd": stats.get("potential_savings", 0),
            "total_resources": stats.get("total_resources", 0),
            "active_resources": stats.get("active_resources", 0),
            "zombie_resources": stats.get("zombie_count", 0),
            "providers_connected": providers,
            "ai_confidence_pct": stats.get("ai_confidence", 0),
            "last_scan": str(stats.get("updated_at", "unknown")),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_zombie_resources(user_id: str, provider: str = "all", limit: int = 10) -> dict:
    """
    Get zombie (wasted) resources from the database. Instant response from cached scan data.
    Use this when the user asks about waste, idle resources, or cost optimization opportunities.

    Args:
        user_id: The authenticated user's ID
        provider: Filter by provider ("aws", "azure", "gcp", or "all")
        limit: Maximum number of resources to return (1-50)

    Returns:
        dict with zombie resources including name, cost, service_type, status, and tags
    """
    try:
        db = _get_db()
        user_id = _resolve_user_id(user_id)
        filters = {"user_id": user_id, "status": {"$in": ["Zombie", "zombie", "Stopped", "stopped"]}}
        if provider != "all":
            filters["provider"] = provider

        resources = list(db.resources.find(filters).sort("cost", -1).limit(limit))

        return {
            "status": "success",
            "source": "database_cache",
            "zombie_count": len(resources),
            "resources": [
                {
                    "resource_name": r.get("resource_name", "unknown"),
                    "provider": r.get("provider", "unknown"),
                    "service_type": r.get("service_type", "unknown"),
                    "region": r.get("region", "unknown"),
                    "monthly_cost_usd": r.get("cost", 0),
                    "status": r.get("status", "unknown"),
                    "tags": r.get("metadata", {}).get("tags", {}),
                    "last_seen": str(r.get("updated_at", "unknown")),
                }
                for r in resources
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_cost_by_service(user_id: str, provider: str = "all") -> dict:
    """
    Get cost breakdown by service type from the database.
    Instant response — no live API calls needed.

    Args:
        user_id: The authenticated user's ID
        provider: Filter by provider ("aws", "azure", "gcp", or "all")

    Returns:
        dict with cost grouped by service_type, sorted by highest spend
    """
    try:
        db = _get_db()
        user_id = _resolve_user_id(user_id)
        match_stage = {"user_id": user_id}
        if provider != "all":
            match_stage["provider"] = provider

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": {"service": "$service_type", "provider": "$provider"},
                "total_cost": {"$sum": "$cost"},
                "resource_count": {"$sum": 1},
            }},
            {"$sort": {"total_cost": -1}},
            {"$limit": 15},
        ]

        results = list(db.resources.aggregate(pipeline))

        return {
            "status": "success",
            "source": "database_cache",
            "breakdown": [
                {
                    "service_type": r["_id"].get("service") or "Unknown",
                    "provider": r["_id"].get("provider") or "Unknown",
                    "total_monthly_cost_usd": round(r["total_cost"], 2),
                    "resource_count": r["resource_count"],
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_recent_alerts(user_id: str, limit: int = 5) -> dict:
    """
    Get recent AI-generated alerts and recommendations from the database.
    These are findings from the last scan that need attention.

    Args:
        user_id: The authenticated user's ID
        limit: Number of alerts to return (1-20)

    Returns:
        dict with recent alerts including severity, message, and affected resources
    """
    try:
        db = _get_db()
        user_id = _resolve_user_id(user_id)
        alerts = list(
            db.agent_notifications.find(
                {"user_id": user_id, "status": {"$ne": "dismissed"}}
            ).sort("created_at", -1).limit(limit)
        )

        return {
            "status": "success",
            "source": "database_cache",
            "alert_count": len(alerts),
            "alerts": [
                {
                    "type": a.get("type", "recommendation"),
                    "severity": a.get("severity", "medium"),
                    "title": a.get("title", ""),
                    "message": a.get("message", ""),
                    "resource_name": a.get("resource_name", ""),
                    "estimated_savings_usd": a.get("estimated_savings", 0),
                    "created_at": str(a.get("created_at", "")),
                }
                for a in alerts
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
