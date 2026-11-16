"""Central API v1 router for EDEN BOUNTY backend."""

from app.api.v1.endpoints import admin, admin_portal, auth, health, password, portal, public
from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(password.router)
api_v1_router.include_router(public.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(admin_portal.router)
api_v1_router.include_router(portal.customer_router)
api_v1_router.include_router(portal.investor_router)
