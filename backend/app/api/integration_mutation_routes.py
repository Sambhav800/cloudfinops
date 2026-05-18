import asyncio
import hashlib
import logging
from typing import Any, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..core.audit import log_audit_event
from ..core.retry import (
    build_aws_retry_config,
    call_with_backoff,
    is_aws_retryable,
    is_azure_retryable,
    is_gcp_retryable,
    is_httpx_retryable,
)
from ..db import MongoDBClient, get_db_client
from ..security.crypto import decrypt_integration_credentials, encrypt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Integration Mutations"])

MANUAL_VALIDATION_FAILURE_DETAILS = {
    "aws": "AWS credentials are invalid or lack the required read-only access.",
    "azure": "Azure credentials are invalid or do not have access to the supplied subscription.",
    "gcp": "GCP service-account credentials are invalid or lack the required access.",
}
MANUAL_VALIDATION_RATE_LIMIT_DETAILS = {
    "aws": "AWS validation is temporarily rate limited. Please retry shortly.",
    "azure": "Azure validation is temporarily rate limited. Please retry shortly.",
    "gcp": "GCP validation is temporarily rate limited. Please retry shortly.",
}


class CreatedIntegrationResponse(BaseModel):
    id: str
    provider: str
    name: str
    status: str
    last_scan: Optional[str] = None
    regions: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class ManualIntegrationCreateRequest(BaseModel):
    provider: Literal["aws", "azure", "gcp"]
    name: str
    regions: list[str] = Field(default_factory=list)
    auth_type: Optional[Literal["role", "keys"]] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    subscription_id: Optional[str] = None
    project_id: Optional[str] = None
    service_account_email: Optional[str] = None
    private_key: Optional[str] = None
    billing_export_table: Optional[str] = None


class AutomatedSyncIntegrationCreateRequest(BaseModel):
    provider: Literal["aws", "azure", "gcp"]
    storage_path: str
    credential: str
    aws_discount: Optional[float] = 0.0
    azure_discount: Optional[float] = 0.0
    gcp_discount: Optional[float] = 0.0


class DeleteIntegrationResponse(BaseModel):
    success: bool


def _encrypt_field(value: str) -> str:
    encrypted_value, iv = encrypt(value)
    return f"{encrypted_value}::{iv}"


def _normalize_regions(provider: str, regions: list[str]) -> list[str]:
    cleaned = [region.strip() for region in regions if isinstance(region, str) and region.strip()]
    if cleaned:
        return cleaned

    if provider == "aws":
        return ["us-east-1"]
    if provider == "azure":
        return ["eastus"]
    return ["us-central1"]


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_private_key(raw_private_key: str) -> str:
    private_key = raw_private_key.strip().replace("\r\n", "\n").replace("\\n", "\n").strip()
    begin_marker = "-----BEGIN PRIVATE KEY-----"
    end_marker = "-----END PRIVATE KEY-----"

    if begin_marker not in private_key or end_marker not in private_key:
        raise HTTPException(
            status_code=400,
            detail="Invalid private key format. Paste the service-account private key with BEGIN/END lines.",
        )

    return private_key


def _manual_account_fingerprint(
    provider: Literal["aws", "azure", "gcp"],
    validated_payload: dict[str, Optional[str]],
) -> str:
    if provider == "aws":
        if validated_payload.get("auth_type") == "role":
            identity = f"role:{validated_payload.get('role_arn') or ''}"
        else:
            identity = f"keys:{validated_payload.get('access_key_id') or ''}"
    elif provider == "azure":
        identity = f"subscription:{validated_payload.get('subscription_id') or ''}"
    else:
        identity = (
            f"project:{validated_payload.get('project_id') or ''}|"
            f"service_account:{validated_payload.get('service_account_email') or ''}"
        )

    digest = hashlib.sha256(f"{provider}:{identity}".lower().encode("utf-8")).hexdigest()
    return f"{provider}:{digest}"


def _legacy_account_fingerprint_from_integration(
    provider: Literal["aws", "azure", "gcp"],
    integration: dict[str, Any],
) -> Optional[str]:
    try:
        credentials = decrypt_integration_credentials(integration)
    except Exception:
        return None

    if provider == "aws":
        role_arn = _normalize_optional_string(credentials.get("role_arn"))
        access_key_id = _normalize_optional_string(credentials.get("access_key_id"))
        if role_arn:
            return _manual_account_fingerprint(
                provider,
                {
                    "auth_type": "role",
                    "role_arn": role_arn,
                    "external_id": _normalize_optional_string(credentials.get("external_id")),
                },
            )
        if access_key_id:
            return _manual_account_fingerprint(
                provider,
                {"auth_type": "keys", "access_key_id": access_key_id},
            )
        return None

    if provider == "azure":
        subscription_id = _normalize_optional_string(credentials.get("subscription_id"))
        if not subscription_id:
            return None
        return _manual_account_fingerprint(provider, {"subscription_id": subscription_id})

    project_id = _normalize_optional_string(credentials.get("project_id"))
    service_account_email = _normalize_optional_string(credentials.get("service_account_email"))
    if not project_id or not service_account_email:
        return None
    return _manual_account_fingerprint(
        provider,
        {
            "project_id": project_id,
            "service_account_email": service_account_email,
        },
    )


