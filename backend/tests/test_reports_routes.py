from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.reports_routes import reports_router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeReportsDB:
    def __init__(self):
        self.users = {
            "user-1": {
                "id": "user-1",
                "email": "owner@example.com",
                "finance_settings": {
                    "portfolio_budget_limit": None,
                    "report_recipients": [],
                    "report_cadence": "weekly",
                    "alert_thresholds": {"warning_pct": 80.0, "critical_pct": 100.0},
                },
            }
        }
        self.reports = [
            {
                "id": "report-older",
                "user_id": "user-1",
                "report_type": "monthly_executive_summary",
                "title": "Older Report",
                "summary": "Older summary",
                "status": "ready",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "generated_at": "2026-03-01T08:00:00+00:00",
                "created_at": "2026-03-01T08:00:00+00:00",
                "currency": "USD",
                "file_size_bytes": 512,
                "delivery_channels": ["in_app"],
                "delivery_status": "available",
                "metadata": {"scope": "portfolio"},
                "data": {"portfolio": {"forecast_eom_spend": 200.0}},
            },
            {
                "id": "report-other-user",
                "user_id": "user-2",
                "report_type": "board_pack",
                "title": "Other User Report",
                "summary": "Other summary",
                "status": "ready",
                "period_start": "2026-03-01",
                "period_end": "2026-03-10",
                "generated_at": "2026-03-10T08:00:00+00:00",
                "created_at": "2026-03-10T08:00:00+00:00",
                "currency": "USD",
                "file_size_bytes": 1024,
                "delivery_channels": ["in_app"],
                "delivery_status": "available",
                "metadata": {"scope": "portfolio"},
                "data": {"portfolio": {"forecast_eom_spend": 300.0}},
            },
        ]
        self.integrations = [
            {
                "id": "int-aws",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Production AWS",
                "status": "active",
                "monthly_budget_limit": 350.0,
                "account_identifier": "111111111111",
            },
            {
                "id": "int-gcp",
                "user_id": "user-1",
                "provider": "gcp",
                "name": "Analytics GCP",
                "status": "active",
                "monthly_budget_limit": 200.0,
                "account_identifier": "gcp-project-1",
            },
        ]
        self.history_by_integration = {
            "int-aws": [
                {"spend_date": "2026-03-01", "amount": 40.0, "currency": "USD"},
                {"spend_date": "2026-03-02", "amount": 42.0, "currency": "USD"},
                {"spend_date": "2026-03-03", "amount": 41.0, "currency": "USD"},
                {"spend_date": "2026-03-04", "amount": 43.0, "currency": "USD"},
                {"spend_date": "2026-03-05", "amount": 44.0, "currency": "USD"},
                {"spend_date": "2026-03-06", "amount": 45.0, "currency": "USD"},
                {"spend_date": "2026-03-07", "amount": 46.0, "currency": "USD"},
                {"spend_date": "2026-03-08", "amount": 47.0, "currency": "USD"},
                {"spend_date": "2026-03-09", "amount": 48.0, "currency": "USD"},
                {"spend_date": "2026-03-10", "amount": 49.0, "currency": "USD"},
            ],
            "int-gcp": [
                {"spend_date": "2026-03-01", "amount": 18.0, "currency": "USD"},
                {"spend_date": "2026-03-02", "amount": 17.0, "currency": "USD"},
                {"spend_date": "2026-03-03", "amount": 19.0, "currency": "USD"},
                {"spend_date": "2026-03-04", "amount": 20.0, "currency": "USD"},
                {"spend_date": "2026-03-05", "amount": 21.0, "currency": "USD"},
                {"spend_date": "2026-03-06", "amount": 22.0, "currency": "USD"},
                {"spend_date": "2026-03-07", "amount": 23.0, "currency": "USD"},
                {"spend_date": "2026-03-08", "amount": 24.0, "currency": "USD"},
                {"spend_date": "2026-03-09", "amount": 25.0, "currency": "USD"},
                {"spend_date": "2026-03-10", "amount": 26.0, "currency": "USD"},
            ],
        }

    async def select(self, table, filters=None, columns="*"):
        filters = filters or {}
        if table == "reports":
            return [
                row
                for row in self.reports
                if all(row.get(key) == value for key, value in filters.items())
            ]

        if table == "users":
            user_id = filters.get("id")
            row = self.users.get(user_id)
            return [row] if row else []

        return []

    async def insert(self, table, data):
        if table != "reports":
            return []

        row = dict(data)
        row.setdefault("id", f"report-{len(self.reports) + 1}")
        row.setdefault("created_at", row.get("generated_at") or "2026-03-10T09:00:00+00:00")
        self.reports.append(row)
        return [row]

    async def get_user_integrations(self, user_id):
        return [row for row in self.integrations if row.get("user_id") == user_id]

    async def get_daily_spend_history(self, user_id, integration_id=None, days=365):
        rows = list(self.history_by_integration.get(integration_id, []))
        return rows[-days:]


