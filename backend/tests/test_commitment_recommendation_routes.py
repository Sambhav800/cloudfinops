from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.finance_routes import finance_router
from app.auth import ClerkUser, get_current_user
from app.core.commitment_recommendations import SOURCE, PURCHASE_SNAPSHOTS
from app.db import get_db_client


class FakeCommitmentDB:
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def get_user_integrations(self, user_id):
        return [{"id": "int-aws", "user_id": user_id, "provider": "aws", "status": "active"}]

    async def select(self, table, filters):
        assert table == PURCHASE_SNAPSHOTS
        assert filters["user_id"] == "user-1"
        return self.rows

    async def get_daily_spend_history(self, *args, **kwargs):
        raise AssertionError("Daily total bills cannot size hourly commitments")


def client(db):
    app = FastAPI()
    app.include_router(finance_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: db
    return TestClient(app)


def test_daily_spend_without_native_estimate_cannot_create_purchase_scenarios():
    response = client(FakeCommitmentDB()).get("/api/finance/commitment-recommendation")
    assert response.status_code == 200
    assert response.json()["status"] == "not_synced"
    assert response.json()["scenarios"] == []
    assert response.json()["compute_fraction_pct"] is None
    assert response.json()["recommended_scenario"] is None


def test_native_estimate_is_returned_without_currency_conversion_or_fake_risk():
    now = datetime.now(timezone.utc).isoformat()
    option = {
        "label": "1-year Compute Savings Plan", "monthly_commitment_usd": 365,
        "monthly_saving_usd": 10, "annual_saving_usd": 120, "term_years": 1,
        "hourly_commitment_usd": 0.5, "integration_id": "int-aws",
        "account_id": "123456789012", "recommendation_id": "native-1", "generated_at": now,
    }
    row = {"user_id": "user-1", "integration_id": "int-aws", "account_id": "123456789012", "status": "ready", "source": SOURCE, "fetched_at": now, "generated_at": now, "scenarios": [option]}
    response = client(FakeCommitmentDB([row])).get("/api/finance/commitment-recommendation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["scenarios"][0]["monthly_commitment_usd"] == 365
    assert payload["scenarios"][0]["over_commitment_risk_pct"] is None
    assert payload["pricing_basis"] == "live_api"
    assert payload["recommended_scenario"] is None


def test_cross_tenant_or_inactive_integration_is_not_found():
    response = client(FakeCommitmentDB()).get("/api/finance/commitment-recommendation?integration_id=other-tenant")
    assert response.status_code == 404


def test_db_failure_returns_service_error_without_leaking_exception():
    class FailingDB(FakeCommitmentDB):
        async def select(self, table, filters):
            raise RuntimeError("secret database address")
    response = client(FailingDB()).get("/api/finance/commitment-recommendation")
    assert response.status_code == 503
    assert "secret" not in response.text
