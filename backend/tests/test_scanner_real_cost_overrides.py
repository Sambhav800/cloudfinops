import asyncio
import logging
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from botocore.exceptions import ClientError

from app.api.routes import _run_scan_ai_verification
from app.ai.analyzer import AIAnalyzer
from app.bill_parser.gemini_extractor import extract_bill_with_gemini
from app.core.finance import aggregate_daily_spend_rows
from app.scanners.aws import AWSScanner, ScannedResource as AWSScannedResource
from app.scanners.azure import AzureWasteScanner
from app.scanners.gcp import GCPScanner, ScannedResource as GCPScannedResource


def _make_gcp_scanner(**kwargs) -> GCPScanner:
    with (
        patch("app.scanners.gcp.service_account.Credentials.from_service_account_info"),
        patch("app.scanners.gcp.build"),
    ):
        scanner = GCPScanner(
            project_id="test-project",
            service_account_email="sa@test-project.iam.gserviceaccount.com",
            private_key="-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
            **kwargs,
        )
    scanner.asset_client = None
    return scanner


def test_aws_apply_real_costs_overrides_non_actual_cost():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    resources = [
        AWSScannedResource(
            resource_name="web-1",
            service_type="AWS EC2 Instance",
            cost=12.34,
            status="Zombie",
            region="us-east-1",
            region_compliance="compliant",
            metadata={"instance_id": "i-abc123"},
        )
    ]

    updated = scanner._apply_real_costs(resources, {"i-abc123": 123.45})

    assert updated == 1
    assert resources[0].cost == 123.45
    assert resources[0].metadata["cost_source"] == "actual"
    assert resources[0].metadata["cost_lookup_key"] == "i-abc123"


def test_optional_gemini_bill_extraction_timeout_logs_deterministic_fallback(caplog, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class TimeoutClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.bill_parser.gemini_extractor.httpx.AsyncClient", TimeoutClient)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            extract_bill_with_gemini(
                b"%PDF-1.7\n%%EOF",
                "aws_bill.pdf",
                content_type="application/pdf",
            )
        )

    assert result is None
    assert "Optional Gemini bill extraction timed out" in caplog.text
    assert "deterministic bill parser will continue" in caplog.text


def test_scan_ai_verification_timeout_returns_deterministic_resources(caplog):
    class SlowAnalyzer:
        async def verify_and_analyze(self, *_args, **_kwargs):
            await asyncio.sleep(0.05)
            return {"verified_resources": []}

    resources = [
        {
            "resource_name": "vm-1",
            "service_type": "GCP Compute Instance",
            "cost": 12.5,
        }
    ]

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            _run_scan_ai_verification(
                SlowAnalyzer(),
                resources,
                provider="gcp",
                timeout_seconds=0.001,
            )
        )

    assert result["verified_resources"] == resources
    assert result["total_spend"] == 12.5
    assert result["potential_savings"] == 0
    assert "AI verification timed out for GCP scan" in caplog.text


def test_aws_db_resource_marks_missing_cost_source_as_billing_unavailable():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    resources = [
        AWSScannedResource(
            resource_name="vpc-1",
            service_type="AWS VPC",
            cost=0.0,
            status="Active",
            region="us-east-1",
            region_compliance="compliant",
            metadata={"vpc_id": "vpc-1"},
        )
    ]

    db_rows = scanner.to_db_resources(resources, "user-1", "integration-1")

    assert db_rows[0]["metadata"]["cost_source"] == "billing_unavailable"
    assert "Exact AWS resource cost" in db_rows[0]["metadata"]["pricing_note"]


