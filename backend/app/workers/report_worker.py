import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import resend
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.finance import DEFAULT_REPORT_CADENCE, normalize_finance_settings
from ..core.reports import build_report_record, resolve_scheduled_report_plan
from ..db import get_db_client

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")
_DEFAULT_REPORT_FROM = "CloudFinOps <reports@yourdomain.com>"


def _group_integrations_by_user(integrations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for integration in integrations:
        user_id = str(integration.get("user_id") or "").strip()
        integration_id = str(integration.get("id") or "").strip()
        if not user_id or not integration_id:
            continue
        grouped.setdefault(user_id, []).append(integration)
    return grouped


def _should_send_report_today(report_cadence: str, today: date) -> bool:
    cadence = str(report_cadence or DEFAULT_REPORT_CADENCE).strip().lower()
    if cadence == "manual":
        return False
    if cadence == "monthly":
        return today.day == 1
    return today.weekday() == 0


async def _resolve_report_delivery(user_id: str) -> tuple[List[str], str]:
    db = get_db_client()
    users = await db.select("users", filters={"id": user_id})
    if not users:
        return [], DEFAULT_REPORT_CADENCE

    user_row = users[0]
    finance_settings = normalize_finance_settings(user_row.get("finance_settings"))
    recipients = [
        str(recipient).strip()
        for recipient in finance_settings.get("report_recipients", [])
        if str(recipient).strip()
    ]
    cadence = str(finance_settings.get("report_cadence") or DEFAULT_REPORT_CADENCE)

    if recipients:
        return recipients, cadence

    email = user_row.get("email")
    if isinstance(email, str) and email.strip():
        return [email.strip()], cadence

    return [], cadence


async def _load_user_finance_settings(user_id: str) -> Dict[str, Any]:
    db = get_db_client()
    users = await db.select("users", filters={"id": user_id})
    if not users:
        return normalize_finance_settings({})
    return normalize_finance_settings(users[0].get("finance_settings"))


async def _load_active_integrations_history(
    *,
    user_id: str,
    integrations: List[Dict[str, Any]],
    db,
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


def _merge_delivery_channels(existing_channels: Any, new_channel: str) -> List[str]:
    merged: List[str] = []
    for candidate in list(existing_channels or []) + [new_channel]:
        normalized = str(candidate or "").strip()
        if not normalized or normalized in merged:
            continue
        merged.append(normalized)
    return merged


def _build_report_email_html(report: Dict[str, Any]) -> str:
    data = report.get("data") if isinstance(report.get("data"), dict) else {}
    portfolio = data.get("portfolio") if isinstance(data.get("portfolio"), dict) else {}
    highlights = [
        str(item).strip()
        for item in data.get("highlights", [])
        if str(item).strip()
    ]
    provider_breakdown = data.get("provider_breakdown")
    providers = provider_breakdown if isinstance(provider_breakdown, list) else []
    currency = str(report.get("currency") or "USD")

    def format_currency(value: Any) -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            amount = 0.0
        return f"{currency} {amount:,.2f}"

    rows = "".join(
        f"""
        <tr>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;">{str(item.get('provider') or 'unknown').upper()}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:right;">{format_currency(item.get('actual_period_spend'))}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:right;">{format_currency(item.get('forecast_eom_spend'))}</td>
        </tr>
        """
        for item in providers[:3]
    )

    highlight_items = "".join(
        f"<li style=\"margin-bottom:8px;\">{item}</li>"
        for item in highlights[:5]
    )

    return f"""
    <html>
        <body style="font-family:Arial,sans-serif;color:#111827;background:#f8fafc;padding:24px;">
            <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;padding:32px;">
                <p style="font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#6b7280;margin:0 0 8px;">CloudFinOps Executive Pack</p>
                <h1 style="margin:0 0 12px;font-size:28px;color:#0f172a;">{report.get('title') or 'Scheduled Report'}</h1>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#475569;">{report.get('summary') or ''}</p>

                <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:24px;">
                    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;">
                        <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.14em;">Actual Period Spend</div>
                        <div style="margin-top:10px;font-size:22px;font-weight:700;color:#0f172a;">{format_currency(portfolio.get('actual_period_spend'))}</div>
                    </div>
                    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;">
                        <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.14em;">Forecasted EOM</div>
                        <div style="margin-top:10px;font-size:22px;font-weight:700;color:#0f172a;">{format_currency(portfolio.get('forecast_eom_spend'))}</div>
                    </div>
                    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;">
                        <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.14em;">Budget Status</div>
                        <div style="margin-top:10px;font-size:18px;font-weight:700;color:#0f172a;">{str(portfolio.get('status') or 'unknown').replace('_', ' ').title()}</div>
                    </div>
                </div>

                <h2 style="margin:0 0 12px;font-size:18px;color:#0f172a;">Highlights</h2>
                <ul style="margin:0 0 24px;padding-left:18px;color:#334155;line-height:1.6;">
                    {highlight_items or '<li>No highlights available for this period yet.</li>'}
                </ul>

                <h2 style="margin:0 0 12px;font-size:18px;color:#0f172a;">Top Providers</h2>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                    <thead>
                        <tr style="background:#f8fafc;text-align:left;color:#475569;">
                            <th style="padding:10px 12px;">Provider</th>
                            <th style="padding:10px 12px;text-align:right;">Actual</th>
                            <th style="padding:10px 12px;text-align:right;">Forecast</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows or '<tr><td colspan="3" style="padding:12px;color:#64748b;">Provider breakdown is still gathering enough history.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </body>
    </html>
    """


async def _update_report_delivery_state(
    *,
    db,
    report: Dict[str, Any],
    user_id: str,
    delivery_status: str,
    delivery_channels: Optional[List[str]] = None,
    metadata_updates: Optional[Dict[str, Any]] = None,
) -> None:
    report_id = str(report.get("id") or "").strip()
    if not report_id:
        return

    current_metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    next_metadata = dict(current_metadata)
    if metadata_updates:
        next_metadata.update(metadata_updates)

    payload: Dict[str, Any] = {
        "delivery_status": delivery_status,
        "metadata": next_metadata,
    }
    if delivery_channels is not None:
        payload["delivery_channels"] = delivery_channels

    await db.update("reports", payload, {"id": report_id, "user_id": user_id})
    report.update(payload)


async def _get_or_create_scheduled_report(
    *,
    user_id: str,
    cadence: str,
    user_integrations: List[Dict[str, Any]],
    db,
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    plan = resolve_scheduled_report_plan(cadence, today=today)
    if not plan:
        return None

    report_type = str(plan["report_type"])
    period_start = plan["period_start"]
    period_end = plan["period_end"]
    existing = await db.select(
        "reports",
        filters={
            "user_id": user_id,
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )
    if existing:
        existing.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return existing[0]

    active_integrations = [
        integration
        for integration in user_integrations
        if str(integration.get("status") or "").lower() == "active"
    ]
    if not active_integrations:
        return None

    history_by_integration = await _load_active_integrations_history(
        user_id=user_id,
        integrations=active_integrations,
        db=db,
    )
    finance_settings = await _load_user_finance_settings(user_id)
    report_record = build_report_record(
        user_id=user_id,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        integrations=active_integrations,
        history_by_integration=history_by_integration,
        portfolio_budget_limit=finance_settings.get("portfolio_budget_limit"),
        warning_threshold_pct=(finance_settings.get("alert_thresholds") or {}).get("warning_pct"),
    )
    metadata = dict(report_record.get("metadata") or {})
    metadata.update({
        "scheduled": True,
        "scheduled_cadence": cadence,
    })
    report_record["metadata"] = metadata
    report_record["delivery_status"] = "pending_schedule"
    report_record["delivery_channels"] = ["in_app"]

    inserted = await db.insert("reports", report_record)
    return inserted[0] if inserted else None


async def generate_and_send_scheduled_reports():
    """
    Generates and persists backend-owned scheduled reports, then emails them.
    """
    logger.info("Running scheduled executive report generation...")
    try:
        db = get_db_client()
        integrations = await db.select("cloud_integrations")
        if not integrations:
            return

        today = datetime.now(timezone.utc).date()
        grouped_integrations = _group_integrations_by_user(integrations)

        for user_id, user_integrations in grouped_integrations.items():
            recipients, cadence = await _resolve_report_delivery(user_id)
            if not _should_send_report_today(cadence, today):
                logger.info("Skipping scheduled report for user %s: cadence=%s does not match today", user_id, cadence)
                continue

            report = await _get_or_create_scheduled_report(
                user_id=user_id,
                cadence=cadence,
                user_integrations=user_integrations,
                db=db,
                today=today,
            )
            if not report:
                logger.info("Skipping scheduled report for user %s: no active integrations available", user_id)
                continue

            if str(report.get("delivery_status") or "") == "sent":
                logger.info("Skipping scheduled report for user %s: report already delivered", user_id)
                continue

            if not recipients:
                await _update_report_delivery_state(
                    db=db,
                    report=report,
                    user_id=user_id,
                    delivery_status="skipped_no_recipients",
                    metadata_updates={"scheduled_delivery": "skipped_no_recipients"},
                )
                logger.info("Scheduled report kept in-app for user %s: no recipients configured", user_id)
                continue

            if not resend.api_key:
                await _update_report_delivery_state(
                    db=db,
                    report=report,
                    user_id=user_id,
                    delivery_status="email_unavailable",
                    metadata_updates={"scheduled_delivery": "email_unavailable"},
                )
                logger.warning("Resend API key missing; scheduled report left in-app for user %s", user_id)
                continue

            params: resend.Emails.SendParams = {
                "from": os.getenv("REPORTS_FROM_EMAIL", _DEFAULT_REPORT_FROM),
                "to": recipients,
                "subject": str(report.get("title") or "Your CloudFinOps Executive Report"),
                "html": _build_report_email_html(report),
            }

            try:
                resend.Emails.send(params)
                await _update_report_delivery_state(
                    db=db,
                    report=report,
                    user_id=user_id,
                    delivery_status="sent",
                    delivery_channels=_merge_delivery_channels(report.get("delivery_channels"), "email"),
                    metadata_updates={
                        "scheduled_delivery": "sent",
                        "scheduled_cadence": cadence,
                        "email_recipient_count": len(recipients),
                        "delivered_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                logger.info("Successfully sent scheduled report to user %s", user_id)
            except Exception as error:
                await _update_report_delivery_state(
                    db=db,
                    report=report,
                    user_id=user_id,
                    delivery_status="delivery_failed",
                    metadata_updates={
                        "scheduled_delivery": "delivery_failed",
                        "delivery_error": str(error),
                    },
                )
                logger.error("Failed to send scheduled report to user %s: %s", user_id, error)

    except Exception as error:
        logger.error("Error generating scheduled report: %s", error)


def start_report_worker(scheduler: AsyncIOScheduler):
    """
    Registers the report generation job.
    Called from the main anomaly_worker file to share the scheduler.
    """
    scheduler.add_job(
        generate_and_send_scheduled_reports,
        trigger=CronTrigger(hour=8, minute=0),
        id="scheduled_executive_report",
        replace_existing=True,
    )
    logger.info("Report worker registered for daily cadence checks at 8 AM.")
