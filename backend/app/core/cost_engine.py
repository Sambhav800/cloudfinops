import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .price_service import price_service

logger = logging.getLogger(__name__)

_HOURS_PER_MONTH = 730.0
_DEFAULT_REGIONS = {
    "aws": "us-east-1",
    "azure": "eastus",
    "gcp": "us-central1",
    "generic": "global",
}
_RESOURCE_TYPE_ALIASES = {
    "aws_alb": "aws_lb",
    "google_compute_engine": "google_compute_instance",
}
_AWS_INSTANCE_MONTHLY = {
    "t3.nano": 3.80,
    "t3.micro": 7.59,
    "t3.small": 15.18,
    "t3.medium": 30.37,
    "t3.large": 60.74,
    "t3.xlarge": 121.47,
    "t3.2xlarge": 242.94,
    "m5.large": 70.08,
    "m5.xlarge": 140.16,
    "m5.2xlarge": 280.32,
    "c5.large": 62.05,
    "c5.xlarge": 124.10,
    "r5.large": 91.98,
    "r5.xlarge": 183.96,
}
_AWS_RDS_INSTANCE_MONTHLY = {
    "db.t3.micro": 15.33,
    "db.t3.small": 30.66,
    "db.t3.medium": 49.64,
    "db.t3.large": 99.28,
    "db.t4g.medium": 40.88,
    "db.m5.large": 140.16,
}
_AWS_STORAGE_GB_MONTHLY = {
    "gp2": 0.115,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.138,
    "st1": 0.045,
    "sc1": 0.025,
    "standard": 0.023,
}
_AZURE_VM_MONTHLY = {
    "standard_b1s": 7.59,
    "standard_b1ms": 12.26,
    "standard_b2s": 30.37,
    "standard_b2ms": 48.91,
    "standard_b4ms": 97.82,
    "standard_d2s_v3": 70.08,
    "standard_d4s_v3": 140.16,
    "standard_d2as_v4": 62.05,
    "standard_d4as_v4": 124.10,
    "standard_e2s_v3": 91.98,
    "standard_e4s_v3": 183.96,
    "standard_f2s_v2": 61.32,
    "standard_f4s_v2": 122.64,
    "standard_ds1_v2": 42.34,
    "standard_ds2_v2": 84.68,
}
_AZURE_DISK_GB_MONTHLY = {
    "premium_lrs": 0.12,
    "premiumv2_lrs": 0.14,
    "ultrassd_lrs": 0.18,
    "standardssd_lrs": 0.08,
    "standard_lrs": 0.05,
}
_AZURE_APP_SERVICE_PLAN_MONTHLY = {
    "f1": 0.0,
    "d1": 10.0,
    "b1": 55.0,
    "b2": 110.0,
    "b3": 220.0,
    "s1": 73.0,
    "s2": 146.0,
    "s3": 292.0,
    "p1v3": 146.0,
    "p2v3": 292.0,
    "p3v3": 584.0,
}
_AZURE_SQL_MONTHLY = {
    "basic": 4.99,
    "s0": 15.0,
    "s1": 30.0,
    "s2": 75.0,
    "gp_s_gen5_2": 150.0,
    "gp_s_gen5_4": 300.0,
}
_GCP_MACHINE_HOUR_PRICE = {
    "n1-standard-1": 0.0475,
    "n1-standard-2": 0.0950,
    "n1-standard-4": 0.1900,
    "n1-standard-8": 0.3800,
    "n1-highmem-2": 0.1184,
    "n2-standard-2": 0.0971,
    "n2-standard-4": 0.1942,
    "n2-standard-8": 0.3883,
    "e2-micro": 0.0084,
    "e2-small": 0.0168,
    "e2-medium": 0.0335,
    "e2-standard-2": 0.0670,
    "e2-standard-4": 0.1341,
    "e2-standard-8": 0.2681,
    "c2-standard-4": 0.2088,
    "c2-standard-8": 0.4176,
    "f1-micro": 0.0076,
    "g1-small": 0.0257,
}
_GCP_DISK_GB_MONTHLY = {
    "pd-standard": 0.040,
    "pd-balanced": 0.100,
    "pd-ssd": 0.170,
    "pd-extreme": 0.220,
}
_GCP_SQL_HOUR_PRICE = {
    "db-f1-micro": 0.0150,
    "db-g1-small": 0.0500,
    "db-n1-standard-1": 0.0965,
    "db-n1-standard-2": 0.1930,
    "db-n1-standard-4": 0.3860,
    "db-n1-standard-8": 0.7720,
    "db-n1-highmem-2": 0.1210,
    "db-n1-highmem-4": 0.2420,
}
_GENERIC_COMPUTE_FAMILY_RATE = {
    "aws": 7.59,
    "azure": 8.25,
    "gcp": 8.4,
    "generic": 8.0,
}
_GENERIC_SIZE_UNITS = {
    "nano": 0.5,
    "micro": 1.0,
    "small": 2.0,
    "medium": 4.0,
    "large": 8.0,
    "xlarge": 16.0,
}


def _finding_extract_value(data: Dict[str, Any], path: str) -> Any:
    value: Any = data
    for key in path.split("."):
        if isinstance(value, list):
            try:
                value = value[int(key)]
            except (ValueError, IndexError):
                return None
        elif isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _finding_text(data: Dict[str, Any], paths: List[str]) -> str:
    for path in paths:
        raw_value = _finding_extract_value(data, path)
        if isinstance(raw_value, list):
            for item in raw_value:
                if item is not None and str(item).strip():
                    return str(item).strip()
        elif raw_value is not None and str(raw_value).strip():
            return str(raw_value).strip()
    return ""


def _finding_float(data: Dict[str, Any], paths: List[str]) -> float:
    for path in paths:
        raw_value = _finding_extract_value(data, path)
        if raw_value in (None, "", []):
            continue
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            continue
    return 0.0


