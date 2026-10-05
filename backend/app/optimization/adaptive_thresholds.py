"""
Adaptive Thresholds — Fleet-calibrated detection thresholds that learn.

Static thresholds (2% CPU, 5MB network) don't work for every workload.
A bastion host at 1% CPU is normal. A GPU instance at 3% is idle.

This module calibrates thresholds from three sources:
1. Fleet P10 — P10 of active resources of the same type = new zombie threshold
2. User feedback — each dismissal nudges threshold upward (EMA, alpha=0.1)
3. Resource-type defaults — base thresholds per workload category

The result is a per-user, per-resource-type threshold set stored in MongoDB
and loaded at scan time by the OptimizationEngine.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .confidence_model import ThresholdSet, DEFAULT_THRESHOLDS
from .evidence_collector import SignalName

logger = logging.getLogger(__name__)

# Minimum fleet size for P10 calibration
MIN_FLEET_FOR_CALIBRATION = 10

# EMA alpha for feedback adjustment (10 dismissals to fully shift)
FEEDBACK_EMA_ALPHA = 0.1

# Absolute floor — never go below these regardless of calibration
ABSOLUTE_FLOOR_THRESHOLDS = {
    SignalName.CPU_AVG.value: 0.5,      # Never flag below 0.5% as the threshold
    SignalName.NETWORK_IN_MB.value: 0.5,
    SignalName.NETWORK_OUT_MB.value: 0.2,
    SignalName.DISK_READ_OPS.value: 1.0,
    SignalName.DISK_WRITE_OPS.value: 1.0,
    SignalName.MEMORY_USED_PCT.value: 5.0,
}

# Resource-type specific base thresholds
RESOURCE_TYPE_DEFAULTS: Dict[str, Dict[str, float]] = {
    "bastion": {
        SignalName.CPU_AVG.value: 0.5,
        SignalName.NETWORK_IN_MB.value: 0.5,
        SignalName.NETWORK_OUT_MB.value: 0.2,
        SignalName.DISK_READ_OPS.value: 1.0,
    },
    "web_server": {
        SignalName.CPU_AVG.value: 3.0,
        SignalName.NETWORK_IN_MB.value: 10.0,
        SignalName.NETWORK_OUT_MB.value: 5.0,
        SignalName.DISK_READ_OPS.value: 20.0,
    },
    "database": {
        SignalName.CPU_AVG.value: 2.0,
        SignalName.NETWORK_IN_MB.value: 5.0,
        SignalName.DISK_READ_OPS.value: 50.0,
        SignalName.DISK_WRITE_OPS.value: 20.0,
    },
    "gpu_training": {
        SignalName.CPU_AVG.value: 5.0,
        SignalName.NETWORK_IN_MB.value: 50.0,
        SignalName.NETWORK_OUT_MB.value: 50.0,
        SignalName.DISK_READ_OPS.value: 100.0,
    },
    "batch_processing": {
        SignalName.CPU_AVG.value: 1.0,
        SignalName.NETWORK_IN_MB.value: 2.0,
        SignalName.DISK_READ_OPS.value: 5.0,
    },
    "monitoring": {
        SignalName.CPU_AVG.value: 1.0,
        SignalName.NETWORK_IN_MB.value: 2.0,
        SignalName.NETWORK_OUT_MB.value: 1.0,
    },
    "cache": {
        SignalName.CPU_AVG.value: 2.0,
        SignalName.NETWORK_IN_MB.value: 20.0,
        SignalName.NETWORK_OUT_MB.value: 20.0,
        SignalName.MEMORY_USED_PCT.value: 15.0,
    },
}

# Heuristic mapping from service type / tags to resource category
CATEGORY_DETECTION_RULES = [
    ({"bastion", "jump", "jumpbox"}, "bastion"),
    ({"gpu", "training", "ml", "ai", "sagemaker"}, "gpu_training"),
    ({"rds", "database", "db", "postgres", "mysql", "mongo", "redis", "sql"}, "database"),
    ({"web", "nginx", "apache", "api", "frontend", "backend"}, "web_server"),
    ({"batch", "etl", "pipeline", "airflow", "glue"}, "batch_processing"),
    ({"monitor", "prometheus", "grafana", "datadog", "nagios"}, "monitoring"),
    ({"cache", "redis", "memcached", "elasticache", "cdn"}, "cache"),
]


@dataclass
class AdaptiveThresholdState:
    """Persistent state for a user's adaptive thresholds."""

    user_id: str
    provider: str = ""
    resource_type: str = ""
    thresholds: Dict[str, float] = field(default_factory=dict)
    source: str = "default"
    last_calibrated: Optional[datetime] = None
    sample_size: int = 0
    feedback_count: int = 0


