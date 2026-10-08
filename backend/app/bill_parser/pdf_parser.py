"""
PDF invoice extraction helpers for billing analysis.

This module supports text-based invoice PDFs. It prefers `pdfplumber` when
available for table-aware extraction, then falls back to a lightweight parser
for embedded PDF text streams so digital invoices remain analyzable even before
the optional dependency is installed. Image-only/scanned PDFs are rejected with
an explicit error because OCR is a separate reliability track.
"""

from __future__ import annotations

import io
import logging
import re
import zlib
from typing import Any, Iterable

import pandas as pd

from .validator import validate_cloud_document

logger = logging.getLogger(__name__)

_PDF_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_PDF_TEXT_RE = re.compile(r"\((?P<text>(?:\\.|[^\\)])*)\)\s*Tj")
_PDF_TEXT_ARRAY_RE = re.compile(r"\[(?P<items>.*?)\]\s*TJ", re.DOTALL)
_PDF_TEXT_ARRAY_ITEM_RE = re.compile(r"\((?P<text>(?:\\.|[^\\)])*)\)")
_PDF_SEGMENT_SPLIT_RE = re.compile(r"\s{2,}|\t+|\s+\|\s+")
_PDF_AMOUNT_TOKEN_RE = re.compile(
    r"(?P<token>(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CHF|Rs\.?|₹|\$|€|£)?\s*-?\(?\d[\d,]*(?:[.,]\d{2,4})?\)?(?:\s?(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CHF))?)",
    re.IGNORECASE,
)
_BARE_AMOUNT_RE = re.compile(r"^\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?$")
_PURE_NUMBER_LABEL_RE = re.compile(r"^\$?[\d,]+\.?\d*$")
_PARENTHESIZED_AMOUNT_RE = re.compile(
    r"\(\s*(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CHF|Rs\.?|₹|\$|€|£)?\s*\d[\d,]*(?:\.\d{2,4})?\s*(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CHF)?\s*\)",
    re.IGNORECASE,
)

_PDF_PROVIDER_HINTS: tuple[tuple[str, str], ...] = (
    ("amazon web services", "aws"),
    ("amazon aws", "aws"),
    ("aws bill", "aws"),
    ("microsoft azure", "azure"),
    ("azure invoice", "azure"),
    ("google cloud", "gcp"),
    ("gcp invoice", "gcp"),
    ("google cloud platform", "gcp"),
)

_PDF_SKIP_LINE_KEYWORDS = (
    "invoice number",
    "invoice no",
    "account number",
    "account id",
    "billing period",
    "bill period",
    "invoice date",
    "statement date",
    "due date",
    "amount due",
    "payment due",
    "bill to",
    "sold to",
    "customer id",
    "subtotal",
    "grand total",
    "tax",
    "vat",
    "gst",
    "balance forward",
    "opening balance",
    "closing balance",
)

_PDF_SKIP_LABEL_PREFIXES = frozenset({
    "estimated grand total",
    "grand total",
    "total pre-tax",
    "total post-tax",
    "total tax",
    "total in usd",
    "service provider",
    "amazon web services india",
    "amazon web services, inc",
    "payable by account",
    "payment information",
    "no data to display",
    "charges by account",
    "charges by service",
    "highest estimated cost",
    "highest service spend",
    "highest aws region",
    "trend compared to prior",
    "billing period",
    "date printed",
    "savings plans discounts",
    "total savings",
    "taxes by service",
    "invoices",
    "tax invoices",
    "total for",
    "charges for",
    "aws service charges",
    "total charges",
    "total aws",
    "balance due",
    "current charges",
    "total amount",
    "summary for",
    "statement total",
})
_PDF_CREDIT_LABEL_PHRASES = frozenset({
    "savings plans discounts",
    "total savings",
    "covered by compute savings plans",
    "free tier",
    "credits",
    "savings plan",
    "compute savings plan",
    "compute savings plans",
    "savings plans for aws compute",
})
_PDF_CREDIT_INCLUDE_PHRASES = frozenset({
    "covered by",
    "total savings",
    "discount",
    "credit",
    "free tier",
    "reserved instance",
    "committed use",
})
_PDF_CREDIT_SUMMARY_PHRASES = frozenset({
    "total savings",
    "total credit",
    "total credits",
    "total discount",
    "total discounts",
})
_PDF_COMMITMENT_CHARGE_PHRASES = frozenset({
    "1 year",
    "3 year",
    "no upfront",
    "partial upfront",
    "all upfront",
    "recurring fee",
})
_PDF_REGION_PREFIXES = (
    "africa",
    "asiapacific",
    "asia",
    "australia",
    "canada",
    "china",
    "europe",
    "middleeast",
    "southamerica",
    "unitedstates",
    "useast",
    "uswest",
    "usgov",
    "pacific",
    "eu",
    "ap",
    "me",
    "sa",
    "ca",
)

_PDF_CURRENCY_CODES = ("USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY", "CHF")
_AWS_UNIT_TOKENS = frozenset({
    "hrs", "hr", "gb", "tb", "mb", "req", "requests", "units",
    "calls", "ms", "per", "each", "instance", "month", "mo",
    "hour", "hours", "days", "day",
})

