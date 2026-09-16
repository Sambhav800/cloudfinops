import asyncio
import threading
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Callable, cast
from unittest.mock import Mock

import pytest
from pymongo.errors import DuplicateKeyError

from app.core import azure_billing_refresh as billing

Document = dict[str, object]
USER = "user-one"
SUBSCRIPTION = "ABC-123"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(billing, "_now", lambda: clock.now)
    return clock


def snapshot(clock: Clock, total: float = 120) -> billing.BillingSnapshot:
    return {
        "resource_costs": {"/subscriptions/abc-123/vm/one": {"actual_cost_mtd": total}},
        "subscription_costs": {
            "total": total, "by_service": {"Compute": total}, "currency": "USD",
            "daily_totals": [{"date": clock.now.date().isoformat(), "amount": total}],
        },
        "billing": {
            "status": "fresh", "observed_at": clock.now.isoformat(),
            "period_start": clock.now.date().replace(day=1).isoformat(),
            "reason": None, "retry_at": None, "resource_costs_available": True,
            "subscription_costs_available": True, "daily_costs_available": True,
        },
    }


def failed_snapshot(clock: Clock, retry_seconds: int = 0) -> billing.BillingSnapshot:
    result = billing._empty(clock.now)
    result["billing"].update(reason="rate_limited", retry_at=(clock.now + timedelta(seconds=retry_seconds)).isoformat())
    return result


def matches(row: Document, filters: Document) -> bool:
    for key, expected in filters.items():
        if key == "$or":
            if not any(matches(row, condition) for condition in cast(list[Document], expected)):
                return False
        elif isinstance(expected, dict):
            if "$exists" in expected and (key in row) != expected["$exists"]:
                return False
            if "$lte" in expected and (key not in row or row[key] > expected["$lte"]):
                return False
            if "$gt" in expected and (key not in row or row[key] <= expected["$gt"]):
                return False
        elif row.get(key) != expected:
            return False
    return True


class MemoryDB:
    """Model atomic generic updates, unique _id, and Mongo's post-update reselect."""

    def __init__(self, documents: dict[str, Document] | None = None) -> None:
        self.documents = documents if documents is not None else {}
        self.calls: list[tuple[str, Document, Document]] = []
        self.fail: set[str] = set()
        self.select_count = 0
        self.fail_select_at = 0
        self.bootstrap_collision: Document | None = None
        self.after_update: Callable[[Document, Document], None] | None = None

    async def select(self, table: str, *, filters: Document) -> list[Document]:
        assert table == billing._TABLE and filters.get("user_id")
        self.calls.append(("select", {}, deepcopy(filters)))
        self.select_count += 1
        if "select" in self.fail or self.select_count == self.fail_select_at:
            raise RuntimeError("database unavailable secret-sentinel")
        rows = [deepcopy(row) for row in self.documents.values() if matches(row, filters)]
        for row in rows:
            row.pop("_id", None)
        await asyncio.sleep(0)
        return rows

    async def upsert(self, table: str, data: Document) -> object:
        assert table == billing._TABLE and set(data) == {"_id", "id", "user_id"}
        self.calls.append(("upsert", deepcopy(data), {}))
        await asyncio.sleep(0)
        if "upsert" in self.fail:
            raise RuntimeError("database unavailable")
        key = cast(str, data["_id"])
        if self.bootstrap_collision is not None:
            self.documents[key] = {**deepcopy(data), **deepcopy(self.bootstrap_collision)}
            self.bootstrap_collision = None
            raise DuplicateKeyError("duplicate _id")
        self.documents.setdefault(key, {}).update(deepcopy(data))
        return []

    async def update(self, table: str, data: Document, filters: Document) -> object:
        assert table == billing._TABLE and filters.get("user_id")
        self.calls.append(("update", deepcopy(data), deepcopy(filters)))
        await asyncio.sleep(0)
        if "update" in self.fail or ("persist" in self.fail and "completed_owner" in data):
            raise RuntimeError("database unavailable")
        for row in self.documents.values():
            if matches(row, filters):
                row.update(deepcopy(data))
                if self.after_update:
                    self.after_update(row, data)
        # In the real wrapper the changed owner/version no longer matches the old filters.
        return []

    @property
    def row(self) -> Document:
        return self.documents[cast(str, billing._scope(USER, SUBSCRIPTION)["id"])]

    @property
    def saved(self) -> billing.BillingSnapshot:
        return cast(billing.BillingSnapshot, self.row["snapshot"])


