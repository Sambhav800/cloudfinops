import logging
import re
from calendar import monthrange
from datetime import date, datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_REPORT_CADENCE = "weekly"
DISPLAY_CURRENCY = "INR"
DEFAULT_USD_TO_INR_RATE = 85.5
DEFAULT_FINANCE_ALERT_THRESHOLDS = {
    "warning_pct": 80.0,
    "critical_pct": 100.0,
}
RISK_BUDGET_STATUSES = {"approaching_budget", "forecasted_over_budget", "over_budget"}
_REPORT_RECIPIENT_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _to_float(value: Any) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return 0.0
        return parsed
    except (TypeError, ValueError):
        return 0.0


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_spend_date(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _to_display_currency_amount(amount: Any, currency: Any) -> float:
    parsed = _to_float(amount)
    currency_code = str(currency or "").strip().upper()
    if currency_code in {"", DISPLAY_CURRENCY, "₹", "RS", "INR"}:
        return parsed
    if currency_code == "USD":
        return parsed * DEFAULT_USD_TO_INR_RATE
    return parsed


def aggregate_daily_spend_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}

    for row in rows or []:
        spend_date = _parse_spend_date(row.get("spend_date"))
        if spend_date is None:
            continue

        key = spend_date.isoformat()
        current = aggregated.setdefault(
            key,
            {
                "spend_date": key,
                "amount": 0.0,
                "currency": DISPLAY_CURRENCY,
                "service_breakdown": {},
            },
        )
        current["amount"] = round(
            current["amount"] + _to_display_currency_amount(row.get("amount"), row.get("currency")),
            4,
        )

        service_breakdown = row.get("service_breakdown")
        if isinstance(service_breakdown, dict):
            merged = current["service_breakdown"]
            for service_name, amount in service_breakdown.items():
                service_key = str(service_name or "Unknown")
                merged[service_key] = round(
                    merged.get(service_key, 0.0)
                    + _to_display_currency_amount(amount, row.get("currency")),
                    4,
                )

    return [aggregated[key] for key in sorted(aggregated.keys())]


def redact_integration_settings_for_audit(update_data: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}

    for key, value in update_data.items():
        if key == "alert_phone_number":
            digits = "".join(ch for ch in str(value or "") if ch.isdigit())
            redacted[key] = f"***{digits[-4:]}" if len(digits) >= 4 else "redacted"
            continue

        if key == "alert_slack_webhook":
            redacted[key] = "configured" if str(value or "").strip() else "empty"
            continue

        redacted[key] = value

    return redacted


def normalize_finance_settings(raw_settings: Any) -> Dict[str, Any]:
    settings = raw_settings if isinstance(raw_settings, dict) else {}

    budget_limit = _to_float(settings.get("portfolio_budget_limit"))
    if budget_limit <= 0:
        portfolio_budget_limit = None
    else:
        portfolio_budget_limit = round(budget_limit, 2)

    report_recipients: List[str] = []
    seen_recipients = set()
    for raw_recipient in settings.get("report_recipients", []):
        candidate = str(raw_recipient or "").strip().lower()
        if not candidate or not _REPORT_RECIPIENT_PATTERN.match(candidate):
            continue
        if candidate in seen_recipients:
            continue
        seen_recipients.add(candidate)
        report_recipients.append(candidate)

    cadence = str(settings.get("report_cadence") or DEFAULT_REPORT_CADENCE).strip().lower()
    if cadence not in {"manual", "weekly", "monthly"}:
        cadence = DEFAULT_REPORT_CADENCE

    raw_thresholds = settings.get("alert_thresholds")
    threshold_settings = raw_thresholds if isinstance(raw_thresholds, dict) else {}
    warning_pct = _to_float(threshold_settings.get("warning_pct")) or DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"]
    critical_pct = _to_float(threshold_settings.get("critical_pct")) or DEFAULT_FINANCE_ALERT_THRESHOLDS["critical_pct"]

    warning_pct = min(max(round(warning_pct, 2), 1.0), 100.0)
    critical_floor = max(warning_pct, DEFAULT_FINANCE_ALERT_THRESHOLDS["critical_pct"])
    critical_pct = min(max(round(critical_pct, 2), critical_floor), 200.0)

    return {
        "portfolio_budget_limit": portfolio_budget_limit,
        "report_recipients": report_recipients,
        "report_cadence": cadence,
        "alert_thresholds": {
            "warning_pct": warning_pct,
            "critical_pct": critical_pct,
        },
    }


