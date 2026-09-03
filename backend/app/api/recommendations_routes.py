import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..config import get_settings
from ..core.recommendation_ai_enrichment import (
    enqueue_recommendation_ai_jobs,
    get_ai_enrichment_run_quota,
    get_recommendation_ai_enrichment,
    run_recommendation_ai_enrichment_batch,
)
from ..core.recommendations import (
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_ID_PATTERN,
    RECOMMENDATION_LEDGER_COLLECTION,
    RECOMMENDATION_STATE_EVENTS_COLLECTION,
)
from ..core.provider_recommendations import (
    ProviderRecommendationError,
    ingest_azure_advisor_recommendations,
)
from ..core.savings_verification import (
    create_or_update_savings_verification,
    get_savings_verification,
    verify_recommendation_savings,
)
from ..db import MongoDBClient, get_db_client
from ..optimization.evidence_card_schemas import EvidenceCardData
from ..security import decrypt_integration_credentials
from ..workers.recommendation_ai_worker import drain_user_recommendation_ai_enrichment

logger = logging.getLogger(__name__)

recommendations_router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])

RecommendationState = Literal[
    "detected",
    "evidence_ready",
    "provider_checked",
    "ready_for_review",
    "approved",
    "dismissed",
    "implemented",
    "verifying",
    "verified_saved",
    "verified_no_savings",
    "expired",
    "superseded",
]

_ALLOWED_STATE_TRANSITIONS = set(RecommendationState.__args__)  # type: ignore[attr-defined]

RecommendationIdPath = Annotated[
    str,
    Path(
        min_length=28,
        max_length=28,
        pattern=RECOMMENDATION_ID_PATTERN,
        description="Canonical recommendation identifier",
    ),
]


class RecommendationRecordResponse(BaseModel):
    id: str
    integration_id: str
    provider: str
    resource_id: str
    cloud_resource_id: str
    resource_name: str
    resource_type: str
    region: str = ""
    recommendation_type: str
    action: str
    state: str
    severity: str
    confidence: float
    trust_score: int
    quality_status: str = "legacy_unassessed"
    quality_reasons: list[str] = Field(default_factory=list)
    risk_level: str
    effort: str
    description: str
    waste_reason: str = ""
    estimated_monthly_savings: float
    claimable_monthly_savings: float = 0.0
    savings_estimate_status: str = "withheld_unassessed"
    savings_calculation_method: str = "unknown"
    savings_estimate_reason: str = ""
    estimated_monthly_waste: float = 0.0
    savings_currency: Optional[str] = None
    cost_source: str
    pricing_basis: str
    pricing_computed_at: Optional[str] = None
    evidence_status: str
    provider_agreement_status: str
    ai_enrichment_status: str
    ai_enrichment_id: Optional[str] = None
    ai_enrichment_job_id: Optional[str] = None
    ai_enriched_at: Optional[str] = None
    ai_model: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_enrichment_error: Optional[str] = None
    source_systems: list[str] = Field(default_factory=list)
    pipeline_version: str
    detected_at: str
    implemented_at: Optional[str] = None
    verification_status: str = "not_started"
    verification_id: Optional[str] = None
    realized_monthly_savings: float = 0.0
    realized_savings_confidence: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationRecordResponse] = Field(default_factory=list)
    count: int


class RecommendationEvidenceResponse(BaseModel):
    id: str
    recommendation_id: str
    resource_id: str
    evidence_kind: str
    signal_name: str
    observed_value: Any = None
    threshold: Any = None
    description: str
    metric_window_start: Optional[str] = None
    metric_window_end: Optional[str] = None
    data_completeness: float = 0.0
    source_system: str
    collected_at: str


class RecommendationEvidenceListResponse(BaseModel):
    evidence: list[RecommendationEvidenceResponse] = Field(default_factory=list)
    count: int


class RecommendationStateUpdateRequest(BaseModel):
    state: RecommendationState
    reason: Optional[str] = None


class RecommendationStateEventResponse(BaseModel):
    id: str
    recommendation_id: str
    from_state: Optional[str] = None
    to_state: str
    actor_type: str
    actor_id: str
    reason: Optional[str] = None
    created_at: str


class RecommendationStateUpdateResponse(BaseModel):
    recommendation: RecommendationRecordResponse
    event: RecommendationStateEventResponse


