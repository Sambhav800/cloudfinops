"""
Chart-ready analytics for the Total Bill dashboard.

The route remains the auth and ownership boundary. This module only reshapes
already-scoped integrations, resources, and spend history into deterministic
visual payloads.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

PROVIDER_KEYS = ("AWS", "AZURE", "GCP")


def _to_float(value: Any) -> float:
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _provider_key(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in PROVIDER_KEYS:
        return normalized
    return "UNKNOWN"


def _spend_date(value: Any) -> str:
    return str(value or "").strip()[:10]


def _date_window(days: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=max(days - 1, 0))
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days)]


def _category_for_service_type(service_type: Any) -> str:
    stype = str(service_type or "").lower()
    if any(keyword in stype for keyword in ["ec2", "compute", "vm", "instance", "container", "eks", "ecs", "gke", "aks", "function", "lambda", "run"]):
        return "Compute"
    if any(keyword in stype for keyword in ["rds", "sql", "database", "mongo", "cosmos", "spanner", "dynamo", "redis", "elastic"]):
        return "Database"
    if any(keyword in stype for keyword in ["s3", "storage", "blob", "bucket", "disk", "ebs"]):
        return "Storage"
    if any(keyword in stype for keyword in ["cloudfront", "cdn", "network", "vpc", "gateway", "lb", "balancer", "nat"]):
        return "Networking"
    if any(keyword in stype for keyword in ["sagemaker", "vertex", "ml", "ai", "bedrock", "gpu"]):
        return "AI / ML"
    return "Other"


def _resource_service_name(resource: dict[str, Any]) -> str:
    for key in ("service_type", "resource_type", "resource_name"):
        value = str(resource.get(key) or "").strip()
        if value:
            return value
    return "Unknown service"


def _resource_cost_source(resource: dict[str, Any]) -> str:
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    source = str(metadata.get("cost_source") or resource.get("cost_source") or "unknown").strip().lower()
    return source or "unknown"


def _round_money(value: float) -> float:
    return round(float(value or 0.0), 2)


def build_totalbill_visuals(
    *,
    active_integrations: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    history_by_integration: dict[str, list[dict[str, Any]]],
    days: int = 90,
) -> dict[str, Any]:
    """Build additive visual payloads for `/api/totalbill`."""
    integration_provider = {
        str(integration.get("id") or "").strip(): _provider_key(integration.get("provider"))
        for integration in active_integrations
        if str(integration.get("id") or "").strip()
    }
    active_integration_ids = set(integration_provider.keys())
    dates = _date_window(days)
    daily_by_date: dict[str, dict[str, float]] = {
        spend_date: {provider: 0.0 for provider in PROVIDER_KEYS}
        for spend_date in dates
    }

    for integration_id, history_rows in history_by_integration.items():
        provider = integration_provider.get(str(integration_id or "").strip(), "UNKNOWN")
        if provider not in PROVIDER_KEYS:
            continue
        for row in history_rows or []:
            spend_date = _spend_date(row.get("spend_date") or row.get("date"))
            if spend_date not in daily_by_date:
                continue
            daily_by_date[spend_date][provider] += _to_float(row.get("amount"))

    daily_provider_spend_90d = []
    for spend_date in dates:
        provider_amounts = daily_by_date[spend_date]
        total = sum(provider_amounts.values())
        daily_provider_spend_90d.append(
            {
                "spend_date": spend_date,
                "aws": _round_money(provider_amounts["AWS"]),
                "azure": _round_money(provider_amounts["AZURE"]),
                "gcp": _round_money(provider_amounts["GCP"]),
                "total": _round_money(total),
            }
        )

    max_daily_total = max((row["total"] for row in daily_provider_spend_90d), default=0.0)
    heatmap_days = [
        {
            "spend_date": row["spend_date"],
            "amount": row["total"],
            "intensity": round((row["total"] / max_daily_total), 4) if max_daily_total > 0 else 0.0,
        }
        for row in daily_provider_spend_90d
    ]

    daily_provider_spend_30d = daily_provider_spend_90d[-30:]
    active_providers = sorted(set(integration_provider.values()) & set(PROVIDER_KEYS))
    provider_forecasts = []
    for provider in active_providers:
        provider_key = provider.lower()
        provider_values = [
            _to_float(row.get(provider_key))
            for row in daily_provider_spend_30d
            if _to_float(row.get(provider_key)) > 0
        ]
        observed_total = sum(provider_values)
        forecast_monthly = (observed_total / len(provider_values) * 30) if provider_values else 0.0
        provider_forecasts.append(
            {
                "provider": provider,
                "forecast_monthly": _round_money(forecast_monthly),
                "forecast_annual": _round_money(forecast_monthly * 12),
                "history_days": len(provider_values),
                "forecast_source": "daily_spend_history_30d" if provider_values else "unavailable",
            }
        )

    service_rollup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for resource in resources or []:
        integration_id = str(resource.get("integration_id") or "").strip()
        if integration_id and integration_id not in active_integration_ids:
            continue

        provider = _provider_key(resource.get("provider") or integration_provider.get(integration_id))
        if provider not in PROVIDER_KEYS:
            continue

        value = _to_float(resource.get("cost"))
        if value <= 0:
            continue

        service = _resource_service_name(resource)
        category = _category_for_service_type(service)
        key = (category, service, provider)
        current = service_rollup.setdefault(
            key,
            {
                "category": category,
                "service": service,
                "provider": provider,
                "value": 0.0,
                "resource_count": 0,
                "cost_sources": set(),
            },
        )
        current["value"] += value
        current["resource_count"] += 1
        current["cost_sources"].add(_resource_cost_source(resource))

    hierarchy_by_category: dict[str, list[dict[str, Any]]] = {}
    flow_rows = []
    for item in service_rollup.values():
        child = {
            "name": f"{item['service']} ({item['provider']})",
            "service": item["service"],
            "provider": item["provider"],
            "value": _round_money(item["value"]),
            "resource_count": int(item["resource_count"]),
            "cost_sources": sorted(item["cost_sources"]),
        }
        hierarchy_by_category.setdefault(str(item["category"]), []).append(child)
        flow_rows.append(
            {
                "provider": item["provider"],
                "category": item["category"],
                "service": item["service"],
                "value": _round_money(item["value"]),
                "resource_count": int(item["resource_count"]),
                "cost_sources": sorted(item["cost_sources"]),
            }
        )

    service_hierarchy = []
    for category, children in hierarchy_by_category.items():
        sorted_children = sorted(children, key=lambda row: row["value"], reverse=True)
        service_hierarchy.append(
            {
                "name": category,
                "value": _round_money(sum(child["value"] for child in sorted_children)),
                "children": sorted_children[:10],
            }
        )
    service_hierarchy.sort(key=lambda row: row["value"], reverse=True)
    flow_rows.sort(key=lambda row: row["value"], reverse=True)

    return {
        "daily_provider_spend_30d": daily_provider_spend_30d,
        "heatmap_days": heatmap_days,
        "provider_forecasts": provider_forecasts,
        "service_hierarchy": service_hierarchy,
        "spend_flows": flow_rows[:15],
        "visual_currency": "INR",
        "visual_data_notes": [
            "Totals come from dashboard_stats for active integrations.",
            "Daily trend and heatmap values come from daily_spend_history.",
            "Service hierarchy and flow use resource-level cost signals with cost source labels.",
        ],
    }
