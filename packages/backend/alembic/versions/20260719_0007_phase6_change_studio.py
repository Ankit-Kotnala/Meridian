"""Add Phase 6 Change Studio.

Revision ID: 20260719_0007
Revises: 20260719_0006
Create Date: 2026-07-19 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0007"
down_revision: str | None = "20260719_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "change_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("target_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("provider_model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("policy_version", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=120), nullable=False),
        sa.Column("grounding_version", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('job_tailoring')",
            name="ck_change_sets_purpose_valid",
        ),
        sa.CheckConstraint(
            "status IN ('draft','applied')",
            name="ck_change_sets_status_valid",
        ),
        sa.CheckConstraint(
            "target_kind IN ('tailored_resume_bullet','profile_summary')",
            name="ck_change_sets_target_kind_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_change_sets_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_sets_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_sets"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_change_sets_owner_idempotency",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_change_sets_owner_id"),
    )
    op.create_index(
        "ix_change_sets_owner_analysis",
        "change_sets",
        ["owner_user_id", "analysis_id", "created_at"],
    )
    op.create_index(
        "ix_change_sets_owner_updated",
        "change_sets",
        ["owner_user_id", "updated_at", "id"],
    )

    op.create_table(
        "change_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("target_kind", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=False),
        sa.Column("after_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("confidence_basis_points", sa.Integer(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("grounding_status", sa.String(length=32), nullable=False),
        sa.Column("grounding_codes", JSONB, nullable=False),
        sa.Column("expected_score_delta_basis_points", sa.Integer(), nullable=True),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_text", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_basis_points BETWEEN 0 AND 10000",
            name="ck_change_operations_confidence_valid",
        ),
        sa.CheckConstraint(
            "expected_score_delta_basis_points IS NULL OR "
            "expected_score_delta_basis_points BETWEEN -10000 AND 10000",
            name="ck_change_operations_expected_score_delta_valid",
        ),
        sa.CheckConstraint(
            "grounding_status IN ('grounded','blocked','needs_clarification')",
            name="ck_change_operations_grounding_status_valid",
        ),
        sa.CheckConstraint(
            "operation_type IN ('add_bullet','replace_bullet','replace_summary')",
            name="ck_change_operations_operation_type_valid",
        ),
        sa.CheckConstraint(
            "risk IN ('low','medium','high')",
            name="ck_change_operations_risk_valid",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_change_operations_sort_order_nonnegative"),
        sa.CheckConstraint(
            "status IN ('proposed','accepted','rejected','edited','blocked')",
            name="ck_change_operations_status_valid",
        ),
        sa.CheckConstraint(
            "target_kind IN ('tailored_resume_bullet','profile_summary')",
            name="ck_change_operations_target_kind_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_change_operations_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_operations_owner_change_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_operations_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_operations"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_change_operations_owner_id",
        ),
    )
    op.create_index(
        "ix_change_operations_change_set_order",
        "change_operations",
        ["owner_user_id", "change_set_id", "sort_order"],
    )

    op.create_table(
        "change_operation_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("claim_kind", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_title", sa.String(length=300), nullable=False),
        sa.Column("evidence_strength", sa.String(length=40), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("validation_codes", JSONB, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "claim_kind IN ('responsibility','achievement','metric_outcome','skill',"
            "'credential','experience','other')",
            name="ck_change_operation_claims_claim_kind_valid",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_change_operation_claims_sort_order_nonnegative",
        ),
        sa.CheckConstraint(
            "validation_status IN ('passed','failed')",
            name="ck_change_operation_claims_validation_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_claims_owner_change_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_claims_owner_operation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_operation_claims_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_operation_claims"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_change_claims_owner_id"),
    )
    op.create_index(
        "ix_change_claims_evidence",
        "change_operation_claims",
        ["owner_user_id", "evidence_id", "operation_id"],
    )
    op.create_index(
        "ix_change_claims_operation_order",
        "change_operation_claims",
        ["owner_user_id", "operation_id", "sort_order"],
    )

    op.create_table(
        "change_clarifying_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open','answered','dismissed')",
            name="ck_change_clarifying_questions_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_questions_owner_change_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_questions_owner_operation",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_clarifying_questions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_clarifying_questions"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_change_questions_owner_id"),
    )
    op.create_index(
        "ix_change_questions_change_set",
        "change_clarifying_questions",
        ["owner_user_id", "change_set_id", "created_at"],
    )
    op.create_index(
        "ix_change_questions_requirement",
        "change_clarifying_questions",
        ["owner_user_id", "requirement_id", "id"],
    )

    op.create_table(
        "change_set_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_operation_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("operation_ids", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_change_set_versions_version_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_versions_owner_change_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "created_by_operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_versions_owner_operation",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "parent_version_id"],
            ["change_set_versions.owner_user_id", "change_set_versions.id"],
            name="fk_change_versions_owner_parent",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_set_versions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_set_versions"),
        sa.UniqueConstraint(
            "owner_user_id",
            "change_set_id",
            "version_number",
            name="uq_change_versions_change_set_number",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_change_versions_owner_id"),
    )
    op.create_index(
        "ix_change_versions_change_set_number",
        "change_set_versions",
        ["owner_user_id", "change_set_id", "version_number"],
    )

    op.create_table(
        "change_provider_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("provider_model", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("policy_version", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=120), nullable=False),
        sa.Column("grounding_version", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("input_evidence_ids", JSONB, nullable=False),
        sa.Column("input_requirement_ids", JSONB, nullable=False),
        sa.Column("output_operation_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_micros", sa.Integer(), nullable=True),
        sa.Column("validation_codes", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="ck_change_provider_runs_completion_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "cost_micros IS NULL OR cost_micros >= 0",
            name="ck_change_provider_runs_cost_micros_nonnegative",
        ),
        sa.CheckConstraint("latency_ms >= 0", name="ck_change_provider_runs_latency_nonnegative"),
        sa.CheckConstraint(
            "output_operation_count BETWEEN 0 AND 100",
            name="ck_change_provider_runs_output_count_valid",
        ),
        sa.CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0",
            name="ck_change_provider_runs_prompt_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded','failed','blocked')",
            name="ck_change_provider_runs_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_provider_runs_owner_change_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_provider_runs_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_provider_runs"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_change_provider_runs_owner_id"),
    )
    op.create_index(
        "ix_change_provider_runs_change_set",
        "change_provider_runs",
        ["owner_user_id", "change_set_id", "created_at"],
    )

    op.create_table(
        "change_studio_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_studio_idempotency_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_studio_idempotency"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_change_studio_idempotency_owner_key",
        ),
    )
    op.create_index(
        "ix_change_studio_idempotency_target",
        "change_studio_idempotency",
        ["owner_user_id", "target_kind", "target_id"],
    )

    op.create_table(
        "change_studio_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('change_set_created','operation_accepted','operation_rejected',"
            "'operation_edited','operation_alternative_created','operation_locked',"
            "'operation_unlocked','safe_changes_applied','change_set_undone',"
            "'change_set_redone','version_restored','clarification_answered')",
            name="ck_change_studio_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_change_studio_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_change_studio_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_studio_audit_events"),
    )
    op.create_index(
        "ix_change_studio_audit_owner_created",
        "change_studio_audit_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_change_studio_audit_target",
        "change_studio_audit_events",
        ["target_kind", "target_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_change_studio_audit_target", table_name="change_studio_audit_events")
    op.drop_index("ix_change_studio_audit_owner_created", table_name="change_studio_audit_events")
    op.drop_table("change_studio_audit_events")
    op.drop_index("ix_change_studio_idempotency_target", table_name="change_studio_idempotency")
    op.drop_table("change_studio_idempotency")
    op.drop_index("ix_change_provider_runs_change_set", table_name="change_provider_runs")
    op.drop_table("change_provider_runs")
    op.drop_index("ix_change_versions_change_set_number", table_name="change_set_versions")
    op.drop_table("change_set_versions")
    op.drop_index("ix_change_questions_requirement", table_name="change_clarifying_questions")
    op.drop_index("ix_change_questions_change_set", table_name="change_clarifying_questions")
    op.drop_table("change_clarifying_questions")
    op.drop_index("ix_change_claims_operation_order", table_name="change_operation_claims")
    op.drop_index("ix_change_claims_evidence", table_name="change_operation_claims")
    op.drop_table("change_operation_claims")
    op.drop_index("ix_change_operations_change_set_order", table_name="change_operations")
    op.drop_table("change_operations")
    op.drop_index("ix_change_sets_owner_updated", table_name="change_sets")
    op.drop_index("ix_change_sets_owner_analysis", table_name="change_sets")
    op.drop_table("change_sets")