class BlockingScanner:
    def __init__(self, value: billing.BillingSnapshot) -> None:
        self.value = value
        self.started = asyncio.Event()
        self.finished = asyncio.Event()
        self.release = threading.Event()
        self.loop = asyncio.get_running_loop()
        self.calls = 0

    def fetch_billing(self) -> billing.BillingSnapshot:
        self.calls += 1
        self.loop.call_soon_threadsafe(self.started.set)
        try:
            if not self.release.wait(timeout=5):
                raise TimeoutError("test worker was not released")
            return deepcopy(self.value)
        finally:
            self.loop.call_soon_threadsafe(self.finished.set)


@pytest.mark.asyncio
async def test_success_persists_atomically_and_cache_survives_new_client(clock: Clock) -> None:
    db = MemoryDB()
    value = snapshot(clock)
    scanner = Mock(fetch_billing=Mock(return_value=value))
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result == value
    assert db.saved == value
    assert db.row["lease_owner"] is None
    assert db.row["cache_until"] == clock.now.timestamp() + 6 * 60 * 60
    writes = [data for operation, data, _ in db.calls if operation == "update" and "snapshot" in data]
    assert len(writes) == 1
    assert writes[0]["snapshot"] == value

    result["resource_costs"].clear()
    value["subscription_costs"]["total"] = 999
    cached = await billing.refresh_azure_billing(
        scanner, db=MemoryDB(db.documents), user_id=USER, subscription_id=" /SUBSCRIPTIONS/{abc-123}/ "
    )
    assert cached["billing"]["status"] == "cached"
    assert cached["billing"]["observed_at"] == db.saved["billing"]["observed_at"]
    assert cached["subscription_costs"]["total"] == 120
    assert cached["resource_costs"]
    scanner.fetch_billing.assert_called_once()


@pytest.mark.asyncio
async def test_cache_ttl_expires_and_success_replaces_whole_snapshot(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    clock.advance(seconds=6 * 60 * 60 - 1)
    cached = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert cached["billing"]["status"] == "cached"
    scanner.fetch_billing.assert_called_once()
    clock.advance(seconds=1)
    scanner.fetch_billing.return_value = snapshot(clock, 200)
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "fresh"
    assert result["subscription_costs"]["total"] == 200
    assert scanner.fetch_billing.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exception", "empty_snapshot"])
async def test_failure_preserves_last_good_and_original_observation(clock: Clock, failure: str) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    saved = deepcopy(db.saved)
    clock.advance(hours=7)
    if failure == "exception":
        scanner.fetch_billing.side_effect = RuntimeError("credentials secret-sentinel")
    else:
        scanner.fetch_billing.return_value = failed_snapshot(clock)
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "stale"
    assert result["billing"]["observed_at"] == saved["billing"]["observed_at"]
    assert result["resource_costs"] == saved["resource_costs"]
    assert result["subscription_costs"] == saved["subscription_costs"]
    assert db.saved == saved
    assert result["billing"]["retry_at"] == (clock.now + timedelta(minutes=15)).isoformat()


@pytest.mark.asyncio
async def test_true_zero_and_empty_success_are_cacheable(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock, 0)
    value["resource_costs"] = {}
    value["subscription_costs"].update(by_service={}, daily_totals=[])
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result == value
    cached = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert cached["billing"]["status"] == "cached"
    assert cached["subscription_costs"]["total"] == 0
    assert all(cached["billing"][part] for part in billing._PARTS)
    scanner.fetch_billing.assert_called_once()


@pytest.mark.asyncio
async def test_partial_refresh_preserves_failed_parts_without_retimestamping(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    old = snapshot(clock)
    scanner.fetch_billing.return_value = old
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    clock.advance(hours=7)
    partial = snapshot(clock, 0)
    partial["billing"].update(status="stale", reason="rate_limited", subscription_costs_available=False, daily_costs_available=False)
    partial["resource_costs"] = {}
    scanner.fetch_billing.return_value = partial
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["resource_costs"] == {}
    assert result["subscription_costs"] == old["subscription_costs"]
    assert result["billing"]["status"] == "stale"
    assert result["billing"]["observed_at"] == old["billing"]["observed_at"]
    stamps = cast(dict[str, str], db.row["part_observed_at"])
    assert stamps["resource_costs_available"] == partial["billing"]["observed_at"]
    assert stamps["subscription_costs_available"] == old["billing"]["observed_at"]
    cached = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert cached["billing"]["reason"] == "cooldown"
    assert cached["subscription_costs"]["total"] == 120


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
async def test_month_rollover_never_carries_old_parts(clock: Clock, partial: bool) -> None:
    db, scanner = MemoryDB(), Mock()
    clock.now = datetime(2026, 9, 30, 23, tzinfo=timezone.utc)
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=2)
    value = snapshot(clock, 0) if partial else failed_snapshot(clock)
    if partial:
        value["billing"].update(status="stale", resource_costs_available=False, daily_costs_available=False)
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert scanner.fetch_billing.call_count == 2
    assert result["billing"]["period_start"] == "2026-10-01"
    assert result["resource_costs"] == {}
    assert result["subscription_costs"].get("daily_totals", []) == []
    assert result["billing"]["resource_costs_available"] is False
    if partial:
        assert result["subscription_costs"]["total"] == 0
        assert result["billing"]["observed_at"] == clock.now.isoformat()
    else:
        assert result["billing"]["status"] == "unavailable"
        assert result["billing"]["observed_at"] is None
        assert result["subscription_costs"] == {}
        assert db.saved == old


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_seconds", [0, 3600])
async def test_cooldown_uses_later_provider_deadline_and_prevents_sdk(clock: Clock, retry_seconds: int) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = failed_snapshot(clock, retry_seconds)
    first = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    deadline = clock.now + timedelta(seconds=max(900, retry_seconds))
    assert first["billing"]["retry_at"] == deadline.isoformat()
    assert "snapshot" not in db.row
    clock.advance(seconds=max(900, retry_seconds) - 1)
    blocked = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION.lower())
    assert blocked["billing"]["reason"] == "cooldown"
    assert blocked["billing"]["retry_at"] == deadline.isoformat()
    scanner.fetch_billing.assert_called_once()
    clock.advance(seconds=1)
    scanner.fetch_billing.return_value = snapshot(clock)
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "fresh"
    assert db.row["retry_at"] is None
    assert db.row["last_failure_reason"] is None


