"""
Evidence Collection Layer — Unified signal model for multi-cloud resource classification.

Every provider-specific metrics client (aws_metrics, azure_metrics, gcp_metrics)
produces an EvidenceBundle per resource. The classification pipeline consumes these
bundles without knowing which cloud they came from.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalName(str, Enum):
    CPU_AVG = "cpu_avg"
    CPU_MAX = "cpu_max"
    NETWORK_IN_MB = "network_in_mb"
    NETWORK_OUT_MB = "network_out_mb"
    DISK_READ_OPS = "disk_read_ops"
    DISK_WRITE_OPS = "disk_write_ops"
    MEMORY_USED_PCT = "memory_used_pct"
    CONNECTIONS = "connections"


class ProviderState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    DEALLOCATED = "deallocated"
    SUSPENDED = "suspended"


@dataclass
class SignalTimeSeries:
    """A single metric's time-series data with precomputed statistics."""

    metric_name: str
    values: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    interval: timedelta = field(default_factory=lambda: timedelta(hours=1))
    aggregation: str = "avg"

    mean: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    max: float = 0.0
    min: float = 0.0
    std: float = 0.0
    coefficient_of_variation: float = 0.0

    def compute_statistics(self) -> None:
        """Compute summary statistics from raw values."""
        if not self.values:
            return

        n = len(self.values)
        sorted_vals = sorted(self.values)

        self.mean = sum(self.values) / n
        self.min = sorted_vals[0]
        self.max = sorted_vals[-1]
        self.p50 = self._percentile(sorted_vals, 50)
        self.p90 = self._percentile(sorted_vals, 90)
        self.p95 = self._percentile(sorted_vals, 95)
        self.p99 = self._percentile(sorted_vals, 99)

        if n > 1:
            variance = sum((v - self.mean) ** 2 for v in self.values) / (n - 1)
            self.std = math.sqrt(variance)
        else:
            self.std = 0.0

        if self.mean > 0:
            self.coefficient_of_variation = self.std / self.mean
        else:
            self.coefficient_of_variation = 0.0

    @staticmethod
    def _percentile(sorted_values: List[float], pct: int) -> float:
        """Compute percentile from pre-sorted list."""
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        idx = (pct / 100.0) * (n - 1)
        lower = int(idx)
        upper = min(lower + 1, n - 1)
        frac = idx - lower
        return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


@dataclass
class ResourceRelationship:
    """A relationship edge to another resource."""

    kind: str  # failover_for, member_of_asg, blue_green_pair, etc.
    target_resource_id: str
    target_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceBundle:
    """
    Complete evidence package for a single resource.

    Produced by provider-specific metrics collectors.
    Consumed by the classification pipeline without provider awareness.
    """

    resource_id: str
    provider: str  # aws | azure | gcp
    resource_type: str  # service_type value (e.g., "AWS EC2 Instance")
    collection_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Raw signals keyed by SignalName
    signals: Dict[str, SignalTimeSeries] = field(default_factory=dict)

    # Metadata context
    tags: Dict[str, str] = field(default_factory=dict)
    relationships: List[ResourceRelationship] = field(default_factory=list)
    resource_age_days: int = 0
    last_state_change: Optional[datetime] = None

    # Provider-specific state
    provider_state: ProviderState = ProviderState.RUNNING

    # Data quality indicators
    observation_days: int = 0
    data_completeness: float = 0.0  # 0.0-1.0: fraction of expected data points present

    # Cost context
    monthly_cost: float = 0.0
    cost_source: str = "unknown"  # actual | catalog_estimate | billing_unavailable

    # Resource identity for deduplication
    resource_name: str = ""
    region: str = ""
    cloud_resource_id: str = ""

    @property
    def has_sufficient_data(self) -> bool:
        """Whether we have enough data for confident classification."""
        return self.observation_days >= 7 and self.data_completeness >= 0.5

    @property
    def has_pattern_data(self) -> bool:
        """Whether we have enough data for pattern analysis (30+ days)."""
        return self.observation_days >= 30 and self.data_completeness >= 0.7

    @property
    def is_new_resource(self) -> bool:
        """Resources < 14 days old should not be classified as waste."""
        return self.resource_age_days < 14

    @property
    def signal_count(self) -> int:
        """Number of signals with actual data."""
        return sum(
            1 for s in self.signals.values()
            if s.values and len(s.values) > 0
        )


def build_evidence_bundle(
    resource_id: str,
    provider: str,
    resource_type: str,
    provider_state: str,
    signals: Dict[str, SignalTimeSeries],
    tags: Optional[Dict[str, str]] = None,
    resource_age_days: int = 0,
    monthly_cost: float = 0.0,
    cost_source: str = "unknown",
    resource_name: str = "",
    region: str = "",
    cloud_resource_id: str = "",
    last_state_change: Optional[datetime] = None,
    relationships: Optional[List[ResourceRelationship]] = None,
) -> EvidenceBundle:
    """
    Factory function to build an EvidenceBundle with computed statistics.

    Computes observation_days and data_completeness from the longest signal
    time-series available. Calls compute_statistics() on each signal.
    """
    # Compute statistics for each signal
    for signal in signals.values():
        signal.compute_statistics()

    # Determine observation window from longest signal
    max_observation_days = 0
    total_completeness = 0.0
    signal_count = 0

    for signal in signals.values():
        if signal.values and signal.timestamps and len(signal.timestamps) >= 2:
            span = signal.timestamps[-1] - signal.timestamps[0]
            days = span.total_seconds() / 86400
            max_observation_days = max(max_observation_days, int(days))

            expected_points = days / (signal.interval.total_seconds() / 86400)
            if expected_points > 0:
                completeness = len(signal.values) / expected_points
                total_completeness += min(1.0, completeness)
                signal_count += 1

    avg_completeness = total_completeness / signal_count if signal_count > 0 else 0.0

    # Map provider state string to enum
    state_map = {
        "running": ProviderState.RUNNING,
        "stopped": ProviderState.STOPPED,
        "terminated": ProviderState.TERMINATED,
        "deallocated": ProviderState.DEALLOCATED,
        "suspended": ProviderState.SUSPENDED,
    }
    state_enum = state_map.get(provider_state.lower(), ProviderState.RUNNING)

    return EvidenceBundle(
        resource_id=resource_id,
        provider=provider,
        resource_type=resource_type,
        provider_state=state_enum,
        signals=signals,
        tags=tags or {},
        resource_age_days=resource_age_days,
        monthly_cost=monthly_cost,
        cost_source=cost_source,
        resource_name=resource_name,
        region=region,
        cloud_resource_id=cloud_resource_id,
        last_state_change=last_state_change,
        relationships=relationships or [],
        observation_days=max_observation_days,
        data_completeness=round(avg_completeness, 2),
    )
