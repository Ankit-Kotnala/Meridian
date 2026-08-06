"""Schema invariants for the additive Phase 7 resume builder migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Table,
    UniqueConstraint,
    Uuid,
)

from rezumi.modules.identity.infrastructure import models as identity_models  # noqa: F401
from rezumi.modules.resume_builder.infrastructure import models


def _phase_tables() -> dict[str, Table]:
    return {
        value.__table__.name: value.__table__
        for value in vars(models).values()
        if isinstance(value, type)
        and value.__module__ == models.__name__
        and hasattr(value, "__table__")
    }


def _revision_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260719_0008_phase7_resume_builder.py"
    )
    spec = importlib.util.spec_from_file_location("phase7_schema_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    return revision


def _durable_cleanup_revision_source() -> str:
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260726_0013_phase7_durable_export_cleanup.py"
    )
    return path.read_text(encoding="utf-8")


class _OperationCapture:
    def __init__(self) -> None:
        self.metadata = MetaData()
        Table("users", self.metadata, Column("id", Uuid, primary_key=True))

    def create_table(self, name: str, *elements: Any, **keywords: Any) -> None:
        Table(name, self.metadata, *elements, **keywords)

    def create_index(
        self,
        name: str,
        table_name: str,
        columns: list[str],
        *,
        unique: bool = False,
        **_keywords: Any,
    ) -> None:
        table = self.metadata.tables[table_name]
        Index(name, *(table.c[column] for column in columns), unique=unique)


def _constraints(table: Table, kind: type[Any]) -> set[tuple[str | None, tuple[str, ...]]]:
    return {
        (constraint.name, tuple(constraint.columns.keys()))
        for constraint in table.constraints
        if isinstance(constraint, kind)
    }


def test_phase7_tables_are_owner_scoped() -> None:
    for table_name, table in _phase_tables().items():
        owner = table.c.get("owner_user_id")
        assert owner is not None and not owner.nullable, table_name
        assert any(foreign_key.column.table.name == "users" for foreign_key in owner.foreign_keys)
        for constraint in table.constraints:
            if not isinstance(constraint, ForeignKeyConstraint):
                continue
            elements = tuple(constraint.elements)
            target_table = elements[0].column.table.name
            if target_table == "users":
                continue
            assert "owner_user_id" in {element.parent.name for element in elements}
            assert "owner_user_id" in {element.column.name for element in elements}


def test_deleted_export_state_is_enforced_by_orm_and_migration() -> None:
    table = models.ResumeExportModel.__table__
    constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_resume_exports_deleted_state_valid"
    )
    expression = str(constraint.sqltext)
    assert "status = 'deleted'" in expression
    assert "deleted_at IS NOT NULL" in expression
    assert "object_key IS NULL" in expression
    assert "status <> 'deleted'" in expression
    assert "deleted_at IS NULL" in expression

    migration = _durable_cleanup_revision_source()
    assert '"ck_resume_exports_deleted_state_valid"' in migration
    assert migration.count("ck_resume_exports_deleted_state_valid") == 2
    assert '"resume_export_object_cleanups"' in migration
    assert '"trace_id", sa.String(128), nullable=False' in migration
    assert "migration_recovered_unverified_deletion" in migration
    assert '"operation": "delete"' in migration
    assert "legacy_deletion_state_unverified" in migration


def test_phase7_migration_matches_registered_orm_schema() -> None:
    """The shipped 0008 migration remains an immutable historical baseline."""
    revision = _revision_module()
    capture = _OperationCapture()
    revision.__dict__["op"] = capture
    revision.upgrade()

    expected = _phase_tables()
    captured_names = set(capture.metadata.tables) - {"users"}
    assert captured_names == set(expected) - {
        "resume_export_object_cleanups",
        "resume_export_outbox",
    }
    closure_columns = {
        "resumes": {"layout"},
        "resume_versions": {"layout", "personal_facts", "entities"},
        "resume_exports": {
            "version_content_sha256",
            "fidelity_manifest",
            "fidelity_manifest_sha256",
            "trace_id",
            "max_attempts",
            "cleanup_attempts",
            "cleanup_max_attempts",
            "fence",
            "execution_token_hash",
            "lease_expires_at",
            "retry_at",
            "dead_lettered_at",
        },
        "resume_export_verification_reports": {
            "occurrence_mismatches",
            "reading_order_failures",
            "manifest_sha256",
            "version_content_sha256",
            "page_count",
        },
    }

    for name in captured_names:
        table = expected[name]
        migrated = capture.metadata.tables[name]
        historical_columns = tuple(
            column.name for column in table.c if column.name not in closure_columns.get(name, set())
        )
        assert historical_columns == tuple(migrated.c.keys()), name
        for column_name in historical_columns:
            column = table.c[column_name]
            migrated_column = migrated.c[column.name]
            assert str(column.type) == str(migrated_column.type), f"{name}.{column.name}"
            assert column.nullable == migrated_column.nullable, f"{name}.{column.name}"
        for constraint_type in (ForeignKeyConstraint, UniqueConstraint):
            assert _constraints(migrated, constraint_type) <= _constraints(
                table, constraint_type
            ), name
        expected_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in table.indexes
        }
        migrated_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in migrated.indexes
        }
        assert migrated_indexes <= expected_indexes, name
