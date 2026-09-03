import asyncio
import json

from app.core.recommendation_ai_enrichment import (
    RECOMMENDATION_AI_ENRICHMENTS_COLLECTION,
    RECOMMENDATION_AI_JOBS_COLLECTION,
    drain_recommendation_ai_enrichment_queue,
    enqueue_recommendation_ai_jobs,
    normalize_ai_enrichment_payload,
    run_recommendation_ai_enrichment_job,
)
from app.core.recommendations import (
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
)


class FakeAiEnrichmentDB:
    def __init__(self):
        self.collections = {
            RECOMMENDATION_LEDGER_COLLECTION: [
                {
                    "id": "rec-1",
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
                    "risk_level": "medium",
                    "effort": "low",
                    "description": "Terminate stopped VM",
                    "waste_reason": "Stopped for 45 days",
                    "estimated_monthly_savings": 120,
                    "estimated_monthly_waste": 120,
                    "cost_source": "actual",
                    "pricing_basis": "live_api",
                    "pricing_computed_at": "2026-08-17T00:00:00+00:00",
                    "evidence_status": "ready",
                    "provider_agreement_status": "unknown",
                    "ai_enrichment_status": "pending",
                }
            ],
            RECOMMENDATION_EVIDENCE_COLLECTION: [
                {
                    "id": "ev-1",
                    "user_id": "user-1",
                    "recommendation_id": "rec-1",
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
                }
            ],
            RECOMMENDATION_AI_JOBS_COLLECTION: [],
            RECOMMENDATION_AI_ENRICHMENTS_COLLECTION: [],
        }

    async def select(self, table, filters=None):
        filters = filters or {}
        return [
            row
            for row in self.collections.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

    async def update(self, table, data, filters):
        rows = await self.select(table, filters)
        for row in rows:
            row.update(data)
        return rows

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


def test_enqueue_recommendation_ai_jobs_marks_ledger_queued():
    db = FakeAiEnrichmentDB()

    summary = asyncio.run(
        enqueue_recommendation_ai_jobs(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            model="gemini-test",
        )
    )

    assert summary["queued"] == 1
    assert len(db.collections[RECOMMENDATION_AI_JOBS_COLLECTION]) == 1
    job = db.collections[RECOMMENDATION_AI_JOBS_COLLECTION][0]
    assert job["recommendation_id"] == "rec-1"
    assert job["status"] == "queued"
    assert job["input_hash"]
    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert ledger["ai_enrichment_status"] == "queued"
    assert ledger["ai_enrichment_job_id"] == job["id"]


def test_run_recommendation_ai_enrichment_job_persists_model_output(monkeypatch):
    db = FakeAiEnrichmentDB()
    summary = asyncio.run(
        enqueue_recommendation_ai_jobs(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            model="gemini-test",
        )
    )
    job_id = summary["job_ids"][0]

    async def fake_call_gemini_enrichment(*, enrichment_input, gemini_api_key, model):
        assert gemini_api_key == "test-key"
        assert model == "gemini-test"
        assert enrichment_input["recommendation_id"] == "rec-1"
        return json.dumps({
            "summary": "Terminate the stopped dev VM after owner validation.",
            "business_impact": (
                "The action can remove recurring waste while keeping implementation risk medium."
            ),
            "evidence_narrative": (
                "The deterministic engine found low CPU over the observed window and actual cost."
            ),
            "remediation_steps": [
                "Confirm the VM is not needed by the owner.",
                "Check attached disks and backups.",
                "Schedule the termination window.",
            ],
            "risk_notes": "Medium risk because workload ownership must be confirmed.",
            "rollback_plan": "Restore from backup or redeploy from the approved image if needed.",
            "validation_plan": "Compare post-change cost snapshots against the baseline window.",
            "assumptions": ["The VM is not part of disaster recovery."],
            "confidence_notes": "Longer network and disk metrics would increase confidence.",
            "evidence_ids_used": ["ev-1"],
        })

    monkeypatch.setattr(
        "app.core.recommendation_ai_enrichment._call_gemini_enrichment",
        fake_call_gemini_enrichment,
    )

    result = asyncio.run(
        run_recommendation_ai_enrichment_job(
            db=db,
            user_id="user-1",
            job_id=job_id,
            gemini_api_key="test-key",
            model="gemini-test",
        )
    )

    assert result["status"] == "succeeded"
    assert len(db.collections[RECOMMENDATION_AI_ENRICHMENTS_COLLECTION]) == 1
    enrichment = db.collections[RECOMMENDATION_AI_ENRICHMENTS_COLLECTION][0]
    assert enrichment["summary"] == "Terminate the stopped dev VM after owner validation."
    assert enrichment["remediation_steps"][0] == "Confirm the VM is not needed by the owner."
    assert enrichment["evidence_ids_used"] == ["ev-1"]
    assert enrichment["quality_status"] == "passed"
    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert ledger["ai_enrichment_status"] == "enriched"
    assert ledger["ai_enrichment_id"] == enrichment["id"]
    assert ledger["ai_summary"] == enrichment["summary"]


def test_drain_recommendation_ai_enrichment_queue_processes_bounded_jobs(monkeypatch):
    db = FakeAiEnrichmentDB()
    original = dict(db.collections[RECOMMENDATION_LEDGER_COLLECTION][0])
    for index in range(2, 5):
        row = dict(original)
        row["id"] = f"rec-{index}"
        row["resource_id"] = f"vm-{index}"
        row["cloud_resource_id"] = f"vm-{index}"
        row["ai_enrichment_status"] = "pending"
        db.collections[RECOMMENDATION_LEDGER_COLLECTION].append(row)

    asyncio.run(
        enqueue_recommendation_ai_jobs(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            model="gemini-test",
            queue_limit=4,
        )
    )

    async def fake_call_gemini_enrichment(*, enrichment_input, gemini_api_key, model):
        evidence_ids = [row["id"] for row in enrichment_input.get("evidence", [])]
        return json.dumps({
            "summary": "Validate this recommendation with the owner before action.",
            "business_impact": "The action can reduce recurring spend after validation.",
            "evidence_narrative": "The deterministic recommendation contains enough context for review.",
            "remediation_steps": [
                "Confirm ownership.",
                "Review dependencies.",
                "Schedule the approved change.",
            ],
            "risk_notes": "Risk depends on workload ownership.",
            "rollback_plan": "Restore the prior resource configuration if needed.",
            "validation_plan": "Compare the post-change bill to the baseline.",
            "assumptions": [],
            "confidence_notes": "More telemetry can improve confidence.",
            "evidence_ids_used": evidence_ids,
        })

    monkeypatch.setattr(
        "app.core.recommendation_ai_enrichment._call_gemini_enrichment",
        fake_call_gemini_enrichment,
    )

    result = asyncio.run(
        drain_recommendation_ai_enrichment_queue(
            db=db,
            user_id="user-1",
            model="gemini-test",
            gemini_api_key="test-key",
            max_jobs=2,
            batch_size=1,
        )
    )

    assert result["processed"] == 2
    assert result["succeeded"] == 2
    queued = [
        row
        for row in db.collections[RECOMMENDATION_AI_JOBS_COLLECTION]
        if row.get("status") == "queued"
    ]
    assert len(queued) == 2


def test_run_recommendation_ai_enrichment_job_rejects_unknown_evidence_id(monkeypatch):
    db = FakeAiEnrichmentDB()
    summary = asyncio.run(
        enqueue_recommendation_ai_jobs(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            model="gemini-test",
        )
    )
    job_id = summary["job_ids"][0]

    async def fake_call_gemini_enrichment(*, enrichment_input, gemini_api_key, model):
        return json.dumps({
            "summary": "Terminate the stopped dev VM after owner validation.",
            "business_impact": (
                "The action can remove recurring waste while keeping implementation risk medium."
            ),
            "evidence_narrative": "The deterministic engine found low CPU over the observed window.",
            "remediation_steps": [
                "Confirm the VM is not needed by the owner.",
                "Check attached disks and backups.",
                "Schedule the termination window.",
            ],
            "risk_notes": "Medium risk because workload ownership must be confirmed.",
            "rollback_plan": "Restore from backup or redeploy from the approved image if needed.",
            "validation_plan": "Compare post-change cost snapshots against the baseline window.",
            "assumptions": [],
            "confidence_notes": "Longer observation windows would increase confidence.",
            "evidence_ids_used": ["ev-missing"],
        })

    monkeypatch.setattr(
        "app.core.recommendation_ai_enrichment._call_gemini_enrichment",
        fake_call_gemini_enrichment,
    )

    result = asyncio.run(
        run_recommendation_ai_enrichment_job(
            db=db,
            user_id="user-1",
            job_id=job_id,
            gemini_api_key="test-key",
            model="gemini-test",
        )
    )

    assert result["status"] == "failed_quality_gate"
    assert "unknown evidence ids" in result["error"]
    assert db.collections[RECOMMENDATION_AI_ENRICHMENTS_COLLECTION] == []
    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert ledger["ai_enrichment_status"] == "failed_quality_gate"


def test_normalize_ai_enrichment_payload_rejects_unsupported_signal_claim():
    db = FakeAiEnrichmentDB()
    evidence_rows = db.collections[RECOMMENDATION_EVIDENCE_COLLECTION]
    response_text = json.dumps({
        "summary": "Terminate the VM because memory is consistently idle.",
        "business_impact": "The action can remove recurring waste.",
        "evidence_narrative": "Memory remained below the configured threshold during the observation window.",
        "remediation_steps": [
            "Confirm the VM is not needed by the owner.",
            "Check attached disks and backups.",
            "Schedule the termination window.",
        ],
        "risk_notes": "Medium risk because workload ownership must be confirmed.",
        "rollback_plan": "Restore from backup or redeploy from the approved image if needed.",
        "validation_plan": "Compare post-change cost snapshots against the baseline window.",
        "assumptions": [],
        "confidence_notes": "Longer observation windows would increase confidence.",
        "evidence_ids_used": ["ev-1"],
    })

    try:
        normalize_ai_enrichment_payload(response_text, evidence_rows=evidence_rows)
    except ValueError as error:
        assert "mentions memory without supporting evidence" in str(error)
    else:
        raise AssertionError("Expected unsupported memory claim to fail the quality gate")


def test_enqueue_recommendation_ai_jobs_respects_queue_limit():
    db = FakeAiEnrichmentDB()
    original = dict(db.collections[RECOMMENDATION_LEDGER_COLLECTION][0])
    for index in range(2, 5):
        row = dict(original)
        row["id"] = f"rec-{index}"
        row["resource_id"] = f"vm-{index}"
        row["cloud_resource_id"] = f"vm-{index}"
        row["ai_enrichment_status"] = "pending"
        row["estimated_monthly_savings"] = 10 * index
        db.collections[RECOMMENDATION_LEDGER_COLLECTION].append(row)

    summary = asyncio.run(
        enqueue_recommendation_ai_jobs(
            db=db,
            user_id="user-1",
            integration_id="int-1",
            model="gemini-test",
            queue_limit=2,
        )
    )

    assert summary["queued"] == 2
    assert summary["skipped"] == 2
    assert len(db.collections[RECOMMENDATION_AI_JOBS_COLLECTION]) == 2
