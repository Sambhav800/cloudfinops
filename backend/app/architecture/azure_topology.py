"""
Azure topology builder.

Transforms flat MongoDB resource rows into a structured RegionTopology
using VNet→Subnet→Resource hierarchy (Azure equivalent of AWS VPC topology).
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from . import azure_field_adapter as fa
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
    Build a structured topology from flat Azure resource rows.

    Maps Azure VNets as VpcTopology, subnets as SubnetNode, and places
    VMs/disks/IPs into their network hierarchy.
    """
    warnings: List[Dict[str, str]] = []

    region_rows = [
        r for r in resource_rows
        if fa.get_region(r) == region or fa.get_region(r) in ("global", "unknown")
    ]

    if not region_rows:
        warnings.append({"type": "no_resources_found", "region": region})
        return RegionTopology(region=region, warnings=warnings)

    vnets_raw: Dict[str, Dict] = {}
    subnets_raw: Dict[str, Dict] = {}
    nsgs_raw: Dict[str, Dict] = {}
    vnet_resources: List[Dict] = []
    standalone_rows: List[Dict] = []

    for row in region_rows:
        kind = fa.get_service_kind(row)

        if kind == "vnet":
            vnet_id = fa.get_cloud_resource_id(row)
            vnets_raw[vnet_id] = row
        elif kind == "subnet":
            subnet_id = fa.get_cloud_resource_id(row)
            subnets_raw[subnet_id] = row
        elif kind == "nsg":
            nsg_id = fa.get_cloud_resource_id(row)
            nsgs_raw[nsg_id] = row
        elif fa.is_standalone_service(kind):
            standalone_rows.append(row)
        elif fa.is_skip_service(kind):
            continue
        else:
            vnet_resources.append(row)

    # Build VNet structures — index by BOTH full resource ID and short name
    vpcs: Dict[str, VpcTopology] = {}
    vnet_name_to_id: Dict[str, str] = {}
    for vnet_id, row in vnets_raw.items():
        name = fa.get_name(row)
        cidr = fa.get_vnet_cidr(row)
        short_name = name if name != "unnamed" else vnet_id
        vpc = VpcTopology(
            vpc_id=vnet_id,
            name=short_name,
            cidr_block=cidr,
        )
        vpcs[vnet_id] = vpc
        vpcs[short_name] = vpc
        vnet_name_to_id[short_name] = vnet_id

    # Map subnets to VNets
    subnet_to_vnet: Dict[str, str] = {}
    for subnet_id, row in subnets_raw.items():
        vnet_id = fa.get_vnet_id(row)
        if not vnet_id:
            cloud_id = str(row.get("cloud_resource_id") or "")
            if "/virtualNetworks/" in cloud_id:
                parts = cloud_id.split("/virtualNetworks/")
                if len(parts) > 1:
                    vnet_id = parts[1].split("/")[0]

        if vnet_id and vnet_id not in vpcs:
            vpcs[vnet_id] = VpcTopology(
                vpc_id=vnet_id,
                name=vnet_id,
                cidr_block="10.0.0.0/16",
            )
            warnings.append({
                "type": "placeholder_vnet",
                "message": f"VNet '{vnet_id}' referenced by subnet but not found in scan results.",
            })

        if vnet_id:
            subnet_to_vnet[subnet_id] = vnet_id

            subnet_node = SubnetNode(
                subnet_id=subnet_id,
                name=fa.get_name(row),
                cidr_block=fa.get_subnet_cidr(row),
                availability_zone=fa.get_region(row),
                vpc_id=vnet_id,
            )
            vpcs[vnet_id].subnets.append(subnet_node)

    # Build map of VM → VNet (from NIC/subnet references)
    vm_vnet_map: Dict[str, str] = {}
    vm_subnet_map: Dict[str, str] = {}

    for row in vnet_resources:
        kind = fa.get_service_kind(row)
        resource_id = fa.get_cloud_resource_id(row)

        if kind == "vm":
            vnet_id = fa.get_vm_vnet_from_nic(row)
            subnet_id = fa.get_subnet_id(row)
            if vnet_id:
                vm_vnet_map[resource_id] = vnet_id
            if subnet_id:
                vm_subnet_map[resource_id] = subnet_id
                if subnet_id in subnet_to_vnet:
                    vm_vnet_map[resource_id] = subnet_to_vnet[subnet_id]

    # Place resources into VNet/Subnet hierarchy
    for row in vnet_resources:
        kind = fa.get_service_kind(row)
        resource_id = fa.get_cloud_resource_id(row)

        node = ResourceNode(
            cloud_resource_id=resource_id,
            resource_name=fa.get_name(row),
            service_kind=kind,
            service_type=str(row.get("service_type") or ""),
            cost=fa.get_cost(row),
            status=fa.get_status(row),
            waste_type=row.get("waste_type"),
            metadata=row.get("metadata") or {},
            vpc_id=None,
            subnet_id=None,
            sg_ids=fa.get_nsg_ids(row),
        )

        # Resolve VNet placement
        vnet_id = None
        subnet_id = None

        if kind == "vm":
            vnet_id = vm_vnet_map.get(resource_id)
            subnet_id = vm_subnet_map.get(resource_id)
        elif kind == "disk":
            attached_vm = fa.get_attached_vm_id(row)
            if attached_vm and attached_vm in vm_vnet_map:
                vnet_id = vm_vnet_map[attached_vm]
                subnet_id = vm_subnet_map.get(attached_vm)
        elif kind == "pip":
            attached_vm = fa.get_attached_vm_id(row)
            if attached_vm and attached_vm in vm_vnet_map:
                vnet_id = vm_vnet_map[attached_vm]
        elif kind == "nic":
            vnet_id = fa.get_vm_vnet_from_nic(row)
            subnet_id = fa.get_subnet_id(row)
        elif kind == "lb":
            vnet_id = fa.get_vnet_id(row)

        if not vnet_id:
            vnet_id = fa.get_vnet_id(row)

        node.vpc_id = vnet_id
        node.subnet_id = subnet_id

        if vnet_id:
            if vnet_id not in vpcs:
                vpcs[vnet_id] = VpcTopology(
                    vpc_id=vnet_id,
                    name=vnet_id,
                    cidr_block="10.0.0.0/16",
                )

            placed = False
            if subnet_id:
                for subnet_node in vpcs[vnet_id].subnets:
                    if (
                        subnet_node.subnet_id == subnet_id
                        or subnet_node.name == subnet_id
                        or subnet_id in subnet_node.subnet_id
                    ):
                        subnet_node.resources.append(node)
                        placed = True
                        break

            if not placed:
                vpcs[vnet_id].unplaced_resources.append(node)
        else:
            standalone_rows.append(row)

    # Aggregate costs per VNet
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

    # Build standalone group
    standalone = StandaloneGroup()
    for row in standalone_rows:
        kind = fa.get_service_kind(row)
        if kind in ("vnet", "subnet", "nsg", "nic"):
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
        if kind == "storage":
            standalone.s3_buckets.append(node)
        elif kind in ("app_service", "cosmosdb"):
            standalone.lambda_functions.append(node)
        else:
            standalone.other.append(node)

    # Deduplicate VPCs (same object may be indexed by both ID and name)
    seen_ids: set = set()
    unique_vpcs: List[VpcTopology] = []
    for vpc in vpcs.values():
        if id(vpc) not in seen_ids:
            seen_ids.add(id(vpc))
            unique_vpcs.append(vpc)

    sorted_vpcs = sorted(unique_vpcs, key=lambda v: v.monthly_cost, reverse=True)

    return RegionTopology(
        region=region,
        vpcs=sorted_vpcs,
        igws=[],
        standalone=standalone,
        warnings=warnings,
    )
