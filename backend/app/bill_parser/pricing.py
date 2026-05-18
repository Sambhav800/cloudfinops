"""
Cross-cloud pricing approximation helpers.
"""

from __future__ import annotations

from typing import Any

# Import canonical multipliers — single source of truth
from ..core.multicloud_comparison import _CATEGORY_MULTIPLIERS


def _normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in {"aws", "gcp", "azure"}:
        return normalized
    return "aws"


def _apply_discount(cost: float, discount_pct: float) -> float:
    bounded_discount = max(0.0, min(100.0, float(discount_pct)))
    return round(cost * (1.0 - bounded_discount / 100.0), 2)


def compute_cross_cloud_prices(
    by_category: dict[str, float],
    source_provider: str,
    aws_discount_pct: float = 0.0,
    gcp_discount_pct: float = 0.0,
    azure_discount_pct: float = 0.0,
) -> list[dict[str, Any]]:
    source = _normalize_provider(source_provider)
    discounts = {
        "aws": float(aws_discount_pct or 0.0),
        "gcp": float(gcp_discount_pct or 0.0),
        "azure": float(azure_discount_pct or 0.0),
    }

    opportunities: list[dict[str, Any]] = []

    for category, amount in by_category.items():
        spend = float(amount or 0.0)
        if spend <= 0:
            continue

        multipliers = _CATEGORY_MULTIPLIERS.get(category, _CATEGORY_MULTIPLIERS["Other"])
        source_multiplier = multipliers.get(source, 1.0)

        projected_costs: dict[str, float] = {}
        for cloud in ("aws", "gcp", "azure"):
            cloud_multiplier = multipliers.get(cloud, 1.0)
            equivalent = spend * (cloud_multiplier / source_multiplier if source_multiplier else 1.0)
            projected_costs[cloud] = _apply_discount(equivalent, discounts[cloud])

        current_cost = projected_costs[source]
        recommended_cloud = min(projected_costs, key=projected_costs.get)
        recommended_cost = projected_costs[recommended_cloud]
        savings = round(current_cost - recommended_cost, 2)
        savings_pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0.0

        opportunities.append(
            {
                "category": category,
                "current_cloud": source.upper(),
                "current_cost": current_cost,
                "all_cloud_costs": {
                    "AWS": projected_costs["aws"],
                    "GCP": projected_costs["gcp"],
                    "Azure": projected_costs["azure"],
                },
                "recommended_cloud": recommended_cloud.upper(),
                "recommended_cost": recommended_cost,
                "savings": savings,
                "savings_pct": savings_pct,
                "pricing_basis": "Public blended rate-card multipliers",
                "discounts_applied": {
                    "AWS": f"{discounts['aws']}%",
                    "GCP": f"{discounts['gcp']}%",
                    "Azure": f"{discounts['azure']}%",
                },
            }
        )

    opportunities.sort(key=lambda item: item.get("savings", 0), reverse=True)
    return opportunities


async def _fetch_live_azure_multiplier(category: str) -> float | None:
    """Attempt to fetch a live Azure price ratio for a category vs AWS baseline."""
    from ..core.price_service import price_service

    category_to_filter = {
        "Compute": (
            "serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' "
            "and armSkuName eq 'Standard_D4s_v5' and priceType eq 'Consumption'",
            "D4s v5",
            "Windows",
        ),
        "Storage": (
            "serviceName eq 'Storage' and armRegionName eq 'eastus' "
            "and skuName eq 'Hot LRS' and meterName eq 'Hot LRS Data Stored' "
            "and priceType eq 'Consumption'",
            None,
            None,
        ),
    }
    entry = category_to_filter.get(category)
    if not entry:
        return None
    filter_query, meter_name, exclude_product = entry
    try:
        price = await price_service.get_azure_price(
            filter_query, "eastus", meter_name=meter_name, exclude_product=exclude_product
        )
        if price and price > 0:
            return price
    except Exception:
        pass
    return None


