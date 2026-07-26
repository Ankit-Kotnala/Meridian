"""Close Phase 7 structured layouts and durable verified export jobs.

Revision ID: 20260726_0012
Revises: 20260726_0011
Create Date: 2026-07-26 12:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0012"
down_revision: str | None = "20260726_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_LAYOUT = {
    "fontFamily": "sans",
    "fontSizePt": 10,
    "lineSpacing": "standard",
    "margins": "standard",
    "pageLimit": 1,
    "pageSize": "letter",
}
_EXPORT_STATUSES = (
    "pending",
    "rendering",
    "retry_wait",
    "verified",
    "blocked",
    "failed",
    "dead_lettered",
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
    "download_intent_created",
    "export_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    layout_default = sa.text(f"'{json.dumps(_DEFAULT_LAYOUT)}'::jsonb")
    empty_array = sa.text("'[]'::jsonb")

    op.add_column(
        "resumes",
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=layout_default,
        ),
    )
    op.add_column(
        "resume_versions",
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=layout_default,
        ),
    )
    op.add_column(
        "resume_versions",
        sa.Column(
            "personal_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_array,
        ),
    )
    op.add_column(
        "resume_versions",
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_array,
        ),
    )
    op.alter_column("resumes", "layout", server_default=None)
    op.alter_column("resume_versions", "layout", server_default=None)
    op.alter_column("resume_versions", "personal_facts", server_default=None)
    op.alter_column("resume_versions", "entities", server_default=None)

    op.add_column("resume_exports", sa.Column("version_content_sha256", sa.String(64)))
    op.add_column(
        "resume_exports",
        sa.Column("fidelity_manifest", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.add_column("resume_exports", sa.Column("fidelity_manifest_sha256", sa.String(64)))
    op.add_column(
        "resume_exports",
        sa.Column(
            "trace_id",
            sa.String(128),
            nullable=False,
            server_default="migration-phase7-export",
        ),
    )
    op.add_column(
        "resume_exports",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "resume_exports",
        sa.Column("fence", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("resume_exports", sa.Column("execution_token_hash", sa.String(64)))
    op.add_column(
        "resume_exports",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    )
    op.add_column("resume_exports", sa.Column("retry_at", sa.DateTime(timezone=True)))
    op.add_column(
        "resume_exports",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True)),
    )

    connection = op.get_bind()
    exports = connection.execute(
        sa.text("SELECT id, version_id FROM resume_exports ORDER BY id")
    ).mappings()
    for row in exports:
        version_digest = hashlib.sha256(
            f"legacy-resume-version:{row['version_id']}".encode()
        ).hexdigest()
        manifest = {
            "entries": [],
            "pageLimit": 2,
            "schemaVersion": "legacy-sync-export-v1",
            "template": "legacy",
            "versionContentSha256": version_digest,
            "versionId": str(row["version_id"]),
        }
        manifest_json = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            sa.text(
                """
                UPDATE resume_exports
                SET version_content_sha256 = :version_digest,
                    fidelity_manifest = CAST(:manifest AS jsonb),
                    fidelity_manifest_sha256 = :manifest_digest
                WHERE id = :export_id
                """
            ),
            {
                "export_id": row["id"],
                "manifest": manifest_json,
                "manifest_digest": hashlib.sha256(manifest_json.encode()).hexdigest(),
                "version_digest": version_digest,
            },
        )
    op.alter_column("resume_exports", "version_content_sha256", nullable=False)
    op.alter_column("resume_exports", "fidelity_manifest", nullable=False)
    op.alter_column("resume_exports", "fidelity_manifest_sha256", nullable=False)
    op.alter_column("resume_exports", "trace_id", server_default=None)
    op.alter_column("resume_exports", "max_attempts", server_default=None)
    op.alter_column("resume_exports", "fence", server_default=None)

    connection.execute(
        sa.text(
            """
            UPDATE resume_exports
            SET status = 'retry_wait',
                retry_at = CURRENT_TIMESTAMP,
                execution_token_hash = NULL,
                lease_expires_at = NULL,
                last_error = 'migration_recovered_rendering'
            WHERE status = 'rendering'
            """
        )
    )
    op.drop_constraint("ck_resume_exports_status_valid", "resume_exports", type_="check")
    op.create_check_constraint(
        "ck_resume_exports_status_valid",
        "resume_exports",
        f"status IN ({_values(_EXPORT_STATUSES)})",
    )
    op.create_check_constraint(
        "ck_resume_exports_max_attempts_valid",
        "resume_exports",
        "max_attempts BETWEEN 1 AND 10",
    )
    op.create_check_constraint(
        "ck_resume_exports_fence_nonnegative",
        "resume_exports",
        "fence >= 0",
    )
    op.create_check_constraint(
        "ck_resume_exports_execution_lease_pair",
        "resume_exports",
        "(execution_token_hash IS NULL) = (lease_expires_at IS NULL)",
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
    op.create_index(
        "ix_resume_exports_retry",
        "resume_exports",
        ["status", "retry_at"],
    )
    op.create_index(
        "ix_resume_exports_lease",
        "resume_exports",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "resume_export_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("leased_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_resume_export_outbox_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 10",
            name="ck_resume_export_outbox_max_attempts_valid",
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL AND leased_at IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_at IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_resume_export_outbox_lease_state_valid",
        ),
        sa.CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="ck_resume_export_outbox_terminal_state_exclusive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_export_outbox_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_export_outbox_owner_export",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_export_outbox"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_resume_export_outbox_owner_id",
        ),
    )
    op.create_index(
        "ix_resume_export_outbox_available",
        "resume_export_outbox",
        ["available_at", "created_at"],
        postgresql_where=sa.text(
            "published_at IS NULL AND dead_lettered_at IS NULL AND lease_token IS NULL"
        ),
    )
    op.create_index(
        "uq_resume_export_outbox_active",
        "resume_export_outbox",
        ["owner_user_id", "export_id"],
        unique=True,
        postgresql_where=sa.text("published_at IS NULL AND dead_lettered_at IS NULL"),
    )
    op.create_index(
        "ix_resume_export_outbox_lease",
        "resume_export_outbox",
        ["lease_expires_at"],
    )

    pending = connection.execute(
        sa.text(
            """
            SELECT id, owner_user_id, trace_id, requested_at, max_attempts,
                   COALESCE(retry_at, requested_at) AS available_at
            FROM resume_exports
            WHERE status IN ('pending', 'retry_wait')
            ORDER BY requested_at, id
            """
        )
    ).mappings()
    outbox_table = sa.table(
        "resume_export_outbox",
        sa.column("id", sa.Uuid()),
        sa.column("owner_user_id", sa.Uuid()),
        sa.column("export_id", sa.Uuid()),
        sa.column("trace_id", sa.String()),
        sa.column("available_at", sa.DateTime(timezone=True)),
        sa.column("attempts", sa.Integer()),
        sa.column("max_attempts", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    rows = [
        {
            "id": uuid4(),
            "owner_user_id": row["owner_user_id"],
            "export_id": row["id"],
            "trace_id": row["trace_id"],
            "available_at": row["available_at"],
            "attempts": 0,
            "max_attempts": row["max_attempts"],
            "created_at": row["requested_at"],
        }
        for row in pending
    ]
    if rows:
        op.bulk_insert(outbox_table, rows)

    op.add_column(
        "resume_export_verification_reports",
        sa.Column(
            "occurrence_mismatches",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_array,
        ),
    )
    op.add_column(
        "resume_export_verification_reports",
        sa.Column(
            "reading_order_failures",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_array,
        ),
    )
    op.add_column(
        "resume_export_verification_reports",
        sa.Column("manifest_sha256", sa.String(64)),
    )
    op.add_column(
        "resume_export_verification_reports",
        sa.Column("version_content_sha256", sa.String(64)),
    )
    op.add_column(
        "resume_export_verification_reports",
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
    )
    connection.execute(
        sa.text(
            """
            UPDATE resume_export_verification_reports AS report
            SET manifest_sha256 = export.fidelity_manifest_sha256,
                version_content_sha256 = export.version_content_sha256
            FROM resume_exports AS export
            WHERE export.owner_user_id = report.owner_user_id
              AND export.id = report.export_id
            """
        )
    )
    op.alter_column(
        "resume_export_verification_reports",
        "occurrence_mismatches",
        server_default=None,
    )
    op.alter_column(
        "resume_export_verification_reports",
        "reading_order_failures",
        server_default=None,
    )
    op.alter_column(
        "resume_export_verification_reports",
        "manifest_sha256",
        nullable=False,
    )
    op.alter_column(
        "resume_export_verification_reports",
        "version_content_sha256",
        nullable=False,
    )
    op.alter_column(
        "resume_export_verification_reports",
        "page_count",
        server_default=None,
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
        f"action IN ({_values(_AUDIT_ACTIONS)})",
    )


def downgrade() -> None:
    connection = op.get_bind()
    owned_rows = connection.execute(
        sa.text(
            """
            SELECT
              (SELECT count(*) FROM resumes)
              + (SELECT count(*) FROM resume_exports)
              + (SELECT count(*) FROM resume_export_outbox)
            """
        )
    ).scalar_one()
    if owned_rows:
        raise RuntimeError(
            "Phase 7 durable-export downgrade refused because immutable resume data exists"
        )

    op.drop_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_resume_builder_audit_events_action_valid",
        "resume_builder_audit_events",
        "action IN ('resume_created','resume_updated','version_created',"
        "'version_restored','export_requested','export_verified','export_blocked',"
        "'download_intent_created','export_deleted')",
    )

    op.drop_constraint(
        "ck_resume_export_verification_reports_page_count_positive",
        "resume_export_verification_reports",
        type_="check",
    )
    for column in (
        "page_count",
        "version_content_sha256",
        "manifest_sha256",
        "reading_order_failures",
        "occurrence_mismatches",
    ):
        op.drop_column("resume_export_verification_reports", column)

    op.drop_index("ix_resume_export_outbox_lease", table_name="resume_export_outbox")
    op.drop_index("uq_resume_export_outbox_active", table_name="resume_export_outbox")
    op.drop_index("ix_resume_export_outbox_available", table_name="resume_export_outbox")
    op.drop_table("resume_export_outbox")

    op.drop_index("ix_resume_exports_lease", table_name="resume_exports")
    op.drop_index("ix_resume_exports_retry", table_name="resume_exports")
    for constraint in (
        "ck_resume_exports_dead_letter_state_valid",
        "ck_resume_exports_retry_state_valid",
        "ck_resume_exports_rendering_requires_lease",
        "ck_resume_exports_execution_lease_pair",
        "ck_resume_exports_fence_nonnegative",
        "ck_resume_exports_max_attempts_valid",
    ):
        op.drop_constraint(constraint, "resume_exports", type_="check")
    op.drop_constraint("ck_resume_exports_status_valid", "resume_exports", type_="check")
    op.create_check_constraint(
        "ck_resume_exports_status_valid",
        "resume_exports",
        "status IN ('pending','rendering','verified','blocked','failed','deleted')",
    )
    for column in (
        "dead_lettered_at",
        "retry_at",
        "lease_expires_at",
        "execution_token_hash",
        "fence",
        "max_attempts",
        "trace_id",
        "fidelity_manifest_sha256",
        "fidelity_manifest",
        "version_content_sha256",
    ):
        op.drop_column("resume_exports", column)

    for column in ("entities", "personal_facts", "layout"):
        op.drop_column("resume_versions", column)
    op.drop_column("resumes", "layout")
