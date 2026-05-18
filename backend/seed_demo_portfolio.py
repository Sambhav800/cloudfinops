from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.core.demo_portfolio import (
    CANONICAL_DEMO_DATA_OWNER_ID,
    DEMO_ACCOUNT_EMAIL,
    DEMO_DATASET_VERSION,
    LEGACY_DEMO_DATA_OWNER_ID,
    build_demo_portfolio_bundle,
)
from app.db import get_db_client


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo_portfolio")

RESET_COLLECTIONS = (
    "cloud_integrations",
    "resources",
    "dashboard_stats",
    "daily_spend_history",
    "waste_distribution",
    "agent_notifications",
    "budget_events",
    "governance_policies",
    "policy_violations",
    "scan_history",
    "reports",
    "audit_logs",
)


async def _select_users_by_demo_email(db: Any) -> List[Dict[str, Any]]:
    users_by_lower = await db.select(
        "users",
        filters={"email_lower": DEMO_ACCOUNT_EMAIL.lower()},
    )
    users_by_email = await db.select(
        "users",
        filters={"email": DEMO_ACCOUNT_EMAIL},
    )

    deduplicated: Dict[str, Dict[str, Any]] = {}
    for row in [*users_by_lower, *users_by_email]:
        user_id = str(row.get("id") or "").strip()
        if not user_id:
            continue
        deduplicated[user_id] = row
    return list(deduplicated.values())


def _resolve_demo_owner_ids(existing_users: Iterable[Dict[str, Any]]) -> List[str]:
    owner_ids = {
        LEGACY_DEMO_DATA_OWNER_ID,
        CANONICAL_DEMO_DATA_OWNER_ID,
    }
    for user in existing_users:
        user_id = str(user.get("id") or "").strip()
        if user_id:
            owner_ids.add(user_id)
    return sorted(owner_ids)


def _resolve_primary_owner_id(existing_users: Iterable[Dict[str, Any]], owner_ids: Iterable[str]) -> str:
    normalized_email = DEMO_ACCOUNT_EMAIL.lower()

    for user in existing_users:
        user_id = str(user.get("id") or "").strip()
        if user_id and str(user.get("email_lower") or "").strip().lower() == normalized_email:
            return user_id

    for user in existing_users:
        user_id = str(user.get("id") or "").strip()
        if user_id and str(user.get("email") or "").strip().lower() == normalized_email:
            return user_id

    if LEGACY_DEMO_DATA_OWNER_ID in set(owner_ids):
        return LEGACY_DEMO_DATA_OWNER_ID
    if CANONICAL_DEMO_DATA_OWNER_ID in set(owner_ids):
        return CANONICAL_DEMO_DATA_OWNER_ID

    return sorted(set(owner_ids))[0]


async def _upsert_demo_user(
    *,
    db: Any,
    owner_id: str,
    existing_user: Dict[str, Any] | None,
    finance_settings: Dict[str, Any],
    primary_owner_id: str,
) -> None:
    current = dict(existing_user or {})
    existing_metadata = current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
    current["id"] = owner_id
    current["email"] = str(current.get("email") or DEMO_ACCOUNT_EMAIL).strip().lower()
    current["email_lower"] = DEMO_ACCOUNT_EMAIL.lower() if owner_id == primary_owner_id else None
    current["full_name"] = str(current.get("full_name") or "Sambhav Pal")
    current["first_name"] = str(current.get("first_name") or "Sambhav")
    current["last_name"] = str(current.get("last_name") or "Pal")
    current["finance_settings"] = finance_settings
    current["metadata"] = {
        **existing_metadata,
        "demo_portfolio_enabled": True,
        "demo_dataset_version": DEMO_DATASET_VERSION,
    }
    await db.upsert("users", current)