def test_aws_generic_inventory_aggregates_all_available_sources_when_resource_explorer_succeeds():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])

    class FakePaginator:
        def __init__(self, pages):
            self.pages = pages

        def paginate(self, **_kwargs):
            return self.pages

    class UnavailableClient:
        def __getattr__(self, name):
            raise RuntimeError(f"{name} unavailable")

    def fake_get_client(service: str, _region: str):
        if service == "resource-explorer-2":
            return SimpleNamespace(
                get_paginator=lambda _name: FakePaginator([
                    {
                        "Resources": [
                            {
                                "Arn": "arn:aws:lambda:us-east-1:123456789012:function:ProcessImage",
                                "Service": "lambda",
                                "ResourceType": "lambda:function",
                            }
                        ]
                    }
                ])
            )
        if service == "resourcegroupstaggingapi":
            return SimpleNamespace(
                get_paginator=lambda _name: FakePaginator([
                    {
                        "ResourceTagMappingList": [
                            {
                                "ResourceARN": "arn:aws:sns:us-east-1:123456789012:TopicA",
                                "Tags": [{"Key": "Name", "Value": "TopicA"}],
                            }
                        ]
                    }
                ])
            )
        if service == "dynamodb":
            return SimpleNamespace(
                get_paginator=lambda _name: FakePaginator([
                    {"TableNames": ["Orders"]}
                ])
            )
        return UnavailableClient()

    scanner._get_client = fake_get_client

    resources = asyncio.run(
        scanner._scan_generic_resources("us-east-1", set(), {"orders": 7.5})
    )

    discovery_methods = {resource.metadata["discovery_method"] for resource in resources}
    assert {"resource-explorer-2", "resourcegroupstaggingapi", "explicit-fallback"} <= discovery_methods
    assert any(resource.service_type == "AWS DynamoDB Table" for resource in resources)
    assert next(resource for resource in resources if resource.resource_name == "Orders").cost == 7.5


def test_aws_resource_cost_lookup_uses_resource_level_cost_explorer_api():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    calls = []

    class FakeCostExplorerClient:
        def get_cost_and_usage_with_resources(self, **kwargs):
            calls.append(("with_resources", kwargs))
            return {
                "ResultsByTime": [
                    {
                        "Groups": [
                            {
                                "Keys": ["i-abc123"],
                                "Metrics": {
                                    "UnblendedCost": {"Amount": "12.34"}
                                },
                            }
                        ]
                    }
                ]
            }

        def get_cost_and_usage(self, **kwargs):
            calls.append(("standard", kwargs))
            return {"ResultsByTime": []}

    scanner._get_client = lambda service, _region: FakeCostExplorerClient()

    costs = asyncio.run(scanner._fetch_daily_resource_costs())

    assert costs["i-abc123"] == 12.34
    assert calls[0][0] == "with_resources"
    assert calls[0][1]["Filter"] == {
        "Dimensions": {
            "Key": "SERVICE",
            "Values": ["Amazon Elastic Compute Cloud - Compute"],
        }
    }
    start = date.fromisoformat(calls[0][1]["TimePeriod"]["Start"])
    end = date.fromisoformat(calls[0][1]["TimePeriod"]["End"])
    assert (end - start).days <= 14
    assert calls[0][1]["Granularity"] == "DAILY"
    assert calls[0][1]["GroupBy"] == [{"Type": "DIMENSION", "Key": "RESOURCE_ID"}]


def test_aws_resource_cost_lookup_marks_resource_granularity_opt_in_gap():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    calls = []

    class FakeCostExplorerClient:
        def get_cost_and_usage_with_resources(self, **kwargs):
            calls.append(("with_resources", kwargs))
            raise ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": (
                            "Resource-level data granularity is an opt-in only feature. "
                            "Enable this feature from the PAYER account Cost Explorer Settings page."
                        ),
                    }
                },
                "GetCostAndUsageWithResources",
            )

        def get_cost_and_usage(self, **kwargs):
            calls.append(("standard", kwargs))
            return {"ResultsByTime": []}

    scanner._get_client = lambda service, _region: FakeCostExplorerClient()

    costs = asyncio.run(scanner._fetch_daily_resource_costs())

    assert costs == {}
    assert calls[0][0] == "with_resources"
    assert calls[1][0] == "standard"
    assert scanner.resource_cost_status == "resource_level_granularity_not_enabled"
    assert "resource-level data granularity" in scanner.resource_cost_message

    rows = scanner.to_db_resources(
        [
            AWSScannedResource(
                resource_name="web-1",
                service_type="AWS EC2 Instance",
                cost=0.0,
                status="Active",
                region="us-east-1",
                region_compliance="compliant",
                metadata={"instance_id": "i-abc123"},
            )
        ],
        "user-1",
        "integration-1",
    )
    assert rows[0]["metadata"]["resource_cost_status"] == "resource_level_granularity_not_enabled"
    assert rows[0]["metadata"]["pricing_note"] == scanner.resource_cost_message


def test_aws_cost_metric_prefers_positive_unblended_when_net_is_credit_adjusted_zero():
    metrics = {
        "NetAmortizedCost": {"Amount": "-0.000000005"},
        "AmortizedCost": {"Amount": "0"},
        "UnblendedCost": {"Amount": "1.17"},
    }

    assert AWSScanner._extract_cost_metric(metrics) == 1.17


