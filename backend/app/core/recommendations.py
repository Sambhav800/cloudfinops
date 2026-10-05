"""
Recommendation ledger persistence.

The ledger is the authoritative backend record for optimization opportunities.
It is written from deterministic verdicts first; AI and provider-native signals
can enrich the same records later without blocking scan completion.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from ..optimization.evidence_collector import EvidenceBundle
from ..optimization.severity import ResourceVerdict

logger = logging.getLogger(__name__)

RECOMMENDATION_LEDGER_COLLECTION = "recommendation_ledger"
RECOMMENDATION_EVIDENCE_COLLECTION = "recommendation_evidence"
RECOMMENDATION_STATE_EVENTS_COLLECTION = "recommendation_state_events"
PROVIDER_RECOMMENDATION_COLLECTION = "provider_recommendations"
RECOMMENDATION_ID_PATTERN = r"^rec_[0-9a-f]{24}$"

CLAIMABLE_SAVINGS_STATUSES = {
    "supported_actual",
    "supported_catalog",
    "provider_estimate",
}

_DEFINITIVE_SCANNER_WASTE_TYPES = {
    "deallocated_vm",
    "old_snapshot",
    "orphan_disk",
    "orphan_nic",
    "orphaned_disk",
    "stopped_vm",
    "unattached_disk",
    "unattached_volume",
    "unused_ip",
    "zombie_ip",
    "zombie_lb",
    "zombie_vm",
}

PROTECTED_RECOMMENDATION_STATES = {
    "approved",
    "dismissed",
    "implemented",
    "verifying",
    "verified_saved",
    "verified_no_savings",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip()


def _stable_hash(parts: Iterable[Any]) -> str:
    raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def recommendation_id_for(
    user_id: str,
    integration_id: str,
    provider: str,
    resource_id: str,
    action: str,
) -> str:
    """Build a stable recommendation id for scan replays and dedupe."""
    digest = _stable_hash([user_id, integration_id, provider, resource_id, action])
    return f"rec_{digest}"


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _pricing_basis_from_finding(finding: Dict[str, Any], cost_source: str = "") -> str:
    metadata = finding.get("metadata") if isinstance(finding.get("metadata"), dict) else {}
    raw = (
        metadata.get("pricing_basis")
        or metadata.get("cost_pricing_basis")
        or finding.get("pricing_basis")
        or "unknown"
    )
    basis = str(raw or "unknown").strip().lower()
    if basis not in {"live_api", "partial_live", "static_fallback", "unknown"}:
        basis = "unknown"
    if basis != "unknown":
        return basis

    normalized_source = str(cost_source or metadata.get("cost_source") or "").strip().lower()
    if normalized_source in {"actual", "catalog_estimate", "provider_native"}:
        return "live_api"
    if normalized_source == "community_estimate":
        return "partial_live"
    return "unknown"


def _pricing_computed_at_from_finding(
    finding: Dict[str, Any],
    *,
    fallback: Optional[str] = None,
) -> Optional[str]:
    metadata = finding.get("metadata") if isinstance(finding.get("metadata"), dict) else {}
    raw = (
        metadata.get("pricing_computed_at")
        or metadata.get("pricing_updated_at")
        or metadata.get("cost_computed_at")
        or finding.get("pricing_computed_at")
    )
    return str(raw).strip() if raw else fallback


def _has_deterministic_evidence(
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    finding: Dict[str, Any],
) -> bool:
    if verdict.corroborating_signals:
        return True
    if evidence.has_sufficient_data:
        return True

    waste_type = str(finding.get("waste_type") or "").strip().lower()
    if waste_type in _DEFINITIVE_SCANNER_WASTE_TYPES:
        return True

    provider_state = str(getattr(evidence.provider_state, "value", evidence.provider_state) or "").lower()
    return (
        provider_state in {"stopped", "terminated", "deallocated", "suspended"}
        and evidence.resource_age_known
        and evidence.resource_age_days >= 14
    )


def _recommendation_quality(
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    finding: Dict[str, Any],
) -> tuple[str, List[str]]:
    reasons: List[str] = []
    if not _has_deterministic_evidence(verdict, evidence, finding):
        reasons.append("No sufficient metric window or definitive provider-state evidence was collected.")
        return "insufficient_evidence", reasons

    if verdict.vetoing_signals:
        reasons.append("A dependency, ownership, or workload signal requires human review.")
    if verdict.ai_verification_needed or verdict.requires_human_review or verdict.confidence < 0.70:
        reasons.append("The deterministic confidence is below the automatic review threshold.")
    if reasons:
        return "needs_review", reasons
    return "ready", []


def _savings_claim(
    *,
    action: str,
    amount: float,
    cost_source: str,
    pricing_basis: str,
    quality_status: str,
) -> Dict[str, Any]:
    if amount <= 0:
        return {
            "status": "unavailable",
            "claimable_amount": 0.0,
            "method": "not_calculated",
            "reason": "No positive savings amount was supported by the collected cost data.",
        }
    if quality_status != "ready":
        return {
            "status": "withheld_evidence",
            "claimable_amount": 0.0,
            "method": "withheld",
            "reason": "Savings are withheld until the recommendation passes the deterministic evidence gate.",
        }

    normalized_action = action.strip().lower()
    if normalized_action not in {"delete", "terminate"}:
        return {
            "status": "withheld_calculation",
            "claimable_amount": 0.0,
            "method": "action_requires_target_pricing",
            "reason": "This action needs a target SKU, schedule, or commitment calculation before savings can be claimed.",
        }

    normalized_source = cost_source.strip().lower()
    if normalized_source == "actual":
        status = "supported_actual"
        method = "current_billed_cost_elimination"
    elif normalized_source == "provider_native":
        status = "provider_estimate"
        method = "provider_native_estimate"
    elif normalized_source == "catalog_estimate" and pricing_basis == "live_api":
        status = "supported_catalog"
        method = "provider_catalog_cost_elimination"
    elif normalized_source == "community_estimate":
        return {
            "status": "withheld_partial_pricing",
            "claimable_amount": 0.0,
            "method": "community_price_reference",
            "reason": "Community pricing is supporting context, not an authoritative savings claim.",
        }
    elif pricing_basis == "static_fallback":
        return {
            "status": "withheld_static_pricing",
            "claimable_amount": 0.0,
            "method": "static_fallback",
            "reason": "Static fallback pricing is not included in enterprise savings totals.",
        }
    else:
        return {
            "status": "withheld_missing_pricing",
            "claimable_amount": 0.0,
            "method": "pricing_unavailable",
            "reason": "A trustworthy resource-level cost source is required before savings can be claimed.",
        }

    return {
        "status": status,
        "claimable_amount": round(amount, 2),
        "method": method,
        "reason": "Savings are based on eliminating the full supported monthly resource cost.",
    }


def _trust_score(
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    quality_status: str,
) -> int:
    score = verdict.confidence * 100
    if evidence.cost_source == "actual":
        score += 10
    elif evidence.cost_source in {"catalog_estimate", "community_estimate"}:
        score += 3

    if len(verdict.corroborating_signals) >= 3:
        score += 5
    if verdict.vetoing_signals:
        score -= 30
    if verdict.ai_verification_needed:
        score -= 10
    if not evidence.has_sufficient_data:
        score -= 15

    score = int(max(0, min(100, round(score))))
    if quality_status == "insufficient_evidence":
        return min(score, 49)
    if quality_status == "needs_review":
        return min(score, 69)
    return score


def _initial_state(verdict: ResourceVerdict, quality_status: str) -> str:
    if quality_status == "insufficient_evidence":
        return "detected"
    if quality_status == "needs_review" or verdict.ai_verification_needed:
        return "evidence_ready"
    if verdict.recommendation:
        return "ready_for_review"
    return "detected"


def _evidence_status(
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    finding: Dict[str, Any],
) -> str:
    if _has_deterministic_evidence(verdict, evidence, finding):
        return "ready"
    return "missing"


def build_recommendation_record(
    *,
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    finding: Dict[str, Any],
    user_id: str,
    integration_id: str,
    provider: str,
    existing_record: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Convert a deterministic verdict into a ledger record."""
    recommendation = verdict.recommendation
    if not recommendation:
        return None

    action = _enum_value(recommendation.action) or "investigate"
    if action == "no_action":
        return None

    resource_id = verdict.resource_id or evidence.resource_id
    rec_id = recommendation_id_for(user_id, integration_id, provider, resource_id, action)
    existing_state = str((existing_record or {}).get("state") or "").strip().lower()
    metadata = finding.get("metadata") if isinstance(finding.get("metadata"), dict) else {}
    cost_source = evidence.cost_source or metadata.get("cost_source") or "unknown"
    pricing_basis = _pricing_basis_from_finding(finding, str(cost_source))
    pricing_computed_at = _pricing_computed_at_from_finding(
        finding,
        fallback=verdict.determined_at.isoformat() if pricing_basis != "unknown" else None,
    )
    quality_status, quality_reasons = _recommendation_quality(verdict, evidence, finding)
    state = existing_state if existing_state in PROTECTED_RECOMMENDATION_STATES else _initial_state(verdict, quality_status)
    raw_savings = round(_safe_float(recommendation.estimated_monthly_savings), 2)
    savings_claim = _savings_claim(
        action=action,
        amount=raw_savings,
        cost_source=str(cost_source),
        pricing_basis=pricing_basis,
        quality_status=quality_status,
    )
    existing_ai_status = str((existing_record or {}).get("ai_enrichment_status") or "").strip().lower()
    preserved_ai_statuses = {"queued", "running", "enriched"}
    ai_enrichment_status = existing_ai_status if existing_ai_status in preserved_ai_statuses else "pending"

    return {
        "id": rec_id,
        "user_id": user_id,
        "integration_id": integration_id,
        "provider": provider,
        "resource_id": resource_id,
        "cloud_resource_id": evidence.cloud_resource_id or resource_id,
        "resource_name": evidence.resource_name or finding.get("resource_name") or resource_id,
        "resource_type": evidence.resource_type or finding.get("service_type") or "Cloud Resource",
        "region": evidence.region or finding.get("region") or finding.get("region_compliance") or "",
        "recommendation_type": verdict.classification.value,
        "action": action,
        "state": state,
        "severity": verdict.severity.value,
        "confidence": round(float(verdict.confidence), 4),
        "trust_score": _trust_score(verdict, evidence, quality_status),
        "quality_status": quality_status,
        "quality_reasons": quality_reasons,
        "risk_level": recommendation.risk,
        "effort": recommendation.effort,
        "description": recommendation.description,
        "waste_reason": verdict.waste_reason,
        "estimated_monthly_savings": raw_savings,
        "claimable_monthly_savings": savings_claim["claimable_amount"],
        "savings_estimate_status": savings_claim["status"],
        "savings_calculation_method": savings_claim["method"],
        "savings_estimate_reason": savings_claim["reason"],
        "estimated_monthly_waste": round(_safe_float(verdict.estimated_monthly_waste), 2),
        "cost_source": str(cost_source or "unknown"),
        "pricing_basis": pricing_basis,
        "pricing_computed_at": pricing_computed_at,
        "evidence_status": _evidence_status(verdict, evidence, finding),
        "provider_agreement_status": "unknown",
        "ai_enrichment_status": ai_enrichment_status,
        "ai_enrichment_id": (existing_record or {}).get("ai_enrichment_id"),
        "ai_enrichment_job_id": (existing_record or {}).get("ai_enrichment_job_id"),
        "ai_enriched_at": (existing_record or {}).get("ai_enriched_at"),
        "ai_model": (existing_record or {}).get("ai_model"),
        "ai_summary": (existing_record or {}).get("ai_summary"),
        "ai_enrichment_error": None if ai_enrichment_status == "pending" else (existing_record or {}).get("ai_enrichment_error"),
        "source_systems": ["cloudfinops_deterministic_optimizer"],
        "pipeline_version": verdict.pipeline_version,
        "detected_at": verdict.determined_at.isoformat(),
        "expires_at": None,
    }


