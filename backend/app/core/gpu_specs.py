"""
Centralized GPU SKU registry — unified specs across AWS, Azure, and GCP.
Single source of truth for GPU instance identification, capabilities, and static fallback pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GpuSkuSpec:
    provider: str
    instance_type: str
    gpu_model: str
    gpu_count: int
    gpu_memory_gb: int
    supports_mig: bool
    mig_slices_per_gpu: int
    architecture: str
    tdp_watts: int
    fp16_tflops: float
    on_demand_hourly: float
    # Specialized cloud pricing (static fallback — live pricing in gpu_pricing_service)
    lambda_hr: float | None = None
    coreweave_hr: float | None = None
    jarvis_hr: float | None = None
    runpod_hr: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# AWS GPU Instance Specs
# ─────────────────────────────────────────────────────────────────────────────

AWS_GPU_SPECS: dict[str, GpuSkuSpec] = {
    # P3 – V100
    "p3.2xlarge": GpuSkuSpec(
        provider="aws", instance_type="p3.2xlarge",
        gpu_model="V100 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=300, fp16_tflops=31.4,
        on_demand_hourly=3.06,
        lambda_hr=1.40, coreweave_hr=1.10, jarvis_hr=1.25, runpod_hr=0.89,
    ),
    "p3.8xlarge": GpuSkuSpec(
        provider="aws", instance_type="p3.8xlarge",
        gpu_model="V100 16GB", gpu_count=4, gpu_memory_gb=64,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=1200, fp16_tflops=125.6,
        on_demand_hourly=12.24,
        lambda_hr=5.60, coreweave_hr=4.40, jarvis_hr=5.00, runpod_hr=3.56,
    ),
    "p3.16xlarge": GpuSkuSpec(
        provider="aws", instance_type="p3.16xlarge",
        gpu_model="V100 16GB", gpu_count=8, gpu_memory_gb=128,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=2400, fp16_tflops=251.2,
        on_demand_hourly=24.48,
        lambda_hr=11.20, coreweave_hr=8.80, jarvis_hr=10.00, runpod_hr=7.12,
    ),
    "p3dn.24xlarge": GpuSkuSpec(
        provider="aws", instance_type="p3dn.24xlarge",
        gpu_model="V100 32GB", gpu_count=8, gpu_memory_gb=256,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=2400, fp16_tflops=251.2,
        on_demand_hourly=31.21,
        lambda_hr=14.40, coreweave_hr=11.20, jarvis_hr=12.80, runpod_hr=9.60,
    ),
    # P4 – A100
    "p4d.24xlarge": GpuSkuSpec(
        provider="aws", instance_type="p4d.24xlarge",
        gpu_model="A100 40GB", gpu_count=8, gpu_memory_gb=320,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=32.77,
        lambda_hr=20.32, coreweave_hr=17.60, jarvis_hr=19.20, runpod_hr=14.24,
    ),
    "p4de.24xlarge": GpuSkuSpec(
        provider="aws", instance_type="p4de.24xlarge",
        gpu_model="A100 80GB", gpu_count=8, gpu_memory_gb=640,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=40.96,
        lambda_hr=25.60, coreweave_hr=22.40, jarvis_hr=24.00, runpod_hr=17.92,
    ),
    # P5 – H100
    "p5.48xlarge": GpuSkuSpec(
        provider="aws", instance_type="p5.48xlarge",
        gpu_model="H100 80GB", gpu_count=8, gpu_memory_gb=640,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Hopper", tdp_watts=5600, fp16_tflops=1600.0,
        on_demand_hourly=98.32,
        lambda_hr=56.96, coreweave_hr=49.60, jarvis_hr=54.40, runpod_hr=41.60,
    ),
    # G4 – T4
    "g4dn.xlarge": GpuSkuSpec(
        provider="aws", instance_type="g4dn.xlarge",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=0.526,
        lambda_hr=0.35, coreweave_hr=0.29, jarvis_hr=0.32, runpod_hr=0.22,
    ),
    "g4dn.2xlarge": GpuSkuSpec(
        provider="aws", instance_type="g4dn.2xlarge",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=0.752,
        lambda_hr=0.45, coreweave_hr=0.38, jarvis_hr=0.42, runpod_hr=0.28,
    ),
    "g4dn.4xlarge": GpuSkuSpec(
        provider="aws", instance_type="g4dn.4xlarge",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=1.204,
        lambda_hr=0.72, coreweave_hr=0.61, jarvis_hr=0.68, runpod_hr=0.46,
    ),
    # G5 – A10G
    "g5.2xlarge": GpuSkuSpec(
        provider="aws", instance_type="g5.2xlarge",
        gpu_model="A10G 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ampere", tdp_watts=150, fp16_tflops=62.5,
        on_demand_hourly=1.212,
        lambda_hr=0.76, coreweave_hr=0.65, jarvis_hr=0.72, runpod_hr=0.51,
    ),
    "g5.4xlarge": GpuSkuSpec(
        provider="aws", instance_type="g5.4xlarge",
        gpu_model="A10G 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ampere", tdp_watts=150, fp16_tflops=62.5,
        on_demand_hourly=1.624,
        lambda_hr=0.98, coreweave_hr=0.84, jarvis_hr=0.93, runpod_hr=0.66,
    ),
    # Trainium / Inferentia
    "trn1.32xlarge": GpuSkuSpec(
        provider="aws", instance_type="trn1.32xlarge",
        gpu_model="Trainium", gpu_count=16, gpu_memory_gb=512,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Trainium", tdp_watts=2800, fp16_tflops=840.0,
        on_demand_hourly=21.50,
        lambda_hr=None, coreweave_hr=15.20, jarvis_hr=None, runpod_hr=12.80,
    ),
    "inf2.xlarge": GpuSkuSpec(
        provider="aws", instance_type="inf2.xlarge",
        gpu_model="Inferentia2", gpu_count=1, gpu_memory_gb=32,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Inferentia", tdp_watts=75, fp16_tflops=47.5,
        on_demand_hourly=0.758,
        lambda_hr=None, coreweave_hr=0.29, jarvis_hr=0.32, runpod_hr=0.22,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# Azure GPU Instance Specs
# ─────────────────────────────────────────────────────────────────────────────

AZURE_GPU_SPECS: dict[str, GpuSkuSpec] = {
    # NC-series v3 (V100)
    "standard_nc6s_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC6s_v3",
        gpu_model="V100 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=300, fp16_tflops=31.4,
        on_demand_hourly=3.06,
    ),
    "standard_nc12s_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC12s_v3",
        gpu_model="V100 16GB", gpu_count=2, gpu_memory_gb=32,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=600, fp16_tflops=62.8,
        on_demand_hourly=6.12,
    ),
    "standard_nc24s_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC24s_v3",
        gpu_model="V100 16GB", gpu_count=4, gpu_memory_gb=64,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Volta", tdp_watts=1200, fp16_tflops=125.6,
        on_demand_hourly=12.24,
    ),
    # ND-series v4 (A100)
    "standard_nd96asr_v4": GpuSkuSpec(
        provider="azure", instance_type="Standard_ND96asr_v4",
        gpu_model="A100 40GB", gpu_count=8, gpu_memory_gb=320,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=27.20,
    ),
    "standard_nd96amsr_a100_v4": GpuSkuSpec(
        provider="azure", instance_type="Standard_ND96amsr_A100_v4",
        gpu_model="A100 80GB", gpu_count=8, gpu_memory_gb=640,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=32.77,
    ),
    # NC H100 v5
    "standard_nc40ads_h100_v5": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC40ads_H100_v5",
        gpu_model="H100 80GB", gpu_count=1, gpu_memory_gb=80,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Hopper", tdp_watts=700, fp16_tflops=200.0,
        on_demand_hourly=12.29,
    ),
    "standard_nc80adis_h100_v5": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC80adis_H100_v5",
        gpu_model="H100 80GB", gpu_count=2, gpu_memory_gb=160,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Hopper", tdp_watts=1400, fp16_tflops=400.0,
        on_demand_hourly=24.58,
    ),
    # NV-series (visualization / A10)
    "standard_nv6": GpuSkuSpec(
        provider="azure", instance_type="Standard_NV6",
        gpu_model="M60 8GB", gpu_count=1, gpu_memory_gb=8,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Maxwell", tdp_watts=150, fp16_tflops=4.8,
        on_demand_hourly=1.14,
    ),
    "standard_nv36ads_a10_v5": GpuSkuSpec(
        provider="azure", instance_type="Standard_NV36ads_A10_v5",
        gpu_model="A10 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ampere", tdp_watts=150, fp16_tflops=62.5,
        on_demand_hourly=1.80,
    ),
    "standard_nv72ads_a10_v5": GpuSkuSpec(
        provider="azure", instance_type="Standard_NV72ads_A10_v5",
        gpu_model="A10 24GB", gpu_count=2, gpu_memory_gb=48,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ampere", tdp_watts=300, fp16_tflops=125.0,
        on_demand_hourly=3.60,
    ),
    # NC T4 v3
    "standard_nc4as_t4_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC4as_T4_v3",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=0.526,
    ),
    "standard_nc8as_t4_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC8as_T4_v3",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=0.752,
    ),
    "standard_nc16as_t4_v3": GpuSkuSpec(
        provider="azure", instance_type="Standard_NC16as_T4_v3",
        gpu_model="T4 16GB", gpu_count=1, gpu_memory_gb=16,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Turing", tdp_watts=70, fp16_tflops=65.1,
        on_demand_hourly=1.204,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# GCP GPU Instance Specs
# ─────────────────────────────────────────────────────────────────────────────

GCP_GPU_SPECS: dict[str, GpuSkuSpec] = {
    # A2 – A100 40GB
    "a2-highgpu-1g": GpuSkuSpec(
        provider="gcp", instance_type="a2-highgpu-1g",
        gpu_model="A100 40GB", gpu_count=1, gpu_memory_gb=40,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=400, fp16_tflops=78.0,
        on_demand_hourly=3.67,
    ),
    "a2-highgpu-2g": GpuSkuSpec(
        provider="gcp", instance_type="a2-highgpu-2g",
        gpu_model="A100 40GB", gpu_count=2, gpu_memory_gb=80,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=800, fp16_tflops=156.0,
        on_demand_hourly=7.35,
    ),
    "a2-highgpu-4g": GpuSkuSpec(
        provider="gcp", instance_type="a2-highgpu-4g",
        gpu_model="A100 40GB", gpu_count=4, gpu_memory_gb=160,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=1600, fp16_tflops=312.0,
        on_demand_hourly=14.69,
    ),
    "a2-highgpu-8g": GpuSkuSpec(
        provider="gcp", instance_type="a2-highgpu-8g",
        gpu_model="A100 40GB", gpu_count=8, gpu_memory_gb=320,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=29.39,
    ),
    # A2 Ultra – A100 80GB
    "a2-ultragpu-1g": GpuSkuSpec(
        provider="gcp", instance_type="a2-ultragpu-1g",
        gpu_model="A100 80GB", gpu_count=1, gpu_memory_gb=80,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=400, fp16_tflops=78.0,
        on_demand_hourly=5.12,
    ),
    "a2-ultragpu-2g": GpuSkuSpec(
        provider="gcp", instance_type="a2-ultragpu-2g",
        gpu_model="A100 80GB", gpu_count=2, gpu_memory_gb=160,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=800, fp16_tflops=156.0,
        on_demand_hourly=10.24,
    ),
    "a2-ultragpu-4g": GpuSkuSpec(
        provider="gcp", instance_type="a2-ultragpu-4g",
        gpu_model="A100 80GB", gpu_count=4, gpu_memory_gb=320,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=1600, fp16_tflops=312.0,
        on_demand_hourly=20.48,
    ),
    "a2-ultragpu-8g": GpuSkuSpec(
        provider="gcp", instance_type="a2-ultragpu-8g",
        gpu_model="A100 80GB", gpu_count=8, gpu_memory_gb=640,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Ampere", tdp_watts=3200, fp16_tflops=624.0,
        on_demand_hourly=40.96,
    ),
    # G2 – L4
    "g2-standard-4": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-4",
        gpu_model="L4 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=72, fp16_tflops=121.0,
        on_demand_hourly=0.84,
    ),
    "g2-standard-8": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-8",
        gpu_model="L4 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=72, fp16_tflops=121.0,
        on_demand_hourly=1.01,
    ),
    "g2-standard-12": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-12",
        gpu_model="L4 24GB", gpu_count=1, gpu_memory_gb=24,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=72, fp16_tflops=121.0,
        on_demand_hourly=1.18,
    ),
    "g2-standard-16": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-16",
        gpu_model="L4 24GB", gpu_count=2, gpu_memory_gb=48,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=144, fp16_tflops=242.0,
        on_demand_hourly=1.68,
    ),
    "g2-standard-24": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-24",
        gpu_model="L4 24GB", gpu_count=2, gpu_memory_gb=48,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=144, fp16_tflops=242.0,
        on_demand_hourly=2.02,
    ),
    "g2-standard-32": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-32",
        gpu_model="L4 24GB", gpu_count=4, gpu_memory_gb=96,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=288, fp16_tflops=484.0,
        on_demand_hourly=3.36,
    ),
    "g2-standard-48": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-48",
        gpu_model="L4 24GB", gpu_count=4, gpu_memory_gb=96,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=288, fp16_tflops=484.0,
        on_demand_hourly=4.03,
    ),
    "g2-standard-96": GpuSkuSpec(
        provider="gcp", instance_type="g2-standard-96",
        gpu_model="L4 24GB", gpu_count=8, gpu_memory_gb=192,
        supports_mig=False, mig_slices_per_gpu=0,
        architecture="Ada Lovelace", tdp_watts=576, fp16_tflops=968.0,
        on_demand_hourly=6.72,
    ),
    # A3 – H100
    "a3-highgpu-8g": GpuSkuSpec(
        provider="gcp", instance_type="a3-highgpu-8g",
        gpu_model="H100 80GB", gpu_count=8, gpu_memory_gb=640,
        supports_mig=True, mig_slices_per_gpu=7,
        architecture="Hopper", tdp_watts=5600, fp16_tflops=1600.0,
        on_demand_hourly=98.32,
    ),
}

# GCP guest accelerator type → spec mapping (for N1/N2 instances with attached GPUs)
GCP_ACCELERATOR_SPECS: dict[str, dict[str, Any]] = {
    "nvidia-tesla-t4": {"gpu_model": "T4 16GB", "gpu_memory_gb": 16, "supports_mig": False, "architecture": "Turing", "tdp_watts": 70, "fp16_tflops": 65.1},
    "nvidia-tesla-v100": {"gpu_model": "V100 16GB", "gpu_memory_gb": 16, "supports_mig": False, "architecture": "Volta", "tdp_watts": 300, "fp16_tflops": 31.4},
    "nvidia-tesla-p100": {"gpu_model": "P100 16GB", "gpu_memory_gb": 16, "supports_mig": False, "architecture": "Pascal", "tdp_watts": 250, "fp16_tflops": 21.2},
    "nvidia-tesla-a100": {"gpu_model": "A100 40GB", "gpu_memory_gb": 40, "supports_mig": True, "architecture": "Ampere", "tdp_watts": 400, "fp16_tflops": 78.0},
    "nvidia-a100-80gb": {"gpu_model": "A100 80GB", "gpu_memory_gb": 80, "supports_mig": True, "architecture": "Ampere", "tdp_watts": 400, "fp16_tflops": 78.0},
    "nvidia-l4": {"gpu_model": "L4 24GB", "gpu_memory_gb": 24, "supports_mig": False, "architecture": "Ada Lovelace", "tdp_watts": 72, "fp16_tflops": 121.0},
    "nvidia-h100-80gb": {"gpu_model": "H100 80GB", "gpu_memory_gb": 80, "supports_mig": True, "architecture": "Hopper", "tdp_watts": 700, "fp16_tflops": 200.0},
}


# ─────────────────────────────────────────────────────────────────────────────
# Unified lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

_ALL_SPECS: dict[str, GpuSkuSpec] = {**AWS_GPU_SPECS, **AZURE_GPU_SPECS, **GCP_GPU_SPECS}

# Detection prefixes per provider
AWS_GPU_PREFIXES = ("p3", "p4", "p5", "g3", "g4", "g5", "trn1", "inf1", "inf2", "dl1")
AZURE_GPU_PREFIXES = ("standard_nc", "standard_nd", "standard_nv")
GCP_GPU_MACHINE_PREFIXES = ("a2-", "g2-", "a3-")

HOURS_PER_MONTH = 730


def get_spec(instance_type: str) -> GpuSkuSpec | None:
    """Look up GPU spec by instance type (case-insensitive)."""
    return _ALL_SPECS.get(instance_type.lower().strip())


def get_spec_for_provider(instance_type: str, provider: str) -> GpuSkuSpec | None:
    """Look up GPU spec scoped to a specific provider."""
    key = instance_type.lower().strip()
    spec_map = {
        "aws": AWS_GPU_SPECS,
        "azure": AZURE_GPU_SPECS,
        "gcp": GCP_GPU_SPECS,
    }
    return spec_map.get(provider, {}).get(key)


def is_gpu_instance_type(instance_type: str, provider: str | None = None) -> bool:
    """Check if an instance type string indicates a GPU instance."""
    it = instance_type.lower().strip()
    if provider == "aws" or provider is None:
        if any(it.startswith(p) for p in AWS_GPU_PREFIXES):
            return True
    if provider == "azure" or provider is None:
        if any(it.startswith(p) for p in AZURE_GPU_PREFIXES):
            return True
    if provider == "gcp" or provider is None:
        if any(it.startswith(p) for p in GCP_GPU_MACHINE_PREFIXES):
            return True
    return False


def get_all_specs_for_provider(provider: str) -> dict[str, GpuSkuSpec]:
    """Return all GPU specs for a given provider."""
    return {k: v for k, v in _ALL_SPECS.items() if v.provider == provider}
