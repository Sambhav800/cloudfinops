"""
GPU Metrics Worker — background job that collects GPU utilization metrics
from cloud monitoring APIs (CloudWatch, Azure Monitor, Cloud Monitoring)
and stores them in the gpu_metrics time-series collection.

Scheduled via APScheduler every 5 minutes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def collect_gpu_metrics() -> None:
    """
    Main worker entry point. Collects GPU metrics for all active GPU resources.
    Called by APScheduler every gpu_metrics_interval_seconds (default 300s).
    """
    from ..db.mongo_client import get_db_client
    from ..core.gpu_metrics_store import GpuMetricsStore
    from ..core.gpu_specs import is_gpu_instance_type

    try:
        db = get_db_client()
        metrics_store = GpuMetricsStore(db)

        all_integrations = await db.select("cloud_integrations", filters={})
        if not all_integrations:
            return

        total_collected = 0
        for integration in all_integrations:
            user_id = integration.get("user_id")
            integration_id = integration.get("id") or integration.get("_id")
            provider = str(integration.get("provider", "")).lower()

            if not user_id:
                continue

            resources = await db.get_resources(user_id, integration_id=str(integration_id))
            gpu_resources = [
                r for r in resources
                if (r.get("metadata") or {}).get("is_gpu_instance")
                or is_gpu_instance_type(
                    str((r.get("metadata") or {}).get("instance_type") or (r.get("metadata") or {}).get("vm_size") or ""),
                    provider=provider,
                )
            ]

            if not gpu_resources:
                continue

            for resource in gpu_resources:
                status = str(resource.get("status") or "").lower()
                if status in ("stopped", "terminated", "deallocated"):
                    continue

                resource_id = resource.get("id") or resource.get("cloud_resource_id") or ""
                metrics = await _fetch_gpu_metrics_for_resource(resource, provider, integration)

                if metrics:
                    await metrics_store.record_sample(
                        resource_id=resource_id,
                        user_id=user_id,
                        provider=provider,
                        sm_pct=metrics.get("sm_pct"),
                        mem_pct=metrics.get("mem_pct"),
                        power_w=metrics.get("power_w"),
                        temp_c=metrics.get("temp_c"),
                    )
                    total_collected += 1

        if total_collected > 0:
            logger.info(f"GPU metrics worker: collected {total_collected} samples")

    except Exception as e:
        logger.error(f"GPU metrics worker failed: {e}", exc_info=True)


async def _fetch_gpu_metrics_for_resource(
    resource: dict[str, Any],
    provider: str,
    integration: dict[str, Any],
) -> dict[str, float] | None:
    """Fetch GPU metrics from the appropriate cloud monitoring API."""
    try:
        if provider == "aws":
            return await _fetch_aws_gpu_metrics(resource, integration)
        elif provider == "azure":
            return await _fetch_azure_gpu_metrics(resource, integration)
        elif provider == "gcp":
            return await _fetch_gcp_gpu_metrics(resource, integration)
    except Exception as e:
        logger.debug(f"GPU metrics fetch failed for {resource.get('resource_name')}: {e}")
    return None


async def _fetch_aws_gpu_metrics(
    resource: dict[str, Any],
    integration: dict[str, Any],
) -> dict[str, float] | None:
    """
    Fetch GPU metrics from AWS CloudWatch.
    Requires DCGM-Exporter or CloudWatch Agent publishing GPU metrics.
    Namespace: CWAgent or custom.
    """
    try:
        import boto3
        from datetime import datetime, timezone, timedelta

        meta = resource.get("metadata") or {}
        region = resource.get("region", "us-east-1")
        instance_id = meta.get("instance_id") or resource.get("cloud_resource_id", "").split("-")[-1]

        credentials = integration.get("credentials") or {}
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=region,
        )
        cw = session.client("cloudwatch")

        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=10)

        metrics_result: dict[str, float] = {}

        for metric_name, result_key in [
            ("gpu_utilization", "sm_pct"),
            ("gpu_memory_utilization", "mem_pct"),
        ]:
            resp = cw.get_metric_statistics(
                Namespace="CWAgent",
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start,
                EndTime=now,
                Period=300,
                Statistics=["Average"],
            )
            datapoints = resp.get("Datapoints", [])
            if datapoints:
                latest = max(datapoints, key=lambda d: d["Timestamp"])
                metrics_result[result_key] = latest["Average"]

        return metrics_result if metrics_result else None

    except ImportError:
        logger.debug("boto3 not available for AWS GPU metrics")
        return None
    except Exception as e:
        logger.debug(f"AWS GPU metrics error: {e}")
        return None


async def _fetch_azure_gpu_metrics(
    resource: dict[str, Any],
    integration: dict[str, Any],
) -> dict[str, float] | None:
    """
    Fetch GPU metrics from Azure Monitor.
    Metrics: Percentage GPU, GPU Memory Used.
    """
    try:
        from azure.identity import ClientSecretCredential
        from azure.monitor.query import MetricsQueryClient
        from datetime import timedelta

        credentials = integration.get("credentials") or {}
        credential = ClientSecretCredential(
            tenant_id=credentials.get("tenant_id"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
        )

        monitor_client = MetricsQueryClient(credential)
        resource_uri = resource.get("cloud_resource_id", "")

        response = monitor_client.query_resource(
            resource_uri,
            metric_names=["Percentage GPU", "GPU Memory Used"],
            timespan=timedelta(minutes=10),
            granularity=timedelta(minutes=5),
        )

        metrics_result: dict[str, float] = {}
        for metric in response.metrics:
            for ts in metric.timeseries:
                for data_point in reversed(ts.data):
                    if data_point.average is not None:
                        if "gpu" in metric.name.lower() and "memory" not in metric.name.lower():
                            metrics_result["sm_pct"] = data_point.average
                        elif "memory" in metric.name.lower():
                            metrics_result["mem_pct"] = data_point.average
                        break

        return metrics_result if metrics_result else None

    except ImportError:
        logger.debug("Azure SDK not available for GPU metrics")
        return None
    except Exception as e:
        logger.debug(f"Azure GPU metrics error: {e}")
        return None


async def _fetch_gcp_gpu_metrics(
    resource: dict[str, Any],
    integration: dict[str, Any],
) -> dict[str, float] | None:
    """
    Fetch GPU metrics from Google Cloud Monitoring.
    Metrics: compute.googleapis.com/instance/gpu/utilization,
             compute.googleapis.com/instance/gpu/memory/utilization
    """
    try:
        from google.cloud import monitoring_v3
        from google.oauth2 import service_account
        from datetime import datetime, timezone, timedelta
        from google.protobuf import timestamp_pb2

        meta = resource.get("metadata") or {}
        project_id = meta.get("project_id") or integration.get("project_id")
        instance_name = resource.get("resource_name", "")
        zone = meta.get("zone", "")

        credentials_info = integration.get("credentials") or {}
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        client = monitoring_v3.MetricServiceClient(credentials=credentials)

        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=10)

        interval = monitoring_v3.TimeInterval()
        end_time = timestamp_pb2.Timestamp()
        end_time.FromDatetime(now)
        start_time = timestamp_pb2.Timestamp()
        start_time.FromDatetime(start)
        interval.end_time = end_time
        interval.start_time = start_time

        metrics_result: dict[str, float] = {}

        for metric_type, result_key in [
            ("compute.googleapis.com/instance/gpu/utilization", "sm_pct"),
            ("compute.googleapis.com/instance/gpu/memory/utilization", "mem_pct"),
        ]:
            filter_str = (
                f'metric.type="{metric_type}" AND '
                f'resource.labels.instance_id="{instance_name}" AND '
                f'resource.labels.zone="{zone}"'
            )

            results = client.list_time_series(
                request={
                    "name": f"projects/{project_id}",
                    "filter": filter_str,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            for ts in results:
                for point in reversed(ts.points):
                    value = point.value.double_value * 100  # Convert 0-1 to percentage
                    metrics_result[result_key] = round(value, 2)
                    break
                break

        return metrics_result if metrics_result else None

    except ImportError:
        logger.debug("Google Cloud Monitoring SDK not available")
        return None
    except Exception as e:
        logger.debug(f"GCP GPU metrics error: {e}")
        return None
