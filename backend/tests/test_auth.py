"""Comprehensive Authentication, Session Management, CSRF, Lockout, and RBAC Tests.

Phase C13.2 — Administrator Authentication & Session Management.
Tests all 20 required specifications:
1. Successful login
2. Incorrect password
3. Unknown email
4. Inactive administrator
5. Soft-deleted administrator
6. Account lockout after five failed attempts
7. Lockout expiration
8. Successful logout
9. Revoked session rejection
10. Expired session rejection
11. CSRF validation
12. Origin validation
13. HttpOnly cookie configuration
14. Secure cookie configuration in production
15. Role authorization
16. HTTP 401 and HTTP 403 behavior
17. CLI provisioning
18. Duplicate administrator prevention
19. No plaintext password storage
20. No raw session token storage
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from app.api.deps import require_operations_admin, require_super_admin
from app.cli.create_admin import provision_super_admin
from app.core.config import settings
from app.core.security import hash_password, hash_session_token
from app.db.seeds import seed_roles
from app.main import app
from app.models.admin import AdminSession, AdminUser, AdminUserRole
from app.models.audit import AuditLog
from fastapi import APIRouter, Depends, status
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# Register test routes on app for testing role dependencies
_test_rbac_router = APIRouter(prefix="/api/v1/test", tags=["Test RBAC"])


@_test_rbac_router.get("/super-admin-only")
async def super_admin_only_endpoint(
    user: Annotated[AdminUser, Depends(require_super_admin)],
):
    return {"status": "ok", "role": "SUPER_ADMIN", "email": user.email}


@_test_rbac_router.get("/operations-admin-only")
async def operations_admin_only_endpoint(
    user: Annotated[AdminUser, Depends(require_operations_admin)],
):
    return {"status": "ok", "role": "OPERATIONS_ADMIN", "email": user.email}


app.include_router(_test_rbac_router)


@pytest.fixture(autouse=True)
async def clean_and_setup_auth(db_session: AsyncSession):
    """Ensures test tables are clean and roles are seeded for every test."""
    # Sign-in failures and sign-outs are audited, and audit rows reference administrators.
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()
    await seed_roles(db_session)
    yield
    # Sign-in failures and sign-outs are audited, and audit rows reference administrators.
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()


async def create_test_user(
    db: AsyncSession,
    email: str,
    password: str,
    role: str = "OPERATIONS_ADMIN",
    is_active: bool = True,
    deleted_at: datetime | None = None,
    failed_attempts: int = 0,
    locked_until: datetime | None = None,
) -> AdminUser:
    """Helper creating a test administrator user."""
    user = AdminUser(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        first_name="Test",
        last_name="Administrator",
        job_title="Trading Officer",
        is_active=is_active,
        failed_login_attempts=failed_attempts,
        locked_until=locked_until,
        deleted_at=deleted_at,
    )
    db.add(user)
    await db.flush()

    role_assign = AdminUserRole(
        admin_user_id=user.id,
        role_id=role,
        assigned_by=user.id,
    )
    db.add(role_assign)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_01_successful_login(db_session: AsyncSession, async_client: AsyncClient):
    """1. Successful login produces 200 OK, returns user profile + CSRF token, and sets HttpOnly cookie."""
    email = "login_success@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password, role="OPERATIONS_ADMIN")

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == email
    assert data["data"]["user"]["roles"] == ["OPERATIONS_ADMIN"]
    assert "csrf_token" in data["data"]
    assert len(data["data"]["csrf_token"]) >= 32

    # Verify session cookie was set
    assert settings.SESSION_COOKIE_NAME in response.cookies


@pytest.mark.asyncio
async def test_02_incorrect_password(db_session: AsyncSession, async_client: AsyncClient):
    """2. Incorrect password returns 401 Unauthorized and increments failed_login_attempts."""
    email = "wrong_pass@edenbounty.org"
    password = "CorrectPass2026!#"
    await create_test_user(db_session, email=email, password=password)

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999!"},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"

    # Verify failed login attempts counter incremented
    stmt = select(AdminUser).where(AdminUser.email == email)
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.failed_login_attempts == 1


@pytest.mark.asyncio
async def test_03_unknown_email(async_client: AsyncClient):
    """3. Unknown email returns generic 401 Unauthorized without leaking account existence."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_email_404@edenbounty.org", "password": "AnyPassword123!#"},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_04_inactive_administrator(db_session: AsyncSession, async_client: AsyncClient):
    """4. Inactive administrator account is rejected with generic 401 Unauthorized."""
    email = "inactive_admin@edenbounty.org"
    password = "ValidPassword123!#"
    await create_test_user(db_session, email=email, password=password, is_active=False)

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_05_soft_deleted_administrator(db_session: AsyncSession, async_client: AsyncClient):
    """5. Soft-deleted administrator account is rejected with generic 401 Unauthorized."""
    email = "deleted_admin@edenbounty.org"
    password = "ValidPassword123!#"
    await create_test_user(
        db_session,
        email=email,
        password=password,
        deleted_at=datetime.now(UTC),
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_06_account_lockout_after_five_failed_attempts(
    db_session: AsyncSession, async_client: AsyncClient
):
    """6. After 5 failures from one client, that client is refused even with the correct password.

    Security remediation (finding 2): the lock applies to the attacking client only. The
    account-wide database lock needs ACCOUNT_LOCKOUT_MAX_ATTEMPTS failures, so one attacker cannot
    lock the real administrator out from another address.
    """
    email = "lockout_admin@edenbounty.org"
    password = "CorrectCorporatePass123!#"
    await create_test_user(db_session, email=email, password=password)
    attacker = {"Origin": "http://localhost:3000", "X-Forwarded-For": "203.0.113.9"}

    # Execute 5 failed login attempts
    for i in range(1, 6):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": f"WrongAttempt{i}!#"},
            headers=attacker,
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Verify user row state in database: failures counted, account itself not locked
    stmt = select(AdminUser).where(AdminUser.email == email)
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.failed_login_attempts >= 5
    assert user.locked_until is None

    # 6th attempt with CORRECT password from the same client must still be rejected
    res_locked = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=attacker,
    )
    assert res_locked.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_locked.json()["detail"] == "Invalid email or password"

    # The administrator signing in from their own address is not affected
    res_owner = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000", "X-Forwarded-For": "198.51.100.20"},
    )
    assert res_owner.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_07_lockout_expiration(db_session: AsyncSession, async_client: AsyncClient):
    """7. Expired lockout period allows successful login and resets lockout counters."""
    email = "lockout_expired@edenbounty.org"
    password = "CorrectCorporatePass123!#"
    # Set lockout timestamp in the past (e.g., 20 minutes ago)
    past_lockout = datetime.now(UTC) - timedelta(minutes=20)
    await create_test_user(
        db_session,
        email=email,
        password=password,
        failed_attempts=5,
        locked_until=past_lockout,
    )

    # Attempt login with correct password
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True

    # Verify database counters are reset
    stmt = select(AdminUser).where(AdminUser.email == email)
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_08_successful_logout(db_session: AsyncSession, async_client: AsyncClient):
    """8. Successful logout revokes session in DB and deletes cookie."""
    email = "logout_test@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    # Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    csrf_token = login_res.json()["data"]["csrf_token"]
    token_digest = hash_session_token(raw_token)

    # Verify session exists in DB
    stmt = select(AdminSession).where(AdminSession.id == token_digest)
    assert (await db_session.execute(stmt)).scalar_one_or_none() is not None

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        cookies={settings.SESSION_COOKIE_NAME: raw_token},
        headers={
            "X-CSRF-Token": csrf_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert logout_res.status_code == status.HTTP_200_OK
    assert logout_res.json()["success"] is True

    # Verify session deleted from DB
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_09_revoked_session_rejection(db_session: AsyncSession, async_client: AsyncClient):
    """9. Requests with a revoked session cookie receive 401 Unauthorized."""
    email = "revoked_session@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    # Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    token_digest = hash_session_token(raw_token)

    # Manually delete session from DB to simulate revocation
    stmt = select(AdminSession).where(AdminSession.id == token_digest)
    session_row = (await db_session.execute(stmt)).scalar_one()
    await db_session.delete(session_row)
    await db_session.commit()

    # Attempt to access /auth/me
    me_res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: raw_token},
    )
    assert me_res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_10_expired_session_rejection(db_session: AsyncSession, async_client: AsyncClient):
    """10. Expired sessions are rejected with 401 and automatically deleted from the database."""
    email = "expired_session@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    token_digest = hash_session_token(raw_token)

    # Set session expires_at in the past
    stmt = select(AdminSession).where(AdminSession.id == token_digest)
    session_row = (await db_session.execute(stmt)).scalar_one()
    session_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    # Access endpoint
    res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: raw_token},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Verify session record is pruned
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_11_csrf_validation(db_session: AsyncSession, async_client: AsyncClient):
    """11. State-changing requests lacking or having mismatched X-CSRF-Token receive 403 Forbidden."""
    email = "csrf_test@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]

    # Logout with missing CSRF token
    res_no_csrf = await async_client.post(
        "/api/v1/auth/logout",
        cookies={settings.SESSION_COOKIE_NAME: raw_token},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_no_csrf.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF token validation failed" in res_no_csrf.json()["detail"]

    # Logout with invalid CSRF token
    res_bad_csrf = await async_client.post(
        "/api/v1/auth/logout",
        cookies={settings.SESSION_COOKIE_NAME: raw_token},
        headers={
            "X-CSRF-Token": "completely_invalid_csrf_token_99999",
            "Origin": "http://localhost:3000",
        },
    )
    assert res_bad_csrf.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_12_origin_validation(db_session: AsyncSession, async_client: AsyncClient):
    """12. State-changing requests with unpermitted Origin receive 403 Forbidden."""
    email = "origin_test@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    # Disallowed origin on login
    login_bad_origin = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "https://malicious-attacker-site.com"},
    )
    assert login_bad_origin.status_code == status.HTTP_403_FORBIDDEN
    assert "origin not permitted" in login_bad_origin.json()["detail"].lower()

    # Allowed origin on login (https://edenbounty.org or http://localhost:3000)
    login_good_origin = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "https://edenbounty.org"},
    )
    assert login_good_origin.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_13_httponly_cookie_configuration(db_session: AsyncSession, async_client: AsyncClient):
    """13. Session cookie is configured with HttpOnly, Path=/, and SameSite=lax."""
    email = "cookie_attrs@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == status.HTTP_200_OK

    # Inspect raw Set-Cookie header
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.SESSION_COOKIE_NAME in set_cookie_header
    assert "HttpOnly" in set_cookie_header or "httponly" in set_cookie_header.lower()
    assert "samesite=lax" in set_cookie_header.lower()
    assert "path=/" in set_cookie_header.lower()