def _signal_window(evidence: EvidenceBundle, signal_name: str) -> tuple[Optional[str], Optional[str]]:
    signal = evidence.signals.get(signal_name)
    if not signal or not signal.timestamps:
        return None, None
    ordered = sorted(signal.timestamps)
    return ordered[0].isoformat(), ordered[-1].isoformat()


def build_evidence_records(
    *,
    recommendation_id: str,
    verdict: ResourceVerdict,
    evidence: EvidenceBundle,
    finding: Dict[str, Any],
    user_id: str,
) -> List[Dict[str, Any]]:
    """Build queryable evidence rows for a recommendation drawer."""
    records: List[Dict[str, Any]] = []
    collected_at = _utc_now_iso()
    metadata = finding.get("metadata") if isinstance(finding.get("metadata"), dict) else {}

    scanner_status = str(finding.get("status") or "").strip()
    scanner_waste_type = str(finding.get("waste_type") or "").strip()
    if scanner_status or scanner_waste_type:
        records.append({
            "id": f"{recommendation_id}_provider_state",
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "resource_id": verdict.resource_id,
            "evidence_kind": "provider_state",
            "signal_name": "resource_status",
            "observed_value": {
                "status": scanner_status or None,
                "waste_type": scanner_waste_type or None,
                "resource_age_days": evidence.resource_age_days if evidence.resource_age_known else None,
            },
            "threshold": None,
            "description": "Provider inventory state used by the deterministic classifier.",
            "metric_window_start": None,
            "metric_window_end": None,
            "data_completeness": 1.0 if scanner_status else evidence.data_completeness,
            "source_system": f"{evidence.provider}_scanner",
            "collected_at": collected_at,
        })

    cost_source = str(evidence.cost_source or metadata.get("cost_source") or "unknown")
    pricing_basis = _pricing_basis_from_finding(finding, cost_source)
    records.append({
        "id": f"{recommendation_id}_cost_provenance",
        "user_id": user_id,
        "recommendation_id": recommendation_id,
        "resource_id": verdict.resource_id,
        "evidence_kind": "cost_provenance",
        "signal_name": "monthly_cost",
        "observed_value": {
            "amount": round(_safe_float(evidence.monthly_cost), 2),
            "currency": metadata.get("currency") or finding.get("currency") or "USD",
            "cost_source": cost_source,
            "pricing_basis": pricing_basis,
        },
        "threshold": None,
        "description": "Cost provenance used for the savings claim decision.",
        "metric_window_start": None,
        "metric_window_end": None,
        "data_completeness": 1.0 if cost_source == "actual" else evidence.data_completeness,
        "source_system": str(metadata.get("pricing_source") or cost_source or "unknown"),
        "collected_at": collected_at,
    })

    for index, signal in enumerate(verdict.corroborating_signals):
        window_start, window_end = _signal_window(evidence, signal.signal_name)
        records.append({
            "id": f"{recommendation_id}_corroborating_{index}_{signal.signal_name}",
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "resource_id": verdict.resource_id,
            "evidence_kind": "corroborating_signal",
            "signal_name": signal.signal_name,
            "observed_value": signal.observed_value,
            "threshold": signal.threshold,
            "description": signal.description,
            "metric_window_start": window_start,
            "metric_window_end": window_end,
            "data_completeness": evidence.data_completeness,
            "source_system": "cloudfinops_deterministic_optimizer",
            "collected_at": collected_at,
        })

    for index, veto in enumerate(verdict.vetoing_signals):
        records.append({
            "id": f"{recommendation_id}_veto_{index}_{_stable_hash([veto.signal_type, veto.reason])}",
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "resource_id": verdict.resource_id,
            "evidence_kind": "veto_signal",
            "signal_name": veto.signal_type,
            "observed_value": veto.details,
            "threshold": None,
            "description": veto.reason,
            "metric_window_start": None,
            "metric_window_end": None,
            "data_completeness": evidence.data_completeness,
            "source_system": "cloudfinops_deterministic_optimizer",
            "collected_at": collected_at,
        })

    for index, factor in enumerate(verdict.context_factors):
        records.append({
            "id": f"{recommendation_id}_context_{index}_{_stable_hash([factor])}",
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "resource_id": verdict.resource_id,
            "evidence_kind": "context_factor",
            "signal_name": "context",
            "observed_value": factor,
            "threshold": None,
            "description": factor,
            "metric_window_start": None,
            "metric_window_end": None,
            "data_completeness": evidence.data_completeness,
            "source_system": "cloudfinops_deterministic_optimizer",
            "collected_at": collected_at,
        })

    return records