@pytest.mark.asyncio
async def test_exception_retry_after_is_persisted_without_logging_credentials(clock: Clock, caplog: pytest.LogCaptureFixture) -> None:
    db, scanner = MemoryDB(), Mock()
    error = RuntimeError("secret-sentinel")
    setattr(error, "retry_after", 7200)
    scanner.fetch_billing.side_effect = error
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["retry_at"] == (clock.now + timedelta(hours=2)).isoformat()
    assert "secret-sentinel" not in caplog.text
    assert "secret-sentinel" not in str(db.row)


@pytest.mark.asyncio
async def test_two_competing_clients_run_only_one_scanner(clock: Clock) -> None:
    db = MemoryDB()
    scanner = BlockingScanner(snapshot(clock))
    first = asyncio.create_task(billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION))
    second = asyncio.create_task(billing.refresh_azure_billing(scanner, db=MemoryDB(db.documents), user_id=USER, subscription_id=SUBSCRIPTION.lower()))
    try:
        await asyncio.wait_for(scanner.started.wait(), timeout=2)
        done, pending = await asyncio.wait({first, second}, timeout=2, return_when=asyncio.FIRST_COMPLETED)
        assert len(done) == len(pending) == 1
        assert next(iter(done)).result()["billing"]["reason"] == "refresh_in_progress"
        assert scanner.calls == 1
        assert db.row["lease_until"] == clock.now.timestamp() + 600
    finally:
        scanner.release.set()
        await asyncio.gather(first, second)
    assert db.saved["billing"]["status"] == "fresh"


