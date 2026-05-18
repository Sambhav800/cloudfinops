import asyncio
from copy import deepcopy
from types import SimpleNamespace

from app.api.routes import run_scan


async def _noop_async(*args, **kwargs):
    return None


class FakeBatchSwapDB:
    def __init__(self):
        self.operations = []
        self.bulk_upsert_calls = []
        self.delete_calls = []
        self.integration_updates = []
        self.dashboard_stats = []
        self.scan_history_completed = []
        self.daily_spend_history_calls = []
        self.resources = []

    async def create_scan_history(self, user_id, integration_id):
        self.operations.append(("create_scan_history", integration_id))
        return "scan-1"

    async def bulk_upsert_resources(self, resources, batch_size=50):
        copied = [deepcopy(resource) for resource in resources]
        self.operations.append(("bulk_upsert_resources", len(copied)))
        self.bulk_upsert_calls.append((copied, batch_size))
        return len(resources)

    async def delete_resources_for_integration(self, user_id, integration_id, exclude_batch_id=None):
        self.operations.append(("delete_resources_for_integration", user_id, integration_id, exclude_batch_id))
        self.delete_calls.append((user_id, integration_id, exclude_batch_id))
        return True

    async def upsert_dashboard_stats(self, data):
        self.dashboard_stats.append(deepcopy(data))
        return True

    async def upsert_waste_distribution(self, data):
        return True

    async def get_resources(self, user_id, integration_id=None):
        return list(self.resources)

    async def create_notifications(self, notifications):
        return True

    async def update(self, table, data, filters):
        return True

    async def update_integration(self, integration_id, user_id, data):
        self.integration_updates.append((integration_id, user_id, deepcopy(data)))
        return True

    async def complete_scan_history(self, **kwargs):
        self.scan_history_completed.append(deepcopy(kwargs))
        return True

    async def fail_scan_history(self, scan_id, error):
        raise AssertionError(f"scan should not fail during batch swap tests: {error}")

    async def save_daily_spend_history(self, **kwargs):
        self.daily_spend_history_calls.append(deepcopy(kwargs))
        return True


class FakeCanonicalizingBatchSwapDB(FakeBatchSwapDB):
    async def bulk_upsert_resources(self, resources, batch_size=50):
        count = await super().bulk_upsert_resources(resources, batch_size=batch_size)
        self.resources = [
            {
                "id": "persisted-1",
                "user_id": "user-1",
                "integration_id": "aws-integration",
                "cloud_resource_id": "canonical-shared",
                "resource_name": "canonical-resource",
            }
        ]
        return count


class FakeAIAnalyzer:
    async def verify_and_analyze(self, findings, provider="aws"):
        verified = []
        for finding in findings:
            enriched = deepcopy(finding)
            enriched["ai_verified"] = False
            verified.append(enriched)
        return {
            "verified_resources": verified,
            "recommendations": [],
            "waste_distribution": [],
            "governance_findings": [],
            "alerts": [],
            "governance_data": None,
            "potential_savings": 0,
            "ai_confidence_score": 75,
            "carbon_footprint_kg": 0,
            "conflict_rate": 0,
            "total_spend": sum(float(finding.get("cost", 0) or 0) for finding in findings),
        }


class FakeAWSScanner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def scan(self):
        return SimpleNamespace(
            resources=[
                {"id": "raw-1"},
                {"id": "raw-2"},
            ],
            total_spend=140.0,
            regions_scanned=1,
            access_denied_services=[],
            daily_totals=[
                {"date": "2026-04-20", "amount": 12.25},
                {"date": "2026-04-21", "amount": 14.75},
            ],
            service_breakdown={"Amazon Elastic Compute Cloud - Compute": 18.0, "Amazon S3": 9.0},
        )

    def to_db_resources(self, resources, user_id, integration_id):
        return [
            {
                "user_id": user_id,
                "integration_id": integration_id,
                "provider": "aws",
                "cloud_resource_id": "i-123",
                "resource_name": "web-1",
                "service_type": "ec2",
                "cost": 90.0,
                "status": "Active",
            },
            {
                "user_id": user_id,
                "integration_id": integration_id,
                "provider": "aws",
                "cloud_resource_id": "vol-456",
                "resource_name": "data-1",
                "service_type": "ebs",
                "cost": 50.0,
                "status": "Active",
            },
        ]


