import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.core.provider_pricing_catalog import (
    CATALOG_COST_SOURCE,
    ProviderPricingCatalog,
)


class FakeCatalogDB:
    def __init__(self, catalog_rows=None, resources=None):
        self.catalog_rows = catalog_rows or []
        self.resources = resources or []
        self.updates = []
        self.upserts = []

    async def select(self, table, columns="*", filters=None):
        filters = filters or {}
        if table == "cloud_price_catalog":
            rows = []
            for row in self.catalog_rows:
                if filters.get("provider") and row.get("provider") != filters["provider"]:
                    continue
                if filters.get("service_code") and row.get("service_code") != filters["service_code"]:
                    continue
                rows.append(row)
            return rows
        if table == "cloud_price_catalog_syncs":
            return []
        return []

    async def get_resources(self, user_id, integration_id=None):
        rows = [row for row in self.resources if row.get("user_id") == user_id]
        if integration_id:
            rows = [row for row in rows if row.get("integration_id") == integration_id]
        return rows

    async def update(self, table, data, filters):
        self.updates.append((table, data, filters))
        return []

    async def upsert(self, table, data):
        rows = data if isinstance(data, list) else [data]
        self.upserts.append((table, rows))
        return rows


def test_normalize_azure_retail_item_preserves_official_price_fields():
    catalog = ProviderPricingCatalog()

    row = catalog.normalize_azure_retail_item(
        {
            "currencyCode": "USD",
            "retailPrice": 0.05,
            "unitOfMeasure": "1 Hour",
            "armRegionName": "eastus",
            "effectiveStartDate": "2026-04-01T00:00:00Z",
            "meterId": "meter-1",
            "productName": "Virtual Machines B Series",
            "skuId": "sku-1",
            "skuName": "B2s",
            "serviceName": "Virtual Machines",
            "serviceFamily": "Compute",
            "type": "Consumption",
            "armSkuName": "Standard_B2s",
        },
        "batch-1",
    )

    assert row is not None
    assert row["provider"] == "azure"
    assert row["source"] == "azure_retail_prices_api"
    assert row["unit_price"] == 0.05
    assert row["price_per_month"] == 36.5
    assert row["attributes"]["armSkuName"] == "Standard_B2s"


