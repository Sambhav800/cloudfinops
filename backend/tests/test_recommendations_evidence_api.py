"""
Integration test for Recommendation Evidence Card API endpoint.
"""

import os
import sys
from unittest.mock import MagicMock

# Set required environment variables for test execution
os.environ.setdefault("CLERK_SECRET_KEY", "test_clerk_secret_key_12345")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test_db")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")

# Import conftest stubs for optional cloud packages
import tests.conftest  # noqa: F401

# Stub boto3 and google.auth if needed
if "boto3" not in sys.modules:
    sys.modules["boto3"] = MagicMock()
if "google.auth" not in sys.modules:
    g_auth = MagicMock()
    g_auth.default = MagicMock(return_value=(MagicMock(), "test-proj"))
    sys.modules["google.auth"] = g_auth
if "google.cloud.storage" not in sys.modules:
    sys.modules["google.cloud.storage"] = MagicMock()

import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.recommendations_routes import recommendations_router
from app.auth import ClerkUser, get_current_user
from app.core.recommendations import RECOMMENDATION_LEDGER_COLLECTION
from app.db import get_db_client

TEST_REC_ID = "rec_0123456789abcdef01234567"
OTHER_REC_ID = "rec_fedcba9876543210fedcba98"


class FakeDB:
    def __init__(self):
        self.collections = {
            RECOMMENDATION_LEDGER_COLLECTION: [
                {
                    "id": TEST_REC_ID,
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "aws",
                    "resource_id": "i-08a9f3b12c4",
                    "cloud_resource_id": "i-08a9f3b12c4",
                    "resource_name": "prod-api-worker-01",
                    "resource_type": "AWS EC2 Instance",
                    "region": "us-east-1",
                    "recommendation_type": "rightsize",
                    "action": "rightsize",
                    "state": "ready_for_review",
                    "severity": "medium",
                    "confidence": 0.9,
                    "trust_score": 95,
                    "risk_level": "low",
                    "effort": "low",
                    "description": "Rightsize c5.2xlarge to c5.xlarge",
                    "estimated_monthly_savings": 122.64,
                    "estimated_monthly_waste": 245.28,
                    "cost_source": "actual",
                    "pricing_basis": "live_api",
                    "evidence_status": "ready",
                    "provider_agreement_status": "unknown",
                    "ai_enrichment_status": "pending",
                    "pipeline_version": "1.0.0",
                    "detected_at": "2026-09-01T12:00:00+00:00",
                },
                {
                    "id": OTHER_REC_ID,
                    "user_id": "user-other",
                    "integration_id": "int-other",
                    "provider": "azure",
                    "resource_id": "other-vm",
                    "cloud_resource_id": "other-vm",
                    "resource_name": "other-vm",
                    "resource_type": "Azure VM",
                    "action": "stop",
                    "state": "ready_for_review",
                    "severity": "high",
                    "confidence": 0.9,
                    "trust_score": 90,
                    "risk_level": "high",
                    "effort": "low",
                    "description": "Stop VM",
                    "estimated_monthly_savings": 100,
                    "cost_source": "actual",
                    "pricing_basis": "live_api",
                    "evidence_status": "ready",
                    "provider_agreement_status": "unknown",
                    "ai_enrichment_status": "pending",
                    "pipeline_version": "1.0.0",
                    "detected_at": "2026-09-01T12:00:00+00:00",
                },
            ]
        }

    async def select(self, collection: str, filters: dict = None, **kwargs):
        rows = self.collections.get(collection, [])
        if not filters:
            return list(rows)

        results = []
        for row in rows:
            match = True
            for k, v in filters.items():
                if row.get(k) != v:
                    match = False
                    break
            if match:
                results.append(row)
        return results


def get_test_app():
    app = FastAPI()
    app.include_router(recommendations_router)
    db = FakeDB()

    app.dependency_overrides[get_current_user] = lambda: ClerkUser(
        id="user-1",
        email="test@cloudfinops.com",
        first_name="Test",
        last_name="User",
    )
    app.dependency_overrides[get_db_client] = lambda: db
    return app


class TestEvidenceCardAPI(unittest.TestCase):

    def setUp(self):
        self.app = get_test_app()
        self.client = TestClient(self.app)

    def test_get_evidence_card_success(self):
        response = self.client.get(f"/api/recommendations/{TEST_REC_ID}/evidence-card")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["recommendation_id"], TEST_REC_ID)
        self.assertEqual(data["resource_summary"]["resource_name"], "prod-api-worker-01")
        self.assertEqual(data["resource_summary"]["provider"], "aws")
        self.assertEqual(data["resource_summary"]["recommended_action"], "rightsize")

        # 6 core goals verified
        self.assertIn("corroborating_signals", data)
        self.assertIn("safety_clearance", data)
        self.assertEqual(len(data["safety_clearance"]), 5)
        self.assertIn("risk_level", data)
        self.assertIn("why_flagged_explanation", data)
        self.assertIn("missing_data_warnings", data)

    def test_get_evidence_card_unauthorized_scope(self):
        # Requesting recommendation belonging to user-other should return 404
        response = self.client.get(f"/api/recommendations/{OTHER_REC_ID}/evidence-card")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
