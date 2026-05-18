from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.finance_routes import finance_router
from app.auth import ClerkUser, get_current_user
from app.core.finance import aggregate_daily_spend_rows
from app.db import get_db_client


class FakeFinanceDB:
    def __init__(self):
        self.users = {
            "user-1": {
                "id": "user-1",
                "finance_settings": {
                    "portfolio_budget_limit": None,
                    "report_recipients": [],
                    "report_cadence": "weekly",
                    "alert_thresholds": {"warning_pct": 80.0, "critical_pct": 100.0},
                },
            }
        }
        self.integrations = [
            {
                "id": "int-aws",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Prod AWS",
                "status": "active",
                "monthly_budget_limit": 300.0,
                "alert_phone_number": "+14155550119",
                "alert_slack_webhook": "https://hooks.slack.test/services/a/b/c",
            },
            {
                "id": "int-gcp",
                "user_id": "user-1",
                "provider": "gcp",
                "name": "Analytics GCP",
                "status": "active",
                "monthly_budget_limit": 200.0,
            },
            {
                "id": "int-old",
                "user_id": "user-1",
                "provider": "azure",
                "name": "Old Azure",
                "status": "inactive",
                "monthly_budget_limit": 999.0,
            },
        ]
        self.history_by_integration = {
            "int-aws": [
                {"spend_date": "2026-03-01", "amount": 20.0, "currency": "USD"},
                {"spend_date": "2026-03-02", "amount": 21.0, "currency": "USD"},
                {"spend_date": "2026-03-03", "amount": 22.0, "currency": "USD"},
                {"spend_date": "2026-03-04", "amount": 23.0, "currency": "USD"},
                {"spend_date": "2026-03-05", "amount": 24.0, "currency": "USD"},
                {"spend_date": "2026-03-06", "amount": 25.0, "currency": "USD"},
            ],
            "int-gcp": [
                {"spend_date": "2026-03-01", "amount": 10.0, "currency": "USD"},
                {"spend_date": "2026-03-02", "amount": 10.0, "currency": "USD"},
                {"spend_date": "2026-03-03", "amount": 10.0, "currency": "USD"},
                {"spend_date": "2026-03-04", "amount": 11.0, "currency": "USD"},
                {"spend_date": "2026-03-05", "amount": 11.0, "currency": "USD"},
                {"spend_date": "2026-03-06", "amount": 12.0, "currency": "USD"},
            ],
        }
        self.budget_events = []
        self.notifications = []

    async def get_user_integrations(self, user_id):
        return [item for item in self.integrations if item.get("user_id") == user_id]

    async def get_integration(self, integration_id, user_id):
        return next((item for item in self.integrations if item["id"] == integration_id), None)

    async def select(self, table, filters=None, columns="*"):
        if table != "users":
            return []

        filters = filters or {}
        user_id = filters.get("id")
        if not user_id:
            return []

        row = self.users.get(user_id)
        return [row] if row else []

    async def upsert(self, table, data):
        if table != "users":
            return []

        row = self.users.setdefault(str(data["id"]), {"id": str(data["id"])})
        row.update(data)
        return [row]

    async def create_notifications(self, notifications):
        self.notifications.extend(notifications)
        return True

    async def create_budget_event(self, event):
        row = dict(event)
        row.setdefault("id", f"evt-{len(self.budget_events) + 1}")
        row.setdefault("created_at", f"2026-03-06T0{len(self.budget_events)}:00:00+00:00")
        self.budget_events.append(row)
        return row

    async def get_budget_events(self, user_id, scope=None, integration_id=None, limit=20):
        rows = [
            row
            for row in self.budget_events
            if row.get("user_id") == user_id
            and (scope is None or row.get("scope") == scope)
            and (integration_id is None or row.get("integration_id") == integration_id)
        ]
        rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
        return rows[:limit]

    async def get_latest_budget_event(self, *, user_id, scope, integration_id=None):
        rows = await self.get_budget_events(
            user_id,
            scope=scope,
            integration_id=integration_id,
            limit=1,
        )
        return rows[0] if rows else None

    async def get_daily_spend_history(self, user_id, integration_id=None, days=60):
        if integration_id == "int-dup":
            rows = [
                {
                    "spend_date": "2026-03-05",
                    "amount": 12.5,
                    "currency": "USD",
                    "service_breakdown": {"EC2": 12.5},
                },
                {
                    "spend_date": "2026-03-05T07:30:00Z",
                    "amount": 7.5,
                    "currency": "USD",
                    "service_breakdown": {"S3": 7.5},
                },
                {
                    "spend_date": "2026-03-06",
                    "amount": 4.0,
                    "currency": "USD",
                    "service_breakdown": {"Lambda": 4.0},
                },
            ]
            return aggregate_daily_spend_rows(rows)[-days:]

        if integration_id:
            rows = self.history_by_integration.get(integration_id, [])
            return aggregate_daily_spend_rows(rows)[-days:]

        merged_rows = []
        for rows in self.history_by_integration.values():
            merged_rows.extend(rows)
        return aggregate_daily_spend_rows(merged_rows)[-days:]


