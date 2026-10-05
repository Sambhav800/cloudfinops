from datetime import date, datetime, timezone

import pytest

from app.core.reports import (
    build_report_record,
    resolve_report_period,
    resolve_scheduled_report_plan,
)


def test_resolve_report_period_defaults_to_current_month(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 18))

    period_start, period_end = resolve_report_period(period_start=None, period_end=None)

    assert period_start == date(2026, 3, 1)
    assert period_end == date(2026, 3, 18)


def test_resolve_scheduled_report_plan_for_weekly_uses_current_month_to_date():
    plan = resolve_scheduled_report_plan("weekly", today=date(2026, 3, 16))

    assert plan == {
        "cadence": "weekly",
        "report_type": "monthly_executive_summary",
        "period_start": date(2026, 3, 1),
        "period_end": date(2026, 3, 16),
    }


def test_resolve_scheduled_report_plan_for_monthly_uses_previous_calendar_month():
    plan = resolve_scheduled_report_plan("monthly", today=date(2026, 4, 1))

    assert plan == {
        "cadence": "monthly",
        "report_type": "board_pack",
        "period_start": date(2026, 3, 1),
        "period_end": date(2026, 3, 31),
    }


def test_resolve_scheduled_report_plan_manual_returns_none():
    assert resolve_scheduled_report_plan("manual", today=date(2026, 3, 16)) is None


def test_build_report_record_aggregates_accounts_and_providers():
    report = build_report_record(
        user_id="user-1",
        report_type="provider_spend_summary",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 6),
        integrations=[
            {"id": "int-aws", "provider": "aws", "name": "Prod AWS", "status": "active", "monthly_budget_limit": 300.0},
            {"id": "int-gcp", "provider": "gcp", "name": "Prod GCP", "status": "active", "monthly_budget_limit": 200.0},
        ],
        history_by_integration={
            "int-aws": [
                {"spend_date": "2026-03-01", "amount": 20.0, "currency": "INR"},
                {"spend_date": "2026-03-02", "amount": 21.0, "currency": "INR"},
                {"spend_date": "2026-03-03", "amount": 22.0, "currency": "INR"},
                {"spend_date": "2026-03-04", "amount": 23.0, "currency": "INR"},
                {"spend_date": "2026-03-05", "amount": 24.0, "currency": "INR"},
                {"spend_date": "2026-03-06", "amount": 25.0, "currency": "INR"},
            ],
            "int-gcp": [
                {"spend_date": "2026-03-01", "amount": 10.0, "currency": "INR"},
                {"spend_date": "2026-03-02", "amount": 11.0, "currency": "INR"},
                {"spend_date": "2026-03-03", "amount": 12.0, "currency": "INR"},
                {"spend_date": "2026-03-04", "amount": 13.0, "currency": "INR"},
                {"spend_date": "2026-03-05", "amount": 14.0, "currency": "INR"},
                {"spend_date": "2026-03-06", "amount": 15.0, "currency": "INR"},
            ],
        },
        generated_at=datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc),
    )

    assert report["status"] == "ready"
    assert report["title"] == "Provider Spend Summary - Mar 2026"
    assert report["file_size_bytes"] > 0
    assert report["data"]["portfolio"]["actual_period_spend"] == 210.0
    assert report["data"]["provider_breakdown"][0]["provider"] == "aws"
    assert report["data"]["provider_breakdown"][0]["actual_period_spend"] == 135.0
    assert report["data"]["accounts"][0]["name"] == "Prod AWS"
    assert report["data"]["readiness"]["ready_accounts"] == 2


def test_build_report_record_marks_attention_needed_for_thin_history():
    report = build_report_record(
        user_id="user-1",
        report_type="monthly_executive_summary",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 3),
        integrations=[
            {"id": "int-aws", "provider": "aws", "name": "Prod AWS", "status": "active", "monthly_budget_limit": 300.0},
        ],
        history_by_integration={
            "int-aws": [
                {"spend_date": "2026-03-01", "amount": 20.0, "currency": "INR"},
                {"spend_date": "2026-03-02", "amount": 21.0, "currency": "INR"},
                {"spend_date": "2026-03-03", "amount": 22.0, "currency": "INR"},
            ],
        },
    )

    assert report["status"] == "attention_needed"
    assert "enough spend history" in report["summary"]


def test_resolve_report_period_rejects_future_end_date(monkeypatch):
    monkeypatch.setattr("app.core.reports._utc_today", lambda: date(2026, 3, 18))

    with pytest.raises(ValueError, match="future"):
        resolve_report_period(period_start="2026-03-01", period_end="2026-03-20")
