"""
AWS Mermaid diagram renderers.

Three views derived from the SAME RegionTopology:
  A) render_topology_summary  — bird's-eye collapsed VPCs
  B) render_cost_hotspots     — same layout, color-coded by spend
  C) render_vpc_detail        — full resource-level inside one VPC
"""

from typing import Dict, List, Optional

from . import aws_field_adapter as fa
from .models import (
    ArchitectureViewResult,
    IgwNode,
    RegionTopology,
    ResourceNode,
    StandaloneGroup,
    SubnetNode,
    VpcTopology,
)
from .sanitizer import sanitize_label, sanitize_node_id

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SUMMARY_VPCS = 50
MAX_DETAIL_NODES = 250
MAX_DETAIL_EDGES = 400

STATUS_EMOJI = {
    "active": "🟢",
    "zombie": "🔴",
    "stopped": "🟡",
}

SERVICE_EMOJI = {
    "ec2": "💻",
    "rds": "🗄️",
    "ebs": "💾",
    "eip": "🔗",
    "s3": "📂",
    "lambda": "⚡",
    "iam": "👤",
    "igw": "🌐",
    "sg": "🛡️",
    "vpc": "🔒",
    "subnet": "📦",
}

STYLE_DEFS = """
    classDef active fill:#065f46,stroke:#10b981,color:#ecfdf5
    classDef zombie fill:#7f1d1d,stroke:#ef4444,color:#fef2f2
    classDef stopped fill:#78350f,stroke:#f59e0b,color:#fffbeb
    classDef unknown fill:#374151,stroke:#6b7280,color:#f3f4f6
    classDef hotspot_green fill:#065f46,stroke:#10b981,color:#ecfdf5
    classDef hotspot_yellow fill:#713f12,stroke:#eab308,color:#fef9c3
    classDef hotspot_orange fill:#7c2d12,stroke:#f97316,color:#fff7ed
    classDef hotspot_red fill:#7f1d1d,stroke:#ef4444,color:#fef2f2
"""


def _status_class(status: str) -> str:
    s = status.lower()
    if s in ("zombie", "waste"):
        return ":::zombie"
    if s == "stopped":
        return ":::stopped"
    if s == "active":
        return ":::active"
    return ":::unknown"


def _hotspot_class(cost: float) -> str:
    if cost > 2000:
        return ":::hotspot_red"
    if cost > 500:
        return ":::hotspot_orange"
    if cost > 100:
        return ":::hotspot_yellow"
    return ":::hotspot_green"


def _fmt_cost(cost: float) -> str:
    if cost >= 1000:
        return f"${cost:,.0f}/mo"
    if cost > 0:
        return f"${cost:.0f}/mo"
    return "$0/mo"


def _waste_badge(waste: float) -> str:
    if waste > 0:
        return f" | ⚠️ ${waste:.0f} waste"
    return ""


# ---------------------------------------------------------------------------
# Renderer A: Topology Summary
# ---------------------------------------------------------------------------

