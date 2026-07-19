"""Add Phase 5 Job Match and Opportunity Priority.

Revision ID: 20260719_0006
Revises: 20260719_0005
Create Date: 2026-07-19 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0006"
down_revision: str | None = "20260719_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("work_model", sa.String(length=16), nullable=False),
        sa.Column("employment_type", sa.String(length=16), nullable=False),
        sa.Column("compensation", sa.String(length=200), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("target_role_id", sa.Uuid(), nullable=True),
        sa.Column("target_role_title", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "employment_type IN ('full_time','part_time','contract','internship',"
            "'temporary','unknown')",
            name="ck_job_postings_employment_type_valid",
        ),
        sa.CheckConstraint(
            "octet_length(source_sha256) = 32",
            name="ck_job_postings_source_hash_length",
        ),
        sa.CheckConstraint(
            "source_kind IN ('paste','url','manual')",
            name="ck_job_postings_source_kind_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_job_postings_version_positive"),
        sa.CheckConstraint(
            "work_model IN ('remote','hybrid','onsite','unknown')",
            name="ck_job_postings_work_model_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_postings_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_postings"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_job_postings_owner_idempotency",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_job_postings_owner_id"),
    )
    op.create_index(
        "ix_job_postings_owner_target_role",
        "job_postings",
        ["owner_user_id", "target_role_id", "id"],
    )
    op.create_index(
        "ix_job_postings_owner_updated",
        "job_postings",
        ["owner_user_id", "updated_at", "id"],
    )
    op.create_table(
        "job_match_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('job_imported','job_created','job_updated','job_deleted',"
            "'job_analyzed','opportunity_prioritized')",
            name="ck_job_match_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_job_match_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_match_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_match_audit_events"),
    )
    op.create_index(
        "ix_job_match_audit_owner_created",
        "job_match_audit_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_job_match_audit_target",
        "job_match_audit_events",
        ["target_kind", "target_id", "created_at"],
    )
    op.create_table(
        "job_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.String(length=1000), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("confidence_basis_points", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "confidence_basis_points BETWEEN 0 AND 10000",
            name="ck_job_requirements_confidence_valid",
        ),
        sa.CheckConstraint(
            "importance IN ('mandatory','preferred','helpful')",
            name="ck_job_requirements_importance_valid",
        ),
        sa.CheckConstraint(
            "requirement_type IN ('responsibility','skill','experience','seniority',"
            "'education','certification','domain','work_authorization','travel',"
            "'compensation','other')",
            name="ck_job_requirements_requirement_type_valid",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_job_requirements_sort_order_nonnegative",
        ),
        sa.CheckConstraint(
            "source_start >= 0 AND source_end > source_start",
            name="ck_job_requirements_source_span_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_job_requirements_owner_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_requirements_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_requirements"),
        sa.UniqueConstraint(
            "owner_user_id",
            "job_id",
            "normalized_text",
            name="uq_job_requirements_job_normalized",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_job_requirements_owner_id"),
    )
    op.create_index(
        "ix_job_requirements_job_order",
        "job_requirements",
        ["owner_user_id", "job_id", "sort_order", "id"],
    )
    op.create_table(
        "job_match_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("engine_version", sa.String(length=120), nullable=False),
        sa.Column("configuration_version", sa.String(length=120), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=120), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feature_set_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("raw_score_basis_points", sa.Integer(), nullable=True),
        sa.Column("display_score", sa.Integer(), nullable=True),
        sa.Column("readiness_label", sa.String(length=32), nullable=False),
        sa.Column("hard_gap_count", sa.Integer(), nullable=False),
        sa.Column("insufficient_reason", sa.String(length=160), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_score IS NULL OR display_score BETWEEN 0 AND 100",
            name="ck_job_match_analyses_display_score_valid",
        ),
        sa.CheckConstraint(
            "octet_length(feature_set_hash) = 32",
            name="ck_job_match_analyses_feature_hash_length",
        ),
        sa.CheckConstraint(
            "hard_gap_count >= 0",
            name="ck_job_match_analyses_hard_gap_count_nonnegative",
        ),
        sa.CheckConstraint(
            "raw_score_basis_points IS NULL OR raw_score_basis_points BETWEEN 0 AND 10000",
            name="ck_job_match_analyses_raw_score_valid",
        ),
        sa.CheckConstraint(
            "readiness_label IN ('strong','viable','needs_work','insufficient_data')",
            name="ck_job_match_analyses_readiness_label_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_job_match_analyses_owner_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_match_analyses_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_match_analyses"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_job_match_analyses_owner_idempotency",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_job_match_analyses_owner_id"),
    )
    op.create_index(
        "ix_job_match_analyses_owner_job_created",
        "job_match_analyses",
        ["owner_user_id", "job_id", "created_at"],
    )
    op.create_table(
        "job_match_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=80), nullable=False),
        sa.Column("weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=False),
        sa.Column("contribution_basis_points", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "contribution_basis_points BETWEEN 0 AND 10000",
            name="ck_job_match_components_contribution_valid",
        ),
        sa.CheckConstraint(
            "score_basis_points BETWEEN 0 AND 10000",
            name="ck_job_match_components_score_valid",
        ),
        sa.CheckConstraint(
            "weight_basis_points BETWEEN 0 AND 10000",
            name="ck_job_match_components_weight_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_job_match_components_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_match_components_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_match_components"),
        sa.UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_job_match_components_dimension",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_job_match_components_owner_id"),
    )
    op.create_table(
        "requirement_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("match_state", sa.String(length=32), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("hard_gap", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "importance IN ('mandatory','preferred','helpful')",
            name="ck_requirement_matches_importance_valid",
        ),
        sa.CheckConstraint(
            "match_state IN ('strong','partial','transferable','unknown','missing',"
            "'not_applicable')",
            name="ck_requirement_matches_match_state_valid",
        ),
        sa.CheckConstraint(
            "requirement_type IN ('responsibility','skill','experience','seniority',"
            "'education','certification','domain','work_authorization','travel',"
            "'compensation','other')",
            name="ck_requirement_matches_requirement_type_valid",
        ),
        sa.CheckConstraint(
            "score_basis_points BETWEEN 0 AND 10000",
            name="ck_requirement_matches_score_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_requirement_matches_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_requirement_matches_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirement_matches"),
        sa.UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "requirement_id",
            name="uq_requirement_matches_analysis_requirement",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_requirement_matches_owner_id"),
    )
    op.create_index(
        "ix_requirement_matches_analysis",
        "requirement_matches",
        ["owner_user_id", "analysis_id", "id"],
    )
    op.create_table(
        "opportunity_priorities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("priority_label", sa.String(length=16), nullable=False),
        sa.Column("priority_score_basis_points", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reasons_for", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reconsiderations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blockers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "priority_label IN ('high','medium','low','defer')",
            name="ck_opportunity_priorities_priority_label_valid",
        ),
        sa.CheckConstraint(
            "priority_score_basis_points BETWEEN 0 AND 10000",
            name="ck_opportunity_priorities_priority_score_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_opportunity_priorities_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_opportunity_priorities_owner_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_opportunity_priorities_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_priorities"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_opportunity_priorities_owner_idempotency",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_opportunity_priorities_owner_id"),
    )
    op.create_index(
        "ix_opportunity_priorities_owner_job_created",
        "opportunity_priorities",
        ["owner_user_id", "job_id", "created_at", "id"],
    )
    op.create_table(
        "requirement_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_match_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_title", sa.String(length=300), nullable=False),
        sa.Column("evidence_strength", sa.String(length=40), nullable=False),
        sa.Column("relevance_basis_points", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "relevance_basis_points BETWEEN 0 AND 10000",
            name="ck_requirement_evidence_links_relevance_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_requirement_evidence_links_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "requirement_match_id"],
            ["requirement_matches.owner_user_id", "requirement_matches.id"],
            name="fk_requirement_evidence_links_owner_match",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_requirement_evidence_links_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirement_evidence_links"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_requirement_evidence_links_owner_id",
        ),
    )
    op.create_index(
        "ix_requirement_evidence_links_match",
        "requirement_evidence_links",
        ["owner_user_id", "requirement_match_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_requirement_evidence_links_match", table_name="requirement_evidence_links")
    op.drop_table("requirement_evidence_links")
    op.drop_index(
        "ix_opportunity_priorities_owner_job_created",
        table_name="opportunity_priorities",
    )
    op.drop_table("opportunity_priorities")
    op.drop_index("ix_requirement_matches_analysis", table_name="requirement_matches")
    op.drop_table("requirement_matches")
    op.drop_table("job_match_components")
    op.drop_index("ix_job_match_analyses_owner_job_created", table_name="job_match_analyses")
    op.drop_table("job_match_analyses")
    op.drop_index("ix_job_requirements_job_order", table_name="job_requirements")
    op.drop_table("job_requirements")
    op.drop_index("ix_job_match_audit_target", table_name="job_match_audit_events")
    op.drop_index("ix_job_match_audit_owner_created", table_name="job_match_audit_events")
    op.drop_table("job_match_audit_events")
    op.drop_index("ix_job_postings_owner_updated", table_name="job_postings")
    op.drop_index("ix_job_postings_owner_target_role", table_name="job_postings")
    op.drop_table("job_postings")
