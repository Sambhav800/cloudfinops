import logging
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..auth.user_profile import resolve_user_email, resolve_user_full_name
from ..core.audit import log_audit_event
from ..core.budget_events import sync_budget_events_for_user
from ..core.commitment_engine import commitment_engine, CommitmentPortfolioSnapshot
from ..core.commitment_recommendations import (
    CommitmentRecommendationResult,
    CommitmentScopeNotFoundError,
    get_commitment_recommendation_result,
)
from ..core.finance import (
    DEFAULT_FINANCE_ALERT_THRESHOLDS,
    DEFAULT_REPORT_CADENCE,
    DISPLAY_CURRENCY,
    build_account_forecast_drivers,
    build_forecast_summary,
    normalize_finance_settings,
    redact_finance_settings_for_audit,
)
from ..db import MongoDBClient, get_db_client

finance_router = APIRouter(prefix="/api/finance", tags=["Finance"])
logger = logging.getLogger(__name__)


class FinanceSpendHistoryPoint(BaseModel):
    spend_date: str
    amount: float
    currency: str = DISPLAY_CURRENCY


class FinanceSpendHistoryResponse(BaseModel):
    scope: str
    integration_id: Optional[str] = None
    currency: str
    history: List[FinanceSpendHistoryPoint]
    count: int
    days_requested: int


class FinanceForecastDriver(BaseModel):
    dimension: str
    key: str
    delta_amount: float


class FinanceForecastResponse(BaseModel):
    scope: str
    integration_id: Optional[str] = None
    as_of: str
    currency: str
    history_days_used: int
    forecast_method: str
    forecast_stable: bool
    actual_mtd_spend: float
    forecast_eom_spend: float
    budget_limit: Optional[float] = None
    budget_source: str
    variance_amount: Optional[float] = None
    variance_pct: Optional[float] = None
    status: str
    trend: str
    drivers: List[FinanceForecastDriver] = Field(default_factory=list)
    message: Optional[str] = None


class FinanceCommitmentsResponse(CommitmentPortfolioSnapshot):
    """Persisted inventory and its measurement completeness."""


class FinanceCommitmentRecommendationResponse(CommitmentRecommendationResult):
    """Provider-backed purchase estimates; no synthetic discount scenarios."""


class FinanceBudgetEventResponse(BaseModel):
    id: str
    scope: Literal["portfolio", "integration"]
    integration_id: Optional[str] = None
    provider: Optional[str] = None
    account_name: Optional[str] = None
    event_type: Literal["approaching_budget", "forecasted_over_budget", "over_budget", "recovered"]
    severity: Literal["warning", "critical", "info"]
    title: str
    message: str
    current_status: str
    previous_status: Optional[str] = None
    currency: str
    budget_limit: Optional[float] = None
    budget_source: str
    actual_mtd_spend: float
    forecast_eom_spend: float
    variance_amount: Optional[float] = None
    variance_pct: Optional[float] = None
    created_at: str


class FinanceBudgetEventsResponse(BaseModel):
    events: List[FinanceBudgetEventResponse] = Field(default_factory=list)
    count: int


class FinanceBudgetEventsSyncResponse(BaseModel):
    events_created: int


class FinanceAlertThresholdsResponse(BaseModel):
    warning_pct: float = DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"]
    critical_pct: float = DEFAULT_FINANCE_ALERT_THRESHOLDS["critical_pct"]


class FinanceSettingsResponse(BaseModel):
    portfolio_budget_limit: Optional[float] = None
    report_recipients: List[str] = Field(default_factory=list)
    report_cadence: Literal["manual", "weekly", "monthly"] = DEFAULT_REPORT_CADENCE
    alert_thresholds: FinanceAlertThresholdsResponse = Field(
        default_factory=FinanceAlertThresholdsResponse,
    )


class FinanceAlertThresholdsUpdate(BaseModel):
    warning_pct: Optional[float] = Field(default=None, ge=1, le=100)
    critical_pct: Optional[float] = Field(default=None, ge=1, le=200)


class FinanceSettingsUpdate(BaseModel):
    portfolio_budget_limit: Optional[float] = Field(default=None, ge=0)
    report_recipients: Optional[List[str]] = None
    report_cadence: Optional[Literal["manual", "weekly", "monthly"]] = None
    alert_thresholds: Optional[FinanceAlertThresholdsUpdate] = None


async def _load_user_finance_settings(
    *,
    user_id: str,
    db: MongoDBClient,
) -> Dict[str, object]:
    users = await db.select("users", filters={"id": user_id})
    if not users:
        return normalize_finance_settings({})

    return normalize_finance_settings(users[0].get("finance_settings"))


