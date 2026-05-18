"""
Proposed architecture generator.

Builds a prompt from the current topology, calls Gemini to generate
a proposed architecture diagram, validates the output, and returns
a structured result with change list + estimated savings.

IMPORTANT: This module is ONLY called when the user clicks "Generate"
on the frontend. It is never called automatically.
"""

import json
import logging
import asyncio
import math
import re
from typing import Any, Dict, List, Optional

from .contracts import ChangeItem, ProposedResult
from .models import RegionTopology
from .aws_renderers import render_topology_summary
from .proposed_validator import validate_proposed_mermaid

logger = logging.getLogger(__name__)

_USE_GOOGLE_GENAI = False
genai_client = None
genai_types = None
try:
    from google import genai as genai_client
    from google.genai import types as genai_types
    _USE_GOOGLE_GENAI = True
except Exception:
    genai_client = None
    genai_types = None

_ALLOWED_CHANGE_TYPES = {
    "terminate",
    "downsize",
    "migrate",
    "add_replica",
    "enable_multi_az",
    "add_monitoring",
    "tighten_security",
    "enable_encryption",
}
_ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
_MAX_CHANGE_ITEMS = 200
_MAX_PROMPT_DETAILS_PER_VPC = 120
_MAX_RATE_LIMIT_FAILURES = 2


# ---------------------------------------------------------------------------
# Mode descriptions (used in prompts)
# ---------------------------------------------------------------------------

_MODE_DESCRIPTIONS = {
    "cost_optimized": (
        "Cost-Optimized Architecture. Your goal is to MINIMIZE monthly spend "
        "while maintaining acceptable availability. Aggressively recommend:\n"
        "- Terminating zombie/idle resources\n"
        "- Downsizing oversized instances (right-sizing)\n"
        "- Consolidating underutilized VPCs/subnets\n"
        "- Switching to Spot/Reserved instances where appropriate\n"
        "- Removing unused EBS volumes, EIPs, snapshots\n"
        "- Using cheaper instance families (e.g. t3 instead of m5 for dev)\n"
        "- Consolidating small Lambda functions"
    ),
    "reliability_security_optimized": (
        "Reliability & Security Optimized Architecture. Your goal is to MAXIMIZE "
        "availability, fault tolerance, and security posture. Recommend:\n"
        "- Adding Multi-AZ for single-AZ RDS instances\n"
        "- Adding read replicas for high-traffic databases\n"
        "- Distributing EC2 across multiple AZs\n"
        "- Adding NAT Gateways for private subnets\n"
        "- Tightening overly permissive security groups\n"
        "- Enabling encryption at rest for EBS/RDS\n"
        "- Adding CloudTrail/GuardDuty if missing\n"
        "- Adding auto-scaling groups\n"
        "NOTE: This mode may INCREASE cost. That's acceptable."
    ),
}

