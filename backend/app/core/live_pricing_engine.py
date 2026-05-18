"""
Live Pricing Engine — fetches real cloud pricing from multiple sources.

Sources (in priority order):
1. Infracost GraphQL API (AWS + GCP on-demand pricing)
2. Azure Retail Prices API (no key needed)
3. MongoDB cloud_price_catalog (synced catalog data)
4. Static fallback (_CATEGORY_MULTIPLIERS from multicloud_comparison.py)

Computes real cost multipliers between AWS/GCP/Azure for each service category.
Stores results in MongoDB `live_pricing_multipliers` collection.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..db import MongoDBClient
from .price_service import price_service
from .multicloud_comparison import _CATEGORY_MULTIPLIERS

logger = logging.getLogger(__name__)

MULTIPLIERS_COLLECTION = "live_pricing_multipliers"
MULTIPLIERS_DOC_ID = "live_multipliers_latest"
STALENESS_THRESHOLD_HOURS = 24
STALE_CRITICAL_HOURS = 48

INSTANCE_EQUIVALENCE_MAP: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Compute": {
        "tier_a": {
            "label": "4 vCPU / 16 GB",
            "aws": {
                "instance": "m5.xlarge",
                "vcpu": 4,
                "memory_gb": 16,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonEC2",
                    "product_family": "Compute Instance",
                    "region": "us-east-1",
                    "filters": [
                        {"key": "instanceType", "value": "m5.xlarge"},
                        {"key": "operatingSystem", "value": "Linux"},
                        {"key": "tenancy", "value": "Shared"},
                        {"key": "preInstalledSw", "value": "NA"},
                        {"key": "capacitystatus", "value": "Used"},
                    ],
                },
            },
            "gcp": {
                "instance": "n2-standard-4",
                "vcpu": 4,
                "memory_gb": 16,
                "infracost": {
                    "vendor": "gcp",
                    "service": "Compute Engine",
                    "product_family": "Compute Instance",
                    "region": "us-central1",
                    "filters": [{"key": "machineType", "value": "n2-standard-4"}],
                },
            },
            "azure": {
                "instance": "D4s_v5",
                "vcpu": 4,
                "memory_gb": 16,
                "azure_filter": (
                    "serviceName eq 'Virtual Machines' and "
                    "armRegionName eq 'eastus' and "
                    "armSkuName eq 'Standard_D4s_v5' and "
                    "priceType eq 'Consumption'"
                ),
                "azure_filter_meter": "D4s v5",
                "azure_exclude_product": "Windows",
            },
        },
        "tier_b": {
            "label": "8 vCPU / 32 GB",
            "aws": {
                "instance": "m5.2xlarge",
                "vcpu": 8,
                "memory_gb": 32,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonEC2",
                    "product_family": "Compute Instance",
                    "region": "us-east-1",
                    "filters": [
                        {"key": "instanceType", "value": "m5.2xlarge"},
                        {"key": "operatingSystem", "value": "Linux"},
                        {"key": "tenancy", "value": "Shared"},
                        {"key": "preInstalledSw", "value": "NA"},
                        {"key": "capacitystatus", "value": "Used"},
                    ],
                },
            },
            "gcp": {
                "instance": "n2-standard-8",
                "vcpu": 8,
                "memory_gb": 32,
                "infracost": {
                    "vendor": "gcp",
                    "service": "Compute Engine",
                    "product_family": "Compute Instance",
                    "region": "us-central1",
                    "filters": [{"key": "machineType", "value": "n2-standard-8"}],
                },
            },
            "azure": {
                "instance": "D8s_v5",
                "vcpu": 8,
                "memory_gb": 32,
                "azure_filter": (
                    "serviceName eq 'Virtual Machines' and "
                    "armRegionName eq 'eastus' and "
                    "armSkuName eq 'Standard_D8s_v5' and "
                    "priceType eq 'Consumption'"
                ),
                "azure_filter_meter": "D8s v5",
                "azure_exclude_product": "Windows",
            },
        },
    },
    "Database": {
        "tier_a": {
            "label": "4 vCPU / 16 GB",
            "aws": {
                "instance": "db.m5.xlarge",
                "vcpu": 4,
                "memory_gb": 16,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonRDS",
                    "product_family": "Database Instance",
                    "region": "us-east-1",
                    "filters": [
                        {"key": "instanceType", "value": "db.m5.xlarge"},
                        {"key": "databaseEngine", "value": "PostgreSQL"},
                    ],
                },
            },
            "gcp": {
                "instance": "db-custom-4-16384",
                "vcpu": 4,
                "memory_gb": 16,
            },
            "azure": {
                "instance": "GP Ddsv5 4-vCore",
                "vcpu": 4,
                "memory_gb": 16,
                "azure_filter": (
                    "serviceName eq 'Azure Database for PostgreSQL' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq '4 vCore' and "
                    "priceType eq 'Consumption' and "
                    "contains(productName, 'General Purpose') and contains(productName, 'Ddsv5')"
                ),
            },
        },
        "tier_b": {
            "label": "8 vCPU / 32 GB",
            "aws": {
                "instance": "db.m5.2xlarge",
                "vcpu": 8,
                "memory_gb": 32,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonRDS",
                    "product_family": "Database Instance",
                    "region": "us-east-1",
                    "filters": [
                        {"key": "instanceType", "value": "db.m5.2xlarge"},
                        {"key": "databaseEngine", "value": "PostgreSQL"},
                    ],
                },
            },
            "gcp": {
                "instance": "db-custom-8-32768",
                "vcpu": 8,
                "memory_gb": 32,
            },
            "azure": {
                "instance": "GP Ddsv5 8-vCore",
                "vcpu": 8,
                "memory_gb": 32,
                "azure_filter": (
                    "serviceName eq 'Azure Database for PostgreSQL' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq '8 vCore' and "
                    "priceType eq 'Consumption' and "
                    "contains(productName, 'General Purpose') and contains(productName, 'Ddsv5')"
                ),
            },
        },
    },
    "Storage": {
        "tier_a": {
            "label": "Standard Object Storage (per GB/month)",
            "aws": {
                "instance": "S3 Standard",
                "unit": "GB/month",
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonS3",
                    "product_family": "Storage",
                    "region": "us-east-1",
                    "filters": [{"key": "volumeType", "value": "Standard"}],
                },
            },
            "gcp": {
                "instance": "Cloud Storage Standard",
                "unit": "GB/month",
            },
            "azure": {
                "instance": "Blob Hot LRS",
                "unit": "GB/month",
                "azure_filter": (
                    "serviceName eq 'Storage' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq 'Hot LRS' and "
                    "meterName eq 'Hot LRS Data Stored' and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "Kubernetes": {
        "tier_a": {
            "label": "4 vCPU node + cluster fee",
            "aws": {
                "instance": "EKS + m5.xlarge",
                "vcpu": 4,
                "memory_gb": 16,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonEKS",
                    "product_family": "Compute",
                    "region": "us-east-1",
                    "filters": [],
                },
            },
            "gcp": {
                "instance": "GKE + n2-standard-4",
                "vcpu": 4,
                "memory_gb": 16,
            },
            "azure": {
                "instance": "AKS + D4s_v5",
                "vcpu": 4,
                "memory_gb": 16,
                "azure_filter": (
                    "serviceName eq 'Azure Kubernetes Service' and "
                    "armRegionName eq 'eastus' and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "Serverless": {
        "tier_a": {
            "label": "Per million invocations (128MB, 200ms avg)",
            "aws": {
                "instance": "Lambda",
                "unit": "requests",
                "infracost": {
                    "vendor": "aws",
                    "service": "AWSLambda",
                    "product_family": "Serverless",
                    "region": "us-east-1",
                    "filters": [{"key": "group", "value": "AWS-Lambda-Requests"}],
                },
            },
            "gcp": {
                "instance": "Cloud Functions",
                "unit": "requests",
            },
            "azure": {
                "instance": "Azure Functions",
                "unit": "requests",
                "azure_filter": (
                    "serviceName eq 'Functions' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq 'On Demand' and "
                    "meterName eq 'On Demand Total Executions' and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "Machine Learning": {
        "tier_a": {
            "label": "4 vCPU ML instance",
            "aws": {
                "instance": "ml.m5.xlarge",
                "vcpu": 4,
                "memory_gb": 16,
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonSageMaker",
                    "product_family": "ML Instance",
                    "region": "us-east-1",
                    "filters": [{"key": "instanceType", "value": "ml.m5.xlarge"}],
                },
            },
            "gcp": {
                "instance": "n1-standard-4 (Vertex AI)",
                "vcpu": 4,
                "memory_gb": 15,
                "infracost": {
                    "vendor": "gcp",
                    "service": "Compute Engine",
                    "product_family": "Compute Instance",
                    "region": "us-central1",
                    "filters": [{"key": "machineType", "value": "n1-standard-4"}],
                },
            },
            "azure": {
                "instance": "Standard_D4s_v3 (Azure ML)",
                "vcpu": 4,
                "memory_gb": 16,
                "azure_filter": (
                    "serviceName eq 'Virtual Machines' and "
                    "armRegionName eq 'eastus' and "
                    "armSkuName eq 'Standard_D4s_v3' and "
                    "priceType eq 'Consumption'"
                ),
                "azure_filter_meter": "D4s v3",
                "azure_exclude_product": "Windows",
            },
        },
    },
    "Data Warehouse": {
        "tier_a": {
            "label": "Base compute unit",
            "aws": {
                "instance": "Redshift dc2.large",
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonRedshift",
                    "product_family": "Compute Instance",
                    "region": "us-east-1",
                    "filters": [{"key": "instanceType", "value": "dc2.large"}],
                },
            },
            "gcp": {
                "instance": "BigQuery (flat-rate slot)",
            },
            "azure": {
                "instance": "Synapse DW100c",
                "azure_filter": (
                    "serviceName eq 'Azure Synapse Analytics' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq 'DW100c' and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "CDN": {
        "tier_a": {
            "label": "Per GB egress (first 10TB tier)",
            "aws": {
                "instance": "CloudFront",
                "unit": "GB",
            },
            "gcp": {
                "instance": "Cloud CDN",
                "unit": "GB",
            },
            "azure": {
                "instance": "Azure CDN Standard",
                "unit": "GB",
                "azure_filter": (
                    "serviceName eq 'Content Delivery Network' and "
                    "contains(productName, 'Microsoft') and "
                    "armRegionName eq 'Zone 1' and "
                    "skuName eq 'Standard' and "
                    "meterName eq 'Standard Data Transfer' and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "Networking": {
        "tier_a": {
            "label": "NAT Gateway per GB processed",
            "aws": {
                "instance": "NAT Gateway",
                "unit": "GB",
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonEC2",
                    "product_family": "NAT Gateway",
                    "region": "us-east-1",
                    "filters": [{"key": "usagetype", "value": "NatGateway-Bytes"}],
                },
            },
            "gcp": {
                "instance": "Cloud NAT",
                "unit": "GB",
            },
            "azure": {
                "instance": "NAT Gateway",
                "unit": "GB",
            },
        },
    },
    "Load Balancing": {
        "tier_a": {
            "label": "Per hour (application load balancer)",
            "aws": {
                "instance": "ALB",
                "unit": "hour",
                "infracost": {
                    "vendor": "aws",
                    "service": "AWSELB",
                    "product_family": "Load Balancer-Application",
                    "region": "us-east-1",
                    "filters": [{"key": "usagetype", "value": "LoadBalancerUsage"}],
                },
            },
            "gcp": {
                "instance": "HTTP(S) Load Balancer",
                "unit": "hour",
            },
            "azure": {
                "instance": "Application Gateway v2",
                "unit": "hour",
                "azure_filter": (
                    "serviceName eq 'Application Gateway' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq 'Standard' and "
                    "meterName eq 'Standard Fixed Cost' and "
                    "contains(productName, 'Standard v2') and "
                    "priceType eq 'Consumption'"
                ),
            },
        },
    },
    "Monitoring": {
        "tier_a": {
            "label": "Per metric/month",
            "aws": {
                "instance": "CloudWatch",
                "unit": "metric",
                "infracost": {
                    "vendor": "aws",
                    "service": "AmazonCloudWatch",
                    "product_family": "Metric",
                    "region": "us-east-1",
                    "filters": [],
                },
            },
            "gcp": {
                "instance": "Cloud Monitoring",
                "unit": "metric",
            },
            "azure": {
                "instance": "Azure Monitor",
                "unit": "metric",
                "azure_filter": (
                    "serviceName eq 'Azure Monitor' and "
                    "armRegionName eq 'eastus' and "
                    "skuName eq 'Metric Samples Ingested' and "
                    "priceType eq 'Consumption'"
                ),
                "azure_filter_meter": "Metric",
            },
        },
    },
    "Security": {
        "tier_a": {
            "label": "Base threat detection",
            "aws": {
                "instance": "GuardDuty",
            },
            "gcp": {
                "instance": "Security Command Center",
            },
            "azure": {
                "instance": "Microsoft Defender",
                "azure_filter": (
                    "serviceName eq 'Microsoft Defender for Cloud' and "
                    "armRegionName eq 'eastus' and "
                    "contains(productName, 'Servers') and "
                    "skuName eq 'Standard P1' and "
                    "priceType eq 'Consumption'"
                ),
                "azure_filter_meter": "Node",
            },
        },
    },
}

HOURS_PER_MONTH = 730.0


async def _fetch_price_for_provider(
    provider: str, category_config: Dict[str, Any]
) -> Optional[float]:
    """Fetch a single price point for a provider from its configured source."""
    try:
        if provider in ("aws", "gcp"):
            infracost_config = category_config.get("infracost")
            if not infracost_config:
                return None
            price = await price_service.get_infracost_price(
                vendor=infracost_config["vendor"],
                service=infracost_config["service"],
                product_family=infracost_config["product_family"],
                region=infracost_config["region"],
                filters=infracost_config["filters"],
            )
            return price
        elif provider == "azure":
            azure_filter = category_config.get("azure_filter")
            if not azure_filter:
                return None
            meter_name = category_config.get("azure_filter_meter")
            exclude_product = category_config.get("azure_exclude_product")
            price = await price_service.get_azure_price(
                azure_filter, "eastus", meter_name=meter_name, exclude_product=exclude_product
            )
            return price
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", provider, e)
    return None


async def _compute_category_multiplier(
    category: str, tier_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute real multiplier for a single category by fetching live prices.
    Returns {multipliers, instance_pricing, pricing_basis}.
    """
    aws_config = tier_config.get("aws", {})
    gcp_config = tier_config.get("gcp", {})
    azure_config = tier_config.get("azure", {})

    aws_price = await _fetch_price_for_provider("aws", aws_config)
    gcp_price = await _fetch_price_for_provider("gcp", gcp_config)
    azure_price = await _fetch_price_for_provider("azure", azure_config)

    static_fallback = _CATEGORY_MULTIPLIERS.get(category, _CATEGORY_MULTIPLIERS["Other"])
    sources_hit: list = []

    if aws_price and aws_price > 0:
        sources_hit.append("aws")
    if gcp_price and gcp_price > 0:
        sources_hit.append("gcp")
    if azure_price and azure_price > 0:
        sources_hit.append("azure")

    if aws_price and aws_price > 0:
        aws_mult = 1.0
        raw_gcp = round(gcp_price / aws_price, 4) if gcp_price and gcp_price > 0 else None
        raw_azure = round(azure_price / aws_price, 4) if azure_price and azure_price > 0 else None

        # Sanity check: if ratio deviates >3x from static fallback, the services
        # likely have incomparable pricing models (e.g. per-request vs per-execution).
        # Use static fallback for the multiplier but still show real prices in instance panel.
        static_gcp = static_fallback.get("gcp", 0.95)
        static_azure = static_fallback.get("azure", 1.0)

        if raw_gcp is not None and 0.2 < raw_gcp < 5.0:
            gcp_mult = raw_gcp
        else:
            gcp_mult = static_gcp

        if raw_azure is not None and 0.2 < raw_azure < 5.0:
            azure_mult = raw_azure
        else:
            azure_mult = static_azure
    elif len(sources_hit) > 0:
        aws_mult = static_fallback.get("aws", 1.0)
        gcp_mult = static_fallback.get("gcp", 0.95)
        azure_mult = static_fallback.get("azure", 1.0)
    else:
        aws_mult = static_fallback.get("aws", 1.0)
        gcp_mult = static_fallback.get("gcp", 0.95)
        azure_mult = static_fallback.get("azure", 1.0)

    if len(sources_hit) == 3:
        pricing_basis = "live_api"
    elif len(sources_hit) > 0:
        pricing_basis = "partial_live"
    else:
        pricing_basis = "static_fallback"
        aws_price = None
        gcp_price = None
        azure_price = None

    instance_pricing = {}
    for provider, config, price in [
        ("aws", aws_config, aws_price),
        ("gcp", gcp_config, gcp_price),
        ("azure", azure_config, azure_price),
    ]:
        entry: Dict[str, Any] = {
            "instance_type": config.get("instance", "N/A"),
            "source": "live_api" if price else "static_fallback",
        }
        if config.get("vcpu"):
            entry["vcpu"] = config["vcpu"]
        if config.get("memory_gb"):
            entry["memory_gb"] = config["memory_gb"]
        if config.get("unit"):
            entry["unit"] = config["unit"]
        if price:
            entry["hourly_usd"] = round(price, 6)
            entry["monthly_usd"] = round(price * HOURS_PER_MONTH, 2)
        instance_pricing[provider] = entry

    return {
        "multipliers": {"aws": aws_mult, "gcp": gcp_mult, "azure": azure_mult},
        "instance_pricing": instance_pricing,
        "pricing_basis": pricing_basis,
        "label": tier_config.get("label", ""),
    }


