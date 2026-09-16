"""Persist Azure billing and coordinate refreshes across users and processes."""

import asyncio
import hashlib
import json
import logging
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal, NotRequired, Protocol, TypedDict, cast
from uuid import uuid4

from bson import BSON
from bson.errors import InvalidDocument
from pymongo.errors import DuplicateKeyError

from .retry import _retry_after_seconds

logger = logging.getLogger(__name__)

_TABLE = "azure_billing_refresh"
Availability = Literal["resource_costs_available", "subscription_costs_available", "daily_costs_available"]
_PARTS: tuple[Availability, ...] = ("resource_costs_available", "subscription_costs_available", "daily_costs_available")


class BillingMetadata(TypedDict):
    status: Literal["fresh", "cached", "stale", "unavailable"]
    observed_at: str | None
    period_start: str
    reason: str | None
    retry_at: str | None
    resource_costs_available: bool
    subscription_costs_available: bool
    daily_costs_available: bool


class DailyCost(TypedDict):
    date: str
    amount: float
    service_breakdown: NotRequired[dict[str, float]]


class SubscriptionCosts(TypedDict, total=False):
    total: float
    by_service: dict[str, float]
    daily_totals: list[DailyCost]
    currency: str


class BillingSnapshot(TypedDict):
    resource_costs: dict[str, dict[str, object]]
    subscription_costs: SubscriptionCosts
    billing: BillingMetadata


class BillingScanner(Protocol):
    def fetch_billing(self) -> BillingSnapshot:
        """Fetch billing synchronously within a 240-second budget."""
        ...


class BillingDB(Protocol):
    async def select(self, table: str, *, filters: dict[str, object]) -> list[dict[str, object]]: ...

    async def upsert(self, table: str, data: dict[str, object]) -> object: ...

    async def update(self, table: str, data: dict[str, object], filters: dict[str, object]) -> object: ...


@dataclass(frozen=True)
class BillingRefreshConfig:
    cache_ttl_seconds: int = 6 * 60 * 60
    cooldown_seconds: int = 15 * 60
    lease_seconds: int = 10 * 60
    max_cache_bytes: int = 4 * 1024 * 1024
    max_resource_rows: int = 10_000


_CONFIG = BillingRefreshConfig()
_REFRESH_TASKS: set[asyncio.Task[BillingSnapshot]] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _period(now: datetime) -> str:
    return now.date().replace(day=1).isoformat()


def _scope(user_id: str, subscription_id: str) -> dict[str, object]:
    subscription = subscription_id.strip().strip("/").lower()
    if subscription == "subscriptions":
        raise ValueError("Missing subscription ID")
    if subscription.startswith("subscriptions/"):
        subscription = subscription[len("subscriptions/"):]
    subscription = subscription.strip("{}")
    if not user_id.strip() or not subscription or "/" in subscription:
        raise ValueError("Invalid billing scope")
    key = hashlib.sha256(json.dumps([user_id, subscription]).encode("utf-8")).hexdigest()
    return {"_id": key, "id": key, "user_id": user_id}


def _empty(now: datetime) -> BillingSnapshot:
    return {
        "resource_costs": {},
        "subscription_costs": {},
        "billing": {
            "status": "unavailable", "observed_at": None, "period_start": _period(now),
            "reason": None, "retry_at": None, "resource_costs_available": False,
            "subscription_costs_available": False, "daily_costs_available": False,
        },
    }


def _cached(state: dict[str, object], now: datetime) -> BillingSnapshot:
    snapshot = cast(BillingSnapshot | None, state.get("snapshot"))
    if snapshot and snapshot["billing"]["period_start"] == _period(now):
        return deepcopy(snapshot)
    return _empty(now)


def _available(snapshot: BillingSnapshot) -> bool:
    return any(snapshot["billing"][part] for part in _PARTS)


def _fallback(
    state: dict[str, object], now: datetime, reason: str,
    retry_at: str | None = None, *, cached: bool = False,
) -> BillingSnapshot:
    result = _cached(state, now)
    result["billing"].update(
        status=("cached" if cached else "stale") if _available(result) else "unavailable",
        reason=None if cached else reason, retry_at=retry_at,
    )
    return result


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_daily_rows(rows: object, now: datetime) -> bool:
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str) or not _number(row.get("amount")):
            return False
        try:
            day = date.fromisoformat(row["date"])
        except ValueError:
            return False
        if day.isoformat() != row["date"] or day.replace(day=1).isoformat() != _period(now):
            return False
    return True


def _valid_resource_costs(costs: object, now: datetime) -> bool:
    if not isinstance(costs, dict):
        return False
    for resource_id, row in costs.items():
        if not isinstance(resource_id, str) or not resource_id or not isinstance(row, dict):
            return False
        if not _number(row.get("actual_cost_mtd", row.get("actual_cost_30d"))):
            return False
        if "actual_cost_30d" in row and not _number(row["actual_cost_30d"]):
            return False
        # Older snapshots omit row-level periods and inherit the validated snapshot period.
        if "period_start" in row and row["period_start"] != _period(now):
            return False
        if "daily_costs" in row and not _valid_daily_rows(row["daily_costs"], now):
            return False
    return True


