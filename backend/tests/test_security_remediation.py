"""Tests for the seven security-audit findings resolved in this remediation.

1. Invitation and password-reset links      4. Audit events for security-relevant actions
2. Layered sign-in throttling               5. Database-level email uniqueness (migration 0009)
3. (CSP is a frontend concern; the API's    6. Expired session / obsolete token cleanup
   download responses are covered here)     7. Investor document upload screening

Uses the shared isolated test database and the helpers/fixtures of test_portal.py.
"""

import asyncio
import json
import re
import struct
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.cli.cleanup_auth import cleanup
from app.core import login_throttle as throttle_module
from app.core.config import settings
from app.core.security import hash_session_token
from app.models.account_security import AccountEmailRegistry, PortalAuthToken
from app.models.admin import AdminSession, AdminUser
from app.models.audit import AuditLog
from app.models.portal import PortalSession, PortalUser
from app.services import password_links
from app.services.audit import UNKNOWN_ACCOUNT_ID, record_security_event
from tests.test_portal import (  # noqa: F401  (clean_portal_tables is an autouse fixture)
    ORIGIN,
    PASSWORD,
    PDF,
    accept_link,
    admin_session,
    clean_portal_tables,
    create_account,
    get,
    login_customer,
    login_investor,
    make_admin,
    patch,
    post,
    token_from,
)

NEW_PASSWORD = "Fresh-Password-2026!"
BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0009_account_security.py"


def ip(addr: str) -> dict:
    return {**ORIGIN, "X-Forwarded-For": addr}


async def main_login(client, email, password=PASSWORD, addr="192.0.2.10"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=ip(addr))


async def tokens_for(db, user_id) -> list[PortalAuthToken]:
    db.expire_all()
    return list((await db.execute(select(PortalAuthToken).where(PortalAuthToken.portal_user_id == uuid.UUID(str(user_id))))).scalars())


