import asyncio
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.scanners.azure import AzureWasteScanner


USER_ID = "user-azure"
INTEGRATION_ID = "integration-azure"
OBSERVED_AT = "2026-09-14T09:00:00+00:00"
PERIOD_START = "2026-09-01"


class ScanClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 15, 12, tzinfo=timezone.utc)


def snapshot(status="fresh", total=200.0):
    available = status in {"fresh", "cached"}
    return {
        "resource_costs": ({"/subscriptions/sub/vm/one": {
            "actual_cost_mtd": 40.0, "period_start": PERIOD_START, "observed_at": OBSERVED_AT,
        }} if available else {}),
        "subscription_costs": {
            "total": total,
            "by_service": {"Virtual Machines": total},
            "daily_totals": [{"date": "2026-09-14", "amount": total}],
            "currency": "USD",
        },
        "billing": {
            "status": status,
            "observed_at": OBSERVED_AT if status != "unavailable" else None,
            "period_start": PERIOD_START,
            "reason": None if available else "rate_limited",
            "retry_at": None if available else "2026-09-15T12:30:00+00:00",
            "resource_costs_available": available,
            "subscription_costs_available": available,
            "daily_costs_available": available,
        },
    }


def resource(cost=40.0, source="actual", **overrides):
    return {
        "id": "resource-one",
        "user_id": USER_ID,
        "integration_id": INTEGRATION_ID,
        "provider": "azure",
        "cloud_resource_id": "/subscriptions/sub/vm/one",
        "resource_name": "one",
        "service_type": "Virtual Machine",
        "status": "Active",
        "cost": cost,
        "metadata": {
            "cost_source": source,
            "cost_observed_at": OBSERVED_AT,
            "cost_period_start": PERIOD_START,
        },
        **overrides,
    }


@pytest.fixture
def scan_env(monkeypatch):
    state = SimpleNamespace(
        snapshot=snapshot(),
        findings=[resource()],
        prior_resources=[],
        prior_stats=None,
        persisted_resources=None,
        daily_rows={"2026-08-31": {"amount": 91.0}},
    )
    db = MagicMock()
    db.create_scan_history = AsyncMock(return_value="scan-azure")
    db.get_resources = AsyncMock(side_effect=lambda *args: deepcopy(
        state.prior_resources if state.persisted_resources is None else state.persisted_resources
    ))
    db.get_dashboard_stats = AsyncMock(side_effect=lambda *args: deepcopy(state.prior_stats))

    def persist_resources(rows, batch_size=50):
        state.persisted_resources = deepcopy(rows)
        return len(rows)

    def upsert(table, data):
        if table == "daily_spend_history":
            for row in data:
                state.daily_rows[row["spend_date"]] = deepcopy(row)
        return deepcopy(data)

    db.bulk_upsert_resources = AsyncMock(side_effect=persist_resources)
    db.upsert = AsyncMock(side_effect=upsert)
    db.select = AsyncMock(return_value=[])
    for method in (
        "delete_resources_for_integration", "upsert_dashboard_stats", "delete",
        "create_notifications", "update", "update_integration",
        "complete_scan_history", "fail_scan_history", "save_daily_spend_history",
    ):
        setattr(db, method, AsyncMock())
    state.db = db

    scanner = MagicMock()

    def scan_all(*, billing_snapshot):
        assert billing_snapshot == state.snapshot
        scanner._scan_summary = deepcopy(billing_snapshot)
        return deepcopy(state.findings)

    scanner.scan_all.side_effect = scan_all
    state.scanner = scanner
    azure = ModuleType("app.scanners.azure")
    azure.AzureWasteScanner = MagicMock(return_value=scanner)
    monkeypatch.setitem(sys.modules, "app.scanners.azure", azure)
    refresh = ModuleType("app.core.azure_billing_refresh")
    refresh.refresh_azure_billing = AsyncMock(side_effect=lambda *args, **kwargs: deepcopy(state.snapshot))
    state.refresh = refresh.refresh_azure_billing
    monkeypatch.setitem(sys.modules, "app.core.azure_billing_refresh", refresh)
    optimization = ModuleType("app.optimization.scan_integration")
    optimization.run_optimization_pipeline = AsyncMock(return_value={})
    state.optimize = optimization.run_optimization_pipeline
    monkeypatch.setitem(sys.modules, "app.optimization.scan_integration", optimization)
    compliance = ModuleType("app.governance.compliance_engine")
    compliance.ComplianceEngine = MagicMock(return_value=SimpleNamespace(evaluate_and_save=AsyncMock()))
    monkeypatch.setitem(sys.modules, "app.governance.compliance_engine", compliance)
    monkeypatch.setattr("app.core.exchange_rates.get_exchange_rates", AsyncMock(return_value={"USD": 1.0}))
    monkeypatch.setattr(routes, "datetime", ScanClock)
    monkeypatch.setattr(routes, "decrypt_integration_credentials", lambda integration: {
        "tenant_id": "tenant", "client_id": "client", "client_secret": "test-secret",
        "subscription_id": "sub",
    })
    for method in (
        "send_scan_progress", "send_scan_complete", "_sync_commitments_after_scan",
        "_apply_catalog_estimates_for_scan", "_apply_community_estimates_for_scan",
        "_contribute_community_prices_for_scan", "generate_exclusion_suggestions",
    ):
        monkeypatch.setattr(routes, method, AsyncMock())
    monkeypatch.setattr(routes, "apply_exclusion_shields", AsyncMock(return_value=(0, 0)))
    state.integration = {
        "id": INTEGRATION_ID, "provider": "azure", "name": "Azure Test",
        "metadata": {"existing": "keep", "last_mtd_cost": 180.0},
    }
    return state


