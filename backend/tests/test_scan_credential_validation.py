import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.routes import run_scan


@pytest.fixture
def scanner_constructors(monkeypatch: pytest.MonkeyPatch) -> dict[str, Mock]:
    constructors = {
        provider: Mock(side_effect=AssertionError("scanner constructor should not be called for invalid credentials"))
        for provider in ("aws", "azure", "gcp")
    }
    monkeypatch.setattr("app.api.routes.AWSScanner", constructors["aws"])
    monkeypatch.setattr("app.scanners.azure.AzureWasteScanner", constructors["azure"])
    monkeypatch.setattr("app.scanners.gcp.GCPScanner", constructors["gcp"])
    return constructors


class FakeCredentialValidationDB:
    def __init__(self):
        self.notifications = []
        self.integration_updates = []
        self.scan_history_called = False

    async def create_notifications(self, notifications):
        self.notifications.extend(notifications)
        return True

    async def update_integration(self, integration_id, user_id, data):
        self.integration_updates.append((integration_id, user_id, data))
        return True

    async def create_scan_history(self, user_id, integration_id):
        self.scan_history_called = True
        raise AssertionError("scan history should not be created for invalid credentials")


@pytest.mark.parametrize(
    ("provider", "credentials", "expected_fragment", "action_label"),
    [
        ("aws", {"access_key_id": "AKIA123"}, "missing secret_access_key", "Reconnect AWS Integration"),
        ("azure", {"tenant_id": "tenant", "client_id": "client"}, "missing client_secret, subscription_id", "Reconnect Azure Integration"),
        ("gcp", {"project_id": "proj"}, "missing service_account_email, private_key", "Reconnect GCP Integration"),
        ("aws", {}, "missing access_key_id, secret_access_key", "Reconnect AWS Integration"),
        ("azure", {}, "missing tenant_id, client_id, client_secret, subscription_id", "Reconnect Azure Integration"),
        ("gcp", {}, "missing project_id, service_account_email, private_key", "Reconnect GCP Integration"),
        ("aws", {"access_key_id": None, "secret_access_key": ""}, "missing access_key_id, secret_access_key", "Reconnect AWS Integration"),
        ("azure", {"tenant_id": "tenant", "client_id": "client", "client_secret": None, "subscription_id": ""}, "missing client_secret, subscription_id", "Reconnect Azure Integration"),
        ("gcp", {"project_id": "proj", "service_account_email": None, "private_key": ""}, "missing service_account_email, private_key", "Reconnect GCP Integration"),
    ],
)
def test_run_scan_aborts_before_scanner_construction_for_invalid_credentials(
    monkeypatch: pytest.MonkeyPatch,
    scanner_constructors: dict[str, Mock],
    provider: str,
    credentials: dict[str, str | None],
    expected_fragment: str,
    action_label: str,
) -> None:
    fake_db = FakeCredentialValidationDB()
    progress_events = []

    async def fake_send_scan_progress(user_id, integration_id, percent, message):
        progress_events.append((user_id, integration_id, percent, message))

    monkeypatch.setattr("app.api.routes.decrypt_integration_credentials", lambda integration: credentials)
    monkeypatch.setattr("app.api.routes.send_scan_progress", fake_send_scan_progress)

    integration = {
        "id": f"{provider}-integration",
        "provider": provider,
        "name": f"{provider.upper()} Prod",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", fake_db))

    for constructor in scanner_constructors.values():
        constructor.assert_not_called()
    assert fake_db.scan_history_called is False
    assert len(progress_events) == 1

    progress_user_id, progress_integration_id, percent, message = progress_events[0]
    assert progress_user_id == "user-1"
    assert progress_integration_id == f"{provider}-integration"
    assert percent == 0
    assert message.startswith("Error: ")
    assert expected_fragment in message

    assert len(fake_db.notifications) == 1
    notification = fake_db.notifications[0]
    assert notification["action"] == action_label
    assert notification["type"] == "permission_alert"
    assert notification["status"] == "pending"
    assert expected_fragment in notification["recommendation"]
    assert notification["user_id"] == "user-1"
    assert notification["metadata"]["integration_id"] == f"{provider}-integration"

    assert len(fake_db.integration_updates) == 1
    updated_integration_id, updated_user_id, update_payload = fake_db.integration_updates[0]
    assert updated_integration_id == f"{provider}-integration"
    assert updated_user_id == "user-1"
    assert update_payload["metadata"]["scan_status"] == "failed"
    assert expected_fragment in update_payload["metadata"]["scan_error"]
    assert update_payload["metadata"]["existing"] == "value"


class ScannerConstructionReached(BaseException):
    """Stop at the credential-validation boundary without entering scan persistence."""


@pytest.mark.parametrize(
    "provider, credentials, expected_kwargs",
    [
        ("aws", {"access_key_id": "key", "secret_access_key": "secret"},
         {"access_key_id": "key", "secret_access_key": "secret", "regions": None, "role_arn": "", "external_id": ""}),
        ("aws", {"role_arn": "arn:aws:iam::123456789012:role/Scan", "external_id": "external"},
         {"access_key_id": "", "secret_access_key": "", "regions": None, "role_arn": "arn:aws:iam::123456789012:role/Scan", "external_id": "external"}),
        ("azure", {"tenant_id": "tenant", "client_id": "client", "client_secret": "secret", "subscription_id": "sub"},
         {"tenant_id": "tenant", "client_id": "client", "client_secret": "secret", "subscription_id": "sub", "exchange_rates": {}}),
        ("gcp", {"project_id": "proj", "service_account_email": "scan@example.com", "private_key": "key"},
         {"project_id": "proj", "service_account_email": "scan@example.com", "private_key": "key", "billing_export_table": None, "billing_lookback_days": None}),
    ],
)
def test_complete_credentials_reach_matching_scanner(
    monkeypatch: pytest.MonkeyPatch,
    scanner_constructors: dict[str, Mock],
    provider: str,
    credentials: dict[str, str],
    expected_kwargs: dict[str, object],
) -> None:
    fake_db = FakeCredentialValidationDB()
    monkeypatch.setattr(fake_db, "create_scan_history", AsyncMock(return_value="scan-1"))
    monkeypatch.setattr("app.core.exchange_rates.get_exchange_rates", AsyncMock(return_value={}))
    monkeypatch.setattr("app.api.routes.decrypt_integration_credentials", lambda integration: credentials)
    progress = AsyncMock()
    monkeypatch.setattr("app.api.routes.send_scan_progress", progress)
    scanner_constructors[provider].side_effect = ScannerConstructionReached

    with pytest.raises(ScannerConstructionReached):
        asyncio.run(run_scan({"id": "integration-1", "provider": provider}, "user-1", fake_db))

    scanner_constructors[provider].assert_called_once_with(**expected_kwargs)
    for other_provider, constructor in scanner_constructors.items():
        if other_provider != provider:
            constructor.assert_not_called()
    progress.assert_not_awaited()
    assert fake_db.notifications == []
    assert fake_db.integration_updates == []
