from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..auth.user_profile import resolve_user_email, resolve_user_full_name
from ..core.audit import log_audit_event
from ..core.budget_events import sync_budget_events_for_user
from ..core.commitment_engine import commitment_engine, CloudCommitment
from ..core.finance import (
    DEFAULT_FINANCE_ALERT_THRESHOLDS,
    DEFAULT_REPORT_CADENCE,
    aggregate_daily_spend_rows,
    build_account_forecast_drivers,
    build_forecast_summary,
    normalize_finance_settings,
    redact_finance_settings_for_audit,
)
from ..db import MongoDBClient, get_db_client

finance_router = APIRouter(prefix="/api/finance", tags=["Finance"])


class FinanceSpendHistoryPoint(BaseModel):
    spend_date: str
    amount: float
    currency: str = "USD"


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


class FinanceCommitmentsResponse(BaseModel):
    commitments: List[CloudCommitment]
    count: int


class FinanceCommitmentRecommendationScenario(BaseModel):
    label: str
    commitment_pct: int
    monthly_commitment_usd: float
    monthly_saving_usd: float
    annual_saving_usd: float
    effective_discount_pct: float
    over_commitment_risk_pct: float
    risk_level: Literal["Low", "Medium", "High"]
    term_years: int


class FinanceCommitmentRecommendationResponse(BaseModel):
    status: Literal["ready", "insufficient_history", "no_spend_data"]
    message: Optional[str] = None
    days_available: Optional[int] = None
    analysis_basis_days: Optional[int] = None
    avg_monthly_spend_usd: Optional[float] = None
    forecast_eom_spend_usd: Optional[float] = None
    forecast_method: Optional[str] = None
    forecast_stable: Optional[bool] = None
    spend_volatility_pct: Optional[float] = None
    compute_fraction_pct: Optional[float] = None
    safe_baseline_monthly_usd: Optional[float] = None
    scenarios: List[FinanceCommitmentRecommendationScenario] = Field(default_factory=list)
    recommended_scenario: Optional[FinanceCommitmentRecommendationScenario] = None
    important_notes: List[str] = Field(default_factory=list)
    aws_console_link: Optional[str] = None


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


_AWS_COMPUTE_SERVICE_KEYWORDS = ("ec2", "compute", "eks", "ecs", "lambda", "fargate")


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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
    currency = "USD"
    if history:
        currency = str(history[-1].get("currency") or "USD")

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
):
    """
    Retrieve all cloud commitments (AWS Savings Plans, Azure Reservations, GCP CUDs).
    """
    commitments = await commitment_engine.get_commitments(user.id)
    return FinanceCommitmentsResponse(
        commitments=commitments,
        count=len(commitments),
    )


