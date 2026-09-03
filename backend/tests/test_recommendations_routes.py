from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.recommendations_routes import recommendations_router
from app.auth import ClerkUser, get_current_user
from app.core.recommendation_ai_enrichment import (
    AI_ENRICHMENT_DAILY_JOB_LIMIT,
    RECOMMENDATION_AI_ENRICHMENTS_COLLECTION,
    RECOMMENDATION_AI_JOBS_COLLECTION,
)
from app.core.recommendations import (
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
    RECOMMENDATION_STATE_EVENTS_COLLECTION,
)
from app.core.savings_verification import RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION
from app.db import get_db_client

RECOMMENDATION_ID = "rec_0123456789abcdef01234567"
OTHER_RECOMMENDATION_ID = "rec_fedcba9876543210fedcba98"
MISSING_RECOMMENDATION_ID = "rec_aaaaaaaaaaaaaaaaaaaaaaaa"


class FakeRecommendationsRouteDB:
    def __init__(self):
        self.select_calls = []
        self.update_calls = []
        self.insert_calls = []
        self.integrations = [
            {
                "id": "int-1",
                "user_id": "user-1",
                "provider": "azure",
                "name": "Azure Prod",
            }
        ]
        self.collections = {
            RECOMMENDATION_LEDGER_COLLECTION: [
                {
                    "id": RECOMMENDATION_ID,
                    "user_id": "user-1",
                    "integration_id": "int-1",
                    "provider": "azure",
                    "resource_id": "vm-1",
                    "cloud_resource_id": "vm-1",
                    "resource_name": "dev-vm-1",
                    "resource_type": "Azure VM",
                    "region": "centralindia",
                    "recommendation_type": "confirmed_waste",
                    "action": "terminate",
                    "state": "ready_for_review",
                    "severity": "high",
                    "confidence": 0.86,
                    "trust_score": 96,
                    "quality_status": "ready",
                    "quality_reasons": [],
                    "risk_level": "medium",
                    "effort": "low",
                    "description": "Terminate stopped VM",
                    "waste_reason": "Stopped for 45 days",
                    "estimated_monthly_savings": 120,
                    "claimable_monthly_savings": 120,
                    "savings_estimate_status": "supported_actual",
                    "savings_calculation_method": "current_billed_cost_elimination",
                    "savings_estimate_reason": "Savings are based on eliminating the full supported monthly resource cost.",
                    "estimated_monthly_waste": 120,
                    "cost_source": "actual",
                    "pricing_basis": "live_api",
                    "pricing_computed_at": "2026-08-17T00:00:00+00:00",
                    "evidence_status": "ready",
                    "provider_agreement_status": "unknown",
                    "ai_enrichment_status": "pending",
                    "source_systems": ["cloudfinops_deterministic_optimizer"],
                    "pipeline_version": "1.0.0",
                    "detected_at": "2026-08-17T01:00:00+00:00",
                },
                {
                    "id": OTHER_RECOMMENDATION_ID,
                    "user_id": "user-2",
                    "integration_id": "int-9",
                    "provider": "aws",
                    "resource_id": "i-other",
                    "cloud_resource_id": "i-other",
                    "resource_name": "other",
                    "resource_type": "EC2",
                    "recommendation_type": "confirmed_waste",
                    "action": "terminate",
                    "state": "ready_for_review",
                    "severity": "critical",
                    "confidence": 0.99,
                    "trust_score": 99,
                    "risk_level": "low",
                    "effort": "low",
                    "description": "Not yours",
                    "estimated_monthly_savings": 999,
                    "cost_source": "actual",
                    "pricing_basis": "live_api",
                    "evidence_status": "ready",
                    "provider_agreement_status": "unknown",
                    "ai_enrichment_status": "not_required",
                    "pipeline_version": "1.0.0",
                    "detected_at": "2026-08-17T01:00:00+00:00",
                },
            ],
            RECOMMENDATION_EVIDENCE_COLLECTION: [
                {
                    "id": "ev-1",
                    "user_id": "user-1",
                    "recommendation_id": RECOMMENDATION_ID,
                    "resource_id": "vm-1",
                    "evidence_kind": "corroborating_signal",
                    "signal_name": "cpu_avg",
                    "observed_value": 0.5,
                    "threshold": 2.0,
                    "description": "Average CPU below threshold",
                    "metric_window_start": "2026-08-10T00:00:00+00:00",
                    "metric_window_end": "2026-08-17T00:00:00+00:00",
                    "data_completeness": 1.0,
                    "source_system": "cloudfinops_deterministic_optimizer",
                    "collected_at": "2026-08-17T01:00:00+00:00",
                }
            ],
            RECOMMENDATION_STATE_EVENTS_COLLECTION: [],
            RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION: [],
            RECOMMENDATION_AI_JOBS_COLLECTION: [],
            RECOMMENDATION_AI_ENRICHMENTS_COLLECTION: [],
        }

    async def select(self, table, filters=None):
        filters = filters or {}
        self.select_calls.append((table, filters))
        return [
            row
            for row in self.collections.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

    async def update(self, table, data, filters):
        self.update_calls.append((table, data, filters))
        rows = await self.select(table, filters)
        for row in rows:
            row.update(data)
        return rows

    async def insert(self, table, data):
        self.insert_calls.append((table, data))
        rows = data if isinstance(data, list) else [data]
        payload = [dict(row) for row in rows]
        self.collections.setdefault(table, []).extend(payload)
        return payload

    async def upsert(self, table, data):
        rows = data if isinstance(data, list) else [data]
        collection = self.collections.setdefault(table, [])
        results = []
        for row in rows:
            existing = next((item for item in collection if item.get("id") == row.get("id")), None)
            if existing:
                existing.update(row)
                results.append(existing)
            else:
                payload = dict(row)
                collection.append(payload)
                results.append(payload)
        return results

    async def get_user_integrations(self, user_id):
        return [
            integration
            for integration in self.integrations
            if integration.get("user_id") == user_id
        ]


class OwnershipFilterBypassRecommendationsRouteDB(FakeRecommendationsRouteDB):
    async def select(self, table, filters=None):
        filters = filters or {}
        self.select_calls.append((table, filters))
        if table == RECOMMENDATION_LEDGER_COLLECTION:
            return [self.collections[RECOMMENDATION_LEDGER_COLLECTION][1]]
        return [
            row
            for row in self.collections.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]


class VanishingOnUpdateRecommendationsRouteDB(FakeRecommendationsRouteDB):
    async def update(self, table, data, filters):
        self.update_calls.append((table, data, filters))
        return []


class ListFilterBypassRecommendationsRouteDB(FakeRecommendationsRouteDB):
    async def select(self, table, filters=None):
        filters = filters or {}
        self.select_calls.append((table, filters))
        if table == RECOMMENDATION_LEDGER_COLLECTION:
            return list(self.collections[RECOMMENDATION_LEDGER_COLLECTION])
        return await super().select(table, filters)


class RelatedFilterBypassRecommendationsRouteDB(FakeRecommendationsRouteDB):
    async def select(self, table, filters=None):
        filters = filters or {}
        self.select_calls.append((table, filters))
        if table == RECOMMENDATION_EVIDENCE_COLLECTION:
            return list(self.collections[RECOMMENDATION_EVIDENCE_COLLECTION])
        return await super().select(table, filters)


def _build_client(fake_db: FakeRecommendationsRouteDB) -> TestClient:
    app = FastAPI()
    app.include_router(recommendations_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_recommendation_id_rejects_mongo_operator_payload_before_query():
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    response = client.get(
        "/api/recommendations/%7B%22%24ne%22%3Anull%7D/evidence"
    )

    assert response.status_code == 422
    assert fake_db.select_calls == []


def test_recommendation_id_rejects_malformed_and_oversized_values_before_query():
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    malformed_ids = [
        "rec_0123456789ABCDEF01234567",
        "rec_0123456789abcdef012345678",
        "rec-0123456789abcdef01234567",
    ]
    responses = [
        client.get(f"/api/recommendations/{recommendation_id}/evidence")
        for recommendation_id in malformed_ids
    ]

    assert all(response.status_code == 422 for response in responses)
    assert fake_db.select_calls == []


def test_list_recommendations_returns_user_scoped_ledger_rows():
    client = _build_client(FakeRecommendationsRouteDB())

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["recommendations"][0]["id"] == RECOMMENDATION_ID
    assert payload["recommendations"][0]["resource_name"] == "dev-vm-1"
    assert payload["recommendations"][0]["pricing_basis"] == "live_api"
    assert payload["recommendations"][0]["quality_status"] == "ready"
    assert payload["recommendations"][0]["claimable_monthly_savings"] == 120
    assert payload["recommendations"][0]["savings_estimate_status"] == "supported_actual"


def test_list_recommendations_discards_rows_from_a_filter_bypass():
    client = _build_client(ListFilterBypassRecommendationsRouteDB())

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [row["id"] for row in payload["recommendations"]] == [RECOMMENDATION_ID]


def test_get_recommendation_evidence_returns_queryable_chain():
    client = _build_client(FakeRecommendationsRouteDB())

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["evidence"][0]["signal_name"] == "cpu_avg"
    assert payload["evidence"][0]["observed_value"] == 0.5


def test_get_recommendation_evidence_discards_foreign_related_rows():
    fake_db = RelatedFilterBypassRecommendationsRouteDB()
    fake_db.collections[RECOMMENDATION_EVIDENCE_COLLECTION].append({
        **fake_db.collections[RECOMMENDATION_EVIDENCE_COLLECTION][0],
        "id": "ev-foreign",
        "user_id": "user-2",
    })
    client = _build_client(fake_db)

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [row["id"] for row in payload["evidence"]] == ["ev-1"]


def test_update_recommendation_state_persists_event():
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    response = client.post(
        f"/api/recommendations/{RECOMMENDATION_ID}/state",
        json={"state": "approved", "reason": "Validated with infra owner"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation"]["state"] == "approved"
    assert payload["event"]["from_state"] == "ready_for_review"
    assert payload["event"]["to_state"] == "approved"
    assert fake_db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION][0]["reason"] == "Validated with infra owner"


def test_update_recommendation_state_rejects_filter_bypass_ownership_mismatch():
    fake_db = OwnershipFilterBypassRecommendationsRouteDB()
    client = _build_client(fake_db)

    response = client.post(
        f"/api/recommendations/{OTHER_RECOMMENDATION_ID}/state",
        json={"state": "approved", "reason": "Must not be applied"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Recommendation not found"}
    assert fake_db.update_calls == []
    assert fake_db.insert_calls == []
    assert fake_db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION] == []


def test_update_recommendation_state_skips_event_when_row_vanishes_during_update():
    fake_db = VanishingOnUpdateRecommendationsRouteDB()
    client = _build_client(fake_db)

    response = client.post(
        f"/api/recommendations/{RECOMMENDATION_ID}/state",
        json={"state": "approved", "reason": "Concurrent update"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Recommendation not found"}
    assert len(fake_db.update_calls) == 1
    assert fake_db.update_calls[0][2] == {
        "user_id": "user-1",
        "id": RECOMMENDATION_ID,
    }
    assert fake_db.insert_calls == []
    assert fake_db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION] == []


def test_update_recommendation_state_to_implemented_starts_savings_verification():
    fake_db = FakeRecommendationsRouteDB()
    fake_db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["state"] = "approved"
    client = _build_client(fake_db)

    response = client.post(
        f"/api/recommendations/{RECOMMENDATION_ID}/state",
        json={"state": "implemented", "reason": "Infra team completed action"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation"]["state"] == "implemented"
    assert payload["recommendation"]["verification_status"] == "collecting_post_window"
    assert payload["recommendation"]["verification_id"]
    assert len(fake_db.collections[RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION]) == 1


def test_get_recommendation_verification_returns_user_scoped_record():
    fake_db = FakeRecommendationsRouteDB()
    fake_db.collections[RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION].append({
        "id": "ver-1",
        "user_id": "user-1",
        "recommendation_id": RECOMMENDATION_ID,
        "integration_id": "int-1",
        "provider": "azure",
        "resource_id": "vm-1",
        "cloud_resource_id": "vm-1",
        "action": "terminate",
        "status": "verified_saved",
        "estimated_monthly_savings": 120,
        "baseline_monthly_cost": 120,
        "post_monthly_cost": 20,
        "realized_monthly_savings": 100,
        "realized_savings_confidence": 92,
        "measurement_source": "resource_snapshot",
        "explanation": "Measured monthly cost moved from 120.00 to 20.00.",
    })
    client = _build_client(fake_db)

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/verification")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified_saved"
    assert payload["realized_monthly_savings"] == 100


def test_get_recommendation_verification_rejects_foreign_related_record(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    async def fake_get_verification(*, db, user_id, recommendation_id):
        assert db is fake_db
        return {
            "id": "ver-foreign",
            "user_id": "user-2",
            "recommendation_id": recommendation_id,
        }

    monkeypatch.setattr(
        "app.api.recommendations_routes.get_savings_verification",
        fake_get_verification,
    )

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/verification")

    assert response.status_code == 404
    assert response.json() == {"detail": "Savings verification not started"}


def test_get_missing_recommendation_verification_returns_404_empty_edge_case():
    client = _build_client(FakeRecommendationsRouteDB())

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/verification")

    assert response.status_code == 404


def test_run_recommendation_verification_returns_measurement(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    async def fake_verify(*, db, user_id, recommendation_id):
        assert db is fake_db
        assert user_id == "user-1"
        assert recommendation_id == RECOMMENDATION_ID
        return {
            "id": "ver-1",
            "user_id": "user-1",
            "recommendation_id": RECOMMENDATION_ID,
            "integration_id": "int-1",
            "provider": "azure",
            "resource_id": "vm-1",
            "cloud_resource_id": "vm-1",
            "action": "terminate",
            "status": "verified_saved",
            "estimated_monthly_savings": 120,
            "baseline_monthly_cost": 120,
            "post_monthly_cost": 20,
            "realized_monthly_savings": 100,
            "realized_savings_confidence": 92,
            "measurement_source": "resource_snapshot",
            "explanation": "Measured monthly cost moved from 120.00 to 20.00.",
        }

    monkeypatch.setattr(
        "app.api.recommendations_routes.verify_recommendation_savings",
        fake_verify,
    )

    response = client.post(f"/api/recommendations/{RECOMMENDATION_ID}/verification/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified_saved"
    assert payload["measurement_source"] == "resource_snapshot"


def test_get_recommendation_ai_enrichment_returns_user_scoped_record():
    fake_db = FakeRecommendationsRouteDB()
    fake_db.collections[RECOMMENDATION_AI_ENRICHMENTS_COLLECTION].append({
        "id": "enrich-1",
        "user_id": "user-1",
        "recommendation_id": RECOMMENDATION_ID,
        "job_id": "job-1",
        "status": "succeeded",
        "summary": "Terminate the stopped dev VM after owner validation.",
        "business_impact": "The action can remove recurring waste.",
        "evidence_narrative": "CPU remained below threshold.",
        "remediation_steps": ["Confirm owner", "Schedule removal"],
        "risk_notes": "Medium risk until ownership is confirmed.",
        "rollback_plan": "Restore from backup if needed.",
        "validation_plan": "Compare post-change cost snapshots.",
        "assumptions": ["Not a DR VM"],
        "confidence_notes": "More network metrics would improve confidence.",
        "evidence_ids_used": ["ev-1"],
        "model": "gemini-test",
        "prompt_version": "recommendation_ai_enrichment_v1",
        "generated_at": "2026-08-17T02:00:00+00:00",
    })
    client = _build_client(fake_db)

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/ai-enrichment")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "Terminate the stopped dev VM after owner validation."
    assert payload["evidence_ids_used"] == ["ev-1"]


def test_get_recommendation_ai_enrichment_rejects_foreign_related_record(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    async def fake_get_enrichment(*, db, user_id, recommendation_id):
        assert db is fake_db
        return {
            "id": "enrich-foreign",
            "user_id": "user-2",
            "recommendation_id": recommendation_id,
        }

    monkeypatch.setattr(
        "app.api.recommendations_routes.get_recommendation_ai_enrichment",
        fake_get_enrichment,
    )

    response = client.get(f"/api/recommendations/{RECOMMENDATION_ID}/ai-enrichment")

    assert response.status_code == 404
    assert response.json() == {"detail": "AI enrichment not available"}


def test_queue_recommendation_ai_enrichment_user_scoped(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)
    monkeypatch.setattr(
        "app.api.recommendations_routes.get_settings",
        lambda: SimpleNamespace(gemini_agent_model="gemini-test", gemini_api_key=None),
    )

    response = client.post(
        f"/api/recommendations/{RECOMMENDATION_ID}/ai-enrichment/queue",
        json={"force": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] == 1
    assert len(fake_db.collections[RECOMMENDATION_AI_JOBS_COLLECTION]) == 1
    assert fake_db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["ai_enrichment_status"] == "queued"


def test_run_ai_enrichment_batch_skips_without_gemini_key(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)
    monkeypatch.setattr(
        "app.api.recommendations_routes.get_settings",
        lambda: SimpleNamespace(gemini_agent_model="gemini-test", gemini_api_key=None),
    )

    response = client.post(
        "/api/recommendations/ai-enrichment/run",
        json={"limit": 1, "queue_pending": True, "queue_limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "skipped"
    assert payload["queued_before_run"] == 1
    assert payload["processed"] == 0


def test_run_ai_enrichment_batch_rate_limits_daily_job_volume(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    for index in range(AI_ENRICHMENT_DAILY_JOB_LIMIT):
        fake_db.collections[RECOMMENDATION_AI_JOBS_COLLECTION].append({
            "id": f"recent-job-{index}",
            "user_id": "user-1",
            "recommendation_id": f"rec_{index:024x}",
            "status": "succeeded",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
    client = _build_client(fake_db)
    monkeypatch.setattr(
        "app.api.recommendations_routes.get_settings",
        lambda: SimpleNamespace(gemini_agent_model="gemini-test", gemini_api_key="test-key"),
    )

    response = client.post(
        "/api/recommendations/ai-enrichment/run",
        json={"limit": 1, "queue_pending": False},
    )

    assert response.status_code == 429
    assert "Daily AI enrichment job limit reached" in response.json()["detail"]


def test_run_ai_enrichment_batch_can_start_background_drain(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)
    calls = []

    monkeypatch.setattr(
        "app.api.recommendations_routes.get_settings",
        lambda: SimpleNamespace(gemini_agent_model="gemini-test", gemini_api_key="test-key"),
    )

    async def fake_drain(*, user_id, max_jobs, batch_size):
        calls.append({"user_id": user_id, "max_jobs": max_jobs, "batch_size": batch_size})
        return {"status": "completed", "processed": 0, "succeeded": 0, "failed": 0}

    monkeypatch.setattr(
        "app.api.recommendations_routes.drain_user_recommendation_ai_enrichment",
        fake_drain,
    )

    response = client.post(
        "/api/recommendations/ai-enrichment/run",
        json={"limit": 3, "queue_pending": True, "queue_limit": 50, "background": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["background_started"] is True
    assert payload["queued_before_run"] == 1
    assert calls == [{"user_id": "user-1", "max_jobs": 50, "batch_size": 3}]


def test_get_missing_recommendation_returns_404_empty_edge_case():
    client = _build_client(FakeRecommendationsRouteDB())

    response = client.get(
        f"/api/recommendations/{MISSING_RECOMMENDATION_ID}/evidence"
    )

    assert response.status_code == 404


def test_provider_ingest_runs_user_scoped_azure_integration(monkeypatch):
    fake_db = FakeRecommendationsRouteDB()
    client = _build_client(fake_db)

    monkeypatch.setattr(
        "app.api.recommendations_routes.decrypt_integration_credentials",
        lambda integration: {
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
            "subscription_id": "sub",
        },
    )

    async def fake_ingest(*, db, user_id, integration, credentials, force_refresh):
        assert db is fake_db
        assert user_id == "user-1"
        assert integration["id"] == "int-1"
        assert credentials["subscription_id"] == "sub"
        assert force_refresh is True
        return {
            "integration_id": "int-1",
            "provider": "azure",
            "status": "ok",
            "fetched": 2,
            "stored": 2,
            "matched": 1,
            "provider_only_created": 1,
            "not_found_marked": 0,
            "message": None,
            "refresh_status": "completed",
            "refreshed": True,
            "refresh_message": "Azure Advisor recommendations were refreshed",
        }

    monkeypatch.setattr(
        "app.api.recommendations_routes.ingest_azure_advisor_recommendations",
        fake_ingest,
    )

    response = client.post("/api/recommendations/provider-ingest", json={"integration_id": "int-1", "force_refresh": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summaries"][0]["status"] == "ok"
    assert payload["summaries"][0]["refresh_status"] == "completed"
    assert payload["totals"]["matched"] == 1
    assert payload["totals"]["provider_only_created"] == 1
    assert payload["totals"]["refreshed"] == 1


def test_provider_ingest_returns_404_for_missing_integration():
    client = _build_client(FakeRecommendationsRouteDB())

    response = client.post("/api/recommendations/provider-ingest", json={"integration_id": "missing"})

    assert response.status_code == 404