async def compute_live_multipliers(
    db: MongoDBClient,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Compute real multipliers from live API data for all categories.
    Stores result in MongoDB for persistence.
    """
    if not force_refresh:
        existing = await _load_from_mongo(db)
        if existing and not _is_stale(existing.get("computed_at", "")):
            return existing

    logger.info("Computing live pricing multipliers from APIs...")
    start_time = time.time()

    multipliers: Dict[str, Dict[str, float]] = {}
    instance_pricing: Dict[str, Dict[str, Any]] = {}
    pricing_basis_per_category: Dict[str, str] = {}
    sources_used: set = set()

    for category, tiers in INSTANCE_EQUIVALENCE_MAP.items():
        tier_a = tiers.get("tier_a")
        if not tier_a:
            continue

        result = await _compute_category_multiplier(category, tier_a)
        multipliers[category] = result["multipliers"]
        instance_pricing[category] = result["instance_pricing"]
        pricing_basis_per_category[category] = result["pricing_basis"]

        if result["pricing_basis"] in ("live_api", "partial_live"):
            sources_used.add("infracost_graphql")
            sources_used.add("azure_retail_prices")

        # Also compute tier_b if it exists (for instance comparison panel)
        tier_b = tiers.get("tier_b")
        if tier_b:
            tier_b_result = await _compute_category_multiplier(category, tier_b)
            instance_pricing[f"{category}_tier_b"] = tier_b_result["instance_pricing"]

    # Fill in categories not in INSTANCE_EQUIVALENCE_MAP with static fallback
    for category in _CATEGORY_MULTIPLIERS:
        if category not in multipliers:
            multipliers[category] = _CATEGORY_MULTIPLIERS[category]
            pricing_basis_per_category[category] = "static_fallback"

    elapsed = round(time.time() - start_time, 2)
    now = datetime.now(timezone.utc).isoformat()

    live_count = sum(1 for v in pricing_basis_per_category.values() if v == "live_api")
    partial_count = sum(1 for v in pricing_basis_per_category.values() if v == "partial_live")
    static_count = sum(1 for v in pricing_basis_per_category.values() if v == "static_fallback")

    logger.info(
        "Live pricing computed in %.2fs: %d live, %d partial, %d static fallback",
        elapsed, live_count, partial_count, static_count,
    )

    document = {
        "id": MULTIPLIERS_DOC_ID,
        "multipliers": multipliers,
        "instance_pricing": instance_pricing,
        "pricing_basis_per_category": pricing_basis_per_category,
        "computed_at": now,
        "next_refresh_at": None,
        "sources_used": sorted(sources_used),
        "computation_time_seconds": elapsed,
        "live_count": live_count,
        "partial_count": partial_count,
        "static_count": static_count,
    }

    try:
        await db.upsert(MULTIPLIERS_COLLECTION, document)
    except Exception as e:
        logger.error("Failed to persist live multipliers to MongoDB: %s", e)

    return document


async def get_current_multipliers(db: MongoDBClient) -> Dict[str, Any]:
    """
    Get the current best-available multipliers.
    Fallback chain: MongoDB (cached) → compute live → static fallback.
    """
    cached = await _load_from_mongo(db)
    if cached and not _is_stale(cached.get("computed_at", "")):
        return cached

    # Data is stale or missing — try to compute fresh
    try:
        return await compute_live_multipliers(db, force_refresh=True)
    except Exception as e:
        logger.error("Live computation failed, using fallback: %s", e)

    # If cached exists but is stale, still return it (better than nothing)
    if cached:
        cached["_warning"] = "stale_data"
        return cached

    # Absolute last resort: static multipliers
    return {
        "id": MULTIPLIERS_DOC_ID,
        "multipliers": _CATEGORY_MULTIPLIERS,
        "instance_pricing": {},
        "pricing_basis_per_category": {k: "static_fallback" for k in _CATEGORY_MULTIPLIERS},
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "sources_used": [],
        "_warning": "all_static_fallback",
    }


def _is_stale(computed_at: str) -> bool:
    """Check if pricing data is older than STALENESS_THRESHOLD_HOURS."""
    if not computed_at:
        return True
    try:
        dt = datetime.fromisoformat(computed_at)
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return age_hours > STALENESS_THRESHOLD_HOURS
    except (ValueError, TypeError):
        return True


def is_critically_stale(computed_at: str) -> bool:
    """Check if pricing data is older than 48 hours (critical)."""
    if not computed_at:
        return True
    try:
        dt = datetime.fromisoformat(computed_at)
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return age_hours > STALE_CRITICAL_HOURS
    except (ValueError, TypeError):
        return True


async def _load_from_mongo(db: MongoDBClient) -> Optional[Dict[str, Any]]:
    """Load the latest multipliers from MongoDB."""
    try:
        results = await db.select(MULTIPLIERS_COLLECTION, filters={"id": MULTIPLIERS_DOC_ID})
        if results:
            doc = results[0]
            doc.pop("_id", None)
            return doc
    except Exception as e:
        logger.warning("Failed to load multipliers from MongoDB: %s", e)
    return None
