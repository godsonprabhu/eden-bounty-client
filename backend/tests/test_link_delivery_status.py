"""Regression tests: accurate invitation/reset email delivery status (pre-staging fix 1).

- Administrator-issued links report SENT only after the SMTP server accepted the message, and
  FAILED otherwise; a failed link is revoked immediately and can be reissued.
- Forgot-password stays generic: identical response whatever happens to the email; the outcome
  is audited and visible to administrators.
- Raw tokens never appear in API responses (EMAIL mode), audit rows or logs.
"""

import json
import logging
import re
import socket

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.account_security import PortalAuthToken
from app.models.audit import AuditLog
from app.services import password_links
from tests.test_portal import (  # noqa: F401  (clean_portal_tables is an autouse fixture)
    ORIGIN,
    PASSWORD,
    admin_session,
    clean_portal_tables,
    create_account,
    get,
    post,
)

NEW_PASSWORD = "Delivered-Pass-2026!"


class FakeSmtp:
    """Stands in for mailer.send_email. ``ok`` decides whether the server 'accepts' the message."""

    def __init__(self):
        self.ok = True
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, to, subject, body):
        self.sent.append((to, body))
        return self.ok

    def last_token(self) -> str:
        return re.search(r"#token=([A-Za-z0-9_-]+)", self.sent[-1][1]).group(1)


@pytest.fixture
def smtp(monkeypatch):
    fake = FakeSmtp()
    monkeypatch.setattr(password_links, "email_delivery_available", lambda: True)
    monkeypatch.setattr(password_links, "send_email", fake)
    return fake


async def redeem(client, token, password=NEW_PASSWORD):
    return await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": password}, headers=ORIGIN)


async def audit(db, suffix):
    db.expire_all()
    return [r for r in (await db.execute(select(AuditLog).order_by(AuditLog.id))).scalars() if r.action.endswith(suffix)]


async def new_customer(client, admin, email):
    res = await client.post(
        "/api/v1/admin/portal-users", json={"role": "CUSTOMER", "email": email, "full_name": "Mail Test"},
        cookies=admin.cookies, headers=admin.headers,
    )
    assert res.status_code == 201, res.text
    return res


async def test_invitation_reported_sent_only_after_acceptance(db_session, async_client, smtp):
    admin = await admin_session(db_session, async_client)
    res = await new_customer(async_client, admin, "sent@example.com")
    inv = res.json()["data"]["invitation"]
    assert (inv["delivery"], inv["delivery_status"], inv["link"]) == ("EMAIL", "SENT", None)
    assert [to for to, _ in smtp.sent] == ["sent@example.com"]
    token = smtp.last_token()
    assert token not in res.text  # EMAIL mode never returns the token

    [row] = await audit(db_session, "LINK_EMAIL_SENT")
    assert row.action == "CUSTOMER_LINK_EMAIL_SENT" and row.actor_admin_id is not None
    assert row.new_state == {"purpose": "INVITE", "link_revoked": False}
    detail = (await get(async_client, f"/admin/portal-users/{res.json()['data']['id']}", admin)).json()["data"]
    assert detail["last_link_email"]["status"] == "SENT" and detail["active_link"]["purpose"] == "INVITE"
    assert (await redeem(async_client, token)).status_code == 200


async def test_failed_invitation_is_reported_revoked_and_can_be_reissued(db_session, async_client, smtp):
    admin = await admin_session(db_session, async_client)
    smtp.ok = False
    res = await new_customer(async_client, admin, "bounce@example.com")
    user_id = res.json()["data"]["id"]
    inv = res.json()["data"]["invitation"]
    assert (inv["delivery"], inv["delivery_status"], inv["link"]) == ("EMAIL", "FAILED", None)
    failed_token = smtp.last_token()

    # The undelivered link is dead even if the message later surfaces somewhere.
    assert (await redeem(async_client, failed_token)).status_code == 400
    [row] = await audit(db_session, "LINK_EMAIL_FAILED")
    assert row.new_state == {"purpose": "INVITE", "link_revoked": True}
    detail = (await get(async_client, f"/admin/portal-users/{user_id}", admin)).json()["data"]
    assert detail["last_link_email"]["status"] == "FAILED" and detail["active_link"] is None
    assert detail["invitation_pending"] is True

    # Retry = reissue: a fresh link, reported SENT once the server accepts it.
    smtp.ok = True
    retry = await post(async_client, f"/admin/portal-users/{user_id}/password-link", admin)
    assert retry.status_code == 200
    assert (retry.json()["data"]["purpose"], retry.json()["data"]["delivery_status"]) == ("INVITE", "SENT")
    new_token = smtp.last_token()
    assert new_token != failed_token
    detail = (await get(async_client, f"/admin/portal-users/{user_id}", admin)).json()["data"]
    assert detail["last_link_email"]["status"] == "SENT"
    assert (await redeem(async_client, new_token)).status_code == 200


