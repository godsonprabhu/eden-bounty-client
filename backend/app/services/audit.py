"""Audit logging service for EDEN BOUNTY backend.

Phase C13.4 — Central Admin Dashboard & Enquiry Management.
Persists application-level append-only audit records within the active database transaction.
"""

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import get_client_ip
from app.models.admin import AdminUser
from app.models.audit import AuditLog


async def record_audit_log(
    session: AsyncSession,
    actor_admin: AdminUser | None,
    action: str,
    entity_table: str,
    entity_id: uuid.UUID,
    old_state: dict[str, Any] | None,
    new_state: dict[str, Any] | None,
    request: Request | None = None,
) -> AuditLog:
    """Inserts an audit log record in the active database transaction.

    This function adds the entry to the current session so that the audit record
    is committed or rolled back atomically alongside the corresponding entity mutation.
    """
    client_ip = get_client_ip(request) if request else None
    user_agent = request.headers.get("user-agent") if request else None

    actor_id = actor_admin.id if actor_admin else None
    actor_email = actor_admin.email if actor_admin else None

    audit_entry = AuditLog(
        actor_admin_id=actor_id,
        actor_email=actor_email,
        ip_address=client_ip,
        action=action,
        entity_table=entity_table,
        entity_id=entity_id,
        old_state=old_state,
        new_state=new_state,
        client_user_agent=user_agent,
    )
    session.add(audit_entry)
    return audit_entry


# Entity id recorded when a sign-in names an email that matches no account. Recording the
# attempted address itself would put arbitrary attacker-supplied text in the ledger, so it is not.
UNKNOWN_ACCOUNT_ID = uuid.UUID(int=0)

# Keys that must never appear in an audit payload (security remediation, finding 4).
_FORBIDDEN_KEYS = {"password", "current_password", "new_password", "password_hash", "token", "token_hash", "csrf_token", "session"}


def record_security_event(
    session: AsyncSession,
    action: str,
    entity_table: str,
    entity_id: uuid.UUID,
    *,
    actor_email: str | None = None,
    actor_admin: AdminUser | None = None,
    old_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Adds a security event (sign-in failure, logout, password or profile change) to the session.

    For events performed by a customer or investor, ``actor_admin_id`` stays NULL and the account's
    email is recorded as ``actor_email``. Passwords, hashes, tokens and session identifiers are
    refused outright rather than silently dropped, so a mistake fails loudly in tests.
    """
    for payload in (old_state, new_state):
        if payload and (_FORBIDDEN_KEYS & set(payload)):
            raise ValueError("Audit payloads must not contain passwords, hashes or tokens")
    entry = AuditLog(
        actor_admin_id=actor_admin.id if actor_admin else None,
        actor_email=actor_admin.email if actor_admin else actor_email,
        ip_address=get_client_ip(request) if request else None,
        action=action,
        entity_table=entity_table,
        entity_id=entity_id,
        old_state=old_state,
        new_state=new_state,
        client_user_agent=request.headers.get("user-agent") if request else None,
    )
    session.add(entry)
    return entry
