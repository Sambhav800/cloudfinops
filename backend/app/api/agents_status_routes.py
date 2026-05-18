"""
Derived status routes for the Clousy multi-agent header.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import ClerkUser, get_current_user
from ..db import MongoDBClient, get_db_client

logger = logging.getLogger(__name__)

status_router = APIRouter(prefix="/api/agents", tags=["AI Agent"])

_SAVINGS_NOTIFICATION_TYPES = frozenset({"alert", "cost_optimization"})
_GOVERNANCE_NOTIFICATION_TYPES = frozenset({"governance", "permission_alert", "security_alert"})


class AgentStatusItem(BaseModel):
    name: str
    status: Literal["idle", "scanning"]
    insights_ready: int


class AgentStatusResponse(BaseModel):
    agents: list[AgentStatusItem]


def _notification_type(notification: dict) -> str:
    return str(notification.get("type") or "").strip().lower()


@status_router.get("/status", response_model=AgentStatusResponse)
async def get_agents_status(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Return live, non-AI Clousy agent pill counts derived from MongoDB."""
    notifications: list[dict] = []
    resources: list[dict] = []
    bill_analyses: list[dict] = []

    try:
        notifications = await db.select(
            "agent_notifications",
            filters={"user_id": user.id, "status": "pending"},
        )
    except Exception as error:
        logger.warning("Could not load pending agent notifications for agent status: %s", error)

    try:
        resources = await db.get_resources(user.id)
    except Exception as error:
        logger.warning("Could not load resources for agent status: %s", error)

    try:
        bill_analyses = await db.select("bill_analyses", filters={"user_id": user.id})
    except Exception as error:
        logger.warning("Could not load bill analyses for agent status: %s", error)

    try:
        resource_count = len(resources)
        savings_insights = sum(
            1
            for notification in notifications
            if _notification_type(notification) in _SAVINGS_NOTIFICATION_TYPES
        )
        governance_insights = sum(
            1
            for notification in notifications
            if _notification_type(notification) in _GOVERNANCE_NOTIFICATION_TYPES
        )
        bill_insights = len(bill_analyses)

        agents = [
            AgentStatusItem(
                name="Savings Agent",
                status="scanning" if resource_count > 0 and savings_insights == 0 else "idle",
                insights_ready=savings_insights,
            ),
            AgentStatusItem(
                name="Governance Agent",
                status="scanning" if resource_count > 0 and governance_insights == 0 else "idle",
                insights_ready=governance_insights,
            ),
            AgentStatusItem(
                name="Bill Agent",
                status="idle",
                insights_ready=bill_insights,
            ),
        ]
        return AgentStatusResponse(agents=agents)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.error("get_agents_status failed: %s", error)
        raise HTTPException(status_code=500, detail="Internal error")
