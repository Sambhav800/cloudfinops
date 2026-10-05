"""
Billing Export Parser — extracts hourly instance-level usage from cloud billing data.

Parses:
- AWS CUR 2.0 (Cost and Usage Report) — CSV/Parquet from S3
- Azure Cost Exports / Cost Details — CSV from Blob Storage
- GCP Detailed Billing Export — BigQuery rows as CSV

Produces HourlyUsageRecord objects that feed the commitment optimizer
for accurate RI/SP/CUD sizing based on real hourly consumption, not daily averages.
"""

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HourlyUsageRecord:
    """Single hour of instance-level usage from billing data."""
    timestamp: datetime
    provider: str
    region: str
    instance_type: str
    instance_family: str
    usage_hours: float
    on_demand_cost: float
    resource_id: str = ""
    account_id: str = ""
    operating_system: str = "Linux"
    tenancy: str = "Shared"
    pricing_type: str = "OnDemand"  # OnDemand, Reserved, SavingsPlan, Spot
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedBillingExport:
    """Complete parsed billing export with aggregated metrics."""
    provider: str
    records: List[HourlyUsageRecord]
    hourly_by_family: Dict[str, List[float]]  # family → list of hourly costs
    total_on_demand_cost: float
    total_committed_cost: float
    total_spot_cost: float
    coverage_pct: float  # % of usage covered by existing commitments
    observation_hours: int
    observation_days: int
    instance_families: List[str]
    regions: List[str]
    parse_errors: int = 0


# ---------------------------------------------------------------------------
# AWS CUR 2.0 Parser
# ---------------------------------------------------------------------------

# Key CUR columns we need
_AWS_CUR_COLUMNS = {
    "line_item_usage_start_date": ["lineItem/UsageStartDate", "line_item_usage_start_date", "usage_start_date"],
    "line_item_usage_type": ["lineItem/UsageType", "line_item_usage_type", "usage_type"],
    "line_item_usage_amount": ["lineItem/UsageAmount", "line_item_usage_amount", "usage_amount"],
    "line_item_unblended_cost": ["lineItem/UnblendedCost", "line_item_unblended_cost", "unblended_cost"],
    "line_item_line_item_type": ["lineItem/LineItemType", "line_item_line_item_type", "line_item_type"],
    "line_item_resource_id": ["lineItem/ResourceId", "line_item_resource_id", "resource_id"],
    "product_instance_type": ["product/instanceType", "product_instance_type", "instance_type"],
    "product_region": ["product/region", "product_region", "region"],
    "product_operating_system": ["product/operatingSystem", "product_operating_system", "operating_system"],
    "product_tenancy": ["product/tenancy", "product_tenancy", "tenancy"],
    "pricing_term": ["pricing/term", "pricing_term"],
    "savings_plan_savings_plan_a_r_n": ["savingsPlan/SavingsPlanARN", "savings_plan_savings_plan_a_r_n"],
    "reservation_reservation_a_r_n": ["reservation/ReservationARN", "reservation_reservation_a_r_n"],
    "line_item_usage_account_id": ["lineItem/UsageAccountId", "line_item_usage_account_id", "usage_account_id"],
}


