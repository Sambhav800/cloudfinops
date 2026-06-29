"""
Safety and State Management Tools for ADK.
Provides the exit_loop mechanism and inter-agent state passing.
"""
from google.adk.tools.tool_context import ToolContext


def exit_loop(tool_context: ToolContext) -> dict:
    """
    Call this tool ONLY when the safety review passes ALL checks and
    no further revisions to the remediation plan are needed.
    This signals the critic loop to complete and proceed to the final report.
    Do NOT call this if any safety check has failed.
    """
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {"status": "loop_complete", "reason": "All safety checks passed. Remediation approved."}


def save_finding_to_state(
    tool_context: ToolContext,
    resource_id: str,
    provider: str,
    region: str,
    resource_type: str,
    monthly_cost: float,
    issue: str,
    tags: str = "{}",
    dependents: int = 0,
) -> dict:
    """
    Saves a discovered zombie/idle/waste resource to shared session state.
    Called by scanner agents when they find resources that need attention.
    The Remediation Agent reads these findings to generate scripts.

    Args:
        resource_id: Cloud resource identifier (e.g., "i-0abc123", "vm-name")
        provider: Cloud provider ("aws", "azure", "gcp")
        region: Resource region or zone
        resource_type: Type of resource (e.g., "ec2", "ebs", "vm", "disk")
        monthly_cost: Estimated monthly cost in USD
        issue: Description of the problem (e.g., "stopped 23 days", "unattached")
        tags: JSON string of resource tags (e.g., '{"env": "dev", "team": "ml"}')
        dependents: Number of resources that depend on this one
    """
    findings = tool_context.state.get("discovered_findings", [])
    findings.append({
        "resource_id": resource_id,
        "provider": provider,
        "region": region,
        "resource_type": resource_type,
        "monthly_cost": monthly_cost,
        "issue": issue,
        "tags": tags,
        "dependents": dependents,
    })
    tool_context.state["discovered_findings"] = findings
    return {
        "status": "saved",
        "resource_id": resource_id,
        "total_findings": len(findings),
    }
