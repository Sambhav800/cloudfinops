from datetime import date

import pytest

from app.core.finance import (
    aggregate_daily_spend_rows,
    build_account_forecast_drivers,
    build_forecast_summary,
    normalize_finance_settings,
    redact_finance_settings_for_audit,
    redact_integration_settings_for_audit,
)


def test_aggregate_daily_spend_rows_merges_same_day_amounts_and_breakdowns():
    aggregated = aggregate_daily_spend_rows(
        [
            {
                "spend_date": "2026-03-10",
                "amount": 12.5,
                "currency": "INR",
                "service_breakdown": {"EC2": 10, "S3": 2.5},
            },
            {
                "spend_date": "2026-03-10T05:00:00Z",
                "amount": "7.5",
                "currency": "INR",
                "service_breakdown": {"EC2": 3, "Lambda": 4.5},
            },
            {
                "spend_date": "2026-03-11",
                "amount": 5,
                "currency": "INR",
                "service_breakdown": {"CloudSQL": 5},
            },
        ]
    )

    assert aggregated == [
        {
            "spend_date": "2026-03-10",
            "amount": 20.0,
            "currency": "INR",
            "service_breakdown": {"EC2": 13.0, "S3": 2.5, "Lambda": 4.5},
        },
        {
            "spend_date": "2026-03-11",
            "amount": 5.0,
            "currency": "INR",
            "service_breakdown": {"CloudSQL": 5.0},
        },
    ]


def test_build_forecast_summary_flags_forecasted_over_budget():
    history_rows = [
        {"spend_date": "2026-03-01", "amount": 20, "currency": "INR"},
        {"spend_date": "2026-03-02", "amount": 21, "currency": "INR"},
        {"spend_date": "2026-03-03", "amount": 22, "currency": "INR"},
        {"spend_date": "2026-03-04", "amount": 23, "currency": "INR"},
        {"spend_date": "2026-03-05", "amount": 24, "currency": "INR"},
        {"spend_date": "2026-03-06", "amount": 25, "currency": "INR"},
    ]

    summary = build_forecast_summary(
        history_rows,
        budget_limit=400.0,
        budget_source="portfolio_sum",
        scope="portfolio",
        as_of=date(2026, 3, 6),
    )

    assert summary["status"] == "forecasted_over_budget"
    assert summary["currency"] == "INR"
    assert summary["budget_source"] == "portfolio_sum"
    assert summary["actual_mtd_spend"] == 135.0
    assert summary["forecast_eom_spend"] > 400.0
    assert summary["variance_amount"] > 0
    assert summary["message"] == "Forecasted month-end spend is above the configured budget."


def test_mixed_usd_and_inr_history_converts_once_and_preserves_service_totals(monkeypatch):
    monkeypatch.setattr("app.core.finance.DEFAULT_USD_TO_INR_RATE", 80.0)
    rows = [
        {"spend_date": "2026-03-10", "amount": 2, "currency": "USD", "service_breakdown": {"EC2": 2}},
        {"spend_date": "2026-03-10", "amount": 40, "currency": "INR", "service_breakdown": {"S3": 40}},
    ]
    expected = [{
        "spend_date": "2026-03-10", "amount": 200.0, "currency": "INR",
        "service_breakdown": {"EC2": 160.0, "S3": 40.0},
    }]
    assert aggregate_daily_spend_rows(rows) == expected
    assert aggregate_daily_spend_rows(expected) == expected


@pytest.mark.parametrize("rows,expected", [
    ([], []),
    ([{"spend_date": "2026-03-10", "amount": 0, "currency": "USD"}], [
        {"spend_date": "2026-03-10", "amount": 0, "currency": "INR", "service_breakdown": {}},
    ]),
])
def test_history_aggregation_handles_empty_and_zero_without_provisional_spend(rows, expected):
    assert aggregate_daily_spend_rows(rows) == expected


@pytest.mark.parametrize("budget", [None, 0, 1000.0])
def test_empty_forecast_keeps_the_configured_budget_currency(budget):
    summary = build_forecast_summary(
        [], budget_limit=budget, budget_source="portfolio_setting", scope="portfolio", as_of=date(2026, 3, 6),
    )
    assert summary["currency"] == "INR"
    assert summary["status"] == "insufficient_history"
    assert summary["budget_limit"] == budget
    assert summary["actual_mtd_spend"] == summary["forecast_eom_spend"] == 0
    assert summary["history_days_used"] == 0


def test_usd_spend_is_compared_to_an_inr_budget_without_converting_the_budget(monkeypatch):
    monkeypatch.setattr("app.core.finance.DEFAULT_USD_TO_INR_RATE", 80.0)
    summary = build_forecast_summary(
        [{"spend_date": f"2026-03-0{day}", "amount": 1, "currency": "USD"} for day in range(1, 7)],
        budget_limit=1000.0, budget_source="portfolio_setting", scope="portfolio", as_of=date(2026, 3, 6),
    )
    assert summary["currency"] == "INR"
    assert summary["actual_mtd_spend"] == 480.0
    assert summary["forecast_eom_spend"] == 2480.0
    assert summary["budget_limit"] == 1000.0
    assert summary["status"] == "forecasted_over_budget"


