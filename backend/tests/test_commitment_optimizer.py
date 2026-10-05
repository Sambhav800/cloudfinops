from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Sequence
from zoneinfo import ZoneInfo

import pytest

from app.core.commitment_optimizer import (
    CommitmentPortfolio,
    CommitmentType,
    HourlyUsageRecord,
    LivePriceQuote,
    OptimizerConfig,
    PaymentOption,
    Term,
    UsageBaseline,
    UsageScope,
    analyze_hourly_usage_baselines,
    analyze_usage_baselines,
    generate_commitment_recommendations,
)


START = datetime(2026, 9, 12, tzinfo=timezone.utc)
END = START + timedelta(days=3)
NOW = END + timedelta(hours=12)
SCOPE = UsageScope("aws", "integration-1", "account-1", "us-east-1", "m5", "USD", "m5.large-linux")
CONFIG = OptimizerConfig(coverage_target_pct=100, min_observation_days=1, holdout_days=1, min_savings_threshold=0)


def _records(costs: Sequence[float] = (10.0,) * 72, scope: UsageScope = SCOPE) -> list[HourlyUsageRecord]:
    return [HourlyUsageRecord(
        scope=scope, timestamp=START + timedelta(hours=i),
        on_demand_cost=cost, on_demand_rate=1.0, residual_on_demand_cost=cost,
        charge_eligible=True, coverage_verified=True, coverage_source="test-billing-reconciliation",
        accounted_commitment_ids=(), environment="production",
    ) for i, cost in enumerate(costs)]


def _quote(scope: UsageScope = SCOPE) -> LivePriceQuote:
    return LivePriceQuote(
        scope=scope, commitment_type=CommitmentType.AWS_COMPUTE_SP,
        term=Term.ONE_YEAR, payment_option=PaymentOption.NO_UPFRONT,
        on_demand_rate=1.0, committed_rate=0.6,
        captured_at=NOW - timedelta(hours=1), valid_until=NOW + timedelta(hours=1),
        source="test-provider-live-quote", quote_id="quote-1", verified=True,
    )


def _baselines(records: Sequence[HourlyUsageRecord]) -> list[UsageBaseline]:
    return analyze_hourly_usage_baselines(records, window_start=START, window_end=END)


def _portfolio(
    records: Sequence[HourlyUsageRecord],
    quotes: Sequence[LivePriceQuote] | None = None,
    existing: list[dict[str, object]] | None = None,
    config: OptimizerConfig = CONFIG,
) -> CommitmentPortfolio:
    return generate_commitment_recommendations(
        _baselines(records), existing or [], config,
        live_quotes=[_quote()] if quotes is None else quotes, now=NOW,
    )


def _inventory() -> list[dict[str, object]]:
    return [{
        "id": "existing-1", "provider": SCOPE.provider, "integration_id": SCOPE.integration_id,
        "account_id": SCOPE.account_id, "currency": SCOPE.currency, "status": "active",
        "commitment_amount": 99999, "utilization_pct": 0,
    }]


def test_daily_subscription_bills_are_not_hourly_compute_evidence() -> None:
    resources = [{
        "service_type": "ec2",
        "cost": 100,
        "region": "us-east-1",
        "metadata": {
            "instance_type": "m5.large",
            "optimization": {"recommendation": {"target_sku": "m5.medium"}},
        },
    }]
    daily = [{"spend_date": f"2026-08-{day:02d}", "amount": 2400} for day in range(1, 31)]

    assert analyze_usage_baselines(resources, daily, "aws") == []
    assert analyze_usage_baselines([], daily, "aws") == []


def test_legacy_summary_without_live_quote_cannot_recommend_purchase() -> None:
    baseline = UsageBaseline("aws", "us-east-1", "m5", 100, 100, 100, 100, 90)

    portfolio = generate_commitment_recommendations([baseline], [])

    assert portfolio.recommendations == []
    assert "quote" in portfolio.strategy_summary.lower()


def test_empty_input_has_no_purchase_or_savings_claim() -> None:
    assert analyze_usage_baselines([], [], "aws") == []
    portfolio = generate_commitment_recommendations([], [])
    assert portfolio.recommendations == []
    assert portfolio.total_monthly_savings == 0
    assert portfolio.current_monthly_on_demand is None
    assert portfolio.existing_commitment_utilization is None
    assert analyze_hourly_usage_baselines([], window_start=START, window_end=END) == []