def redact_finance_settings_for_audit(update_data: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}

    for key, value in update_data.items():
        if key == "report_recipients":
            redacted[key] = {
                "count": len(value) if isinstance(value, list) else 0,
            }
            continue

        if key == "alert_thresholds":
            thresholds = value if isinstance(value, dict) else {}
            redacted[key] = {
                "warning_pct": round(_to_float(thresholds.get("warning_pct")), 2),
                "critical_pct": round(_to_float(thresholds.get("critical_pct")), 2),
            }
            continue

        redacted[key] = value

    return redacted


def build_account_forecast_drivers(
    account_summaries: List[Dict[str, Any]],
    *,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for item in account_summaries:
        forecast_eom_spend = round(_to_float(item.get("forecast_eom_spend")), 2)
        actual_spend = round(
            _to_float(
                item.get("actual_mtd_spend")
                if item.get("actual_mtd_spend") is not None
                else item.get("actual_period_spend")
            ),
            2,
        )
        delta_amount = round(max(forecast_eom_spend - actual_spend, 0.0), 2)

        if delta_amount <= 0:
            continue

        status = str(item.get("forecast_status") or item.get("status") or "").strip().lower()
        if status == "insufficient_history":
            continue

        name = str(
            item.get("name")
            or item.get("account_identifier")
            or item.get("integration_id")
            or "Cloud account"
        ).strip()
        provider = str(item.get("provider") or "").strip().upper()
        key = f"{name} ({provider})" if provider else name

        candidates.append(
            {
                "dimension": "Account",
                "key": key,
                "delta_amount": delta_amount,
            }
        )

    candidates.sort(key=lambda item: _to_float(item.get("delta_amount")), reverse=True)

    deduplicated: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        driver_key = (str(item.get("dimension") or ""), str(item.get("key") or ""))
        if driver_key in seen:
            continue
        seen.add(driver_key)
        deduplicated.append(item)
        if len(deduplicated) >= max(limit, 0):
            break

    return deduplicated


def _compute_trend(series: List[float]) -> str:
    if len(series) < 4:
        return "unknown"

    midpoint = max(1, len(series) // 2)
    earlier = series[:midpoint]
    later = series[midpoint:]
    delta = mean(later) - mean(earlier)
    tolerance = max(mean(series) * 0.02, 1.0)

    if abs(delta) <= tolerance:
        return "flat"
    return "increasing" if delta > 0 else "decreasing"


def _forecast_remaining_daily_spend(series: List[float], forecast_days: int) -> tuple[List[float], str, bool]:
    if forecast_days <= 0:
        return [], "current_period_complete", True

    if len(series) >= 14:
        try:
            import pandas as pd
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            samples = pd.Series(series)
            seasonal_periods = 7 if len(series) >= 21 else None
            if seasonal_periods:
                model = ExponentialSmoothing(
                    samples,
                    trend="add",
                    seasonal="add",
                    seasonal_periods=seasonal_periods,
                    initialization_method="estimated",
                )
            else:
                model = ExponentialSmoothing(
                    samples,
                    trend="add",
                    initialization_method="estimated",
                )

            fit = model.fit(optimized=True)
            forecast = fit.forecast(forecast_days)
            return [max(0.0, float(item)) for item in forecast], "holt_winters", True
        except Exception as error:
            logger.warning("Holt-Winters forecast unavailable, falling back to moving average: %s", error)

    recent_window = series[-min(len(series), 7):]
    baseline = mean(recent_window)

    previous_window: List[float] = []
    if len(series) > len(recent_window):
        start = max(0, len(series) - (2 * len(recent_window)))
        previous_window = series[start:len(series) - len(recent_window)]

    trend_delta = 0.0
    if previous_window:
        trend_delta = (mean(recent_window) - mean(previous_window)) / max(len(recent_window), 1)

    forecast = []
    for day_offset in range(1, forecast_days + 1):
        projected = baseline + (trend_delta * day_offset)
        forecast.append(max(0.0, projected))

    return forecast, "moving_average", False


def build_forecast_summary(
    history_rows: List[Dict[str, Any]],
    *,
    budget_limit: Optional[float],
    budget_source: str,
    scope: str,
    integration_id: Optional[str] = None,
    as_of: Optional[date] = None,
    warning_threshold_pct: float = DEFAULT_FINANCE_ALERT_THRESHOLDS["warning_pct"],
) -> Dict[str, Any]:
    aggregated_history = aggregate_daily_spend_rows(history_rows)
    as_of_date = as_of or _utc_today()
    currency = "USD"
    if aggregated_history:
        currency = str(aggregated_history[-1].get("currency") or "USD")

    current_month_rows = []
    for row in aggregated_history:
        spend_date = _parse_spend_date(row.get("spend_date"))
        if spend_date and spend_date.year == as_of_date.year and spend_date.month == as_of_date.month and spend_date <= as_of_date:
            current_month_rows.append(row)

    actual_mtd_spend = round(sum(_to_float(row.get("amount")) for row in current_month_rows), 2)
    history_series = [_to_float(row.get("amount")) for row in aggregated_history[-60:]]
    history_days_used = len(history_series)

    if history_days_used < 5 or not current_month_rows:
        return {
            "scope": scope,
            "integration_id": integration_id,
            "as_of": datetime.combine(as_of_date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            "currency": currency,
            "history_days_used": history_days_used,
            "forecast_method": "insufficient_history",
            "forecast_stable": False,
            "actual_mtd_spend": actual_mtd_spend,
            "forecast_eom_spend": actual_mtd_spend,
            "budget_limit": budget_limit,
            "budget_source": budget_source,
            "variance_amount": round(actual_mtd_spend - budget_limit, 2) if budget_limit else None,
            "variance_pct": round(((actual_mtd_spend - budget_limit) / budget_limit) * 100, 2) if budget_limit else None,
            "status": "insufficient_history",
            "trend": "unknown",
            "drivers": [],
            "message": "Need at least 5 daily spend records in the current period for a reliable forecast.",
        }

    total_days_in_month = monthrange(as_of_date.year, as_of_date.month)[1]
    remaining_days = max(0, total_days_in_month - as_of_date.day)
    forecast_values, forecast_method, forecast_stable = _forecast_remaining_daily_spend(history_series, remaining_days)
    forecast_eom_spend = round(actual_mtd_spend + sum(forecast_values), 2)
    trend = _compute_trend(history_series)

    variance_amount = None
    variance_pct = None
    status = "no_budget_configured"
    message = None
    warning_threshold_ratio = max(1.0, min(warning_threshold_pct, 100.0)) / 100.0

    if budget_limit and budget_limit > 0:
        variance_amount = round(forecast_eom_spend - budget_limit, 2)
        variance_pct = round((variance_amount / budget_limit) * 100, 2)

        if actual_mtd_spend > budget_limit:
            status = "over_budget"
            message = "Current month-to-date spend is already above the configured budget."
        elif forecast_eom_spend > budget_limit:
            status = "forecasted_over_budget"
            message = "Forecasted month-end spend is above the configured budget."
        elif forecast_eom_spend >= (budget_limit * warning_threshold_ratio):
            status = "approaching_budget"
            message = "Forecasted month-end spend is approaching the configured budget."
        else:
            status = "on_track"
            message = "Forecasted month-end spend is within the configured budget."
    else:
        message = "No budget is configured for this scope yet."

    return {
        "scope": scope,
        "integration_id": integration_id,
        "as_of": datetime.combine(as_of_date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
        "currency": currency,
        "history_days_used": history_days_used,
        "forecast_method": forecast_method,
        "forecast_stable": forecast_stable,
        "actual_mtd_spend": actual_mtd_spend,
        "forecast_eom_spend": forecast_eom_spend,
        "budget_limit": round(budget_limit, 2) if budget_limit else None,
        "budget_source": budget_source,
        "variance_amount": variance_amount,
        "variance_pct": variance_pct,
        "status": status,
        "trend": trend,
        "drivers": [],
        "message": message,
    }
