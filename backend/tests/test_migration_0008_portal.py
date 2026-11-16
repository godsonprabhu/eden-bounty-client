"""Checks for revision 0008 (customer and investor portals): additive only, constraints in place."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0008_portal_accounts_orders_investments.py"
NEW_TABLES = {
    "portal_users", "portal_sessions", "orders", "order_status_history", "shipments",
    "shipment_events", "investments", "investor_documents", "investor_updates",
}
EXISTING_TABLES = {
    "admin_users", "admin_roles", "admin_user_roles", "admin_sessions", "divisions", "enquiries",
    "enquiry_assignments", "enquiry_status_history", "enquiry_notes", "audit_logs", "notification_logs",
}


def _function_body(name: str) -> str:
    source = MIGRATION.read_text()
    start = source.index(f"def {name}()")
    following = source.find("\ndef ", start + 1)
    return source[start: following if following != -1 else len(source)]


def test_upgrade_is_additive_only():
    body = _function_body("upgrade")
    assert not re.search(r"op\.(drop_|alter_column|execute|rename_table|bulk_insert)", body)
    assert set(re.findall(r"op\.create_table\(\s*'(\w+)'", body)) == NEW_TABLES
    # The only existing table touched is `enquiries`, and only to add one nullable column.
    assert re.findall(r"op\.add_column\('(\w+)', sa\.Column\('(\w+)', [^)]*\), nullable=(\w+)\)", body) == [
        ("enquiries", "customer_id", "True")
    ]
    touched = set(re.findall(r"op\.create_(?:index|foreign_key)\([^,]+, '(\w+)'", body)) - NEW_TABLES
    assert touched == {"enquiries"}


def test_downgrade_only_removes_objects_created_by_this_revision():
    body = _function_body("downgrade")
    assert set(re.findall(r"op\.drop_table\('(\w+)'\)", body)) == NEW_TABLES
    assert re.findall(r"op\.drop_column\('(\w+)', '(\w+)'\)", body) == [("enquiries", "customer_id")]
    assert not (set(re.findall(r"op\.drop_table\('(\w+)'\)", body)) & EXISTING_TABLES)


@pytest.mark.asyncio
async def test_schema_objects_exist_with_expected_constraints(db_session: AsyncSession):
    tables = {r[0] for r in (await db_session.execute(text("select table_name from information_schema.tables where table_schema='public'"))).all()}
    assert NEW_TABLES <= tables and EXISTING_TABLES <= tables

    nullable = (await db_session.execute(text(
        "select is_nullable from information_schema.columns where table_name='enquiries' and column_name='customer_id'"
    ))).scalar_one()
    assert nullable == "YES"

    fks = {(r[0], r[1], r[2], r[3]) for r in (await db_session.execute(text("""
        select tc.table_name, kcu.column_name, ccu.table_name, rc.delete_rule
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu using (constraint_name, table_schema)
        join information_schema.constraint_column_usage ccu using (constraint_name, table_schema)
        join information_schema.referential_constraints rc using (constraint_name)
        where tc.constraint_type='FOREIGN KEY' and tc.table_schema='public'
    """))).all()}
    for expected in [
        ("enquiries", "customer_id", "portal_users", "SET NULL"),
        ("portal_sessions", "portal_user_id", "portal_users", "CASCADE"),
        ("orders", "customer_id", "portal_users", "RESTRICT"),
        ("orders", "enquiry_id", "enquiries", "SET NULL"),
        ("orders", "division_id", "divisions", "RESTRICT"),
        ("shipments", "order_id", "orders", "CASCADE"),
        ("shipment_events", "shipment_id", "shipments", "CASCADE"),
        ("investments", "investor_id", "portal_users", "RESTRICT"),
        ("investments", "division_id", "divisions", "RESTRICT"),
        ("investor_documents", "investor_id", "portal_users", "RESTRICT"),
    ]:
        assert expected in fks, expected

    unique = {r[0] for r in (await db_session.execute(text(
        "select indexname from pg_indexes where schemaname='public' and indexdef like 'CREATE UNIQUE%'"
    ))).all()}
    assert {"ix_portal_users_email", "ix_orders_reference_number", "ix_investments_reference_number"} <= unique

    checks = {r[0] for r in (await db_session.execute(text("select conname from pg_constraint where contype='c'"))).all()}
    assert {"ck_portal_users_role", "ck_portal_sessions_role", "ck_orders_status", "ck_shipments_status",
            "ck_investments_status", "ck_investments_amount_positive", "ck_investor_documents_category"} <= checks


def test_models_and_migrations_are_in_sync():
    """`alembic check` compares the migrated test database with the ORM models (read-only)."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=BACKEND_DIR, env=dict(os.environ), capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No new upgrade operations detected" in result.stdout + result.stderr
