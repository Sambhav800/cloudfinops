from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Tuple

from .budget_events import build_budget_event_record
from .finance import build_forecast_summary
from .reports import build_report_record

DEMO_DATASET_VERSION = "2026-04-15"
DEMO_ACCOUNT_EMAIL = "sambhavpal5@gmail.com"
LEGACY_DEMO_DATA_OWNER_ID = "user_38kP2Ff8Jo2Y5g4zCtTr4Qg85kN"
CANONICAL_DEMO_DATA_OWNER_ID = "user_3ALOgTiKSBfTVwyOEahrUCjIWmi"

DEFAULT_FINANCE_SETTINGS: Dict[str, Any] = {
    "portfolio_budget_limit": 60000.0,
    "report_recipients": [DEMO_ACCOUNT_EMAIL],
    "report_cadence": "weekly",
    "alert_thresholds": {
        "warning_pct": 80.0,
        "critical_pct": 100.0,
    },
}

INTEGRATION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "key": "aws-core",
        "provider": "aws",
        "name": "Production AWS",
        "account_identifier": "884112441820",
        "regions": ["us-east-1"],
        "monthly_budget_limit": 28000.0,
        "history_trend_bias": 0.10,
        "history_multipliers": (0.92, 0.97, 1.0),
        "created_days_ago": 120,
        "last_scan_hours_ago": 6,
    },
    {
        "key": "aws-ml",
        "provider": "aws",
        "name": "ML Sandbox AWS",
        "account_identifier": "991772004118",
        "regions": ["us-east-1"],
        "monthly_budget_limit": 7800.0,
        "history_trend_bias": -0.02,
        "history_multipliers": (0.95, 0.98, 1.0),
        "created_days_ago": 75,
        "last_scan_hours_ago": 10,
    },
    {
        "key": "azure-apps",
        "provider": "azure",
        "name": "Customer Apps Azure",
        "account_identifier": "sub-4a27cc91-eus",
        "regions": ["eastus"],
        "monthly_budget_limit": 13800.0,
        "history_trend_bias": 0.03,
        "history_multipliers": (0.94, 0.98, 1.0),
        "created_days_ago": 90,
        "last_scan_hours_ago": 8,
    },
    {
        "key": "gcp-data",
        "provider": "gcp",
        "name": "Data Platform GCP",
        "account_identifier": "finops-analytics-prj",
        "regions": ["us-central1"],
        "monthly_budget_limit": 9800.0,
        "history_trend_bias": 0.05,
        "history_multipliers": (0.91, 0.96, 1.0),
        "created_days_ago": 60,
        "last_scan_hours_ago": 4,
    },
]

DAY_OF_WEEK_WEIGHTS = {
    0: 1.05,
    1: 1.03,
    2: 1.00,
    3: 1.02,
    4: 1.08,
    5: 0.78,
    6: 0.72,
}

