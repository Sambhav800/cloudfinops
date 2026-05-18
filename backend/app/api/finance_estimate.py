import hashlib
import json
import logging
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..core.cost_engine import CostMapper
from ..core.policy_engine import evaluate_policy
from ..core.simulation_store import get_simulation_history, save_simulation_run
from ..db import MongoDBClient, get_db_client

logger = logging.getLogger(__name__)

estimate_router = APIRouter(prefix="/api/finance", tags=["Finance Estimation"])


class TerraformPlanRequest(BaseModel):
    """Request model for Terraform plan estimation."""

    plan: Dict[str, Any]
    filename: Optional[str] = None


class EstimationResourceItem(BaseModel):
    """Estimated cost impact for a single Terraform resource change."""

    name: str
    type: str
    provider: str
    region: str
    action: str
    resource_family: str
    pricing_source: str
    before: float
    after: float
    notes: str = ""


class EstimationSummary(BaseModel):
    """Coverage summary for a Terraform cost estimate run."""

    total_resources: int = 0
    priced_resources: int = 0
    exact_pricing_resources: int = 0
    estimated_resources: int = 0
    usage_based_resources: int = 0
    unsupported_resources: int = 0


class MonthlyBlock(BaseModel):
    """Monthly before/after/delta estimate block."""

    before: float
    after: float
    delta: float


class AnnualBlock(BaseModel):
    """Annual before/after/delta estimate block."""

    before: float
    after: float
    delta: float


class V2SummaryBlock(BaseModel):
    """Coverage summary for the simulator v2 contract."""

    total_resources: int
    priced_resources: int
    exact_resources: int
    estimated_resources: int
    usage_based_resources: int
    unestimated_resources: int


class PricedResource(BaseModel):
    """Priced resource row in the simulator v2 contract."""

    resource_address: str
    resource_type: str
    action: Literal["create", "update", "delete", "no-op"]
    provider: Literal["aws", "azure", "gcp", "generic"]
    region: Optional[str] = None
    resource_family: Literal[
        "compute",
        "storage",
        "network",
        "database",
        "serverless",
        "kubernetes",
        "other",
    ]
    before_monthly: float
    after_monthly: float
    delta_monthly: float
    hourly_rate: Optional[float] = None
    pricing_source: Literal["exact_api", "heuristic_estimate", "usage_based", "unsupported"]
    pricing_basis: Optional[str] = None
    confidence: Literal["high", "medium", "low"]
    notes: Optional[str] = None
    source_provenance: Optional[str] = None


class UnestimatedResource(BaseModel):
    """Terraform resource that remained unpriced."""

    resource_address: str
    resource_type: str
    provider: str
    region: Optional[str] = None
    action: str
    reason: str


class BestPracticeFinding(BaseModel):
    """Deterministic best-practice finding from the simulator engine."""

    resource_address: str
    finding_id: str
    severity: Literal["critical", "high", "medium", "low"]
    monthly_impact: Optional[float] = None
    annual_impact: Optional[float] = None
    evidence: str
    remediation: str
    confidence: Literal["high", "medium", "low"]


class SimulationEstimateResponseV2(BaseModel):
    """Backward-compatible v2 simulator response."""

    schema_version: Literal["2026-04-simulator-v2"] = "2026-04-simulator-v2"
    currency: Literal["USD"] = "USD"
    monthly: MonthlyBlock
    annual: AnnualBlock
    summary: V2SummaryBlock
    resources: List[PricedResource] = Field(default_factory=list)
    unestimated_resources: List[UnestimatedResource] = Field(default_factory=list)
    findings: List[BestPracticeFinding] = Field(default_factory=list)
    policy: Optional[Dict[str, Any]] = None


class EstimationResponse(BaseModel):
    """Response model for cost estimation."""

    delta_monthly_cost: float
    currency: str = "USD"
    resources: List[EstimationResourceItem] = Field(default_factory=list)
    summary: EstimationSummary = Field(default_factory=EstimationSummary)


