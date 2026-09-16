import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call

import pytest
from botocore.exceptions import ClientError

from app.scanners.aws import AWSScanner


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _deprecated_utc_call_token() -> str:
    return "utc" + "now("


def test_target_backend_modules_do_not_use_deprecated_utc_helper() -> None:
    """Regression guard: the targeted backend modules must not reintroduce the deprecated UTC helper."""
    forbidden = _deprecated_utc_call_token()
    for relative_path in (
        "backend/app/api/routes.py",
        "backend/app/core/finance.py",
        "backend/app/scanners/aws.py",
        "backend/app/scanners/azure.py",
        "backend/app/scanners/gcp.py",
    ):
        assert forbidden not in _read(relative_path), relative_path


def test_routes_use_timezone_aware_iso_timestamps_for_health_and_scan_updates() -> None:
    source = _read("backend/app/api/routes.py")
    assert source.count("datetime.now(timezone.utc).isoformat()") >= 4


def test_finance_keeps_timezone_aware_utc_today_helper() -> None:
    source = _read("backend/app/core/finance.py")
    assert "return datetime.now(timezone.utc).date()" in source


@pytest.mark.parametrize("scenario", [
    "traffic", "zero_count", "empty_metrics", "metric_error", "empty_inventory",
    "count_error", "empty_count", "missing_count_sum", "null_count_sum", "negative_count",
    "fractional_count", "nonfinite_count", "partial_count", "secondary_error", "zero_secondary_error",
    "latency_error", "cache_error", "no_cache",
])
def test_api_gateway_cloudwatch_uses_aware_utc_seven_day_window(
    monkeypatch: pytest.MonkeyPatch, scenario: str,
) -> None:
    now = datetime(2026, 1, 3, 0, 5, tzinfo=timezone.utc)
    clock = Mock(wraps=datetime)
    clock.now.return_value = now
    monkeypatch.setattr("app.scanners.aws.datetime", clock)

    rest = Mock(spec=["get_paginator", "get_stages"])
    rest.get_paginator.return_value.paginate.return_value = [{
        "items": [] if scenario == "empty_inventory" else [{"id": "api-1", "name": "Orders"}],
    }]
    rest.get_stages.return_value = {"item": [{
        "stageName": "prod", "cacheClusterEnabled": scenario != "no_cache",
    }]}
    http = Mock(spec=["get_apis"])
    http.get_apis.return_value = {"Items": []}
    cloudwatch = Mock(spec=["get_metric_statistics"])
    metric_names = ["Count", "4XXError", "5XXError", "Latency", "CacheHitCount", "CacheMissCount"]
    denied = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Metrics access denied"}},
        "GetMetricStatistics",
    )
    responses: list[dict[str, object] | ClientError] = [
        {"Datapoints": [{"Sum": 60}, {"Sum": 40}]},
        {"Datapoints": [{"Sum": 3}]},
        {"Datapoints": [{"Sum": 1}]},
        {"Datapoints": [{"ExtendedStatistics": {"p99": 123.4}}]},
        {"Datapoints": [{"Sum": 75}]},
        {"Datapoints": [{"Sum": 25}]},
    ]
    collection = dict.fromkeys(metric_names, "available")
    expected_count: int | None = 100
    if scenario in ("zero_count", "zero_secondary_error"):
        responses = [{"Datapoints": [{"Sum": 0.0}]} for _ in metric_names]
        responses[3] = {"Datapoints": []}
        collection["Latency"] = "no_data"
        expected_count = 0
    if scenario in ("empty_metrics", "metric_error"):
        responses = [denied if scenario == "metric_error" else {"Datapoints": []}] * len(metric_names)
        collection = dict.fromkeys(metric_names, "error" if scenario == "metric_error" else "no_data")
        expected_count = None
    count_overrides = {
        "count_error": denied,
        "empty_count": {"Datapoints": []},
        "missing_count_sum": {"Datapoints": [{}]},
        "null_count_sum": {"Datapoints": [{"Sum": None}]},
        "negative_count": {"Datapoints": [{"Sum": -1}]},
        "fractional_count": {"Datapoints": [{"Sum": 0.5}]},
        "nonfinite_count": {"Datapoints": [{"Sum": float("nan")}]},
        "partial_count": {"Datapoints": [{"Sum": 0}, {}]},
    }
    if scenario in count_overrides:
        responses[0] = count_overrides[scenario]
        expected_count = None
        collection["Count"] = "error" if scenario == "count_error" else "no_data" if scenario == "empty_count" else "invalid_data"
    failed_secondary = {
        "secondary_error": "4XXError", "zero_secondary_error": "4XXError",
        "latency_error": "Latency", "cache_error": "CacheHitCount",
    }.get(scenario)
    if failed_secondary:
        responses[metric_names.index(failed_secondary)] = denied
        collection[failed_secondary] = "error"
    if scenario == "no_cache":
        metric_names = metric_names[:4]
        responses = responses[:4]
        collection = {name: collection[name] for name in metric_names}
    cloudwatch.get_metric_statistics.side_effect = responses

    clients = {"apigateway": rest, "cloudwatch": cloudwatch, "apigatewayv2": http}
    scanner = AWSScanner.__new__(AWSScanner)
    scanner.executor = None
    scanner.access_denied_services = set()
    get_client = Mock(side_effect=lambda service, region: clients[service])
    monkeypatch.setattr(scanner, "_get_client", get_client)

    resources, waste, savings = asyncio.run(scanner._scan_api_gateway("us-east-1"))

    assert get_client.call_args_list == [
        call("apigateway", "us-east-1"), call("cloudwatch", "us-east-1"), call("apigatewayv2", "us-east-1"),
    ]
    rest.get_paginator.assert_called_once_with("get_rest_apis")
    rest.get_paginator.return_value.paginate.assert_called_once_with()
    http.get_apis.assert_called_once_with()
    assert savings == 0.0
    if scenario == "empty_inventory":
        assert resources == []
        assert waste == []
        rest.get_stages.assert_not_called()
        cloudwatch.get_metric_statistics.assert_not_called()
        clock.now.assert_not_called()
        return

    rest.get_stages.assert_called_once_with(restApiId="api-1")
    requests = cloudwatch.get_metric_statistics.call_args_list
    assert len(requests) == len(metric_names)
    for request, metric_name in zip(requests, metric_names):
        start, end = request.kwargs["StartTime"], request.kwargs["EndTime"]
        assert isinstance(start, datetime) and isinstance(end, datetime)
        assert start.utcoffset() == end.utcoffset() == timedelta(0)
        assert end - start == timedelta(days=7)
        assert request == call(
            Namespace="AWS/ApiGateway",
            MetricName=metric_name,
            Dimensions=[{"Name": "ApiName", "Value": "Orders"}, {"Name": "Stage", "Value": "prod"}],
            StartTime=now - timedelta(days=7),
            EndTime=now,
            Period=604800,
            **({"ExtendedStatistics": ["p99"]} if metric_name == "Latency" else {"Statistics": ["Sum"]}),
        )
    clock.now.assert_called_once_with(timezone.utc)

    assert len(resources) == 1
    resource = resources[0]
    assert resource.resource_name == "Orders/prod"
    assert resource.cloud_resource_id == "apigw-api-1-prod"
    assert resource.cost == 0.0
    assert resource.metadata is not None
    assert resource.metadata["invocations_7d"] == expected_count
    assert resource.metadata["metric_collection"] == collection
    assert resource.metadata["avg_daily_invocations"] == (
        round(expected_count / 7, 1) if expected_count is not None else None
    )
    assert resource.metadata["error_rate_4xx"] == (
        3.0 if expected_count == 100 and collection["4XXError"] == "available" else None
    )
    assert resource.metadata["error_rate_5xx"] == (
        1.0 if expected_count == 100 and collection["5XXError"] == "available" else None
    )
    assert resource.metadata["latency_p99_ms"] == (123.4 if collection["Latency"] == "available" else None)
    assert resource.metadata["cache_hit_rate"] == (
        75.0
        if expected_count != 0 and collection.get("CacheHitCount") == collection.get("CacheMissCount") == "available"
        else None
    )
    if expected_count == 0:
        assert resource.status == "Zombie"
        assert waste == [{"category_name": "Ghost API Gateway", "value": 0}]
    else:
        assert resource.status == ("Unknown" if expected_count is None else "Active")
        assert waste == []
