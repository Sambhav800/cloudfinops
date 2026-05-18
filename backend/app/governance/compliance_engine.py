"""
Compliance Engine for CloudFinOps.

Evaluates scanner findings against governance policies and records
violations in the database. Works with data already collected by
the scanner rather than making additional API calls.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..db import MongoDBClient, get_db_client

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """
    Evaluates cloud resources against governance policies.
    
    This engine takes scanner findings (already collected), evaluates them
    against defined policies, and writes results to the governance_policies
    and policy_violations tables in MongoDB.
    
    Usage:
        engine = ComplianceEngine(db_client)
        await engine.evaluate_and_save(user_id, integration_id, findings, resource_id_map)
    """
    
    # Define the standard governance policies
    POLICIES = [
        {
            "name": "Resource Tagging Policy",
            "description": (
                "All cloud resources must have Owner, CostCenter, and "
                "Environment tags for cost attribution and accountability."
            ),
            "policy_type": "tagging",
            "check_fn": "_check_tagging_violations"
        },
        {
            "name": "Region Compliance Policy",
            "description": (
                "Resources must be deployed in approved regions only. "
                "Unapproved regions increase latency and compliance risk."
            ),
            "policy_type": "region",
            "check_fn": "_check_region_violations"
        },
        {
            "name": "Network Security Policy",
            "description": (
                "Network security groups must not allow unrestricted "
                "inbound access on SSH (22), RDP (3389), or all ports."
            ),
            "policy_type": "security",
            "check_fn": "_check_security_violations"
        },
        {
            "name": "Storage Security Policy",
            "description": (
                "Storage accounts must enforce HTTPS-only traffic, "
                "use TLS 1.2+, and disable public blob access."
            ),
            "policy_type": "storage_security",
            "check_fn": "_check_storage_violations"
        },
        {
            "name": "Resource Waste Policy",
            "description": (
                "Idle and unused resources must be identified and "
                "removed to prevent unnecessary cloud spending."
            ),
            "policy_type": "cost",
            "check_fn": "_check_waste_violations"
        }
    ]
    
    def __init__(self, db: MongoDBClient):
        """
        Initialize the Compliance Engine.
        
        Args:
            db: MongoDB client instance for database operations
        """
        self.db = db

    @staticmethod
    def _metadata(finding: Dict[str, Any]) -> Dict[str, Any]:
        metadata = finding.get("metadata")
        return metadata if isinstance(metadata, dict) else {}

    @classmethod
    def _tags(cls, finding: Dict[str, Any]) -> Dict[str, Any]:
        tags = finding.get("tags")
        if isinstance(tags, dict):
            return tags

        metadata_tags = cls._metadata(finding).get("tags")
        return metadata_tags if isinstance(metadata_tags, dict) else {}

    @classmethod
    def _missing_required_tags(cls, finding: Dict[str, Any]) -> List[str]:
        tag_keys = {str(key).strip().casefold() for key in cls._tags(finding)}
        required = {
            "Owner": {"owner", "createdby", "created_by"},
            "CostCenter": {"costcenter", "cost_center", "cost-centre", "costcentre"},
            "Environment": {"environment", "env"},
        }

        missing = []
        for display_name, aliases in required.items():
            if not tag_keys.intersection(aliases):
                missing.append(display_name)
        return missing

    @classmethod
    def _resource_name(cls, finding: Dict[str, Any]) -> str:
        return str(
            finding.get("resource_name")
            or finding.get("name")
            or finding.get("cloud_resource_id")
            or "Unknown resource"
        )

    @classmethod
    def _service_type(cls, finding: Dict[str, Any]) -> str:
        return str(
            finding.get("service_type")
            or finding.get("resource_type")
            or "Resource"
        )
    
    async def evaluate_and_save(
        self,
        user_id: str,
        integration_id: str,
        findings: List[Dict[str, Any]],
        resource_id_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Evaluate all findings against all policies and save results.
        
        Args:
            user_id: Clerk user ID
            integration_id: Cloud integration ID
            findings: List of resource findings from scanner
            resource_id_map: Map of lowercase cloud_resource_id -> DB uuid
        
        Returns:
            Summary dict with policy results
        """
        logger.info(
            f"Evaluating {len(findings)} resources against "
            f"{len(self.POLICIES)} governance policies"
        )
        
        total_resources = len(findings)
        policy_results = []
        
        for policy_def in self.POLICIES:
            try:
                # Run the check function
                check_fn = getattr(self, policy_def["check_fn"])
                violations = check_fn(findings)
                
                violation_count = len(violations)
                compliant_count = total_resources - violation_count
                compliance_rate = (
                    int((compliant_count / total_resources) * 100)
                    if total_resources > 0 else 100
                )
                
                # Upsert the policy record
                policy_record = await self.db.upsert_governance_policy(
                    user_id=user_id,
                    name=policy_def["name"],
                    description=policy_def["description"],
                    policy_type=policy_def["policy_type"],
                    compliance_rate=compliance_rate,
                    violations=violation_count,
                    metadata={
                        "integration_id": integration_id,
                        "total_resources_checked": total_resources,
                        "last_evaluated": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "sample_violations": [
                            v["detail"] for v in violations[:5]
                        ]
                    }
                )
                
                # Replace individual violations for this policy on every run.
                # Otherwise a remediated resource would leave stale active rows.
                if policy_record:
                    policy_id = policy_record.get("id")
                    if policy_id:
                        await self.db.clear_policy_violations(
                            user_id, policy_id
                        )

                        for violation in violations[:50]:
                            cloud_rid = (
                                violation.get("cloud_resource_id") or ""
                            ).lower()
                            db_resource_id = resource_id_map.get(cloud_rid)
                            
                            if db_resource_id:
                                await self.db.upsert_policy_violation(
                                    policy_id=policy_id,
                                    resource_id=db_resource_id,
                                    user_id=user_id,
                                    violation_detail=violation["detail"],
                                    severity=violation.get(
                                        "severity", "medium"
                                    )
                                )
                
                policy_results.append({
                    "name": policy_def["name"],
                    "type": policy_def["policy_type"],
                    "compliance_rate": compliance_rate,
                    "violations": violation_count
                })
                
                logger.info(
                    f"Policy '{policy_def['name']}': "
                    f"{compliance_rate}% compliant, "
                    f"{violation_count} violations"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to evaluate policy "
                    f"'{policy_def['name']}': {e}"
                )
                policy_results.append({
                    "name": policy_def["name"],
                    "type": policy_def["policy_type"],
                    "compliance_rate": 0,
                    "violations": 0,
                    "error": str(e)
                })
        
        summary = {
            "total_policies": len(self.POLICIES),
            "total_resources": total_resources,
            "policy_results": policy_results,
            "overall_compliance": (
                int(
                    sum(p["compliance_rate"] for p in policy_results)
                    / len(policy_results)
                ) if policy_results else 100
            )
        }
        
        logger.info(
            f"Governance evaluation complete: "
            f"{summary['overall_compliance']}% overall compliance"
        )
        
        return summary
    
    # =========================================================================
    # POLICY CHECK FUNCTIONS
    # Each returns a list of violation dicts with:
    #   cloud_resource_id, detail, severity
    # =========================================================================
    
    def _check_tagging_violations(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check all resources for missing required tags."""
        violations = []
        
        for finding in findings:
            gov_violations = finding.get("governance_violations") or []
            matched_embedded_violation = False
            for v in gov_violations:
                if v.get("type") == "missing_tag":
                    matched_embedded_violation = True
                    missing = v.get("tags", [])
                    violations.append({
                        "cloud_resource_id": finding.get(
                            "cloud_resource_id"
                        ),
                        "detail": (
                            f"Resource '{self._resource_name(finding)}' "
                            f"({self._service_type(finding)}) is missing "
                            f"required tags: {', '.join(missing)}"
                        ),
                        "severity": "medium"
                    })

            if matched_embedded_violation:
                continue

            missing = self._missing_required_tags(finding)
            if missing:
                violations.append({
                    "cloud_resource_id": finding.get("cloud_resource_id"),
                    "detail": (
                        f"Resource '{self._resource_name(finding)}' "
                        f"({self._service_type(finding)}) is missing "
                        f"required tags: {', '.join(missing)}"
                    ),
                    "severity": "medium",
                })
        
        return violations
    
    def _check_region_violations(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check all resources for region compliance."""
        violations = []
        
        for finding in findings:
            gov_violations = finding.get("governance_violations") or []
            matched_embedded_violation = False
            for v in gov_violations:
                if v.get("type") == "region_violation":
                    matched_embedded_violation = True
                    violations.append({
                        "cloud_resource_id": finding.get(
                            "cloud_resource_id"
                        ),
                        "detail": (
                            f"Resource '{self._resource_name(finding)}' "
                            f"deployed in non-approved region: "
                            f"{v.get('region')}"
                        ),
                        "severity": "high"
                    })

            if matched_embedded_violation:
                continue

            region_compliance = str(
                finding.get("region_compliance") or ""
            ).strip().lower()
            if region_compliance in {"non_compliant", "shadow_it", "restricted"}:
                violations.append({
                    "cloud_resource_id": finding.get("cloud_resource_id"),
                    "detail": (
                        f"Resource '{self._resource_name(finding)}' "
                        f"deployed in non-approved region: "
                        f"{finding.get('region') or 'unknown'}"
                    ),
                    "severity": "high",
                })
        
        return violations
    
    def _check_security_violations(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for NSG security risks."""
        violations = []
        
        for finding in findings:
            metadata = self._metadata(finding)
            service_type = self._service_type(finding).lower()

            if (finding.get("waste_type") == "security_risk"
                    and finding.get("service_type") == "Network Security Group"):
                risky_rules = (
                    finding.get("metrics_data", {}).get("risky_rules") or []
                )
                for rule in risky_rules:
                    violations.append({
                        "cloud_resource_id": finding.get(
                            "cloud_resource_id"
                        ),
                        "detail": (
                            f"NSG '{finding.get('resource_name')}' allows "
                            f"inbound traffic from {rule.get('source')} "
                            f"to port {rule.get('port')} via rule "
                            f"'{rule.get('name')}'"
                        ),
                        "severity": "critical"
                    })

            if metadata.get("is_overly_permissive"):
                violations.append({
                    "cloud_resource_id": finding.get("cloud_resource_id"),
                    "detail": (
                        f"Security group '{self._resource_name(finding)}' "
                        "allows public inbound access on a sensitive port."
                    ),
                    "severity": "critical",
                })

            if metadata.get("publicly_accessible") is True:
                violations.append({
                    "cloud_resource_id": finding.get("cloud_resource_id"),
                    "detail": (
                        f"Resource '{self._resource_name(finding)}' "
                        "is publicly accessible and should be reviewed."
                    ),
                    "severity": "high",
                })

            if metadata.get("public_ip") and any(
                token in service_type
                for token in ("instance", "virtual machine", "compute")
            ):
                violations.append({
                    "cloud_resource_id": finding.get("cloud_resource_id"),
                    "detail": (
                        f"Compute resource '{self._resource_name(finding)}' "
                        "has a public IP address attached."
                    ),
                    "severity": "high",
                })
        
        return violations
    
    def _check_storage_violations(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for storage account security issues."""
        violations = []
        
        for finding in findings:
            if (finding.get("waste_type") == "security_risk"
                    and finding.get("service_type") == "Storage Account"):
                storage_violations = (
                    finding.get("metrics_data", {}).get("violations") or []
                )
                for sv in storage_violations:
                    violations.append({
                        "cloud_resource_id": finding.get(
                            "cloud_resource_id"
                        ),
                        "detail": (
                            f"Storage account "
                            f"'{finding.get('resource_name')}': {sv}"
                        ),
                        "severity": "high"
                    })
        
        return violations
    
    def _check_waste_violations(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for resource waste (zombies, orphans, etc.)."""
        violations = []
        
        waste_types_to_check = [
            "zombie_vm", "stopped_vm", "deallocated_vm",
            "orphan_disk", "zombie_ip", "zombie_lb", "orphan_nic"
        ]
        
        for finding in findings:
            if finding.get("waste_type") in waste_types_to_check:
                violations.append({
                    "cloud_resource_id": finding.get(
                        "cloud_resource_id"
                    ),
                    "detail": (
                        finding.get("waste_reason")
                        or f"Resource '{finding.get('resource_name')}' "
                           f"identified as {finding.get('waste_type')}"
                    ),
                    "severity": (
                        "high" if finding.get("cost", 0) > 50
                        else "medium"
                    )
                })
        
        return violations


async def run_compliance_check(user_id: str) -> Dict[str, Any]:
    """
    Standalone entry point for running compliance checks.
    Can be called from API endpoints, cron jobs, or CLI —
    independently of the scanner pipeline.
    """
    db = get_db_client()
    engine = ComplianceEngine(db)
    return await engine.run_full_compliance_check(user_id)


# CLI entry point for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.governance.compliance_engine <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    results = asyncio.run(run_compliance_check(user_id))

    print(f"\n📊 Results:")
    print(f"   Policies checked: {results['policies_checked']}")
    print(f"   Violations found: {results['violations_found']}")
    print(f"   Violations resolved: {results['violations_resolved']}")

    sys.exit(0)
