from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dashboard_read_routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeDashboardReadDB:
    def __init__(
        self,
        rows=None,
        integrations=None,
        scan_history_rows=None,
        governance_policy_rows=None,
        policy_violation_rows=None,
        notification_rows=None,
        resource_rows=None,
    ):
        self.rows = rows or []
        self.integrations = integrations or []
        self.scan_history_rows = scan_history_rows or []
        self.governance_policy_rows = governance_policy_rows or []
        self.policy_violation_rows = policy_violation_rows or []
        self.notification_rows = notification_rows or []
        self.resource_rows = resource_rows or []
        self.select_calls = []
        self.integration_calls = []

    async def select(self, table, columns="*", filters=None):
        self.select_calls.append((table, columns, filters))
        filters = filters or {}

        if table == "waste_distribution":
            results = []
            for row in self.rows:
                if row.get("user_id") != filters.get("user_id"):
                    continue
                if filters.get("integration_id") and row.get("integration_id") != filters.get("integration_id"):
                    continue
                results.append(row)
            return results

        if table == "scan_history":
            results = []
            for row in self.scan_history_rows:
                if row.get("user_id") != filters.get("user_id"):
                    continue
                if filters.get("status") and row.get("status") != filters.get("status"):
                    continue
                results.append(row)
            return results

        if table == "governance_policies":
            return [
                row
                for row in self.governance_policy_rows
                if row.get("user_id") == filters.get("user_id")
            ]

        if table == "policy_violations":
            return [
                row
                for row in self.policy_violation_rows
                if row.get("user_id") == filters.get("user_id")
            ]

        if table == "agent_notifications":
            return [
                row
                for row in self.notification_rows
                if row.get("user_id") == filters.get("user_id")
            ]

        return []

    async def get_user_integrations(self, user_id):
        self.integration_calls.append(user_id)
        return [
            integration
            for integration in self.integrations
            if integration.get("user_id") == user_id
        ]

    async def get_resources(self, user_id, integration_id=None):
        rows = [
            resource
            for resource in self.resource_rows
            if resource.get("user_id") == user_id
        ]
        if integration_id:
            rows = [
                resource
                for resource in rows
                if resource.get("integration_id") == integration_id
            ]
        return rows


