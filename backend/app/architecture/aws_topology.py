"""
AWS topology builder.

Transforms flat MongoDB resource rows into a structured RegionTopology.
This is the SINGLE source of truth — all renderers consume this model.
"""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from . import aws_field_adapter as fa
from .models import (
    IgwNode,
    RegionTopology,
    ResourceNode,
    StandaloneGroup,
    SubnetNode,
    VpcTopology,
)

# Service kinds that belong inside VPCs
_VPC_SERVICES = {"ec2", "rds", "ebs", "eip", "sg"}

# Service kinds that are standalone (no VPC relationship)
_STANDALONE_SERVICES = {"s3", "lambda", "iam"}

# Service kinds we skip in diagram (too noisy, not worth visualizing)
_SKIP_SERVICES = {"route_table", "nacl", "dhcp", "key_pair"}


def build_region_topology(
    resource_rows: List[Dict[str, Any]],
    region: str,
) -> RegionTopology:
    """
    Build a structured topology from flat MongoDB resource rows.

    Args:
        resource_rows: All resources for one integration from MongoDB.
        region: Target region to filter for.

    Returns:
        RegionTopology populated with VPCs, subnets, resources, IGWs, standalone.
    """
    warnings: List[Dict[str, str]] = []

    # 1. Filter to target region (include global resources like IAM/S3 in all views)
    region_rows = [
        r for r in resource_rows
        if fa.get_region(r) == region or fa.get_region(r) in ("global", "unknown")
    ]

    if not region_rows:
        warnings.append({"type": "no_resources_found", "region": region})
        return RegionTopology(region=region, warnings=warnings)

    # 2. Categorize all rows by service kind
    vpcs_raw: Dict[str, Dict] = {}         # vpc_id -> row
    subnets_raw: Dict[str, Dict] = {}      # subnet_id -> row
    igws_raw: List[Dict] = []
    sgs_raw: Dict[str, Dict] = {}          # sg_id -> row
    vpc_resources: List[Dict] = []         # resources that belong in a VPC
    standalone_rows: List[Dict] = []
    skipped_count = 0

    for row in region_rows:
        kind = fa.get_service_kind(row)

        if kind == "vpc":
            vid = fa.get_vpc_id(row)
            if vid:
                vpcs_raw[vid] = row
        elif kind == "subnet":
            sid = fa.get_subnet_id(row)
            if sid:
                subnets_raw[sid] = row
        elif kind == "igw":
            igws_raw.append(row)
        elif kind == "sg":
            gid = (row.get("metadata") or {}).get("group_id")
            if gid:
                sgs_raw[gid] = row
        elif kind in _STANDALONE_SERVICES:
            standalone_rows.append(row)
        elif kind in _SKIP_SERVICES:
            skipped_count += 1
        else:
            # EC2, RDS, EBS, EIP, unknown → potential VPC resources
            vpc_resources.append(row)

    if skipped_count:
        warnings.append({
            "type": "services_collapsed",
            "count": str(skipped_count),
            "reason": "Route tables, NACLs, DHCP options, key pairs omitted for clarity",
        })

    # 3. Build instance→vpc lookup (first pass over EC2 resources)
    #    Used to resolve EBS/EIP VPC from their attached instance.
    instance_vpc_map: Dict[str, str] = {}
    for row in vpc_resources:
        if fa.get_service_kind(row) == "ec2":
            iid = fa.get_instance_id(row)
            vid = fa.get_vpc_id(row)
            if iid and vid:
                instance_vpc_map[iid] = vid

    # 4. Build VPC structures
    vpc_map: Dict[str, VpcTopology] = {}
    for vid, row in sorted(vpcs_raw.items()):
        vpc_map[vid] = VpcTopology(
            vpc_id=vid,
            name=fa.get_name(row),
            cidr_block=fa.get_vpc_cidr(row),
        )

    # 5. Build subnet structures and assign to VPCs
    subnet_to_vpc: Dict[str, str] = {}
    for sid, row in sorted(subnets_raw.items()):
        vpc_id = fa.get_vpc_id(row)
        if not vpc_id:
            warnings.append({
                "type": "unresolved_reference",
                "source": sid,
                "field": "vpc_id",
                "target": "unknown",
            })
            continue

        subnet_to_vpc[sid] = vpc_id

        sn = SubnetNode(
            subnet_id=sid,
            name=fa.get_name(row),
            cidr_block=fa.get_vpc_cidr(row),
            availability_zone=fa.get_subnet_az(row),
            vpc_id=vpc_id,
        )

        if vpc_id in vpc_map:
            vpc_map[vpc_id].subnets.append(sn)
        else:
            # Subnet references a VPC we didn't scan — create a placeholder
            vpc_map[vpc_id] = VpcTopology(
                vpc_id=vpc_id,
                name=vpc_id,
                cidr_block="",
                subnets=[sn],
            )
            warnings.append({
                "type": "unresolved_reference",
                "source": sid,
                "field": "vpc_id",
                "target": vpc_id,
                "reason": "VPC not found in scan results — created placeholder",
            })

    # 6. Sort subnets within each VPC by AZ then ID
    for vpc in vpc_map.values():
        vpc.subnets.sort(key=lambda s: (s.availability_zone, s.subnet_id))

    # Build subnet lookup for quick placement
    subnet_node_map: Dict[str, SubnetNode] = {}
    for vpc in vpc_map.values():
        for sn in vpc.subnets:
            subnet_node_map[sn.subnet_id] = sn

    # 7. Place VPC resources (EC2, RDS, EBS, EIP, unknown)
    for row in vpc_resources:
        kind = fa.get_service_kind(row)
        node = _to_resource_node(row, kind)

        # Determine VPC placement
        vpc_id = fa.get_vpc_id(row)
        subnet_id = fa.get_subnet_id(row)

        # For RDS without vpc_id, try via subnet_ids
        if not vpc_id and kind == "rds":
            vpc_id = fa.get_rds_vpc_id(row)
            rds_sids = fa.get_rds_subnet_ids(row)
            if not vpc_id and rds_sids:
                # Derive VPC from first known subnet
                for rs in rds_sids:
                    if rs in subnet_to_vpc:
                        vpc_id = subnet_to_vpc[rs]
                        subnet_id = rs
                        break

        # For EBS, resolve via attached EC2
        if kind == "ebs":
            node.attached_instance_id = fa.get_volume_attached_instance_id(row)
            # Infer VPC from attached EC2 instance if not set directly
            if not vpc_id and node.attached_instance_id:
                vpc_id = instance_vpc_map.get(node.attached_instance_id)

        # For EIP, resolve via instance
        if kind == "eip":
            node.attached_instance_id = fa.get_eip_instance_id(row)
            # Infer VPC from associated EC2 instance if not set directly
            if not vpc_id and node.attached_instance_id:
                vpc_id = instance_vpc_map.get(node.attached_instance_id)

        node.vpc_id = vpc_id
        node.subnet_id = subnet_id
        node.sg_ids = fa.get_sg_ids(row)

        if not vpc_id:
            # No VPC — treat as standalone
            standalone_rows.append(row)
            continue

        # Ensure VPC exists
        if vpc_id not in vpc_map:
            vpc_map[vpc_id] = VpcTopology(
                vpc_id=vpc_id, name=vpc_id, cidr_block=""
            )
            warnings.append({
                "type": "unresolved_reference",
                "source": node.cloud_resource_id,
                "field": "vpc_id",
                "target": vpc_id,
                "reason": "VPC not found in scan — created placeholder",
            })

        target_vpc = vpc_map[vpc_id]

        # Try to place inside a subnet
        if subnet_id and subnet_id in subnet_node_map:
            subnet_node_map[subnet_id].resources.append(node)
        elif subnet_id:
            # Subnet referenced but not found
            warnings.append({
                "type": "unresolved_reference",
                "source": node.cloud_resource_id,
                "field": "subnet_id",
                "target": subnet_id,
            })
            target_vpc.unplaced_resources.append(node)
        else:
            target_vpc.unplaced_resources.append(node)

    # 7. Compute VPC costs and resource counts
    for vpc in vpc_map.values():
        total_cost = 0.0
        waste_cost = 0.0
        counts: Dict[str, int] = defaultdict(int)

        for sn in vpc.subnets:
            # Sort resources within subnet
            sn.resources.sort(key=lambda r: (r.service_kind, -r.cost, r.resource_name))
            for r in sn.resources:
                total_cost += r.cost
                if r.status.lower() in ("zombie", "stopped") or r.waste_type:
                    waste_cost += r.cost
                counts[r.service_kind] += 1

        for r in vpc.unplaced_resources:
            total_cost += r.cost
            if r.status.lower() in ("zombie", "stopped") or r.waste_type:
                waste_cost += r.cost
            counts[r.service_kind] += 1

        counts["subnet"] = len(vpc.subnets)

        vpc.monthly_cost = total_cost
        vpc.waste_cost = waste_cost
        vpc.resource_counts = dict(counts)

    # 8. Build IGW nodes
    igws = []
    for row in igws_raw:
        igw_id = (row.get("metadata") or {}).get("igw_id", "")
        igws.append(IgwNode(
            igw_id=igw_id,
            name=fa.get_name(row),
            attached_vpc_ids=fa.get_igw_vpc_ids(row),
            status=fa.get_status(row),
        ))

    # 9. Build standalone group
    standalone = StandaloneGroup()
    for row in standalone_rows:
        kind = fa.get_service_kind(row)
        node = _to_resource_node(row, kind)
        if kind == "s3":
            standalone.s3_buckets.append(node)
        elif kind == "lambda":
            standalone.lambda_functions.append(node)
        elif kind == "iam":
            standalone.iam_entities.append(node)
        else:
            standalone.other.append(node)

    # Sort standalone groups
    for grp in (standalone.s3_buckets, standalone.lambda_functions,
                standalone.iam_entities, standalone.other):
        grp.sort(key=lambda r: (r.resource_name,))

    # 10. Sort VPCs by cost descending (costliest first)
    sorted_vpcs = sorted(vpc_map.values(), key=lambda v: (-v.monthly_cost, v.vpc_id))

    return RegionTopology(
        region=region,
        vpcs=sorted_vpcs,
        igws=igws,
        standalone=standalone,
        warnings=warnings,
    )


def _to_resource_node(row: Dict[str, Any], kind: str) -> ResourceNode:
    """Convert a MongoDB resource row to a ResourceNode."""
    status = fa.get_status(row)
    waste_type = row.get("waste_type")

    # If AI tagged the resource as waste, surface it as Zombie in architecture views
    # even when legacy status remained "Active".
    if waste_type and status.lower() in {"active", "healthy", "running"}:
        status = "Zombie"

    return ResourceNode(
        cloud_resource_id=row.get("cloud_resource_id", ""),
        resource_name=fa.get_name(row),
        service_kind=kind,
        service_type=row.get("service_type", ""),
        cost=fa.get_cost(row),
        status=status,
        waste_type=waste_type,
        metadata=row.get("metadata") or {},
    )
