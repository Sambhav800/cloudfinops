from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core import commitment_engine as module
from app.core import commitment_recommendations


class FakeCommitmentDB:
    def __init__(self, integrations=(), snapshots=()):
        self.tables = {
            "cloud_integrations": deepcopy(list(integrations)),
            module.SNAPSHOT_COLLECTION: deepcopy(list(snapshots)),
        }
        self.reads = []
        self.writes = []

    @staticmethod
    def matches(row, filters):
        return all(
            row.get(key) in value["$in"] if isinstance(value, dict) else row.get(key) == value
            for key, value in filters.items()
        )

    async def select(self, table, filters=None):
        assert filters and filters.get("user_id")
        self.reads.append((table, deepcopy(filters)))
        return deepcopy([row for row in self.tables[table] if self.matches(row, filters)])

    async def upsert(self, table, data):
        assert data["user_id"] and data["integration_id"]
        self.writes.append((table, deepcopy(data)))
        rows = self.tables[table]
        prior = next((row for row in rows if row["id"] == data["id"]), None)
        if prior is None:
            rows.append(deepcopy(data))
        else:
            assert prior["user_id"] == data["user_id"]
            prior.update(deepcopy(data))
        return [deepcopy(data)]

    async def update(self, table, data, filters):
        assert filters["user_id"] and filters["integration_id"]
        self.writes.append((table, deepcopy(data)))
        updated = []
        for row in self.tables[table]:
            if self.matches(row, filters):
                row.update(deepcopy(data))
                updated.append(deepcopy(row))
        return updated


def integration(**overrides):
    return {"id": "int-aws", "user_id": "user-1", "provider": "aws", "status": "active", **overrides}


def commitment(**overrides):
    return {
        "id": "sp-1", "provider": "aws", "type": "Savings Plan", "name": "Compute Savings Plan",
        "status": "active", "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2027-01-01T00:00:00+00:00", "coverage_type": "Compute",
        "commitment_amount": 100.0, "amount_period": "monthly", "currency": "USD",
        "savings_amount": 10.0, "savings_period_start": "2026-09-01", "savings_period_end": "2026-09-08",
        "utilization_pct": 90.0, "integration_id": "int-aws", "source": "provider_api", "pricing_basis": "live_api",
        **overrides,
    }


def snapshot(*, user_id="user-1", integration_id="int-aws", rows=None, **overrides):
    return {
        "id": module.CommitmentEngine._snapshot_id(user_id, integration_id), "user_id": user_id,
        "integration_id": integration_id, "provider": "aws", "status": "ready", "source": "provider_api",
        "account_id": "123456789012", "inventory_regions": None,
        "last_success_at": datetime.now(timezone.utc).isoformat(), "last_attempt_at": "2026-09-08T00:00:00+00:00",
        "commitments": [commitment(integration_id=integration_id)] if rows is None else rows,
        **overrides,
    }


@pytest.fixture(autouse=True)
def no_cloud_network(monkeypatch):
    monkeypatch.setattr(module.boto3, "Session", MagicMock(side_effect=AssertionError("Unexpected AWS call")))
    monkeypatch.setattr(module.CommitmentEngine, "_get_aws_account_id", lambda self, credentials: "123456789012")
    helper = AsyncMock()
    monkeypatch.setattr(commitment_recommendations, "sync_aws_purchase_recommendations", helper)
    return helper


@pytest.fixture
def provider_engine(monkeypatch):
    engine = module.CommitmentEngine()
    credentials = {"access_key_id": "test-key", "secret_access_key": "test-secret"}
    monkeypatch.setattr(module, "decrypt_integration_credentials", lambda _: credentials)
    provider = AsyncMock(return_value=[module.CloudCommitment(**commitment())])
    monkeypatch.setattr(engine, "get_aws_commitments", provider)
    return engine, provider, credentials