def _build_client(fake_db: FakeDashboardReadDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


def test_get_waste_distribution_returns_user_scoped_rows():
    client = _build_client(
        FakeDashboardReadDB(
            integrations=[
                {"id": "int-1", "user_id": "user-1", "provider": "aws", "status": "active"},
                {"id": "int-2", "user_id": "user-1", "provider": "gcp", "status": "active"},
            ],
            rows=[
                {"user_id": "user-1", "integration_id": "int-1", "category_name": "Idle Resources", "value": 125.5},
                {"user_id": "user-1", "integration_id": "int-2", "category_name": "Orphaned Storage", "value": "80"},
                {"user_id": "user-2", "integration_id": "int-9", "category_name": "Zombie Resources", "value": 999},
            ]
        )
    )

    response = client.get("/api/waste-distribution")

    assert response.status_code == 200
    assert response.json() == {
        "waste_distribution": [
            {"category_name": "Idle Resources", "value": 125.5},
            {"category_name": "Orphaned Storage", "value": 80.0},
        ],
        "count": 2,
    }


def test_get_waste_distribution_filters_by_integration():
    fake_db = FakeDashboardReadDB(
        rows=[
            {"user_id": "user-1", "integration_id": "int-1", "category_name": "Idle Resources", "value": 125.5},
            {"user_id": "user-1", "integration_id": "int-2", "category_name": "Orphaned Storage", "value": 80},
        ]
    )
    client = _build_client(fake_db)

    response = client.get("/api/waste-distribution?integration_id=int-2")

    assert response.status_code == 200
    assert response.json() == {
        "waste_distribution": [
            {"category_name": "Orphaned Storage", "value": 80.0},
        ],
        "count": 1,
    }
    assert fake_db.select_calls == [
        ("waste_distribution", "*", {"user_id": "user-1", "integration_id": "int-2"})
    ]


def test_get_waste_distribution_ignores_inactive_integration_rows():
    client = _build_client(
        FakeDashboardReadDB(
            integrations=[
                {"id": "int-1", "user_id": "user-1", "provider": "aws", "status": "active"},
                {"id": "int-old", "user_id": "user-1", "provider": "gcp", "status": "inactive"},
            ],
            rows=[
                {"user_id": "user-1", "integration_id": "int-1", "category_name": "Idle Resources", "value": 20},
                {"user_id": "user-1", "integration_id": "int-old", "category_name": "Duplicate GCP", "value": 999},
            ],
        )
    )

    response = client.get("/api/waste-distribution")

    assert response.status_code == 200
    assert response.json() == {
        "waste_distribution": [
            {"category_name": "Idle Resources", "value": 20.0},
        ],
        "count": 1,
    }


def test_get_waste_distribution_returns_empty_state():
    client = _build_client(FakeDashboardReadDB())

    response = client.get("/api/waste-distribution")

    assert response.status_code == 200
    assert response.json() == {
        "waste_distribution": [],
        "count": 0,
    }


def test_get_governance_analysis_returns_latest_user_scoped_payload_with_trends():
    fake_db = FakeDashboardReadDB(
        integrations=[
            {"id": "int-1", "user_id": "user-1", "provider": "aws"},
        ],
        governance_policy_rows=[
            {
                "id": "policy-tag",
                "user_id": "user-1",
                "policy_type": "tagging",
                "metadata": {"framework": "FinOps"},
            },
            {
                "id": "policy-rdp",
                "user_id": "user-1",
                "policy_type": "network",
                "metadata": {"framework": "CIS"},
            },
        ],
        policy_violation_rows=[
            {
                "id": "vio-1",
                "policy_id": "policy-rdp",
                "resource_id": "res-nsg",
                "user_id": "user-1",
                "violation_details": {"detail": "Inbound RDP is open to the public internet."},
                "severity": "critical",
                "status": "active",
                "created_at": "2026-04-12T09:00:00Z",
            },
            {
                "id": "vio-2",
                "policy_id": "policy-tag",
                "resource_id": "res-etl",
                "user_id": "user-1",
                "violation_details": {"detail": "CostCenter tag is missing."},
                "severity": "medium",
                "status": "active",
                "created_at": "2026-04-11T09:00:00Z",
            },
        ],
        notification_rows=[
            {
                "id": "note-1",
                "user_id": "user-1",
                "recommendation": "Review inbound RDP access.",
                "status": "pending",
                "type": "security_alert",
                "resource_id": "res-nsg",
                "created_at": "2026-04-12T12:00:00Z",
                "metadata": {"severity": "critical", "description": "Public RDP exposure detected."},
            },
        ],
        resource_rows=[
            {
                "id": "res-nsg",
                "user_id": "user-1",
                "integration_id": "int-1",
                "resource_name": "prod-rdp-nsg",
                "resource_type": "network_security_group",
                "provider": "azure",
                "region": "eastus",
                "status": "non_compliant",
            },
            {
                "id": "res-etl",
                "user_id": "user-1",
                "integration_id": "int-1",
                "resource_name": "etl-runner",
                "resource_type": "vm",
                "provider": "aws",
                "region": "us-east-1",
                "status": "active",
            },
        ],
        scan_history_rows=[
            {
                "user_id": "user-1",
                "status": "completed",
                "created_at": "2026-04-10T10:00:00Z",
                "governance_data": {
                    "score": {"value": 62, "trend": "up", "rating": "Fair"},
                    "tagging": {"missingTags": 3, "costImpact": 140.5, "assets": [{"id": "r1", "name": "api-node", "missing": ["Owner"]}]},
                    "budget": {"projectedSpend": 42000, "budgetLimit": 50000, "burnRate": 84, "status": "Warning", "alert": "Forecast nearing budget"},
                    "officeHours": {"savings": 380, "enabled": True, "recommendation": "Power down dev nodes overnight"},
                    "policies": [
                        {"id": "pol-1", "name": "Tagging", "status": "Fail", "severity": "High", "reason": "Owner missing", "framework": "FinOps"},
                        {"id": "pol-2", "name": "Encryption", "status": "Pass", "severity": "Low", "reason": "Compliant", "framework": "CIS"},
                    ],
                },
            },
            {
                "user_id": "user-1",
                "status": "completed",
                "created_at": "2026-04-12T10:00:00Z",
                "governance_data": {
                    "score": {"value": 78, "trend": "up", "rating": "Fair"},
                    "tagging": {"missingTags": 1, "costImpact": 55, "assets": [{"id": "r2", "name": "etl-runner", "missing": ["CostCenter"]}]},
                    "budget": {"projectedSpend": 56000, "budgetLimit": 60000, "burnRate": 93, "status": "Warning", "alert": "Projected spend is approaching the portfolio budget"},
                    "officeHours": {"savings": 620, "enabled": True, "recommendation": "Apply office hours to test workloads"},
                    "policies": [
                        {"id": "pol-3", "name": "Tagging", "status": "Fail", "severity": "Medium", "reason": "CostCenter missing", "framework": "FinOps"},
                        {"id": "pol-4", "name": "Region", "status": "Pass", "severity": "Low", "reason": "Approved region", "framework": "FinOps"},
                    ],
                },
            },
            {
                "user_id": "user-2",
                "status": "completed",
                "created_at": "2026-04-13T10:00:00Z",
                "governance_data": {
                    "score": {"value": 99},
                },
            },
        ],
    )
    client = _build_client(fake_db)

    response = client.get("/api/governance/analysis")

    assert response.status_code == 200
    assert response.json() == {
        "score": {"value": 78, "trend": "up", "rating": "Fair"},
        "tagging": {
            "missingTags": 1,
            "costImpact": 55.0,
            "assets": [
                {"id": "r2", "name": "etl-runner", "missing": ["CostCenter"]},
            ],
        },
        "budget": {
            "projectedSpend": 56000.0,
            "budgetLimit": 60000.0,
            "burnRate": 93,
            "status": "Warning",
            "alert": "Projected spend is approaching the portfolio budget",
        },
        "officeHours": {
            "savings": 620.0,
            "enabled": True,
            "recommendation": "Apply office hours to test workloads",
        },
        "policies": [
            {
                "id": "pol-3",
                "name": "Tagging",
                "status": "Fail",
                "severity": "Medium",
                "reason": "CostCenter missing",
                "framework": "FinOps",
            },
            {
                "id": "pol-4",
                "name": "Region",
                "status": "Pass",
                "severity": "Low",
                "reason": "Approved region",
                "framework": "FinOps",
            },
        ],
        "trends": [
            {"date": "Apr 10", "score": 62},
            {"date": "Apr 12", "score": 78},
        ],
        "frameworkSummary": [
            {"framework": "FinOps", "pass": 1, "fail": 1, "total": 2},
        ],
        "agentNotifications": [
            {
                "id": "note-1",
                "recommendation": "Review inbound RDP access.",
                "status": "pending",
                "type": "security_alert",
                "resource_id": "res-nsg",
                "created_at": "2026-04-12T12:00:00Z",
                "metadata": {"severity": "critical", "description": "Public RDP exposure detected."},
            },
        ],
        "resources": [
            {
                "id": "res-nsg",
                "resource_id": "res-nsg",
                "resource_name": "prod-rdp-nsg",
                "resource_type": "network_security_group",
                "provider": "azure",
                "region": "eastus",
                "status": "non_compliant",
            },
            {
                "id": "res-etl",
                "resource_id": "res-etl",
                "resource_name": "etl-runner",
                "resource_type": "vm",
                "provider": "aws",
                "region": "us-east-1",
                "status": "active",
            },
        ],
        "policyViolations": [
            {
                "id": "vio-1",
                "policy_id": "policy-rdp",
                "resource_id": "res-nsg",
                "resource": "prod-rdp-nsg",
                "provider": "azure",
                "category": "network",
                "rule_category": "network",
                "severity": "critical",
                "status": "active",
                "description": "Inbound RDP is open to the public internet.",
                "message": "Inbound RDP is open to the public internet.",
                "detected_at": "2026-04-12T09:00:00Z",
                "created_at": "2026-04-12T09:00:00Z",
            },
            {
                "id": "vio-2",
                "policy_id": "policy-tag",
                "resource_id": "res-etl",
                "resource": "etl-runner",
                "provider": "aws",
                "category": "tagging",
                "rule_category": "tagging",
                "severity": "medium",
                "status": "active",
                "description": "CostCenter tag is missing.",
                "message": "CostCenter tag is missing.",
                "detected_at": "2026-04-11T09:00:00Z",
                "created_at": "2026-04-11T09:00:00Z",
            },
        ],
    }
    assert fake_db.integration_calls == ["user-1"]
    assert fake_db.select_calls[0] == (
        "scan_history",
        "*",
        {"user_id": "user-1", "status": "completed"},
    )


def test_get_governance_analysis_returns_zero_state_without_integrations():
    client = _build_client(FakeDashboardReadDB())

    response = client.get("/api/governance/analysis")

    assert response.status_code == 200
    assert response.json() == {
        "score": {"value": 0, "trend": "stable", "rating": "Fair"},
        "tagging": {"missingTags": 0, "costImpact": 0.0, "assets": []},
        "budget": {
            "projectedSpend": 0.0,
            "budgetLimit": 0.0,
            "burnRate": 0,
            "status": "Safe",
            "alert": "No data yet.",
        },
        "officeHours": {
            "savings": 0.0,
            "enabled": False,
            "recommendation": "Run a scan to generate insights.",
        },
        "policies": [],
        "trends": [],
        "frameworkSummary": [],
        "agentNotifications": [],
        "resources": [],
        "policyViolations": [],
    }


def test_get_governance_analysis_returns_zero_state_without_governance_payloads():
    client = _build_client(
        FakeDashboardReadDB(
            integrations=[
                {"id": "int-1", "user_id": "user-1", "provider": "aws"},
            ],
            scan_history_rows=[
                {
                    "user_id": "user-1",
                    "status": "completed",
                    "created_at": "2026-04-12T10:00:00Z",
                    "governance_data": None,
                },
            ],
        )
    )

    response = client.get("/api/governance/analysis")

    assert response.status_code == 200
    assert response.json()["score"] == {
        "value": 0,
        "trend": "stable",
        "rating": "Fair",
    }
    assert response.json()["policies"] == []
    assert response.json()["trends"] == []
    assert response.json()["policyViolations"] == []
    assert response.json()["agentNotifications"] == []
    assert response.json()["resources"] == []


def test_get_security_posture_returns_security_only_user_scoped_metrics():
    fake_db = FakeDashboardReadDB(
        integrations=[
            {"id": "int-1", "user_id": "user-1", "provider": "aws"},
        ],
        governance_policy_rows=[
            {
                "id": "policy-security",
                "user_id": "user-1",
                "name": "Network Security Policy",
                "policy_type": "security",
            },
            {
                "id": "policy-tag",
                "user_id": "user-1",
                "name": "Tagging Policy",
                "policy_type": "tagging",
            },
            {
                "id": "policy-other-user",
                "user_id": "user-2",
                "name": "Other tenant security",
                "policy_type": "security",
            },
        ],
        policy_violation_rows=[
            {
                "id": "vio-security",
                "policy_id": "policy-security",
                "resource_id": "res-nsg",
                "user_id": "user-1",
                "violation_details": {"detail": "Inbound RDP is open to the public internet."},
                "severity": "critical",
                "status": "active",
                "created_at": "2026-04-12T09:00:00Z",
            },
            {
                "id": "vio-tag",
                "policy_id": "policy-tag",
                "resource_id": "res-etl",
                "user_id": "user-1",
                "violation_details": {"detail": "CostCenter tag is missing."},
                "severity": "medium",
                "status": "active",
                "created_at": "2026-04-11T09:00:00Z",
            },
            {
                "id": "vio-other-user",
                "policy_id": "policy-other-user",
                "resource_id": "res-other",
                "user_id": "user-2",
                "violation_details": {"detail": "Should be filtered out."},
                "severity": "critical",
                "status": "active",
                "created_at": "2026-04-13T09:00:00Z",
            },
        ],
        notification_rows=[
            {
                "id": "note-permission",
                "user_id": "user-1",
                "recommendation": "Review overly broad IAM permissions.",
                "status": "pending",
                "type": "permission_alert",
                "resource_id": "res-iam",
                "created_at": "2026-04-13T12:00:00Z",
                "metadata": {
                    "severity": "high",
                    "description": "IAM role allows wildcard administrative access.",
                    "resource_name": "ops-admin-role",
                    "provider": "aws",
                    "category": "iam",
                },
            },
            {
                "id": "note-cost",
                "user_id": "user-1",
                "recommendation": "Rightsize compute.",
                "status": "pending",
                "type": "cost_alert",
                "resource_id": "res-etl",
                "created_at": "2026-04-13T11:00:00Z",
                "metadata": {"severity": "high", "category": "cost"},
            },
        ],
        resource_rows=[
            {
                "id": "row-nsg",
                "cloud_resource_id": "res-nsg",
                "user_id": "user-1",
                "integration_id": "int-1",
                "resource_name": "prod-rdp-nsg",
                "resource_type": "network_security_group",
                "provider": "azure",
                "region": "eastus",
                "status": "non_compliant",
                "metrics_data": {"risky_rules": [{"port": 3389}]},
            },
            {
                "id": "res-iam",
                "user_id": "user-1",
                "integration_id": "int-1",
                "resource_name": "ops-admin-role",
                "resource_type": "iam_role",
                "provider": "aws",
                "region": "global",
                "status": "active",
            },
            {
                "id": "res-etl",
                "user_id": "user-1",
                "integration_id": "int-1",
                "resource_name": "etl-runner",
                "resource_type": "vm",
                "provider": "aws",
                "region": "us-east-1",
                "status": "active",
            },
        ],
    )
    client = _build_client(fake_db)

    response = client.get("/api/security/posture")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "score": 60,
            "rating": "Weak",
            "critical": 1,
            "high": 1,
            "open": 2,
            "exposed_resources": 2,
            "monitored_resources": 3,
            "last_detected_at": "2026-04-13T12:00:00Z",
        },
        "findingsBySeverity": [
            {"name": "critical", "count": 1},
            {"name": "high", "count": 1},
        ],
        "findingsByCategory": [
            {"name": "security", "count": 1},
            {"name": "iam", "count": 1},
        ],
        "activeFindings": [
            {
                "id": "vio-security",
                "resource_id": "res-nsg",
                "resource": "prod-rdp-nsg",
                "provider": "azure",
                "region": "eastus",
                "category": "security",
                "severity": "critical",
                "status": "active",
                "description": "Inbound RDP is open to the public internet.",
                "detected_at": "2026-04-12T09:00:00Z",
                "source": "policy_violation",
                "remediation": "Review the affected resource and restrict the exposed security control.",
            },
            {
                "id": "note-permission",
                "resource_id": "res-iam",
                "resource": "ops-admin-role",
                "provider": "aws",
                "region": "global",
                "category": "iam",
                "severity": "high",
                "status": "pending",
                "description": "IAM role allows wildcard administrative access.",
                "detected_at": "2026-04-13T12:00:00Z",
                "source": "agent_notification",
                "remediation": "Review overly broad IAM permissions.",
            },
        ],
        "exposedResources": [
            {
                "id": "row-nsg",
                "resource_id": "res-nsg",
                "resource_name": "prod-rdp-nsg",
                "resource_type": "network_security_group",
                "provider": "azure",
                "region": "eastus",
                "highest_severity": "critical",
                "risk_count": 1,
                "exposure": "1 risky inbound rule",
                "status": "non_compliant",
            },
            {
                "id": "res-iam",
                "resource_id": "res-iam",
                "resource_name": "ops-admin-role",
                "resource_type": "iam_role",
                "provider": "aws",
                "region": "global",
                "highest_severity": "high",
                "risk_count": 1,
                "exposure": "Security risk detected",
                "status": "active",
            },
        ],
        "recentAlerts": [
            {
                "id": "note-permission",
                "resource_id": "res-iam",
                "resource": "ops-admin-role",
                "provider": "aws",
                "region": "global",
                "category": "iam",
                "severity": "high",
                "status": "pending",
                "description": "IAM role allows wildcard administrative access.",
                "detected_at": "2026-04-13T12:00:00Z",
                "source": "agent_notification",
                "remediation": "Review overly broad IAM permissions.",
            },
            {
                "id": "vio-security",
                "resource_id": "res-nsg",
                "resource": "prod-rdp-nsg",
                "provider": "azure",
                "region": "eastus",
                "category": "security",
                "severity": "critical",
                "status": "active",
                "description": "Inbound RDP is open to the public internet.",
                "detected_at": "2026-04-12T09:00:00Z",
                "source": "policy_violation",
                "remediation": "Review the affected resource and restrict the exposed security control.",
            },
        ],
    }
    assert ("governance_policies", "*", {"user_id": "user-1"}) in fake_db.select_calls
    assert ("policy_violations", "*", {"user_id": "user-1"}) in fake_db.select_calls
    assert ("agent_notifications", "*", {"user_id": "user-1"}) in fake_db.select_calls


