"""Evidence-gated, offline commitment scenarios, not purchase instructions.

Daily bills cannot establish hourly eligibility or utilization. Hourly callers
must supply disjoint, homogeneous price groups, including zero hours, and attest
residual costs after ALL existing commitments (including sharing). Quotes come
from a trusted live-pricing adapter; this module does not fetch or independently
authenticate provider prices or billing evidence.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple, TypeGuard

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


@dataclass(frozen=True)
class UsageScope:
    """group_id identifies a disjoint SKU/OS/tenancy/eligibility price group."""

    provider: str
    integration_id: str
    account_id: str
    region: str
    instance_family: str
    currency: str
    group_id: str


@dataclass(frozen=True)
class HourlyUsageRecord:
    """One full hour of eligible OD-equivalent cost, never amortized bill cost.

    accounted_commitment_ids identifies the ENTIRE inventory supplied to the
    optimizer, not just commitments that consumed this hour's usage. An empty
    tuple explicitly attests no existing coverage; None means unknown coverage.
    on_demand_rate uses the identical billing unit as the matched live quote.
    """

    scope: UsageScope
    timestamp: datetime
    on_demand_cost: float
    on_demand_rate: float
    residual_on_demand_cost: Optional[float] = None
    granularity: str = "hourly"
    cost_basis: str = "on_demand_equivalent"
    charge_eligible: bool = False
    coverage_verified: bool = False
    coverage_source: str = ""
    accounted_commitment_ids: Optional[Tuple[str, ...]] = None
    environment: str = ""


@dataclass(frozen=True)
class LivePriceQuote:
    """Matched OD and all-in committed rates per identical billing unit/hour.

    Scope contains provider, region, family, currency and account/group identity.
    verified attests a trusted adapter checked eligibility and matched live rates
    from source. Only no-upfront AWS Savings Plan economics are implemented here.
    """

    scope: UsageScope
    commitment_type: CommitmentType
    term: Term
    payment_option: PaymentOption
    on_demand_rate: float
    committed_rate: float
    captured_at: datetime
    valid_until: datetime
    source: str
    quote_id: str
    verified: bool = False
    pricing_basis: str = "live_api"


@dataclass
class UsageBaseline:
    """Legacy summary fields plus the evidence required to support a scenario."""

    provider: str
    region: str
    instance_family: str
    hourly_on_demand_cost: Optional[float]
    p10_hourly_cost: Optional[float]
    p50_hourly_cost: Optional[float]
    p75_hourly_cost: Optional[float]
    observation_days: int
    instance_count_at_baseline: Optional[int] = None
    is_rightsized: bool = False
    scope: Optional[UsageScope] = None
    hourly_records: Tuple[HourlyUsageRecord, ...] = ()
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    missing_hours: int = 0
    duplicate_hours: int = 0
    evidence_status: str = "needs_review"
    review_reasons: Tuple[str, ...] = ()


@dataclass
class CommitmentRecommendation:
    """A review-required historical scenario, without calibrated confidence."""

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
    utilization_confidence: Optional[float]
    risk_level: str
    explanation: str
    math_breakdown: Dict[str, object]
    priority: int = 0
    scope: Optional[UsageScope] = None
    status: str = "needs_review"
    pricing_basis: str = "live_api"


@dataclass
class CommitmentPortfolio:
    """Totals describe residual-only scenarios, never authoritative bill totals."""

    recommendations: List[CommitmentRecommendation]
    total_monthly_savings: float
    total_annual_savings: float
    current_monthly_on_demand: Optional[float]
    projected_monthly_after_commitments: Optional[float]
    overall_coverage_pct: Optional[float]
    overall_savings_pct: Optional[float]
    existing_commitment_utilization: Optional[float]
    underutilized_commitments: List[Dict[str, object]]
    expiring_soon: List[Dict[str, object]]
    strategy_summary: str
    currency: Optional[str] = None
    status: str = "withheld"
    withheld_reasons: List[str] = field(default_factory=list)
    evaluations: List[Dict[str, object]] = field(default_factory=list)


@dataclass
class OptimizerConfig:
    """Sizing/backtest policies, not statistical confidence or price defaults."""

    coverage_target_pct: float = 75.0
    max_term: Term = Term.ONE_YEAR
    preferred_payment: PaymentOption = PaymentOption.NO_UPFRONT
    min_observation_days: int = 30  # Training, excluding holdout.
    min_savings_threshold: float = 50.0  # Portfolio currency per month.
    exclude_dev_test: bool = True
    holdout_days: int = 7
    max_quote_age_hours: float = 24.0
    projection_hours_per_month: float = 730.0  # Normalization, not a forecast.


def analyze_usage_baselines(
    resources: List[Dict[str, object]],
    daily_spend: List[Dict[str, object]],
    provider: str,
) -> List[UsageBaseline]:
    """Compatibility entry point: daily spend/inventory cannot prove hourly use."""
    logger.info("Commitment baselines withheld: timestamped hourly evidence required")
    return []


def _number(value: object) -> TypeGuard[float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _aware(value: object) -> TypeGuard[datetime]:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _hour(value: object) -> bool:
    if not _aware(value):
        return False
    utc = value.astimezone(timezone.utc)
    return utc.minute == utc.second == utc.microsecond == 0


def _valid_scope(scope: UsageScope) -> bool:
    return (
        isinstance(scope, UsageScope)
        and all(isinstance(v, str) and v.strip() == v and v for v in vars(scope).values())
        and scope.provider in {"aws", "azure", "gcp"}
        and len(scope.currency) == 3
        and scope.currency.isascii()
        and scope.currency.isalpha()
        and scope.currency.isupper()
    )


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Empirical lower order statistic; not a future utilization guarantee."""
    return sorted(values)[math.floor((len(values) - 1) * fraction)]


