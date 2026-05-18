"""
Community Verified Pricing Pool.

Aggregates real billing data from users who have Cost Explorer / Cost Management
enabled, and provides verified market prices for users who don't. This ensures
no resource ever shows $0 in the dashboard.

Privacy: Only anonymous aggregate pricing is stored — no raw user IDs, no
individual billing details. Contributors identified by SHA-256 hash only.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..db import MongoDBClient

logger = logging.getLogger(__name__)

COLLECTION = "community_verified_prices"
COST_SOURCE_COMMUNITY = "verified_community_price"
MIN_SAMPLES_FOR_USE = 1
MAX_SAMPLES_TRACKED = 200


@dataclass(frozen=True)
class CommunityPriceEstimate:
    monthly_cost: float
    sample_count: int
    confidence: float
    resource_config_key: str
    note: str


def _normalize_instance_type(raw: str) -> str:
    return str(raw or "").strip().lower().replace(" ", "_")


def _normalize_region(raw: str) -> str:
    region = str(raw or "").strip().lower()
    parts = region.split("-")
    if len(parts) >= 3 and len(parts[-1]) == 1 and parts[-1].isalpha():
        return "-".join(parts[:-1])
    return region


def _normalize_service_type(raw: str) -> str:
    service = str(raw or "").strip().lower()
    service = re.sub(r"^(aws|azure|gcp)\s+", "", service)
    return service.replace(" ", "_")


def build_resource_config_key(
    provider: str,
    service_type: str,
    instance_type: str,
    region: str,
    platform: str = "",
) -> str:
    parts = [
        str(provider or "").strip().lower(),
        _normalize_service_type(service_type),
        _normalize_instance_type(instance_type),
        _normalize_region(region),
    ]
    if platform:
        parts.append(str(platform).strip().lower())
    return ":".join(part for part in parts if part)


def _extract_config_key_from_resource(resource: Dict[str, Any]) -> Optional[str]:
    provider = str(resource.get("provider") or "").strip().lower()
    service_type = str(resource.get("service_type") or resource.get("resource_type") or "")
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}

    instance_type = str(
        metadata.get("instance_type")
        or metadata.get("instance_class")
        or metadata.get("machine_type")
        or metadata.get("vm_size")
        or metadata.get("sku")
        or metadata.get("volume_type")
        or metadata.get("storage_class")
        or metadata.get("tier")
        or ""
    ).strip()

    region = str(
        metadata.get("aws_region")
        or resource.get("region")
        or metadata.get("location")
        or metadata.get("region")
        or resource.get("region_compliance")
        or ""
    ).strip()

    if not service_type or not region:
        return None

    platform = str(metadata.get("platform") or metadata.get("os") or "").strip()

    return build_resource_config_key(provider, service_type, instance_type, region, platform)


def _hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


async def contribute_verified_prices(
    db: MongoDBClient,
    user_id: str,
    resources: List[Dict[str, Any]],
) -> Dict[str, int]:
    contributed = 0
    skipped = 0
    contributor_hash = _hash_user_id(user_id)

    for resource in resources:
        metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
        cost_source = str(metadata.get("cost_source") or "").strip().lower()
        cost = float(resource.get("cost") or 0)

        if cost_source != "actual" or cost <= 0:
            skipped += 1
            continue

        config_key = _extract_config_key_from_resource(resource)
        if not config_key:
            skipped += 1
            continue

        try:
            existing = await db.select(COLLECTION, filters={"resource_config_key": config_key})
            record = existing[0] if existing else None

            now = datetime.now(timezone.utc).isoformat()

            if record:
                samples = record.get("samples") or []
                contributors = record.get("contributors") or []

                if contributor_hash in contributors and len(samples) > 3:
                    existing_from_user = [
                        s for s in samples
                        if s.get("contributor") == contributor_hash
                    ]
                    if existing_from_user:
                        for s in existing_from_user:
                            s["cost"] = cost
                            s["updated_at"] = now
                    else:
                        samples.append({"cost": cost, "contributor": contributor_hash, "updated_at": now})
                else:
                    samples.append({"cost": cost, "contributor": contributor_hash, "updated_at": now})
                    if contributor_hash not in contributors:
                        contributors.append(contributor_hash)

                samples = samples[-MAX_SAMPLES_TRACKED:]
                costs = [s["cost"] for s in samples if s.get("cost", 0) > 0]
                median_cost = sorted(costs)[len(costs) // 2] if costs else cost

                await db.update(
                    COLLECTION,
                    {
                        "samples": samples,
                        "contributors": contributors,
                        "sample_count": len(costs),
                        "monthly_cost_median": round(median_cost, 4),
                        "last_contributed_at": now,
                        "confidence": min(0.95, 0.6 + (len(costs) * 0.05)),
                    },
                    filters={"resource_config_key": config_key},
                )
            else:
                provider = str(resource.get("provider") or "").lower()
                service_type = str(resource.get("service_type") or "")
                instance_type = str(
                    metadata.get("instance_type")
                    or metadata.get("instance_class")
                    or metadata.get("machine_type")
                    or metadata.get("vm_size")
                    or ""
                )
                region = str(
                    metadata.get("aws_region")
                    or resource.get("region")
                    or metadata.get("location")
                    or ""
                )

                await db.insert(COLLECTION, {
                    "resource_config_key": config_key,
                    "provider": provider,
                    "service_type": service_type,
                    "instance_type": instance_type,
                    "region": region,
                    "monthly_cost_median": round(cost, 4),
                    "sample_count": 1,
                    "confidence": 0.65,
                    "samples": [{"cost": cost, "contributor": contributor_hash, "updated_at": now}],
                    "contributors": [contributor_hash],
                    "first_seen_at": now,
                    "last_contributed_at": now,
                    "currency": "USD",
                })

            contributed += 1
        except Exception as error:
            logger.debug("Community pool contribution failed for %s: %s", config_key, error)
            skipped += 1

    if contributed > 0:
        logger.info("Community pricing pool: contributed %d prices, skipped %d", contributed, skipped)

    return {"contributed": contributed, "skipped": skipped}


async def lookup_community_price(
    db: MongoDBClient,
    resource: Dict[str, Any],
) -> Optional[CommunityPriceEstimate]:
    config_key = _extract_config_key_from_resource(resource)
    if not config_key:
        return None

    try:
        results = await db.select(COLLECTION, filters={"resource_config_key": config_key})
        if not results:
            return None

        record = results[0]
        sample_count = int(record.get("sample_count") or 0)
        if sample_count < MIN_SAMPLES_FOR_USE:
            return None

        median_cost = float(record.get("monthly_cost_median") or 0)
        if median_cost <= 0:
            return None

        confidence = float(record.get("confidence") or 0.6)

        return CommunityPriceEstimate(
            monthly_cost=median_cost,
            sample_count=sample_count,
            confidence=confidence,
            resource_config_key=config_key,
            note=f"Based on {sample_count} verified billing sample(s) from the CloudFinOps community pool",
        )
    except Exception as error:
        logger.debug("Community price lookup failed for %s: %s", config_key, error)
        return None


async def apply_community_estimates(
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
    limit: int = 500,
) -> Dict[str, int]:
    updated = 0
    unmatched = 0

    try:
        resources = await db.get_resources(user_id, integration_id)
    except Exception as error:
        logger.warning("Community estimates: failed to load resources: %s", error)
        return {"updated": 0, "unmatched": 0}

    estimatable_sources = {"", "billing_unavailable", "pricing_unavailable", "unknown"}

    for resource in resources:
        if updated >= limit:
            break

        metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
        cost_source = str(metadata.get("cost_source") or "").strip().lower()
        current_cost = float(resource.get("cost") or 0)

        if cost_source in {"actual", "catalog_estimate", COST_SOURCE_COMMUNITY}:
            continue
        if cost_source not in estimatable_sources and current_cost > 0:
            continue

        estimate = await lookup_community_price(db, resource)
        if not estimate:
            unmatched += 1
            continue

        updated_metadata = {
            **metadata,
            "cost_source": COST_SOURCE_COMMUNITY,
            "cost_basis": "community_verified_market_price",
            "community_sample_count": estimate.sample_count,
            "community_confidence": estimate.confidence,
            "community_config_key": estimate.resource_config_key,
            "pricing_note": estimate.note,
            "actual_billing_required": True,
        }

        filters = {"user_id": user_id, "integration_id": integration_id}
        resource_id = resource.get("id") or resource.get("cloud_resource_id")
        if resource_id:
            filters["cloud_resource_id"] = resource_id

        try:
            await db.update(
                "resources",
                {"cost": round(estimate.monthly_cost, 4), "metadata": updated_metadata},
                filters,
            )
            updated += 1
        except Exception as error:
            logger.debug("Community estimate update failed: %s", error)
            unmatched += 1

    if updated > 0:
        logger.info(
            "Community estimates applied: integration=%s updated=%d unmatched=%d",
            integration_id, updated, unmatched,
        )

    return {"updated": updated, "unmatched": unmatched}