_RETRY_DELAY_PATTERNS = (
    re.compile(r"retry_delay.*?seconds:\s*(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"retry[_ -]?after[:= ]+(\d+)", re.IGNORECASE),
)


def _extract_retry_delay_seconds(error: Exception | str) -> int:
    message = str(error or "")
    for pattern in _RETRY_DELAY_PATTERNS:
        match = pattern.search(message)
        if match:
            try:
                return max(0, int(match.group(1)))
            except (TypeError, ValueError):
                return 0
    return 0


# ---------------------------------------------------------------------------
# Build the prompt
# ---------------------------------------------------------------------------

def _build_prompt(
    topology: RegionTopology,
    current_mermaid: str,
    mode: str,
    constraints: Optional[List[str]] = None,
) -> str:
    """Build a concise Gemini prompt for proposed architecture generation."""

    # Resource summary (concise, not full metadata)
    resource_summary = []
    for vpc in topology.vpcs:
        vpc_info = {
            "vpc_id": vpc.vpc_id,
            "name": vpc.name,
            "monthly_cost": round(vpc.monthly_cost, 2),
            "waste_cost": round(vpc.waste_cost, 2),
            "resources": {},
        }
        for kind, count in vpc.resource_counts.items():
            vpc_info["resources"][kind] = count

        # Add individual resource details, capped to keep prompt stable at scale.
        details = []
        for sn in vpc.subnets:
            for r in sn.resources:
                details.append({
                    "id": r.cloud_resource_id,
                    "name": r.resource_name,
                    "kind": r.service_kind,
                    "cost": round(r.cost, 2),
                    "status": r.status,
                    "waste_type": r.waste_type,
                    "instance_type": r.metadata.get("instance_type", ""),
                    "instance_class": r.metadata.get("instance_class", ""),
                })
        for r in vpc.unplaced_resources:
            details.append({
                "id": r.cloud_resource_id,
                "name": r.resource_name,
                "kind": r.service_kind,
                "cost": round(r.cost, 2),
                "status": r.status,
                "waste_type": r.waste_type,
            })
        details.sort(
            key=lambda d: (
                0 if d.get("waste_type") else 1,
                0 if str(d.get("status", "")).lower() in ("zombie", "stopped", "waste") else 1,
                -float(d.get("cost") or 0),
            )
        )
        capped_details = details[:_MAX_PROMPT_DETAILS_PER_VPC]
        vpc_info["resource_details"] = capped_details
        if len(details) > _MAX_PROMPT_DETAILS_PER_VPC:
            vpc_info["resource_details_truncated"] = len(details) - _MAX_PROMPT_DETAILS_PER_VPC
        resource_summary.append(vpc_info)

    # Standalone
    standalone_summary = {
        "s3_count": len(topology.standalone.s3_buckets),
        "lambda_count": len(topology.standalone.lambda_functions),
        "iam_count": len(topology.standalone.iam_entities),
        "total_cost": round(topology.standalone.total_cost, 2),
    }

    mode_desc = _MODE_DESCRIPTIONS.get(mode, _MODE_DESCRIPTIONS["cost_optimized"])
    constraints_text = ""
    if constraints:
        clean_constraints = [str(c).strip() for c in constraints if str(c).strip()]
        if clean_constraints:
            constraints_text = "\n**USER CONSTRAINTS (must be respected):**\n" + "\n".join(
                f"- {c[:200]}" for c in clean_constraints[:20]
            )

    resources_json = json.dumps(resource_summary, indent=1, default=str)
    standalone_json = json.dumps(standalone_summary, indent=1)

    return f"""You are a senior AWS Solutions Architect. Generate a PROPOSED architecture diagram.

**MODE:** {mode_desc}
{constraints_text}

**CURRENT ARCHITECTURE — Region: {topology.region}**
Total Cost: ${topology.total_cost:.2f}/mo | Waste: ${topology.total_waste:.2f}/mo | Resources: {topology.resource_count}

VPCs:
```json
{resources_json}
```

Standalone:
```json
{standalone_json}
```

Current Mermaid diagram (for reference):
```mermaid
{current_mermaid}
```

**OUTPUT FORMAT — Return a JSON object with these EXACT keys:**
```json
{{
  "proposed_mermaid": "flowchart TD\\n    ...",
  "change_list": [
    {{
      "resource_id": "<cloud_resource_id>",
      "resource_name": "<name>",
      "service_type": "<kind>",
      "change_type": "terminate|downsize|migrate|add_replica|enable_multi_az|add_monitoring|tighten_security|enable_encryption",
      "current_state": "<current config>",
      "proposed_state": "<proposed config>",
      "monthly_savings": <float positive for savings, negative for added cost>,
      "risk_level": "low|medium|high",
      "reasoning": "<1-2 sentence explanation>"
    }}
  ],
  "estimated_savings": <float total monthly savings, can be negative for reliability mode>,
  "risk_tradeoffs": "<2-3 paragraph summary of trade-offs and risks>"
}}
```

**RULES:**
1. proposed_mermaid MUST start with "flowchart TD"
2. proposed_mermaid MUST be valid Mermaid syntax
3. Show ONLY the proposed state (not current vs proposed)
4. Use emoji in node labels (🟢 active, 🔴 removed, 🔵 new, 🟡 modified)
5. Mark removed resources with strikethrough or [REMOVED] prefix
6. Mark new resources with [NEW] prefix
7. Keep the diagram under 200 lines
8. change_list MUST reference real resource IDs from the input
9. estimated_savings is the SUM of all change_list[].monthly_savings

Return ONLY valid JSON."""


# ---------------------------------------------------------------------------
# Parse and validate Gemini response
# ---------------------------------------------------------------------------

def _parse_gemini_response(
    raw: str,
    mode: str,
    integration_id: str,
    region: str,
    resource_index: Dict[str, Dict[str, Any]],
) -> ProposedResult:
    """Parse and validate a raw Gemini JSON response string."""
    data = json.loads(raw)

    # Extract fields
    proposed_mermaid = data.get("proposed_mermaid", "")
    change_list_raw = data.get("change_list", [])
    model_estimated_savings = float(data.get("estimated_savings", 0))
    risk_tradeoffs = data.get("risk_tradeoffs", "")

    # Validate Mermaid
    is_valid, errors = validate_proposed_mermaid(proposed_mermaid)
    if not is_valid:
        raise ValueError(f"Invalid proposed Mermaid: {'; '.join(errors)}")

    # Parse change list
    if not isinstance(change_list_raw, list):
        raise ValueError("change_list must be an array")
    if len(change_list_raw) > _MAX_CHANGE_ITEMS:
        raise ValueError(f"change_list too large: {len(change_list_raw)} > {_MAX_CHANGE_ITEMS}")

    change_items: List[ChangeItem] = []
    warnings: List[Dict[str, str]] = []
    seen_resource_ids = set()
    for c in change_list_raw:
        if not isinstance(c, dict):
            raise ValueError("Each change_list item must be an object")

        resource_id = str(c.get("resource_id", "")).strip()
        if not resource_id:
            raise ValueError("change_list item is missing resource_id")
        if resource_id not in resource_index:
            raise ValueError(f"change_list references unknown resource_id: {resource_id}")
        if resource_id in seen_resource_ids:
            raise ValueError(f"Duplicate change_list resource_id: {resource_id}")
        seen_resource_ids.add(resource_id)

        change_type = str(c.get("change_type", "")).strip().lower()
        if change_type not in _ALLOWED_CHANGE_TYPES:
            raise ValueError(f"Invalid change_type for {resource_id}: {change_type}")

        monthly_savings = float(c.get("monthly_savings", 0))
        if not math.isfinite(monthly_savings):
            raise ValueError(f"Non-finite monthly_savings for {resource_id}")

        risk_level = str(c.get("risk_level", "medium")).strip().lower()
        if risk_level not in _ALLOWED_RISK_LEVELS:
            warnings.append({
                "type": "risk_level_normalized",
                "message": f"Risk level '{risk_level}' normalized to 'medium' for {resource_id}",
            })
            risk_level = "medium"

        real = resource_index[resource_id]
        resource_cost = max(float(real.get("cost", 0) or 0), 0.0)
        cap = max(resource_cost * 3, 1.0)
        if abs(monthly_savings) > cap:
            raise ValueError(
                f"monthly_savings out of bounds for {resource_id}: "
                f"{monthly_savings} exceeds cap {cap}"
            )
        change_items.append(ChangeItem(
            resource_id=resource_id,
            resource_name=real["resource_name"],
            service_type=real["service_type"],
            change_type=change_type,
            current_state=str(c.get("current_state", "")).strip()[:300],
            proposed_state=str(c.get("proposed_state", "")).strip()[:300],
            monthly_savings=monthly_savings,
            risk_level=risk_level,
            reasoning=str(c.get("reasoning", "")).strip()[:1000],
        ))

    estimated_savings = round(sum(item.monthly_savings for item in change_items), 2)
    if abs(model_estimated_savings - estimated_savings) > 0.01:
        warnings.append({
            "type": "estimated_savings_normalized",
            "message": (
                f"Model estimated_savings {model_estimated_savings:.2f} did not match "
                f"change_list sum {estimated_savings:.2f}; using exact sum."
            ),
        })

    return ProposedResult(
        mode=mode,
        integration_id=integration_id,
        region=region,
        proposed_mermaid=proposed_mermaid,
        change_list=change_items,
        estimated_savings=estimated_savings,
        risk_tradeoffs=str(risk_tradeoffs).strip()[:5000],
        warnings=warnings,
    )


def _resource_index_from_topology(topology: RegionTopology) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    def put(resource: Any) -> None:
        rid = resource.cloud_resource_id
        if not rid:
            return
        index[rid] = {
            "resource_name": resource.resource_name,
            "service_type": resource.service_kind,
            "cost": float(resource.cost or 0),
        }

    for vpc in topology.vpcs:
        for subnet in vpc.subnets:
            for resource in subnet.resources:
                put(resource)
        for resource in vpc.unplaced_resources:
            put(resource)

    for resource in topology.standalone.s3_buckets:
        put(resource)
    for resource in topology.standalone.lambda_functions:
        put(resource)
    for resource in topology.standalone.iam_entities:
        put(resource)
    for resource in topology.standalone.other:
        put(resource)

    return index


# ---------------------------------------------------------------------------
# Public: generate proposed architecture
# ---------------------------------------------------------------------------

async def generate_proposed_architecture(
    topology: RegionTopology,
    resources: List[Dict[str, Any]],
    mode: str,
    integration_id: str,
    constraints: Optional[List[str]] = None,
) -> ProposedResult:
    """
    Generate a proposed architecture using Gemini.

    This function is intentionally called ONLY when the user clicks
    "Generate". It is NEVER triggered automatically.
    """
    from ..config import GEMINI_API_KEY, GEMINI_PROPOSE_MODEL

    region = topology.region

    # 1. Build current mermaid deterministically
    current_view = render_topology_summary(topology)
    current_mermaid = current_view.mermaid

    # 2. Build prompt
    prompt = _build_prompt(topology, current_mermaid, mode, constraints)
    resource_index = _resource_index_from_topology(topology)

    # 3. Check if Gemini is available
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured — returning fallback proposed architecture")
        return _get_fallback_result(topology, mode, integration_id, region)

    # 4. Call Gemini
    if not _USE_GOOGLE_GENAI or genai_client is None or genai_types is None:
        logger.warning("google-genai package unavailable - returning fallback proposed architecture")
        return _get_fallback_result(topology, mode, integration_id, region)

    client = genai_client.Client(api_key=GEMINI_API_KEY)

    max_retries = 3
    base_delay = 3.0
    last_error = None
    rate_limit_failures = 0

    for attempt in range(max_retries):
        if rate_limit_failures >= _MAX_RATE_LIMIT_FAILURES:
            logger.error(
                "🛑 Proposed architecture circuit breaker triggered after %s rate limits",
                rate_limit_failures,
            )
            break
        try:
            logger.info(
                f"🏗️ Generating proposed architecture [{mode}] for {region} "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            response = await client.aio.models.generate_content(
                model=GEMINI_PROPOSE_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                    max_output_tokens=16384,
                    response_mime_type="application/json",
                ),
            )

            result = _parse_gemini_response(
                (getattr(response, "text", "") or ""), mode, integration_id, region, resource_index
            )
            logger.info(
                f"✅ Proposed architecture generated: "
                f"{len(result.change_list)} changes, "
                f"${result.estimated_savings:.2f}/mo savings"
            )
            return result

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(f"⚠️ Gemini returned invalid JSON (attempt {attempt + 1}): {e}")
        except ValueError as e:
            last_error = e
            logger.warning(f"⚠️ Gemini output failed validation (attempt {attempt + 1}): {e}")
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            is_rate_limit = "429" in error_msg or "quota" in error_msg
            if is_rate_limit and attempt < max_retries - 1:
                rate_limit_failures += 1
                api_delay = _extract_retry_delay_seconds(e)
                sleep_time = max(api_delay, base_delay * (2 ** attempt))
                sleep_time = min(sleep_time, 120)
                logger.warning(f"⏳ Rate limit hit. Waiting {sleep_time}s...")
                await asyncio.sleep(sleep_time)
                continue
            logger.error(f"❌ Gemini proposed generation failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(base_delay)

    # All attempts failed
    logger.error(f"🔴 All {max_retries} attempts failed: {last_error}")
    return _get_fallback_result(
        topology, mode, integration_id, region,
        warning_message=f"AI generation failed after {max_retries} attempts: {last_error}"
    )


# ---------------------------------------------------------------------------
# Rule-based fallback (no Gemini)
# ---------------------------------------------------------------------------

def _get_fallback_result(
    topology: RegionTopology,
    mode: str,
    integration_id: str,
    region: str,
    warning_message: Optional[str] = None,
) -> ProposedResult:
    """
    Generate a rule-based proposed architecture when Gemini is unavailable.
    """
    change_items: List[ChangeItem] = []
    total_savings = 0.0

    if mode == "cost_optimized":
        # Find zombies and waste
        for vpc in topology.vpcs:
            for sn in vpc.subnets:
                for r in sn.resources:
                    if r.status.lower() in ("zombie", "stopped") or r.waste_type:
                        savings = r.cost
                        total_savings += savings
                        change_items.append(ChangeItem(
                            resource_id=r.cloud_resource_id,
                            resource_name=r.resource_name,
                            service_type=r.service_kind,
                            change_type="terminate",
                            current_state=f"{r.status} — {r.waste_type or 'unused'}",
                            proposed_state="Terminated",
                            monthly_savings=savings,
                            risk_level="low",
                            reasoning=f"Resource is {r.status.lower()} with waste type '{r.waste_type}'. Safe to remove.",
                        ))
            for r in vpc.unplaced_resources:
                if r.status.lower() in ("zombie", "stopped") or r.waste_type:
                    savings = r.cost
                    total_savings += savings
                    change_items.append(ChangeItem(
                        resource_id=r.cloud_resource_id,
                        resource_name=r.resource_name,
                        service_type=r.service_kind,
                        change_type="terminate",
                        current_state=f"{r.status} — {r.waste_type or 'unused'}",
                        proposed_state="Terminated",
                        monthly_savings=savings,
                        risk_level="low",
                        reasoning=f"Unplaced resource is {r.status.lower()}. Safe to remove.",
                    ))

        risk_text = (
            "Cost optimization focuses on removing waste resources. "
            "All recommended terminations target zombie or stopped resources. "
            "Risk is low as these resources are not actively serving traffic. "
            "Review each change before applying."
        )

    else:  # reliability_security_optimized
        # Find single-AZ RDS instances in all VPC resources
        for vpc in topology.vpcs:
            all_vpc_resources = []
            for sn in vpc.subnets:
                all_vpc_resources.extend(sn.resources)
            all_vpc_resources.extend(vpc.unplaced_resources)

            for r in all_vpc_resources:
                if r.service_kind == "rds" and r.status.lower() == "active":
                    multi_az = r.metadata.get("multi_az", False)
                    if not multi_az:
                        added_cost = r.cost * 0.8  # Multi-AZ roughly doubles cost
                        total_savings -= added_cost
                        change_items.append(ChangeItem(
                            resource_id=r.cloud_resource_id,
                            resource_name=r.resource_name,
                            service_type=r.service_kind,
                            change_type="enable_multi_az",
                            current_state="Single-AZ",
                            proposed_state="Multi-AZ",
                            monthly_savings=-added_cost,
                            risk_level="low",
                            reasoning="Single-AZ RDS has no failover. Enable Multi-AZ for automatic failover.",
                        ))

        risk_text = (
            "Reliability optimization adds redundancy and security controls. "
            "This typically increases monthly cost. "
            "Changes improve availability SLA and reduce blast radius of failures. "
            "Multi-AZ databases have automatic failover within 60 seconds."
        )

    # Build a simple proposed mermaid from current + changes
    current_view = render_topology_summary(topology)
    proposed_mermaid = current_view.mermaid  # Start from current

    warnings: List[Dict[str, str]] = []
    if warning_message:
        warnings.append({"type": "generation_fallback", "message": warning_message})
    warnings.append({
        "type": "rule_based",
        "message": "Generated using rule-based heuristics (no AI). Results may be less comprehensive.",
    })

    return ProposedResult(
        mode=mode,
        integration_id=integration_id,
        region=region,
        proposed_mermaid=proposed_mermaid,
        change_list=change_items,
        estimated_savings=total_savings,
        risk_tradeoffs=risk_text,
        warnings=warnings,
    )
