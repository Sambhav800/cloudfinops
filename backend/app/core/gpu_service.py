"""
GPU Intelligence Service — aggregates GPU data from scanned resources.
Provides ghost GPU detection, MIG advice, and specialized cloud arbitrage
for live-scan data across AWS, Azure, and GCP.
"""

from __future__ import annotations

import logging
from typing import Any

from .gpu_specs import (
    get_spec,
    is_gpu_instance_type,
    GpuSkuSpec,
    HOURS_PER_MONTH,
    AWS_GPU_SPECS,
    AZURE_GPU_SPECS,
    GCP_GPU_SPECS,
)

logger = logging.getLogger(__name__)


def _is_gpu_resource(resource: dict[str, Any]) -> bool:
    """True if resource is a GPU instance based on metadata or service type."""
    meta = resource.get("metadata") or {}
    if meta.get("is_gpu_instance"):
        return True
    instance_type = str(meta.get("instance_type") or meta.get("vm_size") or "").lower()
    if not instance_type:
        return False
    provider = str(resource.get("provider") or "").lower()
    return is_gpu_instance_type(instance_type, provider=provider or None)


def _get_spec_for_resource(resource: dict[str, Any]) -> GpuSkuSpec | None:
    """Resolve the GPU spec for a resource, checking instance_type and vm_size."""
    meta = resource.get("metadata") or {}
    instance_type = str(meta.get("instance_type") or meta.get("vm_size") or "").lower().strip()
    if not instance_type:
        return None
    # Normalize Azure naming (Standard_NC6s_v3 → standard_nc6s_v3)
    normalized = instance_type.lower().replace(" ", "").replace("-", "_")
    # Try direct lookup first, then normalized form
    return get_spec(instance_type) or get_spec(normalized)


def _detect_provider(resource: dict[str, Any]) -> str:
    """Determine the cloud provider for a resource."""
    provider = str(resource.get("provider") or "").lower()
    if provider in ("aws", "azure", "gcp"):
        return provider
    svc = str(resource.get("service_type") or "").lower()
    if "azure" in svc or "virtual machine" in svc:
        return "azure"
    if "gcp" in svc or "google" in svc:
        return "gcp"
    return "aws"


def _cheapest_alternative(spec: GpuSkuSpec) -> tuple[str, float] | tuple[None, None]:
    """Find the cheapest specialized cloud alternative."""
    candidates = {
        "Lambda Labs": spec.lambda_hr,
        "CoreWeave": spec.coreweave_hr,
        "JarvisLabs": spec.jarvis_hr,
        "RunPod": spec.runpod_hr,
    }
    valid = {k: v for k, v in candidates.items() if v is not None}
    if not valid:
        return None, None
    best = min(valid, key=valid.__getitem__)
    return best, valid[best]


def _all_cloud_monthly(spec: GpuSkuSpec, current_monthly: float, current_cloud: str) -> dict[str, float | None]:
    """Build the full cost comparison across all clouds."""
    costs: dict[str, float | None] = {f"{current_cloud} (On-Demand)": current_monthly}
    if spec.lambda_hr is not None:
        costs["Lambda Labs"] = round(spec.lambda_hr * HOURS_PER_MONTH, 2)
    else:
        costs["Lambda Labs"] = None
    if spec.coreweave_hr is not None:
        costs["CoreWeave"] = round(spec.coreweave_hr * HOURS_PER_MONTH, 2)
    else:
        costs["CoreWeave"] = None
    if spec.jarvis_hr is not None:
        costs["JarvisLabs"] = round(spec.jarvis_hr * HOURS_PER_MONTH, 2)
    else:
        costs["JarvisLabs"] = None
    if spec.runpod_hr is not None:
        costs["RunPod"] = round(spec.runpod_hr * HOURS_PER_MONTH, 2)
    else:
        costs["RunPod"] = None
    return costs


def _build_fix_command(resource: dict[str, Any], provider: str) -> str:
    """Generate provider-specific CLI fix commands for ghost GPUs."""
    region = resource.get("region", "us-east-1")
    resource_name = resource.get("resource_name", "INSTANCE_ID")

    if provider == "azure":
        return (
            f"# Deallocate this GPU VM (stops billing):\n"
            f"az vm deallocate --name {resource_name} --resource-group RESOURCE_GROUP\n"
            f"# Or delete permanently:\n"
            f"az vm delete --name {resource_name} --resource-group RESOURCE_GROUP --yes"
        )
    elif provider == "gcp":
        zone = (resource.get("metadata") or {}).get("zone", region)
        project = (resource.get("metadata") or {}).get("project_id", "PROJECT_ID")
        return (
            f"# Stop this GPU instance:\n"
            f"gcloud compute instances stop {resource_name} --zone={zone} --project={project}\n"
            f"# Or delete permanently:\n"
            f"gcloud compute instances delete {resource_name} --zone={zone} --project={project} --quiet"
        )
    else:
        return (
            f"# Stop and terminate this instance (replace INSTANCE_ID):\n"
            f"aws ec2 stop-instances --instance-ids INSTANCE_ID --region {region}\n"
            f"# Or terminate permanently:\n"
            f"aws ec2 terminate-instances --instance-ids INSTANCE_ID --region {region}"
        )


