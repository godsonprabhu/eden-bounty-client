"""Tests for role-based authentication, customer and investor portals, and their admin management.

CR-C4 to CR-C7. Focus: authentication per role, prevention of role switching, and data isolation
(a customer or investor can only ever read their own records).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.seeds import seed_divisions, seed_roles
from app.models.admin import AdminSession, AdminUser, AdminUserRole
from app.models.audit import AuditLog
from app.models.enquiry import (
    Enquiry,
    EnquiryAssignment,
    EnquiryNote,
    EnquiryStatusHistory,
)
from app.models.portal import (
    Investment,
    InvestorDocument,
    InvestorUpdate,
    Order,
    OrderStatusHistory,
    PortalSession,
    PortalUser,
    Shipment,
    ShipmentEvent,
)

PASSWORD = "CorporatePass2026!#"
ORIGIN = {"Origin": "http://localhost:3000"}
ADMIN_COOKIE = settings.SESSION_COOKIE_NAME
CUSTOMER_COOKIE = settings.CUSTOMER_SESSION_COOKIE_NAME
INVESTOR_COOKIE = settings.INVESTOR_SESSION_COOKIE_NAME
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

_TABLES = [
    AuditLog, ShipmentEvent, Shipment, OrderStatusHistory, Order, InvestorDocument, InvestorUpdate,
    Investment, EnquiryNote, EnquiryStatusHistory, EnquiryAssignment, Enquiry, PortalSession,
    PortalUser, AdminSession, AdminUserRole, AdminUser,
]


async def _wipe(db: AsyncSession) -> None:
    for model in _TABLES:
        await db.execute(delete(model))
    await db.commit()


@pytest.fixture(autouse=True)
async def clean_portal_tables(db_session: AsyncSession, async_client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PRIVATE_STORAGE_DIR", str(tmp_path / "private"))

    # The shared test client keeps a cookie jar, so a login in one step would silently
    # authenticate later requests. These tests are about exactly which cookie grants what, so the
    # jar is emptied around every request: only cookies passed explicitly are sent.
    original_request = async_client.request

    async def stateless_request(*args, **kwargs):
        async_client.cookies.clear()
        try:
            return await original_request(*args, **kwargs)
        finally:
            async_client.cookies.clear()

    monkeypatch.setattr(async_client, "request", stateless_request)
    await _wipe(db_session)
    await seed_roles(db_session)
    await seed_divisions(db_session)
    yield
    await _wipe(db_session)


# ------------------------------------------------------------------ helpers
async def make_admin(db: AsyncSession, email: str, role: str = "SUPER_ADMIN") -> AdminUser:
    user = AdminUser(email=email, password_hash=hash_password(PASSWORD), first_name="Test", last_name="Admin")
    db.add(user)
    await db.flush()
    db.add(AdminUserRole(admin_user_id=user.id, role_id=role, assigned_by=user.id))
    await db.commit()
    return user


class Session:
    """Cookie + CSRF token for one signed-in account."""

    def __init__(self, cookie_name: str, token: str, csrf: str):
        self.cookies = {cookie_name: token}
        self.headers = {**ORIGIN, "X-CSRF-Token": csrf}
        self.token = token


async def login_admin(client: AsyncClient, email: str) -> Session:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}, headers=ORIGIN)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["account_type"] == "ADMIN"
    return Session(ADMIN_COOKIE, res.cookies[ADMIN_COOKIE], res.json()["data"]["csrf_token"])


async def admin_session(db: AsyncSession, client: AsyncClient, role: str = "SUPER_ADMIN") -> Session:
    email = f"{role.lower()}-{uuid.uuid4().hex[:6]}@edenbounty.org"
    await make_admin(db, email, role)
    return await login_admin(client, email)


def token_from(link: str) -> str:
    assert "#token=" in link, link
    return link.split("#token=", 1)[1]


async def accept_link(client: AsyncClient, link: str, password: str = PASSWORD):
    return await client.post(
        "/api/v1/auth/password/reset", json={"token": token_from(link), "new_password": password}, headers=ORIGIN
    )


async def create_account(client: AsyncClient, admin: Session, role: str, email: str, *, accept: bool = True, **extra) -> dict:
    """Creates the account as an administrator, then (by default) sets PASSWORD through the
    invitation link exactly as the account holder would."""
    body = {"role": role, "email": email, "full_name": extra.pop("full_name", "Portal User"), **extra}
    res = await client.post("/api/v1/admin/portal-users", json=body, cookies=admin.cookies, headers=admin.headers)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    if accept:
        done = await accept_link(client, data["invitation"]["link"])
        assert done.status_code == 200, done.text
    return data


async def login_customer(client: AsyncClient, email: str) -> Session:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}, headers=ORIGIN)
    assert res.status_code == 200, res.text
    return Session(CUSTOMER_COOKIE, res.cookies[CUSTOMER_COOKIE], res.json()["data"]["csrf_token"])


async def login_investor(client: AsyncClient, email: str) -> Session:
    res = await client.post("/api/v1/investor/login", json={"email": email, "password": PASSWORD}, headers=ORIGIN)
    assert res.status_code == 200, res.text
    return Session(INVESTOR_COOKIE, res.cookies[INVESTOR_COOKIE], res.json()["data"]["csrf_token"])


async def make_enquiry(db: AsyncSession, email: str = "buyer@example.com", division: str = "mineral-water") -> Enquiry:
    enquiry = Enquiry(
        reference_number=f"EB-RFQ-{uuid.uuid4().hex[:12].upper()}",
        full_name="Buyer Person",
        company_name="Buyer Co",
        business_email=email,
        country="Malaysia",
        initial_division_id=division,
        current_division_id=division,
        product_focus="Bottled water 500ml",
        quantity=Decimal("1000.00"),
        unit_of_measurement="Cartons",
        status="NEW",
    )
    db.add(enquiry)
    await db.commit()
    return enquiry


async def get(client: AsyncClient, path: str, session: Session | None = None, **kw):
    return await client.get(f"/api/v1{path}", cookies=session.cookies if session else None, **kw)


async def post(client: AsyncClient, path: str, session: Session, json=None, **kw):
    return await client.post(f"/api/v1{path}", json=json, cookies=session.cookies, headers=session.headers, **kw)


async def patch(client: AsyncClient, path: str, session: Session, json=None):
    return await client.patch(f"/api/v1{path}", json=json, cookies=session.cookies, headers=session.headers)


# ================================================================== authentication
async def test_admin_login_still_works_and_reports_admin_destination(db_session, async_client):
    await make_admin(db_session, "root@edenbounty.org")
    res = await async_client.post("/api/v1/auth/login", json={"email": "root@edenbounty.org", "password": PASSWORD}, headers=ORIGIN)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["account_type"] == "ADMIN" and data["redirect_to"] == "/admin"
    assert data["user"]["roles"] == ["SUPER_ADMIN"]
    assert ADMIN_COOKIE in res.cookies and CUSTOMER_COOKIE not in res.cookies


async def test_customer_signs_in_on_main_login_and_backend_chooses_destination(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "Cust@Example.com", company_name="Cust Co")

    # A client-supplied role is rejected outright: the role is never taken from the request.
    forged = await async_client.post(
        "/api/v1/auth/login", json={"email": "cust@example.com", "password": PASSWORD, "role": "ADMIN"}, headers=ORIGIN
    )
    res = await async_client.post("/api/v1/auth/login", json={"email": "cust@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["account_type"] == "CUSTOMER" and data["redirect_to"] == "/account"
    assert data["user"]["role"] == "CUSTOMER" and "roles" not in data["user"]
    assert CUSTOMER_COOKIE in res.cookies and ADMIN_COOKIE not in res.cookies
    set_cookie = res.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    if forged.status_code == 200:  # extra field ignored: still must not become an admin
        assert forged.json()["data"]["account_type"] == "CUSTOMER" and ADMIN_COOKIE not in forged.cookies

    me = await get(async_client, "/customer/me", Session(CUSTOMER_COOKIE, res.cookies[CUSTOMER_COOKIE], data["csrf_token"]))
    assert me.status_code == 200 and me.json()["data"]["email"] == "cust@example.com"
    assert "password_hash" not in me.text


async def test_investor_cannot_use_main_login_and_others_cannot_use_investor_login(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await make_admin(db_session, "second-admin@edenbounty.org")
    await create_account(async_client, admin, "INVESTOR", "inv@example.com")
    await create_account(async_client, admin, "CUSTOMER", "cust@example.com")

    main = await async_client.post("/api/v1/auth/login", json={"email": "inv@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert main.status_code == 200 and main.json()["data"]["redirect_to"] == "/investors/portal"
    assert INVESTOR_COOKIE in main.cookies

    for email in ("cust@example.com", "second-admin@edenbounty.org", "nobody@example.com"):
        res = await async_client.post("/api/v1/investor/login", json={"email": email, "password": PASSWORD}, headers=ORIGIN)
        assert res.status_code == 401 and res.json()["detail"] == "Invalid email or password", email
        assert not res.cookies

    ok = await async_client.post("/api/v1/investor/login", json={"email": "inv@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert ok.status_code == 200
    assert ok.json()["data"]["account_type"] == "INVESTOR" and ok.json()["data"]["redirect_to"] == "/investors/portal"
    assert INVESTOR_COOKIE in ok.cookies and CUSTOMER_COOKIE not in ok.cookies and ADMIN_COOKIE not in ok.cookies


async def test_portal_login_rejects_disallowed_origin(db_session, async_client):
    res = await async_client.post(
        "/api/v1/investor/login", json={"email": "x@example.com", "password": PASSWORD}, headers={"Origin": "https://evil.example"}
    )
    assert res.status_code == 403


async def test_portal_account_lockout_after_repeated_failures(db_session, async_client):
    """Five failures from one client lock that client out of the account (even with the right
    password) without locking the real account holder out from elsewhere."""
    admin = await admin_session(db_session, async_client)
    account = await create_account(async_client, admin, "CUSTOMER", "lock@example.com")
    attacker = {**ORIGIN, "X-Forwarded-For": "203.0.113.50"}
    for _ in range(settings.LOCKOUT_MAX_ATTEMPTS):
        bad = await async_client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "Wrong-Password-1!"}, headers=attacker)
        assert bad.status_code == 401
    locked = await async_client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": PASSWORD}, headers=attacker)
    assert locked.status_code == 401  # correct password, but this client is locked out of the account
    assert locked.json()["detail"] == "Invalid email or password"
    user = (await db_session.execute(select(PortalUser).where(PortalUser.id == uuid.UUID(account["id"])))).scalar_one()
    await db_session.refresh(user)
    assert user.locked_until is None  # the account itself is not locked
    holder = await async_client.post(
        "/api/v1/auth/login", json={"email": "lock@example.com", "password": PASSWORD}, headers={**ORIGIN, "X-Forwarded-For": "198.51.100.7"}
    )
    assert holder.status_code == 200


async def test_failed_sign_ins_are_throttled_per_client(db_session, async_client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_FAILURE_LIMIT_PER_IP", 3)
    for i in range(3):
        res = await async_client.post("/api/v1/investor/login", json={"email": f"n{i}@example.com", "password": "x"}, headers=ORIGIN)
        assert res.status_code == 401
    res = await async_client.post("/api/v1/investor/login", json={"email": "n9@example.com", "password": "x"}, headers=ORIGIN)
    assert res.status_code == 429
    res = await async_client.post("/api/v1/auth/login", json={"email": "n9@example.com", "password": "x"}, headers=ORIGIN)
    assert res.status_code == 429


async def test_successful_portal_login_is_audited(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    account = await create_account(async_client, admin, "CUSTOMER", "audit@example.com")
    await login_customer(async_client, "audit@example.com")
    rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "PORTAL_LOGIN_CUSTOMER"))).scalars().all()
    assert len(rows) == 1 and str(rows[0].entity_id) == account["id"] and rows[0].actor_email == "audit@example.com"


# ================================================================== role isolation
async def test_unauthenticated_requests_are_rejected_everywhere(async_client):
    for path in ("/customer/me", "/customer/overview", "/customer/enquiries", "/customer/orders",
                 "/investor/me", "/investor/overview", "/investor/investments", "/investor/documents", "/investor/updates",
                 "/admin/portal-users?role=CUSTOMER", "/admin/orders", "/admin/investments", "/admin/investor-updates",
                 "/admin/dashboard/portal-summary"):
        assert (await get(async_client, path)).status_code == 401, path


async def test_sessions_cannot_be_replayed_across_roles(db_session, async_client):
    """Renaming a session cookie must not grant another role's access."""
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    await create_account(async_client, admin, "INVESTOR", "inv@example.com")
    customer = await login_customer(async_client, "cust@example.com")
    investor = await login_investor(async_client, "inv@example.com")

    # Customer token presented as an investor cookie, and the reverse: refused.
    r = await async_client.get("/api/v1/investor/overview", cookies={INVESTOR_COOKIE: customer.token})
    assert r.status_code == 403
    r = await async_client.get("/api/v1/customer/overview", cookies={CUSTOMER_COOKIE: investor.token})
    assert r.status_code == 403
    # Portal tokens presented as the administrator cookie: not a valid admin session.
    for token in (customer.token, investor.token):
        for path in ("/admin/orders", "/admin/portal-users?role=CUSTOMER", "/admin/rfqs", "/admin/dashboard/overview", "/auth/me"):
            r = await async_client.get(f"/api/v1{path}", cookies={ADMIN_COOKIE: token})
            assert r.status_code == 401, path
    # An administrator token is not a portal session either.
    for cookie, path in ((CUSTOMER_COOKIE, "/customer/overview"), (INVESTOR_COOKIE, "/investor/overview")):
        r = await async_client.get(f"/api/v1{path}", cookies={cookie: admin.token})
        assert r.status_code == 401
    # Their own cookies do not open the other portal or the admin API.
    assert (await get(async_client, "/investor/overview", customer)).status_code == 401
    assert (await get(async_client, "/customer/overview", investor)).status_code == 401
    assert (await get(async_client, "/admin/orders", customer)).status_code == 401
    # A portal user cannot perform admin mutations even with a valid portal CSRF token.
    r = await post(async_client, "/admin/portal-users", customer, json={"role": "CUSTOMER", "email": "x@example.com", "full_name": "X"})
    assert r.status_code == 401
    assert (await db_session.execute(select(func.count()).select_from(PortalUser))).scalar_one() == 2


