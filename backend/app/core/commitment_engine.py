import asyncio
import hashlib
import json
import logging
import math
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from functools import partial
from typing import Any, Literal, TypeVar

import boto3
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from ..db.mongo_client import MongoDBClient, get_db_client
from ..core.retry import build_aws_retry_config, call_with_backoff, is_aws_retryable, is_gcp_retryable
from ..security.crypto import decrypt_integration_credentials

logger = logging.getLogger(__name__)

# Monthly-equivalent convention: 365 days * 24 hours / 12 months, not a calendar bill.
MONTHLY_EQUIVALENT_HOURS = 730
SNAPSHOT_COLLECTION = "commitment_snapshots"
MAX_INVENTORY_AGE = timedelta(hours=48)
T = TypeVar("T")
InventoryStatus = Literal["ready", "no_commitments", "not_synced", "error", "unsupported", "demo"]


class CommitmentProviderError(RuntimeError):
    """A provider inventory could not be retrieved or validated completely."""


class CloudCommitment(BaseModel):
    model_config = ConfigDict(validate_assignment=True, allow_inf_nan=False)

    id: str
    provider: str
    type: str
    name: str
    status: str
    start_date: str
    end_date: str
    commitment_amount: float | None = Field(default=None, ge=0)
    amount_period: Literal["monthly"] = "monthly"
    hourly_commitment: float | None = Field(default=None, ge=0)
    currency: str | None = None
    region: str | None = None
    utilization_pct: float | None = Field(default=None, ge=0, le=100)
    utilization_used_commitment: float | None = Field(default=None, ge=0)
    utilization_total_commitment: float | None = Field(default=None, ge=0)
    savings_amount: float | None = None
    savings_period_start: str | None = None
    savings_period_end: str | None = None
    coverage_type: str
    source: Literal["provider_api", "demo"] = "provider_api"
    integration_id: str | None = None
    pricing_basis: Literal["live_api"] | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_source_timestamp(cls, value: str) -> str:
        return _date_string(value)

    @field_validator("savings_period_start", "savings_period_end")
    @classmethod
    def validate_measurement_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return date.fromisoformat(value).isoformat() if len(value) == 10 else _date_string(value)

    @model_validator(mode="after")
    def validate_pricing_source(self) -> "CloudCommitment":
        if self.pricing_basis is not None and (
            self.source != "provider_api"
            or all(value is None for value in (
                self.commitment_amount, self.hourly_commitment, self.savings_amount,
            ))
        ):
            raise ValueError("live_api requires provider financial data")
        return self


class CommitmentSyncStatus(BaseModel):
    integration_id: str
    provider: str
    account_id: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    inventory_regions: list[str] | None = None
    status: InventoryStatus
    source: Literal["provider_api", "demo"] = "provider_api"
    commitment_count: int = Field(default=0, ge=0)
    stale: bool = False
    last_success_at: str | None = None
    last_attempt_at: str | None = None
    error: str | None = None
    error_code: str | None = None
    recommendation_sync_status: str | None = None

    @field_validator("last_success_at", "last_attempt_at")
    @classmethod
    def validate_sync_timestamp(cls, value: str | None) -> str | None:
        return _date_string(value) if value is not None else None


class CommitmentPortfolioSummary(BaseModel):
    currency: str | None = None
    monthly_commitment: float | None = None
    measured_savings: float | None = None
    savings_period_start: str | None = None
    savings_period_end: str | None = None
    utilization_pct: float | None = None
    coverage_pct: None = None
    active_count: int = 0
    measurement_status: Literal["complete", "partial", "unavailable"] = "unavailable"


class CommitmentPortfolioSnapshot(BaseModel):
    commitments: list[CloudCommitment] = Field(default_factory=list)
    integrations: list[CommitmentSyncStatus] = Field(default_factory=list)
    summary: CommitmentPortfolioSummary = Field(default_factory=CommitmentPortfolioSummary)

    @computed_field
    @property
    def count(self) -> int:
        return len(self.commitments)

    @property
    def commitment_count(self) -> int:
        return self.count

    @property
    def statuses(self) -> list[CommitmentSyncStatus]:
        return self.integrations


