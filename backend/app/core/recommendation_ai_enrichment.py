"""
Asynchronous AI enrichment for recommendation ledger records.

Deterministic recommendations remain the source of truth. This module only adds
versioned, evidence-grounded narrative context after the recommendation already
exists, so Gemini latency or failure never blocks scans or dashboard reads.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .gemini_models import resolve_gemini_model_name
from .recommendations import (
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
)

logger = logging.getLogger(__name__)

RECOMMENDATION_AI_JOBS_COLLECTION = "recommendation_ai_jobs"
RECOMMENDATION_AI_ENRICHMENTS_COLLECTION = "recommendation_ai_enrichments"
AI_ENRICHMENT_PROMPT_VERSION = "recommendation_ai_enrichment_v1"
AI_ENRICHMENT_RUN_COOLDOWN_SECONDS = 0
AI_ENRICHMENT_DAILY_JOB_LIMIT = 250

_TERMINAL_RECOMMENDATION_STATES = {"dismissed", "expired", "superseded"}
_ACTIVE_JOB_STATUSES = {"queued", "running"}
_FINAL_AI_STATUSES = {"enriched", "not_required"}
_QUALITY_FAILED_JOB_STATUS = "failed_quality_gate"
_MAX_REMEDIATION_STEPS = 6
_MAX_ASSUMPTIONS = 5
_MAX_EVIDENCE_ROWS = 8
_DISALLOWED_OUTPUT_TERMS = ("terraform", "aws cli", "az cli", "gcloud", "kubectl")
_SIGNAL_SUPPORT_TERMS = {
    "cpu": ("cpu", "processor"),
    "memory": ("memory", "ram"),
    "network": ("network", "ingress", "egress"),
    "disk": ("disk", "storage", "iops"),
    "connection": ("connection", "connections"),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_string(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized or fallback


def _as_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean_text(value: Any, *, max_length: int = 1200) -> str:
    text = _as_string(value)
    if not text:
        return ""
    return " ".join(text.split())[:max_length]


def _clean_string_list(value: Any, *, limit: int, max_item_length: int = 280) -> List[str]:
    raw_items = value if isinstance(value, list) else [value]
    cleaned: List[str] = []
    for item in raw_items:
        text = _clean_text(item, max_length=max_item_length)
        if text:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _as_string(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _run_activity_time(row: Dict[str, Any]) -> Optional[datetime]:
    timestamps = [
        parsed
        for parsed in (
            _parse_iso_datetime(row.get("started_at")),
            _parse_iso_datetime(row.get("completed_at")),
        )
        if parsed is not None
    ]
    return max(timestamps) if timestamps else None


def _job_id_for(user_id: str, recommendation_id: str) -> str:
    digest = _stable_hash({"user_id": user_id, "recommendation_id": recommendation_id})[:24]
    return f"rec_ai_job_{digest}"


def _enrichment_id_for(recommendation_id: str) -> str:
    digest = _stable_hash({"recommendation_id": recommendation_id})[:24]
    return f"rec_ai_enrichment_{digest}"


def _evidence_priority(row: Dict[str, Any]) -> int:
    kind = _as_string(row.get("evidence_kind")).lower()
    if kind == "veto_signal":
        return 0
    if kind == "corroborating_signal":
        return 1
    return 2


def _compact_evidence_rows(evidence_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compacted: List[Dict[str, Any]] = []
    ordered = sorted(
        evidence_rows,
        key=lambda row: (
            _evidence_priority(row),
            _as_string(row.get("signal_name")),
            _as_string(row.get("id")),
        ),
    )
    for row in ordered[:_MAX_EVIDENCE_ROWS]:
        compacted.append({
            "id": _as_string(row.get("id")),
            "kind": _as_string(row.get("evidence_kind"), "unknown"),
            "signal": _as_string(row.get("signal_name"), "unknown"),
            "observed_value": row.get("observed_value"),
            "threshold": row.get("threshold"),
            "description": _clean_text(row.get("description"), max_length=360),
            "metric_window_start": row.get("metric_window_start"),
            "metric_window_end": row.get("metric_window_end"),
            "data_completeness": _as_float(row.get("data_completeness")),
            "source_system": _as_string(row.get("source_system"), "unknown"),
        })
    return compacted


def build_enrichment_input(
    recommendation: Dict[str, Any],
    evidence_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the compact, stable payload sent to the AI enrichment worker."""
    return {
        "recommendation_id": _as_string(recommendation.get("id")),
        "provider": _as_string(recommendation.get("provider"), "unknown"),
        "integration_id": _as_string(recommendation.get("integration_id")),
        "resource": {
            "id": _as_string(recommendation.get("resource_id")),
            "cloud_resource_id": _as_string(
                recommendation.get("cloud_resource_id") or recommendation.get("resource_id")
            ),
            "name": _as_string(recommendation.get("resource_name"), "Unknown resource"),
            "type": _as_string(recommendation.get("resource_type"), "Cloud Resource"),
            "region": _as_string(recommendation.get("region")),
        },
        "deterministic_recommendation": {
            "type": _as_string(recommendation.get("recommendation_type")),
            "action": _as_string(recommendation.get("action"), "investigate"),
            "severity": _as_string(recommendation.get("severity"), "none"),
            "confidence": _as_float(recommendation.get("confidence")),
            "trust_score": _as_int(recommendation.get("trust_score")),
            "risk_level": _as_string(recommendation.get("risk_level"), "unknown"),
            "effort": _as_string(recommendation.get("effort"), "unknown"),
            "description": _clean_text(recommendation.get("description"), max_length=600),
            "waste_reason": _clean_text(recommendation.get("waste_reason"), max_length=600),
        },
        "savings": {
            "estimated_monthly_savings": _as_float(recommendation.get("estimated_monthly_savings")),
            "estimated_monthly_waste": _as_float(recommendation.get("estimated_monthly_waste")),
            "currency": _as_string(recommendation.get("savings_currency") or "provider_default"),
            "cost_source": _as_string(recommendation.get("cost_source"), "unknown"),
            "pricing_basis": _as_string(recommendation.get("pricing_basis"), "unknown"),
            "pricing_computed_at": recommendation.get("pricing_computed_at"),
        },
        "provider_agreement_status": _as_string(
            recommendation.get("provider_agreement_status"),
            "unknown",
        ),
        "evidence": _compact_evidence_rows(evidence_rows),
        "prompt_version": AI_ENRICHMENT_PROMPT_VERSION,
    }


