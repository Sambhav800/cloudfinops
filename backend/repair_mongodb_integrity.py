from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.config import get_settings
from app.db import get_db_client


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("repair_mongodb_integrity")

USER_SCOPED_COLLECTIONS = (
    "users",
    "cloud_integrations",
    "resources",
    "dashboard_stats",
    "daily_spend_history",
    "scan_history",
    "agent_notifications",
    "policy_violations",
    "budget_events",
    "reports",
    "governance_policies",
    "bill_analyses",
)

INTEGRATION_OWNED_COLLECTIONS = (
    ("resources", True),
    ("dashboard_stats", False),
    ("daily_spend_history", False),
    ("scan_history", False),
    ("waste_distribution", False),
)

QUARANTINE_COLLECTION = "integrity_quarantine"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned


def _extract_primary_email(clerk_user: dict[str, Any]) -> str | None:
    primary_id = _clean_optional_string(clerk_user.get("primary_email_address_id"))
    email_addresses = clerk_user.get("email_addresses")
    if isinstance(email_addresses, list):
        for item in email_addresses:
            if not isinstance(item, dict):
                continue
            email = _clean_optional_string(item.get("email_address"))
            if not email:
                continue
            if primary_id and _clean_optional_string(item.get("id")) == primary_id:
                return email
        for item in email_addresses:
            if not isinstance(item, dict):
                continue
            email = _clean_optional_string(item.get("email_address"))
            if email:
                return email
    return None


def _build_full_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [part for part in [first_name, last_name] if part]
    if not parts:
        return None
    return " ".join(parts)


def _build_user_profile_patch(clerk_user: dict[str, Any]) -> dict[str, Any]:
    first_name = _clean_optional_string(clerk_user.get("first_name"))
    last_name = _clean_optional_string(clerk_user.get("last_name"))
    full_name = _build_full_name(first_name, last_name)
    email = _extract_primary_email(clerk_user)
    avatar_url = _clean_optional_string(clerk_user.get("image_url"))

    patch: dict[str, Any] = {
        "id": str(clerk_user["id"]),
        "updated_at": _utc_now_iso(),
    }
    if email:
        patch["email"] = email
        patch["email_lower"] = email.casefold()
    if first_name:
        patch["first_name"] = first_name
    if last_name:
        patch["last_name"] = last_name
    if full_name:
        patch["full_name"] = full_name
    if avatar_url:
        patch["avatar_url"] = avatar_url
    return patch


