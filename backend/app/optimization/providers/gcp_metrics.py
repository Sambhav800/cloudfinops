"""
GCP Metrics Provider — Cloud Monitoring multi-signal collection for Compute Engine.

Fetches CPU utilization, network bytes (in/out), and disk ops from Cloud Monitoring v3.
Returns EvidenceBundle for consumption by the classification pipeline.

This fills the complete gap in gcp.py (line 633-634) which currently does zero
metrics collection and uses purely binary state classification.

Requires: google-cloud-monitoring package and monitoring.timeSeries.list permission
(included in roles/monitoring.viewer).
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

# GCP Cloud Monitoring metric type definitions
GCE_METRICS = {
    SignalName.CPU_AVG: {
        "metric_type": "compute.googleapis.com/instance/cpu/utilization",
        "multiplier": 100.0,  # Convert 0-1 fraction to 0-100 percentage
    },
    SignalName.NETWORK_IN_MB: {
        "metric_type": "compute.googleapis.com/instance/network/received_bytes_count",
        "multiplier": 1.0 / 1_048_576,  # Bytes to MB
    },
    SignalName.NETWORK_OUT_MB: {
        "metric_type": "compute.googleapis.com/instance/network/sent_bytes_count",
        "multiplier": 1.0 / 1_048_576,
    },
    SignalName.DISK_READ_OPS: {
        "metric_type": "compute.googleapis.com/instance/disk/read_ops_count",
        "multiplier": 1.0,
    },
    SignalName.DISK_WRITE_OPS: {
        "metric_type": "compute.googleapis.com/instance/disk/write_ops_count",
        "multiplier": 1.0,
    },
}


def collect_gce_evidence(
    monitoring_client: Any,
    project_id: str,
    instance_id: str,
    zone: str,
    days: int = 7,
) -> Dict[str, SignalTimeSeries]:
    """
    Collect multi-signal metrics from GCP Cloud Monitoring for a GCE instance.

    Uses the monitoring_v3.MetricServiceClient to fetch time-series data.

    Args:
        monitoring_client: google.cloud.monitoring_v3.MetricServiceClient
        project_id: GCP project ID
        instance_id: Numeric instance ID
        zone: GCE zone (e.g., "us-central1-a")
        days: Lookback window in days

    Returns:
        Dict mapping signal names to SignalTimeSeries
    """
    from google.cloud import monitoring_v3
    from google.protobuf.timestamp_pb2 import Timestamp

    signals: Dict[str, SignalTimeSeries] = {}
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    # Build time interval
    interval = monitoring_v3.TimeInterval()
    interval.end_time = Timestamp()
    interval.end_time.FromDatetime(now)
    interval.start_time = Timestamp()
    interval.start_time.FromDatetime(start_time)

    project_name = f"projects/{project_id}"

    for signal_name, metric_def in GCE_METRICS.items():
        try:
            metric_filter = (
                f'metric.type="{metric_def["metric_type"]}" '
                f'AND resource.type="gce_instance" '
                f'AND resource.labels.instance_id="{instance_id}" '
                f'AND resource.labels.zone="{zone}"'
            )

            # Determine alignment period based on lookback
            alignment_period = {"seconds": 86400 if days <= 7 else 3600}

            request = monitoring_v3.ListTimeSeriesRequest(
                name=project_name,
                filter=metric_filter,
                interval=interval,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                aggregation=monitoring_v3.Aggregation(
                    alignment_period=alignment_period,
                    per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                ),
            )

            results = monitoring_client.list_time_series(request=request)

            values: List[float] = []
            timestamps: List[datetime] = []
            multiplier = metric_def["multiplier"]

            for ts in results:
                for point in ts.points:
                    val = point.value.double_value * multiplier
                    values.append(val)
                    timestamps.append(
                        point.interval.end_time.ToDatetime().replace(tzinfo=timezone.utc)
                    )

            if not values:
                continue

            # Sort chronologically
            paired = sorted(zip(timestamps, values), key=lambda x: x[0])
            timestamps = [t for t, _ in paired]
            values = [v for _, v in paired]

            period = timedelta(days=1) if days <= 7 else timedelta(hours=1)
            series = SignalTimeSeries(
                metric_name=signal_name.value,
                values=values,
                timestamps=timestamps,
                interval=period,
                aggregation="avg",
            )
            series.compute_statistics()
            signals[signal_name.value] = series

        except Exception as e:
            logger.debug(
                f"Cloud Monitoring fetch failed for instance {instance_id}/{signal_name.value}: {e}"
            )

    return signals


def collect_gce_hourly_cpu(
    monitoring_client: Any,
    project_id: str,
    instance_id: str,
    zone: str,
    days: int = 30,
) -> Optional[SignalTimeSeries]:
    """
    Collect 30-day hourly CPU for workload pattern analysis.

    Returns the time-series needed by the workload pattern classifier.
    """
    from google.cloud import monitoring_v3
    from google.protobuf.timestamp_pb2 import Timestamp

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    interval = monitoring_v3.TimeInterval()
    interval.end_time = Timestamp()
    interval.end_time.FromDatetime(now)
    interval.start_time = Timestamp()
    interval.start_time.FromDatetime(start_time)

    try:
        metric_filter = (
            f'metric.type="compute.googleapis.com/instance/cpu/utilization" '
            f'AND resource.type="gce_instance" '
            f'AND resource.labels.instance_id="{instance_id}" '
            f'AND resource.labels.zone="{zone}"'
        )

        request = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=metric_filter,
            interval=interval,
            view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            aggregation=monitoring_v3.Aggregation(
                alignment_period={"seconds": 3600},
                per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
            ),
        )

        results = monitoring_client.list_time_series(request=request)

        values: List[float] = []
        timestamps: List[datetime] = []

        for ts in results:
            for point in ts.points:
                values.append(point.value.double_value * 100.0)  # 0-1 → percentage
                timestamps.append(
                    point.interval.end_time.ToDatetime().replace(tzinfo=timezone.utc)
                )

        if len(values) < 48:  # Need at least 2 days of hourly data
            return None

        paired = sorted(zip(timestamps, values), key=lambda x: x[0])
        timestamps = [t for t, _ in paired]
        values = [v for _, v in paired]

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
        logger.debug(f"Hourly CPU fetch failed for GCE instance {instance_id}: {e}")
        return None


def build_gce_evidence_bundle(
    monitoring_client: Any,
    project_id: str,
    instance_id: str,
    instance_name: str,
    zone: str,
    is_stopped: bool,
    monthly_cost: float = 0.0,
    cost_source: str = "unknown",
    tags: Optional[Dict[str, str]] = None,
    resource_name: str = "",
    creation_timestamp: Optional[datetime] = None,
) -> EvidenceBundle:
    """
    Build a complete EvidenceBundle for a GCE instance.

    Args:
        monitoring_client: google.cloud.monitoring_v3.MetricServiceClient
        project_id: GCP project ID
        instance_id: Numeric instance ID
        instance_name: Instance name
        zone: GCE zone
        is_stopped: Whether instance is stopped/terminated/suspended
        monthly_cost: Known monthly cost
        cost_source: How cost was determined
        tags: Instance labels
        resource_name: Display name
        creation_timestamp: When instance was created
    """
    provider_state = "stopped" if is_stopped else "running"
    region = "-".join(zone.split("-")[:-1]) if zone else ""

    # Calculate resource age
    resource_age_days = 0
    if creation_timestamp:
        resource_age_days = (datetime.now(timezone.utc) - creation_timestamp).days

    # Collect signals only for running instances with a monitoring client
    signals: Dict[str, SignalTimeSeries] = {}
    if not is_stopped and monitoring_client:
        signals = collect_gce_evidence(
            monitoring_client, project_id, instance_id, zone, days=7
        )

    cloud_resource_id = (
        f"//compute.googleapis.com/projects/{project_id}/zones/{zone}/instances/{instance_name}"
    )

    return build_evidence_bundle(
        resource_id=f"gcp-instance-{project_id}-{instance_name}-{zone}",
        provider="gcp",
        resource_type="GCP Compute Instance",
        provider_state=provider_state,
        signals=signals,
        tags=tags or {},
        resource_age_days=resource_age_days,
        monthly_cost=monthly_cost,
        cost_source=cost_source,
        resource_name=resource_name or instance_name,
        region=region,
        cloud_resource_id=cloud_resource_id,
        last_state_change=None,
    )