def test_unknown_financials_are_none_and_assignment_is_validated():
    row = commitment()
    for field in ("commitment_amount", "utilization_pct", "savings_amount", "pricing_basis", "currency"):
        row.pop(field)
    item = module.CloudCommitment(**row)
    assert item.commitment_amount is item.hourly_commitment is item.savings_amount is None
    assert item.utilization_pct is item.currency is item.pricing_basis is None
    assert item.amount_period == "monthly"
    with pytest.raises(ValidationError):
        item.utilization_pct = 101


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf")])
def test_invalid_utilization_is_not_clamped_or_hidden(value):
    with pytest.raises(ValidationError):
        module.CloudCommitment(**commitment(utilization_pct=value))


def test_demo_cannot_claim_live_pricing():
    with pytest.raises(ValidationError, match="provider financial data"):
        module.CloudCommitment(**commitment(source="demo"))


@pytest.mark.parametrize("timestamp", ["2026-01-01", "2026-01-01T00:00:00", "invalid"])
def test_source_timestamp_requires_timezone(timestamp):
    with pytest.raises(ValidationError):
        module.CloudCommitment(**commitment(start_date=timestamp))


def test_source_timestamp_normalizes_explicit_timezone():
    item = module.CloudCommitment(**commitment(start_date="2026-01-01T05:30:00+05:30"))
    assert item.start_date == "2026-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_sync_persists_scoped_snapshot_then_delegates_purchase_sync(provider_engine, no_cloud_network):
    engine, provider, credentials = provider_engine
    account = integration()
    db = FakeCommitmentDB([account])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=account)
    assert isinstance(status, module.CommitmentSyncStatus)
    assert status.status == "ready" and status.commitment_count == 1
    assert status.last_success_at and status.last_attempt_at and not status.stale
    assert status.recommendation_sync_status == "completed"
    persisted = db.tables[module.SNAPSHOT_COLLECTION][0]
    assert persisted["id"] == engine._snapshot_id("user-1", "int-aws")
    assert persisted["commitments"][0]["integration_id"] == "int-aws"
    assert persisted["commitments"][0]["amount_period"] == "monthly"
    assert "credentials" not in persisted and "secret_access_key" not in repr(persisted)
    no_cloud_network.assert_awaited_once_with(db=db, user_id="user-1", integration=account, credentials=credentials)
    provider.assert_awaited_once_with("test-key", "test-secret", None)
    assert db.writes[0][1]["status"] == "ready"


@pytest.mark.asyncio
async def test_successful_empty_sync_clears_previous_inventory(provider_engine, no_cloud_network):
    engine, provider, _ = provider_engine
    provider.return_value = []
    db = FakeCommitmentDB([integration()], [snapshot()])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert status.status == "no_commitments" and status.commitment_count == 0
    assert db.tables[module.SNAPSHOT_COLLECTION][0]["commitments"] == []
    no_cloud_network.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_sync_retains_last_known_snapshot_and_marks_stale(provider_engine, no_cloud_network, caplog):
    engine, provider, _ = provider_engine
    provider.side_effect = module.CommitmentProviderError("secret-do-not-log")
    prior = snapshot()
    db = FakeCommitmentDB([integration()], [prior])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    persisted = db.tables[module.SNAPSHOT_COLLECTION][0]
    assert status.status == "error" and status.stale and status.commitment_count == 1
    assert status.last_success_at == prior["last_success_at"]
    assert status.last_attempt_at != prior["last_attempt_at"]
    assert persisted["commitments"] == prior["commitments"]
    assert status.error_code == "CommitmentProviderError"
    assert "secret-do-not-log" not in caplog.text + repr(persisted)
    no_cloud_network.assert_not_awaited()
    portfolio = await engine.get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == 1
    assert portfolio.summary.monthly_commitment is None
    assert portfolio.summary.measurement_status == "partial"


@pytest.mark.asyncio
async def test_first_failed_sync_is_error_not_successful_empty(provider_engine):
    engine, provider, _ = provider_engine
    provider.side_effect = RuntimeError("denied")
    db = FakeCommitmentDB([integration()])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert status.status == "error" and status.last_success_at is None
    assert status.commitment_count == 0
    assert (await engine.get_portfolio_snapshot("user-1", db=db)).integrations[0].status == "error"


