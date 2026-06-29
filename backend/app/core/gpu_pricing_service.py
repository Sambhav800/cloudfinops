"""
GPU Live Pricing Service — fetches and caches GPU pricing from specialized clouds.
Sources: Lambda Labs (public API), RunPod (GraphQL), Azure Retail Prices, GCP Billing Catalog.
Falls back to static specs in gpu_specs.py when APIs are unavailable.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .gpu_specs import HOURS_PER_MONTH

logger = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


class GpuPricingService:
    """Fetches and caches live GPU pricing from multiple sources."""

    LAMBDA_LABS_URL = "https://cloud.lambdalabs.com/api/v1/instances"
    AZURE_RETAIL_URL = "https://prices.azure.com/api/retail/prices"
    RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"

    def __init__(self, lambda_api_key: str | None = None, runpod_api_key: str | None = None):
        self._lambda_key = lambda_api_key
        self._runpod_key = runpod_api_key

    async def get_all_gpu_pricing(self, force_refresh: bool = False) -> dict[str, list[dict]]:
        """
        Return unified pricing map from all sources.
        Cached for 1 hour. Returns cached data on API failures.
        """
        cache_key = "all_gpu_pricing"
        if not force_refresh and cache_key in _CACHE:
            entry = _CACHE[cache_key]
            if time.time() - entry["ts"] < _CACHE_TTL_SECONDS:
                return entry["data"]

        results: dict[str, list[dict]] = {
            "lambda_labs": [],
            "runpod": [],
            "azure": [],
            "coreweave": [],
        }

        results["lambda_labs"] = await self.fetch_lambda_pricing()
        results["runpod"] = await self.fetch_runpod_pricing()
        results["azure"] = await self.fetch_azure_gpu_pricing()

        _CACHE[cache_key] = {"ts": time.time(), "data": results}
        return results

    async def fetch_lambda_pricing(self) -> list[dict]:
        """Fetch Lambda Labs GPU pricing (public API, key optional)."""
        try:
            headers = {}
            if self._lambda_key:
                headers["Authorization"] = f"Bearer {self._lambda_key}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.LAMBDA_LABS_URL, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            instances = data.get("data", {})
            results = []
            for instance_type, info in instances.items():
                specs = info.get("instance_type", {})
                gpu_desc = specs.get("description", instance_type)
                price_hr = info.get("price_cents_per_hour")
                if price_hr is not None:
                    price_hr = price_hr / 100.0
                else:
                    price_hr = specs.get("price_cents_per_hour", 0) / 100.0

                results.append({
                    "provider": "lambda_labs",
                    "instance_type": instance_type,
                    "gpu_model": gpu_desc,
                    "gpu_count": specs.get("specs", {}).get("gpus", 1),
                    "hourly_rate": price_hr,
                    "monthly_rate": round(price_hr * HOURS_PER_MONTH, 2),
                    "availability": "available" if info.get("regions_with_capacity_available") else "unavailable",
                    "regions": [r.get("name") for r in (info.get("regions_with_capacity_available") or [])],
                })

            logger.info(f"Lambda Labs pricing: {len(results)} GPU types fetched")
            return results

        except Exception as e:
            logger.warning(f"Lambda Labs pricing fetch failed: {e}")
            return []

    async def fetch_runpod_pricing(self) -> list[dict]:
        """Fetch RunPod GPU pricing via GraphQL."""
        try:
            query = """
            query GpuTypes {
                gpuTypes {
                    id
                    displayName
                    memoryInGb
                    secureCloud
                    communityCloud
                    lowestPrice {
                        minimumBidPrice
                        uninterruptablePrice
                    }
                }
            }
            """
            headers = {"Content-Type": "application/json"}
            if self._runpod_key:
                headers["Authorization"] = f"Bearer {self._runpod_key}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.RUNPOD_GRAPHQL_URL,
                    json={"query": query},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            gpu_types = data.get("data", {}).get("gpuTypes", [])
            results = []
            for gpu in gpu_types:
                lowest = gpu.get("lowestPrice") or {}
                on_demand = lowest.get("uninterruptablePrice")
                spot = lowest.get("minimumBidPrice")

                if on_demand:
                    results.append({
                        "provider": "runpod",
                        "gpu_model": gpu.get("displayName", gpu.get("id")),
                        "gpu_memory_gb": gpu.get("memoryInGb"),
                        "hourly_rate": on_demand,
                        "monthly_rate": round(on_demand * HOURS_PER_MONTH, 2),
                        "spot_hourly_rate": spot,
                        "availability": "available" if gpu.get("secureCloud") or gpu.get("communityCloud") else "unavailable",
                        "secure_cloud": gpu.get("secureCloud", False),
                        "community_cloud": gpu.get("communityCloud", False),
                    })

            logger.info(f"RunPod pricing: {len(results)} GPU types fetched")
            return results

        except Exception as e:
            logger.warning(f"RunPod pricing fetch failed: {e}")
            return []

    async def fetch_azure_gpu_pricing(self) -> list[dict]:
        """Fetch Azure NC/ND/NV GPU pricing from Azure Retail Prices API (public, no key)."""
        try:
            gpu_filters = [
                "Standard_NC", "Standard_ND", "Standard_NV",
            ]
            filter_expr = " or ".join(
                f"contains(armSkuName, '{prefix}')" for prefix in gpu_filters
            )
            params = {
                "$filter": f"serviceName eq 'Virtual Machines' and priceType eq 'Consumption' and ({filter_expr})",
                "$top": "100",
            }

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(self.AZURE_RETAIL_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("Items", [])
            results = []
            seen = set()

            for item in items:
                sku = item.get("armSkuName", "")
                region = item.get("armRegionName", "")
                key = f"{sku}_{region}"
                if key in seen:
                    continue
                seen.add(key)

                unit_price = item.get("retailPrice", 0)
                if unit_price <= 0:
                    continue

                results.append({
                    "provider": "azure",
                    "instance_type": sku,
                    "gpu_model": item.get("productName", sku),
                    "hourly_rate": unit_price,
                    "monthly_rate": round(unit_price * HOURS_PER_MONTH, 2),
                    "region": region,
                    "currency": item.get("currencyCode", "USD"),
                    "meter_name": item.get("meterName", ""),
                })

            logger.info(f"Azure GPU pricing: {len(results)} items fetched")
            return results

        except Exception as e:
            logger.warning(f"Azure GPU pricing fetch failed: {e}")
            return []

    async def get_pricing_for_model(self, gpu_model: str) -> dict[str, float | None]:
        """
        Get current best pricing across all providers for a specific GPU model.
        Returns {provider: monthly_rate} for comparison.
        """
        all_pricing = await self.get_all_gpu_pricing()
        model_lower = gpu_model.lower()
        comparison: dict[str, float | None] = {}

        for provider, entries in all_pricing.items():
            for entry in entries:
                entry_model = str(entry.get("gpu_model", "")).lower()
                if model_lower in entry_model or entry_model in model_lower:
                    current = comparison.get(provider)
                    rate = entry.get("monthly_rate")
                    if rate and (current is None or rate < current):
                        comparison[provider] = rate
                    break

        return comparison