async def _reject_duplicate_manual_integration(
    db: MongoDBClient,
    user_id: str,
    provider: Literal["aws", "azure", "gcp"],
    account_fingerprint: str,
) -> None:
    existing = await db.select(
        "cloud_integrations",
        columns="id,name",
        filters={
            "user_id": user_id,
            "provider": provider,
            "status": "active",
            "metadata.account_fingerprint": account_fingerprint,
        },
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This cloud account is already connected.",
        )

    legacy_integrations = await db.select(
        "cloud_integrations",
        columns="*",
        filters={
            "user_id": user_id,
            "provider": provider,
            "status": "active",
        },
    )
    for integration in legacy_integrations:
        metadata = integration.get("metadata") if isinstance(integration.get("metadata"), dict) else {}
        if metadata.get("account_fingerprint"):
            continue
        if _legacy_account_fingerprint_from_integration(provider, integration) == account_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="This cloud account is already connected.",
            )


def _manual_validation_failure_detail(provider: Literal["aws", "azure", "gcp"]) -> str:
    return MANUAL_VALIDATION_FAILURE_DETAILS[provider]


def _manual_validation_rate_limit_detail(provider: Literal["aws", "azure", "gcp"]) -> str:
    return MANUAL_VALIDATION_RATE_LIMIT_DETAILS[provider]


def _raise_manual_validation_error(
    provider: Literal["aws", "azure", "gcp"],
    error: Exception,
) -> None:
    retryable = (
        is_aws_retryable(error)
        if provider == "aws"
        else is_gcp_retryable(error)
        if provider == "gcp"
        else is_azure_retryable(error) or is_httpx_retryable(error)
    )
    if retryable:
        logger.warning("%s manual integration validation hit retry exhaustion: %s", provider.upper(), error)
        raise HTTPException(
            status_code=503,
            detail=_manual_validation_rate_limit_detail(provider),
        ) from error

    logger.warning("%s manual integration validation failed: %s", provider.upper(), type(error).__name__)
    raise HTTPException(
        status_code=400,
        detail=_manual_validation_failure_detail(provider),
    ) from error


def _validate_aws_keys(access_key_id: str, secret_access_key: str) -> None:
    import boto3

    client = boto3.client(
        "sts",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="us-east-1",
        config=build_aws_retry_config(region_name="us-east-1"),
    )
    call_with_backoff(
        "AWS STS credential validation",
        client.get_caller_identity,
        is_retryable=is_aws_retryable,
    )