@pytest.mark.asyncio
async def test_recommendation_failure_does_not_discard_successful_inventory(provider_engine, no_cloud_network, caplog):
    engine, _, _ = provider_engine
    no_cloud_network.side_effect = RuntimeError("secret-do-not-log")
    db = FakeCommitmentDB([integration()])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert status.status == "ready" and status.commitment_count == 1
    assert status.recommendation_sync_status == "error"
    assert db.tables[module.SNAPSHOT_COLLECTION][0]["recommendation_sync_status"] == "error"
    assert "secret-do-not-log" not in caplog.text


@pytest.mark.asyncio
async def test_decryption_failure_is_persisted_without_credentials(provider_engine, monkeypatch, caplog):
    engine, provider, _ = provider_engine
    monkeypatch.setattr(module, "decrypt_integration_credentials", MagicMock(side_effect=ValueError("secret-do-not-log")))
    db = FakeCommitmentDB([integration()], [snapshot()])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert status.status == "error" and status.stale
    assert "secret-do-not-log" not in caplog.text + repr(db.tables)
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_tenant_sync_rejected_before_reads_or_provider_calls(provider_engine):
    engine, provider, _ = provider_engine
    db = FakeCommitmentDB()
    with pytest.raises(ValueError, match="does not belong"):
        await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration(user_id="other"))
    assert not db.reads and not db.writes
    provider.assert_not_awaited()


def test_snapshot_ids_include_both_scope_fields_without_delimiter_collisions():
    identity = module.CommitmentEngine._snapshot_id
    assert identity("user-1", "int-1") == identity("user-1", "int-1")
    assert identity("user-1", "int-1") != identity("user-2", "int-1")
    assert identity("user:a", "b") != identity("user", "a:b")


@pytest.mark.asyncio
async def test_generic_upsert_replaces_only_matching_tenant_snapshot(provider_engine):
    engine, _, _ = provider_engine
    other = snapshot(user_id="other", rows=[commitment(name="Other account")])
    db = FakeCommitmentDB([integration()], [snapshot(), other])
    for _ in range(2):
        await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert len(db.tables[module.SNAPSHOT_COLLECTION]) == 2
    assert db.tables[module.SNAPSHOT_COLLECTION][1] == other


@pytest.mark.asyncio
async def test_portfolio_read_is_persisted_only_and_excludes_inactive_and_other_users(monkeypatch):
    accounts = [integration(), integration(id="inactive", status="inactive"), integration(id="other", user_id="other")]
    db = FakeCommitmentDB(accounts, [
        snapshot(), snapshot(integration_id="inactive"), snapshot(user_id="other", integration_id="other"),
        snapshot(integration_id="deleted"),
    ])
    decrypt = MagicMock(side_effect=AssertionError("Read must not decrypt"))
    monkeypatch.setattr(module, "decrypt_integration_credentials", decrypt)
    monkeypatch.setattr(module, "get_db_client", lambda: db)
    engine = module.CommitmentEngine()
    portfolio = await engine.get_portfolio_snapshot("user-1")
    assert isinstance(portfolio, module.CommitmentPortfolioSnapshot)
    assert portfolio.count == 1 and len(portfolio.integrations) == 1
    assert portfolio.commitments[0].integration_id == "int-aws"
    assert set(portfolio.model_dump()) == {"commitments", "count", "integrations", "summary"}
    assert await engine.get_commitments("user-1") == portfolio.commitments
    assert len(db.reads) == 4 and not db.writes
    decrypt.assert_not_called()


@pytest.mark.asyncio
async def test_missing_snapshot_is_not_synced_even_for_demo_and_azure():
    db = FakeCommitmentDB([integration(), integration(id="azure", provider="azure"),
                           integration(id="demo", metadata={"environment": "demo", "demo_commitments": []})])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == 0
    assert {item.status for item in portfolio.integrations} == {"not_synced"}
    assert portfolio.integrations[2].source == "demo"
    assert portfolio.summary.measurement_status == "unavailable"
    assert portfolio.summary.monthly_commitment is None


