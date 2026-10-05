"""
CloudFinOps Core MCP Server.
Exposes cloud infrastructure, cost, and security data via the Model Context Protocol.
"""

import asyncio
import logging
from typing import Dict, Any, List
import shlex
import re

from mcp.server.fastmcp import FastMCP

# Import the existing MongoDB client factory
from app.db import get_db_client
from app.core.gpu_service import GpuService
from app.core.multicloud_comparison import build_multicloud_report
from app.core.commitment_recommendations import get_commitment_recommendation_result

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastMCP("cloudfinops-core")


def _shell_quote(value: Any) -> str:
    return shlex.quote(str(value or ""))


def _safe_s3_bucket_name(value: Any) -> str:
    bucket = str(value or "").strip()
    if re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        return bucket
    return "INVALID_BUCKET_NAME"


@app.tool()
async def get_all_resources(user_id: str, limit: int = 100) -> dict:
    """
    Get a list of ALL cloud resources for the user. Returns resource name,
    type, status, monthly cost, region, provider, waste type.
    Use for overview, resource counts, or general infrastructure questions.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    items = []
    for r in (resources or [])[:limit]:
        items.append({
            "name": r.get("resource_name", "Unknown"),
            "type": r.get("service_type", "Unknown"),
            "status": r.get("status", "unknown"),
            "monthly_cost": r.get("cost", 0) or 0,
            "region": r.get("region_compliance", "unknown"),
            "provider": r.get("provider", "unknown"),
            "waste_type": r.get("waste_type"),
            "waste_reason": r.get("waste_reason"),
        })
    return {"total": len(resources or []), "resources": items}


@app.tool()
async def get_cost_summary(user_id: str) -> dict:
    """
    Get cost summary: total monthly spend, breakdown by resource type,
    region, and provider. Use for cost-related questions.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    if not resources:
        return {"total_monthly_spend": 0, "by_type": {}, "by_region": {}, "by_provider": {}, "resource_count": 0}

    total = 0.0
    by_type: Dict[str, float] = {}
    by_region: Dict[str, float] = {}
    by_provider: Dict[str, float] = {}

    for r in resources:
        cost = r.get("cost", 0) or 0
        total += cost
        rtype = r.get("service_type", "Unknown")
        region = r.get("region_compliance", "Unknown")
        provider = r.get("provider", "Unknown")
        by_type[rtype] = by_type.get(rtype, 0) + cost
        by_region[region] = by_region.get(region, 0) + cost
        by_provider[provider] = by_provider.get(provider, 0) + cost

    real_total = total
    try:
        stats_list = await db.select("dashboard_stats", filters={"user_id": user_id})
        if stats_list:
            db_total = sum(s.get("total_spend", 0) or 0 for s in stats_list)
            real_total = max(total, db_total)
    except Exception:
        pass

    return {
        "total_monthly_spend": round(real_total, 2),
        "total_resource_spend": round(total, 2),
        "unallocated_abstract_costs": round(real_total - total, 2) if real_total > total else 0,
        "resource_count": len(resources),
        "by_type": {k: round(v, 2) for k, v in sorted(by_type.items(), key=lambda x: -x[1])},
        "by_region": {k: round(v, 2) for k, v in sorted(by_region.items(), key=lambda x: -x[1])},
        "by_provider": {k: round(v, 2) for k, v in sorted(by_provider.items(), key=lambda x: -x[1])},
    }


