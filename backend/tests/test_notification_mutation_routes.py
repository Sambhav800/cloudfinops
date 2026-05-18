from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeNotificationMutationDB:
    def __init__(self, notifications=None):
        self.notifications = notifications or []
        self.select_calls = []
        self.update_calls = []
        self.delete_calls = []

    async def select(self, table, columns="*", filters=None):
        self.select_calls.append((table, columns, filters))
        filters = filters or {}
        if table != "agent_notifications":
            return []

        results = []
        for row in self.notifications:
            if filters.get("id") and row.get("id") != filters.get("id"):
                continue
            if filters.get("user_id") and row.get("user_id") != filters.get("user_id"):
                continue
            results.append(dict(row))
        return results

    async def update(self, table, data, filters):
        self.update_calls.append((table, data, filters))
        for row in self.notifications:
            if row.get("id") == filters.get("id") and row.get("user_id") == filters.get("user_id"):
                row.update(data)

    async def delete(self, table, filters):
        self.delete_calls.append((table, filters))
        self.notifications = [
            row
            for row in self.notifications
            if not (
                row.get("id") == filters.get("id")
                and row.get("user_id") == filters.get("user_id")
            )
        ]


def _build_client(fake_db: FakeNotificationMutationDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_mark_notification_read_updates_only_owned_notification():
    fake_db = FakeNotificationMutationDB(
        notifications=[
            {"id": "notif-1", "user_id": "user-1", "status": "pending"},
            {"id": "notif-2", "user_id": "user-2", "status": "pending"},
        ]
    )
    client = _build_client(fake_db)

    response = client.patch("/api/notifications/notif-1")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Notification marked as read",
    }
    assert fake_db.notifications[0]["status"] == "completed"
    assert fake_db.notifications[1]["status"] == "pending"
    assert fake_db.update_calls == [
        (
            "agent_notifications",
            {"status": "completed"},
            {"id": "notif-1", "user_id": "user-1"},
        )
    ]


def test_delete_notification_removes_owned_notification():
    fake_db = FakeNotificationMutationDB(
        notifications=[
            {"id": "notif-1", "user_id": "user-1", "status": "pending"},
            {"id": "notif-2", "user_id": "user-1", "status": "completed"},
        ]
    )
    client = _build_client(fake_db)

    response = client.delete("/api/notifications/notif-2")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Notification deleted",
    }
    assert fake_db.notifications == [
        {"id": "notif-1", "user_id": "user-1", "status": "pending"}
    ]
    assert fake_db.delete_calls == [
        ("agent_notifications", {"id": "notif-2", "user_id": "user-1"})
    ]


def test_notification_mutations_return_not_found_for_missing_or_unowned_rows():
    fake_db = FakeNotificationMutationDB(
        notifications=[
            {"id": "notif-9", "user_id": "user-2", "status": "pending"},
        ]
    )
    client = _build_client(fake_db)

    patch_response = client.patch("/api/notifications/notif-9")
    delete_response = client.delete("/api/notifications/missing-notif")

    assert patch_response.status_code == 404
    assert patch_response.json() == {"detail": "Notification not found"}
    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "Notification not found"}
    assert fake_db.update_calls == []
    assert fake_db.delete_calls == []
