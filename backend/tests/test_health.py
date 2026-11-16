"""Tests for Health Check Endpoints and Database Connectivity Reporting."""

from unittest.mock import patch

import pytest
from app.core.config import settings
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_endpoint_healthy(async_client: AsyncClient):
    """Verify root GET /health returns 200 and healthy status when DB is connected."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["database"] == "connected"
    assert "timestamp" in data
    # Ensure no credentials or URLs are exposed in health response
    assert "password" not in response.text
    assert "localhost" not in response.text
    assert "5433" not in response.text


@pytest.mark.asyncio
async def test_api_v1_health_endpoint_healthy(async_client: AsyncClient):
    """Verify GET /api/v1/health route returns identical healthy status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_degraded_when_db_down(async_client: AsyncClient):
    """Verify GET /health returns 503 and degraded status when database is unreachable."""
    with patch("app.api.v1.endpoints.health.check_database_connection", return_value=False):
        response = await async_client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"
