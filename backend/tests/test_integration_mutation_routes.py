from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.oauth2 import service_account

from app.api.integration_mutation_routes import _validate_gcp_credentials, router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeIntegrationMutationDB:
    def __init__(self):
        self.insert_calls = []
        self.delete_calls = []
        self.select_calls = []
        self.integrations = {
            "int-1": {
                "id": "int-1",
                "user_id": "user-1",
                "provider": "aws",
                "name": "Production AWS",
                "status": "active",
                "regions": ["us-east-1"],
            }
        }
        self.resources = [
            {"id": "res-1", "integration_id": "int-1", "user_id": "user-1"},
            {"id": "res-2", "integration_id": "int-1", "user_id": "user-1"},
        ]

    async def insert(self, table, data):
        self.insert_calls.append((table, data))
        if table == "cloud_integrations":
            record = {
                "id": "int-new",
                "created_at": "2026-04-16T00:00:00Z",
                **data,
            }
            self.integrations[record["id"]] = record
            return [record]
        return [data]

    async def get_integration(self, integration_id, user_id):
        row = self.integrations.get(integration_id)
        if row and row.get("user_id") == user_id:
            return row
        return None

    async def select(self, table, columns="*", filters=None):
        self.select_calls.append((table, columns, filters))
        if table == "resources":
            filters = filters or {}
            return [
                row for row in self.resources
                if row.get("integration_id") == filters.get("integration_id")
                and row.get("user_id") == filters.get("user_id")
            ]
        if table == "cloud_integrations":
            filters = filters or {}
            return [
                row for row in self.integrations.values()
                if row.get("user_id") == filters.get("user_id")
                and row.get("provider") == filters.get("provider")
                and row.get("status") == filters.get("status")
                and (row.get("metadata") or {}).get("account_fingerprint") == filters.get("metadata.account_fingerprint")
            ]
        return []

    async def delete(self, table, filters):
        self.delete_calls.append((table, filters))
        if table == "cloud_integrations":
            integration_id = filters.get("id")
            if integration_id in self.integrations:
                del self.integrations[integration_id]
        return True