@pytest.mark.asyncio
async def test_empty_portfolio_has_no_fake_financial_summary():
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=FakeCommitmentDB())
    assert portfolio.count == portfolio.summary.active_count == 0
    assert portfolio.summary.model_dump() == {
        "currency": None, "monthly_commitment": None, "measured_savings": None,
        "savings_period_start": None, "savings_period_end": None, "utilization_pct": None,
        "coverage_pct": None, "active_count": 0, "measurement_status": "unavailable",
    }


@pytest.mark.asyncio
async def test_inactive_sync_skips_network_and_writes(provider_engine):
    engine, provider, _ = provider_engine
    db = FakeCommitmentDB()
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration(status="inactive"))
    assert status.status == "not_synced" and status.error_code == "inactive"
    assert not db.writes
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_azure_sync_is_explicitly_unsupported_without_decrypt(monkeypatch):
    decrypt = MagicMock(side_effect=AssertionError("Azure is unsupported"))
    monkeypatch.setattr(module, "decrypt_integration_credentials", decrypt)
    account = integration(provider="azure")
    db = FakeCommitmentDB([account])
    status = await module.CommitmentEngine().sync_integration_commitments(db=db, user_id="user-1", integration=account)
    assert status.status == "unsupported" and status.error_code == "unsupported_provider"
    assert status.last_success_at is None
    decrypt.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], None])
async def test_empty_demo_sync_never_calls_cloud_or_decrypt(rows, monkeypatch, no_cloud_network):
    metadata = {"environment": "demo"}
    if rows is not None:
        metadata["demo_commitments"] = rows
    account = integration(metadata=metadata)
    db = FakeCommitmentDB([account])
    decrypt = MagicMock(side_effect=AssertionError("Demo must not decrypt"))
    monkeypatch.setattr(module, "decrypt_integration_credentials", decrypt)
    status = await module.CommitmentEngine().sync_integration_commitments(db=db, user_id="user-1", integration=account)
    assert status.status == "demo" and status.commitment_count == 0 and status.source == "demo"
    decrypt.assert_not_called()
    no_cloud_network.assert_not_awaited()


@pytest.mark.asyncio
async def test_demo_amounts_without_unit_or_window_metadata_remain_unknown():
    row = commitment()
    for key in ("amount_period", "savings_period_start", "savings_period_end"):
        row.pop(key)
    account = integration(metadata={"environment": "demo", "demo_commitments": [row]})
    db = FakeCommitmentDB([account])
    engine = module.CommitmentEngine()
    await engine.sync_integration_commitments(db=db, user_id="user-1", integration=account)
    item = (await engine.get_commitments("user-1", db=db))[0]
    assert item.commitment_amount is item.savings_amount is item.pricing_basis is None
    assert item.source == "demo" and item.utilization_pct == 90.0


@pytest.mark.asyncio
async def test_explicit_demo_units_are_preserved_and_provenance_visible():
    account = integration(metadata={"environment": "demo", "demo_commitments": [commitment()]})
    db = FakeCommitmentDB([account])
    engine = module.CommitmentEngine()
    await engine.sync_integration_commitments(db=db, user_id="user-1", integration=account)
    portfolio = await engine.get_portfolio_snapshot("user-1", db=db)
    assert portfolio.commitments[0].commitment_amount == 100
    assert portfolio.commitments[0].source == "demo" and portfolio.commitments[0].pricing_basis is None
    assert portfolio.integrations[0].status == "demo" and portfolio.integrations[0].source == "demo"


@pytest.mark.asyncio
async def test_unflagged_demo_metadata_does_not_bypass_provider(provider_engine):
    engine, provider, _ = provider_engine
    account = integration(metadata={"demo_commitments": [commitment(name="Untrusted demo")]})
    db = FakeCommitmentDB([account])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=account)
    assert status.status == "ready"
    provider.assert_awaited_once()
    assert db.tables[module.SNAPSHOT_COLLECTION][0]["commitments"][0]["name"] != "Untrusted demo"


