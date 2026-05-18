import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.integration_mutation_routes import (
    ManualIntegrationCreateRequest,
    _validate_azure_credentials,
    _validate_manual_integration_payload,
)


def _install_fake_azure_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    identity_module = ModuleType("azure.identity")

    class FakeCredential:
        def __init__(self, tenant_id: str, client_id: str, client_secret: str):
            self.tenant_id = tenant_id
            self.client_id = client_id
            self.client_secret = client_secret

        def get_token(self, scope: str):
            assert scope == "https://management.azure.com/.default"
            return SimpleNamespace(token="token-123")

    identity_module.ClientSecretCredential = FakeCredential

    azure_module = ModuleType("azure")
    azure_module.identity = identity_module

    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.identity", identity_module)


class FakeHTTPXResponse:
    def __init__(self, status_code: int, payload: dict[str, str] | None):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = b"{}" if payload is not None else b""

    def json(self) -> dict[str, str]:
        return self._payload


def test_validate_azure_credentials_accepts_accessible_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_azure_identity(monkeypatch)

    def fake_get(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float):
        assert url.endswith("/subscriptions/sub-123")
        assert params == {"api-version": "2020-01-01"}
        assert headers == {"Authorization": "Bearer token-123"}
        assert timeout == 10.0
        return FakeHTTPXResponse(200, {"subscriptionId": "sub-123"})

    monkeypatch.setattr("app.api.integration_mutation_routes.httpx.get", fake_get)

    _validate_azure_credentials("tenant-1", "client-1", "secret-1", "sub-123")


def test_validate_azure_credentials_rejects_inaccessible_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_azure_identity(monkeypatch)
    monkeypatch.setattr(
        "app.api.integration_mutation_routes.httpx.get",
        lambda *args, **kwargs: FakeHTTPXResponse(403, {"error": "Forbidden"}),
    )

    with pytest.raises(ValueError, match="subscription access check failed"):
        _validate_azure_credentials("tenant-1", "client-1", "secret-1", "sub-123")


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