def _build_client(fake_db: FakeIntegrationMutationDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_create_manual_integration_persists_encrypted_aws_credentials(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes._validate_aws_keys",
        lambda access_key_id, secret_access_key: None,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes.encrypt",
        lambda value: (f"enc-{value}:tag", "iv-123"),
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations",
        json={
            "provider": "aws",
            "name": "Prod AWS",
            "regions": ["us-east-1", "us-west-2"],
            "auth_type": "keys",
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "SECRET_TEST",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "int-new",
        "provider": "aws",
        "name": "Prod AWS",
        "status": "active",
        "last_scan": None,
        "regions": ["us-east-1", "us-west-2"],
        "created_at": "2026-04-16T00:00:00Z",
    }

    db = client.app.dependency_overrides[get_db_client]()  # type: ignore[misc]
    insert_table, insert_payload = db.insert_calls[0]
    assert insert_table == "cloud_integrations"
    assert insert_payload["user_id"] == "user-1"
    assert insert_payload["provider"] == "aws"
    assert insert_payload["encrypted_access_key_id"] == "enc-AKIA_TEST:tag::iv-123"
    assert insert_payload["encrypted_secret_access_key"] == "enc-SECRET_TEST:tag::iv-123"
    assert str(insert_payload["metadata"]["account_fingerprint"]).startswith("aws:")
    assert "access_key_id" not in insert_payload
    assert "secret_access_key" not in insert_payload


def test_create_manual_integration_rejects_missing_required_fields(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations",
        json={
            "provider": "aws",
            "name": "Prod AWS",
            "auth_type": "keys",
            "access_key_id": "AKIA_TEST",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Access Key ID and Secret Access Key are required"
    }


def test_create_manual_integration_redacts_aws_validation_failures(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    def _raise_validation_error(*args, **kwargs):
        raise RuntimeError("AKIA_TEST arn:aws:iam::123456789012:user/victim is invalid")

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes._validate_aws_keys",
        _raise_validation_error,
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations",
        json={
            "provider": "aws",
            "name": "Prod AWS",
            "auth_type": "keys",
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "SECRET_TEST",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "AWS credentials are invalid or lack the required read-only access."
    }


def test_validate_gcp_credentials_builds_complete_service_account_info(monkeypatch):
    captured = {}

    class FakeCredentials:
        def refresh(self, _request):
            captured["refreshed"] = True

    def fake_from_service_account_info(info, scopes):
        captured["info"] = info
        captured["scopes"] = scopes
        return FakeCredentials()

    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        staticmethod(fake_from_service_account_info),
    )

    normalized_key = _validate_gcp_credentials(
        "resources-test-489719",
        "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----\\n",
    )

    assert normalized_key == "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    assert captured["refreshed"] is True
    assert captured["scopes"] == ["https://www.googleapis.com/auth/cloud-platform.read-only"]
    assert captured["info"] == {
        "type": "service_account",
        "project_id": "resources-test-489719",
        "client_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def test_create_manual_integration_persists_encrypted_gcp_credentials(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes._validate_gcp_credentials",
        lambda project_id, service_account_email, private_key: "NORMALIZED_GCP_PRIVATE_KEY",
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes.encrypt",
        lambda value: (f"enc-{value}:tag", "iv-123"),
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations",
        json={
            "provider": "gcp",
            "name": "Investor Demo GCP",
            "regions": ["us-central1"],
            "project_id": "resources-test-489719",
            "service_account_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
            "private_key": "RAW_PRIVATE_KEY",
            "billing_export_table": "resources-test-489719.billing_export.gcp_billing_export",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gcp"
    assert payload["name"] == "Investor Demo GCP"

    db = client.app.dependency_overrides[get_db_client]()  # type: ignore[misc]
    insert_table, insert_payload = db.insert_calls[0]
    assert insert_table == "cloud_integrations"
    assert insert_payload["provider"] == "gcp"
    assert insert_payload["encrypted_project_id"] == "enc-resources-test-489719:tag::iv-123"
    assert (
        insert_payload["encrypted_service_account_email"]
        == "enc-cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com:tag::iv-123"
    )
    assert insert_payload["encrypted_private_key"] == "enc-NORMALIZED_GCP_PRIVATE_KEY:tag::iv-123"
    assert insert_payload["metadata"]["gcp_billing_export_table"] == "resources-test-489719.billing_export.gcp_billing_export"
    assert str(insert_payload["metadata"]["account_fingerprint"]).startswith("gcp:")
    assert "private_key" not in insert_payload


def test_create_manual_integration_rejects_duplicate_account_fingerprint(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes._validate_gcp_credentials",
        lambda project_id, service_account_email, private_key: "NORMALIZED_GCP_PRIVATE_KEY",
    )

    fake_db = FakeIntegrationMutationDB()
    fake_db.integrations["existing-gcp"] = {
        "id": "existing-gcp",
        "user_id": "user-1",
        "provider": "gcp",
        "name": "Existing GCP",
        "status": "active",
        "metadata": {
            "account_fingerprint": (
                "gcp:7993443e45a24b4e74340c4e80a526ffa2b5a91a704111d76c47bab91452a6de"
            )
        },
    }
    client = _build_client(fake_db)

    response = client.post(
        "/api/integrations",
        json={
            "provider": "gcp",
            "name": "Duplicate GCP",
            "project_id": "resources-test-489719",
            "service_account_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
            "private_key": "RAW_PRIVATE_KEY",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "This cloud account is already connected."}
    assert fake_db.insert_calls == []


def test_create_manual_integration_rejects_legacy_duplicate_without_fingerprint(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes._validate_gcp_credentials",
        lambda project_id, service_account_email, private_key: "NORMALIZED_GCP_PRIVATE_KEY",
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes.decrypt_integration_credentials",
        lambda _integration: {
            "project_id": "resources-test-489719",
            "service_account_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
        },
    )

    fake_db = FakeIntegrationMutationDB()
    fake_db.integrations["legacy-gcp"] = {
        "id": "legacy-gcp",
        "user_id": "user-1",
        "provider": "gcp",
        "name": "Legacy GCP",
        "status": "active",
        "metadata": {},
        "encrypted_project_id": "legacy-encrypted-project",
        "encrypted_service_account_email": "legacy-encrypted-service-account",
    }
    client = _build_client(fake_db)

    response = client.post(
        "/api/integrations",
        json={
            "provider": "gcp",
            "name": "Duplicate Legacy GCP",
            "project_id": "resources-test-489719",
            "service_account_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
            "private_key": "RAW_PRIVATE_KEY",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "This cloud account is already connected."}
    assert fake_db.insert_calls == []


def test_create_manual_integration_rejects_missing_gcp_private_key(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations",
        json={
            "provider": "gcp",
            "name": "Investor Demo GCP",
            "project_id": "resources-test-489719",
            "service_account_email": "cloudfinops-scanner@resources-test-489719.iam.gserviceaccount.com",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Project ID, Service Account Email, and Private Key are required"
    }


def test_create_automated_sync_integration_persists_backend_owned_metadata(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    monkeypatch.setattr(
        "app.api.integration_mutation_routes.encrypt",
        lambda value: (f"enc-{value}:tag", "iv-123"),
    )
    client = _build_client(FakeIntegrationMutationDB())

    response = client.post(
        "/api/integrations/automated-sync",
        json={
            "provider": "aws",
            "storage_path": "billing-bucket",
            "credential": "AKIA_TEST::SECRET_TEST",
            "aws_discount": 12.5,
            "azure_discount": 7.0,
            "gcp_discount": 9.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "int-new"
    db = client.app.dependency_overrides[get_db_client]()  # type: ignore[misc]
    _, insert_payload = db.insert_calls[0]
    assert insert_payload["metadata"] == {
        "ingestion_type": "automated_bucket",
        "storage_path": "billing-bucket",
        "aws_discount_pct": "12.5",
        "azure_discount_pct": "7.0",
        "gcp_discount_pct": "9.0",
    }
    assert insert_payload["encrypted_access_key_id"] == "enc-AKIA_TEST:tag::iv-123"
    assert insert_payload["encrypted_secret_access_key"] == "enc-SECRET_TEST:tag::iv-123"


def test_delete_integration_cleans_owned_records(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    fake_db = FakeIntegrationMutationDB()
    client = _build_client(fake_db)

    response = client.delete("/api/integrations/int-1")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert fake_db.integrations.get("int-1") is None
    assert fake_db.delete_calls == [
        ("policy_violations", {"user_id": "user-1", "resource_id": {"$in": ["res-1", "res-2"]}}),
        ("agent_notifications", {"user_id": "user-1", "resource_id": {"$in": ["res-1", "res-2"]}}),
        ("agent_notifications", {"user_id": "user-1", "resource_id": None, "metadata.integration_id": "int-1"}),
        ("resources", {"integration_id": "int-1", "user_id": "user-1"}),
        ("daily_spend_history", {"integration_id": "int-1", "user_id": "user-1"}),
        ("dashboard_stats", {"integration_id": "int-1", "user_id": "user-1"}),
        ("scan_history", {"integration_id": "int-1", "user_id": "user-1"}),
        ("waste_distribution", {"integration_id": "int-1", "user_id": "user-1"}),
        ("budget_events", {"integration_id": "int-1", "user_id": "user-1"}),
        ("governance_policies", {"user_id": "user-1", "metadata.integration_id": "int-1"}),
        ("cloud_integrations", {"id": "int-1", "user_id": "user-1"}),
    ]


def test_delete_integration_returns_not_found_for_missing_record(monkeypatch):
    async def _noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.integration_mutation_routes.log_audit_event",
        _noop_audit,
    )
    fake_db = FakeIntegrationMutationDB()
    client = _build_client(fake_db)

    response = client.delete("/api/integrations/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Integration not found"}
    assert fake_db.delete_calls == []
