"""
Gemini model selection helpers.

Explicit configured model names always win. Auto aliases are resolved lazily from
Google's model list and fall back to the repo default if discovery is unavailable.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import DEFAULT_GEMINI_FLASH_MODEL

logger = logging.getLogger(__name__)

GEMINI_MODELS_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_AUTO_FLASH_ALIASES = frozenset({
    "auto",
    "auto-flash",
    "latest",
    "latest-flash",
    "gemini-latest-flash",
})

_CACHE_TTL = timedelta(hours=6)
_cached_latest_flash_model: str | None = None
_cached_latest_flash_expires_at: datetime | None = None


def is_gemini_auto_model(model_name: str | None) -> bool:
    """Return true when a configured model name requests automatic Flash discovery."""
    return str(model_name or "").strip().lower() in GEMINI_AUTO_FLASH_ALIASES


def _normalize_model_name(value: Any) -> str:
    raw = str(value or "").strip()
    return raw.removeprefix("models/")


def _model_sort_key(model_name: str) -> tuple[int, int, int, int, int, str]:
    version_match = re.search(r"gemini-(\d+(?:\.\d+)*)", model_name)
    parts = [int(part) for part in version_match.group(1).split(".")] if version_match else []
    padded = (parts + [0, 0, 0])[:3]
    stable_score = 0 if any(token in model_name for token in ("preview", "exp", "experimental")) else 1
    text_score = 0 if any(token in model_name for token in ("audio", "image", "live", "tts")) else 1
    non_lite_score = 0 if "lite" in model_name else 1
    return (padded[0], padded[1], padded[2], stable_score, text_score + non_lite_score, model_name)


def _candidate_supports_generate_content(row: dict[str, Any]) -> bool:
    methods = row.get("supportedGenerationMethods")
    if not isinstance(methods, list):
        return True
    return "generateContent" in methods


def _select_latest_flash_model(rows: list[dict[str, Any]]) -> str | None:
    candidates: list[str] = []
    for row in rows:
        model_name = _normalize_model_name(row.get("name"))
        normalized = model_name.lower()
        if not model_name or "gemini-" not in normalized or "flash" not in normalized:
            continue
        if "embedding" in normalized or not _candidate_supports_generate_content(row):
            continue
        candidates.append(model_name)

    if not candidates:
        return None
    text_candidates = [
        model_name
        for model_name in candidates
        if not any(token in model_name for token in ("audio", "image", "live", "tts"))
    ]
    general_candidates = [model_name for model_name in text_candidates if "lite" not in model_name]
    return sorted(general_candidates or text_candidates or candidates, key=_model_sort_key, reverse=True)[0]


async def resolve_gemini_model_name(
    configured_model: str | None,
    *,
    api_key: str | None = None,
    fallback: str = DEFAULT_GEMINI_FLASH_MODEL,
) -> str:
    """Resolve a configured Gemini model or auto alias into a concrete model id."""
    try:
        normalized = str(configured_model or "").strip()
        if not normalized:
            return fallback
        if not is_gemini_auto_model(normalized):
            return normalized
        if not api_key:
            return fallback

        global _cached_latest_flash_model, _cached_latest_flash_expires_at
        now = datetime.now(timezone.utc)
        if (
            _cached_latest_flash_model
            and _cached_latest_flash_expires_at
            and now < _cached_latest_flash_expires_at
        ):
            return _cached_latest_flash_model

        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(GEMINI_MODELS_API_URL, params={"key": api_key})
            response.raise_for_status()
        payload = response.json()
        rows = payload.get("models") if isinstance(payload, dict) else None
        latest = _select_latest_flash_model(rows if isinstance(rows, list) else [])
        if not latest:
            return fallback

        _cached_latest_flash_model = latest
        _cached_latest_flash_expires_at = now + _CACHE_TTL
        return latest
    except Exception as error:
        logger.warning("Gemini auto model resolution failed, using fallback: %s", error)
        return fallback