def _merge(
    state: dict[str, object], incoming: BillingSnapshot, now: datetime,
) -> tuple[BillingSnapshot, dict[str, str], bool]:
    """Replace successful parts, retaining provenance for same-period fallback parts."""
    result = _cached(state, now)
    stamps = dict(cast(dict[str, str], state.get("part_observed_at", {}))) if _available(result) else {}
    metadata = incoming["billing"]
    observed = _date(metadata["observed_at"])
    if metadata["status"] not in {"fresh", "stale"}:
        raise ValueError("invalid_snapshot")
    if metadata["period_start"] != _period(now):
        raise ValueError("period_mismatch")
    if observed is None or observed > now or _period(observed) != _period(now):
        raise ValueError("invalid_snapshot")
    costs = incoming["subscription_costs"]
    currency = costs.get("currency")
    old_currency = result["subscription_costs"].get("currency")
    if _available(incoming) and currency and old_currency and currency != old_currency:
        result, stamps = _empty(now), {}

    resource_ok = (
        metadata["resource_costs_available"] is True and _valid_resource_costs(incoming["resource_costs"], now)
    )
    subscription_ok = (
        metadata["subscription_costs_available"] is True
        and _number(costs.get("total")) and isinstance(costs.get("by_service"), dict)
        and all(_number(value) for value in costs["by_service"].values())
        and isinstance(currency, str) and bool(currency)
    )
    daily = costs.get("daily_totals")
    daily_ok = (
        metadata["daily_costs_available"] is True and _valid_daily_rows(daily, now)
        and isinstance(currency, str) and bool(currency)
    )
    if resource_ok:
        result["resource_costs"] = deepcopy(incoming["resource_costs"])
    if subscription_ok:
        result["subscription_costs"].update(
            total=costs["total"], by_service=deepcopy(costs["by_service"]), currency=cast(str, currency),
        )
    if daily_ok:
        result["subscription_costs"].update(
            daily_totals=deepcopy(cast(list[DailyCost], daily)), currency=cast(str, currency),
        )
    for part, succeeded in zip(_PARTS, (resource_ok, subscription_ok, daily_ok)):
        if succeeded:
            result["billing"][part] = True
            stamps[part] = cast(str, metadata["observed_at"])
    if stamps:
        result["billing"]["observed_at"] = min(stamps.values(), key=lambda value: cast(datetime, _date(value)))
    complete = resource_ok and subscription_ok and daily_ok and metadata["status"] == "fresh"
    result["billing"]["status"] = "fresh" if complete else ("stale" if _available(result) else "unavailable")
    return result, stamps, complete


def _reason(value: object, default: str = "billing_refresh_failed") -> str:
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value) else default


def _cache_failure(state: dict[str, object], patch: dict[str, object], config: BillingRefreshConfig) -> str | None:
    snapshot = cast(BillingSnapshot, patch["snapshot"])
    if len(snapshot["resource_costs"]) > config.max_resource_rows:
        return "cache_capacity_exceeded"
    try:
        if len(BSON.encode({**state, **patch})) > config.max_cache_bytes:
            return "cache_capacity_exceeded"
    except (InvalidDocument, OverflowError, TypeError, ValueError):
        return "cache_serialization_failed"
    return None


