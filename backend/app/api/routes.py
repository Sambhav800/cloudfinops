"""
API Routes for the CloudFinOps Python backend.
Handles scan triggers, resource fetching, and AI analysis.
"""

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form, Request
from fastapi.responses import Response
from typing import Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta

from ..auth import get_current_user, ClerkUser
from ..auth.user_profile import resolve_user_email, resolve_user_full_name
from ..db import get_db_client, MongoDBClient
from ..core.retry import (
    build_aws_retry_config,
    call_with_backoff,
    is_aws_retryable,
    is_azure_retryable,
    is_gcp_retryable,
)
from ..security import decrypt_integration_credentials
from ..scanners import AWSScanner
from .websocket import send_scan_progress, send_scan_complete, get_scan_progress
from ..ai.analyzer import AIAnalyzer
from ..core.cache import cache_response
from ..core.audit import log_audit_event
from ..core.finance import aggregate_daily_spend_rows, redact_integration_settings_for_audit
from ..core.provider_pricing_catalog import pricing_catalog
from ..core.community_pricing_pool import (
    apply_community_estimates,
    contribute_verified_prices,
)
from ..core.bill_storage import (
    RawBillStorageError,
    RawBillStorageNotFound,
    archive_uploaded_bill_to_gcs,
    download_archived_bill_from_gcs,
)
import logging
import sys

# Fix Windows terminal encoding crash (UnicodeEncodeError on emoji chars)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["CloudFinOps"])
_BILL_PARSE_TIMEOUT_SECONDS = 120.0
_MAX_BILL_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


async def _apply_catalog_estimates_for_scan(
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
) -> dict[str, Any]:
    """Apply provider catalog estimates after resource writeback without failing the scan."""
    try:
        result = await pricing_catalog.apply_catalog_estimates(
            db,
            user_id,
            integration_id=integration_id,
            limit=500,
        )
        logger.info(
            "Applied catalog estimates after scan integration=%s updated=%s unmatched=%s",
            integration_id,
            result.get("updated", 0),
            result.get("unmatched", 0),
        )
        return result
    except Exception as error:
        logger.warning(
            "Catalog estimate application skipped after scan integration=%s: %s",
            integration_id,
            error,
        )
        return {"updated": 0, "skipped_actual": 0, "unmatched": 0, "processed": 0, "samples": []}


async def _contribute_community_prices_for_scan(
    db: MongoDBClient,
    user_id: str,
    resources: list[dict[str, Any]],
) -> None:
    """Contribute verified prices from resources with actual billing data to the community pool."""
    try:
        await contribute_verified_prices(db, user_id, resources)
    except Exception as error:
        logger.debug("Community price contribution skipped: %s", error)


async def _apply_community_estimates_for_scan(
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
) -> dict[str, Any]:
    """Apply community-verified prices to resources still at $0 after catalog estimates."""
    try:
        result = await apply_community_estimates(db, user_id, integration_id, limit=500)
        if result.get("updated", 0) > 0:
            logger.info(
                "Applied community estimates integration=%s updated=%s",
                integration_id,
                result.get("updated", 0),
            )
        return result
    except Exception as error:
        logger.debug("Community estimate application skipped: %s", error)
        return {"updated": 0, "unmatched": 0}


# --- Request/Response Models ---

class ScanRequest(BaseModel):
    """Request to trigger a resource scan."""
    integration_id: str


class ScanResponse(BaseModel):
    """Response from a scan operation."""
    success: bool
    message: str
    task_id: Optional[str] = None


class ResourceResponse(BaseModel):
    """Response containing resources."""
    resources: List[dict]
    count: int


class StatsResponse(BaseModel):
    """Dashboard statistics response."""
    total_spend: float
    potential_savings: float
    active_resources_count: int
    ai_confidence_score: int
    carbon_footprint_kg: float
    cost_of_inaction_6mo: float


class IntegrationResponse(BaseModel):
    """Cloud integration response."""
    id: str
    provider: str
    name: str
    status: str
    last_scan: Optional[str]
    regions: List[str]
    created_at: Optional[str] = None
    account_identifier: Optional[str] = None
    monthly_budget_limit: Optional[float] = None
    alert_phone_number_masked: Optional[str] = None
    alert_slack_webhook_configured: bool = False


class UserSyncRequest(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    last_login: Optional[str] = None


_INVALID_USER_SYNC_VALUES = frozenset({"null", "none", "undefined"})


def _clean_user_sync_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned or cleaned.casefold() in _INVALID_USER_SYNC_VALUES:
        return None
    return cleaned


def _split_synced_full_name(full_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    cleaned = _clean_user_sync_value(full_name)
    if not cleaned:
        return None, None

    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:]).strip() or None


def _compose_full_name(first_name: Optional[str], last_name: Optional[str]) -> Optional[str]:
    parts = [part for part in [first_name, last_name] if part]
    if not parts:
        return None
    return " ".join(parts)


def _build_synced_user_record(
    *,
    existing_user: Optional[dict],
    payload: UserSyncRequest,
    auth_user: ClerkUser,
    now_iso: str,
) -> dict[str, Any]:
    existing_user = existing_user or {}

    payload_email = _clean_user_sync_value(payload.email)
    auth_email = _clean_user_sync_value(resolve_user_email(auth_user))
    existing_email = _clean_user_sync_value(existing_user.get("email"))
    email = payload_email or auth_email or existing_email

    payload_first_name = _clean_user_sync_value(payload.first_name)
    auth_first_name = _clean_user_sync_value(auth_user.first_name)
    existing_first_name = _clean_user_sync_value(existing_user.get("first_name"))

    payload_last_name = _clean_user_sync_value(payload.last_name)
    auth_last_name = _clean_user_sync_value(auth_user.last_name)
    existing_last_name = _clean_user_sync_value(existing_user.get("last_name"))

    payload_full_name = _clean_user_sync_value(payload.full_name)
    auth_full_name = _clean_user_sync_value(resolve_user_full_name(auth_user))
    existing_full_name = _clean_user_sync_value(existing_user.get("full_name"))

    payload_split_first, payload_split_last = _split_synced_full_name(payload_full_name)
    auth_split_first, auth_split_last = _split_synced_full_name(auth_full_name)
    existing_split_first, existing_split_last = _split_synced_full_name(existing_full_name)

    first_name = (
        payload_first_name
        or auth_first_name
        or existing_first_name
        or payload_split_first
        or auth_split_first
        or existing_split_first
    )
    last_name = (
        payload_last_name
        or auth_last_name
        or existing_last_name
        or payload_split_last
        or auth_split_last
        or existing_split_last
    )
    full_name = (
        payload_full_name
        or _compose_full_name(first_name, last_name)
        or auth_full_name
        or existing_full_name
    )

    avatar_url = _clean_user_sync_value(payload.avatar_url) or _clean_user_sync_value(existing_user.get("avatar_url"))
    last_login = _clean_user_sync_value(payload.last_login) or now_iso

    record: dict[str, Any] = {
        "id": auth_user.id,
        "last_login": last_login,
        "updated_at": now_iso,
    }
    if email:
        record["email"] = email
        record["email_lower"] = email.casefold()
    if first_name:
        record["first_name"] = first_name
    if last_name:
        record["last_name"] = last_name
    if full_name:
        record["full_name"] = full_name
    if avatar_url:
        record["avatar_url"] = avatar_url
    return record


class BillAnalysisOpportunityResponse(BaseModel):
    category: str
    current_cloud: str
    current_cost: float
    recommended_cloud: str
    recommended_cost: float
    savings: float
    savings_pct: float
    reasoning: Optional[str] = None
    migration_risk: Optional[str] = None
    migration_note: Optional[str] = None
    all_cloud_costs: dict[str, float] = Field(default_factory=dict)


class BillExecutiveFindingActionResponse(BaseModel):
    name: str
    difficulty: str
    time_required: str
    monthly_saving_min: float
    monthly_saving_max: float
    risk: str
    savings_source: Optional[str] = None
    validation_required: bool = False
    calculation: Optional[str] = None
    evidence_lines: list[str] = Field(default_factory=list)
    confidence_reason: Optional[str] = None


class BillExecutiveFindingResponse(BaseModel):
    rank: int
    service: str
    monthly_cost: float
    pct_of_bill: float
    severity: str
    title: str
    what_we_found: str
    why_inefficient: Optional[str] = None
    how_to_fix: list[str] = Field(default_factory=list)
    actions: list[BillExecutiveFindingActionResponse] = Field(default_factory=list)
    savings_source: Optional[str] = None
    validation_required: bool = False
    calculation: Optional[str] = None
    evidence_lines: list[str] = Field(default_factory=list)
    confidence_reason: Optional[str] = None
    keep: bool = False


class BillExecutiveQuickWinResponse(BaseModel):
    action: str
    time: str
    saving: float
    risk: str


class BillExecutiveRoadmapPhaseResponse(BaseModel):
    phase: str
    timeframe: str
    actions: list[str] = Field(default_factory=list)
    expected_saving_min: float
    expected_saving_max: float


class BillExecutiveCrossCloudComparisonResponse(BaseModel):
    service: str
    aws_current: Optional[float] = None
    aws_optimised: Optional[float] = None
    gcp: Optional[float] = None
    azure: Optional[float] = None


class BillExecutiveClientScriptsResponse(BaseModel):
    opening: str
    explain_biggest_issue: str
    handle_objection: str
    closing: str


class BillExecutiveReportResponse(BaseModel):
    headline: str
    waste_grade: str
    waste_score: int
    waste_grade_explanation: str
    total_spend: float
    existing_savings_active: float
    additional_savings_min: float
    additional_savings_max: float
    optimised_bill_min: float
    optimised_bill_max: float
    annual_savings_min: float
    annual_savings_max: float
    reduction_pct_min: int
    reduction_pct_max: int
    findings: list[BillExecutiveFindingResponse] = Field(default_factory=list)
    quick_wins: list[BillExecutiveQuickWinResponse] = Field(default_factory=list)
    roadmap: list[BillExecutiveRoadmapPhaseResponse] = Field(default_factory=list)
    cross_cloud_comparison: list[BillExecutiveCrossCloudComparisonResponse] = Field(default_factory=list)
    executive_summary: str
    client_scripts: BillExecutiveClientScriptsResponse
    implementation_timeline_days: int
    confidence: str
    benchmark_context: str
    analysis_source: str = "unknown"
    verification_status: str = "unknown"


class BillAnalysisRecordResponse(BaseModel):
    id: str
    analysis_id: Optional[str] = None
    status: str = "success"
    source_type: str = "manual_upload"
    filename: str
    provider: str
    provider_detected: str
    source_format: str
    source_parser: str
    rows_parsed: int
    total_analyzed_spend: float
    total_potential_savings: float
    currency: str
    spend_by_category: dict[str, float] = Field(default_factory=dict)
    top_services: list[dict[str, Any]] = Field(default_factory=list)
    discounts_applied: dict[str, str] = Field(default_factory=dict)
    arbitrage_opportunities: list[BillAnalysisOpportunityResponse] = Field(default_factory=list)
    executive_report: Optional[BillExecutiveReportResponse] = None
    cloudfront_insights: Optional[dict[str, Any]] = None
    gpu_insights: Optional[dict[str, Any]] = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    top_categories: list[str] = Field(default_factory=list)
    created_at: str


class BillAnalysesListResponse(BaseModel):
    analyses: list[BillAnalysisRecordResponse] = Field(default_factory=list)
    count: int


class UserFeatureResponse(BaseModel):
    feature: str
    enabled: bool = True
    last_used: Optional[str] = None
    first_upload_at: Optional[str] = None


class UserFeaturesResponse(BaseModel):
    features: list[str] = Field(default_factory=list)
    feature_details: dict[str, UserFeatureResponse] = Field(default_factory=dict)


class NotificationMutationResponse(BaseModel):
    success: bool
    message: str


_LEGACY_BAD_BILL_SERVICE_PREFIXES = (
    "service provider total in usd",
    "estimated grand total",
    "grand total",
    "total pre-tax",
    "region name",
    "highest aws region spend",
    "highest service spend",
)

_BILL_ANALYSIS_REPORT_CONTRACT_VERSION = "2026-04-28-bill-line-rule-estimate-v5"


def _compact_bill_analysis_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _bill_analysis_money(value: Any, fallback: float = 0.0) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = fallback
    return round(amount, 2)


def _persistable_bill_services(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "service": str(item.get("service") or "Unknown"),
            "cost": round(float(item.get("cost") or 0), 2),
            **(
                {"category": str(item.get("category"))}
                if item.get("category") is not None
                else {}
            ),
            **({"page": int(item.get("page") or 0)} if item.get("page") is not None else {}),
            **({"line_number": int(item.get("line_number") or 0)} if item.get("line_number") is not None else {}),
            **({"line_type": str(item.get("line_type"))} if item.get("line_type") is not None else {}),
            **({"source_line": str(item.get("source_line"))} if item.get("source_line") is not None else {}),
        }
        for item in (parsed.get("raw_services") or [])
        if isinstance(item, dict)
    ]


def _is_legacy_invalid_bill_analysis(record: dict[str, Any]) -> bool:
    if str(record.get("source_format") or "").strip().lower() != "pdf":
        return False
    if str(record.get("source_parser") or "").strip() != "pdf_invoice_parser":
        return False

    source_metadata = record.get("source_metadata") if isinstance(record.get("source_metadata"), dict) else {}
    if str(source_metadata.get("pdf_parser_version") or "").strip() == "2026-03-22-rollup-fix":
        return False

    top_services = record.get("top_services") if isinstance(record.get("top_services"), list) else []
    has_summary_top_service = any(
        any(
            _compact_bill_analysis_label(str(item.get("service") or "")).startswith(
                _compact_bill_analysis_label(prefix)
            )
            for prefix in _LEGACY_BAD_BILL_SERVICE_PREFIXES
        )
        for item in top_services[:8]
        if isinstance(item, dict)
    )

    categories = record.get("spend_by_category") if isinstance(record.get("spend_by_category"), dict) else {}
    other_spend = float(categories.get("Other") or 0)
    total_spend = float(record.get("total_analyzed_spend") or 0)
    rows_parsed = int(record.get("rows_parsed") or 0)

    return has_summary_top_service or (
        rows_parsed > 500
        and total_spend > 5000
        and other_spend > 1000
        and (other_spend / total_spend) > 0.7
    )


def _filter_valid_bill_analyses(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not _is_legacy_invalid_bill_analysis(record)]


def _masked_account_identifier(integration: dict) -> str | None:
    provider = str(integration.get("provider") or "").lower()

    try:
        credentials = decrypt_integration_credentials(integration)
    except Exception:
        credentials = {}

    if provider == "aws":
        access_key_id = str(credentials.get("access_key_id") or "").strip()
        if access_key_id:
            return f"...{access_key_id[-4:]}"
        if integration.get("encrypted_role_arn"):
            return "IAM Role"
        return None

    if provider == "azure":
        subscription_id = str(credentials.get("subscription_id") or "").strip()
        if subscription_id:
            return f"...{subscription_id[-4:]}"
        return "Service Principal"

    if provider == "gcp":
        project_id = str(credentials.get("project_id") or "").strip()
        if project_id:
            return project_id
        return "Service Account"

    return None


def _masked_alert_phone_number(value: Optional[str]) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 4:
        return None
    return f"***{digits[-4:]}"


