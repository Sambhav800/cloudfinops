"""
Provider-native recommendation ingestion.

This module ingests cloud-provider recommendations into the same ledger used by
CloudFinOps deterministic findings. Provider signals enrich existing records
when they match and create provider-only records when the provider found
something CloudFinOps has not classified yet.
"""

import asyncio
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from azure.identity import ClientSecretCredential

from .recommendations import (
    PROVIDER_RECOMMENDATION_COLLECTION,
    PROTECTED_RECOMMENDATION_STATES,
    RECOMMENDATION_EVIDENCE_COLLECTION,
    RECOMMENDATION_LEDGER_COLLECTION,
    RECOMMENDATION_STATE_EVENTS_COLLECTION,
    recommendation_id_for,
)

logger = logging.getLogger(__name__)

AZURE_ADVISOR_API_VERSION = "2025-01-01"
AZURE_ADVISOR_SOURCE = "azure_advisor"
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
AZURE_MANAGEMENT_ENDPOINT = "https://management.azure.com"
AZURE_ADVISOR_REFRESH_TIMEOUT_SECONDS = 25
AZURE_ADVISOR_REFRESH_POLL_SECONDS = 2


class ProviderRecommendationError(Exception):
    """Raised when provider recommendation ingestion cannot complete."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(parts: Iterable[Any]) -> str:
    raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _as_record(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


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


def _nested(record: Dict[str, Any], *keys: str) -> Any:
    current: Any = record
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _get_header(headers: Dict[str, str], name: str) -> str:
    normalized = name.lower()
    for key, value in headers.items():
        if key.lower() == normalized:
            return _as_string(value)
    return ""


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if any(item_key == key for item_key, _ in query):
        return url
    query.append((key, value))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _normalize_status_url(location: str) -> str:
    status_url = _as_string(location)
    if not status_url:
        return ""
    if status_url.startswith("/"):
        status_url = f"{AZURE_MANAGEMENT_ENDPOINT}{status_url}"
    return _append_query_param(status_url, "api-version", AZURE_ADVISOR_API_VERSION)


def _operation_status(payload: Dict[str, Any]) -> str:
    return _as_string(payload.get("status") or payload.get("provisioningState")).strip().lower()


def _clean_resource_token(value: Any) -> str:
    text = _as_string(value).lower()
    if not text:
        return ""
    return text.rstrip("/").split("/")[-1]


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _as_string(value)
        if text:
            return text
    return ""


def _extract_currency(properties: Dict[str, Any]) -> Optional[str]:
    extended = _as_record(properties.get("extendedProperties"))
    for key in (
        "currency",
        "savingsCurrency",
        "annualSavingsCurrency",
        "monthlySavingsCurrency",
        "billingCurrency",
    ):
        value = extended.get(key) or properties.get(key)
        if value:
            return _as_string(value).upper()
    return None


def _extract_monthly_savings(properties: Dict[str, Any]) -> float:
    extended = _as_record(properties.get("extendedProperties"))
    merged = {**properties, **extended}

    monthly_keys = (
        "monthlySavingsAmount",
        "estimatedMonthlySavings",
        "monthlySavings",
        "savingsAmountMonthly",
    )
    for key in monthly_keys:
        value = _as_float(merged.get(key))
        if value > 0:
            return round(value, 2)

    annual_keys = (
        "annualSavingsAmount",
        "estimatedAnnualSavings",
        "annualSavings",
        "savingsAmountAnnual",
    )
    for key in annual_keys:
        value = _as_float(merged.get(key))
        if value > 0:
            return round(value / 12, 2)

    return 0.0


def _impact_to_severity(impact: str) -> str:
    normalized = impact.strip().lower()
    if normalized == "high":
        return "high"
    if normalized == "medium":
        return "medium"
    if normalized == "low":
        return "low"
    return "info"


def _action_from_text(*values: Any) -> str:
    text = " ".join(_as_string(value).lower() for value in values)
    if "right" in text and "siz" in text:
        return "rightsize"
    if "resize" in text or "downsize" in text:
        return "rightsize"
    if "shutdown" in text or "shut down" in text or "deallocate" in text or "stop" in text:
        return "stop"
    if "delete" in text or "remove" in text or "terminate" in text:
        return "delete"
    if "reservation" in text or "reserved instance" in text or "savings plan" in text or "commitment" in text:
        return "purchase_commitment"
    return "review_provider_recommendation"


def _risk_from_impact(impact: str) -> str:
    normalized = impact.strip().lower()
    if normalized == "high":
        return "medium"
    if normalized == "medium":
        return "low"
    return "low"


def _provider_record_completeness(provider_record: Dict[str, Any]) -> int:
    checks = (
        bool(_as_string(provider_record.get("provider_recommendation_id"))),
        bool(_as_string(provider_record.get("provider_resource_id"))),
        bool(_as_string(provider_record.get("resource_name"))),
        bool(_as_string(provider_record.get("resource_type"))),
        bool(_as_string(provider_record.get("description"))),
        bool(_as_string(provider_record.get("action"))),
        _as_float(provider_record.get("estimated_monthly_savings")) > 0,
        bool(_as_string(provider_record.get("savings_currency"))),
    )
    return int(round(sum(1 for check in checks if check) / len(checks) * 100))


def _provider_recommendation_id(
    user_id: str,
    integration_id: str,
    provider_recommendation_id: str,
) -> str:
    digest = _stable_hash([user_id, integration_id, provider_recommendation_id])
    return f"provider_rec_{digest}"


def _get_azure_management_token(credentials: Dict[str, Any]) -> tuple[str, str]:
    tenant_id = _as_string(credentials.get("tenant_id"))
    client_id = _as_string(credentials.get("client_id"))
    client_secret = _as_string(credentials.get("client_secret"))
    subscription_id = _as_string(credentials.get("subscription_id"))
    if not all((tenant_id, client_id, client_secret, subscription_id)):
        raise ProviderRecommendationError("Azure credentials are incomplete")

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    return credential.get_token(AZURE_MANAGEMENT_SCOPE).token, subscription_id


def _azure_advisor_request(
    *,
    url: str,
    token: str,
    method: str,
) -> tuple[int, Dict[str, str], Dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=b"" if method.upper() == "POST" else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method.upper(),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw_body = response.read()
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        headers = {key: value for key, value in response.headers.items()}
        return int(response.getcode()), headers, payload if isinstance(payload, dict) else {}


def _azure_advisor_error_message(error: urllib.error.HTTPError, operation: str) -> str:
    if error.code in (401, 403):
        return (
            f"Azure Advisor {operation} is not authorized; grant the integration service principal "
            "Reader access to the subscription/resource scope and Advisor recommendation permissions"
        )
    return f"Azure Advisor {operation} failed with HTTP {error.code}"


def refresh_azure_advisor_recommendations(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """Ask Azure Advisor to regenerate subscription recommendations and wait briefly."""
    token, subscription_id = _get_azure_management_token(credentials)
    query = urllib.parse.urlencode({"api-version": AZURE_ADVISOR_API_VERSION})
    generate_url = (
        f"{AZURE_MANAGEMENT_ENDPOINT}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.Advisor/generateRecommendations?{query}"
    )

    try:
        status_code, headers, _ = _azure_advisor_request(
            url=generate_url,
            token=token,
            method="POST",
        )
    except urllib.error.HTTPError as error:
        raise ProviderRecommendationError(_azure_advisor_error_message(error, "refresh")) from error
    except Exception as error:
        raise ProviderRecommendationError("Azure Advisor refresh request failed") from error

    status_url = _normalize_status_url(_get_header(headers, "Location") or _get_header(headers, "Azure-AsyncOperation"))
    retry_after = max(0, _as_float(_get_header(headers, "Retry-After")) or AZURE_ADVISOR_REFRESH_POLL_SECONDS)
    if status_code == 204:
        return {
            "refresh_status": "completed",
            "refreshed": True,
            "refresh_message": "Azure Advisor recommendations were refreshed",
        }
    if not status_url:
        return {
            "refresh_status": "accepted_no_status_url",
            "refreshed": False,
            "refresh_message": "Azure Advisor accepted refresh, but did not return a status URL",
        }

    deadline = time.monotonic() + AZURE_ADVISOR_REFRESH_TIMEOUT_SECONDS
    time.sleep(min(retry_after, AZURE_ADVISOR_REFRESH_POLL_SECONDS))
    while time.monotonic() < deadline:
        try:
            poll_status, _, poll_payload = _azure_advisor_request(
                url=status_url,
                token=token,
                method="GET",
            )
        except urllib.error.HTTPError as error:
            raise ProviderRecommendationError(_azure_advisor_error_message(error, "refresh status check")) from error
        except Exception as error:
            raise ProviderRecommendationError("Azure Advisor refresh status check failed") from error

        if poll_status == 204:
            return {
                "refresh_status": "completed",
                "refreshed": True,
                "refresh_message": "Azure Advisor recommendations were refreshed",
            }
        if poll_status == 200:
            operation_status = _operation_status(poll_payload)
            if operation_status in ("succeeded", "success", "completed"):
                return {
                    "refresh_status": "completed",
                    "refreshed": True,
                    "refresh_message": "Azure Advisor recommendations were refreshed",
                }
            if operation_status in ("failed", "canceled", "cancelled"):
                return {
                    "refresh_status": operation_status,
                    "refreshed": False,
                    "refresh_message": f"Azure Advisor refresh ended with status {operation_status}",
                }
            if operation_status in ("running", "inprogress", "in_progress", "accepted"):
                time.sleep(AZURE_ADVISOR_REFRESH_POLL_SECONDS)
                continue
        if poll_status != 202:
            return {
                "refresh_status": "unknown",
                "refreshed": False,
                "refresh_message": f"Azure Advisor refresh returned unexpected status {poll_status}",
            }
        time.sleep(AZURE_ADVISOR_REFRESH_POLL_SECONDS)

    return {
        "refresh_status": "timed_out",
        "refreshed": False,
        "refresh_message": "Azure Advisor refresh was still running; cached recommendations were used",
    }


def fetch_azure_advisor_recommendations(credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch active Azure Advisor cost recommendations for one subscription."""
    token, subscription_id = _get_azure_management_token(credentials)
    query = urllib.parse.urlencode({
        "api-version": AZURE_ADVISOR_API_VERSION,
        "$filter": "Category eq 'Cost'",
        "$top": "100",
    })
    url: Optional[str] = (
        f"{AZURE_MANAGEMENT_ENDPOINT}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.Advisor/recommendations?{query}"
    )

    recommendations: List[Dict[str, Any]] = []
    page_count = 0
    try:
        while url and page_count < 10:
            _, _, payload = _azure_advisor_request(
                url=url,
                token=token,
                method="GET",
            )

            recommendations.extend(
                item
                for item in _as_list(payload.get("value"))
                if isinstance(item, dict)
            )
            url = _as_string(payload.get("nextLink")) or None
            page_count += 1
    except urllib.error.HTTPError as error:
        raise ProviderRecommendationError(_azure_advisor_error_message(error, "recommendation list")) from error
    except Exception as error:
        raise ProviderRecommendationError("Azure Advisor request failed") from error

    return recommendations


