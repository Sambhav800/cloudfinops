"""
Combined dashboard summary endpoint.

Returns all dashboard data in a single API call to eliminate
the N+1 frontend request pattern (previously 10-18+ calls).
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends

from ..auth import get_current_user, ClerkUser
from ..db import get_db_client, MongoDBClient
from ..core.cache import cache_response
from ..core.finance import aggregate_daily_spend_rows

logger = logging.getLogger(__name__)

dashboard_summary_router = APIRouter(prefix="/api", tags=["dashboard-summary"])


async def _get_active_integrations_for_summary(db: MongoDBClient, user_id: str) -> list[dict[str, Any]]:
    integrations = await db.get_user_integrations(user_id)
    return [
        i for i in integrations
        if str(i.get("status") or "").lower() == "active"
    ]


async def _get_portfolio_stats(db: MongoDBClient, user_id: str, integration_ids: list[str]) -> dict[str, Any]:
    if not integration_ids:
        return {
            "total_spend": 0.0,
            "potential_savings": 0.0,
            "active_resources_count": 0,
            "ai_confidence_score": 0,
            "carbon_footprint_kg": 0.0,
            "cost_of_inaction_6mo": 0.0,
        }

    stats_list = await asyncio.gather(
        *(db.get_dashboard_stats(user_id, iid) for iid in integration_ids)
    )

    totals: dict[str, Any] = {
        "total_spend": 0.0,
        "potential_savings": 0.0,
        "active_resources_count": 0,
        "ai_confidence_score": 0,
        "carbon_footprint_kg": 0.0,
        "cost_of_inaction_6mo": 0.0,
    }
    confidence_scores: list[float] = []

    for stats in stats_list:
        stats = stats or {}
        totals["total_spend"] += float(stats.get("total_spend") or 0.0)
        totals["potential_savings"] += float(stats.get("potential_savings") or 0.0)
        totals["active_resources_count"] += int(stats.get("active_resources_count") or 0)
        totals["carbon_footprint_kg"] += float(stats.get("carbon_footprint_kg") or 0.0)
        totals["cost_of_inaction_6mo"] += float(stats.get("cost_of_inaction_6mo") or 0.0)
        try:
            confidence = float(stats.get("ai_confidence_score") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 0:
            confidence_scores.append(confidence)

    if confidence_scores:
        totals["ai_confidence_score"] = int(round(sum(confidence_scores) / len(confidence_scores)))

    return totals


async def _get_aggregated_spend(db: MongoDBClient, user_id: str, integration_ids: list[str], days: int) -> list[dict[str, Any]]:
    if not integration_ids:
        return []
    results = await asyncio.gather(
        *(db.get_daily_spend_history(user_id, iid, days) for iid in integration_ids)
    )
    rows = [row for result in results for row in result]
    history = aggregate_daily_spend_rows(rows)
    return history[-days:] if len(history) > days else history


@dashboard_summary_router.get("/dashboard/summary")
@cache_response(expire_seconds=60)
async def get_dashboard_summary(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """All dashboard data in one call."""
    active_integrations = await _get_active_integrations_for_summary(db, user.id)
    integration_ids = [
        str(i.get("id") or "").strip()
        for i in active_integrations
        if str(i.get("id") or "").strip()
    ]
    active_id_set = set(integration_ids)

    stats_task = _get_portfolio_stats(db, user.id, integration_ids)
    resources_task = db.get_resources(user.id)
    waste_task = db.select("waste_distribution", filters={"user_id": user.id})
    spend_task = _get_aggregated_spend(db, user.id, integration_ids, days=30)
    notifications_task = db.select(
        "agent_notifications",
        filters={"user_id": user.id, "status": "pending"},
        limit=50,
    )

    stats, resources, waste_rows, spend_history, notifications = await asyncio.gather(
        stats_task, resources_task, waste_task, spend_task, notifications_task
    )

    if active_id_set:
        resources = [
            r for r in resources
            if not str(r.get("integration_id") or "").strip()
            or str(r.get("integration_id") or "").strip() in active_id_set
        ]
        waste_rows = [
            r for r in waste_rows
            if str(r.get("integration_id") or "").strip() in active_id_set
        ]

    permission_alert = next(
        (
            n for n in sorted(
                notifications,
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )
            if str(n.get("type") or "").strip().lower() == "permission_alert"
        ),
        None,
    )

    return {
        "stats": stats,
        "resources": resources[:2000],
        "resource_count": len(resources),
        "waste_distribution": waste_rows,
        "spend_history": spend_history,
        "permission_alert": permission_alert,
        "integrations": [
            {
                "id": i.get("id"),
                "provider": i.get("provider"),
                "name": i.get("name"),
                "status": i.get("status"),
                "last_scan": i.get("last_scan"),
                "regions": i.get("regions", []),
            }
            for i in active_integrations
        ],
        "integration_count": len(active_integrations),
    }
