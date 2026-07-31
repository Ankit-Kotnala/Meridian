"""Forward-repair the Phase 7 object-cleanup table on drifted databases.

Revision ID: 20260726_0016
Revises: 20260726_0015
Create Date: 2026-07-26 23:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0016"
down_revision: str | None = "20260726_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "resume_export_object_cleanups"
_COLUMNS = {
    "id",
    "owner_user_id",
    "export_id",
    "attempt_fence",
    "object_key",
    "trace_id",
    "not_before",
    "attempts",
    "max_attempts",
    "last_error",
    "completed_at",
    "cancelled_at",
    "dead_lettered_at",
    "created_at",
}
_CHECK_FRAGMENTS = {
    "attempt_fence > 0",
    "attempts <= max_attempts",
    "num_nonnulls(completed_at, cancelled_at, dead_lettered_at) <= 1",
}
_FOREIGN_KEYS = {
    "fk_resume_export_object_cleanups_owner_user_id_users",
    "fk_resume_export_object_cleanups_owner_export",
}
_UNIQUES = {
    "uq_resume_export_object_cleanups_owner_id",
    "uq_resume_export_object_cleanups_owner_export_fence",
}
_INDEXES = {
    "ix_resume_export_object_cleanups_due",
    "ix_resume_export_object_cleanups_owner",
}


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table(_TABLE):
        _require_complete_existing_table(inspector)
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_fence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_fence > 0",
            name="ck_resume_export_object_cleanups_attempt_fence_positive",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts",
            name="ck_resume_export_object_cleanups_attempts_valid",
        ),
        sa.CheckConstraint(
            "num_nonnulls(completed_at, cancelled_at, dead_lettered_at) <= 1",
            name="ck_resume_export_object_cleanups_terminal_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_export_object_cleanups_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_export_object_cleanups_owner_export",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_resume_export_object_cleanups",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_resume_export_object_cleanups_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "export_id",
            "attempt_fence",
            name="uq_resume_export_object_cleanups_owner_export_fence",
        ),
    )
    op.create_index(
        "ix_resume_export_object_cleanups_due",
        _TABLE,
        ["not_before", "created_at"],
        postgresql_where=sa.text(
            "completed_at IS NULL AND cancelled_at IS NULL AND dead_lettered_at IS NULL"
        ),
    )
    op.create_index(
        "ix_resume_export_object_cleanups_owner",
        _TABLE,
        ["owner_user_id", "created_at"],
    )


def downgrade() -> None:
    # This revision repairs drift against schema owned by 0013. Dropping the
    # table here would corrupt a correct 0015 database, so downgrade is a no-op.
    return


def _require_complete_existing_table(inspector: sa.Inspector) -> None:
    columns = {item["name"] for item in inspector.get_columns(_TABLE)}
    check_definitions = " ".join(
        str(item.get("sqltext", "")).casefold() for item in inspector.get_check_constraints(_TABLE)
    )
    foreign_keys = {item["name"] for item in inspector.get_foreign_keys(_TABLE)}
    uniques = {item["name"] for item in inspector.get_unique_constraints(_TABLE)}
    indexes = {item["name"] for item in inspector.get_indexes(_TABLE)}
    differences = {
        "columns": sorted(_COLUMNS - columns),
        "checks": sorted(
            fragment for fragment in _CHECK_FRAGMENTS if fragment not in check_definitions
        ),
        "foreignKeys": sorted(_FOREIGN_KEYS - foreign_keys),
        "uniques": sorted(_UNIQUES - uniques),
        "indexes": sorted(_INDEXES - indexes),
    }
    missing = {key: value for key, value in differences.items() if value}
    if missing:
        raise RuntimeError(
            f"Phase 7 cleanup schema exists but is incomplete; manual review is required: {missing}"
        )
