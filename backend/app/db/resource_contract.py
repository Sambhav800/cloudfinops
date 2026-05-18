import logging
from typing import Dict, Any, List
import math
import re

logger = logging.getLogger(__name__)

ALLOWED_RESOURCE_COLUMNS = [
    "user_id", "integration_id",
    "resource_name", "service_type",
    "cost", "status",
    "region_compliance", "tags", "metadata",
    "created_by", "region",
    "waste_reason", "confidence_score", "waste_type",
    "metrics_data", "governance_violations",
    "last_scanned_at", "provider", "cloud_resource_id",
    "carbon_footprint_kg", "scan_batch_id"
]

AWS_IDENTITY_METADATA_KEYS = (
    "instance_id",
    "volume_id",
    "allocation_id",
    "subnet_id",
    "route_table_id",
    "nacl_id",
    "igw_id",
    "group_id",
    "dhcp_options_id",
    "key_pair_id",
    "vpc_id",
    "user_id",
    "role_id",
    "bucket_name",
    "resource_id",
)

NO_DIRECT_CHARGE_COST_SOURCE = "no_direct_charge"
BILLING_UNAVAILABLE_COST_SOURCES = {"", "billing_unavailable", "pricing_unavailable", "unknown"}
NO_DIRECT_CHARGE_SERVICE_PATTERNS = (
    "security group",
    "security-group-rule",
    "network security group",
    "route table",
    "internet gateway",
    "network acl",
    "dhcp options",
    "key pair",
    "iam user",
    "iam role",
    "network-interface",
    "vpc",
    "subnet",
    "firewall",
    "gcp service",
    "gcp route",
    "gcp firewall",
    "gcp network",
    "gcp subnetwork",
    "gcp serviceaccount",
    "gcp service account",
    "gcp serviceaccountkey",
    "gcp service account key",
    "gcp project",
    "gcp namespace",
    "gcp entrygroup",
    "gcp entry group",
    "gcp logbucket",
    "gcp log bucket",
    "gcp quotapreference",
    "gcp projectbillinginfo",
    "gcp internalrange",
    "serviceaccount",
    "service account",
    "projectbillinginfo",
    "quota",
    "internalrange",
    "resource-explorer",
    "athena:datacatalog",
    "athena:workgroup",
    "payments",
)

GCP_ASSET_PROJECT_RE = re.compile(r"(?:^|/)projects/([^/]+)(?:/|$)")

