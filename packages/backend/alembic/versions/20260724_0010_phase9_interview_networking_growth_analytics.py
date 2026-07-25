"""Add Phase 9 interview, networking, growth, and analytics persistence.

Revision ID: 20260724_0010
Revises: 20260724_0009
Create Date: 2026-07-25 03:09:34.314101
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_0010"
down_revision: str | None = "20260724_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHASE8_EVENT_KINDS = (
    "created",
    "stage_changed",
    "deadline_changed",
    "follow_up_changed",
    "note_added",
    "task_added",
    "task_completed",
    "pack_generated",
    "outcome_recorded",
    "resume_version_changed",
    "interview",
    "contact",
    "custom",
)
_PHASE8_AUDIT_ACTIONS = (
    "application_created",
    "application_updated",
    "application_stage_changed",
    "resume_version_changed",
    "application_deleted",
    "task_created",
    "task_updated",
    "note_created",
    "event_recorded",
    "pack_generated",
    "document_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def _repair_phase8_enum_check(
    *,
    table_name: str,
    column_name: str,
    constraint_name: str,
    values: tuple[str, ...],
) -> None:
    inspector = sa.inspect(op.get_bind())
    matching = [
        constraint
        for constraint in inspector.get_check_constraints(table_name)
        if column_name in str(constraint.get("sqltext", ""))
    ]
    expected_values = set(values)
    if any(
        all(f"'{value}'" in str(constraint.get("sqltext", "")) for value in expected_values)
        for constraint in matching
    ):
        return
    for constraint in matching:
        physical_name = constraint.get("name")
        if physical_name is not None:
            op.drop_constraint(op.f(str(physical_name)), table_name, type_="check")
    op.create_check_constraint(
        constraint_name,
        table_name,
        f"{column_name} IN ({_values(values)})",
    )


def _repair_phase8_claim_provenance() -> None:
    """Bring pre-release Phase 8 development databases to the shipped schema.

    The canonical ``20260724_0009`` migration already owns these nullable
    columns, their complete-tuple check, and the resume-change event/audit enum
    values. Some long-lived local databases were stamped with an earlier
    development copy of that revision before its hosted release. Phase 9 repairs
    only missing or stale objects and deliberately leaves them in place on
    downgrade because they remain part of the canonical Phase 8 schema.
    """

    inspector = sa.inspect(op.get_bind())
    column_names = {column["name"] for column in inspector.get_columns("change_operation_claims")}
    columns = (
        ("evidence_revision_id", sa.Uuid()),
        ("evidence_revision_number", sa.Integer()),
        ("evidence_statement_sha256", sa.String(length=64)),
    )
    for name, type_ in columns:
        if name not in column_names:
            op.add_column(
                "change_operation_claims",
                sa.Column(name, type_, nullable=True),
            )

    check_constraints = inspector.get_check_constraints("change_operation_claims")
    has_provenance_constraint = any(
        all(
            column_name in str(constraint.get("sqltext", ""))
            for column_name in (
                "evidence_revision_id",
                "evidence_revision_number",
                "evidence_statement_sha256",
            )
        )
        for constraint in check_constraints
    )
    if not has_provenance_constraint:
        op.create_check_constraint(
            "ck_change_operation_claims_evidence_provenance_complete",
            "change_operation_claims",
            (
                "(evidence_revision_id IS NULL "
                "AND evidence_revision_number IS NULL "
                "AND evidence_statement_sha256 IS NULL) "
                "OR "
                "(evidence_revision_id IS NOT NULL "
                "AND evidence_revision_number IS NOT NULL "
                "AND evidence_statement_sha256 IS NOT NULL "
                "AND evidence_revision_number > 0 "
                "AND evidence_statement_sha256 ~ '^[0-9a-f]{64}$')"
            ),
        )
    _repair_phase8_enum_check(
        table_name="application_events",
        column_name="event_kind",
        constraint_name="ck_application_events_event_kind_valid",
        values=_PHASE8_EVENT_KINDS,
    )
    _repair_phase8_enum_check(
        table_name="application_workspace_audit_events",
        column_name="action",
        constraint_name="ck_application_workspace_audit_events_action_valid",
        values=_PHASE8_AUDIT_ACTIONS,
    )


def upgrade() -> None:
    """Create the four additive Phase 9 bounded-context schemas."""
    _repair_phase8_claim_provenance()
    op.create_unique_constraint(
        "uq_evidence_revisions_owner_evidence_id",
        "evidence_revisions",
        ["owner_user_id", "evidence_id", "id"],
    )
    op.create_table(
        "career_analytics_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('refresh_requested','refresh_started','snapshot_created',"
            "'refresh_retry_scheduled','refresh_dead_lettered','snapshot_marked_stale')",
            name=op.f("ck_career_analytics_audit_events_action_valid"),
        ),
        sa.CheckConstraint(
            "length(trace_id) = 32", name=op.f("ck_career_analytics_audit_events_trace_id_length")
        ),
        sa.CheckConstraint(
            "(actor_user_id IS NULL AND request_id IS NULL) OR "
            "(actor_user_id = owner_user_id AND request_id IS NOT NULL)",
            name=op.f("ck_career_analytics_audit_events_actor_context_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_career_analytics_audits_actor_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_analytics_audits_owner_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_analytics_audit_events")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_analytics_audits_owner_id"),
    )
    op.create_index(
        "ix_career_analytics_audits_owner_created",
        "career_analytics_audit_events",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_analytics_refresh_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column(
            "source_watermark_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("source_watermark_after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope IN ('overview','applications','readiness')",
            name=op.f("ck_career_analytics_refresh_jobs_scope_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','retry_wait','completed','dead_letter')",
            name=op.f("ck_career_analytics_refresh_jobs_status_valid"),
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL AND leased_until IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_until IS NOT NULL)",
            name=op.f("ck_career_analytics_refresh_jobs_lease_complete"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 10",
            name=op.f("ck_career_analytics_refresh_jobs_attempts_valid"),
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name=op.f("ck_career_analytics_refresh_jobs_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "length(trace_id) = 32", name=op.f("ck_career_analytics_refresh_jobs_trace_id_length")
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_career_analytics_refresh_jobs_version_positive")
        ),
        sa.CheckConstraint(
            "window_end >= window_start",
            name=op.f("ck_career_analytics_refresh_jobs_window_ordered"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_analytics_jobs_owner_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_analytics_refresh_jobs")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_analytics_jobs_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_career_analytics_jobs_owner_idempotency"
        ),
    )
    op.create_index(
        "ix_career_analytics_jobs_owner_scope_created",
        "career_analytics_refresh_jobs",
        ["owner_user_id", "scope", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_career_analytics_jobs_status_due",
        "career_analytics_refresh_jobs",
        ["status", "next_attempt_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_growth_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('goal_created','goal_updated','goal_deleted','milestone_created',"
            "'milestone_updated','milestone_deleted','development_item_created',"
            "'development_item_updated','development_item_deleted','review_created',"
            "'review_revised','review_finalized','review_deleted','career_health_analyzed',"
            "'career_health_deleted')",
            name=op.f("ck_career_growth_audit_events_action_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_audit_events_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_audit_events")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_audit_events_owner_id"),
    )
    op.create_index(
        "ix_career_growth_audit_events_owner_created",
        "career_growth_audit_events",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_career_growth_audit_events_owner_target",
        "career_growth_audit_events",
        ["owner_user_id", "target_kind", "target_id"],
        unique=False,
    )
    op.create_table(
        "career_growth_development_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name=op.f("ck_career_growth_development_items_completion_state_valid"),
        ),
        sa.CheckConstraint(
            "kind IN ('learning','certification','performance_review','promotion',"
            "'internal_mobility','annual_resume_refresh')",
            name=op.f("ck_career_growth_development_items_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('planned','in_progress','paused','completed','cancelled')",
            name=op.f("ck_career_growth_development_items_status_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_career_growth_development_items_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_development_items_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_development_items")),
        sa.UniqueConstraint(
            "owner_user_id", "id", name="uq_career_growth_development_items_owner_id"
        ),
    )
    op.create_index(
        "ix_career_growth_development_items_owner_kind_status",
        "career_growth_development_items",
        ["owner_user_id", "kind", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_career_growth_development_items_owner_updated",
        "career_growth_development_items",
        ["owner_user_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_growth_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_revision_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("statement_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("evidence_revised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_kind IN ('goal','milestone','development_item','review_version')",
            name=op.f("ck_career_growth_evidence_links_target_kind_valid"),
        ),
        sa.CheckConstraint(
            "octet_length(statement_sha256) = 32",
            name=op.f("ck_career_growth_evidence_links_statement_hash_length"),
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_career_growth_evidence_links_revision_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_evidence_links_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "evidence_id", "evidence_revision_id"],
            [
                "evidence_revisions.owner_user_id",
                "evidence_revisions.evidence_id",
                "evidence_revisions.id",
            ],
            name="fk_career_growth_evidence_links_owner_revision",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_evidence_links")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_evidence_links_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "target_kind",
            "target_id",
            "evidence_id",
            name="uq_career_growth_evidence_links_target_evidence",
        ),
    )
    op.create_index(
        "ix_career_growth_evidence_links_owner_evidence",
        "career_growth_evidence_links",
        ["owner_user_id", "evidence_id"],
        unique=False,
    )
    op.create_index(
        "ix_career_growth_evidence_links_owner_target",
        "career_growth_evidence_links",
        ["owner_user_id", "target_kind", "target_id"],
        unique=False,
    )
    op.create_table(
        "career_growth_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','paused','completed','cancelled')",
            name=op.f("ck_career_growth_goals_status_valid"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_career_growth_goals_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_goals_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_goals")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_goals_owner_id"),
    )
    op.create_index(
        "ix_career_growth_goals_owner_updated",
        "career_growth_goals",
        ["owner_user_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_growth_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(length=32), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name=op.f("ck_career_growth_idempotency_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_idempotency_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_idempotency")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_idempotency_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_career_growth_idempotency_owner_key"
        ),
    )
    op.create_index(
        "ix_career_growth_idempotency_owner_created",
        "career_growth_idempotency",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_growth_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("latest_version_id", sa.Uuid(), nullable=False),
        sa.Column("latest_version_number", sa.Integer(), nullable=False),
        sa.Column("latest_status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cadence IN ('quarterly','annual')", name=op.f("ck_career_growth_reviews_cadence_valid")
        ),
        sa.CheckConstraint(
            "latest_status IN ('draft','finalized')",
            name=op.f("ck_career_growth_reviews_latest_status_valid"),
        ),
        sa.CheckConstraint(
            "latest_version_number > 0",
            name=op.f("ck_career_growth_reviews_latest_version_positive"),
        ),
        sa.CheckConstraint(
            "period_end >= period_start", name=op.f("ck_career_growth_reviews_period_valid")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_career_growth_reviews_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_reviews_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_reviews")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_reviews_owner_id"),
    )
    op.create_index(
        "ix_career_growth_reviews_owner_period",
        "career_growth_reviews",
        ["owner_user_id", "period_end", "id"],
        unique=False,
    )
    op.create_table(
        "career_health_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("engine_version", sa.String(length=120), nullable=False),
        sa.Column("configuration_version", sa.String(length=120), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=120), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("formula_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("raw_score_basis_points", sa.Integer(), nullable=True),
        sa.Column("display_score", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("applicable_component_count", sa.Integer(), nullable=False),
        sa.Column("applicable_weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("insufficient_reason", sa.String(length=500), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'complete' AND raw_score_basis_points IS NOT NULL "
            "AND display_score IS NOT NULL AND insufficient_reason IS NULL "
            "AND label <> 'insufficient_data') OR "
            "(status = 'insufficient_data' AND raw_score_basis_points IS NULL "
            "AND display_score IS NULL AND insufficient_reason IS NOT NULL "
            "AND label = 'insufficient_data')",
            name=op.f("ck_career_health_analyses_result_state_valid"),
        ),
        sa.CheckConstraint(
            "label IN ('well_maintained','developing','needs_attention','insufficient_data')",
            name=op.f("ck_career_health_analyses_label_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('complete','insufficient_data')",
            name=op.f("ck_career_health_analyses_status_valid"),
        ),
        sa.CheckConstraint(
            "applicable_component_count BETWEEN 0 AND 5",
            name=op.f("ck_career_health_analyses_component_count_valid"),
        ),
        sa.CheckConstraint(
            "applicable_weight_basis_points BETWEEN 0 AND 10000",
            name=op.f("ck_career_health_analyses_applicable_weight_valid"),
        ),
        sa.CheckConstraint(
            "display_score IS NULL OR display_score BETWEEN 0 AND 100",
            name=op.f("ck_career_health_analyses_display_score_valid"),
        ),
        sa.CheckConstraint(
            "octet_length(snapshot_sha256) = 32",
            name=op.f("ck_career_health_analyses_snapshot_hash_length"),
        ),
        sa.CheckConstraint(
            "raw_score_basis_points IS NULL OR raw_score_basis_points BETWEEN 0 AND 10000",
            name=op.f("ck_career_health_analyses_raw_score_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_health_analyses_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_health_analyses")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_health_analyses_owner_id"),
    )
    op.create_index(
        "ix_career_health_analyses_owner_created",
        "career_health_analyses",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('story_created','story_updated','story_deleted','session_created',"
            "'session_updated','session_deleted','question_created','questions_generated',"
            "'note_created','note_updated','note_deleted','follow_up_draft_generated')",
            name=op.f("ck_interview_audit_events_action_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_interview_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_audit_events_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_audit_events")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_audit_events_owner_id"),
    )
    op.create_index(
        "ix_interview_audit_events_owner_created",
        "interview_audit_events",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_interview_audit_events_owner_target",
        "interview_audit_events",
        ["owner_user_id", "target_kind", "target_id"],
        unique=False,
    )
    op.create_table(
        "interview_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("resource_kind", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column(
            "response_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "response_snapshot IS NULL OR "
            "(resource_kind = 'star_story' AND jsonb_typeof(response_snapshot) = 'object')",
            name=op.f("ck_interview_idempotency_records_response_snapshot_scope_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_idempotency_records_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_idempotency_records")),
        sa.UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_interview_idempotency_owner_key"
        ),
    )
    op.create_index(
        "ix_interview_idempotency_owner_created",
        "interview_idempotency_records",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_sha256", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('recruiter_screen','behavioral','technical','hiring_manager',"
            "'panel','other')",
            name=op.f("ck_interview_sessions_kind_valid"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_interview_sessions_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_sessions_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_sessions")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_sessions_owner_id"),
    )
    op.create_index(
        "ix_interview_sessions_owner_application_updated",
        "interview_sessions",
        ["owner_user_id", "application_id", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_interview_sessions_owner_scheduled",
        "interview_sessions",
        ["owner_user_id", "scheduled_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_star_stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("personal_contribution", sa.Text(), nullable=False),
        sa.Column("metric_explanation", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("follow_up_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "origin IN ('user_authored','generated')",
            name=op.f("ck_interview_star_stories_origin_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','ready','archived')",
            name=op.f("ck_interview_star_stories_status_valid"),
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 1 AND 5", name=op.f("ck_interview_star_stories_confidence_valid")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_interview_star_stories_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_star_stories_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_star_stories")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_stories_owner_id"),
    )
    op.create_index(
        "ix_interview_stories_owner_application_updated",
        "interview_star_stories",
        ["owner_user_id", "application_id", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_interview_stories_owner_status_updated",
        "interview_star_stories",
        ["owner_user_id", "status", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('organization_created','organization_updated',"
            "'organization_deleted','contact_created','contact_updated','contact_deleted',"
            "'consent_granted','consent_withdrawn','note_created','interaction_recorded',"
            "'referral_created','referral_updated','template_created','template_updated',"
            "'reminder_created','reminder_updated','reminder_occurrence_materialized',"
            "'reminder_occurrence_due','reminder_occurrence_acknowledged',"
            "'reminder_occurrence_snoozed','reminder_occurrence_failed')",
            name=op.f("ck_networking_audit_events_networking_audit_action_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_networking_audit_actor", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_networking_audit_owner", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_audit_events")),
    )
    op.create_index(
        "ix_networking_audit_owner_created",
        "networking_audit_events",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_kind", sa.String(length=64), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name=op.f("ck_networking_idempotency_networking_idempotency_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_idempotency_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_idempotency")),
        sa.UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_networking_idempotency_owner_key"
        ),
    )
    op.create_index(
        "ix_networking_idempotency_owner_created",
        "networking_idempotency",
        ["owner_user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "networking_organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_search", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_networking_organizations_networking_organization_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_organizations_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_organizations")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_organizations_owner_id"),
    )
    op.create_index(
        "ix_networking_organizations_owner_updated",
        "networking_organizations",
        ["owner_user_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('introduction','follow_up','referral_request','thank_you','custom')",
            name=op.f("ck_networking_templates_networking_template_kind_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_networking_templates_networking_template_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_templates_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_templates")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_templates_owner_id"),
    )
    op.create_index(
        "ix_networking_templates_owner_updated",
        "networking_templates",
        ["owner_user_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_analytics_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','leased','published','dead_letter')",
            name=op.f("ck_career_analytics_outbox_status_valid"),
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL AND leased_until IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_until IS NOT NULL)",
            name=op.f("ck_career_analytics_outbox_lease_complete"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 10",
            name=op.f("ck_career_analytics_outbox_attempts_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["career_analytics_refresh_jobs.owner_user_id", "career_analytics_refresh_jobs.id"],
            name="fk_career_analytics_outbox_owner_job",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_analytics_outbox")),
        sa.UniqueConstraint("job_id", name="uq_career_analytics_outbox_job"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_analytics_outbox_owner_id"),
    )
    op.create_index(
        "ix_career_analytics_outbox_status_due",
        "career_analytics_outbox",
        ["status", "next_attempt_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_analytics_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("metric_definition_version", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("source_watermark", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope IN ('overview','applications','readiness')",
            name=op.f("ck_career_analytics_snapshots_scope_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('ready','stale','failed')",
            name=op.f("ck_career_analytics_snapshots_status_valid"),
        ),
        sa.CheckConstraint(
            "length(payload_sha256) = 64",
            name=op.f("ck_career_analytics_snapshots_payload_hash_length"),
        ),
        sa.CheckConstraint(
            "window_end >= window_start", name=op.f("ck_career_analytics_snapshots_window_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["career_analytics_refresh_jobs.owner_user_id", "career_analytics_refresh_jobs.id"],
            name="fk_career_analytics_snapshots_owner_job",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_analytics_snapshots")),
        sa.UniqueConstraint("job_id", name="uq_career_analytics_snapshots_job"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_analytics_snapshots_owner_id"),
    )
    op.create_index(
        "ix_career_analytics_snapshots_owner_scope_window",
        "career_analytics_snapshots",
        [
            "owner_user_id",
            "scope",
            "window_start",
            "window_end",
            "timezone",
            "created_at",
            "id",
        ],
        unique=False,
    )
    op.create_table(
        "career_growth_milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name=op.f("ck_career_growth_milestones_completion_state_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','cancelled')",
            name=op.f("ck_career_growth_milestones_status_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_career_growth_milestones_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "goal_id"],
            ["career_growth_goals.owner_user_id", "career_growth_goals.id"],
            name="fk_career_growth_milestones_owner_goal",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_milestones_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_milestones")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_growth_milestones_owner_id"),
    )
    op.create_index(
        "ix_career_growth_milestones_owner_goal_target",
        "career_growth_milestones",
        ["owner_user_id", "goal_id", "target_date", "id"],
        unique=False,
    )
    op.create_table(
        "career_growth_review_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("achievements", sa.Text(), nullable=True),
        sa.Column("growth_areas", sa.Text(), nullable=True),
        sa.Column("next_focus", sa.Text(), nullable=True),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("content_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','finalized')",
            name=op.f("ck_career_growth_review_versions_status_valid"),
        ),
        sa.CheckConstraint(
            "(version_number = 1 AND supersedes_version_id IS NULL) OR "
            "(version_number > 1 AND supersedes_version_id IS NOT NULL)",
            name=op.f("ck_career_growth_review_versions_predecessor_valid"),
        ),
        sa.CheckConstraint(
            "octet_length(content_sha256) = 32",
            name=op.f("ck_career_growth_review_versions_content_hash_length"),
        ),
        sa.CheckConstraint(
            "version_number > 0",
            name=op.f("ck_career_growth_review_versions_version_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "review_id"],
            ["career_growth_reviews.owner_user_id", "career_growth_reviews.id"],
            name="fk_career_growth_review_versions_owner_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "review_id", "supersedes_version_id"],
            [
                "career_growth_review_versions.owner_user_id",
                "career_growth_review_versions.review_id",
                "career_growth_review_versions.id",
            ],
            name="fk_career_growth_review_versions_owner_predecessor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_growth_review_versions_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_growth_review_versions")),
        sa.UniqueConstraint(
            "owner_user_id", "id", name="uq_career_growth_review_versions_owner_id"
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "review_id",
            "id",
            name="uq_career_growth_review_versions_owner_review_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "review_id",
            "id",
            "version_number",
            "status",
            name="uq_career_growth_review_versions_latest_state",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "review_id",
            "version_number",
            name="uq_career_growth_review_versions_number",
        ),
    )
    op.create_index(
        "ix_career_growth_review_versions_owner_review",
        "career_growth_review_versions",
        ["owner_user_id", "review_id", "version_number"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_career_growth_reviews_owner_latest_version",
        "career_growth_reviews",
        "career_growth_review_versions",
        [
            "owner_user_id",
            "id",
            "latest_version_id",
            "latest_version_number",
            "latest_status",
        ],
        [
            "owner_user_id",
            "review_id",
            "id",
            "version_number",
            "status",
        ],
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(
        """
        CREATE FUNCTION career_growth_validate_evidence_link_target()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_exists boolean;
            provenance_matches boolean;
        BEGIN
            CASE NEW.target_kind
                WHEN 'goal' THEN
                    PERFORM 1
                        FROM career_growth_goals
                        WHERE owner_user_id = NEW.owner_user_id
                          AND id = NEW.target_id
                        FOR KEY SHARE;
                    target_exists := FOUND;
                WHEN 'milestone' THEN
                    PERFORM 1
                        FROM career_growth_milestones
                        WHERE owner_user_id = NEW.owner_user_id
                          AND id = NEW.target_id
                        FOR KEY SHARE;
                    target_exists := FOUND;
                WHEN 'development_item' THEN
                    PERFORM 1
                        FROM career_growth_development_items
                        WHERE owner_user_id = NEW.owner_user_id
                          AND id = NEW.target_id
                        FOR KEY SHARE;
                    target_exists := FOUND;
                WHEN 'review_version' THEN
                    PERFORM 1
                        FROM career_growth_review_versions
                        WHERE owner_user_id = NEW.owner_user_id
                          AND id = NEW.target_id
                        FOR KEY SHARE;
                    target_exists := FOUND;
                ELSE
                    target_exists := false;
            END CASE;
            IF NOT target_exists THEN
                RAISE EXCEPTION
                    'career growth evidence-link target does not exist for its owner'
                    USING ERRCODE = '23503';
            END IF;
            SELECT EXISTS (
                SELECT 1
                FROM evidence_revisions
                WHERE owner_user_id = NEW.owner_user_id
                  AND evidence_id = NEW.evidence_id
                  AND id = NEW.evidence_revision_id
                  AND revision = NEW.revision_number
                  AND created_at = NEW.evidence_revised_at
                  AND sha256(convert_to(statement, 'UTF8')) = NEW.statement_sha256
            ) INTO provenance_matches;
            IF NOT provenance_matches THEN
                RAISE EXCEPTION
                    'career growth evidence-link provenance does not match its exact revision'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_career_growth_evidence_link_target
        BEFORE INSERT OR UPDATE
        ON career_growth_evidence_links
        FOR EACH ROW
        EXECUTE FUNCTION career_growth_validate_evidence_link_target();
        """
    )
    op.execute(
        """
        CREATE FUNCTION career_growth_validate_review_predecessor()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            predecessor_matches boolean;
        BEGIN
            IF NEW.version_number = 1 THEN
                RETURN NEW;
            END IF;
            SELECT EXISTS (
                SELECT 1
                FROM career_growth_review_versions
                WHERE owner_user_id = NEW.owner_user_id
                  AND review_id = NEW.review_id
                  AND id = NEW.supersedes_version_id
                  AND version_number = NEW.version_number - 1
            ) INTO predecessor_matches;
            IF NOT predecessor_matches THEN
                RAISE EXCEPTION
                    'career growth review predecessor is not the prior version'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_career_growth_review_predecessor
        BEFORE INSERT OR UPDATE OF
            owner_user_id, review_id, version_number, supersedes_version_id
        ON career_growth_review_versions
        FOR EACH ROW
        EXECUTE FUNCTION career_growth_validate_review_predecessor();
        """
    )
    op.execute(
        """
        CREATE FUNCTION career_growth_delete_target_links()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            DELETE FROM career_growth_evidence_links
            WHERE owner_user_id = OLD.owner_user_id
              AND target_kind = TG_ARGV[0]
              AND target_id = OLD.id;
            RETURN OLD;
        END;
        $$;
        """
    )
    for table_name, target_kind in (
        ("career_growth_goals", "goal"),
        ("career_growth_milestones", "milestone"),
        ("career_growth_development_items", "development_item"),
        ("career_growth_review_versions", "review_version"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_evidence_link_cleanup
            BEFORE DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION career_growth_delete_target_links('{target_kind}');
            """
        )
    op.create_table(
        "career_health_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=40), nullable=False),
        sa.Column("configured_weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("applicable", sa.Boolean(), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=True),
        sa.Column("contribution_basis_points", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('evidence_currency','goal_progress',"
            "'development_follow_through','review_cadence','readiness_maintenance')",
            name=op.f("ck_career_health_components_dimension_valid"),
        ),
        sa.CheckConstraint(
            "(score_basis_points IS NULL AND contribution_basis_points IS NULL) OR "
            "(score_basis_points IS NOT NULL AND contribution_basis_points IS NOT NULL)",
            name=op.f("ck_career_health_components_score_contribution_pair_valid"),
        ),
        sa.CheckConstraint(
            "applicable OR (score_basis_points IS NULL AND contribution_basis_points IS NULL)",
            name=op.f("ck_career_health_components_applicability_valid"),
        ),
        sa.CheckConstraint(
            "configured_weight_basis_points BETWEEN 0 AND 10000",
            name=op.f("ck_career_health_components_weight_valid"),
        ),
        sa.CheckConstraint(
            "contribution_basis_points IS NULL OR contribution_basis_points BETWEEN 0 AND 10000",
            name=op.f("ck_career_health_components_contribution_valid"),
        ),
        sa.CheckConstraint(
            "score_basis_points IS NULL OR score_basis_points BETWEEN 0 AND 10000",
            name=op.f("ck_career_health_components_score_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["career_health_analyses.owner_user_id", "career_health_analyses.id"],
            name="fk_career_health_components_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_health_components_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_health_components")),
        sa.UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_career_health_components_dimension",
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_health_components_owner_id"),
    )
    op.create_index(
        "ix_career_health_components_owner_analysis",
        "career_health_components",
        ["owner_user_id", "analysis_id"],
        unique=False,
    )
    op.create_table(
        "career_health_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.CheckConstraint(
            "severity IN ('information','attention')",
            name=op.f("ck_career_health_findings_severity_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["career_health_analyses.owner_user_id", "career_health_analyses.id"],
            name="fk_career_health_findings_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_health_findings_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_health_findings")),
        sa.UniqueConstraint(
            "owner_user_id", "analysis_id", "code", name="uq_career_health_findings_code"
        ),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_career_health_findings_owner_id"),
    )
    op.create_index(
        "ix_career_health_findings_owner_analysis",
        "career_health_findings",
        ["owner_user_id", "analysis_id"],
        unique=False,
    )
    op.create_table(
        "interview_follow_up_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_follow_up_drafts_owner_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_follow_up_drafts_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_follow_up_drafts")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_follow_up_drafts_owner_id"),
    )
    op.create_index(
        "ix_interview_follow_up_drafts_owner_session_created",
        "interview_follow_up_drafts",
        ["owner_user_id", "session_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column(
            "source_requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("source_claim_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('behavioral','role_specific','technical','company','follow_up','custom')",
            name=op.f("ck_interview_questions_kind_valid"),
        ),
        sa.CheckConstraint(
            "ordinal > 0",
            name=op.f("ck_interview_questions_ordinal_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_questions_owner_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_questions_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_questions")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_questions_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "session_id",
            "ordinal",
            name="uq_interview_questions_owner_session_ordinal",
        ),
    )
    op.create_index(
        "ix_interview_questions_owner_session_created",
        "interview_questions",
        ["owner_user_id", "session_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_session_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('private_note','reflection')",
            name=op.f("ck_interview_session_notes_kind_valid"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_interview_session_notes_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_session_notes_owner_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_session_notes_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_session_notes")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_interview_session_notes_owner_id"),
    )
    op.create_index(
        "ix_interview_session_notes_owner_session_created",
        "interview_session_notes",
        ["owner_user_id", "session_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "interview_story_claim_pins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("source_claim_id", sa.Uuid(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_sha256", sa.String(length=64), nullable=False),
        sa.Column("strong", sa.Boolean(), nullable=False),
        sa.Column("field_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_pins", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "story_id"],
            ["interview_star_stories.owner_user_id", "interview_star_stories.id"],
            name="fk_interview_story_claim_pins_owner_story",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_interview_story_claim_pins_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_story_claim_pins")),
        sa.UniqueConstraint(
            "owner_user_id",
            "story_id",
            "source_claim_id",
            name="uq_interview_story_claim_pins_claim",
        ),
    )
    op.create_index(
        "ix_interview_story_claim_pins_source_claim",
        "interview_story_claim_pins",
        ["owner_user_id", "source_claim_id", "story_id"],
        unique=False,
    )
    op.create_table(
        "networking_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("profile_url", sa.String(length=500), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("relationship_stage", sa.String(length=24), nullable=False),
        sa.Column("referral_state", sa.String(length=24), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_search", sa.Text(), nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "referral_state IN ('none','considering','requested','referred','declined',"
            "'cancelled')",
            name=op.f("ck_networking_contacts_networking_contact_referral_state_valid"),
        ),
        sa.CheckConstraint(
            "relationship_stage IN ('new','warm','active','trusted','dormant','archived')",
            name=op.f("ck_networking_contacts_networking_contact_stage_valid"),
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR ("
            "organization_id IS NULL AND name = '[deleted]' AND role IS NULL "
            "AND email IS NULL AND phone IS NULL AND profile_url IS NULL "
            "AND location IS NULL AND relationship_stage = 'archived' "
            "AND referral_state = 'cancelled' AND tags = '[]'::jsonb "
            "AND normalized_search = '[deleted]' AND last_contact_at IS NULL "
            "AND next_contact_at IS NULL)",
            name=op.f("ck_networking_contacts_networking_contact_deleted_redacted"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_networking_contacts_networking_contact_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "organization_id"],
            ["networking_organizations.owner_user_id", "networking_organizations.id"],
            name="fk_networking_contacts_owner_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_networking_contacts_owner", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_contacts")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_contacts_owner_id"),
    )
    op.create_index(
        "ix_networking_contacts_owner_next_contact",
        "networking_contacts",
        ["owner_user_id", "next_contact_at"],
        unique=False,
    )
    op.create_index(
        "ix_networking_contacts_owner_organization",
        "networking_contacts",
        ["owner_user_id", "organization_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_networking_contacts_owner_stage",
        "networking_contacts",
        ["owner_user_id", "relationship_stage", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_networking_contacts_owner_updated",
        "networking_contacts",
        ["owner_user_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_consent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('granted','withdrawn')",
            name=op.f("ck_networking_consent_events_networking_consent_action_valid"),
        ),
        sa.CheckConstraint(
            "purpose IN ('collection','storage','outreach')",
            name=op.f("ck_networking_consent_events_networking_consent_purpose_valid"),
        ),
        sa.CheckConstraint(
            "policy_version IN ('networking-contact-consent/1','contact-deletion-v1')",
            name=op.f("ck_networking_consent_events_networking_consent_policy_version_valid"),
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name=op.f("ck_networking_consent_events_networking_consent_sequence_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_networking_consent_actor", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_consent_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_networking_consent_owner", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_consent_events")),
        sa.UniqueConstraint(
            "owner_user_id", "contact_id", "sequence", name="uq_networking_consent_contact_sequence"
        ),
    )
    op.create_index(
        "ix_networking_consent_contact_sequence",
        "networking_consent_events",
        ["owner_user_id", "contact_id", "sequence"],
        unique=False,
    )
    op.create_table(
        "networking_contact_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "deleted_at IS NULL OR body = '[deleted]'",
            name=op.f("ck_networking_contact_notes_networking_note_deleted_redacted"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_notes_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_networking_notes_owner", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_contact_notes")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_contact_notes_owner_id"),
    )
    op.create_index(
        "ix_networking_notes_contact_created",
        "networking_contact_notes",
        ["owner_user_id", "contact_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("direction", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("delivery_state", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "delivery_state = 'recorded_only'",
            name=op.f("ck_networking_interactions_networking_interaction_record_only"),
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR summary = '[deleted]'",
            name=op.f("ck_networking_interactions_networking_interaction_deleted_redacted"),
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound','mutual')",
            name=op.f("ck_networking_interactions_networking_interaction_direction_valid"),
        ),
        sa.CheckConstraint(
            "kind IN ('email','call','meeting','message','social','referral','other')",
            name=op.f("ck_networking_interactions_networking_interaction_kind_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_interactions_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "template_id"],
            ["networking_templates.owner_user_id", "networking_templates.id"],
            name="fk_networking_interactions_owner_template",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_interactions_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_interactions")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_interactions_owner_id"),
    )
    op.create_index(
        "ix_networking_interactions_contact_occurred",
        "networking_interactions",
        ["owner_user_id", "contact_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_referrals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('planned','requested','referred','declined','cancelled')",
            name=op.f("ck_networking_referrals_networking_referral_status_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_networking_referrals_networking_referral_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_referrals_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_referrals_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_referrals")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_referrals_owner_id"),
    )
    op.create_index(
        "ix_networking_referrals_contact_updated",
        "networking_referrals",
        ["owner_user_id", "contact_id", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_networking_referrals_owner_application",
        "networking_referrals",
        ["owner_user_id", "application_id"],
        unique=False,
    )
    op.create_table(
        "networking_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recurrence_days", sa.Integer(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','completed','cancelled')",
            name=op.f("ck_networking_reminders_networking_reminder_status_valid"),
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 20",
            name=op.f("ck_networking_reminders_networking_reminder_attempts_valid"),
        ),
        sa.CheckConstraint(
            "recurrence_days IS NULL OR recurrence_days BETWEEN 1 AND 365",
            name=op.f("ck_networking_reminders_networking_reminder_recurrence_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_networking_reminders_networking_reminder_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_reminders_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_reminders_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_reminders")),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_networking_reminders_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            "contact_id",
            name="uq_networking_reminders_owner_id_contact",
        ),
    )
    op.create_index(
        "ix_networking_reminders_contact_due",
        "networking_reminders",
        ["owner_user_id", "contact_id", "due_at", "id"],
        unique=False,
    )
    op.create_table(
        "networking_reminder_occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('scheduled','due','acknowledged','cancelled','dead_letter')",
            name=op.f("ck_networking_reminder_occurrences_networking_occurrence_status_valid"),
        ),
        sa.CheckConstraint(
            "occurrence_number > 0",
            name=op.f("ck_networking_reminder_occurrences_networking_occurrence_number_positive"),
        ),
        sa.CheckConstraint(
            "trace_id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_networking_reminder_occurrences_networking_occurrence_trace_id_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_occurrences_owner_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "reminder_id", "contact_id"],
            [
                "networking_reminders.owner_user_id",
                "networking_reminders.id",
                "networking_reminders.contact_id",
            ],
            name="fk_networking_occurrences_owner_reminder_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_occurrences_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_reminder_occurrences")),
        sa.UniqueConstraint(
            "owner_user_id", "id", name="uq_networking_reminder_occurrences_owner_id"
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "reminder_id",
            "occurrence_number",
            name="uq_networking_occurrence_reminder_number",
        ),
    )
    op.create_index(
        "ix_networking_occurrences_reminder_scheduled",
        "networking_reminder_occurrences",
        ["owner_user_id", "reminder_id", "scheduled_for"],
        unique=False,
    )
    op.create_table(
        "networking_reminder_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'leased' AND lease_token IS NULL "
            "AND lease_expires_at IS NULL))",
            name=op.f("ck_networking_reminder_outbox_networking_outbox_lease_consistent"),
        ),
        sa.CheckConstraint(
            "kind = 'local_reminder_due'",
            name=op.f("ck_networking_reminder_outbox_networking_outbox_local_only"),
        ),
        sa.CheckConstraint(
            "trace_id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_networking_reminder_outbox_networking_outbox_trace_id_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','leased','processed','cancelled','dead_letter')",
            name=op.f("ck_networking_reminder_outbox_networking_outbox_status_valid"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 20 "
            "AND attempt_count <= max_attempts",
            name=op.f("ck_networking_reminder_outbox_networking_outbox_attempts_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "occurrence_id"],
            ["networking_reminder_occurrences.owner_user_id", "networking_reminder_occurrences.id"],
            name="fk_networking_outbox_owner_occurrence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_networking_outbox_owner", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networking_reminder_outbox")),
        sa.UniqueConstraint(
            "owner_user_id", "occurrence_id", name="uq_networking_outbox_owner_occurrence"
        ),
    )
    op.create_index(
        "ix_networking_outbox_claim",
        "networking_reminder_outbox",
        ["status", "available_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_networking_outbox_lease",
        "networking_reminder_outbox",
        ["status", "lease_expires_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove Phase 9 data in reverse dependency order."""
    op.drop_index("ix_networking_outbox_lease", table_name="networking_reminder_outbox")
    op.drop_index("ix_networking_outbox_claim", table_name="networking_reminder_outbox")
    op.drop_table("networking_reminder_outbox")
    op.drop_index(
        "ix_networking_occurrences_reminder_scheduled", table_name="networking_reminder_occurrences"
    )
    op.drop_table("networking_reminder_occurrences")
    op.drop_index("ix_networking_reminders_contact_due", table_name="networking_reminders")
    op.drop_table("networking_reminders")
    op.drop_index("ix_networking_referrals_owner_application", table_name="networking_referrals")
    op.drop_index("ix_networking_referrals_contact_updated", table_name="networking_referrals")
    op.drop_table("networking_referrals")
    op.drop_index(
        "ix_networking_interactions_contact_occurred", table_name="networking_interactions"
    )
    op.drop_table("networking_interactions")
    op.drop_index("ix_networking_notes_contact_created", table_name="networking_contact_notes")
    op.drop_table("networking_contact_notes")
    op.drop_index("ix_networking_consent_contact_sequence", table_name="networking_consent_events")
    op.drop_table("networking_consent_events")
    op.drop_index("ix_networking_contacts_owner_updated", table_name="networking_contacts")
    op.drop_index("ix_networking_contacts_owner_stage", table_name="networking_contacts")
    op.drop_index("ix_networking_contacts_owner_organization", table_name="networking_contacts")
    op.drop_index("ix_networking_contacts_owner_next_contact", table_name="networking_contacts")
    op.drop_table("networking_contacts")
    op.drop_index(
        "ix_interview_story_claim_pins_source_claim", table_name="interview_story_claim_pins"
    )
    op.drop_table("interview_story_claim_pins")
    op.drop_index(
        "ix_interview_session_notes_owner_session_created", table_name="interview_session_notes"
    )
    op.drop_table("interview_session_notes")
    op.drop_index("ix_interview_questions_owner_session_created", table_name="interview_questions")
    op.drop_table("interview_questions")
    op.drop_index(
        "ix_interview_follow_up_drafts_owner_session_created",
        table_name="interview_follow_up_drafts",
    )
    op.drop_table("interview_follow_up_drafts")
    op.drop_index("ix_career_health_findings_owner_analysis", table_name="career_health_findings")
    op.drop_table("career_health_findings")
    op.drop_index(
        "ix_career_health_components_owner_analysis", table_name="career_health_components"
    )
    op.drop_table("career_health_components")
    op.drop_constraint(
        "fk_career_growth_reviews_owner_latest_version",
        "career_growth_reviews",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_career_growth_review_versions_owner_review", table_name="career_growth_review_versions"
    )
    op.drop_table("career_growth_review_versions")
    op.execute("DROP FUNCTION IF EXISTS career_growth_validate_review_predecessor()")
    op.drop_index(
        "ix_career_growth_milestones_owner_goal_target", table_name="career_growth_milestones"
    )
    op.drop_table("career_growth_milestones")
    op.drop_index(
        "ix_career_analytics_snapshots_owner_scope_window", table_name="career_analytics_snapshots"
    )
    op.drop_table("career_analytics_snapshots")
    op.drop_index("ix_career_analytics_outbox_status_due", table_name="career_analytics_outbox")
    op.drop_table("career_analytics_outbox")
    op.drop_index("ix_networking_templates_owner_updated", table_name="networking_templates")
    op.drop_table("networking_templates")
    op.drop_index(
        "ix_networking_organizations_owner_updated", table_name="networking_organizations"
    )
    op.drop_table("networking_organizations")
    op.drop_index("ix_networking_idempotency_owner_created", table_name="networking_idempotency")
    op.drop_table("networking_idempotency")
    op.drop_index("ix_networking_audit_owner_created", table_name="networking_audit_events")
    op.drop_table("networking_audit_events")
    op.drop_index("ix_interview_stories_owner_status_updated", table_name="interview_star_stories")
    op.drop_index(
        "ix_interview_stories_owner_application_updated", table_name="interview_star_stories"
    )
    op.drop_table("interview_star_stories")
    op.drop_index("ix_interview_sessions_owner_scheduled", table_name="interview_sessions")
    op.drop_index(
        "ix_interview_sessions_owner_application_updated", table_name="interview_sessions"
    )
    op.drop_table("interview_sessions")
    op.drop_index(
        "ix_interview_idempotency_owner_created", table_name="interview_idempotency_records"
    )
    op.drop_table("interview_idempotency_records")
    op.drop_index("ix_interview_audit_events_owner_target", table_name="interview_audit_events")
    op.drop_index("ix_interview_audit_events_owner_created", table_name="interview_audit_events")
    op.drop_table("interview_audit_events")
    op.drop_index("ix_career_health_analyses_owner_created", table_name="career_health_analyses")
    op.drop_table("career_health_analyses")
    op.drop_index("ix_career_growth_reviews_owner_period", table_name="career_growth_reviews")
    op.drop_table("career_growth_reviews")
    op.drop_index(
        "ix_career_growth_idempotency_owner_created", table_name="career_growth_idempotency"
    )
    op.drop_table("career_growth_idempotency")
    op.drop_index("ix_career_growth_goals_owner_updated", table_name="career_growth_goals")
    op.drop_table("career_growth_goals")
    op.drop_index(
        "ix_career_growth_evidence_links_owner_target", table_name="career_growth_evidence_links"
    )
    op.drop_index(
        "ix_career_growth_evidence_links_owner_evidence", table_name="career_growth_evidence_links"
    )
    op.drop_table("career_growth_evidence_links")
    op.execute("DROP FUNCTION IF EXISTS career_growth_validate_evidence_link_target()")
    op.drop_constraint(
        "uq_evidence_revisions_owner_evidence_id",
        "evidence_revisions",
        type_="unique",
    )
    op.drop_index(
        "ix_career_growth_development_items_owner_updated",
        table_name="career_growth_development_items",
    )
    op.drop_index(
        "ix_career_growth_development_items_owner_kind_status",
        table_name="career_growth_development_items",
    )
    op.drop_table("career_growth_development_items")
    op.execute("DROP FUNCTION IF EXISTS career_growth_delete_target_links()")
    op.drop_index(
        "ix_career_growth_audit_events_owner_target", table_name="career_growth_audit_events"
    )
    op.drop_index(
        "ix_career_growth_audit_events_owner_created", table_name="career_growth_audit_events"
    )
    op.drop_table("career_growth_audit_events")
    op.drop_index("ix_career_analytics_jobs_status_due", table_name="career_analytics_refresh_jobs")
    op.drop_index(
        "ix_career_analytics_jobs_owner_scope_created", table_name="career_analytics_refresh_jobs"
    )
    op.drop_table("career_analytics_refresh_jobs")
    op.drop_index(
        "ix_career_analytics_audits_owner_created", table_name="career_analytics_audit_events"
    )
    op.drop_table("career_analytics_audit_events")
    # ### end Alembic commands ###