def analyze_hourly_usage_baselines(
    records: Sequence[HourlyUsageRecord],
    *,
    window_start: datetime,
    window_end: datetime,
) -> List[UsageBaseline]:
    """Validate an end-exclusive window; retain gaps, duplicates and zeros.

    Malformed scope/window raises ValueError because it cannot be grouped safely.
    Bad evidence within a known scope is retained as needs_review, never imputed.
    """
    if not _hour(window_start) or not _hour(window_end):
        raise ValueError("An aware, hour-aligned, nonempty observation window is required")
    start, end = window_start.astimezone(timezone.utc), window_end.astimezone(timezone.utc)
    if end <= start:
        raise ValueError("A nonempty observation window is required")
    expected = int((end - start).total_seconds() / 3600)
    groups: Dict[UsageScope, List[HourlyUsageRecord]] = {}
    for row in records:
        if not isinstance(row, HourlyUsageRecord) or not _valid_scope(row.scope):
            raise ValueError("Hourly records require explicit provider/account/currency/group scope")
        groups.setdefault(row.scope, []).append(row)

    baselines = []
    for scope, rows in groups.items():
        reasons = set()
        timestamps = []
        costs = []
        for row in rows:
            if not _hour(row.timestamp) or not start <= row.timestamp < end:
                reasons.add("invalid_or_out_of_window_timestamp")
            else:
                timestamps.append(row.timestamp.astimezone(timezone.utc))
            if row.granularity != "hourly" or row.cost_basis != "on_demand_equivalent":
                reasons.add("hourly_on_demand_equivalent_required")
            if row.charge_eligible is not True:
                reasons.add("charge_eligibility_unproven")
            if not isinstance(row.environment, str):
                reasons.add("invalid_environment")
            if (
                row.coverage_verified is not True
                or not isinstance(row.coverage_source, str) or not row.coverage_source.strip()
                or not isinstance(row.accounted_commitment_ids, tuple)
                or any(not isinstance(i, str) or not i for i in row.accounted_commitment_ids)
                or len(set(row.accounted_commitment_ids)) != len(row.accounted_commitment_ids)
            ):
                reasons.add("existing_coverage_unproven")
            residual = row.residual_on_demand_cost
            if (
                not _number(row.on_demand_cost) or row.on_demand_cost < 0
                or not _number(row.on_demand_rate) or row.on_demand_rate <= 0
                or not _number(residual) or not 0 <= residual <= row.on_demand_cost
            ):
                reasons.add("invalid_cost_or_residual")
            else:
                costs.append(residual)
        duplicate = len(timestamps) - len(set(timestamps))
        missing = expected - len(set(timestamps))
        if duplicate:
            reasons.add("duplicate_hours")
        if missing:
            reasons.add("missing_hours")
        valid = not reasons
        baselines.append(UsageBaseline(
            provider=scope.provider, region=scope.region, instance_family=scope.instance_family,
            hourly_on_demand_cost=math.fsum(c / len(costs) for c in costs) if valid else None,
            p10_hourly_cost=_percentile(costs, 0.10) if valid else None,
            p50_hourly_cost=_percentile(costs, 0.50) if valid else None,
            p75_hourly_cost=_percentile(costs, 0.75) if valid else None,
            observation_days=len(set(timestamps)) // 24,
            scope=scope, hourly_records=tuple(rows), window_start=start, window_end=end,
            missing_hours=missing, duplicate_hours=duplicate,
            evidence_status="validated" if valid else "needs_review",
            review_reasons=tuple(sorted(reasons)),
        ))
    return baselines


