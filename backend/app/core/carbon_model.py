"""
Instance-aware carbon footprint estimation.

Replaces the flat 72 kg/VM hardcode with a formula based on:
  CO2_kg = vCPU_count * power_per_vCPU_kW * PUE * hours * grid_intensity

Sources:
  - vCPU counts: AWS/Azure/GCP documentation
  - Grid intensity: EPA eGRID, EEA, IEA (2024 data)
  - PUE: Hyperscaler sustainability reports (avg 1.1-1.2)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

POWER_PER_VCPU_KW = 0.005
PUE = 1.2
HOURS_PER_MONTH = 730

_GRID_INTENSITY_KG_CO2_PER_KWH: Dict[str, float] = {
    # AWS regions
    "us-east-1": 0.379,
    "us-east-2": 0.410,
    "us-west-1": 0.200,
    "us-west-2": 0.079,
    "ca-central-1": 0.013,
    "eu-west-1": 0.296,
    "eu-west-2": 0.212,
    "eu-west-3": 0.052,
    "eu-central-1": 0.338,
    "eu-north-1": 0.008,
    "ap-southeast-1": 0.408,
    "ap-southeast-2": 0.530,
    "ap-northeast-1": 0.462,
    "ap-northeast-2": 0.415,
    "ap-south-1": 0.708,
    "sa-east-1": 0.074,
    "me-south-1": 0.505,
    "af-south-1": 0.900,
    # Azure regions (mapped to grid)
    "eastus": 0.379,
    "eastus2": 0.379,
    "westus": 0.200,
    "westus2": 0.079,
    "westus3": 0.370,
    "centralus": 0.410,
    "northcentralus": 0.410,
    "southcentralus": 0.379,
    "northeurope": 0.296,
    "westeurope": 0.276,
    "uksouth": 0.212,
    "ukwest": 0.212,
    "francecentral": 0.052,
    "germanywestcentral": 0.338,
    "swedencentral": 0.008,
    "norwayeast": 0.017,
    "centralindia": 0.708,
    "southindia": 0.708,
    "eastasia": 0.453,
    "southeastasia": 0.408,
    "japaneast": 0.462,
    "japanwest": 0.462,
    "australiaeast": 0.530,
    "koreacentral": 0.415,
    "brazilsouth": 0.074,
    # GCP regions
    "us-central1": 0.410,
    "us-east1": 0.379,
    "us-east4": 0.379,
    "us-west1": 0.079,
    "us-west2": 0.200,
    "us-west4": 0.370,
    "northamerica-northeast1": 0.013,
    "europe-west1": 0.150,
    "europe-west2": 0.212,
    "europe-west3": 0.338,
    "europe-west4": 0.335,
    "europe-north1": 0.008,
    "asia-east1": 0.509,
    "asia-east2": 0.453,
    "asia-southeast1": 0.408,
    "asia-south1": 0.708,
    "asia-northeast1": 0.462,
    "australia-southeast1": 0.530,
    "southamerica-east1": 0.074,
}

_DEFAULT_GRID_INTENSITY = 0.400

_VCPU_BY_SIZE_SUFFIX: Dict[str, int] = {
    "nano": 1,
    "micro": 1,
    "small": 1,
    "medium": 2,
    "large": 2,
    "xlarge": 4,
    "2xlarge": 8,
    "4xlarge": 16,
    "8xlarge": 32,
    "12xlarge": 48,
    "16xlarge": 64,
    "24xlarge": 96,
    "32xlarge": 128,
    "48xlarge": 192,
    "metal": 96,
}

_VCPU_OVERRIDES: Dict[str, int] = {
    # GPU instances
    "p4d.24xlarge": 96,
    "p4de.24xlarge": 96,
    "p5.48xlarge": 192,
    "g4dn.xlarge": 4,
    "g4dn.2xlarge": 8,
    "g4dn.12xlarge": 48,
    "g5.xlarge": 4,
    "g5.2xlarge": 8,
    "g5.12xlarge": 48,
    "trn1.32xlarge": 128,
    "inf2.xlarge": 4,
    "inf2.8xlarge": 32,
    "inf2.24xlarge": 96,
    "inf2.48xlarge": 192,
    # Azure common sizes
    "standard_b1s": 1,
    "standard_b2s": 2,
    "standard_b4ms": 4,
    "standard_d2s_v3": 2,
    "standard_d4s_v3": 4,
    "standard_d8s_v3": 8,
    "standard_d16s_v3": 16,
    "standard_d2as_v5": 2,
    "standard_d4as_v5": 4,
    "standard_d8as_v5": 8,
    "standard_e2s_v3": 2,
    "standard_e4s_v3": 4,
    "standard_e8s_v3": 8,
    "standard_f2s_v2": 2,
    "standard_f4s_v2": 4,
    "standard_nc6s_v3": 6,
    "standard_nc12s_v3": 12,
    "standard_nc24s_v3": 24,
}


def _infer_vcpu_count(instance_type: str) -> int:
    normalized = str(instance_type or "").strip().lower().replace(" ", "_")
    if not normalized:
        return 2

    if normalized in _VCPU_OVERRIDES:
        return _VCPU_OVERRIDES[normalized]

    # GCP machine types: n2-standard-4 → 4 vCPUs
    gcp_match = re.match(r"^[a-z]\d[a-z]?-(?:standard|highmem|highcpu|custom)-(\d+)$", normalized)
    if gcp_match:
        return int(gcp_match.group(1))

    # GCP e2 types: e2-medium → 2
    if normalized.startswith("e2-"):
        suffix = normalized.split("-", 1)[-1]
        return _VCPU_BY_SIZE_SUFFIX.get(suffix, 2)

    # AWS types: m5.xlarge, c6i.2xlarge
    dot_parts = normalized.split(".")
    if len(dot_parts) == 2:
        size = dot_parts[1]
        return _VCPU_BY_SIZE_SUFFIX.get(size, 4)

    # Azure: Standard_D8as_v5 — extract number after D/E/F
    azure_match = re.search(r"[defbln](\d+)", normalized)
    if azure_match:
        return int(azure_match.group(1))

    return 4


def _get_grid_intensity(region: str) -> float:
    normalized = str(region or "").strip().lower()
    if normalized in _GRID_INTENSITY_KG_CO2_PER_KWH:
        return _GRID_INTENSITY_KG_CO2_PER_KWH[normalized]
    for key, value in _GRID_INTENSITY_KG_CO2_PER_KWH.items():
        if normalized.startswith(key) or key.startswith(normalized):
            return value
    return _DEFAULT_GRID_INTENSITY


def estimate_monthly_carbon_kg(
    provider: str,
    instance_type: str,
    region: str,
    *,
    vcpu_override: Optional[int] = None,
) -> float:
    vcpus = vcpu_override if vcpu_override else _infer_vcpu_count(instance_type)
    intensity = _get_grid_intensity(region)

    carbon_kg = vcpus * POWER_PER_VCPU_KW * PUE * HOURS_PER_MONTH * intensity
    return round(carbon_kg, 2)


def estimate_storage_carbon_kg(size_gb: float, region: str) -> float:
    intensity = _get_grid_intensity(region)
    power_kw = (size_gb / 1000.0) * 0.001
    return round(power_kw * PUE * HOURS_PER_MONTH * intensity, 3)