@app.tool()
async def get_zombie_resources(user_id: str) -> dict:
    """
    Get all zombie, waste, idle, and non-compliant resources with savings potential.
    Use for waste, zombie, optimization, or savings questions.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    zombie_statuses = {"zombie", "waste", "idle", "non_compliant", "idle/zombie", "oversized"}
    zombies = []
    total_waste_cost = 0.0

    for r in (resources or []):
        status = (r.get("status") or "").lower()
        if status in zombie_statuses:
            cost = r.get("cost", 0) or 0
            total_waste_cost += cost
            zombies.append({
                "name": r.get("resource_name"),
                "type": r.get("service_type"),
                "status": status,
                "monthly_cost": cost,
                "waste_type": r.get("waste_type"),
                "waste_reason": r.get("waste_reason"),
                "region": r.get("region_compliance"),
            })

    return {
        "zombie_count": len(zombies),
        "total_waste_cost_monthly": round(total_waste_cost, 2),
        "annual_waste": round(total_waste_cost * 12, 2),
        "zombies": zombies,
    }


@app.tool()
async def get_resource_details(user_id: str, resource_name: str) -> dict:
    """
    Get detailed info about a specific resource by name (exact or partial match).
    Returns full metadata. Use when user asks about a specific resource.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    search = resource_name.lower()
    matches = [
        r for r in (resources or [])
        if search in (r.get("resource_name") or "").lower()
    ]

    if not matches:
        return {"found": False, "message": f"No resource matching '{resource_name}'"}

    r = matches[0]
    metadata = r.get("metadata") or {}
    return {
        "found": True,
        "name": r.get("resource_name"),
        "type": r.get("service_type"),
        "status": r.get("status"),
        "monthly_cost": r.get("cost", 0) or 0,
        "region": r.get("region_compliance"),
        "provider": r.get("provider"),
        "waste_type": r.get("waste_type"),
        "waste_reason": r.get("waste_reason"),
        "metadata": metadata,
        "other_matches": [m.get("resource_name") for m in matches[1:5]],
    }


@app.tool()
async def get_daily_spend_trends(user_id: str, days: int = 30) -> dict:
    """
    Get daily cost data for trend analysis. Returns date and amount pairs.
    Use for trend, anomaly, or 'how has spend changed' questions.
    """
    db = get_db_client()
    history = await db.get_daily_spend_history(user_id, days=days)
    if not history:
        return {"days": [], "message": "No spend history available. Run a scan first."}

    entries = [{"date": h.get("spend_date"), "amount": h.get("amount", 0)} for h in history]
    amounts = [e["amount"] for e in entries if e["amount"]]
    avg = sum(amounts) / len(amounts) if amounts else 0

    return {
        "daily_data": entries[-days:],
        "average_daily_spend": round(avg, 2),
        "total_period": round(sum(amounts), 2),
        "days_covered": len(entries),
    }


@app.tool()
async def get_alerts_and_notifications(user_id: str) -> dict:
    """
    Get active alerts and AI-generated recommendations.
    Use for alerts, warnings, or recommendation questions.
    """
    db = get_db_client()
    notifications = await db.get_notifications(user_id)
    items = []
    for n in (notifications or []):
        metadata = n.get("metadata") if isinstance(n.get("metadata"), dict) else {}
        items.append({
            "title": n.get("recommendation") or n.get("type") or "Notification",
            "message": metadata.get("description") or n.get("recommendation"),
            "severity": metadata.get("severity") or "info",
            "type": n.get("type"),
            "resource": n.get("resource_id"),
            "status": n.get("status"),
            "created_at": n.get("created_at"),
        })
    return {"total_alerts": len(items), "alerts": items[:30]}


@app.tool()
async def get_governance_status(user_id: str) -> dict:
    """
    Get governance policy status: compliance rates, violations, policy details.
    Use for compliance, governance, or security posture questions.
    """
    db = get_db_client()
    policies = await db.select("governance_policies", filters={"user_id": user_id})
    items = []
    for p in (policies or []):
        items.append({
            "name": p.get("name"),
            "type": p.get("policy_type"),
            "compliance_rate": p.get("compliance_rate"),
            "violations": p.get("violations", 0),
            "description": p.get("description"),
        })

    rates = [p["compliance_rate"] for p in items if p["compliance_rate"] is not None]
    avg_compliance = sum(rates) / len(rates) if rates else 0

    return {
        "policy_count": len(items),
        "average_compliance": round(avg_compliance, 1),
        "policies": items,
    }