def _quote_problem(quote: LivePriceQuote, config: OptimizerConfig, now: datetime) -> Optional[str]:
    if (
        quote.verified is not True or quote.pricing_basis != "live_api"
        or not isinstance(quote.source, str) or not quote.source.strip()
        or not isinstance(quote.quote_id, str) or not quote.quote_id.strip()
    ):
        return "verified_live_quote_required"
    if (
        not _aware(quote.captured_at) or not _aware(quote.valid_until)
        or not quote.captured_at <= now < quote.valid_until
        or (now - quote.captured_at).total_seconds() / 3600 > config.max_quote_age_hours
    ):
        return "stale_or_invalid_quote_timestamp"
    if (
        quote.scope.provider != "aws"
        or quote.commitment_type not in {CommitmentType.AWS_COMPUTE_SP, CommitmentType.AWS_EC2_SP}
        or quote.payment_option != PaymentOption.NO_UPFRONT
    ):
        return "unsupported_product_or_upfront_cash_flow"
    if (
        quote.payment_option != config.preferred_payment or quote.term not in set(Term)
        or (config.max_term == Term.ONE_YEAR and quote.term != Term.ONE_YEAR)
    ):
        return "quote_term_or_payment_mismatch"
    if (
        not _number(quote.on_demand_rate) or not _number(quote.committed_rate)
        or not 0 < quote.committed_rate < quote.on_demand_rate
    ):
        return "invalid_matched_quote_rates"
    ratio = quote.committed_rate / quote.on_demand_rate
    if not 0 < ratio < 1 or not 0 < 1 - ratio < 1:
        return "unrepresentable_quote_ratio"
    return None


def _backtest(costs: Sequence[float], covered_od: float, ratio: float) -> Dict[str, float]:
    # Pay the full committed-rate obligation every hour, including zero-use hours.
    hourly_commitment = covered_od * ratio
    on_demand = math.fsum(costs)
    covered = math.fsum(min(cost, covered_od) for cost in costs)
    committed = hourly_commitment * len(costs)
    uncovered = math.fsum(max(0.0, cost - covered_od) for cost in costs)
    unused = math.fsum(max(0.0, hourly_commitment - min(cost, covered_od) * ratio) for cost in costs)
    return {
        "hourly_commitment": hourly_commitment,
        "covered_on_demand_hourly_capacity": covered_od,
        "holdout_on_demand_cost": on_demand,
        "holdout_covered_on_demand_cost": covered,
        "holdout_committed_cost": committed,
        "holdout_uncovered_on_demand_cost": uncovered,
        "holdout_unused_commitment_cost": unused,
        "holdout_net_savings": covered - committed,
        "holdout_coverage_pct": covered / on_demand * 100 if on_demand else 0.0,
        "holdout_utilization_pct": (committed - unused) / committed * 100 if committed else 0.0,
    }


