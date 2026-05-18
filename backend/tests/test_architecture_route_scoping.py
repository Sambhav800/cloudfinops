from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.architecture_routes import router as architecture_router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeArchitectureDB:
    def __init__(self, resources: list[dict] | None = None):
        self.resource_calls: list[tuple[str, str | None]] = []
        self.resources = resources or []

    async def get_integration(self, integration_id: str, user_id: str):
        if integration_id == "int-1" and user_id == "user-1":
            return {
                "id": "int-1",
                "user_id": "user-1",
                "provider": "aws",
                "last_scan": "2026-04-24T00:00:00Z",
                "regions": ["us-east-1"],
            }
        return None

    async def get_resources(self, user_id: str, integration_id: str | None = None):
        raise AssertionError("architecture routes should use the integration-scoped helper")

    async def get_resources_for_integration(self, user_id: str, integration_id: str):
        self.resource_calls.append((user_id, integration_id))
        return list(self.resources)

    async def select(self, table: str, columns: str = "*", filters: dict | None = None):
        return []


def _build_client(fake_db: FakeArchitectureDB) -> TestClient:
    app = FastAPI()
    app.include_router(architecture_router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_get_aws_current_architecture_uses_user_scoped_resource_lookup() -> None:
    fake_db = FakeArchitectureDB(resources=[])
    client = _build_client(fake_db)

    response = client.get("/api/architecture/aws/current", params={"integration_id": "int-1"})

    assert response.status_code == 200
    assert response.json()["regions"] == []
    assert fake_db.resource_calls == [("user-1", "int-1")]


def test_get_architecture_graph_uses_user_scoped_resource_lookup() -> None:
    fake_db = FakeArchitectureDB(resources=[])
    client = _build_client(fake_db)

    response = client.get("/api/architecture/aws/graph", params={"integration_id": "int-1"})

    assert response.status_code == 200
    assert response.json()["regions"] == []
    assert fake_db.resource_calls == [("user-1", "int-1")]


def test_generate_provider_proposed_architecture_returns_404_for_empty_owned_inventory() -> None:
    fake_db = FakeArchitectureDB(resources=[])
    client = _build_client(fake_db)

    response = client.post(
        "/api/architecture/aws/proposed",
        params={"integration_id": "int-1", "region": "us-east-1"},
        json={},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No resources found. Run a scan first."}
    assert fake_db.resource_calls == [("user-1", "int-1")]