@app.tool()
async def get_infrastructure_drift(user_id: str) -> dict:
    """
    Detect infrastructure drift by finding resources that are missing IaC tags
    (like Terraform=true or aws:cloudformation).
    Use for security, drift, or unmanaged infrastructure questions.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    drifted = []

    for r in (resources or []):
        metadata = r.get("metadata") or {}
        tags = metadata.get("tags") or {}
            
        tags_lower = {str(k).lower(): str(v).lower() for k, v in tags.items()}
        
        is_managed = "terraform" in tags_lower or "aws:cloudformation:stack-name" in tags_lower or "aws:cloudformation:logical-id" in tags_lower
        
        if not is_managed:
            drifted.append({
                "name": r.get("resource_name"),
                "type": r.get("service_type"),
                "status": r.get("status"),
                "region": r.get("region_compliance"),
                "provider": r.get("provider")
            })

    return {
        "drift_detected": len(drifted) > 0,
        "unmanaged_resource_count": len(drifted),
        "total_resources": len(resources or []),
        "drifted_resources": drifted[:50]
    }

@app.tool()
async def generate_remediation_script(user_id: str, resource_name: str, provider: str, action: str = "delete") -> str:
    """
    Generates a remediation script (e.g., AWS CLI, Azure CLI, or Terraform snippet) 
    to delete or modify a specific cloud resource.
    Use this when the user asks "how do I delete this?" or "fix this".
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    search = resource_name.lower()
    
    matches = [
        r for r in (resources or [])
        if search in (r.get("resource_name") or "").lower() and (r.get("provider") or "").lower() == provider.lower()
    ]

    if not matches:
        return f"Could not find resource '{resource_name}' in provider '{provider}' to generate a script."

    r = matches[0]
    rtype = r.get("service_type", "").lower()
    rname = r.get("resource_name", "")
    metadata = r.get("metadata", {})
    
    script = ""
    # Very basic static generations based on provider
    if provider.lower() == "aws":
        if "ec2" in rtype or "instance" in rtype:
            instance_id = _shell_quote(metadata.get("InstanceId", rname))
            script = f"# AWS CLI command to terminate EC2 instance\naws ec2 terminate-instances --instance-ids {instance_id}"
        elif "s3" in rtype or "bucket" in rtype:
            bucket = _safe_s3_bucket_name(rname)
            script = f"# AWS CLI command to delete S3 bucket and its contents\naws s3 rb s3://{bucket} --force"
        elif "rds" in rtype or "database" in rtype:
            db_id = _shell_quote(metadata.get("DBInstanceIdentifier", rname))
            script = f"# AWS CLI command to delete RDS instance\naws rds delete-db-instance --db-instance-identifier {db_id} --skip-final-snapshot"
        else:
            script = (
                "# Note: Specific delete command could not be automatically determined.\n"
                f"# AWS CLI generic delete command template\naws {_shell_quote(rtype)} delete-resource --name {_shell_quote(rname)}"
            )
            
    elif provider.lower() == "azure":
        rg_name = _shell_quote(metadata.get("resourceGroupName", "YOUR_RESOURCE_GROUP"))
        safe_rname = _shell_quote(rname)
        safe_rtype = _shell_quote(rtype)
        if "vm" in rtype or "virtual machine" in rtype:
            script = f"# Azure CLI command to delete Virtual Machine\naz vm delete --resource-group {rg_name} --name {safe_rname} --yes"
        elif "disk" in rtype:
            script = f"# Azure CLI command to delete Managed Disk\naz disk delete --resource-group {rg_name} --name {safe_rname} --yes"
        else:
            script = f"# Azure CLI generic delete template\naz resource delete --resource-group {rg_name} --name {safe_rname} --resource-type {safe_rtype}"
            
    elif provider.lower() == "gcp":
        project = _shell_quote(metadata.get("projectId", "YOUR_PROJECT_ID"))
        zone = _shell_quote(metadata.get("zone", "YOUR_ZONE"))
        safe_rname = _shell_quote(rname)
        if "compute" in rtype or "instance" in rtype:
            script = f"# Google Cloud CLI command to delete VM\ngcloud compute instances delete {safe_rname} --project={project} --zone={zone} --quiet"
        else:
            script = f"# Google Cloud CLI generic command\ngcloud compute {_shell_quote(rtype)} delete {safe_rname} --project={project} --quiet"
            
    else:
        script = f"# Unsupported provider: {provider}"

    return f"Here is the script to {action} the resource:\n\n```bash\n{script}\n```\n\n**Warning**: Please review the script before executing it. This action may be irreversible."

