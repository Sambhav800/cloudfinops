import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .finance import (
    DEFAULT_FINANCE_ALERT_THRESHOLDS,
    aggregate_daily_spend_rows,
    build_account_forecast_drivers,
    build_forecast_summary,
)

REPORT_TYPE_LABELS: Dict[str, str] = {
    "monthly_executive_summary": "Monthly Executive Summary",
    "budget_variance": "Budget Variance Report",
    "provider_spend_summary": "Provider Spend Summary",
    "board_pack": "Board Pack",
}

SUPPORTED_REPORT_TYPES = set(REPORT_TYPE_LABELS.keys())


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date_value(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def resolve_report_period(
    start_date_raw: Optional[str] = None,
    end_date_raw: Optional[str] = None,
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    today: Optional[date] = None,
) -> Tuple[date, date]:
    baseline = today or _utc_today()
    end_date_value = period_end if period_end is not None else end_date_raw
    start_date_value = period_start if period_start is not None else start_date_raw
    end_date = _parse_date_value(end_date_value) or baseline
    start_date = _parse_date_value(start_date_value) or end_date.replace(day=1)

    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if end_date > baseline:
        raise ValueError("end_date cannot be in the future")

    return start_date, end_date


def resolve_scheduled_report_plan(
    report_cadence: str,
    *,
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    baseline = today or _utc_today()
    cadence = str(report_cadence or "weekly").strip().lower()

    if cadence == "manual":
        return None

    if cadence == "monthly":
        current_month_start = baseline.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        return {
            "cadence": "monthly",
            "report_type": "board_pack",
            "period_start": previous_month_start,
            "period_end": previous_month_end,
        }

    return {
        "cadence": "weekly",
        "report_type": "monthly_executive_summary",
        "period_start": baseline.replace(day=1),
        "period_end": baseline,
    }


def _format_period_label(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.strftime("%b %d, %Y")
    if start_date.year == end_date.year and start_date.month == end_date.month:
        return f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    if start_date.year == end_date.year:
        return f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"


def _format_title_period(start_date: date, end_date: date) -> str:
    if start_date.day == 1 and start_date.year == end_date.year and start_date.month == end_date.month:
        return end_date.strftime("%b %Y")
    return _format_period_label(start_date, end_date)


def _format_currency(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _to_float(value: Any) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return 0.0
        return parsed
    except (TypeError, ValueError):
        return 0.0


def _positive_budget_limit(integration: Dict[str, Any]) -> Optional[float]:
    value = integration.get("monthly_budget_limit")
    if isinstance(value, (int, float)) and float(value) > 0:
        return round(float(value), 2)
    return None


def _filter_history_to_end(
    rows: List[Dict[str, Any]],
    end_date: date,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for row in rows or []:
        spend_date = _parse_date_value(row.get("spend_date"))
        if spend_date is None or spend_date > end_date:
            continue
        filtered.append(row)
    return filtered


def _sum_period_spend(
    rows: List[Dict[str, Any]],
    start_date: date,
    end_date: date,
) -> float:
    total = 0.0
    for row in rows or []:
        spend_date = _parse_date_value(row.get("spend_date"))
        if spend_date is None or spend_date < start_date or spend_date > end_date:
            continue
        total += _to_float(row.get("amount"))
    return round(total, 2)


def _report_status_from_forecast_status(status: str) -> str:
    return "attention_needed" if status == "insufficient_history" else "ready"


def _build_highlights(
    *,
    report_type: str,
    period_label: str,
    currency: str,
    portfolio_actual_period_spend: float,
    portfolio_forecast: Dict[str, Any],
    ready_accounts: int,
    total_accounts: int,
    at_risk_accounts: List[Dict[str, Any]],
    provider_rollups: List[Dict[str, Any]],
) -> List[str]:
    highlights = [
        (
            f"Portfolio spend for {period_label} is "
            f"{_format_currency(portfolio_actual_period_spend, currency)} across {total_accounts} active accounts."
        ),
        f"{ready_accounts} of {total_accounts} active accounts have enough history for forecast-grade reporting.",
    ]

    if portfolio_forecast.get("budget_limit"):
        highlights.append(
            "Portfolio forecast is "
            f"{_format_currency(_to_float(portfolio_forecast.get('forecast_eom_spend')), currency)} "
            f"against a budget of {_format_currency(_to_float(portfolio_forecast.get('budget_limit')), currency)}."
        )
    else:
        highlights.append("No portfolio budget ceiling is configured yet; budget variance is advisory only.")

    if provider_rollups:
        top_provider = provider_rollups[0]
        highlights.append(
            f"Top spend provider is {str(top_provider.get('provider') or 'unknown').upper()} "
            f"at {_format_currency(_to_float(top_provider.get('actual_period_spend')), currency)} "
            f"for the selected period."
        )

    if at_risk_accounts:
        top_risk = at_risk_accounts[0]
        highlights.append(
            f"{top_risk.get('name') or 'An account'} is the highest budget-risk account at "
            f"{_format_currency(_to_float(top_risk.get('variance_amount')), currency)} variance to forecast."
        )
    elif report_type == "budget_variance":
        highlights.append("No active accounts are currently forecasted above or near budget.")

    if report_type == "board_pack":
        highlights.append("Board Pack combines portfolio forecast, provider mix, and account-level budget exposure.")

    return highlights


def _build_summary(
    *,
    report_type: str,
    currency: str,
    total_accounts: int,
    ready_accounts: int,
    portfolio_actual_period_spend: float,
    portfolio_forecast: Dict[str, Any],
    provider_rollups: List[Dict[str, Any]],
    at_risk_accounts: List[Dict[str, Any]],
) -> str:
    forecast_value = _format_currency(_to_float(portfolio_forecast.get("forecast_eom_spend")), currency)
    actual_value = _format_currency(portfolio_actual_period_spend, currency)
    budget_limit = portfolio_forecast.get("budget_limit")
    budget_text = (
        _format_currency(_to_float(budget_limit), currency)
        if budget_limit
        else "no configured portfolio budget"
    )

    if report_type == "monthly_executive_summary":
        if str(portfolio_forecast.get("status") or "") == "insufficient_history":
            return (
                f"{ready_accounts} of {total_accounts} active accounts have enough spend history "
                f"for forecast-grade reporting right now."
            )
        return (
            f"{actual_value} tracked this period, with a month-end forecast of {forecast_value} "
            f"against {budget_text} across {total_accounts} active accounts."
        )

    if report_type == "budget_variance":
        return (
            f"{len(at_risk_accounts)} of {total_accounts} active accounts are forecasted over or near budget; "
            f"portfolio forecast is {forecast_value} against {budget_text}."
        )

    if report_type == "provider_spend_summary":
        if provider_rollups:
            top_provider = provider_rollups[0]
            return (
                f"{str(top_provider.get('provider') or 'unknown').upper()} leads spend at "
                f"{_format_currency(_to_float(top_provider.get('actual_period_spend')), currency)}, "
                f"with {ready_accounts} forecast-ready accounts in view."
            )
        return f"Provider mix is still collecting history; {ready_accounts} of {total_accounts} accounts are forecast-ready."

    return (
        f"Board-level portfolio view covering {total_accounts} active accounts, {ready_accounts} forecast-ready accounts, "
        f"and a current month-end forecast of {forecast_value}."
    )


def build_report_record(
    *,
    user_id: str,
    report_type: str,
    period_start: date,
    period_end: date,
    integrations: List[Dict[str, Any]],
    history_by_integration: Dict[str, List[Dict[str, Any]]],
    portfolio_budget_limit: Optional[float] = None,
    warning_threshold_pct: Optional[float] = None,
    generated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise ValueError("Unsupported report type")

    active_integrations = [
        integration
        for integration in integrations
        if str(integration.get("status") or "").lower() == "active"
    ]
    if not active_integrations:
        raise ValueError("No active integrations found for this user")

    integration_budget_limit = round(
        sum(_positive_budget_limit(integration) or 0.0 for integration in active_integrations),
        2,
    )
    configured_portfolio_budget = (
        round(float(portfolio_budget_limit), 2)
        if isinstance(portfolio_budget_limit, (int, float)) and float(portfolio_budget_limit) > 0
        else None
    )
    portfolio_budget = configured_portfolio_budget
    if portfolio_budget is None and integration_budget_limit > 0:
        portfolio_budget = integration_budget_limit

    portfolio_budget_source = "none"
    if configured_portfolio_budget is not None:
        portfolio_budget_source = "portfolio_setting"
    elif portfolio_budget is not None:
        portfolio_budget_source = "portfolio_sum"

    effective_warning_threshold = (
        float(warning_threshold_pct)
        if isinstance(warning_threshold_pct, (int, float))
        else DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"]
    )
    portfolio_history_seed: List[Dict[str, Any]] = []
    account_summaries: List[Dict[str, Any]] = []
    provider_rollup_map: Dict[str, Dict[str, Any]] = {}

    for integration in active_integrations:
        integration_id = str(integration.get("id") or "").strip()
        if not integration_id:
            continue

        provider = str(integration.get("provider") or "unknown").lower()
        name = str(integration.get("name") or f"{provider.upper()} integration")
        account_identifier = str(integration.get("account_identifier") or "").strip() or None
        history_rows = _filter_history_to_end(history_by_integration.get(integration_id, []), period_end)
        portfolio_history_seed.extend(history_rows)
        budget_limit = _positive_budget_limit(integration)
        forecast = build_forecast_summary(
            history_rows,
            budget_limit=budget_limit,
            budget_source="integration" if budget_limit else "none",
            scope="integration",
            integration_id=integration_id,
            as_of=period_end,
            warning_threshold_pct=effective_warning_threshold,
        )
        actual_period_spend = _sum_period_spend(history_rows, period_start, period_end)
        account_summary = {
            "integration_id": integration_id,
            "name": name,
            "provider": provider,
            "account_identifier": account_identifier,
            "actual_period_spend": actual_period_spend,
            "forecast_eom_spend": round(_to_float(forecast.get("forecast_eom_spend")), 2),
            "budget_limit": budget_limit,
            "variance_amount": forecast.get("variance_amount"),
            "variance_pct": forecast.get("variance_pct"),
            "forecast_status": str(forecast.get("status") or "unknown"),
            "history_days_used": int(forecast.get("history_days_used") or 0),
            "message": forecast.get("message"),
        }
        account_summaries.append(account_summary)

        provider_entry = provider_rollup_map.setdefault(
            provider,
            {
                "provider": provider,
                "actual_period_spend": 0.0,
                "forecast_eom_spend": 0.0,
                "budget_limit": 0.0,
                "active_integrations": 0,
                "ready_integrations": 0,
            },
        )
        provider_entry["actual_period_spend"] = round(
            provider_entry["actual_period_spend"] + actual_period_spend,
            2,
        )
        provider_entry["forecast_eom_spend"] = round(
            provider_entry["forecast_eom_spend"] + _to_float(forecast.get("forecast_eom_spend")),
            2,
        )
        provider_entry["budget_limit"] = round(
            provider_entry["budget_limit"] + (budget_limit or 0.0),
            2,
        )
        provider_entry["active_integrations"] += 1
        if account_summary["forecast_status"] != "insufficient_history":
            provider_entry["ready_integrations"] += 1

    account_summaries.sort(
        key=lambda item: (
            _to_float(item.get("variance_amount")),
            _to_float(item.get("actual_period_spend")),
        ),
        reverse=True,
    )

    portfolio_history = aggregate_daily_spend_rows(portfolio_history_seed)
    portfolio_forecast = build_forecast_summary(
        portfolio_history,
        budget_limit=portfolio_budget,
        budget_source=portfolio_budget_source,
        scope="portfolio",
        as_of=period_end,
        warning_threshold_pct=effective_warning_threshold,
    )
    portfolio_forecast["drivers"] = build_account_forecast_drivers(account_summaries)
    currency = str(portfolio_forecast.get("currency") or "USD")
    portfolio_actual_period_spend = _sum_period_spend(portfolio_history, period_start, period_end)

    provider_rollups: List[Dict[str, Any]] = []
    total_provider_spend = portfolio_actual_period_spend
    for provider, rollup in provider_rollup_map.items():
        actual_spend = _to_float(rollup.get("actual_period_spend"))
        variance_amount = None
        budget_limit = _to_float(rollup.get("budget_limit"))
        if budget_limit > 0:
            variance_amount = round(_to_float(rollup.get("forecast_eom_spend")) - budget_limit, 2)

        provider_rollups.append(
            {
                "provider": provider,
                "actual_period_spend": round(actual_spend, 2),
                "forecast_eom_spend": round(_to_float(rollup.get("forecast_eom_spend")), 2),
                "budget_limit": round(budget_limit, 2) if budget_limit > 0 else None,
                "variance_amount": variance_amount,
                "active_integrations": int(rollup.get("active_integrations") or 0),
                "ready_integrations": int(rollup.get("ready_integrations") or 0),
                "share_pct": round((actual_spend / total_provider_spend) * 100, 2) if total_provider_spend > 0 else None,
            }
        )
    provider_rollups.sort(key=lambda item: _to_float(item.get("actual_period_spend")), reverse=True)

    ready_accounts = len(
        [item for item in account_summaries if item.get("forecast_status") != "insufficient_history"]
    )
    at_risk_accounts = [
        item
        for item in account_summaries
        if str(item.get("forecast_status") or "") in {"forecasted_over_budget", "over_budget", "approaching_budget"}
    ]
    at_risk_accounts.sort(key=lambda item: _to_float(item.get("variance_amount")), reverse=True)

    period_label = _format_period_label(period_start, period_end)
    highlights = _build_highlights(
        report_type=report_type,
        period_label=period_label,
        currency=currency,
        portfolio_actual_period_spend=portfolio_actual_period_spend,
        portfolio_forecast=portfolio_forecast,
        ready_accounts=ready_accounts,
        total_accounts=len(account_summaries),
        at_risk_accounts=at_risk_accounts,
        provider_rollups=provider_rollups,
    )
    summary = _build_summary(
        report_type=report_type,
        currency=currency,
        total_accounts=len(account_summaries),
        ready_accounts=ready_accounts,
        portfolio_actual_period_spend=portfolio_actual_period_spend,
        portfolio_forecast=portfolio_forecast,
        provider_rollups=provider_rollups,
        at_risk_accounts=at_risk_accounts,
    )

    title = f"{REPORT_TYPE_LABELS[report_type]} - {_format_title_period(period_start, period_end)}"
    data = {
        "report_type": report_type,
        "focus": report_type,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "label": period_label,
        },
        "portfolio": {
            "currency": currency,
            "actual_period_spend": portfolio_actual_period_spend,
            "forecast_eom_spend": round(_to_float(portfolio_forecast.get("forecast_eom_spend")), 2),
            "budget_limit": portfolio_forecast.get("budget_limit"),
            "budget_source": portfolio_forecast.get("budget_source"),
            "variance_amount": portfolio_forecast.get("variance_amount"),
            "variance_pct": portfolio_forecast.get("variance_pct"),
            "status": portfolio_forecast.get("status"),
            "trend": portfolio_forecast.get("trend"),
            "history_days_used": int(portfolio_forecast.get("history_days_used") or 0),
            "message": portfolio_forecast.get("message"),
        },
        "highlights": highlights,
        "provider_breakdown": provider_rollups,
        "accounts": account_summaries,
        "at_risk_accounts": at_risk_accounts,
        "readiness": {
            "active_accounts": len(account_summaries),
            "ready_accounts": ready_accounts,
            "status": portfolio_forecast.get("status"),
        },
    }

    file_size_bytes = len(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    generated_at_value = generated_at.isoformat() if generated_at else _utc_now_iso()

    return {
        "user_id": user_id,
        "report_type": report_type,
        "title": title,
        "summary": summary,
        "status": _report_status_from_forecast_status(str(portfolio_forecast.get("status") or "")),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "generated_at": generated_at_value,
        "currency": currency,
        "file_size_bytes": file_size_bytes,
        "delivery_channels": ["in_app"],
        "delivery_status": "available",
        "metadata": {
            "scope": "portfolio",
            "active_accounts": len(account_summaries),
            "ready_accounts": ready_accounts,
            "forecast_status": portfolio_forecast.get("status"),
        },
        "data": data,
    }
