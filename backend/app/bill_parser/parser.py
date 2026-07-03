"""
Parse cloud billing files (CSV/Excel/PDF) into normalized spend insights.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Any

import pandas as pd

from .cloudfront_analyzer import analyze_cloudfront_bill
from .gpu_analyzer import analyze_gpu_billing
from .pdf_parser import parse_pdf_invoice

logger = logging.getLogger(__name__)

# Currency symbol / code → ISO code mapping used for tabular bill detection
_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "₹": "INR",
    "rs.": "INR",
    "rs ": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "chf": "CHF",
    "a$": "AUD",
    "c$": "CAD",
}
_CURRENCY_CODE_RE = re.compile(
    r"\b(USD|EUR|GBP|INR|AUD|CAD|JPY|CHF)\b",
    re.IGNORECASE,
)
_CURRENCY_COLUMN_NAMES = (
    "billingcurrency",
    "currency",
    "costinbillingcurrency",
    "currencycode",
    "billingcurrencycode",
    "billing_currency",
    "invoice_currency",
    "currency_code",
)


def _detect_currency_from_dataframe(df: pd.DataFrame) -> str:
    """
    Heuristically detect the billing currency from a tabular (CSV/Excel) bill.

    Strategy (in priority order):
    1. Look for a dedicated currency column (e.g. "BillingCurrency", "Currency").
    2. Sample cost cell values for embedded currency symbols or ISO codes.
    3. Scan column headers for ISO codes.
    4. Default to USD.
    """
    # 1. Dedicated currency column
    cols_lower = {col.strip().lower().replace(" ", ""): col for col in df.columns}
    for name in _CURRENCY_COLUMN_NAMES:
        col = cols_lower.get(name)
        if col is None:
            continue
        values = df[col].dropna().astype(str).str.strip().str.upper()
        for val in values:
            if len(val) == 3 and val.isalpha():
                return val

    # 2. Sample cost-like column cells for embedded symbols / codes
    cost_keywords = ("cost", "amount", "price", "charge", "spend", "total")
    sample_text = ""
    for col in df.columns:
        if any(kw in col.lower() for kw in cost_keywords):
            sample = df[col].dropna().astype(str).head(30)
            sample_text += " ".join(sample.tolist()) + " "
    if not sample_text:
        # fall back: concatenate first-30 rows of the whole frame
        sample_text = " ".join(
            df.head(30).astype(str).values.flatten().tolist()
        )

    sample_lower = sample_text.lower()
    if "₹" in sample_text or "rs." in sample_lower:
        return "INR"
    if "€" in sample_text:
        return "EUR"
    if "£" in sample_text:
        return "GBP"

    match = _CURRENCY_CODE_RE.search(sample_text)
    if match:
        return match.group(1).upper()

    # 3. Scan column headers for ISO codes (always run, not just when sample is empty)
    for col in df.columns:
        match = _CURRENCY_CODE_RE.search(col)
        if match:
            return match.group(1).upper()

    # 4. Default
    return "USD"

_AWS_SERVICE_COLS = ["product/ProductName", "lineItem/ProductCode", "ProductName", "Service", "product/servicename"]
_AWS_COST_COLS = ["lineItem/NetUnblendedCost", "lineItem/UnblendedCost", "lineItem/BlendedCost", "lineItem/NetAmortizedCost", "TotalCost", "Cost"]

_AZURE_SERVICE_COLS = ["ServiceName", "MeterCategory", "ConsumedService", "Product", "Service"]
_AZURE_COST_COLS = ["CostInBillingCurrency", "Cost", "PreTaxCost", "ExtendedCost"]

_GCP_SERVICE_COLS = ["Service description", "service.description", "SKU description", "Service"]
_GCP_COST_COLS = ["Cost ($)", "cost", "total_cost", "Cost"]

_SERVICE_CATEGORY_MAP: dict[str, str] = {
    "ec2": "Compute",
    "virtual machine": "Compute",
    "compute engine": "Compute",
    "elastic compute": "Compute",
    "elastic compute cloud": "Compute",
    "app service": "Compute",
    "cloud run": "Compute",
    "lambda": "Serverless",
    "function": "Serverless",
    "rds": "Database",
    "relational database": "Database",
    "sql": "Database",
    "elasticache": "Database",
    "dynamodb": "Database",
    "cosmos": "Database",
    "spanner": "Database",
    "bigtable": "Database",
    "s3": "Storage",
    "ebs": "Storage",
    "snapshot": "Storage",
    "simple storage service": "Storage",
    "blob": "Storage",
    "storage": "Storage",
    "cloudfront": "CDN",
    "cloud cdn": "CDN",
    "cdn": "CDN",
    "virtual private cloud": "Networking",
    "amazon vpc": "Networking",
    "vpc": "Networking",
    "network": "Networking",
    "public ipv4": "Networking",
    "ipv4 address": "Networking",
    "nat gateway": "Networking",
    "data transfer": "Networking",
    "bandwidth": "Networking",
    "elastic load balancing": "Load Balancing",
    "load balancer": "Load Balancing",
    "key management service": "Security",
    "secrets manager": "Security",
    "cloudwatch": "Monitoring",
    "dashboard": "Monitoring",
    "simple email service": "Messaging",
    "simple queue service": "Messaging",
    "simple notification service": "Messaging",
    "eks": "Kubernetes",
    "aks": "Kubernetes",
    "gke": "Kubernetes",
    "kubernetes": "Kubernetes",
    "sagemaker": "Machine Learning",
    "vertex": "Machine Learning",
    "machine learning": "Machine Learning",
    "redshift": "Data Warehouse",
    "bigquery": "Data Warehouse",
    "synapse": "Data Warehouse",
}
_SERVICE_SKIP_PATTERNS = (
    "savings plans for aws compute",
    "compute savings plan",
    "compute savings plans",
)
_CREDIT_SAVINGS_PATTERNS = (
    "savings plan",
    "reserved instance",
    "committed use",
    "credit",
    "discount",
    "free tier",
)
_CREDIT_SAVINGS_INCLUDE_PATTERNS = (
    "covered by",
    "total savings",
    "discount",
    "credit",
    "free tier",
    "reserved instance",
    "committed use",
)
_CREDIT_SAVINGS_SUMMARY_PATTERNS = (
    "total savings",
    "total credit",
    "total credits",
    "total discount",
    "total discounts",
)
_COMMITMENT_CHARGE_EXCLUDE_PATTERNS = (
    "1 year",
    "3 year",
    "no upfront",
    "partial upfront",
    "all upfront",
    "recurring fee",
)


def _compact_service_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _to_cost_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[\$,€£₹\sA-Za-z]", "", regex=True),
        errors="coerce",
    ).fillna(0.0)


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols_lower = {column.strip().lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        matched = cols_lower.get(candidate.strip().lower())
        if matched:
            return matched
    return None


def _fallback_cost_column(df: pd.DataFrame) -> str | None:
    keywords = ("cost", "amount", "price", "charge", "spend", "total")
    for column in df.columns:
        if any(word in column.lower() for word in keywords):
            parsed = _to_cost_series(df[column])
            if parsed.sum() > 0:
                return column

    for column in df.columns:
        parsed = _to_cost_series(df[column])
        if parsed.notna().sum() > len(df) * 0.3 and parsed.sum() > 0:
            return column
    return None


def _fallback_service_column(df: pd.DataFrame) -> str | None:
    keywords = ("service", "product", "description", "resource", "sku", "meter", "type")
    for column in df.columns:
        col_lower = column.lower()
        if any(word in col_lower for word in keywords):
            return column
    if len(df.columns) > 0:
        return df.columns[0]
    return None


def _detect_provider(df: pd.DataFrame, filename: str) -> str:
    cols = {column.lower() for column in df.columns}

    aws_score = len(cols & {"lineitem/unblendedcost", "lineitem/productcode", "product/productname"})
    azure_score = len(cols & {"servicename", "costinbillingcurrency", "metercategory"})
    gcp_score = len(cols & {"service description", "sku description", "cost ($)"})

    if aws_score >= 1:
        return "aws"
    if azure_score >= 1:
        return "azure"
    if gcp_score >= 1:
        return "gcp"

    file_hint = filename.lower()
    if "aws" in file_hint or "cur" in file_hint:
        return "aws"
    if "azure" in file_hint:
        return "azure"
    if "gcp" in file_hint or "google" in file_hint:
        return "gcp"
    return "generic"


def _categorize_service(service_name: str) -> str:
    lowered = service_name.lower().strip()
    compact = _compact_service_name(lowered)
    priority_patterns = (
        ("data transfer", "Networking"),
        ("bandwidth", "Networking"),
        ("public ipv4", "Networking"),
        ("ipv4 address", "Networking"),
        ("snapshot", "Storage"),
        ("dashboard", "Monitoring"),
        ("cloudwatch", "Monitoring"),
    )
    for key, category in priority_patterns:
        if key in lowered or _compact_service_name(key) in compact:
            return category
    if re.search(r"(?<![a-z0-9])ebs(?![a-z0-9])", lowered):
        return "Storage"
    for key, category in _SERVICE_CATEGORY_MAP.items():
        if key in {"s3", "ec2", "rds", "vpc", "ebs"}:
            if not re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", lowered):
                continue
        if key in lowered or _compact_service_name(key) in compact:
            return category
    return "Other"


def _should_skip_service(service_name: str) -> bool:
    lowered = service_name.lower().strip()
    compact = _compact_service_name(lowered)
    return any(
        pattern in lowered or _compact_service_name(pattern) in compact
        for pattern in _SERVICE_SKIP_PATTERNS
    )


def _is_credit_or_savings_service(service_name: str) -> bool:
    lowered = str(service_name or "").lower().strip()
    compact = _compact_service_name(lowered)
    if lowered.startswith("$") or lowered.startswith("usd ") or lowered.startswith("usd0"):
        return False
    if "beyond" in lowered and "free tier" in lowered:
        return False
    if not any(
        pattern in lowered or _compact_service_name(pattern) in compact
        for pattern in _CREDIT_SAVINGS_PATTERNS
    ):
        return False
    if any(pattern in lowered for pattern in _COMMITMENT_CHARGE_EXCLUDE_PATTERNS) and not any(
        pattern in lowered for pattern in _CREDIT_SAVINGS_INCLUDE_PATTERNS
    ):
        return False
    if "savings plan" in lowered and not any(
        pattern in lowered for pattern in ("covered by", "total savings", "discount", "credit", "negation")
    ):
        return False
    if "reserved instance" in lowered and "covered by" not in lowered and "discount" not in lowered:
        return False
    return True


def _extract_existing_credits_and_savings(
    df: pd.DataFrame,
    service_col: str,
    cost_col: str,
    source_metadata: dict[str, Any],
) -> float:
    metadata_value = source_metadata.get("existing_credits_and_savings")
    if isinstance(metadata_value, (int, float)) and float(metadata_value) > 0:
        return round(float(metadata_value), 2)

    if service_col not in df.columns or cost_col not in df.columns:
        return 0.0

    working = df[[service_col, cost_col]].copy()
    working["__service__"] = working[service_col].fillna("").astype(str)
    working["__cost__"] = _to_cost_series(working[cost_col]).abs()
    credit_rows = working[working["__service__"].map(_is_credit_or_savings_service)]
    if credit_rows.empty:
        return 0.0
    summary_rows = credit_rows[
        credit_rows["__service__"].astype(str).str.lower().map(
            lambda value: any(pattern in value for pattern in _CREDIT_SAVINGS_SUMMARY_PATTERNS)
        )
    ]
    source_rows = summary_rows if not summary_rows.empty else credit_rows
    return round(float(source_rows["__cost__"].sum()), 2)


def _aggregate(df: pd.DataFrame, service_col: str, cost_col: str) -> tuple[dict[str, float], float, list[dict[str, Any]]]:
    """Aggregate tabular bill rows while preserving negative credits/refunds in the net total."""
    working = df.copy()
    working["__service__"] = working[service_col].fillna("Unknown").astype(str)
    working["__cost__"] = _to_cost_series(working[cost_col])
    # Keep negative credit/refund rows in the net total; only drop zero-value noise rows.
    working = working[working["__cost__"] != 0]
    working = working[~working["__service__"].map(_should_skip_service)]

    if working.empty:
        return {}, 0.0, []

    working["__category__"] = working["__service__"].map(_categorize_service)
    category_grouped = working.groupby("__category__")["__cost__"].sum().sort_values(ascending=False)
    service_grouped = working.groupby("__service__")["__cost__"].sum().sort_values(ascending=False)

    by_category = {
        category: round(float(cost), 2)
        for category, cost in category_grouped.items()
        if float(cost) > 0
    }
    total = round(float(category_grouped.sum()), 2)
    top_services = [
        {"service": str(service), "cost": round(float(cost), 2)}
        for service, cost in service_grouped.items()
    ]
    return by_category, total, top_services


def _pdf_line_items_from_metadata(source_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source_metadata.get("bill_line_items")
    if not isinstance(rows, list):
        return []

    line_items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        service = str(row.get("service") or "").strip()
        if not service:
            continue
        try:
            cost = round(float(row.get("cost") or 0.0), 2)
        except (TypeError, ValueError):
            cost = 0.0
        line_items.append(
            {
                "service": service,
                "cost": cost,
                "category": _categorize_service(service),
                "page": int(row.get("page") or 0),
                "line_number": int(row.get("line_number") or 0),
                "line_type": str(row.get("line_type") or "usage_line"),
                "source_line": str(row.get("source_line") or "").strip(),
            }
        )

    return line_items


def _read_dataframe(content: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".csv":
        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                currency = _detect_currency_from_dataframe(df)
                return df, {
                    "source_format": "csv",
                    "source_parser": f"pandas_csv_{encoding}",
                    "currency": currency,
                }
            except Exception:
                continue
        raise ValueError("Could not parse CSV file. Please re-export and try again.")

    if extension in (".xlsx", ".xls"):
        parser_name = "pandas_excel_xlsx" if extension == ".xlsx" else "pandas_excel_xls"
        df = pd.read_excel(io.BytesIO(content))
        currency = _detect_currency_from_dataframe(df)
        return df, {
            "source_format": extension.lstrip("."),
            "source_parser": parser_name,
            "currency": currency,
        }

    if extension == ".pdf":
        return parse_pdf_invoice(content, filename)

    raise ValueError("Unsupported bill format. Upload .csv, .xlsx, .xls, or .pdf.")


def parse_bill(content: bytes, filename: str) -> dict[str, Any]:
    """
    Parse a cloud billing file into normalized analytics payload.
    """
    df, source_metadata = _read_dataframe(content, filename)
    if df.empty:
        raise ValueError("Uploaded bill file is empty.")

    provider = _detect_provider(df, filename)
    if provider == "generic":
        provider_hint = str(source_metadata.get("provider_hint") or "").strip().lower()
        if provider_hint in {"aws", "azure", "gcp"}:
            provider = provider_hint

    if provider == "aws":
        service_col = _first_existing_column(df, _AWS_SERVICE_COLS)
        cost_col = _first_existing_column(df, _AWS_COST_COLS)
    elif provider == "azure":
        service_col = _first_existing_column(df, _AZURE_SERVICE_COLS)
        cost_col = _first_existing_column(df, _AZURE_COST_COLS)
    elif provider == "gcp":
        service_col = _first_existing_column(df, _GCP_SERVICE_COLS)
        cost_col = _first_existing_column(df, _GCP_COST_COLS)
    else:
        service_col = None
        cost_col = None

    service_col = service_col or _fallback_service_column(df)
    cost_col = cost_col or _fallback_cost_column(df)

    if not service_col or not cost_col:
        raise ValueError(
            "Could not detect bill service/cost columns. "
            "Please upload a standard cloud billing CSV/Excel export."
        )

    aggregate_df = df
    aggregate_service_col = service_col
    aggregate_cost_col = cost_col
    service_rollup_records = source_metadata.get("service_rollup_records")
    rollup_df = pd.DataFrame()
    if source_metadata.get("source_format") == "pdf" and isinstance(service_rollup_records, list) and service_rollup_records:
        rollup_df = pd.DataFrame.from_records(service_rollup_records, columns=["Service", "Cost"])

    invoice_total = float(source_metadata.get("invoice_total") or 0)
    category_df = aggregate_df
    category_service_col = aggregate_service_col
    category_cost_col = aggregate_cost_col
    has_pdf_line_items = bool(source_metadata.get("bill_line_items"))
    if source_metadata.get("source_format") == "pdf" and not rollup_df.empty and not has_pdf_line_items:
        category_df = rollup_df
        category_service_col = "Service"
        category_cost_col = "Cost"
    if source_metadata.get("source_format") == "pdf" and invoice_total > 0 and not aggregate_df.empty:
        materiality_threshold = invoice_total * 0.005
        filtered_df = aggregate_df[aggregate_df[aggregate_cost_col] >= materiality_threshold]
        if not filtered_df.empty and rollup_df.empty:
            category_df = filtered_df

    by_category, _category_total, _ = _aggregate(category_df, category_service_col, category_cost_col)
    _, aggregated_total, top_services = _aggregate(aggregate_df, aggregate_service_col, aggregate_cost_col)
    if source_metadata.get("source_format") == "pdf":
        pdf_line_items = _pdf_line_items_from_metadata(source_metadata)
        if pdf_line_items:
            top_services = pdf_line_items
    total_spend = round(invoice_total if invoice_total > 0 else aggregated_total, 2)
    if total_spend <= 0:
        raise ValueError("No billable costs were found in this file.")

    descriptions = df[service_col].fillna("").astype(str).tolist()
    costs = _to_cost_series(df[cost_col]).tolist()
    existing_credits_and_savings = _extract_existing_credits_and_savings(
        df,
        service_col,
        cost_col,
        source_metadata,
    )

    cloudfront_insights = None
    mentions_cloudfront = any("cloudfront" in desc.lower() for desc in descriptions)
    if provider == "aws" and mentions_cloudfront:
        try:
            cloudfront_insights = analyze_cloudfront_bill(descriptions, costs)
        except Exception as error:
            logger.warning("CloudFront deep analysis skipped: %s", error)

    gpu_insights = None
    try:
        gpu_insights = analyze_gpu_billing(df, service_col=service_col, cost_col=cost_col)
    except Exception as error:
        logger.warning("GPU deep analysis skipped: %s", error)

    return {
        "provider": provider,
        "rows_parsed": int(len(df)),
        "total_spend": total_spend,
        "currency": str(source_metadata.get("currency") or "USD").upper(),
        "by_category": by_category,
        "raw_services": top_services,
        "cloudfront_insights": cloudfront_insights,
        "gpu_insights": gpu_insights,
        "source_format": str(source_metadata.get("source_format") or "").strip().lower(),
        "source_parser": str(source_metadata.get("source_parser") or "").strip(),
        "existing_credits_and_savings": existing_credits_and_savings,
        "savings_amount": existing_credits_and_savings,
        "source_metadata": {
            key: value
            for key, value in source_metadata.items()
            if key != "currency"
        },
    }