def test_live_quote_math_uses_committed_rate_dollars_and_observed_holdout() -> None:
    portfolio = _portfolio(_records())
    rec, = portfolio.recommendations
    math = rec.math_breakdown

    assert rec.hourly_commitment == 6.0  # 10 OD-equivalent * (0.6 committed / 1 OD).
    assert rec.discount_rate == pytest.approx(0.4)
    assert math["training_hours"] == 48
    assert math["holdout_hours"] == 24
    assert math["holdout_on_demand_cost"] == 240
    assert math["holdout_committed_cost"] == 144
    assert math["holdout_uncovered_on_demand_cost"] == 0
    assert math["holdout_net_savings"] == 96
    assert math["holdout_unused_commitment_cost"] == 0
    assert rec.monthly_commitment == 6 * 730
    assert rec.estimated_monthly_savings == 96 / 24 * 730
    assert portfolio.projected_monthly_after_commitments == rec.monthly_commitment
    assert portfolio.overall_coverage_pct == 100
    assert portfolio.currency == "USD"
    assert portfolio.status == rec.status == rec.risk_level == "needs_review"
    assert rec.utilization_confidence is None
    assert "break_even_months" not in math
    assert math["quote_source"] == _quote().source
    assert math["quote_captured_at"] == _quote().captured_at.isoformat()
    assert math["pricing_basis"] == rec.pricing_basis == "live_api"
    assert "not forecasts" in rec.explanation


def test_zero_holdout_keeps_negative_net_savings_and_full_unused_obligation() -> None:
    portfolio = _portfolio(_records([10.0] * 48 + [0.0] * 24))
    evaluation, = portfolio.evaluations

    assert portfolio.recommendations == []
    assert evaluation["hourly_commitment"] == 6
    assert evaluation["holdout_on_demand_cost"] == 0
    assert evaluation["holdout_committed_cost"] == 144
    assert evaluation["holdout_unused_commitment_cost"] == 144
    assert evaluation["holdout_net_savings"] == -144
    assert evaluation["estimated_monthly_savings"] == -6 * 730
    assert evaluation["holdout_utilization_pct"] == 0
    assert evaluation["status"] == "withheld"


def test_partial_unused_hours_are_charged_even_in_profitable_scenario() -> None:
    portfolio = _portfolio(_records([10.0] * 48 + [0.0] * 4 + [10.0] * 20))
    rec, = portfolio.recommendations
    assert rec.math_breakdown["holdout_unused_commitment_cost"] == 24
    assert rec.math_breakdown["holdout_net_savings"] == 200 - 144
    assert rec.math_breakdown["holdout_utilization_pct"] == pytest.approx(100 * 20 / 24)


def test_uncovered_on_demand_remains_payable_and_holdout_does_not_resize() -> None:
    portfolio = _portfolio(_records([10.0] * 48 + [20.0] * 24))
    rec, = portfolio.recommendations
    assert rec.hourly_commitment == 6
    assert rec.math_breakdown["holdout_uncovered_on_demand_cost"] == 240
    assert rec.math_breakdown["holdout_net_savings"] == 480 - 144 - 240
    assert rec.coverage_pct == 50


def test_real_training_zero_hours_are_not_filtered_out_of_percentiles() -> None:
    records = _records([0.0] * 12 + [10.0] * 60)
    baseline, = _baselines(records)
    assert baseline.p10_hourly_cost == 0
    assert baseline.hourly_records == tuple(records)
    assert _portfolio(records).recommendations == []


@pytest.mark.parametrize("missing_index", [0, 36, 71])
def test_missing_edge_or_interior_hour_is_not_imputed(missing_index: int) -> None:
    records = _records()
    records.pop(missing_index)
    baseline, = _baselines(records)
    assert baseline.missing_hours == 1
    assert baseline.evidence_status == "needs_review"
    assert baseline.p10_hourly_cost is None
    assert len(baseline.hourly_records) == 71
    assert "missing_hours" in _portfolio(records).withheld_reasons


def test_duplicate_hour_is_preserved_and_withheld_even_with_different_timezone() -> None:
    records = _records()
    duplicate = replace(records[0], timestamp=START.astimezone(timezone(timedelta(hours=5, minutes=30))))
    records.append(duplicate)
    baseline, = _baselines(records)
    assert baseline.duplicate_hours == 1
    assert baseline.missing_hours == 0
    assert len(baseline.hourly_records) == 73
    assert "duplicate_hours" in _portfolio(records).withheld_reasons


