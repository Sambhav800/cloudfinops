import asyncio

from app.ai.agent import CloudFinOpsAgent
from app.core.agent_context import build_agent_system_prompt


class FakeAgentContextDB:
    async def select(self, table, filters=None, columns="*"):
        filters = filters or {}
        if table == "cloud_price_catalog_syncs":
            return [
                {
                    "provider": "aws",
                    "records_saved": 320,
                    "synced_at": "2026-04-28T10:00:00+00:00",
                }
            ]

        user_id = filters.get("id") or filters.get("user_id")
        if user_id != "user-1":
            return []

        if table == "users":
            return [
                {
                    "id": "user-1",
                    "first_name": "Sambhav",
                    "full_name": "Sambhav Pal",
                    "email": "sambhavpal5@gmail.com",
                    "organization": "CloudFinOps Labs",
                }
            ]

        if table == "dashboard_stats":
            return [
                {
                    "user_id": "user-1",
                    "total_spend": 450.0,
                    "potential_savings": 125.5,
                    "active_resources_count": 38,
                    "ai_confidence_score": 92,
                },
                {
                    "user_id": "user-1",
                    "total_spend": 50.0,
                    "potential_savings": 24.5,
                    "active_resources_count": 12,
                    "ai_confidence_score": 88,
                }
            ]

        if table == "budget_events":
            return [
                {
                    "user_id": "user-1",
                    "scope": "portfolio",
                    "budget_limit": 1000.0,
                    "current_status": "approaching_budget",
                    "forecast_eom_spend": 880.0,
                    "created_at": "2026-03-22T10:00:00+00:00",
                }
            ]

        if table == "agent_notifications":
            return [
                {
                    "id": "alert-1",
                    "user_id": "user-1",
                    "status": "pending",
                    "type": "cost_optimization",
                    "action": "rightsize",
                    "resource_id": "res-1",
                    "metadata": {
                        "resource_name": "prod-api-node-1",
                        "potential_savings": 85.0,
                        "action_type": "rightsize",
                    },
                },
                {
                    "id": "alert-2",
                    "user_id": "user-1",
                    "status": "pending",
                    "type": "cost_optimization",
                    "action": "stop",
                    "resource_id": "res-2",
                    "metadata": {
                        "resource_name": "idle-batch-runner",
                        "potential_savings": 40.0,
                        "action_type": "stop",
                    },
                },
            ]

        if table == "policy_violations":
            return [
                {
                    "id": "violation-1",
                    "user_id": "user-1",
                    "status": "active",
                    "resource_id": "res-nsg",
                    "severity": "critical",
                    "violation_details": {"detail": "Inbound RDP is open to the public internet."},
                    "created_at": "2026-03-22T11:00:00+00:00",
                },
                {
                    "id": "violation-2",
                    "user_id": "user-1",
                    "status": "active",
                    "resource_id": "res-etl",
                    "severity": "medium",
                    "violation_details": {"detail": "CostCenter tag is missing."},
                    "created_at": "2026-03-21T11:00:00+00:00",
                },
            ]

        if table == "cloud_integrations":
            return [
                {
                    "id": "int-aws",
                    "user_id": "user-1",
                    "provider": "aws",
                    "status": "active",
                    "last_scan": "2026-03-22T08:00:00+00:00",
                },
                {
                    "id": "int-gcp",
                    "user_id": "user-1",
                    "provider": "gcp",
                    "status": "active",
                    "last_scan": "2026-03-22T07:00:00+00:00",
                },
            ]

        return []

    async def get_resources(self, user_id, integration_id=None):
        if user_id != "user-1":
            return []

        return [
            {
                "id": "res-actual",
                "user_id": "user-1",
                "provider": "aws",
                "metadata": {"cost_source": "actual"},
            },
            {
                "id": "res-market",
                "user_id": "user-1",
                "provider": "gcp",
                "metadata": {"cost_source": "catalog_estimate"},
            },
            {
                "id": "res-needed",
                "user_id": "user-1",
                "provider": "azure",
                "metadata": {"cost_source": "billing_unavailable"},
            },
            {
                "id": "res-free",
                "user_id": "user-1",
                "provider": "aws",
                "metadata": {"cost_source": "no_direct_charge"},
            },
        ]


