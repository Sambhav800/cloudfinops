"""
Realized savings verification for recommendation ledger records.

The verifier is intentionally conservative: it only marks savings as verified
when the observed cost data supports the claim. Otherwise it keeps collecting
or returns an inconclusive/no-savings status.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from .recommendations import RECOMMENDATION_LEDGER_COLLECTION

logger = logging.getLogger(__name__)

RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION = "recommendation_savings_verifications"
RESOURCE_COST_SNAPSHOT_COLLECTION = "resource_cost_snapshots"

VERIFICATION_FINAL_STATES = {"verified_saved", "verified_no_savings", "inconclusive"}
MIN_POST_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 14
POST_WINDOW_DAYS = 14


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _stable_hash(parts: Iterable[Any]) -> str:
    raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _as_string(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _as_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = _as_string(value)
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _verification_id(recommendation_id: str) -> str:
    return f"ver_{_stable_hash([recommendation_id])}"


def _snapshot_id(
    *,
    user_id: str,
    integration_id: str,
    resource_id: str,
    observed_at: str,
) -> str:
    return f"costsnap_{_stable_hash([user_id, integration_id, resource_id, observed_at])}"


def _resource_identifiers(row: Dict[str, Any]) -> set[str]:
    return {
        _as_string(row.get("resource_id")).lower(),
        _as_string(row.get("cloud_resource_id")).lower(),
    } - {""}


def _row_date(value: Any) -> Optional[datetime]:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed
    text = _as_string(value)
    if not text:
        return None
    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d")
        return parsed_date.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _in_window(row_datetime: Optional[datetime], start: datetime, end: datetime) -> bool:
    if not row_datetime:
        return False
    return start <= row_datetime <= end


def _average_monthly_cost(rows: List[Dict[str, Any]]) -> float:
    values = [_as_float(row.get("cost")) for row in rows if _as_float(row.get("cost")) >= 0]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _daily_monthly_amount(rows: List[Dict[str, Any]], service_key: Optional[str] = None) -> float:
    if not rows:
        return 0.0

    total = 0.0
    usable = 0
    normalized_service = _as_string(service_key).lower()
    for row in rows:
        if normalized_service:
            service_breakdown = row.get("service_breakdown") if isinstance(row.get("service_breakdown"), dict) else {}
            matched_amount = None
            for key, value in service_breakdown.items():
                normalized_key = _as_string(key).lower()
                if normalized_key and (
                    normalized_key == normalized_service
                    or normalized_key in normalized_service
                    or normalized_service in normalized_key
                ):
                    matched_amount = _as_float(value)
                    break
            if matched_amount is None:
                continue
            total += matched_amount
        else:
            total += _as_float(row.get("amount"))
        usable += 1

    if usable == 0:
        return 0.0
    return round((total / usable) * 30, 2)


def _build_verification_record(
    recommendation: Dict[str, Any],
    *,
    now: datetime,
    existing_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    recommendation_id = _as_string(recommendation.get("id"))
    implemented_at = (
        _parse_datetime(recommendation.get("implemented_at"))
        or _parse_datetime(recommendation.get("state_updated_at"))
        or now
    )
    baseline_start = implemented_at - timedelta(days=BASELINE_WINDOW_DAYS)
    baseline_end = implemented_at
    post_start = implemented_at
    post_end = implemented_at + timedelta(days=POST_WINDOW_DAYS)
    existing_status = _as_string((existing_record or {}).get("status"))
    status = existing_status if existing_status in VERIFICATION_FINAL_STATES else "collecting_post_window"

    return {
        "id": _verification_id(recommendation_id),
        "user_id": _as_string(recommendation.get("user_id")),
        "recommendation_id": recommendation_id,
        "integration_id": _as_string(recommendation.get("integration_id")),
        "provider": _as_string(recommendation.get("provider")),
        "resource_id": _as_string(recommendation.get("resource_id")),
        "cloud_resource_id": _as_string(recommendation.get("cloud_resource_id") or recommendation.get("resource_id")),
        "resource_type": _as_string(recommendation.get("resource_type")),
        "action": _as_string(recommendation.get("action")),
        "status": status,
        "estimated_monthly_savings": round(_as_float(
            recommendation.get("claimable_monthly_savings")
            if "claimable_monthly_savings" in recommendation
            else recommendation.get("estimated_monthly_savings")
        ), 2),
        "baseline_window_start": _iso(baseline_start),
        "baseline_window_end": _iso(baseline_end),
        "post_window_start": _iso(post_start),
        "post_window_end": _iso(post_end),
        "baseline_monthly_cost": _as_float((existing_record or {}).get("baseline_monthly_cost")),
        "post_monthly_cost": _as_float((existing_record or {}).get("post_monthly_cost")),
        "realized_monthly_savings": _as_float((existing_record or {}).get("realized_monthly_savings")),
        "realized_savings_confidence": _as_float((existing_record or {}).get("realized_savings_confidence")),
        "measurement_source": _as_string((existing_record or {}).get("measurement_source"), "not_measured"),
        "explanation": _as_string(
            (existing_record or {}).get("explanation"),
            "Waiting for post-implementation cost data.",
        ),
        "created_at": _as_string((existing_record or {}).get("created_at"), _utc_now_iso()),
    }


async def persist_resource_cost_snapshots(
    *,
    db: Any,
    findings: List[Dict[str, Any]],
    user_id: str,
    integration_id: str,
    provider: str,
    observed_at: Optional[str] = None,
) -> int:
    """Persist one scan's resource-level cost observations."""
    try:
        observed = observed_at or _utc_now_iso()
        rows: List[Dict[str, Any]] = []
        for finding in findings:
            resource_id = _as_string(finding.get("cloud_resource_id") or finding.get("resource_id") or finding.get("resource_name"))
            if not resource_id:
                continue
            metadata = finding.get("metadata") if isinstance(finding.get("metadata"), dict) else {}
            rows.append({
                "id": _snapshot_id(
                    user_id=user_id,
                    integration_id=integration_id,
                    resource_id=resource_id,
                    observed_at=observed,
                ),
                "user_id": user_id,
                "integration_id": integration_id,
                "provider": provider,
                "resource_id": resource_id,
                "cloud_resource_id": resource_id,
                "resource_name": _as_string(finding.get("resource_name"), resource_id),
                "service_type": _as_string(finding.get("service_type")),
                "region": _as_string(finding.get("region")),
                "cost": round(_as_float(finding.get("cost")), 4),
                "currency": _as_string(finding.get("currency") or metadata.get("currency"), "USD"),
                "cost_source": _as_string(metadata.get("cost_source"), "unknown"),
                "status": _as_string(finding.get("status"), "Unknown"),
                "observed_at": observed,
            })

        if not rows:
            return 0
        await db.upsert(RESOURCE_COST_SNAPSHOT_COLLECTION, rows)
        return len(rows)
    except Exception as error:
        logger.error("persist_resource_cost_snapshots failed: %s", error)
        raise


