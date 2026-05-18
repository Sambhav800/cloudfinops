from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..core.finance import normalize_finance_settings
from ..core.reports import (
    SUPPORTED_REPORT_TYPES,
    build_report_record,
    resolve_report_period,
)
from ..db import MongoDBClient, get_db_client

reports_router = APIRouter(prefix="/api/reports", tags=["Reports"])


ReportType = Literal[
    "monthly_executive_summary",
    "budget_variance",
    "provider_spend_summary",
    "board_pack",
]


class ReportRecordResponse(BaseModel):
    id: str
    report_type: ReportType
    title: str
    summary: str
    status: str
    period_start: str
    period_end: str
    generated_at: str
    created_at: str
    currency: str
    file_size_bytes: int = 0
    delivery_channels: List[str] = Field(default_factory=list)
    delivery_status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class ReportsListResponse(BaseModel):
    reports: List[ReportRecordResponse] = Field(default_factory=list)
    count: int


class GenerateReportRequest(BaseModel):
    report_type: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


async def _load_active_integrations_history(
    *,
    user_id: str,
    integrations: List[Dict[str, Any]],
    db: MongoDBClient,
) -> Dict[str, List[Dict[str, Any]]]:
    history_by_integration: Dict[str, List[Dict[str, Any]]] = {}
    for integration in integrations:
        integration_id = str(integration.get("id") or "").strip()
        if not integration_id:
            continue
        history_by_integration[integration_id] = await db.get_daily_spend_history(
            user_id,
            integration_id=integration_id,
            days=365,
        )
    return history_by_integration


async def _load_user_finance_settings(
    *,
    user_id: str,
    db: MongoDBClient,
) -> Dict[str, Any]:
    users = await db.select("users", filters={"id": user_id})
    if not users:
        return normalize_finance_settings({})
    return normalize_finance_settings(users[0].get("finance_settings"))


@reports_router.get("", response_model=ReportsListResponse)
async def list_reports(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    rows = await db.select("reports", filters={"user_id": user.id})
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)

    reports: List[ReportRecordResponse] = []
    for row in rows:
        report_type = str(row.get("report_type") or "").strip()
        if report_type not in SUPPORTED_REPORT_TYPES:
            continue

        reports.append(
            ReportRecordResponse(
                id=str(row.get("id")),
                report_type=report_type,
                title=str(row.get("title") or "Generated Report"),
                summary=str(row.get("summary") or ""),
                status=str(row.get("status") or "ready"),
                period_start=str(row.get("period_start") or ""),
                period_end=str(row.get("period_end") or ""),
                generated_at=str(row.get("generated_at") or row.get("created_at") or ""),
                created_at=str(row.get("created_at") or row.get("generated_at") or ""),
                currency=str(row.get("currency") or "USD"),
                file_size_bytes=int(row.get("file_size_bytes") or 0),
                delivery_channels=[
                    str(channel)
                    for channel in row.get("delivery_channels", [])
                    if isinstance(channel, str) and channel.strip()
                ],
                delivery_status=str(row.get("delivery_status") or "available"),
                metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
                data=row.get("data") if isinstance(row.get("data"), dict) else {},
            )
        )

    return ReportsListResponse(reports=reports, count=len(reports))


@reports_router.post(
    "/generate",
    response_model=ReportRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    payload: GenerateReportRequest = Body(...),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    report_type = payload.report_type.strip().lower()
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="report_type must be one of: " + ", ".join(sorted(SUPPORTED_REPORT_TYPES)),
        )

    try:
        period_start, period_end = resolve_report_period(
            payload.start_date,
            payload.end_date,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    integrations = await db.get_user_integrations(user.id)
    active_integrations = [
        integration
        for integration in integrations
        if str(integration.get("status") or "").lower() == "active"
    ]
    if not active_integrations:
        raise HTTPException(status_code=400, detail="No active integrations found for this user")

    history_by_integration = await _load_active_integrations_history(
        user_id=user.id,
        integrations=active_integrations,
        db=db,
    )
    finance_settings = await _load_user_finance_settings(user_id=user.id, db=db)

    try:
        report_record = build_report_record(
            user_id=user.id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            integrations=active_integrations,
            history_by_integration=history_by_integration,
            portfolio_budget_limit=finance_settings.get("portfolio_budget_limit"),
            warning_threshold_pct=(finance_settings.get("alert_thresholds") or {}).get("warning_pct"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    inserted = await db.insert("reports", report_record)
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to persist report")

    created = inserted[0]
    return ReportRecordResponse(
        id=str(created.get("id")),
        report_type=str(created.get("report_type")),
        title=str(created.get("title") or "Generated Report"),
        summary=str(created.get("summary") or ""),
        status=str(created.get("status") or "ready"),
        period_start=str(created.get("period_start") or ""),
        period_end=str(created.get("period_end") or ""),
        generated_at=str(created.get("generated_at") or created.get("created_at") or ""),
        created_at=str(created.get("created_at") or created.get("generated_at") or ""),
        currency=str(created.get("currency") or "USD"),
        file_size_bytes=int(created.get("file_size_bytes") or 0),
        delivery_channels=[
            str(channel)
            for channel in created.get("delivery_channels", [])
            if isinstance(channel, str) and channel.strip()
        ],
        delivery_status=str(created.get("delivery_status") or "available"),
        metadata=created.get("metadata") if isinstance(created.get("metadata"), dict) else {},
        data=created.get("data") if isinstance(created.get("data"), dict) else {},
    )
