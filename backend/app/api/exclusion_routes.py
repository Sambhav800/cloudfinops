"""API routes for Resource Exclusion Shield — CRUD and suggestion management."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..db import MongoDBClient, get_db_client
from ..core.audit import log_audit_event

logger = logging.getLogger(__name__)

exclusion_router = APIRouter(prefix="/api/exclusions", tags=["Resource Exclusions"])

VALID_REASONS = {"seasonal", "disaster_recovery", "compliance", "batch_processing", "other"}
VALID_FREQUENCIES = {"quarterly", "semi_annual", "annual", "custom"}
VALID_MATCH_TYPES = {"tag", "name_pattern", "service_type", "region"}


# --- Request/Response Models ---


class UsageScheduleRequest(BaseModel):
    frequency: str = "quarterly"
    description: Optional[str] = None
    next_expected_active: Optional[str] = None


class CreateExclusionRequest(BaseModel):
    cloud_resource_id: str
    integration_id: str
    resource_name: Optional[str] = None
    provider: Optional[str] = None
    reason: str = "seasonal"
    reason_note: Optional[str] = None
    usage_schedule: Optional[UsageScheduleRequest] = None
    expires_in_days: int = Field(default=365, ge=30, le=1095)


class RuleMatchRequest(BaseModel):
    match_type: str
    tag_key: Optional[str] = None
    tag_value: Optional[str] = None
    pattern: Optional[str] = None
    service_type: Optional[str] = None
    region: Optional[str] = None


class CreateRuleExclusionRequest(BaseModel):
    rule_match: RuleMatchRequest
    reason: str = "seasonal"
    reason_note: Optional[str] = None
    usage_schedule: Optional[UsageScheduleRequest] = None
    expires_in_days: int = Field(default=365, ge=30, le=1095)


class UpdateExclusionRequest(BaseModel):
    reason: Optional[str] = None
    reason_note: Optional[str] = None
    usage_schedule: Optional[UsageScheduleRequest] = None
    expires_in_days: Optional[int] = Field(default=None, ge=30, le=1095)
    is_active: Optional[bool] = None


# --- Endpoints ---


@exclusion_router.post("")
async def create_exclusion(
    body: CreateExclusionRequest,
    user: ClerkUser = Depends(get_current_user),
):
    """Create an individual resource exclusion."""
    db = get_db_client()

    if body.reason not in VALID_REASONS:
        raise HTTPException(400, f"Invalid reason. Must be one of: {VALID_REASONS}")

    existing = await db.select(
        "resource_exclusions",
        filters={
            "user_id": user.id,
            "cloud_resource_id": body.cloud_resource_id,
            "integration_id": body.integration_id,
            "is_active": True,
        },
    )
    if existing:
        raise HTTPException(409, "An active exclusion already exists for this resource")

    now = datetime.now(timezone.utc)
    exclusion = {
        "id": str(uuid4()),
        "user_id": user.id,
        "type": "individual",
        "cloud_resource_id": body.cloud_resource_id,
        "integration_id": body.integration_id,
        "resource_name": body.resource_name,
        "provider": body.provider,
        "rule_match": None,
        "reason": body.reason,
        "reason_note": body.reason_note,
        "usage_schedule": body.usage_schedule.model_dump() if body.usage_schedule else None,
        "expires_at": (now + timedelta(days=body.expires_in_days)).isoformat(),
        "is_active": True,
        "created_at": now.isoformat(),
        "updated_at": None,
    }

    await db.insert("resource_exclusions", exclusion)

    await log_audit_event(
        user_id=user.id,
        action_type="EXCLUSION_CREATED",
        resource_target=body.cloud_resource_id,
        metadata={"exclusion_id": exclusion["id"], "reason": body.reason, "type": "individual"},
    )

    return {"status": "ok", "exclusion": exclusion}


@exclusion_router.post("/rule")
async def create_rule_exclusion(
    body: CreateRuleExclusionRequest,
    user: ClerkUser = Depends(get_current_user),
):
    """Create a rule-based (bulk) exclusion."""
    db = get_db_client()

    if body.reason not in VALID_REASONS:
        raise HTTPException(400, f"Invalid reason. Must be one of: {VALID_REASONS}")
    if body.rule_match.match_type not in VALID_MATCH_TYPES:
        raise HTTPException(400, f"Invalid match_type. Must be one of: {VALID_MATCH_TYPES}")

    now = datetime.now(timezone.utc)
    exclusion = {
        "id": str(uuid4()),
        "user_id": user.id,
        "type": "rule",
        "cloud_resource_id": None,
        "integration_id": None,
        "resource_name": None,
        "provider": None,
        "rule_match": body.rule_match.model_dump(),
        "reason": body.reason,
        "reason_note": body.reason_note,
        "usage_schedule": body.usage_schedule.model_dump() if body.usage_schedule else None,
        "expires_at": (now + timedelta(days=body.expires_in_days)).isoformat(),
        "is_active": True,
        "created_at": now.isoformat(),
        "updated_at": None,
    }

    await db.insert("resource_exclusions", exclusion)

    await log_audit_event(
        user_id=user.id,
        action_type="EXCLUSION_RULE_CREATED",
        resource_target=None,
        metadata={
            "exclusion_id": exclusion["id"],
            "reason": body.reason,
            "match_type": body.rule_match.match_type,
        },
    )

    return {"status": "ok", "exclusion": exclusion}


@exclusion_router.get("")
async def list_exclusions(
    type: Optional[str] = None,
    reason: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: ClerkUser = Depends(get_current_user),
):
    """List all exclusions for the current user."""
    db = get_db_client()
    filters: dict = {"user_id": user.id}

    if type in ("individual", "rule"):
        filters["type"] = type
    if reason and reason in VALID_REASONS:
        filters["reason"] = reason
    if is_active is not None:
        filters["is_active"] = is_active

    exclusions = await db.select("resource_exclusions", filters=filters)

    now = datetime.now(timezone.utc).isoformat()
    for exc in exclusions:
        exc["is_expired"] = (exc.get("expires_at") or "9999") < now

    return {"exclusions": exclusions, "count": len(exclusions)}


@exclusion_router.patch("/{exclusion_id}")
async def update_exclusion(
    exclusion_id: str,
    body: UpdateExclusionRequest,
    user: ClerkUser = Depends(get_current_user),
):
    """Update an exclusion's reason, schedule, or expiry."""
    db = get_db_client()

    existing = await db.select(
        "resource_exclusions",
        filters={"id": exclusion_id, "user_id": user.id},
    )
    if not existing:
        raise HTTPException(404, "Exclusion not found")

    updates: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if body.reason is not None:
        if body.reason not in VALID_REASONS:
            raise HTTPException(400, f"Invalid reason. Must be one of: {VALID_REASONS}")
        updates["reason"] = body.reason
    if body.reason_note is not None:
        updates["reason_note"] = body.reason_note
    if body.usage_schedule is not None:
        updates["usage_schedule"] = body.usage_schedule.model_dump()
    if body.expires_in_days is not None:
        created = existing[0].get("created_at", datetime.now(timezone.utc).isoformat())
        base = datetime.fromisoformat(created)
        updates["expires_at"] = (base + timedelta(days=body.expires_in_days)).isoformat()
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    await db.update("resource_exclusions", updates, filters={"id": exclusion_id})

    await log_audit_event(
        user_id=user.id,
        action_type="EXCLUSION_UPDATED",
        resource_target=existing[0].get("cloud_resource_id"),
        metadata={"exclusion_id": exclusion_id, "updates": list(updates.keys())},
    )

    return {"status": "ok"}


