"""Create synthetic E2E accounts and records in the isolated Playwright database only."""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.cli.create_admin import provision_super_admin
from app.core.security import hash_password
from app.db.seeds import seed_all
from app.db.session import AsyncSessionLocal
from app.models.admin import AdminUser
from app.models.enquiry import Enquiry
from app.models.portal import (
    Investment,
    InvestorDocument,
    InvestorUpdate,
    Order,
    OrderStatusHistory,
    PortalUser,
    Shipment,
    ShipmentEvent,
)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not any(host in database_url for host in ("127.0.0.1", "localhost", "[::1]")):
        raise SystemExit("Refusing E2E seed: database URL must use loopback.")
    if "/eb_playwright_test_" not in database_url:
        raise SystemExit("Refusing E2E seed: database name must use eb_playwright_test_ prefix.")

    password = os.environ["PW_TEST_PASSWORD"]
    admin_email = os.environ["PW_ADMIN_EMAIL"].lower()
    customer_email = os.environ["PW_CUSTOMER_EMAIL"].lower()
    customer_b_email = os.environ["PW_CUSTOMER_B_EMAIL"].lower()
    investor_email = os.environ["PW_INVESTOR_EMAIL"].lower()
    investor_b_email = os.environ["PW_INVESTOR_B_EMAIL"].lower()
    storage = Path(os.environ["PRIVATE_STORAGE_DIR"]).resolve()
    storage.mkdir(mode=0o700, parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        await seed_all(session)
        await provision_super_admin(
            session, admin_email, "Synthetic", "Playwright Admin", password, "E2E only"
        )
        admin_user = (
            await session.execute(select(AdminUser).where(AdminUser.email == admin_email))
        ).scalar_one()
        now = datetime.now(UTC)
        customer = PortalUser(
            email=customer_email, password_hash=hash_password(password), role="CUSTOMER",
            full_name="Synthetic Customer A", company_name="Synthetic Buyer A", country="Malaysia",
            created_by_admin_id=admin_user.id, email_verified_at=now,
        )
        customer_b = PortalUser(
            email=customer_b_email, password_hash=hash_password(password), role="CUSTOMER",
            full_name="Synthetic Customer B", company_name="Synthetic Buyer B", country="Malaysia",
            created_by_admin_id=admin_user.id, email_verified_at=now,
        )
        investor = PortalUser(
            email=investor_email, password_hash=hash_password(password), role="INVESTOR",
            full_name="Synthetic Investor A", company_name="Synthetic Capital A", country="Malaysia",
            created_by_admin_id=admin_user.id, email_verified_at=now,
        )
        investor_b = PortalUser(
            email=investor_b_email, password_hash=hash_password(password), role="INVESTOR",
            full_name="Synthetic Investor B", company_name="Synthetic Capital B", country="Malaysia",
            created_by_admin_id=admin_user.id, email_verified_at=now,
        )
        session.add_all([customer, customer_b, investor, investor_b])
        await session.flush()

        enquiry = Enquiry(
            reference_number="EB-RFQ-PW-FIXTURE-0001",
            full_name="Synthetic Procurement Contact",
            company_name="Synthetic Buyer A",
            business_email=customer_email,
            country="Malaysia",
            initial_division_id="mineral-water",
            current_division_id="mineral-water",
            product_focus="Synthetic bottled water acceptance fixture",
            quantity=Decimal("1000.00"),
            unit_of_measurement="Cartons",
            status="UNDER_REVIEW",
            customer_id=customer.id,
        )
        session.add(enquiry)
        await session.flush()

        order_a = Order(
            reference_number="EB-ORDER-PW-FIXTURE-0001",
            customer_id=customer.id,
            # Keep the pre-existing customer order independent so the admin workflow can
            # exercise conversion of the seeded enquiry into a new order.
            enquiry_id=None,
            division_id="mineral-water",
            product_description="Synthetic bottled water acceptance order",
            quantity=Decimal("1000.00"),
            unit_of_measurement="Cartons",
            total_amount=Decimal("1250.00"),
            currency="MYR",
            status="IN_TRANSIT",
            customer_note="Synthetic customer-visible note",
            created_by_admin_id=admin_user.id,
        )
        order_b = Order(
            reference_number="EB-ORDER-PW-FIXTURE-0002",
            customer_id=customer_b.id,
            division_id="scrap-trading",
            product_description="Synthetic private order for customer B",
            status="PROCESSING",
            created_by_admin_id=admin_user.id,
        )
        session.add_all([order_a, order_b])
        await session.flush()
        session.add(OrderStatusHistory(
            order_id=order_a.id, old_status="CONFIRMED", new_status="IN_TRANSIT",
            note="Synthetic order status fixture", changed_by_admin_id=admin_user.id,
        ))
        shipment = Shipment(
            order_id=order_a.id, carrier="Synthetic Carrier", tracking_number="PW-TRACK-0001",
            origin="Port Klang", destination="Synthetic Test Port", status="IN_TRANSIT",
            shipped_at=datetime.now(UTC), created_by_admin_id=admin_user.id,
        )
        session.add(shipment)
        await session.flush()
        session.add(ShipmentEvent(
            shipment_id=shipment.id, description="Synthetic shipment departed origin",
            location="Port Klang", created_by_admin_id=admin_user.id,
        ))

        session.add(Investment(
            reference_number="EB-INV-PW-0001", investor_id=investor.id,
            division_id="mineral-water", amount=Decimal("50000.00"), currency="MYR",
            invested_on=date.today(), status="ACTIVE",
            summary="Synthetic investor acceptance fixture", created_by_admin_id=admin_user.id,
        ))
        session.add_all([
            InvestorUpdate(
                title="Synthetic public investor update", body="Published update fixture for E2E.",
                is_published=True, published_at=datetime.now(UTC), created_by_admin_id=admin_user.id,
            ),
            InvestorUpdate(
                investor_id=investor_b.id, title="Synthetic private investor B update",
                body="Must not be visible to investor A.", is_published=True,
                published_at=datetime.now(UTC), created_by_admin_id=admin_user.id,
            ),
        ])

        pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        documents: list[InvestorDocument] = []
        for portal_user, title in (
            (investor, "Synthetic investor A report"),
            (investor_b, "Synthetic investor B private report"),
        ):
            key = f"{uuid.uuid4().hex}.pdf"
            (storage / key).write_bytes(pdf_bytes)
            documents.append(InvestorDocument(
                investor_id=portal_user.id, title=title, category="FINANCIAL_REPORT",
                original_filename="synthetic-report.pdf", storage_key=key,
                content_type="application/pdf", size_bytes=len(pdf_bytes),
                sha256=hashlib.sha256(pdf_bytes).hexdigest(), is_published=True,
                published_at=datetime.now(UTC), uploaded_by_admin_id=admin_user.id,
            ))
        session.add_all(documents)
        await session.commit()

        print(json.dumps({
            "adminId": str(admin_user.id), "customerAId": str(customer.id),
            "customerBId": str(customer_b.id), "enquiryId": str(enquiry.id),
            "orderAId": str(order_a.id), "orderBId": str(order_b.id),
            "investorAId": str(investor.id), "investorBId": str(investor_b.id),
            "documentAId": str(documents[0].id), "documentBId": str(documents[1].id),
        }))


asyncio.run(main())
