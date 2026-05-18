import logging
import json
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import ClerkUser, get_current_user
from ..db import MongoDBClient, get_db_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Dashboard Reads"])


def _is_active_integration(integration: dict) -> bool:
    return str(integration.get("status") or "").strip().lower() == "active"


async def _active_integration_ids(db: MongoDBClient, user_id: str) -> set[str]:
    integrations = await db.get_user_integrations(user_id)
    return {
        str(integration.get("id") or "").strip()
        for integration in integrations
        if _is_active_integration(integration) and str(integration.get("id") or "").strip()
    }


class WasteDistributionItem(BaseModel):
    category_name: str
    value: float


class WasteDistributionResponse(BaseModel):
    waste_distribution: list[WasteDistributionItem] = Field(default_factory=list)
    count: int


class GovernanceScoreResponse(BaseModel):
    value: int
    trend: Literal["up", "down", "stable"]
    rating: Literal["Excellent", "Good", "Fair", "Critical"]


class GovernanceTaggingAssetResponse(BaseModel):
    id: str
    name: str
    missing: list[str] = Field(default_factory=list)


class GovernanceTaggingResponse(BaseModel):
    missingTags: int
    costImpact: float
    assets: list[GovernanceTaggingAssetResponse] = Field(default_factory=list)


class GovernanceBudgetResponse(BaseModel):
    projectedSpend: float
    budgetLimit: float
    burnRate: int
    status: Literal["Safe", "Warning", "Excess"]
    alert: str


class GovernanceOfficeHoursResponse(BaseModel):
    savings: float
    enabled: bool
    recommendation: str


class GovernancePolicyResponse(BaseModel):
    id: str
    name: str
    status: Literal["Pass", "Fail"]
    severity: Literal["Critical", "High", "Medium", "Low"]
    reason: str
    framework: str


class GovernanceTrendPointResponse(BaseModel):
    date: str
    score: int


class GovernancePolicyRecordResponse(BaseModel):
    id: str
    name: str
    description: str
    policy_type: str
    is_active: bool
    compliance_rate: float
    violations: int
    created_at: str


class GovernancePoliciesResponse(BaseModel):
    policies: list[GovernancePolicyRecordResponse] = Field(default_factory=list)
    count: int


class GovernanceFrameworkSummaryItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    framework: str
    pass_count: int = Field(alias="pass")
    fail: int
    total: int


class GovernanceAgentNotificationResponse(BaseModel):
    id: str
    recommendation: str
    status: str
    type: str
    resource_id: str
    created_at: str
    metadata: dict[str, object] = Field(default_factory=dict)


class GovernanceSecurityResourceResponse(BaseModel):
    id: str
    resource_id: str
    resource_name: str
    resource_type: str
    provider: str
    region: str
    status: str


class GovernancePolicyViolationResponse(BaseModel):
    id: str
    policy_id: str
    resource_id: str
    resource: str
    provider: str
    category: str
    rule_category: str
    severity: str
    status: str
    description: str
    message: str
    detected_at: str
    created_at: str


class GovernanceAnalysisResponse(BaseModel):
    score: GovernanceScoreResponse
    tagging: GovernanceTaggingResponse
    budget: GovernanceBudgetResponse
    officeHours: GovernanceOfficeHoursResponse
    policies: list[GovernancePolicyResponse] = Field(default_factory=list)
    trends: list[GovernanceTrendPointResponse] = Field(default_factory=list)
    frameworkSummary: list[GovernanceFrameworkSummaryItemResponse] = Field(default_factory=list)
    agentNotifications: list[GovernanceAgentNotificationResponse] = Field(default_factory=list)
    resources: list[GovernanceSecurityResourceResponse] = Field(default_factory=list)
    policyViolations: list[GovernancePolicyViolationResponse] = Field(default_factory=list)


class SecurityPostureSummaryResponse(BaseModel):
    score: int
    rating: Literal["No data", "Strong", "Moderate", "Weak", "Critical"]
    critical: int
    high: int
    open: int
    exposed_resources: int
    monitored_resources: int
    last_detected_at: Optional[str] = None


class SecurityBreakdownItemResponse(BaseModel):
    name: str
    count: int


class SecurityFindingResponse(BaseModel):
    id: str
    resource_id: str
    resource: str
    provider: str
    region: str
    category: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    status: str
    description: str
    detected_at: str
    source: Literal["policy_violation", "agent_notification"]
    remediation: str


class SecurityExposedResourceResponse(BaseModel):
    id: str
    resource_id: str
    resource_name: str
    resource_type: str
    provider: str
    region: str
    highest_severity: Literal["critical", "high", "medium", "low", "info"]
    risk_count: int
    exposure: str
    status: str


