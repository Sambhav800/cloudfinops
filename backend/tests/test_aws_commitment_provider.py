from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import botocore.session
import pytest
from botocore.exceptions import ClientError
from botocore.validate import validate_parameters

from app.core.commitment_engine import CommitmentEngine, CommitmentProviderError


def savings_plan(identifier="sp-1", **overrides):
    return {
        "savingsPlanId": identifier,
        "savingsPlanArn": f"arn:aws:savingsplans::123456789012:savingsplan/{identifier}",
        "savingsPlanType": "Compute", "state": "active",
        "start": "2026-01-01T00:00:00Z", "end": "2027-01-01T00:00:00Z",
        "commitment": "0.50", "currency": "USD", **overrides,
    }


def reservation(identifier="ri-1", **overrides):
    return {
        "ReservedInstancesId": identifier, "ProductDescription": "Linux/UNIX",
        "InstanceType": "m5.large", "State": "active",
        "Start": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "End": datetime(2029, 1, 1, tzinfo=timezone.utc),
        "Duration": 3 * 365 * 24 * 3600, "FixedPrice": 1200.0, "InstanceCount": 3,
        "UsagePrice": 0.01, "RecurringCharges": [{"Frequency": "Hourly", "Amount": 0.05}],
        "CurrencyCode": "USD", **overrides,
    }


def sp_detail(identifier="sp-1", utilization="95.5", savings="10.0"):
    return {
        "SavingsPlanArn": savings_plan(identifier)["savingsPlanArn"],
        "Utilization": {"UtilizationPercentage": utilization},
        "Savings": {"NetSavings": savings},
    }


def ri_group(identifier="ri-1", **overrides):
    return {
        "Key": "SUBSCRIPTION_ID", "Value": "subscription-1",
        "Attributes": {"reservationId": identifier},
        "Utilization": {"UtilizationPercentage": "80.0", "NetRISavings": "5.0"},
        **overrides,
    }


@pytest.fixture
def aws(monkeypatch):
    engine = CommitmentEngine()
    clients = {name: MagicMock() for name in ("savingsplans", "ec2", "ce")}
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": []}
    clients["ec2"].describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
    clients["ce"].get_savings_plans_utilization_details.return_value = {"SavingsPlansUtilizationDetails": []}
    clients["ce"].get_reservation_utilization.return_value = {"UtilizationsByTime": []}
    get_client = MagicMock(side_effect=lambda service, *args, **kwargs: clients[service])
    monkeypatch.setattr(engine, "_get_aws_client", get_client)
    return engine, clients, get_client


@pytest.mark.asyncio
async def test_aws_mapping_uses_actual_sdk_fields_and_monthly_equivalents(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [reservation()]}
    clients["ce"].get_savings_plans_utilization_details.return_value = {"SavingsPlansUtilizationDetails": [sp_detail()]}
    clients["ce"].get_reservation_utilization.return_value = {"UtilizationsByTime": [{"Groups": [ri_group()]}]}
    items = await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])
    assert len(items) == 2
    sp, ri = items
    assert sp.id == "sp-1" and sp.status == "active" and sp.currency == "USD"
    assert sp.hourly_commitment == 0.5 and sp.commitment_amount == 365.0
    assert sp.amount_period == ri.amount_period == "monthly"
    assert sp.utilization_pct == 95.5 and sp.savings_amount == 10
    assert sp.pricing_basis == ri.pricing_basis == "live_api"
    # Three-year upfront amortization, three purchased instances, plus both hourly charge fields.
    assert ri.commitment_amount == pytest.approx((1200 / (3 * 365 * 24) + 0.05 + 0.01) * 3 * 730)
    assert ri.utilization_pct == 80 and ri.savings_amount == 5
    period = clients["ce"].get_reservation_utilization.call_args.kwargs["TimePeriod"]
    assert ri.savings_period_start == sp.savings_period_start == period["Start"]
    assert ri.savings_period_end == sp.savings_period_end == period["End"]
    assert datetime.fromisoformat(period["End"]) - datetime.fromisoformat(period["Start"]) == timedelta(days=7)
    assert datetime.fromisoformat(period["End"]).date() < datetime.now(timezone.utc).date()


