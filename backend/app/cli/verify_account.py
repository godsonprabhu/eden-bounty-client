"""Administrative CLI tool for verifying portal customer and investor accounts.

Usage:
    # Directly verify an account's email address:
    python -m app.cli.verify_account --email customer@example.com

    # Generate and display a single-use verification link:
    python -m app.cli.verify_account --email customer@example.com --show-link

Security:
    - Runs only with local database access.
    - Never prints passwords, hashes, or unrelated tokens.
    - Revokes outstanding verification tokens upon direct verification.
"""

import argparse
import asyncio
import re
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.account_security import TOKEN_PURPOSE_VERIFY
from app.models.portal import PortalUser
from app.services.audit import record_security_event
from app.services.password_links import (
    build_verify_link,
    issue_link,
    revoke_outstanding_tokens,
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


async def verify_account_cli(
    session: AsyncSession,
    email: str,
    *,
    show_link: bool = False,
) -> int:
    normalized = email.strip().lower()
    if not EMAIL_REGEX.match(normalized):
        print(f"Error: Invalid email format '{email}'", file=sys.stderr)
        return 1

    stmt = select(PortalUser).where(PortalUser.email == normalized)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        print(f"Error: No portal account found for email '{normalized}'", file=sys.stderr)
        return 1

    if not user.is_active:
        print(f"Error: Account for '{normalized}' is inactive. Activate it first.", file=sys.stderr)
        return 1

    if show_link:
        # Generate single-use verification token and show the complete link
        issued = await issue_link(session, user, TOKEN_PURPOSE_VERIFY)
        link = build_verify_link(issued.raw_token)
        await session.commit()
        print(f"Verification link generated for {normalized} (role: {user.role}):")
        print(link)
        print(f"Token expires at: {issued.expires_at.isoformat()}")
        return 0

    if user.email_verified_at is not None:
        print(f"Notice: Account '{normalized}' is already verified (at {user.email_verified_at.isoformat()}).")
        return 0

    now = datetime.now(UTC)
    user.email_verified_at = now
    await revoke_outstanding_tokens(session, user, now)
    record_security_event(
        session,
        f"{user.role}_EMAIL_CLI_VERIFIED",
        "portal_users",
        user.id,
        actor_email="cli@edenbounty.internal",
        new_state={"email_verified": True, "via": "cli"},
    )
    await session.commit()
    print(f"Success: Account '{normalized}' ({user.role}) email verified at {now.isoformat()}.")
    return 0


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify portal customer and investor accounts administratively."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address of the portal account to verify.",
    )
    parser.add_argument(
        "--show-link",
        action="store_true",
        default=False,
        help="Generate and print a single-use verification link instead of directly verifying in database.",
    )

    args = parser.parse_args(argv)

    async with AsyncSessionLocal() as session:
        return await verify_account_cli(session, args.email, show_link=args.show_link)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
