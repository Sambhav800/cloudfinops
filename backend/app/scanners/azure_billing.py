"""Bounded, paginated Azure billing reads with one owner for retry scheduling."""

import logging
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation, QueryDataset, QueryDefinition, QueryGrouping, QueryTimePeriod,
)

from ..core.retry import _retry_after_seconds, _status_code

logger = logging.getLogger(__name__)


class AzureBillingDeferred(RuntimeError):
    """A billing refresh must resume later, without publishing incomplete totals."""


class AzureBillingReader:
    """Read service and resource daily costs; never retry a throttled request inline."""

    def __init__(self, credential: Any, subscription_id: str, to_usd: Callable[[float, str], float]):
        self.subscription_id = subscription_id
        self.to_usd = to_usd
        self.now = datetime.now(timezone.utc)
        self.start = self.now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.deadline = time.monotonic() + 180
        self.next_request_at = 0.0
        self.reason: str | None = None
        self.retry_at: str | None = None
        # Keep this identifier stable across requests, accounts and deployments.
        self.client_type = os.getenv("AZURE_COST_CLIENT_TYPE", "CloudFinOps")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", self.client_type):
            raise ValueError("AZURE_COST_CLIENT_TYPE must be a stable application identifier")
        self.client = CostManagementClient(
            credential=credential,
            retry_total=0,
            retry_status=0,
            retry_connect=0,
            retry_read=0,
            connection_timeout=10,
            read_timeout=20,
        )

    def _defer(self, reason: str, seconds: float = 60) -> None:
        self.reason = reason
        self.retry_at = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

    def _usage(self, query: QueryDefinition, params: dict[str, str]) -> Any:
        wait = max(0.0, self.next_request_at - time.monotonic())
        if time.monotonic() + wait >= self.deadline:
            self._defer("refresh_budget_exhausted")
            raise AzureBillingDeferred(self.reason)
        if wait:
            time.sleep(wait)
        try:
            return self.client.query.usage(
                scope=f"/subscriptions/{self.subscription_id}",
                parameters=query,
                headers={"ClientType": self.client_type},
                params=params,
            )
        except Exception as error:
            status = _status_code(error)
            delay = _retry_after_seconds(error)
            self._defer(
                "rate_limited" if status == 429 else "provider_error",
                delay if delay is not None and math.isfinite(delay) else 60,
            )
            headers = getattr(getattr(error, "response", None), "headers", {}) or {}
            safe_headers = {
                str(key).lower(): str(value)
                for key, value in headers.items()
                if str(key).lower().startswith("x-ms-ratelimit-")
                or str(key).lower() == "x-ms-request-id"
            }
            logger.warning("Azure billing deferred: status=%s retry_at=%s quotas=%s", status, self.retry_at, safe_headers)
            raise AzureBillingDeferred(self.reason) from error
        finally:
            # Pace every page as well as the next query, not only query groups.
            self.next_request_at = time.monotonic() + 16

    def _daily_rows(self, dimension: str) -> list[tuple[float, str, str, str]]:
        query = QueryDefinition(
            type="ActualCost", timeframe="Custom",
            time_period=QueryTimePeriod(from_property=self.start, to=self.now),
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                grouping=[QueryGrouping(type="Dimension", name=dimension)],
            ),
        )
        rows: list[tuple[float, str, str, str]] = []
        params: dict[str, str] = {}
        seen: set[str] = set()
        while True:
            result = self._usage(query, params)
            if result is None or not isinstance(result.rows, list):
                raise ValueError("Azure returned no billing dataset")
            columns = {str(column.name).casefold(): index for index, column in enumerate(result.columns or [])}
            if result.rows:
                cost_key = next((key for key in ("cost", "pretaxcost", "totalcost") if key in columns), None)
                required = ("usagedate", dimension.casefold(), "currency")
                if cost_key is None or any(key not in columns for key in required):
                    raise ValueError("Azure billing response is missing required columns")
                for row in result.rows:
                    raw = row[columns[cost_key]]
                    if raw is None or isinstance(raw, bool):
                        raise ValueError("Azure billing cost is missing")
                    amount = float(raw)
                    if not math.isfinite(amount):
                        raise ValueError("Azure billing cost is not finite")
                    day = datetime.strptime(str(row[columns["usagedate"]]), "%Y%m%d").date()
                    if not self.start.date() <= day <= self.now.date():
                        raise ValueError("Azure billing date is outside the requested month")
                    currency = str(row[columns["currency"]] or "").upper()
                    if not currency:
                        raise ValueError("Azure billing currency is missing")
                    key = str(row[columns[dimension.casefold()]] or "")
                    rows.append((amount, day.isoformat(), key, currency))
            next_link = getattr(result, "next_link", None)
            if not next_link:
                return rows
            # Extract only the continuation token; never fetch a returned URL directly.
            link = urlsplit(next_link)
            expected = f"/subscriptions/{self.subscription_id}/providers/Microsoft.CostManagement/query"
            if (link.scheme != "https" or link.netloc.lower() != "management.azure.com"
                    or link.path.rstrip("/").casefold() != expected.casefold()):
                raise ValueError("Azure returned an invalid billing continuation URL")
            query_params = parse_qs(link.query)
            tokens = query_params.get("$skiptoken", [])
            if len(tokens) != 1 or not tokens[0] or tokens[0] in seen or len(seen) >= 20:
                raise ValueError("Azure billing continuation is invalid or exceeds the page budget")
            seen.add(tokens[0])
            params = {"$skiptoken": tokens[0]}

    def _subscription_costs(self) -> dict[str, Any]:
        rows = self._daily_rows("ServiceName")
        daily: dict[str, list[float]] = defaultdict(list)
        services: dict[str, list[float]] = defaultdict(list)
        daily_services: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        currencies: set[str] = set()
        for raw, day, service, currency in rows:
            amount = self.to_usd(raw, currency)
            daily[day].append(amount)
            services[service or "Unallocated"].append(amount)
            daily_services[day][service or "Unallocated"].append(amount)
            currencies.add(currency)
        # A complete successful query establishes genuine zero-cost days too.
        for offset in range((self.now.date() - self.start.date()).days + 1):
            daily.setdefault((self.start.date() + timedelta(days=offset)).isoformat(), [])
        return {
            "total": round(math.fsum(math.fsum(values) for values in daily.values()), 2),
            "by_service": {key: round(math.fsum(values), 4) for key, values in services.items()},
            "daily_totals": [
                {
                    "date": day, "amount": round(math.fsum(values), 4),
                    "service_breakdown": {service: round(math.fsum(costs), 4) for service, costs in daily_services[day].items()},
                }
                for day, values in sorted(daily.items())
            ],
            "currency": "USD", "original_currency": next(iter(currencies)) if len(currencies) == 1 else None,
            "period": "current_month_to_date", "period_start": self.start.date().isoformat(),
            "period_end": self.now.date().isoformat(),
        }

    def _resource_costs(self) -> dict[str, dict[str, Any]]:
        rows = self._daily_rows("ResourceId")
        daily: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for raw, day, resource_id, currency in rows:
            if resource_id:
                daily[resource_id.lower()][day].append(self.to_usd(raw, currency))
        result: dict[str, dict[str, Any]] = {}
        for resource_id, dates in daily.items():
            total = round(math.fsum(math.fsum(values) for values in dates.values()), 2)
            result[resource_id] = {
                "actual_cost_mtd": total, "actual_cost_30d": total,
                "daily_costs": [{"date": day, "amount": round(math.fsum(values), 4)} for day, values in sorted(dates.items())],
                "currency": "USD", "period": "current_month_to_date",
                "period_start": self.start.date().isoformat(), "period_end": self.now.date().isoformat(),
                "observed_at": self.now.isoformat(),
            }
        return result

    def fetch(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "resource_costs": {}, "subscription_costs": {},
            "billing": {
                "status": "unavailable", "observed_at": None,
                "period_start": self.start.date().isoformat(), "reason": None, "retry_at": None,
                "resource_costs_available": False, "subscription_costs_available": False,
                "daily_costs_available": False,
            },
        }
        billing = snapshot["billing"]
        try:
            snapshot["subscription_costs"] = self._subscription_costs()
            billing.update(subscription_costs_available=True, daily_costs_available=True, observed_at=self.now.isoformat())
            snapshot["resource_costs"] = self._resource_costs()
            billing.update(resource_costs_available=True, status="fresh")
        except Exception as error:
            if not self.reason:
                self._defer("invalid_billing_response")
            billing.update(
                status="stale" if billing["subscription_costs_available"] else "unavailable",
                reason=self.reason, retry_at=self.retry_at,
            )
            logger.warning("Azure billing refresh incomplete: reason=%s error_type=%s", self.reason, type(error).__name__)
        finally:
            self.client.close()
        return snapshot