def run(state):
    asyncio.run(routes.run_scan(state.integration, USER_ID, state.db))
    state.db.fail_scan_history.assert_not_awaited()
    routes.send_scan_complete.assert_awaited_once()


def saved_stats(state):
    return state.db.upsert_dashboard_stats.call_args.args[0]


def saved_integration_metadata(state):
    metadata = deepcopy(state.integration["metadata"])
    for call in state.db.update.call_args_list:
        if call.args[0] == "cloud_integrations":
            assert "metadata" not in call.args[1]
            assert call.args[2] == {"id": INTEGRATION_ID, "user_id": USER_ID}
            metadata.update({
                key.removeprefix("metadata."): value for key, value in call.args[1].items()
                if key.startswith("metadata.")
            })
    return metadata


@pytest.mark.parametrize("status", ["stale", "unavailable"])
def test_failed_refresh_preserves_actual_costs_and_dashboard_total(scan_env, status):
    state = scan_env
    state.snapshot = snapshot(status, total=0)
    state.prior_resources = [resource(cost=85.0)]
    state.prior_stats = {"total_spend": 300.0, "metadata": {"keep": "value"}}
    state.findings = [resource(cost=0, source="billing_unavailable")]
    run(state)

    row = state.persisted_resources[0]
    assert row["cost"] == 85.0
    assert row["metadata"]["cost_source"] == "billing_stale"
    assert row["metadata"]["cost_observed_at"] == OBSERVED_AT
    assert row["metadata"]["cost_period_start"] == PERIOD_START
    assert saved_stats(state)["total_spend"] == 300.0
    assert saved_stats(state)["metadata"]["billing"] == state.snapshot["billing"]
    assert saved_stats(state)["metadata"]["keep"] == "value"
    metadata = saved_integration_metadata(state)
    assert metadata["last_mtd_cost"] == 180.0
    assert metadata["billing"] == state.snapshot["billing"]
    assert metadata["existing"] == "keep"
    assert state.db.complete_scan_history.call_args.kwargs["scan_metadata"]["billing"] == state.snapshot["billing"]
    assert state.daily_rows == {"2026-08-31": {"amount": 91.0}}
    state.db.save_daily_spend_history.assert_not_awaited()
    routes._apply_catalog_estimates_for_scan.assert_not_awaited()
    routes._apply_community_estimates_for_scan.assert_not_awaited()
    routes._contribute_community_prices_for_scan.assert_not_awaited()
    assert state.optimize.call_args.kwargs["findings"][0]["cost"] == 85.0


