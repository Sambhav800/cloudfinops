"""
GPU Scheduling Advisor — recommends optimal scheduling strategies for GPU workloads.
Spot/preemptible for training, reserved for inference, time-based scaling.
"""

from __future__ import annotations

import logging
from typing import Any

from .gpu_specs import get_spec, GpuSkuSpec

logger = logging.getLogger(__name__)


class GpuSchedulingAdvisor:
    """Generates scheduling recommendations based on workload type and utilization patterns."""

    async def recommend_schedule(
        self,
        resource_id: str,
        workload_type: str,
        metrics: list[dict[str, Any]] | None = None,
        resource_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate scheduling recommendation for a GPU resource.

        Returns:
            Structured recommendation with strategy, estimated savings, and implementation steps.
        """
        resource_meta = resource_meta or {}
        metrics = metrics or []
        provider = str(resource_meta.get("provider", "aws")).lower()
        instance_type = str(resource_meta.get("instance_type") or resource_meta.get("vm_size") or "")
        monthly_cost = float(resource_meta.get("monthly_cost") or resource_meta.get("cost") or 0)

        spec = get_spec(instance_type) if instance_type else None
        recommendations = []

        if workload_type == "training":
            recommendations.extend(self._training_recommendations(provider, monthly_cost, spec, metrics))
        elif workload_type == "inference":
            recommendations.extend(self._inference_recommendations(provider, monthly_cost, spec, metrics))
        elif workload_type == "burst":
            recommendations.extend(self._burst_recommendations(provider, monthly_cost, spec, metrics))
        elif workload_type == "idle":
            recommendations.extend(self._idle_recommendations(provider, monthly_cost))
        elif workload_type == "rendering":
            recommendations.extend(self._rendering_recommendations(provider, monthly_cost, metrics))
        else:
            recommendations.append({
                "strategy": "monitor",
                "priority": "low",
                "description": "Workload pattern unclear. Continue monitoring for 7 more days before optimizing.",
                "estimated_savings_pct": 0,
                "implementation": "No action needed yet.",
            })

        return {
            "resource_id": resource_id,
            "workload_type": workload_type,
            "provider": provider,
            "instance_type": instance_type,
            "current_monthly_cost": monthly_cost,
            "recommendations": recommendations,
            "total_potential_savings_pct": max((r.get("estimated_savings_pct", 0) for r in recommendations), default=0),
        }

    def _training_recommendations(
        self, provider: str, monthly_cost: float, spec: GpuSkuSpec | None, metrics: list
    ) -> list[dict]:
        recs = []

        # Spot/Preemptible recommendation
        spot_savings = 70
        if provider == "aws":
            impl = (
                "1. Add checkpointing every 30 minutes to S3\n"
                "2. Use EC2 Spot Fleet with capacity-optimized allocation\n"
                "3. Set up Spot interruption handler to save state\n"
                "4. Use `aws ec2 request-spot-instances` or Spot Fleet API"
            )
        elif provider == "gcp":
            impl = (
                "1. Enable periodic checkpointing to GCS\n"
                "2. Use Preemptible VMs or Spot VMs in instance template\n"
                "3. Set up shutdown script for graceful checkpoint\n"
                "4. Use `gcloud compute instances create --provisioning-model=SPOT`"
            )
        else:
            impl = (
                "1. Use Azure Spot VMs with eviction policy 'Deallocate'\n"
                "2. Enable checkpointing to Azure Blob Storage\n"
                "3. Set max price to -1 (pay up to on-demand)\n"
                "4. Use `az vm create --priority Spot --eviction-policy Deallocate`"
            )

        recs.append({
            "strategy": "spot_instances",
            "priority": "high",
            "description": f"Training workloads are fault-tolerant with checkpointing. Spot/preemptible instances save ~{spot_savings}%.",
            "estimated_savings_pct": spot_savings,
            "estimated_monthly_savings": round(monthly_cost * spot_savings / 100, 2),
            "implementation": impl,
            "prerequisites": ["Checkpoint-capable training framework", "Distributed storage for state"],
        })

        # Schedule-based recommendation if metrics show downtime patterns
        if metrics:
            sm_values = [m.get("sm_pct", 0) for m in metrics if m.get("sm_pct") is not None]
            if sm_values and min(sm_values) < 5:
                recs.append({
                    "strategy": "scheduled_start_stop",
                    "priority": "medium",
                    "description": "Training shows idle windows. Schedule auto-stop during detected idle periods.",
                    "estimated_savings_pct": 30,
                    "estimated_monthly_savings": round(monthly_cost * 0.30, 2),
                    "implementation": f"Use {provider.upper()} Instance Scheduler or cron-based Lambda/Cloud Function to stop during idle windows.",
                })

        return recs

    def _inference_recommendations(
        self, provider: str, monthly_cost: float, spec: GpuSkuSpec | None, metrics: list
    ) -> list[dict]:
        recs = []

        recs.append({
            "strategy": "autoscaling",
            "priority": "high",
            "description": "Inference workloads benefit from horizontal scaling. Scale to zero during quiet periods.",
            "estimated_savings_pct": 40,
            "estimated_monthly_savings": round(monthly_cost * 0.40, 2),
            "implementation": (
                "Use Kubernetes HPA with GPU metrics, or managed inference "
                "(SageMaker Endpoints / Vertex AI Endpoints / Azure ML Online Endpoints) "
                "with min-replicas=0 and scale-from-zero support."
            ),
        })

        # Rightsizing for inference
        if spec and spec.gpu_memory_gb > 24:
            recs.append({
                "strategy": "rightsize_gpu",
                "priority": "medium",
                "description": f"Inference on {spec.gpu_model} ({spec.gpu_memory_gb}GB) may be oversized. Consider T4/L4 for lighter models.",
                "estimated_savings_pct": 60,
                "estimated_monthly_savings": round(monthly_cost * 0.60, 2),
                "implementation": "Profile model memory usage. If <16GB VRAM needed, migrate to T4 (G4dn) or L4 (G2).",
            })

        # Reserved instances for steady-state inference
        recs.append({
            "strategy": "reserved_instances",
            "priority": "low",
            "description": "If inference load is predictable and steady, commit to 1-year reserved instances for ~30% savings.",
            "estimated_savings_pct": 30,
            "estimated_monthly_savings": round(monthly_cost * 0.30, 2),
            "implementation": f"Purchase {provider.upper()} Reserved Instance (1yr, no upfront) for baseline capacity.",
        })

        return recs

    def _burst_recommendations(
        self, provider: str, monthly_cost: float, spec: GpuSkuSpec | None, metrics: list
    ) -> list[dict]:
        return [
            {
                "strategy": "event_driven_scaling",
                "priority": "high",
                "description": "Batch workload with long idle gaps. Use event-driven GPU provisioning — spin up on job submit, terminate on completion.",
                "estimated_savings_pct": 60,
                "estimated_monthly_savings": round(monthly_cost * 0.60, 2),
                "implementation": (
                    "Integrate with job scheduler (Airflow, Prefect, Step Functions). "
                    "Trigger GPU instance creation on job start, auto-terminate on exit code 0."
                ),
            },
            {
                "strategy": "spot_instances",
                "priority": "medium",
                "description": "Batch jobs tolerate interruption. Use spot/preemptible for the burst windows.",
                "estimated_savings_pct": 70,
                "estimated_monthly_savings": round(monthly_cost * 0.70, 2),
                "implementation": "Combine with event-driven scaling above: request spot instances for each job.",
            },
        ]

    def _idle_recommendations(self, provider: str, monthly_cost: float) -> list[dict]:
        return [
            {
                "strategy": "terminate",
                "priority": "critical",
                "description": "GPU is completely idle. Terminate immediately to stop all charges.",
                "estimated_savings_pct": 100,
                "estimated_monthly_savings": monthly_cost,
                "implementation": (
                    "Verify no dependent services, then terminate. "
                    "If workload may resume, snapshot the disk and terminate the instance."
                ),
            },
        ]

    def _rendering_recommendations(
        self, provider: str, monthly_cost: float, metrics: list
    ) -> list[dict]:
        return [
            {
                "strategy": "scheduled_scaling",
                "priority": "medium",
                "description": "Rendering follows predictable cycles. Scale GPU pool based on render queue depth.",
                "estimated_savings_pct": 35,
                "estimated_monthly_savings": round(monthly_cost * 0.35, 2),
                "implementation": (
                    "Monitor render queue (Deadline, Tractor). Auto-scale GPU node pool "
                    "between min=0 and max=N based on pending frames."
                ),
            },
            {
                "strategy": "spot_rendering",
                "priority": "medium",
                "description": "Rendering frames are independent. Use spot instances for non-time-critical renders.",
                "estimated_savings_pct": 65,
                "estimated_monthly_savings": round(monthly_cost * 0.65, 2),
                "implementation": "Route non-priority renders to spot GPU pool. Retry interrupted frames automatically.",
            },
        ]
