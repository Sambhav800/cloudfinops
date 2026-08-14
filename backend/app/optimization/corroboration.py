"""
Corroboration Engine — Require 3+ independent signals before waste classification.

This is the primary false-positive prevention mechanism. No resource can be classified
as waste unless at least 3 independent signals agree AND no veto signal is present.

A single veto signal (DR tag, ASG membership, recent config change) immediately
protects the resource regardless of how many signals suggest waste.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .evidence_collector import EvidenceBundle, ProviderState, SignalName
from .confidence_model import ThresholdSet, DEFAULT_THRESHOLDS
from .severity import CorroboratingSignal, VetoSignal


MINIMUM_CORROBORATING_SIGNALS = 3

# Tags that indicate legitimate stopped/idle state
DR_TAG_PATTERNS = {
    "dr", "disaster-recovery", "failover", "standby", "passive",
    "warm-standby", "hot-standby", "cold-standby",
}

ENVIRONMENT_TAGS = {
    "dev", "development", "test", "testing", "staging", "sandbox",
    "qa", "uat", "demo", "playground",
}

BACKUP_TAG_PATTERNS = {
    "backup", "backup-rotation", "snapshot-source", "replication",
}

# Name patterns that suggest legitimate stopped state
DR_NAME_PATTERNS = [
    re.compile(r".*[-_](dr|failover|standby|passive|secondary)[-_]?.*", re.IGNORECASE),
    re.compile(r".*(disaster|recovery).*", re.IGNORECASE),
]

BLUE_GREEN_PATTERNS = [
    re.compile(r".*[-_](blue|green|canary|shadow)[-_]?.*", re.IGNORECASE),
]

ASG_INDICATORS = {
    "aws:autoscaling:groupName",
    "aws:ec2:fleet-id",
    "goog-gke-node",
}


@dataclass
class CorroborationResult:
    """Result of the corroboration check."""

    passed: bool
    corroborating_signals: List[CorroboratingSignal]
    vetoing_signals: List[VetoSignal]
    reason: str

    @property
    def corroboration_count(self) -> int:
        return len(self.corroborating_signals)

    @property
    def has_veto(self) -> bool:
        return len(self.vetoing_signals) > 0


def check_corroboration(
    evidence: EvidenceBundle,
    thresholds: Optional[ThresholdSet] = None,
) -> CorroborationResult:
    """
    Check whether a resource has sufficient corroborating signals for waste
    classification, and whether any veto signals block classification.

    Returns CorroborationResult with pass/fail, signals, and reason.
    """
    if thresholds is None:
        thresholds = ThresholdSet.default()

    corroborating: List[CorroboratingSignal] = []
    vetoing: List[VetoSignal] = []

    # === VETO CHECKS (any one blocks classification) ===
    _check_veto_signals(evidence, vetoing)

    # If any veto found, immediately return failure
    if vetoing:
        return CorroborationResult(
            passed=False,
            corroborating_signals=[],
            vetoing_signals=vetoing,
            reason=f"Veto: {vetoing[0].reason}",
        )

    # === CORROBORATING SIGNAL CHECKS ===
    _check_corroborating_signals(evidence, thresholds, corroborating)

    # Check minimum threshold
    if len(corroborating) >= MINIMUM_CORROBORATING_SIGNALS:
        return CorroborationResult(
            passed=True,
            corroborating_signals=corroborating,
            vetoing_signals=[],
            reason=f"{len(corroborating)} signals corroborate waste classification",
        )
    else:
        return CorroborationResult(
            passed=False,
            corroborating_signals=corroborating,
            vetoing_signals=[],
            reason=(
                f"Only {len(corroborating)}/{MINIMUM_CORROBORATING_SIGNALS} "
                f"signals corroborate — insufficient evidence"
            ),
        )


def _check_veto_signals(evidence: EvidenceBundle, vetoing: List[VetoSignal]) -> None:
    """Check all veto conditions. Any one is enough to block classification."""

    # Veto 1: Resource too new (< 14 days)
    if evidence.is_new_resource:
        vetoing.append(VetoSignal(
            reason=f"Resource is only {evidence.resource_age_days} days old (minimum 14)",
            signal_type="age",
        ))
        return  # Early return — no point checking more

    # Veto 2: DR/failover/standby tags
    tags_lower = {k.lower(): v.lower() for k, v in evidence.tags.items()}
    all_tag_values: Set[str] = set(tags_lower.values()) | set(tags_lower.keys())

    for pattern in DR_TAG_PATTERNS:
        if any(pattern in val for val in all_tag_values):
            vetoing.append(VetoSignal(
                reason=f"DR/failover tag detected: '{pattern}' found in tags",
                signal_type="tag",
                details=f"Tag value contains '{pattern}'",
            ))
            return

    # Veto 3: Auto Scaling Group membership
    for asg_key in ASG_INDICATORS:
        if asg_key in evidence.tags:
            vetoing.append(VetoSignal(
                reason=f"Member of auto-scaling group ({asg_key})",
                signal_type="relationship",
                details=evidence.tags[asg_key],
            ))
            return

    # Veto 4: Blue/green deployment pair
    for pattern in BLUE_GREEN_PATTERNS:
        if pattern.match(evidence.resource_name):
            vetoing.append(VetoSignal(
                reason=f"Blue/green deployment naming pattern detected",
                signal_type="naming",
                details=evidence.resource_name,
            ))
            return

    # Veto 5: DR naming pattern
    for pattern in DR_NAME_PATTERNS:
        if pattern.match(evidence.resource_name):
            vetoing.append(VetoSignal(
                reason=f"DR/failover naming pattern detected in resource name",
                signal_type="naming",
                details=evidence.resource_name,
            ))
            return

    # Veto 6: Relationship-based protection
    for rel in evidence.relationships:
        if rel.kind in ("failover_for", "member_of_asg", "dns_points_to"):
            vetoing.append(VetoSignal(
                reason=f"Protected by relationship: {rel.kind} → {rel.target_resource_id}",
                signal_type="relationship",
                details=f"{rel.kind}: {rel.target_resource_id}",
            ))
            return

    # Veto 7: Recent state change (< 7 days ago) — someone is managing this
    if evidence.last_state_change:
        from datetime import datetime, timezone
        days_since_change = (datetime.now(timezone.utc) - evidence.last_state_change).days
        if days_since_change < 7:
            vetoing.append(VetoSignal(
                reason=f"Recent state change ({days_since_change} days ago) — actively managed",
                signal_type="recency",
                details=f"Last change: {evidence.last_state_change.isoformat()}",
            ))
            return

    # Veto 8: Backup rotation tags
    for pattern in BACKUP_TAG_PATTERNS:
        if any(pattern in val for val in all_tag_values):
            vetoing.append(VetoSignal(
                reason=f"Backup/replication tag detected: '{pattern}'",
                signal_type="tag",
                details=f"Tag value contains '{pattern}'",
            ))
            return


def _check_corroborating_signals(
    evidence: EvidenceBundle,
    thresholds: ThresholdSet,
    corroborating: List[CorroboratingSignal],
) -> None:
    """Check all corroborating signals. Need 3+ for waste classification."""

    # Signal 1: CPU below threshold for observation window
    cpu_signal = evidence.signals.get(SignalName.CPU_AVG.value)
    if cpu_signal and cpu_signal.values:
        cpu_threshold = thresholds.get(SignalName.CPU_AVG.value)
        if cpu_signal.mean < cpu_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.CPU_AVG.value,
                observed_value=round(cpu_signal.mean, 2),
                threshold=cpu_threshold,
                description=f"Average CPU {cpu_signal.mean:.1f}% < {cpu_threshold}% threshold",
            ))

    # Signal 2: Network inbound below threshold
    net_in_signal = evidence.signals.get(SignalName.NETWORK_IN_MB.value)
    if net_in_signal and net_in_signal.values:
        net_threshold = thresholds.get(SignalName.NETWORK_IN_MB.value)
        if net_in_signal.mean < net_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.NETWORK_IN_MB.value,
                observed_value=round(net_in_signal.mean, 2),
                threshold=net_threshold,
                description=f"Network inbound {net_in_signal.mean:.1f}MB < {net_threshold}MB threshold",
            ))

    # Signal 3: Network outbound below threshold
    net_out_signal = evidence.signals.get(SignalName.NETWORK_OUT_MB.value)
    if net_out_signal and net_out_signal.values:
        net_out_threshold = thresholds.get(SignalName.NETWORK_OUT_MB.value)
        if net_out_signal.mean < net_out_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.NETWORK_OUT_MB.value,
                observed_value=round(net_out_signal.mean, 2),
                threshold=net_out_threshold,
                description=f"Network outbound {net_out_signal.mean:.1f}MB < {net_out_threshold}MB threshold",
            ))

    # Signal 4: Disk I/O below threshold
    disk_read = evidence.signals.get(SignalName.DISK_READ_OPS.value)
    disk_write = evidence.signals.get(SignalName.DISK_WRITE_OPS.value)
    disk_threshold = thresholds.get(SignalName.DISK_READ_OPS.value)

    total_disk_io = 0.0
    if disk_read and disk_read.values:
        total_disk_io += disk_read.mean
    if disk_write and disk_write.values:
        total_disk_io += disk_write.mean

    if (disk_read or disk_write) and total_disk_io < disk_threshold:
        corroborating.append(CorroboratingSignal(
            signal_name="disk_io_combined",
            observed_value=round(total_disk_io, 2),
            threshold=disk_threshold,
            description=f"Disk I/O {total_disk_io:.1f} ops < {disk_threshold} ops threshold",
        ))

    # Signal 5: Stopped/terminated state for extended period
    if evidence.provider_state in (
        ProviderState.STOPPED,
        ProviderState.TERMINATED,
        ProviderState.DEALLOCATED,
        ProviderState.SUSPENDED,
    ):
        if evidence.last_state_change:
            from datetime import datetime, timezone
            stopped_days = (datetime.now(timezone.utc) - evidence.last_state_change).days
        else:
            stopped_days = evidence.resource_age_days  # Assume stopped since creation

        if stopped_days >= 14:
            corroborating.append(CorroboratingSignal(
                signal_name="provider_state",
                observed_value=float(stopped_days),
                threshold=14.0,
                description=f"Resource {evidence.provider_state.value} for {stopped_days} days (threshold: 14)",
            ))

    # Signal 6: Max CPU also below elevated threshold (independent from avg)
    cpu_max_signal = evidence.signals.get(SignalName.CPU_MAX.value)
    if cpu_max_signal and cpu_max_signal.values:
        cpu_max_threshold = thresholds.get(SignalName.CPU_MAX.value)
        if cpu_max_signal.max < cpu_max_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.CPU_MAX.value,
                observed_value=round(cpu_max_signal.max, 2),
                threshold=cpu_max_threshold,
                description=f"Peak CPU {cpu_max_signal.max:.1f}% < {cpu_max_threshold}% (never spikes)",
            ))

    # Signal 7: Memory usage below threshold (where available)
    mem_signal = evidence.signals.get(SignalName.MEMORY_USED_PCT.value)
    if mem_signal and mem_signal.values:
        mem_threshold = thresholds.get(SignalName.MEMORY_USED_PCT.value)
        if mem_signal.mean < mem_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.MEMORY_USED_PCT.value,
                observed_value=round(mem_signal.mean, 2),
                threshold=mem_threshold,
                description=f"Memory usage {mem_signal.mean:.1f}% < {mem_threshold}% threshold",
            ))

    # Signal 8: No connections (where available)
    conn_signal = evidence.signals.get(SignalName.CONNECTIONS.value)
    if conn_signal and conn_signal.values:
        conn_threshold = thresholds.get(SignalName.CONNECTIONS.value)
        if conn_signal.max < conn_threshold:
            corroborating.append(CorroboratingSignal(
                signal_name=SignalName.CONNECTIONS.value,
                observed_value=round(conn_signal.max, 2),
                threshold=conn_threshold,
                description=f"Zero connections observed (max: {conn_signal.max:.0f})",
            ))