def test_aws_cost_metric_keeps_positive_net_amortized_precedence():
    metrics = {
        "NetAmortizedCost": {"Amount": "4.50"},
        "AmortizedCost": {"Amount": "7.25"},
        "UnblendedCost": {"Amount": "9.00"},
    }

    assert AWSScanner._extract_cost_metric(metrics) == 4.5


def test_aws_cost_metric_returns_zero_when_all_metrics_are_zero():
    metrics = {
        "NetAmortizedCost": {"Amount": "0"},
        "AmortizedCost": {"Amount": "0"},
        "UnblendedCost": {"Amount": "0"},
    }

    assert AWSScanner._extract_cost_metric(metrics) == 0.0


def test_aws_gross_usage_filter_excludes_credit_and_refund_records():
    assert AWSScanner._gross_usage_cost_filter() == {
        "Not": {
            "Dimensions": {
                "Key": "RECORD_TYPE",
                "Values": ["Credit", "Refund"],
            }
        }
    }


def test_aws_monthly_cost_uses_mtd_actuals_without_forecast():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    calls = []

    class FakeCostExplorerClient:
        def get_cost_and_usage(self, **kwargs):
            calls.append(("cost", kwargs))
            return {
                "ResultsByTime": [
                    {
                        "Total": {
                            "NetAmortizedCost": {"Amount": "-0.000000005"},
                            "AmortizedCost": {"Amount": "0"},
                            "UnblendedCost": {"Amount": "1.17"},
                        }
                    }
                ]
            }

        def get_cost_forecast(self, **kwargs):
            calls.append(("forecast", kwargs))
            raise AssertionError("dashboard MTD actuals must not call forecast")

    scanner._get_client = lambda service, _region: FakeCostExplorerClient()

    assert asyncio.run(scanner._get_monthly_cost()) == 1.17
    assert len(calls) == 1
    assert calls[0][0] == "cost"
    assert calls[0][1]["Granularity"] == "MONTHLY"
    assert calls[0][1]["Metrics"] == ["NetAmortizedCost", "AmortizedCost", "UnblendedCost"]
    assert calls[0][1]["Filter"] == AWSScanner._gross_usage_cost_filter()
    start = date.fromisoformat(calls[0][1]["TimePeriod"]["Start"])
    end = date.fromisoformat(calls[0][1]["TimePeriod"]["End"])
    assert start.day == 1
    assert end > start


def test_gcp_apply_real_costs_overrides_by_global_name():
    scanner = _make_gcp_scanner()
    global_name = "//compute.googleapis.com/projects/test-project/zones/us-central1-a/instances/web-1"
    resources = [
        GCPScannedResource(
            resource_name="web-1",
            service_type="GCP Compute Instance",
            cost=22.0,
            status="Zombie",
            region="us-central1-a",
            region_compliance="compliant",
            cloud_resource_id="gcp-instance-test-project-web-1-us-central1-a",
            metadata={"global_name": global_name},
        )
    ]

    updated = scanner._apply_real_costs(resources, {global_name: 88.1})

    assert updated == 1
    assert resources[0].cost == 88.1
    assert resources[0].metadata["cost_source"] == "actual"
    assert resources[0].metadata["cost_lookup_key"] == global_name


def test_gcp_billing_export_falls_back_to_service_totals_when_resource_fields_missing():
    scanner = _make_gcp_scanner(
        billing_export_table="resources-test-489719.cloud_billing_export.gcp_billing_export_v1_01E5EC_FE159F_963C53"
    )
    queries = []

    class FakeJob:
        def __init__(self, rows=None, error=None):
            self.rows = rows or []
            self.error = error

        def result(self):
            if self.error:
                raise self.error
            return self.rows

    class FakeBigQueryClient:
        def __init__(self, **_kwargs):
            pass

        def query(self, query, job_config=None):
            queries.append(query)
            if "resource.global_name" in query:
                return FakeJob(error=RuntimeError("Unrecognized name: resource at [3:23]"))
            return FakeJob(
                rows=[
                    SimpleNamespace(
                        spend_date=date(2026, 4, 1),
                        service_name="Compute Engine",
                        net_cost=8.25,
                    ),
                    SimpleNamespace(
                        spend_date=date(2026, 4, 1),
                        service_name="Cloud Storage",
                        net_cost=1.75,
                    ),
                ]
            )

    with patch("google.cloud.bigquery.Client", FakeBigQueryClient):
        cost_map, total, daily_totals, service_breakdown, currency = scanner._fetch_real_costs_from_billing_export()

    assert len(queries) == 2
    assert cost_map == {}
    assert total == 10.0
    assert daily_totals == [{"date": "2026-04-01", "amount": 10.0}]
    assert service_breakdown == {"Compute Engine": 8.25, "Cloud Storage": 1.75}
    assert currency == "INR"
    assert scanner.billing_export_resource_status == "detailed_resource_export_unavailable"
    assert "detailed billing export" in scanner.billing_export_resource_message