@pytest.mark.asyncio
async def test_all_aws_pagination_and_groups_use_verified_botocore_shapes(aws):
    engine, clients, _ = aws
    sp_pages = [{"savingsPlans": [savings_plan()], "nextToken": "sp-next"},
                {"savingsPlans": [savings_plan("sp-2")]}]
    sp_util_pages = [{"SavingsPlansUtilizationDetails": [sp_detail()], "NextToken": "sp-ce-next"},
                     {"SavingsPlansUtilizationDetails": [sp_detail("sp-2", "0", "0")]}]
    ri_pages = [{"UtilizationsByTime": [{"Groups": [ri_group()]}], "NextPageToken": "ri-ce-next"},
                {"UtilizationsByTime": [{"Groups": [ri_group(
                    "ri-2", Attributes={"reservationARN": "arn:aws:ec2:us-east-1:123456789012:reserved-instances/ri-2"},
                )]}]}]
    period = {"Start": "2026-09-01", "End": "2026-09-08"}
    for page in sp_util_pages:
        page["TimePeriod"] = period
    for page in ri_pages:
        for detail in page["UtilizationsByTime"]:
            detail["TimePeriod"] = period
    clients["savingsplans"].describe_savings_plans.side_effect = sp_pages
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [reservation(), reservation("ri-2")]}
    clients["ce"].get_savings_plans_utilization_details.side_effect = sp_util_pages
    clients["ce"].get_reservation_utilization.side_effect = ri_pages
    items = await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])
    assert {item.id for item in items} == {"sp-1", "sp-2", "ri-1", "ri-2"}
    assert next(item for item in items if item.id == "sp-2").utilization_pct == 0
    assert next(item for item in items if item.id == "sp-2").savings_amount == 0
    assert next(item for item in items if item.id == "ri-2").utilization_pct == 80
    assert clients["savingsplans"].describe_savings_plans.call_args.kwargs["nextToken"] == "sp-next"
    assert clients["ce"].get_savings_plans_utilization_details.call_args.kwargs["NextToken"] == "sp-ce-next"
    assert clients["ce"].get_reservation_utilization.call_args.kwargs["NextPageToken"] == "ri-ce-next"
    assert clients["ce"].get_reservation_utilization.call_args.kwargs["GroupBy"] == [
        {"Type": "DIMENSION", "Key": "SUBSCRIPTION_ID"},
    ]

    session = botocore.session.get_session()
    cases = [
        ("savingsplans", "DescribeSavingsPlans", clients["savingsplans"].describe_savings_plans, sp_pages),
        ("ec2", "DescribeReservedInstances", clients["ec2"].describe_reserved_instances,
         [clients["ec2"].describe_reserved_instances.return_value]),
        ("ce", "GetSavingsPlansUtilizationDetails", clients["ce"].get_savings_plans_utilization_details, sp_util_pages),
        ("ce", "GetReservationUtilization", clients["ce"].get_reservation_utilization, ri_pages),
    ]
    for service, name, method, pages in cases:
        operation = session.get_service_model(service).operation_model(name)
        for call in method.call_args_list:
            validate_parameters(call.kwargs, operation.input_shape)
        for page in pages:
            validate_parameters(page, operation.output_shape)
    ec2 = session.get_service_model("ec2").operation_model("DescribeReservedInstances")
    assert not {"NextToken", "NextPageToken"} & ec2.input_shape.members.keys()
    group = session.get_service_model("ce").shape_for("ReservationUtilizationGroup")
    assert {"Key", "Value", "Attributes", "Utilization"} == set(group.members)


@pytest.mark.asyncio
@pytest.mark.parametrize("group", [
    ri_group(),
    ri_group(Attributes={"reservationARN": "arn:aws:ec2:us-east-1:123456789012:reserved-instances/ri-1"}),
    ri_group(Attributes={}, Value="ri-1"),
    ri_group(Attributes={}, Keys=["ri-1"]),
    ri_group(Attributes={"reservationId": "not-ours"}, Keys=["ri-1"]),
])
async def test_ri_utilization_matches_id_arn_value_or_legacy_keys(aws, group):
    engine, clients, _ = aws
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [reservation()]}
    clients["ce"].get_reservation_utilization.return_value = {"UtilizationsByTime": [{"Groups": [group]}]}
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.utilization_pct == 80 and item.savings_amount == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [
    ["FixedPrice"], ["InstanceCount"], ["Duration", "Start"], ["Duration", "End"],
    ["UsagePrice", "RecurringCharges"],
])
async def test_missing_ri_price_or_duration_keeps_monthly_amount_unknown(aws, missing):
    engine, clients, _ = aws
    row = reservation()
    for key in missing:
        row.pop(key)
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [row]}
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.commitment_amount is None and item.pricing_basis is None


