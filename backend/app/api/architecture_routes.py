"""
API Routes for Architecture Diagrams.

Exposes endpoints to generate Mermaid.js diagrams AND interactive graph JSON
from existing scan data.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..db import MongoDBClient, get_db_client
from ..architecture.aws_graph_builder import build_region_graph_result
from ..architecture.aws_renderers import (
    render_cost_hotspots,
    render_topology_summary,
    render_vpc_detail,
)
from ..architecture.aws_topology import build_region_topology
from ..architecture.azure_topology import build_region_topology as build_azure_region_topology
from ..architecture.gcp_topology import build_region_topology as build_gcp_region_topology
from ..architecture.contracts import (
    ChangeItem,
    CoverageReport,
    GraphData,
    GraphEdge,
    GraphNode,
    GraphResponse,
    ProposedResult,
    RegionGraphResult,
    ViewData,
)
from ..architecture.models import ArchitectureRegionResult, ArchitectureResult
from ..architecture.sanitizer import sanitize_label, sanitize_node_id

router = APIRouter(prefix="/api/architecture", tags=["Architecture"])

SUPPORTED_PROVIDERS = {"aws", "azure", "gcp"}
VALID_CURRENT_VIEWS = {"summary", "hotspots", "vpc_detail"}
VALID_GRAPH_VIEWS = {"all", "topology_summary", "cost_hotspots", "microservices", "vpc_detail"}
VALID_MODES = {"cost_optimized", "reliability_security_optimized"}

MICROSERVICE_TOKENS = ("eks", "ecs", "aks", "gke", "kubernetes", "k8s", "container", "cloud_run")
PROVIDER_BASELINE_SERVICES = {
    "aws": ["ec2", "rds", "s3", "lambda", "vpc", "ebs", "iam", "eks", "ecs", "alb"],
    "azure": ["virtual_machine", "managed_disk", "storage_account", "network_security_group", "public_ip", "aks"],
    "gcp": ["compute_instance", "persistent_disk", "cloud_sql", "storage_bucket", "vpc_network", "gke"],
}
PROVIDER_DISPLAY_NAMES = {
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
}
PROVIDER_MERMAID_THEME = {
    "aws": {"fill": "#3b2a14", "stroke": "#FF9900"},
    "azure": {"fill": "#0b2f5c", "stroke": "#0078D4"},
    "gcp": {"fill": "#16324f", "stroke": "#4285F4"},
}
CHANGE_TYPE_LABELS = {
    "terminate": "retire",
    "downsize": "right-size",
    "migrate": "tier shift",
    "add_replica": "add replica",
    "enable_multi_az": "multi-zone",
    "add_monitoring": "monitoring",
    "tighten_security": "harden",
    "enable_encryption": "encrypt",
}
MAX_RESOURCES_PER_SERVICE = 20
MAX_MERMAID_SERVICES = 12
MAX_MERMAID_RESOURCES_PER_SERVICE = 6
MAX_INFERRED_SERVICE_EDGES = 18
MAX_INFERRED_RESOURCE_EDGES = 24
GENERIC_CATEGORY_ORDER = [
    "edge",
    "network",
    "compute",
    "containers",
    "serverless",
    "database",
    "storage",
    "security",
    "other",
]
GENERIC_CATEGORY_LABELS = {
    "edge": "Edge & Exposure",
    "network": "Network Fabric",
    "compute": "Application Compute",
    "containers": "Container Platform",
    "serverless": "Serverless Runtime",
    "database": "Data Services",
    "storage": "Storage & Backup",
    "security": "Security Controls",
    "other": "Shared Services",
}
GENERIC_CATEGORY_THEME = {
    "edge": {"fill": "#172554", "stroke": "#60a5fa"},
    "network": {"fill": "#082f49", "stroke": "#06b6d4"},
    "compute": {"fill": "#312e81", "stroke": "#818cf8"},
    "containers": {"fill": "#1e3a8a", "stroke": "#3b82f6"},
    "serverless": {"fill": "#052e16", "stroke": "#10b981"},
    "database": {"fill": "#3b0764", "stroke": "#a855f7"},
    "storage": {"fill": "#365314", "stroke": "#84cc16"},
    "security": {"fill": "#431407", "stroke": "#f97316"},
    "other": {"fill": "#1e293b", "stroke": "#94a3b8"},
}
ARCHITECTURE_METADATA_FIELDS = (
    "cost_source",
    "attached_to",
    "attached",
    "source_disk",
    "network",
    "global_name",
    "url",
    "machine_type",
    "vm_size",
    "size_gb",
    "sku",
    "tier",
    "database_version",
    "storage_gb",
    "node_count",
    "cluster_status",
    "kubernetes_version",
    "runtime",
    "ip_address",
    "address",
    "public_ip",
    "has_public_ip",
    "address_type",
    "ip_status",
    "provisioning_state",
    "state",
    "status",
    "zone",
    "location",
)


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
        )
    return normalized


def _to_number(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else 0.0
    except (TypeError, ValueError):
        return 0.0


def _normalize_status(value: Any) -> str:
    status = str(value or "Active").strip().lower()
    if status in {"zombie", "waste", "idle", "non_compliant"}:
        return "Zombie"
    if status in {"stopped", "terminated", "deallocated", "suspended"}:
        return "Stopped"
    return "Active"


def _is_waste_status(status: str) -> bool:
    return status.lower() in {"zombie", "stopped"}


def _severity_for_resource(status: str, cost: float) -> str:
    status_lower = status.lower()
    if status_lower == "zombie":
        return "high"
    if status_lower == "stopped":
        return "medium"
    if cost >= 500:
        return "high"
    if cost >= 100:
        return "medium"
    if cost > 0:
        return "low"
    return "none"


def _normalize_service_key(value: Any) -> str:
    raw = str(value or "resource").strip().lower()
    raw = raw.replace("aws ", "").replace("azure ", "").replace("gcp ", "")
    compact = "".join(ch if ch.isalnum() else "_" for ch in raw)
    compact = "_".join(part for part in compact.split("_") if part)

    replacements = {
        "virtual_machine": "virtual_machine",
        "virtualmachines": "virtual_machine",
        "vm": "virtual_machine",
        "compute_instance": "compute_instance",
        "instance": "compute_instance",
        "persistent_disk": "persistent_disk",
        "managed_disk": "managed_disk",
        "storageaccount": "storage_account",
        "storage_accounts": "storage_account",
        "networksecuritygroup": "network_security_group",
        "publicipaddress": "public_ip",
        "load_balancer": "load_balancer",
    }
    return replacements.get(compact, compact or "resource")


def _service_label(service_key: str) -> str:
    return service_key.replace("_", " ").strip().title() or "Resource"


def _service_category(service_key: str) -> str:
    if any(token in service_key for token in ("public_ip", "external_ip", "load_balancer", "gateway", "front_door")):
        return "edge"
    if any(token in service_key for token in ("security", "firewall", "nsg", "iam", "key_vault", "kms")):
        return "security"
    if any(token in service_key for token in ("network_interface", "vpc", "subnet", "network")):
        return "network"
    if any(token in service_key for token in ("aks", "gke", "kubernetes", "cluster", "container")):
        return "containers"
    if any(token in service_key for token in ("cloud_run", "cloud_function", "function", "lambda")):
        return "serverless"
    if any(token in service_key for token in ("virtual_machine", "compute_instance", "instance", "vm")):
        return "compute"
    if any(token in service_key for token in ("database", "sql", "cosmos", "spanner", "postgres", "mysql", "rds")):
        return "database"
    if any(token in service_key for token in ("disk", "storage", "bucket", "snapshot", "blob", "backup")):
        return "storage"
    return "other"


def _provider_label(provider: str) -> str:
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.upper())


def _mode_label(mode: str) -> str:
    return "Cost Optimized" if mode == "cost_optimized" else "Reliability & Security"


def _format_compact_amount(value: float) -> str:
    amount = abs(_to_number(value))
    if amount >= 1000:
        return f"${amount / 1000:.1f}k"
    if amount >= 100:
        return f"${amount:.0f}"
    if amount >= 10:
        return f"${amount:.1f}"
    return f"${amount:.2f}"


def _format_monthly_impact(value: float) -> str:
    if value > 0:
        return f"save {_format_compact_amount(value)}/mo"
    if value < 0:
        return f"add {_format_compact_amount(value)}/mo"
    return "steady"


def _change_type_label(change_type: str) -> str:
    return CHANGE_TYPE_LABELS.get(change_type, change_type.replace("_", " "))


def _resource_cost_source(resource: Dict[str, Any]) -> str:
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    metrics_data = resource.get("metrics_data") if isinstance(resource.get("metrics_data"), dict) else {}

    for candidate in (
        metadata.get("cost_source"),
        metrics_data.get("cost_source"),
    ):
        normalized = str(candidate or "").strip().lower()
        if normalized in {"actual", "estimated"}:
            return normalized

    return "unknown"


def _architecture_metadata(resource: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {})
    metrics_data = resource.get("metrics_data") if isinstance(resource.get("metrics_data"), dict) else {}

    for key in ARCHITECTURE_METADATA_FIELDS:
        value = metrics_data.get(key)
        if key not in metadata and value not in (None, "", [], {}):
            metadata[key] = value

    cost_source = _resource_cost_source(resource)
    if cost_source != "unknown":
        metadata.setdefault("cost_source", cost_source)

    return metadata


def _cost_source_summary(resources: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"actual": 0, "estimated": 0, "unknown": 0}
    for resource in resources:
        summary[_resource_cost_source(resource)] += 1
    return summary


def _cost_provenance_label(resources: List[Dict[str, Any]]) -> str:
    summary = _cost_source_summary(resources)
    if summary["actual"] and not summary["estimated"] and not summary["unknown"]:
        return "actual-backed"
    if summary["estimated"] and not summary["actual"] and not summary["unknown"]:
        return "estimate-backed"
    if summary["actual"] and summary["estimated"]:
        return "mixed-cost basis"
    if summary["actual"] and summary["unknown"]:
        return "mostly actual"
    if summary["estimated"] and summary["unknown"]:
        return "mostly estimated"
    return "cost basis pending"


def _cost_provenance_warning(resources: List[Dict[str, Any]], provider: str, region: str) -> Optional[Dict[str, str]]:
    summary = _cost_source_summary(resources)
    total = sum(summary.values())
    if total == 0 or summary["estimated"] == 0:
        return None

    provider_label = _provider_label(provider)
    return {
        "type": "estimated_cost_data",
        "message": (
            f"{summary['estimated']} of {total} mapped {provider_label} resources in {region} still use "
            "estimate-backed monthly cost because provider billing attribution was unavailable."
        ),
    }


def _normalize_reference_tokens(value: Any) -> List[str]:
    if value in (None, "", [], {}):
        return []

    values = value if isinstance(value, list) else [value]
    tokens: Set[str] = set()

    for item in values:
        raw = str(item or "").strip().strip('"').strip("'")
        if not raw:
            continue

        normalized = raw.rstrip("/").split("?", 1)[0].lower()
        if not normalized:
            continue

        tokens.add(normalized)
        if normalized.startswith("//"):
            tokens.add(normalized[2:])

        segments = [segment for segment in normalized.split("/") if segment]
        if segments:
            tokens.add(segments[-1])
            if len(segments) >= 2:
                tokens.add("/".join(segments[-2:]))

        colon_segments = [segment for segment in normalized.split(":") if segment]
        if len(colon_segments) >= 2:
            tokens.add(colon_segments[-1])

    return sorted(token for token in tokens if token)


def _register_reference(mapping: Dict[str, str], value: Any, node_id: str) -> None:
    for token in _normalize_reference_tokens(value):
        mapping.setdefault(token, node_id)


def _resource_region(resource: Dict[str, Any], provider: str) -> str:
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}

    if provider == "aws":
        candidates = [
            metadata.get("aws_region"),
            resource.get("region"),
            resource.get("region_compliance"),
            metadata.get("region"),
            metadata.get("availability_zone"),
        ]
    else:
        candidates = [
            resource.get("region"),
            metadata.get("location"),
            metadata.get("region"),
            metadata.get("zone"),
            resource.get("region_compliance"),
        ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "global"


def _region_to_comparable(value: str) -> str:
    """
    Normalize region/zone strings for provider-agnostic matching.
    Examples:
      - "us-central1-a" -> "us-central1"
      - "US-CENTRAL1" -> "us-central1"
      - "global" -> "global"
    """
    region = str(value or "").strip().lower()
    if not region:
        return ""
    if region == "global":
        return "global"
    parts = region.split("-")
    if len(parts) >= 3 and len(parts[-1]) == 1 and parts[-1].isalpha():
        return "-".join(parts[:-1])
    return region


def _resource_in_region(resource: Dict[str, Any], region: str, provider: str) -> bool:
    resource_region = _resource_region(resource, provider)
    if resource_region.lower() in ("global", "unknown"):
        return True
    if resource_region.lower() == region.lower():
        return True
    return _region_to_comparable(resource_region) == _region_to_comparable(region)


def _collect_target_regions(
    resources: List[Dict[str, Any]],
    integration: Dict[str, Any],
    provider: str,
    requested_region: Optional[str],
) -> List[str]:
    if requested_region:
        return [requested_region]

    # Always discover regions from actual scan data rather than trusting
    # integration.regions config, which is often stale or a static default
    # that doesn't reflect where resources actually exist.
    seen: Dict[str, str] = {}
    for resource in resources:
        region = _resource_region(resource, provider)
        key = region.lower()
        if key != "global" and key not in seen:
            seen[key] = region

    if seen:
        return [seen[key] for key in sorted(seen.keys())]

    # Fallback: if all resources are global (e.g. IAM-only scan), return global
    return ["global"]


def _extract_permission_data(permission_alerts: List[Dict[str, Any]], integration_id: str) -> Dict[str, List[str]]:
    warnings: List[Dict[str, str]] = []
    missing_services: List[str] = []
    seen_warnings = set()
    seen_missing = set()

    for alert in permission_alerts:
        metadata = alert.get("metadata")
        if not isinstance(metadata, dict):
            continue

        metadata_integration = metadata.get("integration_id")
        if metadata_integration and metadata_integration != integration_id:
            continue

        description = metadata.get("description") or alert.get("recommendation")
        if isinstance(description, str) and description.strip():
            warning_key = description.strip().lower()
            if warning_key not in seen_warnings:
                seen_warnings.add(warning_key)
                warnings.append({
                    "type": "permission_alert",
                    "message": description.strip(),
                })

        missing = metadata.get("missing_services")
        if isinstance(missing, list):
            for service in missing:
                if isinstance(service, str) and service.strip():
                    normalized = service.strip().lower()
                    if normalized not in seen_missing:
                        seen_missing.add(normalized)
                        missing_services.append(normalized)

    return {
        "warnings": warnings,
        "missing_services": sorted(missing_services),
    }


def _format_resource_label(resource_name: str, resource_cost: float, resource_status: str) -> str:
    status_label = resource_status.title()
    if resource_cost > 0:
        return sanitize_label(f"{resource_name}\\n{_format_compact_amount(resource_cost)}/mo · {status_label}")
    return sanitize_label(f"{resource_name}\\n{status_label}")


def _build_service_relation_targets(service_nodes: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    by_category: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for service_key, context in service_nodes.items():
        by_category[context["category"]].append((service_key, context["cost"]))

    ranked: Dict[str, List[str]] = {}
    for category, items in by_category.items():
        ranked[category] = [
            service_key
            for service_key, _cost in sorted(items, key=lambda item: (-item[1], item[0]))
        ]
    return ranked


def _infer_generic_relationships(
    displayed_resources: List[Dict[str, Any]],
    service_nodes: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    resource_lookup: Dict[str, str] = {}
    resource_service_map: Dict[str, str] = {}
    resource_edges: List[GraphEdge] = []
    service_edges: List[GraphEdge] = []
    seen_resource_edges: Set[Tuple[str, str, str, str]] = set()
    seen_service_edges: Set[Tuple[str, str, str]] = set()
    resource_backed_service_edges: Set[Tuple[str, str, str]] = set()

    for context in displayed_resources:
        node_id = context["node_id"]
        service_key = context["service_key"]
        resource = context["resource"]
        metadata = context["metadata"]
        resource_service_map[node_id] = service_key
        _register_reference(resource_lookup, resource.get("cloud_resource_id"), node_id)
        _register_reference(resource_lookup, resource.get("resource_name"), node_id)
        _register_reference(resource_lookup, resource.get("id"), node_id)
        _register_reference(resource_lookup, metadata.get("global_name"), node_id)
        _register_reference(resource_lookup, metadata.get("url"), node_id)

    def add_resource_edge(source: str, target: str, kind: str, style: str) -> None:
        if source == target or len(resource_edges) >= MAX_INFERRED_RESOURCE_EDGES:
            return
        edge_key = (source, target, kind, style)
        if edge_key in seen_resource_edges:
            return
        seen_resource_edges.add(edge_key)
        resource_edges.append(GraphEdge(source=source, target=target, kind=kind, style=style))

        source_service = resource_service_map.get(source)
        target_service = resource_service_map.get(target)
        if source_service and target_service and source_service != target_service:
            resource_backed_service_edges.add((source_service, target_service, kind))

    def add_service_edge(source_key: str, target_key: str, kind: str, style: str = "dotted") -> None:
        if (
            source_key == target_key
            or len(service_edges) >= MAX_INFERRED_SERVICE_EDGES
            or (source_key, target_key, kind) in resource_backed_service_edges
        ):
            return

        source_node = service_nodes.get(source_key)
        target_node = service_nodes.get(target_key)
        if not source_node or not target_node:
            return

        edge_key = (source_node["node_id"], target_node["node_id"], kind)
        if edge_key in seen_service_edges:
            return

        seen_service_edges.add(edge_key)
        service_edges.append(
            GraphEdge(
                source=source_node["node_id"],
                target=target_node["node_id"],
                kind=kind,
                style=style,
            )
        )

    for context in displayed_resources:
        node_id = context["node_id"]
        metadata = context["metadata"]

        for field_name, kind, style in (
            ("attached_to", "attached_to", "solid"),
            ("source_disk", "attached_to", "dotted"),
            ("network", "routes_to", "solid"),
        ):
            target_ref = metadata.get(field_name)
            if target_ref in (None, "", [], {}):
                continue

            for token in _normalize_reference_tokens(target_ref):
                target_node_id = resource_lookup.get(token)
                if target_node_id:
                    add_resource_edge(node_id, target_node_id, kind, style)
                    break

    ranked_targets = _build_service_relation_targets(service_nodes)

    def top_targets(*categories: str) -> List[str]:
        result: List[str] = []
        for category in categories:
            result.extend(ranked_targets.get(category, [])[:2])
        return result

    for service_key, context in service_nodes.items():
        category = context["category"]

        if category == "edge":
            for target_key in top_targets("network", "compute", "containers", "serverless"):
                add_service_edge(service_key, target_key, "routes_to")
        elif category == "network":
            for target_key in top_targets("compute", "containers", "serverless"):
                add_service_edge(service_key, target_key, "routes_to")
        elif category in {"compute", "containers", "serverless"}:
            for target_key in ranked_targets.get("database", [])[:1]:
                add_service_edge(service_key, target_key, "routes_to")
            for target_key in ranked_targets.get("storage", [])[:1]:
                add_service_edge(service_key, target_key, "attached_to")
        elif category == "security":
            for target_key in top_targets("network", "compute", "containers", "serverless", "database", "storage"):
                add_service_edge(service_key, target_key, "security_applies_to")

    return {
        "resource_edges": resource_edges,
        "service_edges": service_edges,
        "relationship_summary": {
            "resource_edges": len(resource_edges),
            "service_edges": len(service_edges),
        },
    }


def _render_generic_mermaid(
    provider: str,
    region: str,
    category_services: Dict[str, List[str]],
    service_nodes: Dict[str, Dict[str, Any]],
    displayed_resources: Dict[str, List[Dict[str, Any]]],
    relationship_edges: List[GraphEdge],
) -> str:
    provider_label = _provider_label(provider)
    lines = ["flowchart LR"]
    region_node = sanitize_node_id(f"{provider}:{region}", "reg")
    lines.append(f'    subgraph {region_node}["{sanitize_label(f"{provider_label} {region}")}"]')

    for category in GENERIC_CATEGORY_ORDER:
        service_keys = category_services.get(category, [])
        if not service_keys:
            continue

        category_node_id = sanitize_node_id(f"{provider}:{region}:{category}", "cat")
        lines.append(f'        subgraph {category_node_id}["{sanitize_label(GENERIC_CATEGORY_LABELS[category])}"]')

        for service_key in service_keys[:MAX_MERMAID_SERVICES]:
            service_context = service_nodes[service_key]
            lines.append(f'            {service_context["node_id"]}["{sanitize_label(service_context["mermaid_label"])}"]')

            for resource_context in displayed_resources.get(service_key, [])[:MAX_MERMAID_RESOURCES_PER_SERVICE]:
                lines.append(
                    f'            {resource_context["node_id"]}["{_format_resource_label(resource_context["resource_name"], resource_context["cost"], resource_context["status"])}"]'
                )
                lines.append(f'            {service_context["node_id"]} --> {resource_context["node_id"]}')

        lines.append("        end")

    lines.append("    end")

    for edge in relationship_edges:
        connector = "-.->" if edge.style == "dotted" else "-->"
        lines.append(f"    {edge.source} {connector} {edge.target}")

    lines.extend([
        "    classDef region fill:#020617,stroke:#6366f1,color:#ffffff,stroke-width:2px",
        "    classDef resource fill:#0f172a,stroke:#475569,color:#e2e8f0,stroke-width:1px",
    ])

    lines.append(f"    class {region_node} region")

    for category, theme in GENERIC_CATEGORY_THEME.items():
        lines.append(
            f'    classDef {category} fill:{theme["fill"]},stroke:{theme["stroke"]},color:#f8fafc,stroke-width:1.5px'
        )
        node_ids = [
            service_nodes[service_key]["node_id"]
            for service_key in category_services.get(category, [])
            if service_key in service_nodes
        ]
        if node_ids:
            lines.append(f"    class {','.join(node_ids)} {category}")

    resource_node_ids = [
        resource_context["node_id"]
        for resource_contexts in displayed_resources.values()
        for resource_context in resource_contexts
    ]
    if resource_node_ids:
        lines.append(f"    class {','.join(resource_node_ids)} resource")

    return "\n".join(lines)


def _build_generic_graph_data(
    region: str,
    resources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    services: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    category_services: Dict[str, List[str]] = defaultdict(list)
    service_nodes: Dict[str, Dict[str, Any]] = {}
    displayed_resources_by_service: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for resource in resources:
        service_key = _normalize_service_key(resource.get("service_type") or resource.get("resource_type"))
        services[service_key].append(resource)

    total_cost = sum(_to_number(resource.get("cost")) for resource in resources)
    region_node_id = sanitize_node_id(region, "reg")
    nodes.append(
        GraphNode(
            id=region_node_id,
            cloud_resource_id=region,
            name=region,
            service_type="region",
            region=region,
            cost=total_cost,
            status="Active",
            severity="medium" if total_cost > 0 else "none",
            node_type="group",
            metadata={"cost_provenance": _cost_provenance_label(resources)},
        )
    )

    category_present = [
        category
        for category in GENERIC_CATEGORY_ORDER
        if any(_service_category(service_key) == category for service_key in services)
    ]

    category_node_ids: Dict[str, str] = {}
    for category in category_present:
        category_resources = [
            resource
            for service_key, service_resources in services.items()
            if _service_category(service_key) == category
            for resource in service_resources
        ]
        category_cost = sum(_to_number(resource.get("cost")) for resource in category_resources)
        category_node_id = sanitize_node_id(f"{region}:{category}", "cat")
        category_node_ids[category] = category_node_id
        nodes.append(
            GraphNode(
                id=category_node_id,
                cloud_resource_id=f"{region}:{category}",
                name=GENERIC_CATEGORY_LABELS[category],
                service_type=category,
                region=region,
                cost=category_cost,
                status="Active",
                severity=_severity_for_resource("Active", category_cost),
                parent=region_node_id,
                node_type="group",
                metadata={
                    "category": category,
                    "resource_count": len(category_resources),
                    "cost_provenance": _cost_provenance_label(category_resources),
                },
            )
        )
        edges.append(GraphEdge(source=region_node_id, target=category_node_id, kind="contains", style="solid"))

    ranked_services = sorted(
        services.items(),
        key=lambda item: (
            GENERIC_CATEGORY_ORDER.index(_service_category(item[0])),
            -sum(_to_number(resource.get("cost")) for resource in item[1]),
            item[0],
        ),
    )

    displayed_resources: List[Dict[str, Any]] = []

    for service_key, service_resources in ranked_services:
        category = _service_category(service_key)
        service_node_id = sanitize_node_id(f"{region}:{service_key}", "svc")
        service_cost = sum(_to_number(resource.get("cost")) for resource in service_resources)
        service_status = "Zombie" if any(
            _is_waste_status(_normalize_status(resource.get("status")))
            for resource in service_resources
        ) else "Active"
        cost_provenance = _cost_provenance_label(service_resources)
        category_services[category].append(service_key)

        service_label = f"{_service_label(service_key)} ({len(service_resources)})"
        mermaid_label = (
            f"{_service_label(service_key)}\\n"
            f"{len(service_resources)} resources · {_format_compact_amount(service_cost)}/mo\\n"
            f"{cost_provenance}"
        )

        nodes.append(
            GraphNode(
                id=service_node_id,
                cloud_resource_id=f"{region}:{service_key}",
                name=service_label,
                service_type=service_key,
                region=region,
                cost=service_cost,
                status=service_status,
                severity=_severity_for_resource(service_status, service_cost),
                parent=category_node_ids.get(category, region_node_id),
                node_type="group",
                metadata={
                    "count": len(service_resources),
                    "category": category,
                    "cost_provenance": cost_provenance,
                    "actual_cost_resources": _cost_source_summary(service_resources)["actual"],
                    "estimated_cost_resources": _cost_source_summary(service_resources)["estimated"],
                },
            )
        )
        edges.append(
            GraphEdge(
                source=category_node_ids.get(category, region_node_id),
                target=service_node_id,
                kind="contains",
                style="solid",
            )
        )
        service_nodes[service_key] = {
            "node_id": service_node_id,
            "category": category,
            "cost": service_cost,
            "mermaid_label": mermaid_label,
        }

        ranked_resources = sorted(
            service_resources,
            key=lambda resource: _to_number(resource.get("cost")),
            reverse=True,
        )[:MAX_RESOURCES_PER_SERVICE]
        for index, resource in enumerate(ranked_resources):
            raw_resource_id = str(
                resource.get("cloud_resource_id")
                or resource.get("id")
                or f"{service_key}-{index}"
            )
            resource_status = _normalize_status(resource.get("status"))
            resource_cost = _to_number(resource.get("cost"))
            metadata = _architecture_metadata(resource)
            metadata.setdefault("category", category)

            resource_node_id = sanitize_node_id(raw_resource_id, "res")
            nodes.append(
                GraphNode(
                    id=resource_node_id,
                    cloud_resource_id=raw_resource_id,
                    name=str(resource.get("resource_name") or raw_resource_id),
                    service_type=service_key,
                    region=region,
                    cost=resource_cost,
                    status=resource_status,
                    waste_type=resource.get("waste_type"),
                    metadata=metadata,
                    severity=_severity_for_resource(resource_status, resource_cost),
                    parent=service_node_id,
                    node_type="resource",
                )
            )
            edges.append(
                GraphEdge(
                    source=service_node_id,
                    target=resource_node_id,
                    kind="contains",
                    style="dotted",
                )
            )

            resource_context = {
                "node_id": resource_node_id,
                "resource_name": str(resource.get("resource_name") or raw_resource_id),
                "cost": resource_cost,
                "status": resource_status,
                "service_key": service_key,
                "metadata": metadata,
                "resource": resource,
            }
            displayed_resources_by_service[service_key].append(resource_context)
            displayed_resources.append(resource_context)

    relationship_bundle = _infer_generic_relationships(displayed_resources, service_nodes)
    edges.extend(relationship_bundle["resource_edges"])
    edges.extend(relationship_bundle["service_edges"])

    return {
        "graph": GraphData(nodes=nodes, edges=edges),
        "services": services,
        "category_services": category_services,
        "service_nodes": service_nodes,
        "displayed_resources": displayed_resources_by_service,
        "relationship_edges": [
            *relationship_bundle["service_edges"],
            *relationship_bundle["resource_edges"],
        ],
        "relationship_summary": relationship_bundle["relationship_summary"],
        "cost_summary": _cost_source_summary(resources),
    }


def _build_generic_region_result(
    provider: str,
    integration_id: str,
    region: str,
    resources: List[Dict[str, Any]],
    views_requested: str,
    permission_alerts: List[Dict[str, Any]],
) -> RegionGraphResult:
    region_resources = [resource for resource in resources if _resource_in_region(resource, region, provider)]
    graph_bundle = _build_generic_graph_data(region, region_resources)
    graph_data: GraphData = graph_bundle["graph"]
    services: Dict[str, List[Dict[str, Any]]] = graph_bundle["services"]
    mermaid = (
        _render_generic_mermaid(
            provider=provider,
            region=region,
            category_services=graph_bundle["category_services"],
            service_nodes=graph_bundle["service_nodes"],
            displayed_resources=graph_bundle["displayed_resources"],
            relationship_edges=graph_bundle["relationship_edges"],
        )
        if region_resources else ""
    )

    detected_services = sorted(services.keys())
    baseline = PROVIDER_BASELINE_SERVICES.get(provider, [])
    missing_services = sorted(service for service in baseline if service not in detected_services)

    permission_data = _extract_permission_data(permission_alerts, integration_id)
    coverage_warnings = permission_data["warnings"]
    if not region_resources:
        coverage_warnings = [
            *coverage_warnings,
            {
                "type": "no_resources_found",
                "message": f"No {provider.upper()} resources found in region {region}. Run a fresh scan to populate this view.",
            },
        ]
    else:
        cost_warning = _cost_provenance_warning(region_resources, provider, region)
        if cost_warning:
            coverage_warnings = [*coverage_warnings, cost_warning]

        relationship_count = (
            graph_bundle["relationship_summary"]["resource_edges"]
            + graph_bundle["relationship_summary"]["service_edges"]
        )
        if relationship_count > 0:
            coverage_warnings = [
                *coverage_warnings,
                {
                    "type": "inferred_relationships",
                    "message": (
                        f"{relationship_count} topology relationships in {region} were derived from live "
                        "attachment and network metadata instead of a static template."
                    ),
                },
            ]

    microservices_available = any(
        any(token in service_key for token in MICROSERVICE_TOKENS)
        for service_key in detected_services
    )

    coverage = CoverageReport(
        detected_services=detected_services,
        missing_services=missing_services,
        access_denied_services=permission_data["missing_services"],
        microservices_available=microservices_available,
        warnings=coverage_warnings,
    )

    topology_view = ViewData(graph=graph_data, mermaid=mermaid, warnings=[])
    cost_view = ViewData(graph=graph_data, mermaid=mermaid, warnings=[])

    if microservices_available:
        microservice_services = {
            service_key: service_resources
            for service_key, service_resources in services.items()
            if any(token in service_key for token in MICROSERVICE_TOKENS)
        }
        microservice_bundle = _build_generic_graph_data(
            region,
            [resource for service_resources in microservice_services.values() for resource in service_resources],
        )
        microservice_mermaid = _render_generic_mermaid(
            provider=provider,
            region=region,
            category_services=microservice_bundle["category_services"],
            service_nodes=microservice_bundle["service_nodes"],
            displayed_resources=microservice_bundle["displayed_resources"],
            relationship_edges=microservice_bundle["relationship_edges"],
        )
        microservice_graph = microservice_bundle["graph"]
        microservices_view = ViewData(
            graph=microservice_graph,
            mermaid=microservice_mermaid,
            warnings=[],
        )
    else:
        microservices_view = ViewData(
            graph=GraphData(nodes=[], edges=[]),
            mermaid="",
            warnings=[{
                "type": "microservices_unavailable",
                "message": f"No managed Kubernetes or container services were detected in {provider.upper()} scan data.",
            }],
        )

    views: Dict[str, ViewData] = {}
    if views_requested in {"all", "topology_summary", "vpc_detail"}:
        views["topology_summary"] = topology_view
    if views_requested in {"all", "cost_hotspots"}:
        views["cost_hotspots"] = cost_view
    if views_requested in {"all", "microservices"}:
        views["microservices"] = microservices_view

    if views_requested == "vpc_detail":
        views["vpc_detail"] = ViewData(
            graph=graph_data,
            mermaid=mermaid,
            warnings=[{
                "type": "view_not_supported",
                "message": f"VPC detail is AWS-specific. Showing topology summary for {provider.upper()} instead.",
            }],
        )

    return RegionGraphResult(
        region=region,
        coverage=coverage,
        views=views,
        vpc_index=[],
    )


def _is_publicly_exposed(service_key: str, metadata: Dict[str, Any]) -> bool:
    if any(token in service_key for token in ("public_ip", "external_ip", "gateway", "load_balancer", "front_door")):
        return True

    if metadata.get("url"):
        return True

    if metadata.get("public_ip") or metadata.get("ip_address") or metadata.get("address"):
        return True

    if str(metadata.get("address_type") or "").strip().lower() in {"public", "static", "external"}:
        return True

    return bool(metadata.get("has_public_ip"))


def _describe_resource_state(service_key: str, status: str, metadata: Dict[str, Any]) -> str:
    service_label = _service_label(service_key)
    details: List[str] = []

    for candidate in (metadata.get("machine_type"), metadata.get("vm_size")):
        if candidate and str(candidate) not in details:
            details.append(str(candidate))
            break

    for prefix, candidate in (
        ("sku", metadata.get("sku")),
        ("tier", metadata.get("tier")),
        ("db", metadata.get("database_version")),
        ("runtime", metadata.get("runtime")),
        ("k8s", metadata.get("kubernetes_version")),
    ):
        if candidate:
            details.append(f"{prefix} {candidate}")

    size_value = metadata.get("size_gb") or metadata.get("storage_gb")
    if size_value not in (None, "", 0, "0"):
        details.append(f"{size_value} GiB")

    node_count = metadata.get("node_count")
    if node_count not in (None, "", 0, "0"):
        node_count_value = int(float(node_count)) if str(node_count).replace(".", "", 1).isdigit() else node_count
        plural = "" if node_count_value == 1 else "s"
        details.append(f"{node_count_value} node{plural}")

    if _is_publicly_exposed(service_key, metadata):
        details.append("publicly reachable")

    if metadata.get("attached_to"):
        details.append(f"attached to {metadata['attached_to']}")
    elif metadata.get("attached") is False:
        details.append("currently unattached")

    if metadata.get("network"):
        details.append(f"net {metadata['network']}")

    compact_details = details[:3]
    if compact_details:
        return f"{status} · {service_label} · {', '.join(compact_details)}"
    return f"{status} · {service_label}"


def _describe_cost_basis(resource: Dict[str, Any]) -> str:
    cost_source = _resource_cost_source(resource)
    if cost_source == "actual":
        return "using billed monthly cost"
    if cost_source == "estimated":
        return "using scanner-estimated monthly cost"
    return "using the currently captured monthly cost footprint"


def _build_generic_change_candidate(
    resource: Dict[str, Any],
    mode: str,
) -> Optional[ChangeItem]:
    resource_id = str(resource.get("cloud_resource_id") or resource.get("id") or "")
    resource_name = str(resource.get("resource_name") or resource_id or "Resource")
    service_type = _normalize_service_key(resource.get("service_type") or resource.get("resource_type"))
    status = _normalize_status(resource.get("status"))
    status_lower = status.lower()
    monthly_cost = round(_to_number(resource.get("cost")), 2)
    metadata = _architecture_metadata(resource)
    cost_basis = _describe_cost_basis(resource)
    current_state = _describe_resource_state(service_type, status, metadata)
    publicly_exposed = _is_publicly_exposed(service_type, metadata)
    has_explicit_unattached_signal = metadata.get("attached") is False

    if mode == "cost_optimized":
        if monthly_cost <= 0 and status_lower not in {"zombie", "stopped"}:
            return None

        if status_lower in {"zombie", "stopped"}:
            change_type = "terminate"
            monthly_savings = monthly_cost
            proposed_state = "Retire the idle footprint after validating dependency ownership"
            risk_level = "low"
            reasoning = (
                f"{resource_name} is currently {status_lower} and still contributes "
                f"{_format_compact_amount(monthly_cost)}/mo {cost_basis}; retiring it is the cleanest low-risk savings move."
            )
        elif any(token in service_type for token in ("public_ip", "external_ip")) and has_explicit_unattached_signal:
            change_type = "terminate"
            monthly_savings = monthly_cost
            proposed_state = "Release the unattached public address and remove exposed edge drift"
            risk_level = "low"
            reasoning = (
                f"{resource_name} is a standalone public endpoint with no live attachment metadata and "
                f"{_format_compact_amount(monthly_cost)}/mo {cost_basis}; releasing it removes recurring edge spend."
            )
        elif any(token in service_type for token in ("disk", "storage", "bucket", "blob")):
            if metadata.get("attached") is False and monthly_cost > 0:
                change_type = "terminate"
                monthly_savings = monthly_cost
                proposed_state = "Remove the unattached storage volume after retention review"
                risk_level = "low"
                reasoning = (
                    f"{resource_name} is storage capacity that scan metadata marks as unattached; "
                    f"removing it eliminates {_format_compact_amount(monthly_cost)}/mo {cost_basis} without touching runtime compute."
                )
            else:
                change_type = "migrate"
                monthly_savings = round(monthly_cost * 0.15, 2)
                proposed_state = "Move the volume or bucket to a lower-cost tier with lifecycle cleanup"
                risk_level = "low"
                size_detail = metadata.get("size_gb") or metadata.get("storage_gb")
                reasoning = (
                    f"{resource_name} carries {_format_compact_amount(monthly_cost)}/mo {cost_basis}"
                    + (f" across {size_detail} GiB" if size_detail not in (None, "", 0, "0") else "")
                    + "; cooler storage tiers and retention cleanup are the lowest-risk optimization path."
                )
        elif any(token in service_type for token in ("database", "sql", "cloud_sql", "rds", "cosmos")):
            change_type = "downsize"
            monthly_savings = round(monthly_cost * 0.12, 2)
            proposed_state = "Right-size database compute and tighten backup retention windows"
            risk_level = "medium"
            tier_detail = metadata.get("tier") or metadata.get("sku") or metadata.get("database_version")
            reasoning = (
                f"{resource_name} is a database workload spending {_format_compact_amount(monthly_cost)}/mo {cost_basis}"
                + (f" on {tier_detail}" if tier_detail else "")
                + "; right-sizing and retention tuning should reduce steady-state spend after load validation."
            )
        else:
            change_type = "downsize"
            monthly_savings = round(monthly_cost * 0.18, 2)
            proposed_state = "Right-size compute shape and tune baseline scaling thresholds"
            risk_level = "medium"
            shape_detail = metadata.get("machine_type") or metadata.get("vm_size") or metadata.get("sku")
            reasoning = (
                f"{resource_name} currently runs at {_format_compact_amount(monthly_cost)}/mo {cost_basis}"
                + (f" on {shape_detail}" if shape_detail else "")
                + "; compute rightsizing is the highest-confidence savings move before deeper service refactoring."
            )
    else:
        if publicly_exposed:
            change_type = "tighten_security"
            monthly_savings = round(-(monthly_cost * 0.03), 2) if monthly_cost > 0 else 0.0
            proposed_state = "Place the workload behind tighter ingress policy and restrict public exposure"
            risk_level = "medium"
            exposure_detail = metadata.get("public_ip") or metadata.get("ip_address") or metadata.get("address") or metadata.get("url")
            shape_detail = metadata.get("machine_type") or metadata.get("vm_size") or metadata.get("runtime")
            reasoning = (
                f"{resource_name} exposes a public edge signal"
                + (f" ({exposure_detail})" if exposure_detail else "")
                + (f" on {shape_detail}" if shape_detail else "")
                + "; the target state introduces stricter ingress guardrails."
                + (f" The current cost baseline is {_format_compact_amount(monthly_cost)}/mo {cost_basis}." if monthly_cost > 0 else "")
            )
        elif any(token in service_type for token in ("database", "sql", "cloud_sql", "rds", "storage", "bucket", "blob", "disk")):
            change_type = "enable_encryption"
            monthly_savings = round(-(monthly_cost * 0.02), 2) if monthly_cost > 0 else 0.0
            proposed_state = "Enforce encryption, key rotation, and stronger backup governance"
            risk_level = "low"
            data_detail = metadata.get("database_version") or metadata.get("tier") or metadata.get("size_gb") or metadata.get("storage_gb")
            reasoning = (
                f"{resource_name} holds persistent data"
                + (f" ({data_detail})" if data_detail not in (None, "", 0, "0") else "")
                + "; the hardened target state turns on stronger encryption and recovery controls."
            )
        elif any(token in service_type for token in ("aks", "gke", "kubernetes", "cluster")) and metadata.get("node_count") in (1, "1"):
            change_type = "add_replica"
            monthly_savings = round(-(monthly_cost * 0.08), 2) if monthly_cost > 0 else 0.0
            proposed_state = "Add redundant worker capacity and stronger operational guardrails"
            risk_level = "medium"
            reasoning = (
                f"{resource_name} is a single-node container platform from live scan metadata; adding redundancy reduces outage blast radius."
            )
        else:
            change_type = "add_monitoring"
            monthly_savings = round(-(monthly_cost * 0.01), 2) if monthly_cost > 0 else 0.0
            proposed_state = "Add monitoring, alerting, and runtime protection coverage"
            risk_level = "low"
            runtime_detail = metadata.get("runtime") or metadata.get("machine_type") or metadata.get("vm_size")
            reasoning = (
                f"{resource_name} is kept in place but gains stronger telemetry and alert coverage"
                + (f" for {runtime_detail}" if runtime_detail else "")
                + " so the team can detect drift and incidents earlier."
            )

    return ChangeItem(
        resource_id=resource_id or resource_name,
        resource_name=resource_name,
        service_type=service_type,
        change_type=change_type,
        current_state=current_state,
        proposed_state=proposed_state,
        monthly_savings=round(monthly_savings, 2),
        risk_level=risk_level,
        reasoning=reasoning,
    )


def _render_generic_proposed_mermaid(
    provider: str,
    region: str,
    mode: str,
    graph_bundle: Dict[str, Any],
    changes: List[ChangeItem],
    estimated_savings: float,
) -> str:
    provider_label = _provider_label(provider)
    mode_label = _mode_label(mode)
    theme = PROVIDER_MERMAID_THEME.get(
        provider,
        {"fill": "#1e293b", "stroke": "#94a3b8"},
    )
    category_services: Dict[str, List[str]] = graph_bundle["category_services"]
    service_nodes: Dict[str, Dict[str, Any]] = graph_bundle["service_nodes"]
    displayed_resources: Dict[str, List[Dict[str, Any]]] = graph_bundle["displayed_resources"]
    relationship_edges: List[GraphEdge] = graph_bundle["relationship_edges"]
    services: Dict[str, List[Dict[str, Any]]] = graph_bundle["services"]

    target_root = sanitize_node_id(f"{provider}:{region}:{mode}:target", "tgt")
    outcome_node = sanitize_node_id(f"{provider}:{region}:{mode}:outcome", "sum")

    lines = [
        "flowchart LR",
        f'    {target_root}["{sanitize_label(f"{provider_label} {region} {mode_label} target")}"]',
    ]

    change_lookup = {change.resource_id: change for change in changes}
    service_target_lookup: Dict[str, str] = {}
    original_service_node_lookup: Dict[str, str] = {}
    service_nodes_by_category: Dict[str, List[str]] = defaultdict(list)
    resource_target_lookup: Dict[str, str] = {}
    stable_resource_nodes: List[str] = []
    change_nodes: List[str] = []

    for category in GENERIC_CATEGORY_ORDER:
        service_keys = [service_key for service_key in category_services.get(category, []) if service_key in services]
        if not service_keys:
            continue

        category_id = sanitize_node_id(f"{provider}:{region}:{mode}:{category}", "cat")
        lines.append(
            f'    subgraph {category_id} ["{sanitize_label(GENERIC_CATEGORY_LABELS.get(category, _service_label(category)))}"]'
        )

        for service_key in service_keys[:MAX_MERMAID_SERVICES]:
            service_resources = services.get(service_key, [])
            service_cost = sum(_to_number(resource.get("cost")) for resource in service_resources)
            service_delta = round(
                sum(change.monthly_savings for change in changes if change.service_type == service_key),
                2,
            )
            service_change_count = sum(1 for change in changes if change.service_type == service_key)
            service_cost_basis = _cost_provenance_label(service_resources)
            service_target_id = sanitize_node_id(f"{region}:{service_key}:{mode}:target", "opt")
            original_service_node_id = service_nodes[service_key]["node_id"]

            if service_change_count > 0:
                service_summary = (
                    f"{_service_label(service_key)} ({len(service_resources)} res, "
                    f"{_format_compact_amount(service_cost)}/mo, {service_change_count} change"
                    f"{'' if service_change_count == 1 else 's'}, {_format_monthly_impact(service_delta)}, {service_cost_basis})"
                )
            else:
                service_summary = (
                    f"{_service_label(service_key)} ({len(service_resources)} res, "
                    f"{_format_compact_amount(service_cost)}/mo, retain baseline, {service_cost_basis})"
                )

            lines.append(f'        {service_target_id}["{sanitize_label(service_summary)}"]')
            lines.append(f"        {target_root} --> {service_target_id}")

            service_target_lookup[service_key] = service_target_id
            original_service_node_lookup[original_service_node_id] = service_target_id
            service_nodes_by_category[category].append(service_target_id)

            ranked_resource_contexts = sorted(
                displayed_resources.get(service_key, []),
                key=lambda context: (0 if context["resource"].get("cloud_resource_id") in change_lookup else 1, -context["cost"]),
            )

            for resource_context in ranked_resource_contexts[:MAX_MERMAID_RESOURCES_PER_SERVICE]:
                original_resource_node_id = resource_context["node_id"]
                proposed_resource_node_id = sanitize_node_id(f"{original_resource_node_id}:{mode}", "pr")
                resource_name = resource_context["resource_name"]
                change = change_lookup.get(resource_context["resource"].get("cloud_resource_id"))

                if change:
                    label_text = (
                        f"{resource_name} ({_change_type_label(change.change_type)}, "
                        f"{_format_monthly_impact(change.monthly_savings)})"
                    )
                    change_nodes.append(proposed_resource_node_id)
                else:
                    label_text = (
                        f"{resource_name} (retain, {_format_compact_amount(resource_context['cost'])}/mo)"
                    )
                    stable_resource_nodes.append(proposed_resource_node_id)

                lines.append(f'        {proposed_resource_node_id}["{sanitize_label(label_text)}"]')
                lines.append(f"        {service_target_id} --> {proposed_resource_node_id}")
                resource_target_lookup[original_resource_node_id] = proposed_resource_node_id

        lines.append("    end")

    seen_relationships: Set[Tuple[str, str, str, Optional[str]]] = set()
    for edge in relationship_edges:
        source_id = original_service_node_lookup.get(edge.source) or resource_target_lookup.get(edge.source)
        target_id = original_service_node_lookup.get(edge.target) or resource_target_lookup.get(edge.target)
        if not source_id or not target_id or source_id == target_id:
            continue

        connector = "-.->" if edge.style == "dotted" else "-->"
        label = sanitize_label(edge.label) if edge.label else None
        key = (source_id, target_id, connector, label)
        if key in seen_relationships:
            continue
        seen_relationships.add(key)

        if label:
            lines.append(f"    {source_id} {connector}|{label}| {target_id}")
        else:
            lines.append(f"    {source_id} {connector} {target_id}")

    if mode == "cost_optimized":
        outcome_text = f"Estimated savings {_format_compact_amount(estimated_savings)}/mo"
    else:
        outcome_text = f"Monthly delta {_format_monthly_impact(estimated_savings)}"
    lines.append(f'    {outcome_node}["{sanitize_label(outcome_text)}"]')
    lines.append(f"    {target_root} --> {outcome_node}")

    lines.extend([
        f'    classDef root fill:{theme["fill"]},stroke:{theme["stroke"]},color:#ffffff,stroke-width:2px',
        "    classDef resource fill:#0f172a,stroke:#475569,color:#e2e8f0,stroke-width:1px",
        "    classDef action fill:#111827,stroke:#f59e0b,color:#f8fafc,stroke-width:1.25px",
        "    classDef outcome fill:#052e16,stroke:#10b981,color:#ecfdf5,stroke-width:1.5px",
    ])

    for category, node_ids in service_nodes_by_category.items():
        if not node_ids:
            continue
        theme_tokens = GENERIC_CATEGORY_THEME.get(category, GENERIC_CATEGORY_THEME["other"])
        lines.append(
            f'    classDef cat_{category} fill:{theme_tokens["fill"]},stroke:{theme_tokens["stroke"]},color:#ffffff,stroke-width:1.5px'
        )
        lines.append(f"    class {','.join(node_ids)} cat_{category}")

    lines.append(f"    class {target_root} root")
    if stable_resource_nodes:
        lines.append(f"    class {','.join(stable_resource_nodes)} resource")
    if change_nodes:
        lines.append(f"    class {','.join(change_nodes)} action")
    lines.append(f"    class {outcome_node} outcome")

    return "\n".join(lines)


def _build_generic_proposed_result(
    provider: str,
    integration_id: str,
    region: str,
    resources: List[Dict[str, Any]],
    mode: str,
) -> ProposedResult:
    region_resources = [resource for resource in resources if _resource_in_region(resource, region, provider)]
    if not region_resources:
        return ProposedResult(
            mode=mode,
            integration_id=integration_id,
            region=region,
            proposed_mermaid="",
            change_list=[],
            estimated_savings=0.0,
            risk_tradeoffs=f"No {provider.upper()} resources found in region {region}.",
            warnings=[{
                "type": "no_resources_found",
                "message": f"No {provider.upper()} resources found in region {region}. Run a scan first.",
            }],
        )

    ranked = sorted(
        region_resources,
        key=lambda resource: (
            1 if mode == "reliability_security_optimized" and _is_publicly_exposed(
                _normalize_service_key(resource.get("service_type") or resource.get("resource_type")),
                _architecture_metadata(resource),
            ) else 0,
            1 if _normalize_status(resource.get("status")).lower() in {"zombie", "stopped"} else 0,
            _to_number(resource.get("cost")),
        ),
        reverse=True,
    )

    graph_bundle = _build_generic_graph_data(region, region_resources)
    changes: List[ChangeItem] = []
    change_counts_by_service: Dict[str, int] = defaultdict(int)
    seen_resource_ids: Set[str] = set()
    for resource in ranked:
        if len(changes) >= 6:
            break
        candidate = _build_generic_change_candidate(resource, mode)
        if not candidate:
            continue

        if candidate.resource_id in seen_resource_ids:
            continue
        if change_counts_by_service[candidate.service_type] >= 2:
            continue

        changes.append(candidate)
        seen_resource_ids.add(candidate.resource_id)
        change_counts_by_service[candidate.service_type] += 1

    estimated_savings = round(sum(change.monthly_savings for change in changes), 2)
    proposed_mermaid = _render_generic_proposed_mermaid(
        provider=provider,
        region=region,
        mode=mode,
        graph_bundle=graph_bundle,
        changes=changes,
        estimated_savings=estimated_savings,
    )

    provider_label = _provider_label(provider)
    change_count = len(changes)
    cost_summary = graph_bundle["cost_summary"]
    relationship_summary = graph_bundle["relationship_summary"]
    total_resources = len(region_resources)
    relationship_count = relationship_summary["resource_edges"] + relationship_summary["service_edges"]
    if mode == "cost_optimized":
        risk_tradeoffs = (
            f"Generated {change_count} deterministic optimization changes across {len(change_counts_by_service)} services "
            f"from {total_resources} scanned {provider_label} resources in {region}. "
            f"{cost_summary['actual']} resources use billed monthly cost and {cost_summary['estimated']} still rely on "
            f"estimate-backed cost. The target topology reuses {relationship_count} live attachment or network relationships "
            "from scan metadata, and savings remain a review-before-apply estimate."
        )
    else:
        risk_tradeoffs = (
            f"Generated {change_count} deterministic resilience and hardening changes across {len(change_counts_by_service)} services "
            f"from {total_resources} scanned {provider_label} resources in {region}. "
            f"{cost_summary['actual']} resources use billed monthly cost and {cost_summary['estimated']} use estimates. "
            f"The target-state relationships come from {relationship_count} live metadata-derived edges, and this mode may add "
            "incremental monthly cost for monitoring, encryption, or managed guardrails."
        )

    warnings = [{
        "type": "deterministic_proposed",
        "message": f"{provider_label} proposed architecture was generated deterministically from scan data.",
    }]
    cost_warning = _cost_provenance_warning(region_resources, provider, region)
    if cost_warning:
        warnings.append(cost_warning)
    if relationship_count > 0:
        warnings.append({
            "type": "inferred_relationships",
            "message": (
                f"{relationship_count} target-state connections in {region} were derived from live attachment and "
                "network metadata instead of a provider-managed topology export."
            ),
        })
    if not changes:
        warnings.append({
            "type": "no_change_candidates",
            "message": f"No high-confidence {provider_label} architecture changes were found in {region}; showing a grouped target-state diagram only.",
        })

    return ProposedResult(
        mode=mode,
        integration_id=integration_id,
        region=region,
        proposed_mermaid=proposed_mermaid,
        change_list=changes,
        estimated_savings=estimated_savings,
        risk_tradeoffs=risk_tradeoffs,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Existing: Mermaid-only endpoint (AWS backward-compatible)
# ---------------------------------------------------------------------------

@router.get("/aws/current", response_model=ArchitectureResult)
async def get_aws_current_architecture(
    integration_id: str,
    region: Optional[str] = None,
    vpc_id: Optional[str] = None,
    view: str = "summary",  # summary, hotspots, vpc_detail
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Generate deterministic AWS architecture diagrams from the latest scan data.
    """
    if view not in VALID_CURRENT_VIEWS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view: '{view}'. Must be one of: {', '.join(sorted(VALID_CURRENT_VIEWS))}",
        )
    if view == "vpc_detail" and not vpc_id:
        raise HTTPException(status_code=400, detail="vpc_id is required for vpc_detail view")
    if view == "vpc_detail" and not region:
        raise HTTPException(status_code=400, detail="region is required for vpc_detail view")

    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.get("provider") != "aws":
        raise HTTPException(
            status_code=400,
            detail="Architecture diagrams currently only supported for AWS",
        )

    resources = await db.get_resources_for_integration(user.id, integration_id)
    if not resources:
        return ArchitectureResult(
            provider="aws",
            integration_id=integration_id,
            generated_at=integration.get("last_scan") or "",
            regions=[],
        )

    target_regions = _collect_target_regions(resources, integration, "aws", region)
    regions_result = []

    for target_region in target_regions:
        topology = build_region_topology(resources, region=target_region)
        region_res = ArchitectureRegionResult(
            region=target_region,
            total_cost=topology.total_cost,
            total_waste=topology.total_waste,
            resource_count=topology.resource_count,
            vpc_index=[],
            views={},
        )

        if view == "vpc_detail":
            detail_res = render_vpc_detail(topology, vpc_id)
            if not detail_res:
                raise HTTPException(status_code=404, detail=f"VPC {vpc_id} not found in region {target_region}")
            region_res.views["vpc_detail"] = detail_res
        elif view == "hotspots":
            region_res.views["hotspots"] = render_cost_hotspots(topology)
        else:
            region_res.views["summary"] = render_topology_summary(topology)

        regions_result.append(region_res)

    return ArchitectureResult(
        provider="aws",
        integration_id=integration_id,
        generated_at=integration.get("last_scan") or "",
        regions=regions_result,
    )