@pytest.mark.parametrize("status", ["fresh", "cached"])
@pytest.mark.parametrize("total", [200.0, 0.0])
def test_verified_subscription_total_including_zero_never_uses_findings(scan_env, status, total):
    state = scan_env
    state.snapshot = snapshot(status, total)
    state.prior_resources = [resource(cost=85)]
    state.prior_stats = {"total_spend": 300.0}
    run(state)

    state.refresh.assert_awaited_once_with(state.scanner, db=state.db, user_id=USER_ID, subscription_id="sub")
    state.scanner.scan_all.assert_called_once_with(billing_snapshot=state.snapshot)
    assert saved_stats(state)["total_spend"] == total
    assert state.persisted_resources[0]["cost"] == 40.0
    metadata = saved_integration_metadata(state)
    assert metadata["last_mtd_cost"] == total
    assert metadata["last_mtd_cost_period_start"] == PERIOD_START
    assert state.daily_rows["2026-09-14"]["amount"] == total
    assert state.daily_rows["2026-08-31"] == {"amount": 91.0}
    state.db.save_daily_spend_history.assert_not_awaited()


def test_empty_successful_zero_is_not_billing_unavailable(scan_env):
    state = scan_env
    state.findings = []
    state.snapshot = snapshot("fresh", 0.0)
    state.snapshot["resource_costs"] = {}
    state.snapshot["subscription_costs"]["daily_totals"] = []
    run(state)

    assert saved_stats(state)["total_spend"] == 0.0
    assert saved_stats(state)["metadata"]["billing"]["status"] == "fresh"
    state.db.delete_resources_for_integration.assert_not_awaited()


@pytest.mark.parametrize("findings", [[], [resource(cost=0, source="billing_unavailable")]])
def test_no_prior_billing_is_unknown_not_zero(scan_env, findings):
    state = scan_env
    state.snapshot = snapshot("unavailable", 0.0)
    state.findings = findings
    state.integration["metadata"].pop("last_mtd_cost")
    run(state)

    assert saved_stats(state)["total_spend"] is None
    assert "last_mtd_cost" not in saved_integration_metadata(state)


def test_month_rollover_retains_old_cost_as_last_known_not_current_mtd(scan_env):
    state = scan_env
    state.snapshot = snapshot("stale", 900.0)
    state.snapshot["billing"]["period_start"] = "2026-08-01"
    state.snapshot["billing"]["observed_at"] = "2026-08-31T18:00:00+00:00"
    state.prior_resources = [resource(cost=85, metadata={
        "cost_source": "actual", "cost_observed_at": "2026-08-31T18:00:00+00:00",
        "cost_period_start": "2026-08-01",
    })]
    state.prior_stats = {"total_spend": 300.0}
    state.findings = [resource(cost=0, source="billing_unavailable")]
    state.integration["metadata"]["last_mtd_cost_period_start"] = "2026-08-01"
    run(state)

    row = state.persisted_resources[0]
    assert row["cost"] == 0
    assert row["metadata"]["cost_source"] == "billing_unavailable"
    assert row["metadata"]["cost_period_start"] == PERIOD_START
    assert row["metadata"]["cost_observed_at"] is None
    assert row["metadata"]["last_known_cost"] == {
        "amount": 85.0, "period_start": "2026-08-01", "observed_at": "2026-08-31T18:00:00+00:00",
    }
    assert state.optimize.call_args.kwargs["findings"][0]["cost"] == 0
    assert saved_stats(state)["total_spend"] == 300.0
    metadata = saved_integration_metadata(state)
    assert metadata["last_mtd_cost"] == 180.0
    assert metadata["last_mtd_cost_period_start"] == "2026-08-01"
    assert state.daily_rows == {"2026-08-31": {"amount": 91.0}}


def test_resource_preservation_matches_all_three_scope_keys(scan_env):
    state = scan_env
    state.snapshot = snapshot("unavailable")
    state.prior_resources = [
        resource(cost=800, user_id="other-user"),
        resource(cost=900, integration_id="other-integration"),
        resource(cost=700, cloud_resource_id="/subscriptions/sub/vm/other"),
        resource(cost=600, source="market_estimate"),
    ]
    state.findings = [resource(cost=0, source="billing_unavailable")]
    run(state)

    assert state.persisted_resources[0]["cost"] == 0
    assert state.persisted_resources[0]["metadata"]["cost_source"] == "billing_unavailable"
    state.db.get_resources.assert_any_await(USER_ID, INTEGRATION_ID)