@app.tool()
async def get_spend_by_team_tags(user_id: str) -> dict:
    """
    Get cloud spend grouped dynamically by common resource tags (e.g., Team, Owner, Environment).
    Use for tag-based allocation, chargeback, or finding out which team spends the most.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    
    # Common allocation tags
    tag_keys = ["team", "owner", "environment", "project", "department"]
    allocation: Dict[str, Dict[str, float]] = {k: {} for k in tag_keys}
    allocation["untagged"] = {"total": 0.0}

    for r in (resources or []):
        cost = r.get("cost", 0) or 0
        metadata = r.get("metadata") or {}
        tags = metadata.get("tags") or {}
        tags_lower = {str(k).lower(): str(v) for k, v in tags.items()}
        
        has_allocation_tag = False
        for tk in tag_keys:
            if tk in tags_lower:
                val = tags_lower[tk]
                allocation[tk][val] = allocation[tk].get(val, 0) + cost
                has_allocation_tag = True
                
        if not has_allocation_tag:
            allocation["untagged"]["total"] += cost

    # Sort each category by highest cost
    for tk in tag_keys:
        allocation[tk] = {k: round(v, 2) for k, v in sorted(allocation[tk].items(), key=lambda x: -x[1])}
    allocation["untagged"]["total"] = round(allocation["untagged"]["total"], 2)

    return allocation

@app.tool()
async def get_ml_cost_forecast(user_id: str, forecast_days: int = 30) -> dict:
    """
    Generate an ML-driven cost forecast for the next 'forecast_days' based on historical data.
    Use for budget predictions, forecasting, or future spend questions.
    """
    db = get_db_client()
    # Need at least a few days of history to forecast realistically
    history = await db.get_daily_spend_history(user_id, days=60)
    
    if not history or len(history) < 5:
        # Fallback to simple average or return error
        return {
            "forecast_stable": False,
            "message": "Not enough historical data for accurate ML forecast. Need at least 5 days of spend history.",
            "forecast_total": 0
        }

    try:
        import pandas as pd
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import numpy as np

        # Format data: older first
        history.sort(key=lambda x: x.get("spend_date", ""))
        dates = [h.get("spend_date") for h in history]
        amounts = [h.get("amount", 0) for h in history]
        
        # Simple statsmodel Exponential Smoothing (Holt-Winters)
        s = pd.Series(amounts)
        # Without explicit dates as index, just numerical sequence
        # Check if enough data for seasonality (e.g. 7 days weekly)
        seasonal_periods = 7 if len(amounts) >= 14 else None
        
        if seasonal_periods:
            model = ExponentialSmoothing(s, trend="add", seasonal="add", seasonal_periods=seasonal_periods, initialization_method="estimated")
        else:
            model = ExponentialSmoothing(s, trend="add", initialization_method="estimated")
            
        fit = model.fit()
        forecast = fit.forecast(forecast_days)
        
        # Prevent negative forecasts
        forecast = [max(0, float(x)) for x in forecast]
        
        return {
            "forecast_stable": True,
            "historical_baseline_avg": round(sum(amounts) / len(amounts), 2),
            "predicted_total_spend": round(sum(forecast), 2),
            "predicted_daily_avg": round(sum(forecast) / len(forecast), 2),
            "trend": "increasing" if forecast[-1] > forecast[0] else "decreasing"
        }
    except Exception as e:
        logger.error(f"ML Forecast error: {e}")
        # Fallback to simple moving average
        amounts = [h.get("amount", 0) for h in history]
        avg = sum(amounts) / len(amounts)
        return {
            "forecast_stable": False,
            "message": f"ML model failed, using simple average fallback.",
            "predicted_total_spend": round(avg * forecast_days, 2),
            "predicted_daily_avg": round(avg, 2)
        }

@app.tool()
async def get_gpu_intelligence(user_id: str) -> dict:
    """
    Get deep GPU FinOps intelligence: Ghost GPU alerts, MIG partitioning opportunities, 
    and arbitrage savings across specialized clouds (Lambda Labs, CoreWeave, JarvisLabs, RunPod).
    Use for ALL questions related to GPUs, AI accelerators, and ML workloads.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    service = GpuService()
    summary = service.get_gpu_summary(resources)
    return summary

@app.tool()
async def get_api_intelligence(user_id: str) -> dict:
    """
    Get API infrastructure intelligence: ghost APIs (idle/orphaned), cache waste,
    shadow APIs (compliance risk), cost-per-request ranking, and throttle analysis.
    Use for ALL questions about API Gateways, API Management, endpoints, and API costs.
    """
    from ..core.api_intelligence import ApiIntelligenceService
    db = get_db_client()
    resources = await db.get_resources(user_id)
    service = ApiIntelligenceService()
    return service.get_api_summary(resources)


