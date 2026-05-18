import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json
from ..db import get_db_client

logger = logging.getLogger(__name__)

async def log_audit_event(
    user_id: str,
    action_type: str,
    resource_target: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an event to the SOC2 compliance audit_logs table.
    
    Args:
        user_id: The Clerk user ID performing the action
        action_type: Category of action (e.g., "SCAN_TRIGGERED", "AI_PROMPT", "INTEGRATION_ADDED")
        resource_target: The specific cloud resource, integration ID, or target affected
        metadata: Any additional context (e.g., prompt text, query parameters)
    """
    try:
        db = get_db_client()
        
        event_data = {
            "user_id": user_id,
            "action_type": action_type,
            "resource_target": resource_target or "N/A",
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # We wrap in a try-except specifically so audit log failures don't 
        # break the main application flow (best practice for passive logging).
        await db.insert("audit_logs", event_data)
        
        logger.debug(f"Audit Logged [{action_type}] for user {user_id}")
        
    except Exception as e:
        error_text = str(e)
        if "PGRST205" in error_text or "audit_logs" in error_text:
            logger.warning(
                "Audit log table is unavailable (audit_logs). Continuing without audit persistence."
            )
        else:
            logger.error(f"Could not write to audit_logs table: {e}")