def test_build_forecast_summary_returns_insufficient_history_for_short_series():
    summary = build_forecast_summary(
        [
            {"spend_date": "2026-03-01", "amount": 15, "currency": "INR"},
            {"spend_date": "2026-03-02", "amount": 16, "currency": "INR"},
            {"spend_date": "2026-03-03", "amount": 17, "currency": "INR"},
            {"spend_date": "2026-03-04", "amount": 18, "currency": "INR"},
        ],
        budget_limit=200.0,
        budget_source="integration",
        scope="integration",
        integration_id="int-1",
        as_of=date(2026, 3, 4),
    )

    assert summary["status"] == "insufficient_history"
    assert summary["forecast_method"] == "insufficient_history"
    assert summary["forecast_stable"] is False
    assert summary["forecast_eom_spend"] == 66.0


def test_build_forecast_summary_uses_custom_warning_threshold():
    history_rows = [
        {"spend_date": "2026-03-01", "amount": 10, "currency": "INR"},
        {"spend_date": "2026-03-02", "amount": 10, "currency": "INR"},
        {"spend_date": "2026-03-03", "amount": 10, "currency": "INR"},
        {"spend_date": "2026-03-04", "amount": 10, "currency": "INR"},
        {"spend_date": "2026-03-05", "amount": 10, "currency": "INR"},
    ]

    summary = build_forecast_summary(
        history_rows,
        budget_limit=400.0,
        budget_source="portfolio_setting",
        scope="portfolio",
        as_of=date(2026, 3, 5),
        warning_threshold_pct=75.0,
    )

    assert summary["forecast_eom_spend"] == 310.0
    assert summary["status"] == "approaching_budget"
    assert summary["message"] == "Forecasted month-end spend is approaching the configured budget."


def test_build_account_forecast_drivers_returns_top_remaining_spend_accounts():
    drivers = build_account_forecast_drivers(
        [
            {
                "name": "Prod AWS",
                "provider": "aws",
                "actual_mtd_spend": 150.0,
                "forecast_eom_spend": 310.0,
                "forecast_status": "forecasted_over_budget",
            },
            {
                "name": "Analytics GCP",
                "provider": "gcp",
                "actual_mtd_spend": 80.0,
                "forecast_eom_spend": 140.0,
                "forecast_status": "approaching_budget",
            },
            {
                "name": "Archive Azure",
                "provider": "azure",
                "actual_mtd_spend": 50.0,
                "forecast_eom_spend": 50.0,
                "forecast_status": "on_track",
            },
        ]
    )

    assert drivers == [
        {"dimension": "Account", "key": "Prod AWS (AWS)", "delta_amount": 160.0},
        {"dimension": "Account", "key": "Analytics GCP (GCP)", "delta_amount": 60.0},
    ]


def test_redact_integration_settings_for_audit_masks_sensitive_delivery_fields():
    redacted = redact_integration_settings_for_audit(
        {
            "monthly_budget_limit": 500.0,
            "alert_email": "owner@example.com",
            "alert_phone_number": "+1 (415) 555-0119",
            "alert_slack_webhook": "https://hooks.slack.com/services/T000/B000/secret",
        }
    )

    assert redacted == {
        "monthly_budget_limit": 500.0,
        "alert_email": "owner@example.com",
        "alert_phone_number": "***0119",
        "alert_slack_webhook": "configured",
    }


def test_normalize_finance_settings_cleans_budget_recipients_and_thresholds():
    normalized = normalize_finance_settings(
        {
            "portfolio_budget_limit": "17000.259",
            "report_recipients": [
                " FINANCE@Example.com ",
                "invalid",
                "cto@example.com",
                "finance@example.com",
            ],
            "report_cadence": "monthly",
            "alert_thresholds": {
                "warning_pct": 75,
                "critical_pct": 90,
            },
        }
    )

    assert normalized == {
        "portfolio_budget_limit": 17000.26,
        "report_recipients": ["finance@example.com", "cto@example.com"],
        "report_cadence": "monthly",
        "alert_thresholds": {
            "warning_pct": 75.0,
            "critical_pct": 100.0,
        },
    }


def test_redact_finance_settings_for_audit_hides_recipient_list():
    redacted = redact_finance_settings_for_audit(
        {
            "portfolio_budget_limit": 12000.0,
            "report_recipients": ["finance@example.com", "cto@example.com"],
            "report_cadence": "weekly",
            "alert_thresholds": {"warning_pct": 82.0, "critical_pct": 100.0},
        }
    )

    assert redacted == {
        "portfolio_budget_limit": 12000.0,
        "report_recipients": {"count": 2},
        "report_cadence": "weekly",
        "alert_thresholds": {"warning_pct": 82.0, "critical_pct": 100.0},
    }