class SecurityPostureResponse(BaseModel):
    summary: SecurityPostureSummaryResponse
    findingsBySeverity: list[SecurityBreakdownItemResponse] = Field(default_factory=list)
    findingsByCategory: list[SecurityBreakdownItemResponse] = Field(default_factory=list)
    activeFindings: list[SecurityFindingResponse] = Field(default_factory=list)
    exposedResources: list[SecurityExposedResourceResponse] = Field(default_factory=list)
    recentAlerts: list[SecurityFindingResponse] = Field(default_factory=list)


_SECURITY_POLICY_TYPES = {
    "security",
    "storage_security",
    "network",
    "network_security",
    "iam",
    "identity",
    "permission",
    "permissions",
    "encryption",
}
_SECURITY_NOTIFICATION_TYPES = {"security_alert", "permission_alert"}
_ACTIVE_SECURITY_STATUSES = {"open", "active", "in_review", "pending"}
_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}

        if isinstance(parsed, dict):
            return parsed

    return {}


def _as_string(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    items: list[str] = []
    for item in value:
        normalized = _as_string(item)
        if normalized:
            items.append(normalized)
    return items


def _to_float(value: object) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0

    return parsed if parsed == parsed else 0.0


def _to_int(value: object) -> int:
    return int(round(_to_float(value)))


def _parse_created_at(value: object) -> datetime | None:
    raw = _as_string(value)
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_trend_date(value: object) -> str:
    parsed = _parse_created_at(value)
    if parsed:
        return parsed.strftime("%b %d")

    raw = _as_string(value)
    return raw[:10] if raw else "Unknown"


def _normalize_governance_trend(value: object, score: int) -> Literal["up", "down", "stable"]:
    normalized = _as_string(value)
    if normalized in {"up", "down", "stable"}:
        return normalized
    return "down" if score < 50 else "up"


def _normalize_governance_rating(value: object, score: int) -> Literal["Excellent", "Good", "Fair", "Critical"]:
    normalized = _as_string(value)
    if normalized in {"Excellent", "Good", "Fair", "Critical"}:
        return normalized
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Critical"


def _normalize_budget_status(value: object) -> Literal["Safe", "Warning", "Excess"]:
    normalized = (_as_string(value) or "safe").lower()
    if normalized in {"warning", "warn"}:
        return "Warning"
    if normalized in {"excess", "critical", "over", "over_budget"}:
        return "Excess"
    return "Safe"


def _normalize_policy_status(value: object) -> Literal["Pass", "Fail"]:
    normalized = (_as_string(value) or "").lower()
    return "Fail" if normalized == "fail" else "Pass"


def _normalize_policy_severity(value: object) -> Literal["Critical", "High", "Medium", "Low"]:
    normalized = (_as_string(value) or "medium").lower()
    if normalized == "critical":
        return "Critical"
    if normalized == "high":
        return "High"
    if normalized == "low":
        return "Low"
    return "Medium"


def _build_governance_policies(governance_data: dict[str, object]) -> list[GovernancePolicyResponse]:
    raw_policies = governance_data.get("policies")
    if not isinstance(raw_policies, list):
        return []

    policies: list[GovernancePolicyResponse] = []
    for index, raw_policy in enumerate(raw_policies):
        policy = _as_dict(raw_policy)
        description = _as_string(policy.get("description"))
        policies.append(
            GovernancePolicyResponse(
                id=_as_string(policy.get("id")) or f"pol-{index}",
                name=_as_string(policy.get("name")) or "AI Governance Rule",
                status=_normalize_policy_status(policy.get("status")),
                severity=_normalize_policy_severity(policy.get("severity")),
                reason=_as_string(policy.get("reason")) or description or "Verified by AI Engine",
                framework=_as_string(policy.get("framework")) or "FinOps",
            )
        )

    return policies


def _build_governance_policy_records(
    policy_rows: list[dict[str, object]],
) -> list[GovernancePolicyRecordResponse]:
    def sort_key(row: dict[str, object]) -> float:
        parsed = _parse_created_at(row.get("created_at"))
        return parsed.timestamp() if parsed else 0.0

    records: list[GovernancePolicyRecordResponse] = []
    for row in sorted(policy_rows, key=sort_key, reverse=True):
        metadata = _as_dict(row.get("metadata"))
        policy_type = _as_string(row.get("policy_type")) or "custom"
        records.append(
            GovernancePolicyRecordResponse(
                id=_as_string(row.get("id")) or "",
                name=_as_string(row.get("name")) or "Unnamed policy",
                description=_as_string(row.get("description"))
                or _as_string(metadata.get("description"))
                or policy_type,
                policy_type=policy_type,
                is_active=bool(row.get("is_active")),
                compliance_rate=_to_float(row.get("compliance_rate")),
                violations=max(0, _to_int(row.get("violations"))),
                created_at=_as_string(row.get("created_at")) or "",
            )
        )

    return records


def _build_framework_summary(
    governance_data: dict[str, object],
    policies: list[GovernancePolicyResponse],
) -> list[GovernanceFrameworkSummaryItemResponse]:
    raw_summary = governance_data.get("frameworkSummary")
    summary_items: list[GovernanceFrameworkSummaryItemResponse] = []

    if isinstance(raw_summary, list):
        for item in raw_summary:
            summary = _as_dict(item)
            framework = _as_string(summary.get("framework"))
            if not framework:
                continue

            summary_items.append(
                GovernanceFrameworkSummaryItemResponse.model_validate(
                    {
                        "framework": framework,
                        "pass": _to_int(summary.get("pass")),
                        "fail": _to_int(summary.get("fail")),
                        "total": _to_int(summary.get("total")),
                    }
                )
            )

    if summary_items:
        return summary_items

    framework_counts: dict[str, dict[str, int]] = {}
    for policy in policies:
        bucket = framework_counts.setdefault(policy.framework, {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        if policy.status == "Pass":
            bucket["pass"] += 1
        else:
            bucket["fail"] += 1

    return [
        GovernanceFrameworkSummaryItemResponse.model_validate(
            {
                "framework": framework,
                "pass": counts["pass"],
                "fail": counts["fail"],
                "total": counts["total"],
            }
        )
        for framework, counts in framework_counts.items()
    ]


def _build_governance_trends(scan_rows: list[dict[str, object]]) -> list[GovernanceTrendPointResponse]:
    sortable_rows: list[tuple[datetime, dict[str, object], dict[str, object]]] = []
    for row in scan_rows:
        governance_data = _as_dict(row.get("governance_data"))
        if not governance_data:
            continue

        parsed_date = _parse_created_at(row.get("created_at"))
        if not parsed_date:
            continue

        sortable_rows.append((parsed_date, row, governance_data))

    sortable_rows.sort(key=lambda item: item[0])

    trends: list[GovernanceTrendPointResponse] = []
    for parsed_date, row, governance_data in sortable_rows[-7:]:
        score_payload = _as_dict(governance_data.get("score"))
        score_value = _to_int(score_payload.get("value") if score_payload else governance_data.get("score"))
        trends.append(
            GovernanceTrendPointResponse(
                date=_format_trend_date(row.get("created_at") or parsed_date.isoformat()),
                score=max(0, min(score_value, 100)),
            )
        )

    return trends


def _build_governance_agent_notifications(
    notification_rows: list[dict[str, object]],
) -> list[GovernanceAgentNotificationResponse]:
    sortable_rows = sorted(
        notification_rows,
        key=lambda row: (_parse_created_at(row.get("created_at")) or datetime.fromtimestamp(0)).timestamp(),
        reverse=True,
    )

    notifications: list[GovernanceAgentNotificationResponse] = []
    for row in sortable_rows:
        notifications.append(
            GovernanceAgentNotificationResponse(
                id=_as_string(row.get("id")) or "",
                recommendation=_as_string(row.get("recommendation")) or "",
                status=_as_string(row.get("status")) or "pending",
                type=_as_string(row.get("type")) or "notification",
                resource_id=_as_string(row.get("resource_id")) or "",
                created_at=_as_string(row.get("created_at")) or "",
                metadata=_as_dict(row.get("metadata")),
            )
        )

    return notifications


def _build_governance_resources(
    resource_rows: list[dict[str, object]],
) -> list[GovernanceSecurityResourceResponse]:
    resources: list[GovernanceSecurityResourceResponse] = []
    for row in resource_rows:
        resource_id = _as_string(row.get("id")) or _as_string(row.get("cloud_resource_id")) or ""
        resources.append(
            GovernanceSecurityResourceResponse(
                id=resource_id,
                resource_id=resource_id,
                resource_name=_as_string(row.get("resource_name")) or resource_id or "Unknown resource",
                resource_type=_as_string(row.get("resource_type")) or _as_string(row.get("service_type")) or "resource",
                provider=(_as_string(row.get("provider")) or "").lower(),
                region=_as_string(row.get("region")) or "",
                status=_as_string(row.get("status")) or "unknown",
            )
        )

    return resources


def _build_governance_policy_violations(
    violation_rows: list[dict[str, object]],
    policy_rows: list[dict[str, object]],
    resource_rows: list[dict[str, object]],
) -> list[GovernancePolicyViolationResponse]:
    policy_lookup = {
        _as_string(row.get("id")) or "": row
        for row in policy_rows
        if _as_string(row.get("id"))
    }
    resource_lookup = {
        _as_string(row.get("id")) or "": row
        for row in resource_rows
        if _as_string(row.get("id"))
    }
    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "info": 4,
    }

    def sort_key(row: dict[str, object]) -> tuple[int, float]:
        severity = (_as_string(row.get("severity")) or "low").lower()
        created_at = _parse_created_at(row.get("created_at"))
        timestamp = created_at.timestamp() if created_at else 0.0
        return severity_order.get(severity, 5), -timestamp

    violations: list[GovernancePolicyViolationResponse] = []
    for row in sorted(violation_rows, key=sort_key):
        policy_id = _as_string(row.get("policy_id")) or ""
        resource_id = _as_string(row.get("resource_id")) or ""
        policy_row = policy_lookup.get(policy_id, {})
        resource_row = resource_lookup.get(resource_id, {})
        policy_metadata = _as_dict(policy_row.get("metadata"))
        violation_details = _as_dict(row.get("violation_details"))

        category = (
            _as_string(row.get("category"))
            or _as_string(row.get("rule_category"))
            or _as_string(policy_row.get("policy_type"))
            or _as_string(policy_metadata.get("framework"))
            or "other"
        )
        provider = (
            (_as_string(row.get("provider")) or _as_string(resource_row.get("provider")) or "").lower()
        )
        description = (
            _as_string(row.get("description"))
            or _as_string(row.get("message"))
            or _as_string(violation_details.get("detail"))
            or _as_string(violation_details.get("description"))
            or "No details provided."
        )
        detected_at = _as_string(row.get("detected_at")) or _as_string(row.get("created_at")) or ""
        resource_name = (
            _as_string(row.get("resource"))
            or _as_string(resource_row.get("resource_name"))
            or resource_id
            or "—"
        )

        violations.append(
            GovernancePolicyViolationResponse(
                id=_as_string(row.get("id")) or "",
                policy_id=policy_id,
                resource_id=resource_id,
                resource=resource_name,
                provider=provider,
                category=category,
                rule_category=_as_string(row.get("rule_category")) or category,
                severity=(_as_string(row.get("severity")) or "low").lower(),
                status=(_as_string(row.get("status")) or "open").lower(),
                description=description,
                message=description,
                detected_at=detected_at,
                created_at=_as_string(row.get("created_at")) or detected_at,
            )
        )

    return violations


def _normalize_security_severity(value: object) -> Literal["critical", "high", "medium", "low", "info"]:
    normalized = (_as_string(value) or "medium").lower()
    if normalized == "critical":
        return "critical"
    if normalized == "high":
        return "high"
    if normalized == "low":
        return "low"
    if normalized == "info":
        return "info"
    if normalized in {"warning", "warn"}:
        return "medium"
    return "medium"


def _normalize_security_status(value: object) -> str:
    normalized = (_as_string(value) or "open").lower()
    if normalized in {"resolved", "closed", "completed", "dismissed", "ignored"}:
        return "resolved"
    if normalized in {"pending", "open", "active", "in_review"}:
        return normalized
    return "open"


def _is_security_category(value: object) -> bool:
    normalized = (_as_string(value) or "").lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return False
    if normalized in _SECURITY_POLICY_TYPES:
        return True
    return any(token in normalized for token in ("security", "permission", "iam", "encrypt", "public_access", "open_port"))


def _build_resource_lookup(resource_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for row in resource_rows:
        for key in ("id", "cloud_resource_id", "resource_id"):
            value = _as_string(row.get(key))
            if value:
                lookup[value] = row
    return lookup


def _security_category_from_row(
    row: dict[str, object],
    policy_row: dict[str, object],
) -> str:
    metadata = _as_dict(policy_row.get("metadata"))
    return (
        _as_string(row.get("category"))
        or _as_string(row.get("rule_category"))
        or _as_string(policy_row.get("policy_type"))
        or _as_string(metadata.get("framework"))
        or "security"
    )


def _is_security_violation(
    row: dict[str, object],
    policy_row: dict[str, object],
) -> bool:
    category = _security_category_from_row(row, policy_row)
    if _is_security_category(category):
        return True

    details = _as_dict(row.get("violation_details"))
    description = " ".join(
        filter(
            None,
            [
                _as_string(row.get("description")),
                _as_string(row.get("message")),
                _as_string(details.get("detail")),
                _as_string(details.get("description")),
            ],
        )
    ).lower()
    return any(token in description for token in ("public", "ssh", "rdp", "inbound", "encryption", "permission", "security"))


def _resource_name(row: dict[str, object], resource_row: dict[str, object]) -> str:
    return (
        _as_string(row.get("resource"))
        or _as_string(resource_row.get("resource_name"))
        or _as_string(row.get("resource_id"))
        or "Unknown resource"
    )


def _security_finding_from_violation(
    row: dict[str, object],
    policy_row: dict[str, object],
    resource_row: dict[str, object],
) -> SecurityFindingResponse:
    details = _as_dict(row.get("violation_details"))
    description = (
        _as_string(row.get("description"))
        or _as_string(row.get("message"))
        or _as_string(details.get("detail"))
        or _as_string(details.get("description"))
        or "Security control failed."
    )
    detected_at = _as_string(row.get("detected_at")) or _as_string(row.get("created_at")) or ""
    category = _security_category_from_row(row, policy_row)

    return SecurityFindingResponse(
        id=_as_string(row.get("id")) or "",
        resource_id=_as_string(row.get("resource_id")) or "",
        resource=_resource_name(row, resource_row),
        provider=(_as_string(row.get("provider")) or _as_string(resource_row.get("provider")) or "").lower(),
        region=_as_string(resource_row.get("region")) or "",
        category=category,
        severity=_normalize_security_severity(row.get("severity")),
        status=_normalize_security_status(row.get("status")),
        description=description,
        detected_at=detected_at,
        source="policy_violation",
        remediation=_as_string(details.get("remediation")) or "Review the affected resource and restrict the exposed security control.",
    )


def _is_security_notification(row: dict[str, object]) -> bool:
    notification_type = (_as_string(row.get("type")) or "").lower()
    if notification_type in _SECURITY_NOTIFICATION_TYPES:
        return True

    metadata = _as_dict(row.get("metadata"))
    return _is_security_category(metadata.get("category")) or _is_security_category(metadata.get("policy_type"))


def _security_finding_from_notification(
    row: dict[str, object],
    resource_row: dict[str, object],
) -> SecurityFindingResponse:
    metadata = _as_dict(row.get("metadata"))
    description = (
        _as_string(metadata.get("description"))
        or _as_string(row.get("recommendation"))
        or "Security alert requires review."
    )
    resource_name = (
        _as_string(metadata.get("resource_name"))
        or _as_string(resource_row.get("resource_name"))
        or _as_string(row.get("resource_id"))
        or "Unknown resource"
    )

    return SecurityFindingResponse(
        id=_as_string(row.get("id")) or "",
        resource_id=_as_string(row.get("resource_id")) or "",
        resource=resource_name,
        provider=(_as_string(metadata.get("provider")) or _as_string(resource_row.get("provider")) or "").lower(),
        region=_as_string(metadata.get("region")) or _as_string(resource_row.get("region")) or "",
        category=_as_string(metadata.get("category")) or _as_string(row.get("type")) or "security",
        severity=_normalize_security_severity(metadata.get("severity")),
        status=_normalize_security_status(row.get("status")),
        description=description,
        detected_at=_as_string(row.get("created_at")) or "",
        source="agent_notification",
        remediation=(
            _as_string(row.get("action"))
            or _as_string(metadata.get("remediation"))
            or _as_string(row.get("recommendation"))
            or "Review and remediate the security alert."
        ),
    )


def _is_security_resource(row: dict[str, object]) -> bool:
    metadata = _as_dict(row.get("metadata"))
    metrics = _as_dict(row.get("metrics_data"))
    governance_violations = row.get("governance_violations")
    service_type = " ".join(
        filter(
            None,
            [
                _as_string(row.get("service_type")),
                _as_string(row.get("resource_type")),
                _as_string(row.get("waste_type")),
                _as_string(row.get("waste_reason")),
            ],
        )
    ).lower()

    if "security_risk" in service_type or "public" in service_type:
        return True
    if any(token in service_type for token in ("security group", "network security", "firewall", "key vault", "kms", "iam")):
        status = (_as_string(row.get("status")) or "").lower()
        return status in {"non_compliant", "waste", "zombie", "security_risk"} or bool(metrics.get("risky_rules"))
    if metrics.get("risky_rules") or metrics.get("violations"):
        return True
    if _is_security_category(metadata.get("category")) or _is_security_category(metadata.get("policy_type")):
        return True
    if isinstance(governance_violations, list):
        return any(_is_security_category(item) or _is_security_category(_as_dict(item).get("category")) for item in governance_violations)

    return False


def _security_resource_exposure(row: dict[str, object]) -> str:
    metrics = _as_dict(row.get("metrics_data"))
    risky_rules = metrics.get("risky_rules")
    violations = metrics.get("violations")
    if isinstance(risky_rules, list) and risky_rules:
        return f"{len(risky_rules)} risky inbound rule{'s' if len(risky_rules) != 1 else ''}"
    if isinstance(violations, list) and violations:
        return f"{len(violations)} storage security issue{'s' if len(violations) != 1 else ''}"
    return _as_string(row.get("waste_reason")) or "Security risk detected"


def _build_security_posture(
    policy_rows: list[dict[str, object]],
    violation_rows: list[dict[str, object]],
    notification_rows: list[dict[str, object]],
    resource_rows: list[dict[str, object]],
) -> SecurityPostureResponse:
    policy_lookup = {
        _as_string(row.get("id")) or "": row
        for row in policy_rows
        if _as_string(row.get("id"))
    }
    resource_lookup = _build_resource_lookup(resource_rows)
    findings: list[SecurityFindingResponse] = []
    seen_finding_keys: set[tuple[str, str, str]] = set()

    def append_finding(finding: SecurityFindingResponse) -> None:
        key = (
            finding.resource_id,
            finding.description.strip().lower(),
            finding.severity,
        )
        if key in seen_finding_keys:
            return
        seen_finding_keys.add(key)
        findings.append(finding)

    for row in violation_rows:
        policy_row = policy_lookup.get(_as_string(row.get("policy_id")) or "", {})
        if not _is_security_violation(row, policy_row):
            continue
        resource_row = resource_lookup.get(_as_string(row.get("resource_id")) or "", {})
        append_finding(_security_finding_from_violation(row, policy_row, resource_row))

    for row in notification_rows:
        if not _is_security_notification(row):
            continue
        resource_row = resource_lookup.get(_as_string(row.get("resource_id")) or "", {})
        append_finding(_security_finding_from_notification(row, resource_row))

    findings.sort(
        key=lambda finding: (
            _SEVERITY_ORDER.get(finding.severity, 5),
            -(_parse_created_at(finding.detected_at) or datetime.fromtimestamp(0)).timestamp(),
        )
    )
    active_findings = [
        finding
        for finding in findings
        if finding.status in _ACTIVE_SECURITY_STATUSES
    ]

    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for finding in active_findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        category_key = finding.category.lower().replace("_", " ").replace("-", " ").strip() or "security"
        category_counts[category_key] = category_counts.get(category_key, 0) + 1

    finding_resource_ids = {
        finding.resource_id
        for finding in active_findings
        if finding.resource_id
    }
    findings_by_resource: dict[str, list[SecurityFindingResponse]] = {}
    for finding in active_findings:
        if finding.resource_id:
            findings_by_resource.setdefault(finding.resource_id, []).append(finding)

    exposed_resources: list[SecurityExposedResourceResponse] = []
    seen_resources: set[str] = set()
    for row in resource_rows:
        row_id = _as_string(row.get("id"))
        cloud_resource_id = _as_string(row.get("cloud_resource_id")) or _as_string(row.get("resource_id"))
        resource_keys = list(
            dict.fromkeys(
                key
                for key in (row_id, cloud_resource_id)
                if key
            )
        )
        resource_key = row_id or cloud_resource_id or ""
        if not resource_key or resource_key in seen_resources:
            continue
        row_findings = list(
            {
                finding.id: finding
                for key in resource_keys
                for finding in findings_by_resource.get(key, [])
            }.values()
        )
        if not any(key in finding_resource_ids for key in resource_keys) and not _is_security_resource(row):
            continue
        seen_resources.add(resource_key)
        highest_severity = row_findings[0].severity if row_findings else _normalize_security_severity(row.get("severity"))
        exposed_resources.append(
            SecurityExposedResourceResponse(
                id=resource_key,
                resource_id=cloud_resource_id or resource_key,
                resource_name=_as_string(row.get("resource_name")) or resource_key,
                resource_type=_as_string(row.get("resource_type")) or _as_string(row.get("service_type")) or "resource",
                provider=(_as_string(row.get("provider")) or "").lower(),
                region=_as_string(row.get("region")) or "",
                highest_severity=highest_severity,
                risk_count=max(1, len(row_findings)),
                exposure=_security_resource_exposure(row),
                status=_as_string(row.get("status")) or "unknown",
            )
        )

    exposed_resources.sort(
        key=lambda resource: (
            _SEVERITY_ORDER.get(resource.highest_severity, 5),
            resource.resource_name,
        )
    )

    critical = severity_counts.get("critical", 0)
    high = severity_counts.get("high", 0)
    medium = severity_counts.get("medium", 0)
    low = severity_counts.get("low", 0)
    if not resource_rows and not findings:
        score = 0
        rating: Literal["No data", "Strong", "Moderate", "Weak", "Critical"] = "No data"
    else:
        score = max(0, 100 - (critical * 25) - (high * 15) - (medium * 7) - (low * 2))
        if score >= 90:
            rating = "Strong"
        elif score >= 70:
            rating = "Moderate"
        elif score >= 50:
            rating = "Weak"
        else:
            rating = "Critical"

    dated_findings = [
        finding
        for finding in active_findings
        if finding.detected_at and _parse_created_at(finding.detected_at)
    ]
    last_detected_at = None
    if dated_findings:
        last_detected_at = max(
            dated_findings,
            key=lambda finding: (_parse_created_at(finding.detected_at) or datetime.fromtimestamp(0)).timestamp(),
        ).detected_at

    recent_alerts = sorted(
        findings,
        key=lambda finding: (_parse_created_at(finding.detected_at) or datetime.fromtimestamp(0)).timestamp(),
        reverse=True,
    )[:5]

    return SecurityPostureResponse(
        summary=SecurityPostureSummaryResponse(
            score=score,
            rating=rating,
            critical=critical,
            high=high,
            open=len(active_findings),
            exposed_resources=len(exposed_resources),
            monitored_resources=len(resource_rows),
            last_detected_at=last_detected_at,
        ),
        findingsBySeverity=[
            SecurityBreakdownItemResponse(name=severity, count=severity_counts[severity])
            for severity in ("critical", "high", "medium", "low", "info")
            if severity_counts.get(severity, 0) > 0
        ],
        findingsByCategory=[
            SecurityBreakdownItemResponse(name=name, count=count)
            for name, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)
        ][:6],
        activeFindings=active_findings[:25],
        exposedResources=exposed_resources[:25],
        recentAlerts=recent_alerts,
    )


def _zero_security_posture() -> SecurityPostureResponse:
    return SecurityPostureResponse(
        summary=SecurityPostureSummaryResponse(
            score=0,
            rating="No data",
            critical=0,
            high=0,
            open=0,
            exposed_resources=0,
            monitored_resources=0,
            last_detected_at=None,
        ),
        findingsBySeverity=[],
        findingsByCategory=[],
        activeFindings=[],
        exposedResources=[],
        recentAlerts=[],
    )


def _zero_governance_analysis() -> GovernanceAnalysisResponse:
    return GovernanceAnalysisResponse(
        score=GovernanceScoreResponse(value=0, trend="stable", rating="Fair"),
        tagging=GovernanceTaggingResponse(missingTags=0, costImpact=0.0, assets=[]),
        budget=GovernanceBudgetResponse(
            projectedSpend=0.0,
            budgetLimit=0.0,
            burnRate=0,
            status="Safe",
            alert="No data yet.",
        ),
        officeHours=GovernanceOfficeHoursResponse(
            savings=0.0,
            enabled=False,
            recommendation="Run a scan to generate insights.",
        ),
        policies=[],
        trends=[],
        frameworkSummary=[],
        agentNotifications=[],
        resources=[],
        policyViolations=[],
    )


def _build_governance_analysis(
    scan_rows: list[dict[str, object]],
    policy_rows: list[dict[str, object]],
    violation_rows: list[dict[str, object]],
    notification_rows: list[dict[str, object]],
    resource_rows: list[dict[str, object]],
) -> GovernanceAnalysisResponse:
    sortable_rows: list[tuple[datetime, dict[str, object], dict[str, object]]] = []
    for row in scan_rows:
        governance_data = _as_dict(row.get("governance_data"))
        if not governance_data:
            continue

        parsed_date = _parse_created_at(row.get("created_at"))
        if not parsed_date:
            continue

        sortable_rows.append((parsed_date, row, governance_data))

    if not sortable_rows:
        return _zero_governance_analysis()

    sortable_rows.sort(key=lambda item: item[0], reverse=True)
    latest_governance = sortable_rows[0][2]
    score_payload = _as_dict(latest_governance.get("score"))
    score_value = max(0, min(_to_int(score_payload.get("value") if score_payload else latest_governance.get("score")), 100))

    tagging_payload = _as_dict(latest_governance.get("tagging"))
    raw_assets = tagging_payload.get("assets")
    assets: list[GovernanceTaggingAssetResponse] = []
    if isinstance(raw_assets, list):
        for index, raw_asset in enumerate(raw_assets):
            if isinstance(raw_asset, str):
                asset_name = raw_asset.strip()
                if not asset_name:
                    continue
                assets.append(
                    GovernanceTaggingAssetResponse(
                        id=asset_name,
                        name=asset_name,
                        missing=[],
                    )
                )
                continue

            asset = _as_dict(raw_asset)
            asset_name = _as_string(asset.get("name")) or "Unknown Asset"
            assets.append(
                GovernanceTaggingAssetResponse(
                    id=_as_string(asset.get("id")) or f"asset-{index}",
                    name=asset_name,
                    missing=_as_string_list(asset.get("missing")),
                )
            )

    budget_payload = _as_dict(latest_governance.get("budget"))
    office_hours_payload = _as_dict(latest_governance.get("officeHours"))
    policies = _build_governance_policies(latest_governance)
    resources = _build_governance_resources(resource_rows)
    agent_notifications = _build_governance_agent_notifications(notification_rows)
    policy_violations = _build_governance_policy_violations(
        violation_rows,
        policy_rows,
        resource_rows,
    )

    return GovernanceAnalysisResponse(
        score=GovernanceScoreResponse(
            value=score_value,
            trend=_normalize_governance_trend(
                latest_governance.get("trend") or score_payload.get("trend"),
                score_value,
            ),
            rating=_normalize_governance_rating(
                latest_governance.get("rating") or score_payload.get("rating"),
                score_value,
            ),
        ),
        tagging=GovernanceTaggingResponse(
            missingTags=max(0, _to_int(tagging_payload.get("missingTags"))),
            costImpact=_to_float(tagging_payload.get("costImpact")),
            assets=assets,
        ),
        budget=GovernanceBudgetResponse(
            projectedSpend=_to_float(budget_payload.get("projectedSpend")),
            budgetLimit=_to_float(budget_payload.get("budgetLimit")),
            burnRate=max(0, min(_to_int(budget_payload.get("burnRate")), 999)),
            status=_normalize_budget_status(budget_payload.get("status")),
            alert=_as_string(budget_payload.get("alert")) or "Infrastructure is well-optimized",
        ),
        officeHours=GovernanceOfficeHoursResponse(
            savings=_to_float(office_hours_payload.get("savings")),
            enabled=bool(office_hours_payload.get("enabled")),
            recommendation=_as_string(office_hours_payload.get("recommendation")) or "No schedule changes recommended",
        ),
        policies=policies,
        trends=_build_governance_trends([row for _, row, _ in sortable_rows]),
        frameworkSummary=_build_framework_summary(latest_governance, policies),
        agentNotifications=agent_notifications,
        resources=resources,
        policyViolations=policy_violations,
    )


@router.get("/waste-distribution", response_model=WasteDistributionResponse)
async def get_waste_distribution(
    integration_id: Optional[str] = None,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Get waste-distribution buckets for the current user."""
    try:
        filters = {"user_id": user.id}
        if integration_id:
            filters["integration_id"] = integration_id

        rows = await db.select("waste_distribution", filters=filters)
        if not integration_id:
            active_ids = await _active_integration_ids(db, user.id)
            rows = [
                row
                for row in rows
                if str(row.get("integration_id") or "").strip() in active_ids
            ]
        items: list[WasteDistributionItem] = []

        for row in rows:
            category_name = str(row.get("category_name") or "").strip()
            if not category_name:
                continue

            raw_value = row.get("value")
            try:
                value = float(raw_value or 0)
            except (TypeError, ValueError):
                value = 0.0

            items.append(
                WasteDistributionItem(
                    category_name=category_name,
                    value=value,
                )
            )

        return WasteDistributionResponse(
            waste_distribution=items,
            count=len(items),
        )
    except Exception as error:
        logger.error("get_waste_distribution failed: %s", error)
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/security/posture", response_model=SecurityPostureResponse)
async def get_security_posture(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Get security-only posture metrics for the current user."""
    try:
        integrations = await db.get_user_integrations(user.id)
        if not integrations:
            return _zero_security_posture()

        policy_rows = await db.select(
            "governance_policies",
            filters={"user_id": user.id},
        )
        violation_rows = await db.select(
            "policy_violations",
            filters={"user_id": user.id},
        )
        notification_rows = await db.select(
            "agent_notifications",
            filters={"user_id": user.id},
        )
        resource_rows = await db.get_resources(user.id)

        return _build_security_posture(
            policy_rows,
            violation_rows,
            notification_rows,
            resource_rows,
        )
    except Exception as error:
        logger.error("get_security_posture failed: %s", error)
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/governance/analysis", response_model=GovernanceAnalysisResponse)
async def get_governance_analysis(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Get the latest governance analysis for the current user."""
    try:
        integrations = await db.get_user_integrations(user.id)
        if not integrations:
            return _zero_governance_analysis()

        scan_rows = await db.select(
            "scan_history",
            filters={"user_id": user.id, "status": "completed"},
        )
        policy_rows = await db.select(
            "governance_policies",
            filters={"user_id": user.id},
        )
        violation_rows = await db.select(
            "policy_violations",
            filters={"user_id": user.id},
        )
        notification_rows = await db.select(
            "agent_notifications",
            filters={"user_id": user.id},
        )
        resource_rows = await db.get_resources(user.id)

        return _build_governance_analysis(
            scan_rows,
            policy_rows,
            violation_rows,
            notification_rows,
            resource_rows,
        )
    except Exception as error:
        logger.error("get_governance_analysis failed: %s", error)
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/governance/policies", response_model=GovernancePoliciesResponse)
async def get_governance_policies(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Get governance policies for the current user."""
    try:
        rows = await db.select(
            "governance_policies",
            filters={"user_id": user.id},
        )
        policies = _build_governance_policy_records(rows)

        return GovernancePoliciesResponse(
            policies=policies,
            count=len(policies),
        )
    except Exception as error:
        logger.error("get_governance_policies failed: %s", error)
        raise HTTPException(status_code=500, detail="Internal error")