class GpuService:
    """
    Multi-cloud GPU Intelligence service for live-scanned resources.
    Works on resources already saved to MongoDB (no extra cloud API calls).
    Supports AWS, Azure, and GCP GPU instance detection and analysis.
    """

    def get_gpu_summary(
        self,
        resources: list[dict[str, Any]],
        integration_id: str | None = None,
    ) -> dict[str, Any]:
        """Full GPU intelligence report from a list of scanned resources."""
        gpu_resources = [r for r in resources if _is_gpu_resource(r)]

        if not gpu_resources:
            return {
                "gpu_resources": [],
                "ghost_gpus": [],
                "mig_candidates": [],
                "arbitrage": [],
                "sagemaker_waste": [],
                "total_gpu_spend": 0.0,
                "total_gpu_waste": 0.0,
                "total_savings_available": 0.0,
                "annual_waste_if_unresolved": 0.0,
                "ai_narrative": "No GPU instances detected in this integration.",
                "providers_detected": [],
            }

        ghost_gpus = self.get_ghost_gpus(gpu_resources)
        mig_candidates = self.get_mig_candidates(gpu_resources)
        arbitrage = self.get_specialized_arbitrage(gpu_resources)
        sagemaker_waste = self.get_sagemaker_waste(resources)

        total_spend = round(sum(float(r.get("cost") or 0) for r in gpu_resources), 2)
        ghost_cost = round(sum(float(g["monthly_cost"]) for g in ghost_gpus), 2)
        total_savings = round(sum(float(a.get("savings") or 0) for a in arbitrage), 2)
        annual_waste = round(ghost_cost * 12, 2)

        providers = list(set(_detect_provider(r) for r in gpu_resources))

        narrative = self._build_narrative(
            gpu_count=len(gpu_resources),
            ghost_count=len(ghost_gpus),
            mig_count=len(mig_candidates),
            total_spend=total_spend,
            total_savings=total_savings,
            annual_waste=annual_waste,
            providers=providers,
        )

        enriched = []
        for r in gpu_resources:
            spec = _get_spec_for_resource(r)
            meta = r.get("metadata") or {}
            provider = _detect_provider(r)
            enriched.append({
                "id": r.get("id") or r.get("cloud_resource_id"),
                "name": r.get("resource_name", "Unknown"),
                "instance_type": str(meta.get("instance_type") or meta.get("vm_size") or "").upper(),
                "gpu_type": (
                    f"{spec.gpu_count}× {spec.gpu_model}" if spec
                    else str(meta.get("gpu_type") or "GPU Instance")
                ),
                "gpu_count": spec.gpu_count if spec else meta.get("gpu_count", 1),
                "monthly_cost": float(r.get("cost") or 0),
                "status": r.get("status", "Active"),
                "waste_type": r.get("waste_type"),
                "region": r.get("region", ""),
                "provider": provider,
                "gpu_memory_utilization_pct": meta.get("gpu_memory_utilization_pct"),
                "gpu_sm_occupancy_pct": meta.get("gpu_sm_occupancy_pct"),
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
            "providers_detected": providers,
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
            provider = _detect_provider(r)

            is_ghost = (
                status in ("zombie", "stopped", "idle", "waste")
                or waste_type in ("zombie_vm", "stopped_vm", "deallocated_vm")
                or (sm_occ is not None and float(sm_occ) < 15 and monthly_cost > 100)
                or (monthly_cost > 500 and status == "active")
            )

            if is_ghost:
                spec = _get_spec_for_resource(r)
                ghosts.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": str(meta.get("instance_type") or meta.get("vm_size") or "").upper(),
                    "gpu_type": f"{spec.gpu_count}× {spec.gpu_model}" if spec else str(meta.get("gpu_type") or "GPU Instance"),
                    "monthly_cost": monthly_cost,
                    "annual_cost": round(monthly_cost * 12, 2),
                    "status": r.get("status", "Unknown"),
                    "provider": provider,
                    "gpu_sm_occupancy_pct": sm_occ,
                    "ghost_reason": (
                        f"Instance status is {r.get('status')}. "
                        if status in ("zombie", "stopped", "idle", "waste")
                        else f"GPU SM occupancy is {sm_occ}% — extremely low for a running GPU host."
                        if sm_occ is not None
                        else "High sustained GPU cost with no verified active workload."
                    ),
                    "fix_command": _build_fix_command(r, provider),
                })

        ghosts.sort(key=lambda x: x["monthly_cost"], reverse=True)
        return ghosts

    def get_mig_candidates(self, gpu_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return A100/H100 instances that would benefit from MIG partitioning."""
        candidates = []
        for r in gpu_resources:
            spec = _get_spec_for_resource(r)
            if not spec or not spec.supports_mig:
                continue
            meta = r.get("metadata") or {}
            if not meta.get("supports_mig", spec.supports_mig):
                continue

            resource_id = r.get("id") or r.get("cloud_resource_id") or ""
            sm_occ = meta.get("gpu_sm_occupancy_pct")
            monthly_cost = float(r.get("cost") or 0)
            provider = _detect_provider(r)

            if sm_occ is None or float(sm_occ) < 30:
                mig_slices = spec.gpu_count * spec.mig_slices_per_gpu
                candidates.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": str(meta.get("instance_type") or meta.get("vm_size") or "").upper(),
                    "gpu_type": f"{spec.gpu_count}× {spec.gpu_model}",
                    "gpu_count": spec.gpu_count,
                    "monthly_cost": monthly_cost,
                    "provider": provider,
                    "gpu_sm_occupancy_pct": sm_occ,
                    "mig_slices_possible": mig_slices,
                    "advice": (
                        f"This instance has {spec.gpu_count} {spec.gpu_model} GPUs "
                        f"each supporting NVIDIA MIG. You can partition each GPU into up to "
                        f"{spec.mig_slices_per_gpu} slices, giving {mig_slices} total logical GPU "
                        f"instances at the same ${monthly_cost:,.0f}/mo cost. "
                        f"Ideal if multiple smaller training or inference jobs share this host."
                    ),
                    "enable_command": (
                        "# SSH into the instance and run as root:\n"
                        f"for i in $(seq 0 {spec.gpu_count - 1}); do\n"
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
            spec = _get_spec_for_resource(r)
            if not spec:
                continue
            if spec.lambda_hr is None and spec.coreweave_hr is None and spec.runpod_hr is None:
                continue

            resource_id = r.get("id") or r.get("cloud_resource_id") or ""
            meta = r.get("metadata") or {}
            monthly_cost = float(r.get("cost") or 0)
            provider = _detect_provider(r)
            current_cloud = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}.get(provider, "AWS")

            if monthly_cost <= 0:
                monthly_cost = spec.on_demand_hourly * HOURS_PER_MONTH

            best_cloud, best_hr = _cheapest_alternative(spec)
            all_costs = _all_cloud_monthly(spec, monthly_cost, current_cloud)

            if best_cloud and best_hr:
                alt_monthly = round(best_hr * HOURS_PER_MONTH, 2)
                savings = round(monthly_cost - alt_monthly, 2)
                savings_pct = round((savings / monthly_cost) * 100, 1) if monthly_cost > 0 else 0

                instance_type_lower = str(meta.get("instance_type") or meta.get("vm_size") or "").lower()
                results.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "instance_type": instance_type_lower.upper(),
                    "gpu_type": f"{spec.gpu_count}× {spec.gpu_model}",
                    "current_cloud": current_cloud,
                    "current_monthly_cost": monthly_cost,
                    "best_alternative_cloud": best_cloud,
                    "best_alternative_monthly_cost": alt_monthly,
                    "savings": savings,
                    "savings_pct": savings_pct,
                    "all_cloud_costs": all_costs,
                    "migration_complexity": self._assess_migration_complexity(spec, provider),
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

    def _assess_migration_complexity(self, spec: GpuSkuSpec, provider: str) -> str:
        """Determine migration complexity based on GPU tier and provider."""
        if spec.architecture in ("Turing",):
            return "Low"
        if spec.architecture in ("Ampere",) and spec.gpu_count <= 2:
            return "Medium"
        return "High"

    def _build_narrative(
        self,
        gpu_count: int,
        ghost_count: int,
        mig_count: int,
        total_spend: float,
        total_savings: float,
        annual_waste: float,
        providers: list[str] | None = None,
    ) -> str:
        providers = providers or []
        provider_str = ", ".join(p.upper() for p in sorted(providers))

        parts = [
            f"You have {gpu_count} GPU instance{'s' if gpu_count != 1 else ''} "
            f"across {provider_str or 'your cloud'} totaling ${total_spend:,.0f}/month."
        ]
        if ghost_count:
            parts.append(
                f"{ghost_count} instance{'s' if ghost_count != 1 else ''} "
                f"appear{'s' if ghost_count == 1 else ''} "
                f"idle or unverified, burning ${annual_waste:,.0f}/year if left running."
            )
        if mig_count:
            parts.append(
                f"{mig_count} A100/H100 host{'s' if mig_count != 1 else ''} "
                f"support{'s' if mig_count == 1 else ''} "
                "NVIDIA MIG partitioning for up to 7× utilization at the same cost."
            )
        if total_savings > 0:
            parts.append(
                f"Moving GPU workloads to the cheapest specialized cloud saves "
                f"${total_savings:,.0f}/month (${total_savings * 12:,.0f}/year)."
            )
        return " ".join(parts)
