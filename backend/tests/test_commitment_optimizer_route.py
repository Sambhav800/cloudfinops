import os
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("CLERK_SECRET_KEY", "test_clerk_secret_key_12345")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test_db")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")

import tests.conftest  # noqa: F401

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.finance_routes import finance_router
from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.core import commitment_optimizer, commitment_recommendations
from app.core.commitment_engine import commitment_engine
from app.core.commitment_recommendations import PURCHASE_SNAPSHOTS, SOURCE
from app.db import get_db_client

USER_ID = "user-1"
INTEGRATION_ID = "int-aws"
ACCOUNT_ID = "123456789012"
ROUTE = "/api/commitment-recommendations"
FINANCE_ROUTE = "/api/finance/commitment-recommendation"


def integration(
    integration_id: str = INTEGRATION_ID,
    *,
    user_id: str = USER_ID,
    provider: str = "aws",
    status: str = "active",
) -> dict[str, str]:
    return {"id": integration_id, "user_id": user_id, "provider": provider, "status": status}


def snapshot(
    now: datetime,
    *,
    integration_id: str = INTEGRATION_ID,
    account_id: str = ACCOUNT_ID,
    user_id: str = USER_ID,
) -> dict[str, object]:
    scenarios: list[dict[str, object]] = []
    for years, monthly_saving in ((1, 10.0), (3, 25.0)):
        scenarios.append({
            "label": f"{years}-year Compute Savings Plan",
            "monthly_commitment_usd": 365.0,
            "monthly_saving_usd": monthly_saving,
            "annual_saving_usd": monthly_saving * 12,
            "term_years": years,
            "hourly_commitment_usd": 0.5,
            "integration_id": integration_id,
            "account_id": account_id,
            "recommendation_id": f"{integration_id}-{years}",
            "generated_at": now.isoformat(),
        })
    return {
        "id": f"{user_id}-{integration_id}",
        "user_id": user_id,
        "integration_id": integration_id,
        "account_id": account_id,
        "source": SOURCE,
        "status": "ready",
        "fetched_at": now.isoformat(),
        "generated_at": now.isoformat(),
        "scenarios": scenarios,
    }


class FakeOptimizerDB:
    def __init__(self) -> None:
        self.integrations = [integration()]
        self.rows: list[dict[str, object]] = []
        self.integration_reads: list[str] = []
        self.snapshot_reads: list[dict[str, str]] = []
        self.failure_on: str | None = None

    async def get_user_integrations(self, user_id: str) -> list[dict[str, str]]:
        assert user_id == USER_ID
        self.integration_reads.append(user_id)
        if self.failure_on == "integrations":
            raise RuntimeError("secret database address")
        return deepcopy([row for row in self.integrations if row["user_id"] == user_id])

    async def select(self, table: str, filters: dict[str, str]) -> list[dict[str, object]]:
        assert table == PURCHASE_SNAPSHOTS
        assert filters["user_id"] == USER_ID
        self.snapshot_reads.append(dict(filters))
        if self.failure_on == "snapshots":
            raise RuntimeError("secret database address")
        return deepcopy([
            row for row in self.rows
            if all(row.get(key) == value for key, value in filters.items())
        ])


@pytest.fixture(autouse=True)
def forbid_legacy_and_provider_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    calls: list[Mock] = []
    for method in ("get_resources", "get_daily_spend_history"):
        guard = AsyncMock(side_effect=AssertionError(f"Unexpected legacy read: {method}"))
        monkeypatch.setattr(FakeOptimizerDB, method, guard, raising=False)
        calls.append(guard)
    for method in ("get_commitments", "get_portfolio_snapshot"):
        guard = AsyncMock(side_effect=AssertionError(f"Unexpected inventory read: {method}"))
        monkeypatch.setattr(commitment_engine, method, guard)
        calls.append(guard)
    for method in ("analyze_usage_baselines", "generate_commitment_recommendations"):
        guard = Mock(side_effect=AssertionError(f"Unexpected legacy optimizer: {method}"))
        monkeypatch.setattr(commitment_optimizer, method, guard)
        calls.append(guard)
    guard = Mock(side_effect=AssertionError("GET must not fetch provider estimates"))
    monkeypatch.setattr(commitment_recommendations, "fetch_aws_purchase_recommendations", guard)
    calls.append(guard)
    yield
    for call in calls:
        call.assert_not_called()


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=1)


@pytest.fixture
def db() -> FakeOptimizerDB:
    return FakeOptimizerDB()


@pytest.fixture
def app(db: FakeOptimizerDB) -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    application.include_router(finance_router)
    application.dependency_overrides[get_current_user] = lambda: ClerkUser(id=USER_ID)
    application.dependency_overrides[get_db_client] = lambda: db
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_route_declares_canonical_response_model(app: FastAPI) -> None:
    schema = app.openapi()["paths"][ROUTE]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/CommitmentRecommendationResult"}


