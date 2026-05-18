from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeIntegrationSettingsDB:
    def __init__(self):
        self.integrations = {
            "int-1": {
                "id": "int-1",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Production AWS",
                "status": "active",
                "last_scan": None,
                "regions": ["us-east-1"],
                "monthly_budget_limit": 500.0,
                "alert_phone_number": "+1 (415) 555-0119",
                "alert_slack_webhook": "https://hooks.slack.com/services/T000/B000/secret",
                "encrypted_access_key_id": "AKIA1234567890TEST",
            }
        }
        self.update_calls = []

    async def get_user_integrations(self, user_id):
        return [row for row in self.integrations.values() if row.get("user_id") == user_id]

    async def get_integration(self, integration_id, user_id):
        row = self.integrations.get(integration_id)
        if row and row.get("user_id") == user_id:
            return row
        return None

    async def update(self, table, data, filters):
        self.update_calls.append((table, data, filters))
        row = self.integrations.get(filters["id"])
        if row:
            row.update(data)
            return [row]
        return []


def _build_client(fake_db: FakeIntegrationSettingsDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_get_integrations_exposes_budget_and_alert_configuration(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.routes.log_audit_event", _noop_audit)
    client = _build_client(FakeIntegrationSettingsDB())

    response = client.get("/api/integrations")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "id": "int-1",
            "provider": "aws",
            "name": "Production AWS",
            "status": "active",
            "last_scan": None,
            "regions": ["us-east-1"],
            "created_at": None,
            "account_identifier": None,
            "monthly_budget_limit": 500.0,
            "alert_phone_number_masked": "***0119",
            "alert_slack_webhook_configured": True,
        }
    ]


def test_update_integration_settings_allows_explicit_null_clears(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.routes.log_audit_event", _noop_audit)
    fake_db = FakeIntegrationSettingsDB()
    client = _build_client(fake_db)

    response = client.put(
        "/api/integrations/int-1/settings",
        json={
            "monthly_budget_limit": None,
            "alert_phone_number": None,
            "alert_slack_webhook": None,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert fake_db.update_calls == [
        (
            "cloud_integrations",
            {
                "monthly_budget_limit": None,
                "alert_phone_number": None,
                "alert_slack_webhook": None,
            },
            {"id": "int-1", "user_id": "user-1"},
        )
    ]
    assert fake_db.integrations["int-1"]["monthly_budget_limit"] is None
    assert fake_db.integrations["int-1"]["alert_phone_number"] is None
    assert fake_db.integrations["int-1"]["alert_slack_webhook"] is None
