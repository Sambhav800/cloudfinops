"""
GPU spend/arbitrage heuristics for billing files.
Expanded: 14 SKUs, 4 specialized GPU clouds, MIG candidates, ghost GPU detection.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# GPU SKU database — AWS instance → GPU spec + pricing on specialized clouds
# All prices are approximate USD/hour on-demand (2024-2025 public rates)
# ─────────────────────────────────────────────────────────────────────────────
_GPU_SKUS: dict[str, dict[str, Any]] = {
    # ── P3 (Tesla V100) ──────────────────────────────────────────────────────
    "p3.2xlarge": {
        "gpu_type": "1× NVIDIA V100 16GB",
        "gpu_count": 1,
        "aws_hourly": 3.06,
        "supports_mig": False,
        "lambda_hourly": 1.40,
        "coreweave_hourly": 1.10,
        "jarvis_hourly": 1.25,
        "runpod_hourly": 0.89,
    },
    "p3.8xlarge": {
        "gpu_type": "4× NVIDIA V100 16GB",
        "gpu_count": 4,
        "aws_hourly": 12.24,
        "supports_mig": False,
        "lambda_hourly": 5.60,
        "coreweave_hourly": 4.40,
        "jarvis_hourly": 5.00,
        "runpod_hourly": 3.56,
    },
    "p3.16xlarge": {
        "gpu_type": "8× NVIDIA V100 16GB",
        "gpu_count": 8,
        "aws_hourly": 24.48,
        "supports_mig": False,
        "lambda_hourly": 11.20,
        "coreweave_hourly": 8.80,
        "jarvis_hourly": 10.00,
        "runpod_hourly": 7.12,
    },
    "p3dn.24xlarge": {
        "gpu_type": "8× NVIDIA V100 32GB NVLink",
        "gpu_count": 8,
        "aws_hourly": 31.212,
        "supports_mig": False,
        "lambda_hourly": 14.40,
        "coreweave_hourly": 11.20,
        "jarvis_hourly": 12.80,
        "runpod_hourly": 9.60,
    },
    # ── P4 (A100 40/80GB) ────────────────────────────────────────────────────
    "p4d.24xlarge": {
        "gpu_type": "8× NVIDIA A100 40GB",
        "gpu_count": 8,
        "aws_hourly": 32.77,
        "supports_mig": True,
        "mig_slices": 56,
        "lambda_hourly": 20.32,
        "coreweave_hourly": 17.60,
        "jarvis_hourly": 19.20,
        "runpod_hourly": 14.24,
    },
    "p4de.24xlarge": {
        "gpu_type": "8× NVIDIA A100 80GB",
        "gpu_count": 8,
        "aws_hourly": 40.96,
        "supports_mig": True,
        "mig_slices": 56,
        "lambda_hourly": 25.60,
        "coreweave_hourly": 22.40,
        "jarvis_hourly": 24.00,
        "runpod_hourly": 17.92,
    },
    # ── P5 (H100) ────────────────────────────────────────────────────────────
    "p5.48xlarge": {
        "gpu_type": "8× NVIDIA H100 80GB SXM",
        "gpu_count": 8,
        "aws_hourly": 98.32,
        "supports_mig": True,
        "mig_slices": 56,
        "lambda_hourly": 56.96,
        "coreweave_hourly": 49.60,
        "jarvis_hourly": 54.40,
        "runpod_hourly": 41.60,
    },
    # ── G4 (T4) ──────────────────────────────────────────────────────────────
    "g4dn.xlarge": {
        "gpu_type": "1× NVIDIA T4 16GB",
        "gpu_count": 1,
        "aws_hourly": 0.526,
        "supports_mig": False,
        "lambda_hourly": 0.35,
        "coreweave_hourly": 0.29,
        "jarvis_hourly": 0.32,
        "runpod_hourly": 0.22,
    },
    "g4dn.2xlarge": {
        "gpu_type": "1× NVIDIA T4 16GB",
        "gpu_count": 1,
        "aws_hourly": 0.752,
        "supports_mig": False,
        "lambda_hourly": 0.45,
        "coreweave_hourly": 0.38,
        "jarvis_hourly": 0.42,
        "runpod_hourly": 0.28,
    },
    "g4dn.4xlarge": {
        "gpu_type": "1× NVIDIA T4 16GB",
        "gpu_count": 1,
        "aws_hourly": 1.204,
        "supports_mig": False,
        "lambda_hourly": 0.72,
        "coreweave_hourly": 0.61,
        "jarvis_hourly": 0.68,
        "runpod_hourly": 0.46,
    },
    # ── G5 (A10G) ────────────────────────────────────────────────────────────
    "g5.2xlarge": {
        "gpu_type": "1× NVIDIA A10G 24GB",
        "gpu_count": 1,
        "aws_hourly": 1.212,
        "supports_mig": False,
        "lambda_hourly": 0.76,
        "coreweave_hourly": 0.65,
        "jarvis_hourly": 0.72,
        "runpod_hourly": 0.51,
    },
    "g5.4xlarge": {
        "gpu_type": "1× NVIDIA A10G 24GB",
        "gpu_count": 1,
        "aws_hourly": 1.624,
        "supports_mig": False,
        "lambda_hourly": 0.98,
        "coreweave_hourly": 0.84,
        "jarvis_hourly": 0.93,
        "runpod_hourly": 0.66,
    },
    # ── Trainium + Inferentia ─────────────────────────────────────────────────
    "trn1.32xlarge": {
        "gpu_type": "16× AWS Trainium (ML Training)",
        "gpu_count": 16,
        "aws_hourly": 21.50,
        "supports_mig": False,
        "lambda_hourly": None,  # No equivalent — AWS proprietary
        "coreweave_hourly": 15.20,  # A100 equivalent
        "jarvis_hourly": None,
        "runpod_hourly": 12.80,
    },
    "inf2.xlarge": {
        "gpu_type": "1× AWS Inferentia2 (ML Inference)",
        "gpu_count": 1,
        "aws_hourly": 0.758,
        "supports_mig": False,
        "lambda_hourly": None,  # AWS proprietary
        "coreweave_hourly": 0.29,  # T4 equivalent for inference
        "jarvis_hourly": 0.32,
        "runpod_hourly": 0.22,
    },
}

# Approximate hours in a billing month
_HOURS_PER_MONTH = 730


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[\$,€£₹,\sA-Za-z]", "", regex=True),
        errors="coerce",
    ).fillna(0.0)


def _monthly_cost_to_hourly(monthly: float, sku_meta: dict[str, Any]) -> float:
    """Estimate hourly rate from monthly billing cost."""
    if sku_meta.get("aws_hourly"):
        return float(sku_meta["aws_hourly"])
    return monthly / _HOURS_PER_MONTH


def _best_specialized_cloud(sku_meta: dict[str, Any]) -> tuple[str, float] | tuple[None, None]:
    """Return (cloud_name, hourly_rate) for the cheapest specialized GPU cloud."""
    candidates = {
        "Lambda Labs": sku_meta.get("lambda_hourly"),
        "CoreWeave": sku_meta.get("coreweave_hourly"),
        "JarvisLabs": sku_meta.get("jarvis_hourly"),
        "RunPod": sku_meta.get("runpod_hourly"),
    }
    valid = {k: v for k, v in candidates.items() if v is not None}
    if not valid:
        return None, None
    best = min(valid, key=valid.__getitem__)
    return best, valid[best]


def analyze_gpu_billing(
    df: pd.DataFrame,
    service_col: str,
    cost_col: str,
) -> dict[str, Any]:
    """
    Full GPU intelligence analysis on a cloud billing DataFrame.

    Returns:
        gpu_instances_found:      Every GPU billing line item matched
        arbitrage_opportunities:  Per-instance cross-cloud pricing (all 4 specialized clouds)
        ghost_gpus:               High-cost instances likely running idle ($300+/mo)
        mig_candidates:           A100/H100 instances that could use MIG partitioning
        total_gpu_spend:          Sum of all GPU line item costs
        total_potential_savings:  Best-case savings from switching to cheapest alternative
        annual_waste_if_unresolved: Ghost GPU annual burn rate
    """
    insights: dict[str, Any] = {
        "gpu_instances_found": [],
        "arbitrage_opportunities": [],
        "ghost_gpus": [],
        "mig_candidates": [],
        "total_gpu_spend": 0.0,
        "total_potential_savings": 0.0,
        "annual_waste_if_unresolved": 0.0,
    }

    if df.empty or service_col not in df.columns or cost_col not in df.columns:
        return insights

    service_values = df[service_col].fillna("").astype(str)
    cost_values = _to_float(df[cost_col])

    annual_waste = 0.0

    for idx, (description, cost) in enumerate(zip(service_values.tolist(), cost_values.tolist())):
        if cost <= 0:
            continue

        lowered = description.lower()
        matched_sku = next((sku for sku in _GPU_SKUS if sku in lowered), None)
        if not matched_sku:
            continue

        sku_meta = _GPU_SKUS[matched_sku]
        resource_id = f"gpu_row_{idx}"
        monthly_cost = round(float(cost), 2)

        # ── Record instance found ─────────────────────────────────────────────
        insights["gpu_instances_found"].append({
            "resource_id": resource_id,
            "sku": matched_sku,
            "gpu_type": sku_meta["gpu_type"],
            "gpu_count": sku_meta.get("gpu_count", 1),
            "cost": monthly_cost,
            "description_snippet": description[:100],
        })
        insights["total_gpu_spend"] = round(float(insights["total_gpu_spend"]) + monthly_cost, 2)

        # ── Cross-cloud arbitrage (all 4 specialized clouds) ──────────────────
        best_cloud, best_hourly = _best_specialized_cloud(sku_meta)
        aws_hourly = sku_meta.get("aws_hourly") or (monthly_cost / _HOURS_PER_MONTH)

        all_cloud_costs = {
            "AWS (On-Demand)": monthly_cost,
            "Lambda Labs": round(sku_meta["lambda_hourly"] * _HOURS_PER_MONTH, 2) if sku_meta.get("lambda_hourly") else None,
            "CoreWeave": round(sku_meta["coreweave_hourly"] * _HOURS_PER_MONTH, 2) if sku_meta.get("coreweave_hourly") else None,
            "JarvisLabs": round(sku_meta["jarvis_hourly"] * _HOURS_PER_MONTH, 2) if sku_meta.get("jarvis_hourly") else None,
            "RunPod": round(sku_meta["runpod_hourly"] * _HOURS_PER_MONTH, 2) if sku_meta.get("runpod_hourly") else None,
        }

        if best_cloud and best_hourly:
            alt_monthly = round(best_hourly * _HOURS_PER_MONTH, 2)
            savings = round(monthly_cost - alt_monthly, 2)
            savings_pct = round((savings / monthly_cost) * 100, 1) if monthly_cost > 0 else 0.0

            if savings > 0:
                insights["arbitrage_opportunities"].append({
                    "resource_id": resource_id,
                    "sku": matched_sku,
                    "gpu_type": sku_meta["gpu_type"],
                    "current_cost": monthly_cost,
                    "best_alternative_cloud": best_cloud,
                    "best_alternative_cost": alt_monthly,
                    "savings": savings,
                    "savings_pct": savings_pct,
                    "all_cloud_costs": all_cloud_costs,
                    "message": (
                        f"{matched_sku} ({sku_meta['gpu_type']}) costs ${monthly_cost:,.0f}/mo on AWS. "
                        f"Equivalent on {best_cloud}: ${alt_monthly:,.0f}/mo — save ${savings:,.0f}/mo ({savings_pct}%)."
                    ),
                })
                insights["total_potential_savings"] = round(
                    float(insights["total_potential_savings"]) + savings, 2
                )

        # ── Ghost GPU detection ($300+/mo sustained cost) ─────────────────────
        if monthly_cost >= 300:
            ghost_entry = {
                "resource_id": resource_id,
                "sku": matched_sku,
                "gpu_type": sku_meta["gpu_type"],
                "cost": monthly_cost,
                "hours_assumed_running": _HOURS_PER_MONTH,
                "annual_burn": round(monthly_cost * 12, 0),
                "message": (
                    f"High sustained GPU cost detected: ${monthly_cost:,.0f}/mo. "
                    "Validate whether a training job is actively running. "
                    "If idle, terminate immediately to stop burning $"
                    f"{round(monthly_cost * 12):,}/year."
                ),
                "fix_command": (
                    f"# Find and terminate instance (replace INSTANCE_ID):\n"
                    f"aws ec2 terminate-instances --instance-ids INSTANCE_ID --region us-east-1"
                ),
            }
            insights["ghost_gpus"].append(ghost_entry)
            annual_waste += monthly_cost * 12

        # ── MIG candidate detection ───────────────────────────────────────────
        if sku_meta.get("supports_mig"):
            mig_slices = sku_meta.get("mig_slices", 7)
            insights["mig_candidates"].append({
                "resource_id": resource_id,
                "sku": matched_sku,
                "gpu_type": sku_meta["gpu_type"],
                "gpu_count": sku_meta.get("gpu_count", 8),
                "cost": monthly_cost,
                "mig_slices_possible": mig_slices,
                "advice": (
                    f"This {matched_sku} supports NVIDIA MIG (Multi-Instance GPU). "
                    f"Each GPU can be partitioned into up to 7 logical slices, giving you "
                    f"{mig_slices} total MIG instances for {mig_slices}× utilization at the same cost. "
                    "Enable MIG partitioning if multiple smaller jobs share this host."
                ),
                "enable_command": (
                    "# Enable MIG mode on all GPUs (run inside the instance as root):\n"
                    "sudo nvidia-smi -i 0 -mig 1\n"
                    "sudo nvidia-smi mig -cgi 9,9,9,9,9,9,9 -C\n"
                    "# Verify:\n"
                    "nvidia-smi mig -lgi"
                ),
            })

    insights["annual_waste_if_unresolved"] = round(annual_waste, 2)
    # Sort Ghost GPUs by cost descending
    insights["ghost_gpus"].sort(key=lambda x: x["cost"], reverse=True)
    # Sort arbitrage by savings descending
    insights["arbitrage_opportunities"].sort(key=lambda x: x["savings"], reverse=True)

    return insights