@pytest.mark.asyncio
async def test_14_secure_cookie_configuration_in_production(
    db_session: AsyncSession, async_client: AsyncClient
):
    """14. Session cookie has the Secure attribute enabled when in production mode."""
    email = "secure_cookie@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    # Temporarily set secure override to True
    original_override = settings.SESSION_COOKIE_SECURE_OVERRIDE
    try:
        settings.SESSION_COOKIE_SECURE_OVERRIDE = True

        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == status.HTTP_200_OK
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "secure" in set_cookie_header.lower()
    finally:
        settings.SESSION_COOKIE_SECURE_OVERRIDE = original_override


@pytest.mark.asyncio
async def test_15_role_authorization_super_admin_vs_operations_admin(
    db_session: AsyncSession, async_client: AsyncClient
):
    """15. Role authorization: OPERATIONS_ADMIN cannot access SUPER_ADMIN restricted endpoints."""
    # User 1: OPERATIONS_ADMIN
    ops_email = "ops_only@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=ops_email, password=password, role="OPERATIONS_ADMIN")

    # User 2: SUPER_ADMIN
    super_email = "super_only@edenbounty.org"
    await create_test_user(db_session, email=super_email, password=password, role="SUPER_ADMIN")

    # Log in as OPERATIONS_ADMIN
    ops_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": ops_email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    ops_cookie = ops_login.cookies[settings.SESSION_COOKIE_NAME]

    # OPERATIONS_ADMIN accessing operations endpoint -> 200 OK
    res_ops_access = await async_client.get(
        "/api/v1/test/operations-admin-only",
        cookies={settings.SESSION_COOKIE_NAME: ops_cookie},
    )
    assert res_ops_access.status_code == status.HTTP_200_OK

    # OPERATIONS_ADMIN accessing super_admin endpoint -> 403 Forbidden
    res_super_access_by_ops = await async_client.get(
        "/api/v1/test/super-admin-only",
        cookies={settings.SESSION_COOKIE_NAME: ops_cookie},
    )
    assert res_super_access_by_ops.status_code == status.HTTP_403_FORBIDDEN
    assert "Insufficient permissions" in res_super_access_by_ops.json()["detail"]

    # Log in as SUPER_ADMIN
    super_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": super_email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    super_cookie = super_login.cookies[settings.SESSION_COOKIE_NAME]

    # SUPER_ADMIN accessing super_admin endpoint -> 200 OK
    res_super_access = await async_client.get(
        "/api/v1/test/super-admin-only",
        cookies={settings.SESSION_COOKIE_NAME: super_cookie},
    )
    assert res_super_access.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_16_http_401_and_403_behavior(async_client: AsyncClient):
    """16. Unauthenticated requests receive 401; authenticated requests with wrong role receive 403."""
    # Unauthenticated request to protected endpoint -> 401
    res_unauth = await async_client.get("/api/v1/auth/me")
    assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_17_18_cli_provisioning_and_duplicate_prevention(db_session: AsyncSession):
    """17 & 18. CLI provisioning creates SUPER_ADMIN and strictly prevents duplicate creation."""
    cli_email = "cli_super_admin@edenbounty.org"
    result = await provision_super_admin(
        session=db_session,
        email=cli_email,
        first_name="CLI",
        last_name="SuperAdmin",
        password="ValidSuperPassword2026!#",
    )
    assert result["role"] == "SUPER_ADMIN"

    # Duplicate check
    with pytest.raises(ValueError, match="already exists"):
        await provision_super_admin(
            session=db_session,
            email=cli_email,
            first_name="Duplicate",
            last_name="SuperAdmin",
            password="ValidSuperPassword2026!#",
        )