_KNOWN_SERVICE_ABBREVIATIONS = frozenset({
    "EC2", "RDS", "S3", "KMS", "VPC", "IAM", "SQS", "SNS",
    "SES", "WAF", "CDN", "NAT", "ALB", "NLB", "EBS", "ECS",
    "EKS", "GCP", "USD", "AWS", "GKE", "AKS", "GCS",
})

# Maps spaceless-lowercase → canonical name for known cloud services.
_CANONICAL_SERVICES: dict[str, str] = {
    "elasticloadbalancing": "Elastic Load Balancing",
    "relationaldatabaseservice": "Relational Database Service",
    "virtualprivatecloud": "Virtual Private Cloud",
    "elasticcomputecloud": "Elastic Compute Cloud",
    "elasticache": "ElastiCache",
    "keymanagementservice": "Key Management Service",
    "cloudwatch": "CloudWatch",
    "secretsmanager": "Secrets Manager",
    "simplenotificationservice": "Simple Notification Service",
    "simplestorageservice": "Simple Storage Service",
    "simplequeueservice": "Simple Queue Service",
    "simpleemailservice": "Simple Email Service",
    "cloudfront": "CloudFront",
    "cloudtrail": "CloudTrail",
    "cloudformation": "CloudFormation",
    "codeartifact": "CodeArtifact",
    "codebuild": "CodeBuild",
    "codedeploy": "CodeDeploy",
    "codepipeline": "CodePipeline",
    "codecommit": "CodeCommit",
    "dynamodb": "DynamoDB",
    "eventbridge": "EventBridge",
    "guardduty": "GuardDuty",
    "lightsail": "Lightsail",
    "opensearch": "OpenSearch",
    "opensearchservice": "OpenSearch Service",
    "redshift": "Redshift",
    "sagemaker": "SageMaker",
    "stepfunctions": "Step Functions",
    "systemsmanager": "Systems Manager",
    "webapplicationfirewall": "Web Application Firewall",
    "directconnect": "Direct Connect",
    "elasticbeanstalk": "Elastic Beanstalk",
    "elasticfilesystem": "Elastic File System",
    "elasticblockstore": "Elastic Block Store",
    "elastickubernetesservice": "Elastic Kubernetes Service",
    "elasticcontainerservice": "Elastic Container Service",
    "elasticcontainerregistry": "Elastic Container Registry",
    "elasticmapreduce": "Elastic MapReduce",
    "applicationloadbalancer": "Application Load Balancer",
    "networkloadbalancer": "Network Load Balancer",
    "gatewayloadbalancer": "Gateway Load Balancer",
    "savingsplansdiscounts": "Savings Plans Discounts",
    "datatransfer": "Data Transfer",
    "simplestorage": "Simple Storage",
    "simplequeue": "Simple Queue",
    "simpleemail": "Simple Email",
    "certificatemanager": "Certificate Manager",
    "configservice": "Config Service",
    "costexplorer": "Cost Explorer",
    "identityandaccessmanagement": "Identity and Access Management",
    "apprunner": "App Runner",
    "appmesh": "App Mesh",
    "appflow": "AppFlow",
    "appsync": "AppSync",
    "lambda": "Lambda",
    "apigateway": "API Gateway",
    "athena": "Athena",
    "glue": "Glue",
    "kinesis": "Kinesis",
    "stepfunctions": "Step Functions",
    "amazonec2": "Elastic Compute Cloud",
    "ec2": "Elastic Compute Cloud",
    "amazonelasticcomputecloud": "Amazon Elastic Compute Cloud",
    "amazonrds": "Amazon Relational Database Service",
    "rds": "Relational Database Service",
    "amazons3": "Amazon S3",
    "s3": "Simple Storage Service",
    "amazoncloudwatch": "CloudWatch",
    "lambda": "Lambda",
    "sqs": "Simple Queue Service",
    "sns": "Simple Notification Service",
    "databasemigration": "Database Migration Service",
}

# Pre-sort by length (longest first) so prefix matches are greedy.
_CANONICAL_KEYS_SORTED = sorted(_CANONICAL_SERVICES.keys(), key=len, reverse=True)


