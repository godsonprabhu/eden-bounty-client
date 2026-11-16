"""Expire one synthetic portal user's sessions in the isolated E2E database."""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models.portal import PortalSession, PortalUser


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit("Refusing to expire sessions outside loopback E2E database.")
    if "/eb_playwright_test_" not in url:
        raise SystemExit("Refusing to expire sessions outside eb_playwright_test database.")
    if len(sys.argv) != 2 or "@example.com" not in sys.argv[1]:
        raise SystemExit("Expected one synthetic example.com account email.")
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(PortalSession)
            .where(PortalSession.portal_user_id.in_(select(PortalUser.id).where(PortalUser.email == sys.argv[1])))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()


asyncio.run(main())
