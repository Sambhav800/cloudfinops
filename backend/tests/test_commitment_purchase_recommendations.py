from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.stub import Stubber

from app.core import commitment_recommendations as module

ACCOUNT = "123456789012"
NOW = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)


def detail(**changes):
    return {
        "AccountId": ACCOUNT, "CurrencyCode": "USD", "UpfrontCost": "0",
        "HourlyCommitmentToPurchase": "0.50", "EstimatedMonthlySavingsAmount": "10",
        "EstimatedSavingsAmount": "19.726", "EstimatedSavingsPercentage": "10",
        "EstimatedAverageUtilization": "97.5", "RecommendationDetailId": "12345678-1234-1234-1234-123456789012", **changes,
    }


def page(years=1, details=None, **changes):
    return {
        "Metadata": {"RecommendationId": "set-1", "GenerationTimestamp": NOW.isoformat()},
        "SavingsPlansPurchaseRecommendation": {
            "AccountScope": "LINKED", "SavingsPlansType": "COMPUTE_SP",
            "TermInYears": "ONE_YEAR" if years == 1 else "THREE_YEARS",
            "PaymentOption": "NO_UPFRONT", "LookbackPeriodInDays": "SIXTY_DAYS",
            "SavingsPlansPurchaseRecommendationDetails": [detail()] if details is None else details,
        }, **changes,
    }


def scenario(integration_id="int-aws"):
    return module._normalize_detail(detail(), account_id=ACCOUNT, integration_id=integration_id,
        years=1, generated_at=NOW.isoformat(), recommendation_id="set-1").model_dump()


def snapshot(**changes):
    return {
        "id": "snapshot-1", "user_id": "user-1", "integration_id": "int-aws",
        "account_id": ACCOUNT, "source": module.SOURCE, "status": "ready",
        "fetched_at": NOW.isoformat(), "generated_at": NOW.isoformat(),
        "scenarios": [scenario()], **changes,
    }


class FakeDB:
    def __init__(self, snapshots=(), integrations=None):
        self.rows = deepcopy(list(snapshots))
        self.integrations = integrations or [{"id": "int-aws", "user_id": "user-1", "provider": "aws", "status": "active"}]
        self.filters = []

    async def get_user_integrations(self, user_id):
        return [row for row in self.integrations if row["user_id"] == user_id]

    async def select(self, table, filters):
        assert table == module.PURCHASE_SNAPSHOTS
        assert filters["user_id"] == "user-1"
        self.filters.append(filters)
        return deepcopy([row for row in self.rows if all(row.get(k) == v for k, v in filters.items())])

    async def upsert(self, table, row):
        assert table == module.PURCHASE_SNAPSHOTS
        self.rows = [deepcopy(row)]
        return self.rows


def test_native_request_uses_sdk_supported_account_filter_and_pagination(monkeypatch):
    sts = boto3.client("sts", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    ce = boto3.client("ce", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    session = MagicMock()
    session.client.side_effect = lambda service, **kwargs: sts if service == "sts" else ce
    monkeypatch.setattr(module.boto3, "Session", lambda **kwargs: session)
    with Stubber(sts) as identity, Stubber(ce) as costs:
        identity.add_response("get_caller_identity", {"Account": ACCOUNT, "Arn": f"arn:aws:iam::{ACCOUNT}:user/test", "UserId": "test"}, {})
        base = {
            "SavingsPlansType": "COMPUTE_SP", "TermInYears": "ONE_YEAR",
            "PaymentOption": "NO_UPFRONT", "AccountScope": "LINKED",
            "LookbackPeriodInDays": "SIXTY_DAYS", "PageSize": 100,
            "Filter": {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [ACCOUNT]}},
        }
        costs.add_response("get_savings_plans_purchase_recommendation", page(NextPageToken="next"), base)
        costs.add_response("get_savings_plans_purchase_recommendation", page(details=[]), {**base, "NextPageToken": "next"})
        costs.add_response("get_savings_plans_purchase_recommendation", page(years=3), {**base, "TermInYears": "THREE_YEARS"})
        result = module.fetch_aws_purchase_recommendations(credentials={"access_key_id": "test", "secret_access_key": "test"}, integration_id="int-aws")
        identity.assert_no_pending_responses()
        costs.assert_no_pending_responses()
    assert len(result["scenarios"]) == 2
    assert result["scenarios"][0]["monthly_commitment_usd"] == 365
    assert result["scenarios"][0]["monthly_saving_usd"] == 10
    assert result["scenarios"][0]["annual_saving_usd"] == 120
    assert result["scenarios"][0]["effective_discount_pct"] is None
    assert result["scenarios"][0]["over_commitment_risk_pct"] is None


@pytest.mark.parametrize("changes", [
    {"CurrencyCode": "INR"}, {"AccountId": "999999999999"},
    {"HourlyCommitmentToPurchase": "NaN"}, {"HourlyCommitmentToPurchase": "-1"},
    {"HourlyCommitmentToPurchase": "0"}, {"EstimatedMonthlySavingsAmount": None},
    {"EstimatedMonthlySavingsAmount": "Infinity"}, {"UpfrontCost": "100"},
])
def test_invalid_provider_economics_never_become_purchase_advice(changes):
    with pytest.raises(ValueError):
        module._normalize_detail(detail(**changes), account_id=ACCOUNT, integration_id="int-aws", years=1, generated_at=NOW.isoformat(), recommendation_id="set-1")


def test_unknown_utilization_and_actual_zero_are_distinct():
    unknown = module._normalize_detail(detail(EstimatedAverageUtilization=None), account_id=ACCOUNT, integration_id="int-aws", years=1, generated_at=NOW.isoformat(), recommendation_id="set-1")
    zero = module._normalize_detail(detail(EstimatedAverageUtilization="0", EstimatedMonthlySavingsAmount="0"), account_id=ACCOUNT, integration_id="int-aws", years=1, generated_at=NOW.isoformat(), recommendation_id="set-1")
    assert unknown.estimated_utilization_pct is None
    assert zero.estimated_utilization_pct == 0
    assert zero.monthly_saving_usd == 0


@pytest.mark.asyncio
async def test_persisted_read_never_uses_daily_bill_or_invents_risk():
    result = await module.get_commitment_recommendation_result(db=FakeDB([snapshot()]), user_id="user-1", now=NOW)
    assert result.status == "ready"
    assert result.scenarios[0].monthly_saving_usd == 10
    assert result.recommended_scenario is None
    assert result.safe_baseline_monthly_usd is None
    assert result.compute_fraction_pct is None


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["generated_at", "fetched_at"])
async def test_stale_or_future_provider_evidence_is_withheld(field):
    for timestamp in (NOW - timedelta(days=3), NOW + timedelta(days=1)):
        result = await module.get_commitment_recommendation_result(db=FakeDB([snapshot(**{field: timestamp.isoformat()})]), user_id="user-1", now=NOW)
        assert result.status == "stale"
        assert result.scenarios == []


