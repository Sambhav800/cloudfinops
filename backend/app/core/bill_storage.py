"""
Backend-owned raw bill storage helpers.

Uploads original billing files to private Google Cloud Storage using the
GCS JSON API so the exact uploaded source document can be retained for
download, reprocessing, and audit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from google.auth import exceptions as google_auth_exceptions
from google.oauth2 import service_account

from ..config import get_settings


logger = logging.getLogger(__name__)

_GCS_RW_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"
_GCS_RO_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
_GCS_UPLOAD_TIMEOUT_SECONDS = 45.0
_GCS_DOWNLOAD_TIMEOUT_SECONDS = 45.0


class RawBillStorageError(RuntimeError):
    """Base error for archived raw bill storage failures."""


class RawBillStorageNotFound(RawBillStorageError):
    """Raised when the archived raw bill is missing from storage."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(filename or "").strip())
    safe = safe.strip("._-")
    return safe or "uploaded-bill"


def _build_object_path(prefix: str, user_id: str, filename: str, content_hash: str) -> str:
    now = datetime.now(timezone.utc)
    normalized_prefix = str(prefix or "bill-uploads").strip().strip("/") or "bill-uploads"
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date_path = now.strftime("%Y/%m/%d")
    return (
        f"{normalized_prefix}/{user_id}/{date_path}/"
        f"{timestamp}-{content_hash[:12]}-{_safe_filename(filename)}"
    )


def build_raw_bill_storage_metadata(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
    status: str,
    bucket: str | None = None,
    object_path: str | None = None,
    stored_at: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "storage_provider": "gcs",
        "status": status,
        "original_filename": filename,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": int(size_bytes or 0),
        "sha256": sha256,
    }
    if bucket:
        metadata["bucket"] = bucket
    if object_path:
        metadata["object_path"] = object_path
    if stored_at:
        metadata["stored_at"] = stored_at
    return metadata


def build_raw_bill_storage_failure_metadata(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
    bucket: str | None = None,
    object_path: str | None = None,
) -> dict[str, Any]:
    return build_raw_bill_storage_metadata(
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        status="failed",
        bucket=bucket,
        object_path=object_path,
    )


def _build_scoped_credentials(scope: str):
    settings = get_settings()
    credentials_json = str(settings.gcs_bill_upload_credentials_json or "").strip()

    if credentials_json:
        try:
            credentials_info = json.loads(credentials_json)
        except json.JSONDecodeError as error:
            raise RawBillStorageError("GCS bill upload credentials JSON is invalid") from error

        return service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=[scope],
        )

    try:
        credentials, _ = google_auth_default(scopes=[scope])
        return credentials
    except DefaultCredentialsError as error:
        raise RawBillStorageError("No Google Cloud credentials are available for bill archival") from error


def _refresh_access_token(scope: str) -> str:
    credentials = _build_scoped_credentials(scope)
    try:
        credentials.refresh(Request())
        token = str(getattr(credentials, "token", "") or "").strip()
        if token:
            return token
    except google_auth_exceptions.RefreshError as error:
        logger.warning("Google ADC refresh failed for raw bill archival: %s", error)

    fallback_token = _refresh_access_token_via_gcloud()
    if fallback_token:
        return fallback_token

    raise RawBillStorageError("Google Cloud credentials did not yield an access token")