def _normalize_v2_action(action: str) -> Literal["create", "update", "delete", "no-op"]:
    normalized = (action or "").strip().lower()
    if normalized in {"create", "update", "delete", "no-op"}:
        return normalized  # type: ignore[return-value]
    if "delete" in normalized and "create" in normalized:
        return "update"
    return "no-op"


def _normalize_v2_family(family: str) -> Literal[
    "compute",
    "storage",
    "network",
    "database",
    "serverless",
    "kubernetes",
    "other",
]:
    normalized = (family or "").strip().lower()
    if normalized in {"compute", "storage", "network", "database", "serverless", "kubernetes"}:
        return normalized  # type: ignore[return-value]
    return "other"


def _normalize_v2_provider(provider: str) -> Literal["aws", "azure", "gcp", "generic"]:
    normalized = (provider or "").strip().lower()
    if normalized in {"aws", "azure", "gcp"}:
        return normalized  # type: ignore[return-value]
    return "generic"


def _resource_confidence(pricing_source: str) -> Literal["high", "medium", "low"]:
    if pricing_source == "exact_api":
        return "high"
    if pricing_source == "usage_based":
        return "medium"
    return "low"


def _resource_provenance(pricing_source: str) -> Optional[str]:
    if pricing_source == "exact_api":
        return "provider catalog"
    if pricing_source == "heuristic_estimate":
        return "CloudFinOps deterministic heuristic"
    if pricing_source == "usage_based":
        return "Terraform plan usage-dependent resource"
    return None


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _normalize_v2_severity(value: str) -> Literal["critical", "high", "medium", "low"]:
    normalized = (value or "").strip().lower()
    if normalized in {"critical", "high", "medium", "low"}:
        return normalized  # type: ignore[return-value]
    return "low"


def _normalize_v2_confidence(value: str) -> Literal["high", "medium", "low"]:
    normalized = (value or "").strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized  # type: ignore[return-value]
    return "low"


def _build_v2_response(engine_result: Dict[str, Any]) -> SimulationEstimateResponseV2:
    resources: List[PricedResource] = []
    for item in engine_result.get("resources", []):
        before_monthly = float(item.get("before") or 0)
        after_monthly = float(item.get("after") or 0)
        pricing_source = str(item.get("pricing_source") or "unsupported")
        resources.append(
            PricedResource(
                resource_address=str(item.get("name") or item.get("address") or "unknown"),
                resource_type=str(item.get("type") or "unknown"),
                action=_normalize_v2_action(str(item.get("action") or "")),
                provider=_normalize_v2_provider(str(item.get("provider") or "")),
                region=item.get("region"),
                resource_family=_normalize_v2_family(str(item.get("resource_family") or "")),
                before_monthly=before_monthly,
                after_monthly=after_monthly,
                delta_monthly=round(after_monthly - before_monthly, 2),
                hourly_rate=None,
                pricing_source=pricing_source,  # type: ignore[arg-type]
                pricing_basis=None,
                confidence=_resource_confidence(pricing_source),
                notes=item.get("notes") or None,
                source_provenance=_resource_provenance(pricing_source),
            )
        )

    unestimated_resources = [
        UnestimatedResource(
            resource_address=str(item.get("resource_address") or item.get("address") or "unknown"),
            resource_type=str(item.get("resource_type") or item.get("type") or "unknown"),
            provider=str(item.get("provider") or "generic"),
            region=item.get("region"),
            action=str(item.get("action") or "unknown"),
            reason=str(item.get("reason") or "resource type not in simulator pricing catalog"),
        )
        for item in engine_result.get("unestimated_resources", [])
    ]

    total_before = round(sum(item.before_monthly for item in resources), 2)
    total_after = round(sum(item.after_monthly for item in resources), 2)
    delta = round(total_after - total_before, 2)

    summary = engine_result.get("summary", {})
    findings = [
        BestPracticeFinding(
            resource_address=str(item.get("resource_address") or "unknown"),
            finding_id=str(item.get("finding_id") or "simulator-finding"),
            severity=_normalize_v2_severity(str(item.get("severity") or "")),
            monthly_impact=item.get("monthly_impact"),
            annual_impact=item.get("annual_impact"),
            evidence=str(item.get("evidence") or "Simulator finding generated from Terraform plan attributes."),
            remediation=str(item.get("remediation") or "Review this resource before applying the Terraform plan."),
            confidence=_normalize_v2_confidence(str(item.get("confidence") or "")),
        )
        for item in engine_result.get("findings", [])
    ]
    response = SimulationEstimateResponseV2(
        monthly=MonthlyBlock(before=total_before, after=total_after, delta=delta),
        annual=AnnualBlock(
            before=round(total_before * 12, 2),
            after=round(total_after * 12, 2),
            delta=round(delta * 12, 2),
        ),
        summary=V2SummaryBlock(
            total_resources=int(summary.get("total_resources") or len(resources) + len(unestimated_resources)),
            priced_resources=len(resources),
            exact_resources=sum(1 for item in resources if item.pricing_source == "exact_api"),
            estimated_resources=sum(1 for item in resources if item.pricing_source == "heuristic_estimate"),
            usage_based_resources=sum(1 for item in resources if item.pricing_source == "usage_based"),
            unestimated_resources=len(unestimated_resources),
        ),
        resources=resources,
        unestimated_resources=unestimated_resources,
        findings=findings,
    )
    response.policy = evaluate_policy(
        monthly=_model_to_dict(response.monthly),
        annual=_model_to_dict(response.annual),
        summary=_model_to_dict(response.summary),
        findings=[_model_to_dict(item) for item in response.findings],
    )
    return response


