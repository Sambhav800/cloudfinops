"""
Deterministic policy evaluation for shift-left simulator results.

No external calls, no LLM dependency, and no mutation. The policy result is
advisory metadata that callers can display or use in CI/CD integrations.
"""

from typing import Dict, List, Optional


DEFAULT_POLICY = {
    "monthly_delta_threshold_usd": 500.0,
    "annual_delta_threshold_usd": 6000.0,
    "min_exact_coverage_pct": 50.0,
    "max_unestimated_resources": 5,
    "block_on_critical_finding": True,
}


def evaluate_policy(
    monthly: Dict[str, float],
    annual: Dict[str, float],
    summary: Dict[str, int],
    findings: List[Dict[str, object]],
    policy: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Evaluate deterministic cost policy rules against a simulator result."""
    merged_policy = {**DEFAULT_POLICY, **(policy or {})}

    warnings: List[str] = []
    blocking_reasons: List[str] = []

    monthly_delta = float(monthly.get("delta", 0.0) or 0.0)
    monthly_threshold = float(merged_policy["monthly_delta_threshold_usd"])
    if monthly_delta > monthly_threshold:
        blocking_reasons.append(
            f"Monthly cost increase ${monthly_delta:.2f} exceeds threshold ${monthly_threshold:.2f}"
        )

    annual_delta = float(annual.get("delta", 0.0) or 0.0)
    annual_threshold = float(merged_policy["annual_delta_threshold_usd"])
    if annual_delta > annual_threshold:
        blocking_reasons.append(
            f"Annual cost increase ${annual_delta:.2f} exceeds threshold ${annual_threshold:.2f}"
        )

    total_resources = int(summary.get("total_resources", 0) or 0)
    exact_resources = int(summary.get("exact_resources", 0) or 0)
    exact_pct = (exact_resources / total_resources * 100.0) if total_resources > 0 else 100.0
    min_exact_pct = float(merged_policy["min_exact_coverage_pct"])
    if exact_pct < min_exact_pct:
        warnings.append(
            f"Only {exact_pct:.1f}% of resources have exact pricing. Estimate confidence is low."
        )

    unestimated_count = int(summary.get("unestimated_resources", 0) or 0)
    max_unestimated = int(merged_policy["max_unestimated_resources"])
    if unestimated_count > max_unestimated:
        warnings.append(
            f"{unestimated_count} resources could not be priced. Actual cost may differ significantly."
        )

    if bool(merged_policy["block_on_critical_finding"]):
        for finding in findings:
            if finding.get("severity") == "critical":
                address = str(finding.get("resource_address") or "unknown")
                evidence = str(finding.get("evidence") or "critical simulator finding")
                blocking_reasons.append(f"Critical finding on {address}: {evidence}")

    status = "fail" if blocking_reasons else ("warn" if warnings else "pass")
    lines = [f"## Cost policy: {status.upper()}\n"]
    if blocking_reasons:
        lines.append("### Blocking\n" + "\n".join(f"- {reason}" for reason in blocking_reasons))
    if warnings:
        lines.append("### Warnings\n" + "\n".join(f"- {warning}" for warning in warnings))
    if status == "pass":
        lines.append("All policy checks passed.")

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "markdown_summary": "\n".join(lines),
    }