class RecommendationSavingsVerificationResponse(BaseModel):
    id: str
    recommendation_id: str
    integration_id: str
    provider: str
    resource_id: str
    cloud_resource_id: str
    action: str
    status: str
    estimated_monthly_savings: float = 0.0
    baseline_window_start: Optional[str] = None
    baseline_window_end: Optional[str] = None
    post_window_start: Optional[str] = None
    post_window_end: Optional[str] = None
    baseline_monthly_cost: float = 0.0
    post_monthly_cost: float = 0.0
    realized_monthly_savings: float = 0.0
    realized_savings_confidence: float = 0.0
    measurement_source: str = "not_measured"
    explanation: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RecommendationAIEnrichmentResponse(BaseModel):
    id: str
    recommendation_id: str
    job_id: Optional[str] = None
    status: str
    summary: str = ""
    business_impact: str = ""
    evidence_narrative: str = ""
    remediation_steps: list[str] = Field(default_factory=list)
    risk_notes: str = ""
    rollback_plan: str = ""
    validation_plan: str = ""
    assumptions: list[str] = Field(default_factory=list)
    confidence_notes: str = ""
    evidence_ids_used: list[str] = Field(default_factory=list)
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    generated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RecommendationAIEnrichmentQueueRequest(BaseModel):
    force: bool = False


class RecommendationAIEnrichmentQueueResponse(BaseModel):
    queued: int = 0
    skipped: int = 0
    job_ids: list[str] = Field(default_factory=list)


class RecommendationAIEnrichmentRunRequest(BaseModel):
    limit: int = Field(default=1, ge=1, le=5)
    queue_pending: bool = True
    force_queue: bool = False
    queue_limit: int = Field(default=25, ge=1, le=100)
    background: bool = False


class RecommendationAIEnrichmentRunItemResponse(BaseModel):
    job_id: str
    recommendation_id: str
    status: str
    enrichment_id: Optional[str] = None
    error: Optional[str] = None


class RecommendationAIEnrichmentRunResponse(BaseModel):
    status: str
    message: Optional[str] = None
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    queued_before_run: int = 0
    background_started: bool = False
    results: list[RecommendationAIEnrichmentRunItemResponse] = Field(default_factory=list)


class ProviderRecommendationIngestRequest(BaseModel):
    integration_id: Optional[str] = None
    force_refresh: bool = False


class ProviderRecommendationIngestSummaryResponse(BaseModel):
    integration_id: str
    provider: str
    status: str
    fetched: int = 0
    stored: int = 0
    matched: int = 0
    provider_only_created: int = 0
    not_found_marked: int = 0
    message: Optional[str] = None
    refresh_status: str = "not_requested"
    refreshed: bool = False
    refresh_message: Optional[str] = None


class ProviderRecommendationIngestTotalsResponse(BaseModel):
    integrations_checked: int = 0
    fetched: int = 0
    stored: int = 0
    matched: int = 0
    provider_only_created: int = 0
    not_found_marked: int = 0
    failed: int = 0
    refreshed: int = 0
    refresh_failed: int = 0


class ProviderRecommendationIngestResponse(BaseModel):
    summaries: list[ProviderRecommendationIngestSummaryResponse] = Field(default_factory=list)
    totals: ProviderRecommendationIngestTotalsResponse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


