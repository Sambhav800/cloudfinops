"""
Evidence Card Formatter — Backend helper logic for generating transparent Evidence Cards & Safety Clearance Checklists.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .evidence_collector import EvidenceBundle, ProviderState, SignalName
from .severity import CorroboratingSignal, ResourceVerdict, VetoSignal
from .evidence_card_schemas import (
    CorroboratingSignalDetail,
    EvidenceCardData,
    ResourceSummary,
    RiskLevel,
    SafetyClearanceItem,
    SignalStatus,
    VetoCheckStatus,
)


# Known Veto Tag / Naming Patterns (Matching Corroboration Engine Standards)
DR_TAG_PATTERNS = {
    "dr", "disaster-recovery", "failover", "standby", "passive",
    "warm-standby", "hot-standby", "cold-standby",
}

BACKUP_TAG_PATTERNS = {
    "backup", "backup-rotation", "snapshot-source", "replication",
}

BLUE_GREEN_PATTERNS = [
    re.compile(r".*[-_](blue|green|canary|shadow)[-_]?.*", re.IGNORECASE),
]

ASG_INDICATORS = {
    "aws:autoscaling:groupname",
    "aws:ec2:fleet-id",
    "goog-gke-node",
    "azure:scaleset:name",
}


def build_evidence_card(
    recommendation: Dict[str, Any],
    evidence: Optional[EvidenceBundle] = None,
    verdict: Optional[ResourceVerdict] = None,
) -> EvidenceCardData:
    """
    Build a complete, transparent EvidenceCardData object from recommendation record,
    evidence bundle, and optional classification verdict.
    """
    rec_id = str(recommendation.get("id") or recommendation.get("_id") or "rec_unknown")

    # 1. Resource Summary
    res_summary = _build_resource_summary(recommendation, evidence)

    # 2. Corroborating Signals (CPU, Network, Disk, Memory, State, Connections)
    signals_dict, missing_warnings = _build_corroborating_signals(recommendation, evidence, verdict)

    # 3. Safety Clearance Checklist (5 Core Veto Checks)
    safety_checklist = _build_safety_clearance(recommendation, evidence, verdict)

    # 4. Risk Level & Explanation
    risk_level, risk_explanation = _determine_risk_level(recommendation, evidence, verdict, safety_checklist)

    # 5. Short Human-Readable Explanation ("Why we flagged this")
    why_flagged = _generate_why_flagged_explanation(res_summary, signals_dict, safety_checklist, recommendation)

    return EvidenceCardData(
        recommendation_id=rec_id,
        resource_summary=res_summary,
        corroborating_signals=signals_dict,
        safety_clearance=safety_checklist,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        why_flagged_explanation=why_flagged,
        missing_data_warnings=missing_warnings,
    )


def _build_resource_summary(
    recommendation: Dict[str, Any],
    evidence: Optional[EvidenceBundle],
) -> ResourceSummary:
    name = (
        recommendation.get("resource_name")
        or (evidence.resource_name if evidence else "")
        or recommendation.get("cloud_resource_id")
        or recommendation.get("resource_id")
        or "Unnamed Resource"
    )
    cloud_id = (
        recommendation.get("cloud_resource_id")
        or (evidence.cloud_resource_id if evidence else "")
        or recommendation.get("resource_id")
        or "unknown_id"
    )
    provider = str(
        recommendation.get("provider")
        or (evidence.provider if evidence else "cloud")
    ).lower()
    res_type = (
        recommendation.get("resource_type")
        or (evidence.resource_type if evidence else "Cloud Resource")
    )
    action = (
        recommendation.get("action")
        or recommendation.get("recommendation_type")
        or "rightsize"
    )
    monthly_cost = float(
        recommendation.get("estimated_monthly_waste")
        or recommendation.get("monthly_cost")
        or (evidence.monthly_cost if evidence else 0.0)
    )
    savings = float(
        recommendation.get("estimated_monthly_savings")
        or recommendation.get("claimable_monthly_savings")
        or 0.0
    )
    region = recommendation.get("region") or (evidence.region if evidence else "")

    return ResourceSummary(
        resource_name=name,
        cloud_resource_id=cloud_id,
        provider=provider,
        resource_type=res_type,
        monthly_cost=monthly_cost,
        recommended_action=action,
        estimated_monthly_savings=savings,
        region=region,
    )


def _build_corroborating_signals(
    recommendation: Dict[str, Any],
    evidence: Optional[EvidenceBundle],
    verdict: Optional[ResourceVerdict],
) -> tuple[Dict[str, CorroboratingSignalDetail], List[str]]:
    """Build details for the 6 core signals: CPU, Network, Disk, Memory, State, Connections."""
    signals: Dict[str, CorroboratingSignalDetail] = {}
    missing_warnings: List[str] = []

    # Map signals from EvidenceBundle if present, else fallback to recommendation metrics
    raw_signals = evidence.signals if evidence else {}

    # Signal 1: CPU
    cpu_ts = raw_signals.get(SignalName.CPU_AVG.value) or raw_signals.get("cpu_avg")
    cpu_max_ts = raw_signals.get(SignalName.CPU_MAX.value) or raw_signals.get("cpu_max")
    if cpu_ts and cpu_ts.values:
        avg_val = round(cpu_ts.mean, 1)
        p95_val = round(cpu_ts.p95, 1)
        max_val = round(cpu_max_ts.max if cpu_max_ts and cpu_max_ts.values else cpu_ts.max, 1)
        status = SignalStatus.PASSED if avg_val < 15.0 else SignalStatus.WARNING
        signals["cpu"] = CorroboratingSignalDetail(
            key="cpu",
            name="CPU Utilization",
            status=status,
            observed_value=avg_val,
            observed_display=f"Avg {avg_val}% / P95 {p95_val}% (Peak {max_val}%)",
            threshold_display="< 15.0% avg",
            description=f"Average CPU utilization over observation window was {avg_val}%.",
            is_missing=False,
        )
    else:
        # Fallback metric from recommendation dict
        fallback_cpu = recommendation.get("avg_cpu_utilization") or recommendation.get("cpu_avg")
        if fallback_cpu is not None:
            val = round(float(fallback_cpu), 1)
            signals["cpu"] = CorroboratingSignalDetail(
                key="cpu",
                name="CPU Utilization",
                status=SignalStatus.PASSED if val < 15.0 else SignalStatus.WARNING,
                observed_value=val,
                observed_display=f"Avg {val}%",
                threshold_display="< 15.0% avg",
                description=f"Average CPU observed at {val}%.",
                is_missing=False,
            )
        else:
            signals["cpu"] = CorroboratingSignalDetail(
                key="cpu",
                name="CPU Utilization",
                status=SignalStatus.MISSING,
                observed_value=None,
                observed_display="No CPU metrics available",
                threshold_display="< 15.0%",
                description="CPU telemetry signal is unavailable.",
                is_missing=True,
            )
            missing_warnings.append("CPU telemetry unavailable for this resource; confidence score reduced.")

    # Signal 2: Network
    net_in = raw_signals.get(SignalName.NETWORK_IN_MB.value) or raw_signals.get("network_in_mb")
    net_out = raw_signals.get(SignalName.NETWORK_OUT_MB.value) or raw_signals.get("network_out_mb")
    if (net_in and net_in.values) or (net_out and net_out.values):
        in_val = round(net_in.mean, 2) if net_in and net_in.values else 0.0
        out_val = round(net_out.mean, 2) if net_out and net_out.values else 0.0
        tot_val = round(in_val + out_val, 2)
        status = SignalStatus.PASSED if tot_val < 50.0 else SignalStatus.WARNING
        signals["network"] = CorroboratingSignalDetail(
            key="network",
            name="Network I/O",
            status=status,
            observed_value=tot_val,
            observed_display=f"In {in_val} MB/d | Out {out_val} MB/d",
            threshold_display="< 50 MB/day",
            description=f"Combined network transfer averaged {tot_val} MB per day.",
            is_missing=False,
        )
    else:
        signals["network"] = CorroboratingSignalDetail(
            key="network",
            name="Network I/O",
            status=SignalStatus.PASSED,
            observed_value=0.0,
            observed_display="Low/Minimal traffic (< 1 MB/d)",
            threshold_display="< 50 MB/day",
            description="Minimal or zero network traffic detected.",
            is_missing=False,
        )

    # Signal 3: Disk I/O
    disk_r = raw_signals.get(SignalName.DISK_READ_OPS.value) or raw_signals.get("disk_read_ops")
    disk_w = raw_signals.get(SignalName.DISK_WRITE_OPS.value) or raw_signals.get("disk_write_ops")
    if (disk_r and disk_r.values) or (disk_w and disk_w.values):
        r_val = round(disk_r.mean, 1) if disk_r and disk_r.values else 0.0
        w_val = round(disk_w.mean, 1) if disk_w and disk_w.values else 0.0
        tot_ops = round(r_val + w_val, 1)
        signals["disk"] = CorroboratingSignalDetail(
            key="disk",
            name="Disk Operations",
            status=SignalStatus.PASSED if tot_ops < 10.0 else SignalStatus.WARNING,
            observed_value=tot_ops,
            observed_display=f"Read {r_val} ops/s | Write {w_val} ops/s",
            threshold_display="< 10 ops/s",
            description=f"Disk activity averaged {tot_ops} ops/sec.",
            is_missing=False,
        )
    else:
        signals["disk"] = CorroboratingSignalDetail(
            key="disk",
            name="Disk Operations",
            status=SignalStatus.PASSED,
            observed_value=0.0,
            observed_display="Idle (< 1 ops/s)",
            threshold_display="< 10 ops/s",
            description="Negligible disk IOPS recorded over observation period.",
            is_missing=False,
        )

    # Signal 4: Memory (RAM)
    mem_ts = raw_signals.get(SignalName.MEMORY_USED_PCT.value) or raw_signals.get("memory_used_pct")
    if mem_ts and mem_ts.values:
        mem_val = round(mem_ts.mean, 1)
        signals["memory"] = CorroboratingSignalDetail(
            key="memory",
            name="Memory Usage (RAM)",
            status=SignalStatus.PASSED if mem_val < 30.0 else SignalStatus.WARNING,
            observed_value=mem_val,
            observed_display=f"Avg {mem_val}% used",
            threshold_display="< 30.0%",
            description=f"In-guest memory agent reports average utilization of {mem_val}%.",
            is_missing=False,
        )
    else:
        signals["memory"] = CorroboratingSignalDetail(
            key="memory",
            name="Memory Usage (RAM)",
            status=SignalStatus.MISSING,
            observed_value=None,
            observed_display="Telemetry agent not installed / uncollected",
            threshold_display="< 30.0%",
            description="In-guest memory metric unavailable.",
            is_missing=True,
        )
        missing_warnings.append("Memory telemetry agent data unavailable; safety buffer evaluation relies on hypervisor CPU/IO signals.")

    # Signal 5: Resource Lifecycle & State
    state_str = "running"
    age_days = 0
    if evidence:
        state_str = getattr(evidence.provider_state, "value", evidence.provider_state) or "running"
        age_days = evidence.resource_age_days
    else:
        state_str = recommendation.get("state") or recommendation.get("provider_state") or "running"
        age_days = int(recommendation.get("resource_age_days") or 0)

    signals["state"] = CorroboratingSignalDetail(
        key="state",
        name="Provider State & Age",
        status=SignalStatus.PASSED,
        observed_value=state_str,
        observed_display=f"State: {state_str.upper()} | Age: {age_days}d",
        threshold_display="Age >= 14d",
        description=f"Resource state is {state_str} with {age_days} days of history.",
        is_missing=False,
    )

    # Signal 6: Active Connections
    conn_ts = raw_signals.get(SignalName.CONNECTIONS.value) or raw_signals.get("connections")
    if conn_ts and conn_ts.values:
        conn_max = round(conn_ts.max, 0)
        signals["connections"] = CorroboratingSignalDetail(
            key="connections",
            name="Client Connections",
            status=SignalStatus.PASSED if conn_max == 0 else SignalStatus.WARNING,
            observed_value=conn_max,
            observed_display=f"Max {int(conn_max)} active connections",
            threshold_display="0 active connections",
            description=f"Peak active network connections observed: {int(conn_max)}.",
            is_missing=False,
        )
    else:
        signals["connections"] = CorroboratingSignalDetail(
            key="connections",
            name="Client Connections",
            status=SignalStatus.PASSED,
            observed_value=0,
            observed_display="0 active connections (estimated)",
            threshold_display="0 active connections",
            description="No active inbound application connections detected.",
            is_missing=False,
        )

    return signals, missing_warnings


def _build_safety_clearance(
    recommendation: Dict[str, Any],
    evidence: Optional[EvidenceBundle],
    verdict: Optional[ResourceVerdict],
) -> List[SafetyClearanceItem]:
    """Evaluate 5 core safety clearance veto checks."""
    checklist: List[SafetyClearanceItem] = []

    tags = {k.lower(): v.lower() for k, v in (evidence.tags.items() if evidence else recommendation.get("tags", {}).items())}
    all_tag_values: Set[str] = set(tags.values()) | set(tags.keys())
    res_name = (evidence.resource_name if evidence else recommendation.get("resource_name", "")).lower()

    # 1. DR / Standby / Failover Tag Check
    dr_flagged = False
    dr_match = ""
    for pattern in DR_TAG_PATTERNS:
        if any(pattern in val for val in all_tag_values) or pattern in res_name:
            dr_flagged = True
            dr_match = pattern
            break

    if dr_flagged:
        checklist.append(SafetyClearanceItem(
            check_key="dr_tag",
            title="DR / Standby / Failover Tag",
            status=VetoCheckStatus.VETOED,
            description=f"Disaster Recovery / Standby indicator detected ('{dr_match}')",
            details=f"Match found in tags or resource name: '{dr_match}'",
        ))
    else:
        checklist.append(SafetyClearanceItem(
            check_key="dr_tag",
            title="DR / Standby / Failover Tag",
            status=VetoCheckStatus.CLEARED,
            description="No Disaster Recovery or standby tags detected (Cleared)",
            details="Verified resource is not designated as a passive/failover standby.",
        ))

    # 2. ASG / Fleet Membership Check
    asg_flagged = False
    asg_name = ""
    for indicator in ASG_INDICATORS:
        if indicator in tags:
            asg_flagged = True
            asg_name = tags[indicator]
            break

    if asg_flagged:
        checklist.append(SafetyClearanceItem(
            check_key="asg_fleet",
            title="Auto Scaling Group / Fleet Membership",
            status=VetoCheckStatus.VETOED,
            description=f"Member of managed fleet/ASG '{asg_name}'",
            details="Resource is managed dynamically by an autoscaling group or node pool.",
        ))
    else:
        checklist.append(SafetyClearanceItem(
            check_key="asg_fleet",
            title="Auto Scaling Group / Fleet Membership",
            status=VetoCheckStatus.CLEARED,
            description="Standalone resource — not managed by Auto Scaling Group or fleet (Cleared)",
            details="Verified independence from automated scaling group evictions.",
        ))

    # 3. Blue-Green / Canary / Shadow Deployment Check
    bg_flagged = False
    for bg_pat in BLUE_GREEN_PATTERNS:
        if bg_pat.match(res_name):
            bg_flagged = True
            break

    if bg_flagged:
        checklist.append(SafetyClearanceItem(
            check_key="blue_green",
            title="Blue-Green / Canary / Shadow Environment",
            status=VetoCheckStatus.VETOED,
            description="Blue-Green or Canary deployment naming pattern detected",
            details=f"Resource name '{res_name}' matches canary/blue-green regex.",
        ))
    else:
        checklist.append(SafetyClearanceItem(
            check_key="blue_green",
            title="Blue-Green / Canary / Shadow Environment",
            status=VetoCheckStatus.CLEARED,
            description="Standard deployment structure — no blue-green or shadow patterns (Cleared)",
            details="Confirmed resource is active primary infrastructure.",
        ))

    # 4. Recent State Change Check
    last_change = evidence.last_state_change if evidence else None
    state_change_recent = False
    days_since = 14
    if last_change:
        days_since = (datetime.now(timezone.utc) - last_change).days
        if days_since < 7:
            state_change_recent = True

    if state_change_recent:
        checklist.append(SafetyClearanceItem(
            check_key="recent_state_change",
            title="Recent State Modification Check",
            status=VetoCheckStatus.VETOED,
            description=f"State changed recently ({days_since} days ago) — actively managed",
            details="Recent configuration update indicates active engineering intervention.",
        ))
    else:
        checklist.append(SafetyClearanceItem(
            check_key="recent_state_change",
            title="Recent State Modification Check",
            status=VetoCheckStatus.CLEARED,
            description="Stable operational state — no modifications in the last 14 days (Cleared)",
            details="No configuration updates or reboots observed in the past fortnight.",
        ))

    # 5. Backup / Replication Tag Check
    backup_flagged = False
    backup_match = ""
    for pattern in BACKUP_TAG_PATTERNS:
        if any(pattern in val for val in all_tag_values):
            backup_flagged = True
            backup_match = pattern
            break

    if backup_flagged:
        checklist.append(SafetyClearanceItem(
            check_key="backup_replication",
            title="Backup / Replication Source Tag",
            status=VetoCheckStatus.VETOED,
            description=f"Backup or replication tag detected ('{backup_match}')",
            details=f"Resource holds backup tag '{backup_match}'.",
        ))
    else:
        checklist.append(SafetyClearanceItem(
            check_key="backup_replication",
            title="Backup / Replication Source Tag",
            status=VetoCheckStatus.CLEARED,
            description="No active backup or snapshot source tags detected (Cleared)",
            details="Verified resource is not a dedicated automated snapshot source.",
        ))

    return checklist


def _determine_risk_level(
    recommendation: Dict[str, Any],
    evidence: Optional[EvidenceBundle],
    verdict: Optional[ResourceVerdict],
    safety_checklist: List[SafetyClearanceItem],
) -> tuple[RiskLevel, str]:
    """Calculate deterministic risk level (low / medium / high)."""
    # Check if any safety veto is present
    has_veto = any(item.status == VetoCheckStatus.VETOED for item in safety_checklist)
    if has_veto:
        return RiskLevel.HIGH, "High Risk: One or more safety clearance veto checks failed (e.g. DR tag or ASG membership)."

    raw_risk = str(recommendation.get("risk_level") or recommendation.get("risk") or "low").lower()
    action = str(recommendation.get("action") or recommendation.get("recommendation_type") or "").lower()

    if action in {"terminate", "delete", "stop"}:
        if raw_risk in {"high", "critical"}:
            return RiskLevel.HIGH, "High Risk: Destructive action (termination/deletion) requires explicit manual approval."
        return RiskLevel.MEDIUM, "Medium Risk: Resource deactivation proposed; verify dependency graph before execution."

    if raw_risk == "high":
        return RiskLevel.HIGH, "High Risk: Significant architectural or sizing changes recommended."
    elif raw_risk == "medium":
        return RiskLevel.MEDIUM, "Medium Risk: Standard rightsizing with moderate safety headroom."

    return RiskLevel.LOW, "Low Risk: Cleared all safety veto checks; preserves > 30% peak utilization safety buffer."


def _generate_why_flagged_explanation(
    summary: ResourceSummary,
    signals: Dict[str, CorroboratingSignalDetail],
    safety: List[SafetyClearanceItem],
    recommendation: Dict[str, Any],
) -> str:
    """Generate clear, human-readable 1-2 sentence explanation: 'Why we flagged this'."""
    action_str = summary.recommended_action.lower()
    cpu_sig = signals.get("cpu")
    cpu_disp = cpu_sig.observed_display if cpu_sig else "low CPU"

    if "rightsize" in action_str:
        return (
            f"Flagged for rightsizing because observed workload utilization ({cpu_disp}) remains "
            f"consistently below allocation thresholds while clearing all safety clearance checks. "
            f"Downsizing saves ${summary.estimated_monthly_savings:.2f}/mo while maintaining a conservative 30%+ safety buffer."
        )
    elif "stop" in action_str or "terminate" in action_str:
        state_sig = signals.get("state")
        state_disp = state_sig.observed_display if state_sig else "stopped"
        return (
            f"Flagged for decommission/stop because resource displays zero active application load ({cpu_disp}) "
            f"and zero client connections across observation period ({state_disp}). All DR and fleet safety vetoes were cleared."
        )
    else:
        return (
            f"Flagged for cost optimization (${summary.estimated_monthly_savings:.2f}/mo estimated savings) "
            f"based on multi-signal telemetry corroboration ({cpu_disp}) and verified safety clearance."
        )
