from datetime import datetime, timedelta, timezone

from app.core.recommendations import summarize_recommendation_candidates
from app.optimization.evidence_collector import SignalTimeSeries, build_evidence_bundle
from app.optimization.scan_integration import _compute_overall_confidence, _compute_resource_age
from app.optimization.severity import (
    CorroboratingSignal,
    Recommendation,
    RecommendedAction,
    ResourceClassification,
    ResourceVerdict,
    Severity,
)


def _bundle(*, cost_source: str = "actual"):
    now = datetime.now(timezone.utc)
    timestamps = [now - timedelta(days=7 - index) for index in range(8)]
    signal = SignalTimeSeries(
        metric_name="cpu_avg",
        values=[0.5] * 8,
        timestamps=timestamps,
        interval=timedelta(days=1),
    )
    return build_evidence_bundle(
        resource_id="vm-1",
        provider="azure",
        resource_type="Azure VM",
        provider_state="stopped",
        signals={"cpu_avg": signal},
        resource_age_days=45,
        resource_age_known=True,
        monthly_cost=120,
        cost_source=cost_source,
        resource_name="vm-1",
        cloud_resource_id="vm-1",
    )


def _verdict(action: RecommendedAction = RecommendedAction.TERMINATE):
    classification = (
        ResourceClassification.OVERSIZED
        if action == RecommendedAction.RIGHTSIZE
        else ResourceClassification.CONFIRMED_WASTE
    )
    return ResourceVerdict(
        resource_id="vm-1",
        classification=classification,
        confidence=0.86,
        severity=Severity.HIGH,
        corroborating_signals=[
            CorroboratingSignal(
                signal_name="cpu_avg",
                observed_value=0.5,
                threshold=2.0,
                description="Average CPU remained below threshold.",
            )
        ],
        recommendation=Recommendation(
            action=action,
            description="Review the supported optimization action.",
            estimated_monthly_savings=120,
        ),
        estimated_monthly_waste=120,
    )


def _summary(*, cost_source: str = "actual", action: RecommendedAction = RecommendedAction.TERMINATE):
    return summarize_recommendation_candidates(
        verdicts=[_verdict(action)],
        evidence_bundles=[_bundle(cost_source=cost_source)],
        findings=[{
            "cloud_resource_id": "vm-1",
            "status": "stopped",
            "metadata": {"cost_source": cost_source},
        }],
        user_id="user-1",
        integration_id="int-1",
        provider="azure",
    )


def test_actual_cost_termination_is_included_in_trusted_savings_summary():
    summary = _summary()

    assert summary["claimable_monthly_savings"] == 120
    assert summary["claimable_count"] == 1
    assert summary["confidence_score"] == 86
    assert summary["records"][0]["savings_estimate_status"] == "supported_actual"


def test_unpriced_detector_estimate_is_withheld_from_dashboard_savings():
    summary = _summary(cost_source="billing_unavailable")

    assert summary["detector_monthly_savings"] == 120
    assert summary["claimable_monthly_savings"] == 0
    assert summary["claimable_count"] == 0
    assert summary["records"][0]["savings_estimate_status"] == "withheld_missing_pricing"


def test_rightsizing_without_target_sku_price_is_not_claimed():
    summary = _summary(action=RecommendedAction.RIGHTSIZE)

    assert summary["claimable_monthly_savings"] == 0
    assert summary["records"][0]["quality_status"] == "ready"
    assert summary["records"][0]["savings_estimate_status"] == "withheld_calculation"


def test_missing_resource_age_and_empty_verdicts_do_not_create_confidence():
    assert _compute_resource_age({"metadata": {}}) is None
    assert _compute_overall_confidence([]) == 0