@pytest.mark.asyncio
async def test_invalid_demo_rows_are_visible_error_not_successful_partial_data():
    account = integration(metadata={"environment": "demo", "demo_commitments": [commitment(), {"id": "broken"}]})
    db = FakeCommitmentDB([account], [snapshot()])
    status = await module.CommitmentEngine().sync_integration_commitments(db=db, user_id="user-1", integration=account)
    assert status.status == "error" and status.stale and status.commitment_count == 1


@pytest.mark.asyncio
async def test_database_failure_propagates_without_attempting_cloud_or_recommendations(provider_engine, no_cloud_network):
    engine, provider, _ = provider_engine
    db = FakeCommitmentDB()
    db.select = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    with pytest.raises(RuntimeError, match="Database unavailable"):
        await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    provider.assert_not_awaited()
    no_cloud_network.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_snapshot_write_never_reports_success_or_runs_recommendations(provider_engine, no_cloud_network):
    engine, _, _ = provider_engine
    db = FakeCommitmentDB([integration()], [snapshot()])
    prior = deepcopy(db.tables[module.SNAPSHOT_COLLECTION])
    db.upsert = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    with pytest.raises(RuntimeError):
        await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert db.tables[module.SNAPSHOT_COLLECTION] == prior
    no_cloud_network.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_uses_period_denominators_and_preserves_actual_zero():
    rows = [commitment(utilization_pct=0, savings_amount=0, utilization_used_commitment=0, utilization_total_commitment=10),
            commitment(id="sp-2", commitment_amount=300, utilization_pct=100, savings_amount=30,
                       utilization_used_commitment=30, utilization_total_commitment=30)]
    db = FakeCommitmentDB([integration()], [snapshot(rows=rows)])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.monthly_commitment == 400 and summary.measured_savings == 30
    assert summary.utilization_pct == 75 and summary.active_count == 2
    assert summary.currency == "USD" and summary.coverage_pct is None
    assert summary.savings_period_start == "2026-09-01" and summary.savings_period_end == "2026-09-08"
    assert summary.measurement_status == "complete"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,unknown",
    [
        ({"currency": "EUR"}, ("currency", "monthly_commitment", "measured_savings", "utilization_pct")),
        ({"currency": None}, ("currency", "monthly_commitment", "measured_savings", "utilization_pct")),
        ({"commitment_amount": None}, ("monthly_commitment", "utilization_pct")),
        ({"savings_amount": None}, ("measured_savings",)),
        ({"savings_period_start": "2026-09-02"}, ("measured_savings", "utilization_pct")),
        ({"savings_period_end": None}, ("measured_savings", "utilization_pct")),
        ({"utilization_pct": None}, ("utilization_pct",)),
    ],
)
async def test_summary_does_not_sum_incomparable_or_missing_measurements(changes, unknown):
    rows = [commitment(), commitment(id="sp-2", **changes)]
    db = FakeCommitmentDB([integration()], [snapshot(rows=rows)])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.measurement_status == "partial"
    for field in unknown:
        assert getattr(summary, field) is None


@pytest.mark.asyncio
async def test_summary_all_zero_money_does_not_divide_by_zero():
    db = FakeCommitmentDB([integration()], [snapshot(rows=[commitment(commitment_amount=0, savings_amount=0, utilization_pct=0)])])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.monthly_commitment == summary.measured_savings == 0
    assert summary.utilization_pct == 0 and summary.measurement_status == "complete"


@pytest.mark.asyncio
async def test_missing_integration_snapshot_prevents_complete_portfolio_totals():
    db = FakeCommitmentDB([integration(), integration(id="not-scanned")], [snapshot()])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.monthly_commitment is summary.measured_savings is summary.utilization_pct is None
    assert summary.measurement_status == "partial"


@pytest.mark.asyncio
async def test_summary_excludes_expired_commitments():
    db = FakeCommitmentDB([integration()], [snapshot(rows=[commitment(), commitment(id="old", status="expired", currency="EUR")])])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == 2 and portfolio.summary.active_count == 1
    assert portfolio.summary.monthly_commitment == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("hours", [49, -1, None])