# ---------------------------------------------------------------------------
# Graph JSON endpoint (interactive frontend) for AWS/Azure/GCP
# ---------------------------------------------------------------------------

@router.get("/{provider}/graph")
async def get_architecture_graph(
    provider: str,
    integration_id: str,
    region: Optional[str] = None,
    vpc_id: Optional[str] = None,
    view: str = "all",
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    provider = _normalize_provider(provider)

    if view not in VALID_GRAPH_VIEWS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view: '{view}'. Must be one of: {', '.join(sorted(VALID_GRAPH_VIEWS))}",
        )
    if view == "vpc_detail" and not vpc_id and provider == "aws":
        raise HTTPException(status_code=400, detail="vpc_id is required for AWS vpc_detail view")
    if view == "vpc_detail" and not region and provider == "aws":
        raise HTTPException(status_code=400, detail="region is required for AWS vpc_detail view")

    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration_provider = str(integration.get("provider", "")).lower()
    if integration_provider != provider:
        raise HTTPException(
            status_code=400,
            detail=f"Integration provider mismatch. Expected '{provider}', found '{integration_provider or 'unknown'}'.",
        )

    resources = await db.get_resources_for_integration(user.id, integration_id)
    if not resources:
        empty_response = GraphResponse(
            provider=provider,
            integration_id=integration_id,
            generated_at=integration.get("last_scan") or "",
            regions=[],
        )
        result = empty_response.to_dict()
        result["warnings"] = [{
            "type": "no_resources_found",
            "message": f"No {provider.upper()} resources found. Run a scan first to populate the architecture diagram.",
        }]
        return result

    permission_alerts: List[Dict[str, Any]] = []
    try:
        alerts = await db.select(
            "agent_notifications",
            filters={"user_id": user.id, "type": "permission_alert"},
        )
        permission_alerts = alerts or []
    except Exception:
        permission_alerts = []

    target_regions = _collect_target_regions(resources, integration, provider, region)
    regions_result: List[RegionGraphResult] = []

    if provider == "aws":
        for target_region in target_regions:
            topology = build_region_topology(resources, region=target_region)
            region_resources = [resource for resource in resources if _resource_in_region(resource, target_region, provider)]
            region_result = build_region_graph_result(
                topology=topology,
                resources=region_resources,
                views_requested=view,
                vpc_id=vpc_id,
                permission_alerts=permission_alerts,
            )
            regions_result.append(region_result)
    elif provider == "azure":
        for target_region in target_regions:
            topology = build_azure_region_topology(resources, region=target_region)
            region_resources = [resource for resource in resources if _resource_in_region(resource, target_region, provider)]
            region_result = build_region_graph_result(
                topology=topology,
                resources=region_resources,
                views_requested=view,
                vpc_id=vpc_id,
                permission_alerts=permission_alerts,
            )
            regions_result.append(region_result)
    elif provider == "gcp":
        for target_region in target_regions:
            topology = build_gcp_region_topology(resources, region=target_region)
            region_resources = [resource for resource in resources if _resource_in_region(resource, target_region, provider)]
            region_result = build_region_graph_result(
                topology=topology,
                resources=region_resources,
                views_requested=view,
                vpc_id=vpc_id,
                permission_alerts=permission_alerts,
            )
            regions_result.append(region_result)
    else:
        for target_region in target_regions:
            regions_result.append(
                _build_generic_region_result(
                    provider=provider,
                    integration_id=integration_id,
                    region=target_region,
                    resources=resources,
                    views_requested=view,
                    permission_alerts=permission_alerts,
                )
            )

    response = GraphResponse(
        provider=provider,
        integration_id=integration_id,
        generated_at=integration.get("last_scan") or "",
        regions=regions_result,
    )
    result = response.to_dict()
    result["discovered_regions"] = target_regions
    result["total_resources"] = len(resources)
    return result