@pytest.mark.asyncio
async def test_ri_uses_exact_start_end_duration_when_seconds_missing(aws):
    engine, clients, _ = aws
    row = reservation()
    row.pop("Duration")
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [row]}
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    hours = (row["End"] - row["Start"]).total_seconds() / 3600
    assert item.commitment_amount == pytest.approx((1200 / hours + 0.06) * 3 * 730)


@pytest.mark.asyncio
@pytest.mark.parametrize("changes,expected", [
    ({"FixedPrice": 0, "UsagePrice": 0, "RecurringCharges": []}, 0),
    ({"FixedPrice": 0, "UsagePrice": 0.1, "RecurringCharges": None}, 219),
    ({"FixedPrice": 0, "UsagePrice": None, "RecurringCharges": [{"Frequency": "Hourly", "Amount": 0.1}]}, 219),
    ({"UsagePrice": None, "RecurringCharges": [{"Frequency": "Hourly"}]}, None),
])
async def test_ri_handles_zero_and_legacy_or_recurring_hourly_pricing(aws, changes, expected):
    engine, clients, _ = aws
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [reservation(**changes)]}
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.commitment_amount == pytest.approx(expected) if expected is not None else item.commitment_amount is None


@pytest.mark.asyncio
async def test_unknown_savings_plan_financials_stay_none(aws):
    engine, clients, _ = aws
    row = savings_plan()
    row.pop("commitment")
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [row]}
    clients["ce"].get_savings_plans_utilization_details.return_value = {
        "SavingsPlansUtilizationDetails": [{"SavingsPlanArn": row["savingsPlanArn"], "Utilization": {}, "Savings": {}}],
    }
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.commitment_amount is item.hourly_commitment is item.utilization_pct is item.savings_amount is None
    assert item.pricing_basis is item.savings_period_start is item.savings_period_end is None


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["-0.1", "100.1", "NaN", "Infinity", "not-a-number"])
async def test_invalid_provider_utilization_raises_visible_error(aws, value):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    clients["ce"].get_savings_plans_utilization_details.return_value = {
        "SavingsPlansUtilizationDetails": [sp_detail(utilization=value)],
    }
    with pytest.raises(CommitmentProviderError, match="ValidationError|ValueError"):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])


@pytest.mark.asyncio
async def test_real_negative_provider_savings_is_not_clamped(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    clients["ce"].get_savings_plans_utilization_details.return_value = {
        "SavingsPlansUtilizationDetails": [sp_detail(savings="-10")],
    }
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.savings_amount == -10


@pytest.mark.asyncio
async def test_region_discovery_scans_every_enabled_region(aws):
    engine, clients, get_client = aws
    regions = ["us-east-1", "ap-south-1", "eu-central-1", "sa-east-1"]
    clients["ec2"].describe_regions.return_value = {"Regions": [{"RegionName": region} for region in regions]}
    assert await engine.get_aws_commitments("test-key", "test-secret") == []
    clients["ec2"].describe_regions.assert_called_once_with()
    assert [call.kwargs["region"] for call in get_client.call_args_list if "region" in call.kwargs] == regions
    assert clients["ec2"].describe_reserved_instances.call_count == 4


@pytest.mark.asyncio
async def test_explicit_regions_do_not_discover_or_duplicate_regions(aws):
    engine, clients, _ = aws
    assert await engine.get_aws_commitments("test-key", "test-secret", ["ap-south-1", "ap-south-1"]) == []
    clients["ec2"].describe_regions.assert_not_called()
    clients["ec2"].describe_reserved_instances.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["describe_savings_plans", "describe_regions", "describe_reserved_instances"])
async def test_listing_failure_cannot_become_successful_empty(aws, method, caplog):
    engine, clients, _ = aws
    client = clients["savingsplans"] if method == "describe_savings_plans" else clients["ec2"]
    getattr(client, method).side_effect = RuntimeError("secret-do-not-log")
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret")
    assert "secret-do-not-log" not in caplog.text


@pytest.mark.asyncio
async def test_failure_after_first_savings_plan_page_does_not_return_partial_success(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.side_effect = [
        {"savingsPlans": [savings_plan()], "nextToken": "next"}, RuntimeError("denied"),
    ]
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])


