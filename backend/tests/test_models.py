"""Tests for SQLAlchemy Models, Constraints, and Schema Integrity."""

import uuid
from decimal import Decimal

import pytest
from app.db.base import Base
from app.models.admin import AdminUser
from app.models.enquiry import Enquiry
from app.models.notification import NotificationLog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def test_approved_tables_exist_in_metadata():
    """Verify that all 11 approved C13 tables are defined in SQLAlchemy metadata."""
    expected_tables = {
        "admin_users",
        "admin_roles",
        "admin_user_roles",
        "admin_sessions",
        "divisions",
        "enquiries",
        "enquiry_assignments",
        "enquiry_status_history",
        "enquiry_notes",
        "audit_logs",
        "notification_logs",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), (
        f"Missing tables: {expected_tables - actual_tables}"
    )


@pytest.mark.asyncio
async def test_admin_user_creation_and_unique_email(db_session: AsyncSession):
    """Verify AdminUser creation and unique email constraint enforcement."""
    unique_email = f"test_{uuid.uuid4().hex[:8]}@edenbounty.org"
    user1 = AdminUser(
        email=unique_email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake_hash",
        first_name="Operations",
        last_name="Officer",
        job_title="Trading Desk Officer",
    )
    db_session.add(user1)
    await db_session.commit()
    assert user1.id is not None
    assert user1.is_active is True
    assert user1.failed_login_attempts == 0

    # Duplicate email must raise IntegrityError
    user2 = AdminUser(
        email=unique_email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake_hash2",
        first_name="Duplicate",
        last_name="User",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Clean up test user
    await db_session.delete(user1)
    await db_session.commit()


@pytest.mark.asyncio
async def test_enquiry_foreign_key_constraint(db_session: AsyncSession):
    """Verify foreign key constraint on enquiry division_id."""
    invalid_enquiry = Enquiry(
        reference_number=f"EB-RFQ-TEST-{uuid.uuid4().hex[:6]}",
        full_name="John Doe",
        company_name="Test Enterprise Ltd",
        business_email="buyer@test.com",
        contact_number="+60123456789",
        country="Malaysia",
        initial_division_id="nonexistent-division-id",
        current_division_id="nonexistent-division-id",
        product_focus="Test Product",
    )
    db_session.add(invalid_enquiry)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_enquiry_creation_and_unique_reference(db_session: AsyncSession):
    """Verify valid Enquiry creation and unique reference_number constraint."""
    ref_no = f"EB-RFQ-20261108-{uuid.uuid4().hex[:4].upper()}"
    enquiry1 = Enquiry(
        reference_number=ref_no,
        full_name="Ahmed Al-Kindi",
        company_name="Muscat Trade Logistics",
        business_email="ahmed@muscattrade.com",
        contact_number="+968 24 123456",
        country="Oman",
        initial_division_id="petroleum-products",
        current_division_id="petroleum-products",
        product_focus="Ultra-Low Sulfur Diesel",
        quantity=Decimal("5000.00"),
        unit_of_measurement="Metric Tonnes",
        specifications="Target EN590 10ppm",
    )
    db_session.add(enquiry1)
    await db_session.commit()
    assert enquiry1.id is not None
    assert enquiry1.status == "NEW"

    # Duplicate reference_number must fail
    enquiry2 = Enquiry(
        reference_number=ref_no,
        full_name="Duplicate Submitter",
        company_name="Another Co",
        business_email="another@co.com",
        contact_number="+60123456780",
        country="Malaysia",
        initial_division_id="petroleum-products",
        current_division_id="petroleum-products",
        product_focus="Duplicate Focus",
    )
    db_session.add(enquiry2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Clean up test enquiry
    await db_session.delete(enquiry1)
    await db_session.commit()


@pytest.mark.asyncio
async def test_notification_log_defaults(db_session: AsyncSession):
    """Verify notification_logs model defaults and structure."""
    notif = NotificationLog(
        recipient_email="ops@edenbounty.org",
        notification_type="ADMIN_ALERT",
    )
    db_session.add(notif)
    await db_session.commit()
    assert notif.id is not None
    assert notif.status == "PENDING"
    assert notif.retry_count == 0
    assert notif.sent_at is None

    # Clean up test notification
    await db_session.delete(notif)
    await db_session.commit()
