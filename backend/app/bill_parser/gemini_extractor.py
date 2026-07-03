"""
Gemini 3 Flash direct-file extraction for uploaded cloud bills.

This module is optional enrichment. The deterministic parser remains the first
source of truth, and Gemini is only used to recover unreadable PDFs or improve
service rollups when it returns more complete bill rows.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
from typing import Any

import httpx

from ..config import GEMINI_API_KEY, GEMINI_BILL_MODEL
from .parser import _categorize_service

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_BILL_TIMEOUT_SECONDS = float(
    os.environ.get("BILL_ANALYSIS_GEMINI_EXTRACT_TIMEOUT_SECONDS", "45.0")
)
_GEMINI_BILL_MAX_INLINE_BYTES = int(
    os.environ.get("BILL_ANALYSIS_GEMINI_MAX_INLINE_BYTES", str(50 * 1024 * 1024))
)
_SUPPORTED_INLINE_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "text/csv",
        "text/plain",
        "application/json",
    }
)


def _mime_type_for_bill(filename: str, content_type: str | None) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".pdf":
        return "application/pdf"
    if extension == ".csv":
        return "text/csv"
    if content_type:
        mime_type = content_type.split(";", 1)[0].strip().lower()
        if mime_type:
            return mime_type
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return default
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9,.\-]", "", text).strip()
    if not cleaned:
        return default
    cleaned = cleaned.strip("()")
    if cleaned.count(",") and cleaned.count("."):
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") == 1 and "." not in cleaned:
        left, right = cleaned.split(",", 1)
        cleaned = f"{left}.{right}" if len(right) == 2 else f"{left}{right}"
    elif cleaned.count(",") > 1:
        cleaned = cleaned.replace(",", "")
    try:
        number = float(cleaned)
    except ValueError:
        return default
    return -abs(number) if negative else number


def _safe_json_object(text: str) -> dict[str, Any] | None:
    stripped = str(text or "").strip()
    if not stripped:
        return None
    stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _extract_response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""
    parts: list[str] = []
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        candidate_parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(candidate_parts, list):
            continue
        for part in candidate_parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "\n".join(parts).strip()


def _normalize_provider(value: Any) -> str:
    provider = str(value or "generic").strip().lower()
    if provider in {"amazon", "amazon web services"}:
        return "aws"
    if provider in {"google", "google cloud", "gcp"}:
        return "gcp"
    if provider in {"microsoft", "microsoft azure"}:
        return "azure"
    return provider if provider in {"aws", "azure", "gcp"} else "generic"


def _normalize_services(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    services: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        service = str(item.get("service") or item.get("name") or item.get("description") or "").strip()
        if not service:
            continue
        cost = round(_coerce_float(item.get("cost") or item.get("amount") or item.get("spend")), 2)
        if abs(cost) < 0.001:
            continue
        row = {"service": service, "cost": cost}
        category = str(item.get("category") or "").strip()
        if category:
            row["category"] = category
        services.append(row)
    services.sort(key=lambda row: float(row.get("cost") or 0), reverse=True)
    return services


def _normalize_categories(raw: Any, services: list[dict[str, Any]]) -> dict[str, float]:
    categories: dict[str, float] = {}
    if isinstance(raw, dict):
        for category, amount in raw.items():
            value = round(_coerce_float(amount), 2)
            if value > 0:
                categories[str(category or "Other")] = value
    if categories:
        return categories

    for item in services:
        cost = float(item.get("cost") or 0)
        if cost <= 0:
            continue
        category = str(item.get("category") or "").strip() or _categorize_service(str(item.get("service") or ""))
        categories[category] = round(categories.get(category, 0.0) + cost, 2)
    return categories


def _normalize_gemini_bill_payload(
    payload: dict[str, Any],
    *,
    filename: str,
    mime_type: str,
    content_size: int,
    model_name: str,
) -> dict[str, Any] | None:
    services = _normalize_services(
        payload.get("raw_services")
        or payload.get("services")
        or payload.get("line_items")
        or payload.get("items")
    )
    by_category = _normalize_categories(payload.get("by_category") or payload.get("spend_by_category"), services)
    total_spend = round(
        _coerce_float(
            payload.get("total_spend")
            or payload.get("total")
            or payload.get("invoice_total")
            or payload.get("net_total")
        ),
        2,
    )
    if total_spend <= 0:
        total_spend = round(sum(float(item.get("cost") or 0) for item in services), 2)
    if total_spend <= 0 and by_category:
        total_spend = round(sum(by_category.values()), 2)
    if total_spend <= 0 or not services:
        return None

    source_format = os.path.splitext(filename)[1].lower().lstrip(".") or "unknown"
    line_item_count = int(_coerce_float(payload.get("line_item_count") or payload.get("rows_parsed"), len(services)))
    existing_savings = round(
        abs(
            _coerce_float(
                payload.get("existing_credits_and_savings")
                or payload.get("credits")
                or payload.get("discounts")
            )
        ),
        2,
    )

    _VALID_CURRENCY_CODES = frozenset(
        {"USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY", "CHF"}
    )
    raw_currency = str(payload.get("currency") or "").strip().upper()
    # Reject template placeholder strings like "<3-letter ISO ...>" that Gemini
    # may echo back when it cannot determine the currency.
    if (
        len(raw_currency) == 3
        and raw_currency.isalpha()
        and raw_currency in _VALID_CURRENCY_CODES
    ):
        resolved_currency = raw_currency
    else:
        resolved_currency = "USD"

    return {
        "provider": _normalize_provider(payload.get("provider")),
        "rows_parsed": max(line_item_count, len(services)),
        "total_spend": total_spend,
        "currency": resolved_currency,
        "by_category": by_category,
        "raw_services": services,
        "cloudfront_insights": None,
        "gpu_insights": None,
        "source_format": source_format,
        "source_parser": "gemini_3_flash_direct_file",
        "existing_credits_and_savings": existing_savings,
        "savings_amount": existing_savings,
        "source_metadata": {
            "source_format": source_format,
            "source_parser": "gemini_3_flash_direct_file",
            "filename": filename,
            "line_items_detected": max(line_item_count, len(services)),
            "gemini_direct_file": {
                "status": "extracted",
                "model": model_name,
                "mime_type": mime_type,
                "size_bytes": content_size,
                "service_rows_detected": len(services),
            },
        },
    }


def _build_extraction_prompt(filename: str) -> str:
    return f"""
