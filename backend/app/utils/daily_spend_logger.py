"""
Daily Spend Logger Utility
Captures daily cost snapshots and stores them in daily_spend_history table.
Run this as a daily cron job or scheduled task.
"""

import logging
from datetime import date, datetime
from typing import Dict, Optional
import asyncio

from ..db import get_db_client

logger = logging.getLogger(__name__)


async def log_daily_spend(user_id: str, integration_id: str) -> bool:
    """
    Calculate and log daily spend for a specific integration.
    
    This function:
    1. Aggregates current resource costs by service type
    2. Inserts/updates the daily spend record
    3. Returns True on success, False on failure
    
    Args:
        user_id: The user ID who owns the integration
        integration_id: The cloud integration ID to log spend for
        
    Returns:
        bool: True if logging succeeded, False otherwise
    """
    try:
        db = get_db_client()
        
        # Get all resources for this integration
        resources = await db.get_resources(user_id, integration_id)
        
        if not resources:
            logger.warning(f"No resources found for integration {integration_id}")
            return False
        
        # Calculate total spend
        total_spend = sum(r.get("cost", 0) for r in resources)
        
        # Build service breakdown (group by service_type)
        service_breakdown: Dict[str, float] = {}
        for resource in resources:
            service_type = resource.get("service_type", "Unknown")
            cost = resource.get("cost", 0)
            
            if service_type in service_breakdown:
                service_breakdown[service_type] += cost
            else:
                service_breakdown[service_type] = cost
        
        # Round all values to 2 decimal places
        service_breakdown = {
            service: round(cost, 2) 
            for service, cost in service_breakdown.items()
        }
        
        today = date.today()
        
        # Save using the dedicated method
        await db.save_daily_spend_history(
            user_id=user_id,
            integration_id=integration_id,
            spend_date=today.isoformat(),
            amount=round(total_spend, 2),
            service_breakdown=service_breakdown
        )
        
        logger.info(f"Logged daily spend for {integration_id}: ${total_spend:.2f} on {today}")
        logger.info(f"  Service breakdown: {service_breakdown}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to log daily spend for integration {integration_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def log_all_integrations_daily_spend() -> Dict[str, bool]:
    """
    Log daily spend for ALL active integrations across all users.
    
    This is the main function to call from a cron job.
    
    Returns:
        Dict[str, bool]: Map of integration_id -> success status
    """
    results = {}
    
    try:
        db = get_db_client()
        
        logger.info(f"Starting daily spend logging for all integrations (date: {date.today()})")
        
        # Get all active integrations
        integrations = await db.select(
            "cloud_integrations",
            filters={"status": "active"}
        )
        
        if not integrations:
            logger.warning("No active integrations found for daily spend logging")
            return results
        
        for integration in integrations:
            integration_id = integration.get("id")
            user_id = integration.get("user_id")
            if integration_id and user_id:
                success = await log_daily_spend(user_id, integration_id)
                results[integration_id] = success
        
        logger.info(f"Daily spend logging completed: {sum(results.values())}/{len(results)} succeeded")
        return results
        
    except Exception as e:
        logger.error(f"Failed to log daily spend for all integrations: {e}")
        return results


async def get_spend_trend(
    user_id: str, 
    integration_id: str, 
    days: int = 7
) -> list:
    """
    Retrieve spend trend data for the last N days.
    
    Args:
        user_id: User ID
        integration_id: Integration ID
        days: Number of days to retrieve (default 7)
        
    Returns:
        List of daily spend records, newest first
    """
    try:
        db = get_db_client()
        
        # Use the dedicated method in MongoDBClient
        records = await db.get_daily_spend_history(
            user_id=user_id,
            integration_id=integration_id,
            days=days
        )
        
        return records or []
        
    except Exception as e:
        logger.error(f"Failed to get spend trend: {e}")
        return []


# CLI entry point for manual testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m app.utils.daily_spend_logger <user_id> <integration_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    integration_id = sys.argv[2]
    
    # Run the logger
    success = asyncio.run(log_daily_spend(user_id, integration_id))
    
    if success:
        print("✅ Daily spend logged successfully")
        sys.exit(0)
    else:
        print("❌ Failed to log daily spend")
        sys.exit(1)