def _refresh_access_token_via_gcloud() -> str | None:
    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        return None

    try:
        result = subprocess.run(
            [gcloud_path, "auth", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (subprocess.SubprocessError, OSError) as error:
        logger.warning("gcloud access-token fallback failed for raw bill archival: %s", error)
        return None

    token = str(result.stdout or "").strip()
    return token or None


def _extract_gcs_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""

    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""

    message = str(error.get("message") or "").strip()
    if message:
        return message

    errors = error.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or first.get("reason") or "").strip()

    return ""


async def archive_uploaded_bill_to_gcs(
    *,
    user_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    content_hash: str,
) -> dict[str, Any]:
    settings = get_settings()
    bucket = str(settings.gcs_bill_upload_bucket or "").strip()
    normalized_content_type = str(content_type or "application/octet-stream").strip() or "application/octet-stream"
    size_bytes = len(content or b"")

    if not bucket:
        return build_raw_bill_storage_metadata(
            filename=filename,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
            sha256=content_hash,
            status="not_configured",
        )

    object_path = _build_object_path(
        str(settings.gcs_bill_upload_prefix or "bill-uploads"),
        user_id,
        filename,
        content_hash,
    )

    try:
        token = await asyncio.to_thread(_refresh_access_token, _GCS_RW_SCOPE)
    except RawBillStorageError as error:
        logger.warning("Raw bill archival credentials unavailable: %s", error)
        return build_raw_bill_storage_metadata(
            filename=filename,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
            sha256=content_hash,
            status="credentials_unavailable",
            bucket=bucket,
            object_path=object_path,
        )

    upload_url = f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": normalized_content_type,
    }

    try:
        async with httpx.AsyncClient(timeout=_GCS_UPLOAD_TIMEOUT_SECONDS) as client:
            response = await client.post(
                upload_url,
                params={"uploadType": "media", "name": object_path},
                headers=headers,
                content=content,
            )
    except httpx.HTTPError as error:
        logger.warning("Raw bill archival request failed for %s: %s", filename, error)
        return build_raw_bill_storage_failure_metadata(
            filename=filename,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
            sha256=content_hash,
            bucket=bucket,
            object_path=object_path,
        )

    if not response.is_success:
        logger.warning(
            "Raw bill archival failed for %s with status %s: %s",
            filename,
            response.status_code,
            _extract_gcs_error_detail(response),
        )
        return build_raw_bill_storage_failure_metadata(
            filename=filename,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
            sha256=content_hash,
            bucket=bucket,
            object_path=object_path,
        )

    response_payload = response.json() if response.content else {}
    stored_at = str(response_payload.get("timeCreated") or _utc_now_iso())
    uploaded_content_type = str(response_payload.get("contentType") or normalized_content_type)

    return build_raw_bill_storage_metadata(
        filename=filename,
        content_type=uploaded_content_type,
        size_bytes=int(response_payload.get("size") or size_bytes),
        sha256=content_hash,
        status="stored",
        bucket=bucket,
        object_path=str(response_payload.get("name") or object_path),
        stored_at=stored_at,
    )


async def download_archived_bill_from_gcs(
    raw_bill_metadata: dict[str, Any],
) -> tuple[bytes, str, str]:
    status = str(raw_bill_metadata.get("status") or "").strip().lower()
    bucket = str(raw_bill_metadata.get("bucket") or "").strip()
    object_path = str(raw_bill_metadata.get("object_path") or "").strip()
    filename = str(raw_bill_metadata.get("original_filename") or "uploaded-bill")
    content_type = str(raw_bill_metadata.get("content_type") or "application/octet-stream").strip() or "application/octet-stream"

    if status != "stored" or not bucket or not object_path:
        raise RawBillStorageNotFound("Raw bill file is not available for this analysis")

    token = await asyncio.to_thread(_refresh_access_token, _GCS_RO_SCOPE)
    download_url = (
        f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}"
        f"/o/{quote(object_path, safe='')}"
    )

    try:
        async with httpx.AsyncClient(timeout=_GCS_DOWNLOAD_TIMEOUT_SECONDS) as client:
            response = await client.get(
                download_url,
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as error:
        raise RawBillStorageError("Could not retrieve the archived raw bill file") from error

    if response.status_code == 404:
        raise RawBillStorageNotFound("Archived raw bill file was not found in storage")
    if not response.is_success:
        raise RawBillStorageError(
            f"Archived raw bill download failed with status {response.status_code}"
        )

    response_content_type = str(response.headers.get("content-type") or content_type).strip() or content_type
    return response.content, response_content_type, _safe_filename(filename)