def _validate_azure_credentials(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    subscription_id: str,
) -> None:
    from azure.identity import ClientSecretCredential

    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    access_token = call_with_backoff(
        "Azure token request",
        lambda: credential.get_token("https://management.azure.com/.default"),
        is_retryable=is_azure_retryable,
    )

    def fetch_subscription_response() -> httpx.Response:
        response = httpx.get(
            f"https://management.azure.com/subscriptions/{subscription_id}",
            params={"api-version": "2020-01-01"},
            headers={"Authorization": f"Bearer {access_token.token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response

    response = call_with_backoff(
        "Azure subscription access check",
        fetch_subscription_response,
        is_retryable=lambda error: is_azure_retryable(error) or is_httpx_retryable(error),
    )

    payload = response.json() if response.content else {}
    response_subscription_id = str(payload.get("subscriptionId") or "").strip()
    if not response_subscription_id or response_subscription_id.lower() != subscription_id.lower():
        raise ValueError("subscription access check failed")


def _validate_gcp_credentials(
    project_id: str,
    service_account_email: str,
    private_key: str,
) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    normalized_private_key = _normalize_private_key(private_key)
    credentials = service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "project_id": project_id,
            "client_email": service_account_email,
            "private_key": normalized_private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"],
    )
    call_with_backoff(
        "GCP service-account token refresh",
        lambda: credentials.refresh(Request()),
        is_retryable=is_gcp_retryable,
    )
    return normalized_private_key


async def _validate_manual_integration_payload(
    payload: ManualIntegrationCreateRequest,
) -> dict[str, Optional[str]]:
    provider = payload.provider

    if provider == "aws":
        auth_type = payload.auth_type or "keys"
        if auth_type == "role":
            role_arn = _normalize_optional_string(payload.role_arn)
            if not role_arn:
                raise HTTPException(status_code=400, detail="Role ARN is required")
            return {
                "auth_type": "role",
                "role_arn": role_arn,
                "external_id": _normalize_optional_string(payload.external_id),
            }

        access_key_id = _normalize_optional_string(payload.access_key_id)
        secret_access_key = _normalize_optional_string(payload.secret_access_key)
        if not access_key_id or not secret_access_key:
            raise HTTPException(
                status_code=400,
                detail="Access Key ID and Secret Access Key are required",
            )
        try:
            await asyncio.to_thread(_validate_aws_keys, access_key_id, secret_access_key)
        except Exception as error:
            _raise_manual_validation_error("aws", error)

        return {
            "auth_type": "keys",
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        }

    if provider == "azure":
        tenant_id = _normalize_optional_string(payload.tenant_id)
        client_id = _normalize_optional_string(payload.client_id)
        client_secret = _normalize_optional_string(payload.client_secret)
        subscription_id = _normalize_optional_string(payload.subscription_id)
        if not tenant_id or not client_id or not client_secret or not subscription_id:
            raise HTTPException(
                status_code=400,
                detail="Tenant ID, Client ID, Client Secret, and Subscription ID are required",
            )

        try:
            await asyncio.to_thread(
                _validate_azure_credentials,
                tenant_id,
                client_id,
                client_secret,
                subscription_id,
            )
        except Exception as error:
            _raise_manual_validation_error("azure", error)

        return {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "subscription_id": subscription_id,
        }

    project_id = _normalize_optional_string(payload.project_id)
    service_account_email = _normalize_optional_string(payload.service_account_email)
    private_key = _normalize_optional_string(payload.private_key)
    if not project_id or not service_account_email or not private_key:
        raise HTTPException(
            status_code=400,
            detail="Project ID, Service Account Email, and Private Key are required",
        )

    try:
        normalized_private_key = await asyncio.to_thread(
            _validate_gcp_credentials,
            project_id,
            service_account_email,
            private_key,
        )
    except HTTPException:
        raise
    except Exception as error:
        _raise_manual_validation_error("gcp", error)

    return {
        "project_id": project_id,
        "service_account_email": service_account_email,
        "private_key": normalized_private_key,
        "billing_export_table": _normalize_optional_string(payload.billing_export_table),
    }


def _build_created_integration_response(record: dict[str, Any]) -> CreatedIntegrationResponse:
    return CreatedIntegrationResponse(
        id=str(record.get("id") or ""),
        provider=str(record.get("provider") or ""),
        name=str(record.get("name") or ""),
        status=str(record.get("status") or ""),
        last_scan=record.get("last_scan"),
        regions=list(record.get("regions") or []),
        created_at=record.get("created_at"),
    )


@router.post("/integrations", response_model=CreatedIntegrationResponse)
async def create_manual_integration(
    payload: ManualIntegrationCreateRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    normalized_name = payload.name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Account Name is required")

    validated_payload = await _validate_manual_integration_payload(payload)
    provider = payload.provider
    regions = _normalize_regions(provider, payload.regions)
    account_fingerprint = _manual_account_fingerprint(provider, validated_payload)
    await _reject_duplicate_manual_integration(db, user.id, provider, account_fingerprint)

    record: dict[str, Any] = {
        "user_id": user.id,
        "provider": provider,
        "name": normalized_name,
        "status": "active",
        "regions": regions,
        "metadata": {"account_fingerprint": account_fingerprint},
    }

    if provider == "aws":
        if validated_payload.get("auth_type") == "role":
            record["encrypted_role_arn"] = _encrypt_field(str(validated_payload["role_arn"]))
            external_id = validated_payload.get("external_id")
            if external_id:
                record["encrypted_external_id"] = _encrypt_field(str(external_id))
        else:
            record["encrypted_access_key_id"] = _encrypt_field(str(validated_payload["access_key_id"]))
            record["encrypted_secret_access_key"] = _encrypt_field(str(validated_payload["secret_access_key"]))
    elif provider == "azure":
        record["encrypted_tenant_id"] = _encrypt_field(str(validated_payload["tenant_id"]))
        record["encrypted_client_id"] = _encrypt_field(str(validated_payload["client_id"]))
        record["encrypted_client_secret"] = _encrypt_field(str(validated_payload["client_secret"]))
        record["encrypted_subscription_id"] = _encrypt_field(str(validated_payload["subscription_id"]))
    else:
        record["encrypted_project_id"] = _encrypt_field(str(validated_payload["project_id"]))
        record["encrypted_service_account_email"] = _encrypt_field(str(validated_payload["service_account_email"]))
        record["encrypted_private_key"] = _encrypt_field(str(validated_payload["private_key"]))
        billing_export_table = validated_payload.get("billing_export_table")
        if billing_export_table:
            record["metadata"]["gcp_billing_export_table"] = billing_export_table

    try:
        inserted = await db.insert("cloud_integrations", record)
    except Exception as error:
        logger.error("Failed to create integration for %s: %s", user.id, error)
        raise HTTPException(status_code=500, detail="Failed to save integration") from error

    created = inserted[0] if inserted else {}
    await log_audit_event(
        user_id=user.id,
        action_type="INTEGRATION_ADDED",
        resource_target=f"integration:{created.get('id')}",
        metadata={
            "provider": provider,
            "auth_type": validated_payload.get("auth_type", "service_principal"),
            "regions": regions,
        },
    )
    return _build_created_integration_response(created)


@router.post("/integrations/automated-sync", response_model=CreatedIntegrationResponse)
async def create_automated_sync_integration(
    payload: AutomatedSyncIntegrationCreateRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    provider = payload.provider
    storage_path = payload.storage_path.strip()
    credential = payload.credential.strip()
    if not storage_path or not credential:
        raise HTTPException(status_code=400, detail="storage_path and credential are required")

    metadata = {
        "ingestion_type": "automated_bucket",
        "storage_path": storage_path,
        "aws_discount_pct": str(max(0.0, min(100.0, float(payload.aws_discount or 0.0)))),
        "azure_discount_pct": str(max(0.0, min(100.0, float(payload.azure_discount or 0.0)))),
        "gcp_discount_pct": str(max(0.0, min(100.0, float(payload.gcp_discount or 0.0)))),
    }

    record: dict[str, Any] = {
        "user_id": user.id,
        "provider": provider,
        "name": f"{provider.upper()} Automated Billing Sync",
        "status": "active",
        "regions": ["global"],
        "metadata": metadata,
    }

    if provider == "aws":
        parts = credential.split("::", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise HTTPException(
                status_code=400,
                detail="AWS credential must be ACCESS_KEY_ID::SECRET_ACCESS_KEY",
            )
        record["encrypted_access_key_id"] = _encrypt_field(parts[0].strip())
        record["encrypted_secret_access_key"] = _encrypt_field(parts[1].strip())
    else:
        record["encrypted_access_key_id"] = _encrypt_field(credential)
        record["encrypted_secret_access_key"] = None

    try:
        inserted = await db.insert("cloud_integrations", record)
    except Exception as error:
        logger.error("Failed to create automated sync integration for %s: %s", user.id, error)
        raise HTTPException(status_code=500, detail="Failed to save automated billing integration") from error

    created = inserted[0] if inserted else {}
    await log_audit_event(
        user_id=user.id,
        action_type="INTEGRATION_ADDED",
        resource_target=f"integration:{created.get('id')}",
        metadata={
            "provider": provider,
            "ingestion_type": "automated_bucket",
            "storage_path": storage_path,
        },
    )
    return _build_created_integration_response(created)


@router.delete("/integrations/{integration_id}", response_model=DeleteIntegrationResponse)
async def delete_integration(
    integration_id: str,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    integration = await db.get_integration(integration_id, user.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    resources = await db.select(
        "resources",
        columns="id",
        filters={"integration_id": integration_id, "user_id": user.id},
    )
    resource_ids = [str(resource.get("id") or "").strip() for resource in resources if str(resource.get("id") or "").strip()]

    try:
        if resource_ids:
            await db.delete(
                "policy_violations",
                {"user_id": user.id, "resource_id": {"$in": resource_ids}},
            )
            await db.delete(
                "agent_notifications",
                {"user_id": user.id, "resource_id": {"$in": resource_ids}},
            )

        await db.delete(
            "agent_notifications",
            {
                "user_id": user.id,
                "resource_id": None,
                "metadata.integration_id": integration_id,
            },
        )

        for table in (
            "resources",
            "daily_spend_history",
            "dashboard_stats",
            "scan_history",
            "waste_distribution",
            "budget_events",
        ):
            await db.delete(table, {"integration_id": integration_id, "user_id": user.id})

        await db.delete(
            "governance_policies",
            {"user_id": user.id, "metadata.integration_id": integration_id},
        )
        await db.delete("cloud_integrations", {"id": integration_id, "user_id": user.id})
    except Exception as error:
        logger.error("Failed to delete integration %s for %s: %s", integration_id, user.id, error)
        raise HTTPException(status_code=500, detail="Failed to delete integration") from error

    await log_audit_event(
        user_id=user.id,
        action_type="INTEGRATION_DELETED",
        resource_target=f"integration:{integration_id}",
        metadata={
            "provider": integration.get("provider"),
            "name": integration.get("name"),
        },
    )
    return DeleteIntegrationResponse(success=True)