def test_dst_fallback_hours_are_distinct_and_holdout_order_is_utc() -> None:
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 10, 30, 6, tzinfo=timezone.utc)
    end = start + timedelta(hours=72)
    rows = [replace(r, timestamp=(start + timedelta(hours=i)).astimezone(zone))
            for i, r in enumerate(_records([10.0] * 48 + [0.0] * 24))]
    baselines = analyze_hourly_usage_baselines(list(reversed(rows)), window_start=start, window_end=end)
    assert baselines[0].duplicate_hours == 0
    quote = replace(_quote(), captured_at=end, valid_until=end + timedelta(hours=1))
    portfolio = generate_commitment_recommendations(baselines, [], CONFIG, [quote], now=end)
    assert portfolio.evaluations[0]["holdout_net_savings"] == -144


def test_one_hour_window_across_dst_fold_is_not_mistaken_for_empty_window() -> None:
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 11, 1, 5, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    row = replace(_records()[0], timestamp=start.astimezone(zone))
    baseline, = analyze_hourly_usage_baselines(
        [row], window_start=start.astimezone(zone), window_end=end.astimezone(zone),
    )
    assert baseline.missing_hours == 0
    assert baseline.hourly_on_demand_cost == 10


@pytest.mark.parametrize("change", [
    {"on_demand_cost": float("nan")}, {"on_demand_cost": float("inf")},
    {"on_demand_cost": -1}, {"on_demand_cost": None}, {"on_demand_cost": True},
    {"residual_on_demand_cost": None}, {"residual_on_demand_cost": -1},
    {"residual_on_demand_cost": 11}, {"residual_on_demand_cost": float("nan")},
    {"on_demand_rate": 0}, {"cost_basis": "amortized"}, {"granularity": "daily"},
    {"charge_eligible": False}, {"coverage_verified": False},
    {"coverage_source": ""}, {"coverage_source": None},
    {"accounted_commitment_ids": None}, {"accounted_commitment_ids": ("x", "x")},
    {"environment": None}, {"timestamp": START.replace(tzinfo=None)},
    {"timestamp": START + timedelta(minutes=30)}, {"timestamp": END},
])
def test_invalid_hourly_evidence_is_retained_but_cannot_authorize_purchase(change: dict[str, object]) -> None:
    records = _records()
    records[0] = replace(records[0], **change)
    baseline, = _baselines(records)
    assert baseline.evidence_status == "needs_review"
    assert baseline.hourly_records[0] == records[0]
    assert _portfolio(records).recommendations == []


@pytest.mark.parametrize("change", [
    {"integration_id": "other"}, {"account_id": "other"}, {"currency": "EUR"},
    {"region": "us-west-2"}, {"instance_family": "c5"}, {"group_id": "other"},
    {"provider": "azure"},
])
def test_quotes_must_match_every_scope_boundary(change: dict[str, str]) -> None:
    quote = _quote(replace(SCOPE, **change))
    portfolio = _portfolio(_records(), [quote])
    assert portfolio.recommendations == []
    assert "one_unambiguous_scoped_live_quote_required" in portfolio.withheld_reasons


@pytest.mark.parametrize("change", [
    {"verified": False}, {"pricing_basis": "static_fallback"}, {"pricing_basis": "partial_live"},
    {"source": ""}, {"source": None}, {"quote_id": ""},
    {"captured_at": NOW - timedelta(hours=25)}, {"captured_at": NOW + timedelta(seconds=1)},
    {"captured_at": NOW.replace(tzinfo=None)}, {"valid_until": NOW},
    {"committed_rate": 0}, {"committed_rate": -1}, {"committed_rate": 1},
    {"committed_rate": 2}, {"committed_rate": float("nan")}, {"committed_rate": float("inf")},
    {"on_demand_rate": None}, {"on_demand_rate": 2},
    {"committed_rate": 1e-320},
    {"payment_option": PaymentOption.ALL_UPFRONT}, {"payment_option": PaymentOption.PARTIAL_UPFRONT},
    {"term": Term.THREE_YEAR}, {"commitment_type": CommitmentType.AWS_RI},
])
def test_unverified_stale_invalid_or_unsupported_quotes_are_withheld(change: dict[str, object]) -> None:
    portfolio = _portfolio(_records(), [replace(_quote(), **change)])
    assert portfolio.recommendations == []
    assert portfolio.status == "withheld"
    assert portfolio.withheld_reasons


def test_no_quotes_and_multiple_alternative_quotes_do_not_select_a_discount() -> None:
    assert "verified_live_quotes_required" in _portfolio(_records(), []).withheld_reasons
    portfolio = _portfolio(_records(), [_quote(), replace(_quote(), quote_id="quote-2", committed_rate=0.5)])
    assert "one_unambiguous_scoped_live_quote_required" in portfolio.withheld_reasons
    assert portfolio.recommendations == []