async def persist_recommendation_ledger(
    *,
    db: Any,
    verdicts: List[ResourceVerdict],
    evidence_bundles: List[EvidenceBundle],
    findings: List[Dict[str, Any]],
    user_id: str,
    integration_id: str,
    provider: str,
) -> int:
    """Persist deterministic optimization recommendations and evidence."""
    try:
        evidence_by_resource = {bundle.resource_id: bundle for bundle in evidence_bundles}
        findings_by_resource = {
            str(finding.get("cloud_resource_id") or finding.get("resource_name") or ""): finding
            for finding in findings
        }
        written = 0

        for verdict in verdicts:
            evidence = evidence_by_resource.get(verdict.resource_id)
            if not evidence:
                continue

            finding = findings_by_resource.get(verdict.resource_id, {})
            recommendation_id = recommendation_id_for(
                user_id,
                integration_id,
                provider,
                verdict.resource_id,
                _enum_value(verdict.recommendation.action) if verdict.recommendation else "",
            )

            existing = await db.select(
                RECOMMENDATION_LEDGER_COLLECTION,
                filters={"user_id": user_id, "id": recommendation_id},
            )
            record = build_recommendation_record(
                verdict=verdict,
                evidence=evidence,
                finding=finding,
                user_id=user_id,
                integration_id=integration_id,
                provider=provider,
                existing_record=existing[0] if existing else None,
            )
            if not record:
                continue

            await db.upsert(RECOMMENDATION_LEDGER_COLLECTION, record)
            await db.delete(
                RECOMMENDATION_EVIDENCE_COLLECTION,
                {"user_id": user_id, "recommendation_id": record["id"]},
            )
            evidence_records = build_evidence_records(
                recommendation_id=record["id"],
                verdict=verdict,
                evidence=evidence,
                finding=finding,
                user_id=user_id,
            )
            if evidence_records:
                await db.insert(RECOMMENDATION_EVIDENCE_COLLECTION, evidence_records)

            if not existing:
                await db.insert(
                    RECOMMENDATION_STATE_EVENTS_COLLECTION,
                    {
                        "id": f"{record['id']}_detected",
                        "user_id": user_id,
                        "recommendation_id": record["id"],
                        "from_state": None,
                        "to_state": record["state"],
                        "actor_type": "system",
                        "actor_id": "cloudfinops_deterministic_optimizer",
                        "reason": "Detected by deterministic optimization pipeline",
                        "created_at": _utc_now_iso(),
                    },
                )

            written += 1

        logger.info("Persisted %s recommendation ledger records", written)
        return written
    except Exception as error:
        logger.error("persist_recommendation_ledger failed: %s", error)
        raise