async def _resolve_finance_scope(
    *,
    scope: str,
    integration_id: Optional[str],
    finance_settings: Optional[Dict[str, object]],
    user: ClerkUser,
    db: MongoDBClient,
) -> tuple[Optional[str], float | None, str]:
    normalized_scope = scope.strip().lower()
    if normalized_scope not in {"portfolio", "integration"}:
        raise HTTPException(status_code=400, detail="scope must be either 'portfolio' or 'integration'")

    if normalized_scope == "integration":
        if not integration_id:
            raise HTTPException(status_code=400, detail="integration_id is required when scope='integration'")

        integration = await db.get_integration(integration_id, user.id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        budget_limit = integration.get("monthly_budget_limit")
        if isinstance(budget_limit, (int, float)) and budget_limit > 0:
            return integration_id, float(budget_limit), "integration"
        return integration_id, None, "none"

    portfolio_budget_limit = finance_settings.get("portfolio_budget_limit") if isinstance(finance_settings, dict) else None
    if isinstance(portfolio_budget_limit, (int, float)) and float(portfolio_budget_limit) > 0:
        return None, round(float(portfolio_budget_limit), 2), "portfolio_setting"

    integrations = await db.get_user_integrations(user.id)
    active_integrations = [
        integration
        for integration in integrations
        if str(integration.get("status") or "").lower() == "active"
    ]
    positive_limits = [
        float(integration.get("monthly_budget_limit"))
        for integration in active_integrations
        if isinstance(integration.get("monthly_budget_limit"), (int, float)) and float(integration.get("monthly_budget_limit")) > 0
    ]

    if positive_limits:
        return None, round(sum(positive_limits), 2), "portfolio_sum"
    return None, None, "none"


@finance_router.get("/settings", response_model=FinanceSettingsResponse)
async def get_finance_settings(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    settings = await _load_user_finance_settings(user_id=user.id, db=db)
    return FinanceSettingsResponse(**settings)


@finance_router.post("/budget-events/sync", response_model=FinanceBudgetEventsSyncResponse)
async def sync_finance_budget_events(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    events = await sync_budget_events_for_user(
        user_id=user.id,
        db=db,
        deliver=False,
    )
    return FinanceBudgetEventsSyncResponse(events_created=len(events))


@finance_router.get("/budget-events", response_model=FinanceBudgetEventsResponse)
async def get_finance_budget_events(
    scope: Optional[Literal["portfolio", "integration"]] = Query(None),
    integration_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    if integration_id:
        integration = await db.get_integration(integration_id, user.id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

    events = await db.get_budget_events(
        user.id,
        scope=scope,
        integration_id=integration_id,
        limit=limit,
    )
    return FinanceBudgetEventsResponse(
        events=[FinanceBudgetEventResponse(**event) for event in events],
        count=len(events),
    )


@finance_router.put("/settings", response_model=FinanceSettingsResponse)
async def update_finance_settings(
    payload: FinanceSettingsUpdate,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    current_settings = await _load_user_finance_settings(user_id=user.id, db=db)
    patch = payload.model_dump(exclude_unset=True)

    if not patch:
        return FinanceSettingsResponse(**current_settings)

    merged_settings = dict(current_settings)
    if "portfolio_budget_limit" in patch:
        merged_settings["portfolio_budget_limit"] = patch["portfolio_budget_limit"]
    if "report_recipients" in patch:
        merged_settings["report_recipients"] = patch["report_recipients"] or []
    if "report_cadence" in patch and patch["report_cadence"]:
        merged_settings["report_cadence"] = patch["report_cadence"]

    if "alert_thresholds" in patch and isinstance(patch["alert_thresholds"], dict):
        current_thresholds = current_settings.get("alert_thresholds")
        merged_thresholds = dict(current_thresholds) if isinstance(current_thresholds, dict) else {}
        for key, value in patch["alert_thresholds"].items():
            if value is not None:
                merged_thresholds[key] = value
        merged_settings["alert_thresholds"] = merged_thresholds

    merged_thresholds = merged_settings.get("alert_thresholds")
    if isinstance(merged_thresholds, dict):
        warning_pct = merged_thresholds.get("warning_pct")
        critical_pct = merged_thresholds.get("critical_pct")
        if (
            isinstance(warning_pct, (int, float))
            and isinstance(critical_pct, (int, float))
            and float(critical_pct) < float(warning_pct)
        ):
            raise HTTPException(
                status_code=422,
                detail="Critical threshold must be greater than or equal to the warning threshold.",
            )

    normalized_settings = normalize_finance_settings(merged_settings)

    user_patch: Dict[str, object] = {
        "id": user.id,
        "finance_settings": normalized_settings,
    }
    email = resolve_user_email(user)
    full_name = resolve_user_full_name(user)
    if isinstance(email, str) and email.strip():
        user_patch["email"] = email.strip()
        user_patch["email_lower"] = email.strip().casefold()
    if isinstance(user.first_name, str) and user.first_name.strip():
        user_patch["first_name"] = user.first_name.strip()
    if isinstance(user.last_name, str) and user.last_name.strip():
        user_patch["last_name"] = user.last_name.strip()
    if isinstance(full_name, str) and full_name.strip():
        user_patch["full_name"] = full_name.strip()

    await db.upsert(
        "users",
        user_patch,
    )
    await log_audit_event(
        user_id=user.id,
        action_type="FINANCE_SETTINGS_UPDATED",
        resource_target=f"user:{user.id}:finance_settings",
        metadata=redact_finance_settings_for_audit(normalized_settings),
    )

    return FinanceSettingsResponse(**normalized_settings)


@finance_router.get("/spend-history", response_model=FinanceSpendHistoryResponse)
async def get_finance_spend_history(
    scope: str = Query("portfolio"),
    integration_id: Optional[str] = Query(None),
    days: int = Query(60, ge=1, le=365),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    resolved_integration_id, _, _ = await _resolve_finance_scope(
        scope=scope,
        integration_id=integration_id,
        finance_settings=None,
        user=user,
        db=db,
    )
    history = await db.get_daily_spend_history(
        user.id,
        integration_id=resolved_integration_id,
        days=days,
    )
    currency = DISPLAY_CURRENCY
    if history:
        currency = str(history[-1].get("currency") or DISPLAY_CURRENCY)

    return FinanceSpendHistoryResponse(
        scope=scope.strip().lower(),
        integration_id=resolved_integration_id,
        currency=currency,
        history=[
            FinanceSpendHistoryPoint(
                spend_date=str(row.get("spend_date")),
                amount=round(float(row.get("amount") or 0), 2),
                currency=str(row.get("currency") or currency),
            )
            for row in history
        ],
        count=len(history),
        days_requested=days,
    )


@finance_router.get("/forecast", response_model=FinanceForecastResponse)
async def get_finance_forecast(
    scope: str = Query("portfolio"),
    integration_id: Optional[str] = Query(None),
    days: int = Query(60, ge=5, le=365),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    normalized_scope = scope.strip().lower()
    finance_settings = await _load_user_finance_settings(user_id=user.id, db=db)
    resolved_integration_id, budget_limit, budget_source = await _resolve_finance_scope(
        scope=normalized_scope,
        integration_id=integration_id,
        finance_settings=finance_settings,
        user=user,
        db=db,
    )
    history = await db.get_daily_spend_history(
        user.id,
        integration_id=resolved_integration_id,
        days=days,
    )
    summary = build_forecast_summary(
        history,
        budget_limit=budget_limit,
        budget_source=budget_source,
        scope=normalized_scope,
        integration_id=resolved_integration_id,
        warning_threshold_pct=float(
            (finance_settings.get("alert_thresholds") or {}).get(
                "warning_pct",
                DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"],
            )
        ),
    )

    if normalized_scope == "portfolio":
        integrations = await db.get_user_integrations(user.id)
        active_integrations = [
            integration
            for integration in integrations
            if str(integration.get("status") or "").lower() == "active"
        ]
        warning_threshold_pct = float(
            (finance_settings.get("alert_thresholds") or {}).get(
                "warning_pct",
                DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"],
            )
        )
        account_summaries = []
        for integration in active_integrations:
            current_integration_id = str(integration.get("id") or "").strip()
            if not current_integration_id:
                continue

            integration_history = await db.get_daily_spend_history(
                user.id,
                integration_id=current_integration_id,
                days=days,
            )
            integration_budget_limit = integration.get("monthly_budget_limit")
            normalized_budget_limit = (
                float(integration_budget_limit)
                if isinstance(integration_budget_limit, (int, float)) and float(integration_budget_limit) > 0
                else None
            )
            integration_summary = build_forecast_summary(
                integration_history,
                budget_limit=normalized_budget_limit,
                budget_source="integration" if normalized_budget_limit else "none",
                scope="integration",
                integration_id=current_integration_id,
                warning_threshold_pct=warning_threshold_pct,
            )
            account_summaries.append(
                {
                    "integration_id": current_integration_id,
                    "name": str(integration.get("name") or current_integration_id),
                    "provider": str(integration.get("provider") or ""),
                    "account_identifier": integration.get("account_identifier"),
                    "actual_mtd_spend": integration_summary.get("actual_mtd_spend"),
                    "forecast_eom_spend": integration_summary.get("forecast_eom_spend"),
                    "forecast_status": integration_summary.get("status"),
                }
            )

        summary["drivers"] = build_account_forecast_drivers(account_summaries)

    return FinanceForecastResponse(**summary)


@finance_router.get("/commitments", response_model=FinanceCommitmentsResponse)
async def get_finance_commitments(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> FinanceCommitmentsResponse:
    """Read commitment inventory without calling cloud providers on page load."""
    try:
        snapshot = await commitment_engine.get_portfolio_snapshot(user.id, db=db)
        return FinanceCommitmentsResponse(**snapshot.model_dump())
    except Exception as error:
        logger.error("Commitment inventory read failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Commitment inventory is temporarily unavailable") from error


@finance_router.get(
    "/commitment-recommendation",
    response_model=FinanceCommitmentRecommendationResponse,
)
async def get_commitment_recommendation(
    integration_id: Optional[str] = Query(None),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> FinanceCommitmentRecommendationResponse:
    """Read validated provider estimates from the same source used by the copilot."""
    try:
        result = await get_commitment_recommendation_result(db=db, user_id=user.id, integration_id=integration_id)
        return FinanceCommitmentRecommendationResponse(**result.model_dump())
    except CommitmentScopeNotFoundError as error:
        raise HTTPException(status_code=404, detail="Integration not found") from error
    except Exception as error:
        logger.error("Commitment recommendation read failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Commitment recommendations are temporarily unavailable") from error
