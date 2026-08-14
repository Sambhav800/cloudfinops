"""
Predictive Waste Detection — Catch resources trending toward waste BEFORE they cross thresholds.

While reactive detection flags resources that ARE waste, predictive detection
flags resources that WILL BE waste within 7-14 days based on declining trends.

This is what separates world-class from average:
- Average tool: "This resource has been idle for 7 days"
- Best tool: "This resource's usage has declined 60% over 14 days and will hit zombie threshold in ~5 days"

Signals:
1. Declining CPU trend (linear regression over 14+ days)
2. Declining network trend
3. Declining connection count (databases)
4. Consecutive scan deterioration (getting worse each scan)
5. Cost growth without usage growth (paying more, doing less)

Output: Early warning alerts with "days until zombie" prediction.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PredictiveAlert:
    """An early warning that a resource is trending toward waste."""

    resource_id: str
    alert_type: str  # "declining_usage", "usage_cost_divergence", "approaching_threshold"
    severity: str  # "watch", "warning", "imminent"
    days_until_threshold: Optional[int]
    current_utilization: float
    trend_slope_per_day: float
    prediction_confidence: float  # 0.0-1.0
    description: str
    recommended_action: str


def detect_pre_zombie_signals(
    resource_id: str,
    current_signals: Dict[str, float],
    historical_signals: Optional[List[Dict[str, float]]] = None,
    thresholds: Optional[Dict[str, float]] = None,
    current_cost: float = 0.0,
    historical_costs: Optional[List[float]] = None,
) -> Optional[PredictiveAlert]:
    """
    Detect if a resource is trending toward waste.

    Uses current + historical signal data to project when utilization
    will cross the zombie threshold.

    Args:
        resource_id: Resource identifier
        current_signals: Current metrics {signal_name: value}
        historical_signals: List of past signal snapshots (oldest first)
        thresholds: Zombie thresholds per signal
        current_cost: Current monthly cost
        historical_costs: Past monthly costs (oldest first)
    """
    if thresholds is None:
        thresholds = {
            "cpu_avg": 2.0,
            "network_in_mb": 5.0,
            "disk_read_ops": 1.0,
        }

    # Need at least 3 historical data points for trend analysis
    if not historical_signals or len(historical_signals) < 3:
        return None

    # --- Check each signal for declining trend ---
    alerts: List[PredictiveAlert] = []

    for signal_name, threshold in thresholds.items():
        current_value = current_signals.get(signal_name)
        if current_value is None:
            continue

        # Already below threshold — not predictive, it's current waste
        if current_value <= threshold:
            continue

        # Extract historical values for this signal
        history = [
            h.get(signal_name)
            for h in historical_signals
            if h.get(signal_name) is not None
        ]

        if len(history) < 3:
            continue

        # Append current value as latest data point
        all_values = history + [current_value]

        # Compute linear regression slope
        slope = _linear_slope(all_values)

        # Only care about declining trends
        if slope >= 0:
            continue

        # Project when it will cross the threshold
        distance_to_threshold = current_value - threshold
        if slope < 0:
            days_to_threshold = abs(distance_to_threshold / slope)
        else:
            continue

        # Only alert if crossing is predicted within 14 days
        if days_to_threshold > 14:
            continue

        # Determine severity based on time to threshold
        if days_to_threshold <= 3:
            severity = "imminent"
        elif days_to_threshold <= 7:
            severity = "warning"
        else:
            severity = "watch"

        # Confidence based on data quality and trend strength
        decline_pct = abs(slope * len(all_values)) / max(mean(all_values), 0.01) * 100
        confidence = min(0.90, 0.50 + decline_pct * 0.01 + len(all_values) * 0.02)

        alerts.append(PredictiveAlert(
            resource_id=resource_id,
            alert_type="approaching_threshold",
            severity=severity,
            days_until_threshold=max(1, int(days_to_threshold)),
            current_utilization=current_value,
            trend_slope_per_day=round(slope, 3),
            prediction_confidence=round(confidence, 2),
            description=(
                f"{signal_name} declining at {abs(slope):.2f}/day "
                f"(current: {current_value:.1f}, threshold: {threshold}). "
                f"Predicted to reach zombie threshold in ~{int(days_to_threshold)} days."
            ),
            recommended_action=(
                "Investigate usage decline. If intentional (migration/replacement), "
                "plan decommission. If unintentional, check service health."
            ),
        ))

    # --- Check usage-cost divergence ---
    if historical_costs and len(historical_costs) >= 3 and current_cost > 0:
        divergence = _detect_usage_cost_divergence(
            resource_id, current_signals, historical_signals, current_cost, historical_costs
        )
        if divergence:
            alerts.append(divergence)

    # Return highest severity alert
    if not alerts:
        return None

    severity_rank = {"imminent": 3, "warning": 2, "watch": 1}
    alerts.sort(key=lambda a: severity_rank.get(a.severity, 0), reverse=True)
    return alerts[0]


def _detect_usage_cost_divergence(
    resource_id: str,
    current_signals: Dict[str, float],
    historical_signals: List[Dict[str, float]],
    current_cost: float,
    historical_costs: List[float],
) -> Optional[PredictiveAlert]:
    """
    Detect when cost is growing but usage is declining.

    This is the most expensive type of waste — you're paying MORE for LESS.
    Common with: auto-scaling gone wrong, storage growth without access,
    commitment cost increases while usage declines.
    """
    # Need enough history
    if len(historical_costs) < 5 or len(historical_signals) < 5:
        return None

    # Compute cost trend
    cost_values = historical_costs + [current_cost]
    cost_slope = _linear_slope(cost_values)

    # Compute usage trend (use CPU as primary signal)
    cpu_values = [
        h.get("cpu_avg", 0)
        for h in historical_signals
        if h.get("cpu_avg") is not None
    ]
    current_cpu = current_signals.get("cpu_avg")
    if current_cpu is not None:
        cpu_values.append(current_cpu)

    if len(cpu_values) < 5:
        return None

    usage_slope = _linear_slope(cpu_values)

    # Divergence: cost going up + usage going down
    if cost_slope > 0 and usage_slope < 0:
        cost_growth_pct = (cost_slope * len(cost_values)) / max(mean(cost_values), 1) * 100
        usage_decline_pct = abs(usage_slope * len(cpu_values)) / max(mean(cpu_values), 0.01) * 100

        if cost_growth_pct > 10 and usage_decline_pct > 20:
            confidence = min(0.85, 0.50 + (cost_growth_pct + usage_decline_pct) * 0.003)

            return PredictiveAlert(
                resource_id=resource_id,
                alert_type="usage_cost_divergence",
                severity="warning",
                days_until_threshold=None,
                current_utilization=current_cpu or 0,
                trend_slope_per_day=usage_slope,
                prediction_confidence=round(confidence, 2),
                description=(
                    f"Cost growing +{cost_growth_pct:.0f}% while usage declining "
                    f"-{usage_decline_pct:.0f}%. Paying more for less utilization."
                ),
                recommended_action=(
                    "Review why cost is growing despite declining usage. "
                    "Common causes: storage accumulation, commitment expiry/renewal at higher rates, "
                    "or data transfer growth. Rightsize or migrate."
                ),
            )

    return None


def _linear_slope(values: List[float]) -> float:
    """Compute linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator
