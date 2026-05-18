"""
AWS graph builder.

Converts a RegionTopology into graph JSON (nodes + edges) for the
interactive React Flow frontend. Also produces coverage reports.

Consumes the same topology model as the Mermaid renderers — no
duplication of grouping/placement logic.
"""

import math
from typing import Any, Dict, List, Optional, Set

from .contracts import (
    CoverageReport,
    GraphData,
    GraphEdge,
    GraphNode,
    RegionGraphResult,
    VpcIndexEntry,
    ViewData,
)
from .models import (
    IgwNode,
    RegionTopology,
    ResourceNode,
    StandaloneGroup,
    VpcTopology,
)
from .sanitizer import sanitize_node_id


# ---------------------------------------------------------------------------
# Known AWS services (used for coverage detection)
# ---------------------------------------------------------------------------

_ALL_SERVICES = [
    "ec2", "rds", "s3", "lambda", "vpc", "subnet", "igw",
    "ebs", "eip", "sg", "iam",
    "eks", "ecs", "alb", "cloudtrail", "config",
]

_MICROSERVICES_KINDS = {"eks", "ecs"}


# ---------------------------------------------------------------------------
# Cost severity bands
# ---------------------------------------------------------------------------

def _cost_severity(cost: float) -> str:
    if cost > 2000:
        return "critical"
    if cost > 500:
        return "high"
    if cost > 100:
        return "medium"
    if cost > 0:
        return "low"
    return "none"


def _waste_severity(node: ResourceNode) -> str:
    """Compute severity from waste status."""
    status = node.status.lower()
    if status in ("zombie", "waste"):
        return "high"
    if status == "stopped":
        return "medium"
    if node.waste_type:
        return "medium"
    return _cost_severity(node.cost)


# ---------------------------------------------------------------------------
# Sanitize metadata for JSON serialization
# ---------------------------------------------------------------------------

_MAX_META_DEPTH = 2
_MAX_META_DICT_KEYS = 30
_MAX_META_LIST_ITEMS = 30
_MAX_META_STR_LEN = 300


