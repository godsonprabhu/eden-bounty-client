"""Tests for SUPER_ADMIN Provisioning CLI and Administrator Account Security.

Phase C13.2 — Aligned with C13-security-design.md v2.1.0:
- Explicit execution only.
- Strict password policy enforcement.
- Duplicate administrator prevention.
- No plaintext password storage.
- Role strictly assigned as SUPER_ADMIN.
"""

import pytest
from app.cli.create_admin import provision_super_admin
from app.db.seeds import seed_roles
from app.models.admin import AdminSession, AdminUser, AdminUserRole
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def clean_and_setup_cli(db_session: AsyncSession):
    """Ensures test tables are clean and roles are seeded for every test."""
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()
    await seed_roles(db_session)
    yield
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()


@pytest.mark.asyncio
async def test_cli_provisioning_super_admin_success(db_session: AsyncSession):
    """Verifies that provision_super_admin creates a valid SUPER_ADMIN account."""
    # Ensure roles are seeded
    await seed_roles(db_session)

    test_email = "provisioned_admin_01@edenbounty.org"
    result = await provision_super_admin(
        session=db_session,
        email=test_email,
        first_name="Provisioned",
        last_name="SuperAdmin",
        password="SuperCorporatePass2026!#",
        job_title="Executive Director",
    )

    assert result["email"] == test_email
    assert result["role"] == "SUPER_ADMIN"

    # Query from database to verify persistence and no plaintext password
    stmt = select(AdminUser).where(AdminUser.email == test_email)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")
    assert "SuperCorporatePass2026!#" not in user.password_hash

    # Verify role assignment
    role_stmt = select(AdminUserRole).where(AdminUserRole.admin_user_id == user.id)
    assignments = (await db_session.execute(role_stmt)).scalars().all()
    assert len(assignments) == 1
    assert assignments[0].role_id == "SUPER_ADMIN"


@pytest.mark.asyncio
async def test_cli_provisioning_duplicate_prevention(db_session: AsyncSession):
    """Verifies that duplicate administrator provisioning is strictly refused."""
    await seed_roles(db_session)

    dup_email = "duplicate_test@edenbounty.org"
    await provision_super_admin(
        session=db_session,
        email=dup_email,
        first_name="Original",
        last_name="Admin",
        password="ValidCorporatePass123!#",
    )

    # Attempting to provision again with same email must fail
    with pytest.raises(ValueError, match="already exists"):
        await provision_super_admin(
            session=db_session,
            email=dup_email,
            first_name="Impostor",
            last_name="Admin",
            password="AnotherValidPass999!#",
        )


@pytest.mark.asyncio
async def test_cli_provisioning_password_policy_rejection(db_session: AsyncSession):
    """Verifies that weak passwords are fundamentally rejected during provisioning."""
    await seed_roles(db_session)

    with pytest.raises(ValueError, match="Password policy violation"):
        await provision_super_admin(
            session=db_session,
            email="weak_admin@edenbounty.org",
            first_name="Weak",
            last_name="Password",
            password="weak",
        )
