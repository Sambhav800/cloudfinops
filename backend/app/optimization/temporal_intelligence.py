"""
Temporal Intelligence — Extended pattern detection for false-positive prevention.

Extends the existing workload_patterns.py with longer-horizon patterns that
require 30-90 days of data to detect:

- MONTHLY_BATCH: Spikes at ~30-day intervals (payroll, billing, ETL)
- MAINTENANCE_WINDOW: Brief recurring spikes at consistent times (cron jobs)
- DECOMMISSIONING: Declining trend toward zero (resource being phased out)

These patterns prevent false positives by correctly identifying legitimate usage
that looks like waste in short observation windows.
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExtendedPattern(str, Enum):
    MONTHLY_BATCH = "monthly_batch"
    MAINTENANCE_WINDOW = "maintenance_window"
    DECOMMISSIONING = "decommissioning"
    SEASONAL_QUARTERLY = "seasonal_quarterly"


@dataclass
class PatternMatch:
    """Result of an extended pattern detection."""

    pattern: ExtendedPattern
    confidence: float  # 0.0-1.0
    explanation: str
    next_expected_activity: Optional[int] = None  # days until next expected spike
    evidence: Dict[str, float] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = {}


def detect_extended_patterns(
    daily_values: List[float],
    hourly_values: Optional[List[float]] = None,
    observation_days: int = 0,
) -> Optional[PatternMatch]:
    """
    Run all extended pattern detectors on a resource's time-series data.

    Returns the first matching pattern (priority: monthly_batch > maintenance >
    decommissioning > seasonal), or None if no extended pattern is detected.

    Args:
        daily_values: Daily aggregated metric values (e.g., daily avg CPU)
        hourly_values: Hourly metric values (for maintenance window detection)
        observation_days: Total observation period in days
    """
    if not daily_values:
        return None

    if observation_days == 0:
        observation_days = len(daily_values)

    # Priority 1: Monthly batch (requires 60+ days)
    result = detect_monthly_batch(daily_values, observation_days)
    if result:
        return result

    # Priority 2: Maintenance window (requires hourly data, 14+ days)
    if hourly_values and len(hourly_values) >= 336:  # 14 days * 24 hours
        result = detect_maintenance_window(hourly_values, observation_days)
        if result:
            return result

    # Priority 3: Seasonal quarterly (requires 90+ days)
    result = detect_seasonal_quarterly(daily_values, observation_days)
    if result:
        return result

    # Priority 4: Decommissioning (requires 30+ days)
    result = detect_decommissioning(daily_values, observation_days)
    if result:
        return result

    return None


def detect_monthly_batch(
    daily_values: List[float],
    observation_days: int,
) -> Optional[PatternMatch]:
    """
    Detect monthly batch jobs (payroll runs, billing cycles, ETL pipelines).

    Looks for: 1-3 day spikes recurring at ~28-35 day intervals.
    Requires minimum 60 days of data to see at least 2 cycles.

    This prevents flagging a resource as zombie when it legitimately idles
    for 25-28 days between batch runs.
    """
    if observation_days < 60 or len(daily_values) < 60:
        return None

    # Compute daily median (baseline)
    median_daily = _percentile(daily_values, 50)
    if median_daily < 0.01:
        # If median is basically zero, use mean as spike reference
        mean_daily = mean(daily_values) if daily_values else 0.0
        spike_threshold = max(mean_daily * 3, 2.0)
    else:
        spike_threshold = median_daily * 3.0

    # Find spike days (> 3x median or > 3x mean)
    spike_days = [i for i, v in enumerate(daily_values) if v > spike_threshold]

    if len(spike_days) < 2:
        return None

    # Cluster adjacent spike days (a batch job may run 1-3 days)
    clusters = _cluster_adjacent_days(spike_days, max_gap=2)

    if len(clusters) < 2:
        return None

    # Check if cluster starts are at consistent monthly intervals
    cluster_starts = [c[0] for c in clusters]
    intervals = [
        cluster_starts[i + 1] - cluster_starts[i]
        for i in range(len(cluster_starts) - 1)
    ]

    if not intervals:
        return None

    avg_interval = mean(intervals)
    interval_std = stdev(intervals) if len(intervals) > 1 else 0.0

    # Monthly pattern: average interval 25-35 days with reasonable consistency
    if 25 <= avg_interval <= 35 and interval_std < 7:
        # Confidence increases with more observed cycles
        confidence = min(0.95, 0.60 + len(clusters) * 0.10)

        # Estimate next spike
        last_cluster_start = cluster_starts[-1]
        days_since_last = len(daily_values) - last_cluster_start
        next_expected = max(0, int(avg_interval - days_since_last))

        return PatternMatch(
            pattern=ExtendedPattern.MONTHLY_BATCH,
            confidence=confidence,
            explanation=(
                f"Monthly batch pattern: {len(clusters)} cycles detected, "
                f"recurring every ~{avg_interval:.0f} days "
                f"(±{interval_std:.0f}d). Next expected in ~{next_expected} days."
            ),
            next_expected_activity=next_expected,
            evidence={
                "cycles_detected": float(len(clusters)),
                "avg_interval_days": round(avg_interval, 1),
                "interval_std_days": round(interval_std, 1),
                "spike_threshold": round(spike_threshold, 2),
                "median_daily": round(median_daily, 2),
            },
        )

    return None


def detect_maintenance_window(
    hourly_values: List[float],
    observation_days: int,
) -> Optional[PatternMatch]:
    """
    Detect recurring maintenance/cron patterns.

    Looks for: Brief spikes (1-2 hours) at consistent day-of-week + hour-of-day.
    This catches nightly cron jobs, scheduled backups, health checks, etc.

    A resource that runs a cron job at 3am daily with 0% CPU the rest of the time
    is NOT a zombie — it's a well-configured batch scheduler.
    """
    if len(hourly_values) < 336:  # Need at least 14 days
        return None

    # Build a (day_of_week, hour_of_day) activity map
    hours_per_day = 24
    total_days = len(hourly_values) // hours_per_day

    # Group values by (day_of_week, hour)
    activity_map: Dict[Tuple[int, int], List[float]] = {}
    for i, v in enumerate(hourly_values):
        day = i // hours_per_day
        hour = i % hours_per_day
        dow = day % 7  # 0=Mon ... 6=Sun
        key = (dow, hour)
        if key not in activity_map:
            activity_map[key] = []
        activity_map[key].append(v)

    # Find time slots with consistently elevated activity
    overall_mean = mean(hourly_values) if hourly_values else 0.0
    if overall_mean < 0.1:
        return None

    # A maintenance window slot: consistently > 5x overall mean at that time
    hot_slots: List[Tuple[int, int, float]] = []
    for (dow, hour), values in activity_map.items():
        if len(values) >= 2:  # Need at least 2 observations of this slot
            slot_mean = mean(values)
            if slot_mean > overall_mean * 5:
                consistency = min(values) / max(max(values), 0.01)
                if consistency > 0.3:  # Reasonably consistent across weeks
                    hot_slots.append((dow, hour, slot_mean))

    if not hot_slots:
        return None

    # Check that MOST of the time the resource is idle
    idle_hours_pct = sum(1 for v in hourly_values if v < 2.0) / len(hourly_values) * 100

    if idle_hours_pct < 80:
        return None  # Not a maintenance pattern — too much general activity

    # We have hot slots + mostly idle → maintenance window pattern
    confidence = min(0.90, 0.60 + len(hot_slots) * 0.05 + (idle_hours_pct - 80) * 0.005)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    slot_descriptions = [
        f"{day_names[dow]} {hour:02d}:00"
        for dow, hour, _ in sorted(hot_slots)[:5]
    ]

    return PatternMatch(
        pattern=ExtendedPattern.MAINTENANCE_WINDOW,
        confidence=confidence,
        explanation=(
            f"Maintenance window pattern: resource is idle {idle_hours_pct:.0f}% of the time "
            f"with recurring activity at {', '.join(slot_descriptions)}. "
            f"Likely a scheduled job or cron task."
        ),
        evidence={
            "idle_hours_pct": round(idle_hours_pct, 1),
            "hot_slot_count": float(len(hot_slots)),
            "total_days_observed": float(total_days),
        },
    )


def detect_decommissioning(
    daily_values: List[float],
    observation_days: int,
) -> Optional[PatternMatch]:
    """
    Detect a resource being phased out (declining usage toward zero).

    This is a TRUE waste signal — if usage is trending to zero, the resource
    is likely abandoned. This INCREASES confidence in waste classification
    rather than protecting the resource.

    Looks for: Strong negative slope + recent values near zero + older values
    were meaningfully higher.
    """
    if observation_days < 30 or len(daily_values) < 30:
        return None

    # Compare recent 7d vs older 7d (offset by 23 days)
    recent_7d = daily_values[-7:]
    older_7d = daily_values[-30:-23]

    if not recent_7d or not older_7d:
        return None

    recent_mean = mean(recent_7d)
    older_mean = mean(older_7d)

    # Decommissioning: recent usage near zero AND older usage was meaningful
    if recent_mean >= 3.0:
        return None  # Still has some activity

    if older_mean < 5.0:
        return None  # Was never meaningfully active

    # Check for strong negative slope
    slope = _compute_linear_slope(daily_values)
    if slope >= -0.1:
        return None  # Not declining fast enough

    # Compute decline ratio
    decline_ratio = (older_mean - recent_mean) / max(older_mean, 0.01)

    if decline_ratio < 0.7:
        return None  # Not a dramatic enough decline

    confidence = min(0.90, 0.65 + decline_ratio * 0.2)

    return PatternMatch(
        pattern=ExtendedPattern.DECOMMISSIONING,
        confidence=confidence,
        explanation=(
            f"Decommissioning trend: usage declined {decline_ratio*100:.0f}% over 30 days "
            f"(from {older_mean:.1f}% to {recent_mean:.1f}%). "
            f"Resource appears to be phasing out."
        ),
        evidence={
            "recent_7d_mean": round(recent_mean, 2),
            "older_7d_mean": round(older_mean, 2),
            "decline_ratio": round(decline_ratio, 3),
            "slope_per_day": round(slope, 4),
        },
    )


def detect_seasonal_quarterly(
    daily_values: List[float],
    observation_days: int,
) -> Optional[PatternMatch]:
    """
    Detect quarterly/seasonal patterns (tax season, holiday traffic, fiscal year).

    Requires 90+ days to see one potential cycle. This is a protective pattern —
    a resource idle for 80 days might be waiting for quarter-end processing.
    """
    if observation_days < 90 or len(daily_values) < 90:
        return None

    # Look for activity spikes at ~90 day intervals
    median_daily = _percentile(daily_values, 50)
    if median_daily < 0.01:
        spike_threshold = max(mean(daily_values) * 3, 2.0) if daily_values else 2.0
    else:
        spike_threshold = median_daily * 3.0

    spike_days = [i for i, v in enumerate(daily_values) if v > spike_threshold]

    if len(spike_days) < 2:
        return None

    clusters = _cluster_adjacent_days(spike_days, max_gap=5)  # Wider gap for quarterly

    if len(clusters) < 2:
        return None

    cluster_starts = [c[0] for c in clusters]
    intervals = [
        cluster_starts[i + 1] - cluster_starts[i]
        for i in range(len(cluster_starts) - 1)
    ]

    if not intervals:
        return None

    avg_interval = mean(intervals)

    # Quarterly: 75-100 day intervals
    if 75 <= avg_interval <= 100:
        confidence = min(0.85, 0.55 + len(clusters) * 0.10)

        last_cluster_start = cluster_starts[-1]
        days_since_last = len(daily_values) - last_cluster_start
        next_expected = max(0, int(avg_interval - days_since_last))

        return PatternMatch(
            pattern=ExtendedPattern.SEASONAL_QUARTERLY,
            confidence=confidence,
            explanation=(
                f"Seasonal quarterly pattern: {len(clusters)} cycles detected, "
                f"recurring every ~{avg_interval:.0f} days. "
                f"Next expected activity in ~{next_expected} days."
            ),
            next_expected_activity=next_expected,
            evidence={
                "cycles_detected": float(len(clusters)),
                "avg_interval_days": round(avg_interval, 1),
            },
        )

    return None


# --- Utility functions ---


def _cluster_adjacent_days(spike_days: List[int], max_gap: int = 2) -> List[List[int]]:
    """
    Cluster adjacent spike days together.

    A batch job running over 2-3 days produces adjacent spike days.
    This clusters them into single events for interval calculation.
    """
    if not spike_days:
        return []

    clusters: List[List[int]] = [[spike_days[0]]]

    for day in spike_days[1:]:
        if day - clusters[-1][-1] <= max_gap:
            clusters[-1].append(day)
        else:
            clusters.append([day])

    return clusters


def _percentile(data: List[float], pct: float) -> float:
    """Compute percentile from unsorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (pct / 100.0) * (len(sorted_data) - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return sorted_data[lower]
    frac = idx - lower
    return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac


def _compute_linear_slope(values: List[float]) -> float:
    """Compute linear regression slope (change per data point)."""
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