def _find_column(header_row: List[str], candidates: List[str]) -> Optional[int]:
    """Find column index by trying multiple name variants (CUR v1 vs v2 naming)."""
    header_lower = [h.strip().lower().replace("/", "_").replace(" ", "_") for h in header_row]
    for candidate in candidates:
        normalized = candidate.strip().lower().replace("/", "_").replace(" ", "_")
        if normalized in header_lower:
            return header_lower.index(normalized)
    return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    """Parse various timestamp formats from billing exports."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%d %H:%M:%S+00:00",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_family(instance_type: str) -> str:
    """Extract instance family from type. 'm5.xlarge' → 'm5', 'Standard_D4s_v5' → 'D'."""
    if not instance_type:
        return "unknown"
    if "." in instance_type:
        return instance_type.split(".")[0]
    if instance_type.startswith("Standard_"):
        import re
        match = re.match(r"Standard_([A-Z]+)\d+", instance_type)
        return match.group(1) if match else "unknown"
    if "-" in instance_type:
        parts = instance_type.rsplit("-", 1)
        return parts[0]
    return "unknown"


def parse_aws_cur(data: bytes, max_rows: int = 500_000) -> ParsedBillingExport:
    """
    Parse AWS Cost and Usage Report (CUR) CSV data.

    Extracts hourly instance-level usage for EC2, RDS, ElastiCache, etc.
    Classifies each line item as OnDemand, Reserved, SavingsPlan, or Spot.
    """
    records: List[HourlyUsageRecord] = []
    errors = 0
    total_on_demand = 0.0
    total_committed = 0.0
    total_spot = 0.0

    try:
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return _empty_export("aws")

        col = {}
        for key, candidates in _AWS_CUR_COLUMNS.items():
            idx = _find_column(header, candidates)
            col[key] = idx

        ts_col = col.get("line_item_usage_start_date")
        cost_col = col.get("line_item_unblended_cost")
        type_col = col.get("product_instance_type")
        region_col = col.get("product_region")

        if ts_col is None or cost_col is None:
            logger.warning("AWS CUR missing required columns (UsageStartDate, UnblendedCost)")
            return _empty_export("aws")

        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > max_rows:
                break

            try:
                cost = float(row[cost_col]) if cost_col is not None and cost_col < len(row) else 0.0
                if cost <= 0:
                    continue

                ts_str = row[ts_col] if ts_col < len(row) else ""
                timestamp = _parse_timestamp(ts_str)
                if not timestamp:
                    errors += 1
                    continue

                instance_type = row[type_col].strip() if type_col is not None and type_col < len(row) else ""
                if not instance_type:
                    continue

                region = row[region_col].strip() if region_col is not None and region_col < len(row) else ""
                resource_id = _safe_col(row, col.get("line_item_resource_id"), "")
                account_id = _safe_col(row, col.get("line_item_usage_account_id"), "")
                os_type = _safe_col(row, col.get("product_operating_system"), "Linux")
                tenancy = _safe_col(row, col.get("product_tenancy"), "Shared")
                usage_amount = float(_safe_col(row, col.get("line_item_usage_amount"), "0") or 0)

                # Classify pricing type
                sp_arn = _safe_col(row, col.get("savings_plan_savings_plan_a_r_n"), "")
                ri_arn = _safe_col(row, col.get("reservation_reservation_a_r_n"), "")
                line_type = _safe_col(row, col.get("line_item_line_item_type"), "").lower()
                usage_type = _safe_col(row, col.get("line_item_usage_type"), "").lower()

                if sp_arn:
                    pricing_type = "SavingsPlan"
                    total_committed += cost
                elif ri_arn or "reserved" in line_type:
                    pricing_type = "Reserved"
                    total_committed += cost
                elif "spot" in usage_type or "spotusage" in usage_type:
                    pricing_type = "Spot"
                    total_spot += cost
                else:
                    pricing_type = "OnDemand"
                    total_on_demand += cost

                records.append(HourlyUsageRecord(
                    timestamp=timestamp,
                    provider="aws",
                    region=region,
                    instance_type=instance_type,
                    instance_family=_extract_family(instance_type),
                    usage_hours=max(usage_amount, 0),
                    on_demand_cost=cost if pricing_type == "OnDemand" else 0.0,
                    resource_id=resource_id,
                    account_id=account_id,
                    operating_system=os_type,
                    tenancy=tenancy,
                    pricing_type=pricing_type,
                ))

            except (ValueError, IndexError) as e:
                errors += 1
                if errors <= 5:
                    logger.debug("AWS CUR parse error at row %d: %s", row_count, e)

    except Exception as e:
        logger.error("AWS CUR parsing failed: %s", e)
        return _empty_export("aws", errors)

    return _build_export("aws", records, total_on_demand, total_committed, total_spot, errors)


# ---------------------------------------------------------------------------
# Azure Cost Export Parser
# ---------------------------------------------------------------------------

_AZURE_COLUMNS = {
    "date": ["Date", "UsageDateTime", "date", "BillingPeriodStartDate"],
    "meter_category": ["MeterCategory", "meter_category", "ServiceName", "ConsumedService"],
    "instance_id": ["InstanceId", "ResourceId", "instance_id", "resource_id"],
    "meter_subcategory": ["MeterSubCategory", "meter_sub_category", "MeterSubcategory"],
    "cost": ["CostInBillingCurrency", "Cost", "PreTaxCost", "cost", "CostInUsd"],
    "quantity": ["Quantity", "UsageQuantity", "quantity"],
    "resource_location": ["ResourceLocation", "resource_location", "Location"],
    "resource_group": ["ResourceGroup", "ResourceGroupName", "resource_group"],
    "pricing_model": ["PricingModel", "pricing_model", "ChargeType"],
    "reservation_id": ["ReservationId", "reservation_id"],
    "reservation_name": ["ReservationName", "reservation_name"],
}


def parse_azure_cost_export(data: bytes, max_rows: int = 500_000) -> ParsedBillingExport:
    """
    Parse Azure Cost Management export CSV.

    Extracts daily/hourly usage for VMs, SQL, App Service, etc.
    Classifies as OnDemand vs Reserved based on PricingModel/ReservationId.
    """
    records: List[HourlyUsageRecord] = []
    errors = 0
    total_on_demand = 0.0
    total_committed = 0.0
    total_spot = 0.0

    try:
        text = data.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return _empty_export("azure")

        col = {}
        for key, candidates in _AZURE_COLUMNS.items():
            idx = _find_column(header, candidates)
            col[key] = idx

        date_col = col.get("date")
        cost_col = col.get("cost")
        if date_col is None or cost_col is None:
            logger.warning("Azure export missing required columns (Date, Cost)")
            return _empty_export("azure")

        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > max_rows:
                break

            try:
                cost = float(_safe_col(row, cost_col, "0") or 0)
                if cost <= 0:
                    continue

                ts_str = _safe_col(row, date_col, "")
                timestamp = _parse_timestamp(ts_str)
                if not timestamp:
                    errors += 1
                    continue

                meter_cat = _safe_col(row, col.get("meter_category"), "")
                if not _is_compute_category_azure(meter_cat):
                    continue

                instance_id = _safe_col(row, col.get("instance_id"), "")
                vm_size = _extract_azure_vm_size(instance_id, _safe_col(row, col.get("meter_subcategory"), ""))
                region = _safe_col(row, col.get("resource_location"), "")
                quantity = float(_safe_col(row, col.get("quantity"), "0") or 0)

                pricing_model = _safe_col(row, col.get("pricing_model"), "").lower()
                reservation_id = _safe_col(row, col.get("reservation_id"), "")

                if reservation_id or "reservation" in pricing_model:
                    pricing_type = "Reserved"
                    total_committed += cost
                elif "spot" in pricing_model:
                    pricing_type = "Spot"
                    total_spot += cost
                else:
                    pricing_type = "OnDemand"
                    total_on_demand += cost

                records.append(HourlyUsageRecord(
                    timestamp=timestamp,
                    provider="azure",
                    region=region,
                    instance_type=vm_size,
                    instance_family=_extract_family(vm_size),
                    usage_hours=max(quantity, 0),
                    on_demand_cost=cost if pricing_type == "OnDemand" else 0.0,
                    resource_id=instance_id,
                    pricing_type=pricing_type,
                ))

            except (ValueError, IndexError) as e:
                errors += 1
                if errors <= 5:
                    logger.debug("Azure export parse error at row %d: %s", row_count, e)

    except Exception as e:
        logger.error("Azure billing export parsing failed: %s", e)
        return _empty_export("azure", errors)

    return _build_export("azure", records, total_on_demand, total_committed, total_spot, errors)


# ---------------------------------------------------------------------------
# GCP Billing Export Parser
# ---------------------------------------------------------------------------

_GCP_COLUMNS = {
    "usage_start_time": ["usage_start_time", "usage.start_time", "start_time"],
    "service_description": ["service.description", "service_description"],
    "sku_description": ["sku.description", "sku_description"],
    "cost": ["cost", "total_cost", "cost_at_list"],
    "usage_amount": ["usage.amount", "usage_amount"],
    "resource_name": ["resource.name", "resource_name"],
    "location_region": ["location.region", "location_region", "region"],
    "credits_amount": ["credits.amount", "credits_amount"],
    "labels": ["labels", "project.labels"],
}


def parse_gcp_billing_export(data: bytes, max_rows: int = 500_000) -> ParsedBillingExport:
    """
    Parse GCP Detailed Billing Export (BigQuery export as CSV).

    Extracts hourly Compute Engine usage. Classifies as OnDemand vs CUD
    based on SKU description and credit entries.
    """
    records: List[HourlyUsageRecord] = []
    errors = 0
    total_on_demand = 0.0
    total_committed = 0.0
    total_spot = 0.0

    try:
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return _empty_export("gcp")

        col = {}
        for key, candidates in _GCP_COLUMNS.items():
            idx = _find_column(header, candidates)
            col[key] = idx

        ts_col = col.get("usage_start_time")
        cost_col = col.get("cost")
        if ts_col is None or cost_col is None:
            logger.warning("GCP export missing required columns (usage_start_time, cost)")
            return _empty_export("gcp")

        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > max_rows:
                break

            try:
                cost = float(_safe_col(row, cost_col, "0") or 0)
                if cost <= 0:
                    continue

                ts_str = _safe_col(row, ts_col, "")
                timestamp = _parse_timestamp(ts_str)
                if not timestamp:
                    errors += 1
                    continue

                service = _safe_col(row, col.get("service_description"), "")
                if "compute engine" not in service.lower():
                    continue

                sku = _safe_col(row, col.get("sku_description"), "")
                region = _safe_col(row, col.get("location_region"), "")
                resource_name = _safe_col(row, col.get("resource_name"), "")
                usage_amount = float(_safe_col(row, col.get("usage_amount"), "0") or 0)

                machine_type = _extract_gcp_machine_type(sku, resource_name)

                if "commitment" in sku.lower() or "cud" in sku.lower():
                    pricing_type = "Reserved"
                    total_committed += cost
                elif "preemptible" in sku.lower() or "spot" in sku.lower():
                    pricing_type = "Spot"
                    total_spot += cost
                else:
                    pricing_type = "OnDemand"
                    total_on_demand += cost

                records.append(HourlyUsageRecord(
                    timestamp=timestamp,
                    provider="gcp",
                    region=region,
                    instance_type=machine_type,
                    instance_family=_extract_family(machine_type),
                    usage_hours=max(usage_amount, 0),
                    on_demand_cost=cost if pricing_type == "OnDemand" else 0.0,
                    resource_id=resource_name,
                    pricing_type=pricing_type,
                ))

            except (ValueError, IndexError) as e:
                errors += 1
                if errors <= 5:
                    logger.debug("GCP export parse error at row %d: %s", row_count, e)

    except Exception as e:
        logger.error("GCP billing export parsing failed: %s", e)
        return _empty_export("gcp", errors)

    return _build_export("gcp", records, total_on_demand, total_committed, total_spot, errors)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _safe_col(row: List[str], idx: Optional[int], default: str = "") -> str:
    if idx is None or idx >= len(row):
        return default
    return row[idx].strip()


def _is_compute_category_azure(meter_cat: str) -> bool:
    lower = meter_cat.lower()
    return any(kw in lower for kw in (
        "virtual machines", "sql database", "app service",
        "container instances", "azure kubernetes", "redis cache",
        "cosmos db", "functions",
    ))


def _extract_azure_vm_size(instance_id: str, meter_subcategory: str) -> str:
    """Best-effort VM size extraction from Azure billing fields."""
    import re
    # MeterSubCategory often contains "D4s v5" style
    match = re.search(r"([A-Z]\d+[a-z]*\s*v\d+)", meter_subcategory, re.IGNORECASE)
    if match:
        return "Standard_" + match.group(1).replace(" ", "_")
    # instance_id sometimes ends with /virtualMachines/vmName
    if "/virtualmachines/" in instance_id.lower():
        return instance_id.rsplit("/", 1)[-1]
    return meter_subcategory or "unknown"


def _extract_gcp_machine_type(sku: str, resource_name: str) -> str:
    """Best-effort machine type extraction from GCP billing SKU description."""
    import re
    # SKU like "N2 Instance Core running in Americas" → "n2"
    match = re.match(r"([A-Za-z]\d[\w-]*)\s+Instance", sku)
    if match:
        return match.group(1).lower() + "-standard-1"
    # Resource name sometimes includes machine type
    for prefix in ("e2-", "n1-", "n2-", "c2-", "c3-", "t2d-", "t2a-"):
        if prefix in resource_name.lower():
            idx = resource_name.lower().index(prefix)
            rest = resource_name[idx:].split("/")[0].split(" ")[0]
            return rest
    return "unknown"


def _empty_export(provider: str, errors: int = 0) -> ParsedBillingExport:
    return ParsedBillingExport(
        provider=provider,
        records=[],
        hourly_by_family={},
        total_on_demand_cost=0,
        total_committed_cost=0,
        total_spot_cost=0,
        coverage_pct=0,
        observation_hours=0,
        observation_days=0,
        instance_families=[],
        regions=[],
        parse_errors=errors,
    )


def _build_export(
    provider: str,
    records: List[HourlyUsageRecord],
    total_on_demand: float,
    total_committed: float,
    total_spot: float,
    errors: int,
) -> ParsedBillingExport:
    """Aggregate records into hourly family-level cost timeseries."""
    if not records:
        return _empty_export(provider, errors)

    # Group by family → hour → total cost
    hourly_by_family: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    regions = set()
    families = set()
    timestamps = set()

    for r in records:
        hour_key = r.timestamp.strftime("%Y-%m-%dT%H:00:00Z")
        hourly_by_family[r.instance_family][hour_key] += r.on_demand_cost
        regions.add(r.region)
        families.add(r.instance_family)
        timestamps.add(hour_key)

    # Convert to sorted hourly cost lists per family
    sorted_hours = sorted(timestamps)
    family_hourly_costs: Dict[str, List[float]] = {}
    for family, hour_map in hourly_by_family.items():
        family_hourly_costs[family] = [hour_map.get(h, 0.0) for h in sorted_hours]

    total_all = total_on_demand + total_committed + total_spot
    coverage = round((total_committed / total_all * 100) if total_all > 0 else 0, 1)
    obs_hours = len(sorted_hours)
    obs_days = max(1, obs_hours // 24)

    logger.info(
        "%s billing export parsed: %d records, %d hours, %d families, "
        "on-demand=$%.2f, committed=$%.2f, spot=$%.2f, coverage=%.1f%%",
        provider.upper(), len(records), obs_hours, len(families),
        total_on_demand, total_committed, total_spot, coverage,
    )

    return ParsedBillingExport(
        provider=provider,
        records=records,
        hourly_by_family=family_hourly_costs,
        total_on_demand_cost=round(total_on_demand, 2),
        total_committed_cost=round(total_committed, 2),
        total_spot_cost=round(total_spot, 2),
        coverage_pct=coverage,
        observation_hours=obs_hours,
        observation_days=obs_days,
        instance_families=sorted(families),
        regions=sorted(regions - {""}),
        parse_errors=errors,
    )


def billing_export_to_commitment_baselines(
    export: ParsedBillingExport,
) -> List[Dict[str, Any]]:
    """
    Convert parsed billing export into daily spend format compatible
    with commitment_optimizer.analyze_usage_baselines().

    This bridges the gap between raw billing exports and the commitment
    optimizer, providing hourly-granularity data instead of daily averages.
    """
    if not export.hourly_by_family:
        return []

    # Aggregate all families into total daily spend
    all_hours = set()
    for costs in export.hourly_by_family.values():
        all_hours.update(range(len(costs)))

    if not all_hours:
        return []

    # Sum across families per hour, then aggregate to daily
    total_hourly = [0.0] * max(all_hours) + [0.0]
    for costs in export.hourly_by_family.values():
        for i, c in enumerate(costs):
            if i < len(total_hourly):
                total_hourly[i] += c

    # Convert hourly to daily
    daily_totals = []
    for day_start in range(0, len(total_hourly), 24):
        day_slice = total_hourly[day_start:day_start + 24]
        if day_slice:
            daily_totals.append({
                "date": f"day-{day_start // 24}",
                "amount": round(sum(day_slice), 4),
            })

    return daily_totals