def test_get_security_posture_returns_zero_state_without_integrations():
    client = _build_client(FakeDashboardReadDB())

    response = client.get("/api/security/posture")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "score": 0,
            "rating": "No data",
            "critical": 0,
            "high": 0,
            "open": 0,
            "exposed_resources": 0,
            "monitored_resources": 0,
            "last_detected_at": None,
        },
        "findingsBySeverity": [],
        "findingsByCategory": [],
        "activeFindings": [],
        "exposedResources": [],
        "recentAlerts": [],
    }


def test_get_governance_policies_returns_user_scoped_rows_sorted_and_normalized():
    fake_db = FakeDashboardReadDB(
        governance_policy_rows=[
            {
                "id": "pol-1",
                "user_id": "user-1",
                "name": "Owner Tag Required",
                "description": None,
                "policy_type": "tagging",
                "is_active": True,
                "compliance_rate": "91.5",
                "violations": "4",
                "created_at": "2026-04-11T10:00:00Z",
                "metadata": {"description": "Every workload must have an Owner tag."},
            },
            {
                "id": "pol-2",
                "user_id": "user-1",
                "name": "Encryption at Rest",
                "description": "Storage must be encrypted at rest.",
                "policy_type": "security",
                "is_active": False,
                "compliance_rate": 100,
                "violations": 0,
                "created_at": "2026-04-12T10:00:00Z",
            },
            {
                "id": "pol-9",
                "user_id": "user-2",
                "name": "Other tenant",
                "description": "Should be filtered out",
                "policy_type": "security",
                "is_active": True,
                "compliance_rate": 1,
                "violations": 9,
                "created_at": "2026-04-13T10:00:00Z",
            },
        ]
    )
    client = _build_client(fake_db)

    response = client.get("/api/governance/policies")

    assert response.status_code == 200
    assert response.json() == {
        "policies": [
            {
                "id": "pol-2",
                "name": "Encryption at Rest",
                "description": "Storage must be encrypted at rest.",
                "policy_type": "security",
                "is_active": False,
                "compliance_rate": 100.0,
                "violations": 0,
                "created_at": "2026-04-12T10:00:00Z",
            },
            {
                "id": "pol-1",
                "name": "Owner Tag Required",
                "description": "Every workload must have an Owner tag.",
                "policy_type": "tagging",
                "is_active": True,
                "compliance_rate": 91.5,
                "violations": 4,
                "created_at": "2026-04-11T10:00:00Z",
            },
        ],
        "count": 2,
    }
    assert fake_db.select_calls[-1] == (
        "governance_policies",
        "*",
        {"user_id": "user-1"},
    )


def test_get_governance_policies_returns_empty_state():
    client = _build_client(FakeDashboardReadDB())

    response = client.get("/api/governance/policies")

    assert response.status_code == 200
    assert response.json() == {
        "policies": [],
        "count": 0,
    }
