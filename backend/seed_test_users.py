"""
Seed demo data for test users: Rajiv Sikka and Prabhnandana Das.

Uses the existing demo portfolio builder to generate realistic data
for every dashboard page (resources, alerts, governance, security,
commitments, forecasts, reports, pending actions, architecture, etc.).

Usage:
    # Seed with placeholder user IDs (before users sign up)
    python seed_test_users.py

    # After users sign up via Clerk, re-seed with their actual Clerk IDs
    python seed_test_users.py --rajiv-id user_xxx --prabhnandana-id user_yyy

    # Look up Clerk IDs by email and seed
    python seed_test_users.py --lookup-emails
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.core.demo_portfolio import build_demo_portfolio_bundle, DEMO_DATASET_VERSION
from app.db import get_db_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_test_users")

RESET_COLLECTIONS = (
    "cloud_integrations",
    "resources",
    "dashboard_stats",
    "daily_spend_history",
    "waste_distribution",
    "agent_notifications",
    "budget_events",
    "governance_policies",
    "policy_violations",
    "scan_history",
    "reports",
    "audit_logs",
)

TEST_USERS = [
    {
        "placeholder_id": "demo-rajiv-sikka",
        "email": "rajiv.sikka@demo.cloudfinops.in",
        "first_name": "Rajiv",
        "last_name": "Sikka",
        "full_name": "Rajiv Sikka",
        "company": "Advisory Board",
        "title": "Ex CEO, Adani Gas",
    },
    {
        "placeholder_id": "demo-prabhnandana-das",
        "email": "prabhnandana.das@demo.cloudfinops.in",
        "first_name": "Prabhnandana",
        "last_name": "Das",
        "full_name": "Prabhnandana Das",
        "company": "Advisory Board",
        "title": "IIM Gold Medalist",
    },
]


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _flatten_history(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for integration_rows in bundle["daily_spend_history_by_integration"].values():
        rows.extend(integration_rows)
    return rows


async def _upsert_user(db: Any, user_id: str, user_info: Dict[str, Any]) -> None:
    now_iso = _utc_now_iso()
    record = {
        "id": user_id,
        "email": user_info["email"],
        "email_lower": user_info["email"].lower(),
        "first_name": user_info["first_name"],
        "last_name": user_info["last_name"],
        "full_name": user_info["full_name"],
        "last_login": now_iso,
        "updated_at": now_iso,
        "metadata": {
            "demo_portfolio_enabled": True,
            "demo_dataset_version": DEMO_DATASET_VERSION,
            "company": user_info.get("company", ""),
            "title": user_info.get("title", ""),
            "is_test_user": True,
        },
        "finance_settings": {
            "portfolio_budget_limit": 60000.0,
            "report_recipients": [user_info["email"]],
            "report_cadence": "weekly",
            "alert_thresholds": {
                "warning_pct": 80.0,
                "critical_pct": 100.0,
            },
        },
    }
    await db.upsert("users", record)
    logger.info("  Upserted user record: %s (%s)", user_id, user_info["full_name"])


async def _reset_user_data(db: Any, user_id: str) -> None:
    for collection in RESET_COLLECTIONS:
        await db.delete(collection, {"user_id": user_id})
    logger.info("  Cleared old data from %d collections", len(RESET_COLLECTIONS))


async def _insert_bundle(db: Any, bundle: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    await db.insert("cloud_integrations", bundle["integrations"])
    counts["cloud_integrations"] = len(bundle["integrations"])

    await db.insert("resources", bundle["resources"])
    counts["resources"] = len(bundle["resources"])

    await db.insert("dashboard_stats", bundle["dashboard_stats"])
    counts["dashboard_stats"] = len(bundle["dashboard_stats"])

    daily_spend_history = _flatten_history(bundle)
    if daily_spend_history:
        await db.insert("daily_spend_history", daily_spend_history)
    counts["daily_spend_history"] = len(daily_spend_history)

    if bundle["waste_distribution"]:
        await db.insert("waste_distribution", bundle["waste_distribution"])
    counts["waste_distribution"] = len(bundle["waste_distribution"])

    if bundle["notifications"]:
        await db.insert("agent_notifications", bundle["notifications"])
    counts["agent_notifications"] = len(bundle["notifications"])

    if bundle["budget_events"]:
        await db.insert("budget_events", bundle["budget_events"])
    counts["budget_events"] = len(bundle["budget_events"])

    if bundle["governance_policies"]:
        await db.insert("governance_policies", bundle["governance_policies"])
    counts["governance_policies"] = len(bundle["governance_policies"])

    if bundle["policy_violations"]:
        await db.insert("policy_violations", bundle["policy_violations"])
    counts["policy_violations"] = len(bundle["policy_violations"])

    if bundle["scan_history"]:
        await db.insert("scan_history", bundle["scan_history"])
    counts["scan_history"] = len(bundle["scan_history"])

    if bundle["reports"]:
        await db.insert("reports", bundle["reports"])
    counts["reports"] = len(bundle["reports"])

    if bundle["audit_logs"]:
        await db.insert("audit_logs", bundle["audit_logs"])
    counts["audit_logs"] = len(bundle["audit_logs"])

    return counts


async def _lookup_user_by_email(db: Any, email: str) -> str | None:
    rows = await db.select("users", filters={"email_lower": email.lower()})
    if rows:
        return str(rows[0].get("id") or "").strip() or None
    rows = await db.select("users", filters={"email": email})
    if rows:
        return str(rows[0].get("id") or "").strip() or None
    return None


async def seed_user(db: Any, user_id: str, user_info: Dict[str, Any]) -> None:
    logger.info("Seeding data for %s (user_id: %s)...", user_info["full_name"], user_id)

    await _upsert_user(db, user_id, user_info)
    await _reset_user_data(db, user_id)

    bundle = build_demo_portfolio_bundle(user_id)
    counts = await _insert_bundle(db, bundle)

    total_spend = round(sum(float(s.get("total_spend") or 0.0) for s in bundle["dashboard_stats"]), 2)
    potential_savings = round(sum(float(s.get("potential_savings") or 0.0) for s in bundle["dashboard_stats"]), 2)
    forecast_eom = round(float(bundle["portfolio_forecast"].get("forecast_eom_spend") or 0.0), 2)

    logger.info("  Done! Summary for %s:", user_info["full_name"])
    logger.info("    Integrations: %d (AWS, Azure, GCP)", counts["cloud_integrations"])
    logger.info("    Resources: %d", counts["resources"])
    logger.info("    Daily spend history: %d days", counts["daily_spend_history"])
    logger.info("    Notifications/Actions: %d", counts["agent_notifications"])
    logger.info("    Governance policies: %d", counts["governance_policies"])
    logger.info("    Policy violations: %d", counts["policy_violations"])
    logger.info("    Reports: %d", counts["reports"])
    logger.info("    Audit logs: %d", counts["audit_logs"])
    logger.info("    Total spend: $%s", f"{total_spend:,.2f}")
    logger.info("    Potential savings: $%s", f"{potential_savings:,.2f}")
    logger.info("    Forecast EOM: $%s", f"{forecast_eom:,.2f}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for test users")
    parser.add_argument("--rajiv-id", help="Clerk user ID for Rajiv Sikka")
    parser.add_argument("--prabhnandana-id", help="Clerk user ID for Prabhnandana Das")
    parser.add_argument("--lookup-emails", action="store_true", help="Look up Clerk IDs by email in users collection")
    args = parser.parse_args()

    db = get_db_client()
    try:
        user_ids = {}

        if args.lookup_emails:
            for user_info in TEST_USERS:
                found_id = await _lookup_user_by_email(db, user_info["email"])
                if found_id:
                    user_ids[user_info["placeholder_id"]] = found_id
                    logger.info("Found Clerk ID for %s: %s", user_info["full_name"], found_id)
                else:
                    user_ids[user_info["placeholder_id"]] = user_info["placeholder_id"]
                    logger.warning(
                        "No Clerk ID found for %s (%s), using placeholder: %s",
                        user_info["full_name"],
                        user_info["email"],
                        user_info["placeholder_id"],
                    )
        else:
            user_ids["demo-rajiv-sikka"] = args.rajiv_id or "demo-rajiv-sikka"
            user_ids["demo-prabhnandana-das"] = args.prabhnandana_id or "demo-prabhnandana-das"

        print(f"\n{'='*60}")
        print(f"  CloudFinOps Test User Seeder")
        print(f"  Dataset version: {DEMO_DATASET_VERSION}")
        print(f"{'='*60}\n")

        for user_info in TEST_USERS:
            user_id = user_ids[user_info["placeholder_id"]]
            await seed_user(db, user_id, user_info)
            print()

        print(f"{'='*60}")
        print("  Seeding complete! Both users now have:")
        print("  - 4 cloud integrations (2 AWS + 1 Azure + 1 GCP)")
        print("  - ~40 resources across all providers")
        print("  - 75 days of daily spend history")
        print("  - 10 pending optimization actions")
        print("  - 6 governance policies with violations")
        print("  - 4 financial reports")
        print("  - Security posture with findings")
        print("  - Architecture data for all integrations")
        print("  - Commitment recommendations")
        print("  - Budget forecasts and alerts")
        print(f"{'='*60}\n")

        print("Next steps:")
        print("  1. Have users sign up at your website via Clerk")
        print("  2. After signup, get their Clerk user IDs from MongoDB:")
        print("     db.users.find({email: /rajiv/i})")
        print("     db.users.find({email: /prabhnandana/i})")
        print("  3. Re-run with actual IDs:")
        print("     python seed_test_users.py --rajiv-id user_xxx --prabhnandana-id user_yyy")
        print()

        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
