"""
Findings Synthesizer Agent.
Merges results from parallel scanners, deduplicates, and ranks by cost impact.
"""
from google.adk import Agent

from ...config import DEFAULT_GEMINI_FLASH_MODEL, GEMINI_AGENT_MODEL
from ...core.gemini_models import is_gemini_auto_model

_ADK_MODEL = DEFAULT_GEMINI_FLASH_MODEL if is_gemini_auto_model(GEMINI_AGENT_MODEL) else GEMINI_AGENT_MODEL

synthesizer_agent = Agent(
    name="Findings_Synthesizer",
    model=_ADK_MODEL,
    include_contents="none",
    instruction="""You are the Findings Synthesizer. Your job is to consolidate multi-cloud scanner results into a prioritized action plan.

INPUT DATA (from parallel scanner agents):
- AWS findings: {aws_findings}
- Azure findings: {azure_findings}
- GCP findings: {gcp_findings}

YOUR TASK:
1. Merge all findings across providers into a single prioritized list
2. Rank by monthly cost impact (highest waste first)
3. Calculate total monthly waste and annual projected impact
4. For each resource, include: provider, resource_id, type, monthly_cost, issue, tags, dependents count

OUTPUT FORMAT:
```
COST INVESTIGATION SUMMARY
==========================
Total waste identified: $X/month ($Y/year)
Resources requiring action: N

PRIORITY 1 (Highest Impact):
- [Provider] [resource_type] [resource_id] | $[cost]/mo | [issue] | tags: [tags] | dependents: [N]

PRIORITY 2:
- ...

RESOURCE METADATA FOR SAFETY VALIDATION:
(List each resource with its tags and dependent count — the Safety Critic needs this)
```

If NO waste was found across any provider, state clearly:
"All cloud resources are operating within normal parameters. No waste detected."
""",
    output_key="consolidated_findings",
)
