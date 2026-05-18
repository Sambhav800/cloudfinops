from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeTotalBillDB:
    def __init__(self):
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        self.integrations = [
            {
                "id": "aws-1",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Prod AWS",
                "status": "active",
                "last_scan": "2026-03-22T06:00:00+00:00",
                "account_identifier": "111111111111",
            },
            {
                "id": "aws-2",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Analytics AWS",
                "status": "active",
                "last_scan": "2026-03-22T09:00:00+00:00",
                "account_identifier": "222222222222",
            },
            {
                "id": "gcp-1",
                "user_id": "user-1",
                "provider": "gcp",
                "name": "GCP Prod",
                "status": "active",
                "last_scan": "2026-03-21T08:00:00+00:00",
                "account_identifier": "project-123",
            },
            {
                "id": "azure-1",
                "user_id": "user-1",
                "provider": "azure",
                "name": "Azure Old",
                "status": "inactive",
                "last_scan": "2026-03-20T08:00:00+00:00",
            },
        ]
        self.stats = {
            "aws-1": {
                "total_spend": 100.0,
                "potential_savings": 10.0,
                "active_resources_count": 5,
            },
            "aws-2": {
                "total_spend": 200.0,
                "potential_savings": 20.0,
                "active_resources_count": 10,
            },
            "gcp-1": {
                "total_spend": 50.0,
                "potential_savings": 5.0,
                "active_resources_count": 3,
            },
            "azure-1": {
                "total_spend": 999.0,
                "potential_savings": 99.0,
                "active_resources_count": 99,
            },
        }
        self.resources = [
            {"integration_id": "aws-1", "provider": "aws", "service_type": "ec2", "cost": 70.0},
            {"integration_id": "aws-1", "provider": "aws", "service_type": "rds", "cost": 30.0},
            {"integration_id": "aws-2", "provider": "aws", "service_type": "s3", "cost": 20.0},
            {"integration_id": "aws-2", "provider": "aws", "service_type": "lambda", "cost": 10.0},
            {"integration_id": "gcp-1", "provider": "gcp", "service_type": "compute engine", "cost": 40.0},
            {"integration_id": "gcp-1", "provider": "gcp", "service_type": "cloud sql", "cost": 10.0},
            {"integration_id": "azure-1", "provider": "azure", "service_type": "vm", "cost": 500.0},
        ]
        self.history = {
            "aws-1": [
                {"spend_date": yesterday.isoformat(), "amount": 5.0, "currency": "USD"},
                {"spend_date": today.isoformat(), "amount": 8.0, "currency": "USD"},
            ],
            "aws-2": [
                {"spend_date": today.isoformat(), "amount": 12.0, "currency": "USD"},
            ],
            "gcp-1": [
                {"spend_date": today.isoformat(), "amount": 3.0, "currency": "INR"},
            ],
            "azure-1": [
                {"spend_date": today.isoformat(), "amount": 999.0, "currency": "USD"},
            ],
        }

    async def get_user_integrations(self, user_id):
        return [integration for integration in self.integrations if integration.get("user_id") == user_id]

    async def get_dashboard_stats(self, user_id, integration_id=None):
        if not integration_id:
            return None
        return self.stats.get(integration_id)

    async def get_resources(self, user_id, integration_id=None):
        return list(self.resources)

    async def get_daily_spend_history(self, user_id, integration_id=None, days=30):
        if integration_id:
            return list(self.history.get(integration_id, []))[-days:]
        rows = []
        for values in self.history.values():
            rows.extend(values)
        return rows[-days:]


def _build_client(fake_db: FakeTotalBillDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_totalbill_groups_active_integrations_by_provider_and_categories():
    client = _build_client(FakeTotalBillDB())

    response = client.get("/api/totalbill")

    assert response.status_code == 200
    payload = response.json()

    assert payload["total_spend"] == 350.0
    assert payload["total_savings"] == 35.0
    assert payload["total_resources"] == 18
    assert payload["provider_count"] == 2

    assert payload["providers"] == [
        {
            "provider": "AWS",
            "monthly_spend": 300.0,
            "potential_savings": 30.0,
            "resource_count": 15,
            "last_scan": "2026-03-22T09:00:00+00:00",
            "integration_count": 2,
            "integration_ids": ["aws-1", "aws-2"],
            "account_identifiers": ["111111111111", "222222222222"],
        },
        {
            "provider": "GCP",
            "monthly_spend": 50.0,
            "potential_savings": 5.0,
            "resource_count": 3,
            "last_scan": "2026-03-21T08:00:00+00:00",
            "integration_count": 1,
            "integration_ids": ["gcp-1"],
            "account_identifiers": ["project-123"],
        },
    ]

    assert payload["categories"] == [
        {
            "category": "Compute",
            "by_provider": {"AWS": 80.0, "GCP": 40.0},
            "total": 120.0,
        },
        {
            "category": "Database",
            "by_provider": {"AWS": 30.0, "GCP": 10.0},
            "total": 40.0,
        },
        {
            "category": "Storage",
            "by_provider": {"AWS": 20.0},
            "total": 20.0,
        },
    ]

    latest_daily = payload["daily_provider_spend_30d"][-1]
    assert latest_daily["aws"] == 20.0
    assert latest_daily["gcp"] == 3.0
    assert latest_daily["azure"] == 0.0
    assert latest_daily["total"] == 23.0

    assert len(payload["heatmap_days"]) == 90
    assert payload["heatmap_days"][-1]["amount"] == 23.0
    assert payload["visual_currency"] == "INR"

    assert payload["provider_forecasts"] == [
        {
            "provider": "AWS",
            "forecast_monthly": 375.0,
            "forecast_annual": 4500.0,
            "history_days": 2,
            "forecast_source": "daily_spend_history_30d",
        },
        {
            "provider": "GCP",
            "forecast_monthly": 90.0,
            "forecast_annual": 1080.0,
            "history_days": 1,
            "forecast_source": "daily_spend_history_30d",
        },
    ]

    assert payload["service_hierarchy"][0]["name"] == "Compute"
    flow_providers = {row["provider"] for row in payload["spend_flows"]}
    assert flow_providers == {"AWS", "GCP"}


def test_stats_aggregates_only_active_integration_rows():
    client = _build_client(FakeTotalBillDB())

    response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total_spend": 350.0,
        "potential_savings": 35.0,
        "active_resources_count": 18,
        "ai_confidence_score": 0,
        "carbon_footprint_kg": 0.0,
        "cost_of_inaction_6mo": 0.0,
    }


def test_resources_excludes_inactive_integration_rows_for_portfolio_reads():
    client = _build_client(FakeTotalBillDB())

    response = client.get("/api/resources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 6
    assert {row["integration_id"] for row in payload["resources"]} == {"aws-1", "aws-2", "gcp-1"}
