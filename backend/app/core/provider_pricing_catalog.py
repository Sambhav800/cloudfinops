"""Official provider pricing catalog sync and conservative resource estimates."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional
from uuid import uuid4

import httpx

from ..config import get_settings
from ..db import MongoDBClient

logger = logging.getLogger(__name__)

ProviderName = Literal["aws", "azure", "gcp"]

CATALOG_COLLECTION = "cloud_price_catalog"
CATALOG_SYNC_COLLECTION = "cloud_price_catalog_syncs"
CATALOG_COST_SOURCE = "catalog_estimate"
PROVIDER_CATALOG_SOURCE = "provider_catalog"
HOURS_PER_MONTH = 730.0
SUPPORTED_PROVIDERS = {"aws", "azure", "gcp"}
ESTIMATABLE_COST_SOURCES = {
    "",
    "billing_unavailable",
    "pricing_unavailable",
    "unknown",
    "estimated",
    CATALOG_COST_SOURCE,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _to_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if parsed != parsed else parsed


def _money_to_float(value: Dict[str, Any]) -> float:
    units = _to_float(value.get("units"))
    nanos = _to_float(value.get("nanos")) / 1_000_000_000
    return round(units + nanos, 12)


def _normalize_unit(value: Any) -> str:
    unit = _text(value)
    return unit or "unit"


def _is_hourly_unit(unit: str) -> bool:
    normalized = _lower(unit).replace(" ", "")
    return normalized in {"h", "hrs", "hr", "hour", "hours", "1hour"}


def _is_monthly_storage_unit(unit: str) -> bool:
    normalized = _lower(unit).replace(" ", "").replace("-", "").replace(".", "").replace("/", "")
    return normalized in {
        "gbmo",
        "gbmonth",
        "gibymo",
        "gibymonth",
        "gby.mo",
        "gibymo",
    } or (
        ("gb" in normalized or "gib" in normalized)
        and ("mo" in normalized or "month" in normalized)
    )


def _region_from_zone(provider: str, region: str) -> str:
    normalized = _lower(region)
    if provider == "gcp":
        parts = normalized.split("-")
        if len(parts) >= 3 and len(parts[-1]) == 1 and parts[-1].isalpha():
            return "-".join(parts[:-1])
    return normalized


def _catalog_key(parts: Iterable[Any]) -> str:
    return ":".join(_lower(part).replace(":", "_") for part in parts if _text(part))


def _safe_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 1000
    return max(1, min(parsed, 50_000))


@dataclass(frozen=True)
class CatalogEstimate:
    monthly_cost: float
    unit_price: float
    unit: str
    quantity: float
    catalog_record_id: str
    catalog_key: str
    confidence: float
    note: str
    currency: str = "USD"


class ProviderPricingCatalog:
    """Sync provider list-price catalogs and apply high-confidence estimates."""

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self._http_client = http_client

    async def sync_provider_catalog(
        self,
        db: MongoDBClient,
        provider: str,
        *,
        service_code: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 1000,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch official provider catalog records and store normalized SKU prices."""
        try:
            safe_provider = self._validate_provider(provider)
            safe_limit = _safe_limit(limit)
            sync_batch_id = str(uuid4())

            if safe_provider == "aws":
                records = await self._fetch_aws_catalog(service_code, region, safe_limit, sync_batch_id, credentials)
            elif safe_provider == "azure":
                records = await self._fetch_azure_catalog(service_code, region, safe_limit, sync_batch_id)
            else:
                records = await self._fetch_gcp_catalog(service_code, region, safe_limit, sync_batch_id, credentials)

            saved_rows = await db.upsert(CATALOG_COLLECTION, records) if records else []
            sync_summary = {
                "provider": safe_provider,
                "source": PROVIDER_CATALOG_SOURCE,
                "service_code": _text(service_code) or None,
                "region": _text(region) or None,
                "sync_batch_id": sync_batch_id,
                "records_seen": len(records),
                "records_saved": len(saved_rows),
                "status": "completed",
                "synced_at": _utc_now_iso(),
            }
            await db.upsert(CATALOG_SYNC_COLLECTION, sync_summary)
            return sync_summary
        except ValueError:
            raise
        except Exception as error:
            logger.error("Pricing catalog sync failed for %s: %s", provider, error)
            raise

    async def apply_catalog_estimates(
        self,
        db: MongoDBClient,
        user_id: str,
        *,
        integration_id: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Apply catalog estimates to user resources without overwriting actual costs."""
        try:
            safe_limit = _safe_limit(limit)
            resources = await db.get_resources(user_id, integration_id)
            updated = 0
            processed = 0
            skipped_actual = 0
            unmatched = 0
            samples: List[Dict[str, Any]] = []

            for resource in resources:
                if updated >= safe_limit:
                    break
                processed += 1

                metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
                cost_source = _lower(metadata.get("cost_source"))
                if cost_source in {"actual", "no_direct_charge", "included", "free"}:
                    skipped_actual += 1
                    continue

                if cost_source not in ESTIMATABLE_COST_SOURCES and _to_float(resource.get("cost")) > 0:
                    skipped_actual += 1
                    continue

                estimate = await self.estimate_resource_monthly_cost(db, resource)
                if estimate is None:
                    unmatched += 1
                    continue

                updated_metadata = {
                    **metadata,
                    "cost_source": CATALOG_COST_SOURCE,
                    "cost_basis": "provider_market_list_price",
                    "pricing_source": PROVIDER_CATALOG_SOURCE,
                    "catalog_price_id": estimate.catalog_record_id,
                    "catalog_key": estimate.catalog_key,
                    "catalog_unit": estimate.unit,
                    "catalog_unit_price": estimate.unit_price,
                    "catalog_quantity": estimate.quantity,
                    "currency": estimate.currency,
                    "catalog_confidence": estimate.confidence,
                    "actual_billing_required": True,
                    "pricing_note": estimate.note,
                }
                filters = self._resource_update_filter(user_id, resource)
                if not filters:
                    unmatched += 1
                    continue

                await db.update(
                    "resources",
                    {
                        "cost": round(estimate.monthly_cost, 4),
                        "metadata": updated_metadata,
                    },
                    filters,
                )
                updated += 1
                if len(samples) < 5:
                    samples.append(
                        {
                            "resource_id": resource.get("id"),
                            "resource_name": resource.get("resource_name"),
                            "monthly_cost": round(estimate.monthly_cost, 4),
                            "catalog_key": estimate.catalog_key,
                        }
                    )

            return {
                "updated": updated,
                "skipped_actual": skipped_actual,
                "unmatched": unmatched,
                "processed": processed,
                "samples": samples,
            }
        except Exception as error:
            logger.error("Applying pricing catalog estimates failed: %s", error)
            raise

    async def estimate_resource_monthly_cost(
        self,
        db: MongoDBClient,
        resource: Dict[str, Any],
    ) -> Optional[CatalogEstimate]:
        """Return a conservative monthly estimate for one scanned resource."""
        try:
            provider = _lower(resource.get("provider"))
            if provider not in SUPPORTED_PROVIDERS:
                return None

            service_type = _lower(resource.get("service_type") or resource.get("resource_type"))
            metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
            region_source = resource.get("region") or metadata.get("zone")
            if provider == "aws" and _lower(region_source) in {"", "global"}:
                region_source = metadata.get("aws_region") or metadata.get("region")
            region = _region_from_zone(provider, _text(region_source))

            if provider == "aws":
                return await self._estimate_aws_resource(db, service_type, region, metadata)
            if provider == "azure":
                return await self._estimate_azure_resource(db, service_type, region, metadata)
            return await self._estimate_gcp_resource(db, service_type, region, metadata)
        except Exception as error:
            logger.warning("Catalog estimate lookup failed: %s", error)
            return None

    async def get_sync_status(self, db: MongoDBClient) -> Dict[str, Any]:
        """Return latest sync metadata without scanning the full price collection."""
        try:
            rows = await db.select(CATALOG_SYNC_COLLECTION)
            rows.sort(key=lambda item: str(item.get("synced_at") or item.get("updated_at") or ""), reverse=True)
            return {"syncs": rows[:20], "count": len(rows)}
        except Exception as error:
            logger.error("Pricing catalog status lookup failed: %s", error)
            raise

    def normalize_azure_retail_item(self, item: Dict[str, Any], sync_batch_id: str) -> Optional[Dict[str, Any]]:
        unit_price = _to_float(item.get("retailPrice", item.get("unitPrice")))
        sku = _text(item.get("skuId") or item.get("meterId"))
        meter_id = _text(item.get("meterId") or sku)
        region = _lower(item.get("armRegionName") or item.get("location") or "global")
        unit = _normalize_unit(item.get("unitOfMeasure"))
        if not sku or unit_price < 0:
            return None

        record = {
            "provider": "azure",
            "source": "azure_retail_prices_api",
            "catalog_key": _catalog_key(["azure", sku, meter_id, region, unit, item.get("type")]),
            "service_code": _text(item.get("serviceName")),
            "service_name": _text(item.get("serviceName")),
            "service_family": _text(item.get("serviceFamily")),
            "product_family": _text(item.get("productName")),
            "sku": sku,
            "meter_id": meter_id,
            "rate_code": meter_id,
            "region": region or "global",
            "location": _text(item.get("location")),
            "currency": _text(item.get("currencyCode") or "USD"),
            "unit": unit,
            "unit_price": unit_price,
            "price_per_month": round(unit_price * HOURS_PER_MONTH, 8) if _is_hourly_unit(unit) else unit_price,
            "effective_date": _text(item.get("effectiveStartDate")),
            "description": _text(item.get("meterName") or item.get("productName")),
            "attributes": {
                "armSkuName": item.get("armSkuName"),
                "skuName": item.get("skuName"),
                "meterName": item.get("meterName"),
                "priceType": item.get("type"),
                "isPrimaryMeterRegion": item.get("isPrimaryMeterRegion"),
            },
            "sync_batch_id": sync_batch_id,
        }
        return record

    def normalize_aws_price_product(
        self,
        price_product: Dict[str, Any],
        service_code: str,
        sync_batch_id: str,
    ) -> List[Dict[str, Any]]:
        product = price_product.get("product") if isinstance(price_product.get("product"), dict) else {}
        attributes = product.get("attributes") if isinstance(product.get("attributes"), dict) else {}
        sku = _text(product.get("sku") or price_product.get("sku"))
        terms = price_product.get("terms") if isinstance(price_product.get("terms"), dict) else {}
        on_demand = terms.get("OnDemand") if isinstance(terms.get("OnDemand"), dict) else {}
        records: List[Dict[str, Any]] = []

        for term in on_demand.values():
            if not isinstance(term, dict):
                continue
            price_dimensions = term.get("priceDimensions")
            if not isinstance(price_dimensions, dict):
                continue
            for dimension in price_dimensions.values():
                if not isinstance(dimension, dict):
                    continue
                price_per_unit = dimension.get("pricePerUnit")
                if not isinstance(price_per_unit, dict):
                    continue
                currency = next(iter(price_per_unit.keys()), "USD")
                unit_price = _to_float(price_per_unit.get(currency))
                unit = _normalize_unit(dimension.get("unit"))
                rate_code = _text(dimension.get("rateCode") or term.get("sku") or sku)
                region = _lower(attributes.get("regionCode") or attributes.get("location") or "global")
                if not sku or not rate_code or unit_price < 0:
                    continue
                records.append(
                    {
                        "provider": "aws",
                        "source": "aws_price_list_api",
                        "catalog_key": _catalog_key(["aws", service_code, sku, rate_code, region, unit, currency]),
                        "service_code": _text(service_code),
                        "service_name": _text(attributes.get("servicename") or service_code),
                        "service_family": _text(product.get("productFamily")),
                        "product_family": _text(product.get("productFamily")),
                        "sku": sku,
                        "meter_id": rate_code,
                        "rate_code": rate_code,
                        "region": region or "global",
                        "location": _text(attributes.get("location")),
                        "currency": _text(currency),
                        "unit": unit,
                        "unit_price": unit_price,
                        "price_per_month": round(unit_price * HOURS_PER_MONTH, 8) if _is_hourly_unit(unit) else unit_price,
                        "effective_date": _text(term.get("effectiveDate")),
                        "usage_type": _text(attributes.get("usagetype")),
                        "operation": _text(attributes.get("operation")),
                        "description": _text(dimension.get("description")),
                        "attributes": attributes,
                        "sync_batch_id": sync_batch_id,
                    }
                )
        return records

    def normalize_gcp_sku(
        self,
        service: Dict[str, Any],
        sku: Dict[str, Any],
        sync_batch_id: str,
    ) -> List[Dict[str, Any]]:
        category = sku.get("category") if isinstance(sku.get("category"), dict) else {}
        pricing_infos = sku.get("pricingInfo") if isinstance(sku.get("pricingInfo"), list) else []
        if not pricing_infos:
            return []

        latest_pricing = pricing_infos[-1] if isinstance(pricing_infos[-1], dict) else {}
        expression = latest_pricing.get("pricingExpression") if isinstance(latest_pricing.get("pricingExpression"), dict) else {}
        tiered_rates = expression.get("tieredRates") if isinstance(expression.get("tieredRates"), list) else []
        service_regions = sku.get("serviceRegions") if isinstance(sku.get("serviceRegions"), list) else ["global"]
        regions = [_lower(region or "global") for region in service_regions] or ["global"]
        records: List[Dict[str, Any]] = []

        for tier in tiered_rates:
            if not isinstance(tier, dict):
                continue
            unit_price_payload = tier.get("unitPrice") if isinstance(tier.get("unitPrice"), dict) else {}
            currency = _text(unit_price_payload.get("currencyCode") or "USD")
            unit_price = _money_to_float(unit_price_payload)
            unit = _normalize_unit(expression.get("usageUnit") or expression.get("baseUnit"))
            start_usage = _text(tier.get("startUsageAmount") or 0)
            for region in regions:
                sku_id = _text(sku.get("skuId"))
                rate_code = _catalog_key([sku_id, start_usage, unit])
                if not sku_id or unit_price < 0:
                    continue
                records.append(
                    {
                        "provider": "gcp",
                        "source": "gcp_cloud_billing_catalog_api",
                        "catalog_key": _catalog_key(["gcp", service.get("serviceId"), sku_id, rate_code, region, currency]),
                        "service_code": _text(service.get("serviceId")),
                        "service_name": _text(service.get("displayName") or category.get("serviceDisplayName")),
                        "service_family": _text(category.get("resourceFamily")),
                        "product_family": _text(category.get("resourceFamily")),
                        "sku": sku_id,
                        "meter_id": rate_code,
                        "rate_code": rate_code,
                        "region": region or "global",
                        "location": region or "global",
                        "currency": currency,
                        "unit": unit,
                        "unit_price": unit_price,
                        "price_per_month": unit_price,
                        "effective_date": _text(latest_pricing.get("effectiveTime")),
                        "resource_family": _text(category.get("resourceFamily")),
                        "resource_group": _text(category.get("resourceGroup")),
                        "usage_type": _text(category.get("usageType")),
                        "description": _text(sku.get("description")),
                        "attributes": {
                            "usageUnitDescription": expression.get("usageUnitDescription"),
                            "baseUnit": expression.get("baseUnit"),
                            "baseUnitDescription": expression.get("baseUnitDescription"),
                            "displayQuantity": expression.get("displayQuantity"),
                            "startUsageAmount": start_usage,
                        },
                        "sync_batch_id": sync_batch_id,
                    }
                )
        return records

    async def _estimate_aws_resource(
        self,
        db: MongoDBClient,
        service_type: str,
        region: str,
        metadata: Dict[str, Any],
    ) -> Optional[CatalogEstimate]:
        try:
            if "ec2" in service_type or "instance" in service_type:
                instance_type = _text(metadata.get("instance_type"))
                if not instance_type:
                    return None
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="aws",
                    service_code="AmazonEC2",
                    region=region,
                )
                matches = []
                platform = _lower(metadata.get("platform") or "Linux")
                for row in candidates:
                    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
                    if _text(attrs.get("instanceType")) != instance_type:
                        continue
                    if not _is_hourly_unit(_text(row.get("unit"))):
                        continue
                    if attrs.get("tenancy") and _lower(attrs.get("tenancy")) != "shared":
                        continue
                    operating_system = _lower(attrs.get("operatingSystem"))
                    if "windows" in platform and operating_system and "windows" not in operating_system:
                        continue
                    if "windows" not in platform and operating_system and "linux" not in operating_system:
                        continue
                    matches.append(row)
                return self._estimate_from_lowest_hourly(matches, 1.0, "AWS EC2 on-demand list price from provider catalog.")

            if "ebs" in service_type or "volume" in service_type:
                size_gb = _to_float(metadata.get("size_gb"))
                if size_gb <= 0:
                    return None
                volume_type = _lower(metadata.get("volume_type"))
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="aws",
                    service_code="AmazonEC2",
                    region=region,
                )
                matches = []
                for row in candidates:
                    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
                    text_blob = " ".join(
                        [
                            _lower(row.get("product_family")),
                            _lower(row.get("usage_type")),
                            _lower(row.get("description")),
                            _lower(attrs.get("volumeType")),
                        ]
                    )
                    if "storage" not in text_blob or not _is_monthly_storage_unit(_text(row.get("unit"))):
                        continue
                    if volume_type and volume_type not in text_blob:
                        continue
                    matches.append(row)
                return self._estimate_from_lowest_unit(matches, size_gb, "AWS EBS GB-month list price from provider catalog.")
            return None
        except Exception as error:
            logger.warning("AWS catalog estimate failed: %s", error)
            return None

    async def _estimate_azure_resource(
        self,
        db: MongoDBClient,
        service_type: str,
        region: str,
        metadata: Dict[str, Any],
    ) -> Optional[CatalogEstimate]:
        try:
            if "virtual machine" in service_type or "vm" in service_type:
                vm_size = _text(metadata.get("vm_size") or metadata.get("instance_type"))
                if not vm_size:
                    return None
                expected_skus = {vm_size}
                if not vm_size.lower().startswith("standard_"):
                    expected_skus.add(f"Standard_{vm_size}")
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="azure",
                    service_code="Virtual Machines",
                    region=region,
                )
                matches = []
                for row in candidates:
                    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
                    if _text(attrs.get("armSkuName")) not in expected_skus:
                        continue
                    text_blob = f"{_lower(row.get('description'))} {_lower(row.get('product_family'))} {_lower(attrs.get('priceType'))}"
                    if "spot" in text_blob or "reservation" in text_blob or "low priority" in text_blob:
                        continue
                    if not _is_hourly_unit(_text(row.get("unit"))):
                        continue
                    matches.append(row)
                return self._estimate_from_lowest_hourly(matches, 1.0, "Azure VM consumption list price from provider catalog.")

            if "managed disk" in service_type or "disk" in service_type:
                size_gb = _to_float(metadata.get("size_gb") or metadata.get("disk_size_gb"))
                if size_gb <= 0:
                    return None
                sku_name = _lower(metadata.get("sku"))
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="azure",
                    service_code="Storage",
                    region=region,
                )
                matches = []
                for row in candidates:
                    text_blob = f"{_lower(row.get('description'))} {_lower(row.get('product_family'))}"
                    if "disk" not in text_blob:
                        continue
                    if sku_name and sku_name not in text_blob:
                        continue
                    if not _is_monthly_storage_unit(_text(row.get("unit"))):
                        continue
                    matches.append(row)
                return self._estimate_from_lowest_unit(matches, size_gb, "Azure managed disk GB-month list price from provider catalog.")
            return None
        except Exception as error:
            logger.warning("Azure catalog estimate failed: %s", error)
            return None

    async def _estimate_gcp_resource(
        self,
        db: MongoDBClient,
        service_type: str,
        region: str,
        metadata: Dict[str, Any],
    ) -> Optional[CatalogEstimate]:
        try:
            if "compute instance" in service_type or "virtual machine" in service_type or " vm" in f" {service_type}":
                machine_type = _text(metadata.get("machine_type") or metadata.get("instance_type"))
                if not machine_type:
                    return None
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="gcp",
                    service_code=None,
                    region=region,
                )
                micro_match = self._estimate_gcp_micro_instance(candidates, machine_type)
                if micro_match is not None:
                    return micro_match
                return self._estimate_gcp_core_ram_instance(candidates, machine_type)

            if "persistent disk" in service_type or "snapshot" in service_type:
                size_gb = _to_float(metadata.get("size_gb"))
                if size_gb <= 0:
                    return None
                disk_type = _lower(metadata.get("type") or "pd-standard")
                candidates = await self._select_catalog_candidates(
                    db,
                    provider="gcp",
                    service_code=None,
                    region=region,
                )
                matches = []
                for row in candidates:
                    text_blob = " ".join(
                        [
                            _lower(row.get("service_name")),
                            _lower(row.get("description")),
                            _lower(row.get("resource_group")),
                            _lower(row.get("unit")),
                        ]
                    )
                    if "storage" not in text_blob and "disk" not in text_blob and "pd capacity" not in text_blob:
                        continue
                    if not self._gcp_disk_type_matches(disk_type, text_blob):
                        continue
                    if not _is_monthly_storage_unit(_text(row.get("unit"))):
                        continue
                    matches.append(row)
                return self._estimate_from_lowest_unit(matches, size_gb, "GCP disk GB-month list price from provider catalog.")
            return None
        except Exception as error:
            logger.warning("GCP catalog estimate failed: %s", error)
            return None

    async def _select_catalog_candidates(
        self,
        db: MongoDBClient,
        *,
        provider: str,
        service_code: Optional[str],
        region: str,
    ) -> List[Dict[str, Any]]:
        try:
            filters: Dict[str, Any] = {"provider": provider}
            if service_code:
                filters["service_code"] = service_code
            rows = await db.select(CATALOG_COLLECTION, filters=filters)
            normalized_region = _region_from_zone(provider, region)
            return [
                row for row in rows
                if self._region_matches(provider, _text(row.get("region")), normalized_region)
            ]
        except Exception as error:
            logger.warning("Catalog candidate query failed: %s", error)
            return []

    async def _fetch_azure_catalog(
        self,
        service_code: Optional[str],
        region: Optional[str],
        limit: int,
        sync_batch_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            records: List[Dict[str, Any]] = []
            filters = []
            if service_code:
                filters.append(f"serviceName eq '{service_code}'")
            if region:
                filters.append(f"armRegionName eq '{region}'")
            params = {"$filter": " and ".join(filters)} if filters else None
            url = "https://prices.azure.com/api/retail/prices"

            async with self._client() as client:
                while url and len(records) < limit:
                    response = await self._get_json_with_retry(client, url, params=params)
                    params = None
                    for item in response.get("Items", []):
                        if not isinstance(item, dict):
                            continue
                        record = self.normalize_azure_retail_item(item, sync_batch_id)
                        if record:
                            records.append(record)
                            if len(records) >= limit:
                                break
                    url = response.get("NextPageLink") if isinstance(response.get("NextPageLink"), str) else None
            return records
        except Exception as error:
            logger.error("Azure retail price catalog fetch failed: %s", error)
            raise

    async def _fetch_gcp_catalog(
        self,
        service_code: Optional[str],
        region: Optional[str],
        limit: int,
        sync_batch_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            api_key = self._gcp_catalog_api_key()
            auth_headers = None
            if not api_key:
                auth_headers = await asyncio.to_thread(self._gcp_catalog_auth_headers, credentials)
            if not api_key and not auth_headers:
                raise ValueError(
                    "GCP catalog sync requires GCP_BILLING_CATALOG_API_KEY, GOOGLE_API_KEY, "
                    "or a stored GCP service-account integration"
                )

            records: List[Dict[str, Any]] = []
            async with self._client() as client:
                services = await self._fetch_gcp_services(client, api_key, auth_headers, service_code)
                for service in services:
                    if len(records) >= limit:
                        break
                    page_token = ""
                    while len(records) < limit:
                        params: Dict[str, Any] = {"pageSize": 5000}
                        if api_key:
                            params["key"] = api_key
                        if page_token:
                            params["pageToken"] = page_token
                        url = f"https://cloudbilling.googleapis.com/v1/services/{service['serviceId']}/skus"
                        response = await self._get_json_with_retry(client, url, params=params, headers=auth_headers)
                        for sku in response.get("skus", []):
                            if not isinstance(sku, dict):
                                continue
                            for record in self.normalize_gcp_sku(service, sku, sync_batch_id):
                                if region and not self._region_matches("gcp", record.get("region"), region):
                                    continue
                                records.append(record)
                                if len(records) >= limit:
                                    break
                            if len(records) >= limit:
                                break
                        page_token = _text(response.get("nextPageToken"))
                        if not page_token:
                            break
            return records
        except Exception as error:
            logger.error("GCP public billing catalog fetch failed: %s", error)
            raise

    async def _fetch_aws_catalog(
        self,
        service_code: Optional[str],
        region: Optional[str],
        limit: int,
        sync_batch_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            return await asyncio.to_thread(
                self._fetch_aws_catalog_sync,
                service_code,
                region,
                limit,
                sync_batch_id,
                credentials,
            )
        except Exception as error:
            logger.error("AWS price list catalog fetch failed: %s", error)
            raise

    def _fetch_aws_catalog_sync(
        self,
        service_code: Optional[str],
        region: Optional[str],
        limit: int,
        sync_batch_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        import boto3

        client_kwargs: Dict[str, Any] = {"region_name": "us-east-1"}
        if credentials:
            access_key_id = _text(credentials.get("access_key_id"))
            secret_access_key = _text(credentials.get("secret_access_key"))
            if access_key_id and secret_access_key:
                client_kwargs.update(
                    {
                        "aws_access_key_id": access_key_id,
                        "aws_secret_access_key": secret_access_key,
                    }
                )
        client = boto3.client("pricing", **client_kwargs)
        service_codes = [_text(service_code)] if service_code else self._aws_service_codes(client, limit)
        records: List[Dict[str, Any]] = []

        for code in service_codes:
            if not code or len(records) >= limit:
                continue
            next_token: Optional[str] = None
            while len(records) < limit:
                request: Dict[str, Any] = {
                    "ServiceCode": code,
                    "FormatVersion": "aws_v1",
                    "MaxResults": min(100, limit - len(records)),
                }
                if region:
                    request["Filters"] = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": region}]
                if next_token:
                    request["NextToken"] = next_token
                response = client.get_products(**request)
                for raw_item in response.get("PriceList", []):
                    try:
                        payload = json.loads(raw_item) if isinstance(raw_item, str) else raw_item
                    except json.JSONDecodeError:
                        continue
                    records.extend(self.normalize_aws_price_product(payload, code, sync_batch_id))
                    if len(records) >= limit:
                        break
                next_token = response.get("NextToken")
                if not next_token:
                    break
        return records[:limit]

    def _aws_service_codes(self, client: Any, limit: int) -> List[str]:
        codes: List[str] = []
        next_token: Optional[str] = None
        while len(codes) < limit:
            request: Dict[str, Any] = {"MaxResults": 100}
            if next_token:
                request["NextToken"] = next_token
            response = client.describe_services(**request)
            for service in response.get("Services", []):
                code = _text(service.get("ServiceCode"))
                if code:
                    codes.append(code)
                    if len(codes) >= limit:
                        break
            next_token = response.get("NextToken")
            if not next_token:
                break
        return codes

    async def _fetch_gcp_services(
        self,
        client: httpx.AsyncClient,
        api_key: Optional[str],
        auth_headers: Optional[Dict[str, str]],
        service_code: Optional[str],
    ) -> List[Dict[str, Any]]:
        try:
            if service_code:
                return [{"serviceId": service_code, "displayName": service_code}]

            services: List[Dict[str, Any]] = []
            page_token = ""
            while True:
                params: Dict[str, Any] = {}
                if api_key:
                    params["key"] = api_key
                if page_token:
                    params["pageToken"] = page_token
                response = await self._get_json_with_retry(
                    client,
                    "https://cloudbilling.googleapis.com/v1/services",
                    params=params,
                    headers=auth_headers,
                )
                for service in response.get("services", []):
                    if isinstance(service, dict) and service.get("serviceId"):
                        services.append(service)
                page_token = _text(response.get("nextPageToken"))
                if not page_token:
                    break
            return services
        except Exception as error:
            logger.error("GCP public billing catalog service discovery failed: %s", error)
            raise

    async def _get_json_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except httpx.HTTPError as error:
                last_error = error
                if attempt == 2:
                    break
                await asyncio.sleep(1)
        raise RuntimeError(f"Provider pricing API request failed: {last_error}")

    def _client(self):
        if self._http_client is not None:
            return _ExternalClientContext(self._http_client)
        return httpx.AsyncClient(timeout=30.0)

    def _gcp_catalog_api_key(self) -> Optional[str]:
        try:
            configured = get_settings().gcp_billing_catalog_api_key
        except Exception as error:
            logger.warning("Could not read GCP catalog API key from settings: %s", error)
            configured = None
        return configured or os.getenv("GOOGLE_API_KEY")

    def _gcp_catalog_auth_headers(self, credentials: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        try:
            if not credentials:
                return None
            project_id = _text(credentials.get("project_id"))
            service_account_email = _text(credentials.get("service_account_email"))
            private_key = _text(credentials.get("private_key")).replace("\\n", "\n")
            if not project_id or not service_account_email or not private_key:
                return None

            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            scoped_credentials = service_account.Credentials.from_service_account_info(
                {
                    "type": "service_account",
                    "project_id": project_id,
                    "private_key": private_key,
                    "client_email": service_account_email,
                    "token_uri": "https://oauth2.googleapis.com/token",
                },
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            scoped_credentials.refresh(Request())
            token = _text(scoped_credentials.token)
            if not token:
                return None
            return {"Authorization": f"Bearer {token}"}
        except Exception as error:
            logger.warning("GCP catalog service-account authentication failed: %s", error)
            return None

    def _validate_provider(self, provider: str) -> ProviderName:
        normalized = _lower(provider)
        if normalized not in SUPPORTED_PROVIDERS:
            raise ValueError("provider must be one of: aws, azure, gcp")
        return normalized  # type: ignore[return-value]

    def _resource_update_filter(self, user_id: str, resource: Dict[str, Any]) -> Dict[str, Any]:
        resource_id = _text(resource.get("id"))
        if resource_id:
            return {"user_id": user_id, "id": resource_id}
        integration_id = _text(resource.get("integration_id"))
        cloud_resource_id = _text(resource.get("cloud_resource_id"))
        if integration_id and cloud_resource_id:
            return {
                "user_id": user_id,
                "integration_id": integration_id,
                "cloud_resource_id": cloud_resource_id,
            }
        return {}

    def _region_matches(self, provider: str, record_region: Any, resource_region: Any) -> bool:
        wanted = _region_from_zone(provider, _text(resource_region))
        candidate = _region_from_zone(provider, _text(record_region))
        return not wanted or candidate in {wanted, "global", ""}

    def _gcp_disk_type_matches(self, disk_type: str, text_blob: str) -> bool:
        normalized = _lower(disk_type)
        if not normalized:
            return True
        if normalized == "pd-balanced":
            return "balanced pd capacity" in text_blob or "pd-balanced" in text_blob
        if normalized == "pd-ssd":
            return (
                ("ssd backed pd capacity" in text_blob or "pd-ssd" in text_blob)
                and "balanced" not in text_blob
                and "extreme" not in text_blob
                and "regional" not in text_blob
            )
        if normalized == "pd-standard":
            return (
                ("pd capacity" in text_blob or "pd-standard" in text_blob)
                and "balanced" not in text_blob
                and "ssd" not in text_blob
                and "extreme" not in text_blob
                and "regional" not in text_blob
            )
        return normalized.replace("pd-", "") in text_blob

    def _estimate_gcp_micro_instance(
        self,
        rows: List[Dict[str, Any]],
        machine_type: str,
    ) -> Optional[CatalogEstimate]:
        if not _lower(machine_type).endswith("micro"):
            return None
        matches = []
        for row in rows:
            if _lower(row.get("usage_type")) != "ondemand":
                continue
            if not _is_hourly_unit(_text(row.get("unit"))):
                continue
            text_blob = f"{_lower(row.get('description'))} {_lower(row.get('resource_group'))}"
            if "micro instance" in text_blob and "preemptible" not in text_blob:
                matches.append(row)
        return self._estimate_from_lowest_hourly(matches, 1.0, "GCP micro instance on-demand list price from provider catalog.")

    def _estimate_gcp_core_ram_instance(
        self,
        rows: List[Dict[str, Any]],
        machine_type: str,
    ) -> Optional[CatalogEstimate]:
        shape = self._gcp_machine_shape(machine_type)
        if shape is None:
            return None
        family, vcpus, memory_gb = shape
        cpu_rows = []
        ram_rows = []
        for row in rows:
            if _lower(row.get("usage_type")) != "ondemand":
                continue
            description = _lower(row.get("description"))
            if family not in description or "custom" in description or "preemptible" in description:
                continue
            resource_group = _lower(row.get("resource_group"))
            unit = _lower(row.get("unit")).replace(" ", "")
            if resource_group == "cpu" and _is_hourly_unit(row.get("unit")):
                cpu_rows.append(row)
            if resource_group == "ram" and unit in {"giby.h", "gibyh", "gb.h", "gbh"}:
                ram_rows.append(row)

        cpu_row = min(
            [row for row in cpu_rows if _to_float(row.get("unit_price")) > 0],
            key=lambda row: _to_float(row.get("unit_price")),
            default=None,
        )
        ram_row = min(
            [row for row in ram_rows if _to_float(row.get("unit_price")) > 0],
            key=lambda row: _to_float(row.get("unit_price")),
            default=None,
        )
        if not cpu_row or not ram_row:
            return None

        cpu_hourly = _to_float(cpu_row.get("unit_price")) * vcpus
        ram_hourly = _to_float(ram_row.get("unit_price")) * memory_gb
        monthly_cost = round((cpu_hourly + ram_hourly) * HOURS_PER_MONTH, 6)
        return CatalogEstimate(
            monthly_cost=monthly_cost,
            unit_price=round(cpu_hourly + ram_hourly, 12),
            unit="h",
            quantity=HOURS_PER_MONTH,
            catalog_record_id=f"{_text(cpu_row.get('id'))}+{_text(ram_row.get('id'))}",
            catalog_key=f"{_text(cpu_row.get('catalog_key'))}+{_text(ram_row.get('catalog_key'))}",
            confidence=0.72,
            note="GCP instance CPU and RAM on-demand list prices from provider catalog.",
            currency=_text(cpu_row.get("currency") or ram_row.get("currency") or "USD"),
        )

    def _gcp_machine_shape(self, machine_type: str) -> Optional[tuple[str, float, float]]:
        normalized = _lower(machine_type).split("/")[-1]
        known_shapes = {
            "e2-small": ("e2", 2.0, 2.0),
            "e2-medium": ("e2", 2.0, 4.0),
        }
        if normalized in known_shapes:
            return known_shapes[normalized]
        parts = normalized.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            family = parts[0]
            vcpus = _to_float(parts[-1])
            if vcpus <= 0:
                return None
            shape = parts[-2]
            if shape == "standard":
                return family, vcpus, vcpus * 4.0
            if shape == "highmem":
                return family, vcpus, vcpus * 8.0
            if shape == "highcpu":
                return family, vcpus, vcpus * 1.0
        return None

    def _estimate_from_lowest_hourly(
        self,
        rows: List[Dict[str, Any]],
        quantity: float,
        note: str,
    ) -> Optional[CatalogEstimate]:
        hourly_rows = [row for row in rows if _is_hourly_unit(_text(row.get("unit")))]
        return self._estimate_from_lowest_unit(hourly_rows, quantity * HOURS_PER_MONTH, note)

    def _estimate_from_lowest_unit(
        self,
        rows: List[Dict[str, Any]],
        quantity: float,
        note: str,
    ) -> Optional[CatalogEstimate]:
        positive_rows = [row for row in rows if _to_float(row.get("unit_price")) > 0]
        if not positive_rows or quantity <= 0:
            return None
        selected = min(positive_rows, key=lambda row: _to_float(row.get("unit_price")))
        unit_price = _to_float(selected.get("unit_price"))
        monthly_cost = round(unit_price * quantity, 6)
        return CatalogEstimate(
            monthly_cost=monthly_cost,
            unit_price=unit_price,
            unit=_text(selected.get("unit")),
            quantity=quantity,
            catalog_record_id=_text(selected.get("id")),
            catalog_key=_text(selected.get("catalog_key")),
            confidence=0.78,
            note=note,
            currency=_text(selected.get("currency") or "USD"),
        )


class _ExternalClientContext:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


pricing_catalog = ProviderPricingCatalog()
