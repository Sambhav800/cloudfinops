"""
Discount Manager API routes.

Provides endpoints for the three-tier discount calculator,
template CRUD, and scan-data prefill.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.clerk import ClerkUser, get_current_user
from ..db import MongoDBClient, get_db_client
from ..core.discount_engine import (
    calculate_discount_model,
    categorize_resources_for_discount,
    get_default_services,
    get_sample_data,
    DEFAULT_TIER1_BY_CATEGORY,
    _PROVIDER_SERVICES,
)
from ..core.live_pricing_engine import (
    compute_live_multipliers,
    get_current_multipliers,
    is_critically_stale,
)

logger = logging.getLogger(__name__)
discount_router = APIRouter(prefix="/api/discount-manager", tags=["discount-manager"])

TEMPLATES_COLLECTION = "discount_templates"


class ServiceInput(BaseModel):
    category: str
    source_monthly: float = 0.0
    tier1_discount_pct: Optional[float] = None


class CalculateRequest(BaseModel):
    services: List[ServiceInput]
    source_provider: str = "aws"
    target_provider: str = "gcp"
    tier2_volume_pct: float = 0.0
    tier3_negotiated_pct: float = 0.0


class TemplateSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_provider: str = "aws"
    target_provider: str = "gcp"
    services: List[Dict[str, Any]] = Field(default_factory=list)
    tier2_volume_pct: float = 0.0
    tier3_negotiated_pct: float = 0.0


@discount_router.get("/defaults")
async def get_defaults(
    source_provider: str = "aws",
    user: ClerkUser = Depends(get_current_user),
):
    """Return default service list with categories and tier1 discount rates."""
    services = get_default_services(source_provider)
    return {
        "source_provider": source_provider,
        "services": services,
        "tier1_defaults": DEFAULT_TIER1_BY_CATEGORY,
        "providers": ["aws", "gcp", "azure"],
        "provider_services": _PROVIDER_SERVICES,
    }


@discount_router.get("/sample-data")
async def get_sample(
    source_provider: str = "aws",
    user: ClerkUser = Depends(get_current_user),
):
    """Return sample cost data for demo purposes."""
    return {
        "source_provider": source_provider,
        "services": get_sample_data(source_provider),
    }


@discount_router.get("/prefill")
async def prefill_from_scan(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Pre-populate discount calculator from user's scanned resource data."""
    resources = await db.get_resources(user.id, integration_id)
    if not resources:
        return {
            "has_data": False,
            "source_provider": "aws",
            "category_spend": {},
            "services": get_sample_data("aws"),
            "message": "No scan data found. Showing sample data.",
        }

    providers = {}
    for r in resources:
        p = str(r.get("provider", "")).lower()
        if p in ("aws", "gcp", "azure"):
            providers[p] = providers.get(p, 0) + 1

    source_provider = max(providers, key=providers.get) if providers else "aws"
    category_spend = categorize_resources_for_discount(resources)

    services = get_default_services(source_provider)
    for svc in services:
        spend = category_spend.get(svc["category"], 0.0)
        svc["source_monthly"] = spend

    return {
        "has_data": True,
        "source_provider": source_provider,
        "category_spend": category_spend,
        "services": services,
        "resource_count": len(resources),
    }