def normalize_azure_advisor_recommendation(
    row: Dict[str, Any],
    *,
    user_id: str,
    integration_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Normalize one Azure Advisor REST row into a provider recommendation row."""
    properties = _as_record(row.get("properties"))
    short_description = _as_record(properties.get("shortDescription"))
    resource_metadata = _as_record(properties.get("resourceMetadata"))
    extended_properties = _as_record(properties.get("extendedProperties"))
    provider_recommendation_id = _first_non_empty(row.get("id"), row.get("name"), properties.get("recommendationTypeId"))
    provider_resource_id = _first_non_empty(
        resource_metadata.get("resourceId"),
        properties.get("resourceId"),
        properties.get("impactedValue"),
    )
    impacted_value = _as_string(properties.get("impactedValue"))
    title = _first_non_empty(short_description.get("problem"), properties.get("description"), row.get("name"))
    solution = _first_non_empty(short_description.get("solution"), properties.get("recommendation"))
    description = " - ".join(part for part in (title, solution) if part) or "Azure Advisor cost recommendation"
    impact = _as_string(properties.get("impact"), "Medium")
    category = _as_string(properties.get("category"), "Cost")

    return {
        "id": _provider_recommendation_id(user_id, integration_id, provider_recommendation_id),
        "user_id": user_id,
        "integration_id": integration_id,
        "provider": "azure",
        "source_system": AZURE_ADVISOR_SOURCE,
        "provider_recommendation_id": provider_recommendation_id,
        "provider_resource_id": provider_resource_id,
        "resource_name": _first_non_empty(
            resource_metadata.get("resourceName"),
            impacted_value,
            _clean_resource_token(provider_resource_id),
            row.get("name"),
        ),
        "resource_type": _first_non_empty(
            resource_metadata.get("resourceType"),
            properties.get("impactedField"),
            "Azure Resource",
        ),
        "region": _as_string(resource_metadata.get("region")),
        "category": category,
        "impact": impact,
        "severity": _impact_to_severity(impact),
        "action": _action_from_text(title, solution, properties.get("recommendationTypeId")),
        "description": description,
        "extended_properties": extended_properties,
        "savings_currency": _extract_currency(properties),
        "estimated_monthly_savings": _extract_monthly_savings(properties),
        "fetched_at": fetched_at,
        "raw_type": _as_string(row.get("type")),
    }


def _provider_matches_ledger(provider_record: Dict[str, Any], ledger_record: Dict[str, Any]) -> bool:
    provider_resource_id = _as_string(provider_record.get("provider_resource_id")).lower()
    provider_name = _as_string(provider_record.get("resource_name")).lower()
    provider_token = _clean_resource_token(provider_resource_id)

    ledger_ids = [
        _as_string(ledger_record.get("cloud_resource_id")).lower(),
        _as_string(ledger_record.get("resource_id")).lower(),
        _as_string(ledger_record.get("resource_name")).lower(),
    ]
    ledger_tokens = [_clean_resource_token(item) for item in ledger_ids]

    for ledger_id in ledger_ids:
        if not ledger_id:
            continue
        if ledger_id == provider_resource_id or ledger_id == provider_name:
            return True
        if provider_resource_id and ledger_id in provider_resource_id:
            return True

    for ledger_token in ledger_tokens:
        if not ledger_token:
            continue
        if ledger_token == provider_token or ledger_token == provider_name:
            return True

    return False


def _append_unique(values: Any, value: str) -> List[str]:
    items = [
        _as_string(item)
        for item in values
        if _as_string(item)
    ] if isinstance(values, list) else []
    if value and value not in items:
        items.append(value)
    return items


async def _replace_provider_evidence(
    *,
    db: Any,
    user_id: str,
    recommendation_id: str,
    provider_record: Dict[str, Any],
) -> None:
    await db.delete(
        RECOMMENDATION_EVIDENCE_COLLECTION,
        {
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "source_system": AZURE_ADVISOR_SOURCE,
        },
    )
    await db.insert(
        RECOMMENDATION_EVIDENCE_COLLECTION,
        {
            "id": f"{recommendation_id}_{AZURE_ADVISOR_SOURCE}_{_stable_hash([provider_record.get('id')])}",
            "user_id": user_id,
            "recommendation_id": recommendation_id,
            "resource_id": _as_string(provider_record.get("provider_resource_id")),
            "evidence_kind": "provider_native_recommendation",
            "signal_name": "azure_advisor_cost_recommendation",
            "observed_value": {
                "impact": provider_record.get("impact"),
                "category": provider_record.get("category"),
                "provider_recommendation_id": provider_record.get("provider_recommendation_id"),
            },
            "threshold": None,
            "description": _as_string(provider_record.get("description")),
            "metric_window_start": None,
            "metric_window_end": None,
            "data_completeness": 1.0,
            "source_system": AZURE_ADVISOR_SOURCE,
            "collected_at": _as_string(provider_record.get("fetched_at"), _utc_now_iso()),
        },
    )


def _build_provider_only_ledger_record(
    *,
    user_id: str,
    integration_id: str,
    provider_record: Dict[str, Any],
    existing_record: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    action = _as_string(provider_record.get("action"), "review_provider_recommendation")
    provider_resource_id = _first_non_empty(
        provider_record.get("provider_resource_id"),
        provider_record.get("provider_recommendation_id"),
    )
    recommendation_id = recommendation_id_for(
        user_id,
        integration_id,
        "azure",
        provider_resource_id,
        action,
    )
    existing_state = _as_string((existing_record or {}).get("state")).lower()
    state = existing_state if existing_state in PROTECTED_RECOMMENDATION_STATES else "provider_checked"
    source_systems = _append_unique((existing_record or {}).get("source_systems", []), AZURE_ADVISOR_SOURCE)
    estimated_savings = _as_float(provider_record.get("estimated_monthly_savings"))
    completeness = _provider_record_completeness(provider_record)
    has_savings_estimate = estimated_savings > 0

    return {
        "id": recommendation_id,
        "user_id": user_id,
        "integration_id": integration_id,
        "provider": "azure",
        "resource_id": provider_resource_id,
        "cloud_resource_id": provider_resource_id,
        "resource_name": _as_string(provider_record.get("resource_name"), provider_resource_id),
        "resource_type": _as_string(provider_record.get("resource_type"), "Azure Resource"),
        "region": _as_string(provider_record.get("region")),
        "recommendation_type": "provider_native_cost",
        "action": action,
        "state": state,
        "severity": _as_string(provider_record.get("severity"), "info"),
        "confidence": 0.0,
        "trust_score": min(completeness, 69),
        "provider_record_completeness": completeness,
        "quality_status": "provider_only",
        "quality_reasons": [
            "Azure Advisor supplied this recommendation; CloudFinOps has not independently corroborated it."
        ],
        "risk_level": _risk_from_impact(_as_string(provider_record.get("impact"))),
        "effort": "unknown",
        "description": _as_string(provider_record.get("description"), "Azure Advisor cost recommendation"),
        "waste_reason": "Azure Advisor cost recommendation",
        "estimated_monthly_savings": estimated_savings,
        "claimable_monthly_savings": estimated_savings if has_savings_estimate else 0.0,
        "savings_estimate_status": "provider_estimate" if has_savings_estimate else "unavailable",
        "savings_calculation_method": "provider_native_estimate" if has_savings_estimate else "not_calculated",
        "savings_estimate_reason": (
            "Savings amount was supplied directly by Azure Advisor."
            if has_savings_estimate
            else "Azure Advisor did not supply a savings amount."
        ),
        "estimated_monthly_waste": estimated_savings,
        "cost_source": "provider_native",
        "pricing_basis": "live_api",
        "pricing_computed_at": _as_string(provider_record.get("fetched_at")),
        "savings_currency": provider_record.get("savings_currency"),
        "evidence_status": "ready",
        "provider_agreement_status": "provider_only",
        "provider_agreement_checked_at": _as_string(provider_record.get("fetched_at")),
        "provider_recommendation_ids": [provider_record.get("id")],
        "ai_enrichment_status": "not_required",
        "source_systems": source_systems,
        "pipeline_version": f"azure_advisor_rest_{AZURE_ADVISOR_API_VERSION}",
        "detected_at": _as_string(provider_record.get("fetched_at"), _utc_now_iso()),
        "expires_at": None,
    }


async def ingest_azure_advisor_recommendations(
    *,
    db: Any,
    user_id: str,
    integration: Dict[str, Any],
    credentials: Dict[str, Any],
    advisor_rows: Optional[List[Dict[str, Any]]] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Persist Azure Advisor recommendations and reconcile them with the ledger."""
    try:
        integration_id = _as_string(integration.get("id"))
        if not integration_id:
            raise ProviderRecommendationError("integration id is required")

        fetched_at = _utc_now_iso()
        refresh_result = {
            "refresh_status": "not_requested",
            "refreshed": False,
            "refresh_message": None,
        }
        if force_refresh:
            try:
                refresh_result = await asyncio.to_thread(
                    refresh_azure_advisor_recommendations,
                    credentials,
                )
            except ProviderRecommendationError as error:
                refresh_result = {
                    "refresh_status": "failed",
                    "refreshed": False,
                    "refresh_message": str(error),
                }

        rows = advisor_rows
        if rows is None:
            rows = await asyncio.to_thread(fetch_azure_advisor_recommendations, credentials)

        provider_records = [
            normalize_azure_advisor_recommendation(
                row,
                user_id=user_id,
                integration_id=integration_id,
                fetched_at=fetched_at,
            )
            for row in rows
            if isinstance(row, dict)
        ]
        provider_records = [
            record
            for record in provider_records
            if _as_string(record.get("category")).lower() == "cost"
        ]

        if provider_records:
            await db.upsert(PROVIDER_RECOMMENDATION_COLLECTION, provider_records)

        ledger_rows = await db.select(
            RECOMMENDATION_LEDGER_COLLECTION,
            filters={"user_id": user_id, "integration_id": integration_id, "provider": "azure"},
        )
        matched_provider_ids: set[str] = set()
        matched_count = 0
        not_found_count = 0

        for ledger_row in ledger_rows:
            matching_records = [
                record
                for record in provider_records
                if _provider_matches_ledger(record, ledger_row)
            ]
            if matching_records:
                provider_ids = list(ledger_row.get("provider_recommendation_ids", []))
                source_systems = list(ledger_row.get("source_systems", []))
                for provider_record in matching_records:
                    provider_ids = _append_unique(provider_ids, _as_string(provider_record.get("id")))
                    source_systems = _append_unique(source_systems, AZURE_ADVISOR_SOURCE)
                    matched_provider_ids.add(_as_string(provider_record.get("id")))
                    await _replace_provider_evidence(
                        db=db,
                        user_id=user_id,
                        recommendation_id=_as_string(ledger_row.get("id")),
                        provider_record=provider_record,
                    )

                trust_score = min(100, int(_as_float(ledger_row.get("trust_score"))) + 10)
                await db.update(
                    RECOMMENDATION_LEDGER_COLLECTION,
                    {
                        "provider_agreement_status": "agrees",
                        "provider_agreement_checked_at": fetched_at,
                        "provider_recommendation_ids": provider_ids,
                        "source_systems": source_systems,
                        "trust_score": trust_score,
                        "evidence_status": "ready",
                    },
                    {"user_id": user_id, "id": ledger_row.get("id")},
                )
                matched_count += 1
            elif AZURE_ADVISOR_SOURCE not in _as_list(ledger_row.get("source_systems")):
                await db.update(
                    RECOMMENDATION_LEDGER_COLLECTION,
                    {
                        "provider_agreement_status": "not_found",
                        "provider_agreement_checked_at": fetched_at,
                    },
                    {"user_id": user_id, "id": ledger_row.get("id")},
                )
                not_found_count += 1

        provider_only_count = 0
        existing_by_id = {_as_string(row.get("id")): row for row in ledger_rows}
        for provider_record in provider_records:
            provider_record_id = _as_string(provider_record.get("id"))
            if provider_record_id in matched_provider_ids:
                continue

            action = _as_string(provider_record.get("action"), "review_provider_recommendation")
            provider_resource_id = _first_non_empty(
                provider_record.get("provider_resource_id"),
                provider_record.get("provider_recommendation_id"),
            )
            recommendation_id = recommendation_id_for(
                user_id,
                integration_id,
                "azure",
                provider_resource_id,
                action,
            )
            existing_record = existing_by_id.get(recommendation_id)
            record = _build_provider_only_ledger_record(
                user_id=user_id,
                integration_id=integration_id,
                provider_record=provider_record,
                existing_record=existing_record,
            )
            await db.upsert(RECOMMENDATION_LEDGER_COLLECTION, record)
            await _replace_provider_evidence(
                db=db,
                user_id=user_id,
                recommendation_id=recommendation_id,
                provider_record=provider_record,
            )
            if not existing_record:
                await db.insert(
                    RECOMMENDATION_STATE_EVENTS_COLLECTION,
                    {
                        "id": f"{recommendation_id}_provider_detected",
                        "user_id": user_id,
                        "recommendation_id": recommendation_id,
                        "from_state": None,
                        "to_state": record["state"],
                        "actor_type": "system",
                        "actor_id": AZURE_ADVISOR_SOURCE,
                        "reason": "Detected by Azure Advisor provider-native recommendation",
                        "created_at": fetched_at,
                    },
                )
            provider_only_count += 1

        ingestion_status = "partial" if force_refresh and not refresh_result["refreshed"] else "ok"
        return {
            "integration_id": integration_id,
            "provider": "azure",
            "status": ingestion_status,
            "fetched": len(rows),
            "stored": len(provider_records),
            "matched": matched_count,
            "provider_only_created": provider_only_count,
            "not_found_marked": not_found_count,
            "message": None,
            "refresh_status": refresh_result["refresh_status"],
            "refreshed": refresh_result["refreshed"],
            "refresh_message": refresh_result["refresh_message"],
        }
    except ProviderRecommendationError:
        raise
    except Exception as error:
        logger.error("ingest_azure_advisor_recommendations failed: %s", error)
        raise ProviderRecommendationError("Azure Advisor ingestion failed") from error