async def create_or_update_savings_verification(
    *,
    db: Any,
    user_id: str,
    recommendation: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Create or refresh the verification shell for an implemented recommendation."""
    try:
        current_time = now or _utc_now()
        recommendation_id = _as_string(recommendation.get("id"))
        existing = await db.select(
            RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION,
            filters={"user_id": user_id, "recommendation_id": recommendation_id},
        )
        record = _build_verification_record(
            recommendation,
            now=current_time,
            existing_record=existing[0] if existing else None,
        )
        upserted = await db.upsert(RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION, record)
        verification = upserted[0] if upserted else record
        await db.update(
            RECOMMENDATION_LEDGER_COLLECTION,
            {
                "verification_status": verification["status"],
                "verification_id": verification["id"],
                "implemented_at": _as_string(recommendation.get("implemented_at") or recommendation.get("state_updated_at"), _iso(current_time)),
            },
            {"user_id": user_id, "id": recommendation_id},
        )
        return verification
    except Exception as error:
        logger.error("create_or_update_savings_verification failed: %s", error)
        raise


async def get_savings_verification(
    *,
    db: Any,
    user_id: str,
    recommendation_id: str,
) -> Optional[Dict[str, Any]]:
    """Load an existing savings verification row for one recommendation."""
    try:
        rows = await db.select(
            RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION,
            filters={"user_id": user_id, "recommendation_id": recommendation_id},
        )
        return rows[0] if rows else None
    except Exception as error:
        logger.error("get_savings_verification failed: %s", error)
        raise


def _resource_snapshot_measurement(
    *,
    snapshots: List[Dict[str, Any]],
    recommendation: Dict[str, Any],
    baseline_start: datetime,
    baseline_end: datetime,
    post_start: datetime,
    post_end: datetime,
) -> Optional[Dict[str, Any]]:
    identifiers = _resource_identifiers(recommendation)
    matching = [
        row
        for row in snapshots
        if _resource_identifiers(row) & identifiers
    ]
    baseline_rows = [
        row for row in matching
        if _in_window(_row_date(row.get("observed_at")), baseline_start, baseline_end)
    ]
    post_rows = [
        row for row in matching
        if _in_window(_row_date(row.get("observed_at")), post_start, post_end)
    ]
    if not baseline_rows or not post_rows:
        return None

    return {
        "baseline": _average_monthly_cost(baseline_rows),
        "post": _average_monthly_cost(post_rows),
        "source": "resource_snapshot",
        "confidence": 92,
    }


def _daily_spend_measurement(
    *,
    daily_rows: List[Dict[str, Any]],
    recommendation: Dict[str, Any],
    baseline_start: datetime,
    baseline_end: datetime,
    post_start: datetime,
    post_end: datetime,
) -> Optional[Dict[str, Any]]:
    baseline_rows = [
        row for row in daily_rows
        if _in_window(_row_date(row.get("spend_date")), baseline_start, baseline_end)
    ]
    post_rows = [
        row for row in daily_rows
        if _in_window(_row_date(row.get("spend_date")), post_start, post_end)
    ]
    if len(baseline_rows) < 3 or len(post_rows) < 3:
        return None

    service_key = _as_string(recommendation.get("resource_type"))
    service_baseline = _daily_monthly_amount(baseline_rows, service_key=service_key)
    service_post = _daily_monthly_amount(post_rows, service_key=service_key)
    if service_baseline > 0:
        return {
            "baseline": service_baseline,
            "post": service_post,
            "source": "service_daily_spend",
            "confidence": 74,
        }

    return {
        "baseline": _daily_monthly_amount(baseline_rows),
        "post": _daily_monthly_amount(post_rows),
        "source": "integration_daily_spend",
        "confidence": 58,
    }


def _verification_result(
    *,
    verification: Dict[str, Any],
    measurement: Optional[Dict[str, Any]],
    now: datetime,
) -> Dict[str, Any]:
    post_start = _parse_datetime(verification.get("post_window_start")) or now
    post_min_ready = post_start + timedelta(days=MIN_POST_WINDOW_DAYS)
    if now < post_min_ready:
        return {
            **verification,
            "status": "collecting_post_window",
            "measurement_source": "not_measured",
            "explanation": "Waiting for at least 7 days of post-implementation cost data.",
        }

    if not measurement:
        return {
            **verification,
            "status": "inconclusive",
            "measurement_source": "not_measured",
            "realized_savings_confidence": 0,
            "explanation": "No reliable before/after cost data was available for this recommendation.",
        }

    baseline = round(_as_float(measurement.get("baseline")), 2)
    post = round(_as_float(measurement.get("post")), 2)
    realized = round(max(0.0, baseline - post), 2)
    estimated = _as_float(verification.get("estimated_monthly_savings"))
    minimum_savings = max(1.0, estimated * 0.1)
    status = "verified_saved" if realized >= minimum_savings else "verified_no_savings"
    explanation = (
        f"Measured monthly cost moved from {baseline:.2f} to {post:.2f}; "
        f"realized monthly savings is {realized:.2f}."
    )

    return {
        **verification,
        "status": status,
        "baseline_monthly_cost": baseline,
        "post_monthly_cost": post,
        "realized_monthly_savings": realized,
        "realized_savings_confidence": _as_float(measurement.get("confidence")),
        "measurement_source": _as_string(measurement.get("source"), "unknown"),
        "explanation": explanation,
    }


async def verify_recommendation_savings(
    *,
    db: Any,
    user_id: str,
    recommendation_id: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Measure whether an implemented recommendation actually reduced spend."""
    try:
        current_time = now or _utc_now()
        recommendation_rows = await db.select(
            RECOMMENDATION_LEDGER_COLLECTION,
            filters={"user_id": user_id, "id": recommendation_id},
        )
        if not recommendation_rows:
            raise ValueError("Recommendation not found")

        recommendation = recommendation_rows[0]
        verification = await get_savings_verification(
            db=db,
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        if not verification:
            verification = await create_or_update_savings_verification(
                db=db,
                user_id=user_id,
                recommendation=recommendation,
                now=current_time,
            )

        baseline_start = _parse_datetime(verification.get("baseline_window_start")) or current_time
        baseline_end = _parse_datetime(verification.get("baseline_window_end")) or current_time
        post_start = _parse_datetime(verification.get("post_window_start")) or current_time
        post_end = _parse_datetime(verification.get("post_window_end")) or current_time

        snapshots = await db.select(
            RESOURCE_COST_SNAPSHOT_COLLECTION,
            filters={
                "user_id": user_id,
                "integration_id": _as_string(recommendation.get("integration_id")),
            },
        )
        measurement = _resource_snapshot_measurement(
            snapshots=snapshots,
            recommendation=recommendation,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            post_start=post_start,
            post_end=post_end,
        )

        if not measurement:
            daily_rows = await db.select(
                "daily_spend_history",
                filters={
                    "user_id": user_id,
                    "integration_id": _as_string(recommendation.get("integration_id")),
                },
            )
            measurement = _daily_spend_measurement(
                daily_rows=daily_rows,
                recommendation=recommendation,
                baseline_start=baseline_start,
                baseline_end=baseline_end,
                post_start=post_start,
                post_end=post_end,
            )

        result = _verification_result(
            verification=verification,
            measurement=measurement,
            now=current_time,
        )
        result["updated_at"] = _iso(current_time)
        upserted = await db.upsert(RECOMMENDATION_SAVINGS_VERIFICATION_COLLECTION, result)
        saved = upserted[0] if upserted else result

        ledger_update = {
            "verification_status": saved["status"],
            "verification_id": saved["id"],
            "realized_monthly_savings": _as_float(saved.get("realized_monthly_savings")),
            "realized_savings_confidence": _as_float(saved.get("realized_savings_confidence")),
        }
        if saved["status"] == "verified_saved":
            ledger_update["state"] = "verified_saved"
        elif saved["status"] == "verified_no_savings":
            ledger_update["state"] = "verified_no_savings"
        await db.update(
            RECOMMENDATION_LEDGER_COLLECTION,
            ledger_update,
            {"user_id": user_id, "id": recommendation_id},
        )
        return saved
    except Exception as error:
        logger.error("verify_recommendation_savings failed: %s", error)
        raise


async def verify_implemented_recommendations_for_integration(
    *,
    db: Any,
    user_id: str,
    integration_id: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Best-effort sweep for implemented recommendations after a scan."""
    try:
        rows = await db.select(
            RECOMMENDATION_LEDGER_COLLECTION,
            filters={"user_id": user_id, "integration_id": integration_id},
        )
        candidates = [
            row
            for row in rows
            if _as_string(row.get("state")).lower() in {"implemented", "verifying"}
        ]

        summary = {
            "checked": 0,
            "verified_saved": 0,
            "verified_no_savings": 0,
            "collecting_post_window": 0,
            "inconclusive": 0,
            "failed": 0,
        }
        for recommendation in candidates:
            recommendation_id = _as_string(recommendation.get("id"))
            if not recommendation_id:
                continue
            try:
                result = await verify_recommendation_savings(
                    db=db,
                    user_id=user_id,
                    recommendation_id=recommendation_id,
                    now=now,
                )
                summary["checked"] += 1
                status = _as_string(result.get("status")).lower()
                if status in summary and status != "checked":
                    summary[status] += 1
            except Exception as error:
                summary["failed"] += 1
                logger.warning(
                    "Savings verification sweep skipped recommendation %s: %s",
                    recommendation_id,
                    error,
                )

        return summary
    except Exception as error:
        logger.error("verify_implemented_recommendations_for_integration failed: %s", error)
        raise
