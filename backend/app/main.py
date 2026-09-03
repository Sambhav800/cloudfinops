"""
CloudFinOps Python Backend - Main Application

FastAPI application for high-performance cloud resource scanning,
AI-driven analysis, and real-time dashboard updates.
"""
import logging
import traceback
import uuid

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from .config import get_settings
from .core.rate_limiter import RateLimiterMiddleware
from .api import router
from .api.agent_routes import agent_router
from .api.agents_status_routes import status_router as agents_status_router
from .api.finance_routes import finance_router
from .api.finance_estimate import estimate_router as finance_estimate_router
from .api.reports_routes import reports_router
from .api.slack_routes import slack_router
from .api.architecture_routes import router as architecture_router
from .api.discount_manager_routes import discount_router
from .api.dashboard_summary_routes import dashboard_summary_router
from .api.exclusion_routes import exclusion_router
from .api.recommendations_routes import recommendations_router
from .api.websocket import websocket_endpoint
try:
    from .workers.anomaly_worker import start_workers, stop_workers
except Exception:
    def start_workers():
        logger.warning("Worker startup skipped (optional dependencies missing)")

    def stop_workers():
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    if not settings:
        raise RuntimeError(
            "FATAL: Settings failed to load. Ensure CLERK_SECRET_KEY, "
            "MONGODB_URI, and ENCRYPTION_KEY are set."
        )
    if not settings.encryption_key or len(settings.encryption_key) < 32:
        raise RuntimeError(
            "FATAL: ENCRYPTION_KEY must be set and at least 32 characters "
            "(64 hex chars for AES-256). Backend cannot start without it."
        )
    logger.info("Starting %s", settings.app_name)
    logger.info("Frontend URL: %s", settings.frontend_url)
    logger.info("MongoDB URI: %s", "configured" if settings.mongodb_uri else "missing")

    # Warm up DB connection + indexes at startup (not on first user request)
    from .db import get_db_client
    try:
        db = get_db_client()
        await db._get_db()
        logger.info("Database connection and indexes ready")
    except Exception as e:
        logger.warning("DB warmup failed (will retry on first request): %s", e)

    # Startup workers
    start_workers()
    
    yield
    
    # Shutdown
    stop_workers()
    from .core.price_service import price_service
    await price_service.client.aclose()
    logger.info("Shutting down CloudFinOps Backend")


# Create FastAPI application
app = FastAPI(
    title="CloudFinOps Backend",
    description="Python backend for AI-driven cloud cost optimization",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Configuration
settings = get_settings()
allowed_origins = [settings.frontend_url]
if settings.debug:
    allowed_origins += [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(allowed_origins)),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)
app.add_middleware(RateLimiterMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler: log full traceback, return safe response to client."""
    request_id = str(uuid.uuid4())[:8]
    logger.error(
        "Unhandled exception [request_id=%s] %s %s: %s\n%s",
        request_id, request.method, request.url.path,
        exc, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred.", "request_id": request_id},
    )


# Mount API routes
app.include_router(router)
app.include_router(finance_router)
app.include_router(finance_estimate_router)
app.include_router(reports_router)
app.include_router(agent_router)
app.include_router(agents_status_router)
app.include_router(slack_router)
app.include_router(architecture_router)
app.include_router(discount_router)
app.include_router(dashboard_summary_router)
app.include_router(exclusion_router)
app.include_router(recommendations_router)


# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time scan updates."""
    await websocket_endpoint(websocket, user_id)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "CloudFinOps Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