def summarize_recommendation_candidates(
    *,
    verdicts: List[ResourceVerdict],
    evidence_bundles: List[EvidenceBundle],
    findings: List[Dict[str, Any]],
    user_id: str,
    integration_id: str,
    provider: str,
) -> Dict[str, Any]:
    """Build the current scan's trusted financial summary from ledger records."""
    evidence_by_resource = {bundle.resource_id: bundle for bundle in evidence_bundles}
    findings_by_resource = {
        str(finding.get("cloud_resource_id") or finding.get("resource_name") or ""): finding
        for finding in findings
    }
    records: List[Dict[str, Any]] = []
    for verdict in verdicts:
        evidence = evidence_by_resource.get(verdict.resource_id)
        if not evidence:
            continue
        record = build_recommendation_record(
            verdict=verdict,
            evidence=evidence,
            finding=findings_by_resource.get(verdict.resource_id, {}),
            user_id=user_id,
            integration_id=integration_id,
            provider=provider,
        )
        if record:
            records.append(record)

    ready_records = [record for record in records if record.get("quality_status") == "ready"]
    claimable_records = [
        record
        for record in ready_records
        if record.get("savings_estimate_status") in CLAIMABLE_SAVINGS_STATUSES
    ]
    confidence_score = 0
    if ready_records:
        confidence_score = int(round(
            sum(_safe_float(record.get("confidence")) for record in ready_records)
            / len(ready_records)
            * 100
        ))

    return {
        "records": records,
        "recommendation_count": len(records),
        "ready_count": len(ready_records),
        "claimable_count": len(claimable_records),
        "claimable_monthly_savings": round(
            sum(_safe_float(record.get("claimable_monthly_savings")) for record in claimable_records),
            2,
        ),
        "detector_monthly_savings": round(
            sum(_safe_float(record.get("estimated_monthly_savings")) for record in records),
            2,
        ),
        "confidence_score": confidence_score,
    }
