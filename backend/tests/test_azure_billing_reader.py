from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.scanners.azure import AzureWasteScanner
from app.scanners.azure_billing import AzureBillingReader


def result(dimension, rows, next_link=None, columns=None):
    return SimpleNamespace(
        rows=rows, next_link=next_link,
        columns=[SimpleNamespace(name=name) for name in (columns or ["Cost", "UsageDate", dimension, "Currency"])],
    )


class ProviderError(Exception):
    def __init__(self, status=429, headers=None):
        self.response = SimpleNamespace(status_code=status, headers=headers or {})


def reader(monkeypatch, responses):
    calls = []
    options = {}
    pending = iter(responses)

    class Client:
        def __init__(self, **kwargs):
            options.update(kwargs)
            self.query = SimpleNamespace(usage=self.usage)

        def usage(self, **kwargs):
            calls.append(kwargs)
            response = next(pending)
            if isinstance(response, Exception):
                raise response
            return response

        def close(self):
            options["closed"] = True

    monkeypatch.setattr("app.scanners.azure_billing.CostManagementClient", Client)
    monkeypatch.setattr("app.scanners.azure_billing.time.sleep", lambda _seconds: None)
    instance = AzureBillingReader(object(), "sub", lambda value, _currency: value)
    instance.now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    instance.start = instance.now.replace(day=1)
    return instance, calls, options


def test_429_is_single_attempt_and_stops_all_followup_billing(monkeypatch):
    instance, calls, options = reader(monkeypatch, [ProviderError(headers={
        "x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after": "120",
    })])
    before = datetime.now(timezone.utc)
    snapshot = instance.fetch()
    assert len(calls) == 1
    assert snapshot["subscription_costs"] == {}
    assert snapshot["billing"]["status"] == "unavailable"
    assert snapshot["billing"]["reason"] == "rate_limited"
    assert (datetime.fromisoformat(snapshot["billing"]["retry_at"]) - before).total_seconds() >= 120
    assert options["retry_total"] == options["retry_status"] == options["retry_connect"] == options["retry_read"] == 0
    assert options["closed"] is True


def test_two_daily_queries_populate_totals_and_resource_costs(monkeypatch):
    instance, calls, _ = reader(monkeypatch, [
        result("ServiceName", [[10.1234, 20260901, "VMs", "USD"], [2.0, 20260902, "VMs", "USD"]]),
        result("ResourceId", [[10.1234, 20260901, "/VM/A", "USD"], [2.0, 20260902, "/VM/A", "USD"]]),
    ])
    snapshot = instance.fetch()
    assert len(calls) == 2
    assert all(call["headers"] == {"ClientType": "CloudFinOps"} for call in calls)
    assert all(call["parameters"].dataset.granularity == "Daily" for call in calls)
    assert snapshot["billing"]["status"] == "fresh"
    assert snapshot["subscription_costs"]["total"] == 12.12
    assert snapshot["subscription_costs"]["by_service"] == {"VMs": 12.1234}
    assert snapshot["resource_costs"]["/vm/a"]["actual_cost_mtd"] == 12.12
    assert len(snapshot["subscription_costs"]["daily_totals"]) == 15


def test_empty_success_is_real_zero_not_unavailable(monkeypatch):
    instance, calls, _ = reader(monkeypatch, [result("ServiceName", []), result("ResourceId", [])])
    snapshot = instance.fetch()
    assert snapshot["billing"]["status"] == "fresh"
    assert snapshot["billing"]["daily_costs_available"] is True
    assert snapshot["subscription_costs"]["total"] == 0
    assert all(day["amount"] == 0 for day in snapshot["subscription_costs"]["daily_totals"])
    assert len(calls) == 2


def test_resource_throttling_keeps_complete_subscription_result(monkeypatch):
    instance, calls, _ = reader(monkeypatch, [
        result("ServiceName", [[99, 20260901, "VMs", "USD"]]), ProviderError(),
    ])
    snapshot = instance.fetch()
    assert len(calls) == 2
    assert snapshot["subscription_costs"]["total"] == 99
    assert snapshot["billing"]["subscription_costs_available"] is True
    assert snapshot["billing"]["resource_costs_available"] is False
    assert snapshot["billing"]["status"] == "stale"


def test_pagination_accumulates_all_rows_and_uses_column_names(monkeypatch):
    next_link = "https://management.azure.com/subscriptions/sub/providers/Microsoft.CostManagement/query?api-version=2022-10-01&$skiptoken=next"
    instance, calls, _ = reader(monkeypatch, [
        result("ServiceName", [[20260901, "USD", "VMs", 4]], next_link,
               columns=["UsageDate", "Currency", "ServiceName", "PreTaxCost"]),
        result("ServiceName", [[6, 20260901, "VMs", "USD"]]),
        result("ResourceId", []),
    ])
    snapshot = instance.fetch()
    assert snapshot["subscription_costs"]["total"] == 10
    assert calls[1]["params"] == {"$skiptoken": "next"}
    assert len(calls) == 3


@pytest.mark.parametrize("next_link", [
    "https://evil.example/query?$skiptoken=x",
    "https://management.azure.com/subscriptions/other/providers/Microsoft.CostManagement/query?$skiptoken=x",
    "http://management.azure.com/subscriptions/sub/providers/Microsoft.CostManagement/query?$skiptoken=x",
])
def test_invalid_continuation_does_not_publish_partial_total(monkeypatch, next_link):
    instance, calls, _ = reader(monkeypatch, [result("ServiceName", [[10, 20260901, "VM", "USD"]], next_link)])
    snapshot = instance.fetch()
    assert snapshot["subscription_costs"] == {}
    assert snapshot["billing"]["status"] == "unavailable"
    assert len(calls) == 1


@pytest.mark.parametrize("response", [None, result("ServiceName", [[None, 20260901, "VM", "USD"]]),
    result("ServiceName", [[float("nan"), 20260901, "VM", "USD"]]),
    result("ServiceName", [[1, 20260831, "VM", "USD"]]),
    result("ServiceName", [[1, 20260901, "VM", None]]),
])
def test_invalid_or_absent_data_never_becomes_zero(monkeypatch, response):
    instance, calls, _ = reader(monkeypatch, [response])
    snapshot = instance.fetch()
    assert snapshot["billing"]["subscription_costs_available"] is False
    assert snapshot["subscription_costs"] == {}
    assert len(calls) == 1


def test_zero_resource_actual_replaces_previous_nonzero_value():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    scanner._real_costs = {"/vm": {"actual_cost_mtd": 0}}
    scanner.findings = [{"cloud_resource_id": "/vm", "cost": 90, "metadata": {"cost_source": "actual"}}]
    assert scanner._get_resource_cost("Standard_B2s", "/vm") == (0, True)
    assert scanner._lookup_actual_resource_cost("/vm") == (0, True)
    assert scanner._apply_real_cost_overrides() == 1
    assert scanner.findings[0]["cost"] == 0


def test_inventory_scan_with_supplied_unavailable_snapshot_never_queries_billing():
    scanner = AzureWasteScanner.__new__(AzureWasteScanner)
    scanner.subscription_id = "sub"
    scanner.fetch_billing = lambda: pytest.fail("Billing must not be queried again")
    for name in ("virtual_machines", "managed_disks", "public_ips", "network_security_groups", "storage_accounts", "load_balancers", "network_interfaces", "snapshots", "generic_resources"):
        setattr(scanner, f"scan_{name}", lambda: None)
    assert scanner.scan_all(billing_snapshot={"billing": {"status": "unavailable"}}) == []
    assert scanner._scan_summary["billing"]["status"] == "unavailable"