def generate_commitment_recommendations(
    baselines: List[UsageBaseline],
    existing_commitments: List[Dict[str, object]],
    config: Optional[OptimizerConfig] = None,
    live_quotes: Optional[Sequence[LivePriceQuote]] = None,
    *,
    now: Optional[datetime] = None,
) -> CommitmentPortfolio:
    """Backtest one quote per scope; withhold ambiguous/incomplete portfolios.

    No SDK calls, coverage inference, FX conversion, renewal advice or rightsizing
    claims. Inventory IDs must be globally unique and include shared commitments;
    each inventory row needs provider/integration_id/account_id/currency scope.
    Positive holdout savings are scenarios for review, not term-wide forecasts.
    """
    config = config or OptimizerConfig()
    now = datetime.now(timezone.utc) if now is None else now
    if _aware(now):
        now = now.astimezone(timezone.utc)
    result = CommitmentPortfolio([], 0.0, 0.0, None, None, None, None, None, [], [], "")
    reasons = result.withheld_reasons
    if not live_quotes:
        reasons.append("verified_live_quotes_required")
    if not baselines:
        reasons.append("validated_hourly_residual_evidence_required")
    if (
        not _aware(now) or not _number(config.coverage_target_pct)
        or not 0 < config.coverage_target_pct <= 100
        or not _number(config.min_savings_threshold) or config.min_savings_threshold < 0
        or type(config.min_observation_days) is not int or config.min_observation_days < 1
        or type(config.holdout_days) is not int or config.holdout_days < 1
        or not _number(config.max_quote_age_hours) or config.max_quote_age_hours <= 0
        or not _number(config.projection_hours_per_month) or config.projection_hours_per_month <= 0
        or config.max_term not in set(Term) or config.preferred_payment not in set(PaymentOption)
    ):
        reasons.append("invalid_optimizer_config_or_clock")

    # Amount fields have no established unit here; never subtract or sum them.
    inventory_ids = [c.get("id") for c in existing_commitments]
    if any(not isinstance(i, str) or not i for i in inventory_ids):
        reasons.append("existing_commitment_inventory_ids_required")
    elif len(set(inventory_ids)) != len(inventory_ids):
        reasons.append("duplicate_existing_commitment_ids")
    if any(
        not isinstance(c.get(key), str) or not c[key].strip()
        for c in existing_commitments
        for key in ("provider", "integration_id", "account_id", "currency")
    ):
        reasons.append("existing_commitment_scope_required")

    validated = []
    for baseline in baselines:
        if not baseline.hourly_records or baseline.scope is None:
            reasons.append("legacy_summary_is_not_hourly_evidence")
            continue
        try:
            rebuilt = analyze_hourly_usage_baselines(
                baseline.hourly_records,
                window_start=baseline.window_start, window_end=baseline.window_end,
            )
        except ValueError:
            reasons.append("invalid_hourly_evidence_scope_or_window")
            continue
        if len(rebuilt) != 1 or rebuilt[0].scope != baseline.scope:
            reasons.append("baseline_scope_mismatch")
            continue
        checked = rebuilt[0]
        if checked.evidence_status != "validated":
            reasons.extend(checked.review_reasons)
        validated.append(checked)

    scopes = [b.scope for b in validated]
    if len(set(scopes)) != len(scopes):
        reasons.append("duplicate_baseline_scope")
    currencies = {s.currency for s in scopes}
    if len(currencies) > 1:
        reasons.append("mixed_currencies_run_separately")
    if len({(b.window_start, b.window_end) for b in validated}) > 1:
        reasons.append("observation_windows_must_match")

    prepared = []
    if not reasons:
        for baseline in validated:
            rows = sorted(baseline.hourly_records, key=lambda r: r.timestamp.astimezone(timezone.utc))
            if baseline.window_end > now or baseline.observation_days < config.min_observation_days + config.holdout_days:
                reasons.append("insufficient_completed_training_and_holdout_hours")
            if any(set(r.accounted_commitment_ids) != set(inventory_ids) for r in rows):
                reasons.append("existing_commitment_inventory_not_reconciled")
            if config.exclude_dev_test and any(r.environment.lower() in {"dev", "test", "staging", "sandbox"} for r in rows):
                reasons.append("dev_test_usage_excluded")
            matches = [q for q in live_quotes if q.scope == baseline.scope]
            if len(matches) != 1:
                reasons.append("one_unambiguous_scoped_live_quote_required")
                continue
            quote = matches[0]
            problem = _quote_problem(quote, config, now)
            if problem:
                reasons.append(problem)
            elif any(r.on_demand_rate != quote.on_demand_rate for r in rows):
                reasons.append("hourly_and_quoted_on_demand_rates_must_match")
            prepared.append((baseline, rows, quote))

    if reasons:
        result.withheld_reasons = sorted(set(reasons))
        result.strategy_summary = "Recommendations withheld: " + "; ".join(result.withheld_reasons) + "."
        return result

    result.currency = next(iter(currencies))
    monthly_on_demand = []
    monthly_covered = []
    holdout_hours = config.holdout_days * 24
    factor = config.projection_hours_per_month / holdout_hours
    for baseline, rows, quote in prepared:
        training = [r.residual_on_demand_cost for r in rows[:-holdout_hours]]
        holdout = [r.residual_on_demand_cost for r in rows[-holdout_hours:]]
        target = _percentile(training, 0.10) * (config.coverage_target_pct / 100)
        ratio = quote.committed_rate / quote.on_demand_rate
        try:
            math_values = _backtest(holdout, target, ratio)
            monthly_savings = math_values["holdout_net_savings"] * factor
            monthly_cost = math_values["holdout_on_demand_cost"] * factor
            monthly_commitment = math_values["hourly_commitment"] * config.projection_hours_per_month
            if (
                not all(math.isfinite(v) for v in [*math_values.values(), monthly_savings * 12, monthly_cost, monthly_commitment])
                or (target > 0 and math_values["hourly_commitment"] == 0)
            ):
                raise ValueError("Non-finite financial result")
        except (OverflowError, ValueError):
            result.recommendations.clear()
            result.withheld_reasons.append("non_finite_financial_result")
            result.strategy_summary = "Recommendations withheld: non-finite financial result."
            return result
        monthly_on_demand.append(monthly_cost)
        breakdown: Dict[str, object] = {
            **math_values,
            "scope": baseline.scope,
            "quote_id": quote.quote_id,
            "quote_source": quote.source,
            "quote_captured_at": quote.captured_at.isoformat(),
            "quote_valid_until": quote.valid_until.isoformat(),
            "pricing_basis": quote.pricing_basis,
            "on_demand_rate": quote.on_demand_rate,
            "committed_rate": quote.committed_rate,
            "training_hours": len(training),
            "training_p10_residual_on_demand_cost": _percentile(training, 0.10),
            "holdout_hours": holdout_hours,
            "projection_hours_per_month": config.projection_hours_per_month,
            "estimated_monthly_savings": monthly_savings,
            "status": "needs_review" if monthly_savings > 0 and target > 0 else "withheld",
        }
        result.evaluations.append(breakdown)
        if target <= 0 or monthly_savings <= 0 or monthly_savings < config.min_savings_threshold:
            breakdown["status"] = "withheld"
            breakdown["reason"] = "no_positive_baseline_or_holdout_savings_above_threshold"
            continue
        monthly_covered.append(math_values["holdout_covered_on_demand_cost"] * factor)
        result.recommendations.append(CommitmentRecommendation(
            commitment_type=quote.commitment_type, provider=baseline.provider,
            region=baseline.region, instance_family=baseline.instance_family,
            term=quote.term, payment_option=quote.payment_option,
            hourly_commitment=math_values["hourly_commitment"], monthly_commitment=monthly_commitment,
            discount_rate=1 - ratio, estimated_monthly_savings=monthly_savings,
            estimated_annual_savings=monthly_savings * 12,
            coverage_pct=math_values["holdout_coverage_pct"], utilization_confidence=None,
            risk_level="needs_review", scope=baseline.scope, math_breakdown=breakdown,
            explanation=(
                "Review required: committed-rate hourly obligation evaluated on chronological "
                "holdout residual usage, including unused commitment cost. Monthly/annual values "
                "are normalized historical scenarios, not forecasts or purchase approval. "
                "Future usage, rightsizing, renewal and term-wide savings remain unproven."
            ),
        ))

    try:
        savings = math.fsum(r.estimated_monthly_savings for r in result.recommendations)
        on_demand = math.fsum(monthly_on_demand)
        covered = math.fsum(monthly_covered)
        if not all(math.isfinite(v) for v in (savings * 12, on_demand, covered)):
            raise ValueError("Non-finite portfolio total")
    except (OverflowError, ValueError):
        result.recommendations.clear()
        result.withheld_reasons.append("non_finite_portfolio_total")
        result.strategy_summary = "Recommendations withheld: non-finite portfolio total."
        return result
    result.total_monthly_savings = savings
    result.total_annual_savings = savings * 12
    result.current_monthly_on_demand = on_demand
    result.projected_monthly_after_commitments = result.current_monthly_on_demand - result.total_monthly_savings
    if result.current_monthly_on_demand:
        result.overall_coverage_pct = covered / result.current_monthly_on_demand * 100
        result.overall_savings_pct = result.total_monthly_savings / result.current_monthly_on_demand * 100
    result.status = "needs_review" if result.recommendations else "withheld"
    result.strategy_summary = (
        "Historical residual-only scenarios require review; no calibrated confidence or purchase approval. "
        f"Totals use {result.currency} and {config.projection_hours_per_month:g} hours/month, "
        "not total bills or term forecasts. Existing commitment utilization/renewal is not evaluated."
        if result.recommendations else
        "Recommendations withheld: no positive baseline or holdout savings above threshold; see evaluations."
    )
    return result