def test_build_agent_system_prompt_uses_live_account_data():
    prompt = asyncio.run(build_agent_system_prompt("user-1", FakeAgentContextDB()))

    assert "Name: Sambhav" in prompt
    assert "Organization: CloudFinOps Labs" in prompt
    assert "Connected clouds: AWS, GCP" in prompt
    assert "Budget: $1,000.00/mo | MTD spend: $500.00 (50.0% used) | Forecast EOM: $880.00 | Status: Approaching Budget" in prompt
    assert "Savings identified: $150.00/month ($1,800.00/year)" in prompt
    assert "Resources scanned: 50" in prompt
    assert "AI analysis confidence: 90%" in prompt
    assert "Open alerts: 2 | Governance violations: 2" in prompt
    assert 'Address user as "Sambhav"' in prompt
    assert "there" not in prompt.lower()


class FakeEmailFallbackAgentContextDB(FakeAgentContextDB):
    async def select(self, table, filters=None, columns="*"):
        if table == "users":
            return [
                {
                    "id": "user-1",
                    "full_name": None,
                    "email": "nishantj0803@gmail.com",
                    "organization": "CloudFinOps Labs",
                }
            ]
        return await super().select(table, filters=filters, columns=columns)


def test_build_agent_system_prompt_uses_cleaned_email_prefix_when_name_missing():
    prompt = asyncio.run(build_agent_system_prompt("user-1", FakeEmailFallbackAgentContextDB()))

    assert "Name: Nishantj" in prompt
    assert '"Good' in prompt or '"Hey' in prompt
    assert "there" not in prompt.lower()


def test_build_agent_system_prompt_appends_savings_domain_context():
    prompt = asyncio.run(
        build_agent_system_prompt("user-1", FakeAgentContextDB(), user_query="show me savings")
    )

    assert "CURRENT REQUEST DOMAIN:\nsavings" in prompt
    assert "Pending cost optimizations: 2" in prompt
    assert "- prod-api-node-1: Rightsize ($85.00/month)" in prompt
    assert "- idle-batch-runner: Stop ($40.00/month)" in prompt


def test_build_agent_system_prompt_appends_governance_domain_context():
    prompt = asyncio.run(
        build_agent_system_prompt("user-1", FakeAgentContextDB(), user_query="show me governance")
    )

    assert "CURRENT REQUEST DOMAIN:\ngovernance" in prompt
    assert "Active governance violations: 2" in prompt
    assert "- Critical | res-nsg: Inbound RDP is open to the public internet." in prompt
    assert "- Medium | res-etl: CostCenter tag is missing." in prompt


def test_build_agent_system_prompt_skips_domain_context_for_general_query():
    prompt = asyncio.run(
        build_agent_system_prompt("user-1", FakeAgentContextDB(), user_query="hello there")
    )

    assert "CURRENT REQUEST DOMAIN:" not in prompt


def test_build_agent_system_prompt_appends_pricing_domain_context():
    prompt = asyncio.run(
        build_agent_system_prompt("user-1", FakeAgentContextDB(), user_query="show me market pricing setup")
    )

    assert "CURRENT REQUEST DOMAIN:\npricing" in prompt
    assert "Cost data model: market/list prices first, actual billing second." in prompt
    assert "Cost source coverage: actual=1, catalog_estimate=1, billing_unavailable=1, no_direct_charge=1, unknown=0" in prompt
    assert "Latest catalog sync: AWS 320 rows" in prompt
    assert "AWS CUR 2.0/Data Exports with resource IDs" in prompt
    assert "GCP Detailed Billing Export to BigQuery" in prompt


def test_agent_mcp_params_use_backend_cwd_and_pythonpath():
    agent = CloudFinOpsAgent(db_client=None, user_id="user-1")
    params = agent._get_mcp_params()

    assert params.cwd is not None
    assert str(params.cwd).endswith("/backend")
    assert params.env is not None
    assert "PYTHONPATH" in params.env
    assert str(params.cwd) in params.env["PYTHONPATH"]
