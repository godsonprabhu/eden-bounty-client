"""Removes expired sessions and obsolete invitation/reset tokens (security remediation, finding 6).

Usage (from backend/, or the ``cleanup`` service in docker-compose.prod.yml):

    python -m app.cli.cleanup_auth            # delete
    python -m app.cli.cleanup_auth --dry-run  # count only

What is deleted
- ``admin_sessions`` and ``portal_sessions`` whose ``expires_at`` is in the past. These can never
  authenticate again (every request checks expiry), so removing them changes nothing for users.
  A session that has not expired is never selected, whatever its age or activity.
- ``portal_auth_tokens`` that can no longer be used — used, revoked or expired — and whose last
  state change is older than ``AUTH_TOKEN_RETENTION_DAYS`` (default 7). The retention window
  keeps recent rows for support questions; the audit log keeps the permanent record.

The statements use the database clock (``now()``) so application clock skew cannot widen them.
Safe to run at any time and as often as wanted; run it daily (see DEPLOYMENT_GUIDE.md).
Prints counts only: never tokens, digests or email addresses.
"""

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal

EXPIRED_SESSIONS = {
    "admin_sessions": "expires_at < now()",
    "portal_sessions": "expires_at < now()",
}
OBSOLETE_TOKENS = (
    "(used_at IS NOT NULL AND used_at < now() - make_interval(days => :days))"
    " OR (revoked_at IS NOT NULL AND revoked_at < now() - make_interval(days => :days))"
    " OR (expires_at < now() - make_interval(days => :days))"
)


async def cleanup(session: AsyncSession, *, dry_run: bool = False, retention_days: int | None = None) -> dict[str, int]:
    days = settings.AUTH_TOKEN_RETENTION_DAYS if retention_days is None else retention_days
    targets = [(table, condition, {}) for table, condition in EXPIRED_SESSIONS.items()]
    targets.append(("portal_auth_tokens", OBSOLETE_TOKENS, {"days": days}))
    counts: dict[str, int] = {}
    for table, condition, params in targets:
        verb = "SELECT count(*) FROM" if dry_run else "WITH gone AS (DELETE FROM"
        if dry_run:
            sql = f"{verb} {table} WHERE {condition}"
        else:
            sql = f"{verb} {table} WHERE {condition} RETURNING 1) SELECT count(*) FROM gone"
        counts[table] = (await session.execute(text(sql), params)).scalar_one()
    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return counts


async def _main(dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        counts = await cleanup(session, dry_run=dry_run)
    label = "Would delete" if dry_run else "Deleted"
    for table, count in counts.items():
        print(f"{label} {count} row(s) from {table}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete expired sessions and obsolete invitation/reset tokens.")
    parser.add_argument("--dry-run", action="store_true", help="Only report how many rows would be deleted")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