def _safe_primitive(value: Any) -> Any:
    if isinstance(value, str):
        return value[:_MAX_META_STR_LEN]
    if isinstance(value, (bool, type(None), int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _safe_metadata_value(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_META_DEPTH:
        return "[truncated]"

    primitive = _safe_primitive(value)
    if primitive is not None or value is None:
        return primitive

    if isinstance(value, list):
        items = []
        for item in value[:_MAX_META_LIST_ITEMS]:
            normalized = _safe_metadata_value(item, depth + 1)
            if normalized is not None:
                items.append(normalized)
        if len(value) > _MAX_META_LIST_ITEMS:
            items.append("[truncated]")
        return items

    if isinstance(value, dict):
        safe_dict: Dict[str, Any] = {}
        count = 0
        for k, v in value.items():
            if count >= _MAX_META_DICT_KEYS:
                safe_dict["__truncated__"] = True
                break
            key = str(k)
            if key.startswith("_"):
                continue
            safe_val = _safe_metadata_value(v, depth + 1)
            if safe_val is not None:
                safe_dict[key[:80]] = safe_val
                count += 1
        return safe_dict

    return str(value)[:_MAX_META_STR_LEN]


def _safe_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Strip very large/non-serializable fields and bound payload size."""
    normalized = _safe_metadata_value(meta, depth=0)
    if isinstance(normalized, dict):
        return normalized
    return {}


# ---------------------------------------------------------------------------
# Builder: resource node -> graph node
# ---------------------------------------------------------------------------

def _resource_to_graph_node(
    r: ResourceNode,
    region: str,
    parent_id: Optional[str] = None,
) -> GraphNode:
    return GraphNode(
        id=sanitize_node_id(r.cloud_resource_id, r.service_kind),
        cloud_resource_id=r.cloud_resource_id,
        name=r.resource_name,
        service_type=r.service_kind,
        region=region,
        cost=r.cost,
        status=r.status,
        waste_type=r.waste_type,
        tags={},  # Tags not stored in ResourceNode today; placeholder
        metadata=_safe_metadata(r.metadata),
        severity=_waste_severity(r),
        drilldown_key=r.vpc_id,
        parent=parent_id,
        node_type="resource",
    )


# ---------------------------------------------------------------------------
# Public: Build topology summary graph
# ---------------------------------------------------------------------------

def build_topology_graph(topology: RegionTopology) -> GraphData:
    """
    Build a summary-level graph: VPCs as group nodes, standalone
    as collapsed nodes, IGWs as nodes, with containment/routes edges.
    """
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    region = topology.region

    # Region-level group node
    region_nid = sanitize_node_id(region, "reg")
    nodes.append(GraphNode(
        id=region_nid,
        cloud_resource_id=region,
        name=region,
        service_type="region",
        region=region,
        cost=topology.total_cost,
        status="Active",
        severity=_cost_severity(topology.total_cost),
        node_type="group",
    ))

    # VPC group nodes
    for vpc in topology.vpcs:
        vpc_nid = sanitize_node_id(vpc.vpc_id, "vpc")
        nodes.append(GraphNode(
            id=vpc_nid,
            cloud_resource_id=vpc.vpc_id,
            name=vpc.name,
            service_type="vpc",
            region=region,
            cost=vpc.monthly_cost,
            status="Active",
            severity=_cost_severity(vpc.monthly_cost),
            drilldown_key=vpc.vpc_id,
            parent=region_nid,
            node_type="group",
            metadata={"cidr_block": vpc.cidr_block, "resource_counts": vpc.resource_counts},
        ))
        edges.append(GraphEdge(
            source=region_nid,
            target=vpc_nid,
            kind="contains",
            style="solid",
        ))

    # IGW nodes
    for igw in topology.igws:
        igw_nid = sanitize_node_id(igw.igw_id, "igw")
        nodes.append(GraphNode(
            id=igw_nid,
            cloud_resource_id=igw.igw_id,
            name=igw.name,
            service_type="igw",
            region=region,
            cost=0,
            status=igw.status,
            severity="none",
            node_type="resource",
        ))

        # IGW -> VPC edges (only if VPC exists in graph)
        vpc_ids_in_graph = {n.cloud_resource_id for n in nodes if n.service_type == "vpc"}
        for vid in igw.attached_vpc_ids:
            if vid in vpc_ids_in_graph:
                vpc_nid = sanitize_node_id(vid, "vpc")
                edges.append(GraphEdge(
                    source=igw_nid,
                    target=vpc_nid,
                    kind="routes_to",
                    style="solid",
                ))

    # Standalone group nodes
    _add_standalone_nodes(nodes, edges, topology.standalone, region, region_nid)

    return GraphData(nodes=nodes, edges=edges)


def _add_standalone_nodes(
    nodes: List[GraphNode],
    edges: List[GraphEdge],
    standalone: StandaloneGroup,
    region: str,
    parent_id: str,
) -> None:
    """Add collapsed standalone service groups (S3, Lambda, IAM, other)."""
    groups = [
        ("s3", standalone.s3_buckets, "S3 Buckets"),
        ("lambda", standalone.lambda_functions, "Lambda Functions"),
        ("iam", standalone.iam_entities, "IAM Entities"),
        ("other", standalone.other, "Other Resources"),
    ]
    for kind, items, label in groups:
        if not items:
            continue
        group_nid = sanitize_node_id(f"{kind}_group", "sa")
        total_cost = sum(r.cost for r in items)
        flagged_items = [
            r for r in items
            if r.waste_type or str(r.status).lower() in {"zombie", "idle/zombie", "waste", "idle", "non_compliant", "stopped"}
        ]
        group_status = "Zombie" if flagged_items else "Active"
        group_severity = "high" if flagged_items else _cost_severity(total_cost)
        nodes.append(GraphNode(
            id=group_nid,
            cloud_resource_id=f"standalone_{kind}",
            name=f"{len(items)} {label}",
            service_type=kind,
            region=region,
            cost=total_cost,
            status=group_status,
            waste_type="mixed_waste" if flagged_items else None,
            severity=group_severity,
            node_type="standalone",
            parent=parent_id,
            metadata={"count": len(items), "flagged_count": len(flagged_items)},
        ))
        edges.append(GraphEdge(
            source=parent_id,
            target=group_nid,
            kind="contains",
            style="dotted",
        ))


# ---------------------------------------------------------------------------
# Public: Build cost hotspots graph
# ---------------------------------------------------------------------------

def build_hotspot_graph(topology: RegionTopology) -> GraphData:
    """
    Same structure as topology summary but severity is purely cost-based.
    """
    graph = build_topology_graph(topology)

    # Override severity on all nodes to purely reflect cost bands
    for node in graph.nodes:
        node.severity = _cost_severity(node.cost)

    return graph


# ---------------------------------------------------------------------------
# Public: Build VPC detail graph (drilldown)
# ---------------------------------------------------------------------------

MAX_DETAIL_NODES = 250

def build_vpc_detail_graph(
    topology: RegionTopology,
    vpc_id: str,
) -> Optional[GraphData]:
    """
    Full resource-level graph for a single VPC.
    Returns None if the VPC is not found.
    """
    target_vpc: Optional[VpcTopology] = None
    for v in topology.vpcs:
        if v.vpc_id == vpc_id:
            target_vpc = v
            break

    if target_vpc is None:
        return None

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    region = topology.region
    node_id_set: Set[str] = set()

    # VPC group node
    vpc_nid = sanitize_node_id(target_vpc.vpc_id, "vpc")
    nodes.append(GraphNode(
        id=vpc_nid,
        cloud_resource_id=target_vpc.vpc_id,
        name=target_vpc.name,
        service_type="vpc",
        region=region,
        cost=target_vpc.monthly_cost,
        status="Active",
        severity=_cost_severity(target_vpc.monthly_cost),
        drilldown_key=target_vpc.vpc_id,
        node_type="group",
        metadata={"cidr_block": target_vpc.cidr_block, "resource_counts": target_vpc.resource_counts},
    ))
    node_id_set.add(vpc_nid)

    # Subnet group nodes + their resources
    for sn in target_vpc.subnets:
        sn_nid = sanitize_node_id(sn.subnet_id, "sn")
        nodes.append(GraphNode(
            id=sn_nid,
            cloud_resource_id=sn.subnet_id,
            name=sn.name,
            service_type="subnet",
            region=region,
            cost=sum(r.cost for r in sn.resources),
            status="Active",
            severity="none",
            parent=vpc_nid,
            node_type="group",
            metadata={"cidr_block": sn.cidr_block, "availability_zone": sn.availability_zone},
        ))
        node_id_set.add(sn_nid)
        edges.append(GraphEdge(source=vpc_nid, target=sn_nid, kind="contains", style="solid"))

        for r in sn.resources:
            gn = _resource_to_graph_node(r, region, parent_id=sn_nid)
            nodes.append(gn)
            node_id_set.add(gn.id)

    # Unplaced resources
    for r in target_vpc.unplaced_resources:
        gn = _resource_to_graph_node(r, region, parent_id=vpc_nid)
        nodes.append(gn)
        node_id_set.add(gn.id)

    # Resource relationship edges
    for gn in nodes:
        if gn.node_type != "resource":
            continue

        # EBS -> attached EC2
        if gn.service_type == "ebs" and gn.metadata.get("attached_to"):
            target_nid = sanitize_node_id(gn.metadata["attached_to"], "ec2")
            if target_nid in node_id_set:
                edges.append(GraphEdge(
                    source=gn.id, target=target_nid,
                    kind="attached_to", style="dotted",
                ))

        # EIP -> associated EC2
        if gn.service_type == "eip" and gn.metadata.get("instance_id"):
            target_nid = sanitize_node_id(gn.metadata["instance_id"], "ec2")
            if target_nid in node_id_set:
                edges.append(GraphEdge(
                    source=gn.id, target=target_nid,
                    kind="attached_to", style="solid",
                ))

    # IGW edges into this VPC
    for igw in topology.igws:
        if vpc_id in igw.attached_vpc_ids:
            igw_nid = sanitize_node_id(igw.igw_id, "igw")
            nodes.append(GraphNode(
                id=igw_nid,
                cloud_resource_id=igw.igw_id,
                name=igw.name,
                service_type="igw",
                region=region,
                cost=0,
                status=igw.status,
                severity="none",
                node_type="resource",
            ))
            node_id_set.add(igw_nid)
            edges.append(GraphEdge(
                source=igw_nid, target=vpc_nid,
                kind="routes_to", style="solid",
            ))

    # Truncation guard
    if len(nodes) > MAX_DETAIL_NODES:
        nodes = nodes[:MAX_DETAIL_NODES]
        node_id_set = {n.id for n in nodes}
        edges = [e for e in edges if e.source in node_id_set and e.target in node_id_set]

    return GraphData(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Public: Coverage report
# ---------------------------------------------------------------------------

def build_coverage(
    resources: List[Dict[str, Any]],
    permission_alerts: Optional[List[Dict[str, Any]]] = None,
) -> CoverageReport:
    """
    Analyze which services are present in the scanned resources.
    Cross-reference with known AWS service list.
    """
    from . import aws_field_adapter as fa

    detected_kinds: Set[str] = set()
    for row in resources:
        kind = fa.get_service_kind(row)
        if kind != "unknown":
            detected_kinds.add(kind)

    # Determine missing
    all_set = set(_ALL_SERVICES)
    detected = sorted(detected_kinds & all_set)
    missing = sorted(all_set - detected_kinds)

    # Access denied from permission alerts
    access_denied: List[str] = []
    if permission_alerts:
        for alert in permission_alerts:
            meta = alert.get("metadata") or {}
            missing_svcs = meta.get("missing_services", [])
            for svc in missing_svcs:
                svc_lower = svc.lower()
                if svc_lower not in access_denied:
                    access_denied.append(svc_lower)

    # Microservices availability
    microservices_available = bool(detected_kinds & _MICROSERVICES_KINDS)

    warnings: List[Dict[str, str]] = []
    if not microservices_available:
        warnings.append({
            "type": "microservices_unavailable",
            "message": "Microservices view unavailable: requires EKS or ECS scan permissions",
        })

    return CoverageReport(
        detected_services=detected,
        missing_services=missing,
        access_denied_services=sorted(access_denied),
        microservices_available=microservices_available,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Public: Assemble full RegionGraphResult
# ---------------------------------------------------------------------------

def build_region_graph_result(
    topology: RegionTopology,
    resources: List[Dict[str, Any]],
    views_requested: str = "all",
    vpc_id: Optional[str] = None,
    permission_alerts: Optional[List[Dict[str, Any]]] = None,
) -> RegionGraphResult:
    """
    Build the full region result with graph JSON, Mermaid, and coverage.
    
    views_requested: "all" | "topology_summary" | "cost_hotspots" | "microservices" | "vpc_detail"
    """
    # Lazily import mermaid renderers to avoid circular deps
    from .aws_renderers import render_topology_summary, render_cost_hotspots, render_vpc_detail

    region = topology.region
    coverage = build_coverage(resources, permission_alerts)

    views: Dict[str, ViewData] = {}

    should_include = lambda v: views_requested in ("all", v)

    # Topology summary
    if should_include("topology_summary"):
        graph = build_topology_graph(topology)
        mermaid_result = render_topology_summary(topology)
        views["topology_summary"] = ViewData(
            graph=graph,
            mermaid=mermaid_result.mermaid,
            warnings=mermaid_result.warnings,
        )

    # Cost hotspots
    if should_include("cost_hotspots"):
        graph = build_hotspot_graph(topology)
        mermaid_result = render_cost_hotspots(topology)
        views["cost_hotspots"] = ViewData(
            graph=graph,
            mermaid=mermaid_result.mermaid,
            warnings=mermaid_result.warnings,
        )

    # Microservices
    if should_include("microservices"):
        if coverage.microservices_available:
            # Future: build microservices graph from EKS/ECS data
            views["microservices"] = ViewData(
                graph=GraphData(),
                mermaid="",
                warnings=[{
                    "type": "microservices_placeholder",
                    "message": "Microservices graph will be populated when EKS/ECS scanner is available",
                }],
            )
        else:
            views["microservices"] = ViewData(
                graph=GraphData(),
                mermaid="",
                warnings=coverage.warnings,
            )

    # VPC detail
    if should_include("vpc_detail") and vpc_id:
        detail_graph = build_vpc_detail_graph(topology, vpc_id)
        mermaid_detail = render_vpc_detail(topology, vpc_id)
        if detail_graph is not None:
            detail_warnings = list(mermaid_detail.warnings if mermaid_detail else [])
            target_vpc = next((v for v in topology.vpcs if v.vpc_id == vpc_id), None)
            if target_vpc is not None:
                raw_node_count = (
                    1  # VPC group
                    + len(target_vpc.subnets)
                    + len(target_vpc.unplaced_resources)
                    + sum(len(sn.resources) for sn in target_vpc.subnets)
                    + sum(1 for igw in topology.igws if vpc_id in igw.attached_vpc_ids)
                )
                if raw_node_count > MAX_DETAIL_NODES:
                    detail_warnings.append({
                        "type": "graph_truncated",
                        "message": (
                            f"VPC detail graph truncated to {MAX_DETAIL_NODES} nodes "
                            f"from {raw_node_count} to keep rendering stable."
                        ),
                    })

            views["vpc_detail"] = ViewData(
                graph=detail_graph,
                mermaid=mermaid_detail.mermaid if mermaid_detail else "",
                warnings=detail_warnings,
            )
        else:
            views["vpc_detail"] = ViewData(
                graph=GraphData(),
                mermaid="",
                warnings=[{"type": "vpc_not_found", "vpc_id": vpc_id}],
            )

    # VPC index
    vpc_index = [
        VpcIndexEntry(
            vpc_id=vpc.vpc_id,
            name=vpc.name,
            monthly_cost=vpc.monthly_cost,
            waste_cost=vpc.waste_cost,
        )
        for vpc in topology.vpcs
    ]

    return RegionGraphResult(
        region=region,
        coverage=coverage,
        views=views,
        vpc_index=vpc_index,
    )
