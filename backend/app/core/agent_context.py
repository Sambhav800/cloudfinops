"""
Builds a personalized, data-grounded system prompt for each user session.
All numbers come from MongoDB - never approximated or hardcoded.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from .agent_router import AgentRouter

logger = logging.getLogger(__name__)

_INVALID_FIRST_NAME_TOKENS = frozenset({"null", "none", "undefined", "user", "test"})
_TRAILING_DIGITS_RE = re.compile(r"\d+$")


def _capitalize_name(value: str) -> str:
    if not value:
        return ""
    return value[0].upper() + value[1:]


def _get_first_name(full_name: Any, email: Any) -> str:
    raw_full_name = str(full_name or "").strip()
    if raw_full_name:
        first_token = raw_full_name.split()[0].strip(" ,:-_")
        normalized = first_token.casefold()
        if first_token and normalized not in _INVALID_FIRST_NAME_TOKENS:
            return first_token

    raw_email = str(email or "").strip()
    if raw_email and "@" in raw_email:
        prefix = raw_email.split("@", 1)[0].strip()
        if prefix:
            cleaned_prefix = _TRAILING_DIGITS_RE.sub("", prefix)
            if len(cleaned_prefix) >= 3:
                return _capitalize_name(cleaned_prefix)
            return _capitalize_name(prefix)

    return ""


def _format_relative_last_scan(last_scan_dt: datetime | None) -> str:
    if last_scan_dt is None:
        return "never"

    normalized = last_scan_dt if last_scan_dt.tzinfo else last_scan_dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - normalized.astimezone(timezone.utc)
    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        return "less than an hour ago"
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def _time_greeting() -> str:
    hour = datetime.now(timezone.utc).hour
    if hour < 5:
        return "Hey"
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


async def build_agent_system_prompt(
    user_id: str,
    db,
    user_query: str | None = None,
) -> str:
    """
    Load real account data and build a personalized LLM system prompt.
    Falls back gracefully if any query fails.
    """
    first_name = ""
    organization = "your organization"

    total_spend = 0.0
    potential_savings = 0.0
    resource_count = 0
    ai_confidence = 0

    budget_limit = 0.0
    budget_status = "no_budget_configured"
    forecast_eom = 0.0

    alert_count = 0
    violation_count = 0

    providers: list[str] = []
    last_scan_dt: datetime | None = None

    try:
        users = await db.select("users", filters={"id": user_id})
        if users:
            user_row = users[0]
            first_name = _get_first_name(user_row.get("full_name"), user_row.get("email"))
            organization = str(user_row.get("organization") or "your organization")
    except Exception as error:
        logger.warning("agent_context: user load failed for %s: %s", user_id, error)

    try:
        stats_rows = await db.select("dashboard_stats", filters={"user_id": user_id})
        if stats_rows:
            total_spend = round(sum(float(row.get("total_spend") or 0) for row in stats_rows), 2)
            potential_savings = round(sum(float(row.get("potential_savings") or 0) for row in stats_rows), 2)
            resource_count = sum(int(row.get("active_resources_count") or 0) for row in stats_rows)
            confidence_values = [
                int(row.get("ai_confidence_score") or 0)
                for row in stats_rows
                if row.get("ai_confidence_score") is not None
            ]
            if confidence_values:
                ai_confidence = round(sum(confidence_values) / len(confidence_values))
    except Exception as error:
        logger.warning("agent_context: dashboard_stats load failed for %s: %s", user_id, error)

    try:
        events = await db.select(
            "budget_events",
            filters={"user_id": user_id, "scope": "portfolio"},
        )
        events.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        if events:
            latest_event = events[0]
            budget_limit = float(latest_event.get("budget_limit") or 0)
            budget_status = str(latest_event.get("current_status") or "no_budget_configured")
            forecast_eom = float(latest_event.get("forecast_eom_spend") or total_spend)
    except Exception as error:
        logger.warning("agent_context: budget_events load failed for %s: %s", user_id, error)

    try:
        notifications = await db.select(
            "agent_notifications",
            filters={"user_id": user_id, "status": "pending"},
        )
        alert_count = len(notifications)
    except Exception as error:
        logger.warning("agent_context: agent_notifications load failed for %s: %s", user_id, error)

    try:
        violations = await db.select(
            "policy_violations",
            filters={"user_id": user_id, "status": "active"},
        )
        violation_count = len(violations)
    except Exception as error:
        logger.warning("agent_context: policy_violations load failed for %s: %s", user_id, error)

    try:
        integrations = await db.select(
            "cloud_integrations",
            filters={"user_id": user_id, "status": "active"},
        )
        seen: set[str] = set()
        for integration in integrations:
            provider = str(integration.get("provider") or "").upper()
            if provider and provider not in seen:
                seen.add(provider)
                providers.append(provider)

            raw_last_scan = str(integration.get("last_scan") or "").strip()
            if not raw_last_scan:
                continue
            try:
                parsed = datetime.fromisoformat(raw_last_scan.replace("Z", "+00:00"))
            except Exception:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if last_scan_dt is None or parsed > last_scan_dt:
                last_scan_dt = parsed
    except Exception as error:
        logger.warning("agent_context: cloud_integrations load failed for %s: %s", user_id, error)

    greeting = _time_greeting()
    greeting_line = f"{greeting}, {first_name}!" if first_name else f"{greeting}!"
    last_scan_str = _format_relative_last_scan(last_scan_dt)

    if budget_limit > 0:
        pct_used = round((total_spend / budget_limit) * 100, 1) if budget_limit else 0.0
        budget_line = (
            f"Budget: ${budget_limit:,.2f}/mo | "
            f"MTD spend: ${total_spend:,.2f} ({pct_used}% used) | "
            f"Forecast EOM: ${forecast_eom:,.2f} | "
            f"Status: {budget_status.replace('_', ' ').title()}"
        )
    elif total_spend > 0:
        budget_line = f"MTD spend: ${total_spend:,.2f} | No budget configured yet"
    else:
        budget_line = "No spend data yet - run a scan to populate your account"

    if alert_count > 0 and violation_count > 0:
        alert_line = f"Open alerts: {alert_count} | Governance violations: {violation_count}"
    elif alert_count > 0:
        alert_line = f"Open alerts: {alert_count}"
    elif violation_count > 0:
        alert_line = f"Governance violations: {violation_count}"
    else:
        alert_line = "No open alerts"

    address_rule = f'- Address user as "{first_name}" throughout the conversation\n' if first_name else ""
    example_first_message = (
        f'"{greeting_line} I\'ve spotted ${potential_savings:,.2f}/month in\n'
        f"potential savings across your {', '.join(providers) if providers else 'connected cloud accounts'}, and\n"
        f'you have {alert_count} open alerts that need attention. Want me to walk\n'
        f'through the highest-priority items first?"'
    )

    base_prompt = f"""\
