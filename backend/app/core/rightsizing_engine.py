"""
Rightsizing Engine — recommends specific target SKUs based on utilization metrics.

Given a resource's current instance type and P95 CPU/memory utilization,
finds the smallest SKU in the same family that can handle the workload
with a safety buffer. Returns concrete "downsize X → Y, save $Z/mo".

Covers: AWS EC2, Azure VMs, GCP Compute Engine.
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SKUSpec:
    name: str
    vcpus: int
    memory_gb: float
    relative_price: float  # normalized within family (smallest = 1.0)


@dataclass
class RightsizeRecommendation:
    current_sku: str
    target_sku: str
    current_vcpus: int
    target_vcpus: int
    current_memory_gb: float
    target_memory_gb: float
    estimated_savings_pct: float
    reason: str
    provider: str
    family: str


# ---------------------------------------------------------------------------
# AWS EC2 size ladder (within any family, sizes scale predictably)
# ---------------------------------------------------------------------------

_AWS_SIZE_LADDER: List[Tuple[str, int, float, float]] = [
    # (size_suffix, vcpus, memory_gb_per_vcpu, relative_price)
    ("nano",     1,  0.5,  0.125),
    ("micro",    1,  1.0,  0.25),
    ("small",    1,  2.0,  0.5),
    ("medium",   1,  4.0,  1.0),
    ("large",    2,  4.0,  2.0),
    ("xlarge",   4,  4.0,  4.0),
    ("2xlarge",  8,  4.0,  8.0),
    ("4xlarge",  16, 4.0,  16.0),
    ("8xlarge",  32, 4.0,  32.0),
    ("12xlarge", 48, 4.0,  48.0),
    ("16xlarge", 64, 4.0,  64.0),
    ("24xlarge", 96, 4.0,  96.0),
    ("metal",    96, 4.0,  96.0),
]

_AWS_SIZE_MAP: Dict[str, Tuple[int, float, float]] = {
    s[0]: (s[1], s[1] * s[2], s[3]) for s in _AWS_SIZE_LADDER
}


def _parse_aws_instance(instance_type: str) -> Optional[Tuple[str, str, int, float]]:
    """Parse 'm5.xlarge' → ('m5', 'xlarge', 4, 16.0)."""
    parts = instance_type.split(".")
    if len(parts) != 2:
        return None
    family, size = parts
    spec = _AWS_SIZE_MAP.get(size)
    if not spec:
        return None
    return family, size, spec[0], spec[1]


def _recommend_aws(instance_type: str, p95_cpu: float, p95_mem_pct: Optional[float] = None) -> Optional[RightsizeRecommendation]:
    parsed = _parse_aws_instance(instance_type)
    if not parsed:
        return None

    family, current_size, current_vcpus, current_mem = parsed
    current_price = _AWS_SIZE_MAP[current_size][2]

    required_cpu_vcpus = math.ceil(current_vcpus * (p95_cpu / 100.0) * 1.3)
    required_cpu_vcpus = max(required_cpu_vcpus, 1)

    # Never recommend below "large" (2 vCPU) for production workloads —
    # nano/micro/small/medium have <4GB RAM and hit memory limits.
    min_practical_vcpus = max(required_cpu_vcpus, 2)

    best_size = None
    best_vcpus = 0
    best_mem = 0.0
    best_price = current_price

    for size_name, vcpus, mem, price in _AWS_SIZE_LADDER:
        if vcpus < min_practical_vcpus:
            continue
        if price >= current_price:
            break
        mem_total = vcpus * (current_mem / current_vcpus) if current_vcpus > 0 else vcpus * 4.0
        best_size = size_name
        best_vcpus = vcpus
        best_mem = mem_total
        best_price = price
        break

    if not best_size or best_size == current_size:
        return None

    savings_pct = round((1 - best_price / current_price) * 100, 1)
    if savings_pct < 10:
        return None

    target_sku = f"{family}.{best_size}"
    return RightsizeRecommendation(
        current_sku=instance_type,
        target_sku=target_sku,
        current_vcpus=current_vcpus,
        target_vcpus=best_vcpus,
        current_memory_gb=current_mem,
        target_memory_gb=best_mem,
        estimated_savings_pct=savings_pct,
        reason=(
            f"P95 CPU is {p95_cpu:.0f}% on {current_vcpus} vCPUs — only "
            f"{required_cpu_vcpus} vCPU needed with 30% buffer. "
            f"Downsize {instance_type} → {target_sku} (saves ~{savings_pct:.0f}%)."
        ),
        provider="aws",
        family=family,
    )


# ---------------------------------------------------------------------------
# Azure VM size ladder
# ---------------------------------------------------------------------------

_AZURE_FAMILIES: Dict[str, List[Tuple[str, int, float, float]]] = {}

def _build_azure_family(prefix: str, version: str, sizes: List[Tuple[int, float]]):
    """Build Standard_D{n}s_v{ver} style ladder."""
    entries = []
    base_price = sizes[0][1] if sizes else 1.0
    for vcpus, price in sizes:
        name = f"Standard_{prefix}{vcpus}s_{version}"
        entries.append((name, vcpus, vcpus * 4.0, price / base_price))
    _AZURE_FAMILIES[f"{prefix}s_{version}"] = entries

_build_azure_family("D", "v3", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0)])
_build_azure_family("D", "v4", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0)])
_build_azure_family("D", "v5", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0), (96, 48.0)])
_build_azure_family("E", "v3", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0)])
_build_azure_family("E", "v4", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0)])
_build_azure_family("E", "v5", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0), (96, 48.0)])
_build_azure_family("F", "v2", [(2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (32, 16.0), (48, 24.0), (64, 32.0), (72, 36.0)])
_build_azure_family("B", "v2", [(1, 0.5), (2, 1.0), (4, 2.0), (8, 4.0), (16, 8.0), (20, 10.0)])
_build_azure_family("L", "v2", [(8, 1.0), (16, 2.0), (32, 4.0), (48, 6.0), (64, 8.0), (80, 10.0)])


def _parse_azure_vm(vm_size: str) -> Optional[Tuple[str, str, int, float]]:
    """Parse 'Standard_D4s_v3' → ('Ds_v3', 'Standard_D4s_v3', 4, 16.0)."""
    if not vm_size.startswith("Standard_"):
        return None

    bare = vm_size[len("Standard_"):]

    for family_key, ladder in _AZURE_FAMILIES.items():
        for sku_name, vcpus, mem, price in ladder:
            if sku_name == vm_size:
                return family_key, sku_name, vcpus, mem

    import re
    match = re.match(r"([A-Z]+)(\d+)(.*)", bare)
    if match:
        prefix = match.group(1)
        vcpu_count = int(match.group(2))
        suffix = match.group(3)
        return f"{prefix}{suffix}", vm_size, vcpu_count, vcpu_count * 4.0

    return None


def _recommend_azure(vm_size: str, p95_cpu: float, monthly_cost: float = 0.0) -> Optional[RightsizeRecommendation]:
    parsed = _parse_azure_vm(vm_size)
    if not parsed:
        return None

    family_key, current_name, current_vcpus, current_mem = parsed

    required_vcpus = math.ceil(current_vcpus * (p95_cpu / 100.0) * 1.3)
    required_vcpus = max(required_vcpus, 1)

    if required_vcpus >= current_vcpus:
        return None

    ladder = _AZURE_FAMILIES.get(family_key)
    if not ladder:
        target_vcpus = max(2, required_vcpus)
        if target_vcpus >= current_vcpus:
            return None
        savings_pct = round((1 - target_vcpus / current_vcpus) * 100, 1)
        target_name = vm_size.replace(str(current_vcpus), str(target_vcpus))
        return RightsizeRecommendation(
            current_sku=vm_size,
            target_sku=target_name,
            current_vcpus=current_vcpus,
            target_vcpus=target_vcpus,
            current_memory_gb=current_mem,
            target_memory_gb=target_vcpus * 4.0,
            estimated_savings_pct=savings_pct,
            reason=(
                f"P95 CPU is {p95_cpu:.0f}% on {current_vcpus} vCPUs — "
                f"{required_vcpus} vCPU needed with 30% buffer. "
                f"Downsize {vm_size} → {target_name} (saves ~{savings_pct:.0f}%)."
            ),
            provider="azure",
            family=family_key,
        )

    current_price = None
    for name, vcpus, mem, price in ladder:
        if name == current_name:
            current_price = price
            break

    if current_price is None:
        return None

    best = None
    for name, vcpus, mem, price in ladder:
        if vcpus < required_vcpus:
            continue
        if price >= current_price:
            break
        best = (name, vcpus, mem, price)
        break

    if not best:
        return None

    target_name, target_vcpus, target_mem, target_price = best
    savings_pct = round((1 - target_price / current_price) * 100, 1)
    if savings_pct < 10:
        return None

    estimated_savings = round(monthly_cost * savings_pct / 100, 2) if monthly_cost > 0 else 0.0

    return RightsizeRecommendation(
        current_sku=vm_size,
        target_sku=target_name,
        current_vcpus=current_vcpus,
        target_vcpus=target_vcpus,
        current_memory_gb=current_mem,
        target_memory_gb=target_mem,
        estimated_savings_pct=savings_pct,
        reason=(
            f"P95 CPU is {p95_cpu:.0f}% on {current_vcpus} vCPUs — "
            f"{required_vcpus} vCPU needed with 30% buffer. "
            f"Downsize {vm_size} → {target_name} "
            f"(saves ~{savings_pct:.0f}%"
            f"{f', ${estimated_savings:.0f}/mo' if estimated_savings > 0 else ''})."
        ),
        provider="azure",
        family=family_key,
    )


# ---------------------------------------------------------------------------
# GCP Compute Engine size ladder
# ---------------------------------------------------------------------------

_GCP_FAMILIES: Dict[str, List[Tuple[str, int, float, float]]] = {
    "e2-standard": [
        ("e2-standard-2",  2,   8.0, 1.0),
        ("e2-standard-4",  4,  16.0, 2.0),
        ("e2-standard-8",  8,  32.0, 4.0),
        ("e2-standard-16", 16, 64.0, 8.0),
        ("e2-standard-32", 32, 128.0, 16.0),
    ],
    "e2-highcpu": [
        ("e2-highcpu-2",   2,  2.0,  1.0),
        ("e2-highcpu-4",   4,  4.0,  2.0),
        ("e2-highcpu-8",   8,  8.0,  4.0),
        ("e2-highcpu-16",  16, 16.0, 8.0),
        ("e2-highcpu-32",  32, 32.0, 16.0),
    ],
    "e2-highmem": [
        ("e2-highmem-2",   2,  16.0, 1.0),
        ("e2-highmem-4",   4,  32.0, 2.0),
        ("e2-highmem-8",   8,  64.0, 4.0),
        ("e2-highmem-16",  16, 128.0, 8.0),
    ],
    "n2-standard": [
        ("n2-standard-2",  2,   8.0, 1.0),
        ("n2-standard-4",  4,  16.0, 2.0),
        ("n2-standard-8",  8,  32.0, 4.0),
        ("n2-standard-16", 16, 64.0, 8.0),
        ("n2-standard-32", 32, 128.0, 16.0),
        ("n2-standard-48", 48, 192.0, 24.0),
        ("n2-standard-64", 64, 256.0, 32.0),
        ("n2-standard-80", 80, 320.0, 40.0),
        ("n2-standard-96", 96, 384.0, 48.0),
        ("n2-standard-128", 128, 512.0, 64.0),
    ],
    "n2-highcpu": [
        ("n2-highcpu-2",   2,  2.0,  1.0),
        ("n2-highcpu-4",   4,  4.0,  2.0),
        ("n2-highcpu-8",   8,  8.0,  4.0),
        ("n2-highcpu-16",  16, 16.0, 8.0),
        ("n2-highcpu-32",  32, 32.0, 16.0),
        ("n2-highcpu-48",  48, 48.0, 24.0),
        ("n2-highcpu-64",  64, 64.0, 32.0),
        ("n2-highcpu-80",  80, 80.0, 40.0),
        ("n2-highcpu-96",  96, 96.0, 48.0),
    ],
    "n2-highmem": [
        ("n2-highmem-2",   2,  16.0, 1.0),
        ("n2-highmem-4",   4,  32.0, 2.0),
        ("n2-highmem-8",   8,  64.0, 4.0),
        ("n2-highmem-16",  16, 128.0, 8.0),
        ("n2-highmem-32",  32, 256.0, 16.0),
        ("n2-highmem-48",  48, 384.0, 24.0),
        ("n2-highmem-64",  64, 512.0, 32.0),
        ("n2-highmem-80",  80, 640.0, 40.0),
        ("n2-highmem-96",  96, 768.0, 48.0),
        ("n2-highmem-128", 128, 864.0, 64.0),
    ],
    "n1-standard": [
        ("n1-standard-1",  1,  3.75, 1.0),
        ("n1-standard-2",  2,  7.5,  2.0),
        ("n1-standard-4",  4,  15.0, 4.0),
        ("n1-standard-8",  8,  30.0, 8.0),
        ("n1-standard-16", 16, 60.0, 16.0),
        ("n1-standard-32", 32, 120.0, 32.0),
        ("n1-standard-64", 64, 240.0, 64.0),
        ("n1-standard-96", 96, 360.0, 96.0),
    ],
    "c2-standard": [
        ("c2-standard-4",  4,  16.0, 1.0),
        ("c2-standard-8",  8,  32.0, 2.0),
        ("c2-standard-16", 16, 64.0, 4.0),
        ("c2-standard-30", 30, 120.0, 7.5),
        ("c2-standard-60", 60, 240.0, 15.0),
    ],
}


def _parse_gcp_instance(machine_type: str) -> Optional[Tuple[str, str, int, float]]:
    """Parse 'n2-standard-8' → ('n2-standard', 'n2-standard-8', 8, 32.0)."""
    parts = machine_type.rsplit("-", 1)
    if len(parts) != 2:
        return None

    family_prefix = parts[0]
    try:
        vcpu_count = int(parts[1])
    except ValueError:
        return None

    ladder = _GCP_FAMILIES.get(family_prefix)
    if ladder:
        for name, vcpus, mem, price in ladder:
            if name == machine_type:
                return family_prefix, name, vcpus, mem

    return family_prefix, machine_type, vcpu_count, vcpu_count * 4.0


def _recommend_gcp(machine_type: str, p95_cpu: float, monthly_cost: float = 0.0) -> Optional[RightsizeRecommendation]:
    parsed = _parse_gcp_instance(machine_type)
    if not parsed:
        return None

    family_key, current_name, current_vcpus, current_mem = parsed

    required_vcpus = math.ceil(current_vcpus * (p95_cpu / 100.0) * 1.3)
    required_vcpus = max(required_vcpus, 1)

    if required_vcpus >= current_vcpus:
        return None

    ladder = _GCP_FAMILIES.get(family_key)
    if not ladder:
        return None

    current_price = None
    for name, vcpus, mem, price in ladder:
        if name == current_name:
            current_price = price
            break

    if current_price is None:
        return None

    best = None
    for name, vcpus, mem, price in ladder:
        if vcpus < required_vcpus:
            continue
        if price >= current_price:
            break
        best = (name, vcpus, mem, price)
        break

    if not best:
        return None

    target_name, target_vcpus, target_mem, target_price = best
    savings_pct = round((1 - target_price / current_price) * 100, 1)
    if savings_pct < 10:
        return None

    estimated_savings = round(monthly_cost * savings_pct / 100, 2) if monthly_cost > 0 else 0.0

    return RightsizeRecommendation(
        current_sku=machine_type,
        target_sku=target_name,
        current_vcpus=current_vcpus,
        target_vcpus=target_vcpus,
        current_memory_gb=current_mem,
        target_memory_gb=target_mem,
        estimated_savings_pct=savings_pct,
        reason=(
            f"P95 CPU is {p95_cpu:.0f}% on {current_vcpus} vCPUs — "
            f"{required_vcpus} vCPU needed with 30% buffer. "
            f"Downsize {machine_type} → {target_name} "
            f"(saves ~{savings_pct:.0f}%"
            f"{f', ${estimated_savings:.0f}/mo' if estimated_savings > 0 else ''})."
        ),
        provider="gcp",
        family=family_key,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend_rightsizing(
    provider: str,
    instance_type: str,
    p95_cpu: float,
    p95_mem_pct: Optional[float] = None,
    monthly_cost: float = 0.0,
) -> Optional[RightsizeRecommendation]:
    """
    Recommend a specific smaller SKU based on utilization.

    Args:
        provider: "aws", "azure", or "gcp"
        instance_type: Current instance type (e.g. "m5.xlarge", "Standard_D4s_v3")
        p95_cpu: P95 CPU utilization percentage (0-100)
        p95_mem_pct: Optional P95 memory utilization percentage
        monthly_cost: Current monthly cost for savings estimation

    Returns:
        RightsizeRecommendation with target SKU, or None if no downsize possible.
    """
    if p95_cpu >= 70:
        return None

    provider_lower = provider.lower()
    if provider_lower == "aws":
        return _recommend_aws(instance_type, p95_cpu, p95_mem_pct)
    elif provider_lower == "azure":
        return _recommend_azure(instance_type, p95_cpu, monthly_cost)
    elif provider_lower == "gcp":
        return _recommend_gcp(instance_type, p95_cpu, monthly_cost)

    return None