def _build_client(fake_db: FakeReportsDB) -> TestClient:
    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_reports_list_filters_to_current_user_and_sorts_desc():
    fake_db = FakeReportsDB()
    fake_db.reports.append(
        {
            "id": "report-newer",
            "user_id": "user-1",
            "report_type": "budget_variance",
            "title": "Newest Report",
            "summary": "Newest summary",
            "status": "ready",
            "period_start": "2026-03-01",
            "period_end": "2026-03-10",
            "generated_at": "2026-03-10T09:00:00+00:00",
            "created_at": "2026-03-10T09:00:00+00:00",
            "currency": "USD",
            "file_size_bytes": 768,
            "delivery_channels": ["in_app"],
            "delivery_status": "available",
            "metadata": {"scope": "portfolio"},
            "data": {"portfolio": {"forecast_eom_spend": 450.0}},
        }
    )
    client = _build_client(fake_db)

    response = client.get("/api/reports")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert [item["id"] for item in payload["reports"]] == ["report-newer", "report-older"]


def test_generate_report_persists_backend_owned_record(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 10))
    monkeypatch.setattr("app.core.reports._utc_now_iso", lambda: "2026-03-10T10:00:00+00:00")
    fake_db = FakeReportsDB()
    client = _build_client(fake_db)

    response = client.post(
        "/api/reports/generate",
        json={"report_type": "monthly_executive_summary"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["report_type"] == "monthly_executive_summary"
    assert payload["status"] == "ready"
    assert payload["metadata"]["scope"] == "portfolio"
    assert payload["data"]["portfolio"]["budget_limit"] == 550.0
    assert payload["file_size_bytes"] > 0
    assert fake_db.reports[-1]["user_id"] == "user-1"
    assert fake_db.reports[-1]["report_type"] == "monthly_executive_summary"


def test_generate_report_uses_portfolio_budget_setting_when_present(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 10))
    monkeypatch.setattr("app.core.reports._utc_now_iso", lambda: "2026-03-10T10:30:00+00:00")
    fake_db = FakeReportsDB()
    fake_db.users["user-1"]["finance_settings"]["portfolio_budget_limit"] = 700.0
    client = _build_client(fake_db)

    response = client.post(
        "/api/reports/generate",
        json={"report_type": "budget_variance"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["data"]["portfolio"]["budget_limit"] == 700.0
    assert payload["data"]["portfolio"]["budget_source"] == "portfolio_setting"


def test_generate_report_rejects_invalid_period(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 10))
    fake_db = FakeReportsDB()
    client = _build_client(fake_db)

    response = client.post(
        "/api/reports/generate",
        json={
            "report_type": "budget_variance",
            "start_date": "2026-03-10",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date must be on or before end_date"


def test_generate_report_marks_attention_needed_for_thin_history(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 10))
    monkeypatch.setattr("app.core.reports._utc_now_iso", lambda: "2026-03-10T11:00:00+00:00")
    fake_db = FakeReportsDB()
    fake_db.history_by_integration["int-aws"] = [
        {"spend_date": "2026-03-09", "amount": 30.0, "currency": "USD"},
        {"spend_date": "2026-03-10", "amount": 32.0, "currency": "USD"},
    ]
    fake_db.history_by_integration["int-gcp"] = []
    client = _build_client(fake_db)

    response = client.post(
        "/api/reports/generate",
        json={"report_type": "board_pack"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "attention_needed"
    assert payload["data"]["readiness"]["ready_accounts"] == 0
    assert payload["data"]["portfolio"]["status"] == "insufficient_history"
