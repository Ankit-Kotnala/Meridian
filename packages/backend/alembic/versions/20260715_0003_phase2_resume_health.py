"""Add Phase 2 resume ingestion, processing, canonical, and health data.

Revision ID: 20260715_0003
Revises: 20260715_0002
Create Date: 2026-07-15 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("guest_session_id", sa.Uuid(), nullable=True),
    ]


def _owner_constraints(table: str) -> list[sa.Constraint]:
    constraint_table = {
        "resume_processing_jobs": "resume_jobs",
        "resume_object_cleanups": "resume_cleanups",
        "canonical_resume_snapshots": "canonical_snapshots",
        "resume_health_analyses": "health_analyses",
    }.get(table, table)
    return [
        sa.CheckConstraint(
            "(owner_user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)",
            name=f"ck_{constraint_table}_owner_exactly_one",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=f"fk_{constraint_table}_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guest_session_id"],
            ["guest_resume_sessions.id"],
            name=f"fk_{constraint_table}_guest_session_id_guest_resume_sessions",
            ondelete="CASCADE",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "guest_resume_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("capability_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_document_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["claimed_by_user_id"],
            ["users.id"],
            name="fk_guest_resume_sessions_claimed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guest_resume_sessions"),
    )

    op.create_table(
        "resume_uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("expected_media_type", sa.String(length=100), nullable=False),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("staging_object_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("staging_cleaned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_document_id", sa.Uuid(), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        *_owner_constraints("resume_uploads"),
        sa.CheckConstraint(
            "status IN ('issued','finalized','rejected','expired','deleted')",
            name="ck_resume_uploads_status_valid",
        ),
        sa.CheckConstraint("expected_size > 0", name="ck_resume_uploads_expected_size_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_resume_uploads"),
        sa.UniqueConstraint("staging_object_key", name="uq_resume_uploads_staging_object_key"),
    )
    op.create_index(
        "ix_resume_uploads_owner_user_created",
        "resume_uploads",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_resume_uploads_guest_created",
        "resume_uploads",
        ["guest_session_id", "created_at"],
    )
    op.create_index(
        "ix_resume_uploads_staging_cleanup",
        "resume_uploads",
        ["expires_at", "staging_cleaned_at", "status"],
    )

    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("quarantine_object_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("malware_status", sa.String(length=16), nullable=False),
        sa.Column("content_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("source_documents"),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["resume_uploads.id"],
            name="fk_source_documents_upload_id_resume_uploads",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('quarantined','processing','ready','rejected','failed',"
            "'deleting','deleted')",
            name="ck_source_documents_status_valid",
        ),
        sa.CheckConstraint(
            "malware_status IN ('pending','clean','infected','unavailable')",
            name="ck_source_documents_malware_status_valid",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_source_documents_size_positive"),
        sa.CheckConstraint("version > 0", name="ck_source_documents_version_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_source_documents"),
        sa.UniqueConstraint("upload_id", name="uq_source_documents_upload_id"),
        sa.UniqueConstraint(
            "quarantine_object_key", name="uq_source_documents_quarantine_object_key"
        ),
    )
    op.create_index(
        "ix_source_documents_owner_status",
        "source_documents",
        ["owner_user_id", "status"],
    )
    op.create_index(
        "ix_source_documents_guest_status",
        "source_documents",
        ["guest_session_id", "status"],
    )
    op.create_foreign_key(
        "fk_resume_uploads_finalized_document_id_source_documents",
        "resume_uploads",
        "source_documents",
        ["finalized_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_guest_resume_sessions_claimed_document_id_source_documents",
        "guest_resume_sessions",
        "source_documents",
        ["claimed_document_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "document_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("document_artifacts"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["source_documents.id"],
            name="fk_document_artifacts_document_id_source_documents",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('plain_text','reading_order')", name="ck_document_artifacts_kind_valid"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_document_artifacts_size_nonnegative"),
        sa.PrimaryKeyConstraint("id", name="pk_document_artifacts"),
        sa.UniqueConstraint("document_id", "kind", name="uq_document_artifacts_document_kind"),
        sa.UniqueConstraint("object_key", name="uq_document_artifacts_object_key"),
    )

    op.create_table(
        "resume_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("retryable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_id", sa.Uuid(), nullable=True),
        sa.Column("input_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("execution_token_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_attempts", sa.Integer(), nullable=False),
        sa.Column("max_recovery_attempts", sa.Integer(), nullable=False),
        sa.Column("next_recovery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("resume_processing_jobs"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["source_documents.id"],
            name="fk_resume_processing_jobs_document_id_source_documents",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('parse','analyze','delete')", name="ck_resume_processing_jobs_kind_valid"
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','dead_lettered')",
            name="ck_resume_processing_jobs_status_valid",
        ),
        sa.CheckConstraint(
            "stage IN ('queued','admission','malware_scan','extraction','canonicalization',"
            "'analysis','complete','cleanup')",
            name="ck_resume_processing_jobs_stage_valid",
        ),
        sa.CheckConstraint(
            "progress IS NULL OR (progress >= 0 AND progress <= 100)",
            name="ck_resume_processing_jobs_progress_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0",
            name="ck_resume_processing_jobs_attempts_valid",
        ),
        sa.CheckConstraint(
            "recovery_attempts >= 0 AND max_recovery_attempts > 0 "
            "AND recovery_attempts <= max_recovery_attempts",
            name="ck_resume_processing_jobs_recovery_attempts_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_resume_processing_jobs_version_positive"),
        sa.CheckConstraint(
            "(execution_token_hash IS NULL) = (lease_expires_at IS NULL)",
            name="ck_resume_processing_jobs_execution_lease_pair",
        ),
        sa.CheckConstraint(
            "(status = 'running') = (execution_token_hash IS NOT NULL)",
            name="ck_resume_processing_jobs_running_requires_execution_lease",
        ),
        sa.CheckConstraint(
            "execution_token_hash IS NULL OR octet_length(execution_token_hash) = 32",
            name="ck_resume_processing_jobs_execution_token_hash_length",
        ),
        sa.CheckConstraint(
            "(kind = 'analyze') = (input_snapshot_id IS NOT NULL)",
            name="ck_resume_processing_jobs_analysis_snapshot_required",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_processing_jobs"),
    )
    op.create_index(
        "uq_resume_processing_jobs_user_idempotency",
        "resume_processing_jobs",
        ["owner_user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_resume_processing_jobs_guest_idempotency",
        "resume_processing_jobs",
        ["guest_session_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("guest_session_id IS NOT NULL"),
    )
    op.create_index(
        "ix_resume_processing_jobs_status_created",
        "resume_processing_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_resume_processing_jobs_document_status",
        "resume_processing_jobs",
        ["document_id", "status"],
    )
    op.create_index(
        "ix_resume_processing_jobs_lease",
        "resume_processing_jobs",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_resume_processing_jobs_recovery",
        "resume_processing_jobs",
        ["status", "next_recovery_at"],
    )

    op.create_table(
        "resume_processing_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=120), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["resume_processing_jobs.id"],
            name="fk_resume_processing_outbox_job_id_resume_processing_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_processing_outbox"),
        sa.CheckConstraint(
            "generation >= 0 AND attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_resume_processing_outbox_attempts_valid",
        ),
        sa.CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="ck_resume_processing_outbox_terminal_state_valid",
        ),
        sa.UniqueConstraint(
            "job_id",
            "task_name",
            "generation",
            name="uq_resume_processing_outbox_job_task_generation",
        ),
    )
    op.create_index(
        "ix_resume_processing_outbox_pending",
        "resume_processing_outbox",
        ["published_at", "dead_lettered_at", "next_attempt_at"],
    )

    op.create_table(
        "resume_object_cleanups",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("resume_object_cleanups"),
        sa.CheckConstraint(
            "purpose IN ('claim_compensation','claim_source','upload_staging_backstop',"
            "'upload_quarantine_cleanup')",
            name="ck_resume_object_cleanups_purpose_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_resume_object_cleanups_attempts_valid",
        ),
        sa.CheckConstraint(
            "num_nonnulls(completed_at, cancelled_at, dead_lettered_at) <= 1",
            name="ck_resume_object_cleanups_terminal_state_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_object_cleanups"),
    )
    op.create_index(
        "ix_resume_object_cleanups_due",
        "resume_object_cleanups",
        ["completed_at", "cancelled_at", "dead_lettered_at", "not_before"],
    )
    op.create_index(
        "ix_resume_object_cleanups_owner",
        "resume_object_cleanups",
        ["owner_user_id", "created_at"],
    )

    op.create_table(
        "canonical_resume_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("canonical_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plain_text_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("based_on_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("corrected_by_user", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("canonical_resume_snapshots"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["source_documents.id"],
            name="fk_canonical_resume_snapshots_document_id_source_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["based_on_snapshot_id"],
            ["canonical_resume_snapshots.id"],
            name="fk_canonical_snapshots_based_on_snapshot",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("revision > 0", name="ck_canonical_resume_snapshots_revision_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_canonical_resume_snapshots"),
        sa.UniqueConstraint(
            "document_id", "revision", name="uq_canonical_resume_document_revision"
        ),
    )
    op.create_index(
        "ix_canonical_resume_owner_document",
        "canonical_resume_snapshots",
        ["owner_user_id", "document_id"],
    )
    op.create_index(
        "ix_canonical_resume_guest_document",
        "canonical_resume_snapshots",
        ["guest_session_id", "document_id"],
    )
    op.create_foreign_key(
        "fk_resume_jobs_input_snapshot_canonical_snapshots",
        "resume_processing_jobs",
        "canonical_resume_snapshots",
        ["input_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "resume_health_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("configuration_version", sa.String(length=80), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False),
        sa.Column("feature_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feature_set_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("raw_score_basis_points", sa.Integer(), nullable=True),
        sa.Column("display_score", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("resume_health_analyses"),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["resume_processing_jobs.id"],
            name="fk_resume_health_analyses_job_id_resume_processing_jobs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["source_documents.id"],
            name="fk_resume_health_analyses_document_id_source_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["canonical_resume_snapshots.id"],
            name="fk_health_analyses_snapshot_canonical_snapshots",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded','insufficient_data')",
            name="ck_resume_health_analyses_status_valid",
        ),
        sa.CheckConstraint(
            "raw_score_basis_points IS NULL OR "
            "(raw_score_basis_points >= 0 AND raw_score_basis_points <= 10000)",
            name="ck_resume_health_analyses_raw_score_valid",
        ),
        sa.CheckConstraint(
            "display_score IS NULL OR (display_score >= 0 AND display_score <= 100)",
            name="ck_resume_health_analyses_display_score_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(feature_values) = 'object'",
            name="ck_resume_health_analyses_feature_values_object",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_health_analyses"),
        sa.UniqueConstraint("job_id", name="uq_resume_health_analyses_job_id"),
        sa.UniqueConstraint("snapshot_id", name="uq_resume_health_analyses_snapshot_id"),
    )
    op.create_index(
        "ix_resume_health_analyses_owner_document",
        "resume_health_analyses",
        ["owner_user_id", "document_id"],
    )
    op.create_index(
        "ix_resume_health_analyses_guest_document",
        "resume_health_analyses",
        ["guest_session_id", "document_id"],
    )

    op.create_table(
        "resume_health_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=False),
        sa.Column("contribution_basis_points", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_health_analyses.id"],
            name="fk_resume_health_components_analysis_id_resume_health_analyses",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "weight_basis_points > 0 AND weight_basis_points <= 10000",
            name="ck_resume_health_components_weight_valid",
        ),
        sa.CheckConstraint(
            "score_basis_points >= 0 AND score_basis_points <= 10000",
            name="ck_resume_health_components_score_valid",
        ),
        sa.CheckConstraint(
            "contribution_basis_points >= 0 AND contribution_basis_points <= 10000",
            name="ck_resume_health_components_contribution_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_health_components"),
        sa.UniqueConstraint(
            "analysis_id", "code", name="uq_resume_health_components_analysis_code"
        ),
    )

    op.create_table(
        "resume_health_feature_contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("component_code", sa.String(length=64), nullable=False),
        sa.Column("feature_code", sa.String(length=80), nullable=False),
        sa.Column("feature_value_basis_points", sa.Integer(), nullable=False),
        sa.Column("weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("contribution_basis_points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_health_analyses.id"],
            name="fk_health_feature_contributions_analysis",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "feature_value_basis_points >= 0 AND feature_value_basis_points <= 10000",
            name="ck_resume_health_feature_contributions_feature_value_valid",
        ),
        sa.CheckConstraint(
            "weight_basis_points > 0 AND weight_basis_points <= 10000",
            name="ck_resume_health_feature_contributions_weight_valid",
        ),
        sa.CheckConstraint(
            "contribution_basis_points >= 0 AND contribution_basis_points <= 10000",
            name="ck_resume_health_feature_contributions_contribution_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_health_feature_contributions"),
        sa.UniqueConstraint(
            "analysis_id",
            "component_code",
            "feature_code",
            name="uq_health_feature_contributions_analysis_component_feature",
        ),
    )
    op.create_index(
        "ix_resume_health_feature_contributions_analysis_component",
        "resume_health_feature_contributions",
        ["analysis_id", "component_code"],
    )

    op.create_table(
        "resume_health_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("component_code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("quick_win", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_health_analyses.id"],
            name="fk_resume_health_findings_analysis_id_resume_health_analyses",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_resume_health_findings_severity_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_health_findings"),
        sa.UniqueConstraint("analysis_id", "code", name="uq_resume_health_findings_analysis_code"),
    )
    op.create_index(
        "ix_resume_health_findings_analysis_sort",
        "resume_health_findings",
        ["analysis_id", "sort_order"],
    )

    op.create_table(
        "resume_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_owner_columns(),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_owner_constraints("resume_audit_events"),
        sa.CheckConstraint(
            "outcome IN ('accepted','succeeded','failed','cancelled')",
            name="ck_resume_audit_events_outcome_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resume_audit_events"),
    )
    op.create_index(
        "ix_resume_audit_events_owner_created",
        "resume_audit_events",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_resume_audit_events_guest_created",
        "resume_audit_events",
        ["guest_session_id", "created_at"],
    )
    op.create_index(
        "ix_resume_audit_events_resource",
        "resume_audit_events",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_audit_events_resource", table_name="resume_audit_events")
    op.drop_index("ix_resume_audit_events_guest_created", table_name="resume_audit_events")
    op.drop_index("ix_resume_audit_events_owner_created", table_name="resume_audit_events")
    op.drop_table("resume_audit_events")
    op.drop_index("ix_resume_health_findings_analysis_sort", table_name="resume_health_findings")
    op.drop_table("resume_health_findings")
    op.drop_index(
        "ix_resume_health_feature_contributions_analysis_component",
        table_name="resume_health_feature_contributions",
    )
    op.drop_table("resume_health_feature_contributions")
    op.drop_table("resume_health_components")
    op.drop_index("ix_resume_health_analyses_guest_document", table_name="resume_health_analyses")
    op.drop_index("ix_resume_health_analyses_owner_document", table_name="resume_health_analyses")
    op.drop_table("resume_health_analyses")
    op.drop_constraint(
        "fk_resume_jobs_input_snapshot_canonical_snapshots",
        "resume_processing_jobs",
        type_="foreignkey",
    )
    op.drop_index("ix_canonical_resume_guest_document", table_name="canonical_resume_snapshots")
    op.drop_index("ix_canonical_resume_owner_document", table_name="canonical_resume_snapshots")
    op.drop_table("canonical_resume_snapshots")
    op.drop_index("ix_resume_processing_outbox_pending", table_name="resume_processing_outbox")
    op.drop_table("resume_processing_outbox")
    op.drop_index("ix_resume_object_cleanups_owner", table_name="resume_object_cleanups")
    op.drop_index("ix_resume_object_cleanups_due", table_name="resume_object_cleanups")
    op.drop_table("resume_object_cleanups")
    op.drop_index("ix_resume_processing_jobs_lease", table_name="resume_processing_jobs")
    op.drop_index("ix_resume_processing_jobs_recovery", table_name="resume_processing_jobs")
    op.drop_index("ix_resume_processing_jobs_document_status", table_name="resume_processing_jobs")
    op.drop_index("ix_resume_processing_jobs_status_created", table_name="resume_processing_jobs")
    op.drop_index(
        "uq_resume_processing_jobs_guest_idempotency", table_name="resume_processing_jobs"
    )
    op.drop_index("uq_resume_processing_jobs_user_idempotency", table_name="resume_processing_jobs")
    op.drop_table("resume_processing_jobs")
    op.drop_table("document_artifacts")
    op.drop_constraint(
        "fk_guest_resume_sessions_claimed_document_id_source_documents",
        "guest_resume_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_uploads_finalized_document_id_source_documents",
        "resume_uploads",
        type_="foreignkey",
    )
    op.drop_index("ix_source_documents_guest_status", table_name="source_documents")
    op.drop_index("ix_source_documents_owner_status", table_name="source_documents")
    op.drop_table("source_documents")
    op.drop_index("ix_resume_uploads_staging_cleanup", table_name="resume_uploads")
    op.drop_index("ix_resume_uploads_guest_created", table_name="resume_uploads")
    op.drop_index("ix_resume_uploads_owner_user_created", table_name="resume_uploads")
    op.drop_table("resume_uploads")
    op.drop_table("guest_resume_sessions")