_MAX_TEXT_LEN = 1024
_MAX_DICT_KEYS = 60
_MAX_LIST_ITEMS = 60
_MAX_DEPTH = 3


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value[:_MAX_TEXT_LEN]
    if isinstance(value, (bool, int)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    return None


def _safe_json(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return "[truncated]"

    scalar = _safe_scalar(value)
    if scalar is not None or value is None:
        return scalar

    if isinstance(value, list):
        out = []
        for item in value[:_MAX_LIST_ITEMS]:
            normalized = _safe_json(item, depth + 1)
            if normalized is not None:
                out.append(normalized)
        if len(value) > _MAX_LIST_ITEMS:
            out.append("[truncated]")
        return out

    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        count = 0
        for k, v in value.items():
            if count >= _MAX_DICT_KEYS:
                out["__truncated__"] = True
                break
            key = str(k)[:120]
            normalized = _safe_json(v, depth + 1)
            if normalized is not None:
                out[key] = normalized
                count += 1
        return out

    return str(value)[:_MAX_TEXT_LEN]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _last_resource_token(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""

    tail = text.rstrip("/").split(":")[-1]
    if "/" in tail:
        tail = tail.rsplit("/", 1)[-1]
    return tail.strip()


def _gcp_asset_parts(value: Any) -> tuple[str, list[str]]:
    text = _text(value).lower()
    if not text:
        return "", []
    if text.startswith("//"):
        text = text[2:]
    parts = [part for part in text.split("/") if part]
    service = parts[0] if parts else ""
    return service, parts


def _gcp_part_after(parts: list[str], marker: str) -> str:
    try:
        index = parts.index(marker)
    except ValueError:
        return ""
    return parts[index + 1] if index + 1 < len(parts) else ""


def _canonical_gcp_asset_id(value: Any, metadata: Dict[str, Any]) -> str:
    service, parts = _gcp_asset_parts(value)
    if not service or "projects" not in parts:
        return ""

    project = _gcp_part_after(parts, "projects")
    if not project:
        match = GCP_ASSET_PROJECT_RE.search("/".join(parts))
        project = match.group(1) if match else ""
    if not project:
        return ""

    zone = _gcp_part_after(parts, "zones")
    region = _gcp_part_after(parts, "regions")
    location = _gcp_part_after(parts, "locations") or region or zone or _text(metadata.get("location")).lower()

    if service == "compute.googleapis.com":
        if "instances" in parts and zone:
            name = _gcp_part_after(parts, "instances")
            return f"gcp-instance-{project}-{name}-{zone}" if name else ""
        if "disks" in parts and zone:
            name = _gcp_part_after(parts, "disks")
            return f"gcp-disk-{project}-{name}-{zone}" if name else ""
        if "addresses" in parts:
            name = _gcp_part_after(parts, "addresses")
            address_location = region or "global"
            return f"gcp-ip-{project}-{name}-{address_location}" if name else ""

    if service == "sqladmin.googleapis.com" and "instances" in parts:
        name = _gcp_part_after(parts, "instances")
        return f"gcp-sql-{project}-{name}-{location}" if name and location else ""

    if service == "container.googleapis.com" and "clusters" in parts:
        name = _gcp_part_after(parts, "clusters")
        return f"gcp-gke-{project}-{name}-{location}" if name and location else ""

    if service == "run.googleapis.com" and "services" in parts:
        name = _gcp_part_after(parts, "services")
        return f"gcp-cloudrun-{project}-{name}" if name else ""

    if service == "cloudfunctions.googleapis.com" and "functions" in parts:
        name = _gcp_part_after(parts, "functions")
        return f"gcp-function-{project}-{name}-{location}" if name and location else ""

    return ""


def _canonical_cloud_resource_id(row: Dict[str, Any]) -> str:
    provider = _text(row.get("provider")).lower()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    cloud_resource_id = _text(row.get("cloud_resource_id"))

    if provider == "aws":
        for key in AWS_IDENTITY_METADATA_KEYS:
            value = _text(metadata.get(key))
            if value:
                return value

        if cloud_resource_id.lower().startswith("arn:aws:"):
            token = _last_resource_token(cloud_resource_id)
            return token or cloud_resource_id

    if provider == "azure" and cloud_resource_id.lower().startswith("/subscriptions/"):
        return cloud_resource_id.lower()

    if provider == "gcp":
        canonical = (
            _canonical_gcp_asset_id(cloud_resource_id, metadata)
            or _canonical_gcp_asset_id(metadata.get("global_name"), metadata)
        )
        if canonical:
            return canonical

    return cloud_resource_id


def _is_no_direct_charge_resource(row: Dict[str, Any]) -> bool:
    service_type = _text(row.get("service_type")).lower()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source = _text(metadata.get("cost_source")).lower()

    if source in {"no_direct_charge", "included", "free"}:
        return True

    return any(pattern in service_type for pattern in NO_DIRECT_CHARGE_SERVICE_PATTERNS)


def normalize_resource_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces the exact MongoDB resources table schema contract.
    - Prevents PGRST204 (unknown columns) by stripping extra keys.
    - Prevents PGRST102 (key mismatch) by ensuring all keys exist.
    """
    try:
        normalized = {}
        ai_metadata = {}
        
        # Extract AI metadata and remove any ai_ prefix
        for key, value in row.items():
            if key.startswith("ai_"):
                ai_key = key[3:] # drop "ai_" prefix
                ai_metadata[ai_key] = value
                
        defaults = {
            "cost": 0.0,
            "confidence_score": 0.0,
            "tags": {},
            "metadata": {},
            "metrics_data": {},
            "governance_violations": [],
            "provider": "aws",
            "region": "global",
            "region_compliance": "compliant",
            "carbon_footprint_kg": 0.0,
            "scan_batch_id": None
        }

        # Handle incorrectly mapped region_compliance vs region
        rc = row.get("region_compliance", "")
        rg = row.get("region", "")
        if isinstance(rc, str) and "-" in rc and (not rg or rg == "unknown" or rg == "global"):
            row["region"] = rc
            row["region_compliance"] = "compliant"

        # Apply schema contract
        for col in ALLOWED_RESOURCE_COLUMNS:
            normalized[col] = row.get(col, defaults.get(col))

        # Coerce float values
        try:
            if normalized["cost"] is not None:
                normalized["cost"] = float(normalized["cost"])
                if not math.isfinite(normalized["cost"]):
                    normalized["cost"] = 0.0
        except (ValueError, TypeError):
            normalized["cost"] = 0.0
            
        try:
            if normalized["confidence_score"] is not None:
                normalized["confidence_score"] = float(normalized["confidence_score"])
                if not math.isfinite(normalized["confidence_score"]):
                    normalized["confidence_score"] = 0.0
        except (ValueError, TypeError):
            normalized["confidence_score"] = 0.0

        # Guarantee metadata is a dict
        if normalized["metadata"] is None:
            normalized["metadata"] = {}
        elif not isinstance(normalized["metadata"], dict):
            normalized["metadata"] = {"raw": normalized["metadata"]}

        # Normalize JSON-ish fields with strict size/depth caps for large scans
        normalized["metadata"] = _safe_json(normalized["metadata"]) if isinstance(normalized["metadata"], dict) else {}
        normalized["tags"] = _safe_json(normalized.get("tags", {}))
        normalized["metrics_data"] = _safe_json(normalized.get("metrics_data", {}))
        normalized["governance_violations"] = _safe_json(normalized.get("governance_violations", []))

        # Inject original ai_* fields into nested metadata properly
        if ai_metadata:
            normalized["metadata"]["ai"] = _safe_json(ai_metadata)

        cost_source = _text(normalized["metadata"].get("cost_source")).lower()
        if (
            normalized["cost"] == 0
            and cost_source in BILLING_UNAVAILABLE_COST_SOURCES
            and _is_no_direct_charge_resource(normalized)
        ):
            normalized["metadata"]["cost_source"] = NO_DIRECT_CHARGE_COST_SOURCE
            normalized["metadata"].setdefault(
                "pricing_note",
                "This resource has no direct monthly resource charge; usage by dependent services may still be billed.",
            )

        canonical_resource_id = _canonical_cloud_resource_id(normalized)
        if canonical_resource_id:
            normalized["cloud_resource_id"] = canonical_resource_id

        # Enforce bounded identifiers to prevent oversized keys
        if normalized.get("cloud_resource_id"):
            normalized["cloud_resource_id"] = str(normalized["cloud_resource_id"])[:512]
        if normalized.get("resource_name"):
            normalized["resource_name"] = str(normalized["resource_name"])[:512]
        if normalized.get("service_type"):
            normalized["service_type"] = str(normalized["service_type"])[:256]
        if normalized.get("region"):
            normalized["region"] = str(normalized["region"])[:64]
        if normalized.get("provider"):
            normalized["provider"] = str(normalized["provider"])[:32]

        return normalized
    except Exception as e:
        logger.warning(f"Error normalizing resource row: {e}")
        # Return a safe blank dict with all keys present to avoid batch mismatch errors
        row_safe = {col: None for col in ALLOWED_RESOURCE_COLUMNS}
        row_safe["metadata"] = {}
        return row_safe

def normalize_resource_batch(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Applies normalize_resource_row to an entire list of resources."""
    return [normalize_resource_row(r) for r in rows]