async def test_failed_reset_link_keeps_current_password_and_reports_failure(db_session, async_client, smtp):
    admin = await admin_session(db_session, async_client)
    smtp.ok = True
    created = await new_customer(async_client, admin, "holder@example.com")
    assert (await redeem(async_client, smtp.last_token(), PASSWORD)).status_code == 200
    smtp.ok = False
    res = await post(async_client, f"/admin/portal-users/{created.json()['data']['id']}/password-link", admin)
    assert (res.json()["data"]["purpose"], res.json()["data"]["delivery_status"]) == ("RESET", "FAILED")
    assert (await redeem(async_client, smtp.last_token())).status_code == 400
    login = await async_client.post("/api/v1/auth/login", json={"email": "holder@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert login.status_code == 200  # nothing changed for the holder


async def test_forgot_password_failure_stays_generic_and_is_visible_to_admins(db_session, async_client, smtp):
    admin = await admin_session(db_session, async_client)
    created = await new_customer(async_client, admin, "forgetful@example.com")
    user_id = created.json()["data"]["id"]

    smtp.ok = True
    ok = await async_client.post("/api/v1/auth/password/forgot", json={"email": "forgetful@example.com"}, headers=ORIGIN)
    smtp.ok = False
    failed = await async_client.post("/api/v1/auth/password/forgot", json={"email": "forgetful@example.com"}, headers=ORIGIN)
    unknown = await async_client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"}, headers=ORIGIN)
    assert ok.status_code == failed.status_code == unknown.status_code == 202
    assert ok.text == failed.text == unknown.text  # delivery outcome never reaches the requester

    assert (await redeem(async_client, smtp.last_token())).status_code == 400  # failed link revoked
    rows = await audit(db_session, "_LINK_EMAIL_FAILED")
    assert rows[-1].actor_admin_id is None and rows[-1].actor_email == "forgetful@example.com"
    assert rows[-1].new_state == {"purpose": "RESET", "link_revoked": True}
    detail = (await get(async_client, f"/admin/portal-users/{user_id}", admin)).json()["data"]
    assert detail["last_link_email"]["status"] == "FAILED" and detail["reset_requested_at"] is not None


async def test_real_mailer_failure_is_reported_as_failed(db_session, async_client, monkeypatch, caplog):
    """End to end through app.services.mailer with an unreachable SMTP server (dummy settings)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed_port = s.getsockname()[1]
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", closed_port)
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.invalid")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "dummy-secret-for-test")
    admin = await admin_session(db_session, async_client)
    with caplog.at_level(logging.DEBUG):
        res = await new_customer(async_client, admin, "unreachable@example.com")
    assert res.json()["data"]["invitation"]["delivery_status"] == "FAILED"
    assert "Transactional email could not be sent (ConnectionRefusedError)" in caplog.text
    assert "dummy-secret-for-test" not in caplog.text
    tokens = (await db_session.execute(select(PortalAuthToken))).scalars().all()
    assert len(tokens) == 1 and tokens[0].revoked_at is not None


async def test_raw_tokens_never_in_responses_audit_or_logs(db_session, async_client, smtp, caplog):
    admin = await admin_session(db_session, async_client)
    with caplog.at_level(logging.DEBUG):
        texts = [(await new_customer(async_client, admin, "a@example.com")).text]
        uid = json.loads(texts[0])["data"]["id"]
        smtp.ok = False
        texts.append((await post(async_client, f"/admin/portal-users/{uid}/password-link", admin)).text)
        texts.append((await async_client.post("/api/v1/auth/password/forgot", json={"email": "a@example.com"}, headers=ORIGIN)).text)
        texts.append((await get(async_client, f"/admin/portal-users/{uid}", admin)).text)
    tokens = [re.search(r"#token=([A-Za-z0-9_-]+)", body).group(1) for _, body in smtp.sent]
    assert len(tokens) == 3
    db_session.expire_all()
    audit_dump = json.dumps([[r.action, r.old_state, r.new_state] for r in (await db_session.execute(select(AuditLog))).scalars()])
    for token in tokens:
        assert not any(token in t for t in texts)
        assert token not in audit_dump and token not in caplog.text
    assert "#token=" not in "".join(texts) + audit_dump + caplog.text


async def test_manual_fallback_unchanged_when_smtp_disabled(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    created = await create_account(async_client, admin, "CUSTOMER", "manual@example.com", accept=False)
    inv = created["invitation"]
    assert (inv["delivery"], inv["delivery_status"]) == ("MANUAL", "SHOWN_ONCE")
    assert inv["link"].startswith(f"{settings.PUBLIC_SITE_URL}/reset-password#token=")
    assert await audit(db_session, "_LINK_EMAIL_SENT") == [] and await audit(db_session, "_LINK_EMAIL_FAILED") == []