def test_gcp_billing_export_uses_daily_total_for_dashboard_spend():
    scanner = _make_gcp_scanner(
        billing_export_table="resources-test-489719.cloud_billing_export.gcp_billing_export_resource_v1_01E5EC_FE159F_963C53"
    )
    queries = []

    class FakeJob:
        def __init__(self, rows):
            self.rows = rows

        def result(self):
            return self.rows

    class FakeBigQueryClient:
        def __init__(self, **_kwargs):
            pass

        def query(self, query, job_config=None):
            queries.append(query)
            if "resource.global_name" in query:
                return FakeJob(
                    rows=[
                        SimpleNamespace(
                            global_name="//compute.googleapis.com/projects/test-project/zones/us-central1-a/instances/vm-1",
                            resource_name="vm-1",
                            service_name="Compute Engine",
                            sku_name="N1 Instance Core running in Americas",
                            billing_location="us-central1-a",
                            currency="INR",
                            net_cost=20.0,
                        )
                    ]
                )
            return FakeJob(
                rows=[
                        SimpleNamespace(
                            spend_date=date(2026, 4, 1),
                            service_name="Compute Engine",
                            currency="INR",
                            net_cost=12.5,
                        )
                    ]
                )

    with patch("google.cloud.bigquery.Client", FakeBigQueryClient):
        cost_map, total, daily_totals, service_breakdown, currency = scanner._fetch_real_costs_from_billing_export()

    assert total == 12.5
    assert cost_map["//compute.googleapis.com/projects/test-project/zones/us-central1-a/instances/vm-1"] == 20.0
    assert cost_map["gcp:compute_instance:us-central1-a:vm-1"] == 20.0
    assert cost_map["gcp:compute_instance:vm-1"] == 20.0
    assert "vm-1" not in cost_map
    assert daily_totals == [{"date": "2026-04-01", "amount": 12.5}]
    assert service_breakdown == {"Compute Engine": 12.5}
    assert currency == "INR"
    assert all("DATE_TRUNC(CURRENT_DATE(), MONTH)" in query for query in queries)
    assert all("TIMESTAMP_SUB" not in query for query in queries)
    assert all("UNNEST(credits)" not in query for query in queries)


def test_gcp_apply_real_costs_does_not_share_disk_cost_with_same_named_instance():
    scanner = _make_gcp_scanner()
    resources = [
        GCPScannedResource(
            resource_name="web-1",
            service_type="GCP Compute Instance",
            cost=99.0,
            status="Active",
            region="us-central1-a",
            region_compliance="compliant",
            cloud_resource_id="gcp-instance-test-project-web-1-us-central1-a",
            metadata={
                "global_name": "//compute.googleapis.com/projects/test-project/zones/us-central1-a/instances/web-1",
                "zone": "us-central1-a",
                "cost_source": "catalog_estimate",
            },
        ),
        GCPScannedResource(
            resource_name="web-1",
            service_type="GCP Persistent Disk",
            cost=0.0,
            status="Active",
            region="us-central1-a",
            region_compliance="compliant",
            cloud_resource_id="gcp-disk-test-project-web-1-us-central1-a",
            metadata={
                "global_name": "//compute.googleapis.com/projects/test-project/zones/us-central1-a/disks/web-1",
                "zone": "us-central1-a",
                "cost_source": "billing_unavailable",
            },
        ),
    ]
    cost_map = {
        "gcp:compute_instance:us-central1-a:web-1": 0.0,
        "gcp:persistent_disk:us-central1-a:web-1": 2.74,
    }

    updated = scanner._apply_real_costs(resources, cost_map)

    assert updated == 2
    assert resources[0].cost == 0.0
    assert resources[0].metadata["cost_source"] == "actual"
    assert resources[0].metadata["cost_lookup_key"] == "gcp:compute_instance:us-central1-a:web-1"
    assert resources[0].metadata["currency"] == "INR"
    assert resources[1].cost == 2.74
    assert resources[1].metadata["cost_lookup_key"] == "gcp:persistent_disk:us-central1-a:web-1"


