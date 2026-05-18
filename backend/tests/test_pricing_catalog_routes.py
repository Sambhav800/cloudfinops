from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.pricing_catalog_routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakePricingCatalogDB:
    def __init__(self, integration=None):
        self.integration = integration
        self.integration_calls = []

    async def select(self, table, columns="*", filters=None):
        filters = filters or {}
        if table != "cloud_integrations":
            return []
        integration_id = filters.get("id")
        user_id = filters.get("user_id")
        self.integration_calls.append((integration_id, user_id))
        return [self.integration] if self.integration else []


def _build_client(fake_db: FakePricingCatalogDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_sync_pricing_catalog_returns_protected_sync_summary(monkeypatch):
    apply_calls = []

    async def fake_sync(db, provider, *, service_code=None, region=None, limit=1000, credentials=None):
        assert provider == "azure"
        assert service_code == "Virtual Machines"
        assert region == "eastus"
        assert limit == 25
        assert credentials is None
        return {
            "provider": "azure",
            "source": "provider_catalog",
            "service_code": "Virtual Machines",
            "region": "eastus",
            "sync_batch_id": "batch-1",
            "records_seen": 25,
            "records_saved": 25,
            "status": "completed",
            "synced_at": "2026-04-26T00:00:00+00:00",
        }

    async def fake_apply(db, user_id, *, integration_id=None, limit=500):
        apply_calls.append((user_id, integration_id, limit))
        return {"updated": 2, "skipped_actual": 0, "unmatched": 1, "processed": 3, "samples": []}

    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.sync_provider_catalog", fake_sync)
    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.apply_catalog_estimates", fake_apply)
    client = _build_client(FakePricingCatalogDB())

    response = client.post(
        "/api/pricing-catalog/sync",
        json={
            "provider": "azure",
            "service_code": "Virtual Machines",
            "region": "eastus",
            "limit": 25,
        },
    )

    assert response.status_code == 200
    assert response.json()["records_saved"] == 25
    assert response.json()["applied_estimates"]["updated"] == 2
    assert apply_calls == [("user-1", None, 500)]


def test_sync_pricing_catalog_verifies_integration_owner_and_passes_credentials(monkeypatch):
    apply_calls = []

    async def fake_sync(db, provider, *, service_code=None, region=None, limit=1000, credentials=None):
        assert provider == "gcp"
        assert service_code == "6F81-5844-456A"
        assert credentials == {"project_id": "project-1"}
        return {
            "provider": "gcp",
            "source": "provider_catalog",
            "service_code": "6F81-5844-456A",
            "region": "us-central1",
            "sync_batch_id": "batch-1",
            "records_seen": 5,
            "records_saved": 5,
            "status": "completed",
            "synced_at": "2026-04-26T00:00:00+00:00",
        }

    async def fake_apply(db, user_id, *, integration_id=None, limit=500):
        apply_calls.append((user_id, integration_id, limit))
        return {"updated": 1, "skipped_actual": 0, "unmatched": 0, "processed": 1, "samples": []}

    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.sync_provider_catalog", fake_sync)
    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.apply_catalog_estimates", fake_apply)
    monkeypatch.setattr(
        "app.api.pricing_catalog_routes.decrypt_integration_credentials",
        lambda integration: {"project_id": "project-1"},
    )
    fake_db = FakePricingCatalogDB(integration={"id": "int-1", "user_id": "user-1", "provider": "gcp"})
    client = _build_client(fake_db)

    response = client.post(
        "/api/pricing-catalog/sync",
        json={
            "provider": "gcp",
            "integration_id": "int-1",
            "service_code": "6F81-5844-456A",
            "region": "us-central1",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["records_saved"] == 5
    assert response.json()["applied_estimates"]["updated"] == 1
    assert fake_db.integration_calls == [("int-1", "user-1")]
    assert apply_calls == [("user-1", "int-1", 500)]


def test_apply_catalog_estimates_verifies_integration_owner(monkeypatch):
    async def fake_apply(db, user_id, *, integration_id=None, limit=500):
        assert user_id == "user-1"
        assert integration_id == "int-1"
        return {
            "updated": 1,
            "skipped_actual": 0,
            "unmatched": 0,
            "processed": 1,
            "samples": [
                {
                    "resource_id": "res-1",
                    "resource_name": "vm",
                    "monthly_cost": 14.6,
                    "catalog_key": "aws:ec2:t3micro",
                }
            ],
        }

    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.apply_catalog_estimates", fake_apply)
    fake_db = FakePricingCatalogDB(integration={"id": "int-1", "user_id": "user-1"})
    client = _build_client(fake_db)

    response = client.post(
        "/api/pricing-catalog/apply-estimates",
        json={"integration_id": "int-1", "limit": 50},
    )

    assert response.status_code == 200
    assert response.json()["updated"] == 1
    assert fake_db.integration_calls == [("int-1", "user-1")]


def test_apply_catalog_estimates_rejects_unowned_integration(monkeypatch):
    async def fake_apply(*args, **kwargs):
        raise AssertionError("apply must not run for an unowned integration")

    monkeypatch.setattr("app.api.pricing_catalog_routes.pricing_catalog.apply_catalog_estimates", fake_apply)
    client = _build_client(FakePricingCatalogDB(integration=None))

    response = client.post(
        "/api/pricing-catalog/apply-estimates",
        json={"integration_id": "int-other"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Integration not found"
