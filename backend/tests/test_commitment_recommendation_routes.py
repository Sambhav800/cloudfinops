from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.finance_routes import finance_router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeCommitmentRecommendationDB:
    def __init__(self, *, aws_history, resources=None):
        self.integrations = [
            {
                "id": "int-aws",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Prod AWS",
                "status": "active",
            },
            {
                "id": "int-gcp",
                "user_id": "user-1",
                "provider": "gcp",
                "name": "Analytics GCP",
                "status": "active",
            },
        ]
        self.history_by_integration = {
            "int-aws": list(aws_history),
            "int-gcp": [
                {"spend_date": "2026-03-01", "amount": 999.0, "currency": "USD"},
            ],
        }
        self.resources = list(resources or [])

    async def get_integration(self, integration_id, user_id):
        return next(
            (
                integration
                for integration in self.integrations
                if integration.get("id") == integration_id and integration.get("user_id") == user_id
            ),
            None,
        )

    async def get_user_integrations(self, user_id):
        return [integration for integration in self.integrations if integration.get("user_id") == user_id]

    async def get_daily_spend_history(self, user_id, integration_id=None, days=180):
        rows = self.history_by_integration.get(integration_id or "", [])
        return rows[-days:]

    async def get_resources(self, user_id, integration_id=None):
        if integration_id:
            return [
                resource
                for resource in self.resources
                if resource.get("integration_id") == integration_id
            ]
        return list(self.resources)


def _build_client(fake_db: FakeCommitmentRecommendationDB) -> TestClient:
    app = FastAPI()
    app.include_router(finance_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_commitment_recommendation_ready_returns_forecast_backed_scenarios(monkeypatch):
    history = [
        {
            "spend_date": f"2026-03-{day:02d}",
            "amount": float(100 + day),
            "currency": "USD",
        }
        for day in range(1, 21)
    ]
    fake_db = FakeCommitmentRecommendationDB(
        aws_history=history,
        resources=[
            {"integration_id": "int-aws", "service_type": "ec2", "cost": 900.0},
            {"integration_id": "int-aws", "service_type": "rds", "cost": 300.0},
        ],
    )
    client = _build_client(fake_db)

    def fake_forecast_summary(*args, **kwargs):
        return {
            "forecast_eom_spend": 3200.0,
            "forecast_method": "holt_winters",
            "forecast_stable": True,
            "history_days_used": 20,
        }

    monkeypatch.setattr("app.api.finance_routes.build_forecast_summary", fake_forecast_summary)

    response = client.get("/api/finance/commitment-recommendation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["analysis_basis_days"] == 20
    assert payload["forecast_eom_spend_usd"] == 3200.0
    assert payload["forecast_method"] == "holt_winters"
    assert payload["forecast_stable"] is True
    assert payload["compute_fraction_pct"] == 75.0
    assert len(payload["scenarios"]) == 4
    assert {scenario["label"] for scenario in payload["scenarios"]} == {
        "Conservative",
        "Recommended",
        "Aggressive",
        "3-Year Optimal",
    }
    assert payload["recommended_scenario"]["label"] in {
        scenario["label"] for scenario in payload["scenarios"]
    }
    assert payload["aws_console_link"] == "https://console.aws.amazon.com/billing/home#/bills"
    assert any("Forecast anchor: Holt-Winters" in note for note in payload["important_notes"])


def test_commitment_recommendation_requires_minimum_history():
    history = [
        {
            "spend_date": f"2026-03-{day:02d}",
            "amount": float(75 + day),
            "currency": "USD",
        }
        for day in range(1, 11)
    ]
    client = _build_client(FakeCommitmentRecommendationDB(aws_history=history))

    response = client.get("/api/finance/commitment-recommendation")

    assert response.status_code == 200
    assert response.json() == {
        "status": "insufficient_history",
        "message": "Need at least 14 days of spend history for reliable recommendations.",
        "days_available": 10,
        "analysis_basis_days": None,
        "avg_monthly_spend_usd": None,
        "forecast_eom_spend_usd": None,
        "forecast_method": None,
        "forecast_stable": None,
        "spend_volatility_pct": None,
        "compute_fraction_pct": None,
        "safe_baseline_monthly_usd": None,
        "scenarios": [],
        "recommended_scenario": None,
        "important_notes": [],
        "aws_console_link": None,
    }


def test_commitment_recommendation_handles_zero_spend_history():
    history = [
        {
            "spend_date": f"2026-03-{day:02d}",
            "amount": 0.0,
            "currency": "USD",
        }
        for day in range(1, 21)
    ]
    client = _build_client(FakeCommitmentRecommendationDB(aws_history=history))

    response = client.get("/api/finance/commitment-recommendation")

    assert response.status_code == 200
    assert response.json() == {
        "status": "no_spend_data",
        "message": "No AWS spend data is available yet. Run a fresh scan to populate billing history.",
        "days_available": None,
        "analysis_basis_days": None,
        "avg_monthly_spend_usd": None,
        "forecast_eom_spend_usd": None,
        "forecast_method": None,
        "forecast_stable": None,
        "spend_volatility_pct": None,
        "compute_fraction_pct": None,
        "safe_baseline_monthly_usd": None,
        "scenarios": [],
        "recommended_scenario": None,
        "important_notes": [],
        "aws_console_link": None,
    }