# ---------------------------------------------------------------------------
# Proposed architecture endpoint (user-triggered)
# ---------------------------------------------------------------------------

class ProposedRequest(BaseModel):
    """Request body for proposed architecture generation."""
    constraints: List[str] = Field(
        default_factory=list,
        description="Optional user constraints (e.g. 'keep prod-db running')",
    )


@router.post("/{provider}/proposed")
async def generate_provider_proposed_architecture(
    provider: str,
    integration_id: str,
    region: str,
    mode: str = "cost_optimized",
    body: ProposedRequest = ProposedRequest(),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    provider = _normalize_provider(provider)

    if mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: '{mode}'. Must be one of: {', '.join(sorted(VALID_MODES))}",
        )

    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration_provider = str(integration.get("provider", "")).lower()
    if integration_provider != provider:
        raise HTTPException(
            status_code=400,
            detail=f"Integration provider mismatch. Expected '{provider}', found '{integration_provider or 'unknown'}'.",
        )

    resources = await db.get_resources_for_integration(user.id, integration_id)
    if not resources:
        raise HTTPException(status_code=404, detail="No resources found. Run a scan first.")

    topology_builder = {
        "aws": build_region_topology,
        "azure": build_azure_region_topology,
        "gcp": build_gcp_region_topology,
    }.get(provider)

    if topology_builder:
        topology = topology_builder(resources, region=region)
        if topology.resource_count == 0:
            raise HTTPException(status_code=404, detail=f"No resources found in region {region}")

        from ..architecture.proposed_generator import generate_proposed_architecture

        result = await generate_proposed_architecture(
            topology=topology,
            resources=[resource for resource in resources if _resource_in_region(resource, region, provider)],
            mode=mode,
            integration_id=integration_id,
            constraints=body.constraints or None,
        )
        return result.to_dict()

    generic_result = _build_generic_proposed_result(
        provider=provider,
        integration_id=integration_id,
        region=region,
        resources=resources,
        mode=mode,
    )
    return generic_result.to_dict()