def render_topology_summary(topology: RegionTopology) -> ArchitectureViewResult:
    """
    Bird's-eye view: VPCs as collapsed boxes with resource counts and cost.
    No individual resources shown.
    """
    lines: List[str] = ["flowchart TD"]
    warnings = list(topology.warnings)
    node_count = 0
    edge_count = 0

    vpcs = topology.vpcs
    if len(vpcs) > MAX_SUMMARY_VPCS:
        warnings.append({
            "type": "vpcs_truncated",
            "total": str(len(vpcs)),
            "shown": str(MAX_SUMMARY_VPCS),
        })
        vpcs = vpcs[:MAX_SUMMARY_VPCS]

    # Region subgraph
    region_id = sanitize_node_id(topology.region, "reg")
    region_label = sanitize_label(f"🌍 {topology.region}")
    lines.append(f'    subgraph {region_id}["{region_label}"]')

    for vpc in vpcs:
        vpc_nid = sanitize_node_id(vpc.vpc_id, "vpc")
        # Build VPC label
        counts = _format_counts(vpc.resource_counts)
        vpc_label = sanitize_label(
            f"🔒 {vpc.name}\\n"
            f"{counts}\\n"
            f"{_fmt_cost(vpc.monthly_cost)}{_waste_badge(vpc.waste_cost)}"
        )
        lines.append(f'        {vpc_nid}["{vpc_label}"]{_status_class("active")}')
        node_count += 1

    lines.append("    end")

    # IGW edges
    for igw in topology.igws:
        igw_nid = sanitize_node_id(igw.igw_id, "igw")
        igw_label = sanitize_label(f"🌐 {igw.name}")
        lines.append(f'    {igw_nid}["{igw_label}"]')
        node_count += 1
        for vid in igw.attached_vpc_ids:
            vpc_nid = sanitize_node_id(vid, "vpc")
            # Only create edge if VPC node exists
            if any(v.vpc_id == vid for v in vpcs):
                lines.append(f"    {igw_nid} --> {vpc_nid}")
                edge_count += 1

    # Standalone group
    _render_standalone_summary(lines, topology.standalone)
    node_count += 1 if topology.standalone.total_count > 0 else 0

    lines.append(STYLE_DEFS)

    return ArchitectureViewResult(
        mermaid="\n".join(lines),
        warnings=warnings,
        stats={"nodes": node_count, "edges": edge_count, "subgraphs": 1 + len(vpcs)},
    )


# ---------------------------------------------------------------------------
# Renderer B: Cost Hotspots
# ---------------------------------------------------------------------------

def render_cost_hotspots(topology: RegionTopology) -> ArchitectureViewResult:
    """
    Same VPC layout but color-coded by monthly cost band.
    Highlights where money is burning.
    """
    lines: List[str] = ["flowchart TD"]
    warnings = list(topology.warnings)
    node_count = 0

    vpcs = topology.vpcs
    if len(vpcs) > MAX_SUMMARY_VPCS:
        warnings.append({
            "type": "vpcs_truncated",
            "total": str(len(vpcs)),
            "shown": str(MAX_SUMMARY_VPCS),
        })
        vpcs = vpcs[:MAX_SUMMARY_VPCS]

    total_cost = sum(v.monthly_cost for v in vpcs) + topology.standalone.total_cost
    region_id = sanitize_node_id(topology.region, "reg")
    region_label = sanitize_label(
        f"🌍 {topology.region} — Total: {_fmt_cost(total_cost)}"
    )
    lines.append(f'    subgraph {region_id}["{region_label}"]')

    for vpc in vpcs:
        vpc_nid = sanitize_node_id(vpc.vpc_id, "vpc")
        vpc_label = sanitize_label(
            f"🔒 {vpc.name}\\n"
            f"{_fmt_cost(vpc.monthly_cost)}{_waste_badge(vpc.waste_cost)}"
        )
        lines.append(f'        {vpc_nid}["{vpc_label}"]{_hotspot_class(vpc.monthly_cost)}')
        node_count += 1

    lines.append("    end")

    # Standalone cost
    if topology.standalone.total_cost > 0:
        sa_nid = sanitize_node_id("standalone", "sa")
        sa_label = sanitize_label(
            f"🌐 Standalone\\n{_fmt_cost(topology.standalone.total_cost)}"
        )
        lines.append(f'    {sa_nid}["{sa_label}"]{_hotspot_class(topology.standalone.total_cost)}')
        node_count += 1

    lines.append(STYLE_DEFS)

    return ArchitectureViewResult(
        mermaid="\n".join(lines),
        warnings=warnings,
        stats={"nodes": node_count, "edges": 0, "subgraphs": 1},
    )


# ---------------------------------------------------------------------------
# Renderer C: VPC Detail Drilldown
# ---------------------------------------------------------------------------

