"""
GCP topology builder.

Transforms flat MongoDB resource rows into a structured RegionTopology
using VPC Network→Subnet→Instance hierarchy.

GCP specifics:
- VPC Networks are global, but subnets are regional
- Instances live in zones (which belong to regions)
- Firewall rules attach to VPC Networks (not subnets)
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from . import gcp_field_adapter as fa
from .models import (
    IgwNode,
    RegionTopology,
    ResourceNode,
    StandaloneGroup,
    SubnetNode,
    VpcTopology,
)


def build_region_topology(
    resource_rows: List[Dict[str, Any]],
    region: str,
) -> RegionTopology:
    """
    Build a structured topology from flat GCP resource rows.

    Maps GCP VPC Networks as VpcTopology, regional subnets as SubnetNode,
    and places instances/disks/IPs into their network hierarchy.
    """
    warnings: List[Dict[str, str]] = []

    # GCP regions derived from zones — filter broadly
    region_rows = [
        r for r in resource_rows
        if _matches_region(r, region)
    ]

    if not region_rows:
        warnings.append({"type": "no_resources_found", "region": region})
        return RegionTopology(region=region, warnings=warnings)

    vpcs_raw: Dict[str, Dict] = {}
    subnets_raw: Dict[str, Dict] = {}
    firewalls_raw: List[Dict] = []
    vpc_resources: List[Dict] = []
    standalone_rows: List[Dict] = []

    for row in region_rows:
        kind = fa.get_service_kind(row)

        if kind == "vpc":
            vpc_name = fa.get_name(row)
            vpcs_raw[vpc_name] = row
        elif kind == "subnet":
            subnet_name = fa.get_cloud_resource_id(row)
            subnets_raw[subnet_name] = row
        elif kind == "firewall":
            firewalls_raw.append(row)
        elif fa.is_standalone_service(kind):
            standalone_rows.append(row)
        elif fa.is_skip_service(kind):
            continue
        else:
            vpc_resources.append(row)

    # Build VPC Network structures
    vpcs: Dict[str, VpcTopology] = {}
    for vpc_name, row in vpcs_raw.items():
        vpcs[vpc_name] = VpcTopology(
            vpc_id=vpc_name,
            name=fa.get_name(row),
            cidr_block="auto",
        )

    # Map subnets to VPC Networks
    subnet_to_vpc: Dict[str, str] = {}
    for subnet_id, row in subnets_raw.items():
        vpc_name = fa.get_vpc_name(row)
        subnet_name = fa.get_name(row)

        if vpc_name and vpc_name not in vpcs:
            vpcs[vpc_name] = VpcTopology(
                vpc_id=vpc_name,
                name=vpc_name,
                cidr_block="auto",
            )
            warnings.append({
                "type": "placeholder_vpc",
                "message": f"VPC Network '{vpc_name}' referenced by subnet but not found in scan.",
            })

        if vpc_name:
            subnet_to_vpc[subnet_id] = vpc_name
            subnet_to_vpc[subnet_name] = vpc_name

            subnet_node = SubnetNode(
                subnet_id=subnet_id,
                name=subnet_name,
                cidr_block=fa.get_subnet_cidr(row),
                availability_zone=fa.get_region(row),
                vpc_id=vpc_name,
            )
            vpcs[vpc_name].subnets.append(subnet_node)

    # Build instance → VPC/subnet map
    instance_vpc_map: Dict[str, str] = {}
    instance_subnet_map: Dict[str, str] = {}

    for row in vpc_resources:
        kind = fa.get_service_kind(row)
        resource_id = fa.get_cloud_resource_id(row)
        name = fa.get_name(row)

        if kind == "instance":
            vpc_name = fa.get_vpc_name(row)
            subnet_name = fa.get_subnet_name(row)

            if vpc_name:
                instance_vpc_map[resource_id] = vpc_name
                instance_vpc_map[name] = vpc_name
            elif subnet_name and subnet_name in subnet_to_vpc:
                vpc_name = subnet_to_vpc[subnet_name]
                instance_vpc_map[resource_id] = vpc_name
                instance_vpc_map[name] = vpc_name

            if subnet_name:
                instance_subnet_map[resource_id] = subnet_name
                instance_subnet_map[name] = subnet_name

    # Place resources into VPC/Subnet hierarchy
    for row in vpc_resources:
        kind = fa.get_service_kind(row)
        resource_id = fa.get_cloud_resource_id(row)
        name = fa.get_name(row)

        node = ResourceNode(
            cloud_resource_id=resource_id,
            resource_name=name,
            service_kind=kind,
            service_type=str(row.get("service_type") or ""),
            cost=fa.get_cost(row),
            status=fa.get_status(row),
            waste_type=row.get("waste_type"),
            metadata=row.get("metadata") or {},
            vpc_id=None,
            subnet_id=None,
        )

        vpc_name = None
        subnet_name = None

        if kind == "instance":
            vpc_name = instance_vpc_map.get(resource_id) or instance_vpc_map.get(name)
            subnet_name = instance_subnet_map.get(resource_id) or instance_subnet_map.get(name)
        elif kind == "disk":
            attached = fa.get_attached_instance(row)
            if attached:
                vpc_name = instance_vpc_map.get(attached)
                subnet_name = instance_subnet_map.get(attached)
        elif kind == "ip":
            attached = fa.get_attached_instance(row)
            if attached:
                vpc_name = instance_vpc_map.get(attached)
        elif kind == "cloudsql":
            vpc_name = fa.get_vpc_name(row)
        elif kind == "gke":
            vpc_name = fa.get_vpc_name(row)
            subnet_name = fa.get_subnet_name(row)

        if not vpc_name:
            vpc_name = fa.get_vpc_name(row)

        node.vpc_id = vpc_name
        node.subnet_id = subnet_name

        if vpc_name:
            if vpc_name not in vpcs:
                vpcs[vpc_name] = VpcTopology(
                    vpc_id=vpc_name,
                    name=vpc_name,
                    cidr_block="auto",
                )

            placed = False
            if subnet_name:
                for subnet_node in vpcs[vpc_name].subnets:
                    if subnet_node.name == subnet_name or subnet_node.subnet_id == subnet_name:
                        subnet_node.resources.append(node)
                        placed = True
                        break

                # Auto-create subnet if referenced but not scanned
                if not placed:
                    new_subnet = SubnetNode(
                        subnet_id=f"{vpc_name}/{subnet_name}",
                        name=subnet_name,
                        cidr_block="auto",
                        availability_zone=fa.get_region(row),
                        vpc_id=vpc_name,
                    )
                    new_subnet.resources.append(node)
                    vpcs[vpc_name].subnets.append(new_subnet)
                    subnet_to_vpc[subnet_name] = vpc_name
                    placed = True

            if not placed:
                vpcs[vpc_name].unplaced_resources.append(node)
        else:
            standalone_rows.append(row)

    # Aggregate costs per VPC
    for vpc in vpcs.values():
        total_cost = 0.0
        waste_cost = 0.0
        counts: Dict[str, int] = defaultdict(int)

        for subnet in vpc.subnets:
            for res in subnet.resources:
                total_cost += res.cost
                counts[res.service_kind] += 1
                if res.status.lower() in ("zombie", "stopped") or res.waste_type:
                    waste_cost += res.cost

        for res in vpc.unplaced_resources:
            total_cost += res.cost
            counts[res.service_kind] += 1
            if res.status.lower() in ("zombie", "stopped") or res.waste_type:
                waste_cost += res.cost

        vpc.monthly_cost = total_cost
        vpc.waste_cost = waste_cost
        vpc.resource_counts = dict(counts)

    # Firewall rules as IGW-equivalent (network-level policies)
    firewall_nodes: List[IgwNode] = []
    for row in firewalls_raw:
        network = fa.get_firewall_network(row)
        firewall_nodes.append(IgwNode(
            igw_id=fa.get_cloud_resource_id(row),
            name=fa.get_name(row),
            attached_vpc_ids=[network] if network else [],
            status="Active",
        ))

    # Build standalone group
    standalone = StandaloneGroup()
    for row in standalone_rows:
        kind = fa.get_service_kind(row)
        if kind in ("vpc", "subnet", "firewall"):
            continue
        node = ResourceNode(
            cloud_resource_id=fa.get_cloud_resource_id(row),
            resource_name=fa.get_name(row),
            service_kind=kind,
            service_type=str(row.get("service_type") or ""),
            cost=fa.get_cost(row),
            status=fa.get_status(row),
            waste_type=row.get("waste_type"),
            metadata=row.get("metadata") or {},
        )
        if kind == "gcs":
            standalone.s3_buckets.append(node)
        elif kind in ("function", "cloudrun"):
            standalone.lambda_functions.append(node)
        else:
            standalone.other.append(node)

    sorted_vpcs = sorted(vpcs.values(), key=lambda v: v.monthly_cost, reverse=True)

    return RegionTopology(
        region=region,
        vpcs=sorted_vpcs,
        igws=firewall_nodes,
        standalone=standalone,
        warnings=warnings,
    )


def _matches_region(row: Dict[str, Any], target_region: str) -> bool:
    """Check if a GCP resource belongs to this region (handles zones)."""
    resource_region = fa.get_region(row)
    if resource_region == target_region:
        return True
    if resource_region in ("global", "unknown"):
        return True
    # Zone to region: us-central1-a → us-central1
    if resource_region.startswith(target_region):
        return True
    return False