async def _fetch_live_multipliers(by_category: dict[str, float]) -> dict[str, dict[str, float]]:
    """
    Try to fetch live pricing for key categories.
    Returns updated multipliers dict merged with static fallbacks.
    """
    from ..core.price_service import price_service

    live_multipliers: dict[str, dict[str, float]] = {}

    infracost_lookups = {
        "Compute": {
            "vendor": "aws",
            "service": "AmazonEC2",
            "product_family": "Compute Instance",
            "region": "us-east-1",
            "filters": [{"key": "instanceType", "value": "m5.xlarge"}],
        },
        "Storage": {
            "vendor": "aws",
            "service": "AmazonS3",
            "product_family": "Storage",
            "region": "us-east-1",
            "filters": [{"key": "volumeType", "value": "Standard"}],
        },
    }

    for category, lookup in infracost_lookups.items():
        if category not in by_category:
            continue
        try:
            aws_price = await price_service.get_infracost_price(
                vendor=lookup["vendor"],
                service=lookup["service"],
                product_family=lookup["product_family"],
                region=lookup["region"],
                filters=lookup["filters"],
            )
            if not aws_price or aws_price <= 0:
                continue

            azure_price = await _fetch_live_azure_multiplier(category)

            gcp_lookup = {
                "Compute": {
                    "vendor": "gcp",
                    "service": "Compute Engine",
                    "product_family": "Compute Instance",
                    "region": "us-central1",
                    "filters": [{"key": "machineType", "value": "n2-standard-4"}],
                },
                "Storage": {
                    "vendor": "gcp",
                    "service": "Cloud Storage",
                    "product_family": "Storage",
                    "region": "us-central1",
                    "filters": [{"key": "storageClass", "value": "Standard"}],
                },
            }
            gcp_price = None
            if category in gcp_lookup:
                gcp_price = await price_service.get_infracost_price(
                    vendor=gcp_lookup[category]["vendor"],
                    service=gcp_lookup[category]["service"],
                    product_family=gcp_lookup[category]["product_family"],
                    region=gcp_lookup[category]["region"],
                    filters=gcp_lookup[category]["filters"],
                )

            aws_mult = 1.0
            gcp_mult = round(gcp_price / aws_price, 4) if gcp_price and gcp_price > 0 else _CATEGORY_MULTIPLIERS.get(category, {}).get("gcp", 0.97)
            azure_mult = round(azure_price / aws_price, 4) if azure_price and azure_price > 0 else _CATEGORY_MULTIPLIERS.get(category, {}).get("azure", 1.05)

            live_multipliers[category] = {"aws": aws_mult, "gcp": gcp_mult, "azure": azure_mult}
        except Exception:
            continue

    return live_multipliers


async def fetch_cross_cloud_prices(
    by_category: dict[str, float],
    source_provider: str,
    aws_discount_pct: float = 0.0,
    gcp_discount_pct: float = 0.0,
    azure_discount_pct: float = 0.0,
) -> list[dict[str, Any]]:
    live_multipliers = await _fetch_live_multipliers(by_category)

    merged_multipliers = {**_CATEGORY_MULTIPLIERS}
    for category, mults in live_multipliers.items():
        merged_multipliers[category] = mults

    source = _normalize_provider(source_provider)
    discounts = {
        "aws": float(aws_discount_pct or 0.0),
        "gcp": float(gcp_discount_pct or 0.0),
        "azure": float(azure_discount_pct or 0.0),
    }

    opportunities: list[dict[str, Any]] = []

    for category, amount in by_category.items():
        spend = float(amount or 0.0)
        if spend <= 0:
            continue

        multipliers = merged_multipliers.get(category, merged_multipliers.get("Other", {"aws": 1.0, "gcp": 0.97, "azure": 1.01}))
        source_multiplier = multipliers.get(source, 1.0)
        pricing_basis = "Live API pricing" if category in live_multipliers else "Public blended rate-card multipliers"

        projected_costs: dict[str, float] = {}
        for cloud in ("aws", "gcp", "azure"):
            cloud_multiplier = multipliers.get(cloud, 1.0)
            equivalent = spend * (cloud_multiplier / source_multiplier if source_multiplier else 1.0)
            projected_costs[cloud] = _apply_discount(equivalent, discounts[cloud])

        current_cost = projected_costs[source]
        recommended_cloud = min(projected_costs, key=projected_costs.get)
        recommended_cost = projected_costs[recommended_cloud]
        savings = round(current_cost - recommended_cost, 2)
        savings_pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0.0

        opportunities.append(
            {
                "category": category,
                "current_cloud": source.upper(),
                "current_cost": current_cost,
                "all_cloud_costs": {
                    "AWS": projected_costs["aws"],
                    "GCP": projected_costs["gcp"],
                    "Azure": projected_costs["azure"],
                },
                "recommended_cloud": recommended_cloud.upper(),
                "recommended_cost": recommended_cost,
                "savings": savings,
                "savings_pct": savings_pct,
                "pricing_basis": pricing_basis,
                "discounts_applied": {
                    "AWS": f"{discounts['aws']}%",
                    "GCP": f"{discounts['gcp']}%",
                    "Azure": f"{discounts['azure']}%",
                },
            }
        )

    opportunities.sort(key=lambda item: item.get("savings", 0), reverse=True)
    return opportunities
