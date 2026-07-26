"""Add durable, fenced cleanup for private resume export objects.

Revision ID: 20260726_0013
Revises: 20260726_0012
Create Date: 2026-07-26 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0013"
down_revision: str | None = "20260726_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPORT_STATUSES = (
    "pending",
    "rendering",
    "retry_wait",
    "verified",
    "blocked",
    "failed",
    "dead_lettered",
    "deletion_pending",
    "deleting",
    "deletion_retry_wait",
    "deletion_dead_lettered",
    "deleted",
)
_AUDIT_ACTIONS = (
    "resume_created",
    "resume_updated",
    "version_created",
    "version_restored",
    "export_requested",
    "export_verified",
    "export_blocked",
    "export_retry_scheduled",
    "export_dead_lettered",
    "export_dispatched",
    "export_dispatch_retry_scheduled",
    "export_dispatch_dead_lettered",
    "export_recovery_scheduled",
    "export_deletion_requested",
    "export_deletion_retry_scheduled",
    "export_deletion_dead_lettered",
    "export_deletion_recovery_scheduled",
    "download_intent_created",
    "export_deleted",
    "export_orphan_cleanup_completed",
    "export_orphan_cleanup_retry_scheduled",
    "export_orphan_cleanup_dead_lettered",
)
_PHASE_7_VERIFIED_ACTIONS = _AUDIT_ACTIONS[:13] + _AUDIT_ACTIONS[17:19]


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    connection = op.get_bind()
    op.drop_constraint(
        "ck_resume_export_verification_reports_page_count_positive",
        "resume_export_verification_reports",
        type_="check",
    )
    op.create_check_constraint(
        "ck_resume_export_verification_reports_page_count_nonnegative",
        "resume_export_verification_reports",
        "page_count >= 0",
    )

    op.add_column(
        "resume_exports",
        sa.Column(
            "cleanup_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "resume_exports",
        sa.Column(
            "cleanup_max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )
    op.alter_column("resume_exports", "cleanup_attempts", server_default=None)
    op.alter_column("resume_exports", "cleanup_max_attempts", server_default=None)
    op.create_check_constraint(
        "ck_resume_exports_cleanup_attempts_nonnegative",
        "resume_exports",
        "cleanup_attempts >= 0",
    )
    op.create_check_constraint(
        "ck_resume_exports_cleanup_max_attempts_valid",
        "resume_exports",
        "cleanup_max_attempts BETWEEN 1 AND 10",
    )

    op.add_column(
        "resume_export_outbox",
        sa.Column(
            "operation",
            sa.String(16),
            nullable=False,
            server_default="render",
        ),
    )
    op.alter_column("resume_export_outbox", "operation", server_default=None)
    op.create_check_constraint(
        "ck_resume_export_outbox_operation_valid",
        "resume_export_outbox",
        "operation IN ('render','delete')",
    )
    op.drop_index("uq_resume_export_outbox_active", table_name="resume_export_outbox")
    op.create_index(
        "uq_resume_export_outbox_active",
        "resume_export_outbox",
        ["owner_user_id", "export_id", "operation"],
        unique=True,
        postgresql_where=sa.text("published_at IS NULL AND dead_lettered_at IS NULL"),
    )

    op.create_table(
        "resume_export_object_cleanups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_fence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(80)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True)),
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
        sa.PrimaryKeyConstraint("id", name="pk_resume_export_object_cleanups"),
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
        "resume_export_object_cleanups",
        ["not_before", "created_at"],
        postgresql_where=sa.text(
            "completed_at IS NULL AND cancelled_at IS NULL AND dead_lettered_at IS NULL"
        ),
    )
    op.create_index(
        "ix_resume_export_object_cleanups_owner",
        "resume_export_object_cleanups",
        ["owner_user_id", "created_at"],
    )

    op.drop_constraint("ck_resume_exports_status_valid", "resume_exports", type_="check")
    op.create_check_constraint(
        "ck_resume_exports_status_valid",
        "resume_exports",
        f"status IN ({_values(_EXPORT_STATUSES)})",
    )
    legacy_deleted_rows = tuple(
        connection.execute(
            sa.text(
                """
                SELECT id, owner_user_id, trace_id, requested_at, max_attempts
                FROM resume_exports
                WHERE status = 'deleted'
                  AND (deleted_at IS NULL OR object_key IS NOT NULL)
                ORDER BY requested_at, id
                """
            )
        ).mappings()
    )
    if legacy_deleted_rows:
        migration_now = connection.execute(sa.text("SELECT CURRENT_TIMESTAMP")).scalar_one()
        connection.execute(
            sa.text(
                """
                UPDATE resume_exports
                SET status = 'deletion_pending',
                    deleted_at = NULL,
                    cleanup_attempts = 0,
                    execution_token_hash = NULL,
                    lease_expires_at = NULL,
                    retry_at = NULL,
                    dead_lettered_at = NULL,
                    last_error = 'migration_recovered_unverified_deletion'
                WHERE status = 'deleted'
                  AND (deleted_at IS NULL OR object_key IS NOT NULL)
                """
            )
        )
        cleanup_outbox = sa.table(
            "resume_export_outbox",
            sa.column("id", sa.Uuid()),
            sa.column("owner_user_id", sa.Uuid()),
            sa.column("export_id", sa.Uuid()),
            sa.column("operation", sa.String()),
            sa.column("trace_id", sa.String()),
            sa.column("available_at", sa.DateTime(timezone=True)),
            sa.column("attempts", sa.Integer()),
            sa.column("max_attempts", sa.Integer()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            cleanup_outbox,
            [
                {
                    "id": uuid4(),
                    "owner_user_id": row["owner_user_id"],
                    "export_id": row["id"],
                    "operation": "delete",
                    "trace_id": row["trace_id"],
                    "available_at": migration_now,
                    "attempts": 0,
                    "max_attempts": row["max_attempts"],
                    "created_at": migration_now,
                }
                for row in legacy_deleted_rows
            ],
        )

    for constraint in (
        "ck_resume_exports_dead_letter_state_valid",
        "ck_resume_exports_retry_state_valid",
        "ck_resume_exports_rendering_requires_lease",
    ):
        op.drop_constraint(constraint, "resume_exports", type_="check")
    op.create_check_constraint(
        "ck_resume_exports_rendering_requires_lease",
        "resume_exports",
        "(status IN ('rendering','deleting') AND execution_token_hash IS NOT NULL) OR "
        "(status NOT IN ('rendering','deleting') AND execution_token_hash IS NULL)",
    )
    op.create_check_constraint(
        "ck_resume_exports_retry_state_valid",
        "resume_exports",
        "(status IN ('retry_wait','deletion_retry_wait') AND retry_at IS NOT NULL) OR "
        "(status NOT IN ('retry_wait','deletion_retry_wait') AND retry_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_resume_exports_dead_letter_state_valid",
        "resume_exports",
        "(status IN ('dead_lettered','deletion_dead_lettered') "
        "AND dead_lettered_at IS NOT NULL) OR "
        "(status NOT IN ('dead_lettered','deletion_dead_lettered') "
        "AND dead_lettered_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_resume_exports_deleted_state_valid",
        "resume_exports",
        "(status = 'deleted' AND deleted_at IS NOT NULL AND object_key IS NULL) OR "
        "(status <> 'deleted' AND deleted_at IS NULL)",
    )

    op.drop_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        f"action IN ({_values(_AUDIT_ACTIONS)})",
    )
    if legacy_deleted_rows:
        audit_table = sa.table(
            "resume_builder_audit_events",
            sa.column("id", sa.Uuid()),
            sa.column("owner_user_id", sa.Uuid()),
            sa.column("actor_user_id", sa.Uuid()),
            sa.column("action", sa.String()),
            sa.column("target_kind", sa.String()),
            sa.column("target_id", sa.Uuid()),
            sa.column("request_id", sa.String()),
            sa.column("trace_id", sa.String()),
            sa.column("metadata", postgresql.JSONB(astext_type=sa.Text())),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            audit_table,
            [
                {
                    "id": uuid4(),
                    "owner_user_id": row["owner_user_id"],
                    "actor_user_id": row["owner_user_id"],
                    "action": "export_deletion_recovery_scheduled",
                    "target_kind": "resume_export",
                    "target_id": row["id"],
                    "request_id": "migration:phase7-export-cleanup",
                    "trace_id": row["trace_id"],
                    "metadata": {
                        "reason": "legacy_deletion_state_unverified",
                        "stage": "migration",
                    },
                    "created_at": migration_now,
                }
                for row in legacy_deleted_rows
            ],
        )


def downgrade() -> None:
    connection = op.get_bind()
    cleanup_rows = connection.execute(
        sa.text(
            """
            SELECT
              (SELECT count(*) FROM resume_exports
               WHERE cleanup_attempts <> 0
                  OR status IN (
                    'deletion_pending',
                    'deleting',
                    'deletion_retry_wait',
                    'deletion_dead_lettered'
                  ))
              + (SELECT count(*) FROM resume_export_outbox WHERE operation = 'delete')
              + (SELECT count(*) FROM resume_export_object_cleanups
                 WHERE completed_at IS NULL AND cancelled_at IS NULL)
              + (SELECT count(*) FROM resume_builder_audit_events
                 WHERE action LIKE 'export_deletion_%'
                    OR action LIKE 'export_orphan_cleanup_%')
            """
        )
    ).scalar_one()
    if cleanup_rows:
        raise RuntimeError(
            "Phase 7 export-cleanup downgrade refused because durable cleanup data exists"
        )

    op.drop_constraint(
        "ck_resume_export_verification_reports_page_count_nonnegative",
        "resume_export_verification_reports",
        type_="check",
    )
    op.create_check_constraint(
        "ck_resume_export_verification_reports_page_count_positive",
        "resume_export_verification_reports",
        "page_count > 0",
    )

    op.drop_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        f"action IN ({_values(_PHASE_7_VERIFIED_ACTIONS)})",
    )

    op.drop_index(
        "ix_resume_export_object_cleanups_owner",
        table_name="resume_export_object_cleanups",
    )
    op.drop_index(
        "ix_resume_export_object_cleanups_due",
        table_name="resume_export_object_cleanups",
    )
    op.drop_table("resume_export_object_cleanups")

    for constraint in (
        "ck_resume_exports_deleted_state_valid",
        "ck_resume_exports_dead_letter_state_valid",
        "ck_resume_exports_retry_state_valid",
        "ck_resume_exports_rendering_requires_lease",
        "ck_resume_exports_status_valid",
    ):
        op.drop_constraint(constraint, "resume_exports", type_="check")
    op.create_check_constraint(
        "ck_resume_exports_status_valid",
        "resume_exports",
        "status IN ('pending','rendering','retry_wait','verified','blocked',"
        "'failed','dead_lettered','deleted')",
    )
    op.create_check_constraint(
        "ck_resume_exports_rendering_requires_lease",
        "resume_exports",
        "(status = 'rendering' AND execution_token_hash IS NOT NULL) OR "
        "(status <> 'rendering' AND execution_token_hash IS NULL)",
    )
    op.create_check_constraint(
        "ck_resume_exports_retry_state_valid",
        "resume_exports",
        "(status = 'retry_wait' AND retry_at IS NOT NULL) OR "
        "(status <> 'retry_wait' AND retry_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_resume_exports_dead_letter_state_valid",
        "resume_exports",
        "(status = 'dead_lettered' AND dead_lettered_at IS NOT NULL) OR "
        "(status <> 'dead_lettered' AND dead_lettered_at IS NULL)",
    )

    op.drop_constraint(
        "ck_resume_export_outbox_operation_valid",
        "resume_export_outbox",
        type_="check",
    )
    op.drop_index("uq_resume_export_outbox_active", table_name="resume_export_outbox")
    op.create_index(
        "uq_resume_export_outbox_active",
        "resume_export_outbox",
        ["owner_user_id", "export_id"],
        unique=True,
        postgresql_where=sa.text("published_at IS NULL AND dead_lettered_at IS NULL"),
    )
    op.drop_column("resume_export_outbox", "operation")
    op.drop_constraint(
        "ck_resume_exports_cleanup_max_attempts_valid",
        "resume_exports",
        type_="check",
    )
    op.drop_constraint(
        "ck_resume_exports_cleanup_attempts_nonnegative",
        "resume_exports",
        type_="check",
    )
    op.drop_column("resume_exports", "cleanup_max_attempts")
    op.drop_column("resume_exports", "cleanup_attempts")
