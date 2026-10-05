from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import dashboard_summary_routes as summary_routes
from app.auth import ClerkUser, get_current_user
from app.core import cache
from app.core.finance import DEFAULT_USD_TO_INR_RATE
from app.db import get_db_client


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 31, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def isolated_summary(monkeypatch):
    monkeypatch.setattr(summary_routes, "datetime", FrozenDateTime)
    monkeypatch.setattr(cache, "redis_client", None)
    cache._local_cache.clear()
    yield
    cache._local_cache.clear()


def billing(status="fresh", **overrides):
    return {
        "status": status,
        "observed_at": "2026-08-31T10:00:00+00:00",
        "period_start": "2026-08-01",
        "reason": None,
        "retry_at": None,
        "resource_costs_available": True,
        "subscription_costs_available": True,
        "daily_costs_available": True,
        **overrides,
    }


def integration(id="azure-1", provider="azure", user_id="user-1", metadata=None, **overrides):
    return {"id": id, "provider": provider, "user_id": user_id, "status": "active", "metadata": metadata or {}, **overrides}


def spend(amount, spend_date="2026-08-05", integration_id="azure-1", user_id="user-1", currency="INR"):
    return {"user_id": user_id, "integration_id": integration_id, "spend_date": spend_date, "amount": amount, "currency": currency}


class SummaryDB:
    def __init__(self, integrations, rows):
        self.get_user_integrations = AsyncMock(side_effect=lambda user_id: [i for i in integrations if i["user_id"] == user_id])
        self.get_dashboard_stats = AsyncMock(return_value={"total_spend": 99999, "potential_savings": 20, "active_resources_count": 1})
        self.get_resources = AsyncMock(return_value=[{"integration_id": "azure-1", "cost": 88888}])
        def select(table, *, filters, limit=None):
            if table != "daily_spend_history":
                return []
            dates = filters["spend_date"]
            return [r for r in rows if r["user_id"] == filters["user_id"]
                    and r["integration_id"] == filters["integration_id"]
                    and dates["$gte"] <= r["spend_date"] < dates["$lt"]]

        self.select = AsyncMock(side_effect=select)


def client_for(db, user_id="user-1"):
    app = FastAPI()
    app.include_router(summary_routes.dashboard_summary_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id=user_id)
    app.dependency_overrides[get_db_client] = lambda: db
    return TestClient(app)


def summary(db):
    response = client_for(db).get("/api/dashboard/summary")
    assert response.status_code == 200, response.text
    return response.json()


def test_unavailable_mtd_never_substitutes_resources_or_stats():
    result = summary(SummaryDB([integration(metadata={"billing": billing("unavailable", daily_costs_available=False)})], []))
    assert result["stats"]["total_spend"] == 99999
    assert result["resources"][0]["cost"] == 88888
    assert result["provider_mtd_spend"][0]["amount"] is None
    assert result["mtd_spend"]["amount"] is None
    assert result["mtd_spend"]["status"] == "unavailable"


@pytest.mark.parametrize("status", ["stale", "unavailable"])
def test_failed_billing_refresh_preserves_current_month_history(status):
    metadata = billing(status, daily_costs_available=False, reason="Cost API throttled", retry_at="2026-08-31T15:00:00Z")
    result = summary(SummaryDB([integration(metadata={"billing": metadata})], [spend(240)]))
    actual = result["provider_mtd_spend"][0]
    assert actual["amount"] == 240
    assert actual["status"] == "stale"
    assert actual["observed_at"] == metadata["observed_at"]
    assert actual["retry_at"] == metadata["retry_at"]
    assert actual["reason"] == metadata["reason"]
    assert result["mtd_spend"]["amount"] == 240


@pytest.mark.parametrize("status", ["fresh", "cached"])
def test_successful_current_period_zero_is_known(status):
    result = summary(SummaryDB([integration(metadata={"billing": billing(status)})], [spend(0)]))
    actual = result["provider_mtd_spend"][0]
    assert actual["amount"] == 0
    assert actual["status"] == status
    assert actual["completeness"] == "complete"
    assert result["mtd_spend"]["amount"] == 0