def _build_client(fake_db: FakeFinanceDB) -> TestClient:
    app = FastAPI()
    app.include_router(finance_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_finance_forecast_portfolio_sums_active_budgets(monkeypatch):
    monkeypatch.setattr("app.core.finance._utc_today", lambda: date(2026, 3, 6))
    client = _build_client(FakeFinanceDB())

    response = client.get("/api/finance/forecast", params={"scope": "portfolio"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "portfolio"
    assert payload["budget_limit"] == 500.0
    assert payload["budget_source"] == "portfolio_sum"
    assert payload["status"] == "forecasted_over_budget"
    assert payload["drivers"] == [
        {"dimension": "Account", "key": "Prod AWS (AWS)", "delta_amount": 562.5},
        {"dimension": "Account", "key": "Analytics GCP (GCP)", "delta_amount": 266.67},
    ]


def test_finance_spend_history_returns_aggregated_rows(monkeypatch):
    fake_db = FakeFinanceDB()
    fake_db.integrations.append({"id": "int-dup", "status": "active", "monthly_budget_limit": 100.0})
    client = _build_client(fake_db)

    response = client.get(
        "/api/finance/spend-history",
        params={"scope": "integration", "integration_id": "int-dup", "days": 30},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["history"] == [
        {"spend_date": "2026-03-05", "amount": 20.0, "currency": "USD"},
        {"spend_date": "2026-03-06", "amount": 4.0, "currency": "USD"},
    ]


def test_finance_integration_scope_requires_integration_id(monkeypatch):
    client = _build_client(FakeFinanceDB())

    response = client.get("/api/finance/forecast", params={"scope": "integration"})

    assert response.status_code == 400
    assert response.json()["detail"] == "integration_id is required when scope='integration'"


def test_finance_integration_scope_rejects_unknown_integration(monkeypatch):
    client = _build_client(FakeFinanceDB())

    response = client.get(
        "/api/finance/spend-history",
        params={"scope": "integration", "integration_id": "int-missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Integration not found"


def test_finance_settings_returns_defaults_from_user_document():
    client = _build_client(FakeFinanceDB())

    response = client.get("/api/finance/settings")

    assert response.status_code == 200
    assert response.json() == {
        "portfolio_budget_limit": None,
        "report_recipients": [],
        "report_cadence": "weekly",
        "alert_thresholds": {
            "warning_pct": 80.0,
            "critical_pct": 100.0,
        },
    }


def test_finance_settings_update_persists_user_preferences(monkeypatch):
    monkeypatch.setattr("app.core.finance._utc_today", lambda: date(2026, 3, 6))
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.finance_routes.log_audit_event", _noop_audit)
    fake_db = FakeFinanceDB()
    client = _build_client(fake_db)

    update_response = client.put(
        "/api/finance/settings",
        json={
            "portfolio_budget_limit": 700.0,
            "report_recipients": ["finance@example.com", "cto@example.com"],
            "report_cadence": "monthly",
            "alert_thresholds": {"warning_pct": 75, "critical_pct": 110},
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "portfolio_budget_limit": 700.0,
        "report_recipients": ["finance@example.com", "cto@example.com"],
        "report_cadence": "monthly",
        "alert_thresholds": {
            "warning_pct": 75.0,
            "critical_pct": 110.0,
        },
    }
    assert fake_db.users["user-1"]["finance_settings"]["portfolio_budget_limit"] == 700.0

    forecast_response = client.get("/api/finance/forecast", params={"scope": "portfolio"})

    assert forecast_response.status_code == 200
    forecast = forecast_response.json()
    assert forecast["budget_limit"] == 700.0
    assert forecast["budget_source"] == "portfolio_setting"


def test_finance_settings_update_rejects_thresholds_above_backend_limits():
    client = _build_client(FakeFinanceDB())

    response = client.put(
        "/api/finance/settings",
        json={
            "alert_thresholds": {
                "warning_pct": 80,
                "critical_pct": 400,
            }
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "critical_pct" for item in detail)


def test_finance_settings_update_rejects_critical_threshold_below_warning():
    client = _build_client(FakeFinanceDB())

    response = client.put(
        "/api/finance/settings",
        json={
            "alert_thresholds": {
                "warning_pct": 90,
                "critical_pct": 80,
            }
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Critical threshold must be greater than or equal to the warning threshold."
    )


def test_finance_budget_events_sync_and_list_routes(monkeypatch):
    monkeypatch.setattr("app.core.finance._utc_today", lambda: date(2026, 3, 6))
    client = _build_client(FakeFinanceDB())

    sync_response = client.post("/api/finance/budget-events/sync")

    assert sync_response.status_code == 200
    assert sync_response.json() == {"events_created": 3}

    list_response = client.get("/api/finance/budget-events", params={"limit": 5})

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 3
    assert payload["events"][0]["event_type"] == "forecasted_over_budget"
    assert {event["scope"] for event in payload["events"]} == {"portfolio", "integration"}