def test_existing_inventory_must_be_explicitly_reconciled() -> None:
    portfolio = _portfolio(_records(), existing=_inventory())
    assert portfolio.recommendations == []
    assert "existing_commitment_inventory_not_reconciled" in portfolio.withheld_reasons


def test_existing_coverage_uses_proven_residual_not_raw_amount_subtraction() -> None:
    records = [replace(r, residual_on_demand_cost=4, accounted_commitment_ids=("existing-1",)) for r in _records()]
    portfolio = _portfolio(records, existing=_inventory())
    rec, = portfolio.recommendations
    assert rec.hourly_commitment == pytest.approx(4 * 0.6)
    assert rec.estimated_monthly_savings == pytest.approx(4 * 0.4 * 730)
    assert portfolio.existing_commitment_utilization is None
    assert portfolio.underutilized_commitments == portfolio.expiring_soon == []


def test_fully_covered_usage_cannot_purchase_again() -> None:
    records = [replace(r, residual_on_demand_cost=0, accounted_commitment_ids=("existing-1",)) for r in _records()]
    portfolio = _portfolio(records, existing=_inventory())
    assert portfolio.recommendations == []
    assert portfolio.evaluations[0]["hourly_commitment"] == 0


def test_missing_inventory_and_new_commitments_invalidate_previous_reconciliation() -> None:
    records = [replace(r, residual_on_demand_cost=4, accounted_commitment_ids=("existing-1",)) for r in _records()]
    assert _portfolio(records).recommendations == []
    inventory = _inventory() + [{**_inventory()[0], "id": "existing-2"}]
    assert _portfolio(records, existing=inventory).recommendations == []


@pytest.mark.parametrize("inventory", [[{}], [{"id": "x"}], [{"id": None}], _inventory() * 2])
def test_unknown_or_duplicate_inventory_cannot_authorize_purchase(inventory: list[dict[str, object]]) -> None:
    assert _portfolio(_records(), existing=inventory).recommendations == []


def test_currency_boundaries_never_produce_a_combined_money_total() -> None:
    eur = replace(SCOPE, currency="EUR")
    records = _records() + _records(scope=eur)
    assert len(_baselines(records)) == 2
    portfolio = _portfolio(records, [_quote(), _quote(eur)])
    assert portfolio.recommendations == []
    assert portfolio.currency is None
    assert portfolio.current_monthly_on_demand is None
    assert "mixed_currencies_run_separately" in portfolio.withheld_reasons


@pytest.mark.parametrize("change", [
    {"account_id": "account-2"}, {"integration_id": "integration-2"},
    {"region": "us-west-2"}, {"instance_family": "c5", "group_id": "c5.large-linux"},
    {"group_id": "m5.large-windows"},
])
def test_disjoint_same_currency_scopes_stay_separate_with_safe_totals(change: dict[str, str]) -> None:
    second = replace(SCOPE, **change)
    records = _records() + _records([20.0] * 72, second)
    assert len(_baselines(records)) == 2
    portfolio = _portfolio(records, [_quote(), _quote(second)])
    assert len(portfolio.recommendations) == 2
    assert {r.scope for r in portfolio.recommendations} == {SCOPE, second}
    assert portfolio.current_monthly_on_demand == 30 * 730
    assert portfolio.total_monthly_savings == pytest.approx(30 * 0.4 * 730)


def test_duplicate_baselines_cannot_double_purchase_the_same_evidence() -> None:
    baselines = _baselines(_records()) * 2
    portfolio = generate_commitment_recommendations(baselines, [], CONFIG, [_quote()], now=NOW)
    assert portfolio.recommendations == []
    assert "duplicate_baseline_scope" in portfolio.withheld_reasons


def test_generator_revalidates_raw_hours_and_ignores_invented_summary_and_rightsizing() -> None:
    baseline, = _baselines(_records())
    baseline.p10_hourly_cost = 999999
    baseline.is_rightsized = True
    rec, = generate_commitment_recommendations([baseline], [], CONFIG, [_quote()], now=NOW).recommendations
    assert rec.hourly_commitment == 6
    assert rec.utilization_confidence is None
    assert "already been rightsized" not in rec.explanation
    baseline.hourly_records = baseline.hourly_records[1:]
    assert generate_commitment_recommendations([baseline], [], CONFIG, [_quote()], now=NOW).recommendations == []


