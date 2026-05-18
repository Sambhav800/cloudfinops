import logging
from typing import Any, Dict, List, Optional

from .finance import (
    DEFAULT_FINANCE_ALERT_THRESHOLDS,
    RISK_BUDGET_STATUSES,
    _to_float,
    build_forecast_summary,
    normalize_finance_settings,
)
from .notifications import send_slack_alert, send_whatsapp_alert

logger = logging.getLogger(__name__)


def _positive_budget_limit(value: Any) -> Optional[float]:
    amount = round(_to_float(value), 2)
    return amount if amount > 0 else None


def _format_currency(value: Optional[float], currency: str) -> str:
    if value is None:
        return "Not set"

    return f"{currency} {value:,.2f}"


async def _load_user_finance_settings(
    *,
    user_id: str,
    db: Any,
) -> Dict[str, Any]:
    users = await db.select("users", filters={"id": user_id})
    if not users:
        return normalize_finance_settings({})

    return normalize_finance_settings(users[0].get("finance_settings"))


def _resolve_portfolio_budget(
    *,
    integrations: List[Dict[str, Any]],
    finance_settings: Dict[str, Any],
) -> tuple[Optional[float], str]:
    configured_budget = _positive_budget_limit(finance_settings.get("portfolio_budget_limit"))
    if configured_budget is not None:
        return configured_budget, "portfolio_setting"

    summed_budget = round(
        sum(
            _to_float(integration.get("monthly_budget_limit"))
            for integration in integrations
            if _to_float(integration.get("monthly_budget_limit")) > 0
        ),
        2,
    )
    if summed_budget > 0:
        return summed_budget, "portfolio_sum"

    return None, "none"


def _resolve_event_type(
    *,
    current_status: str,
    previous_status: Optional[str],
) -> Optional[str]:
    if current_status in RISK_BUDGET_STATUSES and current_status != previous_status:
        return current_status

    if previous_status in RISK_BUDGET_STATUSES and current_status == "on_track":
        return "recovered"

    return None


def _resolve_event_severity(event_type: str) -> str:
    if event_type == "approaching_budget":
        return "warning"
    if event_type in {"forecasted_over_budget", "over_budget"}:
        return "critical"
    return "info"


def _resolve_notification_severity(event_type: str) -> str:
    if event_type == "approaching_budget":
        return "medium"
    if event_type in {"forecasted_over_budget", "over_budget"}:
        return "high"
    return "low"


def _build_scope_label(
    *,
    scope: str,
    integration: Optional[Dict[str, Any]],
) -> str:
    if scope == "portfolio" or not integration:
        return "Portfolio"

    name = str(
        integration.get("name")
        or integration.get("account_identifier")
        or integration.get("id")
        or "Cloud account"
    ).strip()
    provider = str(integration.get("provider") or "").strip().upper()
    return f"{name} ({provider})" if provider else name


def _build_budget_event_message(
    *,
    event_type: str,
    scope_label: str,
    summary: Dict[str, Any],
) -> str:
    currency = str(summary.get("currency") or "USD")
    forecast_eom_spend = round(_to_float(summary.get("forecast_eom_spend")), 2)
    budget_limit = _positive_budget_limit(summary.get("budget_limit"))
    variance_amount = summary.get("variance_amount")

    if event_type == "recovered":
        return (
            f"{scope_label} is back within budget. "
            f"Forecast EOM is {_format_currency(forecast_eom_spend, currency)}"
            + (
                f" against a budget of {_format_currency(budget_limit, currency)}."
                if budget_limit is not None
                else "."
            )
        )

    status_message = str(summary.get("message") or "").strip() or "Budget status changed."
    detail_suffix = (
        f" Forecast EOM: {_format_currency(forecast_eom_spend, currency)}"
        + (
            f" vs budget {_format_currency(budget_limit, currency)}"
            if budget_limit is not None
            else ""
        )
        + (
            f" ({'+' if _to_float(variance_amount) > 0 else ''}{_format_currency(_to_float(variance_amount), currency)} variance)."
            if budget_limit is not None and variance_amount is not None
            else "."
        )
    )
    return f"{status_message} {scope_label}.{detail_suffix}"