def test_daily_history_availability_independent_of_subscription_total(scan_env):
    state = scan_env
    state.snapshot["billing"]["daily_costs_available"] = False
    run(state)
    assert saved_stats(state)["total_spend"] == 200.0
    assert state.daily_rows == {"2026-08-31": {"amount": 91.0}}


def test_daily_history_upserts_are_batched_and_scoped(scan_env):
    state = scan_env
    start = datetime(2026, 7, 1)
    state.snapshot["subscription_costs"]["daily_totals"] = [
        {"date": (start + timedelta(days=index)).date().isoformat(), "amount": float(index)}
        for index in range(65)
    ]
    run(state)

    batches = [call.args[1] for call in state.db.upsert.call_args_list if call.args[0] == "daily_spend_history"]
    assert [len(batch) for batch in batches] == [50, 15]
    assert all(row["user_id"] == USER_ID and row["integration_id"] == INTEGRATION_ID for batch in batches for row in batch)
    assert all(call.args[0] != "daily_spend_history" for call in state.db.delete.call_args_list)


@pytest.mark.parametrize("source", ["actual", "billing_stale"])
def test_previous_verified_zero_and_original_timestamp_survive_another_failure(scan_env, source):
    state = scan_env
    state.snapshot = snapshot("unavailable", 0)
    state.prior_resources = [resource(cost=0, source=source)]
    state.prior_stats = {"total_spend": 0}
    state.findings = [resource(cost=99, source="billing_unavailable")]
    run(state)
    assert state.persisted_resources[0]["cost"] == 0
    assert state.persisted_resources[0]["metadata"]["cost_source"] == "billing_stale"
    assert state.persisted_resources[0]["metadata"]["cost_observed_at"] == OBSERVED_AT
    assert saved_stats(state)["total_spend"] == 0
    assert saved_stats(state)["active_resources_count"] == 1


def test_fresh_zero_resource_overwrites_previous_nonzero_actual(scan_env):
    state = scan_env
    state.snapshot = snapshot("fresh", 0)
    state.snapshot["resource_costs"]["/subscriptions/sub/vm/one"]["actual_cost_mtd"] = 0
    state.findings = [resource(cost=0)]
    state.prior_resources = [resource(cost=85)]
    run(state)
    row = state.persisted_resources[0]
    assert row["cost"] == 0
    assert row["metadata"]["cost_source"] == "actual"
    assert row["metadata"]["cost_observed_at"] == OBSERVED_AT


def test_empty_inventory_with_failed_billing_retains_and_marks_existing_costs(scan_env):
    state = scan_env
    state.snapshot = snapshot("unavailable", 0)
    state.findings = []
    state.prior_resources = [resource(cost=85)]
    state.prior_stats = {"total_spend": 300}
    run(state)
    assert state.persisted_resources[0]["cost"] == 85
    assert state.persisted_resources[0]["metadata"]["cost_source"] == "billing_stale"
    assert saved_stats(state)["total_spend"] == 300
    assert saved_stats(state)["active_resources_count"] == 1
    state.db.delete_resources_for_integration.assert_not_awaited()


def test_partial_billing_success_does_not_overwrite_unavailable_subscription_total(scan_env):
    state = scan_env
    state.snapshot["billing"]["subscription_costs_available"] = False
    state.prior_stats = {"total_spend": 300}
    run(state)
    assert saved_stats(state)["total_spend"] == 300
    assert state.persisted_resources[0]["metadata"]["cost_source"] == "actual"
    assert state.daily_rows["2026-09-14"]["amount"] == 200
    routes._apply_catalog_estimates_for_scan.assert_not_awaited()


def test_previous_month_cached_snapshot_cannot_overwrite_current_mtd(scan_env):
    state = scan_env
    state.snapshot["billing"]["status"] = "cached"
    state.snapshot["billing"]["period_start"] = "2026-08-01"
    state.prior_stats = {"total_spend": 300}
    run(state)
    assert saved_stats(state)["total_spend"] == 300
    assert saved_stats(state)["metadata"]["total_spend_basis"] == "last_known"
    assert state.daily_rows == {"2026-08-31": {"amount": 91.0}}
    assert saved_integration_metadata(state)["last_mtd_cost"] == 180


