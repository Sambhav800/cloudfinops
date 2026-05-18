from fastapi import APIRouter

from .dashboard_read_routes import router as dashboard_read_router
from .integration_mutation_routes import router as integration_mutation_router
from .pricing_catalog_routes import router as pricing_catalog_router
from .routes import router as core_router
from .websocket import websocket_endpoint

router = APIRouter()
router.include_router(core_router)
router.include_router(dashboard_read_router)
router.include_router(integration_mutation_router)
router.include_router(pricing_catalog_router)

__all__ = ["router", "websocket_endpoint"]
