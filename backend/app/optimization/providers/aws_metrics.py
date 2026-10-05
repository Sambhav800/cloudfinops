"""
AWS Metrics Provider — CloudWatch multi-signal collection for EC2 instances.

Fetches CPU, Network (In/Out), Disk I/O, and 30-day hourly CPU for pattern analysis.
Returns EvidenceBundle for consumption by the classification pipeline.

This replaces the single-signal CPU fetch in aws.py (line 1112-1135) with a
comprehensive multi-signal collection that feeds the optimization engine.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..optimization.evidence_collector import (
    EvidenceBundle,
    SignalName,
    SignalTimeSeries,
    build_evidence_bundle,
)

logger = logging.getLogger(__name__)

# CloudWatch metric definitions for EC2
EC2_METRICS = {
    SignalName.CPU_AVG: {
        "namespace": "AWS/EC2",
        "metric_name": "CPUUtilization",
        "statistic": "Average",
    },
    SignalName.CPU_MAX: {
        "namespace": "AWS/EC2",
        "metric_name": "CPUUtilization",
        "statistic": "Maximum",
    },
    SignalName.NETWORK_IN_MB: {
        "namespace": "AWS/EC2",
        "metric_name": "NetworkIn",
        "statistic": "Sum",
        "divisor": 1_048_576,  # bytes to MB
    },
    SignalName.NETWORK_OUT_MB: {
        "namespace": "AWS/EC2",
        "metric_name": "NetworkOut",
        "statistic": "Sum",
        "divisor": 1_048_576,
    },
    SignalName.DISK_READ_OPS: {
        "namespace": "AWS/EC2",
        "metric_name": "DiskReadOps",
        "statistic": "Sum",
    },
    SignalName.DISK_WRITE_OPS: {
        "namespace": "AWS/EC2",
        "metric_name": "DiskWriteOps",
        "statistic": "Sum",
    },
}


def collect_ec2_evidence(
    cw_client: Any,
    instance_id: str,
    instance_meta: Dict[str, Any],
    days: int = 7,
) -> Dict[str, SignalTimeSeries]:
    """
    Collect multi-signal metrics from CloudWatch for an EC2 instance.

    Args:
        cw_client: boto3 CloudWatch client
        instance_id: EC2 instance ID
        instance_meta: Instance metadata dict (from scanner)
        days: Number of days to look back (default 7 for immediate, 30 for patterns)

    Returns:
        Dict mapping signal names to SignalTimeSeries
    """
    signals: Dict[str, SignalTimeSeries] = {}
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    period = 86400 if days <= 7 else 3600  # Daily for 7d, hourly for 30d

    dimensions = [{"Name": "InstanceId", "Value": instance_id}]

    for signal_name, metric_def in EC2_METRICS.items():
        try:
            response = cw_client.get_metric_statistics(
                Namespace=metric_def["namespace"],
                MetricName=metric_def["metric_name"],
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=[metric_def["statistic"]],
            )

            datapoints = response.get("Datapoints", [])
            if not datapoints:
                continue

            # Sort by timestamp
            datapoints.sort(key=lambda dp: dp["Timestamp"])

            # Extract values and timestamps
            stat_key = metric_def["statistic"]
            divisor = metric_def.get("divisor", 1)

            values = [dp[stat_key] / divisor for dp in datapoints]
            timestamps = [dp["Timestamp"] for dp in datapoints]

            series = SignalTimeSeries(
                metric_name=signal_name.value,
                values=values,
                timestamps=timestamps,
                interval=timedelta(seconds=period),
                aggregation=stat_key.lower(),
            )
            series.compute_statistics()
            signals[signal_name.value] = series

        except Exception as e:
            logger.debug(f"CloudWatch fetch failed for {instance_id}/{signal_name.value}: {e}")

    return signals


def collect_ec2_hourly_cpu(
    cw_client: Any,
    instance_id: str,
    days: int = 30,
) -> Optional[SignalTimeSeries]:
    """
    Collect 30-day hourly CPU for workload pattern analysis.

    This produces the time-series needed by the workload pattern classifier
    to detect diurnal, weekly, burst, and batch patterns.
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    try:
        response = cw_client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour
            Statistics=["Average"],
        )

        datapoints = response.get("Datapoints", [])
        if len(datapoints) < 48:  # Need at least 2 days of hourly data
            return None

        datapoints.sort(key=lambda dp: dp["Timestamp"])
        values = [dp["Average"] for dp in datapoints]
        timestamps = [dp["Timestamp"] for dp in datapoints]

        series = SignalTimeSeries(
            metric_name="cpu_hourly_30d",
            values=values,
            timestamps=timestamps,
            interval=timedelta(hours=1),
            aggregation="avg",
        )
        series.compute_statistics()
        return series

    except Exception as e:
        logger.debug(f"Hourly CPU fetch failed for {instance_id}: {e}")
        return None


def build_ec2_evidence_bundle(
    cw_client: Any,
    instance_id: str,
    instance_meta: Dict[str, Any],
    is_stopped: bool,
    monthly_cost: float = 0.0,
    cost_source: str = "unknown",
    tags: Optional[Dict[str, str]] = None,
    resource_name: str = "",
    region: str = "",
    launch_time: Optional[datetime] = None,
) -> EvidenceBundle:
    """
    Build a complete EvidenceBundle for an EC2 instance.

    Collects 7-day multi-signal metrics (CPU, network, disk) and
    optionally 30-day hourly CPU for pattern analysis.

    Args:
        cw_client: boto3 CloudWatch client
        instance_id: EC2 instance ID
        instance_meta: Raw instance metadata
        is_stopped: Whether instance is in stopped state
        monthly_cost: Known monthly cost
        cost_source: How cost was determined (actual, catalog_estimate, etc.)
        tags: Instance tags
        resource_name: Display name
        region: AWS region
        launch_time: Instance launch time (for age calculation)
    """
    provider_state = "stopped" if is_stopped else "running"

    # Calculate resource age
    resource_age_days = 0
    if launch_time:
        resource_age_days = (datetime.now(timezone.utc) - launch_time).days

    # Collect signals only for running instances
    signals: Dict[str, SignalTimeSeries] = {}
    if not is_stopped and cw_client:
        signals = collect_ec2_evidence(cw_client, instance_id, instance_meta, days=7)

    return build_evidence_bundle(
        resource_id=instance_id,
        provider="aws",
        resource_type="AWS EC2 Instance",
        provider_state=provider_state,
        signals=signals,
        tags=tags or {},
        resource_age_days=resource_age_days,
        monthly_cost=monthly_cost,
        cost_source=cost_source,
        resource_name=resource_name,
        region=region,
        cloud_resource_id=instance_meta.get("arn", instance_id),
        last_state_change=None,  # AWS doesn't easily expose this
    )