async def test_old_future_or_missing_refresh_time_keeps_rows_but_suppresses_totals(hours):
    refreshed = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat() if hours is not None else None
    db = FakeCommitmentDB([integration()], [snapshot(last_success_at=refreshed)])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == 1 and portfolio.integrations[0].stale
    assert portfolio.integrations[0].error_code == "stale_snapshot"
    assert portfolio.summary.monthly_commitment is portfolio.summary.measured_savings is None
    assert portfolio.summary.utilization_pct is None and portfolio.summary.measurement_status == "partial"
    assert not db.writes


@pytest.mark.asyncio
async def test_scan_fake_without_snapshot_api_fails_before_cloud_calls(provider_engine):
    engine, provider, _ = provider_engine
    with pytest.raises(AttributeError):
        await engine.sync_integration_commitments(db=SimpleNamespace(), user_id="user-1", integration=integration())
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_gcp_inventory_has_no_fabricated_financials_and_discovers_regions(monkeypatch):
    from google.cloud import compute_v1
    from google.oauth2 import service_account

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", MagicMock())
    region_client = MagicMock()
    region_client.list.return_value = [SimpleNamespace(name="test-region")]
    monkeypatch.setattr(compute_v1, "RegionsClient", MagicMock(return_value=region_client))
    client = MagicMock()
    client.list.return_value = [SimpleNamespace(
        id=1, name="gcp-commitment", status="ACTIVE", start_timestamp="2026-01-01T00:00:00Z",
        end_timestamp="2027-01-01T00:00:00Z",
    )]
    monkeypatch.setattr(compute_v1, "RegionCommitmentsClient", MagicMock(return_value=client))
    items = await module.CommitmentEngine().get_gcp_commitments("project", "test@example.invalid", "test-key")
    assert len(items) == 1 and items[0].region == "test-region"
    assert items[0].commitment_amount is items[0].savings_amount is items[0].utilization_pct is None
    assert items[0].currency is items[0].pricing_basis is None
    assert items[0].source == "provider_api"


@pytest.mark.asyncio
async def test_gcp_listing_failure_is_not_successful_empty(monkeypatch):
    from google.cloud import compute_v1
    from google.oauth2 import service_account

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", MagicMock())
    client = MagicMock()
    client.list.side_effect = RuntimeError("Not Found")
    monkeypatch.setattr(compute_v1, "RegionCommitmentsClient", MagicMock(return_value=client))
    with pytest.raises(module.CommitmentProviderError):
        await module.CommitmentEngine().get_gcp_commitments("project", "test@example.invalid", "test-key", ["test-region"])


@pytest.mark.asyncio
async def test_same_aws_commitment_from_duplicate_connections_is_counted_once():
    db = FakeCommitmentDB([integration(), integration(id="duplicate")], [snapshot(), snapshot(integration_id="duplicate")])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == portfolio.summary.active_count == 1
    assert portfolio.summary.monthly_commitment == 100
    assert portfolio.summary.measured_savings == 10
    assert len(portfolio.integrations) == 2


@pytest.mark.asyncio
async def test_distinct_aws_commitment_ids_are_preserved_across_connections():
    db = FakeCommitmentDB([integration(), integration(id="second")], [
        snapshot(), snapshot(integration_id="second", account_id="999999999999", rows=[commitment(id="sp-2", integration_id="second")]),
    ])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == portfolio.summary.active_count == 2
    assert portfolio.summary.monthly_commitment == 200
    assert portfolio.summary.utilization_pct is None


@pytest.mark.asyncio
async def test_current_contractual_expiry_overrides_cached_active_status():
    ended = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db = FakeCommitmentDB([integration()], [snapshot(rows=[commitment(end_date=ended)])])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.commitments[0].status == "expired"
    assert portfolio.summary.active_count == 0
    assert portfolio.summary.monthly_commitment is None
    assert not db.writes


@pytest.mark.asyncio
async def test_different_in_period_start_dates_do_not_distort_utilization():
    rows = [
        commitment(commitment_amount=730, utilization_pct=100,
                   utilization_used_commitment=168, utilization_total_commitment=168),
        commitment(id="new", commitment_amount=730, utilization_pct=0,
                   utilization_used_commitment=0, utilization_total_commitment=24),
    ]
    db = FakeCommitmentDB([integration()], [snapshot(rows=rows)])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.utilization_pct == 87.5


