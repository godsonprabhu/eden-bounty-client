"""FastAPI Application Entry Point for EDEN BOUNTY Sdn. Bhd.

Phase C13.1 — Backend Foundation & Database Setup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import HealthResponse, get_health
from app.api.v1.router import api_v1_router
from app.core.config import settings, validate_proxy_configuration
from app.core.payload_limit import PayloadSizeLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce single-worker runtime for in-memory sliding-window rate limiting
    if settings.WORKERS > 1:
        raise RuntimeError(
            "Fatal configuration error: In-memory rate limiting requires a single worker process (WORKERS=1). "
            "Running multiple workers causes split-brain rate limits. Configure Redis or edge rate limiting before scaling workers."
        )

    # Startup validation of proxy configurations (Phase C13.3 hardening)
    validate_proxy_configuration(settings.TRUSTED_PROXIES, "TRUSTED_PROXIES")
    validate_proxy_configuration(settings.TRUSTED_CLOUDFLARE_PROXIES, "TRUSTED_CLOUDFLARE_PROXIES")
    yield


app = FastAPI(
    title="EDEN BOUNTY Sdn. Bhd. — Commercial Trading Platform API",
    description="Centralized Global Enquiry Management Backend for EDEN BOUNTY Sdn. Bhd.",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Payload Size Limit Middleware (enforces 64 KB limit before body parsing)
app.add_middleware(PayloadSizeLimitMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Root-level health check endpoint (as specified: GET /health)
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def root_health(response: Response) -> HealthResponse:
    """Root health check endpoint."""
    return await get_health(response)


# Institutional root endpoint
@app.get("/", tags=["Institutional"])
async def root_info() -> dict:
    """Institutional system identification."""
    return {
        "entity": "EDEN BOUNTY Sdn. Bhd.",
        "registration_number": "202501058702 (1660108-D)",
        "service": "Centralized Global Enquiry Management API",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "online",
    }


# Include API v1 router
app.include_router(api_v1_router)
