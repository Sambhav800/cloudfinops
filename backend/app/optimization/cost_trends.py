"""
Cost Trend Analysis — Leverage daily_spend_history for predictive detection.

Uses the existing 60-day daily_spend_history MongoDB collection to detect:
1. Cost anomalies (sudden spikes or drops)
2. Declining spend (resource/service being decommissioned)
3. Growing spend (capacity planning signal)
4. Flat-line spend (potential zombie — paying for something unused)

This module is called during classification to add cost-based evidence
to the EvidenceBundle, strengthening or weakening waste verdicts.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CostTrendSignal:
    """A cost-based signal that corroborates or vetoes waste classification."""

    trend_type: str  # "declining", "growing", "anomaly_spike", "anomaly_drop", "flatline", "stable"
    confidence: float  # 0.0–1.0
    description: str
    corroborates_waste: bool  # True = supports waste verdict, False = vetoes it
    days_analyzed: int = 0
    slope_per_day: float = 0.0
    recent_daily_avg: float = 0.0
    historical_daily_avg: float = 0.0


async def analyze_cost_trends(
    db: Any,
    user_id: str,
    integration_id: str,
    resource_cost: float = 0.0,
    lookback_days: int = 60,
) -> Optional[CostTrendSignal]:
    """
    Analyze cost trends for an integration from daily_spend_history.

    This provides integration-level cost intelligence. When combined with
    per-resource signals, it strengthens classification confidence.

    Args:
        db: MongoDBClient
        user_id: User ID
        integration_id: Integration to analyze
        resource_cost: Current cost of the resource being classified
        lookback_days: How many days of history to examine
    """
    if not db:
        return None

    try:
        history = await db.select(
            "daily_spend_history",
            filters={
                "user_id": user_id,
                "integration_id": integration_id,
            },
        )

        if not history or len(history) < 14:
            return None

        # Sort by date and extract daily totals
        sorted_history = sorted(history, key=lambda h: h.get("spend_date", ""))
        daily_totals = [
            float(h.get("total_spend", 0) or 0)
            for h in sorted_history[-lookback_days:]
        ]

        if len(daily_totals) < 14:
            return None

        return compute_cost_trend(daily_totals, resource_cost)

    except Exception as e:
        logger.debug(f"Cost trend analysis failed: {e}")
        return None


def compute_cost_trend(
    daily_totals: List[float],
    resource_cost: float = 0.0,
) -> Optional[CostTrendSignal]:
    """
    Compute cost trend from daily spend values.

    Stateless function for testability — takes raw daily values.
    """
    if not daily_totals or len(daily_totals) < 14:
        return None

    n = len(daily_totals)
    recent_7d = daily_totals[-7:]
    older_7d = daily_totals[-14:-7]

    recent_avg = mean(recent_7d)
    older_avg = mean(older_7d) if older_7d else recent_avg
    overall_avg = mean(daily_totals)
    overall_std = stdev(daily_totals) if len(daily_totals) > 1 else 0.0

    # Compute linear slope
    slope = _linear_slope(daily_totals)

    # --- Anomaly detection (Z-score based, runs first as highest priority) ---
    if overall_std > 0 and n >= 20:
        recent_zscore = (recent_avg - overall_avg) / overall_std

        # Spike: recent spend is 2+ standard deviations above mean
        if recent_zscore > 2.0:
            return CostTrendSignal(
                trend_type="anomaly_spike",
                confidence=min(0.90, 0.6 + recent_zscore * 0.1),
                description=(
                    f"Cost spike: recent 7d avg (${recent_avg:.0f}/day) is "
                    f"{recent_zscore:.1f}σ above historical mean (${overall_avg:.0f}/day)"
                ),
                corroborates_waste=False,  # Spike means resource IS being used
                days_analyzed=n,
                slope_per_day=slope,
                recent_daily_avg=recent_avg,
                historical_daily_avg=overall_avg,
            )

        # Drop: recent spend is 2+ standard deviations below mean
        if recent_zscore < -2.0 and older_avg > 0:
            return CostTrendSignal(
                trend_type="anomaly_drop",
                confidence=min(0.85, 0.6 + abs(recent_zscore) * 0.1),
                description=(
                    f"Cost drop: recent 7d avg (${recent_avg:.0f}/day) is "
                    f"{abs(recent_zscore):.1f}σ below historical mean (${overall_avg:.0f}/day)"
                ),
                corroborates_waste=True,  # Drop suggests decommissioning
                days_analyzed=n,
                slope_per_day=slope,
                recent_daily_avg=recent_avg,
                historical_daily_avg=overall_avg,
            )

    # --- Declining trend ---
    if older_avg > 0:
        decline_ratio = (older_avg - recent_avg) / older_avg

        if decline_ratio > 0.5 and slope < 0:
            return CostTrendSignal(
                trend_type="declining",
                confidence=min(0.85, 0.6 + decline_ratio * 0.3),
                description=(
                    f"Declining spend: dropped {decline_ratio*100:.0f}% over 14 days "
                    f"(${older_avg:.0f}/day → ${recent_avg:.0f}/day)"
                ),
                corroborates_waste=True,
                days_analyzed=n,
                slope_per_day=slope,
                recent_daily_avg=recent_avg,
                historical_daily_avg=older_avg,
            )

    # --- Growing trend ---
    if older_avg > 0:
        growth_ratio = (recent_avg - older_avg) / older_avg

        if growth_ratio > 0.3 and slope > 0:
            return CostTrendSignal(
                trend_type="growing",
                confidence=min(0.80, 0.5 + growth_ratio * 0.2),
                description=(
                    f"Growing spend: increased {growth_ratio*100:.0f}% over 14 days "
                    f"(${older_avg:.0f}/day → ${recent_avg:.0f}/day)"
                ),
                corroborates_waste=False,  # Growing = actively used
                days_analyzed=n,
                slope_per_day=slope,
                recent_daily_avg=recent_avg,
                historical_daily_avg=older_avg,
            )

    # --- Flatline detection (constant non-zero cost with zero variation) ---
    if overall_avg > 1.0 and overall_std < overall_avg * 0.05 and n >= 30:
        cv = overall_std / overall_avg
        return CostTrendSignal(
            trend_type="flatline",
            confidence=min(0.70, 0.5 + (1.0 - cv) * 0.3),
            description=(
                f"Flatline cost: ${overall_avg:.0f}/day with <5% variation "
                f"over {n} days (CV={cv:.3f}). May indicate unused reserved capacity."
            ),
            corroborates_waste=True,  # Constant cost with no usage variation is suspicious
            days_analyzed=n,
            slope_per_day=slope,
            recent_daily_avg=recent_avg,
            historical_daily_avg=overall_avg,
        )

    # --- Stable (healthy, no signal) ---
    return CostTrendSignal(
        trend_type="stable",
        confidence=0.0,
        description=f"Stable spend: ${overall_avg:.0f}/day avg over {n} days",
        corroborates_waste=False,
        days_analyzed=n,
        slope_per_day=slope,
        recent_daily_avg=recent_avg,
        historical_daily_avg=overall_avg,
    )


def _linear_slope(values: List[float]) -> float:
    """Compute linear regression slope (change per day)."""
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
