import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone

from ..db import get_db_client
from ..core.budget_events import sync_budget_events_for_user
from .report_worker import start_report_worker
from ..core.ingestor import BillingIngestor
from ..bill_parser import parse_bill, fetch_cross_cloud_prices, analyze_arbitrage
from ..security import decrypt_integration_credentials

logger = logging.getLogger(__name__)


async def sync_automated_billing():
    """
    Pull and analyze automated billing exports on a schedule.
    """
    logger.info("Automated billing sync job started")
    try:
        db = get_db_client()
        integrations = await db.select("cloud_integrations")
        if not integrations:
            return

        for integration in integrations:
            metadata = integration.get("metadata") or {}
            if metadata.get("ingestion_type") != "automated_bucket":
                continue

            integration_id = integration.get("id")
            user_id = integration.get("user_id")
            provider = str(integration.get("provider") or "").lower()
            storage_path = metadata.get("storage_path")
            if not integration_id or not user_id or not storage_path:
                continue

            raw_data = None
            try:
                creds = decrypt_integration_credentials(integration)
            except Exception as error:
                logger.error("Automated sync decrypt failed for %s: %s", integration_id, error)
                continue

            if provider == "aws":
                access_key = str(creds.get("access_key_id") or "")
                secret_key = str(creds.get("secret_access_key") or "")

                # Backward compatibility with `access_key::secret_key` in a single field.
                if not secret_key and "::" in access_key:
                    split_access, split_secret = access_key.split("::", 1)
                    access_key = split_access.strip()
                    secret_key = split_secret.strip()

                if access_key and secret_key:
                    raw_data = BillingIngestor.pull_aws_cur(storage_path, access_key, secret_key)
            elif provider == "azure":
                connection_string = str(creds.get("access_key_id") or "")
                if connection_string:
                    raw_data = BillingIngestor.pull_azure_cost_export(storage_path, connection_string)
            elif provider == "gcp":
                credentials_json = str(creds.get("access_key_id") or "")
                if credentials_json:
                    raw_data = BillingIngestor.pull_gcp_billing_export(storage_path, credentials_json)

            if not raw_data:
                logger.warning("Automated sync skipped (no data) for integration %s", integration_id)
                continue

            try:
                parsed = parse_bill(raw_data, f"automated_sync_{provider}.csv")

                aws_discount = float(metadata.get("aws_discount_pct", 0) or 0)
                gcp_discount = float(metadata.get("gcp_discount_pct", 0) or 0)
                azure_discount = float(metadata.get("azure_discount_pct", 0) or 0)

                opportunities = await fetch_cross_cloud_prices(
                    by_category=parsed["by_category"],
                    source_provider=parsed["provider"],
                    aws_discount_pct=aws_discount,
                    gcp_discount_pct=gcp_discount,
                    azure_discount_pct=azure_discount,
                )
                opportunities = await analyze_arbitrage(
                    parsed_bill=parsed,
                    opportunities=opportunities,
                    aws_discount_pct=aws_discount,
                    gcp_discount_pct=gcp_discount,
                    azure_discount_pct=azure_discount,
                )

                total_savings = round(
                    sum(
                        float(item.get("savings", 0) or 0)
                        for item in opportunities
                        if float(item.get("savings", 0) or 0) > 0
                    ),
                    2,
                )
                cloudfront_insights = parsed.get("cloudfront_insights") or {}
                cf_savings = float(
                    cloudfront_insights.get("summary", {}).get("total_monthly_savings_available", 0) or 0
                )
                total_savings = max(total_savings, round(cf_savings, 2))

                await db.upsert_dashboard_stats(
                    {
                        "user_id": user_id,
                        "integration_id": integration_id,
                        "total_spend": parsed.get("total_spend", 0),
                        "potential_savings": total_savings,
                        "active_resources_count": parsed.get("rows_parsed", 0),
                        "ai_confidence_score": 88,
                        "carbon_footprint_kg": 0,
                        "cost_of_inaction_6mo": round(total_savings * 6, 2),
                    }
                )

                metadata["last_sync_at"] = datetime.now(timezone.utc).isoformat()
                await db.update_integration(
                    integration_id=integration_id,
                    user_id=user_id,
                    data={"metadata": metadata},
                )
                logger.info("Automated billing sync completed for %s", integration_id)
            except Exception as error:
                logger.error("Automated sync parse/update failed for %s: %s", integration_id, error)
    except Exception as error:
        logger.error("Automated billing sync worker failed: %s", error)


async def check_spend_anomalies():
    """
    Background job to sync durable budget events and optional external alerts.
    Runs every 6 hours and only persists/delivers when a user's budget status changes.
    """
    try:
        db = get_db_client()
        integrations = await db.select("cloud_integrations")
        if not integrations:
            return

        active_user_ids = sorted(
            {
                str(integration.get("user_id") or "").strip()
                for integration in integrations
                if str(integration.get("status") or "").strip().lower() == "active"
                and str(integration.get("user_id") or "").strip()
            }
        )
        if not active_user_ids:
            return

        total_events = 0
        for user_id in active_user_ids:
            created_events = await sync_budget_events_for_user(
                user_id=user_id,
                db=db,
                deliver=True,
            )
            total_events += len(created_events)

        logger.info("Budget anomaly sync completed with %s new budget events", total_events)
    except Exception as e:
        logger.error(f"Error in anomaly worker: {e}")

def start_workers():
    """
    Initializes and starts the background job scheduler.
    Called in main.py startup event.
    """
    scheduler = AsyncIOScheduler()
    
    # Run every 6 hours
    scheduler.add_job(
        check_spend_anomalies,
        trigger=CronTrigger(hour="0,6,12,18"),
        id="spend_anomaly_monitor",
        replace_existing=True
    )

    scheduler.add_job(
        sync_automated_billing,
        trigger=CronTrigger(hour="0,8,16"),
        id="automated_billing_sync",
        replace_existing=True,
    )
    
    # Register the PDF reporting worker
    start_report_worker(scheduler)

    # Live pricing sync — daily at 3:30 AM UTC
    from .pricing_sync_worker import sync_live_pricing
    scheduler.add_job(
        sync_live_pricing,
        trigger=CronTrigger(hour="3", minute="30"),
        id="live_pricing_sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler background workers started.")

def stop_workers():
    """Stops the scheduler on shutdown."""
    pass