You are extracting a cloud provider bill for CloudFinOps.

File name: {filename}

Return only valid JSON with this exact shape:
{{
  "provider": "aws|azure|gcp|generic",
  "currency": "<3-letter ISO currency code as shown in the bill, e.g. USD, INR, EUR, GBP>",
  "billing_period": "string if visible",
  "line_item_count": 0,
  "total_spend": 0.0,
  "existing_credits_and_savings": 0.0,
  "by_category": {{"Compute": 0.0}},
  "raw_services": [
    {{"service": "service or SKU label exactly as shown", "category": "Compute", "cost": 0.0}}
  ]
}}

Rules:
- CRITICAL: Read the currency from the bill header, footer, or column labels. Do NOT assume USD.
  Common currencies: USD (US Dollar), INR (Indian Rupee), EUR (Euro), GBP (British Pound),
  AUD (Australian Dollar), CAD (Canadian Dollar), JPY (Japanese Yen), CHF (Swiss Franc).
  Look for symbols: $ = USD, ₹ = INR, € = EUR, £ = GBP. Return the 3-letter ISO code.
- Extract EVERY visible service, SKU, category, or cost line — no matter how small. Do not stop at top 20. Include $0.01 lines.
- Include region-specific sub-lines (e.g. "EC2 - US East (N. Virginia)") as separate entries.
- Include usage detail lines (e.g. "$0.10 per GB - first 10 TB") when they have a cost amount.
- Do not invent services or prices. If a value is unclear, omit that row.
- Use net spend for total_spend when the bill shows credits, discounts, or refunds.
- Keep negative credits out of by_category, but include the total credit/discount amount in existing_credits_and_savings.
- Use numeric values only for costs, without currency symbols.
- For AWS bills: include Data Transfer, NAT Gateway, Public IPv4, Route 53, CloudWatch, and other small services.
- For Azure bills: include each meter category separately.
- For GCP bills: include each SKU description separately.
""".strip()


async def extract_bill_with_gemini(
    content: bytes,
    filename: str,
    *,
    content_type: str | None = None,
) -> dict[str, Any] | None:
    """Use Gemini 3 Flash to extract a bill when deterministic parsing cannot."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or GEMINI_API_KEY
    if not api_key:
        return None

    mime_type = _mime_type_for_bill(filename, content_type)
    if mime_type not in _SUPPORTED_INLINE_MIME_TYPES:
        logger.info("Gemini bill extraction skipped for unsupported mime type %s", mime_type)
        return None
    if mime_type == "application/pdf" and not content.lstrip().startswith(b"%PDF"):
        logger.warning("Gemini bill extraction skipped for %s because PDF magic bytes were not detected", filename)
        return None
    if len(content) > _GEMINI_BILL_MAX_INLINE_BYTES:
        logger.info(
            "Gemini bill extraction skipped for %s because file size exceeds inline limit",
            filename,
        )
        return None

    model_name = os.environ.get("BILL_ANALYSIS_GEMINI_MODEL") or GEMINI_BILL_MODEL
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(content).decode("ascii"),
                        }
                    },
                    {"text": _build_extraction_prompt(filename)},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
        },
    }

    url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={api_key}"
    try:
        async with httpx.AsyncClient(timeout=_GEMINI_BILL_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        response_text = _extract_response_text(response.json())
        extracted = _safe_json_object(response_text)
        if not extracted:
            logger.warning("Gemini bill extraction returned non-JSON content for %s", filename)
            return None
        return _normalize_gemini_bill_payload(
            extracted,
            filename=filename,
            mime_type=mime_type,
            content_size=len(content),
            model_name=model_name,
        )
    except (asyncio.TimeoutError, httpx.TimeoutException):
        logger.warning(
            "Optional Gemini bill extraction timed out for %s; deterministic bill parser will continue",
            filename,
        )
    except httpx.HTTPStatusError as error:
        logger.warning(
            "Optional Gemini bill extraction failed for %s with HTTP %s; deterministic bill parser will continue: %s",
            filename,
            error.response.status_code,
            error.response.text[:500],
        )
    except Exception as error:
        logger.warning(
            "Optional Gemini bill extraction failed for %s; deterministic bill parser will continue: %s",
            filename,
            error,
        )
    return None


async def enrich_parsed_bill_with_gemini(
    parsed: dict[str, Any],
    content: bytes,
    filename: str,
    *,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Improve deterministic parse rows with Gemini direct-file extraction when it is more complete.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or GEMINI_API_KEY
    if not api_key:
        source_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
        return {
            **parsed,
            "source_metadata": {
                **source_metadata,
                "gemini_direct_file": {
                    "status": "skipped_no_api_key",
                    "deterministic_service_rows": len(parsed.get("raw_services") if isinstance(parsed.get("raw_services"), list) else []),
                },
            },
        }

    extracted = await extract_bill_with_gemini(content, filename, content_type=content_type)
    if not extracted:
        source_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
        return {
            **parsed,
            "source_metadata": {
                **source_metadata,
                "gemini_direct_file": {
                    **(
                        source_metadata.get("gemini_direct_file")
                        if isinstance(source_metadata.get("gemini_direct_file"), dict)
                        else {}
                    ),
                    "status": "unavailable_or_failed",
                    "deterministic_service_rows": len(parsed.get("raw_services") if isinstance(parsed.get("raw_services"), list) else []),
                },
            },
        }

    deterministic_services = parsed.get("raw_services") if isinstance(parsed.get("raw_services"), list) else []
    gemini_services = extracted.get("raw_services") if isinstance(extracted.get("raw_services"), list) else []

    gemini_is_more_complete = len(gemini_services) > len(deterministic_services)
    deterministic_total = float(parsed.get("total_spend") or 0)
    gemini_total = float(extracted.get("total_spend") or 0)
    spend_divergence = abs(deterministic_total - gemini_total) / max(deterministic_total, 1.0)
    gemini_captures_missing_spend = (
        spend_divergence > 0.15
        and gemini_total > deterministic_total
        and len(gemini_services) >= max(len(deterministic_services) - 2, 1)
    )

    if not gemini_is_more_complete and not gemini_captures_missing_spend:
        source_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
        return {
            **parsed,
            "source_metadata": {
                **source_metadata,
                "gemini_direct_file": {
                    **((extracted.get("source_metadata") or {}).get("gemini_direct_file") or {}),
                    "status": "available_not_used",
                    "deterministic_service_rows": len(deterministic_services),
                    "gemini_service_rows": len(gemini_services),
                    "spend_divergence_pct": round(spend_divergence * 100, 1),
                },
            },
        }

    source_metadata = parsed.get("source_metadata") if isinstance(parsed.get("source_metadata"), dict) else {}
    extracted_metadata = extracted.get("source_metadata") if isinstance(extracted.get("source_metadata"), dict) else {}
    return {
        **parsed,
        "raw_services": gemini_services,
        "by_category": extracted.get("by_category") or parsed.get("by_category") or {},
        "rows_parsed": max(int(parsed.get("rows_parsed") or 0), int(extracted.get("rows_parsed") or 0)),
        "source_parser": f"{parsed.get('source_parser') or 'deterministic'}+gemini_3_flash",
        "source_metadata": {
            **source_metadata,
            "gemini_direct_file": {
                **(extracted_metadata.get("gemini_direct_file") or {}),
                "status": "used_for_service_rollup",
                "deterministic_service_rows": len(deterministic_services),
            },
        },
    }
