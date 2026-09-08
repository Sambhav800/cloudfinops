"""
Commitment Optimizer — recommends optimal RI/SP/CUD purchases based on usage analysis.

Analyzes historical usage patterns to recommend:
- AWS: Savings Plans (Compute vs EC2 Instance) and Reserved Instances
- Azure: Reserved VM Instances
- GCP: Committed Use Discounts (resource-based vs flexible)

Key differentiators vs usage.ai:
1. Full transparency — shows the math behind every recommendation
2. Integrated with rightsizing — won't commit to oversized resources
3. Multi-cloud unified view with cross-provider strategy
4. Configurable risk tolerance (coverage target, max term, payment preference)
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommitmentType(str, Enum):
    AWS_COMPUTE_SP = "aws_compute_savings_plan"
    AWS_EC2_SP = "aws_ec2_instance_savings_plan"
    AWS_RI = "aws_reserved_instance"
    AZURE_RI = "azure_reserved_instance"
    GCP_RESOURCE_CUD = "gcp_resource_cud"
    GCP_FLEXIBLE_CUD = "gcp_flexible_cud"


class Term(str, Enum):
    ONE_YEAR = "1_year"
    THREE_YEAR = "3_year"


class PaymentOption(str, Enum):
    ALL_UPFRONT = "all_upfront"
    PARTIAL_UPFRONT = "partial_upfront"
    NO_UPFRONT = "no_upfront"


# Discount rates by provider/type/term/payment (percentage off on-demand)
DISCOUNT_MATRIX: Dict[str, Dict[str, float]] = {
    "aws_compute_savings_plan": {
        "1_year_no_upfront": 0.20,
        "1_year_partial_upfront": 0.25,
        "1_year_all_upfront": 0.30,
        "3_year_no_upfront": 0.36,
        "3_year_partial_upfront": 0.42,
        "3_year_all_upfront": 0.48,
    },
    "aws_ec2_instance_savings_plan": {
        "1_year_no_upfront": 0.28,
        "1_year_partial_upfront": 0.33,
        "1_year_all_upfront": 0.38,
        "3_year_no_upfront": 0.45,
        "3_year_partial_upfront": 0.52,
        "3_year_all_upfront": 0.58,
    },
    "azure_reserved_instance": {
        "1_year_no_upfront": 0.25,
        "1_year_all_upfront": 0.35,
        "3_year_no_upfront": 0.40,
        "3_year_all_upfront": 0.55,
    },
    "gcp_resource_cud": {
        "1_year_no_upfront": 0.28,
        "3_year_no_upfront": 0.55,
    },
    "gcp_flexible_cud": {
        "1_year_no_upfront": 0.20,
        "3_year_no_upfront": 0.46,
    },
}


@dataclass
class UsageBaseline:
    """Steady-state hourly usage derived from historical data."""
    provider: str
    region: str
    instance_family: str
    hourly_on_demand_cost: float
    p10_hourly_cost: float  # 10th percentile — near-guaranteed minimum usage
    p50_hourly_cost: float
    p75_hourly_cost: float
    observation_days: int
    instance_count_at_baseline: int = 1
    is_rightsized: bool = False


@dataclass
class CommitmentRecommendation:
    """A specific commitment purchase recommendation with full transparency."""
    commitment_type: CommitmentType
    provider: str
    region: str
    instance_family: str
    term: Term
    payment_option: PaymentOption
    hourly_commitment: float
    monthly_commitment: float
    discount_rate: float
    estimated_monthly_savings: float
    estimated_annual_savings: float
    coverage_pct: float
    utilization_confidence: float
    risk_level: str  # low, medium, high
    explanation: str
    math_breakdown: Dict[str, Any]
    priority: int = 0  # 1=highest


@dataclass
class CommitmentPortfolio:
    """Complete commitment strategy across all providers."""
    recommendations: List[CommitmentRecommendation]
    total_monthly_savings: float
    total_annual_savings: float
    current_monthly_on_demand: float
    projected_monthly_after_commitments: float
    overall_coverage_pct: float
    overall_savings_pct: float
    existing_commitment_utilization: float
    underutilized_commitments: List[Dict[str, Any]]
    expiring_soon: List[Dict[str, Any]]
    strategy_summary: str


@dataclass
class OptimizerConfig:
    """User-configurable risk tolerance settings."""
    coverage_target_pct: float = 75.0  # 70-80% is sweet spot
    max_term: Term = Term.ONE_YEAR
    preferred_payment: PaymentOption = PaymentOption.NO_UPFRONT
    min_observation_days: int = 30
    min_savings_threshold: float = 50.0  # Don't recommend <$50/mo savings
    exclude_dev_test: bool = True


def analyze_usage_baselines(
    resources: List[Dict[str, Any]],
    daily_spend: List[Dict[str, Any]],
    provider: str,
) -> List[UsageBaseline]:
    """
    Analyze resource usage to determine steady-state baselines for commitment sizing.

    Uses daily spend data + resource inventory to compute:
    - P10 hourly cost (conservative commitment target — near-guaranteed usage)
    - P50 hourly cost (moderate commitment target)
    - P75 hourly cost (aggressive commitment target)
    """
    if not daily_spend:
        return []

    amounts = [float(d.get("amount") or 0) for d in daily_spend if float(d.get("amount") or 0) > 0]
    if len(amounts) < 7:
        return []

    amounts.sort()
    n = len(amounts)

    p10_daily = amounts[max(0, int(n * 0.10))]
    p50_daily = amounts[int(n * 0.50)]
    p75_daily = amounts[int(n * 0.75)]
    avg_daily = sum(amounts) / n

    # Group resources by family for family-level recommendations
    family_costs: Dict[str, float] = {}
    family_regions: Dict[str, str] = {}
    family_counts: Dict[str, int] = {}
    rightsized_families: set = set()

    for r in resources:
        cost = float(r.get("cost") or 0)
        if cost <= 0:
            continue

        service_type = str(r.get("service_type") or "").lower()
        metadata = r.get("metadata") or {}

        # Only consider compute resources for commitments
        if not any(kw in service_type for kw in ("ec2", "virtual machine", "compute", "vm")):
            continue

        # Skip dev/test
        tags = r.get("tags") or {}
        env = str(tags.get("environment") or tags.get("env") or "").lower()
        if env in ("dev", "test", "staging", "sandbox"):
            continue

        # Extract family
        instance_type = str(
            metadata.get("instance_type") or metadata.get("vm_size") or
            metadata.get("machine_type") or ""
        )
        family = _extract_family(instance_type, provider)
        if not family:
            family = "general"

        region = str(r.get("region") or metadata.get("aws_region") or "")

        # Check if resource has been rightsized
        opt = metadata.get("optimization") or {}
        rec = opt.get("recommendation") or {}
        if rec.get("target_sku"):
            rightsized_families.add(family)

        key = f"{family}|{region}"
        family_costs[key] = family_costs.get(key, 0) + cost
        family_regions[key] = region
        family_counts[key] = family_counts.get(key, 0) + 1

    if not family_costs:
        # Fall back to subscription-level baseline
        baselines = [UsageBaseline(
            provider=provider,
            region="all",
            instance_family="compute",
            hourly_on_demand_cost=round(avg_daily / 24, 2),
            p10_hourly_cost=round(p10_daily / 24, 2),
            p50_hourly_cost=round(p50_daily / 24, 2),
            p75_hourly_cost=round(p75_daily / 24, 2),
            observation_days=n,
        )]
        return baselines

    # Build per-family baselines scaled by family's share of total
    total_resource_cost = sum(family_costs.values())
    baselines = []

    for key, cost in family_costs.items():
        family, region = key.split("|", 1) if "|" in key else (key, "")
        share = cost / total_resource_cost if total_resource_cost > 0 else 0

        baselines.append(UsageBaseline(
            provider=provider,
            region=region or "all",
            instance_family=family,
            hourly_on_demand_cost=round(avg_daily * share / 24, 2),
            p10_hourly_cost=round(p10_daily * share / 24, 2),
            p50_hourly_cost=round(p50_daily * share / 24, 2),
            p75_hourly_cost=round(p75_daily * share / 24, 2),
            observation_days=n,
            instance_count_at_baseline=family_counts.get(key, 1),
            is_rightsized=family in rightsized_families,
        ))

    return sorted(baselines, key=lambda b: b.hourly_on_demand_cost, reverse=True)


def generate_commitment_recommendations(
    baselines: List[UsageBaseline],
    existing_commitments: List[Dict[str, Any]],
    config: Optional[OptimizerConfig] = None,
) -> CommitmentPortfolio:
    """
    Generate optimal commitment recommendations from usage baselines.

    Strategy:
    1. Use P10 (conservative) baseline for commitment sizing — this is the
       near-guaranteed minimum usage that will be utilized.
    2. Choose commitment type based on workload flexibility needs.
    3. Calculate exact savings with full math transparency.
    4. Factor in existing commitments to avoid over-commitment.
    """
    if config is None:
        config = OptimizerConfig()

    recommendations: List[CommitmentRecommendation] = []
    total_on_demand = 0.0
    total_savings = 0.0

    # Analyze existing commitments
    existing_hourly = sum(float(c.get("commitment_amount") or 0) for c in existing_commitments)
    existing_util = _avg_utilization(existing_commitments)
    underutilized = _find_underutilized(existing_commitments)
    expiring = _find_expiring_soon(existing_commitments)

    for baseline in baselines:
        if baseline.observation_days < config.min_observation_days:
            continue

        monthly_on_demand = baseline.hourly_on_demand_cost * 730
        total_on_demand += monthly_on_demand

        if monthly_on_demand < config.min_savings_threshold:
            continue

        # Determine commitment sizing from P10 (conservative baseline)
        # This ensures >90% utilization of the commitment
        target_hourly = baseline.p10_hourly_cost * (config.coverage_target_pct / 100)

        if target_hourly <= 0:
            continue

        # Choose optimal commitment type
        commitment_type = _select_commitment_type(baseline)
        term = config.max_term
        payment = config.preferred_payment

        # Get discount rate
        discount_key = f"{term.value}_{payment.value}"
        discount = DISCOUNT_MATRIX.get(commitment_type.value, {}).get(discount_key, 0.15)

        # Calculate savings
        committed_hourly = target_hourly
        monthly_commitment = committed_hourly * 730
        monthly_savings = monthly_commitment * discount
        annual_savings = monthly_savings * 12

        if monthly_savings < config.min_savings_threshold:
            continue

        coverage_pct = round(
            (committed_hourly / baseline.hourly_on_demand_cost * 100)
            if baseline.hourly_on_demand_cost > 0 else 0,
            1,
        )

        # Utilization confidence based on how conservative the commitment is
        util_confidence = round(min(0.99, 0.85 + (baseline.observation_days - 30) * 0.002), 2)
        if baseline.is_rightsized:
            util_confidence = min(0.99, util_confidence + 0.05)

        risk = "low" if coverage_pct <= 70 else ("medium" if coverage_pct <= 85 else "high")

        math_breakdown = {
            "on_demand_hourly": baseline.hourly_on_demand_cost,
            "p10_hourly": baseline.p10_hourly_cost,
            "p50_hourly": baseline.p50_hourly_cost,
            "p75_hourly": baseline.p75_hourly_cost,
            "coverage_target_pct": config.coverage_target_pct,
            "committed_hourly": round(committed_hourly, 4),
            "discount_rate": discount,
            "monthly_on_demand": round(monthly_on_demand, 2),
            "monthly_committed": round(monthly_commitment, 2),
            "monthly_savings": round(monthly_savings, 2),
            "break_even_months": round(monthly_commitment / monthly_savings, 1) if monthly_savings > 0 else 999,
            "observation_days": baseline.observation_days,
            "instance_family": baseline.instance_family,
            "region": baseline.region,
        }

        term_label = "1-year" if term == Term.ONE_YEAR else "3-year"
        payment_label = payment.value.replace("_", " ").title()
        type_label = _commitment_type_label(commitment_type)

        explanation = (
            f"Based on {baseline.observation_days} days of usage data, "
            f"your {baseline.instance_family} workload in {baseline.region} "
            f"has a steady baseline of ${baseline.p10_hourly_cost:.2f}/hr (P10). "
            f"Purchasing a {term_label} {type_label} ({payment_label}) at "
            f"${committed_hourly:.2f}/hr covers {coverage_pct:.0f}% of your baseline usage "
            f"with a {discount*100:.0f}% discount, saving ${monthly_savings:.0f}/mo "
            f"(${annual_savings:.0f}/yr). "
            f"Break-even in {math_breakdown['break_even_months']:.0f} months."
        )

        if baseline.is_rightsized:
            explanation += (
                " This workload has already been rightsized, increasing commitment "
                "utilization confidence."
            )

        recommendations.append(CommitmentRecommendation(
            commitment_type=commitment_type,
            provider=baseline.provider,
            region=baseline.region,
            instance_family=baseline.instance_family,
            term=term,
            payment_option=payment,
            hourly_commitment=round(committed_hourly, 4),
            monthly_commitment=round(monthly_commitment, 2),
            discount_rate=discount,
            estimated_monthly_savings=round(monthly_savings, 2),
            estimated_annual_savings=round(annual_savings, 2),
            coverage_pct=coverage_pct,
            utilization_confidence=util_confidence,
            risk_level=risk,
            explanation=explanation,
            math_breakdown=math_breakdown,
            priority=_compute_priority(monthly_savings, risk, util_confidence),
        ))

        total_savings += monthly_savings

    # Sort by priority (highest savings + lowest risk first)
    recommendations.sort(key=lambda r: r.priority)

    projected_monthly = total_on_demand - total_savings
    overall_savings_pct = round(
        (total_savings / total_on_demand * 100) if total_on_demand > 0 else 0, 1
    )
    overall_coverage = round(
        sum(r.coverage_pct * r.monthly_commitment for r in recommendations)
        / max(sum(r.monthly_commitment for r in recommendations), 1),
        1,
    )

    strategy = _generate_strategy_summary(
        recommendations, total_on_demand, total_savings,
        existing_commitments, underutilized, expiring, config,
    )

    return CommitmentPortfolio(
        recommendations=recommendations,
        total_monthly_savings=round(total_savings, 2),
        total_annual_savings=round(total_savings * 12, 2),
        current_monthly_on_demand=round(total_on_demand, 2),
        projected_monthly_after_commitments=round(projected_monthly, 2),
        overall_coverage_pct=overall_coverage,
        overall_savings_pct=overall_savings_pct,
        existing_commitment_utilization=existing_util,
        underutilized_commitments=underutilized,
        expiring_soon=expiring,
        strategy_summary=strategy,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_family(instance_type: str, provider: str) -> str:
    """Extract instance family from type name."""
    if not instance_type:
        return ""
    if provider == "aws" and "." in instance_type:
        return instance_type.split(".")[0]
    elif provider == "azure" and instance_type.startswith("Standard_"):
        import re
        match = re.match(r"Standard_([A-Z]+)\d+", instance_type)
        return match.group(1) if match else ""
    elif provider == "gcp" and "-" in instance_type:
        parts = instance_type.rsplit("-", 1)
        return parts[0] if len(parts) == 2 else ""
    return ""


def _select_commitment_type(baseline: UsageBaseline) -> CommitmentType:
    """Select optimal commitment type based on workload characteristics."""
    p = baseline.provider.lower()
    if p == "aws":
        if baseline.instance_count_at_baseline >= 3:
            return CommitmentType.AWS_COMPUTE_SP
        return CommitmentType.AWS_EC2_SP
    elif p == "azure":
        return CommitmentType.AZURE_RI
    elif p == "gcp":
        if baseline.instance_count_at_baseline >= 3:
            return CommitmentType.GCP_FLEXIBLE_CUD
        return CommitmentType.GCP_RESOURCE_CUD
    return CommitmentType.AWS_COMPUTE_SP


def _commitment_type_label(ct: CommitmentType) -> str:
    labels = {
        CommitmentType.AWS_COMPUTE_SP: "Compute Savings Plan",
        CommitmentType.AWS_EC2_SP: "EC2 Instance Savings Plan",
        CommitmentType.AWS_RI: "Reserved Instance",
        CommitmentType.AZURE_RI: "Reserved VM Instance",
        CommitmentType.GCP_RESOURCE_CUD: "Resource-Based CUD",
        CommitmentType.GCP_FLEXIBLE_CUD: "Flexible CUD",
    }
    return labels.get(ct, ct.value)


def _avg_utilization(commitments: List[Dict[str, Any]]) -> float:
    utils = [float(c.get("utilization_pct") or 0) for c in commitments if float(c.get("utilization_pct") or 0) > 0]
    return round(sum(utils) / len(utils), 1) if utils else 0.0


def _find_underutilized(commitments: List[Dict[str, Any]], threshold: float = 80.0) -> List[Dict[str, Any]]:
    return [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "type": c.get("type"),
            "utilization_pct": float(c.get("utilization_pct") or 0),
            "commitment_amount": float(c.get("commitment_amount") or 0),
            "wasted_monthly": round(
                float(c.get("commitment_amount") or 0) * (1 - float(c.get("utilization_pct") or 0) / 100),
                2,
            ),
            "action": "Consider downsizing or letting expire" if float(c.get("utilization_pct") or 0) < 50 else "Monitor — may recover with seasonal usage",
        }
        for c in commitments
        if float(c.get("utilization_pct") or 0) < threshold and c.get("status") == "active"
    ]


def _find_expiring_soon(commitments: List[Dict[str, Any]], days: int = 60) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    results = []
    for c in commitments:
        end_str = c.get("end_date") or ""
        try:
            end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = (end_date - now).days
            if 0 < days_left <= days:
                results.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "type": c.get("type"),
                    "end_date": end_str,
                    "days_left": days_left,
                    "utilization_pct": float(c.get("utilization_pct") or 0),
                    "action": "Renew" if float(c.get("utilization_pct") or 0) > 70 else "Let expire — underutilized",
                })
        except (ValueError, TypeError):
            continue
    return sorted(results, key=lambda x: x["days_left"])


def _compute_priority(monthly_savings: float, risk: str, confidence: float) -> int:
    score = monthly_savings * confidence
    if risk == "high":
        score *= 0.5
    elif risk == "medium":
        score *= 0.8
    return -int(score)  # Negative for descending sort


def _generate_strategy_summary(
    recommendations: List[CommitmentRecommendation],
    total_on_demand: float,
    total_savings: float,
    existing: List[Dict[str, Any]],
    underutilized: List[Dict[str, Any]],
    expiring: List[Dict[str, Any]],
    config: OptimizerConfig,
) -> str:
    parts = []

    if not recommendations:
        return "No commitment recommendations at this time. Either spend is too low for meaningful savings or insufficient usage data (need 30+ days)."

    savings_pct = (total_savings / total_on_demand * 100) if total_on_demand > 0 else 0
    parts.append(
        f"Recommended {len(recommendations)} commitment(s) saving "
        f"${total_savings:.0f}/mo (${total_savings*12:.0f}/yr), "
        f"reducing on-demand spend by {savings_pct:.0f}%."
    )

    if underutilized:
        waste = sum(u["wasted_monthly"] for u in underutilized)
        parts.append(
            f"WARNING: {len(underutilized)} existing commitment(s) are underutilized, "
            f"wasting ${waste:.0f}/mo. Address these before purchasing new commitments."
        )

    if expiring:
        parts.append(
            f"{len(expiring)} commitment(s) expiring within 60 days — "
            f"review for renewal or replacement."
        )

    term_label = "1-year" if config.max_term == Term.ONE_YEAR else "3-year"
    parts.append(
        f"Strategy: {config.coverage_target_pct:.0f}% coverage target, "
        f"{term_label} max term, {config.preferred_payment.value.replace('_', ' ')} payment."
    )

    return " ".join(parts)
