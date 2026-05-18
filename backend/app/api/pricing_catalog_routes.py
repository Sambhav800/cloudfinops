import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import ClerkUser, get_current_user
from ..core.provider_pricing_catalog import pricing_catalog
from ..db import MongoDBClient, get_db_client
from ..security import decrypt_integration_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pricing-catalog", tags=["Pricing Catalog"])


class CatalogSyncRequest(BaseModel):
    provider: Literal["aws", "azure", "gcp"]
    integration_id: Optional[str] = None
    service_code: Optional[str] = None
    region: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=50000)


class CatalogSyncResponse(BaseModel):
    provider: str
    source: str
    service_code: Optional[str] = None
    region: Optional[str] = None
    sync_batch_id: str
    records_seen: int
    records_saved: int
    status: str
    synced_at: str
    applied_estimates: Optional[dict] = None


class ApplyCatalogEstimatesRequest(BaseModel):
    integration_id: Optional[str] = None
    limit: int = Field(default=500, ge=1, le=50000)


class CatalogEstimateSample(BaseModel):
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    monthly_cost: float
    catalog_key: str


class ApplyCatalogEstimatesResponse(BaseModel):
    updated: int
    skipped_actual: int
    unmatched: int
    processed: int
    samples: list[CatalogEstimateSample] = Field(default_factory=list)


class PricingCatalogStatusResponse(BaseModel):
    syncs: list[dict]
    count: int


@router.post("/sync", response_model=CatalogSyncResponse)
async def sync_pricing_catalog(
    request: CatalogSyncRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Sync official provider list-price catalog rows."""
    try:
        credentials = None
        if request.integration_id:
            integrations = await db.select(
                "cloud_integrations",
                filters={"id": request.integration_id, "user_id": user.id, "provider": request.provider},
            )
            if not integrations:
                raise HTTPException(status_code=404, detail="Integration not found")
            credentials = decrypt_integration_credentials(integrations[0])

        logger.info(
            "pricing_catalog_sync requested actor=%s provider=%s integration_id=%s service_code=%s region=%s limit=%s",
            user.id,
            request.provider,
            request.integration_id,
            request.service_code,
            request.region,
            request.limit,
        )
        result = await pricing_catalog.sync_provider_catalog(
            db,
            request.provider,
            service_code=request.service_code,
            region=request.region,
            limit=request.limit,
            credentials=credentials,
        )
        try:
            apply_limit = max(500, min(request.limit, 50000))
            apply_result = await pricing_catalog.apply_catalog_estimates(
                db,
                user.id,
                integration_id=request.integration_id,
                limit=apply_limit,
            )
            result = {**result, "applied_estimates": apply_result}
            logger.info(
                "pricing_catalog_sync applied estimates actor=%s provider=%s integration_id=%s updated=%s",
                user.id,
                request.provider,
                request.integration_id,
                apply_result.get("updated", 0),
            )
        except Exception as error:
            logger.warning(
                "pricing_catalog_sync estimate application skipped actor=%s provider=%s integration_id=%s: %s",
                user.id,
                request.provider,
                request.integration_id,
                error,
            )
            result = {
                **result,
                "applied_estimates": {
                    "updated": 0,
                    "skipped_actual": 0,
                    "unmatched": 0,
                    "processed": 0,
                    "samples": [],
                    "status": "skipped",
                },
            }
        return result
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.error("sync_pricing_catalog failed: %s", error)
        raise HTTPException(status_code=500, detail="Pricing catalog sync failed")


@router.post("/apply-estimates", response_model=ApplyCatalogEstimatesResponse)
async def apply_pricing_catalog_estimates(
    request: ApplyCatalogEstimatesRequest,
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Apply official catalog estimates to the current user's resources."""
    try:
        if request.integration_id:
            integrations = await db.select(
                "cloud_integrations",
                filters={"id": request.integration_id, "user_id": user.id},
            )
            if not integrations:
                raise HTTPException(status_code=404, detail="Integration not found")

        result = await pricing_catalog.apply_catalog_estimates(
            db,
            user.id,
            integration_id=request.integration_id,
            limit=request.limit,
        )
        logger.info(
            "pricing_catalog_apply_estimates actor=%s integration_id=%s updated=%s",
            user.id,
            request.integration_id,
            result.get("updated", 0),
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logger.error("apply_pricing_catalog_estimates failed: %s", error)
        raise HTTPException(status_code=500, detail="Pricing catalog estimate application failed")


@router.get("/status", response_model=PricingCatalogStatusResponse)
async def get_pricing_catalog_status(
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Return recent pricing catalog sync metadata."""
    try:
        logger.debug("pricing_catalog_status requested actor=%s", user.id)
        return await pricing_catalog.get_sync_status(db)
    except Exception as error:
        logger.error("get_pricing_catalog_status failed: %s", error)
        raise HTTPException(status_code=500, detail="Pricing catalog status unavailable")
