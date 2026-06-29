"""
GPU Intelligence Tools — ADK tool functions for the GPU Intelligence Agent.
Provides scanning, workload classification, optimization recommendations, and arbitrage checks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def gpu_scan_resources(user_id: str = "") -> dict:
    """
    Scan all GPU instances across AWS, Azure, and GCP from the database.
    Returns a summary of all GPU resources with their current status and metrics.
    """
    import asyncio
    from ...db.mongo_client import get_db_client
    from ...core.gpu_service import GpuService

    async def _scan():
        db = get_db_client()
        resources = await db.get_resources(user_id)
        service = GpuService()
        return service.get_gpu_summary(resources)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _scan()).result()
        else:
            result = asyncio.run(_scan())
        return result
    except Exception as e:
        logger.error(f"GPU scan failed: {e}")
        return {"error": str(e), "gpu_resources": [], "ghost_gpus": [], "mig_candidates": [], "arbitrage": []}


def gpu_classify_workload(resource_id: str, metrics_history: list | None = None) -> dict:
    """
    Classify GPU workload type based on utilization patterns.
    Types: training, inference, rendering, idle, burst.
    """
    if not metrics_history:
        return {
            "resource_id": resource_id,
            "workload_type": "unknown",
            "confidence": 0.0,
            "reason": "No metrics history available for classification.",
        }

    sm_values = [m.get("sm_pct", 0) for m in metrics_history if m.get("sm_pct") is not None]
    mem_values = [m.get("mem_pct", 0) for m in metrics_history if m.get("mem_pct") is not None]

    if not sm_values:
        return {
            "resource_id": resource_id,
            "workload_type": "unknown",
            "confidence": 0.0,
            "reason": "No SM occupancy data in metrics history.",
        }

    avg_sm = sum(sm_values) / len(sm_values)
    max_sm = max(sm_values)
    min_sm = min(sm_values)
    avg_mem = sum(mem_values) / len(mem_values) if mem_values else 0
    variance = sum((x - avg_sm) ** 2 for x in sm_values) / len(sm_values)
    std_dev = variance ** 0.5

    # Classification rules
    if avg_sm < 10 and avg_mem < 20:
        workload_type = "idle"
        confidence = 0.95 if len(sm_values) >= 7 else 0.70
        reason = f"Avg SM {avg_sm:.1f}%, Avg Memory {avg_mem:.1f}% — consistently underutilized."
    elif avg_sm > 70 and avg_mem > 60 and std_dev < 20:
        workload_type = "training"
        confidence = 0.85
        reason = f"High sustained SM ({avg_sm:.1f}%) with high memory ({avg_mem:.1f}%) and low variance."
    elif 20 <= avg_sm <= 60 and std_dev > 15:
        workload_type = "inference"
        confidence = 0.75
        reason = f"Moderate SM ({avg_sm:.1f}%) with high variance (std={std_dev:.1f}) — request-driven pattern."
    elif avg_sm > 60 and avg_mem > 70 and std_dev > 20:
        workload_type = "rendering"
        confidence = 0.65
        reason = f"High SM + memory with periodic bursts (std={std_dev:.1f})."
    elif max_sm > 70 and avg_sm < 30:
        workload_type = "burst"
        confidence = 0.70
        reason = f"Low average ({avg_sm:.1f}%) but high peaks ({max_sm:.1f}%) — batch job pattern."
    else:
        workload_type = "mixed"
        confidence = 0.50
        reason = f"SM avg={avg_sm:.1f}%, mem avg={avg_mem:.1f}%, std={std_dev:.1f} — no clear pattern."

    return {
        "resource_id": resource_id,
        "workload_type": workload_type,
        "confidence": confidence,
        "reason": reason,
        "metrics_summary": {
            "avg_sm_pct": round(avg_sm, 2),
            "max_sm_pct": round(max_sm, 2),
            "min_sm_pct": round(min_sm, 2),
            "avg_mem_pct": round(avg_mem, 2),
            "std_dev_sm": round(std_dev, 2),
            "sample_count": len(sm_values),
        },
    }


def gpu_recommend_optimization(
    resource_id: str,
    workload_type: str,
    utilization: dict | None = None,
) -> dict:
    """
    Generate optimization recommendation for a specific GPU instance.
    Based on workload type and utilization metrics.
    """
    utilization = utilization or {}
    avg_sm = utilization.get("avg_sm_pct", 0)
    avg_mem = utilization.get("avg_mem_pct", 0)

    recommendations = []

    if workload_type == "idle":
        recommendations.append({
            "action": "terminate_or_hibernate",
            "priority": "critical",
            "description": "GPU is idle — terminate to stop all charges or hibernate if workload will resume.",
            "estimated_savings_pct": 100,
        })
    elif workload_type == "training":
        if avg_sm < 50:
            recommendations.append({
                "action": "rightsize",
                "priority": "high",
                "description": "Training workload underutilizing GPU. Consider a smaller instance or increase batch size.",
                "estimated_savings_pct": 30,
            })
        recommendations.append({
            "action": "use_spot_instances",
            "priority": "medium",
            "description": "Training is fault-tolerant with checkpointing. Switch to spot/preemptible for 60-90% savings.",
            "estimated_savings_pct": 70,
        })
        recommendations.append({
            "action": "schedule_based",
            "priority": "medium",
            "description": "If training runs on a schedule, auto-stop the instance between runs.",
            "estimated_savings_pct": 40,
        })
    elif workload_type == "inference":
        recommendations.append({
            "action": "autoscale",
            "priority": "high",
            "description": "Inference workload is bursty. Use GPU autoscaling (Kubernetes GPU pools or SageMaker auto-scaling).",
            "estimated_savings_pct": 40,
        })
        if avg_sm < 30:
            recommendations.append({
                "action": "rightsize_down",
                "priority": "medium",
                "description": "Inference load is light — consider T4/L4 instead of A100/H100.",
                "estimated_savings_pct": 60,
            })
    elif workload_type == "burst":
        recommendations.append({
            "action": "schedule_hibernate",
            "priority": "high",
            "description": "Batch workload with long idle gaps. Hibernate between jobs to eliminate idle cost.",
            "estimated_savings_pct": 50,
        })
        recommendations.append({
            "action": "use_spot_instances",
            "priority": "medium",
            "description": "Batch jobs tolerate interruptions — spot instances save 60-90%.",
            "estimated_savings_pct": 70,
        })
    elif workload_type == "rendering":
        recommendations.append({
            "action": "schedule_scaling",
            "priority": "medium",
            "description": "Rendering follows predictable patterns. Scale down to zero during off-peak.",
            "estimated_savings_pct": 35,
        })

    # Universal MIG recommendation for underutilized A100/H100
    if avg_sm < 30 and workload_type != "idle":
        recommendations.append({
            "action": "enable_mig",
            "priority": "medium",
            "description": "Low SM occupancy on MIG-capable GPU. Partition via NVIDIA MIG to serve multiple workloads.",
            "estimated_savings_pct": 50,
        })

    return {
        "resource_id": resource_id,
        "workload_type": workload_type,
        "recommendations": recommendations,
        "recommendation_count": len(recommendations),
    }


def gpu_arbitrage_check(instance_type: str, provider: str, monthly_cost: float) -> dict:
    """
    Check cross-cloud arbitrage opportunities for a GPU workload.
    Compares current cloud cost against Lambda Labs, CoreWeave, JarvisLabs, RunPod.
    """
    from ...core.gpu_specs import get_spec, HOURS_PER_MONTH

    spec = get_spec(instance_type)
    if not spec:
        return {
            "instance_type": instance_type,
            "provider": provider,
            "alternatives_found": False,
            "reason": f"No spec data found for instance type '{instance_type}'.",
        }

    if monthly_cost <= 0:
        monthly_cost = spec.on_demand_hourly * HOURS_PER_MONTH

    alternatives = []
    for cloud_name, hr_rate in [
        ("Lambda Labs", spec.lambda_hr),
        ("CoreWeave", spec.coreweave_hr),
        ("JarvisLabs", spec.jarvis_hr),
        ("RunPod", spec.runpod_hr),
    ]:
        if hr_rate is None:
            continue
        alt_monthly = round(hr_rate * HOURS_PER_MONTH, 2)
        savings = round(monthly_cost - alt_monthly, 2)
        savings_pct = round((savings / monthly_cost) * 100, 1) if monthly_cost > 0 else 0
        if savings > 0:
            alternatives.append({
                "cloud": cloud_name,
                "monthly_cost": alt_monthly,
                "savings": savings,
                "savings_pct": savings_pct,
            })

    alternatives.sort(key=lambda x: x["savings"], reverse=True)

    return {
        "instance_type": instance_type,
        "provider": provider,
        "current_monthly_cost": monthly_cost,
        "gpu_model": spec.gpu_model,
        "alternatives_found": len(alternatives) > 0,
        "alternatives": alternatives,
        "best_alternative": alternatives[0] if alternatives else None,
    }


def gpu_get_metrics_history(resource_id: str, days: int = 7) -> dict:
    """
    Retrieve GPU metrics history from MongoDB for pattern analysis.
    Returns daily averages for the specified number of days.
    """
    import asyncio
    from ...db.mongo_client import get_db_client
    from ...core.gpu_metrics_store import GpuMetricsStore

    async def _fetch():
        db = get_db_client()
        store = GpuMetricsStore(db)
        return await store.get_history(resource_id, days=days)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _fetch()).result()
        else:
            result = asyncio.run(_fetch())
        return {
            "resource_id": resource_id,
            "days_requested": days,
            "data_points": result,
            "has_data": len(result) > 0,
        }
    except Exception as e:
        logger.error(f"GPU metrics history fetch failed: {e}")
        return {"resource_id": resource_id, "days_requested": days, "data_points": [], "has_data": False}