def test_normalize_aws_price_product_flattens_on_demand_price_dimensions():
    catalog = ProviderPricingCatalog()

    rows = catalog.normalize_aws_price_product(
        {
            "product": {
                "sku": "sku-1",
                "productFamily": "Compute Instance",
                "attributes": {
                    "servicecode": "AmazonEC2",
                    "servicename": "Amazon Elastic Compute Cloud",
                    "instanceType": "t3.micro",
                    "regionCode": "us-east-1",
                    "operatingSystem": "Linux",
                    "tenancy": "Shared",
                },
            },
            "terms": {
                "OnDemand": {
                    "term-1": {
                        "effectiveDate": "2026-04-01T00:00:00Z",
                        "priceDimensions": {
                            "rate-1": {
                                "rateCode": "rate-1",
                                "unit": "Hrs",
                                "description": "$0.01 per On Demand Linux t3.micro Instance Hour",
                                "pricePerUnit": {"USD": "0.0100000000"},
                            }
                        },
                    }
                }
            },
        },
        "AmazonEC2",
        "batch-1",
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "aws"
    assert rows[0]["service_code"] == "AmazonEC2"
    assert rows[0]["unit_price"] == 0.01
    assert rows[0]["price_per_month"] == 7.3
    assert rows[0]["attributes"]["instanceType"] == "t3.micro"


def test_normalize_gcp_sku_expands_regions_and_tiered_rates():
    catalog = ProviderPricingCatalog()

    rows = catalog.normalize_gcp_sku(
        {"serviceId": "6F81-5844-456A", "displayName": "Compute Engine"},
        {
            "skuId": "sku-gcp-1",
            "description": "Balanced PD Capacity",
            "serviceRegions": ["us-central1"],
            "category": {
                "resourceFamily": "Compute",
                "resourceGroup": "Storage",
                "usageType": "OnDemand",
            },
            "pricingInfo": [
                {
                    "effectiveTime": "2026-04-01T00:00:00Z",
                    "pricingExpression": {
                        "usageUnit": "GiBy.mo",
                        "tieredRates": [
                            {
                                "startUsageAmount": 0,
                                "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": 40000000},
                            }
                        ],
                    },
                }
            ],
        },
        "batch-1",
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "gcp"
    assert rows[0]["unit_price"] == 0.04
    assert rows[0]["region"] == "us-central1"
    assert rows[0]["resource_group"] == "Storage"


def test_catalog_estimate_applies_only_to_non_actual_zero_cost_resources():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "price-1",
                "provider": "aws",
                "catalog_key": "aws:ec2:t3micro",
                "service_code": "AmazonEC2",
                "region": "us-east-1",
                "unit": "Hrs",
                "unit_price": 0.02,
                "currency": "USD",
                "attributes": {
                    "instanceType": "t3.micro",
                    "operatingSystem": "Linux",
                    "tenancy": "Shared",
                },
            }
        ],
        resources=[
            {
                "id": "res-actual",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "aws",
                "resource_name": "actual",
                "service_type": "AWS EC2 Instance",
                "region": "us-east-1",
                "cost": 1.0,
                "metadata": {"instance_type": "t3.micro", "cost_source": "actual"},
            },
            {
                "id": "res-estimate",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "aws",
                "resource_name": "estimate",
                "service_type": "AWS EC2 Instance",
                "region": "us-east-1",
                "cost": 0,
                "metadata": {"instance_type": "t3.micro", "cost_source": "pricing_unavailable"},
            },
        ],
    )

    db.resources.extend([
        {**db.resources[1], "user_id": "user-other"},
        {**db.resources[1], "id": "res-other-integration", "integration_id": "int-other"},
    ])

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 1
    assert result["skipped_actual"] == 1
    assert result["processed"] == 2
    assert result["unmatched"] == 0
    assert len(db.updates) == 1
    assert db.updates[0][0] == "resources"
    assert db.updates[0][1]["cost"] == 14.6
    assert db.updates[0][1]["metadata"]["cost_source"] == CATALOG_COST_SOURCE
    assert db.updates[0][1]["metadata"]["cost_basis"] == "provider_market_list_price"
    assert db.updates[0][1]["metadata"]["pricing_source"] == "provider_catalog"
    assert db.updates[0][1]["metadata"]["catalog_price_id"] == "price-1"
    assert db.updates[0][1]["metadata"]["catalog_key"] == "aws:ec2:t3micro"
    assert db.updates[0][1]["metadata"]["catalog_unit"] == "Hrs"
    assert db.updates[0][1]["metadata"]["catalog_unit_price"] == 0.02
    assert db.updates[0][1]["metadata"]["catalog_quantity"] == 730.0
    assert db.updates[0][1]["metadata"]["currency"] == "USD"
    assert db.updates[0][1]["metadata"]["actual_billing_required"] is True
    assert db.updates[0][2] == {"user_id": "user-1", "id": "res-estimate"}


