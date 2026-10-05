"""
Tests for backend/app/core/workload_patterns.py — workload classification engine.

Covers:
- Pattern classification (diurnal, weekly, steady_state, burst, growing, unknown)
- Edge cases (too few data points, flat data, all zeros)
- Percentile helper
- Autoscale threshold computation
- Schedule recommendation computation
- generate_recommendation decision matrix
"""

import math
import random

import pytest

from app.core.workload_patterns import (
    AutoscaleThresholds,
    MetricTimeSeries,
    PatternAnalysis,
    RecommendationType,
    ScheduleRecommendation,
    WorkloadPattern,
    WorkloadRecommendation,
    _compute_linear_slope,
    _hourly_averages_by_hour,
    _percentile,
    classify_pattern,
    compute_autoscale_thresholds,
    compute_schedule,
    generate_recommendation,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic time-series
# ---------------------------------------------------------------------------

def _make_series(hourly_values: list[float], metric_name: str = "cpu") -> MetricTimeSeries:
    return MetricTimeSeries(hourly_values=hourly_values, metric_name=metric_name)


def _diurnal_data(days: int = 30, peak_pct: float = 80.0, trough_pct: float = 10.0) -> list[float]:
    """Simulate a diurnal pattern: high during business hours (9-17), low overnight."""
    values = []
    for d in range(days):
        for h in range(24):
            if 9 <= h <= 17:
                values.append(peak_pct + random.uniform(-5, 5))
            else:
                values.append(trough_pct + random.uniform(-3, 3))
    return values


def _weekly_data(days: int = 28, weekday_pct: float = 60.0, weekend_pct: float = 5.0) -> list[float]:
    """Weekday busy, weekend near-idle."""
    values = []
    for d in range(days):
        day_of_week = d % 7
        for h in range(24):
            if day_of_week < 5:
                values.append(weekday_pct + random.uniform(-5, 5))
            else:
                values.append(weekend_pct + random.uniform(-2, 2))
    return values


def _steady_state_data(days: int = 30, avg_pct: float = 20.0, jitter: float = 2.0) -> list[float]:
    """Very low variance workload."""
    return [avg_pct + random.uniform(-jitter, jitter) for _ in range(days * 24)]


def _burst_data(days: int = 30, idle_pct: float = 1.0, burst_pct: float = 95.0,
                burst_probability: float = 0.05) -> list[float]:
    """Mostly idle, occasional extreme spikes."""
    values = []
    for _ in range(days * 24):
        if random.random() < burst_probability:
            values.append(burst_pct + random.uniform(-5, 5))
        else:
            values.append(idle_pct + random.uniform(0, 2))
    return values


def _growing_data(days: int = 30, start_pct: float = 20.0, growth_per_day: float = 2.0) -> list[float]:
    """Linearly increasing workload."""
    values = []
    for d in range(days):
        base = start_pct + d * growth_per_day
        for h in range(24):
            values.append(base + random.uniform(-3, 3))
    return values


# ---------------------------------------------------------------------------
# _percentile helper
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_empty_list(self):
        assert _percentile([], 50) == 0.0

    def test_single_element(self):
        assert _percentile([42.0], 50) == 42.0
        assert _percentile([42.0], 0) == 42.0
        assert _percentile([42.0], 100) == 42.0

    def test_p50_of_even_count(self):
        result = _percentile([10, 20, 30, 40], 50)
        assert result == pytest.approx(25.0)

    def test_p0_and_p100(self):
        data = [5.0, 10.0, 15.0, 20.0, 25.0]
        assert _percentile(data, 0) == 5.0
        assert _percentile(data, 100) == 25.0

    def test_p90(self):
        data = list(range(1, 101))  # 1..100
        result = _percentile(data, 90)
        assert result == pytest.approx(90.1, abs=0.5)


# ---------------------------------------------------------------------------
# _hourly_averages_by_hour
# ---------------------------------------------------------------------------

class TestHourlyAveragesByHour:
    def test_groups_by_hour_of_day(self):
        values = list(range(48))  # 2 days
        by_hour = _hourly_averages_by_hour(values)
        assert len(by_hour) == 24
        # Hour 0 should have values [0, 24]
        assert by_hour[0] == [0, 24]
        assert by_hour[23] == [23, 47]


# ---------------------------------------------------------------------------
# _compute_linear_slope
# ---------------------------------------------------------------------------

class TestLinearSlope:
    def test_flat_data(self):
        assert _compute_linear_slope([5.0, 5.0, 5.0]) == pytest.approx(0.0)

    def test_positive_slope(self):
        assert _compute_linear_slope([0.0, 1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_negative_slope(self):
        assert _compute_linear_slope([3.0, 2.0, 1.0, 0.0]) == pytest.approx(-1.0)

    def test_single_point(self):
        assert _compute_linear_slope([7.0]) == 0.0

    def test_empty(self):
        assert _compute_linear_slope([]) == 0.0


# ---------------------------------------------------------------------------
# classify_pattern
# ---------------------------------------------------------------------------

class TestClassifyPattern:
    """Test the main classification engine."""

    def test_too_few_points_returns_unknown(self):
        series = _make_series([50.0] * 47)  # < 48 points
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.UNKNOWN
        assert analysis.confidence == 0.0
        assert analysis.data_points_count == 47

    def test_diurnal_pattern(self):
        random.seed(42)
        series = _make_series(_diurnal_data(days=30, peak_pct=80, trough_pct=10))
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.DIURNAL
        assert analysis.confidence > 0.5
        assert analysis.peak_trough_ratio > 2.0
        assert analysis.observation_days == 30
        assert analysis.data_points_count == 720

    def test_weekly_pattern(self):
        random.seed(42)
        series = _make_series(_weekly_data(days=28, weekday_pct=60, weekend_pct=5))
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.WEEKLY
        assert analysis.confidence > 0.5
        assert analysis.weekday_avg > analysis.weekend_avg * 2

    def test_steady_state_pattern(self):
        random.seed(42)
        series = _make_series(_steady_state_data(days=30, avg_pct=50, jitter=2))
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.STEADY_STATE
        assert analysis.coefficient_of_variation < 0.3
        assert analysis.confidence > 0.5

    def test_burst_sporadic_pattern(self):
        # Build a deterministic burst pattern: mostly idle with rare spikes.
        # Step must be coprime with 24 so spikes distribute across ALL hours
        # (avoids false diurnal detection). 29 is coprime with 24.
        values = [2.0] * (30 * 24)  # 720 hours of near-idle
        for i in range(0, len(values), 29):
            values[i] = 95.0
        series = _make_series(values)
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.BURST_SPORADIC
        assert analysis.confidence > 0.4
        assert analysis.p99 > analysis.p50 * 5

    def test_growing_pattern(self):
        random.seed(42)
        series = _make_series(_growing_data(days=30, start_pct=20, growth_per_day=2.5))
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.GROWING
        assert analysis.trend_slope_pct_per_week > 5.0
        assert analysis.confidence > 0.4

    def test_growing_needs_14_days_minimum(self):
        """Growth detection requires >= 14 observation days."""
        random.seed(42)
        series = _make_series(_growing_data(days=7, start_pct=20, growth_per_day=5))
        analysis = classify_pattern(series)
        # With only 7 days, should NOT classify as growing even if slope is high
        assert analysis.pattern != WorkloadPattern.GROWING

    def test_all_zeros_does_not_crash(self):
        series = _make_series([0.0] * 720)
        analysis = classify_pattern(series)
        assert analysis.pattern in (WorkloadPattern.STEADY_STATE, WorkloadPattern.UNKNOWN, WorkloadPattern.BURST_SPORADIC, WorkloadPattern.DIURNAL)
        assert analysis.p50 == 0.0
        assert analysis.p90 == 0.0

    def test_flat_high_is_steady_state(self):
        """Constant 70% CPU with no variation should be steady-state."""
        series = _make_series([70.0] * (30 * 24))
        analysis = classify_pattern(series)
        assert analysis.pattern == WorkloadPattern.STEADY_STATE
        assert analysis.coefficient_of_variation == 0.0

    def test_data_quality_factor_applied(self):
        """Short observation windows should reduce confidence."""
        random.seed(42)
        short = _make_series(_steady_state_data(days=3, avg_pct=50, jitter=2))
        long = _make_series(_steady_state_data(days=30, avg_pct=50, jitter=2))
        analysis_short = classify_pattern(short)
        analysis_long = classify_pattern(long)
        # The 30-day analysis should have higher confidence than 3-day
        assert analysis_long.confidence >= analysis_short.confidence

    def test_analysis_fields_populated(self):
        """Ensure all PatternAnalysis fields have reasonable values."""
        random.seed(42)
        series = _make_series(_diurnal_data(days=14))
        a = classify_pattern(series)
        assert len(a.peak_hours) == 6
        assert len(a.trough_hours) == 6
        assert a.peak_avg > 0
        assert a.trough_avg >= 0
        assert a.observation_days == 14
        assert a.data_points_count == 14 * 24


# ---------------------------------------------------------------------------
# compute_autoscale_thresholds
# ---------------------------------------------------------------------------

class TestAutoscaleThresholds:
    def test_basic_computation(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.DIURNAL,
            confidence=0.9,
            peak_avg=80.0,
            trough_avg=10.0,
            p90=75.0,
            p95=82.0,
        )
        thresholds = compute_autoscale_thresholds(analysis, current_vm_vcpus=2)
        assert thresholds.min_instances >= 1
        assert thresholds.max_instances > thresholds.min_instances
        assert thresholds.scale_out_cpu_pct == 70.0
        assert thresholds.scale_in_cpu_pct == 30.0
        assert thresholds.cooldown_minutes == 5

    def test_target_utilization_capped_at_95(self):
        """VPA target (p90 * 1.15) should not exceed 95%."""
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.DIURNAL,
            confidence=0.9,
            p90=90.0,
        )
        thresholds = compute_autoscale_thresholds(analysis)
        assert thresholds.target_utilization_pct <= 95.0

    def test_max_always_exceeds_min(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.STEADY_STATE,
            confidence=0.9,
            peak_avg=10.0,
            trough_avg=8.0,
            p90=9.0,
        )
        thresholds = compute_autoscale_thresholds(analysis, current_vm_vcpus=1)
        assert thresholds.max_instances >= thresholds.min_instances + 1

    def test_higher_vcpus_scales_instances(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.DIURNAL,
            confidence=0.9,
            peak_avg=80.0,
            trough_avg=10.0,
            p90=75.0,
        )
        small = compute_autoscale_thresholds(analysis, current_vm_vcpus=1)
        large = compute_autoscale_thresholds(analysis, current_vm_vcpus=4)
        # More vCPUs should mean more instances at the same utilization
        assert large.max_instances >= small.max_instances


# ---------------------------------------------------------------------------
# compute_schedule
# ---------------------------------------------------------------------------

class TestComputeSchedule:
    def test_weekly_pattern_stops_weekends(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.WEEKLY,
            confidence=0.9,
            weekend_avg=5.0,
        )
        sched = compute_schedule(analysis)
        assert sched.stop_days == ["Saturday", "Sunday"]
        assert sched.estimated_savings_pct == pytest.approx(28.6, abs=0.1)

    def test_weekly_pattern_high_weekend_no_stop(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.WEEKLY,
            confidence=0.9,
            weekend_avg=30.0,
        )
        sched = compute_schedule(analysis)
        assert sched.stop_days == []
        assert sched.estimated_savings_pct == 0.0

    def test_diurnal_pattern_with_low_trough(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.DIURNAL,
            confidence=0.9,
            trough_avg=5.0,
            trough_hours=[0, 1, 2, 3, 4, 5],
        )
        sched = compute_schedule(analysis)
        assert len(sched.stop_hours) == 1
        assert sched.estimated_savings_pct == 25.0

    def test_diurnal_pattern_high_trough_no_schedule(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.DIURNAL,
            confidence=0.9,
            trough_avg=30.0,
            trough_hours=[0, 1, 2, 3, 4, 5],
        )
        sched = compute_schedule(analysis)
        assert sched.stop_hours == []

    def test_steady_state_no_schedule(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.STEADY_STATE,
            confidence=0.9,
        )
        sched = compute_schedule(analysis)
        assert sched.stop_hours == []
        assert sched.stop_days == []
        assert sched.estimated_savings_pct == 0.0


# ---------------------------------------------------------------------------
# generate_recommendation
# ---------------------------------------------------------------------------

class TestGenerateRecommendation:
    """Test the decision matrix that maps patterns to recommendation types."""

    def test_diurnal_high_ratio_autoscale(self):
        random.seed(42)
        series = _make_series(_diurnal_data(days=30, peak_pct=80, trough_pct=10))
        analysis = classify_pattern(series)
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.AUTOSCALE
        assert rec.autoscale is not None
        assert rec.severity == "high"
        assert "diurnal" in rec.explanation.lower() or "peak" in rec.explanation.lower()
        assert rec.estimated_savings_pct > 0

    def test_weekly_low_weekend_schedule(self):
        random.seed(42)
        series = _make_series(_weekly_data(days=28, weekday_pct=60, weekend_pct=5))
        analysis = classify_pattern(series)
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.SCHEDULE
        assert rec.schedule is not None
        assert "Saturday" in rec.schedule.stop_days or "Sunday" in rec.schedule.stop_days
        assert rec.severity == "high"

    def test_steady_state_low_util_rightsize(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.STEADY_STATE,
            confidence=0.9,
            p90=20.0,
            p95=25.0,
            coefficient_of_variation=0.1,
            observation_days=30,
        )
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.RIGHTSIZE
        assert "rightsize" in rec.explanation.lower() or "over-provisioned" in rec.explanation.lower()

    def test_steady_state_high_util_no_action(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.STEADY_STATE,
            confidence=0.9,
            p90=70.0,
            p95=75.0,
            coefficient_of_variation=0.1,
            observation_days=30,
        )
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.NO_ACTION

    def test_burst_sporadic_spot(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.BURST_SPORADIC,
            confidence=0.8,
            p50=2.0,
            p99=90.0,
            trough_avg=1.5,
            observation_days=30,
        )
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.SPOT_CANDIDATE
        assert rec.estimated_savings_pct > 0

    def test_growing_autoscale(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.GROWING,
            confidence=0.8,
            p90=60.0,
            peak_avg=70.0,
            trough_avg=30.0,
            trend_slope_pct_per_week=8.0,
            observation_days=30,
        )
        rec = generate_recommendation(analysis)
        assert rec.type == RecommendationType.AUTOSCALE
        assert rec.autoscale is not None
        assert rec.severity == "high"
        # Growing recommendation has 0 savings (it's about capacity planning)
        assert rec.estimated_savings_pct == 0.0

    def test_evidence_dict_populated(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.STEADY_STATE,
            confidence=0.9,
            p50=40.0,
            p90=50.0,
            p95=55.0,
            p99=60.0,
            coefficient_of_variation=0.1,
            peak_avg=55.0,
            trough_avg=35.0,
            peak_trough_ratio=1.6,
            weekday_avg=45.0,
            weekend_avg=40.0,
            observation_days=30,
            data_points_count=720,
        )
        rec = generate_recommendation(analysis)
        ev = rec.evidence
        assert ev["observation_days"] == 30
        assert ev["data_points"] == 720
        assert ev["p50"] == 40.0
        assert ev["p90"] == 50.0
        assert ev["cv"] == 0.1

    def test_recommendation_carries_pattern_and_confidence(self):
        analysis = PatternAnalysis(
            pattern=WorkloadPattern.BURST_SPORADIC,
            confidence=0.75,
            p50=2.0,
            p99=90.0,
            trough_avg=1.0,
            observation_days=30,
        )
        rec = generate_recommendation(analysis)
        assert rec.pattern == WorkloadPattern.BURST_SPORADIC
        assert rec.confidence == 0.75
        assert rec.analysis is analysis
