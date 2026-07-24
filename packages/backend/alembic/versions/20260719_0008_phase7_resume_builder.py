"""Add Phase 7 resume builder, version, export, and verification tables.

Revision ID: 20260719_0008
Revises: 20260719_0007
Create Date: 2026-07-19 00:08:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0008"
down_revision: str | None = "20260719_0007"
branch_labels: str | None = None
depends_on: str | None = None

_TEMPLATES = (
    "standard_professional",
    "compact_technical",
    "executive",
    "graduate",
    "consulting_finance",
)
_FORMATS = ("pdf", "docx", "text", "json")
_EXPORT_STATUSES = ("pending", "rendering", "verified", "blocked", "failed", "deleted")
_VERIFICATION_STATUSES = ("passed", "warning", "failed")
_AUDIT_ACTIONS = (
    "resume_created",
    "resume_updated",
    "version_created",
    "version_restored",
    "export_requested",
    "export_verified",
    "export_blocked",
    "download_intent_created",
    "export_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("target_role", sa.String(length=120), nullable=True),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_change_set_id", sa.Uuid(), nullable=True),
        sa.Column("source_change_set_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"template IN ({_values(_TEMPLATES)})",
            name="ck_resumes_template_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_resumes_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resumes_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resumes_owner_id"),
    )
    op.create_index("ix_resumes_owner_updated", "resumes", ["owner_user_id", "updated_at", "id"])
    op.create_index(
        "ix_resumes_owner_source_change",
        "resumes",
        ["owner_user_id", "source_change_set_id"],
    )

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("target_role", sa.String(length=120), nullable=True),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("source_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_change_set_id", sa.Uuid(), nullable=True),
        sa.Column("source_change_set_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"template IN ({_values(_TEMPLATES)})",
            name="ck_resume_versions_template_valid",
        ),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_resume_versions_version_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_versions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "resume_id"],
            ["resumes.owner_user_id", "resumes.id"],
            name="fk_resume_versions_owner_resume",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resume_versions_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "resume_id",
            "version_number",
            name="uq_resume_versions_owner_resume_number",
        ),
    )
    op.create_index(
        "ix_resume_versions_resume_number",
        "resume_versions",
        ["owner_user_id", "resume_id", "version_number"],
    )

    op.create_table(
        "resume_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column("media_type", sa.String(length=140), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_digest", sa.String(length=64), nullable=True),
        sa.Column("verification_status", sa.String(length=16), nullable=True),
        sa.Column("verification_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("critical_failures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("renderer_version", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"format IN ({_values(_FORMATS)})",
            name="ck_resume_exports_format_valid",
        ),
        sa.CheckConstraint(
            f"status IN ({_values(_EXPORT_STATUSES)})",
            name="ck_resume_exports_status_valid",
        ),
        sa.CheckConstraint(
            "verification_status IS NULL OR "
            f"verification_status IN ({_values(_VERIFICATION_STATUSES)})",
            name="ck_resume_exports_verification_status_valid",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_resume_exports_size_bytes_nonnegative"),
        sa.CheckConstraint("attempts >= 0", name="ck_resume_exports_attempts_nonnegative"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_exports_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "resume_id"],
            ["resumes.owner_user_id", "resumes.id"],
            name="fk_resume_exports_owner_resume",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_resume_exports_owner_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resume_exports_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_exports_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_resume_exports_version",
        "resume_exports",
        ["owner_user_id", "version_id", "requested_at"],
    )
    op.create_index("ix_resume_exports_status", "resume_exports", ["status", "requested_at"])

    op.create_table(
        "resume_export_verification_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("critical_failures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("detected_lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duplicate_lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reading_order", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grounding_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_values(_VERIFICATION_STATUSES)})",
            name="ck_resume_export_verification_reports_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_export_verification_reports_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_verifications_owner_export",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_resume_verifications_owner_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resume_verifications_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "export_id",
            name="uq_resume_verifications_owner_export",
        ),
    )
    op.create_index(
        "ix_resume_verifications_export",
        "resume_export_verification_reports",
        ["owner_user_id", "export_id"],
    )

    op.create_table(
        "resume_export_download_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_export_download_intents_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_download_intents_owner_export",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resume_download_intents_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_download_intents_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_resume_download_intents_export",
        "resume_export_download_intents",
        ["owner_user_id", "export_id", "created_at"],
    )
    op.create_index(
        "ix_resume_download_intents_expiry",
        "resume_export_download_intents",
        ["expires_at"],
    )

    op.create_table(
        "resume_builder_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=60), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("response_kind", sa.String(length=60), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_builder_idempotency_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_builder_idempotency_owner_key",
        ),
    )
    op.create_index(
        "ix_resume_builder_idempotency_target",
        "resume_builder_idempotency",
        ["owner_user_id", "target_kind", "target_id"],
    )

    op.create_table(
        "resume_builder_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("target_kind", sa.String(length=60), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=False),
        sa.Column("trace_id", sa.String(length=80), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"action IN ({_values(_AUDIT_ACTIONS)})",
            name="ck_resume_builder_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_resume_builder_audit_events_actor_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_resume_builder_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_resume_builder_audit_owner_id"),
    )
    op.create_index(
        "ix_resume_builder_audit_owner_created",
        "resume_builder_audit_events",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_resume_builder_audit_target",
        "resume_builder_audit_events",
        ["owner_user_id", "target_kind", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_builder_audit_target", table_name="resume_builder_audit_events")
    op.drop_index(
        "ix_resume_builder_audit_owner_created",
        table_name="resume_builder_audit_events",
    )
    op.drop_table("resume_builder_audit_events")
    op.drop_index(
        "ix_resume_builder_idempotency_target",
        table_name="resume_builder_idempotency",
    )
    op.drop_table("resume_builder_idempotency")
    op.drop_index(
        "ix_resume_download_intents_expiry",
        table_name="resume_export_download_intents",
    )
    op.drop_index(
        "ix_resume_download_intents_export",
        table_name="resume_export_download_intents",
    )
    op.drop_table("resume_export_download_intents")
    op.drop_index(
        "ix_resume_verifications_export",
        table_name="resume_export_verification_reports",
    )
    op.drop_table("resume_export_verification_reports")
    op.drop_index("ix_resume_exports_status", table_name="resume_exports")
    op.drop_index("ix_resume_exports_version", table_name="resume_exports")
    op.drop_table("resume_exports")
    op.drop_index("ix_resume_versions_resume_number", table_name="resume_versions")
    op.drop_table("resume_versions")
    op.drop_index("ix_resumes_owner_source_change", table_name="resumes")
    op.drop_index("ix_resumes_owner_updated", table_name="resumes")
    op.drop_table("resumes")
