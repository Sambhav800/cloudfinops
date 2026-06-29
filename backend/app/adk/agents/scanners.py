"""
Multi-Cloud Scanner Agents — ParallelAgent orchestration.
Three specialized scanner agents run concurrently to scan AWS, Azure, and GCP.
"""
from google.adk import Agent
from google.adk.agents.parallel_agent import ParallelAgent

from ..tools.aws_tools import scan_aws_ec2, scan_aws_ebs_volumes, get_aws_cost_breakdown
from ..tools.azure_tools import scan_azure_vms, scan_azure_disks, get_azure_costs
from ..tools.gcp_tools import scan_gcp_instances, scan_gcp_disks, get_gcp_costs
from ..tools.safety_tools import save_finding_to_state

aws_scanner_agent = Agent(
    name="AWS_Scanner",
    model="gemini-3.5-flash",
    instruction="""You are the AWS Scanner Agent. Your mission is to scan AWS infrastructure and identify cost waste.

EXECUTION PLAN:
1. Call get_aws_cost_breakdown to understand recent spending patterns
2. Call scan_aws_ec2 to find stopped/zombie EC2 instances
3. Call scan_aws_ebs_volumes to find orphaned/unattached EBS volumes

For EACH zombie/idle/waste resource you discover:
- Call save_finding_to_state with ALL details (resource_id, monthly_cost, tags, issue description)
- This saves it to shared state so the Remediation Agent can act on it

REPORT FORMAT:
Summarize your findings clearly:
- How many resources scanned
- How many zombies/waste found
- Total monthly waste in USD
- Details of each problematic resource (ID, type, cost, how long idle, tags)

If no issues found, explicitly state "No waste detected in AWS."
""",
    tools=[scan_aws_ec2, scan_aws_ebs_volumes, get_aws_cost_breakdown, save_finding_to_state],
    output_key="aws_findings",
)

azure_scanner_agent = Agent(
    name="Azure_Scanner",
    model="gemini-3.5-flash",
    instruction="""You are the Azure Scanner Agent. Your mission is to scan Azure infrastructure for cost waste.

EXECUTION PLAN:
1. Call get_azure_costs to understand spending patterns
2. Call scan_azure_vms to find idle/deallocated VMs
3. Call scan_azure_disks to find unattached managed disks

For EACH waste resource found:
- Call save_finding_to_state with full details
- Include resource group, location, tags, and estimated monthly cost

REPORT FORMAT:
- Resources scanned count
- Idle/waste resources found
- Total monthly waste in USD
- Details per resource

If no issues, state "No waste detected in Azure."
""",
    tools=[scan_azure_vms, scan_azure_disks, get_azure_costs, save_finding_to_state],
    output_key="azure_findings",
)

gcp_scanner_agent = Agent(
    name="GCP_Scanner",
    model="gemini-3.5-flash",
    instruction="""You are the GCP Scanner Agent. Your mission is to scan Google Cloud for cost waste.

EXECUTION PLAN:
1. Call get_gcp_costs to check spending patterns
2. Call scan_gcp_instances to find terminated/idle Compute Engine VMs
3. Call scan_gcp_disks to find unattached persistent disks

For EACH waste resource found:
- Call save_finding_to_state with all details
- Include project, zone, labels, and cost estimate

REPORT FORMAT:
- Resources scanned
- Waste found
- Monthly waste USD
- Per-resource details

If no issues, state "No waste detected in GCP."
""",
    tools=[scan_gcp_instances, scan_gcp_disks, get_gcp_costs, save_finding_to_state],
    output_key="gcp_findings",
)

from .gpu_intelligence import gpu_intelligence_agent
from .api_intelligence import api_intelligence_agent

parallel_scanner = ParallelAgent(
    name="MultiCloud_Scanner",
    sub_agents=[aws_scanner_agent, azure_scanner_agent, gcp_scanner_agent, gpu_intelligence_agent, api_intelligence_agent],
)
