"""
WebSocket endpoint for real-time scan progress updates.
Also stores progress in memory for HTTP polling fallback.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging
import time

from ..auth.clerk import verify_clerk_token
from ..config import get_settings

logger = logging.getLogger(__name__)

# Store active connections per user
active_connections: Dict[str, Set[WebSocket]] = {}

# In-memory scan progress store (fallback for when WebSocket is unreliable)
# Key: user_id, Value: {percent, message, integration_id, timestamp, status}
scan_progress_store: Dict[str, dict] = {}


def _extract_websocket_token(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("token")
    if token:
        token = token.strip()
        if token:
            return token

    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
        if bearer_token:
            return bearer_token

    return None


async def _authenticate_websocket(websocket: WebSocket, requested_user_id: str) -> bool:
    token = _extract_websocket_token(websocket)
    if not token:
        return False

    try:
        user = await verify_clerk_token(token, get_settings())
    except Exception as error:
        logger.warning("WebSocket auth failed for requested user %s: %s", requested_user_id, error)
        return False

    return user.id == requested_user_id


def _remove_connection(user_id: str, websocket: WebSocket) -> None:
    if user_id not in active_connections:
        return

    active_connections[user_id].discard(websocket)
    if not active_connections[user_id]:
        del active_connections[user_id]


def _is_allowed_origin(websocket: WebSocket) -> bool:
    """Validate the WebSocket Origin header against allowed frontends."""
    origin = websocket.headers.get("origin", "")
    if not origin:
        return True  # Non-browser clients (curl, SDKs) don't send Origin

    settings = get_settings()
    frontend = settings.frontend_url
    allowed = {frontend}
    if frontend.startswith("https://"):
        domain = frontend.replace("https://", "")
        allowed.add(f"https://www.{domain}")
        allowed.add(f"https://{domain}")
    if settings.debug:
        allowed.update({"http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"})

    return origin in allowed


async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time updates."""
    if not _is_allowed_origin(websocket):
        await websocket.close(code=1008)
        return

    if not await _authenticate_websocket(websocket, user_id):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    if user_id not in active_connections:
        active_connections[user_id] = set()
    active_connections[user_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as error:
        logger.warning("WebSocket connection for user %s closed with error: %s", user_id, error)
    finally:
        _remove_connection(user_id, websocket)


async def broadcast_to_user(user_id: str, message: dict):
    """Broadcast a message to all connections for a user."""
    if user_id not in active_connections:
        return
    
    message_json = json.dumps(message)
    disconnected = set()
    
    for websocket in active_connections[user_id]:
        try:
            await websocket.send_text(message_json)
        except Exception:
            disconnected.add(websocket)
    
    for ws in disconnected:
        active_connections[user_id].discard(ws)


async def send_scan_progress(user_id: str, integration_id: str, percent: int, message: str):
    """Send scan progress update via WebSocket + store in memory for HTTP polling."""
    progress_data = {
        "type": "scan_progress",
        "integration_id": integration_id,
        "percent": percent,
        "message": message
    }
    
    # Store in memory for HTTP polling fallback
    scan_progress_store[user_id] = {
        **progress_data,
        "timestamp": time.time(),
        "status": "scanning"
    }
    
    # Also try WebSocket broadcast
    await broadcast_to_user(user_id, progress_data)


async def send_scan_complete(user_id: str, integration_id: str, resources_found: int):
    """Notify user that scan is complete."""
    complete_data = {
        "type": "scan_complete",
        "integration_id": integration_id,
        "resources_found": resources_found
    }
    
    # Store completion in memory
    scan_progress_store[user_id] = {
        **complete_data,
        "percent": 100,
        "message": "Analysis Complete",
        "timestamp": time.time(),
        "status": "complete"
    }
    
    await broadcast_to_user(user_id, complete_data)


def get_scan_progress(user_id: str) -> dict:
    """Get current scan progress for HTTP polling fallback."""
    progress = scan_progress_store.get(user_id)
    if not progress:
        return {"type": "idle", "percent": 0, "message": "No active scan", "status": "idle"}

    # Auto-expire progress after 5 minutes of no updates
    if time.time() - progress.get("timestamp", 0) > 300:
        del scan_progress_store[user_id]
        return {"type": "idle", "percent": 0, "message": "No active scan", "status": "idle"}

    return progress


async def send_gpu_metrics_update(user_id: str, metrics: dict):
    """Push real-time GPU utilization update to connected dashboards."""
    await broadcast_to_user(user_id, {
        "type": "gpu_metrics",
        "payload": metrics,
        "timestamp": time.time(),
    })


async def send_gpu_alert(user_id: str, alert: dict):
    """Push a GPU intelligence alert (ghost detected, MIG opportunity, etc.)."""
    await broadcast_to_user(user_id, {
        "type": "gpu_alert",
        "payload": alert,
        "timestamp": time.time(),
    })