You are Clousy - the CloudFinOps AI assistant and senior FinOps advisor.
You are embedded inside the user's CloudFinOps dashboard.

USER ACCOUNT DATA (loaded from live database - these are exact figures):
Name: {first_name or "Unavailable"}
Organization: {organization}
Connected clouds: {', '.join(providers) if providers else 'None connected yet'}
{budget_line}
Savings identified: ${potential_savings:,.2f}/month (${potential_savings * 12:,.2f}/year)
Resources scanned: {resource_count:,}
AI analysis confidence: {ai_confidence}%
{alert_line}
Last scan: {last_scan_str}

FIRST MESSAGE BEHAVIOR:
Always start your very first message in a session with:
"{greeting_line}"
Then immediately give the most actionable insight from the data above.
If open alerts exist: mention them first.
If potential_savings > 0: lead with the savings opportunity.
Never just say "How can I help you?" - always lead with real data.

EXAMPLE FIRST MESSAGE when savings > 0 and alerts > 0:
{example_first_message}

BEHAVIOR RULES:
{address_rule}- All dollar amounts: $X,XXX.XX format with commas
- Percentages: X.X% format (one decimal)
- For recommendations: use real service names (m5.xlarge, db.r5.large, etc.)
- Cross-cloud cost comparisons: always label as estimates
- Treat provider market/list prices as `catalog_estimate`, never as actual spend
- Explain that actual spend requires billing ingestion before using it for totals,
  savings, budgets, finance forecasts, or executive reports