def test_gcp_resource_cost_lookup_keys_use_composite_identity_before_display_name():
    scanner = _make_gcp_scanner()
    resource = GCPScannedResource(
        resource_name="web-1",
        service_type="GCP Persistent Disk",
        cost=0.0,
        status="Active",
        region="us-central1-a",
        region_compliance="compliant",
        cloud_resource_id="gcp-disk-test-project-web-1-us-central1-a",
        metadata={
            "global_name": "//compute.googleapis.com/projects/test-project/zones/us-central1-a/disks/web-1",
            "zone": "us-central1-a",
        },
    )

    keys = scanner._resource_cost_lookup_keys(resource)

    assert "gcp:persistent_disk:us-central1-a:web-1" in keys
    assert "name:web-1" in keys
    assert "web-1" not in keys


def test_gcp_resource_cost_lookup_keys_match_external_ip_address_before_display_name():
    scanner = _make_gcp_scanner()
    resource = GCPScannedResource(
        resource_name="cfo-static-ip",
        service_type="GCP External IP",
        cost=0.0,
        status="Zombie",
        region="us-central1",
        region_compliance="compliant",
        cloud_resource_id="gcp-ip-test-project-cfo-static-ip-us-central1",
        metadata={
            "address": "34.10.20.30",
            "region": "us-central1",
        },
    )

    keys = scanner._resource_cost_lookup_keys(resource)
    address_key = "gcp:external_ip:us-central1:34.10.20.30"

    assert address_key in keys
    assert "name:cfo-static-ip" in keys
    assert keys.index(address_key) < keys.index("name:cfo-static-ip")


def test_gcp_scan_marks_resources_when_only_service_level_actuals_are_available():
    scanner = GCPScanner.__new__(GCPScanner)
    scanner.executor = None
    scanner.billing_export_table = "project.dataset.standard_export"
    scanner.billing_export_resource_status = "detailed_resource_export_unavailable"
    scanner.billing_export_resource_message = "Detailed export required for per-resource cost."
    scanner._fetch_real_costs_from_billing_export = lambda: (
        {},
        10.0,
        [{"date": "2026-04-01", "amount": 10.0}],
        {"Compute Engine": 10.0},
        "INR",
    )
    scanner._apply_real_costs = lambda _resources, _cost_map, _currency="INR": 0

    def make_resource(name: str) -> GCPScannedResource:
        return GCPScannedResource(
            resource_name=name,
            service_type="GCP Test Resource",
            cost=0.0,
            status="Active",
            region="global",
            region_compliance="compliant",
            cloud_resource_id=name,
            metadata={"global_name": name},
        )

    async def scan_instances():
        return [make_resource("vm-1")], [], 0.0, 1, 72.0

    async def scan_empty_with_existing(_existing_ids):
        return [], [], 0.0

    async def scan_empty_resources(_existing_ids):
        return []

    scanner._scan_instances = scan_instances
    scanner._scan_disks = scan_empty_with_existing
    scanner._scan_static_ips = scan_empty_with_existing
    scanner._scan_snapshots = scan_empty_resources
    scanner._scan_sql = scan_empty_with_existing
    scanner._scan_gke = scan_empty_resources
    scanner._scan_cloud_run = scan_empty_with_existing
    scanner._scan_cloud_functions = scan_empty_resources
    scanner._scan_generic_resources = scan_empty_resources

    result = asyncio.run(scanner.scan())

    assert result.total_spend == 10.0
    assert result.currency == "INR"
    assert result.daily_totals == [{"date": "2026-04-01", "amount": 10.0}]
    assert result.resources[0].cost == 0.0
    assert result.resources[0].metadata["cost_source"] == "billing_unavailable"
    assert result.resources[0].metadata["resource_cost_status"] == "detailed_resource_export_unavailable"
    assert result.resources[0].metadata["pricing_note"] == "Detailed export required for per-resource cost."


