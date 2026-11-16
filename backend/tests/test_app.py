"""Tests for FastAPI Application Initialization and Institutional Endpoints."""

import pytest
from app.core.config import settings
from app.main import app
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_app_metadata():
    """Verify application metadata and configuration."""
    assert app.title == "EDEN BOUNTY Sdn. Bhd. — Commercial Trading Platform API"
    assert app.version == settings.APP_VERSION
    assert settings.APP_NAME == "EDEN BOUNTY Sdn. Bhd. API"


@pytest.mark.asyncio
async def test_root_institutional_info(async_client: AsyncClient):
    """Verify root institutional endpoint disclosures."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["entity"] == "EDEN BOUNTY Sdn. Bhd."
    assert data["registration_number"] == "202501058702 (1660108-D)"
    assert data["status"] == "online"
    assert data["version"] == settings.APP_VERSION
