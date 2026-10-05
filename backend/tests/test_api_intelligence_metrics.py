import pytest

from app.core.api_intelligence import ApiIntelligenceService


def resource(invocations, **metadata):
    return {
        "id": "api-1", "provider": "aws", "resource_name": "Orders/prod",
        "service_type": "AWS API Gateway", "region": "us-east-1", "cost": 100,
        "status": "Unknown",
        "metadata": {
            "api_id": "api-1", "stage_name": "prod", "is_api_resource": True,
            "invocations_7d": invocations, "error_rate_4xx": None, "error_rate_5xx": None,
            "latency_p99_ms": None, "cache_enabled": False,
            "throttle_burst_limit": 10, "throttle_rate_limit": 10,
            **metadata,
        },
    }


@pytest.mark.parametrize("invocations", [None, -1, "invalid", float("nan"), float("inf"), True])
@pytest.mark.parametrize("status", ["Unknown", "Zombie", "Idle"])
def test_missing_metrics_never_create_ghost_findings_or_financial_rankings(invocations, status):
    item = resource(invocations)
    item["status"] = status
    summary = ApiIntelligenceService().get_api_summary([item])
    assert summary["total_api_count"] == 1
    assert summary["api_resources"][0]["invocations_7d"] is None
    assert summary["api_resources"][0]["error_rate_4xx"] is None
    assert summary["api_resources"][0]["error_rate_5xx"] is None
    assert summary["api_resources"][0]["latency_p99_ms"] is None
    assert summary["api_resources"][0]["is_ghost"] is False
    assert summary["ghost_apis"] == summary["throttle_issues"] == summary["cost_per_request_ranking"] == []
    assert summary["total_api_waste"] == summary["ghost_api_count"] == 0


def test_positive_request_count_survives_missing_secondary_metrics():
    summary = ApiIntelligenceService().get_api_summary([resource(100)])
    assert summary["ghost_apis"] == summary["throttle_issues"] == []
    assert summary["api_resources"][0]["invocations_7d"] == 100
    assert summary["api_resources"][0]["error_rate_5xx"] is None
    assert len(summary["cost_per_request_ranking"]) == 1
    assert summary["cost_per_request_ranking"][0]["invocations_7d"] == 100


def test_observed_zero_count_remains_distinct_from_unavailable_metrics():
    summary = ApiIntelligenceService().get_api_summary([resource(0)])
    assert summary["api_resources"][0]["invocations_7d"] == 0
    assert summary["api_resources"][0]["is_ghost"] is True
    assert summary["ghost_api_count"] == 1
    assert summary["ghost_apis"][0]["invocations_7d"] == 0
    assert summary["cost_per_request_ranking"] == []


def test_missing_metric_field_is_not_defaulted_to_zero():
    item = resource(None)
    del item["metadata"]["invocations_7d"]
    summary = ApiIntelligenceService().get_api_summary([item])
    assert summary["api_resources"][0]["invocations_7d"] is None
    assert summary["ghost_apis"] == []


def test_empty_inventory_stays_empty():
    summary = ApiIntelligenceService().get_api_summary([])
    assert summary["api_resources"] == []
    assert summary["ghost_apis"] == []
    assert summary["total_api_count"] == 0
