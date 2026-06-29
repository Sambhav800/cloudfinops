"""
Migration Advisor engine for live-scanned resources.

Groups resources by their actual provider and spend category, then projects
equivalent cost on AWS, GCP, and Azure using deterministic public blended
rate-card multipliers. No AI calls and no extra cloud API calls.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Relative cost multipliers per spend category.
# Baseline = 1.0 on the source cloud; applied relative to source.
# Sources: AWS, GCP, Azure public pricing pages (2024-2025 blended averages).
# ─────────────────────────────────────────────────────────────────────────────
_CATEGORY_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Compute":         {"aws": 1.000, "gcp": 0.960, "azure": 1.050},
    "Database":        {"aws": 1.000, "gcp": 0.900, "azure": 1.080},
    "Storage":         {"aws": 1.000, "gcp": 0.880, "azure": 0.840},
    "CDN":             {"aws": 1.000, "gcp": 0.940, "azure": 1.020},
    "Networking":      {"aws": 1.000, "gcp": 0.900, "azure": 0.970},
    "Load Balancing":  {"aws": 1.000, "gcp": 1.000, "azure": 1.000},
    "Kubernetes":      {"aws": 1.000, "gcp": 0.870, "azure": 0.900},
    "Serverless":      {"aws": 1.000, "gcp": 1.080, "azure": 1.000},
    "API":             {"aws": 1.000, "gcp": 0.920, "azure": 1.100},
    "Machine Learning":{"aws": 1.000, "gcp": 0.900, "azure": 1.050},
    "Data Warehouse":  {"aws": 1.000, "gcp": 0.850, "azure": 1.120},
    "Security":        {"aws": 1.000, "gcp": 0.980, "azure": 1.010},
    "Monitoring":      {"aws": 1.000, "gcp": 0.950, "azure": 0.990},
    "Other":           {"aws": 1.000, "gcp": 0.970, "azure": 1.010},
}

# Map service_type values to categories
_SERVICE_TO_CATEGORY: dict[str, str] = {
    # Compute
    "ec2 instance": "Compute", "ec2": "Compute", "aws ec2 instance": "Compute",
    "virtual machine": "Compute", "compute instance": "Compute",
    "app service": "Compute", "cloud run": "Compute",
    # Database
    "rds": "Database", "aurora": "Database", "cloud sql": "Database",
    "azure sql": "Database", "dynamodb": "Database", "cosmos db": "Database",
    "sql database": "Database", "postgresql": "Database",
    # Storage
    "s3": "Storage", "storage account": "Storage", "cloud storage": "Storage",
    "ebs": "Storage", "managed disk": "Storage", "persistent disk": "Storage",
    # Kubernetes
    "eks": "Kubernetes", "aks": "Kubernetes", "gke": "Kubernetes",
    "kubernetes": "Kubernetes",
    # Serverless
    "lambda": "Serverless", "azure function": "Serverless",
    "cloud function": "Serverless",
    # API
    "api gateway": "API", "aws api gateway": "API", "apigateway": "API",
    "api management": "API", "azure api management": "API",
    "cloud endpoints": "API", "gcp api gateway": "API", "apigee": "API",
    # Machine Learning
    "sagemaker": "Machine Learning", "vertex ai": "Machine Learning",
    "azure ml": "Machine Learning",
    # Networking
    "vpc": "Networking", "vnet": "Networking", "nat gateway": "Networking",
    "data transfer": "Networking", "network": "Networking",
    # Load Balancing
    "load balancer": "Load Balancing", "alb": "Load Balancing",
    "nlb": "Load Balancing", "elb": "Load Balancing",
    # CDN
    "cloudfront": "CDN", "azure cdn": "CDN", "cloud cdn": "CDN",
}

_PROVIDER_SERVICES: dict[str, dict[str, str]] = {
    "aws":   {"Compute": "EC2",      "Database": "RDS",      "Storage": "S3",      "Kubernetes": "EKS",      "Serverless": "Lambda",      "API": "API Gateway",      "Machine Learning": "SageMaker"},
    "gcp":   {"Compute": "Compute Engine", "Database": "Cloud SQL", "Storage": "Cloud Storage", "Kubernetes": "GKE", "Serverless": "Cloud Functions", "API": "API Gateway / Endpoints", "Machine Learning": "Vertex AI"},
    "azure": {"Compute": "Azure VMs", "Database": "Azure SQL", "Storage": "Blob Storage", "Kubernetes": "AKS", "Serverless": "Azure Functions", "API": "API Management",     "Machine Learning": "Azure ML"},
}

_RISK_SCORE: dict[str, int] = {
    "Low": 25,
    "Medium": 55,
    "High": 82,
}

_MIGRATION_COST_FACTOR: dict[str, float] = {
    "Low": 0.35,
    "Medium": 0.75,
    "High": 1.25,
}

_REGION_SCORE = {"aws": 92, "gcp": 86, "azure": 90}
_COMMITMENT_SCORE = {"aws": 90, "gcp": 82, "azure": 86}


def _categorize_service(service_type: str) -> str:
    lowered = str(service_type or "").lower().strip()
    for key, cat in _SERVICE_TO_CATEGORY.items():
        if key in lowered:
            return cat
    return "Other"


def _normalize_provider(provider: Any) -> str:
    p = str(provider or "").lower().strip()
    return p if p in ("aws", "gcp", "azure") else "aws"


def _resource_provider(resource: dict[str, Any], fallback: str | None) -> str:
    raw_provider = str(resource.get("provider") or "").lower().strip()
    if raw_provider in ("aws", "gcp", "azure"):
        return raw_provider
    return _normalize_provider(fallback)


def _round_money(value: float) -> float:
    return round(float(value or 0.0), 2)


def _cloud_costs_for_category(*, category: str, spend: float, source: str) -> dict[str, float]:
    mult = _CATEGORY_MULTIPLIERS.get(category, _CATEGORY_MULTIPLIERS["Other"])
    src_mult = mult.get(source, 1.0)
    cloud_costs: dict[str, float] = {}
    for cloud in ("aws", "gcp", "azure"):
        c_mult = mult.get(cloud, 1.0)
        projected = spend * (c_mult / src_mult if src_mult else 1.0)
        cloud_costs[cloud] = _round_money(projected)
    return cloud_costs


def _axis_score(category: str, cloud: str) -> int:
    mult = _CATEGORY_MULTIPLIERS.get(category, _CATEGORY_MULTIPLIERS["Other"])
    values = [float(mult.get(item, 1.0)) for item in ("aws", "gcp", "azure")]
    low = min(values)
    high = max(values)
    if high == low:
        return 84
    normalized = (float(mult.get(cloud, 1.0)) - low) / (high - low)
    return int(round(96 - normalized * 28))


def _provider_scores() -> list[dict[str, Any]]:
    rows = []
    for cloud in ("aws", "gcp", "azure"):
        rows.append(
            {
                "cloud": cloud.upper(),
                "compute_price": _axis_score("Compute", cloud),
                "storage": _axis_score("Storage", cloud),
                "network": _axis_score("Networking", cloud),
                "gpu": _axis_score("Machine Learning", cloud),
                "regions": _REGION_SCORE[cloud],
                "commitments": _COMMITMENT_SCORE[cloud],
                "score_source": "public_rate_card_blended_estimate",
            }
        )
    return rows


def _empty_report(source_provider: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "source_provider": source_provider,
        "by_category": {},
        "recommended_moves": [],
        "total_current_spend": 0.0,
        "total_best_case_spend": 0.0,
        "total_potential_savings": 0.0,
        "savings_pct": 0.0,
        "current_total_spend": 0.0,
        "optimized_total_spend": 0.0,
        "monthly_delta": 0.0,
        "annual_delta": 0.0,
        "provider_scores": _provider_scores(),
        "migration_scatter": [],
        "roi_curve": [],
        "roi_break_even_month": None,
        "current_allocation": [],
        "recommended_allocation": [],
        "allocation_flow": {"nodes": [], "links": []},
        "advisor_notes": [
            "Migration estimates use public blended rate-card multipliers and scanned resource cost signals.",
        ],
        "disclaimer": _disclaimer(),
    }


def build_multicloud_report(
    resources: list[dict[str, Any]],
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Build a multi-cloud cost comparison from scanned resource data.

    Args:
        resources: All scoped resources for an integration or active portfolio
        provider: Optional source cloud override for an integration view

    Returns:
        Structured report with provider-aware category cost breakdown,
        migration moves, chart-ready advisor fields, and a disclaimer.
    """
    fallback_source = _normalize_provider(provider)

    category_provider_spend: dict[tuple[str, str], dict[str, Any]] = {}
    for r in resources or []:
        cost = float(r.get("cost") or 0)
        if cost <= 0:
            continue
        source = _resource_provider(r, fallback_source)
        cat = _categorize_service(r.get("service_type") or r.get("resource_type") or "Other")
        key = (cat, source)
        current = category_provider_spend.setdefault(
            key,
            {
                "category": cat,
                "source": source,
                "spend": 0.0,
                "resource_count": 0,
            },
        )
        current["spend"] += cost
        current["resource_count"] += 1

    if not category_provider_spend:
        return _empty_report(fallback_source.upper() if provider else "UNKNOWN")

    source_clouds = sorted({str(item["source"]) for item in category_provider_spend.values()})
    source_provider = source_clouds[0].upper() if len(source_clouds) == 1 else "PORTFOLIO"
    by_category: dict[str, dict[str, Any]] = {}
    recommended_moves: list[dict[str, Any]] = []
    current_allocation: dict[str, float] = {"AWS": 0.0, "GCP": 0.0, "AZURE": 0.0}
    recommended_allocation: dict[str, float] = {"AWS": 0.0, "GCP": 0.0, "AZURE": 0.0}
    allocation_links: dict[tuple[str, str], float] = {}
    total_current = 0.0
    total_best = 0.0
    one_time_total = 0.0

    for item in sorted(category_provider_spend.values(), key=lambda row: row["spend"], reverse=True):
        cat = str(item["category"])
        source = str(item["source"])
        spend = _round_money(float(item["spend"]))
        cloud_costs = _cloud_costs_for_category(category=cat, spend=spend, source=source)

        current_cost = cloud_costs[source]
        cheapest_cloud = min(cloud_costs, key=cloud_costs.__getitem__)
        cheapest_cost = cloud_costs[cheapest_cloud]
        savings = round(current_cost - cheapest_cost, 2)
        savings_pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0.0

        category_row = by_category.setdefault(
            cat,
            {
                "current_spend": 0.0,
                "aws": 0.0,
                "gcp": 0.0,
                "azure": 0.0,
                "cheapest_cloud": cheapest_cloud.upper(),
                "cheapest_cost": 0.0,
                "savings": 0.0,
                "savings_pct": 0.0,
                "source_service": cat,
                "aws_equivalent": _PROVIDER_SERVICES.get("aws", {}).get(cat, cat),
                "gcp_equivalent": _PROVIDER_SERVICES.get("gcp", {}).get(cat, cat),
                "azure_equivalent": _PROVIDER_SERVICES.get("azure", {}).get(cat, cat),
                "migration_risk": _migration_risk(cat),
                "resource_count": 0,
            },
        )
        category_row["current_spend"] += current_cost
        category_row["aws"] += cloud_costs["aws"]
        category_row["gcp"] += cloud_costs["gcp"]
        category_row["azure"] += cloud_costs["azure"]
        category_row["savings"] += max(savings, 0.0)
        category_row["resource_count"] += int(item["resource_count"])

        total_current += current_cost
        total_best += cheapest_cost
        current_allocation[source.upper()] += current_cost
        recommended_allocation[cheapest_cloud.upper()] += cheapest_cost
        allocation_links[(source.upper(), cheapest_cloud.upper())] = (
            allocation_links.get((source.upper(), cheapest_cloud.upper()), 0.0) + cheapest_cost
        )

        if savings > 0:
            risk = _migration_risk(cat)
            risk_score = _RISK_SCORE.get(risk, 55)
            one_time_cost = _round_money(current_cost * _MIGRATION_COST_FACTOR.get(risk, 0.75))
            one_time_total += one_time_cost
            break_even = int((one_time_cost + savings - 0.01) // savings) if savings > 0 else None
            recommended_moves.append(
                {
                    "category": cat,
                    "from_cloud": source.upper(),
                    "to_cloud": cheapest_cloud.upper(),
                    "monthly_savings": savings,
                    "annual_savings": _round_money(savings * 12),
                    "savings_pct": savings_pct,
                    "migration_risk": risk,
                    "risk_score": risk_score,
                    "workload_size": _round_money(current_cost),
                    "resource_count": int(item["resource_count"]),
                    "one_time_migration_cost": one_time_cost,
                    "break_even_months": max(break_even or 1, 1),
                    "from_service": _PROVIDER_SERVICES.get(source, {}).get(cat, cat),
                    "to_service": {
                        "AWS": _PROVIDER_SERVICES.get("aws", {}).get(cat, cat),
                        "GCP": _PROVIDER_SERVICES.get("gcp", {}).get(cat, cat),
                        "AZURE": _PROVIDER_SERVICES.get("azure", {}).get(cat, cat),
                    }.get(cheapest_cloud.upper(), cheapest_cloud.upper()),
                }
            )

    for data in by_category.values():
        data["current_spend"] = _round_money(data["current_spend"])
        data["aws"] = _round_money(data["aws"])
        data["gcp"] = _round_money(data["gcp"])
        data["azure"] = _round_money(data["azure"])
        cloud_costs = {"AWS": data["aws"], "GCP": data["gcp"], "AZURE": data["azure"]}
        cheapest_cloud = min(cloud_costs, key=cloud_costs.__getitem__)
        data["cheapest_cloud"] = cheapest_cloud
        data["cheapest_cost"] = _round_money(cloud_costs[cheapest_cloud])
        data["savings"] = _round_money(data["savings"])
        data["savings_pct"] = round((data["savings"] / data["current_spend"]) * 100, 1) if data["current_spend"] > 0 else 0.0

    total_current = round(total_current, 2)
    total_best = round(total_best, 2)
    total_savings = round(total_current - total_best, 2)
    overall_savings_pct = round((total_savings / total_current) * 100, 1) if total_current > 0 else 0.0

    recommended_moves.sort(key=lambda x: x["monthly_savings"], reverse=True)
    recommended_moves = recommended_moves[:5]
    migration_scatter = [
        {
            "name": f"{move['category']} {move['from_cloud']}->{move['to_cloud']}",
            "category": move["category"],
            "risk_score": move["risk_score"],
            "monthly_savings": move["monthly_savings"],
            "annual_savings": move["annual_savings"],
            "workload_size": move["workload_size"],
            "from_cloud": move["from_cloud"],
            "to_cloud": move["to_cloud"],
            "migration_risk": move["migration_risk"],
        }
        for move in recommended_moves
    ]

    roi_curve = []
    roi_break_even_month = None
    if total_savings > 0:
        one_time_total = _round_money(one_time_total)
        for month in range(0, 13):
            net_value = _round_money((total_savings * month) - one_time_total)
            if roi_break_even_month is None and month > 0 and net_value >= 0:
                roi_break_even_month = month
            roi_curve.append(
                {
                    "month": month,
                    "net_value": net_value,
                    "cumulative_savings": _round_money(total_savings * month),
                    "one_time_migration_cost": one_time_total,
                }
            )

    allocation_nodes = sorted(
        {f"Current {source}" for source, _ in allocation_links}
        | {f"Optimized {target}" for _, target in allocation_links}
    )
    allocation_flow = {
        "nodes": [{"name": name} for name in allocation_nodes],
        "links": [
            {
                "source": f"Current {source}",
                "target": f"Optimized {target}",
                "value": _round_money(value),
            }
            for (source, target), value in sorted(allocation_links.items())
            if value > 0
        ],
    }

    return {
        "source_provider": source_provider,
        "by_category": by_category,
        "recommended_moves": recommended_moves,
        "total_current_spend": total_current,
        "total_best_case_spend": total_best,
        "total_potential_savings": total_savings,
        "savings_pct": overall_savings_pct,
        "current_total_spend": total_current,
        "optimized_total_spend": total_best,
        "monthly_delta": total_savings,
        "annual_delta": _round_money(total_savings * 12),
        "provider_scores": _provider_scores(),
        "migration_scatter": migration_scatter,
        "roi_curve": roi_curve,
        "roi_break_even_month": roi_break_even_month,
        "current_allocation": [
            {"provider": provider, "value": _round_money(value)}
            for provider, value in current_allocation.items()
            if value > 0
        ],
        "recommended_allocation": [
            {"provider": provider, "value": _round_money(value)}
            for provider, value in recommended_allocation.items()
            if value > 0
        ],
        "allocation_flow": allocation_flow,
        "advisor_notes": [
            "Portfolio mode preserves each resource's actual provider before estimating target-cloud cost.",
            "ROI uses a deterministic one-time migration cost estimate based on workload spend and migration risk.",
        ],
        "disclaimer": _disclaimer(),
    }


def _migration_risk(category: str) -> str:
    high = {"Database", "Machine Learning", "Data Warehouse"}
    low = {"Storage", "CDN", "Monitoring", "Serverless"}
    if category in high:
        return "High"
    if category in low:
        return "Low"
    return "Medium"


def _disclaimer() -> str:
    return (
        "Pricing based on public blended rate-card multipliers (2024-2025). "
        "Actual costs depend on reserved/committed pricing, data egress fees, "
        "support tiers, and workload-specific configurations. "
        "One-time migration costs are not included."
    )