CARBON_FACTORS = {
    "compute": 0.016,
    "database": 0.012,
    "storage": 0.006,
    "network": 0.004,
    "other": 0.008,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _categorize_service(service_type: str) -> str:
    lowered = str(service_type or "").lower()
    if any(keyword in lowered for keyword in ("ec2", "compute", "vm", "instance", "eks", "aks", "gke", "lambda", "run", "sagemaker")):
        return "compute"
    if any(keyword in lowered for keyword in ("rds", "sql", "database", "cosmos", "warehouse", "bigquery", "elasticache")):
        return "database"
    if any(keyword in lowered for keyword in ("s3", "storage", "blob", "bucket", "disk", "ebs")):
        return "storage"
    if any(keyword in lowered for keyword in ("network", "vpc", "gateway", "balancer", "cdn", "ip", "security group")):
        return "network"
    return "other"


def _resource_id(user_id: str, integration_key: str, suffix: str) -> str:
    return f"{user_id}-{integration_key}-{suffix}"


def _integration_id(user_id: str, integration_key: str) -> str:
    return f"{user_id}-{integration_key}"


def _resource_entry(
    *,
    user_id: str,
    integration_id: str,
    provider: str,
    demo_key: str,
    cloud_resource_id: str,
    resource_name: str,
    service_type: str,
    region: str,
    cost: float,
    status: str = "active",
    waste_type: str | None = None,
    waste_reason: str | None = None,
    region_compliance: str = "compliant",
    confidence_score: float = 91.0,
    last_scanned_at: str,
    tags: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
    metrics_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized_tags = dict(tags or {})
    normalized_metadata = dict(metadata or {})
    normalized_metadata.setdefault("tags", dict(normalized_tags))
    normalized_metadata.setdefault("demo_key", demo_key)
    normalized_metrics = dict(metrics_data or {})

    category = _categorize_service(service_type)
    carbon_footprint_kg = round(cost * CARBON_FACTORS.get(category, CARBON_FACTORS["other"]), 2)

    return {
        "id": _resource_id(user_id, integration_id, demo_key),
        "user_id": user_id,
        "integration_id": integration_id,
        "provider": provider,
        "cloud_resource_id": cloud_resource_id,
        "resource_name": resource_name,
        "service_type": service_type,
        "region": region,
        "region_compliance": region_compliance,
        "status": status,
        "waste_type": waste_type,
        "waste_reason": waste_reason,
        "confidence_score": confidence_score,
        "cost": round(cost, 2),
        "carbon_footprint_kg": carbon_footprint_kg,
        "tags": normalized_tags,
        "metadata": normalized_metadata,
        "metrics_data": normalized_metrics,
        "governance_violations": [],
        "last_scanned_at": last_scanned_at,
    }


def _find_resource(resources: List[Dict[str, Any]], demo_key: str) -> Dict[str, Any]:
    for resource in resources:
        metadata = resource.get("metadata")
        if isinstance(metadata, dict) and metadata.get("demo_key") == demo_key:
            return resource
    raise KeyError(f"Unknown demo resource key: {demo_key}")


def _integration_index(user_id: str, now: datetime) -> Dict[str, Dict[str, Any]]:
    integrations: Dict[str, Dict[str, Any]] = {}
    for template in INTEGRATION_TEMPLATES:
        integration_id = _integration_id(user_id, template["key"])
        created_at = now - timedelta(days=int(template["created_days_ago"]))
        last_scan = now - timedelta(hours=int(template["last_scan_hours_ago"]))
        integrations[template["key"]] = {
            "id": integration_id,
            "user_id": user_id,
            "provider": template["provider"],
            "name": template["name"],
            "status": "active",
            "regions": list(template["regions"]),
            "account_identifier": template["account_identifier"],
            "monthly_budget_limit": template["monthly_budget_limit"],
            "created_at": _iso(created_at),
            "last_scan": _iso(last_scan),
            "metadata": {
                "environment": "demo",
                "demo_dataset_version": DEMO_DATASET_VERSION,
            },
            "history_trend_bias": float(template["history_trend_bias"]),
            "history_multipliers": tuple(template["history_multipliers"]),
        }
    return integrations


def _build_demo_resources(user_id: str, integrations: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []

    aws_core = integrations["aws-core"]
    aws_core_id = aws_core["id"]
    aws_core_region = aws_core["regions"][0]
    aws_core_scan = aws_core["last_scan"]
    aws_core_tags = {"Environment": "prod", "CostCenter": "finops-platform", "Owner": "Platform"}
    resources.extend([
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-vpc",
            cloud_resource_id="vpc-0cf-prod",
            resource_name="prod-core-vpc",
            service_type="AWS VPC",
            region=aws_core_region,
            cost=80.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "cidr_block": "10.20.0.0/16"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-subnet-public-a",
            cloud_resource_id="subnet-0cf-public-a",
            resource_name="public-a",
            service_type="AWS Subnet",
            region=aws_core_region,
            cost=0.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={
                "aws_region": aws_core_region,
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-public-a",
                "availability_zone": "us-east-1a",
                "cidr_block": "10.20.0.0/24",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-subnet-private-a",
            cloud_resource_id="subnet-0cf-private-a",
            resource_name="private-a",
            service_type="AWS Subnet",
            region=aws_core_region,
            cost=0.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={
                "aws_region": aws_core_region,
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-private-a",
                "availability_zone": "us-east-1a",
                "cidr_block": "10.20.10.0/24",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-subnet-private-b",
            cloud_resource_id="subnet-0cf-private-b",
            resource_name="private-b",
            service_type="AWS Subnet",
            region=aws_core_region,
            cost=0.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={
                "aws_region": aws_core_region,
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-private-b",
                "availability_zone": "us-east-1b",
                "cidr_block": "10.20.11.0/24",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-igw",
            cloud_resource_id="igw-0cf-prod",
            resource_name="prod-core-igw",
            service_type="AWS Internet Gateway",
            region=aws_core_region,
            cost=0.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "attached_vpcs": ["vpc-0cf-prod"]},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-sg-open-admin",
            cloud_resource_id="sg-0cf-open-admin",
            resource_name="sg-open-admin",
            service_type="AWS Security Group",
            region=aws_core_region,
            cost=0.0,
            status="non_compliant",
            waste_type="security_risk",
            waste_reason="Ingress rule allows 0.0.0.0/0 on port 22.",
            region_compliance="non_compliant",
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "Owner": "Platform"},
            metadata={"aws_region": aws_core_region, "group_id": "sg-0cf-open-admin", "vpc_id": "vpc-0cf-prod", "is_overly_permissive": True},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-api01",
            cloud_resource_id="i-0cf-api01",
            resource_name="api-prod-app-01",
            service_type="AWS EC2 Instance",
            region=aws_core_region,
            cost=3700.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={
                "aws_region": aws_core_region,
                "instance_id": "i-0cf-api01",
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-private-a",
                "instance_type": "m6i.4xlarge",
                "security_groups": ["sg-0cf-open-admin"],
            },
            metrics_data={"cpu_utilization": 58, "memory_utilization": 64},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-api02",
            cloud_resource_id="i-0cf-api02",
            resource_name="api-prod-app-02",
            service_type="AWS EC2 Instance",
            region=aws_core_region,
            cost=3460.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={
                "aws_region": aws_core_region,
                "instance_id": "i-0cf-api02",
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-private-b",
                "instance_type": "m6i.4xlarge",
                "security_groups": ["sg-0cf-open-admin"],
            },
            metrics_data={"cpu_utilization": 24, "memory_utilization": 34},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-batch01",
            cloud_resource_id="i-0cf-batch01",
            resource_name="billing-batch-01",
            service_type="AWS EC2 Instance",
            region=aws_core_region,
            cost=1200.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "finops-platform", "Owner": "DataOps"},
            metadata={
                "aws_region": aws_core_region,
                "instance_id": "i-0cf-batch01",
                "vpc_id": "vpc-0cf-prod",
                "subnet_id": "subnet-0cf-private-b",
                "instance_type": "m6i.2xlarge",
                "security_groups": ["sg-0cf-open-admin"],
            },
            metrics_data={"cpu_utilization": 42, "memory_utilization": 48},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-aurora",
            cloud_resource_id="db-prod-orders",
            resource_name="orders-aurora",
            service_type="AWS RDS Instance",
            region=aws_core_region,
            cost=4620.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "finops-platform", "Owner": "Data"},
            metadata={
                "aws_region": aws_core_region,
                "vpc_id": "vpc-0cf-prod",
                "subnet_ids": ["subnet-0cf-private-a", "subnet-0cf-private-b"],
                "engine": "aurora-postgresql",
                "instance_class": "db.r6g.2xlarge",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-rds-replica",
            cloud_resource_id="db-prod-analytics-replica",
            resource_name="analytics-read-replica",
            service_type="AWS RDS Instance",
            region=aws_core_region,
            cost=1560.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "analytics", "Owner": "Data"},
            metadata={
                "aws_region": aws_core_region,
                "vpc_id": "vpc-0cf-prod",
                "subnet_ids": ["subnet-0cf-private-a"],
                "engine": "postgres",
                "instance_class": "db.r6g.large",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-eks",
            cloud_resource_id="eks-prod-main",
            resource_name="prod-eks-cluster",
            service_type="AWS EKS Cluster",
            region=aws_core_region,
            cost=6030.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "subnet_id": "subnet-0cf-private-a"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-alb",
            cloud_resource_id="alb-prod-edge",
            resource_name="prod-edge-alb",
            service_type="AWS Load Balancer",
            region=aws_core_region,
            cost=690.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "subnet_id": "subnet-0cf-public-a"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-s3",
            cloud_resource_id="bucket-prod-data-lake",
            resource_name="data-lake-bucket",
            service_type="AWS S3 Bucket",
            region=aws_core_region,
            cost=1320.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "analytics", "Owner": "Data"},
            metadata={"aws_region": aws_core_region, "storage_class": "standard"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-lambda-billing",
            cloud_resource_id="lambda-nightly-billing",
            resource_name="nightly-billing-lambda",
            service_type="AWS Lambda Function",
            region=aws_core_region,
            cost=220.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "finops-platform", "Owner": "FinOps"},
            metadata={"aws_region": aws_core_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-ebs-audit-archive",
            cloud_resource_id="vol-0cf-audit-archive",
            resource_name="audit-archive-ebs",
            service_type="AWS EBS Volume",
            region=aws_core_region,
            cost=540.0,
            status="zombie",
            waste_type="orphan_disk",
            waste_reason="Volume has been detached for 19 days.",
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod"},
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "size_gb": 1200, "volume_type": "gp3"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-ebs-logs",
            cloud_resource_id="vol-0cf-logs",
            resource_name="prod-logs-ebs",
            service_type="AWS EBS Volume",
            region=aws_core_region,
            cost=480.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "attached_to": "i-0cf-api01", "size_gb": 900, "volume_type": "gp3"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-elasticache",
            cloud_resource_id="cache-prod-sessions",
            resource_name="session-cache",
            service_type="AWS ElastiCache Cluster",
            region=aws_core_region,
            cost=1680.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Platform"},
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "subnet_id": "subnet-0cf-private-a"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-lambda-support",
            cloud_resource_id="lambda-support-sync",
            resource_name="support-sync-lambda",
            service_type="AWS Lambda Function",
            region=aws_core_region,
            cost=380.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Support"},
            metadata={"aws_region": aws_core_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-nat",
            cloud_resource_id="nat-0cf-prod",
            resource_name="prod-nat-gateway",
            service_type="AWS NAT Gateway",
            region=aws_core_region,
            cost=80.0,
            last_scanned_at=aws_core_scan,
            tags=aws_core_tags,
            metadata={"aws_region": aws_core_region, "vpc_id": "vpc-0cf-prod", "subnet_id": "subnet-0cf-public-a"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_core_id,
            provider="aws",
            demo_key="aws-core-cloudfront",
            cloud_resource_id="cf-prod-global",
            resource_name="customer-traffic-cdn",
            service_type="AWS CloudFront Distribution",
            region=aws_core_region,
            cost=1620.0,
            last_scanned_at=aws_core_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Growth"},
            metadata={"aws_region": aws_core_region},
        ),
    ])

    aws_ml = integrations["aws-ml"]
    aws_ml_id = aws_ml["id"]
    aws_ml_region = aws_ml["regions"][0]
    aws_ml_scan = aws_ml["last_scan"]
    ml_tags = {"Environment": "sandbox", "CostCenter": "ai-lab", "Owner": "ML Platform"}
    resources.extend([
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-vpc",
            cloud_resource_id="vpc-0cf-ml",
            resource_name="ml-sandbox-vpc",
            service_type="AWS VPC",
            region=aws_ml_region,
            cost=40.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={"aws_region": aws_ml_region, "vpc_id": "vpc-0cf-ml", "cidr_block": "10.40.0.0/16"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-subnet-a",
            cloud_resource_id="subnet-0cf-ml-a",
            resource_name="ml-private-a",
            service_type="AWS Subnet",
            region=aws_ml_region,
            cost=0.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={
                "aws_region": aws_ml_region,
                "vpc_id": "vpc-0cf-ml",
                "subnet_id": "subnet-0cf-ml-a",
                "availability_zone": "us-east-1a",
                "cidr_block": "10.40.10.0/24",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-subnet-b",
            cloud_resource_id="subnet-0cf-ml-b",
            resource_name="ml-private-b",
            service_type="AWS Subnet",
            region=aws_ml_region,
            cost=0.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={
                "aws_region": aws_ml_region,
                "vpc_id": "vpc-0cf-ml",
                "subnet_id": "subnet-0cf-ml-b",
                "availability_zone": "us-east-1b",
                "cidr_block": "10.40.11.0/24",
            },
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-gpu-train",
            cloud_resource_id="i-0cf-gpu-train",
            resource_name="ml-gpu-train-01",
            service_type="AWS EC2 Instance",
            region=aws_ml_region,
            cost=3420.0,
            status="zombie",
            waste_type="stopped_vm",
            waste_reason="Training node has been idle since the last experiment window.",
            last_scanned_at=aws_ml_scan,
            tags={"CostCenter": "ai-lab"},
            metadata={
                "aws_region": aws_ml_region,
                "instance_id": "i-0cf-gpu-train",
                "vpc_id": "vpc-0cf-ml",
                "subnet_id": "subnet-0cf-ml-a",
                "instance_type": "p4d.24xlarge",
                "is_gpu_instance": True,
                "gpu_memory_utilization_pct": 9,
                "gpu_sm_occupancy_pct": 8,
                "gpu_optimization_insight": "Idle for 6 days. Safe to stop before the next training window.",
            },
            metrics_data={"cpu_utilization": 4, "memory_utilization": 11},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-gpu-infer",
            cloud_resource_id="i-0cf-gpu-infer",
            resource_name="ml-gpu-infer-02",
            service_type="AWS EC2 Instance",
            region=aws_ml_region,
            cost=1180.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={
                "aws_region": aws_ml_region,
                "instance_id": "i-0cf-gpu-infer",
                "vpc_id": "vpc-0cf-ml",
                "subnet_id": "subnet-0cf-ml-b",
                "instance_type": "g5.2xlarge",
                "is_gpu_instance": True,
                "gpu_memory_utilization_pct": 46,
                "gpu_sm_occupancy_pct": 39,
                "gpu_optimization_insight": "Steady inference load. Keep online, but consider committing baseline usage.",
            },
            metrics_data={"cpu_utilization": 41, "memory_utilization": 52},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-sagemaker",
            cloud_resource_id="sm-notebook-feature-store",
            resource_name="feature-store-notebook",
            service_type="AWS SageMaker Notebook",
            region=aws_ml_region,
            cost=890.0,
            last_scanned_at=aws_ml_scan,
            tags={"Environment": "sandbox", "Owner": "ML Platform"},
            metadata={"aws_region": aws_ml_region, "vpc_id": "vpc-0cf-ml", "subnet_id": "subnet-0cf-ml-b"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-s3",
            cloud_resource_id="bucket-ml-model-artifacts",
            resource_name="model-artifacts-bucket",
            service_type="AWS S3 Bucket",
            region=aws_ml_region,
            cost=480.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={"aws_region": aws_ml_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-ebs-cache",
            cloud_resource_id="vol-0cf-ml-cache",
            resource_name="ml-training-cache",
            service_type="AWS EBS Volume",
            region=aws_ml_region,
            cost=410.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={"aws_region": aws_ml_region, "attached_to": "i-0cf-gpu-infer", "size_gb": 900, "volume_type": "gp3"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-eip",
            cloud_resource_id="eipalloc-0cf-ml-idle",
            resource_name="idle-train-eip",
            service_type="AWS Elastic IP",
            region=aws_ml_region,
            cost=110.0,
            status="waste",
            waste_type="waste",
            waste_reason="Elastic IP is allocated but not attached to a running workload.",
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={"aws_region": aws_ml_region, "public_ip": "34.229.10.18"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-lambda",
            cloud_resource_id="lambda-feature-pipeline",
            resource_name="feature-pipeline-lambda",
            service_type="AWS Lambda Function",
            region=aws_ml_region,
            cost=250.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={"aws_region": aws_ml_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=aws_ml_id,
            provider="aws",
            demo_key="aws-ml-preprocess",
            cloud_resource_id="i-0cf-preprocess",
            resource_name="spot-preprocess-01",
            service_type="AWS EC2 Instance",
            region=aws_ml_region,
            cost=780.0,
            last_scanned_at=aws_ml_scan,
            tags=ml_tags,
            metadata={
                "aws_region": aws_ml_region,
                "instance_id": "i-0cf-preprocess",
                "vpc_id": "vpc-0cf-ml",
                "subnet_id": "subnet-0cf-ml-a",
                "instance_type": "m6i.large",
            },
            metrics_data={"cpu_utilization": 26, "memory_utilization": 31},
        ),
    ])

    azure = integrations["azure-apps"]
    azure_id = azure["id"]
    azure_region = azure["regions"][0]
    azure_scan = azure["last_scan"]
    azure_tags = {"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Platform"}
    resources.extend([
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-vm-app01",
            cloud_resource_id="vm-app-01",
            resource_name="az-web-01",
            service_type="Azure Virtual Machine",
            region=azure_region,
            cost=3060.0,
            last_scanned_at=azure_scan,
            tags=azure_tags,
            metadata={"location": azure_region, "instance_type": "D8as_v5"},
            metrics_data={"cpu_utilization": 47, "memory_utilization": 58},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-vm-app02",
            cloud_resource_id="vm-app-02",
            resource_name="az-web-02",
            service_type="Azure Virtual Machine",
            region=azure_region,
            cost=2920.0,
            last_scanned_at=azure_scan,
            tags=azure_tags,
            metadata={"location": azure_region, "instance_type": "D8as_v5"},
            metrics_data={"cpu_utilization": 21, "memory_utilization": 30},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-aks",
            cloud_resource_id="aks-customer-prod",
            resource_name="aks-customer-prod",
            service_type="Azure AKS Cluster",
            region=azure_region,
            cost=1440.0,
            last_scanned_at=azure_scan,
            tags=azure_tags,
            metadata={"location": azure_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-sql",
            cloud_resource_id="sqldb-customer-analytics",
            resource_name="customer-analytics-sql",
            service_type="Azure SQL Database",
            region=azure_region,
            cost=2990.0,
            last_scanned_at=azure_scan,
            tags=azure_tags,
            metadata={"location": azure_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-blob",
            cloud_resource_id="blob-customer-archive",
            resource_name="customer-blob-archive",
            service_type="Azure Blob Storage",
            region=azure_region,
            cost=860.0,
            last_scanned_at=azure_scan,
            tags={"Environment": "prod", "CostCenter": "customer-support", "Owner": "Support"},
            metadata={"location": azure_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-orphan-disk",
            cloud_resource_id="disk-orphan-01",
            resource_name="az-orphan-disk-01",
            service_type="Azure Managed Disk",
            region=azure_region,
            cost=460.0,
            status="zombie",
            waste_type="orphan_disk",
            waste_reason="Managed disk has not been attached to a VM since the rollback window closed.",
            last_scanned_at=azure_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Platform"},
            metadata={"location": azure_region, "disk_size_gb": 1024, "is_orphaned": True},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-idle-public-ip",
            cloud_resource_id="pip-idle-01",
            resource_name="idle-gateway-ip",
            service_type="Azure Public IP Address",
            region=azure_region,
            cost=140.0,
            status="waste",
            waste_type="waste",
            waste_reason="Static public IP is reserved but not mapped to an active gateway.",
            last_scanned_at=azure_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Network"},
            metadata={"location": azure_region, "ip_address": "20.86.11.42"},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-nsg",
            cloud_resource_id="nsg-open-rdp",
            resource_name="nsg-open-rdp",
            service_type="Azure Network Security Group",
            region=azure_region,
            cost=0.0,
            status="non_compliant",
            waste_type="security_risk",
            waste_reason="Inbound RDP is open to any source address.",
            region_compliance="non_compliant",
            last_scanned_at=azure_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps"},
            metadata={"location": azure_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=azure_id,
            provider="azure",
            demo_key="azure-lb",
            cloud_resource_id="lb-customer-edge",
            resource_name="customer-edge-lb",
            service_type="Azure Load Balancer",
            region=azure_region,
            cost=490.0,
            last_scanned_at=azure_scan,
            tags=azure_tags,
            metadata={"location": azure_region},
        ),
    ])

    gcp = integrations["gcp-data"]
    gcp_id = gcp["id"]
    gcp_region = gcp["regions"][0]
    gcp_scan = gcp["last_scan"]
    gcp_tags = {"Environment": "prod", "CostCenter": "analytics", "Owner": "Data"}
    resources.extend([
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-vpc",
            cloud_resource_id="vpc-data-core",
            resource_name="gcp-data-vpc",
            service_type="GCP VPC Network",
            region=gcp_region,
            cost=60.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-etl-runner",
            cloud_resource_id="gce-etl-runner-01",
            resource_name="gcp-etl-runner-01",
            service_type="GCP Compute Instance",
            region=gcp_region,
            cost=1620.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region, "instance_type": "n2-standard-8"},
            metrics_data={"cpu_utilization": 54, "memory_utilization": 61},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-dev-runner",
            cloud_resource_id="gce-dev-runner-01",
            resource_name="gcp-dev-runner-01",
            service_type="GCP Compute Instance",
            region=gcp_region,
            cost=410.0,
            status="zombie",
            waste_type="stopped_vm",
            waste_reason="Dev runner has been left on after the last data-science sprint.",
            last_scanned_at=gcp_scan,
            tags={"CostCenter": "analytics"},
            metadata={"location": gcp_region, "instance_type": "e2-standard-4", "state": "stopped"},
            metrics_data={"cpu_utilization": 2, "memory_utilization": 7},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-gke",
            cloud_resource_id="gke-streaming-main",
            resource_name="gke-streaming-main",
            service_type="GCP GKE Cluster",
            region=gcp_region,
            cost=1410.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-cloudsql",
            cloud_resource_id="cloudsql-analytics-prod",
            resource_name="analytics-cloud-sql",
            service_type="GCP Cloud SQL",
            region=gcp_region,
            cost=2140.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-bucket",
            cloud_resource_id="bucket-finops-data-lake",
            resource_name="finops-data-lake",
            service_type="GCP Cloud Storage Bucket",
            region=gcp_region,
            cost=690.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-orphan-disk",
            cloud_resource_id="pd-orphan-etl-cache",
            resource_name="orphaned-etl-disk",
            service_type="GCP Persistent Disk",
            region=gcp_region,
            cost=330.0,
            status="zombie",
            waste_type="orphan_disk",
            waste_reason="Persistent disk is unattached after the ETL migration.",
            last_scanned_at=gcp_scan,
            tags={"Environment": "prod", "CostCenter": "analytics"},
            metadata={"location": gcp_region, "disk_size_gb": 1024, "is_orphaned": True},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-cloudrun",
            cloud_resource_id="cloudrun-events-api",
            resource_name="events-api",
            service_type="GCP Cloud Run Service",
            region=gcp_region,
            cost=390.0,
            last_scanned_at=gcp_scan,
            tags={"Environment": "prod", "CostCenter": "customer-apps", "Owner": "Platform"},
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-bigquery",
            cloud_resource_id="bq-monthly-warehouse",
            resource_name="monthly-warehouse-jobs",
            service_type="GCP BigQuery Warehouse",
            region=gcp_region,
            cost=1040.0,
            last_scanned_at=gcp_scan,
            tags={"Environment": "prod", "Owner": "Analytics"},
            metadata={"location": gcp_region},
        ),
        _resource_entry(
            user_id=user_id,
            integration_id=gcp_id,
            provider="gcp",
            demo_key="gcp-lb",
            cloud_resource_id="gclb-prod-edge",
            resource_name="global-https-lb",
            service_type="GCP Load Balancer",
            region=gcp_region,
            cost=430.0,
            last_scanned_at=gcp_scan,
            tags=gcp_tags,
            metadata={"location": gcp_region},
        ),
    ])

    return resources


def _service_breakdown_shares(resources: List[Dict[str, Any]]) -> Dict[str, float]:
    spend_by_service: Dict[str, float] = defaultdict(float)
    total = 0.0
    for resource in resources:
        cost = float(resource.get("cost") or 0.0)
        if cost <= 0:
            continue
        service = str(resource.get("service_type") or "Other")
        spend_by_service[service] += cost
        total += cost

    if total <= 0:
        return {"Other": 1.0}

    return {
        service: amount / total
        for service, amount in spend_by_service.items()
    }


def _month_target_for_offset(base_target: float, multipliers: Tuple[float, float, float], month_offset: int) -> float:
    if month_offset <= -2:
        return round(base_target * float(multipliers[0]), 2)
    if month_offset == -1:
        return round(base_target * float(multipliers[1]), 2)
    return round(base_target * float(multipliers[2]), 2)


def _build_daily_history_rows(
    *,
    integration: Dict[str, Any],
    resources: List[Dict[str, Any]],
    today: date,
) -> List[Dict[str, Any]]:
    monthly_target = round(sum(float(resource.get("cost") or 0.0) for resource in resources), 2)
    shares = _service_breakdown_shares(resources)
    history_multipliers = integration["history_multipliers"]
    trend_bias = float(integration["history_trend_bias"])
    rows: List[Dict[str, Any]] = []

    start_date = today - timedelta(days=74)
    current_month_start = date(today.year, today.month, 1)

    weight_cache: Dict[Tuple[int, int], List[float]] = {}
    total_weight_cache: Dict[Tuple[int, int], float] = {}

    current = start_date
    while current <= today:
        key = (current.year, current.month)
        if key not in weight_cache:
            days_in_month = monthrange(current.year, current.month)[1]
            month_weights: List[float] = []
            for day in range(1, days_in_month + 1):
                day_date = date(current.year, current.month, day)
                base_weight = DAY_OF_WEEK_WEIGHTS[day_date.weekday()]
                position = ((day - 1) / max(days_in_month - 1, 1)) - 0.5
                trend_multiplier = 1 + (trend_bias * position)
                month_weights.append(max(0.35, base_weight * trend_multiplier))
            weight_cache[key] = month_weights
            total_weight_cache[key] = sum(month_weights)

        month_start = date(current.year, current.month, 1)
        month_offset = (month_start.year - current_month_start.year) * 12 + (month_start.month - current_month_start.month)
        month_target = _month_target_for_offset(monthly_target, history_multipliers, month_offset)
        weights = weight_cache[key]
        total_weight = total_weight_cache[key]
        day_amount = round(month_target * (weights[current.day - 1] / total_weight), 2)

        service_breakdown = {
            service: round(day_amount * share, 2)
            for service, share in shares.items()
        }
        rows.append(
            {
                "user_id": integration["user_id"],
                "integration_id": integration["id"],
                "spend_date": current.isoformat(),
                "amount": day_amount,
                "currency": "USD",
                "service_breakdown": service_breakdown,
            }
        )
        current += timedelta(days=1)

    return rows


def _build_pending_notifications(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    resources: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    action_specs = [
        {
            "key": "aws-core-api02-rightsize",
            "resource_key": "aws-core-api02",
            "integration_key": "aws-core",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "rightsize",
            "severity": "medium",
            "estimated_savings": 760.0,
            "recommendation": "Right-size API application instances",
            "description": "CPU and memory on api-prod-app-02 have stayed below 35% for the last 10 days.",
            "created_days_ago": 2,
        },
        {
            "key": "aws-core-audit-ebs-delete",
            "resource_key": "aws-core-ebs-audit-archive",
            "integration_key": "aws-core",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "terminate",
            "severity": "high",
            "estimated_savings": 540.0,
            "recommendation": "Delete detached audit archive volume",
            "description": "The audit archive volume has been idle for 19 days and is safe to snapshot then remove.",
            "created_days_ago": 1,
        },
        {
            "key": "aws-core-eks-commitment",
            "resource_key": "aws-core-eks",
            "integration_key": "aws-core",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "purchase_ri",
            "severity": "medium",
            "estimated_savings": 980.0,
            "recommendation": "Commit baseline EKS compute with a Savings Plan",
            "description": "The production EKS baseline has been stable enough to justify a 1-year compute commitment.",
            "created_days_ago": 5,
        },
        {
            "key": "aws-ml-gpu-terminate",
            "resource_key": "aws-ml-gpu-train",
            "integration_key": "aws-ml",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "terminate",
            "severity": "high",
            "estimated_savings": 3420.0,
            "recommendation": "Stop idle P4D training node",
            "description": "The P4D training host has been idle since the last experiment window and is burning GPU budget.",
            "created_days_ago": 1,
        },
        {
            "key": "azure-sql-optimize",
            "resource_key": "azure-sql",
            "integration_key": "azure-apps",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "optimize",
            "severity": "medium",
            "estimated_savings": 620.0,
            "recommendation": "Optimize Azure SQL tier",
            "description": "The analytics workload is below the reserved compute floor for most of the month.",
            "created_days_ago": 4,
        },
        {
            "key": "azure-public-ip-delete",
            "resource_key": "azure-idle-public-ip",
            "integration_key": "azure-apps",
            "status": "rejected",
            "type": "cost_optimization",
            "action_type": "terminate",
            "severity": "low",
            "estimated_savings": 140.0,
            "recommendation": "Release unused gateway IP",
            "description": "The public IP is idle, but the networking team asked to review the fallback design first.",
            "created_days_ago": 18,
        },
        {
            "key": "azure-vm-rightsize",
            "resource_key": "azure-vm-app01",
            "integration_key": "azure-apps",
            "status": "approved",
            "type": "cost_optimization",
            "action_type": "rightsize",
            "severity": "low",
            "estimated_savings": 280.0,
            "recommendation": "Right-size Azure web tier",
            "description": "CloudFinOps approved a smaller VM size for the secondary web node after traffic normalization.",
            "created_days_ago": 28,
        },
        {
            "key": "gcp-dev-runner-stop",
            "resource_key": "gcp-dev-runner",
            "integration_key": "gcp-data",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "stop",
            "severity": "low",
            "estimated_savings": 410.0,
            "recommendation": "Shut down idle GCP dev runner",
            "description": "The dev runner is only needed during weekday experiments and can follow office hours.",
            "created_days_ago": 2,
        },
        {
            "key": "gcp-orphan-disk-delete",
            "resource_key": "gcp-orphan-disk",
            "integration_key": "gcp-data",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "terminate",
            "severity": "medium",
            "estimated_savings": 330.0,
            "recommendation": "Delete orphaned ETL disk",
            "description": "The ETL cache disk was left behind after the migration and has no active attachments.",
            "created_days_ago": 3,
        },
        {
            "key": "gcp-bigquery-cap",
            "resource_key": "gcp-bigquery",
            "integration_key": "gcp-data",
            "status": "pending",
            "type": "cost_optimization",
            "action_type": "optimize",
            "severity": "medium",
            "estimated_savings": 310.0,
            "recommendation": "Apply reservation and query guardrails to BigQuery jobs",
            "description": "Scheduled warehouse jobs are bursting above the expected slot baseline during month-end closes.",
            "created_days_ago": 6,
        },
    ]

    notifications: List[Dict[str, Any]] = []
    for index, spec in enumerate(action_specs, start=1):
        resource = _find_resource(resources, spec["resource_key"])
        created_at = now - timedelta(days=int(spec["created_days_ago"]))
        integration_id = integrations[spec["integration_key"]]["id"]
        notifications.append(
            {
                "id": f"{user_id}-notification-{index}",
                "user_id": user_id,
                "resource_id": resource["id"],
                "type": spec["type"],
                "status": spec["status"],
                "recommendation": spec["recommendation"],
                "action": spec["action_type"],
                "created_at": _iso(created_at),
                "metadata": {
                    "resource_name": resource["resource_name"],
                    "resource_type": resource["service_type"],
                    "estimated_savings": spec["estimated_savings"],
                    "potential_savings": spec["estimated_savings"],
                    "severity": spec["severity"],
                    "integration_id": integration_id,
                    "description": spec["description"],
                    "ai_reasoning": spec["description"],
                    "action_type": spec["action_type"],
                },
            }
        )

    return notifications


def _waste_bucket_for_notification(notification: Dict[str, Any]) -> str | None:
    metadata = notification.get("metadata") if isinstance(notification.get("metadata"), dict) else {}
    resource_type = str(metadata.get("resource_type") or "").lower()
    action_type = str(metadata.get("action_type") or "").lower()

    if "ip" in resource_type:
        return "Unused IPs"
    if "disk" in resource_type or "ebs" in resource_type or "storage" in resource_type:
        return "Orphaned Storage"
    if action_type == "rightsize":
        return "Oversized Resources"
    if action_type == "optimize":
        return "Wasted Resources"
    if action_type == "purchase_ri":
        return "Wasted Resources"
    if action_type == "stop":
        return "Idle Resources"
    if action_type == "terminate":
        return "Zombie Resources"
    return None


def _build_waste_distribution(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    notifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    totals: Dict[Tuple[str, str], float] = defaultdict(float)
    for notification in notifications:
        if str(notification.get("status") or "").lower() != "pending":
            continue
        bucket = _waste_bucket_for_notification(notification)
        if not bucket:
            continue
        metadata = notification.get("metadata") if isinstance(notification.get("metadata"), dict) else {}
        integration_id = str(metadata.get("integration_id") or "").strip()
        if not integration_id:
            continue
        totals[(integration_id, bucket)] += float(metadata.get("estimated_savings") or 0.0)

    rows: List[Dict[str, Any]] = []
    for integration_key, integration in integrations.items():
        integration_id = integration["id"]
        for bucket in [
            "Zombie Resources",
            "Wasted Resources",
            "Idle Resources",
            "Oversized Resources",
            "Orphaned Storage",
            "Unused IPs",
        ]:
            value = round(totals.get((integration_id, bucket), 0.0), 2)
            if value <= 0:
                continue
            rows.append(
                {
                    "id": f"{integration_id}-{bucket.lower().replace(' ', '-')}",
                    "user_id": user_id,
                    "integration_id": integration_id,
                    "category_name": bucket,
                    "value": value,
                }
            )

    return rows


def _build_dashboard_stats(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    resources: List[Dict[str, Any]],
    notifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    resources_by_integration: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for resource in resources:
        resources_by_integration[str(resource["integration_id"])].append(resource)

    pending_savings_by_integration: Dict[str, float] = defaultdict(float)
    for notification in notifications:
        if str(notification.get("status") or "").lower() != "pending":
            continue
        metadata = notification.get("metadata") if isinstance(notification.get("metadata"), dict) else {}
        integration_id = str(metadata.get("integration_id") or "").strip()
        if not integration_id:
            continue
        pending_savings_by_integration[integration_id] += float(metadata.get("estimated_savings") or 0.0)

    stats: List[Dict[str, Any]] = []
    confidence_by_provider = {"aws": 92.0, "azure": 90.0, "gcp": 91.0}
    for integration in integrations.values():
        integration_id = integration["id"]
        scoped_resources = resources_by_integration[integration_id]
        total_spend = round(sum(float(resource.get("cost") or 0.0) for resource in scoped_resources), 2)
        carbon = round(sum(float(resource.get("carbon_footprint_kg") or 0.0) for resource in scoped_resources), 2)
        potential_savings = round(pending_savings_by_integration.get(integration_id, 0.0), 2)
        stats.append(
            {
                "id": f"{integration_id}-stats",
                "user_id": user_id,
                "integration_id": integration_id,
                "total_spend": total_spend,
                "potential_savings": potential_savings,
                "active_resources_count": len(scoped_resources),
                "ai_confidence_score": confidence_by_provider.get(str(integration["provider"]), 89.0),
                "carbon_footprint_kg": carbon,
                "cost_of_inaction_6mo": round(potential_savings * 6, 2),
            }
        )

    return stats


def _build_demo_commitments(
    integration: Dict[str, Any],
    resources: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    provider = str(integration.get("provider") or "").lower()
    compute_spend = round(
        sum(
            float(resource.get("cost") or 0.0)
            for resource in resources
            if _categorize_service(str(resource.get("service_type") or "")) == "compute"
        ),
        2,
    )
    if compute_spend <= 0:
        return []

    if provider == "aws" and integration["id"].endswith("aws-core"):
        return [
            {
                "id": f"{integration['id']}-commitment-core",
                "provider": "aws",
                "type": "Savings Plan",
                "name": "Production Compute Savings Plan",
                "status": "active",
                "start_date": _iso(now - timedelta(days=182)),
                "end_date": _iso(now + timedelta(days=183)),
                "commitment_amount": round(compute_spend * 0.42, 2),
                "currency": "USD",
                "region": "global",
                "utilization_pct": 94.6,
                "savings_amount": 2210.0,
                "coverage_type": "Compute",
            }
        ]
    if provider == "aws" and integration["id"].endswith("aws-ml"):
        return [
            {
                "id": f"{integration['id']}-commitment-ml",
                "provider": "aws",
                "type": "Reservation",
                "name": "Inference Capacity Reservation",
                "status": "active",
                "start_date": _iso(now - timedelta(days=91)),
                "end_date": _iso(now + timedelta(days=274)),
                "commitment_amount": round(compute_spend * 0.28, 2),
                "currency": "USD",
                "region": "us-east-1",
                "utilization_pct": 88.2,
                "savings_amount": 710.0,
                "coverage_type": "Instance",
            }
        ]
    if provider == "gcp":
        return [
            {
                "id": f"{integration['id']}-commitment-data",
                "provider": "gcp",
                "type": "CUD",
                "name": "Analytics 1-Year CUD",
                "status": "active",
                "start_date": _iso(now - timedelta(days=63)),
                "end_date": _iso(now + timedelta(days=302)),
                "commitment_amount": round(compute_spend * 0.35, 2),
                "currency": "USD",
                "region": "us-central1",
                "utilization_pct": 91.4,
                "savings_amount": 880.0,
                "coverage_type": "Compute",
            }
        ]
    return []


def _attach_demo_commitments(
    *,
    integrations: Dict[str, Dict[str, Any]],
    resources: List[Dict[str, Any]],
    now: datetime,
) -> None:
    resources_by_integration: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for resource in resources:
        resources_by_integration[str(resource["integration_id"])].append(resource)

    for integration in integrations.values():
        commitments = _build_demo_commitments(integration, resources_by_integration[integration["id"]], now)
        metadata = integration.get("metadata") if isinstance(integration.get("metadata"), dict) else {}
        metadata["demo_commitments"] = commitments
        integration["metadata"] = metadata


def _build_budget_events(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    history_by_integration: Dict[str, List[Dict[str, Any]]],
    finance_settings: Dict[str, Any],
    today: date,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    portfolio_history: List[Dict[str, Any]] = []
    integration_forecasts: Dict[str, Dict[str, Any]] = {}
    budget_events: List[Dict[str, Any]] = []

    for integration in integrations.values():
        integration_id = integration["id"]
        rows = history_by_integration[integration_id]
        portfolio_history.extend(rows)
        summary = build_forecast_summary(
            rows,
            budget_limit=float(integration["monthly_budget_limit"]),
            budget_source="integration",
            scope="integration",
            integration_id=integration_id,
            as_of=today,
            warning_threshold_pct=float(finance_settings["alert_thresholds"]["warning_pct"]),
        )
        integration_forecasts[integration_id] = summary
        event = build_budget_event_record(
            user_id=user_id,
            scope="integration",
            summary=summary,
            previous_status=None,
            integration=integration,
        )
        if event:
            event["id"] = f"{integration_id}-budget-event"
            budget_events.append(event)

    portfolio_forecast = build_forecast_summary(
        portfolio_history,
        budget_limit=float(finance_settings["portfolio_budget_limit"]),
        budget_source="portfolio_setting",
        scope="portfolio",
        as_of=today,
        warning_threshold_pct=float(finance_settings["alert_thresholds"]["warning_pct"]),
    )
    portfolio_event = build_budget_event_record(
        user_id=user_id,
        scope="portfolio",
        summary=portfolio_forecast,
        previous_status=None,
        integration=None,
    )
    if portfolio_event:
        portfolio_event["id"] = f"{user_id}-portfolio-budget-event"
        budget_events.insert(0, portfolio_event)

    now = datetime.combine(today, time(16, 0), tzinfo=timezone.utc)
    for index, event in enumerate(budget_events):
        event["created_at"] = _iso(now - timedelta(hours=index * 6))

    return budget_events, portfolio_forecast, integration_forecasts


def _build_governance_records(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    resources: List[Dict[str, Any]],
    notifications: List[Dict[str, Any]],
    portfolio_forecast: Dict[str, Any],
    now: datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    audit_volume = _find_resource(resources, "aws-core-ebs-audit-archive")
    gpu_train = _find_resource(resources, "aws-ml-gpu-train")
    azure_nsg = _find_resource(resources, "azure-nsg")
    gcp_orphan_disk = _find_resource(resources, "gcp-orphan-disk")
    gcp_bigquery = _find_resource(resources, "gcp-bigquery")

    policy_rows = [
        {
            "id": f"{user_id}-gov-owner-tags",
            "name": "Owner and cost center tags present",
            "description": "Every cost-bearing resource must have Owner and CostCenter tags.",
            "policy_type": "finops",
            "is_active": True,
            "compliance_rate": 84,
            "violations": 4,
            "status": "violations_found",
            "metadata": {"framework": "FinOps"},
            "created_at": _iso(now - timedelta(days=12)),
            "user_id": user_id,
        },
        {
            "id": f"{user_id}-gov-public-rdp",
            "name": "No public RDP or SSH ingress",
            "description": "Administrative ports must not be exposed to 0.0.0.0/0.",
            "policy_type": "security",
            "is_active": True,
            "compliance_rate": 92,
            "violations": 1,
            "status": "violations_found",
            "metadata": {"framework": "CIS"},
            "created_at": _iso(now - timedelta(days=11)),
            "user_id": user_id,
        },
        {
            "id": f"{user_id}-gov-office-hours",
            "name": "Non-production compute follows office hours",
            "description": "Non-production compute should be scheduled down outside business hours.",
            "policy_type": "operations",
            "is_active": True,
            "compliance_rate": 81,
            "violations": 2,
            "status": "violations_found",
            "metadata": {"framework": "FinOps"},
            "created_at": _iso(now - timedelta(days=10)),
            "user_id": user_id,
        },
        {
            "id": f"{user_id}-gov-db-encryption",
            "name": "Production databases encrypted at rest",
            "description": "Aurora, Cloud SQL, and Azure SQL all enforce encryption-at-rest.",
            "policy_type": "security",
            "is_active": True,
            "compliance_rate": 100,
            "violations": 0,
            "status": "active",
            "metadata": {"framework": "ISO 27001"},
            "created_at": _iso(now - timedelta(days=9)),
            "user_id": user_id,
        },
        {
            "id": f"{user_id}-gov-backup-retention",
            "name": "Backups retained for stateful workloads",
            "description": "Stateful services retain backup coverage longer than the minimum policy.",
            "policy_type": "reliability",
            "is_active": True,
            "compliance_rate": 100,
            "violations": 0,
            "status": "active",
            "metadata": {"framework": "SOC2"},
            "created_at": _iso(now - timedelta(days=8)),
            "user_id": user_id,
        },
        {
            "id": f"{user_id}-gov-multi-az",
            "name": "Customer-facing services span multiple zones",
            "description": "Production customer-facing workloads are spread across multiple zones and providers.",
            "policy_type": "reliability",
            "is_active": True,
            "compliance_rate": 95,
            "violations": 0,
            "status": "active",
            "metadata": {"framework": "Well-Architected"},
            "created_at": _iso(now - timedelta(days=7)),
            "user_id": user_id,
        },
    ]

    policy_violations = [
        {
            "id": f"{user_id}-policy-violation-1",
            "policy_id": policy_rows[0]["id"],
            "resource_id": audit_volume["id"],
            "user_id": user_id,
            "violation_details": {"detail": "Audit archive is missing both Owner and CostCenter tags."},
            "severity": "medium",
            "status": "active",
            "created_at": _iso(now - timedelta(days=6)),
        },
        {
            "id": f"{user_id}-policy-violation-2",
            "policy_id": policy_rows[0]["id"],
            "resource_id": gpu_train["id"],
            "user_id": user_id,
            "violation_details": {"detail": "GPU training node is missing Owner and Environment tags."},
            "severity": "high",
            "status": "active",
            "created_at": _iso(now - timedelta(days=5)),
        },
        {
            "id": f"{user_id}-policy-violation-3",
            "policy_id": policy_rows[1]["id"],
            "resource_id": azure_nsg["id"],
            "user_id": user_id,
            "violation_details": {"detail": "Inbound RDP is open to the public internet."},
            "severity": "critical",
            "status": "active",
            "created_at": _iso(now - timedelta(days=5)),
        },
        {
            "id": f"{user_id}-policy-violation-4",
            "policy_id": policy_rows[2]["id"],
            "resource_id": gpu_train["id"],
            "user_id": user_id,
            "violation_details": {"detail": "ML training cluster is running outside the approved office-hours window."},
            "severity": "medium",
            "status": "active",
            "created_at": _iso(now - timedelta(days=4)),
        },
        {
            "id": f"{user_id}-policy-violation-5",
            "policy_id": policy_rows[0]["id"],
            "resource_id": gcp_orphan_disk["id"],
            "user_id": user_id,
            "violation_details": {"detail": "Orphaned ETL disk has no owning team metadata."},
            "severity": "medium",
            "status": "active",
            "created_at": _iso(now - timedelta(days=3)),
        },
        {
            "id": f"{user_id}-policy-violation-6",
            "policy_id": policy_rows[0]["id"],
            "resource_id": gcp_bigquery["id"],
            "user_id": user_id,
            "violation_details": {"detail": "Warehouse jobs are missing CostCenter tagging for showback."},
            "severity": "low",
            "status": "active",
            "created_at": _iso(now - timedelta(days=2)),
        },
    ]

    policy_view = [
        {
            "id": "policy-owner-tags",
            "name": "Owner and cost center tags present",
            "status": "Fail",
            "severity": "High",
            "reason": "Audit archive, ML GPU training, orphan disks, and warehouse jobs are missing ownership metadata.",
            "framework": "FinOps",
        },
        {
            "id": "policy-public-rdp",
            "name": "No public RDP or SSH ingress",
            "status": "Fail",
            "severity": "Critical",
            "reason": "The Azure NSG exposes an administrative port to 0.0.0.0/0.",
            "framework": "CIS",
        },
        {
            "id": "policy-office-hours",
            "name": "Non-production compute follows office hours",
            "status": "Fail",
            "severity": "Medium",
            "reason": "ML training and GCP dev runner instances are still burning spend overnight.",
            "framework": "FinOps",
        },
        {
            "id": "policy-db-encryption",
            "name": "Production databases encrypted at rest",
            "status": "Pass",
            "severity": "Low",
            "reason": "Aurora, Azure SQL, and Cloud SQL all report encryption enabled.",
            "framework": "ISO 27001",
        },
        {
            "id": "policy-backup-retention",
            "name": "Backups retained for stateful workloads",
            "status": "Pass",
            "severity": "Low",
            "reason": "Production databases and analytics storage all meet the backup retention baseline.",
            "framework": "SOC2",
        },
        {
            "id": "policy-multi-az",
            "name": "Customer-facing services span multiple zones",
            "status": "Pass",
            "severity": "Low",
            "reason": "Primary customer workloads are spread across multiple zones and providers.",
            "framework": "Well-Architected",
        },
    ]

    tagging_assets = [
        {"id": audit_volume["id"], "name": audit_volume["resource_name"], "missing": ["Owner", "CostCenter"]},
        {"id": gpu_train["id"], "name": gpu_train["resource_name"], "missing": ["Owner", "Environment"]},
        {"id": azure_nsg["id"], "name": azure_nsg["resource_name"], "missing": ["Owner"]},
        {"id": gcp_orphan_disk["id"], "name": gcp_orphan_disk["resource_name"], "missing": ["Owner", "Environment"]},
        {"id": gcp_bigquery["id"], "name": gcp_bigquery["resource_name"], "missing": ["CostCenter"]},
    ]

    governance_data = {
        "score": {
            "value": 82,
            "trend": "up",
            "rating": "Good",
        },
        "tagging": {
            "missingTags": sum(len(asset["missing"]) for asset in tagging_assets),
            "costImpact": round(
                sum(
                    float(_find_resource(resources, key)["cost"])
                    for key in [
                        "aws-core-ebs-audit-archive",
                        "aws-ml-gpu-train",
                        "gcp-orphan-disk",
                        "gcp-bigquery",
                    ]
                ),
                2,
            ),
            "assets": tagging_assets,
        },
        "budget": {
            "projectedSpend": round(float(portfolio_forecast.get("forecast_eom_spend") or 0.0), 2),
            "budgetLimit": round(float(portfolio_forecast.get("budget_limit") or 0.0), 2),
            "burnRate": round(
                (
                    float(portfolio_forecast.get("forecast_eom_spend") or 0.0)
                    / max(float(portfolio_forecast.get("budget_limit") or 1.0), 1.0)
                ) * 100,
                1,
            ),
            "status": "Warning",
            "alert": "Portfolio is still within budget, but AWS core and GCP analytics workloads are pacing above their safe baseline.",
        },
        "officeHours": {
            "savings": 2080.0,
            "enabled": True,
            "recommendation": "Schedule ML notebooks, GPU training nodes, and GCP dev runners outside 08:00–20:00 IST to protect another $2.1k/month.",
        },
        "policies": policy_view,
        "trends": [
            {"date": "Apr 09", "score": 74},
            {"date": "Apr 10", "score": 76},
            {"date": "Apr 11", "score": 77},
            {"date": "Apr 12", "score": 79},
            {"date": "Apr 13", "score": 80},
            {"date": "Apr 14", "score": 81},
            {"date": "Apr 15", "score": 82},
        ],
        "frameworkSummary": [],
    }

    scan_history: List[Dict[str, Any]] = []
    for index, integration in enumerate(integrations.values(), start=1):
        integration_id = integration["id"]
        scoped_notifications = [
            notification
            for notification in notifications
            if (
                isinstance(notification.get("metadata"), dict)
                and notification["metadata"].get("integration_id") == integration_id
                and str(notification.get("status") or "").lower() == "pending"
            )
        ]
        scoped_resources = [
            resource for resource in resources if resource["integration_id"] == integration_id
        ]
        record: Dict[str, Any] = {
            "id": f"{integration_id}-scan-history",
            "user_id": user_id,
            "integration_id": integration_id,
            "status": "completed",
            "started_at": _iso(now - timedelta(hours=index * 8 + 1)),
            "completed_at": _iso(now - timedelta(hours=index * 8)),
            "created_at": _iso(now - timedelta(hours=index * 8)),
            "total_resources": len(scoped_resources),
            "waste_found": sum(1 for resource in scoped_resources if str(resource.get("status") or "").lower() in {"zombie", "waste", "non_compliant"}),
            "total_savings": round(sum(float(notification["metadata"].get("estimated_savings") or 0.0) for notification in scoped_notifications), 2),
            "scan_metadata": {
                "demo_dataset_version": DEMO_DATASET_VERSION,
                "provider": integration["provider"],
            },
        }
        scan_history.append(record)

    latest_scan = max(scan_history, key=lambda item: str(item.get("created_at") or ""))
    latest_scan["governance_data"] = governance_data

    return policy_rows, policy_violations, scan_history


def _build_reports(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    history_by_integration: Dict[str, List[Dict[str, Any]]],
    finance_settings: Dict[str, Any],
    today: date,
    now: datetime,
) -> List[Dict[str, Any]]:
    active_integrations = list(integrations.values())
    reports: List[Dict[str, Any]] = []
    report_specs = [
        ("monthly_executive_summary", date(today.year, today.month, 1), today, now - timedelta(days=1)),
        ("budget_variance", date(today.year, today.month, 1), today, now - timedelta(days=2)),
        ("provider_spend_summary", date(today.year, today.month, 1), today, now - timedelta(days=3)),
        (
            "board_pack",
            (date(today.year, today.month, 1) - timedelta(days=1)).replace(day=1),
            date(today.year, today.month, 1) - timedelta(days=1),
            now - timedelta(days=7),
        ),
    ]

    for index, (report_type, period_start, period_end, generated_at) in enumerate(report_specs, start=1):
        report = build_report_record(
            user_id=user_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            integrations=active_integrations,
            history_by_integration=history_by_integration,
            portfolio_budget_limit=float(finance_settings["portfolio_budget_limit"]),
            warning_threshold_pct=float(finance_settings["alert_thresholds"]["warning_pct"]),
            generated_at=generated_at,
        )
        report["id"] = f"{user_id}-report-{index}"
        report["created_at"] = _iso(generated_at)
        report["generated_at"] = _iso(generated_at)
        report["metadata"] = {
            **(report.get("metadata") if isinstance(report.get("metadata"), dict) else {}),
            "demo_dataset_version": DEMO_DATASET_VERSION,
        }
        reports.append(report)

    return reports


def _build_audit_logs(
    *,
    user_id: str,
    integrations: Dict[str, Dict[str, Any]],
    reports: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    entries = [
        ("USER_SYNC", "profile", {"source": "dashboard"}),
        ("INTEGRATIONS_VIEWED", "cloud_accounts", {"count": len(integrations)}),
        ("SCAN_TRIGGERED", integrations["aws-core"]["id"], {"provider": "aws"}),
        ("SCAN_COMPLETED", integrations["aws-core"]["id"], {"provider": "aws", "resources": 19, "waste_found": 3}),
        ("FINANCE_SETTINGS_UPDATED", "portfolio_budget", {"portfolio_budget_limit": 60000}),
        ("REPORT_GENERATED", reports[0]["id"], {"report_type": reports[0]["report_type"]}),
        ("ARCHITECTURE_VIEWED", integrations["azure-apps"]["id"], {"provider": "azure"}),
        ("AI_RECOMMENDATION_REVIEWED", "pending_actions", {"approved": 1, "rejected": 1}),
    ]

    rows: List[Dict[str, Any]] = []
    for index, (action_type, resource_target, metadata) in enumerate(entries, start=1):
        rows.append(
            {
                "id": f"{user_id}-audit-{index}",
                "user_id": user_id,
                "action_type": action_type,
                "resource_target": resource_target,
                "metadata": metadata,
                "created_at": _iso(now - timedelta(hours=index * 3)),
            }
        )
    return rows


def build_demo_portfolio_bundle(
    user_id: str,
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> Dict[str, Any]:
    current_now = (now or _utc_now()).astimezone(timezone.utc)
    current_today = today or current_now.date()
    finance_settings = dict(DEFAULT_FINANCE_SETTINGS)

    integrations = _integration_index(user_id, current_now)
    resources = _build_demo_resources(user_id, integrations)
    _attach_demo_commitments(integrations=integrations, resources=resources, now=current_now)

    history_by_integration: Dict[str, List[Dict[str, Any]]] = {}
    resources_by_integration: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for resource in resources:
        resources_by_integration[str(resource["integration_id"])].append(resource)
    for integration in integrations.values():
        history_by_integration[integration["id"]] = _build_daily_history_rows(
            integration=integration,
            resources=resources_by_integration[integration["id"]],
            today=current_today,
        )

    notifications = _build_pending_notifications(
        user_id=user_id,
        integrations=integrations,
        resources=resources,
        now=current_now,
    )
    waste_distribution = _build_waste_distribution(
        user_id=user_id,
        integrations=integrations,
        notifications=notifications,
    )
    dashboard_stats = _build_dashboard_stats(
        user_id=user_id,
        integrations=integrations,
        resources=resources,
        notifications=notifications,
    )
    budget_events, portfolio_forecast, integration_forecasts = _build_budget_events(
        user_id=user_id,
        integrations=integrations,
        history_by_integration=history_by_integration,
        finance_settings=finance_settings,
        today=current_today,
    )
    governance_policies, policy_violations, scan_history = _build_governance_records(
        user_id=user_id,
        integrations=integrations,
        resources=resources,
        notifications=notifications,
        portfolio_forecast=portfolio_forecast,
        now=current_now,
    )
    reports = _build_reports(
        user_id=user_id,
        integrations=integrations,
        history_by_integration=history_by_integration,
        finance_settings=finance_settings,
        today=current_today,
        now=current_now,
    )
    audit_logs = _build_audit_logs(
        user_id=user_id,
        integrations=integrations,
        reports=reports,
        now=current_now,
    )

    return {
        "dataset_version": DEMO_DATASET_VERSION,
        "finance_settings": finance_settings,
        "integrations": list(integrations.values()),
        "resources": resources,
        "daily_spend_history_by_integration": history_by_integration,
        "dashboard_stats": dashboard_stats,
        "waste_distribution": waste_distribution,
        "notifications": notifications,
        "budget_events": budget_events,
        "portfolio_forecast": portfolio_forecast,
        "integration_forecasts": integration_forecasts,
        "governance_policies": governance_policies,
        "policy_violations": policy_violations,
        "scan_history": scan_history,
        "reports": reports,
        "audit_logs": audit_logs,
    }