@pytest.mark.parametrize("status", ["fresh", "cached", "stale", "unavailable"])
def test_empty_history_never_infers_zero_from_metadata(status):
    result = summary(SummaryDB([integration(metadata={"billing": billing(status)})], []))
    assert result["mtd_spend"]["amount"] is None
    assert result["mtd_spend"]["status"] == "unavailable"


@pytest.mark.parametrize("amount", [None, "", "NaN", "Infinity", False])
def test_invalid_persisted_amount_is_not_zero(amount):
    result = summary(SummaryDB([integration(metadata={"billing": billing()})], [spend(amount)]))
    assert result["mtd_spend"]["amount"] is None


def test_subscription_or_resource_availability_does_not_confirm_daily_zero():
    result = summary(SummaryDB([integration(metadata={"billing": billing(daily_costs_available=False)})], []))
    assert result["mtd_spend"]["amount"] is None


@pytest.mark.parametrize("metadata", [{}, {"billing": billing("cached", period_start="2026-07-01")}])
def test_old_month_history_is_not_mtd(metadata):
    result = summary(SummaryDB([integration(metadata=metadata)], [spend(700, "2026-07-31")]))
    assert result["provider_mtd_spend"][0]["amount"] is None
    assert result["provider_mtd_spend"][0]["status"] == "unavailable"
    assert result["mtd_spend"]["period_start"] == "2026-08-01"


def test_calendar_month_includes_all_31_days_and_excludes_other_months():
    rows = [spend(1, f"2026-08-{day:02}") for day in range(1, 32)]
    rows.append(spend(500, "2026-07-31"))
    result = summary(SummaryDB([integration(metadata={"billing": billing()})], rows))
    assert result["mtd_spend"]["amount"] == 31
    assert len(result["spend_history"]) == 30


def test_future_rows_are_not_month_to_date():
    actual = summary_routes._integration_mtd_spend(integration(), [spend(20), spend(80, "2026-08-25")], datetime(2026, 8, 10).date())
    assert actual.amount == 20


@pytest.mark.parametrize("rows, expected", [([], None), ([spend(0)], 0), ([spend(72)], 72)])
def test_legacy_metadata_uses_history_without_inventing_freshness(rows, expected):
    result = summary(SummaryDB([integration()], rows))
    assert result["mtd_spend"]["amount"] == expected
    assert result["mtd_spend"]["observed_at"] is None
    assert result["mtd_spend"]["status"] == ("known" if rows else "unavailable")


def test_incomplete_provider_and_portfolio_do_not_show_partial_sum_as_total():
    db = SummaryDB([integration(), integration(id="azure-2"), integration(id="aws-1", provider="aws")], [spend(25), spend(75, integration_id="aws-1")])
    result = summary(db)
    azure, aws = result["provider_mtd_spend"]
    assert azure["amount"] is None
    assert azure["completeness"] == "partial"
    assert aws["amount"] == 75
    assert result["mtd_spend"]["amount"] is None
    assert result["mtd_spend"]["completeness"] == "partial"


def test_complete_provider_sum_uses_finance_inr_convention_once():
    db = SummaryDB(
        [integration(metadata={"billing": billing()}), integration(id="azure-2", metadata={"billing": billing("cached", observed_at="2026-08-31T09:00:00+00:00")}), integration(id="gcp-1", provider="gcp")],
        [spend(2, currency="USD"), spend(10, integration_id="azure-2"), spend(5, integration_id="gcp-1")],
    )
    result = summary(db)
    azure = result["provider_mtd_spend"][0]
    assert azure["amount"] == round(2 * DEFAULT_USD_TO_INR_RATE + 10, 2)
    assert azure["currency"] == "INR"
    assert azure["status"] == "cached"
    assert azure["observed_at"] == "2026-08-31T09:00:00+00:00"
    assert result["mtd_spend"]["amount"] == round(azure["amount"] + 5, 2)
    assert result["mtd_spend"]["observed_at"] is None


