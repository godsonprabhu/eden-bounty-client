"""Health check endpoints for application and database connectivity."""

from datetime import UTC, datetime

from app.core.config import settings
from app.db.session import check_database_connection
from fastapi import APIRouter, Response, status
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def get_health(response: Response) -> HealthResponse:
    """Verifies application readiness and database connectivity.

    Does not expose sensitive credentials, URLs, or internal state.
    """
    db_connected = await check_database_connection()
    current_time = datetime.now(UTC).isoformat()

    if db_connected:
        return HealthResponse(
            status="healthy",
            app=settings.APP_NAME,
            version=settings.APP_VERSION,
            database="connected",
            timestamp=current_time,
        )
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            app=settings.APP_NAME,
            version=settings.APP_VERSION,
            database="disconnected",
            timestamp=current_time,
        )
