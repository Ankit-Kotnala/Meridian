"""Schema invariants for the additive Phase 6 Change Studio migration."""

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

from rezumi.modules.change_studio.infrastructure import models
from rezumi.modules.identity.infrastructure import models as identity_models  # noqa: F401

_FORWARD_PROVENANCE_COLUMNS = {
    "evidence_revision_id",
    "evidence_revision_number",
    "evidence_statement_sha256",
}
_FORWARD_PROVENANCE_CONSTRAINT = (
    "ck_change_operation_claims_evidence_provenance_complete",
    (),
)


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
        / "20260719_0007_phase6_change_studio.py"
    )
    spec = importlib.util.spec_from_file_location("phase6_schema_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    return revision


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


def test_phase6_tables_are_owner_scoped() -> None:
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


def test_phase6_migration_matches_schema_before_forward_provenance_extension() -> None:
    revision = _revision_module()
    capture = _OperationCapture()
    revision.__dict__["op"] = capture
    revision.upgrade()

    expected = _phase_tables()
    captured_names = set(capture.metadata.tables) - {"users"}
    assert captured_names == set(expected)

    for name, table in expected.items():
        migrated = capture.metadata.tables[name]
        expected_columns = tuple(
            column
            for column in table.c
            if name != "change_operation_claims" or column.name not in _FORWARD_PROVENANCE_COLUMNS
        )
        assert tuple(column.name for column in expected_columns) == tuple(migrated.c.keys()), name
        for column in expected_columns:
            migrated_column = migrated.c[column.name]
            assert str(column.type) == str(migrated_column.type), f"{name}.{column.name}"
            assert column.nullable == migrated_column.nullable, f"{name}.{column.name}"
        for constraint_type in (
            CheckConstraint,
            ForeignKeyConstraint,
            UniqueConstraint,
        ):
            expected_constraints = _constraints(table, constraint_type)
            if name == "change_operation_claims" and constraint_type is CheckConstraint:
                expected_constraints.discard(_FORWARD_PROVENANCE_CONSTRAINT)
            assert expected_constraints == _constraints(migrated, constraint_type), name
        expected_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in table.indexes
        }
        migrated_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in migrated.indexes
        }
        assert expected_indexes == migrated_indexes, name

    legacy_claims = capture.metadata.tables["change_operation_claims"]
    assert _FORWARD_PROVENANCE_COLUMNS.isdisjoint(legacy_claims.c.keys())
