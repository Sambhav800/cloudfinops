import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..ai.agent import CloudFinOpsAgent
from ..config import get_settings
from ..db import get_db_client

logger = logging.getLogger(__name__)

slack_router = APIRouter(prefix="/api/slack", tags=["Slack Bot"])
_SLACK_SIGNATURE_VERSION = "v0"
_SLACK_MAX_REQUEST_AGE_SECONDS = 60 * 5


def _build_slack_signature(signing_secret: str, timestamp: str, body: bytes) -> str:
    basestring = f"{_SLACK_SIGNATURE_VERSION}:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{_SLACK_SIGNATURE_VERSION}={digest}"


def _is_valid_slack_request(
    signing_secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    now: int | None = None,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False

    try:
        request_ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    current_ts = int(now if now is not None else time.time())
    if abs(current_ts - request_ts) > _SLACK_MAX_REQUEST_AGE_SECONDS:
        return False

    expected_signature = _build_slack_signature(signing_secret, timestamp, body)
    return hmac.compare_digest(expected_signature, signature)


async def process_slack_message(event: Dict[str, Any]):
    """Background task to let Gemini process a Slack message and reply asynchronously."""
    # This is still a stub for the enterprise version; the fixed service user is
    # intentionally kept until workspace-to-user mapping is implemented.
    user_id = "slack-integration-user"
    channel = event.get("channel")
    text = event.get("text")

    if not channel or not text:
        return

    try:
        db = get_db_client()
        agent = CloudFinOpsAgent(db_client=db, user_id=user_id)
        async for _ in agent.chat(message=text, session_id=f"slack-{channel}"):
            pass
        logger.info("Processed Slack message in channel %s", channel)
    except Exception as error:
        logger.error("Error processing slack message: %s", error)


@slack_router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Slack Event Subscriptions (Webhooks).
    Handles url_verification challenge and standard message events.
    """
    settings = get_settings()
    signing_secret = settings.slack_signing_secret
    if not signing_secret:
        logger.warning("Slack event received but SLACK_SIGNING_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Slack integration is not configured")

    body = await request.body()
    timestamp = request.headers.get("x-slack-request-timestamp")
    signature = request.headers.get("x-slack-signature")

    if not _is_valid_slack_request(signing_secret, timestamp, signature, body):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    if data.get("type") == "event_callback":
        event = data.get("event", {})

        if event.get("bot_id"):
            return {"status": "ignored"}

        if event.get("type") == "message":
            background_tasks.add_task(process_slack_message, event)
            return {"status": "ok"}

    return {"status": "ignored"}
