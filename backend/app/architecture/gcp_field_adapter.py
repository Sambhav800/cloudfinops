"""
GCP field adapter.

Normalizes GCP resource metadata into canonical fields for topology building.
Mirror of aws_field_adapter.py for Google Cloud resources.
"""

from typing import Any, Dict, List, Optional

_SERVICE_TYPE_MAP = {
    "gcp compute instance": "instance",
    "gcp compute engine": "instance",
    "compute instance": "instance",
    "gcp persistent disk": "disk",
    "persistent disk": "disk",
    "gcp external ip": "ip",
    "external ip": "ip",
    "gcp static ip": "ip",
    "gcp cloud sql": "cloudsql",
    "cloud sql": "cloudsql",
    "gcp cloud sql instance": "cloudsql",
    "gcp storage bucket": "gcs",
    "storage bucket": "gcs",
    "gcp cloud storage": "gcs",
    "gcp vpc network": "vpc",
    "vpc network": "vpc",
    "gcp subnet": "subnet",
    "gcp subnetwork": "subnet",
    "gcp firewall rule": "firewall",
    "firewall rule": "firewall",
    "gcp cloud function": "function",
    "cloud function": "function",
    "gcp cloud run": "cloudrun",
    "cloud run service": "cloudrun",
    "gcp gke cluster": "gke",
    "gke cluster": "gke",
    "gcp snapshot": "snapshot",
    "snapshot": "snapshot",
}

_VPC_SERVICES = {"instance", "disk", "ip", "cloudsql", "gke"}
_STANDALONE_SERVICES = {"gcs", "function", "cloudrun", "snapshot"}
_NETWORK_SERVICES = {"vpc", "subnet", "firewall"}
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


def is_vpc_service(kind: str) -> bool:
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
        zone = str(metadata.get("zone") or "")
        if zone:
            parts = zone.rsplit("-", 1)
            if len(parts) == 2 and len(parts[1]) == 1:
                return parts[0]
            return zone
        region = str(metadata.get("region") or metadata.get("location") or "unknown")
    return region


def get_zone(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(metadata.get("zone") or fa_get_region_from_meta(metadata) or "unknown")


def fa_get_region_from_meta(metadata: Dict[str, Any]) -> str:
    return str(metadata.get("region") or metadata.get("location") or "")


def get_vpc_name(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    network = metadata.get("network") or metadata.get("vpc_name") or metadata.get("vpc_network")
    if network:
        if "/" in str(network):
            return str(network).split("/")[-1]
        return str(network)
    return None


def get_subnet_name(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    subnet = metadata.get("subnet") or metadata.get("subnetwork") or metadata.get("subnet_name")
    if subnet:
        if "/" in str(subnet):
            return str(subnet).split("/")[-1]
        return str(subnet)
    return None


def get_subnet_cidr(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(metadata.get("ip_cidr_range") or metadata.get("cidr") or "10.128.0.0/20")


def get_firewall_network(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    network = metadata.get("network") or ""
    if "/" in str(network):
        return str(network).split("/")[-1]
    return str(network) if network else None


def get_attached_instance(row: Dict[str, Any]) -> Optional[str]:
    metadata = row.get("metadata") or {}
    attached = metadata.get("attached_to") or metadata.get("users")
    if isinstance(attached, list) and attached:
        val = str(attached[0])
        return val.split("/")[-1] if "/" in val else val
    if isinstance(attached, str) and attached:
        return attached.split("/")[-1] if "/" in attached else attached
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
    metadata = row.get("metadata") or {}
    gcp_status = str(metadata.get("status") or "").upper()

    if gcp_status in ("TERMINATED", "STOPPING"):
        return "Stopped"
    if status.lower() in ("zombie", "stopped", "idle"):
        return status.capitalize()
    return "Active"


def get_cloud_resource_id(row: Dict[str, Any]) -> str:
    return str(
        row.get("cloud_resource_id")
        or row.get("metadata", {}).get("global_name")
        or row.get("id")
        or get_name(row)
    )


def get_machine_type(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    mt = metadata.get("machine_type") or ""
    if "/" in str(mt):
        return str(mt).split("/")[-1]
    return str(mt) if mt else "unknown"
