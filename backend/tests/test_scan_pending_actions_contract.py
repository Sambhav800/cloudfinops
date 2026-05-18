import asyncio

from app.api.routes import (
    _build_scan_recommendation_notification,
    _clear_pending_notifications_for_integration,
    _normalize_scan_recommendation_action_type,
)


class FakePendingNotificationDB:
    def __init__(self):
        self.deleted_filters = []

    async def select(self, table, filters=None):
        assert table == "agent_notifications"
        assert filters == {"user_id": "user-1", "status": "pending"}
        return [
            {
                "id": "notif-a",
                "metadata": {"integration_id": "integration-a"},
            },
            {
                "id": "notif-b",
                "metadata": {"integration_id": "integration-b"},
            },
            {
                "id": "notif-c",
                "metadata": {"integration_id": "integration-a"},
            },
            {
                "id": "notif-d",
                "metadata": {"integration_id": "integration-a"},
                "status": "approved",
            },
            {
                "id": "notif-e",
                "metadata": "bad-shape",
            },
        ]

    async def delete(self, table, filters):
        assert table == "agent_notifications"
        self.deleted_filters.append(filters)
        return True


def test_build_scan_recommendation_notification_persists_ui_fields():
    recommendation = {
        "resource_name": "i-abc123",
        "resource_type": "EC2 Instance",
        "action": "Terminate idle instance",
        "potential_savings": 42.25,
        "severity": "high",
        "ai_reasoning": "The instance has been idle for 14 days.",
        "type": "cost_optimization",
        "ai_status": "zombie",
    }

    notification = _build_scan_recommendation_notification(
        recommendation=recommendation,
        user_id="user-1",
        integration_id="integration-a",
        resource_id="resource-1",
    )

    assert notification["user_id"] == "user-1"
    assert notification["resource_id"] == "resource-1"
    assert notification["type"] == "cost_optimization"
    assert notification["recommendation"] == "Terminate idle instance"
    assert notification["action"] == "terminate"
    assert notification["metadata"]["action_type"] == "terminate"
    assert notification["metadata"]["resource_name"] == "i-abc123"
    assert notification["metadata"]["resource_type"] == "EC2 Instance"
    assert notification["metadata"]["description"] == "The instance has been idle for 14 days."
    assert notification["metadata"]["estimated_savings"] == 42.25


def test_clear_pending_notifications_for_integration_only_removes_matching_pending_rows():
    fake_db = FakePendingNotificationDB()

    deleted_count = asyncio.run(
        _clear_pending_notifications_for_integration(
            db=fake_db,
            user_id="user-1",
            integration_id="integration-a",
        )
    )

    assert deleted_count == 2
    assert fake_db.deleted_filters == [
        {"id": "notif-a"},
        {"id": "notif-c"},
    ]


def test_build_scan_recommendation_notification_defaults_missing_fields():
    notification = _build_scan_recommendation_notification(
        recommendation={},
        user_id="user-1",
        integration_id="integration-a",
        resource_id=None,
    )

    assert notification["recommendation"] == "Review this resource"
    assert notification["action"] == "optimize"
    assert notification["metadata"]["action_type"] == "optimize"
    assert notification["metadata"]["resource_name"] == "Unknown Resource"
    assert notification["metadata"]["resource_type"] == "Cloud Resource"
    assert notification["metadata"]["estimated_savings"] == 0
    assert notification["metadata"]["severity"] == "medium"


def test_build_scan_recommendation_notification_coerces_invalid_savings_without_blanking_fields():
    notification = _build_scan_recommendation_notification(
        recommendation={
            "resource_name": "vm-prod-1",
            "resource_type": "Virtual Machine",
            "action": "Stop off-hours instance",
            "potential_savings": "unknown",
        },
        user_id="user-1",
        integration_id="integration-a",
        resource_id="resource-2",
    )

    assert notification["recommendation"] == "Stop off-hours instance"
    assert notification["action"] == "stop"
    assert notification["metadata"]["action_type"] == "stop"
    assert notification["metadata"]["resource_name"] == "vm-prod-1"
    assert notification["metadata"]["resource_type"] == "Virtual Machine"
    assert notification["metadata"]["estimated_savings"] == 0
    assert notification["metadata"]["potential_savings"] == 0


def test_normalize_scan_recommendation_action_type_recognizes_rightsize_keywords():
    assert _normalize_scan_recommendation_action_type("Resize this node pool") == "rightsize"
    assert _normalize_scan_recommendation_action_type("Buy a Savings Plan") == "purchase_ri"