@app.tool()
async def get_multicloud_comparison(user_id: str) -> dict:
    """
    Get a multi-cloud cost projection comparing AWS, GCP, and Azure for the user's live infrastructure.
    Use for migrations, multi-cloud strategy, or answering 'which cloud is cheapest'.
    """
    db = get_db_client()
    resources = await db.get_resources(user_id)
    provider = "aws"
    if resources and resources[0].get("provider"):
        provider = resources[0].get("provider")
    report = build_multicloud_report(resources, provider)
    return report

@app.tool()
async def get_bill_analysis_results(user_id: str) -> dict:
    """
    Get the user's most recent bill analysis results including spend breakdown by service,
    waste grade, savings estimates, and top findings. Use when asked about bill analysis,
    spend breakdown, or 'what did the bill scan find'.
    """
    db = get_db_client()
    analyses = await db.select("bill_analyses", filters={"user_id": user_id})
    if not analyses:
        return {"status": "no_analyses", "message": "No bill analyses found. Upload a bill via the Bill Analysis page."}

    latest = sorted(analyses, key=lambda a: a.get("created_at", ""), reverse=True)[0]
    return {
        "status": "found",
        "provider": latest.get("provider", "unknown"),
        "total_spend": latest.get("total_spend", 0),
        "currency": latest.get("currency", "USD"),
        "waste_grade": latest.get("waste_grade", "N/A"),
        "by_category": latest.get("by_category", {}),
        "top_services": (latest.get("raw_services") or [])[:10],
        "savings_estimate": latest.get("savings_amount", 0),
        "analyzed_at": latest.get("created_at", ""),
        "rows_parsed": latest.get("rows_parsed", 0),
    }


@app.tool()
async def get_commitment_recommendations(user_id: str) -> dict:
    """
    Get commitment/reservation purchase recommendations (Reserved Instances, Savings Plans,
    Committed Use Discounts). Use when asked about 'what RIs should I buy', 'savings plans',
    'commitment coverage', or 'how to reduce costs with commitments'.
    """
    try:
        result = await get_commitment_recommendation_result(db=get_db_client(), user_id=user_id)
        payload = result.model_dump()
        payload["recommendations"] = payload["scenarios"]
        payload["guidance"] = "Use only these stored provider estimates. Do not invent discounts, coverage, risk probabilities, or purchase amounts. Options for the same account are alternatives."
        return payload
    except Exception as error:
        logger.error("Commitment copilot data unavailable (%s)", type(error).__name__)
        return {"status": "unavailable", "recommendations": [], "message": "Verified commitment estimates are unavailable; no purchase recommendation can be made."}


@app.tool()
async def get_optimization_recommendations(user_id: str) -> dict:
    """
    Get all active optimization recommendations (autoscaling, rightsizing, scheduling, spot candidates).
    Use when asked about 'what should I optimize', 'recommendations', 'savings opportunities',
    or 'how to reduce my cloud bill'.
    """
    db = get_db_client()
    notifications = await db.select(
        "agent_notifications",
        filters={"user_id": user_id, "status": "pending"},
    )

    by_type = {}
    total_savings = 0.0
    for n in notifications:
        action_type = n.get("action_type", "review")
        savings = float(n.get("potential_savings", 0))
        total_savings += savings
        by_type.setdefault(action_type, []).append({
            "resource": n.get("resource_name", "Unknown"),
            "service_type": n.get("service_type", ""),
            "action": n.get("action_description", ""),
            "savings": savings,
            "severity": n.get("severity", "medium"),
        })

    return {
        "total_pending_recommendations": len(notifications),
        "total_potential_savings": round(total_savings, 2),
        "by_action_type": {k: len(v) for k, v in by_type.items()},
        "top_5_by_savings": sorted(
            [item for items in by_type.values() for item in items],
            key=lambda x: x["savings"],
            reverse=True,
        )[:5],
    }


if __name__ == "__main__":
    logger.info("Starting CloudFinOps FastMCP Server...")
    app.run()