class FakeEmptyAWSScanner(FakeAWSScanner):
    async def scan(self):
        return SimpleNamespace(
            resources=[],
            total_spend=0.0,
            regions_scanned=0,
            access_denied_services=[],
            daily_totals=[],
            service_breakdown={},
        )


class FakeAzureWasteScanner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._scan_summary = {}

    def scan_all(self):
        return [
            {
                "provider": "azure",
                "cloud_resource_id": "vm-1",
                "resource_name": "vm-worker-eu-1",
                "service_type": "virtual-machine",
                "cost": 112.0,
                "status": "Active",
            },
            {
                "provider": "azure",
                "cloud_resource_id": "disk-2",
                "resource_name": "disk-worker-eu-1",
                "service_type": "managed-disk",
                "cost": 28.0,
                "status": "Active",
            },
        ]


def test_run_scan_inserts_new_aws_batch_before_deleting_old_resources(monkeypatch):
    db = FakeBatchSwapDB()

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {"access_key_id": "AKIA123", "secret_access_key": "secret"},
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AWSScanner", FakeAWSScanner)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.governance.generate_governance_policies", _noop_async)

    integration = {
        "id": "aws-integration",
        "provider": "aws",
        "name": "AWS Prod",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert len(db.bulk_upsert_calls) == 2
    first_batch, _ = db.bulk_upsert_calls[0]
    batch_id = first_batch[0]["scan_batch_id"]

    sequence = [entry[0] for entry in db.operations if entry[0] in {"bulk_upsert_resources", "delete_resources_for_integration"}]

    assert sequence[:2] == ["bulk_upsert_resources", "delete_resources_for_integration"]
    assert first_batch[0]["cloud_resource_id"] == "i-123"
    assert all(resource["scan_batch_id"] == batch_id for resource in first_batch)
    assert db.delete_calls == [("user-1", "aws-integration", batch_id)]
    assert db.integration_updates[0][2]["metadata"]["last_scan_batch_id"] == batch_id
    assert db.daily_spend_history_calls == [
        {
            "user_id": "user-1",
            "integration_id": "aws-integration",
            "daily_totals": [
                {"date": "2026-04-20", "amount": 12.25},
                {"date": "2026-04-21", "amount": 14.75},
            ],
            "service_breakdown": {
                "Amazon Elastic Compute Cloud - Compute": 18.0,
                "Amazon S3": 9.0,
            },
            "currency": "USD",
        }
    ]


def test_run_scan_applies_catalog_estimates_after_resource_writeback(monkeypatch):
    db = FakeBatchSwapDB()
    apply_calls = []

    async def fake_apply_catalog_estimates(db_arg, user_id, *, integration_id=None, limit=500):
        apply_calls.append((user_id, integration_id, limit, len(db_arg.bulk_upsert_calls)))
        return {"updated": 2, "skipped_actual": 0, "unmatched": 0, "processed": 2, "samples": []}

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {"access_key_id": "AKIA123", "secret_access_key": "secret"},
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AWSScanner", FakeAWSScanner)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.governance.generate_governance_policies", _noop_async)
    monkeypatch.setattr(
        "app.api.routes.pricing_catalog.apply_catalog_estimates",
        fake_apply_catalog_estimates,
    )

    integration = {
        "id": "aws-integration",
        "provider": "aws",
        "name": "AWS Prod",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert apply_calls == [("user-1", "aws-integration", 500, 2)]


def test_run_scan_stats_use_persisted_resource_count_after_db_canonicalization(monkeypatch):
    db = FakeCanonicalizingBatchSwapDB()

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {"access_key_id": "AKIA123", "secret_access_key": "secret"},
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AWSScanner", FakeAWSScanner)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.governance.generate_governance_policies", _noop_async)

    integration = {
        "id": "aws-integration",
        "provider": "aws",
        "name": "AWS Prod",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert db.dashboard_stats[-1]["active_resources_count"] == 1
    assert db.integration_updates[-1][2]["metadata"]["resources_found"] == 1
    assert db.scan_history_completed[-1]["total_resources"] == 1


def test_run_scan_inserts_new_azure_batch_before_deleting_old_resources(monkeypatch):
    db = FakeBatchSwapDB()

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
            "subscription_id": "sub",
        },
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.scanners.azure.AzureWasteScanner", FakeAzureWasteScanner)

    integration = {
        "id": "azure-integration",
        "provider": "azure",
        "name": "Azure Prod",
        "metadata": {"existing": "value"},
        "regions": ["westeurope"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert len(db.bulk_upsert_calls) == 1
    first_batch, _ = db.bulk_upsert_calls[0]
    batch_id = first_batch[0]["scan_batch_id"]
    sequence = [entry[0] for entry in db.operations if entry[0] in {"bulk_upsert_resources", "delete_resources_for_integration"}]

    assert sequence == ["bulk_upsert_resources", "delete_resources_for_integration"]
    assert all(resource["scan_batch_id"] == batch_id for resource in first_batch)
    assert db.delete_calls == [("user-1", "azure-integration", batch_id)]
    assert db.integration_updates[0][2]["metadata"]["last_scan_batch_id"] == batch_id


def test_run_scan_keeps_existing_inventory_when_no_new_common_resources_are_found(monkeypatch):
    db = FakeBatchSwapDB()

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {"access_key_id": "AKIA123", "secret_access_key": "secret"},
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AWSScanner", FakeEmptyAWSScanner)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.governance.generate_governance_policies", _noop_async)

    integration = {
        "id": "aws-empty",
        "provider": "aws",
        "name": "AWS Empty",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert db.bulk_upsert_calls == []
    assert db.delete_calls == []
    assert len(db.integration_updates) == 1
    assert db.integration_updates[0][2]["metadata"]["last_scan_batch_id"]
    assert db.daily_spend_history_calls == []


def test_run_scan_normalizes_daily_history_before_persisting(monkeypatch):
    class MessyDailyAWSScanner(FakeAWSScanner):
        async def scan(self):
            result = await super().scan()
            result.daily_totals = [
                {"date": "2026-04-22T10:15:00Z", "amount": "5.12345"},
                {"spend_date": "2026-04-21", "amount": "bad"},
                {"date": "2026-04-22", "amount": 99.0},
                {"amount": 1.0},
                "invalid",
            ]
            result.service_breakdown = {"EC2": "5.33333", "S3": 0, "Lambda": "bad"}
            return result

    db = FakeBatchSwapDB()

    monkeypatch.setattr(
        "app.api.routes.decrypt_integration_credentials",
        lambda integration: {"access_key_id": "AKIA123", "secret_access_key": "secret"},
    )
    monkeypatch.setattr("app.api.routes.send_scan_progress", _noop_async)
    monkeypatch.setattr("app.api.routes.send_scan_complete", _noop_async)
    monkeypatch.setattr("app.api.routes.AWSScanner", MessyDailyAWSScanner)
    monkeypatch.setattr("app.api.routes.AIAnalyzer", FakeAIAnalyzer)
    monkeypatch.setattr("app.governance.generate_governance_policies", _noop_async)

    integration = {
        "id": "aws-messy-history",
        "provider": "aws",
        "name": "AWS Messy History",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", db))

    assert db.daily_spend_history_calls[0]["daily_totals"] == [
        {"date": "2026-04-21", "amount": 0.0},
        {"date": "2026-04-22", "amount": 5.1235},
    ]
    assert db.daily_spend_history_calls[0]["service_breakdown"] == {"EC2": 5.3333}
