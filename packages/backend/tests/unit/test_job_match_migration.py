"""Schema invariants for the additive Phase 5 Job Match migration."""

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

from careeros.modules.identity.infrastructure import models as identity_models  # noqa: F401
from careeros.modules.job_match.infrastructure import models


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
        / "20260719_0006_phase5_job_match.py"
    )
    spec = importlib.util.spec_from_file_location("phase5_schema_revision", path)
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


def test_phase5_tables_are_owner_scoped() -> None:
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


def test_phase5_migration_matches_registered_orm_schema() -> None:
    revision = _revision_module()
    capture = _OperationCapture()
    revision.__dict__["op"] = capture
    revision.upgrade()

    expected = _phase_tables()
    captured_names = set(capture.metadata.tables) - {"users"}
    assert captured_names == set(expected)

    for name, table in expected.items():
        migrated = capture.metadata.tables[name]
        assert tuple(table.c.keys()) == tuple(migrated.c.keys()), name
        for column in table.c:
            migrated_column = migrated.c[column.name]
            assert str(column.type) == str(migrated_column.type), f"{name}.{column.name}"
            assert column.nullable == migrated_column.nullable, f"{name}.{column.name}"
        for constraint_type in (
            CheckConstraint,
            ForeignKeyConstraint,
            UniqueConstraint,
        ):
            assert _constraints(table, constraint_type) == _constraints(
                migrated, constraint_type
            ), name
        expected_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in table.indexes
        }
        migrated_indexes = {
            (index.name, tuple(index.columns.keys()), index.unique) for index in migrated.indexes
        }
        assert expected_indexes == migrated_indexes, name