class AdaptiveThresholdEngine:
    """
    Manages threshold calibration from fleet data and user feedback.

    Called by OptimizationEngine.initialize() to load the right thresholds
    before classification runs.
    """

    def __init__(self, db: Any = None):
        self.db = db

    async def get_thresholds(
        self,
        user_id: str,
        resource_type: str = "",
        provider: str = "",
        tags: Optional[Dict[str, str]] = None,
        service_type: str = "",
    ) -> ThresholdSet:
        """
        Get the best available thresholds for a resource classification.

        Priority:
        1. User-specific calibrated thresholds (from fleet or feedback)
        2. Resource-type specific defaults (from category detection)
        3. Global defaults

        Args:
            user_id: The user whose fleet we're calibrating for
            resource_type: Service type (e.g., "AWS EC2 Instance")
            provider: Cloud provider
            tags: Resource tags (for category inference)
            service_type: Specific service type string
        """
        # Try user-specific saved thresholds first
        if self.db:
            try:
                saved = await self.db.select(
                    "adaptive_thresholds",
                    filters={
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "provider": provider,
                    },
                )
                if saved and saved[0].get("thresholds"):
                    return ThresholdSet(
                        thresholds=saved[0]["thresholds"],
                        source=saved[0].get("source", "saved"),
                        sample_size=saved[0].get("sample_size", 0),
                    )
            except Exception:
                pass

        # Fall back to resource-type defaults
        category = detect_resource_category(service_type, tags or {})
        if category and category in RESOURCE_TYPE_DEFAULTS:
            base = dict(DEFAULT_THRESHOLDS)
            base.update({k: v for k, v in RESOURCE_TYPE_DEFAULTS[category].items()})
            return ThresholdSet(
                thresholds={k if isinstance(k, str) else k.value: v for k, v in base.items()},
                source=f"resource_type:{category}",
            )

        # Global defaults
        return ThresholdSet.default()

    async def calibrate_from_fleet(
        self,
        user_id: str,
        provider: str,
        resource_type: str,
    ) -> Optional[ThresholdSet]:
        """
        Calibrate thresholds from a user's fleet of active resources.

        Algorithm: P10 of active resources' utilization = zombie threshold.
        If the user's smallest actively-used instance runs at 5% CPU,
        then 5% is the new zombie threshold.

        Requires minimum 10 active resources of the same type.
        """
        if not self.db:
            return None

        try:
            # Get all active resources of this type for this user
            resources = await self.db.select(
                "resources",
                filters={
                    "user_id": user_id,
                    "provider": provider,
                    "service_type": resource_type,
                    "status": {"$in": ["Active", "healthy"]},
                },
            )

            if len(resources) < MIN_FLEET_FOR_CALIBRATION:
                return None

            # Extract signal values from metadata
            cpu_values = []
            net_values = []
            disk_values = []

            for r in resources:
                meta = r.get("metadata", {})
                metrics = r.get("metrics_data", {})

                # CPU from various sources
                cpu = meta.get("avg_cpu_7d") or metrics.get("cpu_avg")
                if cpu is not None and cpu > 0:
                    cpu_values.append(float(cpu))

                # Network
                net = metrics.get("network_in_mb")
                if net is not None and net > 0:
                    net_values.append(float(net))

                # Disk
                disk = metrics.get("disk_read_ops")
                if disk is not None and disk > 0:
                    disk_values.append(float(disk))

            # Compute P10 for each available signal
            thresholds = dict(DEFAULT_THRESHOLDS)

            if len(cpu_values) >= MIN_FLEET_FOR_CALIBRATION:
                p10_cpu = _percentile(cpu_values, 10)
                thresholds[SignalName.CPU_AVG.value] = max(
                    ABSOLUTE_FLOOR_THRESHOLDS[SignalName.CPU_AVG.value],
                    round(p10_cpu, 2),
                )

            if len(net_values) >= MIN_FLEET_FOR_CALIBRATION:
                p10_net = _percentile(net_values, 10)
                thresholds[SignalName.NETWORK_IN_MB.value] = max(
                    ABSOLUTE_FLOOR_THRESHOLDS[SignalName.NETWORK_IN_MB.value],
                    round(p10_net, 2),
                )

            if len(disk_values) >= MIN_FLEET_FOR_CALIBRATION:
                p10_disk = _percentile(disk_values, 10)
                thresholds[SignalName.DISK_READ_OPS.value] = max(
                    ABSOLUTE_FLOOR_THRESHOLDS[SignalName.DISK_READ_OPS.value],
                    round(p10_disk, 2),
                )

            result = ThresholdSet(
                thresholds={k if isinstance(k, str) else k.value: v for k, v in thresholds.items()},
                source="fleet_p10",
                last_calibrated=datetime.now(timezone.utc).isoformat(),
                sample_size=len(resources),
            )

            # Persist calibrated thresholds
            await self.db.upsert(
                "adaptive_thresholds",
                {
                    "user_id": user_id,
                    "provider": provider,
                    "resource_type": resource_type,
                    "thresholds": result.thresholds,
                    "source": "fleet_p10",
                    "last_calibrated": datetime.now(timezone.utc),
                    "sample_size": len(resources),
                },
            )

            logger.info(
                f"Fleet calibration for {user_id}/{provider}/{resource_type}: "
                f"CPU threshold={thresholds.get(SignalName.CPU_AVG.value, '?')}% "
                f"(from {len(cpu_values)} active resources)"
            )

            return result

        except Exception as e:
            logger.warning(f"Fleet calibration failed: {e}")
            return None

    async def adjust_from_feedback(
        self,
        user_id: str,
        provider: str,
        resource_type: str,
        signal_name: str,
        observed_value: float,
        action: str,
    ) -> None:
        """
        Adjust thresholds based on user feedback.

        When user dismisses a finding (false positive):
        - The resource's signal value was below our threshold (we thought it was waste)
        - But the user says it's not waste
        - So we need to LOWER our threshold below that value
        - Use EMA to avoid single dismissal causing too big a swing

        When user approves (true positive):
        - Reinforces current threshold — no adjustment needed
        """
        if action not in ("dismiss", "exclude"):
            return  # Only false positives adjust thresholds

        if not self.db:
            return

        try:
            # Load current thresholds
            current_set = await self.get_thresholds(user_id, resource_type, provider)
            current_value = current_set.get(signal_name)

            # EMA adjustment: move threshold toward (observed_value + buffer)
            # The buffer ensures we don't flag this exact value next time
            target = observed_value + (observed_value * 0.1)  # 10% above observed

            new_value = (1 - FEEDBACK_EMA_ALPHA) * current_value + FEEDBACK_EMA_ALPHA * target

            # Apply floor
            floor = ABSOLUTE_FLOOR_THRESHOLDS.get(signal_name, 0.5)
            new_value = max(floor, round(new_value, 2))

            # Update in DB
            current_thresholds = dict(current_set.thresholds)
            current_thresholds[signal_name] = new_value

            await self.db.upsert(
                "adaptive_thresholds",
                {
                    "user_id": user_id,
                    "provider": provider,
                    "resource_type": resource_type,
                    "thresholds": current_thresholds,
                    "source": "user_feedback",
                    "last_calibrated": datetime.now(timezone.utc),
                    "feedback_count": (current_set.sample_size or 0) + 1,
                },
            )

            logger.info(
                f"Threshold adjusted via feedback: {signal_name} "
                f"{current_value} → {new_value} for {user_id}/{resource_type}"
            )

        except Exception as e:
            logger.warning(f"Feedback threshold adjustment failed: {e}")


def detect_resource_category(
    service_type: str,
    tags: Dict[str, str],
) -> Optional[str]:
    """
    Detect the resource category from service type and tags.

    Used to select appropriate default thresholds.
    """
    # Combine all searchable text
    search_text = service_type.lower()
    for k, v in tags.items():
        search_text += f" {k.lower()} {v.lower()}"

    # Check each category rule
    for keywords, category in CATEGORY_DETECTION_RULES:
        if any(kw in search_text for kw in keywords):
            return category

    return None


def _percentile(data: List[float], pct: float) -> float:
    """Compute percentile from unsorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    idx = (pct / 100.0) * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac
