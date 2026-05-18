"""
CloudFront-specific deep analysis helpers.
"""

from __future__ import annotations

from typing import Any


def _classify(description: str) -> str:
    lowered = description.lower()
    if "lambda@edge" in lowered or "lambda-edge" in lowered:
        return "lambda_edge"
    if "transfer" in lowered or "bandwidth" in lowered or "bytes" in lowered:
        return "data_transfer"
    if "request" in lowered:
        return "requests"
    if "origin" in lowered:
        return "origin_fetch"
    return "other"


def analyze_cloudfront_bill(descriptions: list[str], amounts: list[float]) -> dict[str, Any]:
    total_spend = 0.0
    cost_by_type: dict[str, float] = {}

    for description, amount in zip(descriptions, amounts):
        value = float(amount or 0.0)
        if value <= 0:
            continue

        total_spend += value
        cost_type = _classify(description or "")
        cost_by_type[cost_type] = round(cost_by_type.get(cost_type, 0.0) + value, 2)

    lambda_edge_total = round(cost_by_type.get("lambda_edge", 0.0), 2)
    transfer_total = round(cost_by_type.get("data_transfer", 0.0), 2)
    total_spend = round(total_spend, 2)

    opportunities: list[dict[str, Any]] = []
    alerts: list[str] = []
    recommendations: list[str] = []

    if lambda_edge_total > 0:
        potential = round(lambda_edge_total * 0.55, 2)
        opportunities.append(
            {
                "opportunity": "Evaluate CloudFront Functions for Lambda@Edge-compatible logic",
                "current_cost_monthly": lambda_edge_total,
                "estimated_cost_after": round(lambda_edge_total - potential, 2),
                "monthly_savings": potential,
                "savings_pct": round((potential / lambda_edge_total) * 100, 1) if lambda_edge_total else 0.0,
                "effort": "Medium",
                "risk": "Low",
                "note": "Header/URL rewrite patterns often migrate to CloudFront Functions at lower cost.",
            }
        )
        alerts.append(
            f"Lambda@Edge spend detected: ${lambda_edge_total:.2f}/month. "
            "Review whether function logic can move to CloudFront Functions."
        )
        recommendations.append("Audit Lambda@Edge usage and migrate simple request logic to CloudFront Functions.")

    if transfer_total > 0:
        potential = round(transfer_total * 0.08, 2)
        opportunities.append(
            {
                "opportunity": "Optimize egress/cache policy and compare CDN blend",
                "current_cost_monthly": transfer_total,
                "estimated_cost_after": round(transfer_total - potential, 2),
                "monthly_savings": potential,
                "savings_pct": round((potential / transfer_total) * 100, 1) if transfer_total else 0.0,
                "effort": "Low",
                "risk": "Low",
                "note": "Cache-key tuning and origin shielding typically reduce transfer spend quickly.",
            }
        )
        recommendations.append("Tune CloudFront cache policy and review high-egress paths.")

    total_monthly_savings = round(sum(item["monthly_savings"] for item in opportunities), 2)

    return {
        "total_spend": total_spend,
        "annual_projection": round(total_spend * 12, 2),
        "cost_by_type": cost_by_type,
        "cost_by_region": {},
        "lambda_edge_total": lambda_edge_total,
        "savings_opportunities": opportunities,
        "alerts": alerts,
        "recommendations": recommendations,
        "summary": {
            "total_monthly_savings_available": total_monthly_savings,
            "total_annual_savings_available": round(total_monthly_savings * 12, 2),
            "savings_pct_of_bill": round((total_monthly_savings / total_spend) * 100, 1) if total_spend else 0.0,
            "opportunities_count": len(opportunities),
        },
    }
