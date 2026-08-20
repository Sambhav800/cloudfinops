import asyncio

from app.core.provider_recommendations import ingest_azure_advisor_recommendations, refresh_azure_advisor_recommendations
from app.core.recommendations import (
    PROVIDER_RECOMMENDATION_COLLECTION,
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
    RECOMMENDATION_STATE_EVENTS_COLLECTION,
)


class FakeProviderRecommendationDB:
    def __init__(self):
        self.collections = {
            PROVIDER_RECOMMENDATION_COLLECTION: [],
            RECOMMENDATION_LEDGER_COLLECTION: [
                {
                    "id": "rec-existing",
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "azure",
                    "resource_id": "vm-prod-1",
                    "cloud_resource_id": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-prod-1",
                    "resource_name": "vm-prod-1",
                    "state": "ready_for_review",
                    "trust_score": 82,
                    "provider_agreement_status": "unknown",
                    "source_systems": ["cloudfinops_deterministic_optimizer"],
                }
            ],
            RECOMMENDATION_EVIDENCE_COLLECTION: [],
            RECOMMENDATION_STATE_EVENTS_COLLECTION: [],
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

    async def delete(self, table, filters):
        collection = self.collections.setdefault(table, [])
        self.collections[table] = [
            row
            for row in collection
            if not all(row.get(key) == value for key, value in filters.items())
        ]
        return True

    async def insert(self, table, data):
        rows = data if isinstance(data, list) else [data]
        payload = [dict(row) for row in rows]
        self.collections.setdefault(table, []).extend(payload)
        return payload


def _advisor_row(resource_name="vm-prod-1"):
    return {
        "id": f"/subscriptions/sub/providers/Microsoft.Advisor/recommendations/advisor-{resource_name}",
        "name": f"advisor-{resource_name}",
        "type": "Microsoft.Advisor/recommendations",
        "properties": {
            "category": "Cost",
            "impact": "High",
            "impactedField": "Microsoft.Compute/virtualMachines",
            "impactedValue": resource_name,
            "resourceMetadata": {
                "resourceId": f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/{resource_name}",
                "resourceName": resource_name,
                "resourceType": "Microsoft.Compute/virtualMachines",
                "region": "centralindia",
            },
            "shortDescription": {
                "problem": "Virtual machine is underutilized",
                "solution": "Rightsize or shutdown the virtual machine",
            },
            "extendedProperties": {
                "annualSavingsAmount": "1200",
                "savingsCurrency": "INR",
            },
        },
    }


def test_ingest_azure_advisor_marks_existing_ledger_agreement():
    db = FakeProviderRecommendationDB()

    result = asyncio.run(
        ingest_azure_advisor_recommendations(
            db=db,
            user_id="user-1",
            integration={"id": "int-1"},
            credentials={},
            advisor_rows=[_advisor_row()],
        )
    )

    assert result["matched"] == 1
    assert result["provider_only_created"] == 0
    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert ledger["provider_agreement_status"] == "agrees"
    assert "azure_advisor" in ledger["source_systems"]
    assert ledger["trust_score"] == 92
    assert db.collections[PROVIDER_RECOMMENDATION_COLLECTION][0]["source_system"] == "azure_advisor"
    assert db.collections[RECOMMENDATION_EVIDENCE_COLLECTION][0]["evidence_kind"] == "provider_native_recommendation"


def test_ingest_azure_advisor_creates_provider_only_ledger_record():
    db = FakeProviderRecommendationDB()

    result = asyncio.run(
        ingest_azure_advisor_recommendations(
            db=db,
            user_id="user-1",
            integration={"id": "int-1"},
            credentials={},
            advisor_rows=[_advisor_row("vm-provider-only")],
        )
    )

    provider_only = [
        row
        for row in db.collections[RECOMMENDATION_LEDGER_COLLECTION]
        if row.get("provider_agreement_status") == "provider_only"
    ]
    assert result["provider_only_created"] == 1
    assert len(provider_only) == 1
    assert provider_only[0]["resource_name"] == "vm-provider-only"
    assert provider_only[0]["savings_currency"] == "INR"
    assert provider_only[0]["estimated_monthly_savings"] == 100
    assert provider_only[0]["claimable_monthly_savings"] == 100
    assert provider_only[0]["savings_estimate_status"] == "provider_estimate"
    assert provider_only[0]["quality_status"] == "provider_only"
    assert provider_only[0]["pricing_basis"] == "live_api"
    assert provider_only[0]["confidence"] == 0
    assert provider_only[0]["trust_score"] <= 69
    assert db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION][0]["to_state"] == "provider_checked"
    assert db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION][0]["actor_id"] == "azure_advisor"