@estimate_router.post("/estimate", response_model=Union[EstimationResponse, SimulationEstimateResponseV2])
async def estimate_terraform_cost(
    request: Request,
    payload: TerraformPlanRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> Union[EstimationResponse, SimulationEstimateResponseV2]:
    """
    Estimate the monthly cost impact of a Terraform plan.

    The estimator prefers exact provider pricing when catalog matches exist and
    falls back to provider-aware heuristics or explicit zero-cost usage notes
    when the plan includes resources outside the exact catalog coverage.
    """
    try:
        mapper = CostMapper()
        result = await mapper.estimate_monthly_cost(payload.plan)
        if request.headers.get("X-Simulator-Version") == "v2":
            response_v2 = _build_v2_response(result)
            if hasattr(db, "insert"):
                try:
                    plan_hash = hashlib.sha256(
                        json.dumps(payload.plan, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                    await save_simulation_run(
                        db=db,
                        user_id=user.id,
                        source_type="terraform_plan",
                        source_hash=plan_hash,
                        filename=payload.filename,
                        monthly=_model_to_dict(response_v2.monthly),
                        annual=_model_to_dict(response_v2.annual),
                        summary=_model_to_dict(response_v2.summary),
                        resources=[_model_to_dict(item) for item in response_v2.resources],
                        unestimated_resources=[
                            _model_to_dict(item) for item in response_v2.unestimated_resources
                        ],
                        findings=[_model_to_dict(item) for item in response_v2.findings],
                        policy=response_v2.policy,
                    )
                except Exception as save_error:
                    logger.warning("simulation run persistence skipped: %s", save_error)
            return response_v2

        return EstimationResponse(
            delta_monthly_cost=result["delta_monthly_cost"],
            currency=result.get("currency", "USD"),
            resources=result.get("resources", []),
            summary=result.get("summary", {}),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("estimate_terraform_cost failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to estimate Terraform plan cost.",
        ) from exc


@estimate_router.get("/estimate/history")
async def get_estimate_history(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Return recent simulator runs for the authenticated user."""
    try:
        runs = await get_simulation_history(db, user.id)
        return {"runs": runs}
    except Exception as exc:
        logger.error("get_estimate_history failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to load simulator history.",
        ) from exc
