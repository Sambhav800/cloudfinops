"""
Read-only domain router for Clousy.

Routes a user query to a small set of precomputed Mongo-backed facts
without making any AI calls.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _pick_first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


class AgentRouter:
    DOMAINS = {
        "pricing": [
            "price",
            "pricing",
            "catalog",
            "market",
            "estimate",
            "list price",
            "actual cost",
            "resource cost",
            "billing access",
            "ingestion",
            "cur",
            "bigquery",
        ],
        "savings": ["save", "cost", "rightsize", "stop", "delete", "waste"],
        "governance": ["tag", "compliance", "policy", "violation", "governance"],
        "bill": ["bill", "invoice", "pdf", "upload", "arbitrage"],
        "forecast": ["forecast", "predict", "budget", "spend", "month end"],
        "security": ["security", "vulnerability", "risk", "open port"],
    }

    def classify(self, user_query: str) -> str:
        normalized_query = str(user_query or "").casefold()
        if not normalized_query:
            return "general"
        tokens = normalized_query.replace("-", " ").split()

        winning_domain = "general"
        winning_score = 0

        for domain, keywords in self.DOMAINS.items():
            score = 0
            for keyword in keywords:
                normalized_keyword = keyword.casefold()
                normalized_stem = normalized_keyword[:-1] if normalized_keyword.endswith("e") else normalized_keyword
                if normalized_keyword in normalized_query:
                    score += 1
                    continue
                if any(token.startswith(normalized_stem) for token in tokens):
                    score += 1
            if score > winning_score:
                winning_domain = domain
                winning_score = score

        return winning_domain

    async def handle(self, domain: str, user_id: str, db) -> str:
        normalized_domain = str(domain or "").strip().lower()
        if normalized_domain == "pricing":
            return await self._build_pricing_context(user_id, db)
        if normalized_domain == "savings":
            return await self._build_savings_context(user_id, db)
        if normalized_domain == "governance":
            return await self._build_governance_context(user_id, db)
        if normalized_domain == "bill":
            return await self._build_bill_context(user_id, db)
        if normalized_domain == "forecast":
            return await self._build_forecast_context(user_id, db)
        if normalized_domain == "security":
            return await self._build_security_context(user_id, db)
        return ""

    async def _build_pricing_context(self, user_id: str, db) -> str:
        resources = await db.get_resources(user_id)
        source_counts = {
            "actual": 0,
            "catalog_estimate": 0,
            "billing_unavailable": 0,
            "no_direct_charge": 0,
            "unknown": 0,
        }
        provider_counts: dict[str, int] = {}

        for resource in resources:
            provider = str(resource.get("provider") or "unknown").strip().lower() or "unknown"
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
            source = str(metadata.get("cost_source") or "unknown").strip().lower()
            if source in {"pricing_unavailable", ""}:
                source = "billing_unavailable"
            if source not in source_counts:
                source = "unknown"
            source_counts[source] += 1

        try:
            sync_rows = await db.select("cloud_price_catalog_syncs")
        except Exception as error:
            logger.warning("agent_router: pricing catalog sync status unavailable for %s: %s", user_id, error)
            sync_rows = []
        sync_rows.sort(key=lambda row: str(row.get("synced_at") or row.get("updated_at") or ""), reverse=True)

        provider_summary = ", ".join(
            f"{provider.upper()}: {count}"
            for provider, count in sorted(provider_counts.items())
        ) or "No scanned resources yet"
        latest_sync = "No provider pricing catalog sync has completed yet."
        if sync_rows:
            latest = sync_rows[0]
            latest_sync = (
                f"Latest catalog sync: {str(latest.get('provider') or 'unknown').upper()} "
                f"{latest.get('records_saved') or 0} rows at {latest.get('synced_at') or latest.get('updated_at') or 'unknown time'}."
            )

        return "\n".join(
            [
                "Cost data model: market/list prices first, actual billing second.",
                f"Resources by provider: {provider_summary}",
                (
                    "Cost source coverage: "
                    f"actual={source_counts['actual']}, "
                    f"catalog_estimate={source_counts['catalog_estimate']}, "
                    f"billing_unavailable={source_counts['billing_unavailable']}, "
                    f"no_direct_charge={source_counts['no_direct_charge']}, "
                    f"unknown={source_counts['unknown']}"
                ),
                latest_sync,
                "Market costs come from official provider catalogs: AWS Price List API, Azure Retail Prices API, and Google Cloud Billing Pricing/Catalog APIs.",
                "Actual costs require billing ingestion: AWS CUR 2.0/Data Exports with resource IDs, Azure Cost Details/Exports or Cost Management Query by ResourceId, and GCP Detailed Billing Export to BigQuery.",
            ]
        )

    async def _build_savings_context(self, user_id: str, db) -> str:
        notifications = await db.select(
            "agent_notifications",
            filters={"user_id": user_id, "status": "pending"},
        )

        savings_rows = [
            notification
            for notification in notifications
            if str(notification.get("type") or "").strip().lower() == "cost_optimization"
        ]
        savings_rows.sort(
            key=lambda row: _coerce_float((row.get("metadata") or {}).get("potential_savings") or (row.get("metadata") or {}).get("estimated_savings")),
            reverse=True,
        )

        if not savings_rows:
            return "No pending cost optimizations are ready right now."

        lines = [f"Pending cost optimizations: {len(savings_rows)}", "Top actions ready for review:"]
        for row in savings_rows[:3]:
            metadata = row.get("metadata") or {}
            resource_name = _pick_first_string(
                metadata.get("resource_name"),
                row.get("resource_name"),
                row.get("resource_id"),
                "Unknown resource",
            )
            action_type = _pick_first_string(metadata.get("action_type"), row.get("action"), "review")
            monthly_savings = _coerce_float(metadata.get("potential_savings") or metadata.get("estimated_savings"))
            lines.append(
                f"- {resource_name}: {action_type.replace('_', ' ').title()} ({_format_currency(monthly_savings)}/month)"
            )
        return "\n".join(lines)

    async def _build_governance_context(self, user_id: str, db) -> str:
        violations = await db.select(
            "policy_violations",
            filters={"user_id": user_id, "status": "active"},
        )
        violations.sort(
            key=lambda row: (
                -_SEVERITY_ORDER.get(str(row.get("severity") or "").strip().lower(), 0),
                str(row.get("created_at") or ""),
            ),
            reverse=False,
        )

        if not violations:
            return "No active governance violations are open right now."

        lines = [f"Active governance violations: {len(violations)}", "Highest-priority violations:"]
        for row in violations[:3]:
            severity = str(row.get("severity") or "unknown").strip().title()
            detail = _pick_first_string(
                (row.get("violation_details") or {}).get("detail"),
                (row.get("violation_details") or {}).get("reason"),
                row.get("violation_details"),
                "No reasoning recorded.",
            )
            resource_label = _pick_first_string(row.get("resource_id"), "Unknown resource")
            lines.append(f"- {severity} | {resource_label}: {detail}")
        return "\n".join(lines)

    async def _build_bill_context(self, user_id: str, db) -> str:
        analyses = await db.select("bill_analyses", filters={"user_id": user_id})
        analyses.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)

        if not analyses:
            return "No uploaded bill analyses are saved for this account yet."

        latest = analyses[0]
        filename = _pick_first_string(latest.get("filename"), "Unknown bill")
        provider = _pick_first_string(latest.get("provider_detected"), latest.get("provider"), "Unknown").upper()
        analyzed_spend = _coerce_float(latest.get("total_analyzed_spend") or latest.get("total_spend"))
        potential_savings = _coerce_float(latest.get("total_potential_savings"))
        return "\n".join(
            [
                f"Saved bill analyses: {len(analyses)}",
                f"Latest bill: {filename} ({provider})",
                f"Analyzed spend: {_format_currency(analyzed_spend)}",
                f"Estimated opportunity: {_format_currency(potential_savings)}/month",
            ]
        )

    async def _build_forecast_context(self, user_id: str, db) -> str:
        events = await db.select(
            "budget_events",
            filters={"user_id": user_id, "scope": "portfolio"},
        )
        events.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)

        if not events:
            return "No portfolio budget forecast is configured yet."

        latest = events[0]
        budget_limit = _coerce_float(latest.get("budget_limit"))
        actual_mtd_spend = _coerce_float(latest.get("actual_mtd_spend"))
        forecast_eom = _coerce_float(latest.get("forecast_eom_spend"))
        variance_amount = _coerce_float(latest.get("variance_amount"))
        status = str(latest.get("current_status") or "unknown").replace("_", " ").title()
        return "\n".join(
            [
                f"Portfolio forecast status: {status}",
                f"Budget limit: {_format_currency(budget_limit)}/month",
                f"Actual MTD spend: {_format_currency(actual_mtd_spend)}",
                f"Forecast month end: {_format_currency(forecast_eom)}",
                f"Variance amount: {_format_currency(variance_amount)}",
            ]
        )

    async def _build_security_context(self, user_id: str, db) -> str:
        notifications = await db.select(
            "agent_notifications",
            filters={"user_id": user_id, "status": "pending"},
        )
        security_notifications = [
            row
            for row in notifications
            if str(row.get("type") or "").strip().lower() in {"security_alert", "permission_alert", "alert"}
        ]

        violations = await db.select(
            "policy_violations",
            filters={"user_id": user_id, "status": "active"},
        )
        security_violations = [
            row
            for row in violations
            if _SEVERITY_ORDER.get(str(row.get("severity") or "").strip().lower(), 0) >= _SEVERITY_ORDER["high"]
        ]
        security_violations.sort(
            key=lambda row: (
                -_SEVERITY_ORDER.get(str(row.get("severity") or "").strip().lower(), 0),
                str(row.get("created_at") or ""),
            ),
            reverse=False,
        )

        if not security_notifications and not security_violations:
            return "No active security alerts or high-severity risks are open right now."

        lines = [
            f"Pending security alerts: {len(security_notifications)}",
            f"High-severity active risks: {len(security_violations)}",
        ]
        if security_violations:
            lines.append("Top risks:")
        for row in security_violations[:3]:
            severity = str(row.get("severity") or "unknown").strip().title()
            detail = _pick_first_string(
                (row.get("violation_details") or {}).get("detail"),
                (row.get("violation_details") or {}).get("reason"),
                "No reasoning recorded.",
            )
            resource_label = _pick_first_string(row.get("resource_id"), "Unknown resource")
            lines.append(f"- {severity} | {resource_label}: {detail}")
        return "\n".join(lines)