def test_ingest_azure_advisor_marks_existing_rows_not_found_when_provider_has_no_match():
    db = FakeProviderRecommendationDB()

    result = asyncio.run(
        ingest_azure_advisor_recommendations(
            db=db,
            user_id="user-1",
            integration={"id": "int-1"},
            credentials={},
            advisor_rows=[],
        )
    )

    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert result["stored"] == 0
    assert result["not_found_marked"] == 1
    assert ledger["provider_agreement_status"] == "not_found"


def test_ingest_azure_advisor_force_refresh_records_refresh_status(monkeypatch):
    db = FakeProviderRecommendationDB()
    called = {}

    def fake_refresh(credentials):
        called["subscription_id"] = credentials["subscription_id"]
        return {
            "refresh_status": "completed",
            "refreshed": True,
            "refresh_message": "Azure Advisor recommendations were refreshed",
        }

    monkeypatch.setattr("app.core.provider_recommendations.refresh_azure_advisor_recommendations", fake_refresh)

    result = asyncio.run(
        ingest_azure_advisor_recommendations(
            db=db,
            user_id="user-1",
            integration={"id": "int-1"},
            credentials={"subscription_id": "sub"},
            advisor_rows=[],
            force_refresh=True,
        )
    )

    assert called["subscription_id"] == "sub"
    assert result["status"] == "ok"
    assert result["refresh_status"] == "completed"
    assert result["refreshed"] is True


def test_refresh_azure_advisor_recommendations_polls_location_until_complete(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "app.core.provider_recommendations._get_azure_management_token",
        lambda credentials: ("token", credentials["subscription_id"]),
    )
    monkeypatch.setattr("app.core.provider_recommendations.time.sleep", lambda seconds: None)

    def fake_request(*, url, token, method):
        calls.append((method, url, token))
        if method == "POST":
            return 202, {"Location": "/subscriptions/sub/providers/Microsoft.Advisor/operationResults/op-1"}, {}
        return 204, {}, {}

    monkeypatch.setattr("app.core.provider_recommendations._azure_advisor_request", fake_request)

    result = refresh_azure_advisor_recommendations({"subscription_id": "sub"})

    assert result["refresh_status"] == "completed"
    assert result["refreshed"] is True
    assert calls[0][0] == "POST"
    assert calls[1][0] == "GET"
    assert "api-version=2025-01-01" in calls[1][1]


def test_refresh_azure_advisor_recommendations_accepts_arm_succeeded_payload(monkeypatch):
    monkeypatch.setattr(
        "app.core.provider_recommendations._get_azure_management_token",
        lambda credentials: ("token", credentials["subscription_id"]),
    )
    monkeypatch.setattr("app.core.provider_recommendations.time.sleep", lambda seconds: None)

    def fake_request(*, url, token, method):
        if method == "POST":
            return 202, {"Azure-AsyncOperation": "https://management.azure.com/status/op-1"}, {}
        return 200, {}, {"status": "Succeeded"}

    monkeypatch.setattr("app.core.provider_recommendations._azure_advisor_request", fake_request)

    result = refresh_azure_advisor_recommendations({"subscription_id": "sub"})

    assert result["refresh_status"] == "completed"
    assert result["refreshed"] is True
