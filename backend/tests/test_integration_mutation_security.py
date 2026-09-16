import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException

from app.api.integration_mutation_routes import (
    ManualIntegrationCreateRequest,
    _validate_azure_credentials,
    _validate_manual_integration_payload,
)


def _install_fake_azure_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCredential:
        def __init__(self, tenant_id: str, client_id: str, client_secret: str):
            self.tenant_id = tenant_id
            self.client_id = client_id
            self.client_secret = client_secret

        def get_token(self, scope: str) -> SimpleNamespace:
            assert scope == "https://management.azure.com/.default"
            return SimpleNamespace(token="token-123")

    monkeypatch.setattr("azure.identity.ClientSecretCredential", FakeCredential)


def _subscription_response(
    status_code: int, payload: dict[str, str | None] | None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://management.azure.com/subscriptions/sub-123")
    if payload is None:
        return httpx.Response(status_code, content=b"", request=request)
    return httpx.Response(status_code, json=payload, request=request)


@pytest.mark.parametrize("subscription_id", ["sub-123", " SUB-123 "])
def test_validate_azure_credentials_accepts_accessible_subscription(
    monkeypatch: pytest.MonkeyPatch, subscription_id: str,
) -> None:
    _install_fake_azure_identity(monkeypatch)

    def fake_get(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float) -> httpx.Response:
        assert url.endswith("/subscriptions/sub-123")
        assert params == {"api-version": "2020-01-01"}
        assert headers == {"Authorization": "Bearer token-123"}
        assert timeout == 10.0
        return _subscription_response(200, {"subscriptionId": subscription_id})

    monkeypatch.setattr("app.api.integration_mutation_routes.httpx.get", fake_get)

    _validate_azure_credentials("tenant-1", "client-1", "secret-1", "sub-123")


@pytest.mark.parametrize("status_code", [401, 403, 404])
def test_validate_azure_credentials_rejects_inaccessible_subscription(
    monkeypatch: pytest.MonkeyPatch, status_code: int,
) -> None:
    _install_fake_azure_identity(monkeypatch)
    # Even a matching subscription body cannot make an HTTP failure valid.
    response = _subscription_response(status_code, {"subscriptionId": "sub-123"})
    get = Mock(return_value=response)
    monkeypatch.setattr("app.api.integration_mutation_routes.httpx.get", get)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        _validate_azure_credentials("tenant-1", "client-1", "secret-1", "sub-123")

    assert exc_info.value.response is response
    assert exc_info.value.response.status_code == status_code
    assert exc_info.value.request is response.request
    get.assert_called_once()


@pytest.mark.parametrize("payload", [None, {}, {"subscriptionId": None}, {"subscriptionId": " "}, {"subscriptionId": "other-sub"}])
def test_validate_azure_credentials_rejects_missing_or_mismatched_subscription(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, str | None] | None,
) -> None:
    _install_fake_azure_identity(monkeypatch)
    get = Mock(return_value=_subscription_response(200, payload))
    monkeypatch.setattr("app.api.integration_mutation_routes.httpx.get", get)

    with pytest.raises(ValueError, match="subscription access check failed"):
        _validate_azure_credentials("tenant-1", "client-1", "secret-1", "sub-123")

    get.assert_called_once()


@pytest.mark.parametrize("status_code, expected_status, expected_calls", [(401, 400, 1), (403, 400, 1), (404, 400, 1), (429, 503, 4)])
def test_validate_manual_integration_payload_classifies_azure_http_errors(
    monkeypatch: pytest.MonkeyPatch, status_code: int, expected_status: int, expected_calls: int,
) -> None:
    _install_fake_azure_identity(monkeypatch)
    get = Mock(return_value=_subscription_response(status_code, {"error": "victim-subscription-987654321"}))
    sleep = Mock()
    monkeypatch.setattr("app.api.integration_mutation_routes.httpx.get", get)
    monkeypatch.setattr("app.core.retry.time.sleep", sleep)
    payload = ManualIntegrationCreateRequest(
        provider="azure", name="Azure Prod", tenant_id="tenant-1", client_id="client-1",
        client_secret="secret-1", subscription_id="sub-123",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_validate_manual_integration_payload(payload))

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == (
        "Azure validation is temporarily rate limited. Please retry shortly."
        if expected_status == 503
        else "Azure credentials are invalid or do not have access to the supplied subscription."
    )
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    assert "victim-subscription" not in exc_info.value.detail
    assert get.call_count == expected_calls
    assert sleep.call_count == expected_calls - 1


@pytest.mark.asyncio
async def test_validate_manual_integration_payload_redacts_azure_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate(*args, **kwargs):
        raise RuntimeError("victim-subscription-987654321 is forbidden")

    monkeypatch.setattr("app.api.integration_mutation_routes._validate_azure_credentials", fake_validate)

    payload = ManualIntegrationCreateRequest(
        provider="azure",
        name="Azure Prod",
        tenant_id="tenant-1",
        client_id="client-1",
        client_secret="secret-1",
        subscription_id="sub-123",
    )

    with pytest.raises(HTTPException) as exc_info:
        await _validate_manual_integration_payload(payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Azure credentials are invalid or do not have access to the supplied subscription."
    assert "victim-subscription" not in exc_info.value.detail
