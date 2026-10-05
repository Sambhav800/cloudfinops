"""
GPU Workload Analyzer — LLM-powered pattern analysis using Gemini.
Detects temporal patterns, generates health reports, and predicts cost trajectories.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from ..config import DEFAULT_GEMINI_FLASH_MODEL
from .gemini_models import resolve_gemini_model_name

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GpuWorkloadAnalyzer:
    """Uses Gemini to analyze GPU workload patterns and generate intelligence reports."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("GEMINI_AGENT_MODEL", DEFAULT_GEMINI_FLASH_MODEL)
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    async def analyze_patterns(
        self,
        metrics_history: list[dict[str, Any]],
        resource_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send metrics history to Gemini for workload pattern detection.
        Identifies: time-of-day patterns, weekly recurrence, job scheduler patterns.
        """
        if not self.api_key:
            return self._fallback_pattern_analysis(metrics_history, resource_meta)

        prompt = f"""Analyze this GPU resource's utilization metrics and identify workload patterns.

Resource: {resource_meta.get('resource_name', 'Unknown')}
Instance Type: {resource_meta.get('instance_type', 'Unknown')}
Provider: {resource_meta.get('provider', 'Unknown')}
GPU Type: {resource_meta.get('gpu_type', 'Unknown')}

Metrics History (daily averages, most recent first):
{json.dumps(metrics_history[:30], indent=2)}

Analyze and return a JSON object with:
{{
  "workload_type": "training|inference|rendering|idle|burst|mixed",
  "confidence": 0.0-1.0,
  "temporal_pattern": "continuous|business_hours|overnight|weekly_batch|sporadic|none",
  "peak_hours": [list of hours 0-23 when utilization peaks],
  "idle_windows": [list of hour ranges when GPU is idle],
  "trend": "increasing|stable|decreasing|cyclical",
  "anomalies": ["list of detected anomalies"],
  "recommendation": "one-sentence optimization recommendation"
}}

Be precise. Base conclusions only on the data provided."""

        try:
            result = await self._call_gemini(prompt)
            try:
                parsed = json.loads(result)
                return {"status": "success", "analysis": parsed}
            except json.JSONDecodeError:
                return {"status": "success", "analysis": {"raw_response": result}}
        except Exception as e:
            logger.warning(f"Gemini pattern analysis failed: {e}")
            return self._fallback_pattern_analysis(metrics_history, resource_meta)

    async def generate_health_report(self, gpu_summary: dict[str, Any]) -> str:
        """Generate a CTO-grade natural language GPU health report."""
        if not self.api_key:
            return gpu_summary.get("ai_narrative", "GPU intelligence report unavailable.")

        prompt = f"""Generate a concise, executive-level GPU infrastructure health report.

GPU Fleet Summary:
- Total GPU instances: {len(gpu_summary.get('gpu_resources', []))}
- Total monthly spend: ${gpu_summary.get('total_gpu_spend', 0):,.0f}
- Ghost GPUs (idle/wasted): {len(gpu_summary.get('ghost_gpus', []))}
- Monthly waste: ${gpu_summary.get('total_gpu_waste', 0):,.0f}
- MIG candidates: {len(gpu_summary.get('mig_candidates', []))}
- Arbitrage savings available: ${gpu_summary.get('total_savings_available', 0):,.0f}/month
- Providers: {', '.join(gpu_summary.get('providers_detected', []))}

Ghost GPU Details:
{json.dumps(gpu_summary.get('ghost_gpus', [])[:5], indent=2)}

Write 3-5 sentences maximum. Be direct. State the problem, quantify the waste, and give the top action item.
Use this format: [Situation] → [Impact] → [Recommended Action]"""

        try:
            return await self._call_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini health report failed: {e}")
            return gpu_summary.get("ai_narrative", "")

    async def predict_cost_trajectory(
        self,
        daily_costs: list[dict[str, Any]],
        gpu_count_trend: list[int],
    ) -> dict[str, Any]:
        """Predict GPU spend growth using historical data + Gemini reasoning."""
        if not self.api_key or not daily_costs:
            return self._fallback_forecast(daily_costs)

        prompt = f"""Predict GPU cost trajectory based on this historical data.

Daily GPU Costs (last 30 days, most recent first):
{json.dumps(daily_costs[:30], indent=2)}

GPU Instance Count Trend: {gpu_count_trend[:30]}

Return a JSON object:
{{
  "predicted_monthly_cost_30d": float,
  "predicted_monthly_cost_90d": float,
  "growth_rate_pct_monthly": float,
  "trend": "accelerating|linear|decelerating|flat|declining",
  "confidence": 0.0-1.0,
  "risk_factors": ["list of cost risk factors"],
  "recommendation": "one-sentence cost management advice"
}}"""

        try:
            result = await self._call_gemini(prompt)
            try:
                return {"status": "success", "forecast": json.loads(result)}
            except json.JSONDecodeError:
                return {"status": "partial", "raw": result}
        except Exception as e:
            logger.warning(f"Gemini cost prediction failed: {e}")
            return self._fallback_forecast(daily_costs)

    async def _call_gemini(self, prompt: str) -> str:
        """Make a Gemini API call."""
        model_name = await resolve_gemini_model_name(self.model, api_key=self.api_key)
        url = f"{_GEMINI_BASE_URL}/{model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in Gemini response")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError("No parts in Gemini response")
        text = parts[0].get("text", "")
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return text.strip()

    def _fallback_pattern_analysis(
        self, metrics: list[dict], resource_meta: dict
    ) -> dict[str, Any]:
        """Rule-based fallback when Gemini is unavailable."""
        if not metrics:
            return {"status": "fallback", "analysis": {"workload_type": "unknown", "confidence": 0.0}}

        sm_values = [m.get("sm_pct", 0) for m in metrics if m.get("sm_pct") is not None]
        if not sm_values:
            return {"status": "fallback", "analysis": {"workload_type": "unknown", "confidence": 0.0}}

        avg_sm = sum(sm_values) / len(sm_values)
        if avg_sm < 10:
            wtype = "idle"
        elif avg_sm > 70:
            wtype = "training"
        elif 20 <= avg_sm <= 60:
            wtype = "inference"
        else:
            wtype = "mixed"

        return {
            "status": "fallback",
            "analysis": {
                "workload_type": wtype,
                "confidence": 0.6,
                "temporal_pattern": "unknown",
                "trend": "stable",
            },
        }

    def _fallback_forecast(self, daily_costs: list[dict]) -> dict[str, Any]:
        """Holt-Winters-inspired fallback when Gemini is unavailable."""
        if not daily_costs:
            return {"status": "fallback", "forecast": {"predicted_monthly_cost_30d": 0, "trend": "flat"}}

        costs = [d.get("cost", 0) for d in daily_costs if d.get("cost") is not None]
        if not costs:
            return {"status": "fallback", "forecast": {"predicted_monthly_cost_30d": 0, "trend": "flat"}}

        avg_daily = sum(costs) / len(costs)
        predicted_monthly = round(avg_daily * 30, 2)

        if len(costs) >= 7:
            recent = sum(costs[:7]) / 7
            older = sum(costs[7:14]) / max(len(costs[7:14]), 1)
            if older > 0:
                growth = ((recent - older) / older) * 100
            else:
                growth = 0
        else:
            growth = 0

        trend = "increasing" if growth > 5 else "declining" if growth < -5 else "flat"

        return {
            "status": "fallback",
            "forecast": {
                "predicted_monthly_cost_30d": predicted_monthly,
                "predicted_monthly_cost_90d": round(predicted_monthly * (1 + growth / 100 * 3), 2),
                "growth_rate_pct_monthly": round(growth, 1),
                "trend": trend,
                "confidence": 0.5,
            },
        }