def _build_bill_analysis_record(
    *,
    filename: str,
    parsed: dict[str, Any],
    opportunities: list[dict[str, Any]],
    total_savings: float,
    aws_discount_pct: float,
    gcp_discount_pct: float,
    azure_discount_pct: float,
    user_id: str,
    executive_report: dict[str, Any] | None = None,
    content_hash: str | None = None,
    raw_file_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = str(parsed.get("provider") or "generic").strip().lower() or "generic"
    source_format = str(parsed.get("source_format") or "").strip().lower()
    source_parser = str(parsed.get("source_parser") or "").strip() or "unknown"
    source_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
    existing_credits_and_savings = _bill_analysis_money(
        parsed.get("existing_credits_and_savings"),
        _bill_analysis_money(source_metadata.get("existing_credits_and_savings")),
    )

    return {
        "user_id": user_id,
        "status": "success",
        "source_type": "manual_upload",
        "filename": filename,
        "provider": provider,
        "provider_detected": provider.upper(),
        "source_format": source_format,
        "source_parser": source_parser,
        "rows_parsed": int(parsed.get("rows_parsed") or 0),
        "total_analyzed_spend": round(float(parsed.get("total_spend") or 0), 2),
        "total_potential_savings": round(float(total_savings or 0), 2),
        "currency": str(parsed.get("currency") or "USD").upper(),
        "existing_credits_and_savings": existing_credits_and_savings,
        "savings_amount": existing_credits_and_savings,
        "spend_by_category": {
            str(category): round(float(amount or 0), 2)
            for category, amount in (parsed.get("by_category") or {}).items()
        },
        "top_services": _persistable_bill_services(parsed),
        "discounts_applied": {
            "AWS": f"{aws_discount_pct}%",
            "GCP": f"{gcp_discount_pct}%",
            "Azure": f"{azure_discount_pct}%",
        },
        "arbitrage_opportunities": opportunities,
        "executive_report": executive_report,
        "cloudfront_insights": parsed.get("cloudfront_insights"),
        "gpu_insights": parsed.get("gpu_insights"),
        "source_metadata": {
            **source_metadata,
            "existing_credits_and_savings": existing_credits_and_savings,
            "cloudfront_detected": bool(parsed.get("cloudfront_insights")),
            "gpu_analysis_available": bool(parsed.get("gpu_insights")),
            "opportunity_count": len(opportunities),
            "report_contract_version": _BILL_ANALYSIS_REPORT_CONTRACT_VERSION,
            **({"content_hash": content_hash} if content_hash else {}),
            **({"raw_bill_file": raw_file_metadata} if isinstance(raw_file_metadata, dict) else {}),
        },
    }


def _analysis_record_to_parsed_bill(record: dict[str, Any]) -> dict[str, Any]:
    source_metadata = record.get("source_metadata") if isinstance(record.get("source_metadata"), dict) else {}
    existing_credits_and_savings = _bill_analysis_money(
        record.get("existing_credits_and_savings"),
        _bill_analysis_money(
            source_metadata.get("existing_credits_and_savings"),
            _bill_analysis_money(record.get("savings_amount")),
        ),
    )
    return {
        "provider": record.get("provider") or record.get("provider_detected"),
        "total_spend": record.get("total_analyzed_spend"),
        "currency": record.get("currency"),
        "by_category": record.get("spend_by_category") if isinstance(record.get("spend_by_category"), dict) else {},
        "raw_services": record.get("top_services") if isinstance(record.get("top_services"), list) else [],
        "source_format": record.get("source_format"),
        "source_parser": record.get("source_parser"),
        "source_metadata": source_metadata,
        "rows_parsed": record.get("rows_parsed"),
        "existing_credits_and_savings": existing_credits_and_savings,
        "savings_amount": existing_credits_and_savings,
    }


def _bill_analysis_extraction_quality(payload: dict[str, Any], *, persisted: bool) -> int:
    source_metadata = payload.get("source_metadata") if isinstance(payload.get("source_metadata"), dict) else {}
    values: list[int] = []

    for key in ("rows_parsed",):
        try:
            values.append(int(payload.get(key) or 0))
        except (TypeError, ValueError):
            continue

    for key in ("line_items_detected", "service_rows_detected", "top_services_count"):
        try:
            values.append(int(source_metadata.get(key) or 0))
        except (TypeError, ValueError):
            continue

    gemini_metadata = (
        source_metadata.get("gemini_direct_file")
        if isinstance(source_metadata.get("gemini_direct_file"), dict)
        else {}
    )
    try:
        values.append(int(gemini_metadata.get("service_rows_detected") or 0))
    except (TypeError, ValueError):
        pass

    services_key = "top_services" if persisted else "raw_services"
    services = payload.get(services_key)
    if isinstance(services, list):
        values.append(len(services))

    return max(values or [0])


async def _decorate_bill_analysis_response(record: dict[str, Any]) -> dict[str, Any]:
    spend_by_category = record.get("spend_by_category")
    top_categories = (
        [str(key) for key in spend_by_category.keys()][:3]
        if isinstance(spend_by_category, dict)
        else []
    )

    # Trust the executive_report as-is — _ensure_bill_analysis_executive_report
    # already normalized/cached it before this function is called.
    executive_report = record.get("executive_report") if isinstance(record.get("executive_report"), dict) else None

    return {
        **record,
        "analysis_id": str(record.get("id") or ""),
        "executive_report": executive_report,
        "top_categories": top_categories,
    }


def _has_renderable_executive_report(report: Any) -> bool:
    if not isinstance(report, dict):
        return False

    return (
        bool(str(report.get("headline") or "").strip())
        and isinstance(report.get("findings"), list)
        and isinstance(report.get("quick_wins"), list)
        and isinstance(report.get("roadmap"), list)
        and isinstance(report.get("cross_cloud_comparison"), list)
        and isinstance(report.get("client_scripts"), dict)
        and str(report.get("verification_status") or "").strip()
        in {"source_grounded_unverified_savings", "bill_line_rule_estimate", "ai_enriched_source_grounded", "estimated"}
    )


async def _reparse_archived_bill_for_report(
    record: dict[str, Any],
    source_metadata: dict[str, Any],
    existing_credits_and_savings: float,
) -> dict[str, Any] | None:
    raw_file_metadata = (
        source_metadata.get("raw_bill_file")
        if isinstance(source_metadata.get("raw_bill_file"), dict)
        else None
    )
    if str((raw_file_metadata or {}).get("status") or "").strip().lower() != "stored":
        return None

    try:
        content, media_type, archived_filename = await download_archived_bill_from_gcs(raw_file_metadata)
    except (RawBillStorageError, RawBillStorageNotFound) as error:
        logger.warning(
            "Could not reparse archived bill for analysis %s: %s",
            record.get("id"),
            error,
        )
        return None

    filename = str(record.get("filename") or archived_filename or "bill.pdf")
    try:
        from ..bill_parser import enrich_parsed_bill_with_gemini, parse_bill

        parsed = await asyncio.wait_for(
            asyncio.to_thread(parse_bill, content, filename),
            timeout=_BILL_PARSE_TIMEOUT_SECONDS,
        )
        try:
            parsed = await enrich_parsed_bill_with_gemini(
                parsed,
                content,
                filename,
                content_type=media_type,
            )
        except Exception as error:
            logger.warning(
                "Gemini archived-bill enrichment skipped for analysis %s: %s",
                record.get("id"),
                error,
            )
    except asyncio.TimeoutError:
        logger.warning("Archived bill reparse timed out for analysis %s", record.get("id"))
        return None
    except Exception as error:
        logger.warning("Archived bill reparse failed for analysis %s: %s", record.get("id"), error)
        return None

    parsed_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
    parsed["source_metadata"] = {
        **parsed_metadata,
        "existing_credits_and_savings": existing_credits_and_savings,
        **({"content_hash": source_metadata.get("content_hash")} if source_metadata.get("content_hash") else {}),
        "raw_bill_file": raw_file_metadata,
    }
    parsed["existing_credits_and_savings"] = existing_credits_and_savings
    parsed["savings_amount"] = existing_credits_and_savings
    return parsed


async def _ensure_bill_analysis_executive_report(
    record: dict[str, Any],
    db: MongoDBClient,
) -> dict[str, Any]:
    from ..bill_parser import normalize_full_intelligence_report

    source_metadata = record.get("source_metadata") if isinstance(record.get("source_metadata"), dict) else {}
    existing_credits_and_savings = _bill_analysis_money(
        record.get("existing_credits_and_savings"),
        _bill_analysis_money(
            source_metadata.get("existing_credits_and_savings"),
            _bill_analysis_money(record.get("savings_amount")),
        ),
    )

    # Fast path: if the report is already renderable and contract version matches,
    # skip normalization entirely (avoids re-running async _build_findings on every read).
    raw_report = record.get("executive_report")
    contract_version = source_metadata.get("report_contract_version")
    needs_contract_fix = (
        record.get("existing_credits_and_savings") != existing_credits_and_savings
        or record.get("savings_amount") != existing_credits_and_savings
        or contract_version != _BILL_ANALYSIS_REPORT_CONTRACT_VERSION
        or source_metadata.get("existing_credits_and_savings") != existing_credits_and_savings
    )

    if _has_renderable_executive_report(raw_report) and not needs_contract_fix:
        return {**record, "executive_report": raw_report}

    # Slow path: normalize/repair the report.
    patched_source_metadata = {
        **source_metadata,
        "existing_credits_and_savings": existing_credits_and_savings,
        "report_contract_version": _BILL_ANALYSIS_REPORT_CONTRACT_VERSION,
    }
    patched_record = {
        **record,
        "existing_credits_and_savings": existing_credits_and_savings,
        "savings_amount": existing_credits_and_savings,
        "source_metadata": patched_source_metadata,
    }

    parsed_for_report = _analysis_record_to_parsed_bill(patched_record)
    field_updates: dict[str, Any] = {}
    if str(record.get("source_format") or "").strip().lower() == "pdf" and needs_contract_fix:
        reparsed = await _reparse_archived_bill_for_report(
            record,
            patched_source_metadata,
            existing_credits_and_savings,
        )
        if isinstance(reparsed, dict):
            reparsed_metadata = (
                reparsed.get("source_metadata")
                if isinstance(reparsed.get("source_metadata"), dict)
                else {}
            )
            patched_source_metadata = {
                **reparsed_metadata,
                "existing_credits_and_savings": existing_credits_and_savings,
                "report_contract_version": _BILL_ANALYSIS_REPORT_CONTRACT_VERSION,
            }
            field_updates = {
                "provider": str(reparsed.get("provider") or record.get("provider") or "generic").lower(),
                "provider_detected": str(reparsed.get("provider") or record.get("provider_detected") or "generic").upper(),
                "source_format": str(reparsed.get("source_format") or record.get("source_format") or "pdf").lower(),
                "source_parser": str(reparsed.get("source_parser") or record.get("source_parser") or "unknown"),
                "rows_parsed": int(reparsed.get("rows_parsed") or record.get("rows_parsed") or 0),
                "total_analyzed_spend": _bill_analysis_money(
                    reparsed.get("total_spend"),
                    _bill_analysis_money(record.get("total_analyzed_spend")),
                ),
                "currency": str(reparsed.get("currency") or record.get("currency") or "USD").upper(),
                "spend_by_category": {
                    str(category): _bill_analysis_money(amount)
                    for category, amount in (reparsed.get("by_category") or {}).items()
                },
                "top_services": _persistable_bill_services(reparsed),
            }
            parsed_for_report = reparsed
            patched_record = {
                **patched_record,
                **field_updates,
                "source_metadata": patched_source_metadata,
            }

    normalized_report = await normalize_full_intelligence_report(
        raw_report if isinstance(raw_report, dict) else None,
        parsed_for_report,
        patched_record.get("arbitrage_opportunities") if isinstance(patched_record.get("arbitrage_opportunities"), list) else [],
    )
    report_verification_status = str(normalized_report.get("verification_status") or "").strip()
    normalized_total_savings = _bill_analysis_money(patched_record.get("total_potential_savings"))
    if report_verification_status == "bill_line_rule_estimate":
        normalized_total_savings = max(
            normalized_total_savings,
            _bill_analysis_money(normalized_report.get("additional_savings_max")),
        )
    elif report_verification_status == "source_grounded_unverified_savings":
        normalized_total_savings = 0.0
    needs_total_savings_fix = _bill_analysis_money(record.get("total_potential_savings")) != normalized_total_savings
    needs_report_write = not _has_renderable_executive_report(raw_report) or raw_report != normalized_report

    if not needs_report_write and not needs_contract_fix and not needs_total_savings_fix:
        return {**patched_record, "executive_report": normalized_report}

    patched_record = {
        **patched_record,
        "executive_report": normalized_report,
        "total_potential_savings": normalized_total_savings,
    }
    try:
        await db.update(
            "bill_analyses",
            {
                **field_updates,
                "executive_report": normalized_report,
                "total_potential_savings": normalized_total_savings,
                "existing_credits_and_savings": existing_credits_and_savings,
                "savings_amount": existing_credits_and_savings,
                "source_metadata": patched_source_metadata,
            },
            {"id": str(record.get("id") or ""), "user_id": str(record.get("user_id") or "")},
        )
    except Exception as error:
        logger.warning(
            "Failed to persist normalized executive report for bill analysis %s: %s",
            record.get("id"),
            error,
        )
    return patched_record


def _parse_optional_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _latest_last_scan(current_value: Any, candidate_value: Any) -> Any:
    current_dt = _parse_optional_iso_datetime(current_value)
    candidate_dt = _parse_optional_iso_datetime(candidate_value)

    if candidate_dt is None:
        return current_value
    if current_dt is None or candidate_dt > current_dt:
        return candidate_value
    return current_value


def _is_active_integration(integration: dict[str, Any]) -> bool:
    return str(integration.get("status") or "").strip().lower() == "active"


async def _get_active_integrations(db: MongoDBClient, user_id: str) -> list[dict[str, Any]]:
    integrations = await db.get_user_integrations(user_id)
    return [integration for integration in integrations if _is_active_integration(integration)]


async def _get_active_integration_ids(db: MongoDBClient, user_id: str) -> set[str]:
    active_integrations = await _get_active_integrations(db, user_id)
    return {
        str(integration.get("id") or "").strip()
        for integration in active_integrations
        if str(integration.get("id") or "").strip()
    }


async def _get_active_portfolio_stats(db: MongoDBClient, user_id: str) -> dict[str, Any]:
    active_integrations = await _get_active_integrations(db, user_id)
    totals: dict[str, Any] = {
        "total_spend": 0.0,
        "potential_savings": 0.0,
        "active_resources_count": 0,
        "ai_confidence_score": 0,
        "carbon_footprint_kg": 0.0,
        "cost_of_inaction_6mo": 0.0,
    }
    confidence_scores: list[float] = []

    integration_ids = [
        str(i.get("id") or "").strip()
        for i in active_integrations
        if str(i.get("id") or "").strip()
    ]

    if not integration_ids:
        return totals

    stats_list = await asyncio.gather(
        *(db.get_dashboard_stats(user_id, iid) for iid in integration_ids)
    )

    for stats in stats_list:
        stats = stats or {}
        totals["total_spend"] += float(stats.get("total_spend") or 0.0)
        totals["potential_savings"] += float(stats.get("potential_savings") or 0.0)
        totals["active_resources_count"] += int(stats.get("active_resources_count") or 0)
        totals["carbon_footprint_kg"] += float(stats.get("carbon_footprint_kg") or 0.0)
        totals["cost_of_inaction_6mo"] += float(stats.get("cost_of_inaction_6mo") or 0.0)
        try:
            confidence = float(stats.get("ai_confidence_score") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 0:
            confidence_scores.append(confidence)

    if confidence_scores:
        totals["ai_confidence_score"] = int(round(sum(confidence_scores) / len(confidence_scores)))

    return totals


def _totalbill_category_for_service_type(service_type: Any) -> str:
    stype = str(service_type or "").lower()
    if any(keyword in stype for keyword in ["ec2", "compute", "vm", "instance", "container", "eks", "ecs", "gke", "aks", "function", "lambda", "run"]):
        return "Compute"
    if any(keyword in stype for keyword in ["rds", "sql", "database", "mongo", "cosmos", "spanner", "dynamo", "redis", "elastic"]):
        return "Database"
    if any(keyword in stype for keyword in ["s3", "storage", "blob", "bucket", "disk", "ebs"]):
        return "Storage"
    if any(keyword in stype for keyword in ["cloudfront", "cdn", "network", "vpc", "gateway", "lb", "balancer", "nat"]):
        return "Networking"
    if any(keyword in stype for keyword in ["sagemaker", "vertex", "ml", "ai", "bedrock"]):
        return "AI / ML"
    return "Other"


async def _abort_corrupted_scan_credentials(
    *,
    provider_label: str,
    integration_id: str,
    user_id: str,
    db: MongoDBClient,
    integration_metadata: dict[str, Any],
    missing_fields: list[str],
    action_label: str,
    extra_detail: str | None = None,
) -> None:
    error_msg = (
        f"{provider_label} credentials are corrupted or incomplete: missing {', '.join(missing_fields)}. "
        f"Please delete this integration in Settings and reconnect your {provider_label} account."
    )
    if extra_detail:
        error_msg = f"{error_msg} {extra_detail}".strip()

    logger.error(
        "%s scan aborted for integration %s - missing credential fields: %s",
        provider_label,
        integration_id,
        missing_fields,
    )
    await send_scan_progress(user_id, integration_id, 0, f"Error: {error_msg}")
    try:
        await db.create_notifications([{
            "user_id": user_id,
            "resource_id": None,
            "type": "permission_alert",
            "status": "pending",
            "recommendation": error_msg,
            "action": action_label,
            "metadata": {
                "resource_name": f"{provider_label} Credential Error",
                "severity": "critical",
                "description": error_msg,
                "integration_id": integration_id,
                "resource_type": "Alert",
            }
        }])
    except Exception:
        pass

    await db.update_integration(
        integration_id=integration_id,
        user_id=user_id,
        data={
            "metadata": {
                **integration_metadata,
                "scan_status": "failed",
                "scan_error": error_msg,
            }
        },
    )


def _normalize_scan_recommendation_action_type(
    action_label: Any,
    recommendation_type: Any = None,
    ai_status: Any = None,
) -> str:
    normalized = " ".join(
        part
        for part in [
            str(action_label or "").strip().lower(),
            str(recommendation_type or "").strip().lower(),
            str(ai_status or "").strip().lower(),
        ]
        if part
    )

    if not normalized:
        return "optimize"
    if any(keyword in normalized for keyword in ("rightsize", "resize", "smaller", "downsize", "rightsizing")):
        return "rightsize"
    if any(keyword in normalized for keyword in ("savings plan", "reserved instance", "reserved instances", "commitment", "purchase_ri")):
        return "purchase_ri"
    if any(keyword in normalized for keyword in ("stop", "shutdown", "shut down", "deallocate")):
        return "stop"
    if any(keyword in normalized for keyword in ("delete", "terminate", "remove")):
        return "terminate"
    return "optimize"


def _coerce_scan_recommendation_savings(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _normalize_scan_daily_totals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue

        spend_date = str(item.get("date") or item.get("spend_date") or "").strip()[:10]
        if not spend_date or spend_date in seen_dates:
            continue

        try:
            amount = round(float(item.get("amount") or 0.0), 4)
        except (TypeError, ValueError):
            amount = 0.0

        normalized.append({"date": spend_date, "amount": amount})
        seen_dates.add(spend_date)

    normalized.sort(key=lambda row: row["date"])
    return normalized


def _normalize_scan_service_breakdown(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, float] = {}
    for service_name, amount in value.items():
        key = str(service_name or "Unknown").strip() or "Unknown"
        try:
            parsed = round(float(amount or 0.0), 4)
        except (TypeError, ValueError):
            parsed = 0.0
        if parsed:
            normalized[key] = parsed
    return normalized


_DASHBOARD_BILLABLE_RESOURCE_PATTERNS = (
    "compute instance",
    "ec2 instance",
    "persistent disk",
    "ebs volume",
    "external ip",
    "static ip",
    "database",
    "rds",
    "cloud sql",
    "bucket",
    "storage",
    "snapshot",
    "cloud run",
    "cloud function",
    "function",
    "gke",
    "cluster",
    "load balancer",
    "nat gateway",
    "lambda",
)

_DASHBOARD_NO_DIRECT_CHARGE_PATTERNS = (
    "serviceaccountkey",
    "service account key",
    "serviceaccount",
    "service account",
    "entrygroup",
    "logbucket",
    "quotapreference",
    "projectbillinginfo",
    "project billing info",
    "project",
    "firewall",
    "route table",
    "route",
    "network acl",
    "security group rule",
    "security group",
    "internet gateway",
    "dhcp options",
    "key pair",
    "iam role",
    "iam user",
    "iam ",
    "service",
    "subnetwork",
    "subnet",
    "network",
    "namespace",
    "topic",
    "subscription",
    "repository",
    "dockerimage",
    "data catalog",
    "datacatalog",
)


def _scan_resource_cost_amount(resource: dict[str, Any]) -> float:
    try:
        return float(resource.get("cost") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _scan_resource_cost_source(resource: dict[str, Any]) -> str:
    metadata = resource.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return str(
        metadata.get("cost_source")
        or resource.get("cost_source")
        or ""
    ).strip().lower()


def _is_dashboard_counted_resource(resource: dict[str, Any]) -> bool:
    """Return whether a scanned inventory row should affect dashboard resource count."""
    cost_source = _scan_resource_cost_source(resource)
    if cost_source == "actual":
        return True

    if _scan_resource_cost_amount(resource) > 0:
        return True

    service_type = str(resource.get("service_type") or "").strip().lower()
    if not service_type:
        return False

    if any(pattern in service_type for pattern in _DASHBOARD_BILLABLE_RESOURCE_PATTERNS):
        return True

    if any(pattern in service_type for pattern in _DASHBOARD_NO_DIRECT_CHARGE_PATTERNS):
        return False

    return False


def _count_dashboard_resources(resources: list[dict[str, Any]]) -> int:
    return sum(1 for resource in resources if _is_dashboard_counted_resource(resource))


def _build_deterministic_governance(resources: list[dict[str, Any]], total_spend: float) -> dict[str, Any]:
    """Build governance data from actual scanner findings — no AI, no guessing."""
    total = len(resources) or 1
    tag_violations = []
    security_violations = []
    idle_count = 0
    underutilized_count = 0
    orphan_count = 0

    for r in resources:
        status = str(r.get("status") or "").lower()
        waste_type = str(r.get("waste_type") or "").lower()
        govs = r.get("governance_violations") or []

        for g in govs:
            if g.get("type") == "missing_tag":
                tag_violations.append({
                    "resource": r.get("resource_name", "Unknown"),
                    "tags": g.get("tags", []),
                })

        if waste_type == "security_risk":
            security_violations.append(r.get("resource_name", "Unknown"))
        if status in ("zombie", "idle"):
            idle_count += 1
        if status in ("underutilized", "oversized", "moderate"):
            underutilized_count += 1
        if "orphan" in waste_type:
            orphan_count += 1

    compliant_count = total - len(tag_violations) - len(security_violations) - idle_count - orphan_count
    score = max(0, min(100, round((compliant_count / total) * 100)))

    if score >= 80:
        rating = "Good"
    elif score >= 60:
        rating = "Fair"
    elif score >= 40:
        rating = "Needs Attention"
    else:
        rating = "Critical"

    policies = [
        {
            "name": "All resources tagged",
            "status": "pass" if not tag_violations else "fail",
            "severity": "medium",
            "reason": f"{len(tag_violations)} resources missing required tags" if tag_violations else "All resources properly tagged",
            "framework": "FinOps",
        },
        {
            "name": "No idle/zombie resources",
            "status": "pass" if idle_count == 0 else "fail",
            "severity": "high",
            "reason": f"{idle_count} idle resources detected" if idle_count else "No idle resources",
            "framework": "Well-Architected",
        },
        {
            "name": "No public exposure without justification",
            "status": "pass" if not security_violations else "fail",
            "severity": "critical",
            "reason": f"{len(security_violations)} resources with risky inbound rules" if security_violations else "All NSGs properly configured",
            "framework": "CIS",
        },
        {
            "name": "Resources right-sized",
            "status": "pass" if underutilized_count == 0 else "fail",
            "severity": "medium",
            "reason": f"{underutilized_count} underutilized resources" if underutilized_count else "All resources appropriately sized",
            "framework": "FinOps",
        },
        {
            "name": "No orphaned resources",
            "status": "pass" if orphan_count == 0 else "fail",
            "severity": "medium",
            "reason": f"{orphan_count} orphaned disks/IPs/NICs" if orphan_count else "No orphaned resources",
            "framework": "Well-Architected",
        },
    ]

    tag_top_violators = [
        {"resource": tv["resource"], "missing": tv["tags"]}
        for tv in tag_violations[:10]
    ]
    tagged_pct = round(((total - len(tag_violations)) / total) * 100)

    return {
        "score": score,
        "rating": rating,
        "trend": "stable",
        "tagging": {
            "compliancePct": tagged_pct,
            "untaggedAssets": len(tag_violations),
            "topViolators": tag_top_violators,
        },
        "budget": {
            "projectedSpend": total_spend,
            "limit": 0,
            "burnRate": 0,
            "alert": "Budget tracking requires a budget limit to be set in Settings.",
        },
        "officeHours": {
            "savings": 0,
            "enabled": False,
            "recommendation": "Configure office hours scheduling for non-production workloads to reduce costs.",
        },
        "policies": policies,
        "trends": [score],
    }


_SCAN_AI_VERIFICATION_TIMEOUT_SECONDS = 120.0


async def _run_scan_ai_verification(
    analyzer: AIAnalyzer,
    resources: list[dict[str, Any]],
    *,
    provider: str,
    timeout_seconds: float = _SCAN_AI_VERIFICATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run optional scan AI enrichment without making deterministic scans fail."""
    if not resources:
        return {"verified_resources": []}

    try:
        return await asyncio.wait_for(
            analyzer.verify_and_analyze(resources, provider=provider),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "AI verification timed out for %s scan after %.1fs; using deterministic scanner results",
            provider.upper(),
            timeout_seconds,
        )
    except Exception as error:
        logger.warning(
            "AI verification failed for %s scan (%s); using deterministic scanner results",
            provider.upper(),
            type(error).__name__,
        )

    return {
        "verified_resources": resources,
        "total_spend": sum(_scan_resource_cost_amount(resource) for resource in resources),
        "potential_savings": 0,
        "ai_confidence_score": 0,
        "carbon_footprint_kg": 0,
        "recommendations": [],
        "governance_findings": [],
        "alerts": [],
        "waste_distribution": [],
    }


async def _save_scan_daily_spend_history(
    *,
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
    provider: str,
    result: Any,
) -> bool:
    daily_totals = _normalize_scan_daily_totals(getattr(result, "daily_totals", None))
    if not daily_totals:
        logger.info(
            "%s scan did not return provider billing daily history for integration %s",
            provider.upper(),
            integration_id,
        )
        return False

    try:
        await db.save_daily_spend_history(
            user_id=user_id,
            integration_id=integration_id,
            daily_totals=daily_totals,
            service_breakdown=_normalize_scan_service_breakdown(getattr(result, "service_breakdown", None)),
            currency=str(getattr(result, "currency", "USD") or "USD").upper(),
        )
        return True
    except Exception as error:
        logger.warning(
            "Failed to save %s daily spend history for integration %s: %s",
            provider.upper(),
            integration_id,
            error,
        )
        return False


def _build_scan_recommendation_notification(
    *,
    recommendation: dict[str, Any],
    user_id: str,
    integration_id: str,
    resource_id: str | None,
    default_resource_type: str = "Cloud Resource",
) -> dict[str, Any]:
    resource_name = str(recommendation.get("resource_name") or "").strip() or "Unknown Resource"
    resource_type = str(recommendation.get("resource_type") or "").strip() or default_resource_type
    recommendation_text = str(
        recommendation.get("action")
        or recommendation.get("recommendation")
        or "Review this resource"
    ).strip() or "Review this resource"
    normalized_action_type = _normalize_scan_recommendation_action_type(
        recommendation_text,
        recommendation.get("type"),
        recommendation.get("ai_status"),
    )
    ai_reasoning = str(recommendation.get("ai_reasoning") or "").strip()
    description = ai_reasoning or recommendation_text
    potential_savings = _coerce_scan_recommendation_savings(recommendation.get("potential_savings"))
    severity = str(recommendation.get("severity") or "medium").strip().lower() or "medium"

    return {
        "user_id": user_id,
        "resource_id": resource_id,
        "type": str(recommendation.get("type") or "cost_optimization").strip() or "cost_optimization",
        "status": "pending",
        "recommendation": recommendation_text,
        "action": normalized_action_type,
        "metadata": {
            "resource_name": resource_name,
            "estimated_savings": potential_savings,
            "potential_savings": potential_savings,
            "severity": severity,
            "integration_id": integration_id,
            "description": description,
            "resource_type": resource_type,
            "ai_reasoning": ai_reasoning,
            "action_type": normalized_action_type,
        },
    }


async def _clear_pending_notifications_for_integration(
    *,
    db: MongoDBClient,
    user_id: str,
    integration_id: str,
) -> int:
    existing = await db.select(
        "agent_notifications",
        filters={
            "user_id": user_id,
            "status": "pending",
        },
    )
    to_delete = []
    for notification in existing:
        if str(notification.get("status") or "pending").strip().lower() != "pending":
            continue
        metadata = notification.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if metadata.get("integration_id") == integration_id:
            to_delete.append(notification)

    deleted_count = 0
    for notification in to_delete:
        notification_id = str(notification.get("id") or "").strip()
        if not notification_id:
            continue
        try:
            await db.delete("agent_notifications", {"id": notification_id, "user_id": user_id})
            deleted_count += 1
        except Exception as error:
            logger.warning("Failed to delete stale notification %s: %s", notification_id, error)

    return deleted_count


# --- Routes ---

@router.get("/scan-progress")
async def get_scan_progress_endpoint(
    user: ClerkUser = Depends(get_current_user),
):
    """HTTP polling fallback for scan progress (when WebSocket is unreliable)."""
    return get_scan_progress(user.id)


@router.get("/health")
async def health_check(
    user: ClerkUser = Depends(get_current_user),
):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "cloudfinops-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "email": resolve_user_email(user),
    }


@router.post("/user/sync")
async def sync_user(
    payload: UserSyncRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Upsert the authenticated user profile into the users collection."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        existing_users = await db.select("users", filters={"id": user.id})
        existing_user = existing_users[0] if existing_users else None
        sync_record = _build_synced_user_record(
            existing_user=existing_user,
            payload=payload,
            auth_user=user,
            now_iso=now_iso,
        )

        await db.upsert("users", sync_record)

        return {"success": True, "user_id": user.id}
    except Exception as error:
        logger.error("Failed to sync user %s: %s", user.id, error)
        raise HTTPException(status_code=500, detail="Failed to sync user")


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    user: ClerkUser = Depends(get_current_user)
):
    """Get the SOC2 compliance audit logs for the current user."""
    db = get_db_client()
    try:
        # We fetch audit logs descending by created_at.
        # Since MongoDB PostgREST default fetch might not order automatically unless told,
        # we'll sort them in python for this MVP version.
        logs = await db.select("audit_logs", filters={"user_id": user.id})
        logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"logs": logs[:limit]}
    except Exception as e:
        logger.error(f"Failed to fetch audit logs: {e}")
        return {"logs": []}


@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Get all cloud integrations for the current user."""
    integrations = await db.get_user_integrations(user.id)
    await log_audit_event(
        user_id=user.id,
        action_type="INTEGRATIONS_VIEWED",
        metadata={"count": len(integrations)}
    )
    return [
        IntegrationResponse(
            id=i["id"],
            provider=i["provider"],
            name=i["name"],
            status=i["status"],
            last_scan=i.get("last_scan"),
            regions=i.get("regions", []),
            created_at=i.get("created_at"),
            account_identifier=_masked_account_identifier(i),
            monthly_budget_limit=float(i.get("monthly_budget_limit")) if isinstance(i.get("monthly_budget_limit"), (int, float)) else None,
            alert_phone_number_masked=_masked_alert_phone_number(i.get("alert_phone_number")),
            alert_slack_webhook_configured=bool(str(i.get("alert_slack_webhook") or "").strip()),
        )
        for i in integrations
    ]

class IntegrationSettingsUpdate(BaseModel):
    monthly_budget_limit: Optional[float] = None
    alert_phone_number: Optional[str] = None
    alert_slack_webhook: Optional[str] = None

@router.put("/integrations/{integration_id}/settings")
async def update_integration_settings(
    integration_id: str,
    settings: IntegrationSettingsUpdate,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Update budget and alert settings for an integration."""
    
    # Verify ownership
    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    update_data = settings.model_dump(exclude_unset=True)
    
    if not update_data:
        return {"status": "success", "message": "No changes requested"}
        
    try:
        await db.update("cloud_integrations", update_data, {"id": integration_id, "user_id": user.id})
        
        await log_audit_event(
            user_id=user.id,
            action_type="INTEGRATION_SETTINGS_UPDATED",
            resource_target=f"integration:{integration_id}",
            metadata=redact_integration_settings_for_audit(update_data)
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update integration settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/resources", response_model=ResourceResponse)
async def get_resources(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Get resources for the current user."""
    resources = await db.get_resources(user.id, integration_id)
    if not integration_id:
        active_integration_ids = await _get_active_integration_ids(db, user.id)
        resources = [
            resource
            for resource in resources
            if not str(resource.get("integration_id") or "").strip()
            or str(resource.get("integration_id") or "").strip() in active_integration_ids
        ]
    return ResourceResponse(resources=resources, count=len(resources))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Get dashboard statistics for the current user."""
    stats = (
        await db.get_dashboard_stats(user.id, integration_id)
        if integration_id
        else await _get_active_portfolio_stats(db, user.id)
    )
    
    if not stats:
        return StatsResponse(
            total_spend=0,
            potential_savings=0,
            active_resources_count=0,
            ai_confidence_score=0,
            carbon_footprint_kg=0,
            cost_of_inaction_6mo=0
        )
    
    return StatsResponse(
        total_spend=stats.get("total_spend", 0),
        potential_savings=stats.get("potential_savings", 0),
        active_resources_count=stats.get("active_resources_count", 0),
        ai_confidence_score=stats.get("ai_confidence_score", 0),
        carbon_footprint_kg=stats.get("carbon_footprint_kg", 0),
        cost_of_inaction_6mo=stats.get("cost_of_inaction_6mo", 0)
    )


@router.get("/spend-history")
async def get_spend_history(
    integration_id: Optional[str] = None,
    days: int = 30,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """
    Get daily spend history for the spend trend chart.
    
    Returns daily cost data from Azure Cost Management API
    (captured during last scan).
    """
    if integration_id:
        history = await db.get_daily_spend_history(user.id, integration_id, days)
    else:
        active_ids = await _get_active_integration_ids(db, user.id)
        results = await asyncio.gather(
            *(db.get_daily_spend_history(user.id, iid, days) for iid in active_ids)
        )
        rows: list[dict[str, Any]] = [row for result in results for row in result]
        history = aggregate_daily_spend_rows(rows)
        history = history[-days:] if len(history) > days else history

    return {
        "history": history,
        "count": len(history),
        "days_requested": days
    }


@router.get("/totalbill")
async def get_totalbill(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Unified multi-cloud spend view."""
    active_integrations = await _get_active_integrations(db, user.id)

    provider_rollup: dict[str, dict[str, Any]] = {}
    total_spend = 0.0
    total_savings = 0.0
    total_resources = 0
    active_integration_ids = {
        str(integration.get("id") or "")
        for integration in active_integrations
        if str(integration.get("id") or "").strip()
    }

    valid_integrations = [
        i for i in active_integrations if str(i.get("id") or "").strip()
    ]
    stats_list = await asyncio.gather(
        *(db.get_dashboard_stats(user.id, str(i.get("id")).strip()) for i in valid_integrations)
    )

    for integration, stats in zip(valid_integrations, stats_list):
        integration_id = str(integration.get("id") or "").strip()
        provider = str(integration.get("provider") or "").upper() or "UNKNOWN"
        stats = stats or {}
        spend = float(stats.get("total_spend") or 0)
        savings = float(stats.get("potential_savings") or 0)
        resources = int(stats.get("active_resources_count") or 0)
        last_scan = integration.get("last_scan")

        total_spend += spend
        total_savings += savings
        total_resources += resources

        summary = provider_rollup.setdefault(
            provider,
            {
                "provider": provider,
                "monthly_spend": 0.0,
                "potential_savings": 0.0,
                "resource_count": 0,
                "last_scan": None,
                "integration_count": 0,
                "integration_ids": [],
                "account_identifiers": [],
            },
        )
        summary["monthly_spend"] += spend
        summary["potential_savings"] += savings
        summary["resource_count"] += resources
        summary["integration_count"] += 1
        summary["last_scan"] = _latest_last_scan(summary.get("last_scan"), last_scan)
        summary["integration_ids"].append(integration_id)
        account_identifier = integration.get("account_identifier")
        if account_identifier:
            summary["account_identifiers"].append(account_identifier)

    provider_order = {"AWS": 0, "AZURE": 1, "GCP": 2}
    providers = []
    for provider, summary in sorted(
        provider_rollup.items(),
        key=lambda item: (provider_order.get(item[0], 99), item[0]),
    ):
        providers.append(
            {
                "provider": provider,
                "monthly_spend": round(float(summary["monthly_spend"]), 2),
                "potential_savings": round(float(summary["potential_savings"]), 2),
                "resource_count": int(summary["resource_count"]),
                "last_scan": summary.get("last_scan"),
                "integration_count": int(summary["integration_count"]),
                "integration_ids": summary.get("integration_ids", []),
                "account_identifiers": summary.get("account_identifiers", []),
            }
        )

    all_resources = await db.get_resources(user.id)
    category_by_provider: dict[str, dict[str, float]] = {}
    for resource in all_resources:
        integration_id = str(resource.get("integration_id") or "").strip()
        if integration_id and integration_id not in active_integration_ids:
            continue

        provider = str(resource.get("provider") or "unknown").upper()
        category = _totalbill_category_for_service_type(resource.get("service_type"))
        cost = float(resource.get("cost") or 0)

        if category not in category_by_provider:
            category_by_provider[category] = {}
        category_by_provider[category][provider] = category_by_provider[category].get(provider, 0.0) + cost

    categories = []
    for category, by_provider in sorted(
        category_by_provider.items(),
        key=lambda item: -sum(item[1].values()),
    ):
        categories.append(
            {
                "category": category,
                "by_provider": {
                    provider: round(float(amount), 2)
                    for provider, amount in by_provider.items()
                },
                "total": round(float(sum(by_provider.values())), 2),
            }
        )

    from ..core.totalbill_analytics import build_totalbill_visuals

    active_id_list = list(active_integration_ids)
    history_results = await asyncio.gather(
        *(db.get_daily_spend_history(user.id, iid, 90) for iid in active_id_list)
    )
    history_by_integration: dict[str, list[dict[str, Any]]] = dict(
        zip(active_id_list, history_results)
    )

    visual_payload = build_totalbill_visuals(
        active_integrations=active_integrations,
        resources=all_resources,
        history_by_integration=history_by_integration,
        days=90,
    )

    return {
        "total_spend": round(total_spend, 2),
        "total_savings": round(total_savings, 2),
        "total_resources": total_resources,
        "provider_count": len(providers),
        "providers": providers,
        "categories": categories,
        **visual_payload,
    }


@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """
    Trigger a background resource scan for an integration.
    Returns immediately while scan runs in background.
    """
    # Verify integration belongs to user
    integration = await db.get_integration(request.integration_id, user.id)

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Prevent duplicate scans — check if one is already running
    recent_scans = await db.select("scan_history", filters={
        "integration_id": request.integration_id,
        "user_id": user.id,
        "status": "running",
    })
    if recent_scans:
        # Auto-expire stale scans stuck as "running" for > 15 minutes
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
        all_stale = True
        for scan_record in recent_scans:
            started_at = scan_record.get("started_at", "")
            try:
                scan_start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                if scan_start > stale_threshold:
                    all_stale = False
                    break
            except (ValueError, TypeError):
                pass
        if all_stale:
            # Mark all stale scans as failed so they stop blocking
            for scan_record in recent_scans:
                stale_id = scan_record.get("id")
                if stale_id:
                    await db.fail_scan_history(stale_id, "Scan timed out (auto-expired after 15 minutes)")
            logger.warning(
                "Auto-expired %d stale scan(s) for integration %s",
                len(recent_scans),
                request.integration_id,
            )
        else:
            raise HTTPException(
                status_code=409,
                detail="A scan is already in progress for this integration.",
            )

    await log_audit_event(
        user_id=user.id,
        action_type="SCAN_TRIGGERED",
        resource_target=f"integration:{request.integration_id}",
        metadata={"provider": integration["provider"]}
    )

    # Add scan to background tasks
    background_tasks.add_task(
        run_scan,
        integration=integration,
        user_id=user.id,
        db=db
    )
    
    return ScanResponse(
        success=True,
        message=f"Scan started for {integration['name']}",
        task_id=request.integration_id
    )


async def run_scan(integration: dict, user_id: str, db: MongoDBClient):
    """
    Background task to run a cloud resource scan.
    """
    provider = integration["provider"]
    integration_id = integration["id"]
    batch_id = datetime.now(timezone.utc).isoformat()
    integration_metadata = integration.get("metadata")
    if not isinstance(integration_metadata, dict):
        integration_metadata = {}
    
    scan_id = None
    try:
        # Decrypt credentials
        credentials = decrypt_integration_credentials(integration)

        # Create appropriate scanner
        if provider == "aws":
            access_key_id = str(credentials.get("access_key_id") or "").strip()
            secret_access_key = str(credentials.get("secret_access_key") or "").strip()
            role_arn = str(credentials.get("role_arn") or "").strip()
            missing_fields = [
                field_name
                for field_name, value in (
                    ("access_key_id", access_key_id),
                    ("secret_access_key", secret_access_key),
                )
                if not value
            ]
            if missing_fields:
                await _abort_corrupted_scan_credentials(
                    provider_label="AWS",
                    integration_id=integration_id,
                    user_id=user_id,
                    db=db,
                    integration_metadata=integration_metadata,
                    missing_fields=missing_fields,
                    action_label="Reconnect AWS Integration",
                    extra_detail=(
                        "Role-only AWS integrations are not supported by this scanner path yet."
                        if role_arn and (not access_key_id or not secret_access_key)
                        else None
                    ),
                )
                return
            scanner = AWSScanner(
                access_key_id=access_key_id,
                secret_access_key=secret_access_key,
                regions=integration.get("regions")
            )
        elif provider == "azure":
            missing_fields = [
                field_name
                for field_name in ("tenant_id", "client_id", "client_secret", "subscription_id")
                if not credentials.get(field_name)
            ]
            if missing_fields:
                await _abort_corrupted_scan_credentials(
                    provider_label="Azure",
                    integration_id=integration_id,
                    user_id=user_id,
                    db=db,
                    integration_metadata=integration_metadata,
                    missing_fields=missing_fields,
                    action_label="Reconnect Azure Integration",
                )
                return

            from ..scanners.azure import AzureWasteScanner
            from ..core.exchange_rates import get_exchange_rates
            import asyncio

            # Track scan in scan_history
            scan_id = await db.create_scan_history(user_id, integration_id)

            try:
                exchange_rates = await get_exchange_rates(db)
                scanner = AzureWasteScanner(
                    tenant_id=str(credentials.get("tenant_id") or ""),
                    client_id=str(credentials.get("client_id") or ""),
                    client_secret=str(credentials.get("client_secret") or ""),
                    subscription_id=str(credentials.get("subscription_id") or ""),
                    exchange_rates=exchange_rates,
                )
                
                # Run synchronous scanner in thread pool
                await send_scan_progress(user_id, integration_id, 10, "Scanning Azure resources...")
                loop = asyncio.get_event_loop()
                findings = await loop.run_in_executor(None, scanner.scan_all)
                
                await send_scan_progress(user_id, integration_id, 50, f"Analyzing {len(findings)} resources...")
                
                # Prepare resources for DB with user_id and integration_id
                db_resources = []
                for finding in findings:
                    db_resources.append({
                        **finding,
                        "user_id": user_id,
                        "integration_id": integration_id,
                        "scan_batch_id": batch_id,
                    })
                inventory_resource_count = len(db_resources)
                dashboard_resource_count = _count_dashboard_resources(db_resources)

                if db_resources:
                    await db.bulk_upsert_resources(db_resources)
                    # Remove stale resources only after the new scan batch is persisted.
                    await db.delete_resources_for_integration(
                        user_id=user_id,
                        integration_id=integration_id,
                        exclude_batch_id=batch_id,
                    )
                
                # =============================================================
                # AI VERIFICATION — Feed Azure findings to Gemini Flash
                # =============================================================
                await send_scan_progress(user_id, integration_id, 60, "Running AI verification (Gemini Flash)...")
                
                analyzer = AIAnalyzer()
                ai_stats = await _run_scan_ai_verification(analyzer, findings, provider="azure")
                
                # Use AI-verified resources
                verified = ai_stats.get("verified_resources", findings)
                
                # Use REAL subscription cost if available, override AI if we have real data
                scan_summary = getattr(scanner, '_scan_summary', {})
                subscription_costs = scan_summary.get("subscription_costs", {})
                
                if subscription_costs.get("total", 0) > 0:
                    total_spend = subscription_costs["total"]
                    logger.info(f"Using real Azure cost: ${total_spend:.2f}")
                else:
                    total_spend = ai_stats.get("total_spend", sum(f.get("cost", 0) for f in findings))
                
                potential_savings = ai_stats.get("potential_savings", 0)
                
                await send_scan_progress(user_id, integration_id, 70, "Updating dashboard stats...")
                
                # Update resource statuses in DB from AI verdicts
                for vr in verified:
                    if vr.get("ai_verified"):
                        rid = vr.get("cloud_resource_id")
                        if rid:
                            try:
                                await db.update(
                                    "resources",
                                    {
                                        "status": vr.get("status", "Active"),
                                        "waste_reason": vr.get("waste_reason"),
                                        "waste_type": vr.get("waste_type"),
                                        "confidence_score": vr.get("confidence_score", 0),
                                    },
                                    {"cloud_resource_id": rid, "integration_id": integration_id, "user_id": user_id}
                                )
                            except Exception:
                                pass
                
                conflict_pct = ai_stats.get('conflict_rate', 0)
                logger.info("Azure AI verified %d resources (conflict rate: %.0%%)", len(verified), conflict_pct)

                await send_scan_progress(user_id, integration_id, 72, "Applying market-price estimates...")
                await _apply_catalog_estimates_for_scan(db, user_id, integration_id)
                await _apply_community_estimates_for_scan(db, user_id, integration_id)
                await _contribute_community_prices_for_scan(db, user_id, db_resources)

                # Update dashboard stats with AI numbers
                await db.upsert_dashboard_stats({
                    "user_id": user_id,
                    "integration_id": integration_id,
                    "total_spend": total_spend,
                    "potential_savings": potential_savings,
                    "active_resources_count": dashboard_resource_count,
                    "ai_confidence_score": ai_stats.get("ai_confidence_score", 0),
                    "carbon_footprint_kg": ai_stats.get("carbon_footprint_kg", 0),
                    "cost_of_inaction_6mo": potential_savings * 6
                })
                
                # Save daily spend history
                await send_scan_progress(user_id, integration_id, 73, "Saving spend history...")
                
                if subscription_costs.get("daily_totals"):
                    await db.save_daily_spend_history(
                        user_id=user_id,
                        integration_id=integration_id,
                        daily_totals=subscription_costs["daily_totals"],
                        service_breakdown=subscription_costs.get("by_service", {}),
                        currency=subscription_costs.get("currency", "USD")
                    )
                
                # Update waste distribution from AI
                if ai_stats.get("waste_distribution"):
                    waste_data = [
                        {**w, "user_id": user_id, "integration_id": integration_id}
                        for w in ai_stats["waste_distribution"]
                    ]
                    await db.upsert_waste_distribution(waste_data)
                
                # Insert AI recommendations as notifications
                await send_scan_progress(user_id, integration_id, 85, "Generating AI recommendations...")
                
                db_resources_with_ids = await db.get_resources(user_id, integration_id)
                resource_id_map = {
                    r.get("resource_name", "").lower(): r["id"]
                    for r in db_resources_with_ids
                    if r.get("resource_name")
                }
                
                # Build deterministic recommendations from scanner findings
                # These are generated regardless of whether AI succeeds
                scanner_notifications = []
                for finding in db_resources:
                    waste_type = finding.get("waste_type")
                    waste_reason = finding.get("waste_reason")
                    status = finding.get("status", "")
                    if not waste_type and status not in ("zombie", "waste", "underutilized", "non_compliant"):
                        continue
                    if not waste_reason:
                        continue
                    rname = finding.get("resource_name", "")
                    db_resource_id = resource_id_map.get(rname.lower())
                    severity = "high" if status in ("zombie", "waste") else "medium"
                    scanner_notifications.append({
                        "user_id": user_id,
                        "resource_id": db_resource_id,
                        "type": "cost_optimization",
                        "status": "pending",
                        "recommendation": waste_reason,
                        "action": waste_type or "review",
                        "metadata": {
                            "resource_name": rname,
                            "resource_type": finding.get("service_type", "Cloud Resource"),
                            "severity": severity,
                            "description": waste_reason,
                            "integration_id": integration_id,
                            "potential_savings": finding.get("cost", 0),
                            "source": "scanner",
                        },
                    })

                # Clear old notifications THEN insert new ones
                try:
                    await _clear_pending_notifications_for_integration(
                        db=db,
                        user_id=user_id,
                        integration_id=integration_id,
                    )
                except Exception as error:
                    logger.warning("Could not clear old Azure notifications: %s", error)

                # Insert AI recommendations if available
                all_notifications = []
                if ai_stats.get("recommendations"):
                    for rec in ai_stats["recommendations"]:
                        rname = rec.get("resource_name", "")
                        db_resource_id = resource_id_map.get(rname.lower())
                        all_notifications.append(
                            _build_scan_recommendation_notification(
                                recommendation=rec,
                                user_id=user_id,
                                integration_id=integration_id,
                                resource_id=db_resource_id,
                            )
                        )

                # Merge: AI recommendations take priority, scanner fills the gaps
                ai_resource_names = {
                    (n.get("metadata") or {}).get("resource_name", "").lower()
                    for n in all_notifications
                }
                for sn in scanner_notifications:
                    sn_name = (sn.get("metadata") or {}).get("resource_name", "").lower()
                    if sn_name not in ai_resource_names:
                        all_notifications.append(sn)

                if all_notifications:
                    await db.create_notifications(all_notifications)
                    logger.info("Inserted %d recommendations (%d AI + %d scanner) for Azure",
                                len(all_notifications),
                                len(all_notifications) - len(scanner_notifications),
                                len(scanner_notifications))
                
                # Generate governance policies 
                await send_scan_progress(user_id, integration_id, 88, "Generating governance policies...")
                try:
                    from ..governance.compliance_engine import ComplianceEngine
                    compliance = ComplianceEngine(db)
                    resource_crid_map = {
                        r.get("cloud_resource_id", "").lower(): r["id"]
                        for r in db_resources_with_ids
                        if r.get("cloud_resource_id")
                    }
                    await compliance.evaluate_and_save(
                        user_id=user_id,
                        integration_id=integration_id,
                        findings=verified,
                        resource_id_map=resource_crid_map
                    )
                except Exception as e:
                    logger.warning("Governance policy generation failed: %s", e)
                
                # Save AI governance findings and alerts to DB
                if ai_stats.get("governance_findings") or ai_stats.get("alerts"):
                    try:
                        gov_notifications = []
                        for finding in ai_stats.get("governance_findings", []):
                            gov_notifications.append({
                                "user_id": user_id,
                                "resource_id": None,
                                "type": "governance",
                                "status": "pending",
                                "recommendation": finding.get("recommendation", ""),
                                "action": finding.get("recommendation", ""),
                                "metadata": {
                                    "resource_name": f"Governance: {finding.get('type', 'Unknown')}",
                                    "severity": finding.get("severity", "medium"),
                                    "description": finding.get("finding", ""),
                                    "affected_count": finding.get("affected_count", 0),
                                    "integration_id": integration_id,
                                    "resource_type": "Governance Finding",
                                }
                            })
                        for alert in ai_stats.get("alerts", []):
                            gov_notifications.append({
                                "user_id": user_id,
                                "resource_id": None,
                                "type": "alert",
                                "status": "pending",
                                "recommendation": alert.get("description", ""),
                                "action": alert.get("title", ""),
                                "metadata": {
                                    "resource_name": alert.get("title", "Alert"),
                                    "severity": alert.get("severity", "warning"),
                                    "description": alert.get("description", ""),
                                    "integration_id": integration_id,
                                    "resource_type": "Alert",
                                }
                            })
                        if gov_notifications:
                            await db.create_notifications(gov_notifications)
                            logger.info("Saved %d governance findings + alerts", len(gov_notifications))
                    except Exception as e:
                        logger.warning("Failed to save governance/alerts: %s", e)
                
                # Update integration
                await db.update_integration(
                    integration_id=integration_id,
                    user_id=user_id,
                    data={
                        "last_scan": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            **integration_metadata,
                            "last_month_cost": total_spend,
                            "last_scan_batch_id": batch_id,
                            "scan_status": "completed",
                            "scan_error": None,
                            "last_mtd_cost": total_spend,
                            "resources_found": dashboard_resource_count,
                            "inventory_assets_found": inventory_resource_count,
                            "waste_found": len(ai_stats.get("recommendations", [])),
                            "potential_savings": potential_savings
                        }
                    },
                )
                
                # Build deterministic governance data from actual scan findings
                governance_data = _build_deterministic_governance(db_resources, total_spend)

                await db.complete_scan_history(
                    scan_id=scan_id,
                    total_resources=len(findings),
                    waste_found=len(ai_stats.get("recommendations", [])),
                    total_savings=potential_savings,
                    governance_data=governance_data
                )
                
                await send_scan_progress(user_id, integration_id, 90, "Finalizing analysis...")
                logger.info("Azure scan completed: %d resources, $%.2f savings", len(findings), potential_savings)
                await send_scan_complete(user_id, integration_id, len(findings))
                return  # Early return for Azure
                
            except Exception as e:
                # Record failure in scan_history
                if scan_id:
                    await db.fail_scan_history(scan_id, str(e))
                logger.error("Azure scan failed: %s", e, exc_info=True)
                await send_scan_progress(user_id, integration_id, 0, f"Error: {str(e)}")
                await db.update_integration(
                    integration_id=integration_id,
                    user_id=user_id,
                    data={
                        "metadata": {
                            **integration_metadata,
                            "scan_status": "failed",
                            "scan_error": str(e)
                        }
                    },
                )
                return  # Early return on failure
        elif provider == "gcp":
            try:
                from ..scanners.gcp import GCPScanner
            except ImportError:
                GCPScanner = None  # type: ignore

            if GCPScanner is None:
                logger.error("GCP scanner unavailable: google-cloud-compute package not installed")
                await send_scan_progress(user_id, integration_id, 0, "Error: GCP scanner dependencies not installed on the server")
                return

            missing_fields = [
                field_name
                for field_name in ("project_id", "service_account_email", "private_key")
                if not credentials.get(field_name)
            ]
            if missing_fields:
                await _abort_corrupted_scan_credentials(
                    provider_label="GCP",
                    integration_id=integration_id,
                    user_id=user_id,
                    db=db,
                    integration_metadata=integration_metadata,
                    missing_fields=missing_fields,
                    action_label="Reconnect GCP Integration",
                )
                return

            gcp_billing_export_table = str(integration_metadata.get("gcp_billing_export_table", "")).strip() or None
            gcp_billing_lookback_days_raw = integration_metadata.get("gcp_billing_lookback_days")
            gcp_billing_lookback_days = None
            if gcp_billing_lookback_days_raw not in (None, ""):
                try:
                    gcp_billing_lookback_days = int(gcp_billing_lookback_days_raw)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid gcp_billing_lookback_days for integration %s: %s",
                        integration_id,
                        gcp_billing_lookback_days_raw,
                    )

            scanner = GCPScanner(
                project_id=str(credentials.get("project_id") or ""),
                service_account_email=str(credentials.get("service_account_email") or ""),
                private_key=str(credentials.get("private_key") or ""),
                billing_export_table=gcp_billing_export_table,
                billing_lookback_days=gcp_billing_lookback_days,
            )
        elif provider == "kubernetes":
            try:
                from ..scanners.kubernetes import KubernetesScanner
            except ImportError:
                KubernetesScanner = None  # type: ignore

            if KubernetesScanner is None:
                logger.error("Kubernetes scanner unavailable: dependencies not installed")
                await send_scan_progress(user_id, integration_id, 0, "Error: Kubernetes scanner dependencies not installed on the server")
                return
            scanner = KubernetesScanner()
        else:
            logger.error(f"Unknown provider: {provider}")
            await send_scan_progress(user_id, integration_id, 0, f"Error: Unknown provider {provider}")
            return
            
        # Track AWS/GCP/K8s scan in scan_history (Azure does this above)
        scan_id = await db.create_scan_history(user_id, integration_id)
        
        # Run scan
        await send_scan_progress(user_id, integration_id, 10, f"Scanning {provider.upper()} resources...")
        result = await scanner.scan()
        await send_scan_progress(user_id, integration_id, 50, f"Analyzing {len(result.resources)} resources...")

        unique_resources = []
        ai_stats = {}
        persisted_resource_count = 0
        
        if result.resources:
            db_resources = scanner.to_db_resources(result.resources, user_id, integration_id)
            logger.info(f"{provider.upper()} DB resources BEFORE dedup: {len(db_resources)}")
            
            # Free memory from original scanner result
            result.resources = []
            
            # Deduplicate by cloud_resource_id
            seen_ids = set()
            for r in db_resources:
                rid = r.get('cloud_resource_id', '')
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    r["scan_batch_id"] = batch_id
                    unique_resources.append(r)
                else:
                    logger.debug(f"Dedup dropped: {r.get('resource_name', '?')} (id: {rid})")
            
            logger.info(f"{provider.upper()} DB resources AFTER dedup: {len(unique_resources)}")
            
            # Free memory
            db_resources = []

            # Persist deterministic scanner output before any AI work.
            await send_scan_progress(user_id, integration_id, 60, "Saving deterministic scan results...")
            if unique_resources:
                inserted_count = await db.bulk_upsert_resources(unique_resources, batch_size=100)
                logger.info(
                    "Persisted %s/%s raw %s resources before AI verification",
                    inserted_count,
                    len(unique_resources),
                    provider.upper(),
                )
                await db.delete_resources_for_integration(
                    user_id=user_id,
                    integration_id=integration_id,
                    exclude_batch_id=batch_id,
                )
            
            # =====================================================================
            # AI VERIFICATION — Filter target resources to save tokens, memory, and time
            # =====================================================================
            await send_scan_progress(user_id, integration_id, 65, "Filtering target resources for AI verification...")
            
            ai_target_resources = []
            auto_verified_resources = []
            
            target_types = ['compute', 'disk', 'sql', 'database', 'lb', 'ip', 'nat', 'instance', 'rds', 'cluster']
            
            for r in unique_resources:
                service_lower = r.get('service_type', '').lower()
                name_lower = r.get('resource_name', '').lower()
                cost = r.get('cost', 0)
                status = r.get('status', '').lower()
                
                is_target = cost > 0 or any(t in service_lower or t in name_lower for t in target_types) or status in ('waste', 'zombie', 'idle')
                
                if is_target:
                    ai_target_resources.append(r)
                else:
                    r['ai_verified'] = True
                    r['ai_status'] = 'active'
                    r['status'] = 'Active'
                    r['ai_reasoning'] = 'Auto-verified (Zero-cost/Generic)'
                    r['ai_savings'] = 0
                    r['waste_reason'] = None
                    r['waste_type'] = None
                    r['confidence_score'] = 0.0
                    auto_verified_resources.append(r)
            
            await send_scan_progress(user_id, integration_id, 70, f"Running AI Verification on {len(ai_target_resources)} targets...")
            
            analyzer = AIAnalyzer()
            ai_stats = await _run_scan_ai_verification(analyzer, ai_target_resources, provider=provider)
            
            verified = ai_stats.get("verified_resources", [])
            verified.extend(auto_verified_resources)
            
            # Apply AI-enriched updates after deterministic persistence already succeeded.
            await send_scan_progress(user_id, integration_id, 78, "Applying AI verification updates...")
            
            if verified:
                for resource in verified:
                    resource["scan_batch_id"] = batch_id
                logger.info(f"Total verified resources prepared for upsert: {len(verified)}")
                inserted_count = await db.bulk_upsert_resources(verified, batch_size=100)
                logger.info(f"MongoDB successfully upserted {inserted_count} / {len(verified)} resources")
            
            conflict_pct = ai_stats.get('conflict_rate', 0)
            logger.info(f"AI verified {len(verified)} resources (target: {len(ai_target_resources)}, skipped: {len(auto_verified_resources)})")

            await send_scan_progress(user_id, integration_id, 80, "Applying market-price estimates...")
            await _apply_catalog_estimates_for_scan(db, user_id, integration_id)
            await _apply_community_estimates_for_scan(db, user_id, integration_id)
            await _contribute_community_prices_for_scan(db, user_id, unique_resources)

            persisted_resource_count = _count_dashboard_resources(unique_resources)
            persisted_inventory_count = len(unique_resources)
            try:
                persisted_resources = await db.get_resources(user_id, integration_id)
                if persisted_resources:
                    persisted_resource_count = _count_dashboard_resources(persisted_resources)
                    persisted_inventory_count = len(persisted_resources)
            except Exception as error:
                logger.warning(
                    "Could not confirm persisted resource count for integration %s: %s",
                    integration_id,
                    error,
                )
        else:
            persisted_resource_count = 0
            persisted_inventory_count = 0

        # Update dashboard stats with AI-verified numbers
        # Use the real unblended cost from AWS Cost Explorer if available, otherwise AI sum
        real_total_spend = getattr(result, "total_spend", 0)
        final_total_spend = real_total_spend if real_total_spend > 0 else ai_stats.get("total_spend", 0)
        
        await db.upsert_dashboard_stats({
            "user_id": user_id,
            "integration_id": integration_id,
            "total_spend": final_total_spend,
            "potential_savings": ai_stats.get("potential_savings", 0),
            "active_resources_count": persisted_resource_count,
            "ai_confidence_score": ai_stats.get("ai_confidence_score", 0),
            "carbon_footprint_kg": ai_stats.get("carbon_footprint_kg", 0),
            "cost_of_inaction_6mo": ai_stats.get("potential_savings", 0) * 6
        })

        await send_scan_progress(user_id, integration_id, 82, "Saving billing history...")
        await _save_scan_daily_spend_history(
            db=db,
            user_id=user_id,
            integration_id=integration_id,
            provider=provider,
            result=result,
        )
        
        # Update waste distribution
        if ai_stats.get("waste_distribution"):
            waste_data = [
                {
                    **w,
                    "user_id": user_id,
                    "integration_id": integration_id
                }
                for w in ai_stats["waste_distribution"]
            ]
            await db.upsert_waste_distribution(waste_data)
        
        # Insert AI recommendations as notifications
        if ai_stats.get("recommendations"):
            await send_scan_progress(user_id, integration_id, 85, "Generating AI-powered recommendations...")
            
            try:
                deleted_count = await _clear_pending_notifications_for_integration(
                    db=db,
                    user_id=user_id,
                    integration_id=integration_id,
                )
                logger.info("Cleared %d old notifications for integration %s", deleted_count, integration_id)
            except Exception as e:
                logger.warning("Could not clear old notifications: %s", e)
            
            # Get resource IDs from DB for linking
            db_resources_with_ids = await db.get_resources(user_id, integration_id)
            resource_id_map = {
                r.get("resource_name", "").lower(): r["id"]
                for r in db_resources_with_ids
                if r.get("resource_name")
            }
            
            notifications = []
            for rec in ai_stats["recommendations"]:
                rname = rec.get("resource_name", "")
                db_resource_id = resource_id_map.get(rname.lower())
                
                notification = _build_scan_recommendation_notification(
                    recommendation=rec,
                    user_id=user_id,
                    integration_id=integration_id,
                    resource_id=db_resource_id,
                )
                notifications.append(notification)
            
            try:
                if notifications:
                    await db.create_notifications(notifications)
                    logger.info("Inserted %d AI-verified recommendations", len(notifications))
            except Exception as e:
                logger.error("Failed to insert notifications: %s", e)
        
        # Generate Governance Policies (rule-based)
        await send_scan_progress(user_id, integration_id, 88, "Generating governance policies...")
        from ..governance import generate_governance_policies
        try:
            await generate_governance_policies(user_id, integration_id, unique_resources, db)
        except Exception as e:
            logger.warning(f"Failed to generate governance policies: {e}")
        
        # Save AI governance findings and alerts to DB
        if ai_stats.get("governance_findings") or ai_stats.get("alerts"):
            try:
                gov_notifications = []
                for finding in ai_stats.get("governance_findings", []):
                    gov_notifications.append({
                        "user_id": user_id,
                        "resource_id": None,
                        "type": "governance",
                        "status": "pending",
                        "recommendation": finding.get("recommendation", ""),
                        "action": finding.get("recommendation", ""),
                        "metadata": {
                            "resource_name": f"Governance: {finding.get('type', 'Unknown')}",
                            "severity": finding.get("severity", "medium"),
                            "description": finding.get("finding", ""),
                            "affected_count": finding.get("affected_count", 0),
                            "integration_id": integration_id,
                            "resource_type": "Governance Finding",
                        }
                    })
                for alert in ai_stats.get("alerts", []):
                    gov_notifications.append({
                        "user_id": user_id,
                        "resource_id": None,
                        "type": "alert",
                        "status": "pending",
                        "recommendation": alert.get("description", ""),
                        "action": alert.get("title", ""),
                        "metadata": {
                            "resource_name": alert.get("title", "Alert"),
                            "severity": alert.get("severity", "warning"),
                            "description": alert.get("description", ""),
                            "integration_id": integration_id,
                            "resource_type": "Alert",
                        }
                    })
                if gov_notifications:
                    await db.create_notifications(gov_notifications)
                    logger.info(f"Saved {len(gov_notifications)} governance findings + alerts")
            except Exception as e:
                logger.warning(f"Failed to save governance/alerts: {e}")
        
        # Check for restricted AWS permissions and generate an alert
        access_denied = getattr(result, "access_denied_services", [])
        if access_denied:
            missing_svcs = ", ".join(access_denied[:5]) + ("..." if len(access_denied) > 5 else "")
            try:
                await db.create_notifications([{
                    "user_id": user_id,
                    "resource_id": None,
                    "type": "permission_alert",
                    "status": "pending",
                    "recommendation": f"Missing Read-Only permissions. Add 'ViewOnlyAccess' to your IAM user.",
                    "action": "Restricted AWS Permissions Detected",
                    "metadata": {
                        "resource_name": "Restricted Scan",
                        "severity": "high",
                        "description": f"The scanner was denied access to {len(access_denied)} services ({missing_svcs}). We completed a partial scan using available data. Grant 'ViewOnlyAccess' to unlock full insights.",
                        "integration_id": integration_id,
                        "resource_type": "Alert",
                        "missing_services": access_denied
                    }
                }])
                logger.info(f"Created restricted access alert for {len(access_denied)} services")
            except Exception as e:
                logger.warning(f"Failed to save permission alert: {e}")
                
        # Update integration last_scan
        await db.update_integration(
            integration_id=integration_id,
            user_id=user_id,
            data={
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    **integration_metadata,
                    "last_month_cost": final_total_spend,
                    "last_mtd_cost": final_total_spend,
                    "last_scan_batch_id": batch_id,
                    "scan_status": "completed",
                    "scan_error": None,
                            "regions_scanned": getattr(result, 'regions_scanned', 0),
                            "resources_found": persisted_resource_count,
                            "inventory_assets_found": persisted_inventory_count,
                            "waste_found": len(ai_stats.get("recommendations", [])),
                            "potential_savings": ai_stats.get("potential_savings", 0)
                        }
                    },
                )
        
        # Complete AWS/GCP/K8s scan history to save AI Governance payload
        gov_data = ai_stats.get("governance_data")
        logger.info(f"Saving governance_data for AWS/Generic: {list(gov_data.keys()) if gov_data else 'NONE'}")

        if scan_id:
            await db.complete_scan_history(
                scan_id=scan_id,
                total_resources=persisted_resource_count,
                waste_found=len(ai_stats.get("recommendations", [])),
                total_savings=ai_stats.get("potential_savings", 0),
                governance_data=gov_data
            )
        
        await send_scan_progress(user_id, integration_id, 90, "Finalizing analysis...")
        logger.info(f"Scan completed for {integration['name']}: {persisted_resource_count} resources found")
        await send_scan_complete(user_id, integration_id, persisted_resource_count)
        
    except Exception as e:
        # Wrap in secondary try/except so logging can NEVER silently kill the scan
        try:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Scan failed for {integration.get('name', '?')}: {e}")
            logger.error(f"Full traceback: {error_trace}")
            error_msg = str(e) or "Unknown error"
            await send_scan_progress(user_id, integration_id, 0, f"Error: {error_msg}")
            # Mark scan_history as failed so it doesn't block future scans
            if scan_id:
                await db.fail_scan_history(scan_id, error_msg)
            await db.update_integration(
                integration_id=integration_id,
                user_id=user_id,
                data={
                    "metadata": {
                        **integration_metadata,
                        "scan_status": "failed",
                        "scan_error": str(e)
                    }
                },
            )
        except Exception as inner_e:
            logger.error(f"Error handler itself failed: {inner_e}")
            try:
                await send_scan_progress(user_id, integration_id, 0, "Error: Scan failed")
            except Exception:
                pass


class AutomatedSyncValidationRequest(BaseModel):
    provider: str
    storage_path: str
    credential: str


def _split_aws_key_secret(credential: str) -> tuple[str, str]:
    parts = credential.split("::", 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS credential format. Use `ACCESS_KEY_ID::SECRET_ACCESS_KEY`.",
        )
    return parts[0].strip(), parts[1].strip()


def _rate_limit_validation_error(provider_label: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=f"{provider_label} billing validation is temporarily rate limited. Please retry shortly.",
    )


def _validate_aws_automated_sync(storage_path: str, credential: str) -> dict[str, bool]:
    import boto3
    from botocore.exceptions import ClientError

    access_key, secret_key = _split_aws_key_secret(credential)
    client = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=build_aws_retry_config(region_name="us-east-1"),
    )

    try:
        call_with_backoff(
            "AWS automated sync bucket validation",
            lambda: client.list_objects_v2(Bucket=storage_path, MaxKeys=1),
            is_retryable=is_aws_retryable,
        )
        return {"valid": True}
    except ClientError as error:
        if is_aws_retryable(error):
            raise _rate_limit_validation_error("AWS") from error

        error_code = error.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Access denied for bucket `{storage_path}`. "
                    "Grant at least s3:ListBucket and s3:GetObject."
                ),
            ) from error
        if error_code == "NoSuchBucket":
            raise HTTPException(status_code=404, detail=f"S3 bucket `{storage_path}` was not found.") from error
        if error_code in {"InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            raise HTTPException(status_code=401, detail="AWS access key/secret key is invalid.") from error
        raise HTTPException(status_code=400, detail="AWS validation failed.") from error
    except Exception as error:
        if is_aws_retryable(error):
            raise _rate_limit_validation_error("AWS") from error
        raise


def _validate_azure_automated_sync(storage_path: str, credential: str) -> dict[str, bool]:
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError
    from azure.storage.blob import BlobServiceClient

    try:
        client = BlobServiceClient.from_connection_string(credential)
        container = client.get_container_client(storage_path)
        call_with_backoff(
            "Azure automated sync container validation",
            container.get_container_properties,
            is_retryable=is_azure_retryable,
        )
        return {"valid": True}
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Azure container `{storage_path}` was not found.") from error
    except ClientAuthenticationError as error:
        if is_azure_retryable(error):
            raise _rate_limit_validation_error("Azure") from error
        raise HTTPException(status_code=401, detail="Azure authentication failed.") from error
    except HttpResponseError as error:
        if is_azure_retryable(error):
            raise _rate_limit_validation_error("Azure") from error
        raise HTTPException(status_code=400, detail="Azure storage validation failed.") from error
    except Exception as error:
        if is_azure_retryable(error):
            raise _rate_limit_validation_error("Azure") from error
        raise


def _validate_gcp_automated_sync(storage_path: str, credential: str) -> dict[str, bool]:
    import json as json_lib
    import re
    from google.cloud import bigquery
    from google.oauth2 import service_account

    parts = storage_path.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=400,
            detail="GCP storage_path must be `project.dataset.table` for BigQuery billing export.",
        )

    _BQ_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
    for part in parts:
        if not part or not _BQ_IDENTIFIER_RE.match(part):
            raise HTTPException(
                status_code=400,
                detail="GCP storage_path contains invalid characters. Only alphanumeric, hyphens, and underscores are allowed.",
            )

    credentials_info = json_lib.loads(credential)
    creds = service_account.Credentials.from_service_account_info(credentials_info)
    client = bigquery.Client(project=creds.project_id, credentials=creds)
    safe_path = f"{parts[0]}.{parts[1]}.{parts[2]}"
    query = f"SELECT 1 FROM `{safe_path}` LIMIT 1"

    try:
        call_with_backoff(
            "GCP automated sync billing export validation",
            lambda: list(client.query(query).result()),
            is_retryable=is_gcp_retryable,
        )
        return {"valid": True}
    except Exception as error:
        if is_gcp_retryable(error):
            raise _rate_limit_validation_error("GCP") from error
        raise HTTPException(status_code=400, detail="GCP billing export validation failed.") from error


