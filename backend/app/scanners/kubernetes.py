import logging
from typing import List, Optional
from kubernetes import client, config
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ScannedResource(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str
    region: str
    status: str
    tags: dict
    metadata: dict
    cost: Optional[float] = 0.0

class ScanResult(BaseModel):
    resources: List[ScannedResource]
    regions_scanned: int = 1
    total_spend: float = 0.0

class KubernetesScanner:
    def __init__(self, kubeconfig_path: Optional[str] = None):
        try:
            if kubeconfig_path:
                config.load_kube_config(config_file=kubeconfig_path)
            else:
                config.load_kube_config()
            self.v1 = client.CoreV1Api()
            self.connected = True
        except Exception as e:
            logger.error("Failed to load kubeconfig: %s", e)
            self.connected = False

    async def scan(self) -> ScanResult:
        if not self.connected:
            return ScanResult(resources=[], total_spend=0.0)

        resources: List[ScannedResource] = []
        total_spend = 0.0
        
        # Configuration for cost estimation
        HOURLY_COST_VCPU = 0.040
        HOURLY_COST_GB_RAM = 0.005
        HOURLY_COST_STORAGE = 0.0001
        
        try:
            namespaces = self.v1.list_namespace().items
            
            for ns in namespaces:
                ns_name = ns.metadata.name
                
                # Get pods
                pods = self.v1.list_namespaced_pod(ns_name).items
                
                ns_cpu_req = 0.0
                ns_mem_req = 0.0
                
                for pod in pods:
                    for container in pod.spec.containers:
                        res = container.resources
                        if res.requests:
                            ns_cpu_req += self._parse_cpu(res.requests.get('cpu'))
                            ns_mem_req += self._parse_memory(res.requests.get('memory'))
                
                # Estimate Cost
                monthly_cpu = ns_cpu_req * HOURLY_COST_VCPU * 730
                monthly_mem = ns_mem_req * HOURLY_COST_GB_RAM * 730
                monthly_cost = monthly_cpu + monthly_mem
                total_spend += monthly_cost
                
                # Add Namespace as a resource
                resources.append(ScannedResource(
                    resource_id=f"ns-{ns_name}",
                    resource_name=ns_name,
                    resource_type="Kubernetes Namespace",
                    region="local-cluster",
                    status="Active",
                    tags={"k8s-cluster": "local"},
                    metadata={
                        "pod_count": len(pods),
                        "cpu_requests": round(ns_cpu_req, 2),
                        "memory_requests_gb": round(ns_mem_req, 2),
                        "monthly_cost_estimate": round(monthly_cost, 2)
                    },
                    cost=round(monthly_cost, 2)
                ))
            
            return ScanResult(resources=resources, total_spend=total_spend)
            
        except Exception as e:
            logger.error("Error during K8s scan: %s", e)
            return ScanResult(resources=[], total_spend=0.0)

    def _parse_cpu(self, cpu_str):
        if not cpu_str: return 0.0
        if cpu_str.endswith('m'): return float(cpu_str[:-1]) / 1000
        return float(cpu_str)

    def _parse_memory(self, mem_str):
        if not mem_str: return 0.0
        if mem_str.endswith('Ki'): return float(mem_str[:-2]) / (1024**3) # Error in original script, Ki is small
        # Actually standardizing to GB
        if mem_str.endswith('Ki'): return float(mem_str[:-2]) / (1024*1024)
        if mem_str.endswith('Mi'): return float(mem_str[:-2]) / 1024
        if mem_str.endswith('Gi'): return float(mem_str[:-2])
        if mem_str.endswith('Ti'): return float(mem_str[:-2]) * 1024
        return float(mem_str) / (1024**3) # bytes to GB

    def to_db_resources(self, resources: List[ScannedResource], user_id: str, integration_id: str) -> List[dict]:
        db_resources = []
        for r in resources:
            db_resources.append({
                "user_id": user_id,
                "integration_id": integration_id,
                "resource_name": r.resource_name,
                "service_type": r.resource_type,
                "provider": "kubernetes",
                "region": r.region,
                "status": r.status,
                "cost": r.cost,
                "tags": r.tags,
                "metadata": r.metadata,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        return db_resources
