"""Initial Schema for EDEN BOUNTY Centralized Enquiry Management System

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-08 12:35:00.000000

Aligns strictly with Phase C13 database specification v2.1.0.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. admin_users
    op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_admin_users_email", "admin_users", ["email"])
    op.create_index(
        "idx_admin_users_active",
        "admin_users",
        ["is_active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 2. admin_roles
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. admin_user_roles
    op.create_table(
        "admin_user_roles",
        sa.Column("admin_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.String(50), sa.ForeignKey("admin_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_by", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=True),
    )

    # 4. admin_sessions
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("admin_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("csrf_token", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_admin_sessions_user", "admin_sessions", ["admin_user_id"])
    op.create_index("idx_admin_sessions_expires", "admin_sessions", ["expires_at"])

    # 5. divisions
    op.create_table(
        "divisions",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("accent_color", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("manufacturer_attribution", sa.String(255), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_divisions_code", "divisions", ["code"])

    # 6. enquiries
    op.create_table(
        "enquiries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference_number", sa.String(50), nullable=False, unique=True),
        # Submitter Contact Snapshot
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("business_email", sa.String(255), nullable=False),
        sa.Column("contact_number", sa.String(50), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        # Commercial Requirements Snapshot
        sa.Column("initial_division_id", sa.String(50), sa.ForeignKey("divisions.id"), nullable=False),
        sa.Column("current_division_id", sa.String(50), sa.ForeignKey("divisions.id"), nullable=False),
        sa.Column("product_focus", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit_of_measurement", sa.String(50), nullable=True),
        sa.Column("specifications", sa.Text(), nullable=True),
        sa.Column("additional_notes", sa.Text(), nullable=True),
        # Optional Commercial Preferences
        sa.Column("preferred_incoterm", sa.String(10), nullable=True),
        sa.Column("target_destination_port", sa.String(150), nullable=True),
        # Operational Management
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'NEW'")),
        sa.Column("assigned_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        # Ingestion Metadata
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("client_user_agent", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_enquiries_ref", "enquiries", ["reference_number"])
    op.create_index("idx_enquiries_status", "enquiries", ["status"])
    op.create_index("idx_enquiries_current_div", "enquiries", ["current_division_id"])
    op.create_index("idx_enquiries_assigned_admin", "enquiries", ["assigned_admin_id"])
    op.create_index("idx_enquiries_created_at", "enquiries", [sa.text("created_at DESC")])

    # 7. enquiry_assignments
    op.create_table(
        "enquiry_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("enquiry_id", sa.UUID(as_uuid=True), sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_division_id", sa.String(50), sa.ForeignKey("divisions.id"), nullable=True),
        sa.Column("new_division_id", sa.String(50), sa.ForeignKey("divisions.id"), nullable=False),
        sa.Column("previous_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("new_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("assignment_rationale", sa.Text(), nullable=True),
        sa.Column("assigned_by_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_enquiry_assignments_enquiry", "enquiry_assignments", ["enquiry_id"])
    op.create_index("idx_enquiry_assignments_assigned_at", "enquiry_assignments", [sa.text("assigned_at DESC")])

    # 8. enquiry_status_history
    op.create_table(
        "enquiry_status_history",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("enquiry_id", sa.UUID(as_uuid=True), sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("changed_by_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_enquiry_status_history_enquiry", "enquiry_status_history", ["enquiry_id"])

    # 9. enquiry_notes
    op.create_table(
        "enquiry_notes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("enquiry_id", sa.UUID(as_uuid=True), sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("is_internal_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_enquiry_notes_enquiry", "enquiry_notes", ["enquiry_id"])

    # 10. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_admin_id", sa.UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_table", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("old_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_user_agent", sa.Text(), nullable=True),
    )
    op.create_index("idx_audit_logs_timestamp", "audit_logs", [sa.text("timestamp DESC")])
    op.create_index("idx_audit_logs_entity", "audit_logs", ["entity_table", "entity_id"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_admin_id"])

    # 11. notification_logs
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("enquiry_id", sa.UUID(as_uuid=True), sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_notification_logs_enquiry", "notification_logs", ["enquiry_id"])
    op.create_index("idx_notification_logs_status", "notification_logs", ["status"])
    op.create_index(
        "idx_notification_logs_retry",
        "notification_logs",
        ["status", "retry_count"],
        postgresql_where=sa.text("status IN ('PENDING', 'FAILED')"),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_table("audit_logs")
    op.drop_table("enquiry_notes")
    op.drop_table("enquiry_status_history")
    op.drop_table("enquiry_assignments")
    op.drop_table("enquiries")
    op.drop_table("divisions")
    op.drop_table("admin_sessions")
    op.drop_table("admin_user_roles")
    op.drop_table("admin_roles")
    op.drop_table("admin_users")
