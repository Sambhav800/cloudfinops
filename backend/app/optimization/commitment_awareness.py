"""Resource commitment coverage requires explicit, current billing allocations."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommitmentCoverage:
    is_covered: bool = False
    assessment_status: str = "unverified"
    coverage_type: Optional[str] = None
    coverage_percentage: Optional[float] = None
    commitment_end_date: Optional[str] = None
    remaining_months: int = 0
    stranded_monthly_cost: Optional[float] = None
    currency: Optional[str] = None
    marketplace_eligible: bool = False
    recommendation_adjustment: str = "Resource-level commitment allocation has not been measured."


def _number(value: object) -> Optional[float]:
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


def _fresh(value: object) -> bool:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        return timedelta(0) <= datetime.now(timezone.utc) - timestamp <= timedelta(hours=48)
    except (TypeError, ValueError):
        return False


def _allocation(commitment: dict, resource_id: str) -> dict:
    allocations = commitment.get("resource_allocations")
    allocation = allocations.get(resource_id) if isinstance(allocations, dict) else None
    if not isinstance(allocation, dict):
        return {}
    if allocation.get("source") not in {"aws_cur", "azure_cost_details", "gcp_billing_export"}:
        return {}
    return allocation if _fresh(allocation.get("observed_at")) else {}


async def check_commitment_coverage(
    db: Any, user_id: str, integration_id: str, resource_id: str,
    resource_type: str = "", provider: str = "aws",
) -> CommitmentCoverage:
    """Read allocation evidence without inferring coverage from inventory utilization."""
    if not db:
        return CommitmentCoverage()
    try:
        snapshots = await db.select(
            "commitment_snapshots",
            filters={"user_id": user_id, "integration_id": integration_id},
        )
        for snapshot in snapshots:
            if snapshot.get("status") != "ready" or not _fresh(snapshot.get("last_success_at")):
                continue
            for commitment in snapshot.get("commitments", []):
                if not isinstance(commitment, dict) or not _commitment_covers_resource(commitment, resource_id, resource_type, provider):
                    continue
                allocation = _allocation(commitment, resource_id)
                percentage = _number(allocation.get("coverage_percentage"))
                if percentage is None or not 0 < percentage <= 100:
                    continue
                currency = allocation.get("currency")
                marginal_verified = (
                    allocation.get("marginal_cost_verified") is True
                    and allocation.get("cost_period") == "monthly"
                    and isinstance(currency, str) and bool(currency)
                    and currency == commitment.get("currency")
                )
                stranded = _number(allocation.get("stranded_monthly_cost")) if marginal_verified else None
                return CommitmentCoverage(
                    is_covered=True,
                    assessment_status="verified" if stranded is not None else "coverage_only",
                    coverage_type=commitment.get("type"),
                    coverage_percentage=percentage,
                    commitment_end_date=commitment.get("end_date"),
                    stranded_monthly_cost=stranded,
                    currency=currency,
                    marketplace_eligible=_is_marketplace_eligible(commitment, provider),
                    recommendation_adjustment=(
                        "Coverage is supported by resource-level billing allocation. "
                        "Marginal savings require the stranded commitment cost in the same currency and period."
                    ),
                )
        return CommitmentCoverage()
    except Exception as error:
        logger.warning("Commitment coverage evidence unavailable (%s)", type(error).__name__)
        return CommitmentCoverage(assessment_status="unavailable")


async def _check_savings_plan_coverage(db: Any, user_id: str, integration_id: str) -> CommitmentCoverage:
    """Account-level utilization cannot establish an individual resource's coverage."""
    return CommitmentCoverage()


def adjust_verdict_for_commitment(
    verdict_monthly_waste: float, coverage: CommitmentCoverage, *, currency: Optional[str] = None,
) -> Dict[str, Any]:
    """Adjust only when the allocation includes a measured marginal stranded cost."""
    result = {
        "commitment_aware": coverage.is_covered,
        "assessment_status": coverage.assessment_status,
        "adjustment_note": coverage.recommendation_adjustment,
    }
    waste = _number(verdict_monthly_waste)
    stranded = _number(coverage.stranded_monthly_cost)
    if (not coverage.is_covered or coverage.assessment_status != "verified"
        or stranded is None or waste is None or not currency or currency != coverage.currency):
        return {**result, "real_monthly_savings": None, "recommended_action": "review_commitment_allocation"}
    real_savings = max(0.0, waste - stranded)
    return {
        **result,
        "coverage_type": coverage.coverage_type,
        "coverage_pct": coverage.coverage_percentage,
        "stranded_monthly_cost": coverage.stranded_monthly_cost,
        "real_monthly_savings": real_savings,
        "savings_reduction_pct": round((waste - real_savings) / waste * 100, 1) if waste else 0,
        "recommended_action": "review_commitment_allocation",
        "marketplace_eligible": coverage.marketplace_eligible,
    }


def _commitment_covers_resource(commitment: Dict, resource_id: str, resource_type: str, provider: str) -> bool:
    return (
        commitment.get("provider") == provider
        and commitment.get("status") == "active"
        and bool(_allocation(commitment, resource_id))
    )


def _is_marketplace_eligible(commitment: Dict, provider: str) -> bool:
    return (
        provider == "aws"
        and commitment.get("type") in {"Reservation", "reserved_instance"}
        and commitment.get("offering_class") == "standard"
        and commitment.get("marketplace_eligibility_verified") is True
    )
