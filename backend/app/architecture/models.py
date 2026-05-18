"""
Architecture result models.

Typed structures for topology data and API responses.
Uses dataclasses (consistent with existing ScannedResource pattern).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ArchitectureViewResult:
    """Single rendered view (topology summary, cost hotspots, or VPC detail)."""
    mermaid: str
    warnings: List[Dict[str, str]] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"mermaid": self.mermaid, "warnings": self.warnings, "stats": self.stats}


@dataclass
class VpcIndexEntry:
    """Summary entry for a VPC in the vpc_index list."""
    vpc_id: str
    name: str
    cidr_block: str
    monthly_cost: float
    waste_cost: float
    resource_counts: Dict[str, int] = field(default_factory=dict)
    subnet_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vpc_id": self.vpc_id,
            "name": self.name,
            "cidr_block": self.cidr_block,
            "monthly_cost": round(self.monthly_cost, 2),
            "waste_cost": round(self.waste_cost, 2),
            "resource_counts": self.resource_counts,
            "subnet_count": self.subnet_count,
        }


@dataclass
class ArchitectureRegionResult:
    """Architecture data for a single AWS region."""
    region: str
    total_cost: float = 0.0
    total_waste: float = 0.0
    resource_count: int = 0
    views: Dict[str, ArchitectureViewResult] = field(default_factory=dict)
    vpc_index: List[VpcIndexEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region": self.region,
            "total_cost": round(self.total_cost, 2),
            "total_waste": round(self.total_waste, 2),
            "resource_count": self.resource_count,
            "views": {k: v.to_dict() for k, v in self.views.items()},
            "vpc_index": [v.to_dict() for v in self.vpc_index],
        }


@dataclass
class ArchitectureResult:
    """Top-level API response for architecture diagrams."""
    provider: str
    integration_id: str
    generated_at: str
    regions: List[ArchitectureRegionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "integration_id": self.integration_id,
            "generated_at": self.generated_at,
            "regions": [r.to_dict() for r in self.regions],
        }


# ---------------------------------------------------------------------------
# Internal topology structures (used by topology builder, consumed by renderers)
# ---------------------------------------------------------------------------

@dataclass
class ResourceNode:
    """Normalized resource for diagram rendering."""
    cloud_resource_id: str
    resource_name: str
    service_kind: str         # "ec2", "rds", "ebs", "eip", "sg", etc.
    service_type: str         # Original e.g. "AWS EC2 Instance"
    cost: float
    status: str               # Active, Zombie, Stopped
    waste_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Resolved relationships (filled by topology builder)
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    sg_ids: List[str] = field(default_factory=list)
    attached_instance_id: Optional[str] = None


@dataclass
class SubnetNode:
    """Subnet as a container for resources."""
    subnet_id: str
    name: str
    cidr_block: str
    availability_zone: str
    vpc_id: str
    resources: List[ResourceNode] = field(default_factory=list)


@dataclass
class VpcTopology:
    """Full topology within a single VPC."""
    vpc_id: str
    name: str
    cidr_block: str
    subnets: List[SubnetNode] = field(default_factory=list)
    # Resources in VPC but not assignable to a specific subnet
    unplaced_resources: List[ResourceNode] = field(default_factory=list)
    monthly_cost: float = 0.0
    waste_cost: float = 0.0
    resource_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class IgwNode:
    """Internet Gateway with VPC attachments."""
    igw_id: str
    name: str
    attached_vpc_ids: List[str] = field(default_factory=list)
    status: str = "Active"


@dataclass
class StandaloneGroup:
    """Resources not in any VPC (S3, Lambda, IAM, etc.)."""
    s3_buckets: List[ResourceNode] = field(default_factory=list)
    lambda_functions: List[ResourceNode] = field(default_factory=list)
    iam_entities: List[ResourceNode] = field(default_factory=list)
    other: List[ResourceNode] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.s3_buckets) + len(self.lambda_functions) + len(self.iam_entities) + len(self.other)

    @property
    def total_cost(self) -> float:
        return sum(
            r.cost
            for group in (self.s3_buckets, self.lambda_functions, self.iam_entities, self.other)
            for r in group
        )


@dataclass
class RegionTopology:
    """Complete topology for one AWS region."""
    region: str
    vpcs: List[VpcTopology] = field(default_factory=list)
    igws: List[IgwNode] = field(default_factory=list)
    standalone: StandaloneGroup = field(default_factory=StandaloneGroup)
    warnings: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(v.monthly_cost for v in self.vpcs) + self.standalone.total_cost

    @property
    def total_waste(self) -> float:
        return sum(v.waste_cost for v in self.vpcs)

    @property
    def resource_count(self) -> int:
        count = self.standalone.total_count
        for vpc in self.vpcs:
            for s in vpc.subnets:
                count += len(s.resources)
            count += len(vpc.unplaced_resources)
        return count
