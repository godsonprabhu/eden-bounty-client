"""Secure CLI Provisioning Command for Initial SUPER_ADMIN Account.

Phase C13.2 — Aligned with C13-security-design.md v2.1.0:
- Explicit execution only (never executed automatically on boot).
- Interactive password prompt with hidden echo via getpass.
- Strict password policy enforcement.
- Argon2id cryptographic password hashing.
- Duplicate administrator prevention.
- No password or hash output.
- Strictly assigns the SUPER_ADMIN role.
"""

import argparse
import asyncio
import getpass
import re
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, validate_password_policy
from app.db.session import AsyncSessionLocal
from app.models.admin import AdminRole, AdminUser, AdminUserRole
from app.models.portal import PortalUser

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


async def provision_super_admin(
    session: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    job_title: str | None = None,
) -> dict[str, Any]:
    """Provisions a single SUPER_ADMIN administrator in PostgreSQL.

    Raises ValueError on validation failure, policy violation, or duplicate account.
    Never logs or reveals the password or password hash.
    """
    normalized_email = email.strip().lower()

    if not EMAIL_REGEX.match(normalized_email):
        raise ValueError(f"Invalid email address format: {email}")

    if not first_name.strip() or not last_name.strip():
        raise ValueError("First name and last name are required.")

    # Validate password policy
    is_valid, reason = validate_password_policy(password)
    if not is_valid:
        raise ValueError(f"Password policy violation: {reason}")

    # Check for duplicate email
    stmt = select(AdminUser).where(AdminUser.email == normalized_email)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ValueError(f"An administrator with email '{normalized_email}' already exists.")

    # One email address maps to exactly one account across administrators, customers and investors.
    portal_stmt = select(PortalUser.id).where(PortalUser.email == normalized_email)
    if (await session.execute(portal_stmt)).first():
        raise ValueError(f"A customer or investor account with email '{normalized_email}' already exists.")

    # Ensure SUPER_ADMIN role exists in master data
    role_stmt = select(AdminRole).where(AdminRole.id == "SUPER_ADMIN")
    super_role = (await session.execute(role_stmt)).scalar_one_or_none()
    if not super_role:
        raise RuntimeError(
            "The 'SUPER_ADMIN' role does not exist in admin_roles. "
            "Please run seeds before provisioning an administrator."
        )

    # Hash password with Argon2id
    hashed_pw = hash_password(password)

    # Insert user
    new_user = AdminUser(
        email=normalized_email,
        password_hash=hashed_pw,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        job_title=job_title.strip() if job_title else None,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    # Assign SUPER_ADMIN role
    role_assignment = AdminUserRole(
        admin_user_id=new_user.id,
        role_id="SUPER_ADMIN",
        assigned_by=new_user.id,
    )
    session.add(role_assignment)
    await session.commit()

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name,
        "role": "SUPER_ADMIN",
    }


def parse_args() -> argparse.Namespace:
    """Parses optional CLI arguments for scriptable / non-interactive execution."""
    parser = argparse.ArgumentParser(
        description="EDEN BOUNTY Sdn. Bhd. — Super Administrator Provisioning CLI",
    )
    parser.add_argument("--email", help="Administrator corporate email address")
    parser.add_argument("--first-name", help="Administrator first name")
    parser.add_argument("--last-name", help="Administrator last name")
    parser.add_argument("--job-title", help="Job title / commercial designation")
    parser.add_argument("--password", help="Password (optional, prompts securely if omitted)")
    return parser.parse_args()


async def main_async() -> int:
    """CLI execution entrypoint."""
    args = parse_args()

    print("=" * 65)
    print("EDEN BOUNTY Sdn. Bhd. — Super Administrator Provisioning")
    print("Entity: 202501058702 (1660108-D) | Phase C13.2 Security Standard")
    print("=" * 65)

    email = args.email or input("Corporate Email: ").strip()
    first_name = args.first_name or input("First Name: ").strip()
    last_name = args.last_name or input("Last Name: ").strip()
    job_title = args.job_title
    if job_title is None and not args.email:
        raw_job = input("Job Title [Press Enter to skip]: ").strip()
        job_title = raw_job or None

    password = args.password
    if not password:
        password = getpass.getpass("Enter secure password: ")
        confirm = getpass.getpass("Confirm secure password: ")
        if password != confirm:
            print("[ERROR] Passwords do not match. Aborting provisioning.", file=sys.stderr)
            return 1

    async with AsyncSessionLocal() as session:
        try:
            result = await provision_super_admin(
                session=session,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                job_title=job_title,
            )
            print("-" * 65)
            print("[SUCCESS] Super Administrator provisioned successfully.")
            print(f"  Administrator ID : {result['id']}")
            print(f"  Corporate Email  : {result['email']}")
            print(f"  Full Name        : {result['first_name']} {result['last_name']}")
            print(f"  Assigned Role    : {result['role']}")
            print("-" * 65)
            return 0
        except (ValueError, RuntimeError) as err:
            print(f"[ERROR] Provisioning failed: {err}", file=sys.stderr)
            return 1


def main() -> None:
    """Synchronous wrapper for CLI."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
