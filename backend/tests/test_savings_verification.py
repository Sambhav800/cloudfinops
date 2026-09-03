import asyncio
from datetime import datetime, timezone

from app.core.recommendations import RECOMMENDATION_LEDGER_COLLECTION
from app.core.savings_verification import (
    RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION,
    RESOURCE_COST_SNAPSHOT_COLLECTION,
    create_or_update_savings_verification,
    persist_resource_cost_snapshots,
    verify_implemented_recommendations_for_integration,
    verify_recommendation_savings,
)


class FakeSavingsVerificationDB:
    def __init__(self):
        self.collections = {
            RECOMMENDATION_LEDGER_COLLECTION: [
                {
                    "id": "rec-1",
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "azure",
                    "resource_id": "vm-1",
                    "cloud_resource_id": "vm-1",
                    "resource_name": "dev-vm-1",
                    "resource_type": "Azure VM",
                    "action": "terminate",
                    "state": "implemented",
                    "implemented_at": "2026-08-01T00:00:00+00:00",
                    "estimated_monthly_savings": 100,
                }
            ],
            RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION: [],
            RESOURCE_COST_SNAPSHOT_COLLECTION: [],
            "daily_spend_history": [],
        }

    async def select(self, table, filters=None):
        filters = filters or {}
        return [
            row
            for row in self.collections.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

    async def upsert(self, table, data):
        rows = data if isinstance(data, list) else [data]
        collection = self.collections.setdefault(table, [])
        results = []
        for row in rows:
            existing = next((item for item in collection if item.get("id") == row.get("id")), None)
            if existing:
                existing.update(row)
                results.append(existing)
            else:
                payload = dict(row)
                collection.append(payload)
                results.append(payload)
        return results

    async def update(self, table, data, filters):
        rows = await self.select(table, filters)
        for row in rows:
            row.update(data)
        return rows


def test_persist_resource_cost_snapshots_writes_scan_observations():
    db = FakeSavingsVerificationDB()

    written = asyncio.run(
        persist_resource_cost_snapshots(
            db=db,
            findings=[
                {
                    "cloud_resource_id": "vm-1",
                    "resource_name": "dev-vm-1",
                    "service_type": "Azure VM",
                    "region": "centralindia",
                    "cost": 120,
                    "status": "Active",
                    "metadata": {"cost_source": "actual", "currency": "INR"},
                }
            ],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
            observed_at="2026-07-25T00:00:00+00:00",
        )
    )

    assert written == 1
    snapshot = db.collections[RESOURCE_COST_SNAPSHOT_COLLECTION][0]
    assert snapshot["user_id"] == "user-1"
    assert snapshot["cloud_resource_id"] == "vm-1"
    assert snapshot["cost"] == 120


def test_create_or_update_savings_verification_starts_collecting_window():
    db = FakeSavingsVerificationDB()
    recommendation = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]

    verification = asyncio.run(
        create_or_update_savings_verification(
            db=db,
            user_id="user-1",
            recommendation=recommendation,
            now=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    )

    assert verification["status"] == "collecting_post_window"
    assert verification["estimated_monthly_savings"] == 100
    assert db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["verification_id"] == verification["id"]


def test_verify_recommendation_savings_uses_resource_snapshots_for_saved_result():
    db = FakeSavingsVerificationDB()
    db.collections[RESOURCE_COST_SNAPSHOT_COLLECTION] = [
        {
            "id": "snap-before",
            "user_id": "user-1",
            "integration_id": "int-1",
            "resource_id": "vm-1",
            "cloud_resource_id": "vm-1",
            "cost": 120,
            "observed_at": "2026-07-25T00:00:00+00:00",
        },
        {
            "id": "snap-after",
            "user_id": "user-1",
            "integration_id": "int-1",
            "resource_id": "vm-1",
            "cloud_resource_id": "vm-1",
            "cost": 10,
            "observed_at": "2026-08-10T00:00:00+00:00",
        },
    ]

    result = asyncio.run(
        verify_recommendation_savings(
            db=db,
            user_id="user-1",
            recommendation_id="rec-1",
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
    )

    assert result["status"] == "verified_saved"
    assert result["measurement_source"] == "resource_snapshot"
    assert result["realized_monthly_savings"] == 110
    assert db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["state"] == "verified_saved"


def test_verify_recommendation_savings_waits_for_post_window_edge_case():
    db = FakeSavingsVerificationDB()

    result = asyncio.run(
        verify_recommendation_savings(
            db=db,
            user_id="user-1",
            recommendation_id="rec-1",
            now=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )
    )

    assert result["status"] == "collecting_post_window"
    assert "Waiting" in result["explanation"]


def test_verify_recommendation_savings_marks_inconclusive_without_cost_data():
    db = FakeSavingsVerificationDB()

    result = asyncio.run(
        verify_recommendation_savings(
            db=db,
            user_id="user-1",
            recommendation_id="rec-1",
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
    )

    assert result["status"] == "inconclusive"
    assert result["measurement_source"] == "not_measured"


def test_verify_implemented_recommendations_for_integration_sweeps_after_scan():
    db = FakeSavingsVerificationDB()
    db.collections[RECOMMENDATION_LEDGER_COLLECTION].append({
        "id": "rec-ready",
        "user_id": "user-1",
        "integration_id": "int-1",
        "provider": "azure",
        "resource_id": "vm-ready",
        "cloud_resource_id": "vm-ready",
        "state": "ready_for_review",
        "implemented_at": "2026-08-01T00:00:00+00:00",
        "estimated_monthly_savings": 100,
    })
    db.collections[RESOURCE_COST_SNAPSHOT_COLLECTION] = [
        {
            "id": "snap-before",
            "user_id": "user-1",
            "integration_id": "int-1",
            "resource_id": "vm-1",
            "cloud_resource_id": "vm-1",
            "cost": 120,
            "observed_at": "2026-07-25T00:00:00+00:00",
        },
        {
            "id": "snap-after",
            "user_id": "user-1",
            "integration_id": "int-1",
            "resource_id": "vm-1",
            "cloud_resource_id": "vm-1",
            "cost": 10,
            "observed_at": "2026-08-10T00:00:00+00:00",
        },
    ]

    summary = asyncio.run(
        verify_implemented_recommendations_for_integration(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
    )

    assert summary["checked"] == 1
    assert summary["verified_saved"] == 1
    assert db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["state"] == "verified_saved"
    ready = next(row for row in db.collections[RECOMMENDATION_LEDGER_COLLECTION] if row["id"] == "rec-ready")
    assert ready["state"] == "ready_for_review"
