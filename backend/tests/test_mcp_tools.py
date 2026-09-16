"""
Tests for backend/app/ai/mcp_server.py — FastMCP tool functions.

All tools call the database through get_db_client(). We mock that single
entry point and verify each tool's logic, output format, and edge cases.

Covers:
- Tool function existence and callability
- Response structure for each tool
- Empty-data / no-resources edge cases
- Aggregation / filtering logic
- Remediation script generation with shell-safe quoting
- Input sanitization (_shell_quote, _safe_s3_bucket_name)
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set env vars before any app imports
os.environ.setdefault("ENCRYPTION_KEY", "ac1d601fc216a6007afcdc7475e7fdb9ba89ee11c208fd8e3a9b9970ec3ad171")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")

from app.ai.mcp_server import (
    _safe_s3_bucket_name,
    _shell_quote,
    get_all_resources,
    get_alerts_and_notifications,
    get_bill_analysis_results,
    get_commitment_recommendations,
    get_cost_summary,
    get_daily_spend_trends,
    get_governance_status,
    get_infrastructure_drift,
    get_optimization_recommendations,
    get_resource_details,
    get_spend_by_team_tags,
    get_zombie_resources,
    generate_remediation_script,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESOURCES = [
    {
        "resource_name": "web-server-01",
        "service_type": "EC2",
        "status": "Active",
        "cost": 120.50,
        "region_compliance": "us-east-1",
        "provider": "aws",
        "waste_type": None,
        "waste_reason": None,
        "metadata": {"InstanceId": "i-abc123", "tags": {"team": "backend", "environment": "prod"}},
    },
    {
        "resource_name": "old-snapshot-disk",
        "service_type": "Disk",
        "status": "zombie",
        "cost": 45.00,
        "region_compliance": "westus2",
        "provider": "azure",
        "waste_type": "unattached",
        "waste_reason": "No VM attachment for 90+ days",
        "metadata": {"resourceGroupName": "rg-prod", "tags": {}},
    },
    {
        "resource_name": "idle-rds-db",
        "service_type": "RDS",
        "status": "idle",
        "cost": 200.00,
        "region_compliance": "eu-west-1",
        "provider": "aws",
        "waste_type": "idle",
        "waste_reason": "0 connections in 30 days",
        "metadata": {"DBInstanceIdentifier": "prod-db-01", "tags": {"owner": "data-team"}},
    },
]


def _mock_db(resources=None, select_return=None, notifications=None, spend_history=None):
    """Create a mock MongoDBClient with configurable returns."""
    db = AsyncMock()
    db.get_resources = AsyncMock(return_value=resources or [])
    db.select = AsyncMock(return_value=select_return or [])
    db.get_notifications = AsyncMock(return_value=notifications or [])
    db.get_daily_spend_history = AsyncMock(return_value=spend_history or [])
    return db


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------

class TestShellQuote:
    def test_safe_string(self):
        # shlex.quote only adds quotes when the string needs escaping
        assert _shell_quote("hello") == "hello"

    def test_dangerous_injection(self):
        result = _shell_quote("; rm -rf /")
        assert "rm" in result
        # shlex.quote wraps in single quotes and escapes
        assert result.startswith("'")
        assert result.endswith("'")

    def test_none_value(self):
        assert _shell_quote(None) == "''"


class TestSafeS3BucketName:
    def test_valid_bucket(self):
        assert _safe_s3_bucket_name("my-bucket-123") == "my-bucket-123"

    def test_invalid_bucket_returns_sentinel(self):
        assert _safe_s3_bucket_name("; rm -rf /") == "INVALID_BUCKET_NAME"

    def test_empty_bucket(self):
        assert _safe_s3_bucket_name("") == "INVALID_BUCKET_NAME"

    def test_none_bucket(self):
        assert _safe_s3_bucket_name(None) == "INVALID_BUCKET_NAME"

    def test_bucket_with_dots(self):
        assert _safe_s3_bucket_name("my.bucket.name") == "my.bucket.name"

    def test_too_short_bucket(self):
        assert _safe_s3_bucket_name("ab") == "INVALID_BUCKET_NAME"


# ---------------------------------------------------------------------------
# get_all_resources
# ---------------------------------------------------------------------------

class TestGetAllResources:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_resources(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_all_resources(user_id="user-1")

        assert result["total"] == 3
        assert len(result["resources"]) == 3
        assert result["resources"][0]["name"] == "web-server-01"
        assert result["resources"][0]["monthly_cost"] == 120.50

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_limit_parameter(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_all_resources(user_id="user-1", limit=1)
        assert result["total"] == 3  # total is full count
        assert len(result["resources"]) == 1  # but only 1 returned

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_empty_resources(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=[])
        result = await get_all_resources(user_id="user-1")
        assert result["total"] == 0
        assert result["resources"] == []

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_none_resources(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=None)
        result = await get_all_resources(user_id="user-1")
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# get_cost_summary
# ---------------------------------------------------------------------------

class TestGetCostSummary:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_aggregates_costs(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_cost_summary(user_id="user-1")

        assert result["total_resource_spend"] == pytest.approx(365.50)
        assert result["resource_count"] == 3
        assert "EC2" in result["by_type"]
        assert "us-east-1" in result["by_region"]
        assert "aws" in result["by_provider"]

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_empty_resources_returns_zeros(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=[])
        result = await get_cost_summary(user_id="user-1")
        assert result["total_monthly_spend"] == 0
        assert result["resource_count"] == 0

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_uses_dashboard_total_if_higher(self, mock_get_db):
        db = _mock_db(resources=SAMPLE_RESOURCES)
        db.select = AsyncMock(return_value=[{"user_id": "user-1", "total_spend": 1000.0}])
        mock_get_db.return_value = db
        result = await get_cost_summary(user_id="user-1")
        # dashboard_stats has 1000 which is > 365.50 resource sum
        assert result["total_monthly_spend"] == 1000.0
        assert result["unallocated_abstract_costs"] > 0


# ---------------------------------------------------------------------------
# get_zombie_resources
# ---------------------------------------------------------------------------

class TestGetZombieResources:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_filters_zombie_statuses(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_zombie_resources(user_id="user-1")

        assert result["zombie_count"] == 2  # "zombie" + "idle"
        assert result["total_waste_cost_monthly"] == pytest.approx(245.0)
        assert result["annual_waste"] == pytest.approx(2940.0)

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_zombies(self, mock_get_db):
        clean = [r for r in SAMPLE_RESOURCES if r["status"] == "Active"]
        mock_get_db.return_value = _mock_db(resources=clean)
        result = await get_zombie_resources(user_id="user-1")
        assert result["zombie_count"] == 0
        assert result["total_waste_cost_monthly"] == 0


# ---------------------------------------------------------------------------
# get_resource_details
# ---------------------------------------------------------------------------

class TestGetResourceDetails:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_exact_match(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_resource_details(user_id="user-1", resource_name="web-server-01")
        assert result["found"] is True
        assert result["name"] == "web-server-01"

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_partial_match(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_resource_details(user_id="user-1", resource_name="web-server")
        assert result["found"] is True
        assert result["name"] == "web-server-01"

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_case_insensitive(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_resource_details(user_id="user-1", resource_name="WEB-SERVER")
        assert result["found"] is True

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_match(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_resource_details(user_id="user-1", resource_name="nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# get_daily_spend_trends
# ---------------------------------------------------------------------------

class TestGetDailySpendTrends:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_daily_data(self, mock_get_db):
        history = [
            {"spend_date": "2026-09-01", "amount": 100},
            {"spend_date": "2026-09-02", "amount": 120},
        ]
        mock_get_db.return_value = _mock_db(spend_history=history)
        result = await get_daily_spend_trends(user_id="user-1", days=30)
        assert result["days_covered"] == 2
        assert result["average_daily_spend"] == 110.0
        assert result["total_period"] == 220.0

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_history(self, mock_get_db):
        mock_get_db.return_value = _mock_db(spend_history=None)
        result = await get_daily_spend_trends(user_id="user-1")
        assert "message" in result


# ---------------------------------------------------------------------------
# get_alerts_and_notifications
# ---------------------------------------------------------------------------

class TestGetAlertsAndNotifications:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_alerts(self, mock_get_db):
        notifications = [
            {
                "recommendation": "Delete unused disk",
                "type": "waste",
                "resource_id": "disk-01",
                "status": "pending",
                "created_at": "2026-09-01",
                "metadata": {"description": "Unattached disk", "severity": "high"},
            }
        ]
        mock_get_db.return_value = _mock_db(notifications=notifications)
        result = await get_alerts_and_notifications(user_id="user-1")
        assert result["total_alerts"] == 1
        assert result["alerts"][0]["severity"] == "high"

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_notifications(self, mock_get_db):
        mock_get_db.return_value = _mock_db(notifications=[])
        result = await get_alerts_and_notifications(user_id="user-1")
        assert result["total_alerts"] == 0


# ---------------------------------------------------------------------------
# get_governance_status
# ---------------------------------------------------------------------------

class TestGetGovernanceStatus:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_policies(self, mock_get_db):
        policies = [
            {"name": "Tagging", "policy_type": "tag", "compliance_rate": 80, "violations": 5, "description": "All resources must be tagged"},
            {"name": "Encryption", "policy_type": "security", "compliance_rate": 100, "violations": 0, "description": "Encrypt at rest"},
        ]
        mock_get_db.return_value = _mock_db(select_return=policies)
        result = await get_governance_status(user_id="user-1")
        assert result["policy_count"] == 2
        assert result["average_compliance"] == 90.0

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_policies(self, mock_get_db):
        mock_get_db.return_value = _mock_db(select_return=[])
        result = await get_governance_status(user_id="user-1")
        assert result["policy_count"] == 0
        assert result["average_compliance"] == 0


# ---------------------------------------------------------------------------
# get_infrastructure_drift
# ---------------------------------------------------------------------------

class TestGetInfrastructureDrift:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_detects_unmanaged_resources(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_infrastructure_drift(user_id="user-1")
        # None of the sample resources have terraform or cloudformation tags
        assert result["drift_detected"] is True
        assert result["unmanaged_resource_count"] == 3

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_managed_resource_not_flagged(self, mock_get_db):
        managed = [{
            "resource_name": "managed-vm",
            "service_type": "EC2",
            "status": "Active",
            "metadata": {"tags": {"Terraform": "true"}},
            "provider": "aws",
            "region_compliance": "us-east-1",
        }]
        mock_get_db.return_value = _mock_db(resources=managed)
        result = await get_infrastructure_drift(user_id="user-1")
        assert result["drift_detected"] is False
        assert result["unmanaged_resource_count"] == 0


# ---------------------------------------------------------------------------
# generate_remediation_script
# ---------------------------------------------------------------------------

class TestGenerateRemediationScript:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_aws_ec2_script(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await generate_remediation_script("user-1", "web-server-01", "aws")
        assert "terminate-instances" in result
        assert "i-abc123" in result

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_aws_rds_script(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await generate_remediation_script("user-1", "idle-rds", "aws")
        assert "delete-db-instance" in result
        assert "prod-db-01" in result

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_azure_disk_script(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await generate_remediation_script("user-1", "old-snapshot-disk", "azure")
        assert "az disk delete" in result
        assert "rg-prod" in result

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_resource_not_found(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await generate_remediation_script("user-1", "nonexistent", "aws")
        assert "Could not find" in result

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_unsupported_provider(self, mock_get_db):
        resources = [{
            "resource_name": "test-res",
            "service_type": "VM",
            "status": "Active",
            "provider": "oracle",
            "metadata": {},
        }]
        mock_get_db.return_value = _mock_db(resources=resources)
        result = await generate_remediation_script("user-1", "test-res", "oracle")
        assert "Unsupported provider" in result

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_gcp_compute_script(self, mock_get_db):
        resources = [{
            "resource_name": "gce-vm",
            "service_type": "Compute Instance",
            "status": "Active",
            "provider": "gcp",
            "metadata": {"projectId": "my-proj", "zone": "us-central1-a"},
        }]
        mock_get_db.return_value = _mock_db(resources=resources)
        result = await generate_remediation_script("user-1", "gce-vm", "gcp")
        assert "gcloud compute instances delete" in result
        assert "my-proj" in result


# ---------------------------------------------------------------------------
# get_spend_by_team_tags
# ---------------------------------------------------------------------------

class TestGetSpendByTeamTags:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_groups_by_tags(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=SAMPLE_RESOURCES)
        result = await get_spend_by_team_tags(user_id="user-1")
        # web-server has team=backend
        assert result["team"]["backend"] == pytest.approx(120.50)
        # idle-rds has owner=data-team
        assert result["owner"]["data-team"] == pytest.approx(200.0)
        # old-snapshot-disk has no allocation tags => untagged
        assert result["untagged"]["total"] == pytest.approx(45.0)

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_empty_resources(self, mock_get_db):
        mock_get_db.return_value = _mock_db(resources=[])
        result = await get_spend_by_team_tags(user_id="user-1")
        assert result["untagged"]["total"] == 0.0


# ---------------------------------------------------------------------------
# get_bill_analysis_results
# ---------------------------------------------------------------------------

class TestGetBillAnalysisResults:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_latest_analysis(self, mock_get_db):
        analyses = [
            {"created_at": "2026-08-01", "provider": "aws", "total_spend": 500, "currency": "USD",
             "waste_grade": "C", "by_category": {"compute": 300}, "raw_services": ["EC2", "RDS"],
             "savings_amount": 80, "rows_parsed": 1200},
            {"created_at": "2026-09-01", "provider": "aws", "total_spend": 600, "currency": "USD",
             "waste_grade": "B", "by_category": {"compute": 400}, "raw_services": ["EC2"],
             "savings_amount": 50, "rows_parsed": 1500},
        ]
        mock_get_db.return_value = _mock_db(select_return=analyses)
        result = await get_bill_analysis_results(user_id="user-1")
        assert result["status"] == "found"
        assert result["total_spend"] == 600  # latest by created_at
        assert result["waste_grade"] == "B"

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_analyses(self, mock_get_db):
        mock_get_db.return_value = _mock_db(select_return=[])
        result = await get_bill_analysis_results(user_id="user-1")
        assert result["status"] == "no_analyses"


# ---------------------------------------------------------------------------
# get_commitment_recommendations
# ---------------------------------------------------------------------------

class TestGetCommitmentRecommendations:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_aws_recommendations(self, mock_get_db):
        from datetime import datetime, timezone
        from app.core.commitment_recommendations import SOURCE

        db = _mock_db()
        now = datetime.now(timezone.utc).isoformat()
        db.get_user_integrations = AsyncMock(return_value=[{"id": "aws-1", "provider": "aws", "status": "active"}])
        db.select = AsyncMock(return_value=[{
            "integration_id": "aws-1", "account_id": "123456789012", "source": SOURCE,
            "status": "ready", "fetched_at": now, "generated_at": now,
            "scenarios": [{"label": "1-year Compute Savings Plan", "monthly_commitment_usd": 730,
                "monthly_saving_usd": 200, "annual_saving_usd": 2400, "term_years": 1,
                "hourly_commitment_usd": 1, "integration_id": "aws-1", "account_id": "123456789012",
                "recommendation_id": "native-1", "generated_at": now}],
        }])
        mock_get_db.return_value = db
        result = await get_commitment_recommendations(user_id="user-1")
        assert result["status"] == "ready"
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["monthly_saving_usd"] == 200
        assert result["recommendations"] == result["scenarios"]
        assert result["recommended_scenario"] is None
        db.select.assert_awaited_once_with("commitment_purchase_snapshots", filters={"user_id": "user-1"})

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_connected_clouds_do_not_create_fabricated_recommendations(self, mock_get_db):
        db = _mock_db()
        db.get_user_integrations = AsyncMock(return_value=[
            {"id": "aws-1", "provider": "aws", "status": "active"},
            {"id": "azure-1", "provider": "azure", "status": "active"},
            {"id": "gcp-1", "provider": "gcp", "status": "active"},
        ])
        mock_get_db.return_value = db
        result = await get_commitment_recommendations(user_id="user-1")
        assert result["status"] == "not_synced"
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_no_integrations(self, mock_get_db):
        db = _mock_db()
        db.get_user_integrations = AsyncMock(return_value=[])
        mock_get_db.return_value = db
        result = await get_commitment_recommendations(user_id="user-1")
        assert result["recommendations"] == []
        assert result["status"] == "no_spend_data"

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_failure_does_not_fall_back_to_generic_purchase_advice(self, mock_get_db):
        db = _mock_db()
        db.get_user_integrations = AsyncMock(side_effect=RuntimeError("secret connection"))
        mock_get_db.return_value = db
        result = await get_commitment_recommendations(user_id="user-1")
        assert result["status"] == "unavailable"
        assert result["recommendations"] == []
        assert "secret" not in str(result)


# ---------------------------------------------------------------------------
# get_optimization_recommendations
# ---------------------------------------------------------------------------

class TestGetOptimizationRecommendations:
    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_returns_grouped_recommendations(self, mock_get_db):
        notifications = [
            {"action_type": "rightsize", "resource_name": "vm-1", "service_type": "VM",
             "action_description": "Downsize to B2s", "potential_savings": 50, "severity": "high"},
            {"action_type": "rightsize", "resource_name": "vm-2", "service_type": "VM",
             "action_description": "Downsize to B1s", "potential_savings": 30, "severity": "medium"},
            {"action_type": "delete", "resource_name": "disk-1", "service_type": "Disk",
             "action_description": "Delete unattached", "potential_savings": 20, "severity": "low"},
        ]
        mock_get_db.return_value = _mock_db(select_return=notifications)
        result = await get_optimization_recommendations(user_id="user-1")
        assert result["total_pending_recommendations"] == 3
        assert result["total_potential_savings"] == 100.0
        assert result["by_action_type"]["rightsize"] == 2
        assert result["by_action_type"]["delete"] == 1
        assert len(result["top_5_by_savings"]) == 3
        assert result["top_5_by_savings"][0]["savings"] == 50

    @pytest.mark.asyncio
    @patch("app.ai.mcp_server.get_db_client")
    async def test_empty_recommendations(self, mock_get_db):
        mock_get_db.return_value = _mock_db(select_return=[])
        result = await get_optimization_recommendations(user_id="user-1")
        assert result["total_pending_recommendations"] == 0
        assert result["total_potential_savings"] == 0
