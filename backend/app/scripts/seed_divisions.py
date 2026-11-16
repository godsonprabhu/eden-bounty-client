"""CLI script to seed divisions and administrative roles into PostgreSQL."""

import asyncio
import logging
import sys

from app.db.seeds import seed_all
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_divisions")


async def main() -> None:
    logger.info("Connecting to database and running seed operation...")
    async with AsyncSessionLocal() as session:
        try:
            results = await seed_all(session)
            logger.info("Seed completed successfully: %s", results)
        except Exception as exc:  # noqa: BLE001
            logger.error("Seed operation failed: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