def _optional_number(value: object) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Provider financial value must be finite")
    return number


def _date_string(value: object) -> str:
    if value is None or value == "":
        return ""
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Source timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _ri_monthly_amount(reservation: dict[str, Any]) -> float | None:
    fixed = _optional_number(reservation.get("FixedPrice"))
    count = _optional_number(reservation.get("InstanceCount"))
    duration = _optional_number(reservation.get("Duration"))
    if duration is None or duration <= 0:
        start, end = reservation.get("Start"), reservation.get("End")
        if start and end:
            start = datetime.fromisoformat(_date_string(start).replace("Z", "+00:00"))
            end = datetime.fromisoformat(_date_string(end).replace("Z", "+00:00"))
            duration = (end - start).total_seconds()
    if fixed is None or count is None or duration is None or duration <= 0:
        return None
    if fixed < 0 or count < 0 or not count.is_integer():
        raise ValueError("Invalid reservation price or instance count")

    usage = _optional_number(reservation.get("UsagePrice"))
    recurring = reservation.get("RecurringCharges")
    if usage is None and recurring is None:
        return None
    hourly = usage if usage is not None else 0.0
    if hourly < 0:
        raise ValueError("Invalid reservation usage price")
    for charge in recurring or []:
        amount = _optional_number(charge.get("Amount"))
        if charge.get("Frequency") != "Hourly" or amount is None:
            return None
        if amount < 0:
            raise ValueError("Invalid reservation recurring price")
        hourly += amount
    # FixedPrice and both hourly charge fields are per instance, not per purchase.
    return count * (fixed / (duration / 3600) + hourly) * MONTHLY_EQUIVALENT_HOURS


def _summarize(
    commitments: list[CloudCommitment], integrations: list[CommitmentSyncStatus],
) -> CommitmentPortfolioSummary:
    active = [item for item in commitments if item.status.lower() == "active"]
    summary = CommitmentPortfolioSummary(active_count=len(active))
    if not active:
        return summary
    has_measurement = any(
        value is not None for item in active
        for value in (item.commitment_amount, item.savings_amount, item.utilization_pct)
    )
    summary.measurement_status = "partial" if has_measurement else "unavailable"
    currencies = {item.currency for item in active}
    if len(currencies) != 1 or not all(currencies):
        return summary
    summary.currency = active[0].currency
    if any(item.stale or item.status not in {"ready", "no_commitments", "demo"} for item in integrations):
        return summary
    if all(item.commitment_amount is not None for item in active):
        summary.monthly_commitment = sum(item.commitment_amount for item in active)
    windows = {(item.savings_period_start, item.savings_period_end) for item in active}
    if len(windows) == 1 and all(all(window) for window in windows) and all(
        item.savings_amount is not None for item in active
    ):
        summary.measured_savings = sum(item.savings_amount for item in active)
        summary.savings_period_start, summary.savings_period_end = next(iter(windows))
    # Monthly obligations are not the denominator for a historical utilization period.
    # RI hours and Savings Plan dollars are not comparable measurements either.
    if len(windows) == 1 and all(all(window) for window in windows):
        if len(active) == 1:
            summary.utilization_pct = active[0].utilization_pct
        elif all(
            item.provider == "aws" and item.type == "Savings Plan"
            and item.utilization_used_commitment is not None
            and item.utilization_total_commitment is not None
            and item.utilization_used_commitment <= item.utilization_total_commitment
            for item in active
        ):
            total = sum(item.utilization_total_commitment for item in active)
            if total > 0:
                summary.utilization_pct = sum(item.utilization_used_commitment for item in active) / total * 100
    if all(value is not None for value in (
        summary.monthly_commitment, summary.measured_savings, summary.utilization_pct,
    )):
        summary.measurement_status = "complete"
    return summary