def test_aws_catalog_estimate_uses_metadata_region_when_resource_region_is_global():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "price-1",
                "provider": "aws",
                "catalog_key": "aws:ec2:t3micro",
                "service_code": "AmazonEC2",
                "region": "us-east-1",
                "unit": "Hrs",
                "unit_price": 0.01,
                "attributes": {
                    "instanceType": "t3.micro",
                    "operatingSystem": "Linux",
                    "tenancy": "Shared",
                },
            }
        ],
        resources=[
            {
                "id": "res-estimate",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "aws",
                "resource_name": "estimate",
                "service_type": "AWS EC2 Instance",
                "region": "global",
                "cost": 0,
                "metadata": {
                    "aws_region": "us-east-1",
                    "instance_type": "t3.micro",
                    "cost_source": "pricing_unavailable",
                },
            },
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 1
    assert db.updates[0][1]["cost"] == 7.3


def test_gcp_disk_catalog_estimate_accepts_giby_month_unit():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "price-gcp-1",
                "provider": "gcp",
                "catalog_key": "gcp:pd-balanced",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "GiBy.mo",
                "unit_price": 0.04,
                "currency": "USD",
                "description": "Balanced PD Capacity",
                "resource_group": "Storage",
            }
        ],
        resources=[
            {
                "id": "disk-1",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "gcp",
                "resource_name": "disk-1",
                "service_type": "GCP Persistent Disk",
                "region": "us-central1-a",
                "cost": 0,
                "metadata": {"size_gb": 100, "type": "pd-balanced", "cost_source": "pricing_unavailable"},
            }
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 1
    assert result["processed"] == 1
    assert db.updates[0][1]["cost"] == 4.0
    assert db.updates[0][1]["metadata"]["cost_source"] == CATALOG_COST_SOURCE
    assert db.updates[0][1]["metadata"]["currency"] == "USD"


def test_gcp_disk_catalog_estimate_matches_official_pd_capacity_descriptions():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "price-balanced",
                "provider": "gcp",
                "catalog_key": "gcp:pd-balanced",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "GiBy.mo",
                "unit_price": 0.04,
                "description": "Balanced PD Capacity",
                "resource_group": "PDStandard",
            },
            {
                "id": "price-ssd",
                "provider": "gcp",
                "catalog_key": "gcp:pd-ssd",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "GiBy.mo",
                "unit_price": 0.17,
                "description": "SSD backed PD Capacity",
                "resource_group": "SSD",
            },
            {
                "id": "price-extreme",
                "provider": "gcp",
                "catalog_key": "gcp:pd-extreme",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "GiBy.mo",
                "unit_price": 0.3,
                "description": "Extreme PD Capacity",
                "resource_group": "SSD",
            },
        ],
        resources=[
            {
                "id": "balanced-disk",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "gcp",
                "resource_name": "balanced-disk",
                "service_type": "GCP Persistent Disk",
                "region": "us-central1-a",
                "cost": 0,
                "metadata": {"size_gb": 30, "type": "pd-balanced", "cost_source": "pricing_unavailable"},
            },
            {
                "id": "ssd-disk",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "gcp",
                "resource_name": "ssd-disk",
                "service_type": "GCP Persistent Disk",
                "region": "us-central1-a",
                "cost": 0,
                "metadata": {"size_gb": 100, "type": "pd-ssd", "cost_source": "pricing_unavailable"},
            },
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 2
    assert db.updates[0][1]["cost"] == 1.2
    assert db.updates[1][1]["cost"] == 17.0
    assert db.updates[1][1]["metadata"]["catalog_key"] == "gcp:pd-ssd"


def test_gcp_compute_catalog_estimate_combines_cpu_and_ram_prices():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "cpu-price",
                "provider": "gcp",
                "catalog_key": "gcp:e2-cpu",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "h",
                "unit_price": 0.02,
                "currency": "USD",
                "description": "E2 Instance Core running in Americas",
                "resource_group": "CPU",
                "usage_type": "OnDemand",
            },
            {
                "id": "ram-price",
                "provider": "gcp",
                "catalog_key": "gcp:e2-ram",
                "service_code": "6F81-5844-456A",
                "service_name": "Compute Engine",
                "region": "us-central1",
                "unit": "GiBy.h",
                "unit_price": 0.003,
                "currency": "USD",
                "description": "E2 Instance Ram running in Americas",
                "resource_group": "RAM",
                "usage_type": "OnDemand",
            },
        ],
        resources=[
            {
                "id": "vm-1",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "gcp",
                "resource_name": "vm-1",
                "service_type": "GCP Compute Instance",
                "region": "us-central1-a",
                "cost": 0,
                "metadata": {"machine_type": "e2-standard-2", "cost_source": "pricing_unavailable"},
            }
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 1
    assert db.updates[0][1]["cost"] == 46.72
    assert db.updates[0][1]["metadata"]["cost_source"] == CATALOG_COST_SOURCE
    assert db.updates[0][1]["metadata"]["currency"] == "USD"


def test_azure_vm_catalog_estimate_accepts_instance_type_without_standard_prefix():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "azure-vm-price",
                "provider": "azure",
                "catalog_key": "azure:vm:d8as-v5",
                "service_code": "Virtual Machines",
                "region": "eastus",
                "unit": "1 Hour",
                "unit_price": 0.344,
                "description": "D8as v5",
                "product_family": "Virtual Machines Dasv5 Series",
                "attributes": {
                    "armSkuName": "Standard_D8as_v5",
                    "priceType": "Consumption",
                },
            },
            {
                "id": "azure-spot-price",
                "provider": "azure",
                "catalog_key": "azure:vm:d8as-v5-low-priority",
                "service_code": "Virtual Machines",
                "region": "eastus",
                "unit": "1 Hour",
                "unit_price": 0.0688,
                "description": "D8as v5 Low Priority",
                "product_family": "Virtual Machines Dasv5 Series",
                "attributes": {
                    "armSkuName": "Standard_D8as_v5",
                    "priceType": "Consumption",
                },
            },
        ],
        resources=[
            {
                "id": "vm-azure-1",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "azure",
                "resource_name": "vm-azure-1",
                "service_type": "Azure Virtual Machine",
                "region": "eastus",
                "cost": 0,
                "metadata": {"instance_type": "D8as_v5", "cost_source": "pricing_unavailable"},
            }
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 1
    assert db.updates[0][1]["cost"] == 251.12
    assert db.updates[0][1]["metadata"]["cost_source"] == CATALOG_COST_SOURCE


def test_azure_disk_catalog_estimate_requires_size_and_monthly_unit():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[
            {
                "id": "azure-disk-hourly",
                "provider": "azure",
                "catalog_key": "azure:disk-hourly",
                "service_code": "Storage",
                "region": "eastus",
                "unit": "1 GiB/Hour",
                "unit_price": 0.0001,
                "description": "Premium SSD Managed Disks Operations",
                "product_family": "Managed Disks",
            },
            {
                "id": "azure-disk-monthly",
                "provider": "azure",
                "catalog_key": "azure:disk-monthly",
                "service_code": "Storage",
                "region": "eastus",
                "unit": "1 GiB/Month",
                "unit_price": 0.12,
                "description": "Premium SSD Managed Disk Capacity",
                "product_family": "Managed Disks",
            },
        ],
        resources=[
            {
                "id": "disk-without-size",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "azure",
                "resource_name": "disk-without-size",
                "service_type": "Azure Managed Disk",
                "region": "eastus",
                "cost": 0,
                "metadata": {"cost_source": "pricing_unavailable"},
            },
            {
                "id": "disk-with-size",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "azure",
                "resource_name": "disk-with-size",
                "service_type": "Azure Managed Disk",
                "region": "eastus",
                "cost": 0,
                "metadata": {"size_gb": 100, "cost_source": "pricing_unavailable"},
            },
            {
                "id": "disk-with-disk-size",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "azure",
                "resource_name": "disk-with-disk-size",
                "service_type": "Azure Managed Disk",
                "region": "eastus",
                "cost": 0,
                "metadata": {"disk_size_gb": 200, "cost_source": "pricing_unavailable"},
            },
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 2
    assert result["unmatched"] == 1
    assert db.updates[0][2] == {"user_id": "user-1", "id": "disk-with-size"}
    assert db.updates[0][1]["cost"] == 12.0
    assert db.updates[1][2] == {"user_id": "user-1", "id": "disk-with-disk-size"}
    assert db.updates[1][1]["cost"] == 24.0


@pytest.mark.parametrize("metadata", [
    {"machine_type": "e2-standard-2", "cost_source": "pricing_unavailable"},
    {},
    None,
])
def test_catalog_estimate_leaves_unmatched_resource_unchanged(metadata: dict[str, str] | None):
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB(
        catalog_rows=[],
        resources=[
            {
                "id": "res-1",
                "user_id": "user-1",
                "integration_id": "int-1",
                "provider": "gcp",
                "resource_name": "vm",
                "service_type": "GCP Compute Instance",
                "region": "us-central1-a",
                "cost": 0,
                "metadata": metadata,
            }
        ],
    )

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result["updated"] == 0
    assert result["unmatched"] == 1
    assert result["skipped_actual"] == 0
    assert result["processed"] == 1
    assert db.updates == []


@pytest.mark.parametrize("cost_source", ["billing_unavailable", "actual", "no_direct_charge", "included", "free"])
@pytest.mark.parametrize("cost", [0.0, 12.0])
def test_catalog_estimate_skips_protected_costs_before_lookup(
    monkeypatch: pytest.MonkeyPatch, cost_source: str, cost: float,
):
    catalog = ProviderPricingCatalog()
    lookup = AsyncMock(wraps=catalog.estimate_resource_monthly_cost)
    monkeypatch.setattr(catalog, "estimate_resource_monthly_cost", lookup)
    db = FakeCatalogDB(resources=[{
        "id": "res-protected",
        "user_id": "user-1",
        "integration_id": "int-1",
        "provider": "aws",
        "service_type": "AWS EC2 Instance",
        "region": "us-east-1",
        "status": "Active",
        "cost": cost,
        "metadata": {"instance_type": "t3.micro", "cost_source": cost_source},
    }])
    original_resources = deepcopy(db.resources)

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result == {"updated": 0, "skipped_actual": 1, "unmatched": 0, "processed": 1, "samples": []}
    lookup.assert_not_awaited()
    assert db.updates == []
    assert db.resources == original_resources


def test_catalog_estimate_handles_empty_resources():
    catalog = ProviderPricingCatalog()
    db = FakeCatalogDB()

    result = asyncio.run(catalog.apply_catalog_estimates(db, "user-1", integration_id="int-1"))

    assert result == {"updated": 0, "skipped_actual": 0, "unmatched": 0, "processed": 0, "samples": []}
    assert db.updates == []
