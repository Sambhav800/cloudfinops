import asyncio
from datetime import datetime, timedelta, timezone

from app.core.recommendations import (
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
    RECOMMENDATION_STATE_EVENTS_COLLECTION,
    persist_recommendation_ledger,
)
from app.optimization.evidence_collector import SignalTimeSeries, build_evidence_bundle
from app.optimization.severity import (
    CorroboratingSignal,
    Recommendation,
    RecommendedAction,
    ResourceClassification,
    ResourceVerdict,
    Severity,
)


class FakeRecommendationLedgerDB:
    def __init__(self):
        self.collections = {
            RECOMMENDATION_LEDGER_COLLECTION: [],
            RECOMMENDATION_EVIDENCE_COLLECTION: [],
            RECOMMENDATION_STATE_EVENTS_COLLECTION: [],
        }

    async def select(self, table, filters=None):
        filters = filters or {}
        return [
            row
            for row in self.collections.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

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
                collection.append(dict(row))
                results.append(dict(row))
        return results

    async def delete(self, table, filters):
        collection = self.collections.setdefault(table, [])
        self.collections[table] = [
            row
            for row in collection
            if not all(row.get(key) == value for key, value in filters.items())
        ]
        return True

    async def insert(self, table, data):
        rows = data if isinstance(data, list) else [data]
        payload = [dict(row) for row in rows]
        self.collections.setdefault(table, []).extend(payload)
        return payload


def _evidence_bundle():
    now = datetime.now(timezone.utc)
    timestamps = [now - timedelta(days=7 - index) for index in range(8)]
    signal = SignalTimeSeries(
        metric_name="cpu_avg",
        values=[0.5] * 8,
        timestamps=timestamps,
        interval=timedelta(days=1),
    )
    return build_evidence_bundle(
        resource_id="vm-1",
        provider="azure",
        resource_type="Azure VM",
        provider_state="stopped",
        signals={"cpu_avg": signal},
        tags={"env": "dev"},
        resource_age_days=45,
        monthly_cost=120,
        cost_source="actual",
        resource_name="dev-vm-1",
        region="centralindia",
        cloud_resource_id="vm-1",
    )


def _actionable_verdict():
    return ResourceVerdict(
        resource_id="vm-1",
        classification=ResourceClassification.CONFIRMED_WASTE,
        confidence=0.86,
        severity=Severity.HIGH,
        corroborating_signals=[
            CorroboratingSignal(
                signal_name="cpu_avg",
                observed_value=0.5,
                threshold=2.0,
                description="Average CPU 0.5% < 2.0% threshold",
            )
        ],
        recommendation=Recommendation(
            action=RecommendedAction.TERMINATE,
            description="Terminate stopped VM and release attached disks",
            estimated_monthly_savings=120,
            effort="low",
            risk="medium",
        ),
        estimated_monthly_waste=120,
        waste_reason="Resource stopped for 45 days",
    )


def test_persist_recommendation_ledger_writes_record_evidence_and_event():
    db = FakeRecommendationLedgerDB()

    written = asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[_actionable_verdict()],
            evidence_bundles=[_evidence_bundle()],
            findings=[
                {
                    "cloud_resource_id": "vm-1",
                    "resource_name": "dev-vm-1",
                    "service_type": "Azure VM",
                    "region": "centralindia",
                    "metadata": {
                        "cost_source": "actual",
                        "pricing_basis": "live_api",
                        "pricing_computed_at": "2026-08-17T00:00:00+00:00",
                    },
                }
            ],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )

    assert written == 1
    ledger = db.collections[RECOMMENDATION_LEDGER_COLLECTION]
    assert len(ledger) == 1
    assert ledger[0]["state"] == "ready_for_review"
    assert ledger[0]["resource_name"] == "dev-vm-1"
    assert ledger[0]["pricing_basis"] == "live_api"
    assert ledger[0]["estimated_monthly_savings"] == 120
    assert ledger[0]["claimable_monthly_savings"] == 120
    assert ledger[0]["savings_estimate_status"] == "supported_actual"
    assert ledger[0]["quality_status"] == "ready"
    assert ledger[0]["ai_enrichment_status"] == "pending"
    assert ledger[0]["trust_score"] >= 80

    evidence = db.collections[RECOMMENDATION_EVIDENCE_COLLECTION]
    assert len(evidence) == 2
    assert {row["evidence_kind"] for row in evidence} == {"cost_provenance", "corroborating_signal"}
    signal_evidence = next(row for row in evidence if row["evidence_kind"] == "corroborating_signal")
    assert signal_evidence["signal_name"] == "cpu_avg"
    assert signal_evidence["metric_window_start"]
    assert signal_evidence["metric_window_end"]

    events = db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION]
    assert len(events) == 1
    assert events[0]["to_state"] == "ready_for_review"


def test_persist_recommendation_ledger_preserves_existing_human_state():
    db = FakeRecommendationLedgerDB()

    asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[_actionable_verdict()],
            evidence_bundles=[_evidence_bundle()],
            findings=[{"cloud_resource_id": "vm-1", "metadata": {"pricing_basis": "live_api"}}],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )
    db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["state"] = "approved"
    first_event_count = len(db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION])

    written = asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[_actionable_verdict()],
            evidence_bundles=[_evidence_bundle()],
            findings=[{"cloud_resource_id": "vm-1", "metadata": {"pricing_basis": "live_api"}}],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )

    assert written == 1
    assert len(db.collections[RECOMMENDATION_LEDGER_COLLECTION]) == 1
    assert db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]["state"] == "approved"
    assert len(db.collections[RECOMMENDATION_STATE_EVENTS_COLLECTION]) == first_event_count


def test_persist_recommendation_ledger_preserves_existing_ai_enrichment():
    db = FakeRecommendationLedgerDB()

    asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[_actionable_verdict()],
            evidence_bundles=[_evidence_bundle()],
            findings=[{"cloud_resource_id": "vm-1", "metadata": {"pricing_basis": "live_api"}}],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )
    ledger_row = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    ledger_row["ai_enrichment_status"] = "enriched"
    ledger_row["ai_enrichment_id"] = "enrich-1"
    ledger_row["ai_summary"] = "Human-readable enrichment"

    asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[_actionable_verdict()],
            evidence_bundles=[_evidence_bundle()],
            findings=[{"cloud_resource_id": "vm-1", "metadata": {"pricing_basis": "live_api"}}],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )

    refreshed = db.collections[RECOMMENDATION_LEDGER_COLLECTION][0]
    assert refreshed["ai_enrichment_status"] == "enriched"
    assert refreshed["ai_enrichment_id"] == "enrich-1"
    assert refreshed["ai_summary"] == "Human-readable enrichment"


def test_persist_recommendation_ledger_skips_non_actionable_verdicts():
    db = FakeRecommendationLedgerDB()
    verdict = ResourceVerdict(
        resource_id="vm-1",
        classification=ResourceClassification.WELL_UTILIZED,
        confidence=0.0,
        severity=Severity.NONE,
    )

    written = asyncio.run(
        persist_recommendation_ledger(
            db=db,
            verdicts=[verdict],
            evidence_bundles=[_evidence_bundle()],
            findings=[{"cloud_resource_id": "vm-1"}],
            user_id="user-1",
            integration_id="int-1",
            provider="azure",
        )
    )

    assert written == 0
    assert db.collections[RECOMMENDATION_LEDGER_COLLECTION] == []
