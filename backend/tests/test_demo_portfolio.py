from datetime import datetime, timezone

from app.core.demo_portfolio import (
    LEGACY_DEMO_DATA_OWNER_ID,
    build_demo_portfolio_bundle,
)


def _fixed_now() -> datetime:
    return datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)


def test_build_demo_portfolio_bundle_aligns_stats_with_resources_and_notifications():
    now = _fixed_now()
    bundle = build_demo_portfolio_bundle(
        LEGACY_DEMO_DATA_OWNER_ID,
        now=now,
        today=now.date(),
    )

    total_resource_spend = round(
        sum(float(resource.get("cost") or 0.0) for resource in bundle["resources"]),
        2,
    )
    total_stat_spend = round(
        sum(float(stat.get("total_spend") or 0.0) for stat in bundle["dashboard_stats"]),
        2,
    )
    total_pending_savings = round(
        sum(
            float(notification["metadata"].get("estimated_savings") or 0.0)
            for notification in bundle["notifications"]
            if str(notification.get("status") or "").lower() == "pending"
            and isinstance(notification.get("metadata"), dict)
        ),
        2,
    )
    total_stat_savings = round(
        sum(float(stat.get("potential_savings") or 0.0) for stat in bundle["dashboard_stats"]),
        2,
    )

    assert len(bundle["integrations"]) == 4
    assert total_stat_spend == total_resource_spend
    assert total_stat_savings == total_pending_savings
    assert len(bundle["reports"]) == 4
    assert len(bundle["audit_logs"]) >= 4


def test_build_demo_portfolio_bundle_keeps_current_month_history_forecast_ready():
    now = _fixed_now()
    bundle = build_demo_portfolio_bundle(
        LEGACY_DEMO_DATA_OWNER_ID,
        now=now,
        today=now.date(),
    )

    current_month_prefix = "2026-04"
    for integration_id, rows in bundle["daily_spend_history_by_integration"].items():
        current_month_rows = [
            row for row in rows if str(row.get("spend_date") or "").startswith(current_month_prefix)
        ]
        assert len(current_month_rows) >= 5, integration_id

    assert bundle["portfolio_forecast"]["status"] != "insufficient_history"
    assert bundle["portfolio_forecast"]["forecast_eom_spend"] > 0


def test_build_demo_portfolio_bundle_includes_governance_and_budget_contracts():
    now = _fixed_now()
    bundle = build_demo_portfolio_bundle(
        LEGACY_DEMO_DATA_OWNER_ID,
        now=now,
        today=now.date(),
    )

    assert bundle["budget_events"]
    assert all(
        event["event_type"] in {"approaching_budget", "forecasted_over_budget", "over_budget"}
        for event in bundle["budget_events"]
    )
    assert all(event["current_status"] == event["event_type"] for event in bundle["budget_events"])
    assert any("governance_data" in record for record in bundle["scan_history"])
    assert bundle["waste_distribution"]