def test_unexpected_refresh_exception_preserves_data_without_logging_secret(scan_env, caplog):
    state = scan_env
    state.refresh.side_effect = RuntimeError("test-secret")
    state.scanner.scan_all.side_effect = lambda **kwargs: deepcopy(state.findings)
    state.prior_resources = [resource(cost=85)]
    state.prior_stats = {"total_spend": 300}
    run(state)
    assert state.persisted_resources[0]["cost"] == 85
    assert saved_stats(state)["total_spend"] == 300
    assert saved_stats(state)["metadata"]["billing"]["status"] == "unavailable"
    assert "test-secret" not in caplog.text


def test_stats_endpoint_accepts_unknown_azure_spend_and_exposes_freshness(scan_env):
    state = scan_env
    state.snapshot = snapshot("unavailable", 0)
    run(state)
    state.db.get_dashboard_stats.side_effect = None
    state.db.get_dashboard_stats.return_value = saved_stats(state)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: routes.ClerkUser(id=USER_ID)
    app.dependency_overrides[routes.get_db_client] = lambda: state.db
    with TestClient(app) as client:
        response = client.get(f"/api/stats?integration_id={INTEGRATION_ID}")
    assert response.status_code == 200
    assert response.json()["total_spend"] is None
    assert response.json()["metadata"]["billing"] == state.snapshot["billing"]


@pytest.mark.parametrize("total", [200.0, 0.0])
def test_stale_partial_snapshot_persists_verified_subscription_and_daily_subset(scan_env, total):
    state = scan_env
    state.snapshot = snapshot("stale", total)
    state.snapshot["billing"].update({
        "observed_at": "2026-09-15T12:00:00+00:00",
        "subscription_costs_available": True,
        "daily_costs_available": True,
    })
    state.prior_resources = [resource(cost=85)]
    state.prior_stats = {"total_spend": 300}
    state.findings = [resource(cost=0, source="billing_unavailable")]
    run(state)

    assert saved_stats(state)["total_spend"] == total
    assert state.daily_rows["2026-09-14"]["amount"] == total
    assert state.persisted_resources[0]["cost"] == 85
    assert state.persisted_resources[0]["metadata"]["cost_source"] == "billing_stale"
    assert state.persisted_resources[0]["metadata"]["cost_observed_at"] == OBSERVED_AT
    assert saved_integration_metadata(state)["last_mtd_cost"] == total
    routes._apply_catalog_estimates_for_scan.assert_not_awaited()


def test_stale_cached_resource_uses_its_source_timestamp_not_subscription_timestamp(scan_env):
    state = scan_env
    state.snapshot["billing"].update({
        "status": "stale", "observed_at": "2026-09-15T12:00:00+00:00",
    })
    state.snapshot["resource_costs"]["/subscriptions/sub/vm/one"].update({
        "observed_at": "2026-09-10T12:00:00+00:00", "period_start": PERIOD_START,
    })
    run(state)
    row = state.persisted_resources[0]
    assert row["metadata"]["cost_source"] == "billing_stale"
    assert row["metadata"]["cost_observed_at"] == "2026-09-10T12:00:00+00:00"
    assert row["metadata"]["cost_period_start"] == PERIOD_START


@pytest.mark.parametrize("snapshot_amount", [60.0, 0.0])
def test_newer_current_period_cache_wins_over_older_persisted_actual(scan_env, snapshot_amount):
    state = scan_env
    state.snapshot = snapshot("stale")
    state.snapshot["resource_costs"] = {"/subscriptions/sub/vm/one": {
        "actual_cost_mtd": snapshot_amount, "period_start": PERIOD_START,
        "observed_at": "2026-09-15T10:00:00+00:00",
        "daily_costs": [{"date": "2026-09-15", "amount": snapshot_amount}],
    }}
    state.prior_resources = [resource(cost=85, metadata={
        **resource()["metadata"], "cost_monthly_total": 999,
        "daily_costs": [{"date": "2026-09-14", "amount": 85}],
    })]
    state.findings = [resource(cost=0, source="billing_unavailable")]
    run(state)
    row = state.persisted_resources[0]
    assert row["cost"] == snapshot_amount
    assert row["metadata"]["cost_source"] == "billing_stale"
    assert row["metadata"]["cost_observed_at"] == "2026-09-15T10:00:00+00:00"
    assert row["metadata"]["daily_costs"] == [{"date": "2026-09-15", "amount": snapshot_amount}]
    assert "cost_monthly_total" not in row["metadata"]
    assert state.optimize.call_args.kwargs["findings"][0]["cost"] == snapshot_amount


