import asyncio
from types import SimpleNamespace

from app.db.mongo_client import MongoDBClient
from app.db.resource_contract import normalize_resource_row


def _client() -> MongoDBClient:
    return MongoDBClient("mongodb://localhost:27017/cloudfinops", "cloudfinops")


def test_resolve_upsert_filter_scopes_resources_by_user_and_integration() -> None:
    client = _client()

    filters = client._resolve_upsert_filter(
        "resources",
        {
            "id": "res-1",
            "user_id": "user-1",
            "integration_id": "int-1",
            "cloud_resource_id": "i-123",
        },
    )

    assert filters == {
        "user_id": "user-1",
        "integration_id": "int-1",
        "cloud_resource_id": "i-123",
    }


def test_resolve_upsert_filter_scopes_dashboard_spend_and_waste_rows_by_user() -> None:
    client = _client()

    dashboard_filters = client._resolve_upsert_filter(
        "dashboard_stats",
        {"id": "stats-1", "user_id": "user-1", "integration_id": "int-1"},
    )
    daily_spend_filters = client._resolve_upsert_filter(
        "daily_spend_history",
        {
            "id": "history-1",
            "user_id": "user-1",
            "integration_id": "int-1",
            "spend_date": "2026-04-24",
        },
    )
    waste_filters = client._resolve_upsert_filter(
        "waste_distribution",
        {
            "id": "waste-1",
            "user_id": "user-1",
            "integration_id": "int-1",
            "category_name": "Zombie Resources",
        },
    )

    assert dashboard_filters == {"user_id": "user-1", "integration_id": "int-1"}
    assert daily_spend_filters == {
        "user_id": "user-1",
        "integration_id": "int-1",
        "spend_date": "2026-04-24",
    }
    assert waste_filters == {
        "user_id": "user-1",
        "integration_id": "int-1",
        "category_name": "Zombie Resources",
    }


def test_resolve_upsert_filter_falls_back_to_row_id_when_user_scope_is_missing() -> None:
    client = _client()

    filters = client._resolve_upsert_filter(
        "resources",
        {
            "id": "res-1",
            "integration_id": "int-1",
            "cloud_resource_id": "i-123",
        },
    )

    assert filters == {"id": "res-1"}


def test_resolve_upsert_filter_dedupes_provider_catalog_rows_by_catalog_key() -> None:
    client = _client()

    filters = client._resolve_upsert_filter(
        "cloud_price_catalog",
        {
            "id": "price-1",
            "provider": "aws",
            "catalog_key": "aws:amazonec2:sku:rate:us-east-1:hrs:usd",
            "sku": "sku",
        },
    )

    assert filters == {
        "provider": "aws",
        "catalog_key": "aws:amazonec2:sku:rate:us-east-1:hrs:usd",
    }


def test_get_dashboard_stats_aggregates_portfolio_rows_when_integration_is_omitted() -> None:
    client = _client()

    async def fake_select(table, filters=None, columns="*"):
        assert table == "dashboard_stats"
        assert filters == {"user_id": "user-1"}
        return [
            {
                "user_id": "user-1",
                "integration_id": "aws-1",
                "total_spend": 100.25,
                "potential_savings": 10,
                "active_resources_count": 5,
                "ai_confidence_score": 80,
                "carbon_footprint_kg": 12.5,
                "cost_of_inaction_6mo": 60,
            },
            {
                "user_id": "user-1",
                "integration_id": "gcp-1",
                "total_spend": "50.75",
                "potential_savings": "5.5",
                "active_resources_count": "3",
                "ai_confidence_score": 90,
                "carbon_footprint_kg": "7.5",
                "cost_of_inaction_6mo": "33",
            },
        ]

    client.select = fake_select

    stats = asyncio.run(client.get_dashboard_stats("user-1"))

    assert stats == {
        "user_id": "user-1",
        "total_spend": 151.0,
        "potential_savings": 15.5,
        "active_resources_count": 8,
        "ai_confidence_score": 85,
        "carbon_footprint_kg": 20.0,
        "cost_of_inaction_6mo": 93.0,
    }


def test_normalize_resource_row_preserves_scan_batch_and_canonicalizes_provider_ids() -> None:
    aws_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "aws",
            "cloud_resource_id": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            "resource_name": "demo",
            "service_type": "AWS EC2 Instance",
            "scan_batch_id": "batch-1",
            "metadata": {"resource_id": "i-123", "cost_source": "billing_unavailable"},
        }
    )
    azure_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "azure",
            "cloud_resource_id": "/subscriptions/SUB/resourceGroups/RG/providers/Microsoft.Compute/virtualMachines/VM1",
            "resource_name": "VM1",
            "service_type": "Virtual Machine",
        }
    )
    gcp_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "//compute.googleapis.com/projects/proj-1/zones/us-central1-a/instances/vm-1",
            "resource_name": "vm-1",
            "service_type": "Compute Engine VM",
        }
    )

    assert aws_row["cloud_resource_id"] == "i-123"
    assert aws_row["scan_batch_id"] == "batch-1"
    assert (
        azure_row["cloud_resource_id"]
        == "/subscriptions/sub/resourcegroups/rg/providers/microsoft.compute/virtualmachines/vm1"
    )
    assert gcp_row["cloud_resource_id"] == "gcp-instance-proj-1-vm-1-us-central1-a"