def _is_recommendation_eligible(recommendation: Dict[str, Any], *, force: bool) -> bool:
    state = _as_string(recommendation.get("state"), "detected").lower()
    if state in _TERMINAL_RECOMMENDATION_STATES:
        return False

    status = _as_string(recommendation.get("ai_enrichment_status"), "pending").lower()
    if not force and status in _ACTIVE_JOB_STATUSES.union(_FINAL_AI_STATUSES):
        return False

    description = _as_string(recommendation.get("description") or recommendation.get("waste_reason"))
    return bool(description or force)


def _priority_for(recommendation: Dict[str, Any]) -> int:
    severity_rank = {"critical": 500, "high": 400, "medium": 300, "low": 200}
    severity = _as_string(recommendation.get("severity"), "none").lower()
    savings = min(250, int(round(_as_float(recommendation.get("estimated_monthly_savings")))))
    trust_score = min(100, max(0, _as_int(recommendation.get("trust_score"))))
    return severity_rank.get(severity, 100) + savings + trust_score


async def get_recommendation_ai_enrichment(
    *,
    db: Any,
    user_id: str,
    recommendation_id: str,
) -> Optional[Dict[str, Any]]:
    """Return the latest stored AI enrichment for one user-scoped recommendation."""
    try:
        rows = await db.select(
            RECOMMENDATION_AI_ENRICHMENTS_COLLECTION,
            filters={"user_id": user_id, "recommendation_id": recommendation_id},
        )
        if not rows:
            return None
        ordered = sorted(
            rows,
            key=lambda row: _as_string(row.get("updated_at") or row.get("created_at")),
            reverse=True,
        )
        return ordered[0]
    except Exception as error:
        logger.error("get_recommendation_ai_enrichment failed: %s", error)
        raise