@pytest.mark.asyncio
async def test_bootstrap_duplicate_preserves_winner_lease_and_cache(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    good = snapshot(clock)
    winner: Document = {"lease_owner": "winner", "lease_version": 7, "lease_until": clock.now.timestamp() + 600, "snapshot": good}
    db.bootstrap_collision = winner
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "refresh_in_progress"
    assert all(db.row[key] == value for key, value in winner.items())
    assert db.saved == good
    scanner.fetch_billing.assert_not_called()


@pytest.mark.asyncio
async def test_lease_lost_before_confirmation_does_not_call_sdk(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    def steal(row: Document, data: Document) -> None:
        row.update(lease_owner="winner", lease_version=100)
    db.after_update = steal
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "refresh_in_progress"
    scanner.fetch_billing.assert_not_called()
    assert db.row["lease_owner"] == "winner"


@pytest.mark.asyncio
@pytest.mark.parametrize("takeover", [False, True])
async def test_expired_or_lost_lease_cannot_publish_or_release(clock: Clock, takeover: bool) -> None:
    db = MemoryDB()
    scanner = BlockingScanner(snapshot(clock))
    task = asyncio.create_task(billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION))
    try:
        await asyncio.wait_for(scanner.started.wait(), timeout=2)
        if takeover:
            db.row.update(lease_owner="winner", lease_version=100, lease_until=clock.now.timestamp() + 600)
        else:
            clock.advance(minutes=11)
        owner = db.row["lease_owner"]
    finally:
        scanner.release.set()
    result = await task
    assert result["billing"]["reason"] == "lease_lost"
    assert "snapshot" not in db.row
    assert db.row["lease_owner"] == owner


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["select", "upsert", "update", "confirm"])
async def test_database_failure_is_fail_closed_before_sdk(clock: Clock, failure: str, caplog: pytest.LogCaptureFixture) -> None:
    db, scanner = MemoryDB(), Mock()
    if failure == "confirm":
        db.fail_select_at = 3
    else:
        db.fail.add(failure)
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "unavailable"
    assert result["billing"]["reason"] == "coordination_unavailable"
    scanner.fetch_billing.assert_not_called()
    assert "secret-sentinel" not in caplog.text


@pytest.mark.asyncio
async def test_persistence_failure_preserves_good_cache_and_keeps_lease(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=7)
    scanner.fetch_billing.return_value = snapshot(clock, 200)
    db.fail.add("persist")
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "stale"
    assert result["billing"]["reason"] == "coordination_unavailable"
    assert result["subscription_costs"]["total"] == 120
    assert db.saved == old
    assert db.row["lease_owner"] is not None


@pytest.mark.asyncio
async def test_caller_cancellation_keeps_worker_and_lease_until_persisted(clock: Clock) -> None:
    db = MemoryDB()
    scanner = BlockingScanner(snapshot(clock))
    task = asyncio.create_task(billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION))
    owned: set[asyncio.Task[billing.BillingSnapshot]] = set()
    try:
        await asyncio.wait_for(scanner.started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        owned = set(billing._REFRESH_TASKS)
        assert len(owned) == 1
        assert not next(iter(owned)).done()
        assert db.row["lease_owner"] is not None
        blocked = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
        assert blocked["billing"]["reason"] == "refresh_in_progress"
        assert scanner.calls == 1
    finally:
        scanner.release.set()
        await asyncio.gather(*owned)
    assert db.row["lease_owner"] is None
    assert db.saved["billing"]["status"] == "fresh"
    assert not billing._REFRESH_TASKS


@pytest.mark.asyncio
async def test_shutdown_cancellation_does_not_release_executing_worker_lease(clock: Clock) -> None:
    db = MemoryDB()
    scanner = BlockingScanner(snapshot(clock))
    task = asyncio.create_task(billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION))
    try:
        await asyncio.wait_for(scanner.started.wait(), timeout=2)
        owner = db.row["lease_owner"]
        next(iter(billing._REFRESH_TASKS)).cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert db.row["lease_owner"] == owner
        assert "snapshot" not in db.row
    finally:
        scanner.release.set()
        await asyncio.wait_for(scanner.finished.wait(), timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", ["bytes", "rows"])
async def test_oversized_resources_keep_current_subscription_billing(clock: Clock, monkeypatch: pytest.MonkeyPatch, bound: str) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    clock.advance(hours=7)
    value = snapshot(clock, 200)
    value["resource_costs"]["second"] = {"actual_cost_mtd": 0, "padding": "x" * 10_000}
    scanner.fetch_billing.return_value = value
    config = replace(billing._CONFIG, max_cache_bytes=4000) if bound == "bytes" else replace(billing._CONFIG, max_resource_rows=1)
    monkeypatch.setattr(billing, "_CONFIG", config)
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "resource_cache_capacity_exceeded"
    assert result["billing"]["status"] == "stale"
    assert result["subscription_costs"] == value["subscription_costs"]
    assert db.saved["subscription_costs"] == value["subscription_costs"]
    assert result["resource_costs"] == db.saved["resource_costs"] == {}
    assert result["billing"]["resource_costs_available"] is False
    assert result["billing"]["subscription_costs_available"] is True
    assert result["billing"]["daily_costs_available"] is True
    assert result["billing"]["observed_at"] == value["billing"]["observed_at"]
    assert "resource_costs_available" not in db.row["part_observed_at"]
    assert db.row["lease_owner"] is None
    assert db.row["retry_at"] is not None
    cached = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert cached["subscription_costs"] == value["subscription_costs"]
    assert cached["billing"]["reason"] == "cooldown"
    assert scanner.fetch_billing.call_count == 2


@pytest.mark.asyncio
async def test_cooldown_is_scoped_by_both_user_and_subscription(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = failed_snapshot(clock, 3600)
    for user, subscription in [(USER, SUBSCRIPTION), (USER, "another-sub"), ("another-user", SUBSCRIPTION)]:
        await billing.refresh_azure_billing(scanner, db=db, user_id=user, subscription_id=subscription)
    assert scanner.fetch_billing.call_count == 3
    assert len(db.documents) == 3
    assert all(row["_id"] == row["id"] for row in db.documents.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("user, subscription", [("", SUBSCRIPTION), (USER, ""), (USER, "/subscriptions/")])
async def test_invalid_scope_never_calls_database_or_sdk(clock: Clock, user: str, subscription: str) -> None:
    db, scanner = MemoryDB(), Mock()
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=user, subscription_id=subscription)
    assert result["billing"]["reason"] == "invalid_scope"
    assert not db.calls
    scanner.fetch_billing.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["daily", "subscription", "resources"])
async def test_independent_partial_parts_replace_only_successful_data(clock: Clock, changed: str) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=7)
    partial = snapshot(clock, 0)
    partial["billing"].update(
        status="stale", resource_costs_available=changed == "resources",
        subscription_costs_available=changed == "subscription", daily_costs_available=changed == "daily",
    )
    scanner.fetch_billing.return_value = partial
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["observed_at"] == old["billing"]["observed_at"]
    assert result["resource_costs"] == (partial if changed == "resources" else old)["resource_costs"]
    assert result["subscription_costs"]["total"] == (0 if changed == "subscription" else 120)
    assert result["subscription_costs"]["daily_totals"] == (partial if changed == "daily" else old)["subscription_costs"]["daily_totals"]