def test_normalize_resource_row_marks_control_plane_resources_as_no_direct_charge() -> None:
    gcp_service_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "service-cloudapis",
            "resource_name": "cloudapis.googleapis.com",
            "service_type": "GCP Service",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )
    aws_network_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "aws",
            "cloud_resource_id": "subnet-123",
            "resource_name": "subnet-123",
            "service_type": "AWS Subnet",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )
    gcp_route_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "route-1",
            "resource_name": "default-route",
            "service_type": "GCP Route",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )
    gcp_entry_group_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "entrygroup-1",
            "resource_name": "@bigquery",
            "service_type": "GCP EntryGroup",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )
    gcp_log_bucket_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "logbucket-1",
            "resource_name": "_Default",
            "service_type": "GCP LogBucket",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )
    gcp_disk_row = normalize_resource_row(
        {
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "gcp",
            "cloud_resource_id": "disk-1",
            "resource_name": "disk-1",
            "service_type": "GCP Persistent Disk",
            "cost": 0,
            "metadata": {"cost_source": "billing_unavailable"},
        }
    )

    assert gcp_service_row["metadata"]["cost_source"] == "no_direct_charge"
    assert aws_network_row["metadata"]["cost_source"] == "no_direct_charge"
    assert gcp_route_row["metadata"]["cost_source"] == "no_direct_charge"
    assert gcp_entry_group_row["metadata"]["cost_source"] == "no_direct_charge"
    assert gcp_log_bucket_row["metadata"]["cost_source"] == "no_direct_charge"
    assert gcp_disk_row["metadata"]["cost_source"] == "billing_unavailable"


def test_bulk_upsert_resources_canonicalizes_duplicate_batch_rows_and_keeps_actual_cost() -> None:
    client = _client()
    operations = []
    dedupe_scopes = []

    class FakeCollection:
        async def bulk_write(self, batch_operations, ordered=False):
            operations.extend(batch_operations)
            return SimpleNamespace()

    async def fake_collection(table):
        assert table == "resources"
        return FakeCollection()

    async def fake_dedupe(user_id, integration_id):
        dedupe_scopes.append((user_id, integration_id))
        return 0

    client._collection = fake_collection
    client.dedupe_resources_for_integration = fake_dedupe

    inserted = asyncio.run(
        client.bulk_upsert_resources(
            [
                {
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "aws",
                    "cloud_resource_id": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                    "resource_name": "placeholder",
                    "service_type": "AWS EC2 Instance",
                    "cost": 0,
                    "scan_batch_id": "batch-1",
                    "metadata": {"resource_id": "i-123", "cost_source": "billing_unavailable"},
                },
                {
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "aws",
                    "cloud_resource_id": "i-123",
                    "resource_name": "actual",
                    "service_type": "AWS EC2 Instance",
                    "cost": 14.25,
                    "scan_batch_id": "batch-1",
                    "metadata": {"instance_id": "i-123", "cost_source": "actual"},
                },
            ]
        )
    )

    assert inserted == 1
    assert len(operations) == 1
    operation = operations[0]
    assert operation._filter == {
        "user_id": "user-1",
        "integration_id": "int-1",
        "cloud_resource_id": "i-123",
    }
    assert operation._doc["$set"]["cost"] == 14.25
    assert operation._doc["$set"]["resource_name"] == "actual"
    assert operation._doc["$set"]["scan_batch_id"] == "batch-1"
    assert dedupe_scopes == [("user-1", "int-1")]


def test_dedupe_resources_for_integration_removes_semantic_duplicates() -> None:
    client = _client()
    updates = []
    deletes = []

    documents = [
        {
            "id": "old",
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "aws",
            "cloud_resource_id": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            "resource_name": "old-placeholder",
            "service_type": "AWS EC2 Instance",
            "cost": 0,
            "scan_batch_id": "batch-old",
            "metadata": {"resource_id": "i-123", "cost_source": "billing_unavailable"},
        },
        {
            "id": "current",
            "user_id": "user-1",
            "integration_id": "int-1",
            "provider": "aws",
            "cloud_resource_id": "i-123",
            "resource_name": "current-actual",
            "service_type": "AWS EC2 Instance",
            "cost": 14.25,
            "scan_batch_id": "batch-new",
            "metadata": {"instance_id": "i-123", "cost_source": "actual"},
        },
    ]

    class FakeCursor:
        async def to_list(self, length=None):
            return list(documents)

    class FakeCollection:
        def find(self, filters):
            assert filters == {"user_id": "user-1", "integration_id": "int-1"}
            return FakeCursor()

        async def update_one(self, filters, update, upsert=False):
            updates.append((filters, update, upsert))
            return SimpleNamespace()

        async def delete_many(self, filters):
            deletes.append(filters)
            return SimpleNamespace(deleted_count=len(filters["id"]["$in"]))

    async def fake_collection(table):
        assert table == "resources"
        return FakeCollection()

    client._collection = fake_collection

    removed = asyncio.run(client.dedupe_resources_for_integration("user-1", "int-1"))

    assert removed == 1
    assert updates[0][0] == {"user_id": "user-1", "integration_id": "int-1", "id": "current"}
    assert updates[0][1]["$set"]["cloud_resource_id"] == "i-123"
    assert updates[0][1]["$set"]["cost"] == 14.25
    assert deletes == [
        {"user_id": "user-1", "integration_id": "int-1", "id": {"$in": ["old"]}}
    ]
