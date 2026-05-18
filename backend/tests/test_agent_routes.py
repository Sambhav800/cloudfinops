from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.agent_routes import agent_router
from app.api.agents_status_routes import status_router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeAgentRoutesDB:
    async def select(self, table, filters=None, columns="*"):
        filters = filters or {}
        user_id = filters.get("id") or filters.get("user_id")
        if user_id != "user-1":
            return []

        if table == "users":
            return [
                {
                    "id": "user-1",
                    "first_name": "Sambhav",
                    "full_name": "Sambhav Pal",
                    "email": "sambhavpal5@gmail.com",
                }
            ]

        if table == "dashboard_stats":
            return [
                {
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "total_spend": 10.0,
                    "potential_savings": 2.0,
                    "active_resources_count": 54,
                    "ai_confidence_score": 87,
                },
                {
                    "user_id": "user-1",
                    "integration_id": "int-2",
                    "total_spend": 1.0,
                    "potential_savings": 0.5,
                    "active_resources_count": 0,
                    "ai_confidence_score": 87,
                }
            ]

        if table == "agent_notifications":
            return [
                {"id": "n-1", "user_id": "user-1", "status": "pending"},
                {"id": "n-2", "user_id": "user-1", "status": "pending"},
            ]

        if table == "policy_violations":
            return [
                {"id": "v-1", "user_id": "user-1", "status": "active"},
            ]

        if table == "cloud_integrations":
            return [
                {
                    "id": "int-1",
                    "user_id": "user-1",
                    "provider": "aws",
                    "status": "active",
                    "last_scan": "2026-03-22T06:00:00+00:00",
                },
                {
                    "id": "int-2",
                    "user_id": "user-1",
                    "provider": "azure",
                    "status": "active",
                    "last_scan": "2026-03-22T05:00:00+00:00",
                },
            ]

        if table == "budget_events":
            return [
                {
                    "user_id": "user-1",
                    "scope": "portfolio",
                    "budget_limit": 1000.0,
                    "current_status": "on_track",
                    "forecast_eom_spend": 920.0,
                    "created_at": "2026-03-22T09:00:00+00:00",
                }
            ]

        if table == "bill_analyses":
            return [
                {"id": "bill-1", "user_id": "user-1"},
            ]

        return []

    async def get_resources(self, user_id, integration_id=None):
        if user_id != "user-1":
            return []
        return [
            {"id": "res-1", "user_id": "user-1", "resource_name": "prod-db"},
            {"id": "res-2", "user_id": "user-1", "resource_name": "prod-web"},
        ]


def _build_client(fake_db: FakeAgentRoutesDB) -> TestClient:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(status_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(
        id="user-1",
        email="sambhavpal5@gmail.com",
        first_name="Sambhav",
    )
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_agent_summary_returns_live_account_snapshot():
    client = _build_client(FakeAgentRoutesDB())

    response = client.get("/api/agent/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resources"] == 54
    assert payload["savings"] == 207.5
    assert payload["total_spend"] == 913.0
    assert payload["currency"] == "INR"
    assert payload["alerts"] == 2
    assert payload["violations"] == 1
    assert payload["confidence"] == 87
    assert payload["providers"] == ["AWS", "AZURE"]
    assert "Sambhav" in payload["summary"]
    assert "₹913.00" in payload["summary"]
    assert "₹207.50/month" in payload["summary"]
    assert "2 open alerts" in payload["summary"]
    assert "$" not in payload["summary"]


class EmptyAgentRoutesDB(FakeAgentRoutesDB):
    async def select(self, table, filters=None, columns="*"):
        if table == "users":
            return [
                {
                    "id": "user-1",
                    "first_name": "Sambhav",
                    "full_name": "Sambhav Pal",
                    "email": "sambhavpal5@gmail.com",
                }
            ]
        return []


def test_agent_summary_handles_empty_finance_state_in_inr():
    client = _build_client(EmptyAgentRoutesDB())

    response = client.get("/api/agent/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resources"] == 0
    assert payload["savings"] == 0
    assert payload["total_spend"] == 0
    assert payload["currency"] == "INR"
    assert "₹0.00" in payload["summary"]
    assert "no connected clouds yet" in payload["summary"]


def test_agents_status_returns_live_agent_counts():
    client = _build_client(FakeAgentRoutesDB())

    response = client.get("/api/agents/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "agents": [
            {"name": "Savings Agent", "status": "scanning", "insights_ready": 0},
            {"name": "Governance Agent", "status": "scanning", "insights_ready": 0},
            {"name": "Bill Agent", "status": "idle", "insights_ready": 1},
        ]
    }
