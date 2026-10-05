"""
Combined dashboard summary endpoint.

Returns all dashboard data in a single API call to eliminate
the N+1 frontend request pattern (previously 10-18+ calls).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
import math
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, ClerkUser
from ..db import get_db_client, MongoDBClient
from ..core.cache import cache_response
from ..core.azure_billing_refresh import BillingRefreshConfig
from ..core.finance import DISPLAY_CURRENCY, aggregate_daily_spend_rows

logger = logging.getLogger(__name__)

dashboard_summary_router = APIRouter(prefix="/api", tags=["dashboard-summary"])


class BillingSpend(BaseModel):
    amount: float | None
    currency: str = DISPLAY_CURRENCY
    status: Literal["fresh", "cached", "stale", "unavailable", "known"]
    completeness: Literal["complete", "partial", "unavailable"]
    observed_at: str | None = None
    period_start: str
    reason: str | None = None
    retry_at: str | None = None
    as_of: str


class ProviderBillingSpend(BillingSpend):
    provider: str


class DashboardSummaryResponse(BaseModel):
    stats: dict[str, Any]
    resources: list[dict[str, Any]]
    resource_count: int
    waste_distribution: list[dict[str, Any]]
    spend_history: list[dict[str, Any]]
    provider_mtd_spend: list[ProviderBillingSpend]
    mtd_spend: BillingSpend
    permission_alert: dict[str, Any] | None
    integrations: list[dict[str, Any]]
    integration_count: int


def _billing_timestamp(value: Any, period_start: str, now: datetime) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return None
        parsed = parsed.astimezone(timezone.utc)
        return parsed if period_start <= parsed.date().isoformat() and parsed <= now else None
    except (TypeError, ValueError, OverflowError):
        return None


def _valid_spend_amount(row: dict[str, Any]) -> bool:
    try:
        return not isinstance(row.get("amount"), bool) and math.isfinite(float(row["amount"]))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _integration_mtd_spend(
    integration: dict[str, Any], history: list[dict[str, Any]], as_of: date, *, now: datetime | None = None,
) -> BillingSpend:
    now = now or datetime.now(timezone.utc)
    period_start = as_of.replace(day=1).isoformat()
    current_rows = []
    for row in history:
        try:
            spend_date = date.fromisoformat(str(row.get("spend_date"))[:10])
        except ValueError:
            continue
        if period_start <= spend_date.isoformat() <= as_of.isoformat():
            current_rows.append(row)
    valid_rows = [row for row in current_rows if _valid_spend_amount(row)]
    aggregated = aggregate_daily_spend_rows(valid_rows)
    metadata = integration.get("metadata")
    billing = metadata.get("billing") if isinstance(metadata, dict) else None
    billing = billing if isinstance(billing, dict) else {}
    status = billing.get("status")
    current_period = billing.get("period_start") == period_start
    # An empty read can be a persistence failure. Only persisted rows establish an amount, including zero.
    amount = round(sum(row["amount"] for row in aggregated), 2) if valid_rows and len(valid_rows) == len(current_rows) else None
    observed_at = _billing_timestamp(billing.get("observed_at"), period_start, now) if current_period else None
    if observed_at is None:
        observations = []
        for row in valid_rows:
            metadata = row.get("metadata")
            row_billing = metadata.get("billing") if isinstance(metadata, dict) else None
            row_billing = row_billing if isinstance(row_billing, dict) else {}
            if row_billing.get("period_start", period_start) != period_start:
                continue
            stamp = next((parsed for value in (
                row_billing.get("observed_at"), row.get("updated_at"), row.get("created_at"),
            ) if (parsed := _billing_timestamp(value, period_start, now)) is not None), None)
            if stamp is not None:
                observations.append(stamp)
        observed_at = min(observations) if observations else None
    reason = billing.get("reason")
    if amount is None:
        status = "unavailable"
        reason = reason or "No current-month daily billing history"
    elif not billing:
        status = "known"
    elif not current_period or status not in {"fresh", "cached"} or billing.get("daily_costs_available") is not True:
        status = "stale"
        reason = reason or "Using preserved current-month daily billing history"
    elif str(integration.get("provider") or "").lower() == "azure" and (
        observed_at is None or (now - observed_at).total_seconds() >= BillingRefreshConfig().cache_ttl_seconds
    ):
        status = "stale"
        reason = reason or "Billing observation expired or unknown"

    return BillingSpend(
        amount=amount,
        status=status,
        completeness="complete" if amount is not None else ("partial" if valid_rows else "unavailable"),
        observed_at=observed_at.isoformat() if observed_at else None,
        period_start=period_start,
        reason=reason,
        retry_at=billing.get("retry_at"),
        as_of=now.isoformat(),
    )


def _combine_billing_spend(items: list[BillingSpend], now: datetime) -> BillingSpend:
    complete = bool(items) and all(item.amount is not None for item in items)
    known = any(item.amount is not None or item.completeness == "partial" for item in items)
    statuses = {item.status for item in items}
    status = next(
        (value for value in ("unavailable", "stale", "known", "cached", "fresh") if value in statuses),
        "unavailable",
    )
    # The oldest observation bounds freshness; missing timestamps must not look freshly observed.
    observations = [item.observed_at for item in items if item.observed_at]
    retries = [item.retry_at for item in items if item.retry_at]
    return BillingSpend(
        amount=round(sum(item.amount for item in items if item.amount is not None), 2) if complete else None,
        status=status,
        completeness="complete" if complete else ("partial" if known else "unavailable"),
        observed_at=min(observations) if observations and len(observations) == len(items) else None,
        period_start=now.date().replace(day=1).isoformat(),
        reason="; ".join(dict.fromkeys(item.reason for item in items if item.reason)) or None,
        retry_at=max(retries) if retries else None,
        as_of=now.isoformat(),
    )


async def _get_summary_spend(
    db: MongoDBClient, user_id: str, integrations: list[dict[str, Any]], days: int,
) -> tuple[list[dict[str, Any]], list[ProviderBillingSpend], BillingSpend]:
    try:
        now = datetime.now(timezone.utc)
        as_of = now.date()
        history_start = min(as_of.replace(day=1), as_of - timedelta(days=days - 1))
        results = await asyncio.gather(*(
            db.select("daily_spend_history", filters={
                "user_id": user_id,
                "integration_id": str(integration["id"]),
                "spend_date": {"$gte": history_start.isoformat(), "$lt": (as_of + timedelta(days=1)).isoformat()},
            })
            for integration in integrations
        ))
        by_provider: dict[str, list[BillingSpend]] = {}
        for integration, history in zip(integrations, results):
            provider = str(integration.get("provider") or "unknown").strip().lower()
            by_provider.setdefault(provider, []).append(_integration_mtd_spend(integration, history, as_of, now=now))
        providers = [
            ProviderBillingSpend(provider=provider, **_combine_billing_spend(items, now).model_dump())
            for provider, items in by_provider.items()
        ]
        portfolio = _combine_billing_spend([item for items in by_provider.values() for item in items], now)
        history = aggregate_daily_spend_rows([row for result in results for row in result if _valid_spend_amount(row)])
        return history[-days:], providers, portfolio
    except Exception:
        logger.error("Failed to load dashboard billing summary")
        raise


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


@dashboard_summary_router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
@cache_response(expire_seconds=60)
async def get_dashboard_summary(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> dict[str, Any]:
    """All dashboard data in one call."""
    try:
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
        spend_task = _get_summary_spend(
            db, user.id, [i for i in active_integrations if str(i.get("id") or "").strip()], days=30,
        )
        notifications_task = db.select(
            "agent_notifications",
            filters={"user_id": user.id, "status": "pending"},
            limit=50,
        )

        stats, resources, waste_rows, spend_summary, notifications = await asyncio.gather(
            stats_task, resources_task, waste_task, spend_task, notifications_task
        )
        spend_history, provider_mtd_spend, mtd_spend = spend_summary

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
            "provider_mtd_spend": [item.model_dump() for item in provider_mtd_spend],
            "mtd_spend": mtd_spend.model_dump(),
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
    except Exception:
        logger.error("Dashboard summary failed")
        raise HTTPException(status_code=500, detail="Unable to load dashboard summary")