async def _fetch_clerk_user(user_id: str, settings) -> dict[str, Any] | None:
    headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}
    url = f"https://api.clerk.dev/v1/users/{user_id}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
    except Exception as error:
        logger.error("Failed to fetch Clerk user %s: %s", user_id, error)
        return None

    if response.status_code == 404:
        logger.warning("Clerk user %s was not found; skipping profile backfill", user_id)
        return None

    if response.status_code >= 400:
        logger.error(
            "Clerk user fetch failed for %s: status %s body=%s",
            user_id,
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        payload = response.json()
    except Exception as error:
        logger.error("Invalid Clerk response for %s: %s", user_id, error)
        return None

    if not isinstance(payload, dict) or not payload.get("id"):
        logger.error("Unexpected Clerk payload for %s", user_id)
        return None
    return payload


async def _safe_select(db, table: str, *, filters: dict[str, Any] | None = None, columns: str = "*") -> list[dict[str, Any]]:
    try:
        return await db.select(table, filters=filters or {}, columns=columns)
    except Exception as error:
        logger.error("Select failed for %s filters=%s: %s", table, filters, error)
        return []


async def _safe_upsert(db, table: str, data: dict[str, Any]) -> bool:
    try:
        await db.upsert(table, data)
        return True
    except Exception as error:
        logger.error("Upsert failed for %s id=%s: %s", table, data.get("id"), error)
        return False


async def _safe_update(db, table: str, data: dict[str, Any], filters: dict[str, Any]) -> bool:
    try:
        await db.update(table, data, filters)
        return True
    except Exception as error:
        logger.error("Update failed for %s filters=%s: %s", table, filters, error)
        return False


async def _safe_delete(db, table: str, filters: dict[str, Any]) -> bool:
    try:
        await db.delete(table, filters)
        return True
    except Exception as error:
        logger.error("Delete failed for %s filters=%s: %s", table, filters, error)
        return False


async def _quarantine_row(
    db,
    *,
    source_collection: str,
    reason: str,
    record: dict[str, Any],
) -> bool:
    payload = {
        "source_collection": source_collection,
        "reason": reason,
        "record_id": record.get("id"),
        "user_id": record.get("user_id"),
        "integration_id": record.get("integration_id"),
        "quarantined_at": _utc_now_iso(),
        "record": record,
    }
    try:
        await db.insert(QUARANTINE_COLLECTION, payload)
        return True
    except Exception as error:
        logger.error(
            "Failed to quarantine %s row %s: %s",
            source_collection,
            record.get("id"),
            error,
        )
        return False


async def _collect_referenced_user_ids(db) -> set[str]:
    user_ids: set[str] = set()
    for collection in USER_SCOPED_COLLECTIONS:
        columns = "id" if collection == "users" else "user_id"
        rows = await _safe_select(db, collection, columns=columns)
        for row in rows:
            candidate = row.get("id") if collection == "users" else row.get("user_id")
            user_id = _clean_optional_string(candidate)
            if user_id:
                user_ids.add(user_id)
    return user_ids


async def _backfill_users_from_clerk(db, settings, summary: dict[str, int]) -> None:
    user_ids = sorted(await _collect_referenced_user_ids(db))
    logger.info("Found %s referenced user ids to backfill from Clerk", len(user_ids))
    for user_id in user_ids:
        clerk_user = await _fetch_clerk_user(user_id, settings)
        if not clerk_user:
            summary["users_skipped_no_clerk_profile"] += 1
            continue

        patch = _build_user_profile_patch(clerk_user)
        if await _safe_upsert(db, "users", patch):
            summary["users_backfilled"] += 1
            logger.info(
                "Backfilled user %s with email=%s full_name=%s",
                user_id,
                patch.get("email"),
                patch.get("full_name"),
            )


async def _repair_integration_owned_collections(db, summary: dict[str, int]) -> None:
    integrations = await _safe_select(db, "cloud_integrations")
    by_integration_id = {
        str(row.get("id") or ""): row
        for row in integrations
        if _clean_optional_string(row.get("id"))
    }

    for collection, has_provider in INTEGRATION_OWNED_COLLECTIONS:
        rows = await _safe_select(db, collection)
        for row in rows:
            row_id = _clean_optional_string(row.get("id"))
            integration_id = _clean_optional_string(row.get("integration_id"))
            if not row_id:
                continue

            if not integration_id:
                if collection == "daily_spend_history":
                    if await _quarantine_row(
                        db,
                        source_collection=collection,
                        reason="missing integration_id",
                        record=row,
                    ):
                        if await _safe_delete(db, collection, {"id": row_id}):
                            summary["daily_spend_rows_quarantined"] += 1
                continue

            parent = by_integration_id.get(integration_id)
            if not parent:
                if await _quarantine_row(
                    db,
                    source_collection=collection,
                    reason="orphaned integration reference",
                    record=row,
                ):
                    if await _safe_delete(db, collection, {"id": row_id}):
                        summary["orphaned_rows_quarantined"] += 1
                continue

            update_payload: dict[str, Any] = {}
            parent_user_id = _clean_optional_string(parent.get("user_id"))
            row_user_id = _clean_optional_string(row.get("user_id"))
            if parent_user_id and row_user_id != parent_user_id:
                update_payload["user_id"] = parent_user_id

            if has_provider:
                parent_provider = _clean_optional_string(parent.get("provider"))
                row_provider = _clean_optional_string(row.get("provider"))
                if parent_provider and row_provider != parent_provider:
                    update_payload["provider"] = parent_provider

            if update_payload and await _safe_update(db, collection, update_payload, {"id": row_id}):
                summary["ownership_rows_repaired"] += 1


async def _print_post_repair_summary(db) -> None:
    users = await _safe_select(db, "users")
    spend = await _safe_select(db, "daily_spend_history")
    integrations = await _safe_select(db, "cloud_integrations")
    print("Post-repair integrity snapshot:")
    print(
        f"- users missing email: {sum(1 for row in users if not _clean_optional_string(row.get('email')))}"
    )
    print(
        f"- users missing full_name: {sum(1 for row in users if not _clean_optional_string(row.get('full_name')))}"
    )
    print(
        f"- daily_spend_history rows missing integration_id: {sum(1 for row in spend if not _clean_optional_string(row.get('integration_id')))}"
    )
    print(f"- cloud_integrations total: {len(integrations)}")


async def main() -> int:
    settings = get_settings()
    db = get_db_client()
    summary: dict[str, int] = defaultdict(int)
    try:
        await _backfill_users_from_clerk(db, settings, summary)
        await _repair_integration_owned_collections(db, summary)
        try:
            await db._ensure_indexes()
        except Exception as error:
            logger.error("Index refresh failed after repair: %s", error)

        print("Repair summary:")
        print(f"- Users backfilled from Clerk: {summary['users_backfilled']}")
        print(f"- Users skipped (no Clerk profile): {summary['users_skipped_no_clerk_profile']}")
        print(f"- Ownership-linked child rows repaired: {summary['ownership_rows_repaired']}")
        print(f"- Invalid daily_spend_history rows quarantined: {summary['daily_spend_rows_quarantined']}")
        print(f"- Other orphaned rows quarantined: {summary['orphaned_rows_quarantined']}")
        await _print_post_repair_summary(db)
        print("MongoDB identity and ownership repair completed.")
        return 0
    finally:
        try:
            await db.close()
        except Exception as error:
            logger.error("Failed to close DB client cleanly: %s", error)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