def _flatten_history(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for integration_rows in bundle["daily_spend_history_by_integration"].values():
        rows.extend(integration_rows)
    return rows


async def _load_demo_bill_analyses(
    db: Any,
    owner_ids: Iterable[str],
) -> Tuple[str | None, List[Dict[str, Any]]]:
    best_owner_id: str | None = None
    best_rows: List[Dict[str, Any]] = []

    for owner_id in owner_ids:
        rows = await db.select("bill_analyses", filters={"user_id": owner_id})
        if len(rows) > len(best_rows):
            best_owner_id = owner_id
            best_rows = rows

    return best_owner_id, best_rows


async def _sync_bill_analyses(
    *,
    db: Any,
    owner_ids: Iterable[str],
) -> Dict[str, int]:
    source_owner_id, source_rows = await _load_demo_bill_analyses(db, owner_ids)
    if not source_owner_id or not source_rows:
        return {}

    synced_counts: Dict[str, int] = {}
    for owner_id in owner_ids:
        if owner_id == source_owner_id:
            synced_counts[owner_id] = len(source_rows)
            continue

        await db.delete("bill_analyses", {"user_id": owner_id})
        cloned_rows: List[Dict[str, Any]] = []
        for row in source_rows:
            cloned = dict(row)
            cloned["id"] = str(uuid4())
            cloned["user_id"] = owner_id
            cloned_rows.append(cloned)

        if cloned_rows:
            await db.insert("bill_analyses", cloned_rows)
        synced_counts[owner_id] = len(cloned_rows)

    return synced_counts


async def _reset_owner_collections(db: Any, owner_id: str) -> None:
    for collection in RESET_COLLECTIONS:
        await db.delete(collection, {"user_id": owner_id})


async def _insert_bundle(db: Any, bundle: Dict[str, Any]) -> None:
    await db.insert("cloud_integrations", bundle["integrations"])
    await db.insert("resources", bundle["resources"])
    await db.insert("dashboard_stats", bundle["dashboard_stats"])
    daily_spend_history = _flatten_history(bundle)
    if daily_spend_history:
        await db.insert("daily_spend_history", daily_spend_history)
    if bundle["waste_distribution"]:
        await db.insert("waste_distribution", bundle["waste_distribution"])
    if bundle["notifications"]:
        await db.insert("agent_notifications", bundle["notifications"])
    if bundle["budget_events"]:
        await db.insert("budget_events", bundle["budget_events"])
    if bundle["governance_policies"]:
        await db.insert("governance_policies", bundle["governance_policies"])
    if bundle["policy_violations"]:
        await db.insert("policy_violations", bundle["policy_violations"])
    if bundle["scan_history"]:
        await db.insert("scan_history", bundle["scan_history"])
    if bundle["reports"]:
        await db.insert("reports", bundle["reports"])
    if bundle["audit_logs"]:
        await db.insert("audit_logs", bundle["audit_logs"])


async def _seed_owner(
    *,
    db: Any,
    owner_id: str,
    existing_user: Dict[str, Any] | None,
    primary_owner_id: str,
) -> Dict[str, Any]:
    bundle = build_demo_portfolio_bundle(owner_id)
    await _upsert_demo_user(
        db=db,
        owner_id=owner_id,
        existing_user=existing_user,
        finance_settings=bundle["finance_settings"],
        primary_owner_id=primary_owner_id,
    )
    await _reset_owner_collections(db, owner_id)
    await _insert_bundle(db, bundle)

    return {
        "owner_id": owner_id,
        "integrations": len(bundle["integrations"]),
        "resources": len(bundle["resources"]),
        "notifications": len(bundle["notifications"]),
        "reports": len(bundle["reports"]),
        "audit_logs": len(bundle["audit_logs"]),
        "total_spend": round(sum(float(item.get("total_spend") or 0.0) for item in bundle["dashboard_stats"]), 2),
        "potential_savings": round(sum(float(item.get("potential_savings") or 0.0) for item in bundle["dashboard_stats"]), 2),
        "forecast_status": str(bundle["portfolio_forecast"].get("status") or "unknown"),
        "forecast_eom_spend": round(float(bundle["portfolio_forecast"].get("forecast_eom_spend") or 0.0), 2),
    }


async def main() -> int:
    db = get_db_client()
    try:
        existing_users = await _select_users_by_demo_email(db)
        existing_users_by_id = {
            str(user.get("id") or "").strip(): user
            for user in existing_users
            if str(user.get("id") or "").strip()
        }
        owner_ids = _resolve_demo_owner_ids(existing_users)
        primary_owner_id = _resolve_primary_owner_id(existing_users, owner_ids)

        logger.info(
            "Seeding demo portfolio version %s for %s owner ids (primary user row: %s)",
            DEMO_DATASET_VERSION,
            len(owner_ids),
            primary_owner_id,
        )

        summaries: List[Dict[str, Any]] = []
        for owner_id in owner_ids:
            summary = await _seed_owner(
                db=db,
                owner_id=owner_id,
                existing_user=existing_users_by_id.get(owner_id),
                primary_owner_id=primary_owner_id,
            )
            summaries.append(summary)

        synced_bill_analyses = await _sync_bill_analyses(
            db=db,
            owner_ids=owner_ids,
        )

        print("Demo portfolio seed complete.")
        print(f"- Demo email: {DEMO_ACCOUNT_EMAIL}")
        print(f"- Dataset version: {DEMO_DATASET_VERSION}")
        for summary in summaries:
            print(
                "- {owner_id}: {integrations} integrations, {resources} resources, "
                "{notifications} notifications, {reports} reports, forecast {forecast_status} @ ${forecast_eom_spend:,.2f}, "
                "spend ${total_spend:,.2f}, savings ${potential_savings:,.2f}".format(**summary)
            )
        if synced_bill_analyses:
            print(f"- Bill analyses synced: {synced_bill_analyses}")
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