def build_budget_event_record(
    *,
    user_id: str,
    scope: str,
    summary: Dict[str, Any],
    previous_status: Optional[str],
    integration: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    current_status = str(summary.get("status") or "").strip().lower()
    event_type = _resolve_event_type(
        current_status=current_status,
        previous_status=(previous_status or "").strip().lower() or None,
    )
    if not event_type:
        return None

    scope_label = _build_scope_label(scope=scope, integration=integration)
    title_map = {
        "approaching_budget": f"{scope_label} is approaching budget",
        "forecasted_over_budget": f"{scope_label} is forecasted over budget",
        "over_budget": f"{scope_label} is over budget",
        "recovered": f"{scope_label} recovered to on-track budget status",
    }

    return {
        "user_id": user_id,
        "scope": scope,
        "integration_id": integration.get("id") if integration else None,
        "provider": str(integration.get("provider") or "").lower() if integration else None,
        "account_name": scope_label if scope == "integration" else None,
        "event_type": event_type,
        "severity": _resolve_event_severity(event_type),
        "title": title_map[event_type],
        "message": _build_budget_event_message(
            event_type=event_type,
            scope_label=scope_label,
            summary=summary,
        ),
        "current_status": current_status,
        "previous_status": previous_status,
        "currency": str(summary.get("currency") or "USD"),
        "budget_limit": summary.get("budget_limit"),
        "budget_source": str(summary.get("budget_source") or "none"),
        "actual_mtd_spend": round(_to_float(summary.get("actual_mtd_spend")), 2),
        "forecast_eom_spend": round(_to_float(summary.get("forecast_eom_spend")), 2),
        "variance_amount": (
            round(_to_float(summary.get("variance_amount")), 2)
            if summary.get("variance_amount") is not None
            else None
        ),
        "variance_pct": (
            round(_to_float(summary.get("variance_pct")), 2)
            if summary.get("variance_pct") is not None
            else None
        ),
        "metadata": {
            "trend": str(summary.get("trend") or "unknown"),
            "forecast_method": str(summary.get("forecast_method") or "unknown"),
            "history_days_used": int(summary.get("history_days_used") or 0),
        },
    }


def _build_budget_notification(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": event["user_id"],
        "resource_id": event.get("integration_id") or "portfolio",
        "type": "budget_event",
        "status": "pending",
        "recommendation": str(event.get("title") or "Budget status changed"),
        "action": "review",
        "metadata": {
            "description": str(event.get("message") or ""),
            "severity": _resolve_notification_severity(str(event.get("event_type") or "")),
            "scope": str(event.get("scope") or "portfolio"),
            "integration_id": event.get("integration_id"),
            "event_type": str(event.get("event_type") or ""),
            "current_status": str(event.get("current_status") or ""),
        },
    }


def _build_delivery_message(event: Dict[str, Any]) -> str:
    severity = str(event.get("severity") or "info").upper()
    title = str(event.get("title") or "Budget status changed")
    message = str(event.get("message") or "")
    return f"[{severity}] CloudFinOps Budget Alert\n{title}\n{message}"


async def _persist_budget_event_if_changed(
    *,
    db: Any,
    user_id: str,
    scope: str,
    summary: Dict[str, Any],
    integration: Optional[Dict[str, Any]] = None,
    deliver: bool = False,
) -> Optional[Dict[str, Any]]:
    if str(summary.get("status") or "").strip().lower() not in {*RISK_BUDGET_STATUSES, "on_track"}:
        return None

    latest_event = await db.get_latest_budget_event(
        user_id=user_id,
        scope=scope,
        integration_id=integration.get("id") if integration else None,
    )
    previous_status = (
        str(latest_event.get("current_status") or "").strip().lower()
        if latest_event
        else None
    )

    event = build_budget_event_record(
        user_id=user_id,
        scope=scope,
        summary=summary,
        previous_status=previous_status,
        integration=integration,
    )
    if not event:
        return None

    created = await db.create_budget_event(event)
    if created:
        try:
            await db.create_notifications([_build_budget_notification(created)])
        except Exception as error:
            logger.warning("Budget event notification persistence skipped: %s", error)

        if deliver and integration:
            delivery_message = _build_delivery_message(created)
            phone = str(integration.get("alert_phone_number") or "").strip()
            webhook = str(integration.get("alert_slack_webhook") or "").strip()

            if phone:
                try:
                    await send_whatsapp_alert(delivery_message, phone)
                except Exception as error:
                    logger.warning("Budget event WhatsApp delivery skipped: %s", error)
            if webhook:
                try:
                    await send_slack_alert(delivery_message, webhook)
                except Exception as error:
                    logger.warning("Budget event Slack delivery skipped: %s", error)

    return created


async def sync_budget_events_for_user(
    *,
    user_id: str,
    db: Any,
    days: int = 60,
    deliver: bool = False,
) -> List[Dict[str, Any]]:
    integrations = await db.get_user_integrations(user_id)
    active_integrations = [
        integration
        for integration in integrations
        if str(integration.get("status") or "").strip().lower() == "active"
    ]
    if not active_integrations:
        return []

    finance_settings = await _load_user_finance_settings(user_id=user_id, db=db)
    warning_threshold_pct = float(
        (finance_settings.get("alert_thresholds") or {}).get(
            "warning_pct",
            DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"],
        )
    )

    created_events: List[Dict[str, Any]] = []

    portfolio_budget_limit, portfolio_budget_source = _resolve_portfolio_budget(
        integrations=active_integrations,
        finance_settings=finance_settings,
    )
    portfolio_history = await db.get_daily_spend_history(user_id, days=days)
    portfolio_summary = build_forecast_summary(
        portfolio_history,
        budget_limit=portfolio_budget_limit,
        budget_source=portfolio_budget_source,
        scope="portfolio",
        warning_threshold_pct=warning_threshold_pct,
    )
    portfolio_event = await _persist_budget_event_if_changed(
        db=db,
        user_id=user_id,
        scope="portfolio",
        summary=portfolio_summary,
        deliver=False,
    )
    if portfolio_event:
        created_events.append(portfolio_event)

    for integration in active_integrations:
        integration_id = str(integration.get("id") or "").strip()
        if not integration_id:
            continue

        budget_limit = _positive_budget_limit(integration.get("monthly_budget_limit"))
        if budget_limit is None:
            continue

        history_rows = await db.get_daily_spend_history(
            user_id,
            integration_id=integration_id,
            days=days,
        )
        integration_summary = build_forecast_summary(
            history_rows,
            budget_limit=budget_limit,
            budget_source="integration",
            scope="integration",
            integration_id=integration_id,
            warning_threshold_pct=warning_threshold_pct,
        )
        integration_event = await _persist_budget_event_if_changed(
            db=db,
            user_id=user_id,
            scope="integration",
            summary=integration_summary,
            integration=integration,
            deliver=deliver,
        )
        if integration_event:
            created_events.append(integration_event)

    return created_events
