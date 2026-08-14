"""
Commitment-Aware Classification — RI/SP/CUD coverage impacts termination recommendations.

Problem: If a resource is covered by a Reserved Instance or Savings Plan,
terminating it doesn't save money — the commitment keeps billing. The savings
only come if the commitment can be reused or sold on the marketplace.

This module connects to the existing commitment_engine to:
1. Flag RI/SP-covered resources in verdicts
2. Adjust savings estimates (stranded commitment = reduced real savings)
3. Recommend commitment marketplace selling when applicable
4. Prefer rightsizing over termination for committed resources
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommitmentCoverage:
    """How a resource is covered by commitments."""

    is_covered: bool = False
    coverage_type: Optional[str] = None  # "reserved_instance", "savings_plan", "cud"
    coverage_percentage: float = 0.0  # 0-100
    commitment_end_date: Optional[str] = None
    remaining_months: int = 0
    stranded_monthly_cost: float = 0.0  # Cost that continues if resource terminated
    marketplace_eligible: bool = False
    recommendation_adjustment: str = ""  # How this affects our recommendation


async def check_commitment_coverage(
    db: Any,
    user_id: str,
    integration_id: str,
    resource_id: str,
    resource_type: str = "",
    provider: str = "aws",
) -> CommitmentCoverage:
    """
    Check if a resource is covered by a commitment (RI/SP/CUD).

    Queries the commitment_engine's stored data to determine coverage.
    If covered, returns how this should affect the optimization recommendation.
    """
    if not db:
        return CommitmentCoverage()

    try:
        # Check for active commitments that might cover this resource
        commitments = await db.select(
            "cloud_commitments",
            filters={
                "user_id": user_id,
                "integration_id": integration_id,
                "status": "active",
            },
        )

        if not commitments:
            # Try the savings plan utilization data
            return await _check_savings_plan_coverage(db, user_id, integration_id)

        # Look for RIs matching this resource
        for commitment in commitments:
            if _commitment_covers_resource(commitment, resource_id, resource_type, provider):
                remaining_months = commitment.get("remaining_months", 0)
                monthly_cost = float(commitment.get("monthly_cost", 0) or 0)

                return CommitmentCoverage(
                    is_covered=True,
                    coverage_type=commitment.get("type", "reserved_instance"),
                    coverage_percentage=float(commitment.get("utilization_pct", 100)),
                    commitment_end_date=commitment.get("end_date"),
                    remaining_months=remaining_months,
                    stranded_monthly_cost=monthly_cost,
                    marketplace_eligible=_is_marketplace_eligible(commitment, provider),
                    recommendation_adjustment=_build_adjustment_message(
                        commitment, monthly_cost, remaining_months
                    ),
                )

        return CommitmentCoverage()

    except Exception as e:
        logger.debug(f"Commitment coverage check failed: {e}")
        return CommitmentCoverage()


async def _check_savings_plan_coverage(
    db: Any, user_id: str, integration_id: str
) -> CommitmentCoverage:
    """Check if the integration has active Savings Plans with high utilization."""
    try:
        sp_data = await db.select(
            "dashboard_stats",
            filters={"user_id": user_id, "integration_id": integration_id},
        )
        if sp_data:
            metadata = sp_data[0].get("metadata", {})
            sp_utilization = metadata.get("savings_plan_utilization_pct", 0)
            if sp_utilization > 80:
                return CommitmentCoverage(
                    is_covered=True,
                    coverage_type="savings_plan",
                    coverage_percentage=sp_utilization,
                    recommendation_adjustment=(
                        f"This account has {sp_utilization:.0f}% Savings Plan utilization. "
                        f"Terminating resources may strand commitment capacity."
                    ),
                )
    except Exception:
        pass
    return CommitmentCoverage()


def adjust_verdict_for_commitment(
    verdict_monthly_waste: float,
    coverage: CommitmentCoverage,
) -> Dict[str, Any]:
    """
    Adjust a waste verdict's savings estimate based on commitment coverage.

    If a resource is RI-covered, the "real" savings from termination are
    reduced by the stranded commitment cost that continues billing.

    Returns adjustment metadata to include in the verdict.
    """
    if not coverage.is_covered:
        return {"commitment_aware": False}

    real_savings = max(0, verdict_monthly_waste - coverage.stranded_monthly_cost)
    savings_reduction_pct = 0
    if verdict_monthly_waste > 0:
        savings_reduction_pct = (
            (verdict_monthly_waste - real_savings) / verdict_monthly_waste * 100
        )

    action_recommendation = "terminate"
    if coverage.remaining_months > 6 and real_savings < verdict_monthly_waste * 0.3:
        action_recommendation = "rightsize_instead"
    elif coverage.marketplace_eligible:
        action_recommendation = "sell_on_marketplace"

    return {
        "commitment_aware": True,
        "coverage_type": coverage.coverage_type,
        "coverage_pct": coverage.coverage_percentage,
        "stranded_monthly_cost": coverage.stranded_monthly_cost,
        "real_monthly_savings": real_savings,
        "savings_reduction_pct": round(savings_reduction_pct, 1),
        "recommended_action": action_recommendation,
        "marketplace_eligible": coverage.marketplace_eligible,
        "adjustment_note": coverage.recommendation_adjustment,
    }


def _commitment_covers_resource(
    commitment: Dict, resource_id: str, resource_type: str, provider: str
) -> bool:
    """Determine if a commitment covers a specific resource."""
    # RI matching: instance type, region, platform
    covered_ids = commitment.get("covered_resource_ids", [])
    if resource_id in covered_ids:
        return True

    # Fuzzy match on instance type family
    commitment_type = commitment.get("instance_type", "")
    if commitment_type and resource_type:
        # Same family match (e.g., m5 covers m5.large, m5.xlarge, etc.)
        commit_family = commitment_type.split(".")[0] if "." in commitment_type else ""
        resource_family = resource_type.split(".")[0] if "." in resource_type else ""
        if commit_family and resource_family and commit_family == resource_family:
            return True

    return False


def _is_marketplace_eligible(commitment: Dict, provider: str) -> bool:
    """Check if a commitment can be sold on the RI marketplace."""
    if provider != "aws":
        return False  # Only AWS has RI marketplace

    commitment_type = commitment.get("type", "")
    if commitment_type == "reserved_instance":
        remaining = commitment.get("remaining_months", 0)
        return remaining > 1  # Need at least 1 month remaining

    return False


def _build_adjustment_message(
    commitment: Dict, monthly_cost: float, remaining_months: int
) -> str:
    """Build a human-readable adjustment message."""
    commitment_type = commitment.get("type", "commitment")
    total_stranded = monthly_cost * remaining_months

    if remaining_months > 0 and monthly_cost > 0:
        return (
            f"Resource is covered by {commitment_type} "
            f"(${monthly_cost:.0f}/mo, {remaining_months} months remaining, "
            f"${total_stranded:.0f} total stranded cost). "
            f"Consider rightsizing instead of termination."
        )
    return f"Resource has {commitment_type} coverage."
