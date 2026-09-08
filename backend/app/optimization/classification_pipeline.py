"""
Classification Pipeline — 6-stage deterministic resource classification.

Replaces binary scanner logic (stopped=zombie, running=active) with a
multi-stage pipeline that produces graduated verdicts with confidence scores
and full evidence chains.

Pipeline stages:
    1. State Gate — binary state check (stopped/terminated)
    2. Signal Aggregation — multi-metric weighted composite
    3. Pattern Recognition — time-series workload classification
    4. Context Application — tags, names, relationships
    5. Corroboration Check — require 3+ signals agree
    6. Confidence Scoring — Bayesian posterior with fleet calibration
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .evidence_collector import EvidenceBundle, ProviderState, SignalName
from .confidence_model import (
    ThresholdSet,
    compute_confidence,
    compute_stopped_resource_confidence,
)
from .corroboration import check_corroboration, CorroborationResult
from .severity import (
    CorroboratingSignal,
    VetoSignal,
    Recommendation,
    RecommendedAction,
    ResourceClassification,
    ResourceVerdict,
    Severity,
    classification_from_confidence,
    compute_severity,
)

logger = logging.getLogger(__name__)


# Oversized detection: resource is running but using < 15% of its capacity
OVERSIZED_CPU_THRESHOLD = 15.0
OVERSIZED_MEMORY_THRESHOLD = 20.0


def classify_resource(
    evidence: EvidenceBundle,
    thresholds: Optional[ThresholdSet] = None,
    fleet_fp_rate: float = 0.0,
    pattern_result: Optional[str] = None,
) -> ResourceVerdict:
    """
    Run a single resource through the full 6-stage classification pipeline.

    This is the core entry point called by the optimization engine for each
    resource after evidence collection.

    Args:
        evidence: Complete evidence bundle from metrics collection
        thresholds: Adaptive thresholds (optional, defaults used otherwise)
        fleet_fp_rate: Historical false-positive rate for this resource type
        pattern_result: Pre-computed workload pattern (from temporal_intelligence)

    Returns:
        ResourceVerdict with classification, confidence, and evidence chain
    """
    if thresholds is None:
        thresholds = ThresholdSet.default()

    # === STAGE 1: STATE GATE ===
    if evidence.provider_state in (
        ProviderState.STOPPED,
        ProviderState.TERMINATED,
        ProviderState.DEALLOCATED,
        ProviderState.SUSPENDED,
    ):
        return _classify_stopped_resource(evidence, thresholds, fleet_fp_rate)

    # === STAGE 2-6: Running resource classification ===
    return _classify_running_resource(
        evidence, thresholds, fleet_fp_rate, pattern_result
    )


def _classify_stopped_resource(
    evidence: EvidenceBundle,
    thresholds: ThresholdSet,
    fleet_fp_rate: float,
) -> ResourceVerdict:
    """
    Classify a stopped/terminated/deallocated resource.

    Stopped resources can still be legitimate (DR standby, scheduled maintenance,
    dev environments). Context determines whether it's waste.
    """
    # Check veto signals first (DR, ASG, blue/green, etc.)
    corroboration = check_corroboration(evidence, thresholds)

    if corroboration.has_veto:
        # Protected by veto — classify as protected
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.PROTECTED,
            confidence=0.0,
            severity=Severity.NONE,
            vetoing_signals=corroboration.vetoing_signals,
            waste_reason="",
            pattern_detected=None,
        )

    # Compute how long it's been stopped
    if evidence.last_state_change:
        stopped_days = (datetime.now(timezone.utc) - evidence.last_state_change).days
    else:
        stopped_days = evidence.resource_age_days

    # New resource protection
    if evidence.is_new_resource:
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            severity=Severity.NONE,
            waste_reason="Resource too new for classification",
            requires_human_review=False,
        )

    # Build context penalties
    context_penalties = _compute_context_penalties(evidence)

    # Compute confidence for stopped resource
    confidence_result = compute_stopped_resource_confidence(
        evidence, stopped_days, context_penalties
    )

    # Determine classification from confidence
    classification = classification_from_confidence(
        confidence_result.final_confidence,
        evidence.monthly_cost,
    )

    # If still healthy (confidence too low), mark as insufficient
    if classification == ResourceClassification.WELL_UTILIZED and stopped_days < 14:
        classification = ResourceClassification.INSUFFICIENT_DATA

    severity = compute_severity(
        classification, evidence.monthly_cost, confidence_result.final_confidence
    )

    # Build waste reason
    state_name = evidence.provider_state.value
    waste_reason = f"Resource {state_name} for {stopped_days} days"
    if evidence.monthly_cost > 0:
        waste_reason += f" (still incurring ${evidence.monthly_cost:.0f}/mo in disk/IP costs)"

    # Build recommendation
    recommendation = None
    if classification in (
        ResourceClassification.CRITICAL_WASTE,
        ResourceClassification.CONFIRMED_WASTE,
        ResourceClassification.LIKELY_WASTE,
    ):
        recommendation = Recommendation(
            action=RecommendedAction.TERMINATE,
            description=f"Terminate {state_name} resource and release associated storage/IPs",
            estimated_monthly_savings=evidence.monthly_cost,
            effort="low",
            risk="medium" if stopped_days < 30 else "low",
        )

    return ResourceVerdict(
        resource_id=evidence.resource_id,
        classification=classification,
        confidence=confidence_result.final_confidence,
        severity=severity,
        corroborating_signals=corroboration.corroborating_signals,
        vetoing_signals=corroboration.vetoing_signals,
        recommendation=recommendation,
        estimated_monthly_waste=evidence.monthly_cost if classification != ResourceClassification.WELL_UTILIZED else 0.0,
        waste_reason=waste_reason,
        requires_human_review=0.50 <= confidence_result.final_confidence <= 0.75,
        ai_verification_needed=0.50 <= confidence_result.final_confidence <= 0.75,
    )


def _classify_running_resource(
    evidence: EvidenceBundle,
    thresholds: ThresholdSet,
    fleet_fp_rate: float,
    pattern_result: Optional[str],
) -> ResourceVerdict:
    """
    Classify a running resource using multi-signal analysis.

    Running resources require signal evidence (CPU, network, disk, etc.)
    to be classified as waste. Binary state alone is never enough.
    """
    # New resource protection
    if evidence.is_new_resource:
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            severity=Severity.NONE,
            waste_reason="Resource too new for classification",
        )

    # Insufficient data protection
    if not evidence.has_sufficient_data:
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            severity=Severity.NONE,
            waste_reason=f"Only {evidence.observation_days} days of data (minimum 7 required)",
        )

    # === STAGE 3: PATTERN RECOGNITION ===
    if pattern_result and pattern_result in (
        "diurnal", "weekly", "burst_sporadic", "growing", "monthly_batch",
    ):
        # Known workload pattern — this is a legitimate resource
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.WELL_UTILIZED,
            confidence=0.0,
            severity=Severity.NONE,
            pattern_detected=pattern_result,
            waste_reason="",
            context_factors=[f"Workload pattern detected: {pattern_result}"],
        )

    # === STAGE 4: CONTEXT APPLICATION ===
    # Check for dev/test environments (lower severity, not a veto)
    context_penalties = _compute_context_penalties(evidence)

    # === STAGE 5: CORROBORATION CHECK ===
    corroboration = check_corroboration(evidence, thresholds)

    if corroboration.has_veto:
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.PROTECTED,
            confidence=0.0,
            severity=Severity.NONE,
            vetoing_signals=corroboration.vetoing_signals,
            waste_reason="",
        )

    if not corroboration.passed:
        # Not enough signals — check if oversized instead
        oversized_result = _check_oversized(evidence, thresholds)
        if oversized_result:
            return oversized_result

        # Not waste, not oversized — well utilized
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.WELL_UTILIZED,
            confidence=0.0,
            severity=Severity.NONE,
            corroborating_signals=corroboration.corroborating_signals,
            waste_reason="",
            context_factors=[corroboration.reason],
        )

    # === STAGE 6: CONFIDENCE SCORING ===
    confidence_result = compute_confidence(
        evidence,
        thresholds=thresholds,
        fleet_fp_rate=fleet_fp_rate,
        context_penalties=context_penalties,
    )

    classification = classification_from_confidence(
        confidence_result.final_confidence,
        evidence.monthly_cost,
    )

    # If confidence is too low for waste classification, downgrade
    if classification == ResourceClassification.WELL_UTILIZED:
        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.WELL_UTILIZED,
            confidence=confidence_result.final_confidence,
            severity=Severity.NONE,
            corroborating_signals=corroboration.corroborating_signals,
            waste_reason="",
        )

    severity = compute_severity(
        classification, evidence.monthly_cost, confidence_result.final_confidence
    )

    # Build waste reason from corroborating signals
    signal_descriptions = [s.description for s in corroboration.corroborating_signals[:3]]
    waste_reason = "; ".join(signal_descriptions)

    # Build recommendation
    recommendation = _build_recommendation(evidence, classification)

    return ResourceVerdict(
        resource_id=evidence.resource_id,
        classification=classification,
        confidence=confidence_result.final_confidence,
        severity=severity,
        corroborating_signals=corroboration.corroborating_signals,
        vetoing_signals=corroboration.vetoing_signals,
        pattern_detected=pattern_result,
        recommendation=recommendation,
        estimated_monthly_waste=evidence.monthly_cost,
        waste_reason=waste_reason,
        requires_human_review=0.50 <= confidence_result.final_confidence <= 0.75,
        ai_verification_needed=0.50 <= confidence_result.final_confidence <= 0.75,
    )


def _check_oversized(
    evidence: EvidenceBundle,
    thresholds: ThresholdSet,
) -> Optional[ResourceVerdict]:
    """Check if a running resource is oversized (could use a smaller instance)."""
    cpu_signal = evidence.signals.get(SignalName.CPU_AVG.value)
    mem_signal = evidence.signals.get(SignalName.MEMORY_USED_PCT.value)

    is_cpu_oversized = (
        cpu_signal
        and cpu_signal.values
        and cpu_signal.p90 < OVERSIZED_CPU_THRESHOLD
        and evidence.observation_days >= 14
    )

    is_mem_oversized = (
        mem_signal
        and mem_signal.values
        and mem_signal.p90 < OVERSIZED_MEMORY_THRESHOLD
    )

    if is_cpu_oversized:
        # Try specific SKU recommendation via rightsizing engine
        target_sku = None
        rightsize_description = "Downsize to a smaller instance type matching actual utilization"
        estimated_savings = evidence.monthly_cost * 0.5
        savings_pct = 50.0

        try:
            from ..core.rightsizing_engine import recommend_rightsizing
            rec = recommend_rightsizing(
                provider=evidence.provider,
                instance_type=evidence.resource_type.split()[-1] if " " in evidence.resource_type else evidence.resource_type,
                p95_cpu=cpu_signal.p95 if hasattr(cpu_signal, "p95") else cpu_signal.p90,
                monthly_cost=evidence.monthly_cost,
            )
            if not rec:
                vm_size = (evidence.tags or {}).get("vm_size") or (evidence.tags or {}).get("instance_type", "")
                if vm_size:
                    rec = recommend_rightsizing(
                        provider=evidence.provider,
                        instance_type=vm_size,
                        p95_cpu=cpu_signal.p95 if hasattr(cpu_signal, "p95") else cpu_signal.p90,
                        monthly_cost=evidence.monthly_cost,
                    )
            if rec:
                target_sku = rec.target_sku
                savings_pct = rec.estimated_savings_pct
                estimated_savings = evidence.monthly_cost * savings_pct / 100
                rightsize_description = rec.reason
        except Exception:
            pass

        return ResourceVerdict(
            resource_id=evidence.resource_id,
            classification=ResourceClassification.OVERSIZED,
            confidence=0.75 if evidence.observation_days >= 30 else 0.60,
            severity=Severity.INFO,
            corroborating_signals=[
                CorroboratingSignal(
                    signal_name=SignalName.CPU_AVG.value,
                    observed_value=round(cpu_signal.p90, 2),
                    threshold=OVERSIZED_CPU_THRESHOLD,
                    description=f"P90 CPU at {cpu_signal.p90:.1f}% — only using {cpu_signal.p90:.0f}% of capacity",
                )
            ],
            recommendation=Recommendation(
                action=RecommendedAction.RIGHTSIZE,
                description=rightsize_description,
                estimated_monthly_savings=estimated_savings,
                effort="medium",
                risk="low",
                target_sku=target_sku,
            ),
            estimated_monthly_waste=estimated_savings,
            waste_reason=f"P90 CPU at {cpu_signal.p90:.1f}% over {evidence.observation_days} days — significantly oversized",
        )

    return None


def _compute_context_penalties(
    evidence: EvidenceBundle,
) -> List[Tuple[str, float]]:
    """Compute context-based confidence penalties."""
    penalties: List[Tuple[str, float]] = []

    tags_lower = {k.lower(): v.lower() for k, v in evidence.tags.items()}
    all_values = set(tags_lower.values())

    # Dev/test environments — waste is less critical, reduce confidence slightly
    from .corroboration import ENVIRONMENT_TAGS
    for env_tag in ENVIRONMENT_TAGS:
        if env_tag in all_values:
            penalties.append(("dev/test environment", 0.10))
            break

    # Public IP attached — resource may serve external traffic
    # (This is a signal from metadata, not a full veto)
    if evidence.tags.get("has_public_ip") == "true":
        penalties.append(("has public IP", 0.05))

    # Resource has many tags — well-managed, less likely to be abandoned
    if len(evidence.tags) >= 5:
        penalties.append(("well-tagged resource", 0.05))

    return penalties


def _build_recommendation(
    evidence: EvidenceBundle,
    classification: ResourceClassification,
) -> Optional[Recommendation]:
    """Build an actionable recommendation based on classification."""

    if classification in (
        ResourceClassification.CRITICAL_WASTE,
        ResourceClassification.CONFIRMED_WASTE,
    ):
        return Recommendation(
            action=RecommendedAction.TERMINATE,
            description="Terminate idle resource to eliminate waste",
            estimated_monthly_savings=evidence.monthly_cost,
            effort="low",
            risk="low" if evidence.provider_state != ProviderState.RUNNING else "medium",
        )
    elif classification == ResourceClassification.LIKELY_WASTE:
        return Recommendation(
            action=RecommendedAction.STOP,
            description="Stop resource to prevent further cost while you investigate",
            estimated_monthly_savings=evidence.monthly_cost * 0.7,
            effort="low",
            risk="low",
        )
    elif classification == ResourceClassification.POSSIBLE_WASTE:
        return Recommendation(
            action=RecommendedAction.INVESTIGATE,
            description="Review resource usage — signals suggest it may be idle",
            estimated_monthly_savings=evidence.monthly_cost,
            effort="low",
            risk="none",
        )

    return None


def classify_batch(
    evidence_bundles: List[EvidenceBundle],
    thresholds: Optional[ThresholdSet] = None,
    fleet_fp_rate: float = 0.0,
    pattern_results: Optional[Dict[str, str]] = None,
) -> List[ResourceVerdict]:
    """
    Classify a batch of resources through the pipeline.

    This is the primary entry point for the scan flow.
    """
    if thresholds is None:
        thresholds = ThresholdSet.default()
    if pattern_results is None:
        pattern_results = {}

    verdicts = []
    for evidence in evidence_bundles:
        pattern = pattern_results.get(evidence.resource_id)
        try:
            verdict = classify_resource(
                evidence,
                thresholds=thresholds,
                fleet_fp_rate=fleet_fp_rate,
                pattern_result=pattern,
            )
            verdicts.append(verdict)
        except Exception as e:
            logger.warning(
                f"Classification failed for {evidence.resource_id}: {e}"
            )
            verdicts.append(ResourceVerdict(
                resource_id=evidence.resource_id,
                classification=ResourceClassification.INSUFFICIENT_DATA,
                confidence=0.0,
                severity=Severity.NONE,
                waste_reason=f"Classification error: {str(e)[:100]}",
            ))

    return verdicts
