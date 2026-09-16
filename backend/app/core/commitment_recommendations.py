"""Persisted, account-scoped AWS purchase estimates shared by the API and copilot."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

import boto3
from pydantic import BaseModel, Field

from ..db.mongo_client import MongoDBClient
from .retry import build_aws_retry_config

logger = logging.getLogger(__name__)

PURCHASE_SNAPSHOTS = "commitment_purchase_snapshots"
SOURCE = "aws_cost_explorer"
MONTHLY_EQUIVALENT_HOURS = Decimal(730)
MAX_RECOMMENDATION_AGE = timedelta(hours=48)


class CommitmentScopeNotFoundError(ValueError):
    """The requested integration is not active and owned by this user."""


class CommitmentPurchaseScenario(BaseModel):
    label: str
    commitment_pct: None = None
    monthly_commitment_usd: float = Field(ge=0, allow_inf_nan=False)
    monthly_saving_usd: float = Field(ge=0, allow_inf_nan=False)
    annual_saving_usd: float = Field(ge=0, allow_inf_nan=False)
    effective_discount_pct: None = None
    provider_estimated_savings_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    over_commitment_risk_pct: None = None
    risk_level: Literal["Unassessed"] = "Unassessed"
    term_years: Literal[1, 3]
    hourly_commitment_usd: float = Field(gt=0, allow_inf_nan=False)
    estimated_utilization_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    integration_id: str
    account_id: str
    recommendation_id: str
    source: Literal["aws_cost_explorer"] = SOURCE
    generated_at: str
    payment_option: Literal["NO_UPFRONT"] = "NO_UPFRONT"
    savings_plans_type: Literal["COMPUTE_SP"] = "COMPUTE_SP"
    lookback_days: Literal[60] = 60


class CommitmentRecommendationResult(BaseModel):
    status: Literal["ready", "not_synced", "stale", "unavailable", "no_recommendations", "unsupported", "insufficient_history", "no_spend_data"]
    message: str | None = None
    days_available: int | None = None
    analysis_basis_days: int | None = None
    avg_monthly_spend_usd: float | None = None
    forecast_eom_spend_usd: float | None = None
    forecast_method: str | None = None
    forecast_stable: bool | None = None
    spend_volatility_pct: float | None = None
    compute_fraction_pct: None = None
    safe_baseline_monthly_usd: None = None
    scenarios: list[CommitmentPurchaseScenario] = Field(default_factory=list)
    recommended_scenario: None = None
    important_notes: list[str] = Field(default_factory=list)
    aws_console_link: str = "https://console.aws.amazon.com/costmanagement/home#/savings-plans/recommendations"
    source: Literal["aws_cost_explorer"] = SOURCE
    pricing_basis: Literal["live_api"] | None = None
    fetched_at: str | None = None
    generated_at: str | None = None
    currency: Literal["USD"] = "USD"


def _decimal(value: object, *, required: bool = False) -> Decimal | None:
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError("Invalid monetary measurement")
        return number
    except (InvalidOperation, ValueError, TypeError):
        if required:
            raise ValueError("AWS recommendation is missing a valid monetary measurement") from None
        return None


def _timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def _percentage(value: object) -> float | None:
    number = _decimal(value)
    return float(number) if number is not None and number <= 100 else None


def _normalize_detail(
    detail: dict,
    *,
    account_id: str,
    integration_id: str,
    years: Literal[1, 3],
    generated_at: str,
    recommendation_id: str,
) -> CommitmentPurchaseScenario:
    if detail.get("AccountId") != account_id:
        raise ValueError("AWS returned a recommendation for a different account")
    if detail.get("CurrencyCode") != "USD":
        raise ValueError("AWS recommendation currency is not USD")
    hourly = _decimal(detail.get("HourlyCommitmentToPurchase"), required=True)
    monthly_saving = _decimal(detail.get("EstimatedMonthlySavingsAmount"), required=True)
    upfront = _decimal(detail.get("UpfrontCost"), required=True)
    if hourly is None or monthly_saving is None or hourly <= 0 or upfront != 0:
        raise ValueError("AWS recommendation has inconsistent no-upfront purchase terms")
    return CommitmentPurchaseScenario(
        label=f"{years}-year Compute Savings Plan",
        monthly_commitment_usd=float((hourly * MONTHLY_EQUIVALENT_HOURS).quantize(Decimal("0.01"))),
        monthly_saving_usd=float(monthly_saving.quantize(Decimal("0.01"))),
        annual_saving_usd=float((monthly_saving * 12).quantize(Decimal("0.01"))),
        provider_estimated_savings_pct=_percentage(detail.get("EstimatedSavingsPercentage")),
        hourly_commitment_usd=float(hourly),
        estimated_utilization_pct=_percentage(detail.get("EstimatedAverageUtilization")),
        term_years=years,
        integration_id=integration_id,
        account_id=account_id,
        recommendation_id=str(detail.get("RecommendationDetailId") or recommendation_id),
        generated_at=generated_at,
    )


def fetch_aws_purchase_recommendations(*, credentials: dict, integration_id: str) -> dict:
    """Read Cost Explorer estimates without purchasing or changing commitments."""
    access_key = credentials.get("access_key_id")
    secret_key = credentials.get("secret_access_key")
    if not access_key or not secret_key:
        raise ValueError("AWS credentials are incomplete")
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=credentials.get("session_token"),
    )
    config = build_aws_retry_config(region_name="us-east-1", max_attempts=3)
    identity = session.client("sts", config=config).get_caller_identity()
    account_id = str(identity.get("Account") or "")
    if len(account_id) != 12 or not account_id.isdigit():
        raise ValueError("AWS account identity is unavailable")
    client = session.client("ce", config=config)
    scenarios: list[dict] = []
    generations: list[datetime] = []
    for years, term in ((1, "ONE_YEAR"), (3, "THREE_YEARS")):
        request = {
            "SavingsPlansType": "COMPUTE_SP",
            "TermInYears": term,
            "PaymentOption": "NO_UPFRONT",
            "AccountScope": "LINKED",
            "LookbackPeriodInDays": "SIXTY_DAYS",
            "Filter": {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}},
            "PageSize": 100,
        }
        seen_tokens: set[str] = set()
        seen_details: set[str] = set()
        for _ in range(100):
            page = client.get_savings_plans_purchase_recommendation(**request)
            result = page.get("SavingsPlansPurchaseRecommendation")
            if not isinstance(result, dict):
                raise ValueError("AWS purchase recommendation response is incomplete")
            for key in ("SavingsPlansType", "TermInYears", "PaymentOption", "AccountScope", "LookbackPeriodInDays"):
                if result.get(key) != request[key]:
                    raise ValueError("AWS returned different purchase recommendation terms")
            details = result.get("SavingsPlansPurchaseRecommendationDetails")
            if not isinstance(details, list):
                raise ValueError("AWS purchase recommendation details are incomplete")
            metadata = page.get("Metadata") or {}
            generation = _timestamp(metadata.get("GenerationTimestamp"))
            if details and generation is None:
                raise ValueError("AWS recommendation generation time is unavailable")
            if generation is not None:
                generations.append(generation)
            for detail in details:
                if not isinstance(detail, dict):
                    raise ValueError("Invalid AWS recommendation detail")
                scenario = _normalize_detail(
                    detail,
                    account_id=account_id,
                    integration_id=integration_id,
                    years=years,
                    generated_at=generation.isoformat(),
                    recommendation_id=str(metadata.get("RecommendationId") or ""),
                )
                if not scenario.recommendation_id or scenario.recommendation_id in seen_details:
                    raise ValueError("AWS returned missing or duplicate recommendation identity")
                seen_details.add(scenario.recommendation_id)
                scenarios.append(scenario.model_dump())
            token = page.get("NextPageToken")
            if not token:
                break
            if token in seen_tokens:
                raise ValueError("AWS recommendation pagination repeated a token")
            seen_tokens.add(token)
            request["NextPageToken"] = token
        else:
            raise ValueError("AWS recommendation pagination limit reached")
    return {
        "account_id": account_id,
        "scenarios": scenarios,
        "generated_at": min(generations).isoformat() if generations else None,
        "status": "ready" if scenarios else "no_recommendations",
    }


async def sync_aws_purchase_recommendations(
    *, db: MongoDBClient, user_id: str, integration: dict, credentials: dict,
) -> None:
    """Replace a complete snapshot; retain last-known data if a refresh fails."""
    integration_id = str(integration.get("id") or "")
    if (
        not user_id or not integration_id or integration.get("user_id", user_id) != user_id
        or integration.get("provider") != "aws" or integration.get("status") != "active"
    ):
        raise ValueError("Invalid commitment integration scope")
    now = datetime.now(timezone.utc).isoformat()
    filters = {"user_id": user_id, "integration_id": integration_id}
    identity = hashlib.sha256(json.dumps([user_id, integration_id]).encode()).hexdigest()
    try:
        existing = await db.select(PURCHASE_SNAPSHOTS, filters=filters)
        prior = existing[0] if existing else {}
        record = {**prior, "id": identity, **filters, "source": SOURCE, "last_attempt_at": now}
        try:
            fetched = await asyncio.to_thread(
                fetch_aws_purchase_recommendations,
                credentials=credentials,
                integration_id=integration_id,
            )
            record.update(fetched)
            record.update(fetched_at=now, last_success_at=now, message=None)
        except Exception as error:
            logger.warning("AWS purchase estimate refresh failed for %s (%s)", integration_id, type(error).__name__)
            record.update(status="unavailable", message="AWS purchase estimates could not be refreshed. Check Cost Explorer access and billing-data availability.")
        await db.upsert(PURCHASE_SNAPSHOTS, record)
    except Exception as error:
        logger.error("Commitment purchase snapshot persistence failed (%s)", type(error).__name__)
        raise


async def get_commitment_recommendation_result(
    *, db: MongoDBClient, user_id: str, integration_id: str | None = None,
    now: datetime | None = None,
) -> CommitmentRecommendationResult:
    """Serve persisted estimates only; missing evidence never becomes a buy signal."""
    try:
        if not user_id:
            raise ValueError("User ID is required")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("An aware evaluation timestamp is required")
        integrations = await db.get_user_integrations(user_id)
        active = [row for row in integrations if row.get("status") == "active" and row.get("user_id", user_id) == user_id]
        if integration_id:
            active = [row for row in active if row.get("id") == integration_id]
            if not active:
                raise CommitmentScopeNotFoundError("Integration not found")
        aws = [row for row in active if row.get("provider") == "aws"]
        if not aws:
            return CommitmentRecommendationResult(status="unsupported" if active else "no_spend_data", message="Provider-backed purchase estimates currently support AWS Compute Savings Plans.")
        filters = {"user_id": user_id}
        if integration_id:
            filters["integration_id"] = integration_id
        snapshots = await db.select(PURCHASE_SNAPSHOTS, filters=filters)
        active_ids = {row["id"] for row in aws}
        snapshots = [row for row in snapshots if row.get("integration_id") in active_ids and row.get("source") == SOURCE]
        if not snapshots:
            return CommitmentRecommendationResult(status="not_synced", message="Run a cloud scan to refresh AWS purchase estimates.")
        notes = [
            "AWS estimates use the last 60 days of eligible usage and existing commitments; future demand can differ.",
            "Term options for the same account are alternatives and must not be added together.",
            "Monthly commitment is an hourly obligation multiplied by 730 average calendar hours; actual monthly charges vary.",
            "Annual savings are the provider's monthly estimate multiplied by 12, not a guaranteed forecast.",
            "Resource-level coverage, future overcommitment risk, and rightsizing effects have not been measured here.",
        ]
        scenarios: list[CommitmentPurchaseScenario] = []
        fetched_times: list[datetime] = []
        generation_times: list[datetime] = []
        unavailable = 0
        stale = 0
        seen_accounts: set[str] = set()
        for snapshot in sorted(snapshots, key=lambda row: str(row.get("fetched_at") or ""), reverse=True):
            account_id = str(snapshot.get("account_id") or "")
            if account_id and account_id in seen_accounts:
                continue
            if account_id:
                seen_accounts.add(account_id)
            fetched = _timestamp(snapshot.get("fetched_at"))
            generated = _timestamp(snapshot.get("generated_at"))
            if snapshot.get("status") not in {"ready", "no_recommendations"}:
                unavailable += 1
                continue
            if fetched is None or not timedelta(0) <= current - fetched <= MAX_RECOMMENDATION_AGE:
                stale += 1
                continue
            if snapshot.get("status") == "ready" and (generated is None or not timedelta(0) <= current - generated <= MAX_RECOMMENDATION_AGE):
                stale += 1
                continue
            try:
                rows = [CommitmentPurchaseScenario.model_validate(row) for row in snapshot.get("scenarios", [])]
                if (snapshot.get("status") == "ready") != bool(rows):
                    raise ValueError("Snapshot status contradicts its purchase estimates")
                if any(row.account_id != account_id or row.integration_id != snapshot.get("integration_id") for row in rows):
                    raise ValueError("Snapshot scope mismatch")
                for row in rows:
                    row_generated = _timestamp(row.generated_at)
                    if row_generated is None or not timedelta(0) <= current - row_generated <= MAX_RECOMMENDATION_AGE:
                        raise ValueError("Purchase estimate has no current provider generation timestamp")
            except (ValueError, TypeError):
                unavailable += 1
                continue
            scenarios.extend(rows)
            fetched_times.append(fetched)
            if generated:
                generation_times.append(generated)
        missing = len(active_ids - {row.get("integration_id") for row in snapshots})
        if unavailable or stale or missing:
            notes.append(f"Incomplete account coverage: {unavailable} unavailable, {stale} stale, {missing} not synced.")
        status = "ready" if scenarios else ("unavailable" if unavailable else "stale" if stale else "not_synced" if missing else "no_recommendations")
        return CommitmentRecommendationResult(
            status=status,
            message=None if scenarios else "No current, validated AWS purchase estimates are available. Refresh the scan and review Cost Explorer permissions.",
            analysis_basis_days=60 if scenarios else None,
            scenarios=scenarios,
            important_notes=notes,
            pricing_basis="live_api" if scenarios else None,
            fetched_at=min(fetched_times).isoformat() if fetched_times else None,
            generated_at=min(generation_times).isoformat() if generation_times else None,
        )
    except Exception as error:
        logger.warning("Commitment recommendation read failed (%s)", type(error).__name__)
        raise
