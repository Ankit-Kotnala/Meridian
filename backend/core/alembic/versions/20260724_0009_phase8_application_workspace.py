"""Add Phase 8 application workspace and grounded pack tables.

Revision ID: 20260724_0009
Revises: 20260719_0008
Create Date: 2026-07-24 00:09:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_0009"
down_revision: str | None = "20260719_0008"
branch_labels: str | None = None
depends_on: str | None = None

_STAGES = (
    "saved",
    "researching",
    "preparing",
    "ready_to_apply",
    "applied",
    "recruiter_screen",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
)
_REFERRAL_STATUSES = ("none", "needed", "requested", "referred")
_OUTCOME_STATUSES = ("none", "offer", "rejected", "withdrawn")
_EVENT_KINDS = (
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
_DOCUMENT_KINDS = (
    "tailored_resume",
    "cover_letter",
    "professional_bio",
    "interest_answer",
    "fit_answer",
    "recruiter_message",
    "hiring_manager_message",
    "referral_request",
    "linkedin_connection_note",
    "follow_up_email",
    "interview_introduction",
    "achievement_summary",
)
_DOCUMENT_STATUSES = ("generated", "blocked", "deleted")
_PACK_STATUSES = ("generated", "blocked")
_CONSISTENCY_STATUSES = ("passed", "warning", "failed")
_AUDIT_ACTIONS = (
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


def upgrade() -> None:
    # Phase 6 shipped before exact evidence-revision pins were persisted. Preserve
    # those historical claims as explicitly unpinned; only claims created after
    # this forward migration carry a complete, machine-checkable provenance tuple.
    op.add_column(
        "change_operation_claims",
        sa.Column("evidence_revision_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "change_operation_claims",
        sa.Column("evidence_revision_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "change_operation_claims",
        sa.Column("evidence_statement_sha256", sa.String(length=64), nullable=True),
    )
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

    op.create_table(
        "application_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("job_version", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("job_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("job_source_sha256", sa.String(length=64), nullable=False),
        sa.Column("job_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "requirement_support",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("resume_version_id", sa.Uuid(), nullable=False),
        sa.Column("resume_version_number", sa.Integer(), nullable=False),
        sa.Column("resume_title", sa.String(length=120), nullable=False),
        sa.Column("resume_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_pins", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resume_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column("follow_up_at", sa.Date(), nullable=True),
        sa.Column("contacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("referral_status", sa.String(length=24), nullable=False),
        sa.Column("outcome_status", sa.String(length=24), nullable=False),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("offer_summary", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"stage IN ({_values(_STAGES)})",
            name="ck_application_records_stage_valid",
        ),
        sa.CheckConstraint(
            f"referral_status IN ({_values(_REFERRAL_STATUSES)})",
            name="ck_application_records_referral_status_valid",
        ),
        sa.CheckConstraint(
            f"outcome_status IN ({_values(_OUTCOME_STATUSES)})",
            name="ck_application_records_outcome_status_valid",
        ),
        sa.CheckConstraint(
            "("
            "(stage = 'offer' AND outcome_status = 'offer') OR "
            "(stage = 'rejected' AND outcome_status = 'rejected') OR "
            "(stage = 'withdrawn' AND outcome_status = 'withdrawn') OR "
            "("
            "stage NOT IN ('offer','rejected','withdrawn') "
            "AND outcome_status = 'none'"
            ")"
            ")",
            name="ck_application_records_stage_outcome_consistent",
        ),
        sa.CheckConstraint("job_version > 0", name="ck_application_records_job_version_positive"),
        sa.CheckConstraint(
            "length(job_source_sha256) = 64",
            name="ck_application_records_job_source_sha256_length",
        ),
        sa.CheckConstraint(
            "resume_version_number > 0",
            name="ck_application_records_resume_version_number_positive",
        ),
        sa.CheckConstraint("version > 0", name="ck_application_records_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_records_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "resume_version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_application_records_owner_resume_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_records_owner_id"),
    )
    op.create_index(
        "ix_application_records_owner_updated",
        "application_records",
        ["owner_user_id", "updated_at", "id"],
    )
    op.create_index(
        "ix_application_records_owner_stage",
        "application_records",
        ["owner_user_id", "stage", "updated_at"],
    )
    op.create_index(
        "ix_application_records_owner_deadline",
        "application_records",
        ["owner_user_id", "application_deadline"],
    )
    op.create_index(
        "ix_application_records_owner_follow_up",
        "application_records",
        ["owner_user_id", "follow_up_at"],
    )
    op.create_index(
        "ix_application_records_owner_source",
        "application_records",
        ["owner_user_id", "source"],
    )
    op.create_index(
        "ix_application_records_owner_industry",
        "application_records",
        ["owner_user_id", "industry"],
    )

    op.create_table(
        "application_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_application_tasks_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_tasks_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_tasks_owner_application",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_tasks_owner_id"),
    )
    op.create_index(
        "ix_application_tasks_application_due",
        "application_tasks",
        ["owner_user_id", "application_id", "due_at", "created_at", "id"],
    )
    op.create_index(
        "ix_application_tasks_owner_due",
        "application_tasks",
        ["owner_user_id", "due_at", "id"],
    )

    op.create_table(
        "application_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_notes_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_notes_owner_application",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_notes_owner_id"),
    )
    op.create_index(
        "ix_application_notes_application_created",
        "application_notes",
        ["owner_user_id", "application_id", "created_at", "id"],
    )

    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"event_kind IN ({_values(_EVENT_KINDS)})",
            name="ck_application_events_event_kind_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_events_owner_application",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_events_owner_id"),
    )
    op.create_index(
        "ix_application_events_application_occurred",
        "application_events",
        ["owner_user_id", "application_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_application_events_application_kind",
        "application_events",
        ["owner_user_id", "application_id", "event_kind"],
    )
    op.create_index(
        "ix_application_events_owner_occurred",
        "application_events",
        ["owner_user_id", "occurred_at", "id"],
    )

    op.create_table(
        "application_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("job_version", sa.Integer(), nullable=False),
        sa.Column("resume_version_id", sa.Uuid(), nullable=False),
        sa.Column("resume_version_number", sa.Integer(), nullable=False),
        sa.Column("application_version", sa.Integer(), nullable=False),
        sa.Column(
            "evidence_revision_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consistency_status", sa.String(length=16), nullable=False),
        sa.Column("consistency_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_values(_PACK_STATUSES)})",
            name="ck_application_packs_status_valid",
        ),
        sa.CheckConstraint(
            f"consistency_status IN ({_values(_CONSISTENCY_STATUSES)})",
            name="ck_application_packs_consistency_status_valid",
        ),
        sa.CheckConstraint("job_version > 0", name="ck_application_packs_job_version_positive"),
        sa.CheckConstraint(
            "resume_version_number > 0",
            name="ck_application_packs_resume_version_number_positive",
        ),
        sa.CheckConstraint(
            "application_version > 0",
            name="ck_application_packs_application_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_packs_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_packs_owner_application",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_packs_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            "application_id",
            name="uq_application_packs_owner_id_application",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_application_packs_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_application_packs_application_created",
        "application_packs",
        ["owner_user_id", "application_id", "created_at", "id"],
    )

    op.create_table(
        "application_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "source_requirement_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("claims", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consistency_status", sa.String(length=16), nullable=False),
        sa.Column("consistency_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"kind IN ({_values(_DOCUMENT_KINDS)})",
            name="ck_application_documents_kind_valid",
        ),
        sa.CheckConstraint(
            f"status IN ({_values(_DOCUMENT_STATUSES)})",
            name="ck_application_documents_status_valid",
        ),
        sa.CheckConstraint(
            f"consistency_status IN ({_values(_CONSISTENCY_STATUSES)})",
            name="ck_application_documents_consistency_status_valid",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64",
            name="ck_application_documents_content_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_documents_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_documents_owner_application",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "pack_id", "application_id"],
            [
                "application_packs.owner_user_id",
                "application_packs.id",
                "application_packs.application_id",
            ],
            name="fk_application_documents_owner_pack_application",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_application_documents_owner_id"),
    )
    op.create_index(
        "ix_application_documents_application_kind",
        "application_documents",
        ["owner_user_id", "application_id", "kind"],
    )

    op.create_table(
        "application_workspace_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("response_kind", sa.String(length=80), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_workspace_idempotency_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_application_workspace_idempotency_owner_key",
        ),
    )
    op.create_index(
        "ix_application_workspace_idempotency_owner_created",
        "application_workspace_idempotency",
        ["owner_user_id", "created_at"],
    )

    op.create_table(
        "application_workspace_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"action IN ({_values(_AUDIT_ACTIONS)})",
            name="ck_application_workspace_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_workspace_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_application_workspace_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_workspace_audit_owner_created",
        "application_workspace_audit_events",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_workspace_audit_owner_created",
        table_name="application_workspace_audit_events",
    )
    op.drop_table("application_workspace_audit_events")
    op.drop_index(
        "ix_application_workspace_idempotency_owner_created",
        table_name="application_workspace_idempotency",
    )
    op.drop_table("application_workspace_idempotency")
    op.drop_index(
        "ix_application_documents_application_kind",
        table_name="application_documents",
    )
    op.drop_table("application_documents")
    op.drop_index(
        "ix_application_packs_application_created",
        table_name="application_packs",
    )
    op.drop_table("application_packs")
    op.drop_index(
        "ix_application_events_owner_occurred",
        table_name="application_events",
    )
    op.drop_index(
        "ix_application_events_application_kind",
        table_name="application_events",
    )
    op.drop_index(
        "ix_application_events_application_occurred",
        table_name="application_events",
    )
    op.drop_table("application_events")
    op.drop_index(
        "ix_application_notes_application_created",
        table_name="application_notes",
    )
    op.drop_table("application_notes")
    op.drop_index("ix_application_tasks_application_due", table_name="application_tasks")
    op.drop_table("application_tasks")
    op.drop_index("ix_application_records_owner_industry", table_name="application_records")
    op.drop_index("ix_application_records_owner_source", table_name="application_records")
    op.drop_index("ix_application_records_owner_follow_up", table_name="application_records")
    op.drop_index("ix_application_records_owner_deadline", table_name="application_records")
    op.drop_index("ix_application_records_owner_stage", table_name="application_records")
    op.drop_index("ix_application_records_owner_updated", table_name="application_records")
    op.drop_table("application_records")
    op.drop_constraint(
        "ck_change_operation_claims_evidence_provenance_complete",
        "change_operation_claims",
        type_="check",
    )
    op.drop_column("change_operation_claims", "evidence_statement_sha256")
    op.drop_column("change_operation_claims", "evidence_revision_number")
    op.drop_column("change_operation_claims", "evidence_revision_id")