- If asked about data not in your context: say "I'd need to query that -
  let me check" and use your tools to fetch it
- If asked to delete/stop/modify resources: explain the action and provide
  the CLI command, but clarify the user must execute it themselves
- Never invent resource IDs, ARNs, or metric values you don't have

COST INTELLIGENCE MODEL:
CloudFinOps has two cost tiers:
1. Market/list price estimates: official provider catalog prices for investor-demo
   coverage before billing export access is ready. These must be labeled as
   catalog estimates and described as "provider market/list price", not invoices.
2. Actual billing costs: provider billing records joined back to scanned resources.
   These override catalog estimates and are the only numbers allowed in actual
   spend, realized savings, budgets, finance forecasts, and executive reports.

OFFICIAL MARKET PRICE SOURCES:
- AWS: AWS Price List API / Bulk Price List for public on-demand SKU rates.
- Azure: Azure Retail Prices API for retail meters, regions, SKUs, and units.
- GCP: Cloud Billing Pricing API / Catalog API, or the BigQuery pricing export.

ACTUAL BILLING INGESTION PATH:
- AWS: guide the user to enable AWS Data Exports / CUR 2.0 with resource IDs,
  deliver to S3, query with Athena/Glue, and connect read access.
- Azure: guide the user to Cost Details API or Cost Management Exports, with
  Cost Management Reader access and ResourceId grouping when using live query.
- GCP: guide the user to enable Detailed Cloud Billing Export to BigQuery,
  use the Google-created gcp_billing_export_resource_v1 table, and enable GKE
  cost allocation when Kubernetes cluster-level costs are needed.

When a user asks why costs are estimates, explain the tier they are seeing and
offer the next exact setup tasks needed to unlock actual billing for their cloud.

DOMAIN EXPERTISE:
AWS (EC2, EBS, RDS, S3, Lambda, EKS, Cost Explorer, Savings Plans, RI),
Azure (VMs, AKS, App Service, Cosmos DB, Cost Management, Reservations),
GCP (Compute Engine, GKE, Cloud SQL, BigQuery, Committed Use Discounts),
FinOps (commitment coverage, rightsizing, waste detection, chargeback,
unit economics, cost per customer, showback reporting)
"""

    router = AgentRouter()
    current_domain = "general"
    domain_context = ""

    try:
        current_domain = router.classify(user_query or "")
    except Exception as error:
        logger.warning("agent_context: domain classification failed for %s: %s", user_id, error)
        current_domain = "general"

    if current_domain == "general":
        return base_prompt

    try:
        domain_context = await router.handle(current_domain, user_id, db)
    except Exception as error:
        logger.warning("agent_context: domain context load failed for %s (%s): %s", user_id, current_domain, error)
        domain_context = ""

    if not domain_context:
        return base_prompt

    return (
        f"{base_prompt}\n\n"
        "CURRENT REQUEST DOMAIN:\n"
        f"{current_domain}\n"
        "DOMAIN-SPECIFIC FACTS (live database reads already performed by the application):\n"
        f"{domain_context}\n\n"
        "WHEN ANSWERING THIS REQUEST:\n"
        f"- Start from these {current_domain} facts before deciding whether you need extra tool calls.\n"
        "- Treat these facts as current read-only account context, not examples.\n"
        "- Keep the answer scoped to this domain unless the user asks to broaden the discussion.\n"
    )