@pytest.mark.parametrize("scoped", [False, True])
def test_ready_snapshot_matches_finance_without_summing_term_alternatives(
    client: TestClient, db: FakeOptimizerDB, now: datetime, scoped: bool,
) -> None:
    db.rows = [snapshot(now)]
    params = {"integration_id": INTEGRATION_ID} if scoped else {}
    response = client.get(ROUTE, params=params)
    finance = client.get(FINANCE_ROUTE, params=params)
    assert response.status_code == finance.status_code == 200
    payload = response.json()
    assert payload == finance.json()
    assert payload["status"] == "ready"
    assert payload["pricing_basis"] == "live_api"
    assert payload["source"] == SOURCE
    assert payload["currency"] == "USD"
    assert payload["fetched_at"] == payload["generated_at"] == now.isoformat()
    assert payload["analysis_basis_days"] == 60
    assert [row["term_years"] for row in payload["scenarios"]] == [1, 3]
    assert [row["monthly_saving_usd"] for row in payload["scenarios"]] == [10, 25]
    assert [row["annual_saving_usd"] for row in payload["scenarios"]] == [120, 300]
    assert "total_monthly_savings" not in payload
    assert "total_annual_savings" not in payload
    assert payload["recommended_scenario"] is None
    assert payload["safe_baseline_monthly_usd"] is None
    assert payload["compute_fraction_pct"] is None
    assert any("alternatives" in note for note in payload["important_notes"])
    for option in payload["scenarios"]:
        assert option["monthly_commitment_usd"] == 365
        assert option["payment_option"] == "NO_UPFRONT"
        assert option["over_commitment_risk_pct"] is None
        assert option["effective_discount_pct"] is None
        assert option["estimated_utilization_pct"] is None
    assert db.integration_reads == [USER_ID, USER_ID]
    assert db.snapshot_reads == [{"user_id": USER_ID, **params}] * 2


@pytest.mark.parametrize("status", ["not_synced", "unavailable", "no_recommendations"])
def test_nonready_snapshot_matches_finance_without_buy_signals(
    client: TestClient, db: FakeOptimizerDB, now: datetime, status: str,
) -> None:
    if status != "not_synced":
        row = snapshot(now)
        row["status"] = status
        if status == "no_recommendations":
            row["scenarios"] = []
        db.rows = [row]
    response = client.get(ROUTE)
    finance = client.get(FINANCE_ROUTE)
    assert response.status_code == finance.status_code == 200
    assert response.json() == finance.json()
    payload = response.json()
    assert payload["status"] == status
    assert payload["scenarios"] == []
    assert payload["pricing_basis"] is None
    assert payload["recommended_scenario"] is None


@pytest.mark.parametrize("field", ["fetched_at", "generated_at"])
@pytest.mark.parametrize("age_hours", [72, -24, None])
def test_stale_future_or_missing_timestamps_withhold_purchase_estimates(
    client: TestClient, db: FakeOptimizerDB, now: datetime, field: str, age_hours: int | None,
) -> None:
    row = snapshot(now)
    row[field] = (now - timedelta(hours=age_hours)).isoformat() if age_hours is not None else None
    db.rows = [row]
    response = client.get(ROUTE)
    finance = client.get(FINANCE_ROUTE)
    assert response.status_code == finance.status_code == 200
    assert response.json() == finance.json()
    assert response.json()["status"] == "stale"
    assert response.json()["scenarios"] == []
    assert response.json()["pricing_basis"] is None


@pytest.mark.parametrize("provider", ["azure", "gcp"])
@pytest.mark.parametrize("scoped", [False, True])
def test_unsupported_provider_matches_finance_without_snapshot_reads(
    client: TestClient, db: FakeOptimizerDB, provider: str, scoped: bool,
) -> None:
    db.integrations = [integration(provider=provider)]
    params = {"integration_id": INTEGRATION_ID} if scoped else {}
    response = client.get(ROUTE, params=params)
    finance = client.get(FINANCE_ROUTE, params=params)
    assert response.status_code == finance.status_code == 200
    assert response.json() == finance.json()
    assert response.json()["status"] == "unsupported"
    assert response.json()["scenarios"] == []
    assert db.snapshot_reads == []


def test_empty_portfolio_matches_finance(client: TestClient, db: FakeOptimizerDB) -> None:
    db.integrations = []
    response = client.get(ROUTE)
    finance = client.get(FINANCE_ROUTE)
    assert response.status_code == finance.status_code == 200
    assert response.json() == finance.json()
    assert response.json()["status"] == "no_spend_data"
    assert response.json()["scenarios"] == []
    assert db.snapshot_reads == []


