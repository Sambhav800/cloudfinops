"""
Azure field adapter.

Normalizes Azure resource metadata into canonical fields for topology building.
Mirror of aws_field_adapter.py for Azure resources.
"""

from typing import Any, Dict, List, Optional

_SERVICE_TYPE_MAP = {
    "azure virtual machine": "vm",
    "azure vm": "vm",
    "virtual machine": "vm",
    "microsoft.compute/virtualmachines": "vm",
    "azure managed disk": "disk",
    "managed disk": "disk",
    "microsoft.compute/disks": "disk",
    "azure public ip": "pip",
    "public ip address": "pip",
    "public ip": "pip",
    "microsoft.network/publicipaddresses": "pip",
    "azure virtual network": "vnet",
    "virtual network": "vnet",
    "microsoft.network/virtualnetworks": "vnet",
    "azure subnet": "subnet",
    "subnet": "subnet",
    "microsoft.network/virtualnetworks/subnets": "subnet",
    "azure network security group": "nsg",
    "network security group": "nsg",
    "microsoft.network/networksecuritygroups": "nsg",
    "azure network interface": "nic",
    "network interface": "nic",
    "microsoft.network/networkinterfaces": "nic",
    "azure load balancer": "lb",
    "load balancer": "lb",
    "microsoft.network/loadbalancers": "lb",
    "azure storage account": "storage",
    "storage account": "storage",
    "microsoft.storage/storageaccounts": "storage",
    "azure sql database": "sql",
    "microsoft.sql/servers/databases": "sql",
    "azure cosmos db": "cosmosdb",
    "microsoft.documentdb/databaseaccounts": "cosmosdb",
    "azure app service": "app_service",
    "microsoft.web/sites": "app_service",
    "azure key vault": "keyvault",
    "microsoft.keyvault/vaults": "keyvault",
    "azure aks": "aks",
    "azure kubernetes service": "aks",
    "microsoft.containerservice/managedclusters": "aks",
}

_VPC_SERVICES = {"vm", "disk", "pip", "nsg", "nic", "lb", "sql"}
_STANDALONE_SERVICES = {"storage", "app_service", "keyvault", "cosmosdb"}
_NETWORK_SERVICES = {"vnet", "subnet", "nsg", "nic"}
_SKIP_SERVICES = set()


def get_service_kind(row: Dict[str, Any]) -> str:
    raw = str(row.get("service_type") or "").lower().strip()
    kind = _SERVICE_TYPE_MAP.get(raw)
    if kind:
        return kind
    for key, value in _SERVICE_TYPE_MAP.items():
        if key in raw:
            return value
    return "other"


def is_vnet_service(kind: str) -> bool:
    return kind in _VPC_SERVICES


def is_standalone_service(kind: str) -> bool:
    return kind in _STANDALONE_SERVICES


def is_network_infra(kind: str) -> bool:
    return kind in _NETWORK_SERVICES


def is_skip_service(kind: str) -> bool:
    return kind in _SKIP_SERVICES


def get_region(row: Dict[str, Any]) -> str:
    region = str(row.get("region") or "").strip().lower()
    if not region or region in ("unknown", "none"):
        metadata = row.get("metadata") or {}
        region = str(metadata.get("location") or metadata.get("region") or "unknown").lower()
    return region


def get_resource_group(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    rg = metadata.get("resource_group") or metadata.get("resourceGroupName") or ""
    if not rg:
        cloud_id = str(row.get("cloud_resource_id") or "")
        parts = cloud_id.split("/")
        for i, part in enumerate(parts):
            if part.lower() == "resourcegroups" and i + 1 < len(parts):
                return parts[i + 1]
    return rg


def get_vnet_id(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    return metadata.get("vnet_id") or metadata.get("virtual_network_id") or None


def get_subnet_id(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    return metadata.get("subnet_id") or None


def get_vnet_cidr(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    cidrs = metadata.get("address_prefixes") or metadata.get("address_space") or []
    if isinstance(cidrs, list) and cidrs:
        return cidrs[0]
    if isinstance(cidrs, str):
        return cidrs
    return "10.0.0.0/16"


def get_subnet_cidr(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(metadata.get("address_prefix") or metadata.get("cidr") or "10.0.0.0/24")


def get_nsg_ids(row: Dict[str, Any]) -> List[str]:
    metadata = row.get("metadata") or {}
    nsg_id = metadata.get("nsg_id") or metadata.get("network_security_group_id")
    if nsg_id:
        return [nsg_id]
    return []


def get_attached_vm_id(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    return metadata.get("attached_to") or metadata.get("managed_by") or None


def get_vm_vnet_from_nic(row: Dict[str, Any]) -> Optional[str]:
    """Attempt to resolve VNet ID from a VM's NIC references in metadata."""
    metadata = row.get("metadata") or {}
    vnet = metadata.get("vnet_id") or metadata.get("virtual_network_id")
    if vnet:
        return vnet
    subnet_id = metadata.get("subnet_id") or ""
    if "/virtualNetworks/" in subnet_id:
        parts = subnet_id.split("/virtualNetworks/")
        if len(parts) > 1:
            vnet_part = parts[1].split("/")[0]
            return vnet_part
    return None


def get_name(row: Dict[str, Any]) -> str:
    return str(row.get("resource_name") or row.get("name") or "unnamed")


def get_cost(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("cost") or 0)
    except (TypeError, ValueError):
        return 0.0


def get_status(row: Dict[str, Any]) -> str:
    status = str(row.get("status") or "Active").strip()
    if status.lower() in ("zombie", "stopped", "idle", "deallocated"):
        return status.capitalize()
    return "Active"


def get_cloud_resource_id(row: Dict[str, Any]) -> str:
    return str(row.get("cloud_resource_id") or row.get("id") or get_name(row))