@pytest.mark.asyncio
async def test_ri_hours_and_savings_plan_dollars_are_not_blended():
    rows = [commitment(utilization_used_commitment=90, utilization_total_commitment=100),
            commitment(id="ri", type="Reservation", utilization_pct=0)]
    db = FakeCommitmentDB([integration()], [snapshot(rows=rows)])
    summary = (await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)).summary
    assert summary.utilization_pct is None
    assert summary.monthly_commitment == 200


@pytest.mark.asyncio
async def test_role_only_integration_uses_existing_assume_role_and_propagates_token(provider_engine, no_cloud_network, monkeypatch):
    from app.scanners.aws import AWSScanner

    engine, provider, _ = provider_engine
    role = {"role_arn": "arn:aws:iam::123456789012:role/ReadOnly", "external_id": "tenant-external-id"}
    monkeypatch.setattr(module, "decrypt_integration_credentials", lambda _: role)
    assume = MagicMock(return_value={"AccessKeyId": "temporary", "SecretAccessKey": "secret", "SessionToken": "token"})
    monkeypatch.setattr(AWSScanner, "_assume_role", assume)
    db = FakeCommitmentDB([integration()])
    status = await engine.sync_integration_commitments(db=db, user_id="user-1", integration=integration())
    assert status.status == "ready"
    assume.assert_called_once_with("", "", role["role_arn"], role["external_id"])
    provider.assert_awaited_once_with("temporary", "secret", None, session_token="token")
    assert no_cloud_network.call_args.kwargs["credentials"]["session_token"] == "token"
    assert "SessionToken" not in repr(db.tables) and "session_token" not in repr(db.tables)


@pytest.mark.asyncio
async def test_role_without_external_id_is_rejected_before_assumption(provider_engine, monkeypatch):
    from app.scanners.aws import AWSScanner

    engine, provider, _ = provider_engine
    monkeypatch.setattr(module, "decrypt_integration_credentials", lambda _: {"role_arn": "arn:aws:iam::123456789012:role/ReadOnly"})
    assume = MagicMock(side_effect=AssertionError("Missing ExternalId"))
    monkeypatch.setattr(AWSScanner, "_assume_role", assume)
    status = await engine.sync_integration_commitments(db=FakeCommitmentDB([integration()]), user_id="user-1", integration=integration())
    assert status.status == "error"
    assume.assert_not_called()
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_newer_empty_snapshot_supersedes_old_duplicate_account_inventory():
    now = datetime.now(timezone.utc)
    db = FakeCommitmentDB([integration(), integration(id="new")], [
        snapshot(last_success_at=(now - timedelta(hours=1)).isoformat()),
        snapshot(integration_id="new", status="no_commitments", rows=[], last_success_at=now.isoformat()),
    ])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == portfolio.summary.active_count == 0
    assert portfolio.summary.monthly_commitment is None
    assert len(portfolio.integrations) == 2


@pytest.mark.asyncio
async def test_duplicate_account_region_scope_mismatch_withholds_totals():
    db = FakeCommitmentDB([integration(), integration(id="second")], [
        snapshot(inventory_regions=["us-east-1"]),
        snapshot(integration_id="second", inventory_regions=["us-west-2"], rows=[]),
    ])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert any(row.error_code == "incompatible_inventory_scopes" for row in portfolio.integrations)
    assert portfolio.summary.monthly_commitment is None


@pytest.mark.asyncio
async def test_legacy_snapshot_requires_verified_account_scope_before_financial_totals():
    db = FakeCommitmentDB([integration()], [snapshot(account_id=None)])
    portfolio = await module.CommitmentEngine().get_portfolio_snapshot("user-1", db=db)
    assert portfolio.count == 1
    assert portfolio.integrations[0].error_code == "unverified_account_scope"
    assert portfolio.summary.monthly_commitment is None
