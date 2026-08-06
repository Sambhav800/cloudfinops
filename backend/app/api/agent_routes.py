"""
API Routes for the CloudFinOps AI Agent.
Provides a chat endpoint with Gemini function calling.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import uuid
import logging

from ..auth import get_current_user, ClerkUser
from ..db import get_db_client, MongoDBClient
from ..ai.agent import CloudFinOpsAgent
from ..core.agent_context import build_agent_system_prompt, _get_first_name

logger = logging.getLogger(__name__)

agent_router = APIRouter(prefix="/api/agent", tags=["AI Agent"])

USD_TO_INR_RATE = 95.19


class ChatRequest(BaseModel):
    """Chat request from the frontend."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response to the frontend."""
    success: bool
    response: str
    session_id: str


from fastapi.responses import StreamingResponse


def _first_name_from_user_row(user: ClerkUser, row: dict | None) -> str:
    if row:
        derived = _get_first_name(row.get("full_name"), row.get("email"))
        if derived:
            return derived

    if user.first_name and str(user.first_name).strip():
        return str(user.first_name).strip()
    if user.email:
        return _get_first_name(None, user.email)
    return ""


def _format_last_scan(integrations: list[dict]) -> str:
    latest_scan: datetime | None = None
    for integration in integrations:
        last_scan = integration.get("last_scan")
        if not last_scan:
            continue
        try:
            parsed = datetime.fromisoformat(str(last_scan).replace("Z", "+00:00"))
        except Exception:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if latest_scan is None or parsed > latest_scan:
            latest_scan = parsed

    if latest_scan is None:
        return "never"

    delta = datetime.now(timezone.utc) - latest_scan.astimezone(timezone.utc)
    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        return "less than an hour ago"
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def _to_float(value: object) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _source_currency_for_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"aws", "azure"}:
        return "USD"
    return "INR"


def _to_display_inr(value: object, source_currency: str) -> float:
    amount = _to_float(value)
    if source_currency.upper() == "USD":
        amount *= USD_TO_INR_RATE
    return round(amount, 2)


def _format_inr(value: object) -> str:
    return f"₹{_to_float(value):,.2f}"


def _summary_stats_for_active_integrations(
    stats: list[dict],
    integrations: list[dict],
) -> list[dict]:
    active_integration_ids = {
        str(integration.get("id"))
        for integration in integrations
        if integration.get("id")
    }
    integration_stats = [
        item
        for item in stats
        if str(item.get("integration_id") or "") in active_integration_ids
    ]
    if integration_stats:
        return integration_stats

    portfolio_stats = [
        item for item in stats if not item.get("integration_id")
    ]
    return portfolio_stats or stats


def _provider_for_stat(item: dict, provider_by_integration_id: dict[str, str]) -> str:
    integration_id = str(item.get("integration_id") or "")
    return str(
        item.get("provider")
        or provider_by_integration_id.get(integration_id, "")
    )


def _display_stat_amount(
    item: dict,
    field_name: str,
    provider_by_integration_id: dict[str, str],
) -> float:
    return _to_display_inr(
        item.get(field_name),
        _source_currency_for_provider(
            _provider_for_stat(item, provider_by_integration_id)
        ),
    )


@agent_router.post("/chat")
async def agent_chat(
    request: ChatRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """
    Chat with the AI Agent via Server-Sent Events (SSE).
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_stream():
        try:
            agent = CloudFinOpsAgent(db_client=db, user_id=user.id)
            # The agent's chat method now yields SSE formatted strings directly
            async for chunk in agent.chat(
                message=request.message,
                session_id=session_id,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Agent stream error for user {user.id}: {e}", exc_info=True)
            import json
            yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error occurred.'})}\n\n"

    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream"
    )


@agent_router.get("/summary")
async def get_account_summary(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    await build_agent_system_prompt(user.id, db)

    stats = []
    user_rows = []
    notifications = []
    violations = []
    integrations = []

    try:
        stats = await db.select("dashboard_stats", filters={"user_id": user.id})
    except Exception as error:
        logger.debug("Could not load dashboard stats for agent summary: %s", error)

    try:
        user_rows = await db.select("users", filters={"id": user.id})
    except Exception as error:
        logger.debug("Could not load user row for agent summary: %s", error)

    try:
        notifications = await db.select(
            "agent_notifications",
            filters={"user_id": user.id, "status": "pending"},
        )
    except Exception as error:
        logger.debug("Could not load agent notifications for summary: %s", error)

    try:
        violations = await db.select(
            "policy_violations",
            filters={"user_id": user.id, "status": "active"},
        )
    except Exception as error:
        logger.debug("Could not load policy violations for summary: %s", error)

    try:
        integrations = await db.select(
            "cloud_integrations",
            filters={"user_id": user.id, "status": "active"},
        )
    except Exception as error:
        logger.debug("Could not load integrations for summary: %s", error)

    first_name = _first_name_from_user_row(user, user_rows[0] if user_rows else None)
    summary_stats = _summary_stats_for_active_integrations(stats, integrations)
    provider_by_integration_id = {
        str(integration.get("id")): str(integration.get("provider") or "")
        for integration in integrations
        if integration.get("id")
    }

    resources = sum(int(item.get("active_resources_count") or 0) for item in summary_stats)
    savings = round(
        sum(
            _display_stat_amount(item, "potential_savings", provider_by_integration_id)
            for item in summary_stats
        ),
        2,
    )
    total_spend = round(
        sum(
            _display_stat_amount(item, "total_spend", provider_by_integration_id)
            for item in summary_stats
        ),
        2,
    )
    confidence_values = [
        int(item.get("ai_confidence_score") or 0)
        for item in summary_stats
        if item.get("ai_confidence_score") is not None
    ]
    confidence = round(sum(confidence_values) / len(confidence_values)) if confidence_values else 0
    alert_count = len(notifications)
    violation_count = len(violations)
    providers = []
    seen: set[str] = set()
    for integration in integrations:
        provider = str(integration.get("provider") or "").upper()
        if provider and provider not in seen:
            seen.add(provider)
            providers.append(provider)

    alert_line = (
        f"You also have {alert_count} open alerts and {violation_count} active governance violations."
        if alert_count > 0 and violation_count > 0
        else f"You also have {alert_count} open alerts."
        if alert_count > 0
        else f"You also have {violation_count} active governance violations."
        if violation_count > 0
        else "You have no open alerts right now."
    )

    clouds = ", ".join(providers) if providers else "no connected clouds yet"
    greeting_name = f"{first_name}, " if first_name else ""
    summary = (
        f"{greeting_name}I'm looking at your live CloudFinOps account. "
        f"You're running {resources:,} scanned resources across {clouds}, "
        f"month-to-date spend is {_format_inr(total_spend)}, and I've identified {_format_inr(savings)}/month in savings opportunities. "
        f"{alert_line} "
        f"Current AI analysis confidence is {confidence}% and your latest scan was {_format_last_scan(integrations)}."
    )

    return {
        "summary": summary,
        "total_spend": total_spend,
        "savings": savings,
        "currency": "INR",
        "resources": resources,
        "alerts": alert_count,
        "violations": violation_count,
        "confidence": confidence,
        "providers": providers,
    }