def test_legacy_baseline_is_withheld_even_when_quote_is_present() -> None:
    legacy = UsageBaseline("aws", "us-east-1", "m5", 100, 100, 100, 100, 90)
    assert generate_commitment_recommendations([legacy], [], CONFIG, [_quote()], now=NOW).recommendations == []


@pytest.mark.parametrize("start,end", [(START.replace(tzinfo=None), END), (END, START), (START, START), (START, None)])
def test_invalid_window_is_rejected(start: datetime, end: datetime) -> None:
    with pytest.raises(ValueError, match="window"):
        analyze_hourly_usage_baselines(_records(), window_start=start, window_end=end)


@pytest.mark.parametrize("change", [{"account_id": ""}, {"provider": "other"}, {"currency": ""}, {"currency": "usd"}])
def test_unscoped_hourly_records_cannot_be_grouped(change: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="scope"):
        _baselines(_records(scope=replace(SCOPE, **change)))


def test_training_minimum_excludes_holdout_and_observation_must_be_completed() -> None:
    assert _portfolio(_records(), config=OptimizerConfig()).recommendations == []
    assert _portfolio(_records(), config=replace(CONFIG, min_observation_days=3)).recommendations == []
    portfolio = generate_commitment_recommendations(_baselines(_records()), [], CONFIG, [_quote()], now=START)
    assert portfolio.recommendations == []


def test_default_policy_requires_thirty_training_days_plus_seven_holdout_days() -> None:
    rows = _records([10.0] * (37 * 24))
    end = START + timedelta(days=37)
    quote = replace(_quote(), captured_at=end, valid_until=end + timedelta(hours=2))
    baselines = analyze_hourly_usage_baselines(rows, window_start=START, window_end=end)
    rec, = generate_commitment_recommendations(baselines, [], live_quotes=[quote], now=end).recommendations
    assert rec.math_breakdown["training_hours"] == 30 * 24
    assert rec.math_breakdown["holdout_hours"] == 7 * 24
    assert rec.hourly_commitment == 10 * 0.75 * 0.6


@pytest.mark.parametrize("change", [
    {"coverage_target_pct": -1}, {"coverage_target_pct": 101}, {"coverage_target_pct": float("nan")},
    {"holdout_days": 0}, {"min_observation_days": 0}, {"holdout_days": 1.5},
    {"min_savings_threshold": -1}, {"projection_hours_per_month": float("inf")},
    {"max_quote_age_hours": 0},
])
def test_invalid_config_withholds_instead_of_generating_numbers(change: dict[str, object]) -> None:
    portfolio = _portfolio(_records(), config=replace(CONFIG, **change))
    assert portfolio.recommendations == []
    assert "invalid_optimizer_config_or_clock" in portfolio.withheld_reasons


def test_dev_test_policy_and_savings_threshold_are_honored() -> None:
    rows = [replace(r, environment="dev") for r in _records()]
    assert _portfolio(rows).recommendations == []
    assert _portfolio(rows, config=replace(CONFIG, exclude_dev_test=False)).recommendations
    assert _portfolio(_records(), config=replace(CONFIG, min_savings_threshold=10000)).recommendations == []


def test_three_year_no_upfront_quote_can_be_reviewed_with_explicit_term_policy() -> None:
    quote = replace(_quote(), term=Term.THREE_YEAR)
    rec, = _portfolio(_records(), [quote], config=replace(CONFIG, max_term=Term.THREE_YEAR)).recommendations
    assert rec.term == Term.THREE_YEAR
    assert "term-wide savings remain unproven" in rec.explanation


@pytest.mark.parametrize("provider,product", [("azure", CommitmentType.AZURE_RI), ("gcp", CommitmentType.GCP_FLEXIBLE_CUD)])
def test_other_provider_product_economics_are_explicitly_withheld(provider: str, product: CommitmentType) -> None:
    scope = replace(SCOPE, provider=provider)
    quote = replace(_quote(scope), commitment_type=product)
    portfolio = _portfolio(_records(scope=scope), [quote])
    assert "unsupported_product_or_upfront_cash_flow" in portfolio.withheld_reasons


def test_non_finite_financial_outputs_are_withheld_and_result_is_serializable() -> None:
    portfolio = _portfolio(_records([1e307] * 72))
    assert portfolio.recommendations == []
    assert "non_finite_financial_result" in portfolio.withheld_reasons
    assert asdict(_portfolio(_records()))["recommendations"][0]["scope"]["currency"] == "USD"