@finance_router.get(
    "/commitment-recommendation",
    response_model=FinanceCommitmentRecommendationResponse,
)
async def get_commitment_recommendation(
    integration_id: Optional[str] = Query(None),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Generate Savings Plan / RI purchase recommendation
    based on historical AWS spend patterns.
    """
    target_integrations = []
    if integration_id:
        integration = await db.get_integration(integration_id, user.id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if str(integration.get("provider") or "").lower() != "aws":
            return FinanceCommitmentRecommendationResponse(
                status="no_spend_data",
                message="Savings Plan recommendations are available for AWS integrations only.",
            )
        target_integrations = [integration]
    else:
        integrations = await db.get_user_integrations(user.id)
        target_integrations = [
            integration
            for integration in integrations
            if str(integration.get("status") or "").lower() == "active"
            and str(integration.get("provider") or "").lower() == "aws"
        ]

    if not target_integrations:
        return FinanceCommitmentRecommendationResponse(
            status="no_spend_data",
            message="Connect an AWS account and run a scan to see Savings Plan recommendations.",
        )

    history_rows: List[Dict[str, object]] = []
    for integration in target_integrations:
        current_integration_id = str(integration.get("id") or "").strip()
        if not current_integration_id:
            continue
        history_rows.extend(
            await db.get_daily_spend_history(
                user.id,
                integration_id=current_integration_id,
                days=180,
            )
        )

    history = aggregate_daily_spend_rows(history_rows)
    if len(history) < 14:
        return FinanceCommitmentRecommendationResponse(
            status="insufficient_history",
            message="Need at least 14 days of spend history for reliable recommendations.",
            days_available=len(history),
        )

    amounts = [_safe_float(point.get("amount")) for point in history if point.get("amount") is not None]
    non_zero_amounts = [amount for amount in amounts if amount > 0]
    if not non_zero_amounts:
        return FinanceCommitmentRecommendationResponse(
            status="no_spend_data",
            message="No AWS spend data is available yet. Run a fresh scan to populate billing history.",
        )

    forecast_summary = build_forecast_summary(
        history,
        budget_limit=None,
        budget_source="none",
        scope="integration" if integration_id else "portfolio",
        integration_id=integration_id,
    )
    forecast_eom_spend = round(_safe_float(forecast_summary.get("forecast_eom_spend")), 2)

    avg_daily = sum(amounts) / len(amounts)
    avg_monthly = avg_daily * 30.44
    mean = avg_daily
    variance = sum((value - mean) ** 2 for value in amounts) / len(amounts)
    std_dev = variance ** 0.5
    cv = (std_dev / mean) if mean > 0 else 0.0

    if integration_id:
        resources = await db.get_resources(user.id, integration_id)
    else:
        resources = await db.get_resources(user.id)

    active_integration_ids = {
        str(integration.get("id") or "").strip()
        for integration in target_integrations
        if str(integration.get("id") or "").strip()
    }
    scoped_resources = [
        resource
        for resource in resources
        if str(resource.get("integration_id") or "").strip() in active_integration_ids
    ]
    compute_spend = sum(
        _safe_float(resource.get("cost"))
        for resource in scoped_resources
        if any(
            keyword in str(resource.get("service_type") or "").lower()
            for keyword in _AWS_COMPUTE_SERVICE_KEYWORDS
        )
    )
    total_resource_spend = sum(_safe_float(resource.get("cost")) for resource in scoped_resources)
    compute_fraction = (compute_spend / total_resource_spend) if total_resource_spend > 0 else 0.45

    historical_safe_baseline = max(0.0, (avg_daily - std_dev * 0.5) * 30.44)
    safe_baseline_monthly = historical_safe_baseline
    if forecast_eom_spend > 0:
        safe_baseline_monthly = min(historical_safe_baseline, forecast_eom_spend)

    sp_discount = 0.34
    sp_discount_3yr = 0.50

    def scenario(pct: float, discount: float, label: str, risk: Literal["Low", "Medium", "High"], years: int):
        committable = safe_baseline_monthly * pct
        on_demand_equivalent = committable / (1 - discount) if discount < 1 else committable
        monthly_saving = on_demand_equivalent * discount
        annual_saving = monthly_saving * 12
        over_commit_risk = max(0.0, (pct - (1 - cv)) / pct) if pct > 0 and cv < 1 else 0.5
        return FinanceCommitmentRecommendationScenario(
            label=label,
            commitment_pct=round(pct * 100),
            monthly_commitment_usd=round(committable, 2),
            monthly_saving_usd=round(monthly_saving, 2),
            annual_saving_usd=round(annual_saving, 2),
            effective_discount_pct=round(discount * 100, 1),
            over_commitment_risk_pct=round(over_commit_risk * 100, 1),
            risk_level=risk,
            term_years=years,
        )

    scenarios = [
        scenario(0.50, sp_discount, "Conservative", "Low", 1),
        scenario(0.70, sp_discount, "Recommended", "Medium", 1),
        scenario(0.85, sp_discount, "Aggressive", "High", 1),
        scenario(0.70, sp_discount_3yr, "3-Year Optimal", "Medium", 3),
    ]

    risk_safe_scenarios = [
        item
        for item in scenarios
        if item.over_commitment_risk_pct < 20
    ]
    best = max(
        risk_safe_scenarios,
        key=lambda item: item.annual_saving_usd,
        default=scenarios[0],
    )

    forecast_method = str(forecast_summary.get("forecast_method") or "moving_average")
    forecast_method_label = "Holt-Winters" if forecast_method == "holt_winters" else forecast_method.replace("_", " ").title()

    return FinanceCommitmentRecommendationResponse(
        status="ready",
        analysis_basis_days=len(history),
        avg_monthly_spend_usd=round(avg_monthly, 2),
        forecast_eom_spend_usd=forecast_eom_spend,
        forecast_method=forecast_method,
        forecast_stable=bool(forecast_summary.get("forecast_stable")),
        spend_volatility_pct=round(cv * 100, 1),
        compute_fraction_pct=round(compute_fraction * 100, 1),
        safe_baseline_monthly_usd=round(safe_baseline_monthly, 2),
        scenarios=scenarios,
        recommended_scenario=best,
        important_notes=[
            "These projections use your actual AWS spend history and published discount-rate assumptions.",
            "Savings Plans apply automatically to eligible EC2, Lambda, and Fargate usage.",
            "Actual savings depend on your specific instance families, regions, and utilization patterns.",
            "You execute the purchase directly in your AWS Console — CloudFinOps generates the analysis only.",
            f"Forecast anchor: {forecast_method_label} using {forecast_summary.get('history_days_used', len(history))} daily spend points.",
            f"Based on {len(history)} days of AWS spend history with {round(cv * 100, 1)}% volatility.",
        ],
        aws_console_link="https://console.aws.amazon.com/billing/home#/bills",
    )