def render_vpc_detail(
    topology: RegionTopology,
    vpc_id: str,
) -> Optional[ArchitectureViewResult]:
    """
    Full resource-level diagram for one VPC.
    Shows subnets, EC2, RDS, EBS, EIP with relationship edges.
    """
    target_vpc: Optional[VpcTopology] = None
    for v in topology.vpcs:
        if v.vpc_id == vpc_id:
            target_vpc = v
            break

    if target_vpc is None:
        return None

    lines: List[str] = ["flowchart TD"]
    warnings = list(topology.warnings)
    node_count = 0
    edge_count = 0
    node_ids_emitted: set = set()
    edges: List[str] = []

    # Collect all resources for complexity check
    all_resources: List[ResourceNode] = []
    for sn in target_vpc.subnets:
        all_resources.extend(sn.resources)
    all_resources.extend(target_vpc.unplaced_resources)

    truncated = False
    if len(all_resources) > MAX_DETAIL_NODES:
        warnings.append({
            "type": "diagram_truncated",
            "reason": "node_limit_exceeded",
            "total": str(len(all_resources)),
            "limit": str(MAX_DETAIL_NODES),
        })
        truncated = True

    # VPC subgraph
    vpc_nid = sanitize_node_id(target_vpc.vpc_id, "vpc")
    vpc_label = sanitize_label(
        f"🔒 {target_vpc.name} ({target_vpc.cidr_block}) — "
        f"{_fmt_cost(target_vpc.monthly_cost)}"
    )
    lines.append(f'    subgraph {vpc_nid}["{vpc_label}"]')

    # Render subnets
    for sn in target_vpc.subnets:
        sn_nid = sanitize_node_id(sn.subnet_id, "sn")
        sn_label = sanitize_label(
            f"📦 {sn.name} ({sn.cidr_block}) — {sn.availability_zone}"
        )
        lines.append(f'        subgraph {sn_nid}["{sn_label}"]')

        resources = sn.resources
        if truncated:
            # Show top resources by cost
            resources = sorted(resources, key=lambda r: -r.cost)[:20]

        for r in resources:
            r_nid = _render_resource_node(lines, r, indent=12)
            node_ids_emitted.add(r_nid)
            node_count += 1
            # Collect edges
            _collect_edges(r, r_nid, edges, node_ids_emitted)

        lines.append("        end")

    # Unplaced resources (in VPC but unknown subnet)
    unplaced = target_vpc.unplaced_resources
    if truncated:
        unplaced = sorted(unplaced, key=lambda r: -r.cost)[:20]

    for r in unplaced:
        r_nid = _render_resource_node(lines, r, indent=8)
        node_ids_emitted.add(r_nid)
        node_count += 1
        _collect_edges(r, r_nid, edges, node_ids_emitted)

    lines.append("    end")

    # Render edges (only if both endpoints exist)
    if len(edges) > MAX_DETAIL_EDGES:
        warnings.append({
            "type": "edges_truncated",
            "total": str(len(edges)),
            "limit": str(MAX_DETAIL_EDGES),
        })
        edges = edges[:MAX_DETAIL_EDGES]

    for e in edges:
        lines.append(f"    {e}")
        edge_count += 1

    # IGW connections
    for igw in topology.igws:
        if vpc_id in igw.attached_vpc_ids:
            igw_nid = sanitize_node_id(igw.igw_id, "igw")
            igw_label = sanitize_label(f"🌐 {igw.name}")
            lines.append(f'    {igw_nid}["{igw_label}"]')
            lines.append(f"    {igw_nid} --> {vpc_nid}")
            node_count += 1
            edge_count += 1

    lines.append(STYLE_DEFS)

    return ArchitectureViewResult(
        mermaid="\n".join(lines),
        warnings=warnings,
        stats={
            "nodes": node_count,
            "edges": edge_count,
            "subgraphs": 1 + len(target_vpc.subnets),
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_resource_node(
    lines: List[str],
    r: ResourceNode,
    indent: int = 8,
) -> str:
    """Render a single resource as a Mermaid node. Returns the node ID."""
    r_nid = sanitize_node_id(r.cloud_resource_id, r.service_kind)
    emoji = SERVICE_EMOJI.get(r.service_kind, "📌")
    status_em = STATUS_EMOJI.get(r.status.lower(), "⚪")

    # Build label based on service kind
    if r.service_kind == "ec2":
        itype = r.metadata.get("instance_type", "")
        label = f"{emoji} {r.resource_name}\\n{itype} | {_fmt_cost(r.cost)}\\n{status_em} {r.status}"
    elif r.service_kind == "rds":
        engine = r.metadata.get("engine", "")
        iclass = r.metadata.get("instance_class", "")
        label = f"{emoji} {r.resource_name}\\n{iclass} | {engine}\\n{_fmt_cost(r.cost)} | {status_em} {r.status}"
    elif r.service_kind == "ebs":
        size = r.metadata.get("size_gb", 0)
        vtype = r.metadata.get("volume_type", "")
        label = f"{emoji} {r.resource_name}\\n{size}GB {vtype} | {_fmt_cost(r.cost)}\\n{status_em} {r.status}"
    elif r.service_kind == "eip":
        ip = r.metadata.get("public_ip", "")
        label = f"{emoji} {ip}\\nEIP | {_fmt_cost(r.cost)}\\n{status_em} {r.status}"
    else:
        label = f"{emoji} {r.resource_name}\\n{_fmt_cost(r.cost)} | {status_em} {r.status}"

    label = sanitize_label(label)
    pad = " " * indent
    lines.append(f'{pad}{r_nid}["{label}"]{_status_class(r.status)}')
    return r_nid


def _collect_edges(
    r: ResourceNode,
    r_nid: str,
    edges: List[str],
    known_nodes: set,
) -> None:
    """Collect edges for a resource. Only adds edges where target exists."""
    # EBS -> EC2
    if r.service_kind == "ebs" and r.attached_instance_id:
        target = sanitize_node_id(r.attached_instance_id, "ec2")
        if target in known_nodes:
            edges.append(f"{r_nid} -.-> {target}")

    # EIP -> EC2
    if r.service_kind == "eip" and r.attached_instance_id:
        target = sanitize_node_id(r.attached_instance_id, "ec2")
        if target in known_nodes:
            edges.append(f"{r_nid} --> {target}")


def _render_standalone_summary(lines: List[str], standalone: StandaloneGroup) -> None:
    """Render standalone resources as a collapsed summary group."""
    if standalone.total_count == 0:
        return

    lines.append('    subgraph sa_group["🌐 Global / Standalone"]')

    if standalone.s3_buckets:
        nid = sanitize_node_id("s3_group", "sa")
        cost = sum(r.cost for r in standalone.s3_buckets)
        label = sanitize_label(f"📂 {len(standalone.s3_buckets)} S3 Buckets | {_fmt_cost(cost)}")
        lines.append(f'        {nid}["{label}"]')

    if standalone.lambda_functions:
        nid = sanitize_node_id("lambda_group", "sa")
        label = sanitize_label(f"⚡ {len(standalone.lambda_functions)} Lambda Functions")
        lines.append(f'        {nid}["{label}"]')

    if standalone.iam_entities:
        nid = sanitize_node_id("iam_group", "sa")
        label = sanitize_label(f"👤 {len(standalone.iam_entities)} IAM Entities")
        lines.append(f'        {nid}["{label}"]')

    if standalone.other:
        nid = sanitize_node_id("other_group", "sa")
        label = sanitize_label(f"📌 {len(standalone.other)} other resources")
        lines.append(f'        {nid}["{label}"]')

    lines.append("    end")


def _format_counts(counts: Dict[str, int]) -> str:
    """Format resource counts like '5 EC2 · 2 RDS · 3 Subnets'."""
    parts = []
    # Ordered by importance
    for kind, display in [
        ("ec2", "EC2"),
        ("rds", "RDS"),
        ("ebs", "EBS"),
        ("eip", "EIP"),
        ("subnet", "Subnets"),
    ]:
        c = counts.get(kind, 0)
        if c > 0:
            parts.append(f"{c} {display}")
    return " · ".join(parts) if parts else "0 resources"
