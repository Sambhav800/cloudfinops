import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

os.environ.setdefault("CLERK_SECRET_KEY", "test_clerk_secret_key_12345")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test_db")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")

import tests.conftest  # noqa: F401
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router, _safe_inventory_error, _build_inventory_health, _build_billing_health
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeHealthDB:
    def __init__(self, batch_data=None):
        # batch_data is keyed by user_id -> list of raw health rows
        self._data_by_user = batch_data or {}

    async def get_user_integrations_health_batch(self, user_id: str):
        return self._data_by_user.get(user_id, [])


class TestIntegrationHealthRoutes(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.user_a = ClerkUser(id="user_test_a", email="usera@example.com", first_name="User", last_name="A")
        self.user_b = ClerkUser(id="user_test_b", email="userb@example.com", first_name="User", last_name="B")

    def test_successful_scan_health_telemetry(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        db = FakeHealthDB({
            "user_test_a": [
                {
                    "integration": {
                        "id": "integ_aws_1",
                        "provider": "aws",
                        "name": "Production AWS",
                        "metadata": {
                            "billing_status": "ok",
                            "billing_last_success_at": now_iso,
                            "billing_last_attempt_at": now_iso,
                            "billing_observed_at": now_iso,
                            "last_month_cost": 12500.0,
                            "using_cached_costs": False,
                        },
                    },
                    "last_scan": {
                        "status": "completed",
                        "started_at": now_iso,
                        "completed_at": now_iso,
                        "total_resources": 142,
                        "error_message": None,
                    },
                    "last_success_scan": {
                        "status": "completed",
                        "started_at": now_iso,
                        "completed_at": now_iso,
                        "total_resources": 142,
                    },
                    "ai_counts": {
                        "queued": 2,
                        "running": 1,
                        "enriched": 38,
                        "failed": 0,
                        "last_success_at": now_iso,
                    },
                }
            ]
        })

        self.app.dependency_overrides[get_current_user] = lambda: self.user_a
        self.app.dependency_overrides[get_db_client] = lambda: db

        client = TestClient(self.app)
        response = client.get("/api/integration-health")
        assert response.status_code == 200, response.text
        data = response.json()

        assert len(data["integrations"]) == 1
        item = data["integrations"][0]
        assert item["integration_id"] == "integ_aws_1"
        assert item["provider"] == "aws"
        assert item["name"] == "Production AWS"

        # Inventory health
        assert item["inventory"]["status"] == "ok"
        assert item["inventory"]["resource_count"] == 142
        assert item["inventory"]["reason_code"] is None
        assert item["inventory"]["display_message"] is None

        # Billing health
        assert item["billing"]["status"] == "ok"
        assert item["billing"]["using_cached_costs"] is False
        assert item["billing"]["retry_at"] is None

        # AI Enrichment health
        assert item["ai_enrichment"]["enriched"] == 38
        assert item["ai_enrichment"]["queued"] == 2
        assert item["ai_enrichment"]["running"] == 1
        assert item["ai_enrichment"]["failed"] == 0

    def test_azure_429_rate_limit_and_cooldown(self):
        now = datetime.now(timezone.utc)
        retry_time = (now + timedelta(minutes=15)).isoformat()
        last_success = (now - timedelta(hours=2)).isoformat()

        db = FakeHealthDB({
            "user_test_a": [
                {
                    "integration": {
                        "id": "integ_azure_1",
                        "provider": "azure",
                        "name": "Azure Primary",
                        "metadata": {
                            "billing_status": "rate_limited",
                            "billing_retry_at": retry_time,
                            "billing_last_success_at": last_success,
                            "billing_last_attempt_at": now.isoformat(),
                            "billing_observed_at": last_success,
                            "last_month_cost": 45000.0,
                            "using_cached_costs": True,
                        },
                    },
                    "last_scan": {
                        "status": "completed",
                        "started_at": now.isoformat(),
                        "completed_at": now.isoformat(),
                        "total_resources": 85,
                        "error_message": None,
                    },
                    "last_success_scan": {
                        "status": "completed",
                        "completed_at": now.isoformat(),
                        "total_resources": 85,
                    },
                    "ai_counts": {"queued": 0, "running": 0, "enriched": 12, "failed": 0, "last_success_at": None},
                }
            ]
        })

        self.app.dependency_overrides[get_current_user] = lambda: self.user_a
        self.app.dependency_overrides[get_db_client] = lambda: db

        client = TestClient(self.app)
        response = client.get("/api/integration-health")
        assert response.status_code == 200
        item = response.json()["integrations"][0]

        # Billing preserves last valid cost (using_cached_costs=True) and sets cooldown
        assert item["billing"]["status"] == "failed"
        assert item["billing"]["reason_code"] == "rate_limited"
        assert item["billing"]["using_cached_costs"] is True
        assert item["billing"]["retry_at"] == retry_time
        assert "rate limit" in item["billing"]["display_message"].lower()

    def test_permission_denied_sanitizes_sdk_errors(self):
        # Raw error message contains internal SDK details that must NEVER be returned
        raw_sdk_error = (
            "azure.core.exceptions.HttpResponseError: Operation returned an invalid status 'Forbidden'. "
            "AuthorizationFailed: The client 'abcd-1234' does not have authorization to perform action "
            "'Microsoft.Resources/subscriptions/resources/read' over scope '/subscriptions/sub-123'."
        )

        db = FakeHealthDB({
            "user_test_a": [
                {
                    "integration": {
                        "id": "integ_azure_perm",
                        "provider": "azure",
                        "name": "Restricted Azure",
                        "metadata": {
                            "billing_status": "failed",
                            "billing_error": raw_sdk_error,
                        },
                    },
                    "last_scan": {
                        "status": "failed",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "completed_at": None,
                        "total_resources": 0,
                        "error_message": raw_sdk_error,
                    },
                    "last_success_scan": None,
                    "ai_counts": {"queued": 0, "running": 0, "enriched": 0, "failed": 0, "last_success_at": None},
                }
            ]
        })

        self.app.dependency_overrides[get_current_user] = lambda: self.user_a
        self.app.dependency_overrides[get_db_client] = lambda: db

        client = TestClient(self.app)
        response = client.get("/api/integration-health")
        assert response.status_code == 200
        item = response.json()["integrations"][0]

        # Scan inventory error must be sanitized allowlisted message
        inv = item["inventory"]
        assert inv["status"] == "failed"
        assert inv["reason_code"] == "permission_denied"
        assert "lacks required read permissions" in inv["display_message"]
        # CRITICAL: Verify NO raw internal details leaked
        assert "abcd-1234" not in inv["display_message"]
        assert "HttpResponseError" not in inv["display_message"]
        assert "sub-123" not in inv["display_message"]

    def test_account_switching_and_user_scoping(self):
        # User A owns integ_a, User B owns integ_b
        db = FakeHealthDB({
            "user_test_a": [
                {
                    "integration": {"id": "integ_a", "provider": "aws", "name": "User A AWS", "metadata": {}},
                    "last_scan": None,
                    "last_success_scan": None,
                    "ai_counts": {},
                }
            ],
            "user_test_b": [
                {
                    "integration": {"id": "integ_b", "provider": "azure", "name": "User B Azure", "metadata": {}},
                    "last_scan": None,
                    "last_success_scan": None,
                    "ai_counts": {},
                }
            ],
        })

        client = TestClient(self.app)

        # As User A
        self.app.dependency_overrides[get_current_user] = lambda: self.user_a
        self.app.dependency_overrides[get_db_client] = lambda: db
        res_a = client.get("/api/integration-health")
        assert res_a.status_code == 200
        ids_a = [i["integration_id"] for i in res_a.json()["integrations"]]
        assert ids_a == ["integ_a"]
        assert "integ_b" not in ids_a

        # Switch to User B
        self.app.dependency_overrides[get_current_user] = lambda: self.user_b
        res_b = client.get("/api/integration-health")
        assert res_b.status_code == 200
        ids_b = [i["integration_id"] for i in res_b.json()["integrations"]]
        assert ids_b == ["integ_b"]
        assert "integ_a" not in ids_b

    def test_billing_stale_threshold_six_hour_contract(self):
        # Contract: Billing stale threshold is 6 hours
        fresh_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()

        # Fresh integration (<6 hours)
        fresh_meta = {"billing_last_success_at": fresh_time}
        fresh_health = _build_billing_health({"metadata": fresh_meta})
        assert fresh_health["status"] == "ok"

        # Stale integration (>6 hours)
        stale_meta = {"billing_last_success_at": stale_time}
        stale_health = _build_billing_health({"metadata": stale_meta})
        assert stale_health["status"] == "stale"

    def test_running_scan_shows_last_known_success(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        last_scan = {"status": "running", "started_at": now_iso, "total_resources": 0}
        last_success = {"status": "completed", "completed_at": past_iso, "total_resources": 42}

        inv_health = _build_inventory_health(last_scan, last_success)
        assert inv_health["status"] == "ok"
        assert inv_health["last_attempt_at"] == now_iso
        assert inv_health["last_success_at"] == past_iso
        assert inv_health["resource_count"] == 42

    def test_never_scanned_clean_defaults(self):
        inv_health = _build_inventory_health(None, None)
        assert inv_health["status"] == "never"
        assert inv_health["last_success_at"] is None
        assert inv_health["resource_count"] == 0

        bill_health = _build_billing_health({"metadata": {}})
        assert bill_health["status"] == "never"
        assert bill_health["using_cached_costs"] is False