@pytest.mark.asyncio
async def test_partial_currency_change_does_not_mix_cached_currency(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    clock.advance(hours=7)
    partial = snapshot(clock, 20)
    partial["subscription_costs"]["currency"] = "EUR"
    partial["billing"].update(status="stale", resource_costs_available=False, daily_costs_available=False)
    scanner.fetch_billing.return_value = partial
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["subscription_costs"] == {"total": 20, "by_service": {"Compute": 20}, "currency": "EUR"}
    assert result["resource_costs"] == {}
    assert result["billing"]["daily_costs_available"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("observed", [None, "malformed", "2026-09-15T12:00:00", "2026-09-16T00:00:00Z"])
async def test_invalid_observation_does_not_replace_good_cache(clock: Clock, observed: str | None) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=7)
    invalid = snapshot(clock, 0)
    invalid["billing"]["observed_at"] = observed
    scanner.fetch_billing.return_value = invalid
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "invalid_snapshot"
    assert db.saved == old


@pytest.mark.asyncio
async def test_scanner_finishing_across_month_boundary_is_not_current_mtd(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    clock.now = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
    value = snapshot(clock)
    def cross_month() -> billing.BillingSnapshot:
        clock.advance(minutes=2)
        return value
    scanner.fetch_billing.side_effect = cross_month
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "period_mismatch"
    assert result["billing"]["period_start"] == "2026-10-01"
    assert result["subscription_costs"] == {}
    assert "snapshot" not in db.row


@pytest.mark.asyncio
@pytest.mark.parametrize("day", ["2026-08-31", "2026-09-99", "not-a-date"])
async def test_malformed_or_old_daily_rows_are_not_cached(clock: Clock, day: str) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock)
    value["subscription_costs"]["daily_totals"] = [{"date": day, "amount": 0}]
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "stale"
    assert result["billing"]["daily_costs_available"] is False
    assert "daily_totals" not in result["subscription_costs"]
    assert result["subscription_costs"]["total"] == 120


@pytest.mark.asyncio
async def test_invalid_cache_encoding_is_explicit_without_payload_logs(clock: Clock, caplog: pytest.LogCaptureFixture) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock)
    value["resource_costs"]["bad"] = {"actual_cost_mtd": 0, "invalid": object()}
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "cache_serialization_failed"
    assert "snapshot" not in db.row
    assert db.row["lease_owner"] is None
    assert "object at" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("invalid", [
    {}, {"actual_cost_mtd": None}, {"actual_cost_mtd": float("inf")},
    {"actual_cost_mtd": float("nan")}, {"actual_cost_mtd": True},
    {"actual_cost_mtd": "12"}, {"actual_cost_mtd": 0, "actual_cost_30d": None},
    {"actual_cost_mtd": 0, "period_start": "2026-08-01"},
    {"actual_cost_mtd": 0, "period_start": None},
    {"actual_cost_mtd": 0, "daily_costs": [{"date": "2026-08-31", "amount": 0}]},
    {"actual_cost_mtd": 0, "daily_costs": [{"date": "2026-09-15", "amount": float("inf")}]},
])
async def test_invalid_resource_costs_do_not_replace_confirmed_data(clock: Clock, invalid: Document, existing: bool) -> None:
    db, scanner = MemoryDB(), Mock()
    old = snapshot(clock)
    if existing:
        scanner.fetch_billing.return_value = old
        await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
        clock.advance(hours=7)
    value = snapshot(clock, 200)
    value["resource_costs"] = {"/vm/bad": invalid}
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["status"] == "stale"
    assert result["resource_costs"] == (old["resource_costs"] if existing else {})
    assert result["billing"]["resource_costs_available"] is existing
    assert result["subscription_costs"]["total"] == 200
    assert db.saved["resource_costs"] == result["resource_costs"]


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, -1.25, 12.5])
@pytest.mark.parametrize("field", ["actual_cost_mtd", "actual_cost_30d"])
async def test_finite_resource_costs_including_zero_and_credits_remain_valid(clock: Clock, amount: float, field: str) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock, amount)
    value["resource_costs"] = {"/vm/a": {
        field: amount, "period_start": "2026-09-01",
        "daily_costs": [{"date": "2026-09-15", "amount": amount}],
    }}
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result == value