def test_gcp_generic_inventory_skips_existing_global_name_identity():
    scanner = _make_gcp_scanner()
    global_name = "//custom.googleapis.com/projects/test-project/locations/us-central1/widgets/web-1"
    existing_ids = set()
    scanner._remember_resource_ids(
        existing_ids,
        GCPScannedResource(
            resource_name="web-1",
            service_type="GCP Custom Widget",
            cost=0.0,
            status="Active",
            region="us-central1",
            region_compliance="compliant",
            cloud_resource_id="gcp-widget-test-project-web-1",
            metadata={"global_name": global_name},
        ),
    )

    request = object()
    scanner.asset_client = SimpleNamespace(
        searchAllResources=lambda **_kwargs: request,
        searchAllResources_next=lambda **_kwargs: None,
    )
    scanner._gcp_execute = lambda _operation_name, _request: {
        "results": [
            {
                "assetType": "custom.googleapis.com/Widget",
                "displayName": "web-1",
                "name": global_name,
                "location": "us-central1",
            }
        ]
    }

    resources = asyncio.run(scanner._scan_generic_resources(existing_ids))

    assert scanner._normalize_lookup_key(global_name) in existing_ids
    assert resources == []


def test_gcp_generic_inventory_uses_cloud_asset_v1_resource():
    scanner = _make_gcp_scanner()
    request = object()
    global_name = "//custom.googleapis.com/projects/test-project/locations/us-central1/widgets/web-2"
    asset_resource = SimpleNamespace(
        searchAllResources=lambda **_kwargs: request,
        searchAllResources_next=lambda **_kwargs: None,
    )
    scanner.asset_client = SimpleNamespace(v1=lambda: asset_resource)
    scanner._gcp_execute = lambda _operation_name, _request: {
        "results": [
            {
                "assetType": "custom.googleapis.com/Widget",
                "displayName": "web-2",
                "name": global_name,
                "location": "us-central1",
            }
        ]
    }

    resources = asyncio.run(scanner._scan_generic_resources(set()))

    assert len(resources) == 1
    assert resources[0].cloud_resource_id == global_name
    assert resources[0].metadata["global_name"] == global_name


def test_gcp_scan_resource_count_matches_returned_inventory():
    scanner = GCPScanner.__new__(GCPScanner)
    scanner.executor = None
    scanner._fetch_real_costs_from_billing_export = lambda: ({}, 0.0, [], {}, "INR")
    scanner._apply_real_costs = lambda _resources, _cost_map, _currency="INR": 0

    def make_resource(name: str) -> GCPScannedResource:
        return GCPScannedResource(
            resource_name=name,
            service_type="GCP Test Resource",
            cost=0.0,
            status="Active",
            region="global",
            region_compliance="compliant",
            cloud_resource_id=name,
            metadata={"global_name": name, "cost_source": "billing_unavailable"},
        )

    async def scan_instances():
        return [make_resource("vm-1")], [], 0.0, 1, 72.0

    async def scan_disks(_existing_ids):
        return [make_resource("disk-1")], [], 0.0

    async def scan_static_ips(_existing_ids):
        return [], [], 0.0

    async def scan_snapshots(_existing_ids):
        return []

    async def scan_sql(_existing_ids):
        return [], [], 0.0

    async def scan_gke(_existing_ids):
        return [make_resource("gke-1")]

    async def scan_cloud_run(_existing_ids):
        return [make_resource("run-1")], [], 0.0

    async def scan_cloud_functions(_existing_ids):
        return []

    async def scan_generic_resources(_existing_ids):
        return [make_resource("generic-1")]

    scanner._scan_instances = scan_instances
    scanner._scan_disks = scan_disks
    scanner._scan_static_ips = scan_static_ips
    scanner._scan_snapshots = scan_snapshots
    scanner._scan_sql = scan_sql
    scanner._scan_gke = scan_gke
    scanner._scan_cloud_run = scan_cloud_run
    scanner._scan_cloud_functions = scan_cloud_functions
    scanner._scan_generic_resources = scan_generic_resources

    result = asyncio.run(scanner.scan())

    assert len(result.resources) == 5
    assert result.active_resources_count == 5


def test_dashboard_resource_count_excludes_no_direct_charge_inventory():
    from app.api.routes import _count_dashboard_resources

    rows = [
        {
            "service_type": "GCP Compute Instance",
            "cost": 0.0,
            "metadata": {"cost_source": "billing_unavailable"},
        },
        {
            "service_type": "GCP Service",
            "cost": 0.0,
            "metadata": {"cost_source": "no_direct_charge"},
        },
        {
            "service_type": "AWS IAM Role",
            "cost": 0.0,
            "metadata": {"cost_source": "no_direct_charge"},
        },
        {
            "service_type": "GCP Firewall",
            "cost": 0.0,
            "metadata": {"cost_source": "no_direct_charge"},
        },
        {
            "service_type": "GCP External IP",
            "cost": 2.5,
            "metadata": {"cost_source": "actual"},
        },
        {
            "service_type": "GCP Bucket",
            "cost": 0.0,
            "metadata": {"cost_source": "billing_unavailable"},
        },
    ]

    assert _count_dashboard_resources(rows) == 3