@pytest.mark.asyncio
async def test_empty_snapshot_is_different_from_missing_snapshot():
    missing = await module.get_commitment_recommendation_result(db=FakeDB(), user_id="user-1", now=NOW)
    empty = await module.get_commitment_recommendation_result(db=FakeDB([snapshot(status="no_recommendations", scenarios=[])]), user_id="user-1", now=NOW)
    assert missing.status == "not_synced"
    assert empty.status == "no_recommendations"


@pytest.mark.asyncio
async def test_failed_refresh_preserves_last_known_but_withholds_purchase(monkeypatch):
    db = FakeDB([snapshot()])
    def fail(**kwargs):
        raise RuntimeError("sensitive provider error")
    monkeypatch.setattr(module, "fetch_aws_purchase_recommendations", fail)
    await module.sync_aws_purchase_recommendations(db=db, user_id="user-1", integration=db.integrations[0], credentials={})
    assert db.rows[0]["scenarios"] == [scenario()]
    result = await module.get_commitment_recommendation_result(db=db, user_id="user-1", now=NOW)
    assert result.status == "unavailable"
    assert result.scenarios == []
    assert "sensitive" not in db.rows[0]["message"]


@pytest.mark.asyncio
async def test_successful_empty_refresh_clears_obsolete_purchase_estimates(monkeypatch):
    db = FakeDB([snapshot()])
    monkeypatch.setattr(module, "fetch_aws_purchase_recommendations", lambda **kwargs: {"account_id": ACCOUNT, "status": "no_recommendations", "scenarios": [], "generated_at": NOW.isoformat()})
    await module.sync_aws_purchase_recommendations(db=db, user_id="user-1", integration=db.integrations[0], credentials={})
    assert db.rows[0]["status"] == "no_recommendations"
    assert db.rows[0]["scenarios"] == []


@pytest.mark.asyncio
async def test_duplicate_cloud_account_is_not_counted_twice():
    integrations = [
        {"id": "int-aws", "user_id": "user-1", "provider": "aws", "status": "active"},
        {"id": "int-duplicate", "user_id": "user-1", "provider": "aws", "status": "active"},
    ]
    db = FakeDB([snapshot(), snapshot(integration_id="int-duplicate", scenarios=[scenario("int-duplicate")])], integrations)
    result = await module.get_commitment_recommendation_result(db=db, user_id="user-1", now=NOW)
    assert len(result.scenarios) == 1


@pytest.mark.asyncio
async def test_unowned_integration_is_not_read():
    db = FakeDB()
    with pytest.raises(module.CommitmentScopeNotFoundError):
        await module.get_commitment_recommendation_result(db=db, user_id="user-1", integration_id="someone-else", now=NOW)
    assert db.filters == []


@pytest.mark.asyncio
async def test_empty_user_scope_is_rejected_before_database_access():
    db = FakeDB()
    with pytest.raises(ValueError, match="User ID"):
        await module.get_commitment_recommendation_result(db=db, user_id="", now=NOW)
    assert db.filters == []


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"status": "ready", "scenarios": []},
    {"status": "no_recommendations"},
    {"scenarios": [{**scenario(), "generated_at": (NOW - timedelta(days=3)).isoformat()}]},
    {"scenarios": [{**scenario(), "generated_at": "not-a-date"}]},
    {"scenarios": [{**scenario(), "account_id": "999999999999"}]},
])
async def test_inconsistent_snapshot_cannot_create_a_purchase_signal(changes):
    result = await module.get_commitment_recommendation_result(db=FakeDB([snapshot(**changes)]), user_id="user-1", now=NOW)
    assert result.status == "unavailable"
    assert result.scenarios == []


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"provider": "azure"}, {"status": "inactive"}, {"user_id": "other"}])
async def test_purchase_sync_requires_active_owned_aws_integration(changes):
    db = FakeDB()
    with pytest.raises(ValueError, match="scope"):
        await module.sync_aws_purchase_recommendations(
            db=db, user_id="user-1", integration={**db.integrations[0], **changes}, credentials={},
        )
    assert db.filters == [] and db.rows == []
