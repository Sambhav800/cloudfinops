import asyncio
from datetime import date, datetime, timezone

from app.workers import report_worker
from app.workers.report_worker import (
    _build_report_email_html,
    _group_integrations_by_user,
    _resolve_report_delivery,
    _should_send_report_today,
)


def test_group_integrations_by_user_is_tenant_scoped():
    grouped = _group_integrations_by_user(
        [
            {"id": "int-1", "user_id": "user-a", "provider": "aws"},
            {"id": "int-2", "user_id": "user-b", "provider": "gcp"},
            {"id": "int-3", "user_id": "user-a", "provider": "azure"},
            {"id": "", "user_id": "user-a", "provider": "aws"},
        ]
    )

    assert sorted(grouped.keys()) == ["user-a", "user-b"]
    assert [item["id"] for item in grouped["user-a"]] == ["int-1", "int-3"]
    assert [item["id"] for item in grouped["user-b"]] == ["int-2"]


def test_build_report_email_html_includes_summary_and_provider_rows():
    html = _build_report_email_html(
        {
            "title": "Monthly Executive Summary - Mar 2026",
            "summary": "Portfolio forecast is on track.",
            "currency": "USD",
            "data": {
                "portfolio": {
                    "actual_period_spend": 210.0,
                    "forecast_eom_spend": 320.0,
                    "status": "on_track",
                },
                "highlights": ["AWS remains the largest provider.", "All active accounts are forecast-ready."],
                "provider_breakdown": [
                    {"provider": "aws", "actual_period_spend": 135.0, "forecast_eom_spend": 220.0},
                    {"provider": "gcp", "actual_period_spend": 75.0, "forecast_eom_spend": 100.0},
                ],
            },
        }
    )

    assert "Monthly Executive Summary - Mar 2026" in html
    assert "Portfolio forecast is on track." in html
    assert "AWS remains the largest provider." in html
    assert "USD 135.00" in html
    assert "GCP" in html


def test_should_send_report_today_supports_manual_weekly_and_monthly():
    assert _should_send_report_today("manual", date(2026, 3, 16)) is False
    assert _should_send_report_today("weekly", date(2026, 3, 16)) is True
    assert _should_send_report_today("weekly", date(2026, 3, 17)) is False
    assert _should_send_report_today("monthly", date(2026, 4, 1)) is True
    assert _should_send_report_today("monthly", date(2026, 4, 2)) is False


def test_resolve_report_delivery_prefers_finance_settings_recipients(monkeypatch):
    class FakeDB:
        async def select(self, table, filters=None):
            if table != "users":
                return []
            return [
                {
                    "id": "user-1",
                    "email": "owner@example.com",
                    "finance_settings": {
                        "report_recipients": ["finance@example.com", "cto@example.com"],
                        "report_cadence": "monthly",
                        "alert_thresholds": {"warning_pct": 80, "critical_pct": 100},
                    },
                }
            ]

    monkeypatch.setattr(report_worker, "get_db_client", lambda: FakeDB())

    recipients, cadence = asyncio.run(_resolve_report_delivery("user-1"))

    assert recipients == ["finance@example.com", "cto@example.com"]
    assert cadence == "monthly"