def test_daily_spend_aggregation_converts_provider_rows_to_display_inr(monkeypatch):
    monkeypatch.setattr("app.core.finance.DEFAULT_USD_TO_INR_RATE", 83.0)
    rows = [
        {
            "spend_date": "2026-04-01",
            "amount": 2.0,
            "currency": "USD",
            "service_breakdown": {"Amazon EC2": 1.5},
        },
        {
            "spend_date": "2026-04-01",
            "amount": 100.0,
            "currency": "INR",
            "service_breakdown": {"Compute Engine": 100.0},
        },
    ]

    assert aggregate_daily_spend_rows(rows) == [
        {
            "spend_date": "2026-04-01",
            "amount": 266.0,
            "currency": "INR",
            "service_breakdown": {
                "Amazon EC2": 124.5,
                "Compute Engine": 100.0,
            },
        }
    ]


def test_gcp_billing_export_table_prefers_integration_value_over_env():
    with patch.dict(
        "os.environ",
        {"GCP_BILLING_EXPORT_TABLE": "env.project.dataset_table"},
        clear=False,
    ):
        scanner = _make_gcp_scanner()
        scanner_with_override = _make_gcp_scanner(
            billing_export_table="integration.project.dataset_table",
        )

    assert scanner.billing_export_table == "env.project.dataset_table"
    assert scanner_with_override.billing_export_table == "integration.project.dataset_table"


def test_gcp_billing_export_table_is_optional_with_empty_default():
    with patch.dict("os.environ", {"GCP_BILLING_EXPORT_TABLE": ""}, clear=False):
        scanner = _make_gcp_scanner()
    assert scanner.billing_export_table == ""


def test_azure_apply_real_cost_overrides_backfills_estimates():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    resource_id = "/subscriptions/sub-1/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1"
    scanner.findings = [
        {
            "cloud_resource_id": resource_id,
            "resource_name": "vm-1",
            "service_type": "Virtual Machine",
            "cost": 0.0,
            "status": "waste",
            "metadata": {"cost_source": "estimated"},
        }
    ]
    scanner._real_costs = {resource_id.lower(): {"actual_cost_30d": 64.2}}

    updated = scanner._apply_real_cost_overrides()

    assert updated == 1
    assert scanner.findings[0]["cost"] == 64.2
    assert scanner.findings[0]["metadata"]["cost_source"] == "actual"


def test_azure_resource_cost_does_not_fall_back_to_static_vm_price():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    scanner._real_costs = {}

    cost, is_real = scanner._get_resource_cost("Standard_B2s", "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm")

    assert cost == 0.0
    assert is_real is False


def test_azure_resource_cost_accepts_large_actual_cost_without_static_cap():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm"
    scanner._real_costs = {resource_id.lower(): {"actual_cost_30d": 812.34}}

    cost, is_real = scanner._get_resource_cost("Standard_B2s", resource_id)

    assert cost == 812.34
    assert is_real is True


def test_azure_subscription_cost_uses_mtd_period_and_usd_normalized_currency():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    scanner.credential = object()
    scanner.subscription_id = "sub"
    scanner._exchange_rates = {"INR": 0.012}
    calls = []

    class FakeResult:
        def __init__(self, rows, dimension):
            self.rows = rows
            self.columns = [SimpleNamespace(name=name) for name in ["Cost", "UsageDate", dimension, "Currency"]]
            self.next_link = None

    class FakeQuery:
        def usage(self, *, scope, parameters, **kwargs):
            calls.append((scope, parameters))
            dimension = parameters.dataset.grouping[0].name
            today = date.today().strftime("%Y%m%d")
            return FakeResult([[97.0, today, "Virtual Machines", "INR"]], dimension)

    class FakeCostManagementClient:
        def __init__(self, **_kwargs):
            self.query = FakeQuery()

        def close(self):
            return None

    with (
        patch("app.scanners.azure_billing.CostManagementClient", FakeCostManagementClient),
        patch("app.scanners.azure_billing.time.sleep"),
    ):
        summary = scanner._fetch_subscription_cost_by_service()

    assert summary["total"] == 1.16
    assert summary["currency"] == "USD"
    assert summary["original_currency"] == "INR"
    assert summary["period"] == "current_month_to_date"
    assert summary["daily_totals"][-1] == {
        "date": date.today().isoformat(), "amount": 1.164,
        "service_breakdown": {"Virtual Machines": 1.164},
    }
    assert summary["by_service"] == {"Virtual Machines": 1.164}
    assert calls[0][1].time_period.from_property.day == 1
    assert calls[1][1].time_period.from_property.day == 1


