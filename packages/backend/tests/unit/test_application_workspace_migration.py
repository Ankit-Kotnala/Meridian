"""Schema invariants for the additive Phase 8 application workspace migration."""

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
from sqlalchemy.dialects import postgresql

from careeros.modules.application_workspace.domain import (
    ApplicationAuditAction,
    ApplicationDocumentKind,
    ApplicationDocumentStatus,
    ApplicationEventKind,
    ApplicationPackStatus,
    ApplicationStage,
    ConsistencyStatus,
    OutcomeStatus,
    ReferralStatus,
)
from careeros.modules.application_workspace.infrastructure import models
from careeros.modules.change_studio.infrastructure import models as change_studio_models
from careeros.modules.identity.infrastructure import models as identity_models  # noqa: F401
from careeros.modules.resume_builder.infrastructure import models as resume_models  # noqa: F401


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
        / "20260724_0009_phase8_application_workspace.py"
    )
    spec = importlib.util.spec_from_file_location("phase8_schema_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    return revision


class _OperationCapture:
    def __init__(self) -> None:
        self.metadata = MetaData()
        self.added_columns: list[tuple[str, Column[Any]]] = []
        self.added_check_constraints: list[tuple[str, str, str]] = []
        Table("users", self.metadata, Column("id", Uuid, primary_key=True))
        Table(
            "resume_versions",
            self.metadata,
            Column("id", Uuid, primary_key=True),
            Column("owner_user_id", Uuid, nullable=False),
            UniqueConstraint("owner_user_id", "id"),
        )

    def add_column(self, table_name: str, column: Column[Any]) -> None:
        self.added_columns.append((table_name, column))

    def create_check_constraint(
        self,
        name: str,
        table_name: str,
        condition: str,
    ) -> None:
        self.added_check_constraints.append((name, table_name, condition))

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


def test_phase8_tables_are_owner_scoped() -> None:
    for table_name, table in _phase_tables().items():
        owner = table.c.get("owner_user_id")
        assert owner is not None and not owner.nullable, table_name
        assert any(foreign_key.column.table.name == "users" for foreign_key in owner.foreign_keys)
        for constraint in table.constraints:
            if not isinstance(constraint, ForeignKeyConstraint):
                continue
            elements = tuple(constraint.elements)
            target_table = elements[0].column.table.name
            if target_table in {"users", "resume_versions"}:
                if target_table == "resume_versions":
                    assert "owner_user_id" in {element.parent.name for element in elements}
                continue
            assert "owner_user_id" in {element.parent.name for element in elements}
            assert "owner_user_id" in {element.column.name for element in elements}


def test_phase8_migration_matches_registered_orm_schema() -> None:
    revision = _revision_module()
    capture = _OperationCapture()
    revision.__dict__["op"] = capture
    revision.upgrade()

    expected = _phase_tables()
    captured_names = set(capture.metadata.tables) - {"users", "resume_versions"}
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


def test_phase8_database_allowlists_match_domain_enums() -> None:
    revision = _revision_module()
    expected = {
        "_STAGES": ApplicationStage,
        "_REFERRAL_STATUSES": ReferralStatus,
        "_OUTCOME_STATUSES": OutcomeStatus,
        "_EVENT_KINDS": ApplicationEventKind,
        "_DOCUMENT_KINDS": ApplicationDocumentKind,
        "_DOCUMENT_STATUSES": ApplicationDocumentStatus,
        "_PACK_STATUSES": ApplicationPackStatus,
        "_CONSISTENCY_STATUSES": ConsistencyStatus,
        "_AUDIT_ACTIONS": ApplicationAuditAction,
    }
    for constant_name, enum_type in expected.items():
        domain_values = tuple(member.value for member in enum_type)
        assert getattr(models, constant_name) == domain_values
        assert getattr(revision, constant_name) == domain_values


def test_phase8_migration_adds_nullable_all_or_none_claim_provenance() -> None:
    revision = _revision_module()
    capture = _OperationCapture()
    revision.__dict__["op"] = capture
    revision.upgrade()

    assert [
        (table_name, column.name, column.nullable) for table_name, column in capture.added_columns
    ] == [
        ("change_operation_claims", "evidence_revision_id", True),
        ("change_operation_claims", "evidence_revision_number", True),
        ("change_operation_claims", "evidence_statement_sha256", True),
    ]
    assert len(capture.added_check_constraints) == 1
    name, table_name, condition = capture.added_check_constraints[0]
    assert name == "ck_change_operation_claims_evidence_provenance_complete"
    assert table_name == "change_operation_claims"
    normalized = " ".join(condition.split())
    assert "evidence_revision_id IS NULL" in normalized
    assert "evidence_revision_number IS NULL" in normalized
    assert "evidence_statement_sha256 IS NULL" in normalized
    assert "evidence_revision_number IS NOT NULL" in normalized
    assert "evidence_statement_sha256 IS NOT NULL" in normalized
    assert "evidence_revision_number > 0" in normalized
    assert "^[0-9a-f]{64}$" in normalized

    claim_table = change_studio_models.ChangeClaimModel.__table__
    for column_name in (
        "evidence_revision_id",
        "evidence_revision_number",
        "evidence_statement_sha256",
    ):
        assert claim_table.c[column_name].nullable
    registered_constraint = next(
        value
        for value in claim_table.constraints
        if isinstance(value, CheckConstraint)
        and value.name == "ck_change_operation_claims_evidence_provenance_complete"
    )
    registered_condition = str(
        registered_constraint.sqltext.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert " ".join(registered_condition.split()) == normalized


def test_application_stage_and_outcome_have_a_database_consistency_guard() -> None:
    table = _phase_tables()["application_records"]
    constraint = next(
        value
        for value in table.constraints
        if isinstance(value, CheckConstraint)
        and value.name == "ck_application_records_stage_outcome_consistent"
    )
    compiled = str(
        constraint.sqltext.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    normalized = " ".join(compiled.split())
    assert "stage = 'offer' AND outcome_status = 'offer'" in normalized
    assert "stage = 'rejected' AND outcome_status = 'rejected'" in normalized
    assert "stage = 'withdrawn' AND outcome_status = 'withdrawn'" in normalized
    assert "stage NOT IN ('offer','rejected','withdrawn')" in normalized
    assert "outcome_status = 'none'" in normalized


def test_child_history_indexes_cover_owner_parent_and_page_anchor() -> None:
    expected = {
        "application_tasks": {
            "ix_application_tasks_application_due": (
                "owner_user_id",
                "application_id",
                "due_at",
                "created_at",
                "id",
            ),
        },
        "application_notes": {
            "ix_application_notes_application_created": (
                "owner_user_id",
                "application_id",
                "created_at",
                "id",
            ),
        },
        "application_events": {
            "ix_application_events_application_occurred": (
                "owner_user_id",
                "application_id",
                "occurred_at",
                "id",
            ),
            "ix_application_events_application_kind": (
                "owner_user_id",
                "application_id",
                "event_kind",
            ),
        },
        "application_packs": {
            "ix_application_packs_application_created": (
                "owner_user_id",
                "application_id",
                "created_at",
                "id",
            ),
        },
    }
    tables = _phase_tables()
    for table_name, indexes in expected.items():
        actual = {index.name: tuple(index.columns.keys()) for index in tables[table_name].indexes}
        for index_name, columns in indexes.items():
            assert actual[index_name] == columns
