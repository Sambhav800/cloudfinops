import asyncio
from copy import deepcopy

from app.governance.compliance_engine import ComplianceEngine
from app.governance.policy_generator import generate_governance_policies


class FakeGovernanceDB:
    def __init__(self, resources=None):
        self.resources = resources or []
        self.policies = []
        self.cleared_policy_ids = []
        self.violations = []

    async def get_resources(self, user_id, integration_id=None):
        rows = [
            deepcopy(resource)
            for resource in self.resources
            if resource.get("user_id") == user_id
        ]
        if integration_id:
            rows = [
                resource
                for resource in rows
                if resource.get("integration_id") == integration_id
            ]
        return rows

    async def upsert_governance_policy(
        self,
        user_id,
        name,
        description,
        policy_type,
        compliance_rate,
        violations,
        metadata=None,
    ):
        policy = {
            "id": f"policy-{policy_type}",
            "user_id": user_id,
            "name": name,
            "description": description,
            "policy_type": policy_type,
            "compliance_rate": compliance_rate,
            "violations": violations,
            "metadata": metadata or {},
        }
        self.policies.append(deepcopy(policy))
        return policy

    async def clear_policy_violations(self, user_id, policy_id=None):
        self.cleared_policy_ids.append((user_id, policy_id))

    async def upsert_policy_violation(
        self,
        policy_id,
        resource_id,
        user_id,
        violation_detail,
        severity="medium",
    ):
        self.violations.append(
            {
                "policy_id": policy_id,
                "resource_id": resource_id,
                "user_id": user_id,
                "violation_detail": violation_detail,
                "severity": severity,
            }
        )


def _policy_by_type(db: FakeGovernanceDB, policy_type: str):
    return next(policy for policy in db.policies if policy["policy_type"] == policy_type)


def test_compliance_engine_derives_aws_gcp_violations_from_scanner_fields():
    db = FakeGovernanceDB()
    engine = ComplianceEngine(db)
    resources = [
        {
            "id": "row-sg",
            "user_id": "user-1",
            "integration_id": "int-1",
            "cloud_resource_id": "sg-123",
            "resource_name": "open-admin-sg",
            "service_type": "AWS Security Group",
            "region": "us-east-1",
            "region_compliance": "compliant",
            "metadata": {
                "is_overly_permissive": True,
                "tags": {"Owner": "platform", "Environment": "prod"},
            },
        },
        {
            "id": "row-gcp",
            "user_id": "user-1",
            "integration_id": "int-1",
            "cloud_resource_id": "gcp-vm-1",
            "resource_name": "analytics-runner",
            "service_type": "GCP Compute Instance",
            "region": "asia-east5-a",
            "region_compliance": "non_compliant",
            "metadata": {},
        },
    ]

    asyncio.run(
        engine.evaluate_and_save(
            user_id="user-1",
            integration_id="int-1",
            findings=resources,
            resource_id_map={"sg-123": "row-sg", "gcp-vm-1": "row-gcp"},
        )
    )

    assert _policy_by_type(db, "tagging")["violations"] == 2
    assert _policy_by_type(db, "region")["violations"] == 1
    assert _policy_by_type(db, "security")["violations"] == 1
    assert {
        (violation["policy_id"], violation["resource_id"], violation["severity"])
        for violation in db.violations
    } >= {
        ("policy-tagging", "row-sg", "medium"),
        ("policy-region", "row-gcp", "high"),
        ("policy-security", "row-sg", "critical"),
    }


def test_compliance_engine_clears_stale_violations_when_resources_are_compliant():
    db = FakeGovernanceDB()
    engine = ComplianceEngine(db)
    resources = [
        {
            "id": "row-ok",
            "cloud_resource_id": "vm-ok",
            "resource_name": "compliant-worker",
            "service_type": "AWS EC2 Instance",
            "region": "us-east-1",
            "region_compliance": "compliant",
            "metadata": {
                "tags": {
                    "Owner": "platform",
                    "CostCenter": "finops",
                    "Environment": "prod",
                }
            },
        }
    ]

    asyncio.run(
        engine.evaluate_and_save(
            user_id="user-1",
            integration_id="int-1",
            findings=resources,
            resource_id_map={"vm-ok": "row-ok"},
        )
    )

    assert db.violations == []
    assert {policy["violations"] for policy in db.policies} == {0}
    assert db.cleared_policy_ids == [
        ("user-1", "policy-tagging"),
        ("user-1", "policy-region"),
        ("user-1", "policy-security"),
        ("user-1", "policy-storage_security"),
        ("user-1", "policy-cost"),
    ]


def test_generate_governance_policies_uses_persisted_resource_ids_for_violations():
    db = FakeGovernanceDB(
        resources=[
            {
                "id": "row-sg",
                "user_id": "user-1",
                "integration_id": "int-1",
                "cloud_resource_id": "sg-123",
                "resource_name": "open-admin-sg",
                "service_type": "AWS Security Group",
                "region": "us-east-1",
                "region_compliance": "compliant",
                "metadata": {
                    "is_overly_permissive": True,
                    "tags": {
                        "Owner": "platform",
                        "CostCenter": "finops",
                        "Environment": "prod",
                    },
                },
            }
        ]
    )

    asyncio.run(
        generate_governance_policies(
            user_id="user-1",
            integration_id="int-1",
            resources=[
                {
                    "cloud_resource_id": "temporary-scan-row-without-db-id",
                    "resource_name": "should-not-be-used",
                }
            ],
            db=db,
        )
    )

    assert db.violations == [
        {
            "policy_id": "policy-security",
            "resource_id": "row-sg",
            "user_id": "user-1",
            "violation_detail": (
                "Security group 'open-admin-sg' allows public inbound access "
                "on a sensitive port."
            ),
            "severity": "critical",
        }
    ]
