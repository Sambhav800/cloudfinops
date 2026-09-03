"""
Architecture Report Generator.

Produces a professional, executive-grade architecture report using Gemini AI.
The output is structured markdown suitable for PDF conversion, written as if
a senior DevOps team prepared it for management review.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from ..config import GEMINI_API_KEY, GEMINI_PROPOSE_MODEL
from ..core.gemini_models import resolve_gemini_model_name

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REPORT_MODEL = GEMINI_PROPOSE_MODEL


async def generate_architecture_report(
    *,
    provider: str,
    integration_name: str,
    region: str,
    mermaid_code: str,
    nodes: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    warnings: List[Dict[str, str]],
    proposed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a professional architecture report using Gemini.

    Returns a dict with:
      - report_markdown: Full structured report in markdown
      - generated_at: ISO timestamp
      - title: Report title
    """
    if not GEMINI_API_KEY:
        return {
            "status": "error",
            "message": "Gemini API key not configured. Cannot generate report.",
        }

    # Build context for the AI
    resource_summary = _build_resource_summary(nodes)
    coverage_summary = _build_coverage_summary(coverage)
    warnings_text = "\n".join(f"- {w.get('message', '')}" for w in warnings) if warnings else "None"
    proposed_text = _build_proposed_summary(proposed) if proposed else "No optimization proposal generated yet."

    prompt = f"""You are a senior DevOps architect at a Fortune 500 company. Generate a comprehensive
infrastructure architecture report that will be presented to the VP of Engineering and CTO.

This report should read as if a team of experienced cloud architects prepared it after a thorough
infrastructure review. It must be precise, data-driven, and actionable.

CLOUD PROVIDER: {provider.upper()}
INTEGRATION: {integration_name}
REGION: {region}
GENERATED: {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}

ARCHITECTURE DIAGRAM (Mermaid):
```
{mermaid_code[:3000]}
```

RESOURCE INVENTORY:
{resource_summary}

SERVICE COVERAGE:
{coverage_summary}

COVERAGE WARNINGS:
{warnings_text}

OPTIMIZATION PROPOSAL:
{proposed_text}

---

Generate a professional report with EXACTLY these sections:

# Infrastructure Architecture Report — {provider.upper()} ({region})

## 1. Executive Summary
(2-3 sentences: What is this infrastructure, what is its purpose, and what is the overall health status)

## 2. Architecture Overview
(Describe the network topology — VPCs/VNets, subnets, how services are organized. Reference the diagram.)

## 3. Resource Inventory
(Table of all resources: Name | Type | Cost | Status | Risk Level)
(Include actual numbers from the data provided)

## 4. Cost Analysis
(Total monthly spend, top cost drivers, waste identified, cost per service category)

## 5. Security & Compliance Posture
(Based on coverage data: what's monitored, what's missing, compliance gaps, exposed services)

## 6. Risk Assessment
| Risk | Severity | Impact | Recommendation |
(At least 3-5 risks identified from the architecture)

## 7. Optimization Recommendations
(Based on the proposed architecture if available, or derived from waste/zombie resources)
(Each recommendation: What to do, Expected savings, Risk level, Implementation effort)

## 8. Action Items
(Prioritized list: P1/P2/P3 with owner placeholder and timeline)

## 9. Appendix: Service Coverage Matrix
(Table showing detected vs missing services)

---

FORMATTING RULES:
- Use precise numbers (don't round excessively)
- Include $ amounts for ALL cost references
- Use tables wherever data is structured
- Keep recommendations specific and actionable (not generic)
- Write with authority — this is an expert assessment, not a suggestion
- Total report length: 800-1200 words
"""

    try:
        model_name = await resolve_gemini_model_name(REPORT_MODEL, api_key=GEMINI_API_KEY)
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return {"status": "error", "message": "No response from Gemini"}

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return {"status": "error", "message": "Empty response from Gemini"}

        title = f"Infrastructure Architecture Report — {provider.upper()} ({region})"

        return {
            "status": "success",
            "report_markdown": text,
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "region": region,
            "integration_name": integration_name,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API error for report generation: {e.response.status_code}")
        return {"status": "error", "message": f"AI service returned {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {"status": "error", "message": str(e)}


def _build_resource_summary(nodes: List[Dict[str, Any]]) -> str:
    if not nodes:
        return "No resources found in scan data."

    lines = []
    total_cost = 0.0
    status_counts: Dict[str, int] = {}
    type_counts: Dict[str, int] = {}

    for node in nodes[:50]:
        cost = node.get("cost", 0)
        total_cost += cost
        status = node.get("status", "Unknown")
        service_type = node.get("service_type", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts[service_type] = type_counts.get(service_type, 0) + 1

    lines.append(f"Total resources: {len(nodes)}")
    lines.append(f"Total monthly cost: ${total_cost:.2f}")
    lines.append(f"Status breakdown: {', '.join(f'{k}: {v}' for k, v in sorted(status_counts.items()))}")
    lines.append(f"Service types: {', '.join(f'{k}: {v}' for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:8])}")

    waste_nodes = [n for n in nodes if n.get("status", "").lower() in ("zombie", "stopped") or n.get("waste_type")]
    if waste_nodes:
        waste_cost = sum(n.get("cost", 0) for n in waste_nodes)
        lines.append(f"Waste resources: {len(waste_nodes)} (${waste_cost:.2f}/mo)")

    lines.append("\nTop 10 by cost:")
    sorted_nodes = sorted(nodes, key=lambda n: n.get("cost", 0), reverse=True)[:10]
    for node in sorted_nodes:
        lines.append(f"  - {node.get('name', 'unnamed')} ({node.get('service_type', '?')}) — ${node.get('cost', 0):.2f}/mo [{node.get('status', '?')}]")

    return "\n".join(lines)


def _build_coverage_summary(coverage: Dict[str, Any]) -> str:
    if not coverage:
        return "Coverage data not available."

    detected = coverage.get("detected_services", [])
    missing = coverage.get("missing_services", [])
    access_denied = coverage.get("access_denied_services", [])

    lines = [
        f"Detected services: {len(detected)} ({', '.join(s.upper() for s in detected[:10])})",
        f"Missing services: {len(missing)} ({', '.join(s.upper() for s in missing)})" if missing else "All baseline services detected.",
        f"Access denied: {len(access_denied)} ({', '.join(s.upper() for s in access_denied)})" if access_denied else "",
    ]
    return "\n".join(line for line in lines if line)


def _build_proposed_summary(proposed: Dict[str, Any]) -> str:
    if not proposed:
        return "No optimization proposal."

    changes = proposed.get("change_list", [])
    savings = proposed.get("estimated_savings", 0)
    risk = proposed.get("risk_tradeoffs", "")

    lines = [
        f"Estimated monthly savings: ${savings:.2f}",
        f"Changes proposed: {len(changes)}",
        f"Risk assessment: {risk}" if risk else "",
    ]

    for change in changes[:5]:
        lines.append(
            f"  - {change.get('resource_name', '?')}: {change.get('change_type', '?')} "
            f"({change.get('current_state', '?')} → {change.get('proposed_state', '?')}) "
            f"— saves ${change.get('monthly_savings', 0):.2f}/mo [{change.get('risk_level', '?')} risk]"
        )

    return "\n".join(line for line in lines if line)
