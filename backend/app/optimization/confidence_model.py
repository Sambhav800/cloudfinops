"""
Confidence Model — Bayesian confidence computation from multi-signal evidence.

Replaces Azure's step-function scoring (line 434-490 of azure.py) with a smooth
sigmoid-based model that adapts to fleet data and penalizes context factors.

Formula:
    Confidence = BaseSignalScore × DataQualityFactor × FleetCalibration × (1 - ContextPenalty)

Each component is independently computable and explainable.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .evidence_collector import EvidenceBundle, ProviderState, SignalName


# Default thresholds (before fleet calibration)
DEFAULT_THRESHOLDS = {
    SignalName.CPU_AVG: 2.0,           # % average CPU below which = idle signal
    SignalName.CPU_MAX: 10.0,          # % max CPU below which = strong idle signal
    SignalName.NETWORK_IN_MB: 5.0,     # MB total inbound below which = idle signal
    SignalName.NETWORK_OUT_MB: 2.0,    # MB total outbound below which = idle signal
    SignalName.DISK_READ_OPS: 10.0,    # ops/day below which = idle signal
    SignalName.DISK_WRITE_OPS: 5.0,    # ops/day below which = idle signal
    SignalName.MEMORY_USED_PCT: 10.0,  # % memory below which = idle signal
    SignalName.CONNECTIONS: 1.0,       # connections below which = idle signal
}

# Signal weights for composite scoring
SIGNAL_WEIGHTS = {
    SignalName.CPU_AVG: 0.30,
    SignalName.NETWORK_IN_MB: 0.20,
    SignalName.DISK_READ_OPS: 0.15,
    SignalName.CPU_MAX: 0.10,
    SignalName.NETWORK_OUT_MB: 0.10,
    SignalName.MEMORY_USED_PCT: 0.10,
    SignalName.CONNECTIONS: 0.05,
}


@dataclass
class ThresholdSet:
    """Adaptive thresholds for a specific resource type/fleet."""

    thresholds: Dict[str, float]
    source: str = "default"  # default | fleet_p10 | user_feedback | resource_type
    last_calibrated: Optional[str] = None
    sample_size: int = 0

    @classmethod
    def default(cls) -> "ThresholdSet":
        return cls(thresholds={k.value: v for k, v in DEFAULT_THRESHOLDS.items()})

    def get(self, signal_name: str) -> float:
        return self.thresholds.get(signal_name, DEFAULT_THRESHOLDS.get(signal_name, 5.0))


@dataclass
class ConfidenceBreakdown:
    """Explainable confidence computation result."""

    final_confidence: float
    base_signal_score: float
    data_quality_factor: float
    fleet_calibration_factor: float
    context_penalty: float
    per_signal_scores: Dict[str, float]
    explanation: str


def compute_confidence(
    evidence: EvidenceBundle,
    thresholds: Optional[ThresholdSet] = None,
    fleet_fp_rate: float = 0.0,
    context_penalties: Optional[List[Tuple[str, float]]] = None,
) -> ConfidenceBreakdown:
    """
    Compute classification confidence from evidence bundle.

    Uses sigmoid function for smooth degradation near thresholds instead of
    step functions. This means a resource at 1.9% CPU vs 2.1% CPU doesn't
    jump from "definitely waste" to "definitely healthy" — the transition is gradual.

    Args:
        evidence: The resource's complete evidence bundle
        thresholds: Adaptive thresholds (falls back to defaults)
        fleet_fp_rate: Historical false-positive rate for this resource type (0.0-1.0)
        context_penalties: List of (reason, penalty_amount) tuples

    Returns:
        ConfidenceBreakdown with final score and per-component explanation
    """
    if thresholds is None:
        thresholds = ThresholdSet.default()

    if context_penalties is None:
        context_penalties = []

    # Stage 1: Base Signal Score (weighted sigmoid composite)
    base_score, per_signal = _compute_base_signal_score(evidence, thresholds)

    # Stage 2: Data Quality Factor
    quality_factor = _compute_data_quality_factor(evidence)

    # Stage 3: Fleet Calibration
    calibration_factor = 1.0 - fleet_fp_rate

    # Stage 4: Context Penalty
    total_penalty = min(0.60, sum(p for _, p in context_penalties))

    # Final confidence
    final = base_score * quality_factor * calibration_factor * (1.0 - total_penalty)
    final = round(max(0.0, min(1.0, final)), 3)

    # Build explanation
    explanation_parts = []
    if base_score >= 0.8:
        explanation_parts.append("Strong idle signals across multiple metrics")
    elif base_score >= 0.5:
        explanation_parts.append("Moderate idle signals detected")
    else:
        explanation_parts.append("Signals do not clearly indicate waste")

    if quality_factor < 0.85:
        explanation_parts.append(
            f"Limited observation window ({evidence.observation_days}d) reduces certainty"
        )
    if total_penalty > 0:
        penalty_reasons = [r for r, _ in context_penalties]
        explanation_parts.append(f"Context factors reduce confidence: {', '.join(penalty_reasons)}")

    return ConfidenceBreakdown(
        final_confidence=final,
        base_signal_score=round(base_score, 3),
        data_quality_factor=round(quality_factor, 3),
        fleet_calibration_factor=round(calibration_factor, 3),
        context_penalty=round(total_penalty, 3),
        per_signal_scores=per_signal,
        explanation=". ".join(explanation_parts),
    )


def _compute_base_signal_score(
    evidence: EvidenceBundle,
    thresholds: ThresholdSet,
) -> Tuple[float, Dict[str, float]]:
    """
    Weighted sigmoid composite of all available signals.

    Sigmoid function: score = 1 / (1 + e^(-k * (threshold - value) / threshold))
    where k=5 controls steepness.

    When value << threshold: score → 1.0 (strong waste signal)
    When value == threshold: score = 0.5 (ambiguous)
    When value >> threshold: score → 0.0 (definitely not waste)
    """
    per_signal: Dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0
    k = 5.0  # Sigmoid steepness

    for signal_name_enum, weight in SIGNAL_WEIGHTS.items():
        signal_name = signal_name_enum.value
        signal = evidence.signals.get(signal_name)

        if signal is None or not signal.values:
            continue

        threshold = thresholds.get(signal_name)
        value = signal.mean

        # Sigmoid scoring: 1.0 when far below threshold, 0.0 when far above
        if threshold > 0:
            distance = (threshold - value) / threshold
            score = 1.0 / (1.0 + math.exp(-k * distance))
        else:
            score = 0.0

        per_signal[signal_name] = round(score, 3)
        weighted_sum += weight * score
        total_weight += weight

    # Normalize by actual weight used (handles missing signals gracefully)
    base_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    return base_score, per_signal


def _compute_data_quality_factor(evidence: EvidenceBundle) -> float:
    """
    Penalizes incomplete or short observation windows.

    30+ days with >90% completeness → 1.0 (full confidence)
    14-30 days → 0.85 (slight reduction)
    7-14 days → 0.70 (moderate reduction)
    <7 days → 0.50 (significant reduction — too early to be confident)
    """
    days = evidence.observation_days
    completeness = max(0.0, min(1.0, evidence.data_completeness))

    if days >= 30 and completeness >= 0.9:
        return 1.0
    elif days >= 30:
        return 0.90 * completeness
    elif days >= 14:
        return 0.85 * completeness
    elif days >= 7:
        return 0.70 * completeness
    else:
        return 0.50 * completeness


def compute_stopped_resource_confidence(
    evidence: EvidenceBundle,
    stopped_days: int,
    context_penalties: Optional[List[Tuple[str, float]]] = None,
) -> ConfidenceBreakdown:
    """
    Confidence for stopped/terminated/deallocated resources.

    These don't have utilization signals, so confidence comes from:
    - How long stopped (longer = higher confidence it's waste)
    - Whether it has tags suggesting legitimate stoppage (DR, maintenance)
    - Cost (stopped VMs often still incur disk costs)
    """
    if context_penalties is None:
        context_penalties = []

    # Base score from duration stopped
    if stopped_days >= 90:
        base_score = 0.95
    elif stopped_days >= 30:
        base_score = 0.85
    elif stopped_days >= 14:
        base_score = 0.70
    elif stopped_days >= 7:
        base_score = 0.55
    else:
        base_score = 0.30  # Stopped < 7 days — probably intentional

    # No data quality factor needed (we KNOW it's stopped)
    quality_factor = 1.0

    # Fleet calibration (use same FP rate)
    calibration_factor = 1.0

    # Context penalties still apply
    total_penalty = min(0.60, sum(p for _, p in context_penalties))

    final = base_score * quality_factor * calibration_factor * (1.0 - total_penalty)
    final = round(max(0.0, min(1.0, final)), 3)

    explanation_parts = [f"Resource stopped for {stopped_days} days"]
    if total_penalty > 0:
        penalty_reasons = [r for r, _ in context_penalties]
        explanation_parts.append(f"Context: {', '.join(penalty_reasons)}")

    return ConfidenceBreakdown(
        final_confidence=final,
        base_signal_score=round(base_score, 3),
        data_quality_factor=quality_factor,
        fleet_calibration_factor=calibration_factor,
        context_penalty=round(total_penalty, 3),
        per_signal_scores={"stopped_days": float(stopped_days)},
        explanation=". ".join(explanation_parts),
    )
