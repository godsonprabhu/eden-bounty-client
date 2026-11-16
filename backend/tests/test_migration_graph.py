"""Read-only checks for Alembic revision topology.

Authoritative path (see alembic/deferred/README.md):
    0001_initial_schema -> 0002_add_enquiry_idempotency -> 0005_optional_contact_nullable -> 0007_align_index_names
    -> 0008_portal_accounts_orders_investments -> 0009_account_security
Revisions 0003/0004/0006 are deferred: kept verbatim in alembic/deferred/, outside the active graph.
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0002_add_enquiry_idempotency"
PHONE_BRANCH_REVISION = "0005_optional_contact_nullable"
ALIGNMENT_REVISION = "0007_align_index_names"
PORTAL_REVISION = "0008_portal_accounts_orders_investments"
SECURITY_REVISION = "0009_account_security"
REGISTRATION_REVISION = "0010_registration_verification"
CONSOLIDATION_REVISION = "0011_consolidate_building_promotions"
HEAD_REVISION = "0012_deactivate_shisha_and_axe_oil"
AUTHORITATIVE_PATH = [
    "0001_initial_schema",
    BASELINE_REVISION,
    PHONE_BRANCH_REVISION,
    ALIGNMENT_REVISION,
    PORTAL_REVISION,
    SECURITY_REVISION,
    REGISTRATION_REVISION,
    CONSOLIDATION_REVISION,
    HEAD_REVISION,
]
DEFERRED = {
    "0003_v43_0_0": "0003_v43_0_0_notification_claiming_and_payload.py",
    "0004_optional_enquiry_contact_number": "0004_optional_enquiry_contact_number.py",
    "0006_merge_contact_branches": "0006_merge_optional_contact_branches.py",
}


def migration_script() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini")))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def phone_migration_module():
    return load_module(BACKEND_DIR / "alembic" / "versions" / "0005_optional_contact_nullable.py", "phone_nullable_migration")


def test_graph_has_single_head() -> None:
    assert migration_script().get_heads() == [HEAD_REVISION]


def test_authoritative_path_is_linear_from_empty_database() -> None:
    script = migration_script()
    path = [rev.revision for rev in reversed(list(script.walk_revisions("base", "heads")))]
    assert path == AUTHORITATIVE_PATH
    for rev in script.walk_revisions():
        assert not rev.is_merge_point
        assert not rev.is_branch_point


def test_deferred_revisions_are_preserved_but_not_loaded() -> None:
    script = migration_script()
    loaded = {rev.revision for rev in script.walk_revisions()}
    for revision, filename in DEFERRED.items():
        assert revision not in loaded
        assert (BACKEND_DIR / "alembic" / "deferred" / filename).is_file()
        assert not (BACKEND_DIR / "alembic" / "versions" / filename).exists()


def test_phone_revision_is_targetable_from_0002() -> None:
    revision = migration_script().get_revision(PHONE_BRANCH_REVISION)
    assert revision.down_revision == BASELINE_REVISION


def test_alignment_revision_follows_phone_revision() -> None:
    module = load_module(
        BACKEND_DIR / "alembic" / "versions" / "0007_align_index_names_with_models.py", "align_index_names"
    )
    assert module.down_revision == PHONE_BRANCH_REVISION
    # every statement is issued separately (asyncpg cannot prepare multi-command strings)
    statements: list[str] = []

    class FakeOp:
        def execute(self, sql: str) -> None:
            statements.append(sql)

    module.op = FakeOp()
    module.upgrade()
    module.downgrade()
    assert statements and all(";" not in stmt for stmt in statements)


def test_phone_migration_upgrade_is_noop_when_column_is_already_nullable(
    monkeypatch,
) -> None:
    migration = phone_migration_module()

    class Inspector:
        def get_columns(self, table: str, schema: str | None = None) -> list[dict]:
            if table == "alembic_version":
                return [{"name": "version_num", "type": sa.String(64)}]
            return [{"name": "contact_number", "nullable": True}]

    bind = object()
    altered: list[tuple] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector())
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: altered.append((args, kwargs)),
    )

    migration.upgrade()

    assert altered == []


@pytest.mark.parametrize(
    ("version_type", "expected_widening"),
    [
        (sa.Text(), False),
        (sa.String(), False),
        (sa.String(32), True),
        (sa.String(64), False),
        (sa.String(128), False),
    ],
    ids=["text", "unbounded-varchar", "varchar-32", "varchar-64", "varchar-128"],
)
def test_version_column_is_only_widened_when_bounded_below_64(
    monkeypatch, version_type, expected_widening
) -> None:
    migration = phone_migration_module()

    class Inspector:
        def get_columns(self, table: str) -> list[dict]:
            return [{"name": "version_num", "type": version_type}]

    bind = object()
    altered: list[tuple] = []
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector())
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: altered.append((args, kwargs)),
    )

    migration._ensure_revision_id_capacity(bind)

    if expected_widening:
        assert len(altered) == 1
        assert altered[0][0][:2] == ("alembic_version", "version_num")
        assert altered[0][1]["type_"].length == 64
    else:
        assert altered == []


def test_phone_migration_downgrade_refuses_null_values(monkeypatch) -> None:
    migration = phone_migration_module()

    class Bind:
        def scalar(self, statement):
            return True

    monkeypatch.setattr(migration.op, "get_bind", Bind)

    with pytest.raises(RuntimeError, match="rows omit a contact number"):
        migration.downgrade()
