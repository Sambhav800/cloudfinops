"""
Discount Manager calculation engine.

Three-tier sequential discount model for cloud migration cost modeling:
  Tier 1: Per-service product discounts (CUD/SP/volume pricing)
  Tier 2: Volume/CUD blanket discount on post-Tier-1 total
  Tier 3: Negotiated enterprise discount on post-Tier-2 total

Reuses category multipliers from multicloud_comparison.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .multicloud_comparison import (
    _CATEGORY_MULTIPLIERS,
    _PROVIDER_SERVICES,
    _SERVICE_TO_CATEGORY,
)

logger = logging.getLogger(__name__)

DEFAULT_TIER1_BY_CATEGORY: Dict[str, float] = {
    "Compute": 30.0,
    "Database": 28.0,
    "Storage": 20.0,
    "CDN": 40.0,
    "Networking": 15.0,
    "Load Balancing": 15.0,
    "Kubernetes": 35.0,
    "Serverless": 10.0,
    "Machine Learning": 25.0,
    "Data Warehouse": 30.0,
    "Security": 10.0,
    "Monitoring": 12.0,
    "Other": 10.0,
}

SAMPLE_COSTS: Dict[str, float] = {
    "Compute": 4200.0,
    "Database": 1800.0,
    "Storage": 950.0,
    "CDN": 620.0,
    "Networking": 380.0,
    "Kubernetes": 1100.0,
    "Serverless": 450.0,
    "Machine Learning": 2300.0,
    "Data Warehouse": 1500.0,
    "Monitoring": 200.0,
    "Security": 150.0,
    "Load Balancing": 280.0,
    "Other": 170.0,
}


@dataclass
class ServiceLine:
    category: str
    source_service: str
    target_service: str
    source_monthly: float
    target_base: float
    tier1_discount_pct: float
    after_tier1: float
    saving: float


@dataclass
class DiscountResult:
    service_breakdown: List[Dict[str, Any]]
    source_monthly_total: float
    target_base_total: float
    after_tier1_total: float
    after_tier2_total: float
    final_cost: float
    total_monthly_savings: float
    total_annual_savings: float
    total_reduction_pct: float
    three_year_savings: float
    est_migration_cost: float
    payback_months: float
    one_year_net: float
    three_year_net: float
    waterfall: List[Dict[str, Any]]
    tier1_blended_pct: float
    tier2_savings_amount: float
    tier3_savings_amount: float
    source_provider: str
    target_provider: str


def get_default_services(source_provider: str = "aws") -> List[Dict[str, Any]]:
    """Return the default service list with categories, names, and default tier1 discounts."""
    source = source_provider.lower()
    services = []
    for category in _CATEGORY_MULTIPLIERS:
        source_name = _PROVIDER_SERVICES.get(source, {}).get(category, category)
        services.append({
            "category": category,
            "source_service": source_name,
            "aws_service": _PROVIDER_SERVICES.get("aws", {}).get(category, category),
            "gcp_service": _PROVIDER_SERVICES.get("gcp", {}).get(category, category),
            "azure_service": _PROVIDER_SERVICES.get("azure", {}).get(category, category),
            "default_tier1_pct": DEFAULT_TIER1_BY_CATEGORY.get(category, 10.0),
            "source_monthly": 0.0,
        })
    return services


def get_sample_data(source_provider: str = "aws") -> List[Dict[str, Any]]:
    """Return sample data for demo purposes."""
    services = get_default_services(source_provider)
    for svc in services:
        svc["source_monthly"] = SAMPLE_COSTS.get(svc["category"], 0.0)
    return services


def _get_multiplier(category: str, source: str, target: str) -> float:
    """Get the relative cost multiplier from source to target provider."""
    mults = _CATEGORY_MULTIPLIERS.get(category, _CATEGORY_MULTIPLIERS["Other"])
    source_base = mults.get(source, 1.0)
    target_base = mults.get(target, 1.0)
    if source_base == 0:
        return 1.0
    return target_base / source_base


def calculate_discount_model(
    services: List[Dict[str, Any]],
    source_provider: str,
    target_provider: str,
    tier2_volume_pct: float = 0.0,
    tier3_negotiated_pct: float = 0.0,
    multipliers_override: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Run the three-tier sequential discount calculation.

    Args:
        services: List of dicts with at minimum {category, source_monthly, tier1_discount_pct}
        source_provider: "aws", "gcp", or "azure"
        target_provider: "aws", "gcp", or "azure"
        tier2_volume_pct: Volume/CUD discount percentage (0-100)
        tier3_negotiated_pct: Negotiated discount percentage (0-100)
        multipliers_override: Live pricing multipliers (from live_pricing_engine). If provided, used instead of static _CATEGORY_MULTIPLIERS.

    Returns:
        Full DiscountResult as a dict.
    """
    source = source_provider.lower()
    target = target_provider.lower()
    tier2_pct = max(0.0, min(100.0, tier2_volume_pct))
    tier3_pct = max(0.0, min(100.0, tier3_negotiated_pct))

    breakdown: List[Dict[str, Any]] = []
    source_total = 0.0
    target_base_total = 0.0
    after_tier1_total = 0.0

    for svc in services:
        category = svc.get("category", "Other")
        source_monthly = float(svc.get("source_monthly", 0) or 0)
        tier1_pct = float(svc.get("tier1_discount_pct") or DEFAULT_TIER1_BY_CATEGORY.get(category, 10.0))
        tier1_pct = max(0.0, min(100.0, tier1_pct))

        if source_monthly <= 0:
            continue

        if multipliers_override and category in multipliers_override:
            mults = multipliers_override[category]
            src_base = mults.get(source, 1.0)
            tgt_base = mults.get(target, 1.0)
            multiplier = tgt_base / src_base if src_base != 0 else 1.0
        else:
            multiplier = _get_multiplier(category, source, target)
        target_base = round(source_monthly * multiplier, 2)
        after_tier1 = round(target_base * (1 - tier1_pct / 100.0), 2)
        saving = round(source_monthly - after_tier1, 2)

        source_name = _PROVIDER_SERVICES.get(source, {}).get(category, category)
        target_name = _PROVIDER_SERVICES.get(target, {}).get(category, category)

        breakdown.append({
            "category": category,
            "source_service": source_name,
            "target_service": target_name,
            "source_monthly": source_monthly,
            "target_base": target_base,
            "tier1_discount_pct": tier1_pct,
            "after_tier1": after_tier1,
            "saving_after_tier1": saving,
        })

        source_total += source_monthly
        target_base_total += target_base
        after_tier1_total += after_tier1

    after_tier2_total = round(after_tier1_total * (1 - tier2_pct / 100.0), 2)
    final_cost = round(after_tier2_total * (1 - tier3_pct / 100.0), 2)

    monthly_savings = round(source_total - final_cost, 2)
    annual_savings = round(monthly_savings * 12, 2)
    three_year = round(annual_savings * 3, 2)
    reduction_pct = round((monthly_savings / source_total) * 100, 1) if source_total > 0 else 0.0

    est_migration = round(monthly_savings * 4, 2) if monthly_savings > 0 else 0.0
    payback = round(est_migration / monthly_savings, 1) if monthly_savings > 0 else 0.0
    one_year_net = round(annual_savings - est_migration, 2)
    three_year_net = round(three_year - est_migration, 2)

    tier1_blended = round(
        ((target_base_total - after_tier1_total) / target_base_total) * 100, 1
    ) if target_base_total > 0 else 0.0
    tier2_savings_amount = round(after_tier1_total - after_tier2_total, 2)
    tier3_savings_amount = round(after_tier2_total - final_cost, 2)

    waterfall = [
        {"label": f"{source.upper()} Monthly", "value": source_total, "type": "start"},
        {"label": "Base Pricing Advantage", "value": round(source_total - target_base_total, 2), "type": "saving" if source_total > target_base_total else "increase"},
        {"label": "Tier 1: Product Discounts", "value": round(target_base_total - after_tier1_total, 2), "type": "saving"},
        {"label": "Tier 2: Volume/CUD", "value": tier2_savings_amount, "type": "saving"},
        {"label": "Tier 3: Negotiated", "value": tier3_savings_amount, "type": "saving"},
        {"label": f"Final {target.upper()} Cost", "value": final_cost, "type": "end"},
    ]

    for row in breakdown:
        vol_final_factor = (1 - tier2_pct / 100.0) * (1 - tier3_pct / 100.0)
        row["final_cost"] = round(row["after_tier1"] * vol_final_factor, 2)
        row["total_saving"] = round(row["source_monthly"] - row["final_cost"], 2)
        row["annual_saving"] = round(row["total_saving"] * 12, 2)

    return {
        "service_breakdown": breakdown,
        "source_monthly_total": round(source_total, 2),
        "target_base_total": round(target_base_total, 2),
        "after_tier1_total": round(after_tier1_total, 2),
        "after_tier2_total": after_tier2_total,
        "final_cost": final_cost,
        "total_monthly_savings": monthly_savings,
        "total_annual_savings": annual_savings,
        "total_reduction_pct": reduction_pct,
        "three_year_savings": three_year,
        "est_migration_cost": est_migration,
        "payback_months": payback,
        "one_year_net": one_year_net,
        "three_year_net": three_year_net,
        "waterfall": waterfall,
        "tier1_blended_pct": tier1_blended,
        "tier2_savings_amount": tier2_savings_amount,
        "tier3_savings_amount": tier3_savings_amount,
        "source_provider": source,
        "target_provider": target,
    }


def categorize_resources_for_discount(
    resources: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Aggregate scanned resources into category-level monthly spend."""
    category_spend: Dict[str, float] = {}
    for r in resources:
        cost = float(r.get("cost", 0) or r.get("monthly_cost", 0) or 0)
        if cost <= 0:
            continue
        service_type = str(r.get("service_type", "") or "").lower().strip()
        category = "Other"
        for key, cat in _SERVICE_TO_CATEGORY.items():
            if key in service_type:
                category = cat
                break
        category_spend[category] = category_spend.get(category, 0.0) + cost
    return {k: round(v, 2) for k, v in category_spend.items()}