def test_generate_and_send_scheduled_reports_persists_and_sends_email(monkeypatch):
    class FakeDB:
        def __init__(self):
            self.users = {
                "user-1": {
                    "id": "user-1",
                    "email": "owner@example.com",
                    "finance_settings": {
                        "report_recipients": ["finance@example.com"],
                        "report_cadence": "weekly",
                        "alert_thresholds": {"warning_pct": 80, "critical_pct": 100},
                    },
                }
            }
            self.integrations = [
                {
                    "id": "int-1",
                    "user_id": "user-1",
                    "provider": "aws",
                    "name": "Prod AWS",
                    "status": "active",
                    "monthly_budget_limit": 400.0,
                }
            ]
            self.history_by_integration = {
                "int-1": [
                    {"spend_date": "2026-03-01", "amount": 20.0, "currency": "USD"},
                    {"spend_date": "2026-03-02", "amount": 21.0, "currency": "USD"},
                    {"spend_date": "2026-03-03", "amount": 22.0, "currency": "USD"},
                    {"spend_date": "2026-03-04", "amount": 23.0, "currency": "USD"},
                    {"spend_date": "2026-03-05", "amount": 24.0, "currency": "USD"},
                    {"spend_date": "2026-03-06", "amount": 25.0, "currency": "USD"},
                ]
            }
            self.reports = []

        async def select(self, table, filters=None, columns="*"):
            filters = filters or {}
            if table == "users":
                user_id = filters.get("id")
                row = self.users.get(user_id)
                return [row] if row else []
            if table == "cloud_integrations":
                return list(self.integrations)
            if table == "reports":
                return [
                    row for row in self.reports
                    if all(row.get(key) == value for key, value in filters.items())
                ]
            return []

        async def insert(self, table, data):
            row = dict(data)
            row.setdefault("id", f"report-{len(self.reports) + 1}")
            row.setdefault("created_at", "2026-03-16T08:00:00+00:00")
            self.reports.append(row)
            return [row]

        async def update(self, table, data, filters):
            for row in self.reports:
                if all(row.get(key) == value for key, value in filters.items()):
                    row.update(data)
            return self.reports

        async def get_daily_spend_history(self, user_id, integration_id=None, days=365):
            return self.history_by_integration.get(integration_id, [])[-days:]

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 16, 8, 0, tzinfo=timezone.utc)

    fake_db = FakeDB()
    sent_params = []

    monkeypatch.setattr(report_worker, "get_db_client", lambda: fake_db)
    monkeypatch.setattr(report_worker, "datetime", FrozenDateTime)
    monkeypatch.setattr(report_worker.resend, "api_key", "test-key")
    monkeypatch.setattr(report_worker.resend.Emails, "send", lambda params: sent_params.append(params))

    asyncio.run(report_worker.generate_and_send_scheduled_reports())

    assert len(fake_db.reports) == 1
    report = fake_db.reports[0]
    assert report["report_type"] == "monthly_executive_summary"
    assert report["delivery_status"] == "sent"
    assert report["metadata"]["scheduled"] is True
    assert report["metadata"]["scheduled_cadence"] == "weekly"
    assert "email" in report["delivery_channels"]
    assert len(sent_params) == 1
    assert sent_params[0]["to"] == ["finance@example.com"]
    assert sent_params[0]["subject"] == report["title"]


def test_generate_and_send_scheduled_reports_keeps_report_in_app_when_no_recipients(monkeypatch):
    class FakeDB:
        def __init__(self):
            self.users = {
                "user-1": {
                    "id": "user-1",
                    "email": "",
                    "finance_settings": {
                        "report_recipients": [],
                        "report_cadence": "weekly",
                        "alert_thresholds": {"warning_pct": 80, "critical_pct": 100},
                    },
                }
            }
            self.integrations = [
                {
                    "id": "int-1",
                    "user_id": "user-1",
                    "provider": "aws",
                    "name": "Prod AWS",
                    "status": "active",
                    "monthly_budget_limit": 400.0,
                }
            ]
            self.history_by_integration = {
                "int-1": [
                    {"spend_date": "2026-03-01", "amount": 20.0, "currency": "USD"},
                    {"spend_date": "2026-03-02", "amount": 21.0, "currency": "USD"},
                    {"spend_date": "2026-03-03", "amount": 22.0, "currency": "USD"},
                    {"spend_date": "2026-03-04", "amount": 23.0, "currency": "USD"},
                    {"spend_date": "2026-03-05", "amount": 24.0, "currency": "USD"},
                    {"spend_date": "2026-03-06", "amount": 25.0, "currency": "USD"},
                ]
            }
            self.reports = []

        async def select(self, table, filters=None, columns="*"):
            filters = filters or {}
            if table == "users":
                user_id = filters.get("id")
                row = self.users.get(user_id)
                return [row] if row else []
            if table == "cloud_integrations":
                return list(self.integrations)
            if table == "reports":
                return [
                    row for row in self.reports
                    if all(row.get(key) == value for key, value in filters.items())
                ]
            return []

        async def insert(self, table, data):
            row = dict(data)
            row.setdefault("id", f"report-{len(self.reports) + 1}")
            row.setdefault("created_at", "2026-03-16T08:00:00+00:00")
            self.reports.append(row)
            return [row]

        async def update(self, table, data, filters):
            for row in self.reports:
                if all(row.get(key) == value for key, value in filters.items()):
                    row.update(data)
            return self.reports

        async def get_daily_spend_history(self, user_id, integration_id=None, days=365):
            return self.history_by_integration.get(integration_id, [])[-days:]

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 16, 8, 0, tzinfo=timezone.utc)

    fake_db = FakeDB()
    sent_params = []

    monkeypatch.setattr(report_worker, "get_db_client", lambda: fake_db)
    monkeypatch.setattr(report_worker, "datetime", FrozenDateTime)
    monkeypatch.setattr(report_worker.resend, "api_key", "test-key")
    monkeypatch.setattr(report_worker.resend.Emails, "send", lambda params: sent_params.append(params))

    asyncio.run(report_worker.generate_and_send_scheduled_reports())

    assert len(fake_db.reports) == 1
    report = fake_db.reports[0]
    assert report["delivery_status"] == "skipped_no_recipients"
    assert report["delivery_channels"] == ["in_app"]
    assert report["metadata"]["scheduled"] is True
    assert report["metadata"]["scheduled_delivery"] == "skipped_no_recipients"
    assert sent_params == []
