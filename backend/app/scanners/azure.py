"""
Azure Waste Scanner - Production Grade Implementation.

Scans Azure resources using Azure SDK to detect:
- Zombie VMs (low CPU/network utilization)
- Orphaned Disks (unattached managed disks)
- Zombie Public IPs (unattached static IPs)
- Security Risks (open NSGs, insecure storage)
- Governance Violations (missing tags, wrong regions)

Author: CloudFinOps Team
Version: 2.0.0
"""

import json
import time
import os
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.core.exceptions import HttpResponseError

from ..core.retry import call_with_backoff, is_azure_retryable
from ..core.carbon_model import estimate_monthly_carbon_kg, estimate_storage_carbon_kg

logger = logging.getLogger(__name__)
COST_SOURCE_ACTUAL = "actual"
COST_SOURCE_BILLING_UNAVAILABLE = "billing_unavailable"


class AzureWasteScanner:
    """
    Production-grade Azure waste detection scanner.
    
    Uses Azure SDK clients to scan resources and identify waste/security issues
    using metrics-based analysis, governance compliance checks, and security audits.
    
    Attributes:
        credential: Azure authentication credential
        subscription_id: Target Azure subscription
        findings: List of discovered resources with waste analysis
    """
    
    # VM power consumption (kW)
    VM_POWER_KW: Dict[str, float] = {
        "Standard_B1s": 0.010,
        "Standard_B2s": 0.020,
        "Standard_D2s_v3": 0.060,
        "Standard_D4s_v3": 0.120,
        "Standard_E2s_v3": 0.065,
    }
    
    # Carbon intensity by region (kgCO2/kWh)
    CARBON_INTENSITY: Dict[str, float] = {
        "eastus": 0.379,
        "eastus2": 0.379,
        "westus": 0.079,
        "westus2": 0.079,
        "northeurope": 0.150,
        "westeurope": 0.276,
        "centralindia": 0.708,
        "eastasia": 0.453,
    }
    
    # Approximate exchange rates to USD (updated periodically)
    # Used to normalize Azure Cost Management data which returns
    # costs in the subscription's billing currency
    CURRENCY_TO_USD: Dict[str, float] = {
        "USD": 1.0,
        "INR": 0.01051, # 1 INR ≈ $0.01051 (1 USD = 95.19 INR)
        "EUR": 1.08,
        "GBP": 1.27,
        "JPY": 0.0067,
        "CAD": 0.74,
        "AUD": 0.65,
        "BRL": 0.20,
        "KRW": 0.00074,
        "SGD": 0.75,
    }
    
    def _to_usd(self, amount: float, currency: str) -> float:
        """Convert an amount from any currency to USD using dynamic rates."""
        if not currency or currency.upper() == "USD":
            return round(amount, 2)
        key = currency.upper()
        rate = self._exchange_rates.get(key)
        if rate and rate > 0:
            return round(amount * rate, 2)
        rate = self.CURRENCY_TO_USD.get(key, 1.0)
        if key not in self.CURRENCY_TO_USD:
            logger.warning(f"Unknown currency '{currency}', treating as USD")
        return round(amount * rate, 2)
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        subscription_id: str,
        exchange_rates: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Initialize the Azure Waste Scanner.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Service principal client ID
            client_secret: Service principal client secret
            subscription_id: Target Azure subscription ID
            exchange_rates: Pre-fetched USD exchange rates (currency → USD multiplier)
        """
        self.subscription_id = subscription_id
        self.findings: List[Dict[str, Any]] = []
        self._exchange_rates = exchange_rates or {}
        
        # Load configuration from environment with defaults
        self.CPU_THRESHOLD = float(os.getenv("ZOMBIE_CPU_THRESHOLD", "2.0"))
        self.NETWORK_THRESHOLD_MB = float(os.getenv("ZOMBIE_NETWORK_MB_THRESHOLD", "5.0"))
        self.LOOKBACK_DAYS = int(os.getenv("METRICS_LOOKBACK_DAYS", "7"))
        self.REQUIRED_TAGS = os.getenv(
            "REQUIRED_TAGS", "Owner,CostCenter,Environment"
        ).split(",")
        self.ALLOWED_REGIONS = os.getenv(
            "ALLOWED_REGIONS", "eastus,eastus2,westus,westus2,westus3,centralus,northcentralus,southcentralus,centralindia,southindia,westindia,northeurope,westeurope,southeastasia,eastasia"
        ).split(",")
        
        # Create Azure credential
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Initialize Azure SDK clients
        self.compute_client = ComputeManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
        self.network_client = NetworkManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
        self.monitor_client = MonitorManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
        self.resource_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
        self.storage_client = StorageManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
        
        logger.info(f"AzureWasteScanner initialized for subscription: {subscription_id}")

    def _azure_call(self, operation_name: str, func, *, base_delay: float = 1.0, max_delay: float = 16.0):
        return call_with_backoff(
            operation_name, func,
            is_retryable=is_azure_retryable,
            base_delay=base_delay,
            max_delay=max_delay,
        )

    def _azure_cost_call(self, operation_name: str, func):
        """Cost Management API has strict rate limits (~30 req/5 min). Fail fast on 429."""
        return call_with_backoff(
            operation_name, func,
            is_retryable=is_azure_retryable,
            max_attempts=2,
            base_delay=30.0,
            max_delay=60.0,
        )

    def _azure_list(self, operation_name: str, func) -> list[Any]:
        return self._azure_call(operation_name, lambda: list(func()))

    @staticmethod
    def _resource_field(resource: Any, field: str, default: Any = None) -> Any:
        if isinstance(resource, dict):
            return resource.get(field, default)
        return getattr(resource, field, default)

    def _fetch_resource_graph_resources(self) -> List[Dict[str, Any]]:
        """Fetch broad Azure inventory via Azure Resource Graph REST API."""
        endpoint = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2024-04-01"
        query = (
            "Resources "
            "| project id, name, type, location, tags, resourceGroup, subscriptionId "
            "| order by tostring(id) asc"
        )
        resources: List[Dict[str, Any]] = []
        skip_token: Optional[str] = None

        try:
            access_token = self.credential.get_token("https://management.azure.com/.default").token

            while True:
                body: Dict[str, Any] = {
                    "subscriptions": [self.subscription_id],
                    "query": query,
                    "options": {"$top": 1000},
                }
                if skip_token:
                    body["options"]["$skipToken"] = skip_token

                request = urllib.request.Request(
                    endpoint,
                    data=json.dumps(body).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                data = payload.get("data") or []
                if isinstance(data, list):
                    resources.extend(row for row in data if isinstance(row, dict))

                skip_token = payload.get("$skipToken")
                if not skip_token:
                    break

            return resources
        except urllib.error.HTTPError as error:
            logger.warning(
                "Azure Resource Graph inventory unavailable (%s); falling back to ARM resource list",
                error.code,
            )
            return []
        except Exception as error:
            logger.warning(
                "Azure Resource Graph inventory unavailable; falling back to ARM resource list: %s",
                error,
            )
            return []

    def _fetch_arm_resources(self) -> List[Any]:
        return self._azure_list(
            "Azure resources list",
            lambda: self.resource_client.resources.list(expand="createdTime,changedTime"),
        )
    
    def _get_vm_metrics(self, resource_id: str) -> Dict[str, Any]:
        """
        Query Azure Monitor for VM CPU and network metrics.
        
        This is the core method for zombie detection. It fetches 7 days of
        metrics with P1D (1-day) granularity to analyze VM utilization.
        
        Args:
            resource_id: Full Azure resource ID of the VM
            
        Returns:
            Dict containing:
                - cpu_avg: Average CPU percentage across all days
                - cpu_max: Maximum CPU percentage seen
                - network_in_max_mb: Maximum network ingress in MB
                - data_points: List of daily metrics for charting
                - days_with_data: Number of days with valid data
                - has_data: Whether any metrics data was retrieved
                - error: Error message if metrics fetch failed
        """
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=self.LOOKBACK_DAYS)
            # FIXED: Azure Monitor requires clean ISO format with Z suffix
            # Python's isoformat() produces "+00:00" which Azure rejects
            timespan = (
                f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
                f"{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            
            # Query CPU metrics
            cpu_response = self._azure_call(
                f"Azure VM CPU metrics ({resource_id})",
                lambda: self.monitor_client.metrics.list(
                    resource_uri=resource_id,
                    timespan=timespan,
                    interval="P1D",
                    metricnames="Percentage CPU",
                    aggregation="Average,Maximum"
                ),
            )
            
            # Extract CPU data points
            cpu_averages: List[float] = []
            cpu_maximums: List[float] = []
            data_points: List[Dict[str, Any]] = []
            
            for metric in cpu_response.value:
                if metric.name.value == "Percentage CPU":
                    for ts in metric.timeseries:
                        for data in ts.data:
                            if data.average is not None:
                                cpu_averages.append(data.average)
                                cpu_maximums.append(data.maximum or data.average)
                                data_points.append({
                                    "date": data.time_stamp.strftime("%Y-%m-%d") if data.time_stamp else None,
                                    "cpu_avg": round(data.average, 2),
                                    "cpu_max": round(data.maximum, 2) if data.maximum else None,
                                    "network_in_mb": 0.0  # Will be updated below
                                })
            
            # Query Network, Memory, Disk metrics in one call
            memory_avg: Optional[float] = None
            memory_max: Optional[float] = None
            disk_iops_avg: Optional[float] = None
            disk_throughput_mbps: Optional[float] = None
            network_max = 0.0

            try:
                multi_response = self._azure_call(
                    f"Azure VM multi-metrics ({resource_id})",
                    lambda: self.monitor_client.metrics.list(
                        resource_uri=resource_id,
                        timespan=timespan,
                        interval="P1D",
                        metricnames="Network In Total,Available Memory Bytes,OS Disk IOPS Consumed Percentage,OS Disk Bandwidth Consumed Percentage",
                        aggregation="Average,Maximum"
                    ),
                )

                network_values: List[float] = []
                memory_pcts: List[float] = []
                disk_iops_pcts: List[float] = []
                disk_bw_pcts: List[float] = []
                net_idx = 0

                for metric in multi_response.value:
                    metric_name = metric.name.value
                    for ts in metric.timeseries:
                        for data in ts.data:
                            if "Network In" in metric_name and data.maximum is not None:
                                network_mb = data.maximum / (1024 * 1024)
                                network_values.append(network_mb)
                                if net_idx < len(data_points):
                                    data_points[net_idx]["network_in_mb"] = round(network_mb, 2)
                                net_idx += 1
                            elif "Available Memory" in metric_name and data.average is not None:
                                memory_pcts.append(data.average)
                            elif "IOPS Consumed" in metric_name and data.average is not None:
                                disk_iops_pcts.append(data.average)
                            elif "Bandwidth Consumed" in metric_name and data.average is not None:
                                disk_bw_pcts.append(data.average)

                network_max = max(network_values) if network_values else 0.0
                if memory_pcts:
                    memory_avg = round(sum(memory_pcts) / len(memory_pcts), 2)
                    memory_max = round(max(memory_pcts), 2)
                if disk_iops_pcts:
                    disk_iops_avg = round(sum(disk_iops_pcts) / len(disk_iops_pcts), 2)
                if disk_bw_pcts:
                    disk_throughput_mbps = round(sum(disk_bw_pcts) / len(disk_bw_pcts), 2)
            except Exception as e:
                logger.warning(f"Failed to get extended metrics for {resource_id}: {e}")

            # Calculate aggregates
            if cpu_averages:
                cpu_avg = sum(cpu_averages) / len(cpu_averages)
                cpu_max = max(cpu_maximums) if cpu_maximums else cpu_avg
                has_data = True
            else:
                cpu_avg = None
                cpu_max = None
                has_data = False

            return {
                "cpu_avg": round(cpu_avg, 2) if cpu_avg is not None else None,
                "cpu_max": round(cpu_max, 2) if cpu_max is not None else None,
                "cpu_utilization": round(cpu_avg, 2) if cpu_avg is not None else None,
                "cpu_utilization_avg": round(cpu_avg, 2) if cpu_avg is not None else None,
                "memory_avg_pct": memory_avg,
                "memory_max_pct": memory_max,
                "disk_iops_consumed_pct": disk_iops_avg,
                "disk_bandwidth_consumed_pct": disk_throughput_mbps,
                "network_in_max_mb": round(network_max, 2),
                "data_points": data_points,
                "days_with_data": len(cpu_averages),
                "has_data": has_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics for {resource_id}: {e}")
            return {
                "cpu_avg": None,
                "cpu_max": None,
                "network_in_max_mb": 0.0,
                "data_points": [],
                "days_with_data": 0,
                "has_data": False,
                "error": str(e)
            }
    
    def _get_vm_metrics_hourly(self, resource_id: str, lookback_days: int = 30) -> Optional[List[float]]:
        """
        Fetch hourly CPU metrics for workload pattern analysis.

        Returns a list of hourly CPU average values (up to 720 points for 30 days)
        ordered chronologically, or None if the fetch fails.
        """
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=lookback_days)
            timespan = (
                f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
                f"{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

            response = self._azure_call(
                f"Azure VM hourly CPU metrics ({resource_id})",
                lambda: self.monitor_client.metrics.list(
                    resource_uri=resource_id,
                    timespan=timespan,
                    interval="PT1H",
                    metricnames="Percentage CPU",
                    aggregation="Average"
                ),
            )

            hourly_values: List[float] = []
            for metric in response.value:
                if metric.name.value == "Percentage CPU":
                    for ts in metric.timeseries:
                        for data in ts.data:
                            hourly_values.append(data.average if data.average is not None else 0.0)

            if len(hourly_values) < 48:
                return None

            return hourly_values

        except Exception as e:
            logger.debug(f"Hourly metrics fetch failed for {resource_id}: {e}")
            return None

    def _calculate_confidence(
        self,
        avg_cpu: float,
        max_network_mb: float,
        days_with_data: int,
        has_public_ip: bool,
        instance_age_days: int
    ) -> float:
        """
        Calculate confidence score for zombie VM classification.
        
        Weighs multiple factors to produce a confidence score from 0.0 to 1.0.
        
        Args:
            avg_cpu: Average CPU percentage
            max_network_mb: Maximum network ingress in MB
            days_with_data: Number of days with metrics data
            has_public_ip: Whether VM has a public IP attached
            instance_age_days: Age of the VM in days
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        
        # CPU weight (40%)
        if avg_cpu < 0.5:
            score += 0.40
        elif avg_cpu < 1.0:
            score += 0.30
        elif avg_cpu < 2.0:
            score += 0.15
        
        # Network weight (30%)
        if max_network_mb < 1.0:
            score += 0.30
        elif max_network_mb < 3.0:
            score += 0.20
        elif max_network_mb < 5.0:
            score += 0.10
        
        # Duration weight (20%)
        if days_with_data >= 7:
            score += 0.20
        elif days_with_data >= 3:
            score += 0.10
        
        # Age bonus (10%)
        if instance_age_days > 90:
            score += 0.10
        
        # Negative: public IP exposure reduces confidence slightly
        if has_public_ip:
            score -= 0.05
        
        # Clamp to valid range
        return round(max(0.0, min(1.0, score)), 2)
    
    def _get_resource_cost(
        self,
        vm_size: str,
        resource_id: str = ""
    ) -> tuple[float, bool]:
        """
        Get cost for a resource from Azure Cost Management.
        
        Checks the real cost map populated by _fetch_real_costs. If exact
        resource cost is unavailable, returns 0.0 and marks the source as
        unavailable instead of writing a fixed fallback price as real scan data.
        
        Args:
            vm_size: Azure VM size name (for estimation fallback)
            resource_id: Full Azure resource ID (for real cost lookup)
            
        Returns:
            Tuple of (monthly_cost: float, is_real: bool)
            is_real is True if cost came from Cost Management API
        """
        # Try real cost first
        if hasattr(self, '_real_costs') and resource_id:
            real = self._real_costs.get(resource_id.lower())
            if real and (real.get("actual_cost_mtd", 0) or real.get("actual_cost_30d", 0)) > 0:
                actual = real.get("actual_cost_mtd", real.get("actual_cost_30d", 0))
                return round(actual, 2), True
        
        return 0.0, False

    def _lookup_actual_resource_cost(self, resource_id: str = "") -> tuple[float, bool]:
        """Return exact current-month resource cost from Azure Cost Management when present."""
        if hasattr(self, '_real_costs') and resource_id:
            real = self._real_costs.get(resource_id.lower())
            if real and (real.get("actual_cost_mtd", 0) or real.get("actual_cost_30d", 0)) > 0:
                actual = real.get("actual_cost_mtd", real.get("actual_cost_30d", 0))
                return round(float(actual), 2), True
        return 0.0, False
    
    def _estimate_vm_cost(self, vm_size: str) -> float:
        """
        Legacy compatibility method.
        VM shape alone is not exact billing data, so this returns 0.0.
        
        Args:
            vm_size: Azure VM size name (e.g., "Standard_B2s")
            
        Returns:
            0.0 because exact monthly cost is not available from the VM shape alone.
        """
        return 0.0
    
    def _estimate_carbon(
        self,
        vm_size: str,
        region: str,
        hours_running: float
    ) -> float:
        """Estimate carbon footprint for a running VM using the shared carbon model."""
        monthly_kg = estimate_monthly_carbon_kg("azure", vm_size, region)
        proportion = hours_running / 730.0 if hours_running < 730 else 1.0
        return round(monthly_kg * proportion, 3)
    
    def _fetch_real_costs(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch actual cost data from Azure Cost Management API.
        
        Returns a map of lowercase resource_id -> cost info.
        Returns empty dict if Cost Management API is unavailable
        (user hasn't granted Cost Management Reader role, or SDK
        not installed, or any other failure).
        
        This method NEVER raises exceptions — it always returns
        a dict (possibly empty) so the scanner can keep running while
        marking per-resource pricing unavailable where Azure does not
        return exact billing data.
        
        Returns:
            Dict mapping lowercase resource_id -> {
                "actual_cost_mtd": float,
                "daily_costs": list of {"date": str, "amount": float},
                "currency": str
            }
        """
        try:
            from azure.mgmt.costmanagement import CostManagementClient
        except ImportError:
            logger.warning(
                "azure-mgmt-costmanagement not installed. "
                "Exact Azure resource costs unavailable. Install with: "
                "pip install azure-mgmt-costmanagement"
            )
            return {}
        
        try:
            cost_client = CostManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            end_date = datetime.now(timezone.utc)
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            scope = f"/subscriptions/{self.subscription_id}"

            from azure.mgmt.costmanagement.models import (
                QueryDefinition,
                QueryTimePeriod,
                QueryDataset,
                QueryAggregation,
                QueryGrouping,
            )

            # Query 1: Cost per resource (current month-to-date total)
            resource_query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date,
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum"),
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ResourceId"),
                    ],
                ),
            )

            result = self._azure_cost_call(
                "Azure Cost Management resource usage query",
                lambda: cost_client.query.usage(
                    scope=scope,
                    parameters=resource_query
                ),
            )
            
            cost_map: Dict[str, Dict[str, Any]] = {}
            
            if result.rows:
                for row in result.rows:
                    cost = float(row[0])
                    resource_id = str(row[1]).lower()
                    currency = str(row[2]) if len(row) > 2 else "USD"
                    
                    cost_usd = self._to_usd(cost, currency)
                    cost_map[resource_id] = {
                        "actual_cost_mtd": cost_usd,
                        "actual_cost_30d": cost_usd,  # Backward-compatible key; value is MTD.
                        "daily_costs": [],
                        "currency": "USD",
                        "original_currency": currency,
                        "original_amount": round(cost, 2),
                        "period": "current_month_to_date",
                        "period_start": start_date.date().isoformat(),
                        "period_end": end_date.date().isoformat(),
                    }
            
            # ── Query 2: Daily breakdown for trending ──
            daily_query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date,
                ),
                dataset=QueryDataset(
                    granularity="Daily",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum"),
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ResourceId"),
                    ],
                ),
            )

            try:
                daily_result = self._azure_cost_call(
                    "Azure Cost Management daily resource usage query",
                    lambda: cost_client.query.usage(
                        scope=scope,
                        parameters=daily_query
                    ),
                )
                
                if daily_result.rows:
                    for row in daily_result.rows:
                        cost = float(row[0])
                        date_val = str(row[1])
                        resource_id = str(row[2]).lower()
                        currency = str(row[3]) if len(row) > 3 else cost_map.get(resource_id, {}).get("original_currency", "USD")
                        
                        # Format date: API returns YYYYMMDD or int
                        if len(date_val) == 8:
                            formatted_date = (
                                f"{date_val[:4]}-{date_val[4:6]}-"
                                f"{date_val[6:]}"
                            )
                        else:
                            formatted_date = date_val
                        
                        if resource_id in cost_map:
                            cost_map[resource_id]["daily_costs"].append({
                                "date": formatted_date,
                                "amount": round(self._to_usd(cost, currency), 4)
                            })
            except Exception as e:
                logger.debug(
                    f"Daily cost breakdown failed (non-critical): {e}"
                )
            
            logger.info(
                f"Fetched real costs for {len(cost_map)} resources "
                f"from Azure Cost Management"
            )
            return cost_map
            
        except HttpResponseError as e:
            error_str = str(e)
            if "429" in error_str or "Too many requests" in error_str:
                self._cost_rate_limited = True
                logger.warning("Azure Cost Management rate-limited (429). Exact resource costs unavailable.")
            elif "AuthorizationFailed" in error_str or "403" in error_str:
                logger.warning(
                    "Cost Management Reader role not granted. "
                    "Exact Azure resource costs unavailable."
                )
            else:
                logger.warning(
                    f"Azure Cost Management API error: {e}. "
                    f"Exact Azure resource costs unavailable."
                )
            return {}
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Too many requests" in error_str:
                self._cost_rate_limited = True
            logger.warning(
                f"Could not fetch real costs (falling back to "
                f"billing-unavailable resource costs): {e}"
            )
            return {}
    
    def _fetch_subscription_cost_by_service(self) -> Dict[str, Any]:
        """
        Fetch total subscription cost grouped by service name.
        Used for the service breakdown pie chart on dashboard.
        
        Returns:
            Dict with:
                "total": float (current month-to-date cost),
                "by_service": {"Virtual Machines": 123.45, ...},
                "daily_totals": [{"date": "2025-01-20", "amount": 12.34}],
                "currency": str
            Or empty dict on failure.
        """
        try:
            from azure.mgmt.costmanagement import CostManagementClient
        except ImportError:
            return {}
        
        try:
            cost_client = CostManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
            
            end_date = datetime.now(timezone.utc)
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            scope = f"/subscriptions/{self.subscription_id}"

            from azure.mgmt.costmanagement.models import (
                QueryDefinition,
                QueryTimePeriod,
                QueryDataset,
                QueryAggregation,
                QueryGrouping,
            )

            # Service breakdown (current month-to-date)
            service_query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date,
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum"),
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName"),
                    ],
                ),
            )

            result = self._azure_cost_call(
                "Azure Cost Management service usage query",
                lambda: cost_client.query.usage(
                    scope=scope,
                    parameters=service_query
                ),
            )

            by_service: Dict[str, float] = {}
            total = 0.0
            billing_currency = "USD"

            if result.rows:
                for row in result.rows:
                    cost_raw = float(row[0])
                    service = str(row[1])
                    row_currency = str(row[2]) if len(row) > 2 else billing_currency
                    billing_currency = row_currency or billing_currency
                    cost_usd = self._to_usd(cost_raw, billing_currency)
                    by_service[service] = cost_usd
                    total += cost_usd
            if billing_currency != "USD":
                logger.info(
                    f"Converted subscription costs from "
                    f"{billing_currency} to USD (rate: "
                    f"{self.CURRENCY_TO_USD.get(billing_currency, 1.0)})"
                )

            # Daily totals for trend chart
            daily_totals: List[Dict[str, Any]] = []
            try:
                daily_query = QueryDefinition(
                    type="ActualCost",
                    timeframe="Custom",
                    time_period=QueryTimePeriod(
                        from_property=start_date,
                        to=end_date,
                    ),
                    dataset=QueryDataset(
                        granularity="Daily",
                        aggregation={
                            "totalCost": QueryAggregation(name="Cost", function="Sum"),
                        },
                    ),
                )

                daily_result = self._azure_cost_call(
                    "Azure Cost Management daily subscription totals query",
                    lambda: cost_client.query.usage(
                        scope=scope,
                        parameters=daily_query
                    ),
                )
                
                if daily_result.rows:
                    for row in daily_result.rows:
                        cost_raw = float(row[0])
                        date_val = str(row[1])
                        row_currency = str(row[2]) if len(row) > 2 else billing_currency
                        cost_usd = self._to_usd(
                            cost_raw, row_currency
                        )
                        
                        if len(date_val) == 8:
                            formatted_date = (
                                f"{date_val[:4]}-{date_val[4:6]}-"
                                f"{date_val[6:]}"
                            )
                        else:
                            formatted_date = date_val
                        
                        daily_totals.append({
                            "date": formatted_date,
                            "amount": round(cost_usd, 4)
                        })
            except Exception as e:
                logger.debug(f"Daily totals fetch failed: {e}")
            
            logger.info(
                f"Total subscription cost (MTD, USD-normalized): "
                f"${total:.2f} across {len(by_service)} services"
            )
            
            return {
                "total": round(total, 2),
                "by_service": by_service,
                "daily_totals": daily_totals,
                "currency": "USD",
                "original_currency": billing_currency,
                "period": "current_month_to_date",
                "period_start": start_date.date().isoformat(),
                "period_end": end_date.date().isoformat(),
            }
            
        except Exception as e:
            logger.warning(
                f"Could not fetch subscription cost breakdown: {e}"
            )
            return {}

    def _create_finding(
        self,
        cloud_resource_id: str,
        resource_name: str,
        service_type: str,
        cost: float,
        status: str,
        waste_type: Optional[str],
        waste_reason: Optional[str],
        confidence_score: float,
        metrics_data: Dict[str, Any],
        region: str,
        tags: Dict[str, str],
        metadata: Dict[str, Any],
        governance_violations: List[Dict[str, Any]],
        region_compliance: str = "compliant",
        carbon_footprint_kg: float = 0.0
    ) -> Dict[str, Any]:
        """Create a standardized finding dictionary."""
        utilization_score = None
        if isinstance(metadata, dict):
            utilization_score = metadata.get("utilization_score")
        if utilization_score is None and isinstance(metrics_data, dict):
            cpu = metrics_data.get("cpu_utilization") or metrics_data.get("cpu_avg")
            if cpu is not None:
                utilization_score = round(float(cpu), 1)

        return {
            "cloud_resource_id": cloud_resource_id,
            "resource_name": resource_name,
            "service_type": service_type,
            "cost": cost,
            "status": status,
            "waste_type": waste_type,
            "waste_reason": waste_reason,
            "confidence_score": confidence_score,
            "utilization_score": utilization_score,
            "metrics_data": metrics_data,
            "region": region,
            "tags": tags,
            "metadata": metadata,
            "governance_violations": governance_violations,
            "provider": "azure",
            "region_compliance": region_compliance,
            "carbon_footprint_kg": carbon_footprint_kg,
            "last_scanned_at": datetime.now(timezone.utc).isoformat()
        }

    def _apply_real_cost_overrides(self) -> int:
        """
        Backfill/override finding costs using Azure Cost Management map.
        This keeps scan success deterministic while maximizing real-cost coverage.
        """
        if not hasattr(self, "_real_costs") or not self._real_costs:
            return 0

        updated = 0
        for finding in self.findings:
            resource_id = str(finding.get("cloud_resource_id", "") or "").lower()
            if not resource_id:
                continue

            real = self._real_costs.get(resource_id)
            if not real:
                continue

            actual = float(real.get("actual_cost_mtd", real.get("actual_cost_30d", 0)) or 0)
            if actual <= 0:
                continue

            current = float(finding.get("cost", 0) or 0)
            metadata = finding.get("metadata") or {}
            source = str(metadata.get("cost_source", "") or "").lower()

            if source == "actual" and abs(current - actual) < 0.01:
                continue

            finding["cost"] = round(actual, 2)
            metadata["cost_source"] = COST_SOURCE_ACTUAL
            finding["metadata"] = metadata
            updated += 1

        return updated
    
    def scan_virtual_machines(self) -> None:
        """
        Scan all virtual machines for waste patterns.
        
        Detects:
            - Stopped VMs (charges compute cost)
            - Deallocated VMs (charges disk cost only)
            - Zombie VMs (running but idle based on metrics)
            - Healthy VMs (active utilization)
        """
        logger.info("Scanning Virtual Machines...")
        
        try:
            vms = self._azure_list(
                "Azure virtual machines list",
                self.compute_client.virtual_machines.list_all,
            )
            logger.info(f"Found {len(vms)} virtual machines")
            
            for vm in vms:
                try:
                    # Extract basic info
                    cloud_resource_id = vm.id
                    resource_name = vm.name
                    region = vm.location
                    vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "Unknown"
                    tags = dict(vm.tags) if vm.tags else {}
                    
                    # Parse resource group from ID
                    parts = vm.id.split("/")
                    resource_group = parts[4] if len(parts) > 4 else "unknown"
                    # Get power state and instance age
                    power_state = "unknown"
                    instance_age_days = 0
                    
                    try:
                        instance_view = self._azure_call(
                            f"Azure VM instance view ({vm.name})",
                            lambda: self.compute_client.virtual_machines.instance_view(
                                resource_group_name=resource_group,
                                vm_name=vm.name
                            ),
                        )
                        for s in instance_view.statuses:
                            if s.code and s.code.startswith("PowerState/"):
                                power_state = s.code.split("/")[1]
                            # FIXED: Extract provisioning time for age calculation
                            if s.code and s.code.startswith("ProvisioningState/") and s.time:
                                prov_time = s.time
                                if prov_time.tzinfo is None:
                                    prov_time = prov_time.replace(tzinfo=timezone.utc)
                                instance_age_days = (datetime.now(timezone.utc) - prov_time).days
                    except Exception as e:
                        logger.warning(f"Failed to get instance view for {vm.name}: {e}")
                    
                    # FIXED: Also try vm.time_created (available in newer SDK versions)
                    if instance_age_days == 0:
                        try:
                            if hasattr(vm, 'time_created') and vm.time_created:
                                created = vm.time_created
                                if created.tzinfo is None:
                                    created = created.replace(tzinfo=timezone.utc)
                                instance_age_days = (datetime.now(timezone.utc) - created).days
                        except Exception:
                            pass
                    
                    # FIXED: Check if VM has a public IP by inspecting NICs
                    has_public_ip = False
                    try:
                        if vm.network_profile and vm.network_profile.network_interfaces:
                            for nic_ref in vm.network_profile.network_interfaces:
                                nic_parts = nic_ref.id.split("/")
                                nic_rg = nic_parts[4]
                                nic_name = nic_parts[-1]
                                nic = self._azure_call(
                                    f"Azure network interface get ({nic_name})",
                                    lambda: self.network_client.network_interfaces.get(
                                        resource_group_name=nic_rg,
                                        network_interface_name=nic_name
                                    ),
                                )
                                if nic.ip_configurations:
                                    for ip_config in nic.ip_configurations:
                                        if ip_config.public_ip_address:
                                            has_public_ip = True
                                            break
                                if has_public_ip:
                                    break
                    except Exception as e:
                        logger.debug(f"Could not check public IP for {vm.name}: {e}")
                    
                    # Calculate monthly cost and carbon
                    monthly_cost, cost_is_real = self._get_resource_cost(
                        vm_size, vm.id
                    )
                    hours_running = 730  # Approximate month
                    carbon = self._estimate_carbon(vm_size, region, hours_running)
                    
                    # Extract VNet/Subnet from NIC for architecture topology
                    vm_vnet_id = None
                    vm_subnet_id = None
                    try:
                        if vm.network_profile and vm.network_profile.network_interfaces:
                            primary_nic_ref = vm.network_profile.network_interfaces[0]
                            nic_parts = primary_nic_ref.id.split("/")
                            nic_rg = nic_parts[4]
                            nic_name = nic_parts[-1]
                            nic = self._azure_call(
                                f"Azure NIC topology ({nic_name})",
                                lambda: self.network_client.network_interfaces.get(
                                    resource_group_name=nic_rg,
                                    network_interface_name=nic_name
                                ),
                            )
                            if nic and nic.ip_configurations:
                                for ip_config in nic.ip_configurations:
                                    if ip_config.subnet and ip_config.subnet.id:
                                        subnet_parts = ip_config.subnet.id.split("/")
                                        for idx, part in enumerate(subnet_parts):
                                            if part.lower() == "virtualnetworks" and idx + 1 < len(subnet_parts):
                                                vm_vnet_id = subnet_parts[idx + 1]
                                            if part.lower() == "subnets" and idx + 1 < len(subnet_parts):
                                                vm_subnet_id = subnet_parts[idx + 1]
                                        break
                    except Exception as e:
                        logger.debug(f"Could not extract VNet/Subnet for {vm.name}: {e}")

                    base_metadata = {
                        "vm_size": vm_size,
                        "power_state": power_state,
                        "cost_source": COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE,
                        "vnet_id": vm_vnet_id,
                        "subnet_id": vm_subnet_id,
                    }

                    # GPU instance detection (NC/ND/NV series)
                    from ..core.gpu_specs import AZURE_GPU_PREFIXES, AZURE_GPU_SPECS, is_gpu_instance_type
                    vm_size_lower = vm_size.lower().replace(" ", "").replace("-", "_")
                    if is_gpu_instance_type(vm_size_lower, provider="azure"):
                        base_metadata["is_gpu_instance"] = True
                        base_metadata["instance_type"] = vm_size
                        spec = AZURE_GPU_SPECS.get(vm_size_lower)
                        if spec:
                            base_metadata["gpu_type"] = f"{spec.gpu_count}× {spec.gpu_model}"
                            base_metadata["gpu_count"] = spec.gpu_count
                            base_metadata["supports_mig"] = spec.supports_mig
                            base_metadata["gpu_memory_gb"] = spec.gpu_memory_gb
                            base_metadata["gpu_architecture"] = spec.architecture
                            if spec.supports_mig:
                                base_metadata["gpu_optimization_insight"] = (
                                    f"MIG-capable {spec.gpu_model} detected on Azure. "
                                    f"Partition each GPU into up to {spec.mig_slices_per_gpu} slices for multi-tenant workloads."
                                )
                            elif "v100" in spec.gpu_model.lower():
                                base_metadata["gpu_optimization_insight"] = (
                                    "V100 GPU on Azure. Consider NC T4 v3 for inference or "
                                    "specialized GPU clouds (Lambda Labs, RunPod) for 40-60% savings."
                                )
                            else:
                                base_metadata["gpu_optimization_insight"] = (
                                    f"{spec.gpu_model} GPU detected. Compare cost vs. specialized clouds."
                                )
                    
                    # CLASSIFICATION
                    if power_state == "stopped":
                        stopped_reason = (
                            f"VM is stopped but NOT deallocated. Azure reported ${monthly_cost:.2f}/mo "
                            "for this resource. Deallocate or delete to stop charges."
                            if cost_is_real
                            else (
                                "VM is stopped but NOT deallocated. Exact compute cost is unavailable "
                                "because Cost Management did not return a resource-level amount."
                            )
                        )
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Virtual Machine",
                            cost=monthly_cost,
                            status="waste",
                            waste_type="stopped_vm",
                            waste_reason=stopped_reason,
                            confidence_score=0.99,
                            metrics_data={"power_state": "stopped"},
                            region=region,
                            tags=tags,
                            metadata=base_metadata,
                            governance_violations=[],
                            carbon_footprint_kg=0
                        ))
                        
                    elif power_state == "deallocated":
                        deallocated_cost = monthly_cost if cost_is_real else 0.0
                        age_note = f" Deallocated for {instance_age_days}+ days." if instance_age_days > 7 else ""
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Virtual Machine",
                            cost=deallocated_cost,
                            status="waste",
                            waste_type="deallocated_vm",
                            waste_reason=(
                                f"Deallocated {vm_size} VM — compute charges stopped but attached "
                                f"disks still incur storage cost.{age_note} "
                                f"Action: If no longer needed, delete the VM and its disks to reclaim all costs."
                            ),
                            confidence_score=0.70,
                            metrics_data={"power_state": "deallocated"},
                            region=region,
                            tags=tags,
                            metadata=base_metadata,
                            governance_violations=[],
                            carbon_footprint_kg=0
                        ))
                        
                    elif power_state == "running":
                        metrics = self._get_vm_metrics(vm.id)
                        
                        if not metrics["has_data"]:
                            self.findings.append(self._create_finding(
                                cloud_resource_id=cloud_resource_id,
                                resource_name=resource_name,
                                service_type="Virtual Machine",
                                cost=monthly_cost,
                                status="unknown",
                                waste_type=None,
                                waste_reason=(
                                    "Unable to retrieve metrics. VM may be too new or "
                                    "monitoring not enabled."
                                ),
                                confidence_score=0.0,
                                metrics_data=metrics,
                                region=region,
                                tags=tags,
                                metadata=base_metadata,
                                governance_violations=[],
                                carbon_footprint_kg=carbon
                            ))
                            
                        elif metrics["days_with_data"] < 3:
                            self.findings.append(self._create_finding(
                                cloud_resource_id=cloud_resource_id,
                                resource_name=resource_name,
                                service_type="Virtual Machine",
                                cost=monthly_cost,
                                status="unknown",
                                waste_type=None,
                                waste_reason=(
                                    f"Only {metrics['days_with_data']} days of metrics "
                                    f"available. Need at least 3 days for accurate "
                                    f"classification."
                                ),
                                confidence_score=0.0,
                                metrics_data=metrics,
                                region=region,
                                tags=tags,
                                metadata=base_metadata,
                                governance_violations=[],
                                carbon_footprint_kg=carbon
                            ))
                            
                        else:
                            avg_cpu = metrics["cpu_avg"]
                            max_cpu = metrics["cpu_max"]
                            max_net = metrics["network_in_max_mb"]
                            days = metrics["days_with_data"]
                            mem_avg = metrics.get("memory_avg_pct")
                            disk_iops = metrics.get("disk_iops_consumed_pct")
                            disk_bw = metrics.get("disk_bandwidth_consumed_pct")

                            # Build utilization summary for every VM
                            util_parts = [f"CPU {avg_cpu:.1f}% avg / {max_cpu:.1f}% peak"]
                            if mem_avg is not None:
                                util_parts.append(f"Memory {mem_avg:.0f}%")
                            if disk_iops is not None:
                                util_parts.append(f"Disk IOPS {disk_iops:.0f}%")
                            if disk_bw is not None:
                                util_parts.append(f"Disk BW {disk_bw:.0f}%")
                            util_parts.append(f"Network {max_net:.1f}MB peak")
                            utilization_summary = " | ".join(util_parts)

                            # Compute composite utilization score (0-100)
                            scores = [avg_cpu]
                            if mem_avg is not None:
                                scores.append(mem_avg)
                            if disk_iops is not None:
                                scores.append(disk_iops)
                            utilization_score = round(max(scores), 1)

                            enriched_metadata = {
                                **base_metadata,
                                "avg_cpu_7d": avg_cpu,
                                "max_cpu_7d": max_cpu,
                                "memory_avg_pct": mem_avg,
                                "disk_iops_consumed_pct": disk_iops,
                                "disk_bandwidth_consumed_pct": disk_bw,
                                "max_network_mb_7d": max_net,
                                "utilization_score": utilization_score,
                                "utilization_summary": utilization_summary,
                                "observation_days": days,
                            }

                            # CLASSIFICATION based on utilization score
                            # Idle: < 2% CPU AND < 5MB network (truly doing nothing)
                            if avg_cpu < self.CPU_THRESHOLD and max_net < self.NETWORK_THRESHOLD_MB and (max_cpu is None or max_cpu < 10.0):
                                confidence = self._calculate_confidence(
                                    avg_cpu, max_net, days, has_public_ip, instance_age_days
                                )
                                self.findings.append(self._create_finding(
                                    cloud_resource_id=cloud_resource_id,
                                    resource_name=resource_name,
                                    service_type="Virtual Machine",
                                    cost=monthly_cost,
                                    status="zombie",
                                    waste_type="idle",
                                    waste_reason=(
                                        f"IDLE: {utilization_summary} over {days} days. "
                                        f"This {vm_size} is running but processing no workload."
                                    ),
                                    confidence_score=confidence,
                                    metrics_data=metrics,
                                    region=region,
                                    tags=tags,
                                    metadata=enriched_metadata,
                                    governance_violations=[],
                                    carbon_footprint_kg=carbon
                                ))

                            # === WORKLOAD PATTERN ANALYSIS ===
                            # For all non-zombie running VMs, fetch 30-day hourly metrics
                            # and classify the workload pattern for intelligent recommendations.
                            elif days >= 5:
                                from ..core.workload_patterns import (
                                    MetricTimeSeries,
                                    classify_pattern,
                                    generate_recommendation,
                                    WorkloadPattern,
                                    RecommendationType,
                                )

                                hourly_data = self._get_vm_metrics_hourly(vm.id, lookback_days=30)
                                pattern_metadata = {**enriched_metadata}

                                if hourly_data and len(hourly_data) >= 48:
                                    series = MetricTimeSeries(hourly_values=hourly_data, metric_name="cpu")
                                    analysis = classify_pattern(series)
                                    vm_vcpus = int(vm_size.split("_")[-1].replace("s", "").replace("d", "")) if "_" in vm_size else 2
                                    rec = generate_recommendation(
                                        analysis,
                                        current_vm_size=vm_size,
                                        current_monthly_cost=monthly_cost,
                                        current_vm_vcpus=max(vm_vcpus, 1),
                                    )

                                    pattern_metadata["workload_pattern"] = analysis.pattern.value
                                    pattern_metadata["peak_trough_ratio"] = analysis.peak_trough_ratio
                                    pattern_metadata["peak_avg_cpu"] = analysis.peak_avg
                                    pattern_metadata["trough_avg_cpu"] = analysis.trough_avg
                                    pattern_metadata["p90_cpu"] = analysis.p90
                                    pattern_metadata["p95_cpu"] = analysis.p95
                                    pattern_metadata["observation_days"] = analysis.observation_days
                                    pattern_metadata["recommendation_type"] = rec.type.value
                                    pattern_metadata["recommendation_explanation"] = rec.explanation
                                    pattern_metadata["estimated_savings_pct"] = rec.estimated_savings_pct
                                    pattern_metadata["pattern_confidence"] = rec.confidence

                                    if rec.autoscale:
                                        pattern_metadata["autoscale_min_instances"] = rec.autoscale.min_instances
                                        pattern_metadata["autoscale_max_instances"] = rec.autoscale.max_instances
                                        pattern_metadata["autoscale_scale_out_cpu"] = rec.autoscale.scale_out_cpu_pct
                                        pattern_metadata["autoscale_scale_in_cpu"] = rec.autoscale.scale_in_cpu_pct
                                        pattern_metadata["autoscale_cooldown_min"] = rec.autoscale.cooldown_minutes

                                    if rec.schedule:
                                        pattern_metadata["schedule_stop_days"] = rec.schedule.stop_days
                                        pattern_metadata["schedule_savings_pct"] = rec.schedule.estimated_savings_pct

                                    # Determine status based on recommendation
                                    if rec.type == RecommendationType.AUTOSCALE:
                                        status_val = "underutilized"
                                        waste_type_val = "autoscale_candidate"
                                    elif rec.type == RecommendationType.SCHEDULE:
                                        status_val = "underutilized"
                                        waste_type_val = "schedule_candidate"
                                    elif rec.type == RecommendationType.RIGHTSIZE:
                                        status_val = "underutilized"
                                        waste_type_val = "underutilized"
                                    elif rec.type == RecommendationType.SPOT_CANDIDATE:
                                        status_val = "underutilized"
                                        waste_type_val = "spot_candidate"
                                    else:
                                        status_val = "healthy"
                                        waste_type_val = None

                                    self.findings.append(self._create_finding(
                                        cloud_resource_id=cloud_resource_id,
                                        resource_name=resource_name,
                                        service_type="Virtual Machine",
                                        cost=monthly_cost,
                                        status=status_val,
                                        waste_type=waste_type_val,
                                        waste_reason=rec.explanation,
                                        confidence_score=rec.confidence,
                                        metrics_data=metrics,
                                        region=region,
                                        tags=tags,
                                        metadata=pattern_metadata,
                                        governance_violations=[],
                                        carbon_footprint_kg=carbon
                                    ))

                                else:
                                    # Fallback: no hourly data, use simple threshold
                                    if utilization_score < 25.0:
                                        self.findings.append(self._create_finding(
                                            cloud_resource_id=cloud_resource_id,
                                            resource_name=resource_name,
                                            service_type="Virtual Machine",
                                            cost=monthly_cost,
                                            status="underutilized",
                                            waste_type="underutilized",
                                            waste_reason=(
                                                f"UNDERUTILIZED: {utilization_summary} over {days} days. "
                                                f"Hourly pattern data unavailable — based on daily averages, "
                                                f"this {vm_size} appears over-provisioned."
                                            ),
                                            confidence_score=0.6,
                                            metrics_data=metrics,
                                            region=region,
                                            tags=tags,
                                            metadata={**enriched_metadata, "workload_pattern": "unknown"},
                                            governance_violations=[],
                                            carbon_footprint_kg=carbon
                                        ))
                                    else:
                                        self.findings.append(self._create_finding(
                                            cloud_resource_id=cloud_resource_id,
                                            resource_name=resource_name,
                                            service_type="Virtual Machine",
                                            cost=monthly_cost,
                                            status="healthy",
                                            waste_type=None,
                                            waste_reason=(
                                                f"ACTIVE: {utilization_summary} over {days} days. "
                                                f"Resource is utilized within acceptable range."
                                            ),
                                            confidence_score=0.0,
                                            metrics_data=metrics,
                                            region=region,
                                            tags=tags,
                                            metadata={**enriched_metadata, "workload_pattern": "unknown"},
                                            governance_violations=[],
                                            carbon_footprint_kg=carbon
                                        ))
                    else:
                        # Unknown power state
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Virtual Machine",
                            cost=monthly_cost,
                            status="unknown",
                            waste_type=None,
                            waste_reason=f"Unknown power state: {power_state}",
                            confidence_score=0.0,
                            metrics_data={},
                            region=region,
                            tags=tags,
                            metadata=base_metadata,
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing VM {vm.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan virtual machines: {e}")
    
    def scan_managed_disks(self) -> None:
        """
        Scan all managed disks for orphaned disks.
        
        A disk is orphaned if:
            - managed_by is None
            - disk_state is "Unattached"
            - provisioning_state is "Succeeded"
        """
        logger.info("Scanning Managed Disks...")
        
        try:
            disks = self._azure_list(
                "Azure managed disks list",
                self.compute_client.disks.list,
            )
            logger.info(f"Found {len(disks)} managed disks")
            
            for disk in disks:
                try:
                    cloud_resource_id = disk.id
                    resource_name = disk.name
                    region = disk.location
                    tags = dict(disk.tags) if disk.tags else {}
                    size_gb = disk.disk_size_gb or 0
                    sku_name = disk.sku.name if disk.sku else "unknown"
                    disk_state = disk.disk_state if hasattr(disk, 'disk_state') else "Unknown"
                    provisioning_state = disk.provisioning_state or "Unknown"
                    
                    cost, cost_is_real = self._lookup_actual_resource_cost(disk.id)
                    cost_source = COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE
                    
                    # Check if orphaned
                    is_orphaned = (
                        disk.managed_by is None and
                        disk_state == "Unattached" and
                        provisioning_state == "Succeeded"
                    )
                    
                    metrics_data = {
                        "size_gb": size_gb,
                        "sku": sku_name,
                        "disk_state": disk_state,
                        "provisioning_state": provisioning_state,
                        "time_created": disk.time_created.isoformat() if disk.time_created else None,
                        "cost_source": cost_source
                    }
                    
                    if is_orphaned:
                        age_str = ""
                        if disk.time_created:
                            created = disk.time_created
                            if created.tzinfo is None:
                                created = created.replace(tzinfo=timezone.utc)
                            disk_age = (datetime.now(timezone.utc) - created).days
                            age_str = f" Created {disk_age} days ago."
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Managed Disk",
                            cost=cost,
                            status="waste",
                            waste_type="orphan_disk",
                            waste_reason=(
                                f"Unattached {sku_name} disk ({size_gb}GB) wasting storage cost.{age_str} "
                                f"Action: Snapshot data if needed, then delete with "
                                f"'az disk delete --name {resource_name} --resource-group <rg>'."
                            ),
                            confidence_score=0.99,
                            metrics_data=metrics_data,
                            region=region,
                            tags=tags,
                            metadata={"size_gb": size_gb, "sku": sku_name, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                    else:
                        metrics_data["attached_to"] = disk.managed_by
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Managed Disk",
                            cost=cost,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data=metrics_data,
                            region=region,
                            tags=tags,
                            metadata={"size_gb": size_gb, "attached_to": disk.managed_by, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing disk {disk.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan managed disks: {e}")
    
    def scan_public_ips(self) -> None:
        """
        Scan all public IP addresses for zombie IPs.
        
        A public IP is a zombie if ip_configuration is None (not attached to any NIC).
        """
        logger.info("Scanning Public IPs...")
        
        try:
            ips = self._azure_list(
                "Azure public IPs list",
                self.network_client.public_ip_addresses.list_all,
            )
            logger.info(f"Found {len(ips)} public IP addresses")
            
            for ip in ips:
                try:
                    cloud_resource_id = ip.id
                    resource_name = ip.name
                    region = ip.location
                    tags = dict(ip.tags) if ip.tags else {}
                    ip_address = ip.ip_address or "Not assigned"
                    
                    cost, cost_is_real = self._lookup_actual_resource_cost(ip.id)
                    cost_source = COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE
                    
                    is_zombie = ip.ip_configuration is None
                    
                    if is_zombie:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Public IP Address",
                            cost=cost,
                            status="waste",
                            waste_type="zombie_ip",
                            waste_reason=(
                                f"Unused static IP {ip_address} incurring charges while unattached. "
                                f"Azure charges ~$3.65/mo for unassociated static IPs. "
                                f"Action: Release with 'az network public-ip delete --name {resource_name} --resource-group <rg>'."
                            ),
                            confidence_score=0.99,
                            metrics_data={"ip_address": ip_address, "attached": False},
                            region=region,
                            tags=tags,
                            metadata={"ip_address": ip_address, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Public IP Address",
                            cost=cost,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data={
                                "ip_address": ip_address,
                                "attached_to": ip.ip_configuration.id if ip.ip_configuration else None
                            },
                            region=region,
                            tags=tags,
                            metadata={"ip_address": ip_address, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing public IP {ip.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan public IPs: {e}")
    
    def scan_network_security_groups(self) -> None:
        """
        Scan all NSGs for security risks.
        
        Flags NSGs with rules allowing inbound traffic on sensitive ports
        (22, 3389, or *) from Internet/any source.
        """
        logger.info("Scanning Network Security Groups...")
        
        try:
            nsgs = self._azure_list(
                "Azure network security groups list",
                self.network_client.network_security_groups.list_all,
            )
            logger.info(f"Found {len(nsgs)} network security groups")
            
            for nsg in nsgs:
                try:
                    cloud_resource_id = nsg.id
                    resource_name = nsg.name
                    region = nsg.location
                    tags = dict(nsg.tags) if nsg.tags else {}
                    
                    risky_rules: List[Dict[str, Any]] = []
                    rules = nsg.security_rules or []
                    
                    for rule in rules:
                        # Check for risky inbound rules
                        if (rule.direction == "Inbound" and
                            rule.access == "Allow" and
                            rule.source_address_prefix in ["*", "0.0.0.0/0", "Internet"]):
                            
                            # FIXED: Collect ports from BOTH singular and plural fields
                            ports_to_check = set()
                            
                            if rule.destination_port_range:
                                ports_to_check.add(rule.destination_port_range)
                            
                            # FIXED: Azure can put ports in destination_port_ranges (list)
                            if hasattr(rule, 'destination_port_ranges') and rule.destination_port_ranges:
                                ports_to_check.update(rule.destination_port_ranges)
                            
                            is_risky = False
                            matched_port = ""
                            
                            for port in ports_to_check:
                                if port in ["22", "3389", "*"]:
                                    is_risky = True
                                    matched_port = port
                                    break
                                
                                # Check port ranges like "20-25"
                                if "-" in port:
                                    try:
                                        start, end = port.split("-")
                                        start_p, end_p = int(start), int(end)
                                        if start_p <= 22 <= end_p or start_p <= 3389 <= end_p:
                                            is_risky = True
                                            matched_port = port
                                            break
                                    except ValueError:
                                        pass
                            
                            if is_risky:
                                risky_rules.append({
                                    "name": rule.name,
                                    "port": matched_port,
                                    "source": rule.source_address_prefix,
                                    "protocol": rule.protocol,
                                    "all_ports": list(ports_to_check)
                                })
                    
                    if risky_rules:
                        rule_details = []
                        for r in risky_rules:
                            port_label = "ALL PORTS" if r["port"] == "*" else f"port {r['port']}"
                            rule_details.append(
                                f"Rule '{r['name']}' allows {r.get('protocol', 'Any')} "
                                f"from Internet to {port_label}"
                            )
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Network Security Group",
                            cost=0,
                            status="non_compliant",
                            waste_type="security_risk",
                            waste_reason=(
                                f"CRITICAL: {'; '.join(rule_details)}. "
                                f"Restrict source IPs or use Azure Bastion for SSH/RDP access."
                            ),
                            confidence_score=1.0,
                            metrics_data={"risky_rules": risky_rules},
                            region=region,
                            tags=tags,
                            metadata={"total_rules": len(rules)},
                            governance_violations=[]
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Network Security Group",
                            cost=0,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data={"total_rules": len(rules)},
                            region=region,
                            tags=tags,
                            metadata={"total_rules": len(rules)},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing NSG {nsg.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan network security groups: {e}")
    
    def scan_storage_accounts(self) -> None:
        """
        Scan all storage accounts for security misconfigurations.
        
        Checks for:
            - Public blob access enabled
            - HTTPS-only traffic not enforced
            - TLS version below 1.2
        """
        logger.info("Scanning Storage Accounts...")
        
        try:
            accounts = self._azure_list(
                "Azure storage accounts list",
                self.storage_client.storage_accounts.list,
            )
            logger.info(f"Found {len(accounts)} storage accounts")
            
            for account in accounts:
                try:
                    cloud_resource_id = account.id
                    resource_name = account.name
                    region = account.location
                    tags = dict(account.tags) if account.tags else {}
                    cost, cost_is_real = self._lookup_actual_resource_cost(account.id)
                    cost_source = COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE

                    violations: List[str] = []
                    
                    # Check public blob access
                    if getattr(account, 'allow_blob_public_access', None) is True:
                        violations.append("Public blob access enabled")
                    
                    # Check HTTPS-only
                    if getattr(account, 'enable_https_traffic_only', None) is False:
                        violations.append("HTTPS-only traffic not enforced")
                    
                    # Check TLS version
                    min_tls = getattr(account, 'minimum_tls_version', None)
                    if min_tls and min_tls != "TLS1_2":
                        violations.append(f"TLS version {min_tls} (should be TLS1_2)")
                    
                    if violations:
                        actions = []
                        if "Public blob access" in str(violations):
                            actions.append("Disable public access: az storage account update --name " + resource_name + " --allow-blob-public-access false")
                        if "HTTPS" in str(violations):
                            actions.append("Enforce HTTPS: az storage account update --name " + resource_name + " --https-only true")
                        if "TLS" in str(violations):
                            actions.append("Upgrade TLS: az storage account update --name " + resource_name + " --min-tls-version TLS1_2")
                        action_text = " | ".join(actions) if actions else "Review security settings"

                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Storage Account",
                            cost=cost,
                            status="non_compliant",
                            waste_type="security_risk",
                            waste_reason=(
                                f"SECURITY: {'; '.join(violations)}. "
                                f"Action: {action_text}"
                            ),
                            confidence_score=1.0,
                            metrics_data={"violations": violations},
                            region=region,
                            tags=tags,
                            metadata={"sku": account.sku.name if account.sku else "unknown", "cost_source": cost_source},
                            governance_violations=[]
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Storage Account",
                            cost=cost,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data={},
                            region=region,
                            tags=tags,
                            metadata={"sku": account.sku.name if account.sku else "unknown", "cost_source": cost_source},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing storage account {account.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan storage accounts: {e}")
    
    def scan_load_balancers(self) -> None:
        """
        Scan all load balancers for zombie LBs.
        
        A load balancer is zombie if it has no backend pools or all pools are empty.
        """
        logger.info("Scanning Load Balancers...")
        
        try:
            lbs = self._azure_list(
                "Azure load balancers list",
                self.network_client.load_balancers.list_all,
            )
            logger.info(f"Found {len(lbs)} load balancers")
            
            for lb in lbs:
                try:
                    cloud_resource_id = lb.id
                    resource_name = lb.name
                    region = lb.location
                    tags = dict(lb.tags) if lb.tags else {}
                    
                    sku_name = lb.sku.name if lb.sku else "Basic"
                    cost, cost_is_real = self._lookup_actual_resource_cost(lb.id)
                    cost_source = COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE
                    
                    # Check backend pools
                    pools = lb.backend_address_pools or []
                    is_zombie = True
                    
                    for pool in pools:
                        if pool.backend_ip_configurations:
                            is_zombie = False
                            break
                    
                    if not pools:
                        is_zombie = True
                    
                    if is_zombie:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Load Balancer",
                            cost=cost,
                            status="waste",
                            waste_type="zombie_lb",
                            waste_reason=(
                                f"Empty {sku_name} load balancer with zero backend targets. "
                                f"Standard LBs cost ~$18/mo + data charges even with no traffic. "
                                f"Action: Delete if no longer needed, or attach backend VMs."
                            ),
                            confidence_score=0.95,
                            metrics_data={"backend_pools": len(pools), "sku": sku_name},
                            region=region,
                            tags=tags,
                            metadata={"sku": sku_name, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Load Balancer",
                            cost=cost,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data={"backend_pools": len(pools), "sku": sku_name},
                            region=region,
                            tags=tags,
                            metadata={"sku": sku_name, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing load balancer {lb.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan load balancers: {e}")
    
    def scan_generic_resources(self) -> None:
        """
        Scan resources available through broad Azure inventory APIs.
        
        This method serves two purposes:
        1. Discover resources NOT found by specific scanners using broad Azure inventory APIs.
        2. Perform governance checks (tags, region) on every discovered resource.
        
        Resources already found by specific scanners (VMs, Disks, etc.) are updated
        with governance violations. New resources are added as 'Active' with
        generic governance resources with real costs only when available.
        """
        logger.info("Scanning broad Azure inventory (Universal Scan & Governance)...")
        
        try:
            resources: List[Any] = self._fetch_resource_graph_resources()
            inventory_source = "azure-resource-graph"
            if not resources:
                resources = self._fetch_arm_resources()
                inventory_source = "azure-resource-manager"
            logger.info(
                "Universal Scan found %s total resources via %s",
                len(resources),
                inventory_source,
            )
            
            # Map existing findings by lowercase ID for O(1) lookup
            findings_map: Dict[str, int] = {
                f["cloud_resource_id"].lower(): idx
                for idx, f in enumerate(self.findings)
                if f.get("cloud_resource_id")
            }
            
            for resource in resources:
                try:
                    resource_id = self._resource_field(resource, "id", "")
                    resource_name = self._resource_field(resource, "name", "Unknown")
                    region = self._resource_field(resource, "location", None) or "global"
                    tags_raw = self._resource_field(resource, "tags", {}) or {}
                    tags = dict(tags_raw) if isinstance(tags_raw, dict) else {}
                    resource_type = self._resource_field(resource, "type", "Unknown") or "Unknown"
                    kind = self._resource_field(resource, "kind", "") or ""
                    resource_group = self._resource_field(resource, "resourceGroup", "")
                    subscription_id = self._resource_field(resource, "subscriptionId", self.subscription_id)
                    created_time = self._resource_field(resource, "created_time", None)
                    changed_time = self._resource_field(resource, "changed_time", None)
                    
                    # 1. GOVERNANCE CHECKS
                    violations: List[Dict[str, Any]] = []

                    # Tag compliance — only enforce on billable resource types
                    # (skip infrastructure: NSGs, NICs, VNets, subnets, route tables, watchers)
                    resource_type_lower = resource_type.lower()
                    skip_tag_check = any(infra in resource_type_lower for infra in (
                        "networksecuritygroups", "networkinterfaces", "virtualnetworks",
                        "subnets", "routetables", "networkwatchers", "natgateways",
                        "bastionhosts", "privatednszones", "applicationgateways/sslcertificates",
                    ))
                    if not skip_tag_check:
                        tags_lower = {k.lower(): k for k, v in tags.items()}
                        missing_tags = [t for t in self.REQUIRED_TAGS if t.lower() not in tags_lower]
                        if missing_tags:
                            violations.append({
                                "type": "missing_tag",
                                "tags": missing_tags,
                                "message": f"Missing required tags: {', '.join(missing_tags)}"
                            })
                    
                    # Region compliance
                    region_compliant = (
                        region in self.ALLOWED_REGIONS or
                        region == "global" or
                        region is None
                    )
                    if not region_compliant:
                        violations.append({
                            "type": "region_violation",
                            "region": region,
                            "allowed_regions": self.ALLOWED_REGIONS,
                            "message": f"Resource in non-compliant region: {region}"
                        })

                    # Handle case-insensitive ID matching
                    resource_id_lower = resource_id.lower() if resource_id else ""
                    
                    # 2. MERGE OR CREATE
                    if resource_id_lower in findings_map:
                        # Existing resource: Update with governance info
                        idx = findings_map[resource_id_lower]
                        if violations:
                            self.findings[idx]["governance_violations"].extend(violations)
                            # Only mark non_compliant if status is healthy (don't override waste/zombie)
                            if self.findings[idx]["status"] == "healthy":
                                self.findings[idx]["status"] = "non_compliant"
                                self.findings[idx]["waste_type"] = "governance_violation"
                                self.findings[idx]["waste_reason"] = "; ".join(v["message"] for v in violations)
                        
                        if not region_compliant:
                            self.findings[idx]["region_compliance"] = "non_compliant"
                            
                    else:
                        # New Generic Resource: Add to findings
                        # Try to get cost
                        cost = 0.0
                        cost_source = COST_SOURCE_BILLING_UNAVAILABLE
                        
                        # Check real cost first
                        if hasattr(self, '_real_costs') and self._real_costs:
                            real_data = self._real_costs.get(resource_id_lower)
                            if real_data:
                                cost = real_data.get("actual_cost_30d", 0.0)
                                cost_source = COST_SOURCE_ACTUAL
                        
                        # Determine status
                        status = "non_compliant" if violations else "healthy"
                        waste_type = "governance_violation" if violations else None
                        waste_reason = "; ".join(v["message"] for v in violations) if violations else None
                        
                        # Metadata
                        metadata = {
                            "kind": kind,
                            "resource_group": resource_group,
                            "subscription_id": subscription_id,
                            "inventory_source": inventory_source,
                            "created_time": str(created_time) if created_time else None,
                            "changed_time": str(changed_time) if changed_time else None,
                            "cost_source": cost_source
                        }
                        
                        self.findings.append(self._create_finding(
                            cloud_resource_id=resource_id,
                            resource_name=resource_name,
                            service_type=resource_type,
                            cost=cost,
                            status=status,
                            waste_type=waste_type,
                            waste_reason=waste_reason,
                            confidence_score=1.0 if violations else 0.0,
                            metrics_data={},
                            region=region,
                            tags=tags,
                            metadata=metadata,
                            governance_violations=violations,
                            region_compliance="non_compliant" if not region_compliant else "compliant"
                        ))
                        if resource_id_lower:
                            findings_map[resource_id_lower] = len(self.findings) - 1
                        
                except Exception as e:
                    resource_name_for_log = self._resource_field(resource, "name", "unknown")
                    logger.warning(f"Error checking resource {resource_name_for_log}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan generic resources: {e}")
    
    def scan_network_interfaces(self) -> None:
        """
        Scan all network interfaces for orphaned NICs.
        
        A NIC is orphaned if it is not attached to any VM
        (virtual_machine is None) and has no active IP configuration
        linked to a running resource.
        """
        logger.info("Scanning Network Interfaces...")
        
        try:
            nics = self._azure_list(
                "Azure network interfaces list",
                self.network_client.network_interfaces.list_all,
            )
            logger.info(f"Found {len(nics)} network interfaces")
            
            for nic in nics:
                try:
                    cloud_resource_id = nic.id
                    resource_name = nic.name
                    region = nic.location
                    tags = dict(nic.tags) if nic.tags else {}
                    
                    is_orphaned = nic.virtual_machine is None
                    
                    if is_orphaned:
                        has_pip = any(
                            ipc.public_ip_address is not None
                            for ipc in (nic.ip_configurations or [])
                        )
                        pip_warning = " Has an associated public IP (also wasting cost)." if has_pip else ""
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Network Interface",
                            cost=0.0,
                            status="waste",
                            waste_type="orphan_nic",
                            waste_reason=(
                                f"Orphaned NIC not attached to any VM — leftover from a deleted resource.{pip_warning} "
                                f"Action: Delete with 'az network nic delete --name {nic.name} --resource-group <rg>'."
                            ),
                            confidence_score=0.95,
                            metrics_data={
                                "provisioning_state": nic.provisioning_state,
                                "has_public_ip": any(
                                    ipc.public_ip_address is not None
                                    for ipc in (nic.ip_configurations or [])
                                )
                            },
                            region=region,
                            tags=tags,
                            metadata={
                                "provisioning_state": nic.provisioning_state
                            },
                            governance_violations=[]
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Network Interface",
                            cost=0.0,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data={
                                "attached_to": nic.virtual_machine.id
                                if nic.virtual_machine else None
                            },
                            region=region,
                            tags=tags,
                            metadata={},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(
                        f"Error processing NIC {nic.name}: {e}"
                    )
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan network interfaces: {e}")

    
    def scan_snapshots(self) -> None:
        """
        Scan all snapshots for old/orphaned snapshots.
        
        A snapshot is considered waste if:
        - It is older than 30 days (default)
        """
        logger.info("Scanning Snapshots...")
        
        try:
            snapshots = self._azure_list(
                "Azure snapshots list",
                self.compute_client.snapshots.list,
            )
            logger.info(f"Found {len(snapshots)} snapshots")
            
            for snapshot in snapshots:
                try:
                    cloud_resource_id = snapshot.id
                    resource_name = snapshot.name
                    region = snapshot.location
                    tags = dict(snapshot.tags) if snapshot.tags else {}
                    size_gb = snapshot.disk_size_gb or 0
                    
                    cost, cost_is_real = self._lookup_actual_resource_cost(snapshot.id)
                    cost_source = COST_SOURCE_ACTUAL if cost_is_real else COST_SOURCE_BILLING_UNAVAILABLE
                    
                    # Calculate age
                    created_at = snapshot.time_created
                    if created_at and created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    age_days = 0
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    
                    # Waste logic: Older than 30 days
                    is_waste = age_days > 30
                    
                    metric_data = {
                        "size_gb": size_gb,
                        "age_days": age_days,
                        "created_at": created_at.isoformat() if created_at else None
                    }
                    
                    if is_waste:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Snapshot",
                            cost=cost,
                            status="waste",
                            waste_type="old_snapshot",
                            waste_reason=(
                                f"Stale snapshot ({size_gb}GB) is {age_days} days old. "
                                f"Standard snapshots cost ~$0.05/GB/mo = ~${size_gb * 0.05:.2f}/mo. "
                                f"Action: Delete if backup is no longer needed — "
                                f"'az snapshot delete --name {resource_name} --resource-group <rg>'."
                            ),
                            confidence_score=0.8,
                            metrics_data=metric_data,
                            region=region,
                            tags=tags,
                            metadata={"size_gb": size_gb, "age_days": age_days, "cost_source": cost_source},
                            governance_violations=[],
                            carbon_footprint_kg=estimate_storage_carbon_kg(size_gb, region)
                        ))
                    else:
                        self.findings.append(self._create_finding(
                            cloud_resource_id=cloud_resource_id,
                            resource_name=resource_name,
                            service_type="Snapshot",
                            cost=cost,
                            status="healthy",
                            waste_type=None,
                            waste_reason=None,
                            confidence_score=0.0,
                            metrics_data=metric_data,
                            region=region,
                            tags=tags,
                            metadata={"size_gb": size_gb, "age_days": age_days, "cost_source": cost_source},
                            governance_violations=[]
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing snapshot {snapshot.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to scan snapshots: {e}")

    def scan_all(self) -> List[Dict[str, Any]]:
        """
        Execute all scan modules and return consolidated findings.
        
        Each module runs in a try/except to ensure one failure doesn't
        kill the entire scan.
        
        Returns:
            List of finding dictionaries matching resources table schema
        """
        logger.info(f"Starting Azure waste scan for subscription: {self.subscription_id}")
        
        # Reset findings
        self.findings = []
        
        # Fetch real cost data from Azure Cost Management.
        # Rate limit: ~30 req/5 min. If resource costs 429, skip subscription
        # costs entirely to avoid burning the rate limit budget further.
        logger.info("Fetching cost data from Azure Cost Management...")
        self._cost_rate_limited = False
        self._real_costs = self._fetch_real_costs()
        if self._cost_rate_limited:
            logger.warning(
                "Azure Cost Management rate-limited — skipping subscription cost query. "
                "Wait 15-30 min before rescanning to let the rate limit reset."
            )
            self._subscription_costs = {}
        else:
            if self._real_costs:
                time.sleep(5)
            self._subscription_costs = self._fetch_subscription_cost_by_service()
        
        if self._real_costs:
            logger.info(
                f"Using REAL cost data for {len(self._real_costs)} "
                f"resources"
            )
        else:
            logger.info(
                "Real cost data unavailable — per-resource costs will be marked billing_unavailable"
            )
        
        # Define modules to run
        modules = [
            ("Virtual Machines", self.scan_virtual_machines),
            ("Managed Disks", self.scan_managed_disks),
            ("Public IPs", self.scan_public_ips),
            ("Network Security Groups", self.scan_network_security_groups),
            ("Storage Accounts", self.scan_storage_accounts),
            ("Load Balancers", self.scan_load_balancers),
            ("Network Interfaces", self.scan_network_interfaces),
            ("Snapshots", self.scan_snapshots), # ADDED
            ("Generic Resources & Governance", self.scan_generic_resources),  # MUST be last
        ]
        
        # Execute each module
        for name, module_fn in modules:
            try:
                logger.info(f"Scanning {name}...")
                module_fn()
                logger.info(f"Completed {name}")
            except Exception as e:
                logger.error(f"Module '{name}' failed: {e}", exc_info=True)
                # Continue to next module

        real_cost_backfills = self._apply_real_cost_overrides()
        if real_cost_backfills:
            logger.info(
                f"Applied {real_cost_backfills} Azure real-cost overrides from Cost Management data"
            )
        
        # Calculate summary with utilization focus
        waste_items = [
            f for f in self.findings
            if f["status"] in ["waste", "zombie", "non_compliant"]
        ]
        underutilized_items = [
            f for f in self.findings
            if f["status"] in ["underutilized", "oversized", "moderate"]
        ]
        total_savings = sum(f["cost"] for f in waste_items)
        total_carbon = sum(f.get("carbon_footprint_kg", 0) for f in self.findings)

        # Compute fleet utilization average (VMs only)
        vm_scores = [
            f["utilization_score"] for f in self.findings
            if f.get("utilization_score") is not None and "Virtual Machine" in f.get("service_type", "")
        ]
        fleet_utilization = round(sum(vm_scores) / len(vm_scores), 1) if vm_scores else None

        logger.info(
            f"Scan complete: {len(self.findings)} resources, "
            f"{len(waste_items)} waste, {len(underutilized_items)} underutilized, "
            f"fleet utilization {fleet_utilization}%, "
            f"${total_savings:.2f} potential savings"
        )

        # Attach subscription-level cost data for routes.py to use
        self._scan_summary = {
            "total_resources": len(self.findings),
            "waste_items": len(waste_items),
            "underutilized_items": len(underutilized_items),
            "fleet_utilization_pct": fleet_utilization,
            "potential_savings": total_savings,
            "total_carbon_kg": total_carbon,
            "subscription_costs": self._subscription_costs if hasattr(
                self, '_subscription_costs'
            ) else {},
            "has_real_costs": bool(
                hasattr(self, '_real_costs') and self._real_costs
            )
        }
        
        return self.findings


# Compatibility alias for existing imports
AzureScanner = AzureWasteScanner