async def _refresh_owned(
    scanner: BillingScanner, db: BillingDB, scope: dict[str, object], config: BillingRefreshConfig,
) -> BillingSnapshot:
    state: dict[str, object] = {}
    try:
        rows = await db.select(_TABLE, filters=scope)
        if not rows:
            try:
                # Identity only: a racing bootstrap must never reset a lease or cache.
                await db.upsert(_TABLE, dict(scope))
            except DuplicateKeyError:
                logger.debug("Azure billing cache bootstrap raced with another refresh")
            rows = await db.select(_TABLE, filters=scope)
        if not rows:
            raise RuntimeError("Billing coordination document missing")
        state = rows[0]
        now = _now()
        retry_at = _date(state.get("retry_at"))
        if retry_at and retry_at > now:
            return _fallback(state, now, "cooldown", _iso(retry_at))
        lease_until = float(state.get("lease_until", 0))
        if lease_until > now.timestamp():
            return _fallback(state, now, "refresh_in_progress", _iso(datetime.fromtimestamp(lease_until, timezone.utc)))
        if float(state.get("cache_until", 0)) > now.timestamp() and _available(_cached(state, now)):
            return _fallback(state, now, "", cached=True)

        owner = uuid4().hex
        version = int(state.get("lease_version", 0)) + 1
        filters = {
            **scope, "lease_owner": state.get("lease_owner"),
            "lease_version": state.get("lease_version", {"$exists": False}),
            "$or": [{"lease_until": {"$exists": False}}, {"lease_until": {"$lte": now.timestamp()}}],
        }
        await db.update(_TABLE, {
            "lease_owner": owner, "lease_version": version,
            "lease_until": now.timestamp() + config.lease_seconds,
        }, filters)
        rows = await db.select(_TABLE, filters=scope)
        state = rows[0] if rows else {}
        # update() re-selects its old CAS filters and can return [] after a successful write.
        if state.get("lease_owner") != owner or state.get("lease_version") != version:
            retry_at = _date(state.get("retry_at"))
            return _fallback(state, _now(), "refresh_in_progress", _iso(retry_at) if retry_at else None)
        if float(state.get("lease_until", 0)) - _now().timestamp() <= 240:
            return _fallback(state, _now(), "lease_lost")

        incoming = _empty(_now())
        reason = "billing_refresh_failed"
        provider_retry_at = None
        try:
            incoming = await asyncio.to_thread(scanner.fetch_billing)
            provider_retry_at = _date(incoming["billing"].get("retry_at"))
            reason = _reason(
                incoming["billing"].get("reason"),
                "partial_billing" if _available(incoming) else "billing_refresh_failed",
            )
        except Exception as error:
            logger.warning("Azure billing fetch failed; preserving successful cached parts")
            delay = _retry_after_seconds(error)
            if delay is not None and math.isfinite(delay):
                provider_retry_at = _now() + timedelta(seconds=delay)
        now = _now()
        merged, stamps, complete = _cached(state, now), {}, False
        try:
            if _available(incoming):
                merged, stamps, complete = _merge(state, incoming, now)
        except (KeyError, TypeError, ValueError) as error:
            reason = _reason(str(error), "invalid_snapshot")
        retry_at = None if complete else max(now + timedelta(seconds=config.cooldown_seconds), provider_retry_at or now)
        patch: dict[str, object] = {
            "lease_owner": None, "lease_until": 0, "completed_owner": owner,
            "retry_at": _iso(retry_at) if retry_at else None,
            "cache_until": cast(datetime, _date(merged["billing"]["observed_at"])).timestamp() + config.cache_ttl_seconds if complete else 0,
        }
        if stamps:
            patch.update(snapshot=merged, part_observed_at=stamps)
            cache_failure = _cache_failure(state, patch, config)
            if cache_failure == "cache_capacity_exceeded":
                # Keep verified subscription billing when the resource map cannot fit.
                reduced_stamps = {part: stamp for part, stamp in stamps.items() if part != "resource_costs_available"}
                if reduced_stamps:
                    reduced: BillingSnapshot = {
                        "resource_costs": {}, "subscription_costs": merged["subscription_costs"],
                        "billing": {
                            **merged["billing"], "status": "stale", "resource_costs_available": False,
                            "observed_at": min(reduced_stamps.values(), key=lambda value: cast(datetime, _date(value))),
                        },
                    }
                    smaller_patch = {**patch, "snapshot": reduced, "part_observed_at": reduced_stamps}
                    if _cache_failure(state, smaller_patch, config) is None:
                        patch = smaller_patch
                        cache_failure = "resource_cache_capacity_exceeded"
            if cache_failure:
                if cache_failure != "resource_cache_capacity_exceeded":
                    patch.pop("snapshot")
                    patch.pop("part_observed_at")
                complete, reason = False, cache_failure
                retry_at = max(now + timedelta(seconds=config.cooldown_seconds), provider_retry_at or now)
                patch.update(cache_until=0, retry_at=_iso(retry_at))
        patch["last_failure_reason"] = None if complete else reason
        await db.update(_TABLE, patch, {
            **scope, "lease_owner": owner, "lease_version": version,
            "lease_until": {"$gt": now.timestamp()},
        })
        rows = await db.select(_TABLE, filters=scope)
        current = rows[0] if rows else {}
        if current.get("completed_owner") != owner or current.get("lease_version") != version:
            return _fallback(current, _now(), "lease_lost")
        if complete:
            result = _cached(current, _now())
            result["billing"].update(reason=None, retry_at=None)
            return result
        return _fallback(current, _now(), reason, _iso(retry_at) if retry_at else None)
    except asyncio.CancelledError:
        # Shutdown can cancel this task even though callers shield it. The thread may still run.
        logger.debug("Azure billing refresh cancelled; retaining its lease until expiry")
        raise
    except Exception:
        logger.warning("Azure billing coordination unavailable; skipping uncoordinated billing")
        return _fallback(state, _now(), "coordination_unavailable")


async def refresh_azure_billing(
    scanner: BillingScanner, *, db: BillingDB, user_id: str, subscription_id: str,
) -> BillingSnapshot:
    """Return current billing or same-month stale data without overlapping provider calls."""
    try:
        scope = _scope(user_id, subscription_id)
        task = asyncio.create_task(_refresh_owned(scanner, db, scope, _CONFIG))
        _REFRESH_TASKS.add(task)
        task.add_done_callback(_REFRESH_TASKS.discard)
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        raise
    except ValueError:
        return _fallback({}, _now(), "invalid_scope")
    except Exception:
        logger.warning("Azure billing refresh unavailable")
        return _fallback({}, _now(), "coordination_unavailable")