@pytest.mark.asyncio
async def test_daily_service_breakdown_survives_cache_round_trip(clock: Clock) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock, 0)
    value["subscription_costs"]["daily_totals"][0]["service_breakdown"] = {"Compute": 0}
    scanner.fetch_billing.return_value = value
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result == value
    cached = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert cached["subscription_costs"]["daily_totals"][0]["service_breakdown"] == {"Compute": 0}


@pytest.mark.asyncio
async def test_subscription_too_large_even_without_resources_preserves_good_cache(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    db, scanner = MemoryDB(), Mock()
    scanner.fetch_billing.return_value = snapshot(clock)
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=7)
    value = snapshot(clock, 200)
    value["subscription_costs"]["by_service"] = {"x" * 10_000: 200}
    scanner.fetch_billing.return_value = value
    monkeypatch.setattr(billing, "_CONFIG", replace(billing._CONFIG, max_cache_bytes=4000))
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "cache_capacity_exceeded"
    assert result["subscription_costs"] == old["subscription_costs"]
    assert db.saved == old


@pytest.mark.asyncio
async def test_resource_capacity_reduction_never_replaces_good_snapshot_with_empty_failure(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    db, scanner = MemoryDB(), Mock()
    value = snapshot(clock)
    value["billing"].update(status="stale", subscription_costs_available=False, daily_costs_available=False)
    scanner.fetch_billing.return_value = value
    await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    old = deepcopy(db.saved)
    clock.advance(hours=1)
    value = deepcopy(value)
    value["billing"]["observed_at"] = clock.now.isoformat()
    value["resource_costs"]["/vm/second"] = {"actual_cost_mtd": 0}
    scanner.fetch_billing.return_value = value
    monkeypatch.setattr(billing, "_CONFIG", replace(billing._CONFIG, max_resource_rows=1))
    result = await billing.refresh_azure_billing(scanner, db=db, user_id=USER, subscription_id=SUBSCRIPTION)
    assert result["billing"]["reason"] == "cache_capacity_exceeded"
    assert db.saved == old
    assert result["resource_costs"] == old["resource_costs"]
