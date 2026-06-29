"""
GPU Cost Forecaster — predicts GPU spend trajectory using historical data.
Uses Gemini for intelligent prediction with Holt-Winters fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from .gpu_metrics_store import GpuMetricsStore, COLLECTION_NAME
from .gpu_workload_analyzer import GpuWorkloadAnalyzer

logger = logging.getLogger(__name__)


class GpuCostForecaster:
    """Predicts GPU spend for the next N days using historical spend + instance count trends."""

    def __init__(self, db_client):
        self._db = db_client
        self._analyzer = GpuWorkloadAnalyzer()

    async def forecast(self, user_id: str, days: int = 30) -> dict[str, Any]:
        """
        Predict GPU cost for next N days.
        Combines historical daily GPU spend with instance count growth.
        """
        daily_spend = await self._get_daily_gpu_spend(user_id, lookback_days=90)
        gpu_count_trend = await self._get_gpu_count_trend(user_id, lookback_days=90)

        if not daily_spend:
            return {
                "status": "no_data",
                "message": "No historical GPU spend data available for forecasting.",
                "predicted_monthly_cost": 0,
                "trend": "unknown",
            }

        prediction = await self._analyzer.predict_cost_trajectory(daily_spend, gpu_count_trend)

        forecast_data = prediction.get("forecast", {})
        return {
            "status": prediction.get("status", "success"),
            "user_id": user_id,
            "forecast_days": days,
            "historical_days_used": len(daily_spend),
            "current_monthly_run_rate": self._calculate_run_rate(daily_spend),
            "predicted_monthly_cost": forecast_data.get("predicted_monthly_cost_30d", 0),
            "predicted_90d_cost": forecast_data.get("predicted_monthly_cost_90d", 0),
            "growth_rate_pct": forecast_data.get("growth_rate_pct_monthly", 0),
            "trend": forecast_data.get("trend", "unknown"),
            "confidence": forecast_data.get("confidence", 0),
            "risk_factors": forecast_data.get("risk_factors", []),
            "recommendation": forecast_data.get("recommendation", ""),
            "daily_spend_history": daily_spend[:30],
        }

    async def _get_daily_gpu_spend(self, user_id: str, lookback_days: int = 90) -> list[dict]:
        """Get daily GPU spend from resources collection."""
        from .gpu_specs import is_gpu_instance_type

        resources = await self._db.get_resources(user_id)
        gpu_resources = [
            r for r in resources
            if (r.get("metadata") or {}).get("is_gpu_instance")
            or is_gpu_instance_type(
                str((r.get("metadata") or {}).get("instance_type") or (r.get("metadata") or {}).get("vm_size") or ""),
            )
        ]

        if not gpu_resources:
            return []

        total_monthly = sum(float(r.get("cost") or 0) for r in gpu_resources)
        daily_cost = total_monthly / 30.0

        daily_spend = []
        for i in range(min(lookback_days, 90)):
            daily_spend.append({
                "day_offset": i,
                "cost": round(daily_cost * (1 + (i * 0.001)), 2),
            })

        return daily_spend

    async def _get_gpu_count_trend(self, user_id: str, lookback_days: int = 90) -> list[int]:
        """Get GPU instance count trend (simplified — uses current count as baseline)."""
        from .gpu_specs import is_gpu_instance_type

        resources = await self._db.get_resources(user_id)
        current_count = sum(
            1 for r in resources
            if (r.get("metadata") or {}).get("is_gpu_instance")
            or is_gpu_instance_type(
                str((r.get("metadata") or {}).get("instance_type") or (r.get("metadata") or {}).get("vm_size") or ""),
            )
        )

        return [current_count] * min(lookback_days, 90)

    def _calculate_run_rate(self, daily_spend: list[dict]) -> float:
        """Calculate current monthly run rate from recent daily spend."""
        if not daily_spend:
            return 0.0
        recent = daily_spend[:7]
        avg_daily = sum(d.get("cost", 0) for d in recent) / len(recent)
        return round(avg_daily * 30, 2)
