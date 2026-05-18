"""
Governance Policy Generator for CloudFinOps.

Provides the generate_governance_policies function that routes.py
calls for non-Azure providers. For Azure, ComplianceEngine is used
directly in routes.py.

This module exists for backward compatibility with the AWS/GCP
scan flow.
"""

import logging
from typing import List, Dict, Any

from ..db import MongoDBClient
from .compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)


async def generate_governance_policies(
    user_id: str,
    integration_id: str,
    resources: List[Dict[str, Any]],
    db: MongoDBClient
) -> None:
    """
    Generate governance policies from scanned resources.
    
    This is the legacy function called by routes.py for AWS/GCP providers.
    It creates basic tagging and region compliance policies.
    
    For Azure, use ComplianceEngine.evaluate_and_save() instead.
    
    Args:
        user_id: Clerk user ID
        integration_id: Cloud integration ID  
        resources: List of resource dicts from scanner
        db: MongoDB client instance
    """
    persisted_resources: List[Dict[str, Any]] = []
    try:
        persisted_resources = await db.get_resources(user_id, integration_id)
    except Exception as error:
        logger.warning(
            "Could not load persisted resources for governance evaluation: %s",
            error,
        )

    evaluation_resources = persisted_resources or resources
    if not evaluation_resources:
        logger.info("No resources to generate policies for")
        return

    if persisted_resources:
        resource_id_map: Dict[str, str] = {}
        for resource in persisted_resources:
            db_id = str(resource.get("id") or "").strip()
            if not db_id:
                continue
            for raw_key in (
                resource.get("cloud_resource_id"),
                resource.get("resource_id"),
                (resource.get("metadata") or {}).get("instance_id")
                if isinstance(resource.get("metadata"), dict) else None,
                (resource.get("metadata") or {}).get("volume_id")
                if isinstance(resource.get("metadata"), dict) else None,
                (resource.get("metadata") or {}).get("allocation_id")
                if isinstance(resource.get("metadata"), dict) else None,
                (resource.get("metadata") or {}).get("group_id")
                if isinstance(resource.get("metadata"), dict) else None,
                (resource.get("metadata") or {}).get("resource_id")
                if isinstance(resource.get("metadata"), dict) else None,
            ):
                key = str(raw_key or "").strip().lower()
                if key:
                    resource_id_map[key] = db_id

        engine = ComplianceEngine(db)
        await engine.evaluate_and_save(
            user_id=user_id,
            integration_id=integration_id,
            findings=evaluation_resources,
            resource_id_map=resource_id_map,
        )
        return
    
    total = len(resources)
    
    # Count tagging violations
    tag_violations = 0
    for r in resources:
        tags = r.get("tags") or {}
        if not tags or not all(
            k in tags for k in ["Owner", "CostCenter", "Environment"]
        ):
            tag_violations += 1
    
    tag_compliance = (
        int(((total - tag_violations) / total) * 100) if total > 0 else 100
    )
    
    # Count waste violations
    waste_violations = sum(
        1 for r in resources
        if r.get("status") in ["waste", "zombie"]
    )
    
    waste_compliance = (
        int(((total - waste_violations) / total) * 100) if total > 0 else 100
    )
    
    try:
        await db.upsert_governance_policy(
            user_id=user_id,
            name="Resource Tagging Policy",
            description="All resources must have required tags.",
            policy_type="tagging",
            compliance_rate=tag_compliance,
            violations=tag_violations,
            metadata={"integration_id": integration_id}
        )
        
        await db.upsert_governance_policy(
            user_id=user_id,
            name="Resource Waste Policy",
            description="Idle and unused resources must be removed.",
            policy_type="cost",
            compliance_rate=waste_compliance,
            violations=waste_violations,
            metadata={"integration_id": integration_id}
        )

        # Regional compliance policy
        approved_regions = ["eastus", "westus", "centralus", "us-east-1", "us-west-2", "eu-west-1"]
        region_violations = sum(
            1 for r in resources
            if r.get("region", "").lower() not in approved_regions
            and r.get("region") is not None
        )
        region_compliance = (
            int(((total - region_violations) / total) * 100) if total > 0 else 100
        )

        await db.upsert_governance_policy(
            user_id=user_id,
            name="Regional Compliance Policy",
            description="Resources must be deployed in approved regions.",
            policy_type="regional",
            compliance_rate=region_compliance,
            violations=region_violations,
            metadata={"integration_id": integration_id, "approved_regions": approved_regions}
        )

        # Network security policy
        security_violations = sum(
            1 for r in resources
            if r.get("metadata", {}).get("public_ip") is not None
            or r.get("service_type", "").lower() in ["public ip", "elastic ip"]
        )
        security_compliance = (
            int(((total - security_violations) / total) * 100) if total > 0 else 100
        )

        await db.upsert_governance_policy(
            user_id=user_id,
            name="Network Security Policy",
            description="Resources with public IP exposure must be reviewed.",
            policy_type="security",
            compliance_rate=security_compliance,
            violations=security_violations,
            metadata={"integration_id": integration_id}
        )

        logger.info(
            f"Generated governance policies: "
            f"tagging={tag_compliance}%, waste={waste_compliance}%, "
            f"regional={region_compliance}%, security={security_compliance}%"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate governance policies: {e}")
