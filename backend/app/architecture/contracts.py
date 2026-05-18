"""
Graph JSON contracts for AWS Architecture diagrams.

These dataclasses define the wire format for the interactive React Flow
frontend. The existing Mermaid renderers remain untouched — graph JSON
is produced in parallel from the same RegionTopology.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """Single node in the interactive architecture graph."""
    id: str                              # Stable, deterministic (sanitized)
    cloud_resource_id: str               # Raw ARN / resource-id
    name: str                            # Human-readable
    service_type: str                    # Canonical kind: ec2, rds, vpc, s3, …
    region: str
    cost: float
    status: str                          # Active, Zombie, Stopped
    waste_type: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    severity: str = "none"               # none, low, medium, high, critical
    drilldown_key: Optional[str] = None  # vpc_id, cluster, service group id
    parent: Optional[str] = None         # id of containing group node (VPC / subnet / region)
    node_type: str = "resource"          # resource, group, standalone

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "cloud_resource_id": self.cloud_resource_id,
            "name": self.name,
            "service_type": self.service_type,
            "region": self.region,
            "cost": round(self.cost, 2),
            "status": self.status,
            "waste_type": self.waste_type,
            "tags": self.tags,
            "metadata": self.metadata,
            "severity": self.severity,
            "drilldown_key": self.drilldown_key,
            "parent": self.parent,
            "node_type": self.node_type,
        }


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

@dataclass
class GraphEdge:
    """Directed edge between two graph nodes."""
    source: str                          # Node id
    target: str                          # Node id
    kind: str                            # contains, routes_to, attached_to, security_applies_to
    label: Optional[str] = None
    style: str = "solid"                 # solid, dotted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "label": self.label,
            "style": self.style,
        }


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

@dataclass
class CoverageReport:
    """Which AWS services are detected, missing, or access-denied."""
    detected_services: List[str] = field(default_factory=list)
    missing_services: List[str] = field(default_factory=list)
    access_denied_services: List[str] = field(default_factory=list)
    microservices_available: bool = False
    warnings: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_services": self.detected_services,
            "missing_services": self.missing_services,
            "access_denied_services": self.access_denied_services,
            "microservices_available": self.microservices_available,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Graph Data (nodes + edges bundle)
# ---------------------------------------------------------------------------

@dataclass
class GraphData:
    """Bundle of nodes and edges for a single view."""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


# ---------------------------------------------------------------------------
# View (graph + optional mermaid)
# ---------------------------------------------------------------------------

@dataclass
class ViewData:
    """One rendered view with both graph JSON and Mermaid string."""
    graph: GraphData = field(default_factory=GraphData)
    mermaid: str = ""
    warnings: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph": self.graph.to_dict(),
            "mermaid": self.mermaid,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# VPC index entry
# ---------------------------------------------------------------------------

@dataclass
class VpcIndexEntry:
    """Summary of a single VPC for the sidebar index."""
    vpc_id: str
    name: str
    monthly_cost: float
    waste_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vpc_id": self.vpc_id,
            "name": self.name,
            "monthly_cost": round(self.monthly_cost, 2),
            "waste_cost": round(self.waste_cost, 2),
        }


# ---------------------------------------------------------------------------
# Region-level result
# ---------------------------------------------------------------------------

@dataclass
class RegionGraphResult:
    """Full architecture data for one AWS region."""
    region: str
    coverage: CoverageReport = field(default_factory=CoverageReport)
    views: Dict[str, ViewData] = field(default_factory=dict)
    vpc_index: List[VpcIndexEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region": self.region,
            "coverage": self.coverage.to_dict(),
            "views": {k: v.to_dict() for k, v in self.views.items()},
            "vpc_index": [v.to_dict() for v in self.vpc_index],
        }


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

@dataclass
class GraphResponse:
    """Top-level API response for GET /api/architecture/aws/graph."""
    provider: str
    integration_id: str
    generated_at: str
    regions: List[RegionGraphResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "integration_id": self.integration_id,
            "generated_at": self.generated_at,
            "regions": [r.to_dict() for r in self.regions],
        }


# ---------------------------------------------------------------------------
# Proposed Architecture contracts
# ---------------------------------------------------------------------------

@dataclass
class ChangeItem:
    """Single change in a proposed architecture."""
    resource_id: str
    resource_name: str
    service_type: str
    change_type: str               # "terminate", "downsize", "migrate", "add_replica", "enable_multi_az"
    current_state: str             # e.g. "m5.xlarge"
    proposed_state: str            # e.g. "m5.large"
    monthly_savings: float
    risk_level: str                # "low", "medium", "high"
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "service_type": self.service_type,
            "change_type": self.change_type,
            "current_state": self.current_state,
            "proposed_state": self.proposed_state,
            "monthly_savings": round(self.monthly_savings, 2),
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
        }


@dataclass
class ProposedResult:
    """API response for POST /api/architecture/aws/proposed."""
    mode: str                      # "cost_optimized" | "reliability_security_optimized"
    integration_id: str
    region: str
    proposed_mermaid: str
    change_list: List[ChangeItem] = field(default_factory=list)
    estimated_savings: float = 0.0
    risk_tradeoffs: str = ""
    warnings: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "integration_id": self.integration_id,
            "region": self.region,
            "proposed_mermaid": self.proposed_mermaid,
            "change_list": [c.to_dict() for c in self.change_list],
            "estimated_savings": round(self.estimated_savings, 2),
            "risk_tradeoffs": self.risk_tradeoffs,
            "warnings": self.warnings,
        }
