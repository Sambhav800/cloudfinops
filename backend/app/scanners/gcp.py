"""
GCP Resource Scanner for CloudFinOps.
Production-grade scanner that covers:
  - Compute Engine instances (inventory plus billing-export cost override)
  - Persistent Disks (unattached = zombie)
  - External Static IPs (unattached = zombie)
  - Compute Snapshots (billable storage)
  - Cloud SQL instances
  - GKE clusters / node-pools
  - Cloud Run services
  - Cloud Functions
  - Universal inventory via Cloud Asset Inventory API
"""

import logging
import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Set, Tuple

from google.cloud import compute_v1
from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..core.retry import call_with_backoff, is_gcp_retryable

logger = logging.getLogger(__name__)
COST_SOURCE_ACTUAL = "actual"
COST_SOURCE_BILLING_UNAVAILABLE = "billing_unavailable"

# ---------------------------------------------------------------------------
# Regions approved for compliance checks
# ---------------------------------------------------------------------------
APPROVED_REGIONS: Set[str] = {
    "us-central1", "us-east1", "us-east4", "us-west1", "us-west2",
    "europe-west1", "europe-west2", "europe-west4",
    "asia-east1", "asia-northeast1", "asia-south1",
    "australia-southeast1",
}

def _region_compliance(location: str) -> str:
    """Return 'compliant' if location is in the approved list, otherwise 'non_compliant'.

    GCP zones look like 'us-central1-a' (region = 'us-central1').
    Regions look like 'us-central1'.  'global' is treated as compliant.
    """
    if not location or location == "global":
        return "compliant"

    parts = location.split("-")

    # Strip zone suffix: the last segment of a zone is a single lowercase letter (a–z)
    if len(parts) >= 3 and len(parts[-1]) == 1 and parts[-1].isalpha():
        region = "-".join(parts[:-1])
    else:
        region = location

    return "compliant" if region in APPROVED_REGIONS else "non_compliant"



# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScannedResource:
    """Represents a scanned GCP cloud resource."""
    resource_name: str
    service_type: str
    cost: float
    status: str
    region: str
    region_compliance: str
    cloud_resource_id: Optional[str] = None
    created_by: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class ScanResult:
    """Result of a complete GCP scan."""
    resources: List[ScannedResource]
    total_spend: float
    potential_savings: float
    active_resources_count: int
    carbon_footprint_kg: float
    waste_distribution: List[Dict[str, Any]]
    daily_totals: Optional[List[Dict[str, Any]]] = None
    service_breakdown: Optional[Dict[str, float]] = None
    currency: str = "INR"


# ---------------------------------------------------------------------------
# Main scanner class
# ---------------------------------------------------------------------------

