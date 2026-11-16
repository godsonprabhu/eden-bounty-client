"""Customer and investor portals: accounts, sessions, orders, shipments, investments.

Revision ID: 0008_portal_accounts_orders_investments
Revises: 0007_align_index_names
Create Date: 2026-11-13

Purely additive (CR-C4 to CR-C7):
- New tables: portal_users, portal_sessions, orders, order_status_history, shipments,
  shipment_events, investments, investor_documents, investor_updates.
- One new nullable column on an existing table: enquiries.customer_id (FK to portal_users,
  ON DELETE SET NULL). Existing enquiries keep customer_id NULL, i.e. they stay anonymous until an
  administrator explicitly links them.

No existing column, row, index or constraint is altered or removed. Downgrade drops only the
objects created here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_portal_accounts_orders_investments"
down_revision: str | None = "0007_align_index_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENQUIRY_CUSTOMER_FK = "enquiries_customer_id_fkey"


def upgrade() -> None:
    op.create_table('portal_users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=True),
    sa.Column('contact_number', sa.String(length=50), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('CUSTOMER', 'INVESTOR')", name='ck_portal_users_role'),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portal_users_email'), 'portal_users', ['email'], unique=True)
    op.create_index(op.f('ix_portal_users_role'), 'portal_users', ['role'], unique=False)
    op.create_table('investments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference_number', sa.String(length=40), nullable=False),
    sa.Column('investor_id', sa.UUID(), nullable=False),
    sa.Column('division_id', sa.String(length=50), nullable=False),
    sa.Column('amount', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('invested_on', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'ACTIVE', 'MATURED', 'EXITED', 'CANCELLED')", name='ck_investments_status'),
    sa.CheckConstraint('amount > 0', name='ck_investments_amount_positive'),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['investor_id'], ['portal_users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investments_division_id'), 'investments', ['division_id'], unique=False)
    op.create_index(op.f('ix_investments_investor_id'), 'investments', ['investor_id'], unique=False)
    op.create_index(op.f('ix_investments_reference_number'), 'investments', ['reference_number'], unique=True)
    op.create_index(op.f('ix_investments_status'), 'investments', ['status'], unique=False)
    op.create_table('investor_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('investor_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.String(length=80), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('uploaded_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category IN ('FINANCIAL_REPORT', 'INVESTMENT_DOCUMENT', 'OTHER')", name='ck_investor_documents_category'),
    sa.ForeignKeyConstraint(['investor_id'], ['portal_users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_investor_documents_investor_id'), 'investor_documents', ['investor_id'], unique=False)
    op.create_table('investor_updates',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('investor_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['investor_id'], ['portal_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investor_updates_investor_id'), 'investor_updates', ['investor_id'], unique=False)
    op.create_table('portal_sessions',
    sa.Column('id', sa.String(length=128), nullable=False),
    sa.Column('portal_user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('csrf_token', sa.String(length=128), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('CUSTOMER', 'INVESTOR')", name='ck_portal_sessions_role'),
    sa.ForeignKeyConstraint(['portal_user_id'], ['portal_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portal_sessions_expires_at'), 'portal_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_portal_sessions_portal_user_id'), 'portal_sessions', ['portal_user_id'], unique=False)
    op.create_table('orders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference_number', sa.String(length=40), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('enquiry_id', sa.UUID(), nullable=True),
    sa.Column('division_id', sa.String(length=50), nullable=False),
    sa.Column('product_description', sa.String(length=255), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('unit_of_measurement', sa.String(length=50), nullable=True),
    sa.Column('total_amount', sa.Numeric(precision=16, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('customer_note', sa.Text(), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('CONFIRMED', 'PROCESSING', 'READY_TO_SHIP', 'SHIPPED', 'IN_TRANSIT', 'DELIVERED', 'COMPLETED', 'CANCELLED')", name='ck_orders_status'),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['portal_users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['enquiry_id'], ['enquiries.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_orders_created_at_desc', 'orders', [sa.literal_column('created_at DESC')], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_enquiry_id'), 'orders', ['enquiry_id'], unique=False)
    op.create_index(op.f('ix_orders_reference_number'), 'orders', ['reference_number'], unique=True)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_table('order_status_history',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('old_status', sa.String(length=30), nullable=True),
    sa.Column('new_status', sa.String(length=30), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('changed_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_status_history_order_id'), 'order_status_history', ['order_id'], unique=False)
    op.create_table('shipments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('carrier', sa.String(length=150), nullable=True),
    sa.Column('tracking_number', sa.String(length=120), nullable=True),
    sa.Column('origin', sa.String(length=150), nullable=True),
    sa.Column('destination', sa.String(length=150), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimated_delivery_on', sa.Date(), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PREPARING', 'SHIPPED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'RETURNED')", name='ck_shipments_status'),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shipments_order_id'), 'shipments', ['order_id'], unique=False)
    op.create_index(op.f('ix_shipments_tracking_number'), 'shipments', ['tracking_number'], unique=False)
    op.create_table('shipment_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('shipment_id', sa.UUID(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('location', sa.String(length=150), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shipment_events_shipment_id'), 'shipment_events', ['shipment_id'], unique=False)
    op.add_column('enquiries', sa.Column('customer_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_enquiries_customer_id'), 'enquiries', ['customer_id'], unique=False)
    op.create_foreign_key(ENQUIRY_CUSTOMER_FK, 'enquiries', 'portal_users', ['customer_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # WARNING: constraint name is None; this directive will fail as
    # rendered.  Add a name, or use a naming convention; see
    # https://alembic.sqlalchemy.org/en/latest/naming.html
    op.drop_constraint(ENQUIRY_CUSTOMER_FK, 'enquiries', type_='foreignkey')
    op.drop_index(op.f('ix_enquiries_customer_id'), table_name='enquiries')
    op.drop_column('enquiries', 'customer_id')
    op.drop_index(op.f('ix_shipment_events_shipment_id'), table_name='shipment_events')
    op.drop_table('shipment_events')
    op.drop_index(op.f('ix_shipments_tracking_number'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_order_id'), table_name='shipments')
    op.drop_table('shipments')
    op.drop_index(op.f('ix_order_status_history_order_id'), table_name='order_status_history')
    op.drop_table('order_status_history')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_reference_number'), table_name='orders')
    op.drop_index(op.f('ix_orders_enquiry_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_index('idx_orders_created_at_desc', table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_portal_sessions_portal_user_id'), table_name='portal_sessions')
    op.drop_index(op.f('ix_portal_sessions_expires_at'), table_name='portal_sessions')
    op.drop_table('portal_sessions')
    op.drop_index(op.f('ix_investor_updates_investor_id'), table_name='investor_updates')
    op.drop_table('investor_updates')
    op.drop_index(op.f('ix_investor_documents_investor_id'), table_name='investor_documents')
    op.drop_table('investor_documents')
    op.drop_index(op.f('ix_investments_status'), table_name='investments')
    op.drop_index(op.f('ix_investments_reference_number'), table_name='investments')
    op.drop_index(op.f('ix_investments_investor_id'), table_name='investments')
    op.drop_index(op.f('ix_investments_division_id'), table_name='investments')
    op.drop_table('investments')
    op.drop_index(op.f('ix_portal_users_role'), table_name='portal_users')
    op.drop_index(op.f('ix_portal_users_email'), table_name='portal_users')
    op.drop_table('portal_users')
