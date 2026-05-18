import asyncio
from datetime import date

from app.core.budget_events import sync_budget_events_for_user
from app.core.finance import aggregate_daily_spend_rows


class FakeBudgetEventsDB:
    def __init__(self):
        self.users = {
            "user-1": {
                "id": "user-1",
                "finance_settings": {
                    "portfolio_budget_limit": 300.0,
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
                "monthly_budget_limit": 200.0,
                "alert_phone_number": "+14155550119",
                "alert_slack_webhook": "https://hooks.slack.test/services/a/b/c",
            }
        ]
        self.history_by_integration = {
            "int-aws": [
                {"spend_date": "2026-03-01", "amount": 20.0, "currency": "USD"},
                {"spend_date": "2026-03-02", "amount": 21.0, "currency": "USD"},
                {"spend_date": "2026-03-03", "amount": 22.0, "currency": "USD"},
                {"spend_date": "2026-03-04", "amount": 23.0, "currency": "USD"},
                {"spend_date": "2026-03-05", "amount": 24.0, "currency": "USD"},
                {"spend_date": "2026-03-06", "amount": 25.0, "currency": "USD"},
            ]
        }
        self.budget_events = []
        self.notifications = []

    async def select(self, table, filters=None, columns="*"):
        filters = filters or {}
        if table != "users":
            return []

        user_id = filters.get("id")
        row = self.users.get(user_id)
        return [row] if row else []

    async def get_user_integrations(self, user_id):
        return [row for row in self.integrations if row.get("user_id") == user_id]

    async def get_daily_spend_history(self, user_id, integration_id=None, days=60):
        if integration_id:
            rows = self.history_by_integration.get(integration_id, [])
            return aggregate_daily_spend_rows(rows)[-days:]

        merged_rows = []
        for rows in self.history_by_integration.values():
            merged_rows.extend(rows)
        return aggregate_daily_spend_rows(merged_rows)[-days:]

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

    async def create_notifications(self, notifications):
        self.notifications.extend(notifications)
        return True


def test_sync_budget_events_for_user_persists_and_dedupes(monkeypatch):
    async def _fake_whatsapp(message, phone):
        sent_whatsapp.append((message, phone))

    async def _fake_slack(message, webhook):
        sent_slack.append((message, webhook))

    monkeypatch.setattr("app.core.finance._utc_today", lambda: date(2026, 3, 6))
    sent_whatsapp = []
    sent_slack = []
    monkeypatch.setattr("app.core.budget_events.send_whatsapp_alert", _fake_whatsapp)
    monkeypatch.setattr("app.core.budget_events.send_slack_alert", _fake_slack)

    fake_db = FakeBudgetEventsDB()

    created = asyncio.run(
        sync_budget_events_for_user(user_id="user-1", db=fake_db, deliver=True)
    )

    assert len(created) == 2
    assert {event["scope"] for event in created} == {"portfolio", "integration"}
    assert {event["event_type"] for event in created} == {"forecasted_over_budget"}
    assert len(fake_db.notifications) == 2
    assert len(sent_whatsapp) == 1
    assert len(sent_slack) == 1

    created_again = asyncio.run(
        sync_budget_events_for_user(user_id="user-1", db=fake_db, deliver=True)
    )

    assert created_again == []
    assert len(fake_db.budget_events) == 2


def test_sync_budget_events_for_user_records_recovered_transition(monkeypatch):
    monkeypatch.setattr("app.core.finance._utc_today", lambda: date(2026, 3, 6))
    fake_db = FakeBudgetEventsDB()

    asyncio.run(sync_budget_events_for_user(user_id="user-1", db=fake_db, deliver=False))

    fake_db.history_by_integration["int-aws"] = [
        {"spend_date": "2026-03-01", "amount": 5.0, "currency": "USD"},
        {"spend_date": "2026-03-02", "amount": 5.0, "currency": "USD"},
        {"spend_date": "2026-03-03", "amount": 5.0, "currency": "USD"},
        {"spend_date": "2026-03-04", "amount": 5.0, "currency": "USD"},
        {"spend_date": "2026-03-05", "amount": 5.0, "currency": "USD"},
        {"spend_date": "2026-03-06", "amount": 5.0, "currency": "USD"},
    ]

    recovered_events = asyncio.run(
        sync_budget_events_for_user(user_id="user-1", db=fake_db, deliver=False)
    )

    assert len(recovered_events) == 2
    assert {event["event_type"] for event in recovered_events} == {"recovered"}
    assert {event["current_status"] for event in recovered_events} == {"on_track"}
