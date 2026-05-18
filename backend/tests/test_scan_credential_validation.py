import asyncio

import pytest

from app.api.routes import run_scan


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
    ],
)
def test_run_scan_aborts_before_scanner_construction_for_invalid_credentials(
    monkeypatch,
    provider,
    credentials,
    expected_fragment,
    action_label,
):
    fake_db = FakeCredentialValidationDB()
    progress_events = []

    async def fake_send_scan_progress(user_id, integration_id, percent, message):
        progress_events.append((user_id, integration_id, percent, message))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("scanner constructor should not be called for invalid credentials")

    monkeypatch.setattr("app.api.routes.decrypt_integration_credentials", lambda integration: credentials)
    monkeypatch.setattr("app.api.routes.send_scan_progress", fake_send_scan_progress)
    monkeypatch.setattr("app.api.routes.AWSScanner", fail_if_called)
    monkeypatch.setattr("app.api.routes.GCPScanner", fail_if_called)

    integration = {
        "id": f"{provider}-integration",
        "provider": provider,
        "name": f"{provider.upper()} Prod",
        "metadata": {"existing": "value"},
        "regions": ["us-east-1"],
    }

    asyncio.run(run_scan(integration, "user-1", fake_db))

    assert fake_db.scan_history_called is False
    assert len(progress_events) == 1

    _, _, percent, message = progress_events[0]
    assert percent == 0
    assert message.startswith("Error: ")
    assert expected_fragment in message

    assert len(fake_db.notifications) == 1
    notification = fake_db.notifications[0]
    assert notification["action"] == action_label
    assert notification["type"] == "permission_alert"
    assert notification["status"] == "pending"
    assert expected_fragment in notification["recommendation"]

    assert len(fake_db.integration_updates) == 1
    updated_integration_id, updated_user_id, update_payload = fake_db.integration_updates[0]
    assert updated_integration_id == f"{provider}-integration"
    assert updated_user_id == "user-1"
    assert update_payload["metadata"]["scan_status"] == "failed"
    assert expected_fragment in update_payload["metadata"]["scan_error"]