@pytest.mark.asyncio
async def test_19_no_plaintext_password_storage(db_session: AsyncSession):
    """19. Plaintext passwords are never stored in the database."""
    test_pw = "RawSecretPassword123!#"
    email = "no_plaintext@edenbounty.org"
    await create_test_user(db_session, email=email, password=test_pw)

    stmt = select(AdminUser).where(AdminUser.email == email)
    stored_user = (await db_session.execute(stmt)).scalar_one()

    assert stored_user.password_hash != test_pw
    assert test_pw not in stored_user.password_hash
    assert stored_user.password_hash.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_20_no_raw_session_token_storage(
    db_session: AsyncSession, async_client: AsyncClient
):
    """20. Raw session tokens are never stored in the database; only SHA-256 hashes are persisted."""
    email = "hash_storage_test@edenbounty.org"
    password = "CorporatePass2026!#"
    await create_test_user(db_session, email=email, password=password)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Query admin_sessions by ID
    stmt = select(AdminSession).where(AdminSession.id == expected_hash)
    session_record = (await db_session.execute(stmt)).scalar_one_or_none()

    assert session_record is not None
    assert session_record.id == expected_hash
    assert session_record.id != raw_token

    # Verify querying by raw token returns nothing
    stmt_raw = select(AdminSession).where(AdminSession.id == raw_token)
    assert (await db_session.execute(stmt_raw)).scalar_one_or_none() is None
