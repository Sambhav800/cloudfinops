from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.finance_estimate import estimate_router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeDb:
    def __init__(self):
        self.rows = []

    async def insert(self, table, data):
        self.rows.append(dict(data))
        return [dict(data)]

    async def select(self, table, columns="*", filters=None):
        filters = filters or {}
        return [
            dict(row)
            for row in self.rows
            if all(row.get(key) == value for key, value in filters.items())
        ]


def _build_client(db=None) -> TestClient:
    app = FastAPI()
    app.include_router(estimate_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: db if db is not None else object()
    return TestClient(app)


def test_finance_estimate_route_returns_summary_for_heuristic_resource(monkeypatch):
    async def _no_price(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _no_price)
    client = _build_client()

    response = client.post(
        "/api/finance/estimate",
        json={
            "plan": {
                "resource_changes": [
                    {
                        "type": "google_compute_instance",
                        "provider_name": "registry.terraform.io/hashicorp/google",
                        "change": {
                            "actions": ["create"],
                            "after": {"machine_type": "e2-standard-2", "zone": "us-central1-a"},
                        },
                    }
                ]
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "schema_version" not in payload
    assert "policy" not in payload
    assert payload["summary"]["estimated_resources"] == 1
    assert payload["summary"]["exact_pricing_resources"] == 0
    assert payload["resources"][0]["pricing_source"] == "heuristic_estimate"


def test_finance_estimate_route_keeps_usage_based_resources_visible(monkeypatch):
    async def _no_price(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _no_price)
    client = _build_client()

    response = client.post(
        "/api/finance/estimate",
        json={
            "plan": {
                "resource_changes": [
                    {
                        "type": "aws_lambda_function",
                        "change": {"actions": ["create"], "after": {}},
                    }
                ]
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["usage_based_resources"] == 1
    assert payload["resources"][0]["pricing_source"] == "usage_based"


def test_finance_estimate_route_handles_empty_plan(monkeypatch):
    async def _no_price(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _no_price)
    client = _build_client()

    response = client.post("/api/finance/estimate", json={"plan": {"resource_changes": []}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["delta_monthly_cost"] == 0.0
    assert payload["resources"] == []
    assert payload["summary"]["total_resources"] == 0


def test_finance_estimate_route_returns_v2_contract_with_header(monkeypatch):
    async def _no_price(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _no_price)
    db = FakeDb()
    client = _build_client(db)

    response = client.post(
        "/api/finance/estimate",
        headers={"X-Simulator-Version": "v2"},
        json={
            "plan": {
                "resource_changes": [
                    {
                        "type": "google_compute_instance",
                        "address": "google_compute_instance.api",
                        "provider_name": "registry.terraform.io/hashicorp/google",
                        "change": {
                            "actions": ["create"],
                            "after": {"machine_type": "e2-standard-2", "zone": "us-central1-a"},
                        },
                    },
                    {
                        "type": "aws_new_unmodeled_service",
                        "address": "aws_new_unmodeled_service.preview",
                        "provider_name": "registry.terraform.io/hashicorp/aws",
                        "change": {"actions": ["create"], "after": {}},
                    },
                    {
                        "type": "aws_eip",
                        "address": "aws_eip.static",
                        "provider_name": "registry.terraform.io/hashicorp/aws",
                        "change": {"actions": ["create"], "after": {}},
                    },
                ]
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "2026-04-simulator-v2"
    assert payload["currency"] == "USD"
    assert payload["monthly"]["after"] > 0
    assert payload["annual"]["after"] == payload["monthly"]["after"] * 12
    assert payload["summary"]["total_resources"] == 3
    assert payload["summary"]["priced_resources"] == 2
    assert payload["summary"]["estimated_resources"] == 2
    assert payload["summary"]["unestimated_resources"] == 1
    assert payload["resources"][0]["resource_address"] == "google_compute_instance.api"
    assert payload["resources"][0]["delta_monthly"] == payload["resources"][0]["after_monthly"]
    assert payload["unestimated_resources"][0]["resource_type"] == "aws_new_unmodeled_service"
    assert any(finding["finding_id"] == "public-ipv4-cost" for finding in payload["findings"])
    assert payload["policy"]["status"] == "warn"
    assert db.rows
    assert db.rows[0]["user_id"] == "user-1"
    assert "plan" not in db.rows[0]


def test_finance_estimate_history_route_filters_current_user():
    db = FakeDb()
    db.rows.append(
        {
            "id": "run-1",
            "user_id": "user-1",
            "source_type": "terraform_plan",
            "source_hash": "abc",
            "filename": "plan.json",
            "monthly": {"delta": 1.0},
            "annual": {"delta": 12.0},
            "summary": {"total_resources": 1},
            "resources": [{"resource_address": "aws_instance.web"}],
            "unestimated_resources": [],
            "findings": [],
            "policy": {"status": "pass"},
            "created_at": "2026-04-28T00:00:00+00:00",
        }
    )
    db.rows.append(
        {
            "id": "run-2",
            "user_id": "user-2",
            "source_type": "terraform_plan",
            "source_hash": "def",
            "created_at": "2026-04-28T00:01:00+00:00",
        }
    )
    client = _build_client(db)

    response = client.get("/api/finance/estimate/history")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["id"] == "run-1"
    assert payload["runs"][0]["_id"] == "run-1"