async def get_ai_enrichment_run_quota(
    *,
    db: Any,
    user_id: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return the current user-scoped manual AI enrichment run allowance."""
    try:
        now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        rows = await db.select(RECOMMENDATION_AI_JOBS_COLLECTION, filters={"user_id": user_id})
        activity_times = [
            timestamp
            for timestamp in (_run_activity_time(row) for row in rows)
            if timestamp is not None
        ]
        latest_activity = max(activity_times) if activity_times else None
        recent_count = sum(
            1
            for timestamp in activity_times
            if now_utc - timestamp <= timedelta(hours=24)
        )
        remaining = max(0, AI_ENRICHMENT_DAILY_JOB_LIMIT - recent_count)

        if latest_activity:
            seconds_since_latest = (now_utc - latest_activity).total_seconds()
            if 0 <= seconds_since_latest < AI_ENRICHMENT_RUN_COOLDOWN_SECONDS:
                retry_after = int(AI_ENRICHMENT_RUN_COOLDOWN_SECONDS - seconds_since_latest) + 1
                return {
                    "allowed": False,
                    "message": f"Please wait {retry_after}s before starting another AI enrichment run",
                    "retry_after_seconds": retry_after,
                    "remaining_daily_jobs": remaining,
                }

        if recent_count >= AI_ENRICHMENT_DAILY_JOB_LIMIT:
            return {
                "allowed": False,
                "message": "Daily AI enrichment job limit reached",
                "retry_after_seconds": None,
                "remaining_daily_jobs": 0,
            }

        return {
            "allowed": True,
            "message": None,
            "retry_after_seconds": None,
            "remaining_daily_jobs": remaining,
        }
    except Exception as error:
        logger.error("get_ai_enrichment_run_quota failed: %s", error)
        raise


async def enqueue_recommendation_ai_jobs(
    *,
    db: Any,
    user_id: str,
    model: str,
    integration_id: Optional[str] = None,
    recommendation_ids: Optional[List[str]] = None,
    force: bool = False,
    queue_limit: int = 25,
) -> Dict[str, Any]:
    """Create or refresh AI enrichment jobs for eligible recommendations."""
    try:
        model_name = _as_string(model)
        if not model_name:
            raise ValueError("AI enrichment model is not configured")

        safe_queue_limit = max(1, min(_as_int(queue_limit) or 25, 100))
        filters: Dict[str, Any] = {"user_id": user_id}
        if integration_id:
            filters["integration_id"] = integration_id

        rows = await db.select(RECOMMENDATION_LEDGER_COLLECTION, filters=filters)
        wanted_ids = {item for item in (recommendation_ids or []) if item}
        if wanted_ids:
            rows = [row for row in rows if _as_string(row.get("id")) in wanted_ids]

        queued_job_ids: List[str] = []
        skipped = 0
        now = _utc_now_iso()
        candidates: List[Dict[str, Any]] = []

        for recommendation in rows:
            recommendation_id = _as_string(recommendation.get("id"))
            if not recommendation_id or not _is_recommendation_eligible(recommendation, force=force):
                skipped += 1
                continue
            candidates.append(recommendation)

        ordered_candidates = sorted(candidates, key=_priority_for, reverse=True)
        limited_candidates = ordered_candidates[:safe_queue_limit]
        skipped += max(0, len(ordered_candidates) - len(limited_candidates))

        for recommendation in limited_candidates:
            recommendation_id = _as_string(recommendation.get("id"))
            evidence_rows = await db.select(
                RECOMMENDATION_EVIDENCE_COLLECTION,
                filters={"user_id": user_id, "recommendation_id": recommendation_id},
            )
            enrichment_input = build_enrichment_input(recommendation, evidence_rows)
            input_hash = _stable_hash(enrichment_input)
            job_id = _job_id_for(user_id, recommendation_id)

            existing_jobs = await db.select(
                RECOMMENDATION_AI_JOBS_COLLECTION,
                filters={"user_id": user_id, "id": job_id},
            )
            existing_job = existing_jobs[0] if existing_jobs else {}
            if (
                not force
                and _as_string(existing_job.get("status")).lower() in _ACTIVE_JOB_STATUSES
                and _as_string(existing_job.get("input_hash")) == input_hash
            ):
                skipped += 1
                continue

            job = {
                "id": job_id,
                "user_id": user_id,
                "integration_id": _as_string(recommendation.get("integration_id")),
                "recommendation_id": recommendation_id,
                "resource_id": _as_string(recommendation.get("resource_id")),
                "status": "queued",
                "priority": _priority_for(recommendation),
                "attempts": _as_int(existing_job.get("attempts")),
                "input_hash": input_hash,
                "model": model_name,
                "prompt_version": AI_ENRICHMENT_PROMPT_VERSION,
                "queued_at": now,
                "started_at": None,
                "completed_at": None,
                "last_error": None,
                "lease_id": None,
            }
            await db.upsert(RECOMMENDATION_AI_JOBS_COLLECTION, job)
            await db.update(
                RECOMMENDATION_LEDGER_COLLECTION,
                {
                    "ai_enrichment_status": "queued",
                    "ai_enrichment_job_id": job_id,
                    "ai_enrichment_error": None,
                },
                {"user_id": user_id, "id": recommendation_id},
            )
            queued_job_ids.append(job_id)

        return {
            "queued": len(queued_job_ids),
            "skipped": skipped,
            "queue_limit": safe_queue_limit,
            "job_ids": queued_job_ids,
        }
    except Exception as error:
        logger.error("enqueue_recommendation_ai_jobs failed: %s", error)
        raise


def _build_prompt(enrichment_input: Dict[str, Any]) -> str:
    payload = json.dumps(enrichment_input, ensure_ascii=True, indent=2, default=str)
    return f"""You are CloudFinOps' enterprise cost optimization reviewer.

Use ONLY the deterministic recommendation and evidence JSON below. Do not invent
metrics, prices, tags, owners, or implementation status. Do not generate Terraform
or cloud CLI commands. Produce concise operator guidance that helps a human infra
team validate and execute the recommendation.

Return strict JSON with these keys:
- summary: one sentence, max 220 chars
- business_impact: one sentence on cost/risk impact
- evidence_narrative: one concise paragraph explaining why the evidence supports this
- remediation_steps: 3-6 human handoff steps, no code
- risk_notes: one sentence on implementation risk
- rollback_plan: one sentence
- validation_plan: one sentence describing how to confirm savings safely
- assumptions: array of assumptions, max 5
- confidence_notes: one sentence explaining what would increase or decrease confidence
- evidence_ids_used: array of evidence.id values used; every value must exist in the evidence JSON

Recommendation evidence JSON:
{payload}
"""


async def _call_gemini_enrichment(
    *,
    enrichment_input: Dict[str, Any],
    gemini_api_key: str,
    model: str,
) -> str:
    """Call Gemini through the existing REST pattern used by backend AI code."""
    try:
        import httpx

        prompt = _build_prompt(enrichment_input)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                url,
                params={"key": gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 1400,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return _as_string(parts[0].get("text"))
        return ""
    except Exception as error:
        logger.error("_call_gemini_enrichment failed: %s", error)
        raise


def _parse_json_object(response_text: str) -> Dict[str, Any]:
    text = response_text.strip()
    if not text:
        raise ValueError("AI enrichment response was empty")

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI enrichment response was not valid JSON")
        parsed = json.loads(text[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("AI enrichment response must be a JSON object")
    return parsed


def _support_corpus(
    *,
    evidence_rows: List[Dict[str, Any]],
    enrichment_input: Optional[Dict[str, Any]],
) -> str:
    support_payload = {
        "evidence": _compact_evidence_rows(evidence_rows),
        "deterministic_input": enrichment_input or {},
    }
    return json.dumps(support_payload, sort_keys=True, default=str).lower()


def _validate_ai_enrichment_quality(
    normalized: Dict[str, Any],
    *,
    evidence_rows: List[Dict[str, Any]],
    enrichment_input: Optional[Dict[str, Any]],
) -> None:
    missing_fields = [
        field
        for field in (
            "summary",
            "business_impact",
            "evidence_narrative",
            "risk_notes",
            "rollback_plan",
            "validation_plan",
            "confidence_notes",
        )
        if not _as_string(normalized.get(field))
    ]
    if len(normalized.get("remediation_steps") or []) < 3:
        missing_fields.append("remediation_steps")
    if missing_fields:
        raise ValueError(
            "AI enrichment failed quality gate: missing required fields "
            + ", ".join(sorted(set(missing_fields)))
        )

    available_evidence_ids = {
        _as_string(row.get("id"))
        for row in _compact_evidence_rows(evidence_rows)
        if _as_string(row.get("id"))
    }
    evidence_ids_used = {
        _as_string(item)
        for item in normalized.get("evidence_ids_used", [])
        if _as_string(item)
    }
    if available_evidence_ids and not evidence_ids_used:
        raise ValueError("AI enrichment failed quality gate: evidence_ids_used is required")

    unknown_ids = sorted(evidence_ids_used - available_evidence_ids)
    if unknown_ids:
        raise ValueError(
            "AI enrichment failed quality gate: unknown evidence ids "
            + ", ".join(unknown_ids)
        )

    full_text = " ".join(
        str(value)
        for key, value in normalized.items()
        if key not in {"evidence_ids_used", "quality_status"}
    ).lower()
    for term in _DISALLOWED_OUTPUT_TERMS:
        if term in full_text:
            raise ValueError(
                f"AI enrichment failed quality gate: disallowed implementation guidance '{term}'"
            )

    claim_text = " ".join(
        _as_string(normalized.get(field))
        for field in ("summary", "business_impact", "evidence_narrative", "risk_notes")
    ).lower()
    corpus = _support_corpus(evidence_rows=evidence_rows, enrichment_input=enrichment_input)
    for signal_name, terms in _SIGNAL_SUPPORT_TERMS.items():
        mentions_signal = any(term in claim_text for term in terms)
        has_support = any(term in corpus for term in terms)
        if mentions_signal and not has_support:
            raise ValueError(
                f"AI enrichment failed quality gate: mentions {signal_name} without supporting evidence"
            )


def normalize_ai_enrichment_payload(
    response_text: str,
    *,
    evidence_rows: List[Dict[str, Any]],
    enrichment_input: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize model output into the persisted enrichment contract."""
    parsed = _parse_json_object(response_text)
    available_evidence_ids = {
        _as_string(row.get("id"))
        for row in _compact_evidence_rows(evidence_rows)
        if _as_string(row.get("id"))
    }
    raw_evidence_ids = parsed.get("evidence_ids_used")
    evidence_ids_used: List[str] = []
    if isinstance(raw_evidence_ids, list):
        for item in raw_evidence_ids:
            evidence_id = _as_string(item)
            if evidence_id and evidence_id not in evidence_ids_used:
                evidence_ids_used.append(evidence_id)
    elif raw_evidence_ids is not None:
        evidence_id = _as_string(raw_evidence_ids)
        if evidence_id:
            evidence_ids_used.append(evidence_id)

    if not available_evidence_ids:
        evidence_ids_used = []

    normalized = {
        "summary": _clean_text(parsed.get("summary"), max_length=260),
        "business_impact": _clean_text(parsed.get("business_impact"), max_length=520),
        "evidence_narrative": _clean_text(parsed.get("evidence_narrative"), max_length=1200),
        "remediation_steps": _clean_string_list(
            parsed.get("remediation_steps"),
            limit=_MAX_REMEDIATION_STEPS,
        ),
        "risk_notes": _clean_text(parsed.get("risk_notes"), max_length=520),
        "rollback_plan": _clean_text(parsed.get("rollback_plan"), max_length=520),
        "validation_plan": _clean_text(parsed.get("validation_plan"), max_length=520),
        "assumptions": _clean_string_list(parsed.get("assumptions"), limit=_MAX_ASSUMPTIONS),
        "confidence_notes": _clean_text(parsed.get("confidence_notes"), max_length=520),
        "evidence_ids_used": evidence_ids_used,
        "quality_status": "passed",
    }
    _validate_ai_enrichment_quality(
        normalized,
        evidence_rows=evidence_rows,
        enrichment_input=enrichment_input,
    )
    return normalized


async def run_recommendation_ai_enrichment_job(
    *,
    db: Any,
    user_id: str,
    job_id: str,
    gemini_api_key: str,
    model: str,
) -> Dict[str, Any]:
    """Run one queued AI enrichment job and persist its result."""
    recommendation_id = ""
    attempts = 0
    lease_id = ""
    try:
        model_name = _as_string(model)
        if not model_name:
            raise ValueError("AI enrichment model is not configured")
        model_name = await resolve_gemini_model_name(model_name, api_key=gemini_api_key)

        job_rows = await db.select(
            RECOMMENDATION_AI_JOBS_COLLECTION,
            filters={"user_id": user_id, "id": job_id},
        )
        if not job_rows:
            raise ValueError("AI enrichment job not found")

        job = job_rows[0]
        recommendation_id = _as_string(job.get("recommendation_id"))
        job_status = _as_string(job.get("status"), "queued").lower()
        if job_status != "queued":
            return {
                "job_id": job_id,
                "recommendation_id": recommendation_id,
                "status": "skipped",
                "error": f"AI enrichment job is {job_status or 'not queued'}",
            }

        attempts = _as_int(job.get("attempts")) + 1
        now = _utc_now_iso()
        lease_id = str(uuid4())
        claimed_rows = await db.update(
            RECOMMENDATION_AI_JOBS_COLLECTION,
            {
                "status": "running",
                "attempts": attempts,
                "started_at": now,
                "last_error": None,
                "lease_id": lease_id,
            },
            {"user_id": user_id, "id": job_id, "status": "queued"},
        )
        if not claimed_rows:
            return {
                "job_id": job_id,
                "recommendation_id": recommendation_id,
                "status": "skipped",
                "error": "AI enrichment job was already claimed",
            }

        claimed_job_rows = await db.select(
            RECOMMENDATION_AI_JOBS_COLLECTION,
            filters={"user_id": user_id, "id": job_id},
        )
        claimed_job = claimed_job_rows[0] if claimed_job_rows else {}
        if _as_string(claimed_job.get("lease_id")) != lease_id:
            return {
                "job_id": job_id,
                "recommendation_id": recommendation_id,
                "status": "skipped",
                "error": "AI enrichment job lease was lost",
            }
        job = claimed_job

        await db.update(
            RECOMMENDATION_LEDGER_COLLECTION,
            {"ai_enrichment_status": "running", "ai_enrichment_error": None},
            {"user_id": user_id, "id": recommendation_id},
        )

        recommendation_rows = await db.select(
            RECOMMENDATION_LEDGER_COLLECTION,
            filters={"user_id": user_id, "id": recommendation_id},
        )
        if not recommendation_rows:
            raise ValueError("Recommendation for AI enrichment job not found")

        evidence_rows = await db.select(
            RECOMMENDATION_EVIDENCE_COLLECTION,
            filters={"user_id": user_id, "recommendation_id": recommendation_id},
        )
        enrichment_input = build_enrichment_input(recommendation_rows[0], evidence_rows)
        response_text = await _call_gemini_enrichment(
            enrichment_input=enrichment_input,
            gemini_api_key=gemini_api_key,
            model=model_name,
        )
        normalized = normalize_ai_enrichment_payload(
            response_text,
            evidence_rows=evidence_rows,
            enrichment_input=enrichment_input,
        )

        completed_at = _utc_now_iso()
        enrichment_id = _enrichment_id_for(recommendation_id)
        enrichment_record = {
            "id": enrichment_id,
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "job_id": job_id,
            "status": "succeeded",
            "input_hash": _as_string(job.get("input_hash")),
            "model": model_name,
            "prompt_version": AI_ENRICHMENT_PROMPT_VERSION,
            "generated_at": completed_at,
            **normalized,
        }
        await db.upsert(RECOMMENDATION_AI_ENRICHMENTS_COLLECTION, enrichment_record)
        await db.update(
            RECOMMENDATION_LEDGER_COLLECTION,
            {
                "ai_enrichment_status": "enriched",
                "ai_enrichment_id": enrichment_id,
                "ai_enriched_at": completed_at,
                "ai_model": model_name,
                "ai_summary": normalized["summary"],
                "ai_enrichment_error": None,
            },
            {"user_id": user_id, "id": recommendation_id},
        )
        await db.update(
            RECOMMENDATION_AI_JOBS_COLLECTION,
            {
                "status": "succeeded",
                "completed_at": completed_at,
                "enrichment_id": enrichment_id,
                "last_error": None,
                "lease_id": None,
            },
            {"user_id": user_id, "id": job_id, "lease_id": lease_id},
        )
        return {
            "job_id": job_id,
            "recommendation_id": recommendation_id,
            "status": "succeeded",
            "enrichment_id": enrichment_id,
        }
    except Exception as error:
        logger.error("run_recommendation_ai_enrichment_job failed: %s", error)
        if job_id and recommendation_id:
            quality_failed = isinstance(error, ValueError) and "quality gate" in str(error).lower()
            failed_status = (
                _QUALITY_FAILED_JOB_STATUS
                if quality_failed
                else ("dead" if attempts >= 3 else "failed")
            )
            message = _clean_text(str(error), max_length=500)
            job_filters = {"user_id": user_id, "id": job_id}
            if lease_id:
                job_filters["lease_id"] = lease_id
            await db.update(
                RECOMMENDATION_AI_JOBS_COLLECTION,
                {
                    "status": failed_status,
                    "last_error": message,
                    "completed_at": _utc_now_iso(),
                    "lease_id": None,
                },
                job_filters,
            )
            await db.update(
                RECOMMENDATION_LEDGER_COLLECTION,
                {
                    "ai_enrichment_status": failed_status if quality_failed else "failed",
                    "ai_enrichment_error": message,
                },
                {"user_id": user_id, "id": recommendation_id},
            )
            return {
                "job_id": job_id,
                "recommendation_id": recommendation_id,
                "status": failed_status,
                "error": message,
            }
        raise


async def run_recommendation_ai_enrichment_batch(
    *,
    db: Any,
    user_id: str,
    model: str,
    limit: int = 1,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a small batch of queued enrichment jobs for the current user."""
    try:
        safe_limit = max(1, min(int(limit or 1), 5))
        model_name = _as_string(model)
        if not model_name:
            return {
                "status": "skipped",
                "message": "AI enrichment model is not configured",
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
            }
        if not gemini_api_key:
            return {
                "status": "skipped",
                "message": "GEMINI_API_KEY is not configured",
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
            }

        rows = await db.select(
            RECOMMENDATION_AI_JOBS_COLLECTION,
            filters={"user_id": user_id, "status": "queued"},
        )
        jobs = sorted(
            rows,
            key=lambda row: (
                -_as_int(row.get("priority")),
                _as_string(row.get("queued_at") or row.get("created_at")),
            ),
        )[:safe_limit]

        results: List[Dict[str, Any]] = []
        for job in jobs:
            job_id = _as_string(job.get("id"))
            if not job_id:
                continue
            result = await run_recommendation_ai_enrichment_job(
                db=db,
                user_id=user_id,
                job_id=job_id,
                gemini_api_key=gemini_api_key,
                model=model_name,
            )
            results.append(result)

        succeeded = sum(1 for result in results if result.get("status") == "succeeded")
        failed = sum(
            1
            for result in results
            if result.get("status") in {"failed", "dead", _QUALITY_FAILED_JOB_STATUS}
        )
        worker_skipped = sum(1 for result in results if result.get("status") == "skipped")
        return {
            "status": "completed" if results else "empty",
            "message": None if results else "No queued AI enrichment jobs",
            "processed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": max(0, len(rows) - len(jobs)) + worker_skipped,
            "results": results,
        }
    except Exception as error:
        logger.error("run_recommendation_ai_enrichment_batch failed: %s", error)
        raise


async def drain_recommendation_ai_enrichment_queue(
    *,
    db: Any,
    user_id: str,
    model: str,
    gemini_api_key: Optional[str] = None,
    max_jobs: int = 25,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """Drain queued recommendation AI jobs in bounded batches for one user."""
    try:
        safe_max_jobs = max(1, min(int(max_jobs or 25), 100))
        safe_batch_size = max(1, min(int(batch_size or 3), 10))
        totals: Dict[str, Any] = {
            "status": "completed",
            "message": None,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }

        while totals["processed"] < safe_max_jobs:
            remaining = safe_max_jobs - int(totals["processed"])
            batch_result = await run_recommendation_ai_enrichment_batch(
                db=db,
                user_id=user_id,
                model=model,
                limit=min(safe_batch_size, remaining),
                gemini_api_key=gemini_api_key,
            )
            status = _as_string(batch_result.get("status"), "unknown")
            results = batch_result.get("results") if isinstance(batch_result.get("results"), list) else []
            totals["processed"] += _as_int(batch_result.get("processed"))
            totals["succeeded"] += _as_int(batch_result.get("succeeded"))
            totals["failed"] += _as_int(batch_result.get("failed"))
            totals["skipped"] += _as_int(batch_result.get("skipped"))
            totals["results"].extend(results)

            if status in {"skipped", "empty"}:
                totals["status"] = status if totals["processed"] == 0 else "completed"
                totals["message"] = batch_result.get("message")
                break
            if not results:
                break

        return totals
    except Exception as error:
        logger.error("drain_recommendation_ai_enrichment_queue failed: %s", error)
        raise