async def audit_rows(db, action: str | None = None) -> list[AuditLog]:
    db.expire_all()
    stmt = select(AuditLog).order_by(AuditLog.id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list((await db.execute(stmt)).scalars())


# ====================================================================== 1. invitation & reset
async def test_invitation_flow_single_use_and_hashed(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "invitee@example.com", accept=False)

    assert created["invitation_pending"] is True
    invitation = created["invitation"]
    assert invitation["purpose"] == "INVITE" and invitation["delivery"] == "MANUAL"
    assert invitation["link"].startswith(f"{settings.PUBLIC_SITE_URL}/reset-password#token=")
    ttl = datetime.fromisoformat(invitation["expires_at"]) - datetime.now(UTC)
    assert timedelta(hours=71, minutes=59) < ttl <= timedelta(hours=72)

    # Before accepting, no password works (the stored value is an unusable marker, not a hash).
    assert (await main_login(async_client, "invitee@example.com")).status_code == 401
    stored = (await db_session.execute(select(PortalUser).where(PortalUser.email == "invitee@example.com"))).scalar_one()
    assert stored.password_hash.startswith("!")

    raw = token_from(invitation["link"])
    [token] = await tokens_for(db_session, created["id"])
    assert token.token_hash == hash_session_token(raw) and raw not in token.token_hash

    status_res = await async_client.post("/api/v1/auth/password/status", json={"token": raw}, headers=ORIGIN)
    assert status_res.status_code == 200
    assert status_res.json()["data"] | {"expires_at": None} == {
        "purpose": "INVITE", "account_type": "CUSTOMER", "login_path": "/login", "expires_at": None,
    }

    done = await accept_link(async_client, invitation["link"], NEW_PASSWORD)
    assert done.status_code == 200 and done.json()["data"]["login_path"] == "/login"
    assert (await accept_link(async_client, invitation["link"], "Another-Password-2026!")).status_code == 400  # single use
    assert (await async_client.post("/api/v1/auth/password/status", json={"token": raw}, headers=ORIGIN)).status_code == 400
    assert (await main_login(async_client, "invitee@example.com", NEW_PASSWORD)).status_code == 200

    detail = (await get(async_client, f"/admin/portal-users/{created['id']}", admin)).json()["data"]
    assert detail["invitation_pending"] is False and detail["active_link"] is None
    assert [r.action for r in await audit_rows(db_session) if r.action.endswith("INVITATION_ACCEPTED")] == ["CUSTOMER_INVITATION_ACCEPTED"]


async def test_expired_invitation_is_refused(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "INVESTOR", "late@example.com", accept=False)
    [token] = await tokens_for(db_session, created["id"])
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    res = await accept_link(async_client, created["invitation"]["link"], NEW_PASSWORD)
    assert res.status_code == 400 and "expired" in res.json()["detail"]
    assert (await async_client.post("/api/v1/investor/login", json={"email": "late@example.com", "password": NEW_PASSWORD}, headers=ORIGIN)).status_code == 401


async def test_new_link_invalidates_previous_links(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "INVESTOR", "twice@example.com", accept=False)
    resent = await post(async_client, f"/admin/portal-users/{created['id']}/password-link", admin)
    assert resent.status_code == 200 and resent.json()["data"]["purpose"] == "INVITE"
    assert resent.headers["cache-control"] == "no-store"

    assert (await accept_link(async_client, created["invitation"]["link"], NEW_PASSWORD)).status_code == 400
    done = await accept_link(async_client, resent.json()["data"]["link"], NEW_PASSWORD)
    assert done.status_code == 200 and done.json()["data"]["login_path"] == "/investors/login"
    tokens = await tokens_for(db_session, created["id"])
    assert sorted((t.used_at is not None, t.revoked_at is not None) for t in tokens) == [(False, True), (True, False)]


async def test_reset_link_has_short_expiry_revokes_sessions_and_clears_lock(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "reset@example.com")
    s1 = await login_customer(async_client, "reset@example.com")
    s2 = await login_customer(async_client, "reset@example.com")
    user = (await db_session.execute(select(PortalUser).where(PortalUser.email == "reset@example.com"))).scalar_one()
    user.failed_login_attempts, user.locked_until = 25, datetime.now(UTC) + timedelta(minutes=10)
    await db_session.commit()

    link = (await post(async_client, f"/admin/portal-users/{created['id']}/password-link", admin)).json()["data"]
    assert link["purpose"] == "RESET"
    ttl = datetime.fromisoformat(link["expires_at"]) - datetime.now(UTC)
    assert timedelta(minutes=29) < ttl <= timedelta(minutes=30)

    assert (await accept_link(async_client, link["link"], NEW_PASSWORD)).status_code == 200
    for session in (s1, s2):
        assert (await get(async_client, "/customer/me", session)).status_code == 401
    assert (await db_session.execute(select(func.count()).select_from(PortalSession))).scalar_one() == 0
    await db_session.refresh(user)
    assert (user.failed_login_attempts, user.locked_until) == (0, None)
    assert (await main_login(async_client, "reset@example.com", PASSWORD)).status_code == 401
    assert (await main_login(async_client, "reset@example.com", NEW_PASSWORD)).status_code == 200


async def test_reset_link_enforces_password_policy(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "policy@example.com", accept=False)
    weak = await accept_link(async_client, created["invitation"]["link"], "short")
    assert weak.status_code == 422
    assert (await accept_link(async_client, created["invitation"]["link"], NEW_PASSWORD)).status_code == 200


async def test_deactivation_and_password_change_revoke_outstanding_links(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    a = await create_account(async_client, admin, "CUSTOMER", "deact@example.com", accept=False)
    await patch(async_client, f"/admin/portal-users/{a['id']}", admin, json={"is_active": False})
    assert (await accept_link(async_client, a["invitation"]["link"], NEW_PASSWORD)).status_code == 400
    assert (await post(async_client, f"/admin/portal-users/{a['id']}/password-link", admin)).status_code == 400

    b = await create_account(async_client, admin, "CUSTOMER", "change@example.com")
    link = (await post(async_client, f"/admin/portal-users/{b['id']}/password-link", admin)).json()["data"]["link"]
    session = await login_customer(async_client, "change@example.com")
    changed = await post(async_client, "/customer/password", session, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert changed.status_code == 200
    assert (await accept_link(async_client, link, "Hijack-Password-2026!")).status_code == 400


async def test_admins_never_choose_or_see_portal_passwords(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "private@example.com")
    old_endpoint = await post(async_client, f"/admin/portal-users/{created['id']}/reset-password", admin, json={"new_password": NEW_PASSWORD})
    assert old_endpoint.status_code in (404, 405)

    await post(async_client, f"/admin/portal-users/{created['id']}/password-link", admin)
    detail = await get(async_client, f"/admin/portal-users/{created['id']}", admin)
    body = detail.json()["data"]
    assert body["active_link"]["purpose"] == "RESET"
    assert "token" not in detail.text and "#token=" not in detail.text and "argon2" not in detail.text
    assert "password_hash" not in detail.text


@pytest.mark.parametrize("delivery", ["MANUAL", "EMAIL"])
async def test_forgot_password_is_generic_and_rate_limited(db_session, async_client, monkeypatch, delivery):
    sent: list[tuple[str, str]] = []
    admin = await admin_session(db_session, async_client)
    await make_admin(db_session, "staff@edenbounty.org")
    created = await create_account(async_client, admin, "CUSTOMER", "forgot@example.com")
    inactive = await create_account(async_client, admin, "CUSTOMER", "gone@example.com")
    await patch(async_client, f"/admin/portal-users/{inactive['id']}", admin, json={"is_active": False})

    if delivery == "EMAIL":
        monkeypatch.setattr(password_links, "email_delivery_available", lambda: True)

        async def fake_send(to, subject, body):
            sent.append((to, body))
            return True

        monkeypatch.setattr(password_links, "send_email", fake_send)

    answers = set()
    for email in ["forgot@example.com", "nobody@example.com", "staff@edenbounty.org", "gone@example.com", "FORGOT@example.com"]:
        res = await async_client.post("/api/v1/auth/password/forgot", json={"email": email}, headers=ORIGIN)
        assert res.status_code == 202
        answers.add(res.text)
    assert len(answers) == 1  # identical for every address

    reset_tokens = [t.revoked_at is None for t in await tokens_for(db_session, created["id"]) if t.purpose == "RESET"]
    requested = await audit_rows(db_session, "CUSTOMER_PASSWORD_RESET_REQUESTED")
    assert len(requested) == 2 and all(str(r.entity_id) == created["id"] for r in requested)
    if delivery == "MANUAL":
        assert reset_tokens == [] and sent == []  # nothing usable is created without a delivery channel
        detail = (await get(async_client, f"/admin/portal-users/{created['id']}", admin)).json()["data"]
        assert detail["reset_requested_at"] is not None
    else:
        assert sorted(reset_tokens) == [False, True]  # the second request revoked the first link
        assert [to for to, _ in sent] == ["forgot@example.com", "forgot@example.com"]
        latest = re.search(r"#token=(\S+)", sent[-1][1]).group(1)
        assert (await async_client.post("/api/v1/auth/password/reset", json={"token": latest, "new_password": NEW_PASSWORD}, headers=ORIGIN)).status_code == 200

    # Per-address allowance: further requests for the same email do nothing, silently.
    for _ in range(settings.PASSWORD_RESET_REQUESTS_PER_HOUR):
        assert (await async_client.post("/api/v1/auth/password/forgot", json={"email": "forgot@example.com"}, headers=ORIGIN)).status_code == 202
    assert len(await audit_rows(db_session, "CUSTOMER_PASSWORD_RESET_REQUESTED")) == settings.PASSWORD_RESET_REQUESTS_PER_HOUR

    # Per-client allowance -> 429.
    monkeypatch.setattr(settings, "PASSWORD_RESET_REQUESTS_PER_IP_HOUR", 2)
    await throttle_module.password_reset_throttle.reset()
    codes = [(await async_client.post("/api/v1/auth/password/forgot", json={"email": f"x{i}@example.com"}, headers=ip("192.0.2.99"))).status_code for i in range(3)]
    assert codes == [202, 202, 429]


async def test_invalid_tokens_are_throttled(db_session, async_client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_FAILURE_LIMIT_PER_IP", 3)
    codes = [
        (await async_client.post("/api/v1/auth/password/reset", json={"token": "x" * 43, "new_password": NEW_PASSWORD}, headers=ip("192.0.2.77"))).status_code
        for _ in range(4)
    ]
    assert codes == [400, 400, 400, 429]


# ====================================================================== 2. throttling
async def test_one_attacker_cannot_lock_out_the_account_holder(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "INVESTOR", "victim@example.com")
    attacker = ip("203.0.113.66")
    for _ in range(settings.LOGIN_FAILURE_LIMIT_PER_IP - 1):
        await async_client.post("/api/v1/investor/login", json={"email": "victim@example.com", "password": "Guess-Password-1!"}, headers=attacker)
    user = (await db_session.execute(select(PortalUser).where(PortalUser.email == "victim@example.com"))).scalar_one()
    await db_session.refresh(user)
    # Only the first five reached password verification; the rest were refused before it.
    assert user.failed_login_attempts == settings.LOCKOUT_MAX_ATTEMPTS and user.locked_until is None
    ok = await async_client.post("/api/v1/investor/login", json={"email": "victim@example.com", "password": PASSWORD}, headers=ip("198.51.100.30"))
    assert ok.status_code == 200


async def test_distributed_guessing_still_locks_the_account(db_session, async_client, monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 8)
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "target@example.com")
    for n in range(8):
        res = await main_login(async_client, "target@example.com", "Guess-Password-1!", addr=f"203.0.113.{n + 1}")
        assert res.status_code == 401
    locked = await main_login(async_client, "target@example.com", PASSWORD, addr="198.51.100.40")
    assert locked.status_code == 401 and locked.json()["detail"] == "Invalid email or password"
    user = (await db_session.execute(select(PortalUser).where(PortalUser.email == "target@example.com"))).scalar_one()
    await db_session.refresh(user)
    assert user.locked_until is not None and user.locked_until > datetime.now(UTC)


async def test_admin_login_has_per_ip_spray_limit(db_session, async_client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_FAILURE_LIMIT_PER_IP", 4)
    for i in range(4):
        await make_admin(db_session, f"staff{i}@edenbounty.org")
        assert (await main_login(async_client, f"staff{i}@edenbounty.org", "Wrong-Password-1!", addr="203.0.113.200")).status_code == 401
    assert (await main_login(async_client, "staff0@edenbounty.org", PASSWORD, addr="203.0.113.200")).status_code == 429
    assert (await main_login(async_client, "staff0@edenbounty.org", PASSWORD, addr="198.51.100.50")).status_code == 200


async def test_shared_office_address_is_not_blocked_by_normal_use(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    office = "192.0.2.150"
    for i in range(12):
        await create_account(async_client, admin, "CUSTOMER", f"colleague{i}@example.com")
    for i in range(12):
        # Each colleague mistypes once, then signs in. 12 failures stay below the per-address cap.
        assert (await main_login(async_client, f"colleague{i}@example.com", "Typo-Password-1!", addr=office)).status_code == 401
        assert (await main_login(async_client, f"colleague{i}@example.com", PASSWORD, addr=office)).status_code == 200


async def test_success_clears_per_account_counter(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "typo@example.com")
    for _ in range(settings.LOCKOUT_MAX_ATTEMPTS - 1):
        await main_login(async_client, "typo@example.com", "Typo-Password-1!")
    assert (await main_login(async_client, "typo@example.com")).status_code == 200
    for _ in range(settings.LOCKOUT_MAX_ATTEMPTS - 1):
        await main_login(async_client, "typo@example.com", "Typo-Password-1!")
    assert (await main_login(async_client, "typo@example.com")).status_code == 200


def test_throttle_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(throttle_module, "_MAX_KEYS", 10)
    counter = throttle_module.SlidingWindowCounter()
    for i in range(50):
        counter.add(f"k{i}", now=1000.0 + i, window=900)
    assert len(counter) <= 10
    counter.sweep(now=10_000.0, window=900)  # everything expired
    assert len(counter) == 0


# ====================================================================== 4. audit events
async def test_sign_in_failures_are_audited_without_secrets(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "audited@example.com")
    secret = "Secret-Guess-2026!"
    await main_login(async_client, "audited@example.com", secret)
    await main_login(async_client, "nobody-here@example.com", secret)
    await async_client.post("/api/v1/investor/login", json={"email": "audited@example.com", "password": secret}, headers=ORIGIN)
    staff_id = str((await make_admin(db_session, "audit-staff@edenbounty.org")).id)
    await main_login(async_client, "audit-staff@edenbounty.org", secret)

    rows = await audit_rows(db_session, "SIGN_IN_FAILED")
    summary = [(r.entity_table, str(r.entity_id), r.actor_email, r.new_state["portal"], r.new_state["reason"]) for r in rows]
    assert summary == [
        ("portal_users", created["id"], "audited@example.com", "main", "bad_password"),
        ("unknown_account", str(UNKNOWN_ACCOUNT_ID), None, "main", "unknown_account"),
        ("portal_users", created["id"], "audited@example.com", "investor", "wrong_portal"),
        ("admin_users", staff_id, "audit-staff@edenbounty.org", "main", "bad_password"),
    ]
    assert all(r.ip_address for r in rows)
    everything = json.dumps([[r.action, r.actor_email, r.old_state, r.new_state] for r in await audit_rows(db_session)])
    assert secret not in everything and "nobody-here" not in everything and "$argon2" not in everything


async def test_logout_password_and_profile_changes_are_audited(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    cust = await create_account(async_client, admin, "CUSTOMER", "events@example.com", company_name="Old Co")
    inv = await create_account(async_client, admin, "INVESTOR", "inv-events@example.com")
    c = await login_customer(async_client, "events@example.com")
    i = await login_investor(async_client, "inv-events@example.com")

    assert (await patch(async_client, "/customer/profile", c, json={"company_name": "New Co", "country": "Malaysia"})).status_code == 200
    assert (await patch(async_client, "/customer/profile", c, json={"company_name": "New Co"})).status_code == 200  # no change
    assert (await post(async_client, "/customer/password", c, json={"current_password": "Wrong-Current-1!", "new_password": NEW_PASSWORD})).status_code == 400
    assert (await post(async_client, "/customer/password", c, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})).status_code == 200
    assert (await post(async_client, "/investor/password", i, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})).status_code == 200
    assert (await post(async_client, "/customer/logout", c)).status_code == 200
    assert (await post(async_client, "/investor/logout", i)).status_code == 200
    assert (await post(async_client, "/auth/logout", admin)).status_code == 200

    rows = await audit_rows(db_session)
    by_action = {r.action: r for r in rows}
    profile = [r for r in rows if r.action == "CUSTOMER_PROFILE_UPDATED"]
    assert len(profile) == 1
    assert profile[0].old_state == {"company_name": "Old Co", "country": None}
    assert profile[0].new_state == {"company_name": "New Co", "country": "Malaysia"}
    assert by_action["CUSTOMER_PASSWORD_CHANGE_FAILED"].new_state == {"reason": "bad_current_password"}
    assert str(by_action["CUSTOMER_PASSWORD_CHANGED"].entity_id) == cust["id"]
    assert str(by_action["INVESTOR_PASSWORD_CHANGED"].entity_id) == inv["id"]
    assert by_action["PORTAL_LOGOUT_CUSTOMER"].actor_email == "events@example.com"
    assert by_action["PORTAL_LOGOUT_INVESTOR"].actor_email == "inv-events@example.com"
    assert by_action["ADMIN_LOGOUT"].actor_admin_id is not None
    dump = json.dumps([[r.old_state, r.new_state] for r in rows])
    assert PASSWORD not in dump and NEW_PASSWORD not in dump and c.token not in dump and i.token not in dump


def test_audit_helper_refuses_secret_fields():
    for bad in ({"password": "x"}, {"token": "x"}, {"password_hash": "x"}, {"csrf_token": "x"}):
        with pytest.raises(ValueError):
            record_security_event(None, "X", "t", UNKNOWN_ACCOUNT_ID, new_state=bad)  # type: ignore[arg-type]


# ====================================================================== 5. email uniqueness (DB)
async def test_database_rejects_same_email_across_account_tables(db_session):
    db_session.add(AdminUser(email="shared@example.com", password_hash="x", first_name="A", last_name="B"))
    await db_session.commit()
    db_session.add(PortalUser(email="shared@example.com", password_hash="x", role="CUSTOMER", full_name="C"))
    with pytest.raises(IntegrityError, match="account_email_registry_pkey"):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(PortalUser(email="Mixed@Example.com", password_hash="x", role="CUSTOMER", full_name="C"))
    with pytest.raises(IntegrityError, match="ck_portal_users_email_normalized"):
        await db_session.commit()
    await db_session.rollback()

    admin = (await db_session.execute(select(AdminUser).where(AdminUser.email == "shared@example.com"))).scalar_one()
    await db_session.delete(admin)
    await db_session.commit()
    db_session.add(PortalUser(email="shared@example.com", password_hash="x", role="INVESTOR", full_name="C"))
    await db_session.commit()  # freed by the delete
    registry = (await db_session.execute(select(AccountEmailRegistry).where(AccountEmailRegistry.email_normalized == "shared@example.com"))).scalar_one()
    assert registry.account_table == "portal_users"


async def test_registry_follows_email_changes(db_session):
    user = PortalUser(email="before@example.com", password_hash="x", role="CUSTOMER", full_name="C")
    db_session.add(user)
    await db_session.commit()
    user.email = "after@example.com"
    await db_session.commit()
    emails = set((await db_session.execute(select(AccountEmailRegistry.email_normalized))).scalars())
    assert "after@example.com" in emails and "before@example.com" not in emails


async def test_migration_preflight_refuses_conflicting_data(test_engine):
    """Runs 0009's preflight against planted conflicts inside a transaction that is rolled back."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig0009", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(text("ALTER TABLE admin_users DROP CONSTRAINT ck_admin_users_email_normalized"))
            await conn.execute(text("ALTER TABLE admin_users DISABLE TRIGGER trg_admin_users_email_registry"))
            await conn.execute(text("ALTER TABLE portal_users DISABLE TRIGGER trg_portal_users_email_registry"))
            await conn.execute(text("INSERT INTO admin_users (id, email, password_hash, first_name, last_name, is_active, failed_login_attempts) VALUES (gen_random_uuid(), 'Clash@Example.com', 'x', 'a', 'b', true, 0)"))
            await conn.execute(text("INSERT INTO portal_users (id, email, password_hash, role, full_name, is_active, failed_login_attempts) VALUES (gen_random_uuid(), 'clash@example.com', 'x', 'CUSTOMER', 'c', true, 0)"))
            with pytest.raises(module.ExistingDataConflict) as exc:
                await conn.run_sync(module._preflight)
            message = str(exc.value)
            assert "1 admin_users row(s) with a non-normalised email" in message
            assert "1 email address(es) used by more than one account" in message
            assert "clash" not in message.lower()  # no addresses are printed
        finally:
            await trans.rollback()


def test_migration_0009_is_additive_and_reversible():
    source = MIGRATION.read_text()
    upgrade = source[source.index("def upgrade()"): source.index("def downgrade()")]
    downgrade = source[source.index("def downgrade()"):]
    assert not re.search(r"op\.(drop_|alter_column|rename_table)", upgrade)
    assert not re.search(r"\b(DROP|ALTER COLUMN|UPDATE admin_users|UPDATE portal_users|DELETE FROM (admin|portal)_users)\b", upgrade)
    assert set(re.findall(r'op\.create_table\(\s*"(\w+)"', upgrade)) == {"portal_auth_tokens", "account_email_registry"}
    assert set(re.findall(r'op\.drop_table\("(\w+)"\)', downgrade)) == {"portal_auth_tokens", "account_email_registry"}
    assert "drop_column" not in downgrade


# ====================================================================== 6. cleanup
async def test_cleanup_removes_only_expired_sessions_and_obsolete_tokens(db_session, async_client):
    admin_s = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin_s, "CUSTOMER", "cleanup@example.com")
    await login_customer(async_client, "cleanup@example.com")  # active portal session
    user_id = uuid.UUID(created["id"])
    admin_row = (await db_session.execute(select(AdminUser))).scalars().first()
    now = datetime.now(UTC)
    old = now - timedelta(days=settings.AUTH_TOKEN_RETENTION_DAYS + 1)

    db_session.add_all([
        PortalSession(id="e" * 64, portal_user_id=user_id, role="CUSTOMER", csrf_token="c", expires_at=now - timedelta(seconds=5)),
        AdminSession(id="f" * 64, admin_user_id=admin_row.id, csrf_token="c", expires_at=now - timedelta(hours=1)),
        PortalAuthToken(portal_user_id=user_id, purpose="RESET", token_hash="1" * 64, expires_at=old, used_at=old),
        PortalAuthToken(portal_user_id=user_id, purpose="RESET", token_hash="2" * 64, expires_at=now + timedelta(minutes=5), revoked_at=old),
        PortalAuthToken(portal_user_id=user_id, purpose="INVITE", token_hash="3" * 64, expires_at=old),
        # kept: recently used, recently expired, still valid
        PortalAuthToken(portal_user_id=user_id, purpose="RESET", token_hash="4" * 64, expires_at=now - timedelta(minutes=1), used_at=now - timedelta(minutes=2)),
        PortalAuthToken(portal_user_id=user_id, purpose="RESET", token_hash="5" * 64, expires_at=now - timedelta(hours=1)),
        PortalAuthToken(portal_user_id=user_id, purpose="RESET", token_hash="6" * 64, expires_at=now + timedelta(minutes=20)),
    ])
    await db_session.commit()

    counts_before = {
        "admin_sessions": (await db_session.execute(select(func.count()).select_from(AdminSession))).scalar_one(),
        "portal_sessions": (await db_session.execute(select(func.count()).select_from(PortalSession))).scalar_one(),
    }
    preview = await cleanup(db_session, dry_run=True)
    assert preview == {"admin_sessions": 1, "portal_sessions": 1, "portal_auth_tokens": 3}
    assert (await db_session.execute(select(func.count()).select_from(PortalAuthToken))).scalar_one() >= 6  # dry run deleted nothing

    assert await cleanup(db_session) == preview
    db_session.expire_all()
    assert (await db_session.execute(select(func.count()).select_from(AdminSession))).scalar_one() == counts_before["admin_sessions"] - 1
    assert (await db_session.execute(select(func.count()).select_from(PortalSession))).scalar_one() == counts_before["portal_sessions"] - 1
    remaining = set((await db_session.execute(select(PortalAuthToken.token_hash))).scalars())
    assert {"4" * 64, "5" * 64, "6" * 64} <= remaining and not ({"1" * 64, "2" * 64, "3" * 64} & remaining)
    # Every session that has not expired is still there and still works.
    assert (await db_session.execute(select(func.count()).select_from(PortalSession).where(PortalSession.expires_at <= func.now()))).scalar_one() == 0
    assert (await get(async_client, "/auth/me", admin_s)).status_code == 200
    assert await cleanup(db_session) == {"admin_sessions": 0, "portal_sessions": 0, "portal_auth_tokens": 0}


# ====================================================================== 7. investor documents
def _pdf(body: bytes = b"") -> bytes:
    return b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog " + body + b" >>\nendobj\ntrailer\n<<>>\n%%EOF\n"


async def _upload(client, admin, investor_id, content: bytes):
    return await post(client, f"/admin/investors/{investor_id}/documents?title=Report&filename=r.pdf", admin, content=content)


@pytest.mark.parametrize(
    "content, status",
    [
        (_pdf(), 201),
        (_pdf(b"/OpenAction 3 0 R /PageMode /UseOutlines"), 201),  # common, harmless
        (_pdf(b"/OpenAction << /S /JavaScript /JS (app.alert(1)) >>"), 422),
        (_pdf(b"/OpenAction << /S /J#61vaScript >>"), 422),  # hex-escaped name
        (_pdf(b"/Names << /EmbeddedFiles 4 0 R >>"), 422),
        (_pdf(b"/AA << /O << /S /Launch /F (cmd.exe) >> >>"), 422),
        (b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n", 422),  # truncated: no %%EOF
    ],
)
async def test_active_or_damaged_pdfs_are_refused_and_not_kept(db_session, async_client, content, status):
    admin = await admin_session(db_session, async_client)
    investor = await create_account(async_client, admin, "INVESTOR", "docs@example.com")
    res = await _upload(async_client, admin, investor["id"], content)
    assert res.status_code == status, res.text
    stored = list(Path(settings.PRIVATE_STORAGE_DIR).glob("*"))
    assert len(stored) == (1 if status == 201 else 0)


async def _fake_clamd(reply: bytes):
    received = bytearray()

    async def handle(reader, writer):
        assert await reader.readuntil(b"\0") == b"zINSTREAM\0"
        while True:
            (size,) = struct.unpack(">I", await reader.readexactly(4))
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(reply)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], received


@pytest.mark.parametrize(
    "reply, expected",
    [(b"stream: OK\0", 201), (b"stream: Eicar-Test-Signature FOUND\0", 422), (None, 503)],
)
async def test_clamav_scanning_fails_closed(db_session, async_client, monkeypatch, reply, expected):
    admin = await admin_session(db_session, async_client)
    investor = await create_account(async_client, admin, "INVESTOR", "scan@example.com")
    monkeypatch.setattr(settings, "DOCUMENT_SCAN_MODE", "clamav")
    monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "CLAMAV_TIMEOUT_SECONDS", 5.0)
    server = None
    if reply is None:
        probe = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = probe.sockets[0].getsockname()[1]
        probe.close()
        await probe.wait_closed()  # nothing listens here any more
    else:
        server, port, received = await _fake_clamd(reply)
    monkeypatch.setattr(settings, "CLAMAV_PORT", port)
    try:
        res = await _upload(async_client, admin, investor["id"], PDF)
    finally:
        if server:
            server.close()
            await server.wait_closed()
    assert res.status_code == expected, res.text
    if server:
        assert bytes(received) == PDF
    assert len(list(Path(settings.PRIVATE_STORAGE_DIR).glob("*"))) == (1 if expected == 201 else 0)


async def test_document_download_is_attachment_with_sandbox_csp(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    investor = await create_account(async_client, admin, "INVESTOR", "dl@example.com")
    doc = (await _upload(async_client, admin, investor["id"], PDF)).json()["data"]
    await patch(async_client, f"/admin/investor-documents/{doc['id']}", admin, json={"is_published": True})
    session = await login_investor(async_client, "dl@example.com")
    res = await get(async_client, f"/investor/documents/{doc['id']}/download", session)
    assert res.status_code == 200 and res.content == PDF
    assert res.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in res.headers["content-security-policy"] and "default-src 'none'" in res.headers["content-security-policy"]
    assert res.headers["cache-control"] == "private, no-store"
    # Isolation is unchanged: another investor cannot fetch it.
    other = await create_account(async_client, admin, "INVESTOR", "other@example.com")
    assert other
    stranger = await login_investor(async_client, "other@example.com")
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download", stranger)).status_code == 404


__all__ = ["sa"]