async def test_portal_mutations_require_csrf_token_and_allowed_origin(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    customer = await login_customer(async_client, "cust@example.com")
    body = {"current_password": PASSWORD, "new_password": "AnotherPass2026!#"}

    no_token = await async_client.post("/api/v1/customer/password", json=body, cookies=customer.cookies, headers=ORIGIN)
    wrong = await async_client.post("/api/v1/customer/password", json=body, cookies=customer.cookies, headers={**ORIGIN, "X-CSRF-Token": "nope"})
    bad_origin = await async_client.post(
        "/api/v1/customer/password", json=body, cookies=customer.cookies,
        headers={"Origin": "https://evil.example", "X-CSRF-Token": customer.headers["X-CSRF-Token"]},
    )
    assert (no_token.status_code, wrong.status_code, bad_origin.status_code) == (403, 403, 403)
    assert (await async_client.post("/api/v1/customer/logout", cookies=customer.cookies, headers=ORIGIN)).status_code == 403


async def test_password_change_and_logout(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    first = await login_customer(async_client, "cust@example.com")
    second = await login_customer(async_client, "cust@example.com")

    weak = await post(async_client, "/customer/password", first, json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.status_code == 422
    wrong = await post(async_client, "/customer/password", first, json={"current_password": "Not-The-Password-1!", "new_password": "AnotherPass2026!#"})
    assert wrong.status_code == 400
    ok = await post(async_client, "/customer/password", first, json={"current_password": PASSWORD, "new_password": "AnotherPass2026!#"})
    assert ok.status_code == 200

    assert (await get(async_client, "/customer/me", first)).status_code == 200  # the session that changed it stays
    assert (await get(async_client, "/customer/me", second)).status_code == 401  # every other session is revoked
    old = await async_client.post("/api/v1/auth/login", json={"email": "cust@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert old.status_code == 401

    out = await post(async_client, "/customer/logout", first)
    assert out.status_code == 200
    assert (await get(async_client, "/customer/me", first)).status_code == 401


async def test_deactivated_account_is_signed_out_immediately_and_cannot_log_in(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    account = await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    customer = await login_customer(async_client, "cust@example.com")
    res = await patch(async_client, f"/admin/portal-users/{account['id']}", admin, json={"is_active": False})
    assert res.status_code == 200 and res.json()["data"]["is_active"] is False
    assert (await get(async_client, "/customer/me", customer)).status_code == 401
    again = await async_client.post("/api/v1/auth/login", json={"email": "cust@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert again.status_code == 401


# ================================================================== admin: accounts
async def test_account_creation_rules(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await make_admin(db_session, "taken-admin@edenbounty.org")
    await create_account(async_client, admin, "CUSTOMER", "dup@example.com")

    dup = await post(async_client, "/admin/portal-users", admin, json={"role": "INVESTOR", "email": "DUP@example.com", "full_name": "X"})
    admin_email = await post(async_client, "/admin/portal-users", admin, json={"role": "CUSTOMER", "email": "taken-admin@edenbounty.org", "full_name": "X"})
    # Administrators can no longer choose a portal password: the field is refused outright.
    admin_password = await post(async_client, "/admin/portal-users", admin, json={"role": "CUSTOMER", "email": "weak@example.com", "password": PASSWORD, "full_name": "X"})
    bad_role = await post(async_client, "/admin/portal-users", admin, json={"role": "ADMIN", "email": "r@example.com", "full_name": "X"})
    extra = await post(async_client, "/admin/portal-users", admin, json={"role": "CUSTOMER", "email": "e@example.com", "full_name": "X", "is_admin": True})
    no_csrf = await async_client.post("/api/v1/admin/portal-users", json={"role": "CUSTOMER", "email": "n@example.com", "full_name": "X"}, cookies=admin.cookies, headers=ORIGIN)
    assert (dup.status_code, admin_email.status_code) == (409, 409)
    assert (admin_password.status_code, bad_role.status_code, extra.status_code, no_csrf.status_code) == (422, 422, 422, 403)

    listing = await get(async_client, "/admin/portal-users?role=CUSTOMER", admin)
    assert [u["email"] for u in listing.json()["data"]] == ["dup@example.com"]
    assert "password" not in listing.text
    stored = (await db_session.execute(select(PortalUser))).scalar_one()
    assert stored.password_hash.startswith("$argon2id$")  # set by the holder through the invitation


async def test_operations_admin_manages_customers_but_not_investor_records(db_session, async_client):
    root = await admin_session(db_session, async_client, "SUPER_ADMIN")
    ops = await admin_session(db_session, async_client, "OPERATIONS_ADMIN")
    investor = await create_account(async_client, root, "INVESTOR", "inv@example.com")
    await create_account(async_client, ops, "CUSTOMER", "cust@example.com")

    denied = [
        await post(async_client, "/admin/portal-users", ops, json={"role": "INVESTOR", "email": "i2@example.com", "full_name": "X"}),
        await get(async_client, "/admin/portal-users?role=INVESTOR", ops),
        await get(async_client, f"/admin/portal-users/{investor['id']}", ops),
        await patch(async_client, f"/admin/portal-users/{investor['id']}", ops, json={"is_active": False}),
        await post(async_client, f"/admin/portal-users/{investor['id']}/password-link", ops),
        await get(async_client, "/admin/investments", ops),
        await post(async_client, "/admin/investments", ops, json={"investor_id": investor["id"], "division_id": "mineral-water", "amount": "100.00", "invested_on": "2026-01-01"}),
        await get(async_client, "/admin/investor-updates", ops),
        await post(async_client, f"/admin/investors/{investor['id']}/documents?title=T&filename=a.pdf", ops, content=PDF),
    ]
    assert [r.status_code for r in denied] == [403] * len(denied)

    summary = (await get(async_client, "/admin/dashboard/portal-summary", ops)).json()["data"]
    assert summary["total_customers"] == 1 and summary["total_investors"] == 1
    assert summary["investment_totals"] is None and summary["investments_count"] is None


# ================================================================== customer: enquiries
async def test_enquiry_is_not_exposed_by_email_match_until_admin_links_it(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    owner = await create_account(async_client, admin, "CUSTOMER", "buyer@example.com")
    await create_account(async_client, admin, "CUSTOMER", "other@example.com")
    enquiry = await make_enquiry(db_session, email="buyer@example.com")  # same email as the account
    buyer = await login_customer(async_client, "buyer@example.com")
    other = await login_customer(async_client, "other@example.com")

    assert (await get(async_client, "/customer/enquiries", buyer)).json()["data"] == []
    assert (await get(async_client, f"/customer/enquiries/{enquiry.id}", buyer)).status_code == 404

    # Linking to a non-customer account is refused; linking to the customer works.
    investor = await create_account(async_client, admin, "INVESTOR", "inv@example.com")
    assert (await post(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin, json={"customer_id": investor["id"]})).status_code == 404
    assert (await post(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin, json={"customer_id": owner["id"]})).status_code == 200

    link = (await get(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin)).json()["data"]
    assert link["customer"]["email"] == "buyer@example.com" and link["orders"] == []
    assert (await get(async_client, f"/admin/rfqs/{enquiry.id}/customer", buyer)).status_code == 401

    mine = (await get(async_client, "/customer/enquiries", buyer)).json()["data"]
    assert [e["reference_number"] for e in mine] == [enquiry.reference_number]
    assert (await get(async_client, "/customer/enquiries", other)).json()["data"] == []
    assert (await get(async_client, f"/customer/enquiries/{enquiry.id}", other)).status_code == 404

    # Unlinking hides it again; the enquiry row itself is untouched.
    assert (await post(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin, json={"customer_id": None})).status_code == 200
    assert (await get(async_client, "/customer/enquiries", buyer)).json()["data"] == []
    assert (await db_session.execute(select(func.count()).select_from(Enquiry))).scalar_one() == 1
    actions = {a for (a,) in (await db_session.execute(select(AuditLog.action))).all()}
    assert {"ENQUIRY_CUSTOMER_LINKED", "ENQUIRY_CUSTOMER_UNLINKED"} <= actions


async def test_customer_sees_status_and_customer_visible_updates_but_never_internal_notes(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    owner = await create_account(async_client, admin, "CUSTOMER", "buyer@example.com")
    enquiry = await make_enquiry(db_session)
    await post(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin, json={"customer_id": owner["id"]})

    internal = await post(async_client, f"/admin/rfqs/{enquiry.id}/notes", admin, json={"note_text": "INTERNAL margin is 40 percent"})
    assert internal.status_code == 201
    status_change = await patch(async_client, f"/admin/rfqs/{enquiry.id}/status", admin, json={"new_status": "UNDER_REVIEW", "change_reason": "INTERNAL reason text"})
    assert status_change.status_code == 200, status_change.text
    visible = await post(async_client, f"/admin/rfqs/{enquiry.id}/customer-updates", admin, json={"message": "We are preparing <b>your</b> quotation."})
    assert visible.status_code == 201

    buyer = await login_customer(async_client, "buyer@example.com")
    res = await get(async_client, f"/customer/enquiries/{enquiry.id}", buyer)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "UNDER_REVIEW"
    assert {u["kind"] for u in data["updates"]} == {"STATUS", "MESSAGE"}
    assert "We are preparing your quotation." in res.text
    assert "INTERNAL" not in res.text
    for hidden in ("business_email", "source_ip", "assigned_admin", "contact_number"):
        assert hidden not in data


# ================================================================== orders
async def _order_for(async_client, admin, customer_id, **extra) -> dict:
    body = {"customer_id": customer_id, "division_id": "mineral-water", "product_description": "Bottled water", **extra}
    res = await post(async_client, "/admin/orders", admin, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


async def test_order_workflow_from_enquiry_to_tracking(db_session, async_client):
    admin = await admin_session(db_session, async_client, "OPERATIONS_ADMIN")
    owner = await create_account(async_client, admin, "CUSTOMER", "buyer@example.com")
    enquiry = await make_enquiry(db_session)

    created = await post(async_client, "/admin/orders", admin, json={"customer_id": owner["id"], "enquiry_id": str(enquiry.id), "total_amount": "12500.50", "currency": "myr"})
    assert created.status_code == 201, created.text
    order = created.json()["data"]
    assert order["reference_number"].startswith("EB-ORD-") and order["status"] == "CONFIRMED"
    assert order["product_description"] == "Bottled water 500ml" and order["division"]["id"] == "mineral-water"
    assert order["quantity"] == "1000.00" and order["currency"] == "MYR" and order["enquiry_reference"] == enquiry.reference_number
    await db_session.refresh(enquiry)
    assert str(enquiry.customer_id) == owner["id"]  # converting an enquiry links it to that customer

    moved = await patch(async_client, f"/admin/orders/{order['id']}/status", admin, json={"new_status": "processing", "note": "Stock allocated"})
    assert moved.status_code == 200 and moved.json()["data"]["status"] == "PROCESSING"
    assert (await patch(async_client, f"/admin/orders/{order['id']}/status", admin, json={"new_status": "PROCESSING"})).status_code == 400
    assert (await patch(async_client, f"/admin/orders/{order['id']}/status", admin, json={"new_status": "TELEPORTED"})).status_code == 422

    shipment = await post(async_client, f"/admin/orders/{order['id']}/shipments", admin, json={"carrier": "Ocean Line", "tracking_number": "TRK-001", "origin": "Port Klang", "destination": "Singapore", "status": "SHIPPED", "estimated_delivery_on": "2026-12-01"})
    assert shipment.status_code == 201, shipment.text
    shipment_id = shipment.json()["data"]["id"]
    event = await post(async_client, f"/admin/shipments/{shipment_id}/events", admin, json={"description": "Departed origin port", "location": "Port Klang"})
    assert event.status_code == 201
    updated = await patch(async_client, f"/admin/shipments/{shipment_id}", admin, json={"status": "IN_TRANSIT"})
    assert updated.json()["data"]["status"] == "IN_TRANSIT" and updated.json()["data"]["carrier"] == "Ocean Line"

    buyer = await login_customer(async_client, "buyer@example.com")
    detail = (await get(async_client, f"/customer/orders/{order['id']}", buyer)).json()["data"]
    assert detail["status"] == "PROCESSING"
    assert [h["new_status"] for h in detail["status_history"]] == ["PROCESSING", "CONFIRMED"]
    assert detail["status_history"][0]["note"] == "Stock allocated"
    assert detail["shipments"][0]["tracking_number"] == "TRK-001" and detail["shipments"][0]["status"] == "IN_TRANSIT"
    assert detail["shipments"][0]["events"][0]["description"] == "Departed origin port"
    assert "customer" not in detail and "created_by_admin_id" not in detail

    overview = (await get(async_client, "/customer/overview", buyer)).json()["data"]
    assert (overview["orders_total"], overview["orders_active"], overview["enquiries_total"]) == (1, 1, 1)
    enquiry_view = (await get(async_client, f"/customer/enquiries/{enquiry.id}", buyer)).json()["data"]
    assert enquiry_view["orders"][0]["reference_number"] == order["reference_number"]

    actions = {a for (a,) in (await db_session.execute(select(AuditLog.action))).all()}
    assert {"ORDER_CREATED", "ORDER_STATUS_UPDATED", "SHIPMENT_CREATED", "SHIPMENT_EVENT_ADDED", "SHIPMENT_UPDATED"} <= actions


async def test_customers_only_see_their_own_orders_and_cannot_modify_them(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    a = await create_account(async_client, admin, "CUSTOMER", "a@example.com")
    b = await create_account(async_client, admin, "CUSTOMER", "b@example.com")
    order_a = await _order_for(async_client, admin, a["id"])
    order_b = await _order_for(async_client, admin, b["id"])
    sa, sb = await login_customer(async_client, "a@example.com"), await login_customer(async_client, "b@example.com")

    assert [o["id"] for o in (await get(async_client, "/customer/orders", sa)).json()["data"]] == [order_a["id"]]
    assert [o["id"] for o in (await get(async_client, "/customer/orders", sb)).json()["data"]] == [order_b["id"]]
    assert (await get(async_client, f"/customer/orders/{order_b['id']}", sa)).status_code == 404
    assert (await get(async_client, f"/customer/orders/{order_a['id']}", sb)).status_code == 404
    # No ownership override through query parameters.
    spoof = await get(async_client, f"/customer/orders?customer_id={b['id']}", sa)
    assert [o["id"] for o in spoof.json()["data"]] == [order_a["id"]]
    # Customers have no write routes for orders, and admin routes reject their session.
    for method, path in (("patch", f"/customer/orders/{order_a['id']}"), ("post", "/customer/orders"), ("delete", f"/customer/orders/{order_a['id']}")):
        r = await getattr(async_client, method)(f"/api/v1{path}", cookies=sa.cookies, headers=sa.headers)
        assert r.status_code in (404, 405), path
    assert (await patch(async_client, f"/admin/orders/{order_a['id']}/status", sa, json={"new_status": "DELIVERED"})).status_code == 401


async def test_order_creation_validation(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    a = await create_account(async_client, admin, "CUSTOMER", "a@example.com")
    b = await create_account(async_client, admin, "CUSTOMER", "b@example.com")
    investor = await create_account(async_client, admin, "INVESTOR", "inv@example.com")
    enquiry = await make_enquiry(db_session)
    await post(async_client, f"/admin/rfqs/{enquiry.id}/customer", admin, json={"customer_id": a["id"]})

    cases = {
        "investor as customer": ({"customer_id": investor["id"], "division_id": "mineral-water", "product_description": "x"}, 404),
        "unknown division": ({"customer_id": a["id"], "division_id": "nope", "product_description": "x"}, 400),
        "missing product": ({"customer_id": a["id"], "division_id": "mineral-water"}, 400),
        "amount without currency": ({"customer_id": a["id"], "division_id": "mineral-water", "product_description": "x", "total_amount": "5.00"}, 400),
        "enquiry of another customer": ({"customer_id": b["id"], "enquiry_id": str(enquiry.id)}, 409),
        "negative quantity": ({"customer_id": a["id"], "division_id": "mineral-water", "product_description": "x", "quantity": "-1"}, 422),
    }
    for label, (body, expected) in cases.items():
        assert (await post(async_client, "/admin/orders", admin, json=body)).status_code == expected, label
    assert (await db_session.execute(select(func.count()).select_from(Order))).scalar_one() == 0


# ================================================================== investors
async def _investment(async_client, admin, investor_id, amount, division="mineral-water", **extra) -> dict:
    body = {"investor_id": investor_id, "division_id": division, "amount": amount, "invested_on": "2026-03-01", **extra}
    res = await post(async_client, "/admin/investments", admin, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


async def test_investor_sees_only_own_investments_with_exact_totals(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    one = await create_account(async_client, admin, "INVESTOR", "one@example.com")
    two = await create_account(async_client, admin, "INVESTOR", "two@example.com")
    await _investment(async_client, admin, one["id"], "100000.10")
    await _investment(async_client, admin, one["id"], "50000.20", division="construction", status="PENDING")
    cancelled = await _investment(async_client, admin, one["id"], "999.00", status="CANCELLED")
    await _investment(async_client, admin, two["id"], "777777.00")
    s1, s2 = await login_investor(async_client, "one@example.com"), await login_investor(async_client, "two@example.com")

    mine = (await get(async_client, "/investor/investments", s1)).json()["data"]
    assert sorted(i["amount"] for i in mine) == ["100000.10", "50000.20", "999.00"]
    assert "777777" not in (await get(async_client, "/investor/investments", s1)).text
    assert [i["amount"] for i in (await get(async_client, "/investor/investments", s2)).json()["data"]] == ["777777.00"]
    spoof = await get(async_client, f"/investor/investments?investor_id={two['id']}", s1)
    assert "777777" not in spoof.text

    overview = (await get(async_client, "/investor/overview", s1)).json()["data"]
    assert overview["totals"] == [{"currency": "MYR", "total": "150000.30", "active_total": "100000.10"}]
    assert overview["investments_count"] == 3 and overview["status_counts"]["CANCELLED"] == 1
    shares = {a["division"]["id"]: (a["amount"], a["share_percent"]) for a in overview["allocation"]}
    assert shares == {"mineral-water": ("100000.10", "66.7"), "construction": ("50000.20", "33.3")}
    assert not any(k in str(overview).lower() for k in ("return", "profit", "yield", "projection"))

    edited = await patch(async_client, f"/admin/investments/{cancelled['id']}", admin, json={"status": "ACTIVE", "amount": "1000.00"})
    assert edited.status_code == 200 and edited.json()["data"]["status"] == "ACTIVE"
    assert (await post(async_client, "/admin/investments", admin, json={"investor_id": one["id"], "division_id": "mineral-water", "amount": "0", "invested_on": "2026-03-01"})).status_code == 422

    summary = (await get(async_client, "/admin/dashboard/portal-summary", admin)).json()["data"]
    assert summary["investment_totals"] == [{"currency": "MYR", "total": "928777.30", "active_total": "878777.10"}]
    assert summary["investments_count"] == 4 and summary["total_investors"] == 2


async def test_investor_documents_are_private_and_owner_only(db_session, async_client, tmp_path):
    admin = await admin_session(db_session, async_client)
    one = await create_account(async_client, admin, "INVESTOR", "one@example.com")
    await create_account(async_client, admin, "INVESTOR", "two@example.com")
    await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    s1, s2 = await login_investor(async_client, "one@example.com"), await login_investor(async_client, "two@example.com")
    customer = await login_customer(async_client, "cust@example.com")

    up = await post(async_client, f"/admin/investors/{one['id']}/documents?title=FY2026%20Report&filename=..%2F..%2Fetc%2Freport%20final.pdf", admin, content=PDF)
    assert up.status_code == 201, up.text
    doc = up.json()["data"]
    assert doc["original_filename"] == "report final.pdf" and doc["content_type"] == "application/pdf"
    assert doc["is_published"] is False and "storage_key" not in doc

    stored = (await db_session.execute(select(InvestorDocument))).scalar_one()
    files = list((tmp_path / "private").iterdir())
    assert [f.name for f in files] == [stored.storage_key] and files[0].read_bytes() == PDF
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"

    # Unpublished: invisible even to the owner.
    assert (await get(async_client, "/investor/documents", s1)).json()["data"] == []
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download", s1)).status_code == 404

    assert (await patch(async_client, f"/admin/investor-documents/{doc['id']}", admin, json={"is_published": True})).status_code == 200
    listed = (await get(async_client, "/investor/documents", s1)).json()["data"]
    assert [d["title"] for d in listed] == ["FY2026 Report"]
    download = await get(async_client, f"/investor/documents/{doc['id']}/download", s1)
    assert download.status_code == 200 and download.content == PDF
    assert download.headers["cache-control"] == "private, no-store"
    assert "attachment" in download.headers["content-disposition"]

    # Another investor, a customer, and anonymous visitors cannot list or download it.
    assert (await get(async_client, "/investor/documents", s2)).json()["data"] == []
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download", s2)).status_code == 404
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download", customer)).status_code == 401
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download")).status_code == 401
    assert (await get(async_client, f"/admin/investor-documents/{doc['id']}/download", s1)).status_code == 401
    assert (await get(async_client, f"/admin/investor-documents/{doc['id']}/download", admin)).content == PDF

    assert (await patch(async_client, f"/admin/investor-documents/{doc['id']}", admin, json={"is_published": False})).status_code == 200
    assert (await get(async_client, f"/investor/documents/{doc['id']}/download", s1)).status_code == 404


async def test_document_upload_validation(db_session, async_client, tmp_path, monkeypatch):
    admin = await admin_session(db_session, async_client)
    one = await create_account(async_client, admin, "INVESTOR", "one@example.com")
    customer = await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    url = f"/admin/investors/{one['id']}/documents?title=T&filename=a.pdf"

    assert (await post(async_client, url, admin, content=b"<html><script>alert(1)</script></html>")).status_code == 415
    assert (await post(async_client, url, admin, content=b"")).status_code == 400
    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 64)
    assert (await post(async_client, url, admin, content=PDF + b"0" * 100)).status_code == 413
    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 1024 * 1024)
    assert (await post(async_client, url + "&category=NONSENSE", admin, content=PDF)).status_code == 400
    assert (await post(async_client, f"/admin/investors/{customer['id']}/documents?title=T&filename=a.pdf", admin, content=PDF)).status_code == 404
    no_csrf = await async_client.post(f"/api/v1{url}", content=PDF, cookies=admin.cookies, headers=ORIGIN)
    assert no_csrf.status_code == 403

    assert (await db_session.execute(select(func.count()).select_from(InvestorDocument))).scalar_one() == 0
    private = tmp_path / "private"
    assert not private.exists() or list(private.iterdir()) == []  # rejected uploads leave nothing behind


async def test_investor_updates_visibility(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    one = await create_account(async_client, admin, "INVESTOR", "one@example.com")
    two = await create_account(async_client, admin, "INVESTOR", "two@example.com")
    s1, s2 = await login_investor(async_client, "one@example.com"), await login_investor(async_client, "two@example.com")

    async def publish(title, investor_id=None, is_published=True):
        res = await post(async_client, "/admin/investor-updates", admin, json={"title": title, "body": f"Body of {title}", "investor_id": investor_id, "is_published": is_published})
        assert res.status_code == 201, res.text
        return res.json()["data"]

    await publish("For everyone")
    await publish("Only for one", one["id"])
    await publish("Only for two", two["id"])
    draft = await publish("Draft", one["id"], is_published=False)

    titles = lambda r: sorted(u["title"] for u in r.json()["data"])
    assert titles(await get(async_client, "/investor/updates", s1)) == ["For everyone", "Only for one"]
    assert titles(await get(async_client, "/investor/updates", s2)) == ["For everyone", "Only for two"]

    assert (await patch(async_client, f"/admin/investor-updates/{draft['id']}", admin, json={"is_published": True})).status_code == 200
    assert "Draft" in titles(await get(async_client, "/investor/updates", s1))
    assert "Draft" not in titles(await get(async_client, "/investor/updates", s2))
    customer_target = await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    assert (await post(async_client, "/admin/investor-updates", admin, json={"title": "x", "body": "y", "investor_id": customer_target["id"]})).status_code == 404


# ================================================================== admin detail & data preservation
async def test_admin_account_detail_and_password_reset(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    cust = await create_account(async_client, admin, "CUSTOMER", "cust@example.com")
    enquiry = await make_enquiry(db_session)
    await _order_for(async_client, admin, cust["id"], enquiry_id=str(enquiry.id))
    session = await login_customer(async_client, "cust@example.com")

    detail = (await get(async_client, f"/admin/portal-users/{cust['id']}", admin)).json()["data"]
    assert len(detail["enquiries"]) == 1 and len(detail["orders"]) == 1 and detail["investments"] == []

    edited = await patch(async_client, f"/admin/portal-users/{cust['id']}", admin, json={"company_name": "New Co", "country": ""})
    assert edited.json()["data"]["company_name"] == "New Co" and edited.json()["data"]["country"] is None

    # The administrator issues a reset link; it never sets or sees the password itself.
    reset = await post(async_client, f"/admin/portal-users/{cust['id']}/password-link", admin)
    assert reset.status_code == 200 and reset.json()["data"]["purpose"] == "RESET"
    assert (await get(async_client, "/customer/me", session)).status_code == 200  # nothing changes until the link is used
    assert (await accept_link(async_client, reset.json()["data"]["link"], "ResetPass2026!#x")).status_code == 200
    assert (await get(async_client, "/customer/me", session)).status_code == 401
    relog = await async_client.post("/api/v1/auth/login", json={"email": "cust@example.com", "password": "ResetPass2026!#x"}, headers=ORIGIN)
    assert relog.status_code == 200


async def test_expired_portal_session_is_rejected_and_removed(db_session, async_client):
    admin = await admin_session(db_session, async_client)
    await create_account(async_client, admin, "INVESTOR", "inv@example.com")
    investor = await login_investor(async_client, "inv@example.com")
    session_row = (await db_session.execute(select(PortalSession))).scalar_one()
    session_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    assert (await get(async_client, "/investor/me", investor)).status_code == 401
    assert (await db_session.execute(select(func.count()).select_from(PortalSession))).scalar_one() == 0