def test_newer_persisted_actual_wins_without_copying_snapshot_daily_costs(scan_env):
    state = scan_env
    state.snapshot = snapshot("stale")
    state.snapshot["resource_costs"] = {"/subscriptions/sub/vm/one": {
        "actual_cost_mtd": 60, "period_start": PERIOD_START,
        "observed_at": "2026-09-10T10:00:00+00:00",
        "daily_costs": [{"date": "2026-09-10", "amount": 60}],
    }}
    state.prior_resources = [resource(cost=85)]
    state.findings = [resource(cost=60, source="billing_stale", metadata={
        "cost_source": "billing_stale", "cost_monthly_total": 60,
        "daily_costs": [{"date": "2026-09-10", "amount": 60}],
    })]
    run(state)
    row = state.persisted_resources[0]
    assert row["cost"] == 85
    assert row["metadata"]["cost_observed_at"] == OBSERVED_AT
    assert row["metadata"]["daily_costs"] == []
    assert "cost_monthly_total" not in row["metadata"]


@pytest.mark.parametrize("source", ["previous", "snapshot"])
def test_old_period_billing_only_survives_as_metadata_across_repeated_scans(scan_env, source):
    state = scan_env
    state.snapshot = snapshot("unavailable")
    old_cost = {"amount": 85, "observed_at": "2026-08-31T10:00:00+00:00", "period_start": "2026-08-01"}
    if source == "previous":
        state.prior_resources = [resource(cost=0, source="billing_unavailable", metadata={
            "cost_source": "billing_unavailable", "last_known_cost": old_cost,
        })]
    else:
        state.snapshot["resource_costs"] = {"/subscriptions/sub/vm/one": {
            "actual_cost_mtd": 85, "observed_at": old_cost["observed_at"], "period_start": old_cost["period_start"],
        }}
    state.findings = [resource(cost=85, source="billing_stale", metadata={
        "cost_source": "billing_stale", "cost_observed_at": old_cost["observed_at"],
        "cost_period_start": old_cost["period_start"], "daily_costs": [{"date": "2026-08-31", "amount": 85}],
    })]
    run(state)
    row = state.persisted_resources[0]
    assert row["cost"] == 0
    assert row["metadata"]["cost_source"] == "billing_unavailable"
    assert row["metadata"]["last_known_cost"] == old_cost
    assert row["metadata"]["daily_costs"] == []
    assert state.optimize.call_args.kwargs["findings"][0]["cost"] == 0


@pytest.mark.parametrize("explicit_observation", [False, True])
def test_failed_refresh_preserves_dashboard_total_observation_separately(scan_env, explicit_observation):
    state = scan_env
    state.snapshot = snapshot("unavailable")
    previous_metadata = {"billing": {"observed_at": OBSERVED_AT, "period_start": PERIOD_START}}
    if explicit_observation:
        previous_metadata.update(total_spend_observed_at=OBSERVED_AT, total_spend_period_start=PERIOD_START)
        previous_metadata["billing"] = snapshot("unavailable")["billing"]
    state.prior_stats = {"total_spend": 300, "metadata": previous_metadata}
    run(state)
    metadata = saved_stats(state)["metadata"]
    assert metadata["billing"]["observed_at"] is None
    assert metadata["total_spend_observed_at"] == OBSERVED_AT
    assert metadata["total_spend_period_start"] == PERIOD_START


