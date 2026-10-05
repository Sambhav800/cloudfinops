"""Scan-time exclusion shield application and suggestion generation."""

import logging
from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

from ..db import MongoDBClient
from .rule_engine import matches_any_exclusion

logger = logging.getLogger(__name__)

_ZOMBIE_STATUSES = {"zombie", "waste", "idle", "non_compliant"}
_SUGGESTION_THRESHOLD = 3


async def apply_exclusion_shields(
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
) -> Tuple[int, float]:
    """
    Apply active exclusion shields to zombie resources post-scan.

    Returns (excluded_count, excluded_savings) for stats adjustment.
    """
    now = datetime.now(timezone.utc).isoformat()

    exclusions = await db.select(
        "resource_exclusions",
        filters={"user_id": user_id, "is_active": True},
    )
    active_exclusions = [
        exc for exc in exclusions
        if (exc.get("expires_at") or "9999") > now
    ]

    if not active_exclusions:
        return 0, 0.0

    resources = await db.select(
        "resources",
        filters={"user_id": user_id, "integration_id": integration_id},
    )

    excluded_count = 0
    excluded_savings = 0.0

    for resource in resources:
        status = str(resource.get("status") or "").lower()
        if status not in _ZOMBIE_STATUSES:
            continue

        matching_exclusion = matches_any_exclusion(resource, active_exclusions)
        if not matching_exclusion:
            continue

        metadata = resource.get("metadata") or {}
        metadata["excluded"] = True
        metadata["exclusion_id"] = matching_exclusion.get("id", "")
        metadata["exclusion_reason"] = matching_exclusion.get("reason", "")

        await db.update(
            "resources",
            {"metadata": metadata},
            filters={"id": resource["id"]},
        )

        excluded_count += 1
        excluded_savings += float(resource.get("cost") or 0)

    if excluded_count > 0:
        logger.info(
            "Exclusion shield applied: %d resources shielded (%.2f savings excluded) for user=%s integration=%s",
            excluded_count, excluded_savings, user_id, integration_id,
        )

    return excluded_count, excluded_savings


async def generate_exclusion_suggestions(
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
) -> int:
    """
    After scan, check for resources that have been zombie 3+ consecutive scans
    and generate exclusion suggestions if none exist.

    Returns count of new suggestions created.
    """
    resources = await db.select(
        "resources",
        filters={"user_id": user_id, "integration_id": integration_id},
    )

    new_suggestions = 0

    for resource in resources:
        status = str(resource.get("status") or "").lower()
        metadata = resource.get("metadata") or {}

        if status in _ZOMBIE_STATUSES:
            consecutive = int(metadata.get("consecutive_zombie_scans") or 0) + 1
            metadata["consecutive_zombie_scans"] = consecutive
            await db.update(
                "resources",
                {"metadata": metadata},
                filters={"id": resource["id"]},
            )

            if consecutive >= _SUGGESTION_THRESHOLD and not metadata.get("excluded"):
                created = await _maybe_create_suggestion(db, user_id, resource, consecutive)
                if created:
                    new_suggestions += 1
        else:
            if metadata.get("consecutive_zombie_scans"):
                metadata["consecutive_zombie_scans"] = 0
                await db.update(
                    "resources",
                    {"metadata": metadata},
                    filters={"id": resource["id"]},
                )

    return new_suggestions


async def _maybe_create_suggestion(
    db: MongoDBClient,
    user_id: str,
    resource: dict,
    consecutive_count: int,
) -> bool:
    """Create a suggestion if one doesn't already exist for this resource."""
    cloud_resource_id = resource.get("cloud_resource_id", "")
    integration_id = resource.get("integration_id", "")

    existing = await db.select(
        "exclusion_suggestions",
        filters={
            "user_id": user_id,
            "cloud_resource_id": cloud_resource_id,
            "integration_id": integration_id,
            "status": "pending",
        },
    )
    if existing:
        return False

    suggestion = {
        "id": str(uuid4()),
        "user_id": user_id,
        "cloud_resource_id": cloud_resource_id,
        "integration_id": integration_id,
        "resource_name": resource.get("resource_name", ""),
        "provider": resource.get("provider", ""),
        "suggestion_type": "repeated_zombie",
        "consecutive_zombie_scans": consecutive_count,
        "suggested_reason": "seasonal",
        "suggested_schedule": None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.insert("exclusion_suggestions", suggestion)
    return True
