import httpx
import logging
import os
import asyncio
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self):
        self._cache: Dict[str, tuple] = {}
        self.client = httpx.AsyncClient(timeout=10.0)
        self.infracost_api_key = os.getenv("INFRACOST_API_KEY")

    def _get_cache(self, key: str) -> Optional[float]:
        if key in self._cache:
            val, expiry = self._cache[key]
            if time.time() < expiry:
                return val
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: float, ttl: int = 86400):
        self._cache[key] = (value, time.time() + ttl)

    async def fetch_with_retry(self, make_request_coro, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = await make_request_coro()
                if response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                if attempt == max_retries - 1:
                    logger.error(f"API failed after {max_retries} attempts: {e}")
                    return None
                await asyncio.sleep(1)
        return None

    async def get_infracost_price(self, vendor: str, service: str, product_family: str, region: str, filters: List[Dict[str, str]]) -> Optional[float]:
        api_key = self.infracost_api_key
        if not api_key:
            try:
                from ..config import get_settings
                api_key = get_settings().infracost_api_key
            except Exception as e:
                pass
        
        api_key = api_key or os.getenv("INFRACOST_API_KEY")
        if not api_key:
            return None

        # Strip "ico-" prefix if present (dashboard display format vs actual key)
        if api_key.startswith("ico-"):
            api_key = api_key[4:]

        cache_key = f"infracost:{vendor}:{service}:{product_family}:{region}:{str(filters)}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = "https://pricing.api.infracost.io/graphql"
        # Keys starting with "ics" use Bearer token auth; legacy keys use X-Api-Key header
        if api_key.startswith("ics"):
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
        # Use any of [value, value_regex] in attribute filters
        query = """
        query($vendor: String!, $service: String!, $productFamily: String!, $region: String!, $attributeFilters: [AttributeFilter!]) {
          products(filter: {vendorName: $vendor, service: $service, productFamily: $productFamily, region: $region, attributeFilters: $attributeFilters}) {
            prices(filter: {purchaseOption: "on_demand"}) { USD }
          }
        }
        """

        async def make_req():
            return await self.client.post(url, headers=headers, json={"query": query, "variables": {"vendor": vendor, "service": service, "productFamily": product_family, "region": region, "attributeFilters": filters}})

        response = await self.fetch_with_retry(make_req)
        if not response:
            return None
            
        data = response.json()
        if "errors" in data:
            logger.error(f"Infracost API returned errors: {data['errors']}")
            return None

        products = data.get("data", {}).get("products", [])
        if not products:
            logger.warning(f"WARNING: No pricing found for {vendor} {service} {product_family} in {region}. Using fallback.")
            return None

        valid_price = None
        for product in products:
            for price_obj in product.get("prices", []):
                if price_obj.get("USD") is not None:
                    p_val = float(price_obj["USD"])
                    if p_val > 0:
                        self._set_cache(cache_key, p_val)
                        return p_val
                    if valid_price is None:
                        valid_price = p_val

        if valid_price is not None:
            self._set_cache(cache_key, valid_price)
            return valid_price
            
        return None

    async def get_azure_price(self, filter_query: str, region: str, meter_name: Optional[str] = None, exclude_product: Optional[str] = None) -> Optional[float]:
        cache_key = f"azure:{region}:{filter_query}:{meter_name or ''}:{exclude_product or ''}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = "https://prices.azure.com/api/retail/prices"
        async def make_req():
            return await self.client.get(url, params={"$filter": filter_query})

        response = await self.fetch_with_retry(make_req)
        if not response:
            return None

        items = response.json().get("Items", [])
        if not items:
            logger.warning(f"No Azure pricing found for filter: {filter_query}")
            return None

        # Filter by meter name if specified, skip Spot/Low Priority/excluded products
        for item in items:
            item_meter = item.get("meterName", "")
            if "Spot" in item_meter or "Low Priority" in item_meter:
                continue
            if meter_name and meter_name not in item_meter:
                continue
            if exclude_product:
                product_name = item.get("productName", "")
                if exclude_product.lower() in product_name.lower():
                    continue
            if "retailPrice" in item:
                price = float(item["retailPrice"])
                if price > 0:
                    self._set_cache(cache_key, price)
                    return price
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

price_service = PriceService()
