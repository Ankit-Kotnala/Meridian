"""Add Phase 3 owned career profile, evidence vault, and achievement records.

Revision ID: 20260715_0004
Revises: 20260715_0003
Create Date: 2026-07-15 00:00:02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0004"
down_revision: str | None = "20260715_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("professional_headline", sa.String(length=240), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("work_authorization", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_career_profiles_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_profiles_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_profiles"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_profiles_owner_id"),
        sa.UniqueConstraint("owner_user_id", name="uq_career_profiles_owner_user_id"),
    )
    op.create_table(
        "career_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("organization", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("official_title", sa.String(length=300), nullable=True),
        sa.Column("display_title", sa.String(length=300), nullable=True),
        sa.Column("employment_type", sa.String(length=24), nullable=True),
        sa.Column("location", sa.String(length=240), nullable=True),
        sa.Column("external_url", sa.String(length=2048), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("start_month", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("end_month", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "employment_type IS NULL OR employment_type IN "
            "('full_time','part_time','contract','internship','temporary','volunteer','other')",
            name="ck_career_entities_employment_type_valid",
        ),
        sa.CheckConstraint(
            "external_url IS NULL OR external_url LIKE 'http://%' OR external_url LIKE 'https://%'",
            name="ck_career_entities_external_url_http",
        ),
        sa.CheckConstraint(
            "kind = 'experience' OR employment_type IS NULL",
            name="ck_career_entities_employment_type_experience_only",
        ),
        sa.CheckConstraint(
            "kind IN ('experience','education','project','credential','publication',"
            "'award','volunteering','language','portfolio_link')",
            name="ck_career_entities_kind_valid",
        ),
        sa.CheckConstraint(
            "NOT is_current OR end_year IS NULL",
            name="ck_career_entities_current_has_no_end",
        ),
        sa.CheckConstraint(
            "end_month IS NULL OR (end_year IS NOT NULL AND end_month BETWEEN 1 AND 12)",
            name="ck_career_entities_end_month_valid",
        ),
        sa.CheckConstraint(
            "end_year IS NULL OR (end_year BETWEEN 1900 AND 2200)",
            name="ck_career_entities_end_year_valid",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_career_entities_sort_order_nonnegative"),
        sa.CheckConstraint(
            "start_month IS NULL OR (start_year IS NOT NULL AND start_month BETWEEN 1 AND 12)",
            name="ck_career_entities_start_month_valid",
        ),
        sa.CheckConstraint(
            "start_year IS NULL OR (start_year BETWEEN 1900 AND 2200)",
            name="ck_career_entities_start_year_valid",
        ),
        sa.CheckConstraint(
            "start_year IS NULL OR end_year IS NULL OR "
            "(end_year * 12 + COALESCE(end_month, 12)) >= "
            "(start_year * 12 + COALESCE(start_month, 1))",
            name="ck_career_entities_date_order_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_career_entities_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_entities_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_entities_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_entities"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_entities_owner_id"),
    )
    op.create_index(
        "ix_career_entities_owner_profile_order",
        "career_entities",
        ["owner_user_id", "profile_id", "sort_order", "id"],
    )
    op.create_table(
        "career_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("name_normalized", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("proficiency", sa.String(length=24), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "proficiency IS NULL OR proficiency IN ('beginner','intermediate','advanced','expert')",
            name="ck_career_skills_proficiency_valid",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_career_skills_sort_order_nonnegative"),
        sa.CheckConstraint("version > 0", name="ck_career_skills_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_skills_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_skills_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_skills"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_skills_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "profile_id",
            "name_normalized",
            name="uq_career_skills_owner_name",
        ),
    )
    op.create_index(
        "ix_career_skills_owner_profile_order",
        "career_skills",
        ["owner_user_id", "profile_id", "sort_order", "id"],
    )
    op.create_table(
        "career_entity_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_skills_owner_entity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_entity_skills_owner_skill",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_entity_skills_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_entity_skills"),
        sa.UniqueConstraint(
            "owner_user_id",
            "entity_id",
            "skill_id",
            name="uq_career_entity_skills_pair",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_entity_skills_owner_id"),
    )
    op.create_index(
        "ix_career_entity_skills_owner_entity",
        "career_entity_skills",
        ["owner_user_id", "entity_id"],
    )
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle", sa.String(length=16), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "lifecycle IN ('active','archived','deleted')",
            name="ck_evidence_items_lifecycle_valid",
        ),
        sa.CheckConstraint(
            "current_revision > 0",
            name="ck_evidence_items_current_revision_positive",
        ),
        sa.CheckConstraint("version > 0", name="ck_evidence_items_version_positive"),
        sa.CheckConstraint(
            "(lifecycle = 'active' AND archived_at IS NULL AND deleted_at IS NULL) OR "
            "(lifecycle = 'archived' AND archived_at IS NOT NULL "
            "AND deleted_at IS NULL) OR "
            "(lifecycle = 'deleted' AND deleted_at IS NOT NULL)",
            name="ck_evidence_items_lifecycle_timestamps_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_items_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_items"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_items_owner_id"),
    )
    op.create_index(
        "ix_evidence_items_owner_lifecycle_created",
        "evidence_items",
        ["owner_user_id", "lifecycle", "created_at", "id"],
    )
    op.create_table(
        "evidence_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("organization", sa.String(length=300), nullable=True),
        sa.Column("project", sa.String(length=300), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("start_month", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("end_month", sa.Integer(), nullable=True),
        sa.Column("strength", sa.String(length=16), nullable=False),
        sa.Column("input_kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('resume_statement','achievement','metric','project',"
            "'credential','publication','award','review_excerpt','portfolio',"
            "'testimonial','support_document','note')",
            name="ck_evidence_revisions_type_valid",
        ),
        sa.CheckConstraint(
            "input_kind IN ('manual','parser','exact_source_span','achievement','material_edit')",
            name="ck_evidence_revisions_input_kind_valid",
        ),
        sa.CheckConstraint(
            "strength IN ('verified','confirmed','supported','inferred','unsupported')",
            name="ck_evidence_revisions_strength_valid",
        ),
        sa.CheckConstraint(
            "end_month IS NULL OR (end_year IS NOT NULL AND end_month BETWEEN 1 AND 12)",
            name="ck_evidence_revisions_end_month_valid",
        ),
        sa.CheckConstraint(
            "end_year IS NULL OR (end_year BETWEEN 1900 AND 2200)",
            name="ck_evidence_revisions_end_year_valid",
        ),
        sa.CheckConstraint("revision > 0", name="ck_evidence_revisions_revision_positive"),
        sa.CheckConstraint(
            "start_month IS NULL OR (start_year IS NOT NULL AND start_month BETWEEN 1 AND 12)",
            name="ck_evidence_revisions_start_month_valid",
        ),
        sa.CheckConstraint(
            "start_year IS NULL OR (start_year BETWEEN 1900 AND 2200)",
            name="ck_evidence_revisions_start_year_valid",
        ),
        sa.CheckConstraint(
            "start_year IS NULL OR end_year IS NULL OR "
            "(end_year * 12 + COALESCE(end_month, 12)) >= "
            "(start_year * 12 + COALESCE(start_month, 1))",
            name="ck_evidence_revisions_date_order_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_revisions_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_revisions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_revisions"),
        sa.UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "revision",
            name="uq_evidence_revisions_number",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_revisions_owner_id"),
    )
    op.create_index(
        "ix_evidence_revisions_owner_evidence_revision",
        "evidence_revisions",
        ["owner_user_id", "evidence_id", "revision"],
    )
    op.create_table(
        "evidence_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=True),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "workflow_status",
            sa.String(length=16),
            server_default=sa.text("'admitted'"),
            nullable=False,
        ),
        sa.Column("staging_object_key", sa.String(length=1024), nullable=True),
        sa.Column("quarantine_object_key", sa.String(length=1024), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("extraction_format_valid", sa.Boolean(), nullable=True),
        sa.Column("extraction_page_count", sa.Integer(), nullable=True),
        sa.Column("extraction_extracted_characters", sa.Integer(), nullable=True),
        sa.Column("extraction_extracted_blocks", sa.Integer(), nullable=True),
        sa.Column("extraction_archive_entries", sa.Integer(), nullable=True),
        sa.Column("extraction_archive_uncompressed_bytes", sa.Integer(), nullable=True),
        sa.Column("extraction_max_archive_ratio", sa.Integer(), nullable=True),
        sa.Column("extraction_parser_version", sa.String(length=128), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','quarantined','clean','rejected','deleting','deleted')",
            name="ck_evidence_attachments_status_valid",
        ),
        sa.CheckConstraint(
            "workflow_status IN "
            "('admitted','quarantined','processing','clean','rejected','deleting','deleted')",
            name="ck_evidence_attachments_workflow_status_valid",
        ),
        sa.CheckConstraint(
            "content_sha256 IS NULL OR octet_length(content_sha256) = 32",
            name="ck_evidence_attachments_sha256_length",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="ck_evidence_attachments_size_positive",
        ),
        sa.CheckConstraint(
            "(extraction_format_valid IS NULL AND extraction_page_count IS NULL AND "
            "extraction_extracted_characters IS NULL AND extraction_extracted_blocks IS NULL "
            "AND extraction_archive_entries IS NULL "
            "AND extraction_archive_uncompressed_bytes IS NULL "
            "AND extraction_max_archive_ratio IS NULL AND extraction_parser_version IS NULL) "
            "OR (extraction_format_valid IS NOT NULL AND extraction_page_count IS NOT NULL "
            "AND extraction_extracted_characters IS NOT NULL "
            "AND extraction_extracted_blocks IS NOT NULL "
            "AND extraction_archive_entries IS NOT NULL "
            "AND extraction_archive_uncompressed_bytes IS NOT NULL "
            "AND extraction_max_archive_ratio IS NOT NULL "
            "AND extraction_parser_version IS NOT NULL)",
            name="ck_evidence_attachments_extraction_complete",
        ),
        sa.CheckConstraint(
            "COALESCE(extraction_page_count, 0) >= 0 "
            "AND COALESCE(extraction_extracted_characters, 0) >= 0 "
            "AND COALESCE(extraction_extracted_blocks, 0) >= 0 "
            "AND COALESCE(extraction_archive_entries, 0) >= 0 "
            "AND COALESCE(extraction_archive_uncompressed_bytes, 0) >= 0 "
            "AND COALESCE(extraction_max_archive_ratio, 0) >= 0",
            name="ck_evidence_attachments_extraction_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "workflow_status <> 'clean' OR "
            "(content_sha256 IS NOT NULL AND extraction_format_valid IS TRUE)",
            name="ck_evidence_attachments_clean_has_validated_content",
        ),
        sa.CheckConstraint(
            "workflow_status <> 'deleted' OR deleted_at IS NOT NULL",
            name="ck_evidence_attachments_deleted_has_timestamp",
        ),
        sa.CheckConstraint(
            "(workflow_status = 'deleted' AND display_filename IS NULL "
            "AND media_type IS NULL AND size_bytes IS NULL) OR "
            "(workflow_status <> 'deleted' AND display_filename IS NOT NULL "
            "AND media_type IS NOT NULL AND size_bytes IS NOT NULL)",
            name="ck_evidence_attachments_tombstone_metadata_redacted",
        ),
        sa.CheckConstraint(
            "workflow_status <> 'deleted' OR (content_sha256 IS NULL "
            "AND staging_object_key IS NULL AND quarantine_object_key IS NULL "
            "AND safe_error_code IS NULL AND extraction_format_valid IS NULL)",
            name="ck_evidence_attachments_tombstone_sensitive_state_redacted",
        ),
        sa.CheckConstraint("version > 0", name="ck_evidence_attachments_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_attachments_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachments_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachments"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachments_owner_id"),
    )
    op.create_index(
        "ix_evidence_attachments_owner_evidence",
        "evidence_attachments",
        ["owner_user_id", "evidence_id"],
    )
    op.create_table(
        "evidence_attachment_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("execution_token_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','retry_wait','succeeded','rejected',"
            "'dead_lettered','cancelled')",
            name="ck_evidence_attachment_processing_jobs_status_valid",
        ),
        sa.CheckConstraint(
            "stage IN ('queued','malware_scan','extraction','complete')",
            name="ck_evidence_attachment_processing_jobs_stage_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_evidence_attachment_processing_jobs_attempts_valid",
        ),
        sa.CheckConstraint(
            "fence >= 0", name="ck_evidence_attachment_processing_jobs_fence_nonnegative"
        ),
        sa.CheckConstraint(
            "execution_token_hash IS NULL OR octet_length(execution_token_hash) = 32",
            name="ck_evidence_attachment_processing_jobs_execution_token_hash_length",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND execution_token_hash IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'running' AND execution_token_hash IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ck_evidence_attachment_processing_jobs_lease_state_valid",
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded','rejected','dead_lettered','cancelled') "
            "AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running','retry_wait') AND completed_at IS NULL)",
            name="ck_evidence_attachment_processing_jobs_completion_state_valid",
        ),
        sa.CheckConstraint(
            "(status = 'dead_lettered' AND dead_lettered_at IS NOT NULL) OR "
            "(status <> 'dead_lettered' AND dead_lettered_at IS NULL)",
            name="ck_evidence_attachment_processing_jobs_dead_letter_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_jobs_owner_attachment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_processing_jobs_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachment_processing_jobs"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_jobs_owner_id"),
    )
    op.create_index(
        "ix_evidence_attachment_jobs_owner_attachment_created",
        "evidence_attachment_processing_jobs",
        ["owner_user_id", "attachment_id", "created_at", "id"],
    )
    op.create_table(
        "evidence_attachment_finalizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(request_hash) = 32",
            name="ck_evidence_attachment_finalizations_request_hash_length",
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 8 AND 128",
            name="ck_evidence_attachment_finalizations_idempotency_key_length",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_finalizations_owner_attachment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "evidence_attachment_processing_jobs.owner_user_id",
                "evidence_attachment_processing_jobs.id",
            ],
            name="fk_evidence_attachment_finalizations_owner_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_finalizations_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachment_finalizations"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_evidence_attachment_finalizations_owner_key",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_evidence_attachment_finalizations_owner_id",
        ),
    )
    op.create_index(
        "ix_evidence_attachment_finalizations_owner_attachment",
        "evidence_attachment_finalizations",
        ["owner_user_id", "attachment_id"],
    )
    op.create_table(
        "evidence_attachment_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=160), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "generation >= 0 AND attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_evidence_attachment_outbox_attempts_valid",
        ),
        sa.CheckConstraint(
            "(CASE WHEN published_at IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN dead_lettered_at IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN cancelled_at IS NULL THEN 0 ELSE 1 END) <= 1",
            name="ck_evidence_attachment_outbox_terminal_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "evidence_attachment_processing_jobs.owner_user_id",
                "evidence_attachment_processing_jobs.id",
            ],
            name="fk_evidence_attachment_outbox_owner_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_outbox_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachment_outbox"),
        sa.UniqueConstraint(
            "owner_user_id",
            "job_id",
            "generation",
            name="uq_evidence_attachment_outbox_job_generation",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_outbox_owner_id"),
    )
    op.create_index(
        "ix_evidence_attachment_outbox_due",
        "evidence_attachment_outbox",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text(
            "published_at IS NULL AND dead_lettered_at IS NULL AND cancelled_at IS NULL"
        ),
    )
    op.create_table(
        "evidence_attachment_object_cleanups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('rejected_staging','finalized_staging','rejected_quarantine',"
            "'owner_deletion')",
            name="ck_evidence_attachment_object_cleanups_purpose_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending','retry_wait','completed','dead_lettered')",
            name="ck_evidence_attachment_object_cleanups_status_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_evidence_attachment_object_cleanups_attempts_valid",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL "
            "AND dead_lettered_at IS NULL) OR "
            "(status = 'dead_lettered' AND completed_at IS NULL "
            "AND dead_lettered_at IS NOT NULL) OR "
            "(status IN ('pending','retry_wait') AND completed_at IS NULL "
            "AND dead_lettered_at IS NULL)",
            name="ck_evidence_attachment_object_cleanups_terminal_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_cleanups_owner_attachment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_object_cleanups_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachment_object_cleanups"),
        sa.UniqueConstraint(
            "owner_user_id",
            "object_key",
            name="uq_evidence_attachment_cleanups_owner_object",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_cleanups_owner_id"),
    )
    op.create_index(
        "ix_evidence_attachment_cleanups_due",
        "evidence_attachment_object_cleanups",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("status IN ('pending','retry_wait')"),
    )
    op.create_index(
        "ix_evidence_attachment_cleanups_owner_attachment",
        "evidence_attachment_object_cleanups",
        ["owner_user_id", "attachment_id", "created_at", "id"],
    )
    op.create_table(
        "evidence_attachment_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column(
            "safe_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('evidence_attachment.admission_created',"
            "'evidence_attachment.admission_rejected','evidence_attachment.finalized',"
            "'evidence_attachment.processing_retry','evidence_attachment.processing_rejected',"
            "'evidence_attachment.processing_dead_lettered','evidence_attachment.clean',"
            "'evidence_attachment.deletion_requested','evidence_attachment.deleted',"
            "'evidence_attachment.cleanup_dead_lettered')",
            name="ck_evidence_attachment_audit_events_action_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(safe_details) = 'object'",
            name="ck_evidence_attachment_audit_events_safe_details_object",
        ),
        sa.CheckConstraint(
            "safe_details - ARRAY['status','safe_error_code','job_status'] = '{}'::jsonb",
            name="ck_evidence_attachment_audit_events_safe_details_keys_allowlisted",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_audits_owner_attachment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_attachment_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_attachment_audit_events"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_audits_owner_id"),
    )
    op.create_index(
        "ix_evidence_attachment_audits_owner_attachment_created",
        "evidence_attachment_audit_events",
        ["owner_user_id", "attachment_id", "created_at", "id"],
    )
    op.create_index(
        "ix_evidence_attachment_audits_owner_created",
        "evidence_attachment_audit_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_table(
        "evidence_state_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("from_revision_id", sa.Uuid(), nullable=True),
        sa.Column("to_revision_id", sa.Uuid(), nullable=False),
        sa.Column("previous_strength", sa.String(length=16), nullable=True),
        sa.Column("next_strength", sa.String(length=16), nullable=False),
        sa.Column("authority", sa.String(length=40), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("verifier_reference", sa.String(length=240), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "authority IN ('system_source_validation','owner_confirmation',"
            "'owner_rejection','deterministic_policy','server_verification',"
            "'material_edit')",
            name="ck_evidence_state_transitions_authority_valid",
        ),
        sa.CheckConstraint(
            "next_strength IN ('verified','confirmed','supported','inferred','unsupported')",
            name="ck_evidence_state_transitions_next_strength_valid",
        ),
        sa.CheckConstraint(
            "previous_strength IS NULL OR previous_strength IN "
            "('verified','confirmed','supported','inferred','unsupported')",
            name="ck_evidence_state_transitions_previous_strength_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_evidence_state_transitions_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_transitions_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "from_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_transitions_owner_from_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "to_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_transitions_owner_to_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_state_transitions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_state_transitions"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_transitions_owner_id"),
    )
    op.create_index(
        "ix_evidence_transitions_owner_evidence",
        "evidence_state_transitions",
        ["owner_user_id", "evidence_id"],
    )
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_revision_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=True),
        sa.Column("external_url", sa.String(length=2048), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("exact_span_validated", sa.Boolean(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_revision", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.String(length=80), nullable=True),
        sa.Column("parser_version", sa.String(length=120), nullable=True),
        sa.Column("block_id", sa.Uuid(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("source_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("review_excerpt", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind <> 'attachment' OR attachment_id IS NOT NULL",
            name="ck_evidence_sources_attachment_has_reference",
        ),
        sa.CheckConstraint(
            "kind <> 'external_url' OR (external_url LIKE 'http://%' "
            "OR external_url LIKE 'https://%')",
            name="ck_evidence_sources_external_url_http",
        ),
        sa.CheckConstraint(
            "kind <> 'resume' OR (document_id IS NOT NULL AND snapshot_id IS NOT NULL "
            "AND block_id IS NOT NULL AND source_sha256 IS NOT NULL)",
            name="ck_evidence_sources_resume_has_provenance",
        ),
        sa.CheckConstraint(
            "kind IN ('user_attestation','resume','attachment','achievement',"
            "'external_url','independent_verifier')",
            name="ck_evidence_sources_kind_valid",
        ),
        sa.CheckConstraint(
            "NOT exact_span_validated OR (document_id IS NOT NULL "
            "AND snapshot_id IS NOT NULL AND block_id IS NOT NULL)",
            name="ck_evidence_sources_exact_span_has_provenance",
        ),
        sa.CheckConstraint(
            "source_sha256 IS NULL OR octet_length(source_sha256) = 32",
            name="ck_evidence_sources_sha256_length",
        ),
        sa.CheckConstraint(
            "(document_id IS NULL AND snapshot_id IS NULL AND snapshot_revision IS NULL "
            "AND schema_version IS NULL AND parser_version IS NULL AND block_id IS NULL "
            "AND page IS NULL AND start_offset IS NULL AND end_offset IS NULL "
            "AND source_sha256 IS NULL AND review_excerpt IS NULL) OR "
            "(document_id IS NOT NULL AND snapshot_id IS NOT NULL "
            "AND snapshot_revision > 0 AND schema_version IS NOT NULL "
            "AND parser_version IS NOT NULL AND block_id IS NOT NULL AND page > 0 "
            "AND start_offset >= 0 AND end_offset >= start_offset "
            "AND source_sha256 IS NOT NULL AND review_excerpt IS NOT NULL)",
            name="ck_evidence_sources_provenance_complete",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_sources_owner_attachment",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_sources_owner_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_sources_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_sources"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_sources_owner_id"),
    )
    op.create_index(
        "ix_evidence_sources_owner_revision",
        "evidence_sources",
        ["owner_user_id", "evidence_revision_id"],
    )
    op.create_table(
        "evidence_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_revision_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("value", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("value_max", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("period", sa.String(length=240), nullable=False),
        sa.Column("baseline", sa.String(length=500), nullable=True),
        sa.Column("comparator", sa.String(length=500), nullable=True),
        sa.Column("comparison_applicable", sa.Boolean(), nullable=False),
        sa.Column("precision", sa.String(length=16), nullable=False),
        sa.Column("attribution", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "precision <> 'range' OR value_max IS NOT NULL",
            name="ck_evidence_metrics_range_has_maximum",
        ),
        sa.CheckConstraint(
            "precision IN ('exact','approximate','range')",
            name="ck_evidence_metrics_precision_valid",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR char_length(currency) = 3",
            name="ck_evidence_metrics_currency_length",
        ),
        sa.CheckConstraint(
            "value_max IS NULL OR value_max >= value",
            name="ck_evidence_metrics_value_range_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_metrics_owner_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_metrics_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_metrics"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_metrics_owner_id"),
    )
    op.create_index(
        "ix_evidence_metrics_owner_revision",
        "evidence_metrics",
        ["owner_user_id", "evidence_revision_id"],
    )
    op.create_table(
        "evidence_entity_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_evidence_entity_links_owner_entity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_entity_links_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_entity_links_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_entity_links"),
        sa.UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "entity_id",
            name="uq_evidence_entity_links_pair",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_entity_links_owner_id"),
    )
    op.create_index(
        "ix_evidence_entity_links_owner_evidence",
        "evidence_entity_links",
        ["owner_user_id", "evidence_id"],
    )
    op.create_table(
        "evidence_skill_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_skill_links_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_evidence_skill_links_owner_skill",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_skill_links_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_skill_links"),
        sa.UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "skill_id",
            name="uq_evidence_skill_links_pair",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_skill_links_owner_id"),
    )
    op.create_index(
        "ix_evidence_skill_links_owner_evidence",
        "evidence_skill_links",
        ["owner_user_id", "evidence_id"],
    )
    op.create_table(
        "evidence_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("consumer_kind", sa.String(length=80), nullable=False),
        sa.Column("consumer_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_usage_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_usage_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_usage"),
        sa.UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "consumer_kind",
            "consumer_id",
            "purpose",
            name="uq_evidence_usage_target",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_usage_owner_id"),
    )
    op.create_index(
        "ix_evidence_usage_owner_evidence",
        "evidence_usage",
        ["owner_user_id", "evidence_id"],
    )
    op.create_table(
        "evidence_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("conflicting_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolution", sa.String(length=24), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('date','title','metric','entity','source')",
            name="ck_evidence_conflicts_kind_valid",
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN "
            "('keep_current','accept_incoming','keep_both','not_a_conflict')",
            name="ck_evidence_conflicts_resolution_valid",
        ),
        sa.CheckConstraint(
            "status IN ('open','resolved','dismissed')",
            name="ck_evidence_conflicts_status_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_evidence_conflicts_version_positive"),
        sa.CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status IN ('resolved','dismissed') AND resolution IS NOT NULL "
            "AND resolved_at IS NOT NULL)",
            name="ck_evidence_conflicts_resolution_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "conflicting_evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_conflicts_owner_conflicting_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_conflicts_owner_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_evidence_conflicts_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_conflicts"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_evidence_conflicts_owner_id"),
    )
    op.create_index(
        "ix_evidence_conflicts_owner_evidence_status",
        "evidence_conflicts",
        ["owner_user_id", "evidence_id", "status"],
    )
    op.create_index(
        "ix_evidence_conflicts_owner_other_status",
        "evidence_conflicts",
        ["owner_user_id", "conflicting_evidence_id", "status"],
    )
    op.create_table(
        "career_import_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_entity_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_kind", sa.String(length=32), nullable=False),
        sa.Column("proposed_title", sa.String(length=300), nullable=False),
        sa.Column("proposed_organization", sa.String(length=300), nullable=True),
        sa.Column("proposed_description", sa.Text(), nullable=True),
        sa.Column("proposed_official_title", sa.String(length=300), nullable=True),
        sa.Column("proposed_display_title", sa.String(length=300), nullable=True),
        sa.Column("proposed_employment_type", sa.String(length=24), nullable=True),
        sa.Column("proposed_location", sa.String(length=240), nullable=True),
        sa.Column("proposed_external_url", sa.String(length=2048), nullable=True),
        sa.Column("proposed_start_year", sa.Integer(), nullable=True),
        sa.Column("proposed_start_month", sa.Integer(), nullable=True),
        sa.Column("proposed_end_year", sa.Integer(), nullable=True),
        sa.Column("proposed_end_month", sa.Integer(), nullable=True),
        sa.Column("proposed_is_current", sa.Boolean(), nullable=False),
        sa.Column("proposed_sort_order", sa.Integer(), nullable=False),
        sa.Column("proposed_group_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=120), nullable=False),
        sa.Column("block_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("review_excerpt", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("conflict_code", sa.String(length=80), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "proposed_employment_type IS NULL OR proposed_employment_type IN "
            "('full_time','part_time','contract','internship','temporary','volunteer','other')",
            name="ck_career_import_proposals_employment_type_valid",
        ),
        sa.CheckConstraint(
            "proposed_external_url IS NULL OR proposed_external_url LIKE 'http://%' "
            "OR proposed_external_url LIKE 'https://%'",
            name="ck_career_import_proposals_external_url_http",
        ),
        sa.CheckConstraint(
            "proposed_kind = 'experience' OR proposed_employment_type IS NULL",
            name="ck_career_import_proposals_employment_type_experience_only",
        ),
        sa.CheckConstraint(
            "proposed_kind IN ('experience','education','project','credential',"
            "'publication','award','volunteering','language','portfolio_link')",
            name="ck_career_import_proposals_kind_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','rejected')",
            name="ck_career_import_proposals_status_valid",
        ),
        sa.CheckConstraint(
            "NOT proposed_is_current OR proposed_end_year IS NULL",
            name="ck_career_import_proposals_current_has_no_end",
        ),
        sa.CheckConstraint(
            "octet_length(source_sha256) = 32",
            name="ck_career_import_proposals_sha256_length",
        ),
        sa.CheckConstraint(
            "page > 0 AND start_offset >= 0 AND end_offset >= start_offset",
            name="ck_career_import_proposals_span_valid",
        ),
        sa.CheckConstraint(
            "proposed_end_month IS NULL OR "
            "(proposed_end_year IS NOT NULL AND proposed_end_month BETWEEN 1 AND 12)",
            name="ck_career_import_proposals_end_month_valid",
        ),
        sa.CheckConstraint(
            "proposed_end_year IS NULL OR (proposed_end_year BETWEEN 1900 AND 2200)",
            name="ck_career_import_proposals_end_year_valid",
        ),
        sa.CheckConstraint(
            "proposed_sort_order >= 0",
            name="ck_career_import_proposals_sort_order_nonnegative",
        ),
        sa.CheckConstraint(
            "proposed_start_month IS NULL OR (proposed_start_year IS NOT NULL "
            "AND proposed_start_month BETWEEN 1 AND 12)",
            name="ck_career_import_proposals_start_month_valid",
        ),
        sa.CheckConstraint(
            "proposed_start_year IS NULL OR (proposed_start_year BETWEEN 1900 AND 2200)",
            name="ck_career_import_proposals_start_year_valid",
        ),
        sa.CheckConstraint(
            "proposed_start_year IS NULL OR proposed_end_year IS NULL OR "
            "(proposed_end_year * 12 + COALESCE(proposed_end_month, 12)) >= "
            "(proposed_start_year * 12 + COALESCE(proposed_start_month, 1))",
            name="ck_career_import_proposals_date_order_valid",
        ),
        sa.CheckConstraint(
            "snapshot_revision > 0",
            name="ck_career_import_proposals_snapshot_revision_positive",
        ),
        sa.CheckConstraint("version > 0", name="ck_career_import_proposals_version_positive"),
        sa.CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR "
            "(status IN ('accepted','rejected') AND reviewed_at IS NOT NULL)",
            name="ck_career_import_proposals_review_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_import_proposals_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "target_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_import_proposals_owner_target",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_import_proposals_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_import_proposals"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_import_proposals_owner_id"),
    )
    op.create_index(
        "ix_career_import_proposals_owner_status_created",
        "career_import_proposals",
        ["owner_user_id", "status", "created_at", "id"],
    )
    op.create_table(
        "achievement_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("delivered", sa.Text(), nullable=True),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("measurement", sa.Text(), nullable=True),
        sa.Column("effect", sa.Text(), nullable=True),
        sa.Column("collaboration", sa.Text(), nullable=True),
        sa.Column("methods", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("metric_name", sa.String(length=160), nullable=True),
        sa.Column("metric_value", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("metric_value_max", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("metric_unit", sa.String(length=80), nullable=True),
        sa.Column("metric_currency", sa.String(length=3), nullable=True),
        sa.Column("metric_period", sa.String(length=240), nullable=True),
        sa.Column("metric_baseline", sa.String(length=500), nullable=True),
        sa.Column("metric_comparator", sa.String(length=500), nullable=True),
        sa.Column("metric_comparison_applicable", sa.Boolean(), nullable=True),
        sa.Column("metric_precision", sa.String(length=16), nullable=True),
        sa.Column("metric_attribution", sa.String(length=500), nullable=True),
        sa.Column("reminder_cadence", sa.String(length=16), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("converted_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("conversion_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "metric_precision IS NULL OR metric_precision IN ('exact','approximate','range')",
            name="ck_achievement_drafts_metric_precision_valid",
        ),
        sa.CheckConstraint(
            "reminder_cadence <> 'custom' OR remind_at IS NOT NULL",
            name="ck_achievement_drafts_custom_reminder_has_time",
        ),
        sa.CheckConstraint(
            "reminder_cadence IN ('none','monthly','quarterly','custom')",
            name="ck_achievement_drafts_reminder_cadence_valid",
        ),
        sa.CheckConstraint(
            "status IN ('draft','converted','archived')",
            name="ck_achievement_drafts_status_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_achievement_drafts_version_positive"),
        sa.CheckConstraint(
            "(metric_value IS NULL AND metric_name IS NULL AND metric_value_max IS NULL "
            "AND metric_unit IS NULL AND metric_currency IS NULL "
            "AND metric_period IS NULL AND metric_baseline IS NULL "
            "AND metric_comparator IS NULL AND metric_comparison_applicable IS NULL "
            "AND metric_precision IS NULL AND metric_attribution IS NULL) OR "
            "(metric_value IS NOT NULL AND metric_unit IS NOT NULL "
            "AND metric_period IS NOT NULL AND metric_comparison_applicable IS NOT NULL "
            "AND metric_precision IS NOT NULL AND metric_attribution IS NOT NULL)",
            name="ck_achievement_drafts_metric_complete",
        ),
        sa.CheckConstraint(
            "metric_precision <> 'range' OR metric_value_max IS NOT NULL",
            name="ck_achievement_drafts_metric_range_has_maximum",
        ),
        sa.CheckConstraint(
            "metric_value_max IS NULL OR metric_value_max >= metric_value",
            name="ck_achievement_drafts_metric_value_range_valid",
        ),
        sa.CheckConstraint(
            "metric_currency IS NULL OR char_length(metric_currency) = 3",
            name="ck_achievement_drafts_metric_currency_length",
        ),
        sa.CheckConstraint(
            "(status = 'converted' AND converted_evidence_id IS NOT NULL "
            "AND conversion_idempotency_key IS NOT NULL) OR "
            "(status <> 'converted' AND converted_evidence_id IS NULL "
            "AND conversion_idempotency_key IS NULL)",
            name="ck_achievement_drafts_conversion_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "converted_evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_achievement_drafts_owner_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_achievement_drafts_owner_entity",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_achievement_drafts_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_achievement_drafts_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_achievement_drafts"),
        sa.UniqueConstraint(
            "owner_user_id",
            "conversion_idempotency_key",
            name="uq_achievement_drafts_owner_conversion_key",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_achievement_drafts_owner_id"),
    )
    op.create_index(
        "ix_achievement_drafts_owner_created",
        "achievement_drafts",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_table(
        "career_reminder_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(enabled AND day_of_month BETWEEN 1 AND 28) OR (NOT enabled AND day_of_month IS NULL)",
            name="ck_career_reminder_preferences_enabled_day_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_career_reminder_preferences_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_reminder_preferences_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_reminder_preferences"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_reminder_preferences_owner_id"),
        sa.UniqueConstraint("owner_user_id", name="uq_career_reminder_preferences_owner_user_id"),
    )
    op.create_table(
        "career_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_career_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_career_audit_events"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_audit_events_owner_id"),
    )
    op.create_index(
        "ix_career_audit_events_owner_created",
        "career_audit_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_career_audit_events_owner_target",
        "career_audit_events",
        ["owner_user_id", "target_kind", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_career_audit_events_owner_target", table_name="career_audit_events")
    op.drop_index("ix_career_audit_events_owner_created", table_name="career_audit_events")
    op.drop_table("career_audit_events")
    op.drop_table("career_reminder_preferences")
    op.drop_index("ix_achievement_drafts_owner_created", table_name="achievement_drafts")
    op.drop_table("achievement_drafts")
    op.drop_index(
        "ix_career_import_proposals_owner_status_created",
        table_name="career_import_proposals",
    )
    op.drop_table("career_import_proposals")
    op.drop_index("ix_evidence_conflicts_owner_other_status", table_name="evidence_conflicts")
    op.drop_index(
        "ix_evidence_conflicts_owner_evidence_status",
        table_name="evidence_conflicts",
    )
    op.drop_table("evidence_conflicts")
    op.drop_index("ix_evidence_usage_owner_evidence", table_name="evidence_usage")
    op.drop_table("evidence_usage")
    op.drop_index("ix_evidence_skill_links_owner_evidence", table_name="evidence_skill_links")
    op.drop_table("evidence_skill_links")
    op.drop_index("ix_evidence_entity_links_owner_evidence", table_name="evidence_entity_links")
    op.drop_table("evidence_entity_links")
    op.drop_index("ix_evidence_metrics_owner_revision", table_name="evidence_metrics")
    op.drop_table("evidence_metrics")
    op.drop_index("ix_evidence_sources_owner_revision", table_name="evidence_sources")
    op.drop_table("evidence_sources")
    op.drop_index(
        "ix_evidence_transitions_owner_evidence",
        table_name="evidence_state_transitions",
    )
    op.drop_table("evidence_state_transitions")
    op.drop_index(
        "ix_evidence_attachment_audits_owner_created",
        table_name="evidence_attachment_audit_events",
    )
    op.drop_index(
        "ix_evidence_attachment_audits_owner_attachment_created",
        table_name="evidence_attachment_audit_events",
    )
    op.drop_table("evidence_attachment_audit_events")
    op.drop_index(
        "ix_evidence_attachment_cleanups_owner_attachment",
        table_name="evidence_attachment_object_cleanups",
    )
    op.drop_index(
        "ix_evidence_attachment_cleanups_due",
        table_name="evidence_attachment_object_cleanups",
    )
    op.drop_table("evidence_attachment_object_cleanups")
    op.drop_index(
        "ix_evidence_attachment_outbox_due",
        table_name="evidence_attachment_outbox",
    )
    op.drop_table("evidence_attachment_outbox")
    op.drop_index(
        "ix_evidence_attachment_finalizations_owner_attachment",
        table_name="evidence_attachment_finalizations",
    )
    op.drop_table("evidence_attachment_finalizations")
    op.drop_index(
        "ix_evidence_attachment_jobs_owner_attachment_created",
        table_name="evidence_attachment_processing_jobs",
    )
    op.drop_table("evidence_attachment_processing_jobs")
    op.drop_index("ix_evidence_attachments_owner_evidence", table_name="evidence_attachments")
    op.drop_table("evidence_attachments")
    op.drop_index(
        "ix_evidence_revisions_owner_evidence_revision",
        table_name="evidence_revisions",
    )
    op.drop_table("evidence_revisions")
    op.drop_index("ix_evidence_items_owner_lifecycle_created", table_name="evidence_items")
    op.drop_table("evidence_items")
    op.drop_index("ix_career_entity_skills_owner_entity", table_name="career_entity_skills")
    op.drop_table("career_entity_skills")
    op.drop_index("ix_career_skills_owner_profile_order", table_name="career_skills")
    op.drop_table("career_skills")
    op.drop_index("ix_career_entities_owner_profile_order", table_name="career_entities")
    op.drop_table("career_entities")
    op.drop_table("career_profiles")