@router.post("/{provider}/report")
async def generate_architecture_report_endpoint(
    provider: str,
    integration_id: str,
    region: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Generate a professional AI-powered architecture report.
    Returns structured markdown suitable for PDF rendering on the frontend.
    """
    provider = _normalize_provider(provider)

    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration_provider = str(integration.get("provider", "")).lower()
    if integration_provider != provider:
        raise HTTPException(status_code=400, detail="Integration provider mismatch.")

    resources = await db.get_resources_for_integration(user.id, integration_id)
    if not resources:
        raise HTTPException(status_code=404, detail="No resources found. Run a scan first.")

    # Build graph data to pass to report generator
    topology_builder = {
        "aws": build_region_topology,
        "azure": build_azure_region_topology,
        "gcp": build_gcp_region_topology,
    }.get(provider, build_region_topology)

    topology = topology_builder(resources, region=region)
    region_resources = [r for r in resources if _resource_in_region(r, region, provider)]
    graph_result = build_region_graph_result(
        topology=topology,
        resources=region_resources,
        views_requested="topology_summary",
        vpc_id=None,
        permission_alerts=[],
    )

    view_data = graph_result.views.get("topology_summary")
    mermaid_code = view_data.mermaid if view_data else ""
    nodes = [n.to_dict() for n in (view_data.graph.nodes if view_data else [])]
    coverage = graph_result.coverage.to_dict()
    warnings = coverage.get("warnings", [])

    from ..architecture.report_generator import generate_architecture_report

    result = await generate_architecture_report(
        provider=provider,
        integration_name=integration.get("name") or f"{provider.upper()} Integration",
        region=region,
        mermaid_code=mermaid_code,
        nodes=nodes,
        coverage=coverage,
        warnings=warnings,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Report generation failed"))

    return result