@discount_router.post("/calculate")
async def calculate(
    body: CalculateRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Run the three-tier discount calculation with live pricing multipliers."""
    if body.source_provider == body.target_provider:
        raise HTTPException(400, "Source and target provider must be different")

    pricing_data = await get_current_multipliers(db)

    services_dicts = [s.model_dump() for s in body.services]
    result = calculate_discount_model(
        services=services_dicts,
        source_provider=body.source_provider,
        target_provider=body.target_provider,
        tier2_volume_pct=body.tier2_volume_pct,
        tier3_negotiated_pct=body.tier3_negotiated_pct,
        multipliers_override=pricing_data.get("multipliers"),
    )

    result["pricing_metadata"] = {
        "pricing_basis_per_category": pricing_data.get("pricing_basis_per_category", {}),
        "computed_at": pricing_data.get("computed_at", ""),
        "sources_used": pricing_data.get("sources_used", []),
        "is_stale": is_critically_stale(pricing_data.get("computed_at", "")),
    }
    result["instance_pricing"] = pricing_data.get("instance_pricing", {})

    return result


@discount_router.get("/templates")
async def list_templates(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """List all discount templates for the current user."""
    templates = await db.select(TEMPLATES_COLLECTION, filters={"user_id": user.id})
    for t in templates:
        t.pop("_id", None)
    return {"templates": templates, "count": len(templates)}


@discount_router.post("/templates")
async def save_template(
    body: TemplateSaveRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Save a new discount template."""
    existing = await db.select(TEMPLATES_COLLECTION, filters={"user_id": user.id})
    if len(existing) >= 20:
        raise HTTPException(400, "Maximum 20 templates allowed. Delete one first.")

    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": template_id,
        "user_id": user.id,
        "name": body.name,
        "source_provider": body.source_provider,
        "target_provider": body.target_provider,
        "services": body.services,
        "tier2_volume_pct": body.tier2_volume_pct,
        "tier3_negotiated_pct": body.tier3_negotiated_pct,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert(TEMPLATES_COLLECTION, record)
    return {"id": template_id, "message": "Template saved", "template": record}


@discount_router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Get a specific template by ID."""
    results = await db.select(
        TEMPLATES_COLLECTION, filters={"id": template_id, "user_id": user.id}
    )
    if not results:
        raise HTTPException(404, "Template not found")
    result = results[0]
    result.pop("_id", None)
    return result


@discount_router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateSaveRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Update an existing template."""
    results = await db.select(
        TEMPLATES_COLLECTION, filters={"id": template_id, "user_id": user.id}
    )
    if not results:
        raise HTTPException(404, "Template not found")

    update_data = {
        "name": body.name,
        "source_provider": body.source_provider,
        "target_provider": body.target_provider,
        "services": body.services,
        "tier2_volume_pct": body.tier2_volume_pct,
        "tier3_negotiated_pct": body.tier3_negotiated_pct,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.update(TEMPLATES_COLLECTION, update_data, filters={"id": template_id, "user_id": user.id})
    return {"id": template_id, "message": "Template updated"}


@discount_router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Delete a template."""
    results = await db.select(
        TEMPLATES_COLLECTION, filters={"id": template_id, "user_id": user.id}
    )
    if not results:
        raise HTTPException(404, "Template not found")

    await db.delete(TEMPLATES_COLLECTION, filters={"id": template_id, "user_id": user.id})
    return {"id": template_id, "message": "Template deleted"}


@discount_router.get("/pricing-status")
async def get_pricing_status(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Return current pricing data freshness and source breakdown."""
    pricing_data = await get_current_multipliers(db)
    computed_at = pricing_data.get("computed_at", "")
    return {
        "computed_at": computed_at,
        "sources_used": pricing_data.get("sources_used", []),
        "pricing_basis_per_category": pricing_data.get("pricing_basis_per_category", {}),
        "instance_pricing": pricing_data.get("instance_pricing", {}),
        "multipliers": pricing_data.get("multipliers", {}),
        "is_stale": is_critically_stale(computed_at),
        "live_count": pricing_data.get("live_count", 0),
        "partial_count": pricing_data.get("partial_count", 0),
        "static_count": pricing_data.get("static_count", 0),
    }


@discount_router.post("/refresh-pricing")
async def refresh_pricing(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Manually trigger a live pricing refresh. Rate-limited to prevent abuse."""
    pricing_data = await compute_live_multipliers(db, force_refresh=True)
    return {
        "status": "refreshed",
        "computed_at": pricing_data.get("computed_at", ""),
        "live_count": pricing_data.get("live_count", 0),
        "partial_count": pricing_data.get("partial_count", 0),
        "static_count": pricing_data.get("static_count", 0),
        "computation_time_seconds": pricing_data.get("computation_time_seconds", 0),
        "sources_used": pricing_data.get("sources_used", []),
    }