class CommitmentEngine:
    """Collect provider inventory during sync; serve only durable snapshots on reads."""

    def __init__(self):
        self.executor = None

    @staticmethod
    def _call_with_backoff(
        operation_name: str, func: Callable[[], T], is_retryable: Callable[[Exception], bool],
    ) -> T:
        def invoke() -> T:
            try:
                return func()
            except Exception as error:
                if not is_retryable(error):
                    raise
                # The shared retry logger prints exceptions; never pass raw SDK messages to it.
                raise CommitmentProviderError("Retryable provider request failed") from error

        return call_with_backoff(
            operation_name, invoke,
            is_retryable=lambda error: isinstance(error, CommitmentProviderError)
            and isinstance(error.__cause__, Exception) and is_retryable(error.__cause__),
        )

    def _aws_pages(
        self, operation: str, method: Callable[..., dict[str, Any]], token_key: str,
        **parameters: Any,
    ) -> Iterator[dict[str, Any]]:
        seen: set[str] = set()
        while True:
            page = self._call_with_backoff(operation, lambda: method(**parameters), is_aws_retryable)
            yield page
            token = page.get(token_key)
            if not token:
                return
            if not isinstance(token, str) or token in seen:
                raise CommitmentProviderError("AWS inventory returned an invalid pagination token")
            seen.add(token)
            parameters[token_key] = token

    def _load_demo_commitments(self, integration: dict[str, Any]) -> tuple[list[CloudCommitment], bool]:
        metadata = integration.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("environment") != "demo":
            return [], False
        rows = metadata.get("demo_commitments", [])
        if not isinstance(rows, list):
            raise ValueError("Demo commitments must be a list")
        parsed = []
        for raw in rows:
            row = dict(raw)
            # Legacy demo amounts have no documented units or savings interval.
            if row.get("amount_period") != "monthly":
                row.update(commitment_amount=None, hourly_commitment=None)
            if not row.get("savings_period_start") or not row.get("savings_period_end"):
                row.update(savings_amount=None, savings_period_start=None, savings_period_end=None)
            row.update(
                amount_period="monthly", source="demo", pricing_basis=None,
                integration_id=integration["id"], provider=integration["provider"],
            )
            parsed.append(CloudCommitment.model_validate(row))
        return parsed, True

    def _get_aws_client(
        self, service: str, access_key_id: str, secret_access_key: str, region: str = "us-east-1",
        *, session_token: str | None = None,
    ):
        return boto3.Session().client(
            service,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
            config=build_aws_retry_config(region_name=region),
        )

    def _get_aws_account_id(self, credentials: dict[str, str]) -> str:
        client = self._get_aws_client(
            "sts", credentials["access_key_id"], credentials["secret_access_key"],
            session_token=credentials.get("session_token"),
        )
        identity = self._call_with_backoff("AWS account identity", client.get_caller_identity, is_aws_retryable)
        account_id = str(identity.get("Account") or "")
        if len(account_id) != 12 or not account_id.isascii() or not account_id.isdigit():
            raise ValueError("AWS inventory account identity is unavailable")
        return account_id

    @staticmethod
    def _apply_utilization(
        commitment: CloudCommitment, utilization: object, savings: object, period: dict[str, str],
    ) -> None:
        commitment.utilization_pct = _optional_number(utilization)
        commitment.savings_amount = _optional_number(savings)
        if commitment.utilization_pct is not None or commitment.savings_amount is not None:
            commitment.savings_period_start = period["Start"]
            commitment.savings_period_end = period["End"]
        if commitment.savings_amount is not None:
            commitment.pricing_basis = "live_api"

    async def get_aws_commitments(
        self, access_key_id: str, secret_access_key: str, regions: list[str] | None = None,
        *, session_token: str | None = None,
    ) -> list[CloudCommitment]:
        """Fetch complete AWS inventory and trailing seven-day provider financials."""
        def fetch() -> list[CloudCommitment]:
            get_client = partial(self._get_aws_client, session_token=session_token)
            sp_map: dict[str, CloudCommitment] = {}
            ri_map: dict[str, CloudCommitment] = {}
            sp_client = get_client("savingsplans", access_key_id, secret_access_key)
            for page in self._aws_pages(
                "AWS savings plans list", sp_client.describe_savings_plans, "nextToken",
                states=["active", "payment-pending"],
            ):
                for sp in page["savingsPlans"]:
                    hourly = _optional_number(sp.get("commitment"))
                    sp_map[sp["savingsPlanArn"]] = CloudCommitment(
                        id=sp["savingsPlanId"], provider="aws", type="Savings Plan",
                        name=f"{sp['savingsPlanType']} Savings Plan", status=sp["state"].lower(),
                        start_date=_date_string(sp.get("start")), end_date=_date_string(sp.get("end")),
                        commitment_amount=hourly * MONTHLY_EQUIVALENT_HOURS if hourly is not None else None,
                        hourly_commitment=hourly, currency=sp.get("currency"),
                        region=sp.get("region") or "global",
                        coverage_type=sp["savingsPlanType"],
                        pricing_basis="live_api" if hourly is not None else None,
                    )

            scan_regions = regions
            if not scan_regions:
                ec2 = get_client("ec2", access_key_id, secret_access_key)
                response = self._call_with_backoff("AWS region discovery", ec2.describe_regions, is_aws_retryable)
                scan_regions = [region["RegionName"] for region in response["Regions"]]
                if not scan_regions:
                    raise CommitmentProviderError("AWS region discovery returned no enabled regions")
            for region in dict.fromkeys(scan_regions):
                ec2 = get_client("ec2", access_key_id, secret_access_key, region=region)
                # DescribeReservedInstances has no pagination fields in the EC2 service model.
                response = self._call_with_backoff(
                    "AWS reserved instances list",
                    lambda: ec2.describe_reserved_instances(
                        Filters=[{"Name": "state", "Values": ["active", "payment-pending"]}],
                    ),
                    is_aws_retryable,
                )
                for ri in response["ReservedInstances"]:
                    amount = _ri_monthly_amount(ri)
                    ri_map[ri["ReservedInstancesId"]] = CloudCommitment(
                        id=ri["ReservedInstancesId"], provider="aws", type="Reservation",
                        name=f"{ri['ProductDescription']} RI ({ri['InstanceType']})", status=ri["State"].lower(),
                        start_date=_date_string(ri.get("Start")), end_date=_date_string(ri.get("End")),
                        commitment_amount=amount, currency=ri.get("CurrencyCode"), region=region,
                        coverage_type="Instance", pricing_basis="live_api" if amount is not None else None,
                    )

            if not sp_map and not ri_map:
                return []
            ce = get_client("ce", access_key_id, secret_access_key)
            today = datetime.now(timezone.utc).date()
            # Cost Explorer requires End to precede today; it is end-exclusive.
            end = today - timedelta(days=1)
            period = {"Start": (end - timedelta(days=7)).isoformat(), "End": end.isoformat()}
            if sp_map:
                for page in self._aws_pages(
                    "AWS savings plans utilization", ce.get_savings_plans_utilization_details, "NextToken",
                    TimePeriod=period, DataType=["UTILIZATION", "SAVINGS"],
                ):
                    for detail in page.get("SavingsPlansUtilizationDetails", []):
                        commitment = sp_map.get(detail.get("SavingsPlanArn"))
                        if commitment is not None:
                            utilization = detail.get("Utilization") or {}
                            self._apply_utilization(
                                commitment, utilization.get("UtilizationPercentage"),
                                (detail.get("Savings") or {}).get("NetSavings"), page.get("TimePeriod") or period,
                            )
                            commitment.utilization_used_commitment = _optional_number(utilization.get("UsedCommitment"))
                            commitment.utilization_total_commitment = _optional_number(utilization.get("TotalCommitment"))
                            if (commitment.utilization_used_commitment is not None
                                and commitment.utilization_total_commitment is not None
                                and commitment.utilization_used_commitment > commitment.utilization_total_commitment):
                                raise ValueError("Used commitment exceeds measured total commitment")
            if ri_map:
                for page in self._aws_pages(
                    "AWS reservation utilization", ce.get_reservation_utilization, "NextPageToken",
                    TimePeriod=period, GroupBy=[{"Type": "DIMENSION", "Key": "SUBSCRIPTION_ID"}],
                ):
                    for detail in page.get("UtilizationsByTime", []):
                        for group in detail.get("Groups", []):
                            # Botocore models Key/Value and a string Attributes map; Keys is legacy fallback.
                            attributes = group.get("Attributes") or {}
                            candidates = [attributes.get("reservationId"), attributes.get("reservationARN"),
                                          group.get("Value"), *(group.get("Keys") or [])]
                            for candidate in candidates:
                                if not isinstance(candidate, str):
                                    continue
                                reservation_id = candidate.rsplit("/", 1)[-1] if candidate.startswith("arn:") else candidate
                                commitment = ri_map.get(reservation_id)
                                if commitment is not None:
                                    utilization = group.get("Utilization") or {}
                                    self._apply_utilization(
                                        commitment, utilization.get("UtilizationPercentage"),
                                        utilization.get("NetRISavings"), detail.get("TimePeriod") or period,
                                    )
                                    break
            return [*sp_map.values(), *ri_map.values()]

        try:
            return await asyncio.get_running_loop().run_in_executor(self.executor, fetch)
        except Exception as error:
            logger.warning("AWS commitment inventory failed (%s)", type(error).__name__)
            raise CommitmentProviderError(f"AWS commitment inventory failed ({type(error).__name__})") from error

    async def get_gcp_commitments(
        self, project_id: str, service_account_email: str, private_key: str, regions: list[str] | None = None,
    ) -> list[CloudCommitment]:
        """Fetch GCP CUD inventory; Compute Engine does not supply its financials."""
        def fetch() -> list[CloudCommitment]:
            from google.cloud import compute_v1
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(
                {"type": "service_account", "project_id": project_id, "private_key": private_key,
                 "client_email": service_account_email, "token_uri": "https://oauth2.googleapis.com/token"},
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            scan_regions = regions
            if not scan_regions:
                region_client = compute_v1.RegionsClient(credentials=credentials)
                discovered = self._call_with_backoff(
                    "GCP region discovery",
                    lambda: list(region_client.list(request=compute_v1.ListRegionsRequest(project=project_id))),
                    is_gcp_retryable,
                )
                scan_regions = [region.name for region in discovered]
                if not scan_regions:
                    raise CommitmentProviderError("GCP region discovery returned no regions")
            client = compute_v1.RegionCommitmentsClient(credentials=credentials)
            commitments = []
            for region in dict.fromkeys(scan_regions):
                request = compute_v1.ListRegionCommitmentsRequest(project=project_id, region=region)
                response = self._call_with_backoff(
                    "GCP commitments list", lambda: list(client.list(request=request)), is_gcp_retryable,
                )
                for item in response:
                    commitments.append(CloudCommitment(
                        id=str(item.id), provider="gcp", type="CUD", name=item.name,
                        status=item.status.lower(), start_date=item.start_timestamp or "",
                        end_date=item.end_timestamp or "", region=region, coverage_type="Compute",
                    ))
            return commitments

        try:
            return await asyncio.get_running_loop().run_in_executor(self.executor, fetch)
        except Exception as error:
            logger.warning("GCP commitment inventory failed (%s)", type(error).__name__)
            raise CommitmentProviderError(f"GCP commitment inventory failed ({type(error).__name__})") from error

    @staticmethod
    def _snapshot_id(user_id: str, integration_id: str) -> str:
        return hashlib.sha256(json.dumps([user_id, integration_id]).encode("utf-8")).hexdigest()

    async def sync_integration_commitments(
        self, *, db: MongoDBClient, user_id: str, integration: dict[str, Any],
    ) -> CommitmentSyncStatus:
        """Replace a scoped snapshot on success; retain last-known inventory on failure."""
        try:
            if not user_id or not integration.get("id"):
                raise ValueError("User and integration IDs are required")
            if "user_id" in integration and integration["user_id"] != user_id:
                raise ValueError("Integration does not belong to the authenticated user")
            integration_id = integration["id"]
            provider = integration.get("provider", "")
            if integration.get("status") != "active":
                return CommitmentSyncStatus(
                    integration_id=integration_id, provider=provider, status="not_synced", error_code="inactive",
                )
            snapshot_id = self._snapshot_id(user_id, integration_id)
            rows = await db.select(SNAPSHOT_COLLECTION, filters={
                "id": snapshot_id, "user_id": user_id, "integration_id": integration_id,
            })
            previous = rows[0] if rows else {}
            is_demo = isinstance(integration.get("metadata"), dict) and integration["metadata"].get("environment") == "demo"
            status = CommitmentSyncStatus(
                integration_id=integration_id, provider=provider, status="error",
                source="demo" if is_demo else "provider_api",
                last_attempt_at=datetime.now(timezone.utc).isoformat(),
                last_success_at=previous.get("last_success_at"),
                account_id=previous.get("account_id"), inventory_regions=previous.get("inventory_regions"),
            )
            commitments = previous.get("commitments", [])
            try:
                inventory, is_demo = self._load_demo_commitments(integration)
                if not is_demo and provider not in {"aws", "gcp"}:
                    status.status = "unsupported"
                    status.error = "Commitment inventory is not supported for this provider"
                    status.error_code = "unsupported_provider"
                    status.stale = bool(status.last_success_at)
                else:
                    credentials = {} if is_demo else decrypt_integration_credentials(integration)
                    if not is_demo:
                        if provider == "aws" and credentials.get("role_arn"):
                            from ..scanners.aws import AWSScanner

                            if not credentials.get("external_id"):
                                raise ValueError("Role-based access requires an ExternalId")
                            assumed = await asyncio.to_thread(
                                AWSScanner._assume_role,
                                credentials.get("access_key_id", ""), credentials.get("secret_access_key", ""),
                                credentials["role_arn"], credentials["external_id"],
                            )
                            credentials = {"access_key_id": assumed["AccessKeyId"],
                                           "secret_access_key": assumed["SecretAccessKey"],
                                           "session_token": assumed["SessionToken"]}
                        required = ("access_key_id", "secret_access_key") if provider == "aws" else (
                            "project_id", "service_account_email", "private_key",
                        )
                        if any(not credentials.get(key) for key in required):
                            raise ValueError("Required provider credentials are missing")
                        if provider == "aws":
                            account_id = await asyncio.to_thread(self._get_aws_account_id, credentials)
                            token_options = {"session_token": credentials["session_token"]} if credentials.get("session_token") else {}
                            inventory = await self.get_aws_commitments(
                                credentials["access_key_id"], credentials["secret_access_key"], integration.get("regions"),
                                **token_options,
                            )
                            status.account_id = account_id
                            status.inventory_regions = sorted(set(integration["regions"])) if integration.get("regions") else None
                        else:
                            inventory = await self.get_gcp_commitments(
                                credentials["project_id"], credentials["service_account_email"],
                                credentials["private_key"], integration.get("regions"),
                            )
                    for commitment in inventory:
                        commitment.integration_id = integration_id
                    commitments = [commitment.model_dump(mode="json") for commitment in inventory]
                    status.status = "demo" if is_demo else ("ready" if commitments else "no_commitments")
                    status.last_success_at = datetime.now(timezone.utc).isoformat()
            except Exception as error:
                status.error_code = type(error).__name__
                status.error = f"Commitment inventory refresh failed ({status.error_code})"
                status.stale = bool(status.last_success_at)
                logger.warning("Commitment inventory sync failed (%s)", status.error_code)

            status.commitment_count = len(commitments)
            payload = {"id": snapshot_id, "user_id": user_id, **status.model_dump(mode="json"),
                       "commitments": commitments}
            await db.upsert(SNAPSHOT_COLLECTION, payload)
            if status.status in {"ready", "no_commitments"} and provider == "aws":
                try:
                    from app.core.commitment_recommendations import sync_aws_purchase_recommendations

                    await sync_aws_purchase_recommendations(
                        db=db, user_id=user_id, integration=integration, credentials=credentials,
                    )
                    # The helper owns recommendation failure persistence; this records invocation completion.
                    status.recommendation_sync_status = "completed"
                except Exception as error:
                    status.recommendation_sync_status = "error"
                    logger.warning("Commitment recommendation sync failed (%s)", type(error).__name__)
                await db.update(SNAPSHOT_COLLECTION, {
                    "recommendation_sync_status": status.recommendation_sync_status,
                }, filters={"id": snapshot_id, "user_id": user_id, "integration_id": integration_id})
            return status
        except Exception as error:
            logger.warning("Commitment snapshot sync failed (%s)", type(error).__name__)
            raise

    async def get_portfolio_snapshot(
        self, user_id: str, *, db: MongoDBClient | None = None,
    ) -> CommitmentPortfolioSnapshot:
        """Read only persisted inventory belonging to this user's active integrations."""
        try:
            if not user_id:
                raise ValueError("User ID is required")
            db = db if db is not None else get_db_client()
            integrations = await db.select("cloud_integrations", filters={"user_id": user_id, "status": "active"})
            portfolio = CommitmentPortfolioSnapshot()
            if not integrations:
                return portfolio
            rows = await db.select(SNAPSHOT_COLLECTION, filters={
                "user_id": user_id, "integration_id": {"$in": [integration["id"] for integration in integrations]},
            })
            snapshots = {row["integration_id"]: row for row in rows}
            now = datetime.now(timezone.utc)
            seen_aws: set[tuple[str, str, str, str | None, str]] = set()
            seen_accounts: dict[str, tuple[str, ...] | None] = {}
            # Duplicate connections can expose the same AWS inventory; the newest snapshot wins.
            integrations.sort(key=lambda integration: str(snapshots.get(integration["id"], {}).get("last_success_at") or ""), reverse=True)
            for integration in integrations:
                row = snapshots.get(integration["id"])
                if row is None:
                    metadata = integration.get("metadata") if isinstance(integration.get("metadata"), dict) else {}
                    portfolio.integrations.append(CommitmentSyncStatus(
                        integration_id=integration["id"], provider=integration["provider"], status="not_synced",
                        source="demo" if metadata.get("environment") == "demo" else "provider_api",
                    ))
                    continue
                inventory = [CloudCommitment.model_validate(commitment) for commitment in row.get("commitments", [])]
                if any(commitment.integration_id != integration["id"] or commitment.provider != integration["provider"] for commitment in inventory):
                    raise ValueError("Persisted commitment has an invalid integration scope")
                status = CommitmentSyncStatus.model_validate(row)
                status.commitment_count = len(inventory)
                if status.status in {"ready", "no_commitments", "demo"}:
                    last_success = datetime.fromisoformat(status.last_success_at) if status.last_success_at else None
                    if last_success is None or not timedelta(0) <= now - last_success <= MAX_INVENTORY_AGE:
                        status.stale = True
                        status.error_code = "stale_snapshot"
                        status.error = "Commitment inventory has no recent successful refresh"
                portfolio.integrations.append(status)
                if status.provider == "aws" and status.source == "provider_api":
                    if not status.account_id:
                        status.stale = True
                        status.error_code = "unverified_account_scope"
                        status.error = "Refresh inventory to verify its AWS account identity"
                    else:
                        region_scope = tuple(sorted(status.inventory_regions)) if status.inventory_regions is not None else None
                        if status.account_id in seen_accounts:
                            if seen_accounts[status.account_id] == region_scope:
                                continue
                            status.stale = True
                            status.error_code = "incompatible_inventory_scopes"
                            status.error = "Duplicate AWS connections have different region scopes; portfolio totals require a unified inventory scope"
                        else:
                            seen_accounts[status.account_id] = region_scope
                for commitment in inventory:
                    if commitment.status.lower() == "active":
                        if commitment.end_date and datetime.fromisoformat(commitment.end_date) <= now:
                            commitment.status = "expired"
                        elif commitment.start_date and datetime.fromisoformat(commitment.start_date) > now:
                            commitment.status = "pending"
                    identity = (status.account_id or integration["id"], commitment.source,
                                commitment.type, commitment.region, commitment.id)
                    if commitment.provider == "aws":
                        if identity in seen_aws:
                            continue
                        seen_aws.add(identity)
                    portfolio.commitments.append(commitment)
            portfolio.summary = _summarize(portfolio.commitments, portfolio.integrations)
            return portfolio
        except Exception as error:
            logger.warning("Commitment snapshot read failed (%s)", type(error).__name__)
            raise

    async def get_commitments(self, user_id: str, db: MongoDBClient | None = None) -> list[CloudCommitment]:
        """Compatibility list view of the persisted portfolio snapshot."""
        try:
            return (await self.get_portfolio_snapshot(user_id, db=db)).commitments
        except Exception as error:
            logger.warning("Commitment inventory read failed (%s)", type(error).__name__)
            raise


commitment_engine = CommitmentEngine()
