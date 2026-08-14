"""
Graduated Severity Spectrum — Replaces binary zombie/active classification.

Resources are classified on a spectrum from CRITICAL_WASTE to WELL_UTILIZED,
with each classification requiring a specific confidence threshold before being
shown to users.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ResourceClassification(str, Enum):
    """Graduated classification spectrum."""

    # Waste spectrum (actionable, ordered by severity)
    CRITICAL_WASTE = "critical_waste"
    CONFIRMED_WASTE = "confirmed_waste"
    LIKELY_WASTE = "likely_waste"
    POSSIBLE_WASTE = "possible_waste"

    # Optimization opportunities (not waste, but improvable)
    OVERSIZED = "oversized"
    SCHEDULE_CANDIDATE = "schedule_candidate"
    SPOT_CANDIDATE = "spot_candidate"
    COMMITMENT_CANDIDATE = "commitment_candidate"

    # Healthy spectrum
    WELL_UTILIZED = "well_utilized"
    PROTECTED = "protected"
    INSUFFICIENT_DATA = "insufficient_data"


class Severity(str, Enum):
    """Severity level combining classification certainty with financial impact."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class RecommendedAction(str, Enum):
    """What the user should do."""

    TERMINATE = "terminate"
    STOP = "stop"
    RIGHTSIZE = "rightsize"
    SCHEDULE = "schedule"
    USE_SPOT = "use_spot"
    PURCHASE_COMMITMENT = "purchase_commitment"
    INVESTIGATE = "investigate"
    MONITOR = "monitor"
    NO_ACTION = "no_action"


@dataclass
class CorroboratingSignal:
    """A signal that supports the classification verdict."""

    signal_name: str  # e.g., "cpu_avg", "network_in_mb"
    observed_value: float
    threshold: float
    description: str  # Human-readable explanation


@dataclass
class VetoSignal:
    """A signal that blocks waste classification."""

    reason: str  # e.g., "DR failover for active resource"
    signal_type: str  # e.g., "relationship", "tag", "age", "pattern"
    details: Optional[str] = None


@dataclass
class Recommendation:
    """Actionable recommendation attached to a verdict."""

    action: RecommendedAction
    description: str
    estimated_monthly_savings: float = 0.0
    effort: str = "low"  # low | medium | high
    risk: str = "low"  # low | medium | high
    script_hint: Optional[str] = None  # CLI command template


@dataclass
class ResourceVerdict:
    """
    Complete classification output for a single resource.

    Contains the verdict, confidence, evidence chain, and recommended action.
    This is what the UI renders and what feeds back into the system.
    """

    resource_id: str
    classification: ResourceClassification
    confidence: float  # 0.0-1.0
    severity: Severity

    # Evidence chain (for explainability)
    corroborating_signals: List[CorroboratingSignal] = field(default_factory=list)
    vetoing_signals: List[VetoSignal] = field(default_factory=list)
    pattern_detected: Optional[str] = None  # workload pattern name if any
    context_factors: List[str] = field(default_factory=list)

    # Actionable output
    recommendation: Optional[Recommendation] = None
    estimated_monthly_waste: float = 0.0
    waste_reason: str = ""  # Human-readable summary

    # Metadata
    pipeline_version: str = "1.0.0"
    determined_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    requires_human_review: bool = False
    ai_verification_needed: bool = False

    # Mapping to existing schema fields
    @property
    def legacy_status(self) -> str:
        """Map to existing status field values for backward compatibility."""
        if self.classification in (
            ResourceClassification.CRITICAL_WASTE,
            ResourceClassification.CONFIRMED_WASTE,
            ResourceClassification.LIKELY_WASTE,
        ):
            return "zombie"
        elif self.classification == ResourceClassification.POSSIBLE_WASTE:
            return "waste"
        elif self.classification == ResourceClassification.OVERSIZED:
            return "zombie"  # Current schema uses zombie for oversized
        elif self.classification == ResourceClassification.PROTECTED:
            return "Active"
        elif self.classification == ResourceClassification.INSUFFICIENT_DATA:
            return "Active"
        else:
            return "Active"

    @property
    def legacy_waste_type(self) -> Optional[str]:
        """Map to existing waste_type field values."""
        if self.classification == ResourceClassification.OVERSIZED:
            return "oversized"
        elif self.classification in (
            ResourceClassification.CRITICAL_WASTE,
            ResourceClassification.CONFIRMED_WASTE,
            ResourceClassification.LIKELY_WASTE,
        ):
            return "zombie"
        elif self.classification == ResourceClassification.POSSIBLE_WASTE:
            return "idle"
        return None


def compute_severity(
    classification: ResourceClassification,
    monthly_cost: float,
    confidence: float,
) -> Severity:
    """
    Compute severity from classification certainty and financial impact.

    A $500/mo zombie at 95% confidence = CRITICAL
    A $5/mo zombie at 95% confidence = LOW
    A $500/mo zombie at 60% confidence = MEDIUM (uncertainty reduces severity)
    """
    if classification in (
        ResourceClassification.WELL_UTILIZED,
        ResourceClassification.PROTECTED,
        ResourceClassification.INSUFFICIENT_DATA,
    ):
        return Severity.NONE

    if classification in (
        ResourceClassification.OVERSIZED,
        ResourceClassification.SCHEDULE_CANDIDATE,
        ResourceClassification.SPOT_CANDIDATE,
        ResourceClassification.COMMITMENT_CANDIDATE,
    ):
        return Severity.INFO

    # Waste classifications: severity = f(cost × confidence)
    waste_impact = monthly_cost * confidence

    if classification in (
        ResourceClassification.CRITICAL_WASTE,
        ResourceClassification.CONFIRMED_WASTE,
    ):
        if waste_impact >= 100:
            return Severity.CRITICAL
        elif waste_impact >= 50:
            return Severity.HIGH
        elif waste_impact >= 10:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    elif classification == ResourceClassification.LIKELY_WASTE:
        if waste_impact >= 100:
            return Severity.HIGH
        elif waste_impact >= 25:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    elif classification == ResourceClassification.POSSIBLE_WASTE:
        if waste_impact >= 100:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    return Severity.NONE


def classification_from_confidence(confidence: float, monthly_cost: float) -> ResourceClassification:
    """
    Map confidence score to classification tier.

    This is used AFTER the full pipeline runs — the confidence determines
    which bucket the resource falls into.
    """
    if confidence >= 0.90 and monthly_cost >= 50:
        return ResourceClassification.CRITICAL_WASTE
    elif confidence >= 0.80:
        return ResourceClassification.CONFIRMED_WASTE
    elif confidence >= 0.70:
        return ResourceClassification.LIKELY_WASTE
    elif confidence >= 0.60:
        return ResourceClassification.POSSIBLE_WASTE
    else:
        # Below 0.60 confidence is not shown to users as waste
        return ResourceClassification.WELL_UTILIZED
