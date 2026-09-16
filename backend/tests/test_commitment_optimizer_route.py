import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("CLERK_SECRET_KEY", "test_clerk_secret_key_12345")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test_db")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")

import tests.conftest  # noqa: F401

import unittest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client
from app.core.commitment_engine import commitment_engine


class FakeOptimizerDB:
    def __init__(self, integrations=None, resources=None, daily_spend=None):
        self.integrations = integrations or []
        self.resources = resources or []
        self.daily_spend = daily_spend or []

    async def get_user_integrations(self, user_id):
        return [i for i in self.integrations if i.get("user_id") == user_id]

    async def get_daily_spend_history(self, user_id, integration_id=None, days=90):
        if integration_id:
            return [
                d for d in self.daily_spend
                if d.get("integration_id") == integration_id
            ][-days:]
        return self.daily_spend[-days:]

    async def get_resources(self, user_id, integration_id=None):
        if integration_id:
            return [
                r for r in self.resources
                if r.get("integration_id") == integration_id
            ]
        return list(self.resources)


class TestCommitmentOptimizerRoute(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.mock_commitments_patch = patch.object(
            commitment_engine, "get_commitments", new_callable=AsyncMock
        )
        self.mock_get_commitments = self.mock_commitments_patch.start()
        self.mock_get_commitments.return_value = []

    def tearDown(self):
        self.mock_commitments_patch.stop()

    def test_get_commitment_recommendations_authenticated_with_usage(self):
        daily_spend = [
            {
                "integration_id": "int-aws-1",
                "spend_date": f"2026-03-{d:02d}",
                "amount": 250.0 + (d * 2.0),
                "currency": "USD",
            }
            for d in range(1, 31)
        ]
        resources = [
            {
                "id": f"res-ec2-{i}",
                "integration_id": "int-aws-1",
                "service_type": "Amazon EC2",
                "cost": 150.0,
                "region": "us-east-1",
                "metadata": {"instance_type": "m5.xlarge"},
                "tags": {"environment": "production"},
            }
            for i in range(4)
        ]
        integrations = [
            {
                "id": "int-aws-1",
                "user_id": "user-test-1",
                "provider": "aws",
                "status": "active",
                "name": "Production AWS",
            }
        ]
        fake_db = FakeOptimizerDB(
            integrations=integrations,
            resources=resources,
            daily_spend=daily_spend,
        )

        self.app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-test-1")
        self.app.dependency_overrides[get_db_client] = lambda: fake_db

        client = TestClient(self.app)
        response = client.get("/api/commitment-recommendations")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("recommendations", data)
        self.assertIn("total_monthly_savings", data)
        self.assertIn("total_annual_savings", data)
        self.assertIn("overall_coverage_pct", data)
        self.assertIn("strategy_summary", data)

        self.assertGreater(data["total_annual_savings"], 0)
        self.assertGreater(len(data["recommendations"]), 0)

        first_rec = data["recommendations"][0]
        self.assertEqual(first_rec["provider"], "aws")
        self.assertIn("m5", first_rec["instance_family"])
        self.assertIn("savings", first_rec["explanation"].lower())
        self.assertIn("break_even_months", first_rec["math_breakdown"])

    def test_get_commitment_recommendations_with_query_params(self):
        daily_spend = [
            {
                "integration_id": "int-aws-1",
                "spend_date": f"2026-03-{d:02d}",
                "amount": 300.0,
                "currency": "USD",
            }
            for d in range(1, 31)
        ]
        resources = [
            {
                "id": "res-ec2-1",
                "integration_id": "int-aws-1",
                "service_type": "Amazon EC2",
                "cost": 300.0,
                "region": "us-east-1",
                "metadata": {"instance_type": "c5.2xlarge"},
            }
        ]
        integrations = [
            {
                "id": "int-aws-1",
                "user_id": "user-test-2",
                "provider": "aws",
                "status": "active",
            }
        ]
        fake_db = FakeOptimizerDB(
            integrations=integrations,
            resources=resources,
            daily_spend=daily_spend,
        )

        self.app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-test-2")
        self.app.dependency_overrides[get_db_client] = lambda: fake_db

        client = TestClient(self.app)
        response = client.get(
            "/api/commitment-recommendations?coverage_target=80&max_term=3_year&payment_option=all_upfront"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recommendations", data)
        if data["recommendations"]:
            rec = data["recommendations"][0]
            self.assertEqual(rec["term"], "3_year")
            self.assertEqual(rec["payment_option"], "all_upfront")

    def test_get_commitment_recommendations_with_underutilized_and_expiring(self):
        daily_spend = [
            {
                "integration_id": "int-aws-1",
                "spend_date": f"2026-03-{d:02d}",
                "amount": 200.0,
                "currency": "USD",
            }
            for d in range(1, 31)
        ]
        resources = [
            {
                "id": "res-ec2-1",
                "integration_id": "int-aws-1",
                "service_type": "Amazon EC2",
                "cost": 200.0,
                "region": "us-east-1",
                "metadata": {"instance_type": "t3.medium"},
            }
        ]
        integrations = [
            {
                "id": "int-aws-1",
                "user_id": "user-test-3",
                "provider": "aws",
                "status": "active",
            }
        ]
        fake_db = FakeOptimizerDB(
            integrations=integrations,
            resources=resources,
            daily_spend=daily_spend,
        )

        now = datetime.now(timezone.utc)
        expiring_date = (now + timedelta(days=25)).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.mock_get_commitments.return_value = [
            {
                "id": "comm-under-1",
                "name": "Underutilized Compute SP",
                "type": "Savings Plan",
                "status": "active",
                "utilization_pct": 42.0,
                "commitment_amount": 1000.0,
                "end_date": (now + timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            {
                "id": "comm-exp-1",
                "name": "Expiring Soon EC2 RI",
                "type": "Reservation",
                "status": "active",
                "utilization_pct": 92.0,
                "commitment_amount": 800.0,
                "end_date": expiring_date,
            },
        ]

        self.app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-test-3")
        self.app.dependency_overrides[get_db_client] = lambda: fake_db

        client = TestClient(self.app)
        response = client.get("/api/commitment-recommendations")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["underutilized_commitments"]), 1)
        self.assertEqual(data["underutilized_commitments"][0]["id"], "comm-under-1")
        self.assertGreater(data["underutilized_commitments"][0]["wasted_monthly"], 0)

        self.assertEqual(len(data["expiring_soon"]), 1)
        self.assertEqual(data["expiring_soon"][0]["id"], "comm-exp-1")
        self.assertEqual(data["expiring_soon"][0]["action"], "Renew")

    def test_get_commitment_recommendations_empty_returns_clean_portfolio(self):
        fake_db = FakeOptimizerDB()
        self.app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-empty")
        self.app.dependency_overrides[get_db_client] = lambda: fake_db

        client = TestClient(self.app)
        response = client.get("/api/commitment-recommendations")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["recommendations"], [])
        self.assertEqual(data["total_monthly_savings"], 0.0)
        self.assertIn("No commitment recommendations", data["strategy_summary"])


if __name__ == "__main__":
    unittest.main()