def test_daily_history_persists_only_per_day_service_breakdowns(scan_env):
    state = scan_env
    state.snapshot["subscription_costs"]["by_service"] = {"VM": 200}
    state.snapshot["subscription_costs"]["daily_totals"] = [
        {"date": "2026-09-13", "amount": 80, "service_breakdown": {"VM": 80}},
        {"date": "2026-09-14", "amount": 120, "service_breakdown": {"VM": 120}},
        {"date": "2026-09-15", "amount": 0},
    ]
    run(state)
    assert state.daily_rows["2026-09-13"]["service_breakdown"] == {"VM": 80}
    assert state.daily_rows["2026-09-14"]["service_breakdown"] == {"VM": 120}
    assert state.daily_rows["2026-09-15"]["service_breakdown"] == {}


def test_billing_is_marked_stale_before_inventory_and_interruption(scan_env):
    state = scan_env

    def interrupted_inventory(**kwargs):
        updates = [call for call in state.db.update.call_args_list if call.args[0] == "cloud_integrations"]
        assert updates
        patch = updates[-1].args[1]
        assert "metadata" not in patch
        assert patch["metadata.billing"]["status"] == "stale"
        assert patch["metadata.billing"]["reason"] == "persistence_pending"
        assert updates[-1].args[2] == {"id": INTEGRATION_ID, "user_id": USER_ID}
        raise asyncio.CancelledError()

    state.scanner.scan_all.side_effect = interrupted_inventory
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(routes.run_scan(state.integration, USER_ID, state.db))
    state.db.upsert_dashboard_stats.assert_not_awaited()


def test_daily_write_failure_never_publishes_fresh_billing(scan_env):
    state = scan_env

    def fail_daily(table, data):
        if table == "daily_spend_history":
            raise RuntimeError("daily persistence failed")
        return data

    state.db.upsert.side_effect = fail_daily
    asyncio.run(routes.run_scan(state.integration, USER_ID, state.db))
    state.db.fail_scan_history.assert_awaited_once()
    state.db.upsert_dashboard_stats.assert_not_awaited()
    for call in state.db.update.call_args_list:
        if call.args[0] == "cloud_integrations":
            assert "metadata" not in call.args[1]
            if "metadata.billing" in call.args[1]:
                assert call.args[1]["metadata.billing"]["status"] != "fresh"


def test_freshness_is_published_only_after_daily_persistence(scan_env):
    state = scan_env
    persist = state.db.upsert.side_effect

    def persist_after_check(table, data):
        if table == "daily_spend_history":
            assert saved_integration_metadata(state)["billing"]["status"] == "stale"
            state.db.upsert_dashboard_stats.assert_not_awaited()
        return persist(table, data)

    state.db.upsert.side_effect = persist_after_check
    run(state)
    assert saved_integration_metadata(state)["billing"]["status"] == "fresh"
    assert saved_stats(state)["metadata"]["total_spend_observed_at"] == OBSERVED_AT
    assert saved_stats(state)["metadata"]["total_spend_period_start"] == PERIOD_START
    assert state.daily_rows["2026-09-14"]["amount"] == 200


@pytest.mark.parametrize("status, amount", [("fresh", 0), ("cached", 40), ("stale", 60)])
def test_real_scanner_consumes_snapshot_without_billing_network_calls(scan_env, status, amount):
    state = scan_env
    state.snapshot = snapshot(status)
    state.snapshot["resource_costs"] = {"/subscriptions/sub/vm/one": {
        "actual_cost_mtd": amount, "period_start": PERIOD_START, "observed_at": OBSERVED_AT,
    }}
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    scanner.subscription_id = "sub"
    scanner.fetch_billing = MagicMock(side_effect=AssertionError("Billing must not be fetched again"))
    for name in (
        "virtual_machines", "managed_disks", "public_ips", "network_security_groups",
        "storage_accounts", "load_balancers", "network_interfaces", "snapshots", "generic_resources",
    ):
        setattr(scanner, f"scan_{name}", lambda: None)
    scanner.scan_virtual_machines = lambda: scanner.findings.append(resource(cost=0, source="billing_unavailable"))
    state.scanner.scan_all.side_effect = scanner.scan_all
    run(state)
    scanner.fetch_billing.assert_not_called()
    assert state.persisted_resources[0]["cost"] == amount
    assert state.persisted_resources[0]["metadata"]["cost_source"] == ("billing_stale" if status == "stale" else "actual")
    assert state.persisted_resources[0]["metadata"]["cost_observed_at"] == OBSERVED_AT