def test_billing_reads_and_cache_are_tenant_scoped_and_ignore_inactive_integrations():
    db = SummaryDB(
        [integration(), integration(id="inactive", status="inactive"), integration(id="other", user_id="user-2")],
        [spend(10), spend(900, integration_id="inactive"), spend(800, integration_id="other", user_id="user-2"), spend(700, user_id="user-2")],
    )
    assert summary(db)["mtd_spend"]["amount"] == 10
    assert client_for(db, "user-2").get("/api/dashboard/summary").json()["mtd_spend"]["amount"] == 800
    history_filters = [call.kwargs["filters"] for call in db.select.await_args_list if call.args[0] == "daily_spend_history"]
    assert [(item["user_id"], item["integration_id"]) for item in history_filters] == [("user-1", "azure-1"), ("user-2", "other")]
    assert all(item["spend_date"] == {"$gte": "2026-08-01", "$lt": "2026-09-01"} for item in history_filters)
    assert all(call.kwargs["filters"]["user_id"] in {"user-1", "user-2"} for call in db.select.await_args_list)


def test_no_integrations_is_unavailable_not_fake_zero():
    result = summary(SummaryDB([], []))
    assert result["provider_mtd_spend"] == []
    assert result["mtd_spend"]["amount"] is None


def test_summary_read_failure_returns_safe_error():
    db = SummaryDB([integration()], [])
    db.get_user_integrations.side_effect = RuntimeError("private database detail")
    response = client_for(db).get("/api/dashboard/summary")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to load dashboard summary"}


def test_history_database_failure_does_not_return_fresh_zero():
    db = SummaryDB([integration(metadata={"billing": billing()})], [])
    db.select.side_effect = RuntimeError("private database detail")
    response = client_for(db).get("/api/dashboard/summary")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to load dashboard summary"}


@pytest.mark.parametrize("status", ["fresh", "cached"])
@pytest.mark.parametrize("observed_at, expired", [("2026-08-31T06:00:00Z", True), ("2026-08-31T06:00:01Z", False), (None, True)])
def test_freshness_expires_using_coordinator_six_hour_ttl(status, observed_at, expired):
    result = summary(SummaryDB([integration(metadata={"billing": billing(status, observed_at=observed_at)})], [spend(30)]))
    assert result["mtd_spend"]["amount"] == 30
    assert result["mtd_spend"]["status"] == ("stale" if expired else status)
    assert result["mtd_spend"]["as_of"] == "2026-08-31T12:00:00+00:00"


@pytest.mark.parametrize("row_fields, expected", [
    ({"metadata": {"billing": billing(observed_at="2026-08-30T10:00:00Z")}, "updated_at": "2026-08-31T11:00:00Z"}, "2026-08-30T10:00:00+00:00"),
    ({"updated_at": "2026-08-29T10:00:00Z", "created_at": "2026-08-28T10:00:00Z"}, "2026-08-29T10:00:00+00:00"),
    ({"created_at": "2026-08-28T10:00:00Z"}, "2026-08-28T10:00:00+00:00"),
    ({"created_at": "invalid"}, None),
    ({"created_at": "2026-08-31T13:00:00Z"}, None),
    ({"created_at": "2026-08-30T10:00:00"}, None),
    ({"metadata": {"billing": billing(period_start="2026-07-01")}, "updated_at": "2026-08-31T11:00:00Z"}, None),
    ({"created_at": "2026-07-28T10:00:00Z"}, None),
])
def test_failed_integration_billing_recovers_only_valid_current_period_row_timestamps(row_fields, expected):
    result = summary(SummaryDB(
        [integration(metadata={"billing": billing("unavailable", observed_at=None)})],
        [{**spend(40), **row_fields}],
    ))
    assert result["mtd_spend"]["amount"] == 40
    assert result["mtd_spend"]["status"] == "stale"
    assert result["mtd_spend"]["observed_at"] == expected