def clean_service_name(raw: str) -> str:
    """
    Fix word-split artifacts from PDF character spacing extraction.
    """
    if not raw:
        return raw

    is_detail_label = " - " in raw or raw.strip().startswith("$") or raw.upper().startswith("USD")

    # 1. Aggressively remove trailing currency and metadata artifacts.
    # For detailed SKU/rate rows, keep parenthetical product/region details.
    cleaned = raw.strip()
    if not is_detail_label:
        cleaned = re.sub(r'[\s]*\(.*?\).*$', '', cleaned).strip()
    cleaned = re.sub(r'[\s]*U[\s]*S[\s]*D[\s]*$', '', cleaned, flags=re.IGNORECASE).strip()

    if not cleaned:
        return raw.strip()

    if is_detail_label:
        return re.sub(r"\s+", " ", cleaned).strip()

    # 2. Collapse all whitespace for inner lookup
    spaceless = re.sub(r'\s+', '', cleaned).lower()

    # 3. Try exact, prefix, or suffix match against canonical names
    # This handles "Amazon RDS", "RDS (1)", etc.
    for key in _CANONICAL_KEYS_SORTED:
        if spaceless == key or spaceless.startswith(key) or spaceless.endswith(key):
            return _CANONICAL_SERVICES[key]

    # 4. Fallback: Fix common word-break artifacts
    cleaned = re.sub(r'Databa\s+se', 'Database', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'CloudWatc\s+h', 'CloudWatch', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'ElastiCach\s+e', 'ElastiCache', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Balan\s+cing', 'Balancing', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Servic\s+e', 'Service', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def _clean_label_tokens(label: str) -> str:
    """Remove unit tokens and bare numbers from a label string."""
    parts = label.split()
    cleaned = []
    for part in parts:
        stripped = part.lower().strip("(),.")
        if stripped in _AWS_UNIT_TOKENS:
            continue
        if re.match(r"^\d+(\.\d+)?$", stripped):
            continue
        cleaned.append(part)
    return " ".join(cleaned).strip()


def _normalize_label_text(label: str) -> str:
    return re.sub(r"\s+", " ", str(label or "")).strip().lower().strip(" :-|")


def _compact_label_text(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_label_text(label))


def _should_skip_summary_label(label: str) -> bool:
    normalized = _normalize_label_text(label)
    compact = _compact_label_text(label)
    return any(
        normalized == pattern
        or normalized.startswith(f"{pattern} ")
        or compact.startswith(_compact_label_text(pattern))
        for pattern in _PDF_SKIP_LABEL_PREFIXES
    )


def _is_credit_label(label: str) -> bool:
    normalized = _normalize_label_text(label)
    compact = _compact_label_text(label)
    if normalized.startswith("$") or normalized.startswith("usd ") or normalized.startswith("usd0"):
        return False
    if "beyond" in normalized and "free tier" in normalized:
        return False
    if not any(
        phrase in normalized or _compact_label_text(phrase) in compact
        for phrase in _PDF_CREDIT_LABEL_PHRASES
    ):
        return False
    if any(phrase in normalized for phrase in _PDF_COMMITMENT_CHARGE_PHRASES) and not any(
        phrase in normalized for phrase in _PDF_CREDIT_INCLUDE_PHRASES
    ):
        return False
    if "savings plan" in normalized and not any(
        phrase in normalized for phrase in ("covered by", "total savings", "discount", "credit")
    ):
        return False
    return True


def _is_region_rollup_label(label: str) -> bool:
    normalized = _normalize_label_text(label)
    compact = _compact_label_text(label)
    if "(" not in normalized or ")" not in normalized:
        return False
    return any(compact.startswith(prefix) for prefix in _PDF_REGION_PREFIXES)


def _is_pricing_detail_label(label: str) -> bool:
    normalized = _normalize_label_text(label)
    compact = _compact_label_text(label)
    return (
        normalized.startswith("$")
        or normalized.startswith("usd ")
        or normalized.startswith("usd0")
        or " per " in normalized
        or compact.startswith("usd")
    )


def _extract_invoice_total(lines: Iterable[str]) -> float | None:
    total_prefixes = (
        "estimated grand total",
        "grand total",
        "total pre-tax",
        "total post-tax",
    )

    for line in lines:
        if not _should_skip_summary_label(line):
            continue
        compact_line = _compact_label_text(line)
        if not any(compact_line.startswith(_compact_label_text(prefix)) for prefix in total_prefixes):
            continue
        for match in reversed(list(_PDF_AMOUNT_TOKEN_RE.finditer(line))):
            amount, _currency = _normalize_amount_token(match.group("token"))
            if amount is not None and amount > 0:
                return round(float(amount), 2)
    return None


def _extract_service_rollup_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rollups: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()

    for index, record in enumerate(records[:-1]):
        label = str(record.get("Service") or "").strip()
        amount = round(float(record.get("Cost") or 0), 4)
        next_record = records[index + 1]
        next_label = str(next_record.get("Service") or "").strip()
        next_amount = round(float(next_record.get("Cost") or 0), 4)

        if (
            not label
            or label.startswith("$")
            or label.upper().startswith("USD ")
            or _should_skip_summary_label(label)
            or _is_credit_label(label)
            or _is_region_rollup_label(label)
            or _PURE_NUMBER_LABEL_RE.match(label)
            or _normalize_label_text(label) == "any"
        ):
            continue

        if abs(amount - next_amount) >= 0.001 or not _is_region_rollup_label(next_label):
            continue

        key = (_compact_label_text(label), amount)
        if key in seen:
            continue
        seen.add(key)
        rollups.append({
            "Service": label,
            "Cost": amount,
        })

    return rollups


def _extract_credit_savings_records(lines: Iterable[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()

    for raw_line in lines:
        normalized = re.sub(r"\s+", " ", str(raw_line or "")).strip()
        if not normalized:
            continue

        normalized_label = _normalize_label_text(normalized)
        if not _is_credit_label(normalized_label):
            continue

        amount: float | None = None
        amount_match_start = len(normalized)
        parenthesized_match = None
        parenthesized_matches = list(_PARENTHESIZED_AMOUNT_RE.finditer(normalized))
        if parenthesized_matches:
            parenthesized_match = parenthesized_matches[-1]
            amount_match_start = min(amount_match_start, parenthesized_match.start())
            token = parenthesized_match.group(0).strip()
            inner_token = token[1:-1].strip()
            amount, _ = _normalize_amount_token(inner_token)

        if amount is None:
            for match in reversed(list(_PDF_AMOUNT_TOKEN_RE.finditer(normalized))):
                parsed_amount, _ = _normalize_amount_token(match.group("token"))
                if parsed_amount is None:
                    continue
                amount = parsed_amount
                amount_match_start = min(amount_match_start, match.start())
                break

        if amount is None or abs(float(amount)) < 0.001:
            continue

        label = normalized[:amount_match_start].strip(" :-|()") or normalized
        if not label:
            continue

        key = (_compact_label_text(label), round(abs(float(amount)), 4))
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "label": label,
                "amount": round(abs(float(amount)), 4),
            }
        )

    summary_records = [
        record
        for record in records
        if any(phrase in _normalize_label_text(record.get("label")) for phrase in _PDF_CREDIT_SUMMARY_PHRASES)
    ]
    if summary_records:
        return summary_records

    return records


def _rollup_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Rolls up records by service name, summing costs for identical services.
    This ensures no data is lost even if the PDF has multiple entries for the same service.
    """
    rolled_up: dict[str, float] = {}
    seen_exact_rows: set[tuple[str, float]] = set()

    for record in records:
        raw_label = str(record.get("Service") or "").strip()
        if not raw_label:
            continue

        label = clean_service_name(raw_label)
        amount = float(record.get("Cost") or 0.0)

        if abs(amount) < 0.001:
            continue

        exact_row_key = (_compact_label_text(label), round(amount, 4))
        if exact_row_key in seen_exact_rows:
            continue
        seen_exact_rows.add(exact_row_key)

        rolled_up[label] = rolled_up.get(label, 0.0) + amount

    return [
        {"Service": label, "Cost": round(max(0.0, cost), 4)}
        for label, cost in rolled_up.items()
        if round(max(0.0, cost), 4) > 0
    ]


def _clean_pdf_line_item_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    line_items: list[dict[str, Any]] = []
    seen_exact_rows: set[tuple[str, float, str]] = set()

    for record in records:
        raw_label = str(record.get("Service") or "").strip()
        if not raw_label:
            continue

        label = clean_service_name(raw_label)
        amount = round(float(record.get("Cost") or 0.0), 4)
        source_line = re.sub(r"\s+", " ", str(record.get("source_line") or "")).strip()
        exact_row_key = (_compact_label_text(label), amount, source_line)
        if exact_row_key in seen_exact_rows:
            continue
        seen_exact_rows.add(exact_row_key)

        line_items.append(
            {
                "Service": label,
                "Cost": amount,
                "Page": int(record.get("page") or 0),
                "LineNumber": int(record.get("line_number") or 0),
                "SourceLine": source_line,
                "LineType": str(record.get("line_type") or "usage_line").strip() or "usage_line",
            }
        )

    return line_items


def _remove_pdf_rollup_records(
    records: list[dict[str, Any]],
    service_rollup_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep leaf/detail charge rows while dropping duplicated PDF parent rollups."""
    service_rollup_labels = {
        _compact_label_text(record.get("Service"))
        for record in service_rollup_records
        if record.get("Service")
    }
    child_totals_by_parent: dict[str, float] = {}
    child_counts_by_parent: dict[str, int] = {}
    for record in records:
        label = str(record.get("Service") or "").strip()
        if " - " not in label:
            continue
        parent = label.split(" - ", 1)[0].strip()
        if not parent:
            continue
        parent_key = _compact_label_text(parent)
        child_totals_by_parent[parent_key] = child_totals_by_parent.get(parent_key, 0.0) + float(record.get("Cost") or 0)
        child_counts_by_parent[parent_key] = child_counts_by_parent.get(parent_key, 0) + 1

    filtered: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        label = str(record.get("Service") or "").strip()
        amount = float(record.get("Cost") or 0)
        label_key = _compact_label_text(label)
        cleaned_label_key = _compact_label_text(clean_service_name(label))
        if (
            not label
            or label_key in service_rollup_labels
            or cleaned_label_key in service_rollup_labels
            or _is_region_rollup_label(label)
            or _should_skip_summary_label(label)
            or _is_credit_label(label)
            or _PURE_NUMBER_LABEL_RE.match(label)
            or _normalize_label_text(label) == "any"
        ):
            continue

        child_total = child_totals_by_parent.get(label_key, 0.0)
        child_count = child_counts_by_parent.get(label_key, 0)
        if child_count >= 2 and abs(child_total - amount) <= max(0.02, abs(amount) * 0.01):
            continue

        if cleaned_label_key == "cloudwatch":
            cloudwatch_child_total = sum(
                float(other.get("Cost") or 0)
                for other in records
                if _compact_label_text(other.get("Service")) != label_key
                and "cloudwatch" in _compact_label_text(other.get("Service"))
                and " - " in str(other.get("Service") or "")
            )
            if abs(cloudwatch_child_total - amount) <= max(0.02, abs(amount) * 0.02):
                continue

        next_record = records[index + 1] if index + 1 < len(records) else None
        if isinstance(next_record, dict):
            next_label = str(next_record.get("Service") or "").strip()
            next_amount = float(next_record.get("Cost") or 0)
            if abs(next_amount - amount) <= 0.02 and (
                len(next_label) > len(label)
                or "|" in next_label
                or _is_pricing_detail_label(next_label)
            ):
                continue

        filtered.append(record)
    return filtered


def _normalize_pdf_lines(lines: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw_line in lines:
        line = re.sub(r"\s+", " ", str(raw_line or "")).strip()
        if line:
            normalized.append(line)
    return normalized


def _unescape_pdf_text(value: str) -> str:
    """
    Unescape the most common PDF string escapes.
    """
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        index += 1
        if index >= len(value):
            break

        escaped = value[index]
        if escaped in {"\\", "(", ")"}:
            result.append(escaped)
            index += 1
            continue
        if escaped == "n":
            result.append("\n")
            index += 1
            continue
        if escaped == "r":
            result.append("\r")
            index += 1
            continue
        if escaped == "t":
            result.append("\t")
            index += 1
            continue
        if escaped == "b":
            result.append("\b")
            index += 1
            continue
        if escaped == "f":
            result.append("\f")
            index += 1
            continue
        if escaped.isdigit():
            octal_digits = escaped
            for _ in range(2):
                if index + 1 < len(value) and value[index + 1].isdigit():
                    index += 1
                    octal_digits += value[index]
                else:
                    break
            try:
                result.append(chr(int(octal_digits, 8)))
            except ValueError:
                pass
            index += 1
            continue

        result.append(escaped)
        index += 1
    return "".join(result)


def _decode_pdf_streams(content: bytes) -> list[str]:
    lines: list[str] = []

    for match in _PDF_STREAM_RE.finditer(content):
        payload = match.group(1)
        candidates: list[bytes] = [payload]

        for decompressor in (
            lambda value: zlib.decompress(value),
            lambda value: zlib.decompress(value, -15),
        ):
            try:
                decoded = decompressor(payload)
            except Exception:
                continue
            if decoded not in candidates:
                candidates.append(decoded)

        for candidate in candidates:
            text = candidate.decode("latin-1", errors="ignore")
            tokens: list[tuple[int, str]] = []

            for text_match in _PDF_TEXT_RE.finditer(text):
                tokens.append((text_match.start(), _unescape_pdf_text(text_match.group("text"))))

            for array_match in _PDF_TEXT_ARRAY_RE.finditer(text):
                items = [
                    _unescape_pdf_text(item_match.group("text"))
                    for item_match in _PDF_TEXT_ARRAY_ITEM_RE.finditer(array_match.group("items"))
                ]
                merged = "".join(item for item in items if item)
                if merged:
                    tokens.append((array_match.start(), merged))

            for _, token in sorted(tokens, key=lambda item: item[0]):
                if token.strip():
                    lines.append(token)

    return _normalize_pdf_lines(lines)


def _extract_with_pdfplumber(content: bytes) -> tuple[list[str], dict[str, Any]]:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return [], {
            "extractors_used": [],
            "page_count": 0,
            "table_rows_detected": 0,
            "text_lines_detected": 0,
        }

    lines: list[str] = []
    text_lines: list[str] = []
    table_lines: list[str] = []
    source_text_pages: list[dict[str, Any]] = []
    page_count = 0
    table_rows_detected = 0
    text_lines_detected = 0

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            for page_number, page in enumerate(pdf.pages, start=1):
                # Use layout=True to keep physical spaces intact between service names and dollar amounts
                try:
                    page_text = page.extract_text(layout=True) or page.extract_text() or ""
                except TypeError:
                    page_text = page.extract_text() or ""
                except Exception as error:
                    logger.debug("pdfplumber text extraction skipped on page: %s", error)
                    page_text = ""

                page_lines = [line for line in page_text.splitlines() if str(line).strip()]
                normalized_page_lines = _normalize_pdf_lines(page_lines)
                source_text_pages.append({"page": page_number, "lines": normalized_page_lines})
                # Remove mutually exclusive logic. AWS/GCP bills heavily rely on standard
                # layout text, while table parsers fail on invisible borders.
                # Keep the layout-preserved text.
                text_lines.extend(page_lines)
                text_lines_detected += len(normalized_page_lines)

                try:
                    tables = page.extract_tables() or []
                except Exception as error:
                    logger.debug("pdfplumber table extraction skipped on page: %s", error)
                    tables = []

                for table in tables:
                    for row in table or []:
                        cells = [
                            re.sub(r"\s+", " ", str(cell or "")).strip()
                            for cell in (row or [])
                            if str(cell or "").strip()
                        ]
                        if len(cells) < 2:
                            continue
                        table_lines.append("  ".join(cells))
                        table_rows_detected += 1

            lines = [*text_lines, *table_lines]
    except Exception as error:
        logger.warning("pdfplumber PDF extraction failed, falling back to stream parser: %s", error)
        return [], {
            "extractors_used": [],
            "page_count": 0,
            "table_rows_detected": 0,
            "text_lines_detected": 0,
        }

    return _normalize_pdf_lines(lines), {
        "extractors_used": ["pdfplumber"],
        "page_count": page_count,
        "table_rows_detected": table_rows_detected,
        "text_lines_detected": text_lines_detected,
        "source_text_pages": source_text_pages,
    }


def _detect_provider_from_text(lines: list[str]) -> str | None:
    text = " ".join(lines).lower()
    for needle, provider in _PDF_PROVIDER_HINTS:
        if needle in text:
            return provider
    return None


def _detect_currency_from_text(lines: list[str]) -> str:
    text = " ".join(lines)
    text_upper = text.upper()

    # Symbol checks — highest confidence
    if "\u20b9" in text:
        return "INR"
    if "\u20ac" in text:
        return "EUR"
    if "\u00a3" in text:
        return "GBP"

    # Rupee textual markers (e.g. "Rs.", "Rs " in header)
    if re.search(r"\bRS\.?\b", text_upper):
        return "INR"

    # ISO code checks — look for the code surrounded by word boundaries so
    # "AUD" in "FRAUD" doesn't trigger a false positive.
    # Priority order: less-common codes first so USD doesn't crowd them out.
    for code in ("INR", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY"):
        if re.search(rf"(?<![A-Z]){code}(?![A-Z])", text_upper):
            return code

    return "USD"


def _normalize_amount_token(token: str) -> tuple[float | None, str | None]:
    raw = str(token or "").strip()
    if not raw:
        return None, None
    if raw.startswith("(") and raw.endswith(")"):
        return None, None

    currency: str | None = None
    upper = raw.upper()
    has_currency_marker = any(symbol in raw for symbol in ("$", "€", "£", "₹")) or "RS." in upper
    if "₹" in raw or "RS." in upper or " INR" in upper:
        currency = "INR"
    elif "€" in raw or " EUR" in upper:
        currency = "EUR"
    elif "£" in raw or " GBP" in upper:
        currency = "GBP"
    else:
        for code in _PDF_CURRENCY_CODES:
            if code in upper:
                currency = code
                break
        if currency is None and "$" in raw:
            currency = "USD"

    alpha_tokens = re.findall(r"[A-Za-z]+", raw)
    allowed_alpha_tokens = {code.upper() for code in _PDF_CURRENCY_CODES} | {"RS"}
    if alpha_tokens and any(token.upper() not in allowed_alpha_tokens for token in alpha_tokens):
        return None, None
    if currency:
        has_currency_marker = True

    # AWS invoices: bare decimal amounts with no currency symbol
    # Pattern: optional leading (, digits with comma separators, period, 2 decimals, optional )
    # NOTE: We leave currency as None here — the caller will fill in the
    # document-level currency detected by _detect_currency_from_text so we
    # don't blindly assume USD for non-US invoices.
    if not has_currency_marker and _BARE_AMOUNT_RE.match(raw):
        has_currency_marker = True
        # currency remains None; resolved at the document level

    if re.search(r"[A-Za-z]", raw) and not has_currency_marker:
        return None, None

    if not has_currency_marker and not re.search(r"[.,]\d{2,4}\)?(?:\s*[A-Z]{0,4})?$", raw):
        return None, None

    cleaned = re.sub(r"[^0-9,.\-()]", "", raw)
    if not cleaned or not any(char.isdigit() for char in cleaned):
        return None, currency

    negative = cleaned.startswith("-") or (cleaned.startswith("(") and cleaned.endswith(")"))
    cleaned = cleaned.strip("()")

    if cleaned.count(",") and cleaned.count("."):
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") > 1:
        cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") == 1 and "." not in cleaned:
        left, right = cleaned.split(",", 1)
        cleaned = f"{left}.{right}" if len(right) == 2 else f"{left}{right}"

    try:
        amount = float(cleaned)
    except ValueError:
        return None, currency

    if negative:
        amount *= -1

    return amount, currency


def _parse_pdf_line_item(
    line: str,
    *,
    carry_label: str | None,
    page_number: int | None = None,
    line_number: int | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    normalized = re.sub(r"\s+", " ", line).strip()
    if not normalized:
        return None, carry_label
    if _should_skip_summary_label(normalized):
        return None, carry_label
    if _PARENTHESIZED_AMOUNT_RE.search(normalized):
        return None, carry_label

    # Only skip pure header lines — not service lines that happen to
    # contain a skip word within a longer name
    _SUMMARY_SKIP_EXACT = frozenset({
        "total", "subtotal", "grand total", "total due", "invoice total",
        "total charges", "tax", "vat", "gst", "balance forward",
        "opening balance", "closing balance", "amount due", "payment due",
        "bill to", "sold to", "customer id", "invoice number", "invoice no",
        "account number", "account id", "billing period", "bill period",
        "invoice date", "statement date", "due date",
        "aws service charges", "current charges", "total for linked account",
    })
    normalized_check = re.sub(r"\s+", " ", normalized.split("  ")[0].lower()).strip(" :-")
    if normalized_check in _SUMMARY_SKIP_EXACT:
        return None, carry_label

    if not re.sub(_PDF_AMOUNT_TOKEN_RE, "", normalized).strip(" :-|"):
        return None, carry_label

    segments = [segment.strip(" :-") for segment in _PDF_SEGMENT_SPLIT_RE.split(normalized) if segment.strip(" :-")]
    best_amount: float | None = None
    best_currency: str | None = None
    best_label: str | None = None

    for index in range(len(segments) - 1, -1, -1):
        amount, currency = _normalize_amount_token(segments[index])
        if amount is None:
            continue
        label_segments = [segment for segment in segments[:index] if _normalize_amount_token(segment)[0] is None]
        label = _clean_label_tokens(
            " ".join(label_segments).strip() or carry_label or ""
        ) or carry_label
        if label:
            best_amount = amount
            best_currency = currency
            best_label = label
            break

    if best_amount is None:
        matches = list(_PDF_AMOUNT_TOKEN_RE.finditer(normalized))
        for match in reversed(matches):
            amount, currency = _normalize_amount_token(match.group("token"))
            if amount is None:
                continue
            label = _clean_label_tokens(
                normalized[:match.start()].strip(" :-|") or carry_label or ""
            ) or carry_label
            if label:
                best_amount = amount
                best_currency = currency
                best_label = label
                break

    if best_amount is None or not best_label:
        if re.search(r"[A-Za-z]", normalized) and len(normalized) <= 120:
            if _should_skip_summary_label(normalized):
                return None, carry_label
            if normalized.startswith("(") and normalized.endswith(")"):
                return None, carry_label
            return None, normalized
        return None, carry_label

    if not best_label:
        return None, carry_label

    if best_label.lower().strip() in _SUMMARY_SKIP_EXACT:
        return None, carry_label

    clean_lower_label = best_label.lower().strip()
    if clean_lower_label in _SUMMARY_SKIP_EXACT or clean_lower_label.startswith("total for "):
        return None, carry_label

    if _should_skip_summary_label(best_label):
        return None, carry_label
    if _is_credit_label(best_label):
        return None, carry_label
    if _PURE_NUMBER_LABEL_RE.match(best_label.strip()):
        return None, carry_label
    is_pricing_detail = _is_pricing_detail_label(best_label)
    if is_pricing_detail:
        if not carry_label:
            return None, carry_label
        best_label = f"{carry_label} - {best_label}"
    if _normalize_label_text(best_label) == "any":
        return None, carry_label
    amount_val = float(best_amount)

    next_carry_label = carry_label if is_pricing_detail or _is_region_rollup_label(best_label) else best_label
    if is_pricing_detail:
        line_type = "usage_detail"
    elif "|" in best_label:
        line_type = "usage_code"
    elif abs(amount_val) < 0.001:
        line_type = "zero_amount_line"
    else:
        line_type = "service_line"
    return {
        "Service": best_label,
        "Cost": round(amount_val, 4),
        "currency": best_currency,
        "page": page_number or 0,
        "line_number": line_number or 0,
        "source_line": normalized,
        "line_type": line_type,
    }, next_carry_label


def _source_line_entries(lines: list[str], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    pages = metadata.get("source_text_pages") if isinstance(metadata.get("source_text_pages"), list) else []
    entries: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_number = int(page.get("page") or 0)
        page_lines = page.get("lines") if isinstance(page.get("lines"), list) else []
        for line_number, line in enumerate(page_lines, start=1):
            normalized = re.sub(r"\s+", " ", str(line or "")).strip()
            if normalized:
                entries.append({"page": page_number, "line_number": line_number, "line": normalized})

    if entries:
        return entries

    return [
        {"page": 1, "line_number": index, "line": line}
        for index, line in enumerate(lines, start=1)
    ]


def _bill_line_item_payload(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for record in records:
        payload.append(
            {
                "service": str(record.get("Service") or "").strip(),
                "cost": round(float(record.get("Cost") or 0.0), 4),
                "page": int(record.get("Page") or record.get("page") or 0),
                "line_number": int(record.get("LineNumber") or record.get("line_number") or 0),
                "line_type": str(record.get("LineType") or record.get("line_type") or "usage_line"),
                "source_line": str(record.get("SourceLine") or record.get("source_line") or "").strip(),
            }
        )
    return payload


def parse_pdf_invoice(content: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Parse a text-based PDF invoice into a normalized DataFrame.
    """
    lines, metadata = _extract_with_pdfplumber(content)

    if not lines:
        fallback_lines = _decode_pdf_streams(content)
        if fallback_lines:
            lines = fallback_lines
            metadata = {
                **metadata,
                "extractors_used": [*metadata.get("extractors_used", []), "internal_text_layer"],
                "text_lines_detected": len(fallback_lines),
            }

    if not lines:
        raise ValueError(
            "Could not extract readable text from this PDF invoice. "
            "Upload a text-based invoice PDF or a CSV/Excel export."
        )

    # Domain validation: reject non-cloud documents before attempting line-item extraction
    combined_text = " ".join(
        str(line.get("line") if isinstance(line, dict) else line or "").strip()
        for line in lines
        if (line.get("line") if isinstance(line, dict) else line)
    )[:8000]
    domain_check = validate_cloud_document(combined_text)
    if not domain_check.is_cloud_bill:
        raise ValueError(domain_check.rejection_reason or "Not a cloud provider bill.")

    raw_records: list[dict[str, Any]] = []
    carry_label: str | None = None
    currencies: list[str] = []
    source_entries = _source_line_entries(lines, metadata)
    for source_entry in source_entries:
        record, carry_label = _parse_pdf_line_item(
            str(source_entry.get("line") or ""),
            carry_label=carry_label,
            page_number=int(source_entry.get("page") or 0),
            line_number=int(source_entry.get("line_number") or 0),
        )
        if not record:
            continue
        currency = str(record.pop("currency") or "").strip().upper()
        if currency:
            currencies.append(currency)
        raw_records.append(record)

    if not raw_records:
        raise ValueError(
            "This PDF invoice did not expose service-level charges. "
            "Upload a detailed text-based invoice PDF or a CSV/Excel billing export."
        )

    service_rollup_records = _extract_service_rollup_records(raw_records)
    for rollup in service_rollup_records:
        rollup["Service"] = clean_service_name(str(rollup.get("Service") or ""))
    records = _clean_pdf_line_item_records(_remove_pdf_rollup_records(raw_records, service_rollup_records))
    positive_records = [record for record in records if float(record.get("Cost") or 0) > 0]
    if not positive_records:
        raise ValueError(
            "This PDF invoice did not expose service-level charges. "
            "Upload a detailed text-based invoice PDF or a CSV/Excel billing export."
        )

    # Note: Service names are already cleaned inside _rollup_records

    # Resolve the document currency using a two-stage approach:
    # 1. Take the majority vote from per-line currency hints (populated when
    #    the parser found an explicit symbol like $, ₹, €, or an ISO code).
    # 2. Cross-check with the full-document text scan which is more reliable
    #    for invoices that only print a currency header once (not per line).
    doc_level_currency = _detect_currency_from_text(lines)
    if currencies:
        # Majority vote among per-line detected currencies
        from collections import Counter
        currency_counts = Counter(currencies)
        majority_currency = currency_counts.most_common(1)[0][0]
        # If doc-level and per-line majority agree, great. If they disagree,
        # prefer doc-level since it scans the whole document header/footer
        # which always has the authoritative currency label.
        if doc_level_currency != "USD" and majority_currency == "USD":
            # Document header says non-USD but per-line defaulted to USD —
            # doc-level wins (per-line USD was a bare-amount default, not explicit).
            currency = doc_level_currency
        else:
            currency = majority_currency
    else:
        currency = doc_level_currency
    provider_hint = _detect_provider_from_text(lines)
    df = pd.DataFrame.from_records(
        records,
        columns=["Service", "Cost", "Page", "LineNumber", "SourceLine", "LineType"],
    )
    invoice_total = _extract_invoice_total(lines)
    credit_savings_records = _extract_credit_savings_records(lines)
    existing_credits_and_savings = round(
        sum(float(record.get("amount") or 0.0) for record in credit_savings_records),
        2,
    )

    return df, {
        **metadata,
        "source_format": "pdf",
        "source_parser": "pdf_invoice_parser",
        "currency": currency or "USD",
        "provider_hint": provider_hint,
        "line_items_detected": len(records),
        "positive_line_items_detected": len(positive_records),
        "zero_line_items_detected": len(records) - len(positive_records),
        "source_money_rows_detected": len(raw_records),
        "invoice_total": invoice_total,
        "service_rollup_records": service_rollup_records,
        "bill_line_items": _bill_line_item_payload(records),
        "bill_source_rows": _bill_line_item_payload(raw_records),
        "existing_credits_and_savings": existing_credits_and_savings,
        "credit_savings_records": credit_savings_records,
        "pdf_parser_version": "2026-04-28-source-line-items",
        "sample_lines": lines[:8],
        "filename": filename,
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    backend_root = Path(__file__).resolve().parents[2]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.bill_parser import parse_bill

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python backend/app/bill_parser/pdf_parser.py path/to/aws_bill.pdf")

    bill_path = Path(sys.argv[1])
    result = parse_bill(bill_path.read_bytes(), bill_path.name)
    logger.info("Total: $%.2f", result["total_spend"])
    logger.info("Rows: %s", result["rows_parsed"])
    logger.info("Categories: %s", result["by_category"])
    assert 800 < result["total_spend"] < 900, f"FAIL: total={result['total_spend']}"
    assert result["rows_parsed"] < 200, f"FAIL: rows={result['rows_parsed']}"
    logger.info("PASS")