@exclusion_router.delete("/{exclusion_id}")
async def delete_exclusion(
    exclusion_id: str,
    user: ClerkUser = Depends(get_current_user),
):
    """Deactivate an exclusion (soft-delete)."""
    db = get_db_client()

    existing = await db.select(
        "resource_exclusions",
        filters={"id": exclusion_id, "user_id": user.id},
    )
    if not existing:
        raise HTTPException(404, "Exclusion not found")

    await db.update(
        "resource_exclusions",
        {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()},
        filters={"id": exclusion_id},
    )

    await log_audit_event(
        user_id=user.id,
        action_type="EXCLUSION_REMOVED",
        resource_target=existing[0].get("cloud_resource_id"),
        metadata={"exclusion_id": exclusion_id},
    )

    return {"status": "ok"}


# --- Suggestions ---


@exclusion_router.get("/suggestions")
async def list_suggestions(
    user: ClerkUser = Depends(get_current_user),
):
    """Get pending exclusion suggestions generated by the scanner."""
    db = get_db_client()
    suggestions = await db.select(
        "exclusion_suggestions",
        filters={"user_id": user.id, "status": "pending"},
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@exclusion_router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: str,
    body: CreateExclusionRequest,
    user: ClerkUser = Depends(get_current_user),
):
    """Convert a suggestion into an active exclusion."""
    db = get_db_client()

    suggestions = await db.select(
        "exclusion_suggestions",
        filters={"id": suggestion_id, "user_id": user.id},
    )
    if not suggestions:
        raise HTTPException(404, "Suggestion not found")

    await db.update(
        "exclusion_suggestions",
        {"status": "accepted", "updated_at": datetime.now(timezone.utc).isoformat()},
        filters={"id": suggestion_id},
    )

    response = await create_exclusion(body, user)
    return response


@exclusion_router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(
    suggestion_id: str,
    user: ClerkUser = Depends(get_current_user),
):
    """Dismiss a suggestion (won't be shown again for this resource)."""
    db = get_db_client()

    suggestions = await db.select(
        "exclusion_suggestions",
        filters={"id": suggestion_id, "user_id": user.id},
    )
    if not suggestions:
        raise HTTPException(404, "Suggestion not found")

    await db.update(
        "exclusion_suggestions",
        {"status": "dismissed", "updated_at": datetime.now(timezone.utc).isoformat()},
        filters={"id": suggestion_id},
    )

    return {"status": "ok"}


@exclusion_router.get("/stats")
async def exclusion_stats(
    user: ClerkUser = Depends(get_current_user),
):
    """Get summary stats for exclusions."""
    db = get_db_client()
    now = datetime.now(timezone.utc).isoformat()

    all_exclusions = await db.select(
        "resource_exclusions",
        filters={"user_id": user.id},
    )

    active = [e for e in all_exclusions if e.get("is_active")]
    rules = [e for e in active if e.get("type") == "rule"]
    expiring_soon = [
        e for e in active
        if e.get("expires_at") and e["expires_at"] < (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    ]

    suggestions = await db.select(
        "exclusion_suggestions",
        filters={"user_id": user.id, "status": "pending"},
    )

    return {
        "total_active": len(active),
        "rules_active": len(rules),
        "expiring_soon": len(expiring_soon),
        "pending_suggestions": len(suggestions),
    }
