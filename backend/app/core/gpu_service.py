"""
GPU Intelligence Service — aggregates GPU data from scanned resources.
Provides ghost GPU detection, MIG advice, and specialized cloud arbitrage
for live-scan data (not bill uploads).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# GPU instance type → spec + specialized cloud pricing
# ─────────────────────────────────────────────────────────────────────────────
_GPU_INSTANCE_SPECS: dict[str, dict[str, Any]] = {
    # P3 – V100
    "p3.2xlarge":   {"gpu": "1× V100 16GB",  "gpu_count": 1,  "supports_mig": False, "aws_hr": 3.06,   "lambda_hr": 1.40,  "coreweave_hr": 1.10,  "jarvis_hr": 1.25,  "runpod_hr": 0.89},
    "p3.8xlarge":   {"gpu": "4× V100 16GB",  "gpu_count": 4,  "supports_mig": False, "aws_hr": 12.24,  "lambda_hr": 5.60,  "coreweave_hr": 4.40,  "jarvis_hr": 5.00,  "runpod_hr": 3.56},
    "p3.16xlarge":  {"gpu": "8× V100 16GB",  "gpu_count": 8,  "supports_mig": False, "aws_hr": 24.48,  "lambda_hr": 11.20, "coreweave_hr": 8.80,  "jarvis_hr": 10.00, "runpod_hr": 7.12},
    "p3dn.24xlarge":{"gpu": "8× V100 32GB",  "gpu_count": 8,  "supports_mig": False, "aws_hr": 31.21,  "lambda_hr": 14.40, "coreweave_hr": 11.20, "jarvis_hr": 12.80, "runpod_hr": 9.60},
    # P4 – A100
    "p4d.24xlarge":  {"gpu": "8× A100 40GB",  "gpu_count": 8,  "supports_mig": True,  "mig_slices": 56, "aws_hr": 32.77,  "lambda_hr": 20.32, "coreweave_hr": 17.60, "jarvis_hr": 19.20, "runpod_hr": 14.24},
    "p4de.24xlarge": {"gpu": "8× A100 80GB",  "gpu_count": 8,  "supports_mig": True,  "mig_slices": 56, "aws_hr": 40.96,  "lambda_hr": 25.60, "coreweave_hr": 22.40, "jarvis_hr": 24.00, "runpod_hr": 17.92},
    # P5 – H100
    "p5.48xlarge":   {"gpu": "8× H100 80GB",  "gpu_count": 8,  "supports_mig": True,  "mig_slices": 56, "aws_hr": 98.32,  "lambda_hr": 56.96, "coreweave_hr": 49.60, "jarvis_hr": 54.40, "runpod_hr": 41.60},
    # G4 – T4
    "g4dn.xlarge":   {"gpu": "1× T4 16GB",    "gpu_count": 1,  "supports_mig": False, "aws_hr": 0.526,  "lambda_hr": 0.35,  "coreweave_hr": 0.29,  "jarvis_hr": 0.32,  "runpod_hr": 0.22},
    "g4dn.2xlarge":  {"gpu": "1× T4 16GB",    "gpu_count": 1,  "supports_mig": False, "aws_hr": 0.752,  "lambda_hr": 0.45,  "coreweave_hr": 0.38,  "jarvis_hr": 0.42,  "runpod_hr": 0.28},
    "g4dn.4xlarge":  {"gpu": "1× T4 16GB",    "gpu_count": 1,  "supports_mig": False, "aws_hr": 1.204,  "lambda_hr": 0.72,  "coreweave_hr": 0.61,  "jarvis_hr": 0.68,  "runpod_hr": 0.46},
    # G5 – A10G
    "g5.2xlarge":    {"gpu": "1× A10G 24GB",  "gpu_count": 1,  "supports_mig": False, "aws_hr": 1.212,  "lambda_hr": 0.76,  "coreweave_hr": 0.65,  "jarvis_hr": 0.72,  "runpod_hr": 0.51},
    "g5.4xlarge":    {"gpu": "1× A10G 24GB",  "gpu_count": 1,  "supports_mig": False, "aws_hr": 1.624,  "lambda_hr": 0.98,  "coreweave_hr": 0.84,  "jarvis_hr": 0.93,  "runpod_hr": 0.66},
    # Trainium / Inferentia
    "trn1.32xlarge": {"gpu": "16× AWS Trainium","gpu_count": 16, "supports_mig": False, "aws_hr": 21.50,  "lambda_hr": None,  "coreweave_hr": 15.20, "jarvis_hr": None,  "runpod_hr": 12.80},
    "inf2.xlarge":   {"gpu": "1× AWS Inferentia2","gpu_count":1,"supports_mig": False, "aws_hr": 0.758,  "lambda_hr": None,  "coreweave_hr": 0.29,  "jarvis_hr": 0.32,  "runpod_hr": 0.22},
}

_HOURS_PER_MONTH = 730
_GPU_PREFIXES = ("p3", "p4", "p5", "g3", "g4", "g5", "trn1", "inf1", "inf2", "dl1")


def _is_gpu_resource(resource: dict[str, Any]) -> bool:
    """True if resource is a GPU instance based on metadata or service type."""
    meta = resource.get("metadata") or {}
    if meta.get("is_gpu_instance"):
        return True
    instance_type = str(meta.get("instance_type") or "").lower()
    return any(instance_type.startswith(p) for p in _GPU_PREFIXES)


def _get_spec(resource: dict[str, Any]) -> dict[str, Any] | None:
    meta = resource.get("metadata") or {}
    instance_type = str(meta.get("instance_type") or "").lower().strip()
    return _GPU_INSTANCE_SPECS.get(instance_type)


def _cheapest_alternative(spec: dict[str, Any]) -> tuple[str, float] | tuple[None, None]:
    candidates = {
        "Lambda Labs": spec.get("lambda_hr"),
        "CoreWeave":   spec.get("coreweave_hr"),
        "JarvisLabs":  spec.get("jarvis_hr"),
        "RunPod":      spec.get("runpod_hr"),
    }
    valid = {k: v for k, v in candidates.items() if v is not None}
    if not valid:
        return None, None
    best = min(valid, key=valid.__getitem__)
    return best, valid[best]


def _all_cloud_monthly(spec: dict[str, Any], current_monthly: float) -> dict[str, float | None]:
    return {
        "AWS (On-Demand)": current_monthly,
        "Lambda Labs": round(spec["lambda_hr"] * _HOURS_PER_MONTH, 2) if spec.get("lambda_hr") else None,
        "CoreWeave":   round(spec["coreweave_hr"] * _HOURS_PER_MONTH, 2) if spec.get("coreweave_hr") else None,
        "JarvisLabs":  round(spec["jarvis_hr"] * _HOURS_PER_MONTH, 2) if spec.get("jarvis_hr") else None,
        "RunPod":      round(spec["runpod_hr"] * _HOURS_PER_MONTH, 2) if spec.get("runpod_hr") else None,
    }


class GpuService:
    """
    First-class GPU Intelligence service for live-scanned resources.
    Works on resources already saved to MongoDB (no extra cloud API calls).
    """

    def get_gpu_summary(
        self,
        resources: list[dict[str, Any]],
        integration_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Full GPU intelligence report from a list of scanned resources.

        Args:
            resources: All resources from DB for a user/integration
            integration_id: Optional filter

        Returns:
            Structured GPU intelligence report
        """
        gpu_resources = [r for r in resources if _is_gpu_resource(r)]

        if not gpu_resources:
            return {
                "gpu_resources": [],
                "ghost_gpus": [],
                "mig_candidates": [],
                "arbitrage": [],
                "sagemak er_waste": [],
                "total_gpu_spend": 0.0,
                "total_gpu_waste": 0.0,
                "total_savings_available": 0.0,
                "annual_waste_if_unresolved": 0.0,
                "ai_narrative": "No GPU instances detected in this integration.",
            }

        ghost_gpus = self.get_ghost_gpus(gpu_resources)
        mig_candidates = self.get_mig_candidates(gpu_resources)
        arbitrage = self.get_specialized_arbitrage(gpu_resources)
        sagemaker_waste = self.get_sagemaker_waste(resources)

        total_spend = round(sum(float(r.get("cost") or 0) for r in gpu_resources), 2)
        ghost_cost = round(sum(float(g["monthly_cost"]) for g in ghost_gpus), 2)
        total_savings = round(sum(float(a.get("savings") or 0) for a in arbitrage), 2)
        annual_waste = round(ghost_cost * 12, 2)

        # Deterministic narrative (Gemini enrichment can be layered on top)
        narrative = self._build_narrative(
            gpu_count=len(gpu_resources),
            ghost_count=len(ghost_gpus),
            mig_count=len(mig_candidates),
            total_spend=total_spend,
            total_savings=total_savings,
            annual_waste=annual_waste,
        )

        # Enrich GPU resource list with spec info
        enriched = []
        for r in gpu_resources:
            spec = _get_spec(r)
            meta = r.get("metadata") or {}
            enriched.append({
                "id": r.get("id") or r.get("cloud_resource_id"),
                "name": r.get("resource_name", "Unknown"),
                "instance_type": str(meta.get("instance_type") or "").upper(),
                "gpu_type": spec["gpu"] if spec else str(meta.get("gpu_type") or "GPU Instance"),
                "gpu_count": spec["gpu_count"] if spec else meta.get("gpu_count", 1),
                "monthly_cost": float(r.get("cost") or 0),
                "status": r.get("status", "Active"),
                "waste_type": r.get("waste_type"),
                "region": r.get("region", ""),
                "gpu_memory_utilization_pct": meta.get("gpu_memory_utilization_pct", None),
                "gpu_sm_occupancy_pct": meta.get("gpu_sm_occupancy_pct", None),
                "gpu_optimization_insight": meta.get("gpu_optimization_insight", ""),
                "is_ghost": any(g["resource_id"] == (r.get("id") or r.get("cloud_resource_id")) for g in ghost_gpus),
                "is_mig_candidate": any(m["resource_id"] == (r.get("id") or r.get("cloud_resource_id")) for m in mig_candidates),
            })

        return {
            "gpu_resources": enriched,
            "ghost_gpus": ghost_gpus,
            "mig_candidates": mig_candidates,
            "arbitrage": arbitrage,
            "sagemaker_waste": sagemaker_waste,
            "total_gpu_spend": total_spend,
            "total_gpu_waste": ghost_cost,
            "total_savings_available": total_savings,
            "annual_waste_if_unresolved": annual_waste,
            "ai_narrative": narrative,
        }

    def get_ghost_gpus(self, gpu_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Identify GPU instances that are stopped, zombie, or have low utilization."""
        ghosts = []
        for r in gpu_resources:
            resource_id = r.get("id") or r.get("cloud_resource_id") or ""
            meta = r.get("metadata") or {}
            monthly_cost = float(r.get("cost") or 0)
            status = str(r.get("status") or "").lower()
            sm_occ = meta.get("gpu_sm_occupancy_pct")
            waste_type = r.get("waste_type") or ""

            is_ghost = (
                status in ("zombie", "stopped", "idle", "waste")
                or waste_type in ("zombie_vm", "stopped_vm", "deallocated_vm")
                or (sm_occ is not None and float(sm_occ) < 15 and monthly_cost > 100)
                or (monthly_cost > 500 and status == "active")  # High-cost with no waste reason = suspect
            )

            if is_ghost:
                spec = _get_spec(r)
                ghosts.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": str(meta.get("instance_type") or "").upper(),
                    "gpu_type": spec["gpu"] if spec else "GPU Instance",
                    "monthly_cost": monthly_cost,
                    "annual_cost": round(monthly_cost * 12, 2),
                    "status": r.get("status", "Unknown"),
                    "gpu_sm_occupancy_pct": sm_occ,
                    "ghost_reason": (
                        f"Instance status is {r.get('status')}. "
                        if status in ("zombie", "stopped", "idle", "waste")
                        else f"GPU SM occupancy is {sm_occ}% — extremely low for a running GPU host."
                        if sm_occ is not None
                        else "High sustained GPU cost with no verified active workload."
                    ),
                    "fix_command": (
                        f"# Stop and terminate this instance (replace INSTANCE_ID):\n"
                        f"aws ec2 stop-instances --instance-ids INSTANCE_ID --region {r.get('region', 'us-east-1')}\n"
                        f"# Or terminate permanently:\n"
                        f"aws ec2 terminate-instances --instance-ids INSTANCE_ID --region {r.get('region', 'us-east-1')}"
                    ),
                })

        ghosts.sort(key=lambda x: x["monthly_cost"], reverse=True)
        return ghosts

    def get_mig_candidates(self, gpu_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return A100/H100 instances that would benefit from MIG partitioning."""
        candidates = []
        for r in gpu_resources:
            spec = _get_spec(r)
            if not spec or not spec.get("supports_mig"):
                continue

            resource_id = r.get("id") or r.get("cloud_resource_id") or ""
            meta = r.get("metadata") or {}
            sm_occ = meta.get("gpu_sm_occupancy_pct")
            monthly_cost = float(r.get("cost") or 0)

            # Flag as MIG candidate if SM occupancy < 30% or not measured (conservative)
            if sm_occ is None or float(sm_occ) < 30:
                mig_slices = spec.get("mig_slices", 7)
                candidates.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": str(meta.get("instance_type") or "").upper(),
                    "gpu_type": spec["gpu"],
                    "gpu_count": spec["gpu_count"],
                    "monthly_cost": monthly_cost,
                    "gpu_sm_occupancy_pct": sm_occ,
                    "mig_slices_possible": mig_slices,
                    "advice": (
                        f"This {str(meta.get('instance_type','GPU')).upper()} has {spec['gpu_count']} GPUs "
                        f"each supporting NVIDIA MIG. You can partition each GPU into up to 7 slices, "
                        f"giving {mig_slices} total logical GPU instances at the same ${monthly_cost:,.0f}/mo cost. "
                        f"Ideal if multiple smaller training or inference jobs share this host."
                    ),
                    "enable_command": (
                        "# SSH into the instance and run as root:\n"
                        f"for i in $(seq 0 {spec['gpu_count'] - 1}); do\n"
                        "  sudo nvidia-smi -i $i -mig 1\n"
                        "done\n"
                        "sudo nvidia-smi mig -cgi 9,9,9,9,9,9,9 -C\n"
                        "# Verify:\n"
                        "nvidia-smi mig -lgi"
                    ),
                })

        return candidates

    def get_specialized_arbitrage(self, gpu_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compare each GPU instance against Lambda Labs, CoreWeave, JarvisLabs, RunPod."""
        results = []
        for r in gpu_resources:
            spec = _get_spec(r)
            if not spec:
                continue

            resource_id = r.get("id") or r.get("cloud_resource_id") or ""
            meta = r.get("metadata") or {}
            monthly_cost = float(r.get("cost") or 0)
            if monthly_cost <= 0:
                monthly_cost = spec["aws_hr"] * _HOURS_PER_MONTH

            best_cloud, best_hr = _cheapest_alternative(spec)
            all_costs = _all_cloud_monthly(spec, monthly_cost)

            if best_cloud and best_hr:
                alt_monthly = round(best_hr * _HOURS_PER_MONTH, 2)
                savings = round(monthly_cost - alt_monthly, 2)
                savings_pct = round((savings / monthly_cost) * 100, 1) if monthly_cost > 0 else 0

                results.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": str(meta.get("instance_type") or "").upper(),
                    "gpu_type": spec["gpu"],
                    "current_cloud": "AWS",
                    "current_monthly_cost": monthly_cost,
                    "best_alternative_cloud": best_cloud,
                    "best_alternative_monthly_cost": alt_monthly,
                    "savings": savings,
                    "savings_pct": savings_pct,
                    "all_cloud_costs": all_costs,
                    "migration_complexity": (
                        "Low" if "g4" in str(meta.get("instance_type", "")).lower()
                        else "Medium" if "g5" in str(meta.get("instance_type", "")).lower()
                        else "High"  # P-series require workload testing
                    ),
                })

        results.sort(key=lambda x: x.get("savings", 0), reverse=True)
        return results

    def get_sagemaker_waste(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Identify SageMaker notebooks and endpoints that are idle."""
        waste = []
        for r in resources:
            svc = str(r.get("service_type") or "").lower()
            if "sagemaker" not in svc:
                continue
            status = str(r.get("status") or "").lower()
            waste_type = str(r.get("waste_type") or "").lower()
            if status in ("zombie", "idle", "waste") or waste_type:
                monthly_cost = float(r.get("cost") or 0)
                waste.append({
                    "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                    "name": r.get("resource_name", "Unknown"),
                    "service_type": r.get("service_type", "SageMaker"),
                    "monthly_cost": monthly_cost,
                    "status": r.get("status"),
                    "waste_reason": r.get("waste_reason") or "Idle SageMaker resource",
                })
        return waste

    def _build_narrative(
        self,
        gpu_count: int,
        ghost_count: int,
        mig_count: int,
        total_spend: float,
        total_savings: float,
        annual_waste: float,
    ) -> str:
        parts = [
            f"You have {gpu_count} GPU instance{'s' if gpu_count != 1 else ''} "
            f"totaling ${total_spend:,.0f}/month."
        ]
        if ghost_count:
            parts.append(
                f"{ghost_count} instance{'s' if ghost_count != 1 else ''} appear{'s' if ghost_count == 1 else ''} "
                f"idle or unverified, burning ${annual_waste:,.0f}/year if left running."
            )
        if mig_count:
            parts.append(
                f"{mig_count} A100/H100 host{'s' if mig_count != 1 else ''} support{'s' if mig_count == 1 else ''} "
                "NVIDIA MIG partitioning for up to 7× utilization at the same cost."
            )
        if total_savings > 0:
            parts.append(
                f"Moving GPU workloads to the cheapest specialized cloud saves ${total_savings:,.0f}/month "
                f"(${total_savings * 12:,.0f}/year)."
            )
        return " ".join(parts)
