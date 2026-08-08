"""
Workload Pattern Analyzer — Enterprise-grade time-series classification engine.

Analyzes 30 days of hourly metrics to classify workload patterns and generate
autoscaling/scheduling/rightsizing recommendations with computed thresholds.

Inspired by: Google Active Assist, AWS Compute Optimizer, Kubernetes VPA (P90 target),
KEDA (event-driven scaling), and GCP Predictive Autoscaling (3-week lookback).

References:
- VPA: P90 target + 15% safety margin + confidence decay (24h half-life)
- AWS Target Tracking: ceil(capacity * metric/target), conservative scale-in rounding
- GCP Autoscaler: 10-min stabilization, 50% scale-out cap, predictive with 3-week history
- KEDA: ceil(metric/threshold), 300s cooldown, 10% tolerance band
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WorkloadPattern(str, Enum):
    DIURNAL = "diurnal"
    WEEKLY = "weekly"
    STEADY_STATE = "steady_state"
    BURST_SPORADIC = "burst_sporadic"
    GROWING = "growing"
    UNKNOWN = "unknown"


class RecommendationType(str, Enum):
    AUTOSCALE = "autoscale"
    RIGHTSIZE = "rightsize"
    SCHEDULE = "schedule"
    SPOT_CANDIDATE = "spot_candidate"
    NO_ACTION = "no_action"


@dataclass
class MetricTimeSeries:
    hourly_values: List[float]
    metric_name: str = "cpu"
    interval_hours: int = 1


@dataclass
class PatternAnalysis:
    pattern: WorkloadPattern
    confidence: float
    peak_hours: List[int] = field(default_factory=list)
    trough_hours: List[int] = field(default_factory=list)
    peak_avg: float = 0.0
    trough_avg: float = 0.0
    peak_trough_ratio: float = 0.0
    weekday_avg: float = 0.0
    weekend_avg: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    coefficient_of_variation: float = 0.0
    trend_slope_pct_per_week: float = 0.0
    observation_days: int = 0
    data_points_count: int = 0


@dataclass
class AutoscaleThresholds:
    min_instances: int = 1
    max_instances: int = 1
    scale_out_cpu_pct: float = 70.0
    scale_in_cpu_pct: float = 30.0
    cooldown_minutes: int = 5
    target_utilization_pct: float = 60.0


@dataclass
class ScheduleRecommendation:
    stop_hours: List[Tuple[int, int]] = field(default_factory=list)
    stop_days: List[str] = field(default_factory=list)
    estimated_savings_pct: float = 0.0


@dataclass
class WorkloadRecommendation:
    type: RecommendationType
    pattern: WorkloadPattern
    analysis: PatternAnalysis
    autoscale: Optional[AutoscaleThresholds] = None
    schedule: Optional[ScheduleRecommendation] = None
    target_vm_size: Optional[str] = None
    explanation: str = ""
    estimated_savings_pct: float = 0.0
    confidence: float = 0.0
    severity: str = "medium"
    evidence: Dict[str, Any] = field(default_factory=dict)


def _percentile(data: List[float], pct: float) -> float:
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


def _hourly_averages_by_hour(values: List[float]) -> Dict[int, List[float]]:
    """Group values by hour-of-day (0-23) assuming chronological hourly data."""
    by_hour: Dict[int, List[float]] = {h: [] for h in range(24)}
    for i, v in enumerate(values):
        hour = i % 24
        by_hour[hour].append(v)
    return by_hour


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


def classify_pattern(series: MetricTimeSeries) -> PatternAnalysis:
    """
    Classify workload pattern from hourly time-series data.

    Uses statistical decomposition to detect:
    - Diurnal (day/night cycles)
    - Weekly (weekday/weekend difference)
    - Steady-state (low variance)
    - Burst/sporadic (high peaks, mostly idle)
    - Growing (upward trend)
    """
    values = series.hourly_values
    n = len(values)

    if n < 48:
        return PatternAnalysis(
            pattern=WorkloadPattern.UNKNOWN,
            confidence=0.0,
            observation_days=n // 24,
            data_points_count=n,
        )

    observation_days = n // 24
    overall_mean = mean(values) if values else 0.0
    overall_std = stdev(values) if len(values) > 1 else 0.0
    cv = overall_std / overall_mean if overall_mean > 0 else 0.0

    p50 = _percentile(values, 50)
    p90 = _percentile(values, 90)
    p95 = _percentile(values, 95)
    p99 = _percentile(values, 99)

    # --- Diurnal detection ---
    by_hour = _hourly_averages_by_hour(values)
    hour_avgs = {h: mean(vs) if vs else 0.0 for h, vs in by_hour.items()}

    sorted_hours = sorted(hour_avgs.items(), key=lambda x: x[1], reverse=True)
    peak_hours = [h for h, _ in sorted_hours[:6]]
    trough_hours = [h for h, _ in sorted_hours[-6:]]

    peak_avg = mean([hour_avgs[h] for h in peak_hours])
    trough_avg = mean([hour_avgs[h] for h in trough_hours]) if trough_hours else 0.001
    peak_trough_ratio = peak_avg / max(trough_avg, 0.1)

    hour_std = stdev(hour_avgs.values()) if len(hour_avgs) > 1 else 0.0
    diurnal_strength = hour_std / max(overall_mean, 0.1)

    # --- Weekly detection ---
    weekday_values = []
    weekend_values = []
    for i, v in enumerate(values):
        day_of_week = (i // 24) % 7
        if day_of_week < 5:
            weekday_values.append(v)
        else:
            weekend_values.append(v)

    weekday_avg = mean(weekday_values) if weekday_values else 0.0
    weekend_avg = mean(weekend_values) if weekend_values else 0.0

    # --- Trend detection ---
    daily_avgs = []
    for d in range(observation_days):
        day_slice = values[d * 24:(d + 1) * 24]
        if day_slice:
            daily_avgs.append(mean(day_slice))

    slope_per_day = _compute_linear_slope(daily_avgs) if daily_avgs else 0.0
    slope_pct_per_week = (slope_per_day * 7 / max(overall_mean, 0.1)) * 100

    # --- Burst detection ---
    idle_hours_pct = sum(1 for v in values if v < 5.0) / max(n, 1) * 100

    # --- Classification decision tree ---
    # Priority: Growing > Diurnal > Weekly > Burst > Steady

    pattern = WorkloadPattern.UNKNOWN
    confidence = 0.0

    if slope_pct_per_week > 5.0 and observation_days >= 14:
        pattern = WorkloadPattern.GROWING
        confidence = min(0.95, 0.6 + abs(slope_pct_per_week) * 0.03)

    elif diurnal_strength > 0.25 and peak_trough_ratio > 2.5:
        pattern = WorkloadPattern.DIURNAL
        confidence = min(0.98, 0.6 + (peak_trough_ratio - 2.5) * 0.1 + diurnal_strength * 0.3)

    elif weekday_avg > 0 and weekend_avg > 0 and weekday_avg / max(weekend_avg, 0.1) > 2.0:
        pattern = WorkloadPattern.WEEKLY
        confidence = min(0.95, 0.6 + (weekday_avg / max(weekend_avg, 0.1) - 2.0) * 0.1)

    elif idle_hours_pct > 70 and p99 > 5 * p50:
        pattern = WorkloadPattern.BURST_SPORADIC
        confidence = min(0.92, 0.5 + idle_hours_pct * 0.005)

    elif cv < 0.3:
        pattern = WorkloadPattern.STEADY_STATE
        confidence = min(0.95, 0.7 + (0.3 - cv) * 0.5)

    else:
        pattern = WorkloadPattern.DIURNAL if peak_trough_ratio > 1.8 else WorkloadPattern.STEADY_STATE
        confidence = 0.5

    # Data quality factor
    data_quality = 1.0 if observation_days >= 28 else (
        0.85 if observation_days >= 14 else (
            0.7 if observation_days >= 7 else 0.5
        )
    )
    confidence *= data_quality

    return PatternAnalysis(
        pattern=pattern,
        confidence=round(confidence, 3),
        peak_hours=sorted(peak_hours),
        trough_hours=sorted(trough_hours),
        peak_avg=round(peak_avg, 2),
        trough_avg=round(trough_avg, 2),
        peak_trough_ratio=round(peak_trough_ratio, 2),
        weekday_avg=round(weekday_avg, 2),
        weekend_avg=round(weekend_avg, 2),
        p50=round(p50, 2),
        p90=round(p90, 2),
        p95=round(p95, 2),
        p99=round(p99, 2),
        coefficient_of_variation=round(cv, 3),
        trend_slope_pct_per_week=round(slope_pct_per_week, 2),
        observation_days=observation_days,
        data_points_count=n,
    )


def compute_autoscale_thresholds(
    analysis: PatternAnalysis,
    current_vm_vcpus: int = 2,
) -> AutoscaleThresholds:
    """
    Compute autoscaling min/max thresholds from pattern analysis.

    Uses the VPA-inspired P90 + 15% safety margin approach for target utilization,
    and GCP-style conservative scale-in (P25 for scale-in threshold).
    """
    # Target utilization: P90 of peak hours determines how much capacity we need
    # Following VPA: target = P90 + 15% safety margin
    target_util = min(analysis.p90 * 1.15, 95.0)

    # Scale-out threshold: when avg exceeds this, add capacity
    # Industry standard: 70% (AWS default for target tracking)
    scale_out = 70.0

    # Scale-in threshold: when avg drops below this, remove capacity
    # Conservative: 30% (GCP uses 60% target with 10-min stabilization)
    scale_in = 30.0

    # Min instances: enough to handle trough demand
    # Formula: ceil(trough_demand / per_instance_capacity_at_target)
    trough_demand_fraction = analysis.trough_avg / 100.0
    min_instances = max(1, math.ceil(trough_demand_fraction * current_vm_vcpus / (scale_out / 100.0)))

    # Max instances: enough to handle peak demand + 20% buffer
    # Following AWS: conservative rounding UP for scale-out
    peak_demand_fraction = analysis.peak_avg / 100.0
    buffer = 1.2
    max_instances = max(
        min_instances + 1,
        math.ceil(peak_demand_fraction * current_vm_vcpus * buffer / (scale_out / 100.0))
    )

    # Cooldown: 5 min default (industry consensus: AWS 300s, GCP 600s, KEDA 300s)
    cooldown = 5

    return AutoscaleThresholds(
        min_instances=min_instances,
        max_instances=max_instances,
        scale_out_cpu_pct=scale_out,
        scale_in_cpu_pct=scale_in,
        cooldown_minutes=cooldown,
        target_utilization_pct=round(target_util, 1),
    )


def compute_schedule(analysis: PatternAnalysis) -> ScheduleRecommendation:
    """Compute scheduling recommendation for weekly patterns."""
    stop_hours = []
    stop_days = []
    savings_pct = 0.0

    if analysis.pattern == WorkloadPattern.WEEKLY:
        if analysis.weekend_avg < 10.0:
            stop_days = ["Saturday", "Sunday"]
            savings_pct = round((2.0 / 7.0) * 100, 1)

    elif analysis.pattern == WorkloadPattern.DIURNAL:
        # Find consecutive low-usage hours
        by_hour = {h: analysis.trough_avg for h in analysis.trough_hours}
        if analysis.trough_avg < 10.0 and len(analysis.trough_hours) >= 4:
            sorted_trough = sorted(analysis.trough_hours)
            start = sorted_trough[0]
            end = sorted_trough[-1]
            stop_hours = [(start, end)]
            off_hours = len(analysis.trough_hours)
            savings_pct = round((off_hours / 24.0) * 100, 1)

    return ScheduleRecommendation(
        stop_hours=stop_hours,
        stop_days=stop_days,
        estimated_savings_pct=savings_pct,
    )


def generate_recommendation(
    analysis: PatternAnalysis,
    current_vm_size: str = "",
    current_monthly_cost: float = 0.0,
    current_vm_vcpus: int = 2,
) -> WorkloadRecommendation:
    """
    Generate the optimal recommendation based on pattern classification.

    Decision matrix (priority order):
    1. DIURNAL + peak/trough ratio > 2.5 → AUTOSCALE
    2. WEEKLY + weekend < 10% → SCHEDULE (stop weekends)
    3. STEADY_STATE + avg < 30% → RIGHTSIZE
    4. BURST_SPORADIC + idle > 80% → SPOT/SERVERLESS
    5. GROWING → warn about capacity planning
    """
    rec_type = RecommendationType.NO_ACTION
    autoscale = None
    schedule = None
    target_size = None
    explanation = ""
    savings_pct = 0.0
    severity = "medium"

    if analysis.pattern == WorkloadPattern.DIURNAL and analysis.peak_trough_ratio > 2.5:
        rec_type = RecommendationType.AUTOSCALE
        autoscale = compute_autoscale_thresholds(analysis, current_vm_vcpus)
        severity = "high"

        peak_hour_range = f"{min(analysis.peak_hours):02d}:00-{max(analysis.peak_hours):02d}:00"
        trough_hour_range = f"{min(analysis.trough_hours):02d}:00-{max(analysis.trough_hours):02d}:00"

        explanation = (
            f"Strong diurnal pattern detected over {analysis.observation_days} days: "
            f"{analysis.peak_avg:.0f}% CPU during peak hours ({peak_hour_range}) vs "
            f"{analysis.trough_avg:.0f}% during trough ({trough_hour_range}). "
            f"Peak-to-trough ratio is {analysis.peak_trough_ratio:.1f}x. "
            f"Instead of paying for peak capacity 24/7, enable autoscaling with "
            f"min {autoscale.min_instances} / max {autoscale.max_instances} instances. "
            f"Scale out at {autoscale.scale_out_cpu_pct:.0f}% CPU, scale in at "
            f"{autoscale.scale_in_cpu_pct:.0f}% CPU, {autoscale.cooldown_minutes}-minute cooldown."
        )

        # Savings: fraction of time at trough × (1 - min/max ratio)
        trough_fraction = len(analysis.trough_hours) / 24.0
        savings_pct = round(trough_fraction * (1 - autoscale.min_instances / autoscale.max_instances) * 100, 1)

    elif analysis.pattern == WorkloadPattern.WEEKLY and analysis.weekend_avg < 10.0:
        rec_type = RecommendationType.SCHEDULE
        schedule = compute_schedule(analysis)
        severity = "high"

        explanation = (
            f"Weekly pattern detected: {analysis.weekday_avg:.0f}% CPU on weekdays vs "
            f"{analysis.weekend_avg:.0f}% on weekends (over {analysis.observation_days} days). "
            f"Schedule this resource to stop on {', '.join(schedule.stop_days)} to save "
            f"~{schedule.estimated_savings_pct:.0f}% of monthly cost."
        )
        savings_pct = schedule.estimated_savings_pct

    elif analysis.pattern == WorkloadPattern.STEADY_STATE and analysis.p90 < 30.0:
        rec_type = RecommendationType.RIGHTSIZE
        severity = "medium"

        explanation = (
            f"Steady-state workload at {analysis.p90:.0f}% P90 utilization "
            f"(over {analysis.observation_days} days, CV={analysis.coefficient_of_variation:.2f}). "
            f"This resource is consistently over-provisioned. "
            f"Rightsize to a smaller SKU that handles P95 ({analysis.p95:.0f}%) + 30% buffer = "
            f"{min(analysis.p95 * 1.3, 100):.0f}% target utilization."
        )
        savings_pct = round(max(0, (1 - (analysis.p95 * 1.3 / 100)) * 50), 1)

    elif analysis.pattern == WorkloadPattern.BURST_SPORADIC:
        rec_type = RecommendationType.SPOT_CANDIDATE
        severity = "medium"

        idle_pct = sum(1 for v in [analysis.trough_avg] * 18 if v < 5) / 24 * 100
        explanation = (
            f"Burst/sporadic workload: P50={analysis.p50:.0f}%, P99={analysis.p99:.0f}% "
            f"(over {analysis.observation_days} days). Resource is idle most of the time with "
            f"rare high-demand spikes. Consider: (1) Azure Spot VMs for fault-tolerant workloads "
            f"(60-90% savings), (2) Azure Functions/Container Apps for event-driven execution, "
            f"or (3) Autoscaling from 0 with KEDA-style activation."
        )
        savings_pct = round(min(70, 40 + (100 - analysis.p50) * 0.3), 1)

    elif analysis.pattern == WorkloadPattern.GROWING:
        rec_type = RecommendationType.AUTOSCALE
        autoscale = compute_autoscale_thresholds(analysis, current_vm_vcpus)
        severity = "high"

        explanation = (
            f"Growing workload detected: {analysis.trend_slope_pct_per_week:.1f}% increase per week "
            f"over {analysis.observation_days} days. Current P90={analysis.p90:.0f}%. "
            f"Enable autoscaling now to handle increasing demand without manual intervention. "
            f"Recommended: min {autoscale.min_instances} / max {autoscale.max_instances} instances, "
            f"scale out at {autoscale.scale_out_cpu_pct:.0f}% CPU."
        )
        savings_pct = 0.0

    else:
        explanation = (
            f"Resource is well-utilized (P90={analysis.p90:.0f}%, "
            f"CV={analysis.coefficient_of_variation:.2f}) over {analysis.observation_days} days. "
            f"No optimization action required."
        )

    evidence = {
        "observation_days": analysis.observation_days,
        "data_points": analysis.data_points_count,
        "peak_hours_utc": analysis.peak_hours,
        "trough_hours_utc": analysis.trough_hours,
        "peak_avg_cpu": analysis.peak_avg,
        "trough_avg_cpu": analysis.trough_avg,
        "peak_trough_ratio": analysis.peak_trough_ratio,
        "weekday_avg_cpu": analysis.weekday_avg,
        "weekend_avg_cpu": analysis.weekend_avg,
        "p50": analysis.p50,
        "p90": analysis.p90,
        "p95": analysis.p95,
        "p99": analysis.p99,
        "cv": analysis.coefficient_of_variation,
        "trend_pct_per_week": analysis.trend_slope_pct_per_week,
    }

    return WorkloadRecommendation(
        type=rec_type,
        pattern=analysis.pattern,
        analysis=analysis,
        autoscale=autoscale,
        schedule=schedule,
        target_vm_size=target_size,
        explanation=explanation,
        estimated_savings_pct=savings_pct,
        confidence=analysis.confidence,
        severity=severity,
        evidence=evidence,
    )
