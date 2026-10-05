"""
Background worker helpers for recommendation AI enrichment.

FastAPI BackgroundTasks runs this in-process after the API response is sent. It is
not a durable queue, but it keeps user-facing pages from waiting on Gemini while
we still persist every job in MongoDB for retry/audit.
"""

import logging
from typing import Any, Dict

from ..config import get_settings
from ..core.recommendation_ai_enrichment import drain_recommendation_ai_enrichment_queue
from ..db import get_db_client

logger = logging.getLogger(__name__)


async def drain_user_recommendation_ai_enrichment(
    *,
    user_id: str,
    max_jobs: int = 25,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """Drain queued recommendation AI enrichment jobs for one user."""
    try:
        settings = get_settings()
        if not settings.gemini_api_key:
            logger.info("Recommendation AI enrichment drain skipped; GEMINI_API_KEY is not configured")
            return {
                "status": "skipped",
                "message": "GEMINI_API_KEY is not configured",
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
            }

        db = get_db_client()
        result = await drain_recommendation_ai_enrichment_queue(
            db=db,
            user_id=user_id,
            model=settings.gemini_agent_model,
            gemini_api_key=settings.gemini_api_key,
            max_jobs=max_jobs,
            batch_size=batch_size,
        )
        logger.info(
            "Recommendation AI enrichment drain completed for user %s: processed=%s succeeded=%s failed=%s",
            user_id,
            result.get("processed"),
            result.get("succeeded"),
            result.get("failed"),
        )
        return result
    except Exception as error:
        logger.error("Recommendation AI enrichment drain failed for user %s: %s", user_id, error)
        return {
            "status": "failed",
            "message": "Recommendation AI enrichment drain failed",
            "processed": 0,
            "succeeded": 0,
            "failed": 1,
            "skipped": 0,
            "results": [],
        }
