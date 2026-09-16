from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.optimization.commitment_awareness import (
    CommitmentCoverage, _commitment_covers_resource, _is_marketplace_eligible,
    adjust_verdict_for_commitment, check_commitment_coverage,
)


def allocated():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "provider": "aws", "status": "active", "type": "Reservation", "currency": "USD",
        "resource_allocations": {"i-1": {
            "source": "aws_cur", "observed_at": now, "coverage_percentage": 75,
            "stranded_monthly_cost": 25, "currency": "USD", "cost_period": "monthly",
            "marginal_cost_verified": True,
        }},
    }


def test_family_match_is_not_proof_of_resource_coverage():
    assert not _commitment_covers_resource({"provider": "aws", "status": "active", "instance_type": "m5.large", "utilization_pct": 100}, "i-1", "m5.xlarge", "aws")


@pytest.mark.asyncio
async def test_explicit_allocation_adjusts_only_same_currency_marginal_cost():
    db = AsyncMock()
    db.select.return_value = [{"status": "ready", "last_success_at": datetime.now(timezone.utc).isoformat(), "commitments": [allocated()]}]
    coverage = await check_commitment_coverage(db, "user-1", "int-1", "i-1")
    assert coverage.is_covered
    assert coverage.coverage_percentage == 75
    assert adjust_verdict_for_commitment(100, coverage, currency="USD")["real_monthly_savings"] == 75
    assert adjust_verdict_for_commitment(100, coverage, currency="INR")["real_monthly_savings"] is None
    db.select.assert_awaited_once_with("commitment_snapshots", filters={"user_id": "user-1", "integration_id": "int-1"})


@pytest.mark.asyncio
async def test_coverage_without_marginal_cost_proof_cannot_claim_savings():
    row = allocated()
    row["resource_allocations"]["i-1"].pop("marginal_cost_verified")
    db = AsyncMock()
    db.select.return_value = [{"status": "ready", "last_success_at": datetime.now(timezone.utc).isoformat(), "commitments": [row]}]
    coverage = await check_commitment_coverage(db, "user-1", "int-1", "i-1")
    assert coverage.assessment_status == "coverage_only"
    assert adjust_verdict_for_commitment(100, coverage, currency="USD")["real_monthly_savings"] is None


@pytest.mark.asyncio
async def test_empty_or_failed_query_does_not_prove_uncovered():
    db = AsyncMock()
    db.select.return_value = []
    assert (await check_commitment_coverage(db, "user-1", "int-1", "i-1")).assessment_status == "unverified"
    db.select.side_effect = RuntimeError("database failed")
    assert (await check_commitment_coverage(db, "user-1", "int-1", "i-1")).assessment_status == "unavailable"


def test_marketplace_restrictions_are_not_inferred_from_months_remaining():
    assert not _is_marketplace_eligible({"type": "reserved_instance", "remaining_months": 12}, "aws")
    assert adjust_verdict_for_commitment(0, CommitmentCoverage())["real_monthly_savings"] is None