async def _load_owned_recommendation(
    *,
    db: MongoDBClient,
    user_id: str,
    recommendation_id: str,
) -> dict[str, Any]:
    """Load one recommendation and enforce its ownership invariant."""
    try:
        rows = await db.select(
            RECOMMENDATION_LEDGER_COLLECTION,
            filters={"user_id": user_id, "id": recommendation_id},
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Recommendation not found")

        recommendation = rows[0]
        if (
            str(recommendation.get("id") or "") != recommendation_id
            or str(recommendation.get("user_id") or "") != user_id
        ):
            logger.warning(
                "Recommendation ownership invariant failed for recommendation %s",
                recommendation_id,
            )
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return recommendation
    except HTTPException:
        raise
    except Exception as error:
        logger.error("_load_owned_recommendation failed: %s", error)
        raise


def _is_owned_recommendation_record(
    row: dict[str, Any],
    *,
    user_id: str,
    recommendation_id: Optional[str] = None,
) -> bool:
    """Return whether a selected recommendation record matches its requested scope."""
    if str(row.get("user_id") or "") != user_id:
        return False
    if recommendation_id is None:
        return True
    return str(row.get("recommendation_id") or "") == recommendation_id


def _require_owned_recommendation_record(
    row: dict[str, Any],
    *,
    user_id: str,
    recommendation_id: str,
    not_found_detail: str,
) -> dict[str, Any]:
    """Fail closed when a related recommendation query returns a foreign row."""
    if not _is_owned_recommendation_record(
        row,
        user_id=user_id,
        recommendation_id=recommendation_id,
    ):
        logger.warning(
            "Related recommendation ownership invariant failed for recommendation %s",
            recommendation_id,
        )
        raise HTTPException(status_code=404, detail=not_found_detail)
    return row


def _record_response(row: dict[str, Any]) -> RecommendationRecordResponse:
    return RecommendationRecordResponse(
        id=str(row.get("id") or ""),
        integration_id=str(row.get("integration_id") or ""),
        provider=str(row.get("provider") or ""),
        resource_id=str(row.get("resource_id") or ""),
        cloud_resource_id=str(row.get("cloud_resource_id") or row.get("resource_id") or ""),
        resource_name=str(row.get("resource_name") or "Unknown Resource"),
        resource_type=str(row.get("resource_type") or "Cloud Resource"),
        region=str(row.get("region") or ""),
        recommendation_type=str(row.get("recommendation_type") or ""),
        action=str(row.get("action") or ""),
        state=str(row.get("state") or "detected"),
        severity=str(row.get("severity") or "none"),
        confidence=_as_float(row.get("confidence")),
        trust_score=_as_int(row.get("trust_score")),
        quality_status=str(row.get("quality_status") or "legacy_unassessed"),
        quality_reasons=_string_list(row.get("quality_reasons")),
        risk_level=str(row.get("risk_level") or "unknown"),
        effort=str(row.get("effort") or "unknown"),
        description=str(row.get("description") or ""),
        waste_reason=str(row.get("waste_reason") or ""),
        estimated_monthly_savings=round(_as_float(row.get("estimated_monthly_savings")), 2),
        claimable_monthly_savings=round(_as_float(row.get("claimable_monthly_savings")), 2),
        savings_estimate_status=str(row.get("savings_estimate_status") or "withheld_unassessed"),
        savings_calculation_method=str(row.get("savings_calculation_method") or "unknown"),
        savings_estimate_reason=str(row.get("savings_estimate_reason") or ""),
        estimated_monthly_waste=round(_as_float(row.get("estimated_monthly_waste")), 2),
        savings_currency=str(row.get("savings_currency")) if row.get("savings_currency") else None,
        cost_source=str(row.get("cost_source") or "unknown"),
        pricing_basis=str(row.get("pricing_basis") or "unknown"),
        pricing_computed_at=str(row.get("pricing_computed_at")) if row.get("pricing_computed_at") else None,
        evidence_status=str(row.get("evidence_status") or "missing"),
        provider_agreement_status=str(row.get("provider_agreement_status") or "unknown"),
        ai_enrichment_status=str(row.get("ai_enrichment_status") or "not_requested"),
        ai_enrichment_id=str(row.get("ai_enrichment_id")) if row.get("ai_enrichment_id") else None,
        ai_enrichment_job_id=str(row.get("ai_enrichment_job_id")) if row.get("ai_enrichment_job_id") else None,
        ai_enriched_at=str(row.get("ai_enriched_at")) if row.get("ai_enriched_at") else None,
        ai_model=str(row.get("ai_model")) if row.get("ai_model") else None,
        ai_summary=str(row.get("ai_summary")) if row.get("ai_summary") else None,
        ai_enrichment_error=str(row.get("ai_enrichment_error")) if row.get("ai_enrichment_error") else None,
        source_systems=[
            str(item)
            for item in row.get("source_systems", [])
            if item is not None
        ] if isinstance(row.get("source_systems"), list) else [],
        pipeline_version=str(row.get("pipeline_version") or "unknown"),
        detected_at=str(row.get("detected_at") or ""),
        implemented_at=str(row.get("implemented_at")) if row.get("implemented_at") else None,
        verification_status=str(row.get("verification_status") or "not_started"),
        verification_id=str(row.get("verification_id")) if row.get("verification_id") else None,
        realized_monthly_savings=round(_as_float(row.get("realized_monthly_savings")), 2),
        realized_savings_confidence=round(_as_float(row.get("realized_savings_confidence")), 2),
        created_at=str(row.get("created_at")) if row.get("created_at") else None,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
    )


def _evidence_response(row: dict[str, Any]) -> RecommendationEvidenceResponse:
    return RecommendationEvidenceResponse(
        id=str(row.get("id") or ""),
        recommendation_id=str(row.get("recommendation_id") or ""),
        resource_id=str(row.get("resource_id") or ""),
        evidence_kind=str(row.get("evidence_kind") or ""),
        signal_name=str(row.get("signal_name") or ""),
        observed_value=row.get("observed_value"),
        threshold=row.get("threshold"),
        description=str(row.get("description") or ""),
        metric_window_start=str(row.get("metric_window_start")) if row.get("metric_window_start") else None,
        metric_window_end=str(row.get("metric_window_end")) if row.get("metric_window_end") else None,
        data_completeness=_as_float(row.get("data_completeness")),
        source_system=str(row.get("source_system") or ""),
        collected_at=str(row.get("collected_at") or ""),
    )


def _event_response(row: dict[str, Any]) -> RecommendationStateEventResponse:
    return RecommendationStateEventResponse(
        id=str(row.get("id") or ""),
        recommendation_id=str(row.get("recommendation_id") or ""),
        from_state=str(row.get("from_state")) if row.get("from_state") else None,
        to_state=str(row.get("to_state") or ""),
        actor_type=str(row.get("actor_type") or ""),
        actor_id=str(row.get("actor_id") or ""),
        reason=str(row.get("reason")) if row.get("reason") else None,
        created_at=str(row.get("created_at") or ""),
    )


def _verification_response(row: dict[str, Any]) -> RecommendationSavingsVerificationResponse:
    return RecommendationSavingsVerificationResponse(
        id=str(row.get("id") or ""),
        recommendation_id=str(row.get("recommendation_id") or ""),
        integration_id=str(row.get("integration_id") or ""),
        provider=str(row.get("provider") or ""),
        resource_id=str(row.get("resource_id") or ""),
        cloud_resource_id=str(row.get("cloud_resource_id") or row.get("resource_id") or ""),
        action=str(row.get("action") or ""),
        status=str(row.get("status") or "not_started"),
        estimated_monthly_savings=round(_as_float(row.get("estimated_monthly_savings")), 2),
        baseline_window_start=str(row.get("baseline_window_start")) if row.get("baseline_window_start") else None,
        baseline_window_end=str(row.get("baseline_window_end")) if row.get("baseline_window_end") else None,
        post_window_start=str(row.get("post_window_start")) if row.get("post_window_start") else None,
        post_window_end=str(row.get("post_window_end")) if row.get("post_window_end") else None,
        baseline_monthly_cost=round(_as_float(row.get("baseline_monthly_cost")), 2),
        post_monthly_cost=round(_as_float(row.get("post_monthly_cost")), 2),
        realized_monthly_savings=round(_as_float(row.get("realized_monthly_savings")), 2),
        realized_savings_confidence=round(_as_float(row.get("realized_savings_confidence")), 2),
        measurement_source=str(row.get("measurement_source") or "not_measured"),
        explanation=str(row.get("explanation") or ""),
        created_at=str(row.get("created_at")) if row.get("created_at") else None,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _ai_enrichment_response(row: dict[str, Any]) -> RecommendationAIEnrichmentResponse:
    return RecommendationAIEnrichmentResponse(
        id=str(row.get("id") or ""),
        recommendation_id=str(row.get("recommendation_id") or ""),
        job_id=str(row.get("job_id")) if row.get("job_id") else None,
        status=str(row.get("status") or "unknown"),
        summary=str(row.get("summary") or ""),
        business_impact=str(row.get("business_impact") or ""),
        evidence_narrative=str(row.get("evidence_narrative") or ""),
        remediation_steps=_string_list(row.get("remediation_steps")),
        risk_notes=str(row.get("risk_notes") or ""),
        rollback_plan=str(row.get("rollback_plan") or ""),
        validation_plan=str(row.get("validation_plan") or ""),
        assumptions=_string_list(row.get("assumptions")),
        confidence_notes=str(row.get("confidence_notes") or ""),
        evidence_ids_used=_string_list(row.get("evidence_ids_used")),
        model=str(row.get("model")) if row.get("model") else None,
        prompt_version=str(row.get("prompt_version")) if row.get("prompt_version") else None,
        generated_at=str(row.get("generated_at")) if row.get("generated_at") else None,
        created_at=str(row.get("created_at")) if row.get("created_at") else None,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
    )


def _sort_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "none": 5}
    return sorted(
        rows,
        key=lambda row: (
            severity_rank.get(str(row.get("severity") or "none").lower(), 9),
            -_as_int(row.get("trust_score")),
            -_as_float(row.get("estimated_monthly_savings")),
            str(row.get("created_at") or ""),
        ),
    )


def _provider_ingest_summary(row: dict[str, Any]) -> ProviderRecommendationIngestSummaryResponse:
    return ProviderRecommendationIngestSummaryResponse(
        integration_id=str(row.get("integration_id") or ""),
        provider=str(row.get("provider") or ""),
        status=str(row.get("status") or "unknown"),
        fetched=_as_int(row.get("fetched")),
        stored=_as_int(row.get("stored")),
        matched=_as_int(row.get("matched")),
        provider_only_created=_as_int(row.get("provider_only_created")),
        not_found_marked=_as_int(row.get("not_found_marked")),
        message=str(row.get("message")) if row.get("message") else None,
        refresh_status=str(row.get("refresh_status") or "not_requested"),
        refreshed=bool(row.get("refreshed")),
        refresh_message=str(row.get("refresh_message")) if row.get("refresh_message") else None,
    )


@recommendations_router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    integration_id: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationListResponse:
    """List the user's optimization recommendations from the ledger."""
    try:
        filters: dict[str, Any] = {"user_id": user.id}
        if integration_id:
            filters["integration_id"] = integration_id
        if state:
            filters["state"] = state

        rows = await db.select(RECOMMENDATION_LEDGER_COLLECTION, filters=filters)
        owned_rows = [
            row
            for row in rows
            if _is_owned_recommendation_record(row, user_id=user.id)
        ]
        if len(owned_rows) != len(rows):
            logger.warning("Discarded recommendation rows outside the authenticated user scope")
        records = [_record_response(row) for row in _sort_recommendations(owned_rows)]
        return RecommendationListResponse(recommendations=records, count=len(records))
    except Exception as error:
        logger.error("list_recommendations failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to load recommendations")


@recommendations_router.post("/provider-ingest", response_model=ProviderRecommendationIngestResponse)
async def ingest_provider_recommendations(
    payload: ProviderRecommendationIngestRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> ProviderRecommendationIngestResponse:
    """Ingest provider-native recommendations into the ledger."""
    try:
        integrations = [
            integration
            for integration in await db.get_user_integrations(user.id)
            if str(integration.get("user_id") or "") == user.id
        ]
        if payload.integration_id:
            integrations = [
                integration
                for integration in integrations
                if str(integration.get("id") or "") == payload.integration_id
            ]
            if not integrations:
                raise HTTPException(status_code=404, detail="Integration not found")

        azure_integrations = [
            integration
            for integration in integrations
            if str(integration.get("provider") or "").strip().lower() == "azure"
        ]
        if payload.integration_id and not azure_integrations:
            raise HTTPException(status_code=400, detail="Provider-native ingestion currently supports Azure integrations")

        summaries: list[ProviderRecommendationIngestSummaryResponse] = []
        for integration in azure_integrations:
            integration_id = str(integration.get("id") or "")
            try:
                credentials = decrypt_integration_credentials(integration)
                missing_fields = [
                    field_name
                    for field_name in ("tenant_id", "client_id", "client_secret", "subscription_id")
                    if not credentials.get(field_name)
                ]
                if missing_fields:
                    summaries.append(_provider_ingest_summary({
                        "integration_id": integration_id,
                        "provider": "azure",
                        "status": "skipped",
                        "message": "Azure credentials are incomplete; reconnect the integration",
                    }))
                    continue

                result = await ingest_azure_advisor_recommendations(
                    db=db,
                    user_id=user.id,
                    integration=integration,
                    credentials=credentials,
                    force_refresh=payload.force_refresh,
                )
                summaries.append(_provider_ingest_summary(result))
            except ProviderRecommendationError as error:
                summaries.append(_provider_ingest_summary({
                    "integration_id": integration_id,
                    "provider": "azure",
                    "status": "failed",
                    "message": str(error),
                    "refresh_status": "failed" if payload.force_refresh else "not_requested",
                    "refresh_message": str(error) if payload.force_refresh else None,
                }))
            except Exception as error:
                logger.error("ingest_provider_recommendations failed for integration %s: %s", integration_id, error)
                summaries.append(_provider_ingest_summary({
                    "integration_id": integration_id,
                    "provider": "azure",
                    "status": "failed",
                    "message": "Provider recommendation ingestion failed",
                }))

        totals = ProviderRecommendationIngestTotalsResponse(
            integrations_checked=len(azure_integrations),
            fetched=sum(item.fetched for item in summaries),
            stored=sum(item.stored for item in summaries),
            matched=sum(item.matched for item in summaries),
            provider_only_created=sum(item.provider_only_created for item in summaries),
            not_found_marked=sum(item.not_found_marked for item in summaries),
            failed=sum(1 for item in summaries if item.status == "failed"),
            refreshed=sum(1 for item in summaries if item.refreshed),
            refresh_failed=sum(1 for item in summaries if item.refresh_status == "failed"),
        )
        return ProviderRecommendationIngestResponse(summaries=summaries, totals=totals)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("ingest_provider_recommendations failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to ingest provider recommendations")


@recommendations_router.post("/ai-enrichment/run", response_model=RecommendationAIEnrichmentRunResponse)
async def run_ai_enrichment_batch(
    payload: RecommendationAIEnrichmentRunRequest,
    background_tasks: BackgroundTasks,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationAIEnrichmentRunResponse:
    """Run a small user-scoped batch of queued recommendation AI enrichments."""
    try:
        settings = get_settings()
        quota = await get_ai_enrichment_run_quota(db=db, user_id=user.id)
        if not quota.get("allowed"):
            raise HTTPException(
                status_code=429,
                detail=str(quota.get("message") or "AI enrichment quota exceeded"),
            )

        queued_before_run = 0
        if payload.queue_pending:
            queue_summary = await enqueue_recommendation_ai_jobs(
                db=db,
                user_id=user.id,
                force=payload.force_queue,
                model=settings.gemini_agent_model,
                queue_limit=payload.queue_limit,
            )
            queued_before_run = _as_int(queue_summary.get("queued"))

        if payload.background:
            if not settings.gemini_api_key:
                return RecommendationAIEnrichmentRunResponse(
                    status="skipped",
                    message="GEMINI_API_KEY is not configured",
                    processed=0,
                    succeeded=0,
                    failed=0,
                    skipped=0,
                    queued_before_run=queued_before_run,
                    background_started=False,
                    results=[],
                )
            background_tasks.add_task(
                drain_user_recommendation_ai_enrichment,
                user_id=user.id,
                max_jobs=payload.queue_limit,
                batch_size=payload.limit,
            )
            return RecommendationAIEnrichmentRunResponse(
                status="queued",
                message="AI enrichment queued for background processing",
                processed=0,
                succeeded=0,
                failed=0,
                skipped=0,
                queued_before_run=queued_before_run,
                background_started=True,
                results=[],
            )

        result = await run_recommendation_ai_enrichment_batch(
            db=db,
            user_id=user.id,
            limit=payload.limit,
            gemini_api_key=settings.gemini_api_key,
            model=settings.gemini_agent_model,
        )
        return RecommendationAIEnrichmentRunResponse(
            status=str(result.get("status") or "unknown"),
            message=str(result.get("message")) if result.get("message") else None,
            processed=_as_int(result.get("processed")),
            succeeded=_as_int(result.get("succeeded")),
            failed=_as_int(result.get("failed")),
            skipped=_as_int(result.get("skipped")),
            queued_before_run=queued_before_run,
            results=[
                RecommendationAIEnrichmentRunItemResponse(
                    job_id=str(item.get("job_id") or ""),
                    recommendation_id=str(item.get("recommendation_id") or ""),
                    status=str(item.get("status") or "unknown"),
                    enrichment_id=str(item.get("enrichment_id")) if item.get("enrichment_id") else None,
                    error=str(item.get("error")) if item.get("error") else None,
                )
                for item in result.get("results", [])
                if isinstance(item, dict)
            ],
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error("run_ai_enrichment_batch failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to run recommendation AI enrichment")


@recommendations_router.get("/{recommendation_id}", response_model=RecommendationRecordResponse)
async def get_recommendation(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationRecordResponse:
    """Get one recommendation from the user's ledger."""
    try:
        recommendation = await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        return _record_response(recommendation)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("get_recommendation failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to load recommendation")


@recommendations_router.get("/{recommendation_id}/ai-enrichment", response_model=RecommendationAIEnrichmentResponse)
async def get_ai_enrichment(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationAIEnrichmentResponse:
    """Get the stored AI enrichment for one recommendation."""
    try:
        await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )

        enrichment = await get_recommendation_ai_enrichment(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        if not enrichment:
            raise HTTPException(status_code=404, detail="AI enrichment not available")
        owned_enrichment = _require_owned_recommendation_record(
            enrichment,
            user_id=user.id,
            recommendation_id=recommendation_id,
            not_found_detail="AI enrichment not available",
        )
        return _ai_enrichment_response(owned_enrichment)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("get_ai_enrichment failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to load recommendation AI enrichment")


@recommendations_router.post("/{recommendation_id}/ai-enrichment/queue", response_model=RecommendationAIEnrichmentQueueResponse)
async def queue_ai_enrichment(
    recommendation_id: RecommendationIdPath,
    payload: RecommendationAIEnrichmentQueueRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationAIEnrichmentQueueResponse:
    """Queue AI enrichment for one recommendation."""
    try:
        await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )

        settings = get_settings()
        quota = await get_ai_enrichment_run_quota(db=db, user_id=user.id)
        if not quota.get("allowed"):
            raise HTTPException(
                status_code=429,
                detail=str(quota.get("message") or "AI enrichment quota exceeded"),
            )

        summary = await enqueue_recommendation_ai_jobs(
            db=db,
            user_id=user.id,
            recommendation_ids=[recommendation_id],
            force=payload.force,
            model=settings.gemini_agent_model,
            queue_limit=1,
        )
        job_ids = [
            str(job_id)
            for job_id in summary.get("job_ids", [])
            if job_id
        ] if isinstance(summary.get("job_ids"), list) else []
        return RecommendationAIEnrichmentQueueResponse(
            queued=_as_int(summary.get("queued")),
            skipped=_as_int(summary.get("skipped")),
            job_ids=job_ids,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error("queue_ai_enrichment failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to queue recommendation AI enrichment")


@recommendations_router.get("/{recommendation_id}/evidence", response_model=RecommendationEvidenceListResponse)
async def get_recommendation_evidence(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationEvidenceListResponse:
    """Get the evidence chain for a recommendation."""
    try:
        await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )

        rows = await db.select(
            RECOMMENDATION_EVIDENCE_COLLECTION,
            filters={"user_id": user.id, "recommendation_id": recommendation_id},
        )
        owned_rows = [
            row
            for row in rows
            if _is_owned_recommendation_record(
                row,
                user_id=user.id,
                recommendation_id=recommendation_id,
            )
        ]
        if len(owned_rows) != len(rows):
            logger.warning(
                "Discarded evidence rows outside the authenticated recommendation scope"
            )
        evidence = [_evidence_response(row) for row in owned_rows]
        return RecommendationEvidenceListResponse(evidence=evidence, count=len(evidence))
    except HTTPException:
        raise
    except Exception as error:
        logger.error("get_recommendation_evidence failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to load recommendation evidence")


@recommendations_router.get("/{recommendation_id}/evidence-card", response_model=EvidenceCardData)
async def get_recommendation_evidence_card(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> EvidenceCardData:
    """Get the Evidence Card and Safety Clearance Checklist for a recommendation."""
    try:
        recommendation = await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )

        from ..optimization.evidence_card_formatter import build_evidence_card

        return build_evidence_card(recommendation)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("get_recommendation_evidence_card failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to generate recommendation evidence card")


@recommendations_router.get("/{recommendation_id}/verification", response_model=RecommendationSavingsVerificationResponse)
async def get_recommendation_verification(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationSavingsVerificationResponse:
    """Get savings verification for one recommendation."""
    try:
        await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )

        verification = await get_savings_verification(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        if not verification:
            raise HTTPException(status_code=404, detail="Savings verification not started")
        owned_verification = _require_owned_recommendation_record(
            verification,
            user_id=user.id,
            recommendation_id=recommendation_id,
            not_found_detail="Savings verification not started",
        )
        return _verification_response(owned_verification)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("get_recommendation_verification failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to load savings verification")


@recommendations_router.post("/{recommendation_id}/verification/run", response_model=RecommendationSavingsVerificationResponse)
async def run_recommendation_verification(
    recommendation_id: RecommendationIdPath,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationSavingsVerificationResponse:
    """Run realized savings verification for one recommendation."""
    try:
        await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        verification = await verify_recommendation_savings(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        owned_verification = _require_owned_recommendation_record(
            verification,
            user_id=user.id,
            recommendation_id=recommendation_id,
            not_found_detail="Savings verification not started",
        )
        return _verification_response(owned_verification)
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error("run_recommendation_verification failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to run savings verification")


@recommendations_router.post("/{recommendation_id}/state", response_model=RecommendationStateUpdateResponse)
async def update_recommendation_state(
    recommendation_id: RecommendationIdPath,
    payload: RecommendationStateUpdateRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> RecommendationStateUpdateResponse:
    """Update the human workflow state for a recommendation."""
    try:
        if payload.state not in _ALLOWED_STATE_TRANSITIONS:
            raise HTTPException(status_code=400, detail="Invalid recommendation state")

        current = await _load_owned_recommendation(
            db=db,
            user_id=user.id,
            recommendation_id=recommendation_id,
        )
        from_state = str(current.get("state") or "detected")
        now = _utc_now_iso()
        ledger_update: dict[str, Any] = {
            "state": payload.state,
            "state_reason": payload.reason,
            "state_updated_at": now,
        }
        if payload.state == "implemented":
            ledger_update["implemented_at"] = now
            ledger_update["verification_status"] = "collecting_post_window"

        updated_rows = await db.update(
            RECOMMENDATION_LEDGER_COLLECTION,
            ledger_update,
            {"user_id": user.id, "id": recommendation_id},
        )
        if not updated_rows:
            raise HTTPException(status_code=404, detail="Recommendation not found")

        updated = updated_rows[0]
        if (
            str(updated.get("id") or "") != recommendation_id
            or str(updated.get("user_id") or "") != user.id
        ):
            logger.warning(
                "Recommendation ownership invariant failed after update for recommendation %s",
                recommendation_id,
            )
            raise HTTPException(status_code=404, detail="Recommendation not found")

        event = {
            "id": f"{recommendation_id}_{payload.state}_{now}",
            "user_id": user.id,
            "recommendation_id": recommendation_id,
            "from_state": from_state,
            "to_state": payload.state,
            "actor_type": "user",
            "actor_id": user.id,
            "reason": payload.reason,
            "created_at": now,
        }
        inserted = await db.insert(RECOMMENDATION_STATE_EVENTS_COLLECTION, event)
        if payload.state == "implemented":
            verification: Optional[dict[str, Any]] = None
            try:
                verification = await create_or_update_savings_verification(
                    db=db,
                    user_id=user.id,
                    recommendation=updated,
                )
                updated = await _load_owned_recommendation(
                    db=db,
                    user_id=user.id,
                    recommendation_id=recommendation_id,
                )
            except Exception as error:
                logger.error("Savings verification bootstrap failed for %s: %s", recommendation_id, error)
                if verification:
                    updated = {
                        **updated,
                        "verification_status": verification.get("status"),
                        "verification_id": verification.get("id"),
                    }
        return RecommendationStateUpdateResponse(
            recommendation=_record_response(updated),
            event=_event_response(inserted[0] if inserted else event),
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error("update_recommendation_state failed: %s", error)
        raise HTTPException(status_code=500, detail="Failed to update recommendation state")
