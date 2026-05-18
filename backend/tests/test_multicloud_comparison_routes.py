from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeMulticloudDB:
    def __init__(self):
        self.integrations = [
            {"id": "aws-1", "user_id": "user-1", "provider": "aws", "status": "active"},
            {"id": "gcp-1", "user_id": "user-1", "provider": "gcp", "status": "active"},
            {"id": "azure-old", "user_id": "user-1", "provider": "azure", "status": "inactive"},
        ]
        self.resources = [
            {
                "integration_id": "aws-1",
                "provider": "aws",
                "service_type": "ec2",
                "cost": 100.0,
            },
            {
                "integration_id": "gcp-1",
                "provider": "gcp",
                "service_type": "cloud storage",
                "cost": 80.0,
            },
            {
                "integration_id": "azure-old",
                "provider": "azure",
                "service_type": "virtual machine",
                "cost": 10000.0,
            },
        ]

    async def get_user_integrations(self, user_id):
        return [row for row in self.integrations if row.get("user_id") == user_id]

    async def get_resources(self, user_id, integration_id=None):
        if integration_id:
            return [row for row in self.resources if row.get("integration_id") == integration_id]
        return list(self.resources)

    async def get_integration(self, integration_id, user_id):
        for row in self.integrations:
            if row.get("id") == integration_id and row.get("user_id") == user_id:
                return row
        return None


def _build_client(fake_db: FakeMulticloudDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_multicloud_portfolio_preserves_each_resource_provider():
    client = _build_client(FakeMulticloudDB())

    response = client.get("/api/multicloud/comparison")

    assert response.status_code == 200
    payload = response.json()

    assert payload["source_provider"] == "PORTFOLIO"
    assert payload["total_current_spend"] == 180.0
    assert payload["provider_scores"]
    assert payload["migration_scatter"]
    assert payload["roi_curve"][0]["month"] == 0

    move_pairs = {
        (move["category"], move["from_cloud"], move["to_cloud"])
        for move in payload["recommended_moves"]
    }
    assert ("Compute", "AWS", "GCP") in move_pairs
    assert ("Storage", "GCP", "AZURE") in move_pairs

    assert {move["from_cloud"] for move in payload["recommended_moves"]} == {"AWS", "GCP"}
    assert all(move["workload_size"] < 10000.0 for move in payload["recommended_moves"])

    link_sources = {link["source"] for link in payload["allocation_flow"]["links"]}
    assert link_sources == {"Current AWS", "Current GCP"}


def test_multicloud_integration_view_uses_selected_integration_provider():
    client = _build_client(FakeMulticloudDB())

    response = client.get("/api/multicloud/comparison?integration_id=gcp-1")

    assert response.status_code == 200
    payload = response.json()

    assert payload["source_provider"] == "GCP"
    assert payload["total_current_spend"] == 80.0
    assert payload["recommended_moves"][0]["from_cloud"] == "GCP"
