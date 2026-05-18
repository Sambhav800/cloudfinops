from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.db import get_db_client
from app.security import decrypt_integration_credentials


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("repair_db")

TARGET_EMAIL = "nishantj0803@gmail.com"
PROTECTED_USER_ID = "user_38kP2Ff8Jo2Y5g4zCtTr4Qg85kN"
PROTECTED_EMAIL = "sambhavpal5@gmail.com"


async def _safe_select(db, table: str, *, filters: dict, columns: str = "*") -> list[dict]:
    try:
        return await db.select(table, filters=filters, columns=columns)
    except Exception as error:
        logger.error("Failed to select from %s with filters %s: %s", table, filters, error)
        return []


async def _safe_delete(db, table: str, *, filters: dict) -> bool:
    try:
        await db.delete(table, filters)
        return True
    except Exception as error:
        logger.error("Failed to delete from %s with filters %s: %s", table, filters, error)
        return False


async def main() -> int:
    db = get_db_client()
    summary = {
        "corrupted_integrations_found": 0,
        "integrations_deleted": 0,
        "failures": 0,
    }

    try:
        users = await _safe_select(
            db,
            "users",
            filters={"email": TARGET_EMAIL},
        )
        if not users:
            print(f"No user found for {TARGET_EMAIL}.")
            print("Nishant can now go to Settings → Cloud Accounts → Add Account and reconnect GCP with real credentials.")
            return 0

        user = users[0]
        user_id = str(user.get("id") or "").strip()
        email = str(user.get("email") or "").strip().lower()

        if user_id == PROTECTED_USER_ID or email == PROTECTED_EMAIL:
            print(f"HARD ABORT: protected account detected for {email or user_id}. No changes were made.")
            return 1

        integrations = await _safe_select(
            db,
            "cloud_integrations",
            filters={"user_id": user_id, "provider": "gcp"},
        )

        if not integrations:
            print(f"No GCP integrations found for {TARGET_EMAIL}.")
            print("Nishant can now go to Settings → Cloud Accounts → Add Account and reconnect GCP with real credentials.")
            return 0

        for integration in integrations:
            integration_id = str(integration.get("id") or "").strip()
            if not integration_id:
                logger.error("Skipping GCP integration with missing id for user %s", user_id)
                summary["failures"] += 1
                continue

            credentials = {}
            corrupted = False
            try:
                credentials = decrypt_integration_credentials(integration)
            except Exception as error:
                logger.error("Failed to decrypt credentials for integration %s: %s", integration_id, error)
                corrupted = True

            missing_fields = [
                field_name
                for field_name in ("project_id", "service_account_email", "private_key")
                if not str(credentials.get(field_name) or "").strip()
            ]
            if missing_fields:
                logger.error(
                    "Integration %s is missing required GCP credential fields: %s",
                    integration_id,
                    ", ".join(missing_fields),
                )
                corrupted = True

            if not corrupted:
                logger.info("Integration %s looks healthy; leaving it untouched.", integration_id)
                continue

            summary["corrupted_integrations_found"] += 1
            logger.info("Cleaning corrupted GCP integration %s for user %s", integration_id, user_id)

            resources = await _safe_select(
                db,
                "resources",
                filters={"integration_id": integration_id, "user_id": user_id},
                columns="id",
            )
            resource_ids = [
                str(resource.get("id") or "").strip()
                for resource in resources
                if str(resource.get("id") or "").strip()
            ]

            if resource_ids:
                deleted = await _safe_delete(
                    db,
                    "policy_violations",
                    filters={"resource_id": {"$in": resource_ids}, "user_id": user_id},
                )
                if not deleted:
                    summary["failures"] += 1

                deleted = await _safe_delete(
                    db,
                    "agent_notifications",
                    filters={"resource_id": {"$in": resource_ids}, "user_id": user_id},
                )
                if not deleted:
                    summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "resources",
                filters={"integration_id": integration_id, "user_id": user_id},
            )
            if not deleted:
                summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "daily_spend_history",
                filters={"integration_id": integration_id, "user_id": user_id},
            )
            if not deleted:
                summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "dashboard_stats",
                filters={"integration_id": integration_id, "user_id": user_id},
            )
            if not deleted:
                summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "scan_history",
                filters={"integration_id": integration_id, "user_id": user_id},
            )
            if not deleted:
                summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "waste_distribution",
                filters={"integration_id": integration_id, "user_id": user_id},
            )
            if not deleted:
                summary["failures"] += 1

            policies = await _safe_select(
                db,
                "governance_policies",
                filters={"user_id": user_id, "metadata.integration_id": integration_id},
            )
            for policy in policies:
                policy_id = str(policy.get("id") or "").strip()
                if not policy_id:
                    logger.error("Skipping governance policy without id for integration %s", integration_id)
                    summary["failures"] += 1
                    continue
                deleted = await _safe_delete(
                    db,
                    "governance_policies",
                    filters={"id": policy_id, "user_id": user_id},
                )
                if not deleted:
                    summary["failures"] += 1

            deleted = await _safe_delete(
                db,
                "cloud_integrations",
                filters={"id": integration_id, "user_id": user_id},
            )
            if deleted:
                summary["integrations_deleted"] += 1
            else:
                summary["failures"] += 1

        print("Repair summary:")
        print(f"- Target user: {TARGET_EMAIL}")
        print(f"- Corrupted GCP integrations found: {summary['corrupted_integrations_found']}")
        print(f"- GCP integrations deleted: {summary['integrations_deleted']}")
        print(f"- Delete-step failures: {summary['failures']}")
        print("Nishant can now go to Settings → Cloud Accounts → Add Account and reconnect GCP with real credentials.")
        return 0 if summary["failures"] == 0 else 2
    finally:
        try:
            await db.close()
        except Exception as error:
            logger.error("Failed to close DB client cleanly: %s", error)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