def generate_findings(resources: List[Dict[str, Any]], unestimated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate deterministic simulator findings from Terraform plan attributes.

    Findings are advisory and separate from billing totals. Monetary impact is
    only attached when the simulator row was priced from an exact catalog match.
    """
    _ = unestimated
    findings: List[Dict[str, Any]] = []

    for resource in resources:
        resource_type = str(resource.get("resource_type") or resource.get("type") or "")
        address = str(resource.get("resource_address") or resource.get("name") or resource.get("address") or "unknown")
        attributes = resource.get("attributes") if isinstance(resource.get("attributes"), dict) else {}
        pricing_source = str(resource.get("pricing_source") or "")

        if resource_type == "aws_ebs_volume":
            volume_type = _finding_text(attributes, ["type", "volume_type"]).lower()
            if volume_type == "gp2":
                size_gb = _finding_float(attributes, ["size", "volume_size"])
                findings.append(
                    {
                        "resource_address": address,
                        "finding_id": "ebs-gp2-to-gp3",
                        "severity": "high",
                        "monthly_impact": None,
                        "annual_impact": None,
                        "evidence": (
                            f"Volume type is gp2 on a {size_gb:g}GB EBS volume."
                            if size_gb > 0
                            else "Volume type is gp2."
                        ),
                        "remediation": "Change the EBS volume type from gp2 to gp3 after validating workload requirements.",
                        "confidence": "high" if pricing_source == "exact_api" else "medium",
                    }
                )

        if resource_type in {"aws_instance", "aws_autoscaling_group"}:
            instance_type = _finding_text(
                attributes,
                [
                    "instance_type",
                    "launch_template.0.instance_type",
                    "mixed_instances_policy.0.launch_template.0.override.0.instance_type",
                ],
            ).lower()
            old_generations = ("c4.", "m4.", "r4.", "t2.", "m3.", "c3.", "r3.")
            if any(instance_type.startswith(prefix) for prefix in old_generations):
                findings.append(
                    {
                        "resource_address": address,
                        "finding_id": "ec2-old-generation",
                        "severity": "medium",
                        "monthly_impact": None,
                        "annual_impact": None,
                        "evidence": f"Instance type '{instance_type}' is a previous-generation EC2 family.",
                        "remediation": "Compare against the equivalent current-generation family and validate performance before applying.",
                        "confidence": "medium",
                    }
                )

        if resource_type in {"aws_eip", "google_compute_address", "azurerm_public_ip"}:
            after_cost = float(resource.get("after_monthly") or resource.get("after") or 0.0)
            findings.append(
                {
                    "resource_address": address,
                    "finding_id": "public-ipv4-cost",
                    "severity": "low",
                    "monthly_impact": after_cost if pricing_source == "exact_api" else None,
                    "annual_impact": round(after_cost * 12, 2) if pricing_source == "exact_api" else None,
                    "evidence": "Public IPv4 address resource detected in the Terraform plan.",
                    "remediation": "Release unused public IPs and prefer private routing behind NAT or load balancers where possible.",
                    "confidence": "high" if pricing_source == "exact_api" else "medium",
                }
            )

        if resource_type == "aws_nat_gateway":
            after_cost = float(resource.get("after_monthly") or resource.get("after") or 0.0)
            findings.append(
                {
                    "resource_address": address,
                    "finding_id": "nat-gateway-baseline",
                    "severity": "medium",
                    "monthly_impact": after_cost if pricing_source == "exact_api" else None,
                    "annual_impact": round(after_cost * 12, 2) if pricing_source == "exact_api" else None,
                    "evidence": "NAT Gateway resource detected; fixed hourly and traffic processing charges can be material.",
                    "remediation": "For low-traffic environments, validate whether shared egress or an existing NAT path is sufficient.",
                    "confidence": "high" if pricing_source == "exact_api" else "medium",
                }
            )

    return findings


class CostMapper:
    """
    Parse Terraform plan JSON and estimate monthly cost changes.

    Exact provider catalog pricing is used when the existing resource mapping
    can be resolved through Infracost. When that is unavailable, the estimator
    falls back to provider-aware heuristics for common resource families and
    explicit zero-cost usage notes for usage-based/control-plane resources.
    """

    def __init__(self) -> None:
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Any]:
        try:
            path = os.path.join(os.path.dirname(__file__), "resource_mappings.json")
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file).get("resources", {})
        except Exception as exc:
            logger.error("Failed to load resource mappings: %s", exc)
            return {}

    def _extract_value(self, data: Dict[str, Any], path: str) -> Any:
        keys = path.split(".")
        value: Any = data
        for key in keys:
            if isinstance(value, list):
                try:
                    value = value[int(key)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _extract_string(self, data: Dict[str, Any], paths: List[str], default: str = "") -> str:
        for path in paths:
            raw_value = self._extract_value(data, path)
            if raw_value is None:
                continue
            if isinstance(raw_value, list):
                for item in raw_value:
                    if item is not None and str(item).strip():
                        return str(item).strip()
                continue
            text = str(raw_value).strip()
            if text:
                return text
        return default

    def _extract_float(self, data: Dict[str, Any], paths: List[str], default: float = 0.0) -> float:
        for path in paths:
            raw_value = self._extract_value(data, path)
            if raw_value in (None, "", []):
                continue
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                continue
        return default

    def _extract_int(self, data: Dict[str, Any], paths: List[str], default: int = 0) -> int:
        value = self._extract_float(data, paths, float(default))
        return int(round(value))

    def _apply_transform(self, value: Any, transform: str) -> Any:
        if transform == "title":
            text = str(value).lower() if value else ""
            if text == "mysql":
                return "MySQL"
            if text == "postgresql":
                return "PostgreSQL"
            if text == "mariadb":
                return "MariaDB"
            return text.capitalize()
        if transform == "multi_az":
            return "Multi-AZ" if value else "Single-AZ"
        if transform == "rds_volume_type":
            return "General Purpose" if str(value).lower() in ["gp2", "gp3"] else "Provisioned IOPS (SSD)"
        return value

    def _resolve_filters(self, component: Dict[str, Any], values: Dict[str, Any]) -> List[Dict[str, str]]:
        resolved: List[Dict[str, str]] = []
        for filter_item in component.get("filters", []):
            item = {"key": filter_item["key"]}
            if "value" in filter_item:
                item["value"] = filter_item["value"]
            elif "value_regex" in filter_item:
                item["value_regex"] = filter_item["value_regex"]
            elif "attribute" in filter_item:
                raw_value = self._extract_value(values, filter_item["attribute"])
                if raw_value is None:
                    raw_value = filter_item.get("default")
                if "transform" in filter_item:
                    raw_value = self._apply_transform(raw_value, filter_item["transform"])
                item["value"] = str(raw_value)
            resolved.append(item)
        return resolved

    def _normalize_resource_type(self, resource_type: str) -> str:
        normalized = (resource_type or "").strip().lower()
        return _RESOURCE_TYPE_ALIASES.get(normalized, normalized)

    def _infer_provider(self, resource_type: str, provider_name: str) -> str:
        normalized_type = self._normalize_resource_type(resource_type)
        provider_name_normalized = (provider_name or "").lower()

        if "azurerm" in provider_name_normalized or normalized_type.startswith("azurerm_"):
            return "azure"
        if (
            "google" in provider_name_normalized
            or "gcp" in provider_name_normalized
            or normalized_type.startswith("google_")
        ):
            return "gcp"
        if "aws" in provider_name_normalized or normalized_type.startswith("aws_"):
            return "aws"

        prefix = normalized_type.split("_", 1)[0]
        if prefix in {"azure", "azurerm"}:
            return "azure"
        if prefix in {"google", "gcp"}:
            return "gcp"
        if prefix == "aws":
            return "aws"
        return "generic"

    def _default_region(self, provider: str) -> str:
        return _DEFAULT_REGIONS.get(provider, _DEFAULT_REGIONS["generic"])

    def _normalize_region(self, provider: str, candidate: str) -> str:
        text = str(candidate or "").strip()
        if not text:
            return self._default_region(provider)

        normalized = text.lower()
        parts = normalized.split("-")
        if provider == "aws" and len(parts) >= 4 and len(parts[-1]) == 1 and parts[-1].isalpha():
            return "-".join(parts[:-1])
        if provider == "gcp" and len(parts) >= 3 and len(parts[-1]) == 1 and parts[-1].isalpha():
            return "-".join(parts[:-1])
        return normalized

    def _extract_regions(self, tf_plan: Dict[str, Any]) -> Dict[str, str]:
        regions: Dict[str, str] = {}
        provider_configs = tf_plan.get("configuration", {}).get("provider_config", {})
        for alias, config in provider_configs.items():
            expressions = config.get("expressions", {})
            region = (
                expressions.get("region", {}).get("constant_value")
                or expressions.get("location", {}).get("constant_value")
            )
            if region:
                regions[alias] = str(region)
        return regions

    def _detect_region(
        self,
        global_regions: Dict[str, str],
        provider_name: str,
        values: Dict[str, Any],
        provider: str,
    ) -> str:
        candidate = self._extract_string(
            values,
            [
                "region",
                "location",
                "region_name",
                "availability_zone",
                "zone",
                "primary_location",
            ],
        )
        if candidate:
            return self._normalize_region(provider, candidate)

        alias = provider_name.split("/")[-1] if provider_name else ""
        if alias and alias in global_regions:
            return self._normalize_region(provider, global_regions[alias])

        for known_region in global_regions.values():
            if known_region:
                return self._normalize_region(provider, known_region)

        return self._default_region(provider)

    def _extract_instance_count(self, values: Dict[str, Any]) -> int:
        count = self._extract_int(
            values,
            [
                "instance_count",
                "desired_capacity",
                "count",
                "node_count",
                "nodes",
                "number_of_nodes",
                "min_count",
                "default_node_pool.0.node_count",
                "default_node_pool.0.min_count",
                "default_node_pool.0.max_count",
                "scaling_config.0.desired_size",
                "sku.capacity",
                "capacity",
            ],
            default=1,
        )
        return max(count, 1)

    def _estimate_storage_size_gb(self, values: Dict[str, Any], default: float = 0.0) -> float:
        size_gb = self._extract_float(
            values,
            [
                "size",
                "size_gb",
                "disk_size_gb",
                "storage_size_in_gb",
                "allocated_storage",
                "max_size_gb",
                "root_block_device.0.volume_size",
                "boot_disk.0.initialize_params.0.size",
                "storage_mb",
            ],
            default=default,
        )
        if size_gb <= 0:
            return default
        if size_gb > 0 and size_gb < 1:
            return size_gb
        return size_gb

    def _infer_resource_family(self, resource_type: str, values: Dict[str, Any]) -> str:
        normalized_type = self._normalize_resource_type(resource_type)
        if any(token in normalized_type for token in ["db_", "database", "sql", "redis", "cache", "postgres", "mysql", "mariadb", "cosmos", "spanner"]):
            return "database"
        if any(token in normalized_type for token in ["nat_gateway", "load_balancer", "_lb", "application_gateway", "forwarding_rule", "public_ip", "eip", "address"]):
            return "network"
        if any(token in normalized_type for token in ["eks", "aks", "gke", "container_cluster", "kubernetes", "_cluster", "_node_group", "_node_pool"]) and "db_" not in normalized_type:
            return "kubernetes"
        if any(token in normalized_type for token in ["disk", "volume", "bucket", "storage", "snapshot", "blob", "file_share"]):
            return "storage"
        if any(token in normalized_type for token in ["function", "lambda", "cloud_run", "web_app", "container_app", "serverless"]):
            return "serverless"
        if any(token in normalized_type for token in ["instance", "virtual_machine", "vm", "machine", "scale_set", "app_service_plan"]):
            return "compute"
        if self._extract_string(values, ["instance_type", "vm_size", "machine_type"]):
            return "compute"
        return "other"

    def _is_usage_based_zero_resource(self, resource_type: str) -> bool:
        normalized_type = self._normalize_resource_type(resource_type)
        recurring_tokens = [
            "instance",
            "virtual_machine",
            "vm",
            "db_",
            "database",
            "sql",
            "redis",
            "cache",
            "disk",
            "volume",
            "snapshot",
            "nat_gateway",
            "load_balancer",
            "_lb",
            "application_gateway",
            "forwarding_rule",
            "public_ip",
            "eip",
            "address",
            "app_service_plan",
            "cluster",
            "node_group",
            "node_pool",
        ]
        if any(token in normalized_type for token in recurring_tokens):
            return False

        usage_tokens = [
            "bucket",
            "storage_account",
            "function",
            "lambda",
            "cloud_run",
            "queue",
            "topic",
            "pubsub",
            "sns",
            "sqs",
            "firewall",
            "security_group",
            "nsg",
            "role",
            "policy",
            "iam",
            "subnet",
            "vpc",
            "network_interface",
            "route_table",
            "route",
            "dns",
            "monitor",
            "log",
            "secret",
            "kms",
            "key_vault",
        ]
        return any(token in normalized_type for token in usage_tokens)

    async def _calculate_component(
        self,
        vendor: str,
        service: str,
        product_family: str,
        region: str,
        component: Dict[str, Any],
        values: Dict[str, Any],
    ) -> tuple[float, Optional[str], bool]:
        filters = self._resolve_filters(component, values)
        price = await price_service.get_infracost_price(vendor, service, product_family, region, filters)
        if price is None:
            return 0.0, None, False

        multiplier = _HOURS_PER_MONTH if component.get("hourly", True) else 1.0
        attribute_multiplier = 1.0
        if "multiplier_attribute" in component:
            raw_value = self._extract_value(values, component["multiplier_attribute"])
            if raw_value is not None:
                try:
                    attribute_multiplier = float(raw_value)
                except (TypeError, ValueError):
                    attribute_multiplier = 1.0
        multiplier *= attribute_multiplier

        cost = price * multiplier
        note = None
        if component.get("usage_baseline"):
            cost = price * multiplier * float(component["usage_baseline"])
            note = f"Estimated usage baseline applied for {component.get('name', 'resource component')}"

        return cost, note, True

    async def _calculate_exact_cost(
        self,
        resource_type: str,
        values: Dict[str, Any],
        region: str,
    ) -> Dict[str, Any]:
        entry = self.mappings.get(resource_type)
        if isinstance(entry, str):
            entry = self.mappings.get(entry)

        resource_family = self._infer_resource_family(resource_type, values)
        if not entry:
            return {
                "cost": 0.0,
                "notes": [],
                "pricing_source": "unsupported",
                "resource_family": resource_family,
                "matched": False,
            }

        vendor = entry["vendor"]
        service = entry["service"]
        family = entry["productFamily"]
        lookup_region = entry.get("region", region)

        tasks = []
        for component in entry.get("components", []):
            component_family = component.get("productFamily", family)
            tasks.append(
                self._calculate_component(vendor, service, component_family, lookup_region, component, values)
            )

        results = await asyncio.gather(*tasks)
        total = 0.0
        notes: List[str] = []
        matched_any = False
        for cost, note, matched in results:
            total += cost
            matched_any = matched_any or matched
            if note:
                notes.append(note)

        return {
            "cost": round(total, 2),
            "notes": notes,
            "pricing_source": "exact_api" if matched_any else "unsupported",
            "resource_family": resource_family,
            "matched": matched_any,
        }

    def _estimate_aws_instance_monthly(self, instance_type: str) -> float:
        normalized = (instance_type or "").strip().lower()
        if not normalized:
            return 60.74
        if normalized in _AWS_INSTANCE_MONTHLY:
            return _AWS_INSTANCE_MONTHLY[normalized]

        family, _, size = normalized.partition(".")
        if not size:
            return 60.74

        family_multiplier = {
            "t": 1.0,
            "m": 1.15,
            "c": 1.02,
            "r": 1.52,
            "x": 1.75,
            "i": 1.6,
            "g": 2.0,
            "p": 2.6,
        }.get(family[:1], 1.1)
        return round(self._size_units(size) * _GENERIC_COMPUTE_FAMILY_RATE["aws"] * family_multiplier, 2)

    def _estimate_aws_rds_monthly(self, instance_class: str) -> float:
        normalized = (instance_class or "").strip().lower()
        if not normalized:
            return 49.64
        if normalized in _AWS_RDS_INSTANCE_MONTHLY:
            return _AWS_RDS_INSTANCE_MONTHLY[normalized]
        base_instance = normalized.replace("db.", "", 1)
        return round(self._estimate_aws_instance_monthly(base_instance) * 0.82, 2)

    def _estimate_azure_vm_monthly(self, vm_size: str) -> float:
        normalized = (vm_size or "").strip().lower()
        if not normalized:
            return 70.08
        if normalized in _AZURE_VM_MONTHLY:
            return _AZURE_VM_MONTHLY[normalized]

        match = re.search(r"_(\d+)", normalized)
        cores = int(match.group(1)) if match else 2
        family_multiplier = {
            "b": 0.8,
            "d": 1.0,
            "e": 1.3,
            "f": 0.9,
        }.get(normalized.replace("standard_", "")[:1], 1.0)
        return round(cores * 35.0 * family_multiplier, 2)

    def _estimate_gcp_machine_monthly(self, machine_type: str) -> float:
        normalized = (machine_type or "").split("/")[-1].strip().lower()
        if not normalized:
            return 48.91
        hourly = _GCP_MACHINE_HOUR_PRICE.get(normalized)
        if hourly is not None:
            return round(hourly * _HOURS_PER_MONTH, 2)

        trailing_digits = re.findall(r"(\d+)", normalized)
        if trailing_digits:
            vcpus = int(trailing_digits[-1])
            return round(vcpus * 0.048 * _HOURS_PER_MONTH, 2)
        return 48.91

    def _size_units(self, size: str) -> float:
        normalized = (size or "").strip().lower()
        if normalized in _GENERIC_SIZE_UNITS:
            return _GENERIC_SIZE_UNITS[normalized]

        match = re.fullmatch(r"(\d+)xlarge", normalized)
        if match:
            return float(match.group(1)) * 16.0
        return 8.0

    def _build_estimate(
        self,
        *,
        cost: float,
        notes: List[str],
        pricing_source: str,
        resource_family: str,
    ) -> Dict[str, Any]:
        return {
            "cost": round(cost, 2),
            "notes": [note for note in notes if note],
            "pricing_source": pricing_source,
            "resource_family": resource_family,
        }

    def _estimate_aws(self, resource_type: str, values: Dict[str, Any]) -> Dict[str, Any]:
        normalized_type = self._normalize_resource_type(resource_type)
        family = self._infer_resource_family(normalized_type, values)

        if "db_instance" in normalized_type or "rds" in normalized_type:
            instance_class = self._extract_string(values, ["instance_class", "instance_type"], "db.t3.medium")
            storage_gb = self._estimate_storage_size_gb(values, default=20.0)
            storage_type = self._extract_string(values, ["storage_type"], "gp2").lower()
            compute_cost = self._estimate_aws_rds_monthly(instance_class)
            if self._extract_value(values, "multi_az"):
                compute_cost *= 2
            storage_rate = _AWS_STORAGE_GB_MONTHLY.get(storage_type, _AWS_STORAGE_GB_MONTHLY["gp2"])
            storage_cost = storage_gb * storage_rate
            return self._build_estimate(
                cost=compute_cost + storage_cost,
                notes=["Estimated from AWS instance class and storage profile reference pricing."],
                pricing_source="heuristic_estimate",
                resource_family="database",
            )

        if any(token in normalized_type for token in ["elasticache", "redis", "cache_cluster"]):
            node_count = self._extract_instance_count(values)
            node_type = self._extract_string(values, ["node_type", "cache_node_type"], "cache.t3.micro")
            size_hint = node_type.split(".")[-1]
            return self._build_estimate(
                cost=node_count * max(self._estimate_aws_instance_monthly(f"t3.{size_hint}"), 35.0),
                notes=["Estimated from cache node class because exact ElastiCache catalog lookup is unavailable."],
                pricing_source="heuristic_estimate",
                resource_family="database",
            )

        if any(token in normalized_type for token in ["nat_gateway"]):
            return self._build_estimate(
                cost=32.85,
                notes=["Estimated from AWS NAT Gateway hourly baseline only; data processing charges are not included."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if any(token in normalized_type for token in ["eip", "public_ip", "elastic_ip"]):
            return self._build_estimate(
                cost=3.65,
                notes=["Estimated from standard Elastic IP monthly rate."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if any(token in normalized_type for token in ["load_balancer", "_lb", "_alb", "_elb"]):
            return self._build_estimate(
                cost=16.43,
                notes=["Estimated from Application Load Balancer hourly baseline only; LCU usage is not included."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if any(token in normalized_type for token in ["eks_node_group"]):
            instance_type = self._extract_string(values, ["instance_types.0", "instance_type"], "t3.medium")
            node_count = self._extract_instance_count(values)
            return self._build_estimate(
                cost=node_count * self._estimate_aws_instance_monthly(instance_type),
                notes=["Estimated from EKS node group instance mix; control-plane cost is modeled separately."],
                pricing_source="heuristic_estimate",
                resource_family="kubernetes",
            )

        if any(token in normalized_type for token in ["eks_cluster", "ecs_cluster"]):
            return self._build_estimate(
                cost=73.0 if "eks_cluster" in normalized_type else 0.0,
                notes=[
                    "Estimated from EKS control-plane baseline."
                    if "eks_cluster" in normalized_type
                    else "Cluster metadata itself does not imply recurring compute cost without backing capacity."
                ],
                pricing_source="heuristic_estimate" if "eks_cluster" in normalized_type else "usage_based",
                resource_family="kubernetes" if "eks_cluster" in normalized_type else "other",
            )

        if any(token in normalized_type for token in ["ebs_volume", "volume", "snapshot"]):
            size_gb = self._estimate_storage_size_gb(values, default=100.0)
            volume_type = self._extract_string(values, ["type", "volume_type"], "gp3").lower()
            rate = _AWS_STORAGE_GB_MONTHLY.get(volume_type, _AWS_STORAGE_GB_MONTHLY["gp3"])
            cost = size_gb * rate
            if volume_type in {"io1", "io2"}:
                iops = self._extract_float(values, ["iops"], 0.0)
                cost += iops * (0.065 if volume_type == "io1" else 0.078)
            return self._build_estimate(
                cost=cost,
                notes=["Estimated from EBS storage size, class, and provisioned IOPS when present."],
                pricing_source="heuristic_estimate",
                resource_family="storage",
            )

        if any(token in normalized_type for token in ["instance", "spot_instance", "launch_template", "autoscaling_group"]) and "db_" not in normalized_type:
            instance_type = self._extract_string(values, ["instance_type", "launch_template.0.instance_type"], "t3.medium")
            instance_count = self._extract_instance_count(values)
            root_disk_gb = self._estimate_storage_size_gb(values, default=0.0)
            root_disk_type = self._extract_string(values, ["root_block_device.0.volume_type"], "gp3").lower()
            root_disk_cost = root_disk_gb * _AWS_STORAGE_GB_MONTHLY.get(root_disk_type, _AWS_STORAGE_GB_MONTHLY["gp3"])
            return self._build_estimate(
                cost=(instance_count * self._estimate_aws_instance_monthly(instance_type)) + root_disk_cost,
                notes=["Estimated from EC2 instance class, count, and attached root-disk size when available."],
                pricing_source="heuristic_estimate",
                resource_family="compute",
            )

        if self._is_usage_based_zero_resource(normalized_type) or "bucket" in normalized_type:
            return self._build_estimate(
                cost=0.0,
                notes=["This AWS resource is usage-based or control-plane only; recurring monthly baseline was not inferred from the Terraform plan."],
                pricing_source="usage_based",
                resource_family=family,
            )

        return self._build_estimate(
            cost=0.0,
            notes=["No AWS pricing heuristic matched this Terraform resource type yet."],
            pricing_source="unsupported",
            resource_family=family,
        )

    def _estimate_azure(self, resource_type: str, values: Dict[str, Any]) -> Dict[str, Any]:
        normalized_type = self._normalize_resource_type(resource_type)
        family = self._infer_resource_family(normalized_type, values)

        if any(token in normalized_type for token in ["virtual_machine", "scale_set"]):
            vm_size = self._extract_string(
                values,
                ["size", "vm_size", "sku_name", "hardware_profile.vm_size"],
                "Standard_D2s_v3",
            )
            count = self._extract_instance_count(values)
            disk_gb = self._estimate_storage_size_gb(values, default=0.0)
            disk_type = self._extract_string(
                values,
                ["storage_account_type", "sku_name", "managed_disk_type"],
                "Premium_LRS",
            ).lower()
            disk_cost = disk_gb * _AZURE_DISK_GB_MONTHLY.get(disk_type, _AZURE_DISK_GB_MONTHLY["premium_lrs"])
            return self._build_estimate(
                cost=(count * self._estimate_azure_vm_monthly(vm_size)) + disk_cost,
                notes=["Estimated from Azure VM size and attached-disk storage profile reference pricing."],
                pricing_source="heuristic_estimate",
                resource_family="compute",
            )

        if any(token in normalized_type for token in ["managed_disk", "snapshot"]):
            size_gb = self._estimate_storage_size_gb(values, default=128.0)
            disk_type = self._extract_string(values, ["storage_account_type", "sku_name"], "StandardSSD_LRS").lower()
            rate = _AZURE_DISK_GB_MONTHLY.get(disk_type, _AZURE_DISK_GB_MONTHLY["standardssd_lrs"])
            return self._build_estimate(
                cost=size_gb * rate,
                notes=["Estimated from Azure managed-disk size and redundancy tier."],
                pricing_source="heuristic_estimate",
                resource_family="storage",
            )

        if any(token in normalized_type for token in ["mssql_database", "postgresql", "mysql", "redis_cache", "sql_database"]):
            sku_name = self._extract_string(values, ["sku_name", "sku.0.name", "sku"], "S1").lower()
            base_cost = _AZURE_SQL_MONTHLY.get(sku_name)
            if base_cost is None:
                if "redis" in normalized_type:
                    capacity = max(self._extract_int(values, ["capacity", "sku.0.capacity"], 1), 1)
                    base_cost = 40.0 * capacity
                else:
                    base_cost = max(self._estimate_azure_vm_monthly(sku_name), 75.0)
            storage_gb = self._estimate_storage_size_gb(values, default=0.0)
            storage_cost = storage_gb * 0.10
            return self._build_estimate(
                cost=base_cost + storage_cost,
                notes=["Estimated from Azure database/cache SKU plus provisioned storage when present."],
                pricing_source="heuristic_estimate",
                resource_family="database",
            )

        if any(token in normalized_type for token in ["app_service_plan"]):
            sku_name = self._extract_string(values, ["sku_name", "sku.0.tier", "sku.0.size"], "S1").lower()
            return self._build_estimate(
                cost=_AZURE_APP_SERVICE_PLAN_MONTHLY.get(sku_name, 73.0),
                notes=["Estimated from Azure App Service plan SKU reference pricing."],
                pricing_source="heuristic_estimate",
                resource_family="compute",
            )

        if any(token in normalized_type for token in ["kubernetes_cluster"]):
            node_count = self._extract_instance_count(values)
            vm_size = self._extract_string(values, ["default_node_pool.0.vm_size"], "Standard_D2s_v3")
            node_cost = node_count * self._estimate_azure_vm_monthly(vm_size)
            return self._build_estimate(
                cost=node_cost,
                notes=["Estimated from AKS default node-pool size and count; control-plane charges are not included."],
                pricing_source="heuristic_estimate",
                resource_family="kubernetes",
            )

        if any(token in normalized_type for token in ["public_ip"]):
            return self._build_estimate(
                cost=2.92,
                notes=["Estimated from Azure standard public IP monthly baseline."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if any(token in normalized_type for token in ["load_balancer", "_lb", "application_gateway", "nat_gateway"]):
            baseline = 18.0 if "load_balancer" in normalized_type else 25.0 if "application_gateway" in normalized_type else 32.85
            return self._build_estimate(
                cost=baseline,
                notes=["Estimated from Azure network-service baseline; traffic and capacity unit charges are not included."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if self._is_usage_based_zero_resource(normalized_type) or "storage_account" in normalized_type or "web_app" in normalized_type or "function_app" in normalized_type:
            return self._build_estimate(
                cost=0.0,
                notes=["This Azure resource is plan-backed, usage-based, or control-plane only; recurring monthly baseline was not inferred from the Terraform plan."],
                pricing_source="usage_based",
                resource_family=family,
            )

        return self._build_estimate(
            cost=0.0,
            notes=["No Azure pricing heuristic matched this Terraform resource type yet."],
            pricing_source="unsupported",
            resource_family=family,
        )

    def _estimate_gcp(self, resource_type: str, values: Dict[str, Any]) -> Dict[str, Any]:
        normalized_type = self._normalize_resource_type(resource_type)
        family = self._infer_resource_family(normalized_type, values)

        if any(token in normalized_type for token in ["compute_instance", "instance_template"]) and "sql" not in normalized_type:
            machine_type = self._extract_string(values, ["machine_type"], "e2-standard-2")
            count = self._extract_instance_count(values)
            disk_type = self._extract_string(values, ["boot_disk.0.initialize_params.0.type"], "pd-balanced").split("/")[-1].lower()
            disk_gb = self._estimate_storage_size_gb(values, default=0.0)
            disk_cost = disk_gb * _GCP_DISK_GB_MONTHLY.get(disk_type, _GCP_DISK_GB_MONTHLY["pd-balanced"])
            return self._build_estimate(
                cost=(count * self._estimate_gcp_machine_monthly(machine_type)) + disk_cost,
                notes=["Estimated from GCP machine type and attached persistent-disk size when available."],
                pricing_source="heuristic_estimate",
                resource_family="compute",
            )

        if any(token in normalized_type for token in ["compute_disk", "snapshot"]):
            size_gb = self._estimate_storage_size_gb(values, default=100.0)
            disk_type = self._extract_string(values, ["type", "disk_type"], "pd-standard").split("/")[-1].lower()
            rate = _GCP_DISK_GB_MONTHLY.get(disk_type, _GCP_DISK_GB_MONTHLY["pd-standard"])
            return self._build_estimate(
                cost=size_gb * rate,
                notes=["Estimated from GCP persistent-disk size and class reference pricing."],
                pricing_source="heuristic_estimate",
                resource_family="storage",
            )

        if any(token in normalized_type for token in ["sql_database_instance", "redis_instance"]):
            tier = self._extract_string(values, ["settings.0.tier", "tier"], "db-n1-standard-1").lower()
            hourly = _GCP_SQL_HOUR_PRICE.get(tier, 0.10)
            storage_gb = self._estimate_storage_size_gb(values, default=0.0)
            storage_cost = storage_gb * _GCP_DISK_GB_MONTHLY["pd-ssd"]
            return self._build_estimate(
                cost=(hourly * _HOURS_PER_MONTH) + storage_cost,
                notes=["Estimated from GCP database/cache tier plus SSD storage baseline."],
                pricing_source="heuristic_estimate",
                resource_family="database",
            )

        if any(token in normalized_type for token in ["container_cluster", "container_node_pool"]):
            node_count = self._extract_instance_count(values)
            machine_type = self._extract_string(values, ["node_config.0.machine_type", "node_pool.0.node_config.0.machine_type"], "e2-standard-2")
            control_plane = 73.0 if "container_cluster" in normalized_type else 0.0
            return self._build_estimate(
                cost=control_plane + (node_count * self._estimate_gcp_machine_monthly(machine_type)),
                notes=["Estimated from GKE control-plane baseline plus node-pool machine type when present."],
                pricing_source="heuristic_estimate",
                resource_family="kubernetes",
            )

        if any(token in normalized_type for token in ["compute_address", "global_address"]):
            address_type = self._extract_string(values, ["address_type"], "EXTERNAL").upper()
            if address_type == "INTERNAL":
                return self._build_estimate(
                    cost=0.0,
                    notes=["Internal addresses do not carry the external static-IP monthly baseline."],
                    pricing_source="usage_based",
                    resource_family="network",
                )
            return self._build_estimate(
                cost=7.20,
                notes=["Estimated from GCP external static-IP monthly baseline."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if any(token in normalized_type for token in ["forwarding_rule", "backend_service", "target_http_proxy", "router_nat"]):
            baseline = 18.0 if "forwarding_rule" in normalized_type or "backend_service" in normalized_type else 32.85
            return self._build_estimate(
                cost=baseline,
                notes=["Estimated from GCP networking-service baseline; traffic processing is not included."],
                pricing_source="heuristic_estimate",
                resource_family="network",
            )

        if self._is_usage_based_zero_resource(normalized_type) or "storage_bucket" in normalized_type or "cloud_run" in normalized_type or "cloudfunctions" in normalized_type:
            return self._build_estimate(
                cost=0.0,
                notes=["This GCP resource is usage-based or control-plane only; recurring monthly baseline was not inferred from the Terraform plan."],
                pricing_source="usage_based",
                resource_family=family,
            )

        return self._build_estimate(
            cost=0.0,
            notes=["No GCP pricing heuristic matched this Terraform resource type yet."],
            pricing_source="unsupported",
            resource_family=family,
        )

    def _estimate_generic(self, resource_type: str, values: Dict[str, Any]) -> Dict[str, Any]:
        family = self._infer_resource_family(resource_type, values)

        if family == "compute":
            count = self._extract_instance_count(values)
            instance_hint = self._extract_string(values, ["instance_type", "vm_size", "machine_type"])
            if instance_hint:
                guess = count * self._estimate_aws_instance_monthly(instance_hint)
            else:
                guess = count * 60.0
            return self._build_estimate(
                cost=guess,
                notes=["Estimated from generic compute heuristics because this provider/resource type is not yet modeled explicitly."],
                pricing_source="heuristic_estimate",
                resource_family=family,
            )

        if family == "database":
            storage_gb = self._estimate_storage_size_gb(values, default=20.0)
            return self._build_estimate(
                cost=120.0 + (storage_gb * 0.10),
                notes=["Estimated from generic database heuristics because this provider/resource type is not yet modeled explicitly."],
                pricing_source="heuristic_estimate",
                resource_family=family,
            )

        if family == "storage":
            size_gb = self._estimate_storage_size_gb(values, default=0.0)
            if size_gb <= 0:
                return self._build_estimate(
                    cost=0.0,
                    notes=["Storage usage is variable and the plan did not include a billable size baseline."],
                    pricing_source="usage_based",
                    resource_family=family,
                )
            return self._build_estimate(
                cost=size_gb * 0.08,
                notes=["Estimated from generic storage-per-GB heuristics."],
                pricing_source="heuristic_estimate",
                resource_family=family,
            )

        if family == "network":
            normalized_type = self._normalize_resource_type(resource_type)
            if "nat" in normalized_type:
                cost = 32.85
            elif any(token in normalized_type for token in ["ip", "address"]):
                cost = 4.0
            else:
                cost = 18.0
            return self._build_estimate(
                cost=cost,
                notes=["Estimated from generic networking-service heuristics."],
                pricing_source="heuristic_estimate",
                resource_family=family,
            )

        if family == "kubernetes":
            return self._build_estimate(
                cost=73.0,
                notes=["Estimated from generic managed-cluster control-plane heuristic."],
                pricing_source="heuristic_estimate",
                resource_family=family,
            )

        if family == "serverless" or self._is_usage_based_zero_resource(resource_type):
            return self._build_estimate(
                cost=0.0,
                notes=["This resource is usage-based or control-plane only; recurring monthly baseline was not inferred from the Terraform plan."],
                pricing_source="usage_based",
                resource_family=family,
            )

        return self._build_estimate(
            cost=0.0,
            notes=["No pricing heuristic matched this Terraform resource type yet."],
            pricing_source="unsupported",
            resource_family=family,
        )

    async def _estimate_cost(
        self,
        resource_type: str,
        values: Dict[str, Any],
        region: str,
        provider: str,
    ) -> Dict[str, Any]:
        exact = await self._calculate_exact_cost(resource_type, values, region)
        if exact.get("matched"):
            return exact

        if provider == "aws":
            return self._estimate_aws(resource_type, values)
        if provider == "azure":
            return self._estimate_azure(resource_type, values)
        if provider == "gcp":
            return self._estimate_gcp(resource_type, values)
        return self._estimate_generic(resource_type, values)

    def _combine_notes(self, before_notes: List[str], after_notes: List[str]) -> str:
        combined: List[str] = []
        for note in before_notes + after_notes:
            cleaned = note.strip()
            if cleaned and cleaned not in combined:
                combined.append(cleaned)
        return " ".join(combined)

    def _aggregate_pricing_source(self, before_source: str, after_source: str) -> str:
        priority = {
            "exact_api": 0,
            "heuristic_estimate": 1,
            "usage_based": 2,
        }
        sources = [
            source
            for source in [before_source, after_source]
            if source and source != "unsupported"
        ]
        if not sources:
            return "unsupported"
        return max(sources, key=lambda source: priority.get(source, 99))

    async def estimate_monthly_cost(self, tf_plan: Dict[str, Any]) -> Dict[str, Any]:
        global_regions = self._extract_regions(tf_plan)
        delta_cost = 0.0
        resources: List[Dict[str, Any]] = []
        unestimated_resources: List[Dict[str, Any]] = []
        resource_changes = tf_plan.get("resource_changes", []) or []

        async def process_change(change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            resource_type = self._normalize_resource_type(change.get("type", ""))
            if not resource_type:
                return None

            resource_name = change.get("address", "unknown")
            actions = change.get("change", {}).get("actions", [])
            provider_name = change.get("provider_name", "")
            provider = self._infer_provider(resource_type, provider_name)
            before_values = change.get("change", {}).get("before", {}) or {}
            after_values = change.get("change", {}).get("after", {}) or {}
            resource_attributes = after_values or before_values
            action_label = ",".join(actions) if actions else "unknown"
            region = self._detect_region(
                global_regions,
                provider_name,
                resource_attributes,
                provider,
            )

            before_estimate = self._build_estimate(
                cost=0.0,
                notes=[],
                pricing_source="unsupported",
                resource_family=self._infer_resource_family(resource_type, before_values),
            )
            after_estimate = self._build_estimate(
                cost=0.0,
                notes=[],
                pricing_source="unsupported",
                resource_family=self._infer_resource_family(resource_type, after_values),
            )

            if actions == ["create"]:
                after_estimate = await self._estimate_cost(resource_type, after_values, region, provider)
            elif actions == ["delete"]:
                before_estimate = await self._estimate_cost(resource_type, before_values, region, provider)
            elif actions == ["update"] or actions == ["no-op"] or ("delete" in actions and "create" in actions):
                before_estimate = await self._estimate_cost(resource_type, before_values, region, provider)
                after_estimate = await self._estimate_cost(resource_type, after_values, region, provider)
            else:
                if after_values:
                    after_estimate = await self._estimate_cost(resource_type, after_values, region, provider)
                elif before_values:
                    before_estimate = await self._estimate_cost(resource_type, before_values, region, provider)

            notes = self._combine_notes(before_estimate["notes"], after_estimate["notes"])

            if actions == ["create"]:
                pricing_source = after_estimate["pricing_source"]
            elif actions == ["delete"]:
                pricing_source = before_estimate["pricing_source"]
            else:
                pricing_source = self._aggregate_pricing_source(
                    before_estimate["pricing_source"],
                    after_estimate["pricing_source"],
                )
            resource_family = after_estimate["resource_family"] or before_estimate["resource_family"]

            if (
                before_estimate["cost"] == 0
                and after_estimate["cost"] == 0
                and pricing_source == "unsupported"
            ):
                reason = (
                    notes
                    or f"resource type '{resource_type}' is not supported by the simulator pricing catalog yet"
                )
                return {
                    "_unestimated": True,
                    "resource_address": resource_name,
                    "resource_type": resource_type,
                    "address": resource_name,
                    "type": resource_type,
                    "provider": provider,
                    "region": region,
                    "action": action_label,
                    "resource_family": resource_family,
                    "pricing_source": "unsupported",
                    "reason": reason,
                    "attributes": resource_attributes,
                }

            return {
                "name": resource_name,
                "type": resource_type,
                "provider": provider,
                "region": region,
                "action": action_label,
                "resource_family": resource_family,
                "pricing_source": pricing_source,
                "before": round(before_estimate["cost"], 2),
                "after": round(after_estimate["cost"], 2),
                "notes": notes,
                "attributes": resource_attributes,
            }

        results = await asyncio.gather(*(process_change(change) for change in resource_changes))
        for resource in results:
            if resource is None:
                continue
            if resource.get("_unestimated"):
                unestimated = {
                    key: value
                    for key, value in resource.items()
                    if key != "_unestimated"
                }
                unestimated_resources.append(unestimated)
                continue
            delta_cost += resource["after"] - resource["before"]
            resources.append(resource)

        summary = {
            "total_resources": len(resource_changes),
            "priced_resources": len(resources),
            "exact_pricing_resources": sum(1 for item in resources if item["pricing_source"] == "exact_api"),
            "estimated_resources": sum(1 for item in resources if item["pricing_source"] == "heuristic_estimate"),
            "usage_based_resources": sum(1 for item in resources if item["pricing_source"] == "usage_based"),
            "unsupported_resources": (
                sum(1 for item in resources if item["pricing_source"] == "unsupported")
                + len(unestimated_resources)
            ),
            "unestimated_resources": len(unestimated_resources),
        }
        findings = generate_findings(resources, unestimated_resources)

        return {
            "delta_monthly_cost": round(delta_cost, 2),
            "currency": "USD",
            "resources": resources,
            "unestimated_resources": unestimated_resources,
            "findings": findings,
            "summary": summary,
        }