@pytest.mark.parametrize("scoped", [False, True])
def test_only_owned_active_snapshots_are_returned(
    client: TestClient, db: FakeOptimizerDB, now: datetime, scoped: bool,
) -> None:
    db.integrations += [
        integration("int-other"),
        integration("int-inactive", status="inactive"),
        integration("int-foreign", user_id="other-user"),
    ]
    db.rows = [
        snapshot(now),
        snapshot(now, integration_id="int-other", account_id="222222222222"),
        snapshot(now, integration_id="int-inactive", account_id="333333333333"),
        snapshot(now, integration_id="int-foreign", account_id="444444444444", user_id="other-user"),
        snapshot(now, account_id="555555555555", user_id="other-user"),
    ]
    params = {"integration_id": INTEGRATION_ID} if scoped else {}
    response = client.get(ROUTE, params=params)
    assert response.status_code == 200
    options = response.json()["scenarios"]
    expected_ids = {INTEGRATION_ID} if scoped else {INTEGRATION_ID, "int-other"}
    assert {row["integration_id"] for row in options} == expected_ids
    assert {row["account_id"] for row in options} <= {ACCOUNT_ID, "222222222222"}
    assert len(options) == 2 * len(expected_ids)
    assert db.snapshot_reads == [{"user_id": USER_ID, **params}]


@pytest.mark.parametrize("integration_id", ["missing", "int-foreign", "int-inactive"])
def test_missing_foreign_or_inactive_integration_returns_404_before_snapshot_reads(
    client: TestClient, db: FakeOptimizerDB, now: datetime, integration_id: str,
) -> None:
    db.integrations += [
        integration("int-foreign", user_id="other-user"),
        integration("int-inactive", status="inactive"),
    ]
    db.rows = [snapshot(now)]
    params = {"integration_id": integration_id}
    response = client.get(ROUTE, params=params)
    finance = client.get(FINANCE_ROUTE, params=params)
    assert response.status_code == finance.status_code == 404
    assert response.json() == finance.json() == {"detail": "Integration not found"}
    assert db.snapshot_reads == []


@pytest.mark.parametrize("failure_on", ["integrations", "snapshots"])
def test_database_failures_return_sanitized_503(
    client: TestClient, db: FakeOptimizerDB, failure_on: str, caplog: pytest.LogCaptureFixture,
) -> None:
    db.failure_on = failure_on
    response = client.get(ROUTE)
    finance = client.get(FINANCE_ROUTE)
    assert response.status_code == finance.status_code == 503
    assert response.json() == finance.json() == {
        "detail": "Commitment recommendations are temporarily unavailable",
    }
    assert "secret database address" not in response.text + caplog.text


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer malformed-token"},
    {"x-cloudfinops-user-id": USER_ID},
])
def test_authentication_is_required_before_database_reads(
    client: TestClient, app: FastAPI, db: FakeOptimizerDB, headers: dict[str, str],
) -> None:
    app.dependency_overrides.pop(get_current_user)
    response = client.get(ROUTE, headers=headers)
    assert response.status_code == 401
    assert db.integration_reads == db.snapshot_reads == []


@pytest.mark.parametrize("query", [
    "coverage_target=75", "coverage_target=80", "coverage_target=0", "coverage_target=",
    "max_term=1_year", "max_term=3_year", "max_term=", "max_term=invalid",
    "payment_option=no_upfront", "payment_option=all_upfront", "payment_option=",
    "coverage_target=80&max_term=3_year&payment_option=all_upfront",
    "coverage_target=75&coverage_target=80",
])
def test_legacy_customization_is_rejected_before_reading_snapshots(
    client: TestClient, db: FakeOptimizerDB, now: datetime, query: str,
) -> None:
    db.rows = [snapshot(now)]
    response = client.get(f"{ROUTE}?integration_id={INTEGRATION_ID}&{query}")
    assert response.status_code == 422
    assert "unsupported" in response.json()["detail"].lower()
    assert db.integration_reads == db.snapshot_reads == []


@pytest.mark.parametrize("utilization", [0.0, None])
def test_measured_zero_savings_remain_zero_without_invented_utilization(
    client: TestClient, db: FakeOptimizerDB, now: datetime, utilization: float | None,
) -> None:
    row = snapshot(now)
    options = row["scenarios"]
    assert isinstance(options, list)
    for option in options:
        option.update(monthly_saving_usd=0, annual_saving_usd=0, estimated_utilization_pct=utilization)
    db.rows = [row]
    response = client.get(ROUTE)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    for option in response.json()["scenarios"]:
        assert option["monthly_saving_usd"] == option["annual_saving_usd"] == 0
        assert option["estimated_utilization_pct"] == utilization


@pytest.mark.parametrize("field,value", [
    ("monthly_saving_usd", None),
    ("account_id", "999999999999"),
    ("integration_id", "int-foreign"),
    ("generated_at", "invalid"),
])
def test_invalid_persisted_estimates_are_unavailable(
    client: TestClient, db: FakeOptimizerDB, now: datetime, field: str, value: str | None,
) -> None:
    row = snapshot(now)
    options = row["scenarios"]
    assert isinstance(options, list)
    options[0][field] = value
    db.rows = [row]
    response = client.get(ROUTE)
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["scenarios"] == []