@pytest.mark.asyncio
async def test_region_failure_after_successful_region_is_not_hidden(aws):
    engine, clients, _ = aws
    clients["ec2"].describe_reserved_instances.side_effect = [
        {"ReservedInstances": [reservation()]}, RuntimeError("denied"),
    ]
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1", "ap-south-1"])


@pytest.mark.asyncio
async def test_ce_failure_is_visible_not_fake_zero_utilization(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    clients["ce"].get_savings_plans_utilization_details.side_effect = RuntimeError("denied")
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])


@pytest.mark.asyncio
async def test_empty_region_discovery_cannot_imply_complete_inventory(aws):
    engine, clients, _ = aws
    clients["ec2"].describe_regions.return_value = {"Regions": []}
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret")


@pytest.mark.asyncio
async def test_repeated_pagination_token_is_detected(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [], "nextToken": "repeated"}
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])
    assert clients["savingsplans"].describe_savings_plans.call_count == 2


@pytest.mark.asyncio
async def test_retry_logs_do_not_expose_sdk_error_messages(aws, monkeypatch, caplog):
    engine, clients, _ = aws
    monkeypatch.setattr("app.core.retry.time.sleep", lambda _: None)
    clients["savingsplans"].describe_savings_plans.side_effect = [
        ClientError({"Error": {"Code": "ThrottlingException", "Message": "secret-do-not-log"}}, "DescribeSavingsPlans"),
        {"savingsPlans": []},
    ]
    assert await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]) == []
    assert "Retrying" in caplog.text and "secret-do-not-log" not in caplog.text


@pytest.mark.asyncio
async def test_naive_ri_dates_are_not_assumed_utc(aws):
    engine, clients, _ = aws
    row = reservation(Start=datetime(2026, 1, 1), End=datetime(2027, 1, 1))
    row.pop("Duration")
    clients["ec2"].describe_reserved_instances.return_value = {"ReservedInstances": [row]}
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])


@pytest.mark.asyncio
async def test_empty_inventory_does_not_request_utilization(aws):
    engine, clients, _ = aws
    assert await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]) == []
    clients["ce"].get_savings_plans_utilization_details.assert_not_called()
    clients["ce"].get_reservation_utilization.assert_not_called()


@pytest.mark.asyncio
async def test_period_utilization_denominators_are_preserved(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    measured = sp_detail()
    measured["Utilization"].update(UsedCommitment="95.5", TotalCommitment="100")
    clients["ce"].get_savings_plans_utilization_details.return_value = {"SavingsPlansUtilizationDetails": [measured]}
    item = (await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"]))[0]
    assert item.utilization_used_commitment == 95.5
    assert item.utilization_total_commitment == 100


@pytest.mark.asyncio
async def test_temporary_token_is_supplied_to_every_provider_client(aws):
    engine, _, client = aws
    await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"], session_token="temporary-token")
    assert client.call_args_list
    assert all(call.kwargs["session_token"] == "temporary-token" for call in client.call_args_list)


@pytest.mark.asyncio
async def test_invalid_utilization_denominators_fail_visibly(aws):
    engine, clients, _ = aws
    clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": [savings_plan()]}
    measured = sp_detail()
    measured["Utilization"].update(UsedCommitment="101", TotalCommitment="100")
    clients["ce"].get_savings_plans_utilization_details.return_value = {"SavingsPlansUtilizationDetails": [measured]}
    with pytest.raises(CommitmentProviderError):
        await engine.get_aws_commitments("test-key", "test-secret", ["us-east-1"])


@pytest.mark.parametrize("account", ["123456789012", "", "not-an-account"])
def test_account_identity_is_verified_with_sts_and_temporary_token(monkeypatch, account):
    engine = CommitmentEngine()
    client = MagicMock()
    client.get_caller_identity.return_value = {"Account": account}
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(engine, "_get_aws_client", factory)
    credentials = {"access_key_id": "test", "secret_access_key": "test", "session_token": "temporary"}
    if account == "123456789012":
        assert engine._get_aws_account_id(credentials) == account
    else:
        with pytest.raises(ValueError, match="identity"):
            engine._get_aws_account_id(credentials)
    factory.assert_called_once_with("sts", "test", "test", session_token="temporary")