class GCPScanner:
    """Production-grade GCP resource scanner for CloudFinOps."""

    def __init__(
        self,
        project_id: str,
        service_account_email: str,
        private_key: str,
        billing_export_table: Optional[str] = None,
        billing_lookback_days: Optional[int] = None,
    ):
        self.project_id = project_id
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.billing_export_table = (billing_export_table or "").strip() or os.getenv("GCP_BILLING_EXPORT_TABLE", "").strip()

        if billing_lookback_days is None:
            raw_lookback_days = os.getenv("GCP_BILLING_LOOKBACK_DAYS", "30")
        else:
            raw_lookback_days = str(billing_lookback_days)

        try:
            self.billing_lookback_days = max(int(raw_lookback_days), 1)
        except (TypeError, ValueError):
            self.billing_lookback_days = 30

        service_info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": service_account_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        self.credentials = service_account.Credentials.from_service_account_info(
            service_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Cloud Asset Inventory client (universal resource discovery)
        try:
            self.asset_client = build("cloudasset", "v1", credentials=self.credentials)
        except Exception as e:
            logger.warning(f"Cloud Asset Inventory client init failed: {e}")
            self.asset_client = None

        # Cloud Resource Manager client (project metadata)
        try:
            self.crm_client = build("cloudresourcemanager", "v1", credentials=self.credentials)
        except Exception as e:
            logger.warning(f"CRM client init failed: {e}")
            self.crm_client = None
        self.billing_export_resource_status = "not_checked"
        self.billing_export_resource_message = ""

    def _gcp_call(self, operation_name: str, func):
        return call_with_backoff(operation_name, func, is_retryable=is_gcp_retryable)

    def _gcp_execute(self, operation_name: str, request):
        return self._gcp_call(operation_name, request.execute)

    def _fetch_real_costs_from_billing_export(self) -> Tuple[Dict[str, float], float, List[Dict[str, Any]], Dict[str, float], str]:
        """
        Fetch current month-to-date project costs from BigQuery billing export.
        Expected table schema: Detailed billing export containing
        `resource.global_name`, `resource.name`, `cost`, `usage_start_time`,
        and `project.id`.
        """
        if not self.billing_export_table:
            return {}, 0.0, [], {}, "INR"

        try:
            from google.cloud import bigquery
        except Exception as e:
            logger.warning(
                f"google-cloud-bigquery unavailable; exact GCP resource costs unavailable: {e}"
            )
            return {}, 0.0, [], {}, "INR"

        resource_query = f"""
            SELECT
                LOWER(resource.global_name) AS global_name,
                LOWER(COALESCE(resource.name, REGEXP_EXTRACT(resource.global_name, r'/([^/]+)$'))) AS resource_name,
                COALESCE(service.description, '') AS service_name,
                COALESCE(sku.description, '') AS sku_name,
                COALESCE(location.location, '') AS billing_location,
                ANY_VALUE(currency) AS currency,
                SUM(CAST(cost AS FLOAT64)) AS net_cost
            FROM `{self.billing_export_table}`
            WHERE project.id = @project_id
              AND DATE(usage_start_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            GROUP BY global_name, resource_name, service_name, sku_name, billing_location
        """
        daily_query = f"""
            SELECT
                DATE(usage_start_time) AS spend_date,
                COALESCE(service.description, 'Unknown') AS service_name,
                ANY_VALUE(currency) AS currency,
                SUM(CAST(cost AS FLOAT64)) AS net_cost
            FROM `{self.billing_export_table}`
            WHERE project.id = @project_id
              AND DATE(usage_start_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            GROUP BY spend_date, service_name
            ORDER BY spend_date
        """

        try:
            client = bigquery.Client(project=self.project_id, credentials=self.credentials)
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("project_id", "STRING", self.project_id),
                ]
            )
        except Exception as e:
            logger.warning(
                f"GCP billing export client setup failed ({self.billing_export_table}); exact GCP costs unavailable: {e}"
            )
            return {}, 0.0, [], {}, "INR"

        cost_map: Dict[str, float] = {}
        positive_resource_total = 0.0
        total_cost = 0.0
        billing_currency = "INR"
        try:
            rows = self._gcp_call(
                "GCP billing export query",
                lambda: list(client.query(resource_query, job_config=job_config).result()),
            )
        except Exception as e:
            self.billing_export_resource_status = "detailed_resource_export_unavailable"
            self.billing_export_resource_message = (
                "Exact GCP per-resource cost requires a detailed billing export table "
                "with resource fields. Service-level actual totals can still be imported "
                "from the configured billing export."
            )
            logger.warning(
                f"GCP billing export query failed ({self.billing_export_table}); exact GCP resource costs unavailable: {e}"
            )
            rows = []

        for row in rows:
            amount = round(float(getattr(row, "net_cost", 0.0) or 0.0), 6)
            if amount > 0:
                positive_resource_total += amount
            row_currency = str(getattr(row, "currency", "") or "").strip().upper()
            if row_currency:
                billing_currency = row_currency

            global_name = (getattr(row, "global_name", "") or "").strip().lower()
            resource_name = (getattr(row, "resource_name", "") or "").strip().lower()
            service_name = str(getattr(row, "service_name", "") or "")
            sku_name = str(getattr(row, "sku_name", "") or "")
            billing_location = str(getattr(row, "billing_location", "") or "")
            resource_kind = self._billing_resource_kind_from_values(
                global_name=global_name,
                service_name=service_name,
                sku_name=sku_name,
            )
            resource_location = self._extract_billing_location(global_name) or billing_location

            lookup_keys: List[str] = []
            if global_name:
                lookup_keys.append(global_name)
            lookup_keys.extend(
                self._billing_composite_lookup_keys(resource_kind, resource_name, resource_location)
            )
            if not lookup_keys and resource_name:
                lookup_keys.append(f"name:{resource_name}")
            for lookup_key in lookup_keys:
                cost_map[lookup_key] = round(cost_map.get(lookup_key, 0.0) + amount, 6)

        if cost_map:
            self.billing_export_resource_status = "resource_costs_available"
            self.billing_export_resource_message = ""
            logger.info(
                f"Fetched GCP real costs from billing export for {len(cost_map)} keys "
                f"(table: {self.billing_export_table})"
            )

        daily_totals: List[Dict[str, Any]] = []
        service_breakdown: Dict[str, float] = {}
        try:
            daily_rows = self._gcp_call(
                "GCP billing export daily history query",
                lambda: list(client.query(daily_query, job_config=job_config).result()),
            )
            daily_by_date: Dict[str, float] = {}
            for row in daily_rows:
                spend_date = str(getattr(row, "spend_date", "") or "").strip()
                if not spend_date:
                    continue
                amount = round(float(getattr(row, "net_cost", 0.0) or 0.0), 4)
                service_name = str(getattr(row, "service_name", "") or "Unknown")
                row_currency = str(getattr(row, "currency", "") or "").strip().upper()
                if row_currency:
                    billing_currency = row_currency
                daily_by_date[spend_date] = round(daily_by_date.get(spend_date, 0.0) + amount, 4)
                if amount:
                    service_breakdown[service_name] = round(
                        service_breakdown.get(service_name, 0.0) + amount,
                        4,
                    )
            daily_totals = [
                {"date": day, "amount": amount}
                for day, amount in sorted(daily_by_date.items())
            ]
            if daily_by_date:
                total_cost = sum(daily_by_date.values())
        except Exception as e:
            logger.warning(
                f"GCP billing export daily history query failed ({self.billing_export_table}); forecast history unavailable: {e}"
            )
            total_cost = positive_resource_total

        return cost_map, round(total_cost, 2), daily_totals, service_breakdown, billing_currency

    @staticmethod
    def _normalize_lookup_key(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @staticmethod
    def _extract_billing_location(global_name: Any) -> str:
        normalized = GCPScanner._normalize_lookup_key(global_name)
        if not normalized:
            return ""

        match = re.search(r"/(?:zones|regions|locations)/([^/]+)", normalized)
        return match.group(1) if match else ""

    @classmethod
    def _billing_resource_kind_from_values(
        cls,
        *,
        global_name: Any = "",
        service_name: Any = "",
        sku_name: Any = "",
        service_type: Any = "",
    ) -> str:
        global_key = cls._normalize_lookup_key(global_name)
        text = " ".join(
            cls._normalize_lookup_key(value)
            for value in (service_name, sku_name, service_type)
            if value is not None
        )

        if "/instances/" in global_key or "compute instance" in text or "ec2 instance" in text:
            return "compute_instance"
        if "/disks/" in global_key or "persistent disk" in text or "storage pd" in text:
            return "persistent_disk"
        if "/addresses/" in global_key or "external ip" in text or "static ip" in text:
            return "external_ip"
        if "/snapshots/" in global_key or "snapshot" in text:
            return "snapshot"
        if "cloud sql" in text or "sqladmin" in global_key:
            return "cloud_sql"
        if "/services/" in global_key and "run.googleapis.com" in global_key:
            return "cloud_run"
        if "/functions/" in global_key or "cloud function" in text:
            return "cloud_function"
        return ""

    @classmethod
    def _billing_composite_lookup_keys(
        cls,
        resource_kind: Any,
        resource_name: Any,
        location: Any,
    ) -> List[str]:
        kind_key = cls._normalize_lookup_key(resource_kind)
        name_key = cls._normalize_lookup_key(resource_name)
        location_key = cls._normalize_lookup_key(location)
        if not kind_key or not name_key:
            return []

        keys: List[str] = []
        if location_key:
            keys.append(f"gcp:{kind_key}:{location_key}:{name_key}")
        keys.append(f"gcp:{kind_key}:{name_key}")
        return keys

    def _resource_cost_lookup_keys(self, resource: ScannedResource) -> List[str]:
        metadata = resource.metadata or {}
        keys: List[str] = []
        for raw_value in (
            metadata.get("global_name"),
            metadata.get("billing_global_name"),
            metadata.get("resource_id"),
            metadata.get("url"),
            resource.cloud_resource_id,
        ):
            normalized = self._normalize_lookup_key(raw_value)
            if normalized:
                keys.append(normalized)

        resource_kind = self._billing_resource_kind_from_values(
            global_name=metadata.get("global_name"),
            service_type=resource.service_type,
        )
        resource_location = (
            metadata.get("zone")
            or metadata.get("region")
            or metadata.get("location")
            or resource.region
        )
        keys.extend(
            self._billing_composite_lookup_keys(
                resource_kind,
                resource.resource_name,
                resource_location,
            )
        )
        if resource_kind == "external_ip" and metadata.get("address"):
            keys.extend(
                self._billing_composite_lookup_keys(
                    resource_kind,
                    metadata.get("address"),
                    resource_location,
                )
            )

        for raw_value in (resource.resource_name, metadata.get("source_disk")):
            normalized = self._normalize_lookup_key(raw_value)
            if normalized:
                keys.append(f"name:{normalized}")

        deduped: List[str] = []
        seen = set()
        for key in keys:
            if key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    def _remember_resource_ids(self, existing_ids: Set[str], resource: ScannedResource) -> None:
        existing_ids.update(self._resource_cost_lookup_keys(resource))

    def _apply_real_costs(self, resources: List[ScannedResource], cost_map: Dict[str, float], currency: str = "INR") -> int:
        if not cost_map:
            return 0
        updates = 0
        for resource in resources:
            matched_key = None
            for key in self._resource_cost_lookup_keys(resource):
                if key in cost_map:
                    matched_key = key
                    break
            if not matched_key:
                continue
            real_cost = round(float(cost_map[matched_key]), 2)
            resource.metadata = resource.metadata or {}
            existing_source = self._normalize_lookup_key(resource.metadata.get("cost_source"))
            existing_lookup_key = self._normalize_lookup_key(resource.metadata.get("cost_lookup_key"))
            if (
                abs(resource.cost - real_cost) < 0.01
                and existing_source == COST_SOURCE_ACTUAL
                and existing_lookup_key == matched_key
            ):
                continue
            resource.cost = real_cost
            resource.metadata["cost_source"] = COST_SOURCE_ACTUAL
            resource.metadata["cost_lookup_key"] = matched_key
            resource.metadata["currency"] = currency
            updates += 1
        return updates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scan(self, progress_callback: Optional[callable] = None) -> ScanResult:
        """Perform a GCP scan using detailed service scanners plus Cloud Asset Inventory."""
        resources: List[ScannedResource] = []
        waste_list: List[Dict[str, Any]] = []
        potential_savings = 0.0
        active_resources_count = 0
        carbon_footprint = 0.0
        existing_ids: Set[str] = set()
        real_cost_map: Dict[str, float] = {}
        billed_total_spend = 0.0
        daily_totals: List[Dict[str, Any]] = []
        service_breakdown: Dict[str, float] = {}
        billing_currency = "INR"

        # Optional real-cost enrichment from billing export.
        if progress_callback:
            await progress_callback(5, "Fetching GCP billing-export cost data...")
        real_cost_map, billed_total_spend, daily_totals, service_breakdown, billing_currency = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._fetch_real_costs_from_billing_export
        )

        # --- Compute Instances ---
        if progress_callback:
            await progress_callback(10, "Scanning GCP Compute Engine instances...")
        vm_res, vm_waste, vm_savings, vm_active, vm_carbon = await self._scan_instances()
        for r in vm_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        waste_list.extend(vm_waste)
        potential_savings += vm_savings
        active_resources_count += vm_active
        carbon_footprint += vm_carbon

        # --- Persistent Disks ---
        if progress_callback:
            await progress_callback(22, "Scanning GCP Persistent Disks...")
        disk_res, disk_waste, disk_savings = await self._scan_disks(existing_ids)
        for r in disk_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        waste_list.extend(disk_waste)
        potential_savings += disk_savings

        # --- External Static IPs ---
        if progress_callback:
            await progress_callback(32, "Scanning GCP External Static IPs...")
        ip_res, ip_waste, ip_savings = await self._scan_static_ips(existing_ids)
        for r in ip_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        waste_list.extend(ip_waste)
        potential_savings += ip_savings

        # --- Snapshots ---
        if progress_callback:
            await progress_callback(40, "Scanning GCP Compute Snapshots...")
        snap_res = await self._scan_snapshots(existing_ids)
        for r in snap_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)

        # --- Cloud SQL ---
        if progress_callback:
            await progress_callback(50, "Scanning Cloud SQL instances...")
        sql_res, sql_waste, sql_savings = await self._scan_sql(existing_ids)
        for r in sql_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        waste_list.extend(sql_waste)
        potential_savings += sql_savings

        # --- GKE ---
        if progress_callback:
            await progress_callback(60, "Scanning GKE clusters...")
        gke_res = await self._scan_gke(existing_ids)
        for r in gke_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        active_resources_count += len(gke_res)

        # --- Cloud Run ---
        if progress_callback:
            await progress_callback(68, "Scanning Cloud Run services...")
        run_res, run_waste, run_savings = await self._scan_cloud_run(existing_ids)
        for r in run_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)
        waste_list.extend(run_waste)
        potential_savings += run_savings

        # --- Cloud Functions ---
        if progress_callback:
            await progress_callback(74, "Scanning Cloud Functions...")
        fn_res = await self._scan_cloud_functions(existing_ids)
        for r in fn_res:
            resources.append(r)
            self._remember_resource_ids(existing_ids, r)

        # --- Universal catch-all (Cloud Asset Inventory) ---
        if progress_callback:
            await progress_callback(82, "Running universal inventory (Cloud Asset API)...")
        generic_res = await self._scan_generic_resources(existing_ids)
        resources.extend(generic_res)
        active_resources_count += len(generic_res)

        if progress_callback:
            await progress_callback(95, "Finalizing GCP scan...")

        real_overrides = self._apply_real_costs(resources, real_cost_map, billing_currency)
        if real_overrides:
            logger.info(f"Applied {real_overrides} real-cost overrides to GCP resources")
        elif billed_total_spend > 0 and self.billing_export_resource_status == "detailed_resource_export_unavailable":
            for resource in resources:
                resource.metadata = resource.metadata or {}
                resource.metadata.setdefault("cost_source", COST_SOURCE_BILLING_UNAVAILABLE)
                resource.metadata["resource_cost_status"] = self.billing_export_resource_status
                resource.metadata["pricing_note"] = self.billing_export_resource_message

        total_spend = billed_total_spend if billed_total_spend > 0 else sum(r.cost for r in resources)
        potential_savings = round(
            sum(r.cost for r in resources if str(r.status).lower() == "zombie"),
            2
        )

        return ScanResult(
            resources=resources,
            total_spend=total_spend,
            potential_savings=potential_savings,
            active_resources_count=len(resources),
            carbon_footprint_kg=carbon_footprint,
            waste_distribution=waste_list,
            daily_totals=daily_totals,
            service_breakdown=service_breakdown,
            currency=billing_currency,
        )

    # ------------------------------------------------------------------
    # Compute Engine Instances
    # ------------------------------------------------------------------

    async def _scan_instances(self) -> Tuple[List[ScannedResource], List[Dict], float, int, float]:
        loop = asyncio.get_event_loop()

        def scan():
            resources, waste, savings = [], [], 0.0
            active_count, carbon = 0, 0.0

            try:
                client = compute_v1.InstancesClient(credentials=self.credentials)
                req = compute_v1.AggregatedListInstancesRequest(project=self.project_id)
                instances = self._gcp_call(
                    "GCP compute instances aggregated list",
                    lambda: list(client.aggregated_list(request=req)),
                )

                for zone_path, response in instances:
                    if not response.instances:
                        continue
                    zone_name = zone_path.split("/")[-1]

                    for instance in response.instances:
                        machine_type_url = instance.machine_type or ""
                        monthly_cost = 0.0
                        is_stopped = instance.status in ("TERMINATED", "STOPPED", "SUSPENDED")
                        status_str = "Zombie" if is_stopped else "Active"
                        resource_id = f"gcp-instance-{self.project_id}-{instance.name}-{zone_name}"

                        if is_stopped:
                            savings += monthly_cost
                            waste.append({"category_name": "Stopped Instances", "value": monthly_cost})
                        else:
                            active_count += 1
                            from ..core.carbon_model import estimate_monthly_carbon_kg
                            machine_type_short = machine_type_url.split("/")[-1] if machine_type_url else ""
                            region_from_zone = "-".join(zone_name.split("-")[:-1]) if zone_name else ""
                            carbon += estimate_monthly_carbon_kg("gcp", machine_type_short, region_from_zone)

                        # Extract network/subnet for architecture topology
                        instance_network = None
                        instance_subnet = None
                        try:
                            if instance.network_interfaces:
                                nic = instance.network_interfaces[0]
                                if nic.network:
                                    instance_network = nic.network.split("/")[-1] if "/" in nic.network else nic.network
                                if nic.subnetwork:
                                    instance_subnet = nic.subnetwork.split("/")[-1] if "/" in nic.subnetwork else nic.subnetwork
                        except Exception:
                            pass

                        # GPU detection (A2/G2/A3 machine types + guest accelerators)
                        from ..core.gpu_specs import (
                            GCP_GPU_MACHINE_PREFIXES, GCP_GPU_SPECS,
                            GCP_ACCELERATOR_SPECS, is_gpu_instance_type,
                        )
                        instance_metadata = {
                            "machine_type": machine_type_url.split("/")[-1] if "/" in machine_type_url else machine_type_url,
                            "status": instance.status,
                            "zone": zone_name,
                            "project_id": self.project_id,
                            "global_name": f"//compute.googleapis.com/projects/{self.project_id}/zones/{zone_name}/instances/{instance.name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                            "network": instance_network,
                            "subnet": instance_subnet,
                        }

                        mt_short = machine_type_url.split("/")[-1] if machine_type_url else ""
                        is_gpu_by_type = is_gpu_instance_type(mt_short, provider="gcp")
                        guest_accels = list(instance.guest_accelerators) if hasattr(instance, "guest_accelerators") and instance.guest_accelerators else []

                        if is_gpu_by_type or guest_accels:
                            instance_metadata["is_gpu_instance"] = True
                            instance_metadata["instance_type"] = mt_short
                            if is_gpu_by_type:
                                spec = GCP_GPU_SPECS.get(mt_short.lower())
                                if spec:
                                    instance_metadata["gpu_type"] = f"{spec.gpu_count}× {spec.gpu_model}"
                                    instance_metadata["gpu_count"] = spec.gpu_count
                                    instance_metadata["supports_mig"] = spec.supports_mig
                                    instance_metadata["gpu_memory_gb"] = spec.gpu_memory_gb
                                    instance_metadata["gpu_architecture"] = spec.architecture
                                    if spec.supports_mig:
                                        instance_metadata["gpu_optimization_insight"] = (
                                            f"MIG-capable {spec.gpu_model} on GCP. "
                                            f"Partition each GPU into up to {spec.mig_slices_per_gpu} slices."
                                        )
                                    else:
                                        instance_metadata["gpu_optimization_insight"] = (
                                            f"{spec.gpu_model} GPU detected. Compare cost vs. specialized clouds."
                                        )
                            elif guest_accels:
                                accel = guest_accels[0]
                                accel_type_full = accel.accelerator_type if hasattr(accel, "accelerator_type") else ""
                                accel_type = accel_type_full.split("/")[-1] if "/" in accel_type_full else accel_type_full
                                accel_count = accel.accelerator_count if hasattr(accel, "accelerator_count") else 1
                                accel_spec = GCP_ACCELERATOR_SPECS.get(accel_type, {})
                                gpu_model = accel_spec.get("gpu_model", accel_type)
                                instance_metadata["gpu_type"] = f"{accel_count}× {gpu_model}"
                                instance_metadata["gpu_count"] = accel_count
                                instance_metadata["supports_mig"] = accel_spec.get("supports_mig", False)
                                instance_metadata["gpu_memory_gb"] = accel_spec.get("gpu_memory_gb", 0) * accel_count
                                instance_metadata["gpu_architecture"] = accel_spec.get("architecture", "Unknown")
                                instance_metadata["gpu_optimization_insight"] = (
                                    f"Attached {accel_count}× {gpu_model} accelerator. "
                                    "Consider dedicated GPU machine types (A2/G2) for better price-performance."
                                )

                        resources.append(ScannedResource(
                            resource_name=instance.name,
                            service_type="GCP Compute Instance",
                            cost=monthly_cost,
                            status=status_str,
                            region=zone_name,
                            region_compliance=_region_compliance(zone_name),
                            cloud_resource_id=resource_id,
                            metadata=instance_metadata,
                        ))

            except Exception as e:
                logger.error(f"GCP instance scan error: {e}")

            return resources, waste, savings, active_count, carbon

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Persistent Disks
    # ------------------------------------------------------------------

    async def _scan_disks(self, existing_ids: Set[str]) -> Tuple[List[ScannedResource], List[Dict], float]:
        loop = asyncio.get_event_loop()

        def scan():
            resources, waste, savings = [], [], 0.0

            try:
                client = compute_v1.DisksClient(credentials=self.credentials)
                req = compute_v1.AggregatedListDisksRequest(project=self.project_id)
                disks = self._gcp_call(
                    "GCP persistent disks aggregated list",
                    lambda: list(client.aggregated_list(request=req)),
                )

                for zone_path, response in disks:
                    if not response.disks:
                        continue
                    zone_name = zone_path.split("/")[-1]

                    for disk in response.disks:
                        size_gb = int(disk.size_gb) if disk.size_gb else 0
                        disk_type_url = disk.type_ or "pd-standard"
                        disk_type = disk_type_url.split("/")[-1].lower() if "/" in disk_type_url else disk_type_url.lower()
                        monthly_cost = 0.0

                        is_unattached = not disk.users
                        status_str = "Zombie" if is_unattached else "Active"
                        resource_id = f"gcp-disk-{self.project_id}-{disk.name}-{zone_name}"

                        if self._normalize_lookup_key(resource_id) in existing_ids:
                            continue

                        if is_unattached:
                            if monthly_cost > 0:
                                savings += monthly_cost
                                waste.append({"category_name": "Unattached Disks", "value": monthly_cost})

                        resources.append(ScannedResource(
                            resource_name=disk.name,
                            service_type="GCP Persistent Disk",
                            cost=monthly_cost,
                            status=status_str,
                            region=zone_name,
                            region_compliance=_region_compliance(zone_name),
                            cloud_resource_id=resource_id,
                            metadata={
                                "size_gb": size_gb,
                                "type": disk_type,
                                "zone": zone_name,
                                "attached": not is_unattached,
                                "global_name": f"//compute.googleapis.com/projects/{self.project_id}/zones/{zone_name}/disks/{disk.name}",
                                "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                            }
                        ))

            except Exception as e:
                logger.error(f"GCP disk scan error: {e}")

            return resources, waste, savings

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # External Static IPs
    # ------------------------------------------------------------------

    async def _scan_static_ips(self, existing_ids: Set[str]) -> Tuple[List[ScannedResource], List[Dict], float]:
        loop = asyncio.get_event_loop()

        def scan():
            resources, waste, savings = [], [], 0.0

            try:
                client = compute_v1.AddressesClient(credentials=self.credentials)
                req = compute_v1.AggregatedListAddressesRequest(project=self.project_id)
                addresses = self._gcp_call(
                    "GCP external IPs aggregated list",
                    lambda: list(client.aggregated_list(request=req)),
                )

                for region_path, response in addresses:
                    if not response.addresses:
                        continue
                    region_name = region_path.split("/")[-1]
                    if region_name == "global":
                        region_name = "global"

                    for addr in response.addresses:
                        # RESERVED = unattached (still billing), IN_USE = attached
                        is_unattached = addr.status == "RESERVED" and not addr.users
                        monthly_cost = 0.0
                        status_str = "Zombie" if is_unattached else "Active"
                        resource_id = f"gcp-ip-{self.project_id}-{addr.name}-{region_name}"

                        if self._normalize_lookup_key(resource_id) in existing_ids:
                            continue

                        if is_unattached:
                            if monthly_cost > 0:
                                savings += monthly_cost
                                waste.append({"category_name": "Unattached IPs", "value": monthly_cost})

                        resources.append(ScannedResource(
                            resource_name=addr.name,
                            service_type="GCP External IP",
                            cost=monthly_cost,
                            status=status_str,
                            region=region_name,
                            region_compliance=_region_compliance(region_name),
                            cloud_resource_id=resource_id,
                            metadata={
                                "address": addr.address,
                                "address_type": addr.address_type,
                                "ip_status": addr.status,
                                "global_name": (
                                    f"//compute.googleapis.com/projects/{self.project_id}/global/addresses/{addr.name}"
                                    if region_name == "global"
                                    else f"//compute.googleapis.com/projects/{self.project_id}/regions/{region_name}/addresses/{addr.name}"
                                ),
                                "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                            }
                        ))

            except Exception as e:
                logger.error(f"GCP static IP scan error: {e}")

            return resources, waste, savings

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Compute Snapshots
    # ------------------------------------------------------------------

    async def _scan_snapshots(self, existing_ids: Set[str]) -> List[ScannedResource]:
        loop = asyncio.get_event_loop()

        def scan():
            resources = []

            try:
                client = compute_v1.SnapshotsClient(credentials=self.credentials)
                req = compute_v1.ListSnapshotsRequest(project=self.project_id)
                snapshots = self._gcp_call(
                    "GCP snapshots list",
                    lambda: list(client.list(request=req)),
                )

                for snapshot in snapshots:
                    size_gb = int(snapshot.storage_bytes or 0) / (1024 ** 3)
                    monthly_cost = 0.0
                    resource_id = f"gcp-snapshot-{self.project_id}-{snapshot.name}"

                    if self._normalize_lookup_key(resource_id) in existing_ids:
                        continue

                    resources.append(ScannedResource(
                        resource_name=snapshot.name,
                        service_type="GCP Compute Snapshot",
                        cost=monthly_cost,
                        status="Active",
                        region="global",
                        region_compliance="compliant",
                        cloud_resource_id=resource_id,
                        metadata={
                            "size_gb": round(size_gb, 2),
                            "source_disk": (snapshot.source_disk or "").split("/")[-1],
                            "creation_timestamp": snapshot.creation_timestamp,
                            "global_name": f"//compute.googleapis.com/projects/{self.project_id}/global/snapshots/{snapshot.name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                        }
                    ))

            except Exception as e:
                logger.error(f"GCP snapshot scan error: {e}")

            return resources

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Cloud SQL
    # ------------------------------------------------------------------

    async def _scan_sql(self, existing_ids: Set[str]) -> Tuple[List[ScannedResource], List[Dict], float]:
        loop = asyncio.get_event_loop()

        def scan():
            resources, waste, savings = [], [], 0.0

            try:
                sql_client = build("sqladmin", "v1beta4", credentials=self.credentials)
                result = self._gcp_execute(
                    "GCP Cloud SQL instances list",
                    sql_client.instances().list(project=self.project_id),
                )

                for instance in result.get("items", []):
                    name = instance.get("name", "unknown")
                    tier = instance.get("settings", {}).get("tier", "db-n1-standard-1")
                    region = instance.get("region", "unknown")
                    state = instance.get("state", "RUNNABLE")
                    monthly_cost = 0.0

                    is_stopped = state in ("SUSPENDED", "MAINTENANCE", "OFFLINE")
                    status_str = "Zombie" if is_stopped else "Active"
                    resource_id = f"gcp-sql-{self.project_id}-{name}-{region}"

                    if self._normalize_lookup_key(resource_id) in existing_ids:
                        continue

                    if is_stopped:
                        if monthly_cost > 0:
                            savings += monthly_cost
                            waste.append({"category_name": "Stopped SQL Instances", "value": monthly_cost})

                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type="GCP Cloud SQL",
                        cost=monthly_cost,
                        status=status_str,
                        region=region,
                        region_compliance=_region_compliance(region),
                        cloud_resource_id=resource_id,
                        metadata={
                            "tier": tier,
                            "database_version": instance.get("databaseVersion", ""),
                            "state": state,
                            "storage_gb": instance.get("settings", {}).get("dataDiskSizeGb", 0),
                            "global_name": f"//sqladmin.googleapis.com/projects/{self.project_id}/instances/{name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                        }
                    ))

            except Exception as e:
                logger.error(f"GCP Cloud SQL scan error: {e}")

            return resources, waste, savings

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # GKE Clusters
    # ------------------------------------------------------------------

    async def _scan_gke(self, existing_ids: Set[str]) -> List[ScannedResource]:
        loop = asyncio.get_event_loop()

        def scan():
            resources = []

            try:
                container_client = build("container", "v1", credentials=self.credentials)
                clusters = self._gcp_execute(
                    "GCP GKE clusters list",
                    container_client.projects().locations().clusters().list(
                        parent=f"projects/{self.project_id}/locations/-"
                    ),
                )

                for cluster in clusters.get("clusters", []):
                    name = cluster.get("name", "unknown")
                    location = cluster.get("location", "unknown")
                    status = cluster.get("status", "RUNNING")
                    node_count = sum(
                        int(pool.get("currentNodeCount", 0))
                        for pool in cluster.get("nodePools", [])
                    )
                    monthly_cost = 0.0
                    resource_id = f"gcp-gke-{self.project_id}-{name}-{location}"

                    if self._normalize_lookup_key(resource_id) in existing_ids:
                        continue

                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type="GCP GKE Cluster",
                        cost=monthly_cost,
                        status="Active" if status == "RUNNING" else "Zombie",
                        region=location,
                        region_compliance=_region_compliance(location),
                        cloud_resource_id=resource_id,
                        metadata={
                            "node_count": node_count,
                            "cluster_status": status,
                            "kubernetes_version": cluster.get("currentMasterVersion", ""),
                            "network": cluster.get("network", ""),
                            "global_name": f"//container.googleapis.com/projects/{self.project_id}/locations/{location}/clusters/{name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                        }
                    ))

            except Exception as e:
                logger.error(f"GCP GKE scan error: {e}")

            return resources

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Cloud Run Services
    # ------------------------------------------------------------------

    async def _scan_cloud_run(self, existing_ids: Set[str]) -> Tuple[List[ScannedResource], List[Dict], float]:
        loop = asyncio.get_event_loop()

        def scan():
            resources, waste, savings = [], [], 0.0

            try:
                run_client = build("run", "v1", credentials=self.credentials)
                # List namespaces (projects map to namespaces in Cloud Run v1)
                result = self._gcp_execute(
                    "GCP Cloud Run services list",
                    run_client.projects().locations().services().list(
                        parent=f"projects/{self.project_id}/locations/-"
                    ),
                )

                for svc in result.get("items", []):
                    name = svc.get("metadata", {}).get("name", "unknown")
                    region = svc.get("metadata", {}).get("namespace", self.project_id)
                    labels = svc.get("metadata", {}).get("labels", {})
                    # Determine if service has recent traffic
                    traffic = svc.get("status", {}).get("traffic", [])
                    has_traffic = len(traffic) > 0
                    monthly_cost = 0.0
                    status_str = "Zombie" if not has_traffic else "Active"

                    if not has_traffic:
                        if monthly_cost > 0:
                            savings += monthly_cost
                            waste.append({"category_name": "Idle Cloud Run Services", "value": monthly_cost})

                    # /apis/serving.knative.dev/v1/namespaces/{project}/services/{name}
                    resource_id = f"gcp-cloudrun-{self.project_id}-{name}"
                    parsed_region = labels.get("cloud.googleapis.com/location", region)

                    if self._normalize_lookup_key(resource_id) in existing_ids:
                        continue

                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type="GCP Cloud Run",
                        cost=monthly_cost,
                        status=status_str,
                        region=parsed_region,
                        region_compliance=_region_compliance(parsed_region),
                        cloud_resource_id=resource_id,
                        metadata={
                            "has_traffic": has_traffic,
                            "url": svc.get("status", {}).get("url", ""),
                            "global_name": f"//run.googleapis.com/projects/{self.project_id}/locations/{parsed_region}/services/{name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                        }
                    ))

            except Exception as e:
                logger.error(f"GCP Cloud Run scan error: {e}")

            return resources, waste, savings

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Cloud Functions
    # ------------------------------------------------------------------

    async def _scan_cloud_functions(self, existing_ids: Set[str]) -> List[ScannedResource]:
        loop = asyncio.get_event_loop()

        def scan():
            resources = []

            try:
                fn_client = build("cloudfunctions", "v2", credentials=self.credentials)
                result = self._gcp_execute(
                    "GCP Cloud Functions list",
                    fn_client.projects().locations().functions().list(
                        parent=f"projects/{self.project_id}/locations/-"
                    ),
                )

                for fn in result.get("functions", []):
                    name_full = fn.get("name", "")
                    name = name_full.split("/")[-1]
                    location = name_full.split("/")[3] if len(name_full.split("/")) > 3 else "unknown"
                    state = fn.get("state", "ACTIVE")
                    monthly_cost = 0.0
                    resource_id = f"gcp-function-{self.project_id}-{name}-{location}"

                    if self._normalize_lookup_key(resource_id) in existing_ids:
                        continue

                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type="GCP Cloud Function",
                        cost=monthly_cost,
                        status="Active" if state == "ACTIVE" else "Zombie",
                        region=location,
                        region_compliance=_region_compliance(location),
                        cloud_resource_id=resource_id,
                        metadata={
                            "runtime": fn.get("buildConfig", {}).get("runtime", ""),
                            "state": state,
                            "environment": fn.get("environment", "GEN_2"),
                            "global_name": f"//cloudfunctions.googleapis.com/projects/{self.project_id}/locations/{location}/functions/{name}",
                            "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                        }
                    ))

            except Exception as e:
                logger.error(f"GCP Cloud Functions scan error: {e}")

            return resources

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # Universal catch-all – Cloud Asset Inventory
    # ------------------------------------------------------------------

    async def _scan_generic_resources(self, existing_ids: Set[str]) -> List[ScannedResource]:
        loop = asyncio.get_event_loop()

        def scan():
            new_resources = []
            if not self.asset_client:
                return []

            try:
                parent = f"projects/{self.project_id}"
                asset_api = self.asset_client.v1() if hasattr(self.asset_client, "v1") else self.asset_client
                request = asset_api.searchAllResources(
                    scope=parent,
                    pageSize=200
                )

                while request is not None:
                    response = self._gcp_execute("GCP Cloud Asset search resources", request)

                    for asset in response.get("results", []):
                        asset_type = asset.get("assetType", "Unknown")
                        name = asset.get("displayName") or asset.get("name", "Unknown")
                        location = asset.get("location", "global")

                        # Skip types we already scan in detail
                        if any(t in asset_type for t in (
                            "compute.googleapis.com/Instance",
                            "compute.googleapis.com/Disk",
                            "compute.googleapis.com/Address",
                            "compute.googleapis.com/Snapshot",
                            "sqladmin.googleapis.com",
                            "container.googleapis.com",
                            "run.googleapis.com",
                            "cloudfunctions.googleapis.com",
                        )):
                            continue

                        resource_id = asset.get("name") or f"gcp-generic-{self.project_id}-{name}-{location}"
                        if (
                            self._normalize_lookup_key(resource_id) in existing_ids
                            or self._normalize_lookup_key(name) in existing_ids
                        ):
                            continue

                        service = asset_type.split("/")[-1] if "/" in asset_type else asset_type

                        resource = ScannedResource(
                            resource_name=name,
                            service_type=f"GCP {service}",
                            cost=0.0,
                            status="Active",
                            region=location,
                            region_compliance=_region_compliance(location),
                            cloud_resource_id=resource_id,
                            metadata={
                                "assetType": asset_type,
                                "displayName": asset.get("displayName"),
                                "location": location,
                                "labels": asset.get("labels", {}),
                                "createTime": asset.get("createTime"),
                                "state": asset.get("state"),
                                "global_name": asset.get("name"),
                                "cost_source": COST_SOURCE_BILLING_UNAVAILABLE,
                            }
                        )
                        new_resources.append(resource)
                        self._remember_resource_ids(existing_ids, resource)

                    request = asset_api.searchAllResources_next(
                        previous_request=request,
                        previous_response=response
                    )

            except Exception as e:
                logger.warning(f"GCP Asset Inventory scan failed: {e}")

            return new_resources

        return await loop.run_in_executor(self.executor, scan)

    # ------------------------------------------------------------------
    # DB conversion
    # ------------------------------------------------------------------

    def to_db_resources(self, resources: List[ScannedResource], user_id: str, integration_id: str) -> List[Dict]:
        """Convert scanned resources to database format for bulk upsert."""
        return [
            {
                "resource_name": r.resource_name,
                "service_type": r.service_type,
                "cost": r.cost,
                "status": r.status,
                "region": r.region,
                "region_compliance": r.region_compliance,          # ← fixed: was storing r.region
                "provider": "gcp",
                "cloud_resource_id": r.cloud_resource_id or f"gcp-{r.resource_name}-{r.region}",  # ← non-empty
                "user_id": user_id,
                "integration_id": integration_id,
                "created_by": r.created_by,
                "metadata": r.metadata or {},
            }
            for r in resources
        ]