@router.post("/scan/validate-automated-sync")
async def validate_automated_sync(
    req: AutomatedSyncValidationRequest,
    user: ClerkUser = Depends(get_current_user),
):
    """
    Validate read-only billing sync credentials before saving integration.
    """
    _ = user
    provider = (req.provider or "").strip().lower()
    storage_path = (req.storage_path or "").strip()
    credential = (req.credential or "").strip()

    if provider not in {"aws", "azure", "gcp"}:
        raise HTTPException(status_code=400, detail="provider must be one of: aws, azure, gcp")
    if not storage_path or not credential:
        raise HTTPException(status_code=400, detail="storage_path and credential are required")

    try:
        validator = {
            "aws": _validate_aws_automated_sync,
            "azure": _validate_azure_automated_sync,
            "gcp": _validate_gcp_automated_sync,
        }[provider]
        return await asyncio.to_thread(validator, storage_path, credential)

    except HTTPException:
        raise
    except Exception as error:
        logger.warning("Automated sync validation failed for provider %s: %s", provider, error)
        raise HTTPException(status_code=400, detail="Connection failed.") from error


@router.post("/scan/upload-bill", response_model=BillAnalysisRecordResponse)
async def upload_bill(
    file: UploadFile = File(...),
    aws_discount_pct: float = Form(0.0),
    gcp_discount_pct: float = Form(0.0),
    azure_discount_pct: float = Form(0.0),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Parse uploaded bill and return cross-cloud arbitrage analysis.
    """
    from ..bill_parser import (
        analyze_arbitrage,
        enrich_parsed_bill_with_gemini,
        extract_bill_with_gemini,
        fetch_cross_cloud_prices,
        generate_full_intelligence_report,
        normalize_full_intelligence_report,
        parse_bill,
    )

    try:
        filename = file.filename or "bill.csv"
        extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if extension not in {"csv", "xlsx", "xls", "pdf"}:
            raise HTTPException(
                status_code=400,
                detail="Only .csv, .xlsx, .xls, and .pdf files are supported.",
            )

        content = await file.read(_MAX_BILL_UPLOAD_BYTES + 1)
        if len(content) > _MAX_BILL_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum upload size is {_MAX_BILL_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )

        _MAGIC_BYTES = {
            "pdf": b"%PDF",
            "xlsx": b"PK\x03\x04",
            "xls": b"\xd0\xcf\x11\xe0",
        }
        expected_magic = _MAGIC_BYTES.get(extension)
        if expected_magic and not content[:len(expected_magic)] == expected_magic:
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match expected .{extension} format.",
            )
        async def _try_gemini_direct_extraction(reason: str) -> dict[str, Any] | None:
            try:
                return await extract_bill_with_gemini(
                    content,
                    filename,
                    content_type=file.content_type,
                )
            except Exception as error:
                logger.warning(
                    "Gemini direct bill extraction skipped for %s after %s: %s",
                    filename,
                    reason,
                    error,
                )
                return None

        try:
            parsed = await asyncio.wait_for(
                asyncio.to_thread(parse_bill, content, filename),
                timeout=_BILL_PARSE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as error:
            parsed = await _try_gemini_direct_extraction("parser timeout")
            if not parsed:
                raise HTTPException(
                    status_code=504,
                    detail=(
                        "Bill parsing took too long and Gemini direct extraction could not recover it. "
                        "Upload a CSV/Excel export, or use a smaller text-based PDF."
                    ),
                ) from error
        except ValueError as parse_error:
            parsed = await _try_gemini_direct_extraction("parser error")
            if not parsed:
                raise parse_error
        else:
            try:
                parsed = await enrich_parsed_bill_with_gemini(
                    parsed,
                    content,
                    filename,
                    content_type=file.content_type,
                )
            except Exception as error:
                logger.warning("Gemini direct bill enrichment skipped for %s: %s", filename, error)

        # Dedup: if the same user uploaded the same filename with identical content hash
        # and similar total spend within the last 6 hours, return the existing analysis.
        import hashlib
        content_hash = hashlib.sha256(content).hexdigest()
        parsed_total_spend = float(parsed.get("total_spend") or 0)
        existing_analyses = await db.get_bill_analyses(user.id, limit=5)
        for existing in existing_analyses or []:
            existing_filename = str(existing.get("filename") or "")
            existing_hash = str(existing.get("source_metadata", {}).get("content_hash") or "")
            existing_created = str(existing.get("created_at") or "")
            if existing_filename != filename:
                continue
            if existing_hash and existing_hash != content_hash:
                continue
            if not existing_hash:
                # Legacy record without hash — fall back to spend comparison
                existing_spend = float(existing.get("total_analyzed_spend") or 0)
                spend_diff = abs(existing_spend - parsed_total_spend)
                spend_threshold = max(abs(parsed_total_spend) * 0.01, 0.01)
                if spend_diff > spend_threshold:
                    continue
            # Check recency (within 6 hours).
            try:
                created_dt = datetime.fromisoformat(existing_created.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                if age_hours <= 6:
                    existing_source_metadata = (
                        existing.get("source_metadata")
                        if isinstance(existing.get("source_metadata"), dict)
                        else {}
                    )
                    parsed_source_metadata = (
                        parsed.get("source_metadata")
                        if isinstance(parsed.get("source_metadata"), dict)
                        else {}
                    )
                    existing_quality = _bill_analysis_extraction_quality(existing, persisted=True)
                    parsed_quality = _bill_analysis_extraction_quality(parsed, persisted=False)
                    existing_parser_version = str(
                        existing_source_metadata.get("pdf_parser_version")
                        or existing.get("source_parser")
                        or ""
                    )
                    parsed_parser_version = str(
                        parsed_source_metadata.get("pdf_parser_version")
                        or parsed.get("source_parser")
                        or ""
                    )
                    if parsed_quality > existing_quality or (
                        parsed_parser_version
                        and parsed_parser_version != existing_parser_version
                        and parsed_quality >= existing_quality
                    ):
                        logger.info(
                            "Skipping recent bill analysis reuse for %s because current extraction is richer "
                            "(existing_quality=%s, parsed_quality=%s)",
                            filename,
                            existing_quality,
                            parsed_quality,
                        )
                        continue
                    existing_raw_file_metadata = (
                        existing_source_metadata.get("raw_bill_file")
                        if isinstance(existing_source_metadata.get("raw_bill_file"), dict)
                        else None
                    )
                    if str((existing_raw_file_metadata or {}).get("status") or "").strip().lower() != "stored":
                        archived_raw_file_metadata = await archive_uploaded_bill_to_gcs(
                            user_id=user.id,
                            filename=filename,
                            content=content,
                            content_type=file.content_type,
                            content_hash=content_hash,
                        )
                        patched_source_metadata = {
                            **existing_source_metadata,
                            "content_hash": existing_hash or content_hash,
                            "raw_bill_file": archived_raw_file_metadata,
                        }
                        try:
                            await db.update(
                                "bill_analyses",
                                {"source_metadata": patched_source_metadata},
                                {"id": str(existing.get("id") or ""), "user_id": user.id},
                            )
                            existing = {
                                **existing,
                                "source_metadata": patched_source_metadata,
                            }
                        except Exception as error:
                            logger.warning(
                                "Failed to backfill raw bill archival metadata for analysis %s: %s",
                                existing.get("id"),
                                error,
                            )
                    existing = await _ensure_bill_analysis_executive_report(existing, db)
                    decorated = await _decorate_bill_analysis_response(existing)
                    return BillAnalysisRecordResponse(**decorated)
            except Exception:
                pass

        opportunities = await fetch_cross_cloud_prices(
            by_category=parsed["by_category"],
            source_provider=parsed["provider"],
            aws_discount_pct=aws_discount_pct,
            gcp_discount_pct=gcp_discount_pct,
            azure_discount_pct=azure_discount_pct,
        )

        try:
            opportunities = await analyze_arbitrage(
                parsed_bill=parsed,
                opportunities=opportunities,
                aws_discount_pct=aws_discount_pct,
                gcp_discount_pct=gcp_discount_pct,
                azure_discount_pct=azure_discount_pct,
            )
        except Exception as error:
            logger.warning(
                "Bill AI enrichment failed for %s, deterministic pricing fallback used: %s",
                filename,
                error,
            )

        total_savings = round(
            sum(float(item.get("savings", 0) or 0) for item in opportunities if float(item.get("savings", 0) or 0) > 0),
            2,
        )
        cloudfront_insights = parsed.get("cloudfront_insights")
        if cloudfront_insights:
            cf_savings = float(
                cloudfront_insights.get("summary", {}).get("total_monthly_savings_available", 0) or 0
            )
            total_savings = max(total_savings, round(cf_savings, 2))
        parsed_source_metadata = (
            parsed.get("source_metadata")
            if isinstance(parsed.get("source_metadata"), dict)
            else {}
        )
        if str(parsed.get("source_format") or parsed_source_metadata.get("source_format") or "").lower() == "pdf":
            total_savings = 0.0

        try:
            executive_report = await generate_full_intelligence_report(
                parsed_bill=parsed,
                opportunities=opportunities,
            )
        except Exception as error:
            executive_report = None
            logger.warning(
                "Executive bill report generation failed for %s, continuing without it: %s",
                filename,
                error,
            )
        executive_report = await normalize_full_intelligence_report(
            executive_report if isinstance(executive_report, dict) else None,
            parsed,
            opportunities,
        )
        report_verification_status = str(executive_report.get("verification_status") or "").strip()
        if report_verification_status == "bill_line_rule_estimate":
            total_savings = max(
                total_savings,
                _bill_analysis_money(executive_report.get("additional_savings_max")),
            )
        elif report_verification_status == "source_grounded_unverified_savings":
            total_savings = 0.0
        raw_file_metadata = await archive_uploaded_bill_to_gcs(
            user_id=user.id,
            filename=filename,
            content=content,
            content_type=file.content_type,
            content_hash=content_hash,
        )

        analysis_record = _build_bill_analysis_record(
            filename=filename,
            parsed=parsed,
            opportunities=opportunities,
            total_savings=total_savings,
            aws_discount_pct=aws_discount_pct,
            gcp_discount_pct=gcp_discount_pct,
            azure_discount_pct=azure_discount_pct,
            user_id=user.id,
            executive_report=executive_report,
            content_hash=content_hash,
            raw_file_metadata=raw_file_metadata,
        )
        created = await db.create_bill_analysis(analysis_record)
        if not created:
            raise HTTPException(status_code=500, detail="Bill analysis could not be persisted")

        try:
            await db.mark_user_feature_enabled(
                user.id,
                "bill_analysis",
                last_used=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as error:
            logger.warning("Failed to persist bill-analysis feature flag for %s: %s", user.id, error)

        return BillAnalysisRecordResponse(**await _decorate_bill_analysis_response(created))

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid bill format or parameters.")
    except Exception as error:
        logger.error("Bill upload processing error: %s", error, exc_info=True)
        raise HTTPException(status_code=500, detail="Bill processing failed. Please try again or use a different file format.")


@router.get("/bill-analyses", response_model=BillAnalysesListResponse)
async def list_bill_analyses(
    limit: int = 10,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    analyses = _filter_valid_bill_analyses(
        await db.get_bill_analyses(user.id, limit=max(limit * 3, limit))
    )[:limit]
    analyses = await asyncio.gather(
        *[_ensure_bill_analysis_executive_report(analysis, db) for analysis in analyses]
    ) if analyses else []
    decorated_analyses = await asyncio.gather(
        *[_decorate_bill_analysis_response(analysis) for analysis in analyses]
    )
    return BillAnalysesListResponse(
        analyses=[BillAnalysisRecordResponse(**item) for item in decorated_analyses],
        count=len(decorated_analyses),
    )


@router.get("/bill-analyses/latest", response_model=BillAnalysisRecordResponse)
async def get_latest_bill_analysis(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    analyses = _filter_valid_bill_analyses(await db.get_bill_analyses(user.id, limit=10))
    analysis = analyses[0] if analyses else None
    if not analysis:
        raise HTTPException(status_code=404, detail="No bill analysis found for this user")
    analysis = await _ensure_bill_analysis_executive_report(analysis, db)
    return BillAnalysisRecordResponse(**await _decorate_bill_analysis_response(analysis))


@router.get("/bill-analyses/{analysis_id}", response_model=BillAnalysisRecordResponse)
async def get_bill_analysis(
    analysis_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    analysis = await db.get_bill_analysis(user.id, analysis_id)
    if not analysis or _is_legacy_invalid_bill_analysis(analysis):
        raise HTTPException(status_code=404, detail="Bill analysis not found")
    analysis = await _ensure_bill_analysis_executive_report(analysis, db)
    return BillAnalysisRecordResponse(**await _decorate_bill_analysis_response(analysis))


@router.get("/bill-analyses/{analysis_id}/source-file")
async def download_bill_analysis_source_file(
    analysis_id: str,
    request: Request,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    analysis = await db.get_bill_analysis(user.id, analysis_id)
    if not analysis or _is_legacy_invalid_bill_analysis(analysis):
        raise HTTPException(status_code=404, detail="Bill analysis not found")

    source_metadata = analysis.get("source_metadata") if isinstance(analysis.get("source_metadata"), dict) else {}
    raw_bill_metadata = source_metadata.get("raw_bill_file") if isinstance(source_metadata.get("raw_bill_file"), dict) else None
    if not raw_bill_metadata:
        raise HTTPException(status_code=404, detail="Raw bill file is not available for this analysis")

    try:
        content, media_type, filename = await download_archived_bill_from_gcs(raw_bill_metadata)
    except RawBillStorageNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RawBillStorageError as error:
        logger.error("download_bill_analysis_source_file failed for %s: %s", analysis_id, error)
        raise HTTPException(status_code=502, detail="Archived raw bill file could not be retrieved") from error

    disposition_type = "attachment" if request.query_params.get("download") == "1" else "inline"
    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/user/features", response_model=UserFeaturesResponse)
async def get_user_features(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    feature_rows = await db.get_user_features(user.id)
    feature_details: dict[str, UserFeatureResponse] = {}
    features: list[str] = []

    for row in feature_rows:
        feature_name = str(row.get("feature") or "").strip()
        if not feature_name or not bool(row.get("enabled", True)):
            continue
        features.append(feature_name)
        feature_details[feature_name] = UserFeatureResponse(
            feature=feature_name,
            enabled=True,
            last_used=str(row.get("last_used") or "") or None,
            first_upload_at=str(row.get("first_upload_at") or "") or None,
        )

    return UserFeaturesResponse(features=features, feature_details=feature_details)


@router.get("/notifications")
async def get_notifications(
    status: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Get notifications for the current user."""
    notifications = await db.get_notifications(user.id, status)
    return {"notifications": notifications, "count": len(notifications)}


@router.patch("/notifications/{notification_id}", response_model=NotificationMutationResponse)
async def mark_notification_read(
    notification_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Mark a notification as read for the current user."""
    try:
        notifications = await db.select(
            "agent_notifications",
            filters={"id": notification_id, "user_id": user.id},
        )
        if not notifications:
            raise HTTPException(status_code=404, detail="Notification not found")

        await db.update(
            "agent_notifications",
            {"status": "completed"},
            {"id": notification_id, "user_id": user.id},
        )
        return NotificationMutationResponse(success=True, message="Notification marked as read")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("mark_notification_read failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to mark alert as read")


@router.delete("/notifications/{notification_id}", response_model=NotificationMutationResponse)
async def delete_notification(
    notification_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Delete a notification for the current user."""
    try:
        notifications = await db.select(
            "agent_notifications",
            filters={"id": notification_id, "user_id": user.id},
        )
        if not notifications:
            raise HTTPException(status_code=404, detail="Notification not found")

        await db.delete(
            "agent_notifications",
            {"id": notification_id, "user_id": user.id},
        )
        return NotificationMutationResponse(success=True, message="Notification deleted")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("delete_notification failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to delete alert")


# --- Fix Generation Endpoints ---

class GenerateFixRequest(BaseModel):
    """Request to generate a fix script for a notification."""
    notification_id: str


class GenerateFixResponse(BaseModel):
    """Response containing the generated fix script."""
    success: bool
    script: Optional[str] = None
    error: Optional[str] = None


@router.post("/generate-fix", response_model=GenerateFixResponse)
async def generate_fix_script(
    request: GenerateFixRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """
    Generate an AI-powered CLI command to fix a cloud waste issue.
    
    Process:
    1. Fetch notification and resource details
    2. Send prompt to Gemini AI
    3. Save generated script to database
    4. Return script to frontend
    """
    try:
        user_id = user.id
        notification_id = request.notification_id
        
        # Fetch the notification
        notifications = await db.select(
            "agent_notifications",
            filters={"id": notification_id, "user_id": user_id}
        )
        
        if not notifications:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification = notifications[0]
        metadata = notification.get("metadata", {})
        resource_name = metadata.get("resource_name", "unknown")
        action_type = notification.get("action", "delete")
        
        # Try to get resource details if resource_id exists
        resource_id = notification.get("resource_id")
        provider = "Azure"  # Default
        service_type = metadata.get("resource_type", "Cloud Resource")
        region = "unknown"
        
        if resource_id:
            resources = await db.select(
                "resources",
                filters={"id": resource_id, "user_id": user_id}
            )
            if resources:
                resource = resources[0]
                provider = resource.get("provider", "Azure")
                service_type = resource.get("service_type", service_type)
                region = resource.get("region", "unknown")
                resource_id_str = resource.get("resource_id", resource_id)
            else:
                # Resource might have been deleted
                resource_id_str = resource_id
        else:
            # No resource_id - use resource_name as identifier
            resource_id_str = resource_name
        
        # Generate fix script using AI
        from ..ai.fix_generator import get_fix_generator
        
        try:
            generator = get_fix_generator()
            
            # Route to appropriate generator based on action type
            if action_type in ["delete", "terminate"]:
                script = await generator.generate_delete_command(
                    provider=provider,
                    service_type=service_type,
                    resource_id=resource_id_str,
                    resource_name=resource_name,
                    region=region,
                    metadata=metadata
                )
            elif action_type == "resize":
                current_size = metadata.get("current_size", "unknown")
                recommended_size = metadata.get("recommended_size", "smaller")
                script = await generator.generate_resize_command(
                    provider=provider,
                    service_type=service_type,
                    resource_id=resource_id_str,
                    current_size=current_size,
                    recommended_size=recommended_size,
                    region=region
                )
            elif action_type in ["stop", "deallocate"]:
                script = await generator.generate_stop_command(
                    provider=provider,
                    service_type=service_type,
                    resource_id=resource_id_str,
                    resource_name=resource_name,
                    region=region
                )
            else:
                # Default to delete
                script = await generator.generate_delete_command(
                    provider=provider,
                    service_type=service_type,
                    resource_id=resource_id_str,
                    resource_name=resource_name,
                    region=region,
                    metadata=metadata
                )
            
            # Save the generated script to the notification
            await db.update(
                "agent_notifications",
                {"generated_script": script},
                {"id": notification_id, "user_id": user_id}
            )
            
            logger.debug("Generated fix script for notification %s", notification_id)
            
            return GenerateFixResponse(success=True, script=script)
            
        except Exception as e:
            error_msg = f"AI script generation failed: {str(e)}"
            logger.error("Fix script generation failed: %s", e)
            return GenerateFixResponse(
                success=False,
                error=error_msg
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in generate_fix_script: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Fix script generation failed.")


class ExecuteActionRequest(BaseModel):
    """Request to mark an action as executed."""
    notification_id: str


class RejectActionRequest(BaseModel):
    """Request to reject an action."""
    notification_id: str
    reason: str


@router.post("/execute-action")
async def execute_action(
    request: ExecuteActionRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Mark a pending action as executed."""
    try:
        await db.update(
            "agent_notifications",
            {
                "status": "approved",
                "executed_at": datetime.now().isoformat()
            },
            {
                "id": request.notification_id,
                "user_id": user.id
            }
        )
        return {"success": True, "message": "Action marked as executed"}
    except Exception as e:
        logger.error("execute_action failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute action.")


@router.post("/reject-action")
async def reject_action(
    request: RejectActionRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client)
):
    """Reject a pending action with a reason."""
    try:
        await db.update(
            "agent_notifications",
            {
                "status": "rejected",
                "rejection_reason": request.reason
            },
            {
                "id": request.notification_id,
                "user_id": user.id
            }
        )
        return {"success": True, "message": "Action rejected"}
    except Exception as e:
        logger.error("reject_action failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reject action.")


# ─────────────────────────────────────────────────────────────────────────────
# GPU Intelligence
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/gpu/summary")
@cache_response(expire_seconds=600)
async def get_gpu_summary(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Full GPU Intelligence report for live-scanned resources.
    Returns ghost GPUs, MIG candidates, specialized cloud arbitrage,
    SageMaker waste, and an AI narrative — no extra cloud API calls.
    """
    try:
        from ..core.gpu_service import GpuService
        resources = await db.get_resources(user.id, integration_id)
        service = GpuService()
        report = service.get_gpu_summary(resources, integration_id)
        return report
    except Exception as e:
        logger.error("GPU summary failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU analysis failed.")


@router.get("/gpu/inventory")
async def get_gpu_inventory(
    provider: Optional[str] = None,
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Multi-cloud GPU inventory with optional provider filter."""
    try:
        from ..core.gpu_service import GpuService
        resources = await db.get_resources(user.id, integration_id)
        service = GpuService()
        report = service.get_gpu_summary(resources, integration_id)
        gpu_resources = report.get("gpu_resources", [])
        if provider:
            gpu_resources = [r for r in gpu_resources if r.get("provider") == provider.lower()]
        return {
            "gpu_resources": gpu_resources,
            "total_count": len(gpu_resources),
            "providers": list(set(r.get("provider", "unknown") for r in gpu_resources)),
        }
    except Exception as e:
        logger.error("GPU inventory failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU inventory failed.")


@router.get("/gpu/metrics/live")
async def get_gpu_metrics_live(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Current GPU metrics snapshot (last 5 min) for all user's GPU resources."""
    try:
        from ..core.gpu_metrics_store import GpuMetricsStore
        store = GpuMetricsStore(db)
        metrics = await store.get_all_live_metrics(user.id)
        return {"metrics": metrics, "count": len(metrics)}
    except Exception as e:
        logger.error("GPU live metrics failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU metrics unavailable.")


@router.get("/gpu/metrics/history")
async def get_gpu_metrics_history(
    resource_id: str,
    days: int = 7,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Historical GPU metrics for charting (daily averages)."""
    try:
        from ..core.gpu_metrics_store import GpuMetricsStore
        store = GpuMetricsStore(db)
        history = await store.get_history(resource_id, days=min(days, 90))
        return {"resource_id": resource_id, "days": days, "data": history}
    except Exception as e:
        logger.error("GPU metrics history failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU metrics history unavailable.")


@router.get("/gpu/forecast")
@cache_response(expire_seconds=300)
async def get_gpu_cost_forecast(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """GPU cost trajectory prediction (30-day and 90-day)."""
    try:
        from ..core.gpu_cost_forecast import GpuCostForecaster
        forecaster = GpuCostForecaster(db)
        return await forecaster.forecast(user.id, days=30)
    except Exception as e:
        logger.error("GPU forecast failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU forecast unavailable.")


@router.get("/gpu/workloads")
async def get_gpu_workloads(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """GPU workload classification summary across all instances."""
    try:
        from ..core.gpu_service import GpuService
        from ..core.gpu_metrics_store import GpuMetricsStore
        from ..adk.tools.gpu_tools import gpu_classify_workload

        resources = await db.get_resources(user.id)
        service = GpuService()
        report = service.get_gpu_summary(resources)
        store = GpuMetricsStore(db)

        classifications = []
        for gpu in report.get("gpu_resources", []):
            resource_id = gpu.get("id", "")
            history = await store.get_history(resource_id, days=7)
            daily_metrics = [h for h in history if h.get("sm_pct") is not None]
            classification = gpu_classify_workload(resource_id, daily_metrics)
            classifications.append({
                **classification,
                "name": gpu.get("name"),
                "instance_type": gpu.get("instance_type"),
                "provider": gpu.get("provider"),
                "monthly_cost": gpu.get("monthly_cost"),
            })

        return {"workloads": classifications, "count": len(classifications)}
    except Exception as e:
        logger.error("GPU workloads failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU workload classification failed.")


@router.get("/gpu/pricing")
@cache_response(expire_seconds=3600)
async def get_gpu_live_pricing(
    user: ClerkUser = Depends(get_current_user),
):
    """Live GPU pricing from all specialized clouds."""
    try:
        from ..core.gpu_pricing_service import GpuPricingService
        service = GpuPricingService()
        pricing = await service.get_all_gpu_pricing()
        return {"pricing": pricing}
    except Exception as e:
        logger.error("GPU pricing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU pricing unavailable.")


@router.post("/gpu/analyze")
async def trigger_gpu_analysis(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Trigger deep LLM-powered GPU analysis. Returns results inline."""
    try:
        from ..core.gpu_service import GpuService
        from ..core.gpu_workload_analyzer import GpuWorkloadAnalyzer

        resources = await db.get_resources(user.id)
        service = GpuService()
        summary = service.get_gpu_summary(resources)

        analyzer = GpuWorkloadAnalyzer()
        health_report = await analyzer.generate_health_report(summary)

        return {
            "summary": summary,
            "ai_health_report": health_report,
            "analysis_model": analyzer.model,
        }
    except Exception as e:
        logger.error("GPU analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="GPU analysis failed.")


# ─────────────────────────────────────────────────────────────────────────────
# API Intelligence
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/apis/summary")
@cache_response(expire_seconds=600)
async def get_api_summary(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Full API Intelligence report — ghost APIs, cache waste, shadow APIs, cost efficiency."""
    try:
        from ..core.api_intelligence import ApiIntelligenceService
        resources = await db.get_resources(user.id, integration_id)
        service = ApiIntelligenceService()
        return service.get_api_summary(resources, integration_id)
    except Exception as e:
        logger.error("API summary failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="API analysis failed.")


@router.get("/apis/inventory")
async def get_api_inventory(
    provider: Optional[str] = None,
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Multi-cloud API inventory with optional provider filter."""
    try:
        from ..core.api_intelligence import ApiIntelligenceService
        resources = await db.get_resources(user.id, integration_id)
        service = ApiIntelligenceService()
        report = service.get_api_summary(resources, integration_id)
        api_resources = report.get("api_resources", [])
        if provider:
            api_resources = [r for r in api_resources if r.get("provider") == provider.lower()]
        return {"api_resources": api_resources, "total_count": len(api_resources)}
    except Exception as e:
        logger.error("API inventory failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="API inventory failed.")


@router.get("/apis/ghost")
async def get_ghost_apis(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Ghost/idle APIs with fix commands."""
    try:
        from ..core.api_intelligence import ApiIntelligenceService
        resources = await db.get_resources(user.id, integration_id)
        service = ApiIntelligenceService()
        report = service.get_api_summary(resources, integration_id)
        return {"ghost_apis": report.get("ghost_apis", []), "count": report.get("ghost_api_count", 0)}
    except Exception as e:
        logger.error("Ghost APIs failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ghost API detection failed.")


@router.get("/apis/cost-per-request")
async def get_api_cost_per_request(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Cost efficiency ranking — most expensive APIs per 1K requests."""
    try:
        from ..core.api_intelligence import ApiIntelligenceService
        resources = await db.get_resources(user.id, integration_id)
        service = ApiIntelligenceService()
        report = service.get_api_summary(resources, integration_id)
        return {"ranking": report.get("cost_per_request_ranking", [])}
    except Exception as e:
        logger.error("API cost-per-request failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="API cost analysis failed.")


# ─────────────────────────────────────────────────────────────────────────────
# Multi-Cloud Comparison
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/multicloud/comparison")
async def get_multicloud_comparison(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Multi-cloud cost comparison for live-scanned resources.
    Groups resources by category and projects equivalent cost on
    AWS, GCP, and Azure using public rate-card multipliers.
    No extra cloud API calls.
    """
    try:
        from ..core.multicloud_comparison import build_multicloud_report

        resources = await db.get_resources(user.id, integration_id)
        if not integration_id:
            active_integration_ids = await _get_active_integration_ids(db, user.id)
            resources = [
                resource
                for resource in resources
                if str(resource.get("integration_id") or "").strip() in active_integration_ids
            ]
        if not resources:
            return {
                "source_provider": "UNKNOWN",
                "by_category": {},
                "recommended_moves": [],
                "total_current_spend": 0.0,
                "total_best_case_spend": 0.0,
                "total_potential_savings": 0.0,
                "savings_pct": 0.0,
                "current_total_spend": 0.0,
                "optimized_total_spend": 0.0,
                "monthly_delta": 0.0,
                "annual_delta": 0.0,
                "provider_scores": [],
                "migration_scatter": [],
                "roi_curve": [],
                "allocation_flow": {"nodes": [], "links": []},
                "disclaimer": (
                    "No resources found. Run a scan first to populate multi-cloud comparison."
                ),
            }

        # Determine provider from integrations
        provider = None
        if integration_id:
            integration = await db.get_integration(integration_id, user.id)
            if integration:
                provider = str(integration.get("provider") or "aws").lower()

        report = build_multicloud_report(resources, provider)
        return report
    except Exception as e:
        logger.error("Multi-cloud comparison failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Multi-cloud comparison failed.")


# ---------------------------------------------------------------------------
# Public (unauthenticated) bill scan endpoint — lead-generation tool
# ---------------------------------------------------------------------------

import threading as _threading
import time as _time
from collections import defaultdict as _defaultdict

_PUBLIC_SCAN_RATE_LIMIT = 5          # max requests
_PUBLIC_SCAN_WINDOW_SECONDS = 3600   # per hour
_PUBLIC_SCAN_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_PUBLIC_SCAN_PARSE_TIMEOUT = 60.0    # seconds

# Thread-safe in-memory rate limiter: ip -> list[timestamp]
_public_scan_ip_log: dict[str, list[float]] = _defaultdict(list)
_public_scan_lock = _threading.Lock()


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = _time.time()
    window_start = now - _PUBLIC_SCAN_WINDOW_SECONDS
    with _public_scan_lock:
        # Prune stale timestamps outside the current window
        _public_scan_ip_log[ip] = [
            ts for ts in _public_scan_ip_log[ip] if ts > window_start
        ]
        if len(_public_scan_ip_log[ip]) >= _PUBLIC_SCAN_RATE_LIMIT:
            return False
        _public_scan_ip_log[ip].append(now)
    return True


def _resolve_client_ip(request: Request) -> str:
    """Extract real client IP, honouring X-Forwarded-For from the Next.js proxy."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _compute_waste_grade(savings_amount: float, total_spend: float) -> tuple[str, str]:
    """Derive waste grade letter + label from savings-to-spend ratio."""
    if total_spend <= 0:
        return "C", "Unable to determine grade"
    ratio = savings_amount / total_spend
    if ratio < 0.05:
        return "A", "Excellent — minimal waste detected"
    if ratio < 0.15:
        return "B", "Good — small optimisations available"
    if ratio < 0.30:
        return "C", "Moderate — significant savings on the table"
    if ratio < 0.50:
        return "D", "Poor — high waste detected"
    return "F", "Critical — severe overspend detected"


def _redact_and_build_teaser(raw: dict[str, Any], rows_parsed: int) -> dict[str, Any]:
    """
    Apply the spec §3 redaction map and return the public teaser payload.

    Strips:
    - evidence_lines / raw source strings
    - how_to_fix arrays and remediation scripts
    - complete cross-cloud tables
    - resource IDs
    """
    total_spend = float(raw.get("total_spend") or 0)
    savings_amount = float(raw.get("savings_amount") or raw.get("existing_credits_and_savings") or 0)
    currency = str(raw.get("currency") or "USD").upper()
    provider = str(raw.get("provider") or "generic").lower()
    by_category: dict[str, float] = raw.get("by_category") or {}

    waste_grade, waste_grade_label = _compute_waste_grade(savings_amount, total_spend)

    # Savings range: ±20% band around the detected savings figure.
    # If no existing savings detected, estimate conservatively from spend.
    if savings_amount > 0:
        savings_min = round(savings_amount * 0.8, 2)
        savings_max = round(savings_amount * 1.2, 2)
    else:
        # Heuristic: 10–20% of spend is typically recoverable.
        savings_min = round(total_spend * 0.10, 2)
        savings_max = round(total_spend * 0.20, 2)

    # Build top-3 redacted findings from raw_services
    raw_services: list[dict[str, Any]] = raw.get("raw_services") or []
    top_findings: list[dict[str, Any]] = []
    for svc in raw_services[:3]:
        service_name = str(svc.get("service") or svc.get("Service") or "Unknown Service")
        cost = float(svc.get("cost") or svc.get("Cost") or 0)
        category = str(svc.get("category") or "Other")

        # Construct a generic, non-sensitive finding description.
        what_we_found = (
            f"{service_name} accounts for a significant portion of your bill. "
            "Our analysis detected usage patterns that indicate potential optimisation opportunities. "
            "Sign up to see specific resource IDs, utilisation metrics, and exact fix steps."
        )

        top_findings.append({
            "service": service_name,
            "what_we_found": what_we_found,
            "category": category,
            "estimated_impact": round(cost * 0.15, 2),  # conservative 15% waste estimate
            # Fully redacted per spec §3
            "how_to_fix": "SIGNUP_REQUIRED",
            "evidence_lines": [],
        })

    return {
        "provider_detected": provider,
        "total_analyzed_spend": total_spend,
        "currency": currency,
        "by_category": by_category,
        "waste_grade": waste_grade,
        "waste_grade_label": waste_grade_label,
        "estimated_monthly_savings_min": savings_min,
        "estimated_monthly_savings_max": savings_max,
        "top_findings_teaser": top_findings,
        "remediation_status": "SIGNUP_REQUIRED",
        "rows_parsed": rows_parsed,
        # client_scripts key intentionally absent (fully redacted)
    }


@router.post("/scan/public-upload")
async def public_bill_scan(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Publicly accessible, unauthenticated processing endpoint for lead-gen scans.

    - No auth required (bypasses Depends(get_current_user))
    - Rate-limited: max 5 scans per hour per IP
    - File processed in-memory only — never archived to GCS
    - Redacted response per spec §3: no resource IDs, no fix steps, no scripts
    """
    from ..bill_parser.parser import parse_bill

    # 1. Rate limiting
    client_ip = _resolve_client_ip(request)
    if not _check_rate_limit(client_ip):
        logger.warning(
            "Public scan rate limit exceeded for IP %s",
            client_ip,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Free scan limit reached ({_PUBLIC_SCAN_RATE_LIMIT} scans per hour). "
                "Please try again later or sign up for unlimited access."
            ),
            headers={"Retry-After": str(_PUBLIC_SCAN_WINDOW_SECONDS)},
        )

    # 2. File extension validation
    filename = file.filename or "bill.csv"
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in {"csv", "xlsx", "xls", "pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xlsx, .xls, and .pdf files are supported.",
        )

    # 3. Size validation — read exactly up to limit + 1 byte to detect oversized files
    content = await file.read(_PUBLIC_SCAN_MAX_BYTES + 1)
    if len(content) > _PUBLIC_SCAN_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Free tier files must be under {_PUBLIC_SCAN_MAX_BYTES // (1024 * 1024)} MB.",
        )

    # 4. Parse the bill in-memory (non-blocking, with timeout)
    try:
        raw_analysis = await asyncio.wait_for(
            asyncio.to_thread(parse_bill, content, filename),
            timeout=_PUBLIC_SCAN_PARSE_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(
            "Public scan parse timeout for IP=%s file=%s",
            client_ip,
            filename,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "Bill parsing took too long. "
                "Try uploading a CSV/Excel export, or a smaller text-based PDF."
            ),
        ) from exc
    except ValueError as parse_err:
        logger.warning(
            "Public scan parse error for IP=%s file=%s: %s",
            client_ip,
            filename,
            parse_err,
        )
        raise HTTPException(status_code=422, detail=str(parse_err)) from parse_err
    except Exception as exc:
        logger.error(
            "Unexpected public scan error for IP=%s file=%s: %s",
            client_ip,
            filename,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your bill.",
        ) from exc
    finally:
        # Explicitly delete the raw bytes buffer — privacy lifecycle.
        del content

    # 5. Apply redaction map and return teaser
    rows_parsed = int(raw_analysis.get("rows_parsed") or 0)
    redacted = _redact_and_build_teaser(raw_analysis, rows_parsed)
    logger.info(
        "Public scan complete: IP=%s provider=%s rows=%d grade=%s",
        client_ip,
        redacted.get("provider_detected"),
        rows_parsed,
        redacted.get("waste_grade"),
    )
    return redacted