def test_azure_generic_resources_prefers_resource_graph_inventory_for_unseen_resources():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/db1"
    scanner.subscription_id = "sub"
    scanner.findings = []
    scanner.REQUIRED_TAGS = ["Owner"]
    scanner.ALLOWED_REGIONS = ["eastus"]
    scanner._real_costs = {resource_id.lower(): {"actual_cost_30d": 42.5}}
    scanner._fetch_resource_graph_resources = lambda: [
        {
            "id": resource_id,
            "name": "db1",
            "type": "microsoft.documentdb/databaseaccounts",
            "location": "eastus",
            "tags": {"Owner": "finops"},
            "resourceGroup": "rg",
            "subscriptionId": "sub",
        }
    ]

    def fail_arm_fallback():
        raise AssertionError("ARM fallback should not run when Resource Graph returns rows")

    scanner._fetch_arm_resources = fail_arm_fallback

    scanner.scan_generic_resources()

    assert len(scanner.findings) == 1
    finding = scanner.findings[0]
    assert finding["cloud_resource_id"] == resource_id
    assert finding["service_type"] == "microsoft.documentdb/databaseaccounts"
    assert finding["cost"] == 42.5
    assert finding["metadata"]["cost_source"] == "actual"
    assert finding["metadata"]["inventory_source"] == "azure-resource-graph"


def test_aws_to_db_resources_dedup_keeps_real_cost_over_placeholder():
    scanner = AWSScanner("ak", "sk", regions=["us-east-1"])
    resources = [
        AWSScannedResource(
            resource_name="vol-placeholder",
            service_type="AWS EBS Volume",
            cost=0.0,
            status="Zombie",
            region="us-east-1",
            region_compliance="compliant",
            metadata={"volume_id": "vol-123", "cost_source": "billing_unavailable"},
        ),
        AWSScannedResource(
            resource_name="vol-actual",
            service_type="AWS EBS Volume",
            cost=19.87,
            status="Zombie",
            region="us-east-1",
            region_compliance="compliant",
            metadata={"volume_id": "vol-123", "cost_source": "actual"},
        ),
    ]

    rows = scanner.to_db_resources(resources, "user-1", "integration-1")

    assert len(rows) == 1
    assert rows[0]["cloud_resource_id"] == "vol-123"
    assert rows[0]["cost"] == 19.87
    assert rows[0]["metadata"]["cost_source"] == "actual"


def test_ai_analysis_caps_savings_to_actual_resource_cost_only():
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    merged = [
        {
            "resource_name": "actual-ip",
            "service_type": "AWS Elastic IP",
            "cost": 4.25,
            "metadata": {"cost_source": "actual"},
        },
        {
            "resource_name": "unknown-ip",
            "service_type": "AWS Elastic IP",
            "cost": 0.0,
            "metadata": {"cost_source": "billing_unavailable"},
        },
    ]
    verdicts = [
        {"index": 0, "ai_status": "waste", "ai_savings": 99.0, "ai_action": "release ip"},
        {"index": 1, "ai_status": "waste", "ai_savings": 3.65, "ai_action": "release ip"},
    ]

    result = analyzer._build_final_analysis(
        merged=merged,
        verdicts=verdicts,
        conflict_rate=0.0,
        cost_governance={"verified_total_cost": 999.0, "verified_savings": 999.0},
    )

    assert result["total_spend"] == 4.25
    assert result["potential_savings"] == 4.25
    assert result["waste_distribution"] == [{"category_name": "Wasted Resources", "value": 4.25}]
    assert [item["potential_savings"] for item in result["recommendations"]] == [4.25, 0.0]


def test_ai_permanent_model_error_disables_ai_for_current_scan():
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    analyzer.client = object()
    analyzer.model = SimpleNamespace(
        generate_content_async=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(
                "404 NOT_FOUND. models/gemini-bad is not found for API version v1beta, "
                "or is not supported for generateContent."
            )
        )
    )

    verdicts = asyncio.run(analyzer._verify_batch([{"index": 0, "cost": 0}], "aws"))

    assert verdicts == []
    assert analyzer.client is None
    assert analyzer.model is None
