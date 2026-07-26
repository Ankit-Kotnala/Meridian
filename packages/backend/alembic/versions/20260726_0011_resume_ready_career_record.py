"""Add observed semantic imports and resume-ready Career Record facts.

Revision ID: 20260726_0011
Revises: 20260724_0010
Create Date: 2026-07-26 03:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0011"
down_revision: str | None = "20260724_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_map(table_name: str) -> dict[str, dict[str, object]]:
    return {
        str(column["name"]): dict(column)
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _constraint_names(
    table_name: str,
    inspector_method: str,
) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    constraints = getattr(inspector, inspector_method)(table_name)
    return {
        str(constraint["name"]) for constraint in constraints if constraint.get("name") is not None
    }


def _foreign_key(
    table_name: str,
    constraint_name: str,
) -> dict[str, object] | None:
    for constraint in sa.inspect(op.get_bind()).get_foreign_keys(table_name):
        if constraint.get("name") == constraint_name:
            return dict(constraint)
    return None


def _has_check_containing(table_name: str, sql_fragment: str) -> bool:
    return any(
        sql_fragment in str(constraint.get("sqltext", ""))
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
    )


def _repair_phase9_schema_drift() -> None:
    """Repair pre-release Phase 9 databases without rewriting their revision.

    The canonical ``20260724_0010`` migration owns these objects. Long-lived
    development databases may have been stamped with earlier copies of that
    still-unreleased revision. This migration adds or corrects only canonical
    objects, fails instead of discarding conflicting data, and deliberately
    leaves the repairs in place on downgrade.
    """

    audit_columns = _column_map("career_analytics_audit_events")
    if audit_columns["actor_user_id"]["nullable"] is False:
        op.alter_column(
            "career_analytics_audit_events",
            "actor_user_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
    if audit_columns["request_id"]["nullable"] is False:
        op.alter_column(
            "career_analytics_audit_events",
            "request_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )
    if (
        _foreign_key(
            "career_analytics_audit_events",
            "fk_career_analytics_audits_actor_user",
        )
        is None
    ):
        op.create_foreign_key(
            "fk_career_analytics_audits_actor_user",
            "career_analytics_audit_events",
            "users",
            ["actor_user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    snapshot_columns = _column_map("career_analytics_snapshots")
    if "timezone" not in snapshot_columns:
        op.add_column(
            "career_analytics_snapshots",
            sa.Column("timezone", sa.String(length=80), nullable=True),
        )
        op.execute(
            """
            UPDATE career_analytics_snapshots AS snapshot
            SET timezone = refresh_job.timezone
            FROM career_analytics_refresh_jobs AS refresh_job
            WHERE refresh_job.owner_user_id = snapshot.owner_user_id
              AND refresh_job.id = snapshot.job_id
            """
        )
        op.alter_column(
            "career_analytics_snapshots",
            "timezone",
            existing_type=sa.String(length=80),
            nullable=False,
        )
    snapshot_index_columns = [
        "owner_user_id",
        "scope",
        "window_start",
        "window_end",
        "timezone",
        "created_at",
        "id",
    ]
    snapshot_indexes = {
        str(index["name"]): index
        for index in sa.inspect(op.get_bind()).get_indexes("career_analytics_snapshots")
        if index.get("name") is not None
    }
    snapshot_index = snapshot_indexes.get("ix_career_analytics_snapshots_owner_scope_window")
    if snapshot_index is not None and snapshot_index.get("column_names") != (
        snapshot_index_columns
    ):
        op.drop_index(
            "ix_career_analytics_snapshots_owner_scope_window",
            table_name="career_analytics_snapshots",
        )
        snapshot_index = None
    if snapshot_index is None:
        op.create_index(
            "ix_career_analytics_snapshots_owner_scope_window",
            "career_analytics_snapshots",
            snapshot_index_columns,
            unique=False,
        )

    if "uq_evidence_revisions_owner_evidence_id" not in _constraint_names(
        "evidence_revisions", "get_unique_constraints"
    ):
        op.create_unique_constraint(
            "uq_evidence_revisions_owner_evidence_id",
            "evidence_revisions",
            ["owner_user_id", "evidence_id", "id"],
        )
    if (
        _foreign_key(
            "career_growth_evidence_links",
            "fk_career_growth_evidence_links_owner_revision",
        )
        is None
    ):
        op.create_foreign_key(
            "fk_career_growth_evidence_links_owner_revision",
            "career_growth_evidence_links",
            "evidence_revisions",
            ["owner_user_id", "evidence_id", "evidence_revision_id"],
            ["owner_user_id", "evidence_id", "id"],
        )

    review_unique_constraints = _constraint_names(
        "career_growth_review_versions",
        "get_unique_constraints",
    )
    if "uq_career_growth_review_versions_latest_state" not in review_unique_constraints:
        op.create_unique_constraint(
            "uq_career_growth_review_versions_latest_state",
            "career_growth_review_versions",
            ["owner_user_id", "review_id", "id", "version_number", "status"],
        )
    predecessor_foreign_key = _foreign_key(
        "career_growth_review_versions",
        "fk_career_growth_review_versions_owner_predecessor",
    )
    predecessor_columns = [
        "owner_user_id",
        "review_id",
        "supersedes_version_id",
    ]
    if (
        predecessor_foreign_key is not None
        and predecessor_foreign_key.get("constrained_columns") != predecessor_columns
    ):
        op.drop_constraint(
            "fk_career_growth_review_versions_owner_predecessor",
            "career_growth_review_versions",
            type_="foreignkey",
        )
        predecessor_foreign_key = None
    if predecessor_foreign_key is None:
        op.create_foreign_key(
            "fk_career_growth_review_versions_owner_predecessor",
            "career_growth_review_versions",
            "career_growth_review_versions",
            predecessor_columns,
            ["owner_user_id", "review_id", "id"],
            ondelete="CASCADE",
        )

    latest_foreign_key = _foreign_key(
        "career_growth_reviews",
        "fk_career_growth_reviews_owner_latest_version",
    )
    latest_columns = [
        "owner_user_id",
        "id",
        "latest_version_id",
        "latest_version_number",
        "latest_status",
    ]
    if (
        latest_foreign_key is not None
        and latest_foreign_key.get("constrained_columns") != latest_columns
    ):
        op.drop_constraint(
            "fk_career_growth_reviews_owner_latest_version",
            "career_growth_reviews",
            type_="foreignkey",
        )
        latest_foreign_key = None
    if latest_foreign_key is None:
        op.create_foreign_key(
            "fk_career_growth_reviews_owner_latest_version",
            "career_growth_reviews",
            "career_growth_review_versions",
            latest_columns,
            ["owner_user_id", "review_id", "id", "version_number", "status"],
            deferrable=True,
            initially="DEFERRED",
        )

    question_columns = _column_map("interview_questions")
    if "ordinal" not in question_columns:
        op.add_column(
            "interview_questions",
            sa.Column("ordinal", sa.Integer(), nullable=True),
        )
        op.execute(
            """
            WITH ranked_questions AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY owner_user_id, session_id
                        ORDER BY created_at, id
                    )::integer AS ordinal
                FROM interview_questions
            )
            UPDATE interview_questions AS question
            SET ordinal = ranked.ordinal
            FROM ranked_questions AS ranked
            WHERE ranked.id = question.id
            """
        )
        op.alter_column(
            "interview_questions",
            "ordinal",
            existing_type=sa.Integer(),
            nullable=False,
        )
    if not _has_check_containing("interview_questions", "ordinal"):
        op.create_check_constraint(
            "ck_interview_questions_ordinal_positive",
            "interview_questions",
            "ordinal > 0",
        )
    if "uq_interview_questions_owner_session_ordinal" not in _constraint_names(
        "interview_questions", "get_unique_constraints"
    ):
        op.create_unique_constraint(
            "uq_interview_questions_owner_session_ordinal",
            "interview_questions",
            ["owner_user_id", "session_id", "ordinal"],
        )

    idempotency_columns = _column_map("interview_idempotency_records")
    if "response_snapshot" not in idempotency_columns:
        op.add_column(
            "interview_idempotency_records",
            sa.Column(
                "response_snapshot",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
    if not _has_check_containing(
        "interview_idempotency_records",
        "response_snapshot",
    ):
        op.create_check_constraint(
            "ck_interview_idempotency_records_response_snapshot_scope_valid",
            "interview_idempotency_records",
            "response_snapshot IS NULL OR "
            "(resource_kind = 'star_story' "
            "AND jsonb_typeof(response_snapshot) = 'object')",
        )

    if "uq_networking_reminders_owner_id_contact" not in _constraint_names(
        "networking_reminders", "get_unique_constraints"
    ):
        op.create_unique_constraint(
            "uq_networking_reminders_owner_id_contact",
            "networking_reminders",
            ["owner_user_id", "id", "contact_id"],
        )

    occurrence_columns = _column_map("networking_reminder_occurrences")
    if "trace_id" not in occurrence_columns:
        op.add_column(
            "networking_reminder_occurrences",
            sa.Column("trace_id", sa.String(length=32), nullable=True),
        )
        op.execute(
            """
            UPDATE networking_reminder_occurrences
            SET trace_id = md5(id::text)
            """
        )
        op.alter_column(
            "networking_reminder_occurrences",
            "trace_id",
            existing_type=sa.String(length=32),
            nullable=False,
        )
    if not _has_check_containing("networking_reminder_occurrences", "trace_id"):
        op.create_check_constraint(
            "ck_networking_occurrences_trace_id_valid",
            "networking_reminder_occurrences",
            "trace_id ~ '^[0-9a-f]{32}$'",
        )
    expected_occurrence_columns = ["owner_user_id", "reminder_id", "contact_id"]
    occurrence_foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(
        "networking_reminder_occurrences"
    )
    for foreign_key in occurrence_foreign_keys:
        if (
            foreign_key.get("referred_table") == "networking_reminders"
            and foreign_key.get("constrained_columns") != expected_occurrence_columns
        ):
            constraint_name = foreign_key.get("name")
            if constraint_name is not None:
                op.drop_constraint(
                    str(constraint_name),
                    "networking_reminder_occurrences",
                    type_="foreignkey",
                )
    if (
        _foreign_key(
            "networking_reminder_occurrences",
            "fk_networking_occurrences_owner_reminder_contact",
        )
        is None
    ):
        op.create_foreign_key(
            "fk_networking_occurrences_owner_reminder_contact",
            "networking_reminder_occurrences",
            "networking_reminders",
            expected_occurrence_columns,
            ["owner_user_id", "id", "contact_id"],
            ondelete="CASCADE",
        )

    outbox_columns = _column_map("networking_reminder_outbox")
    if "trace_id" not in outbox_columns:
        op.add_column(
            "networking_reminder_outbox",
            sa.Column("trace_id", sa.String(length=32), nullable=True),
        )
        op.execute(
            """
            UPDATE networking_reminder_outbox AS outbox
            SET trace_id = occurrence.trace_id
            FROM networking_reminder_occurrences AS occurrence
            WHERE occurrence.owner_user_id = outbox.owner_user_id
              AND occurrence.id = outbox.occurrence_id
            """
        )
        op.execute(
            """
            UPDATE networking_reminder_outbox
            SET trace_id = md5(id::text)
            WHERE trace_id IS NULL
            """
        )
        op.alter_column(
            "networking_reminder_outbox",
            "trace_id",
            existing_type=sa.String(length=32),
            nullable=False,
        )
    if not _has_check_containing("networking_reminder_outbox", "trace_id"):
        op.create_check_constraint(
            "ck_networking_reminder_outbox_networking_outbox_trace_id_valid",
            "networking_reminder_outbox",
            "trace_id ~ '^[0-9a-f]{32}$'",
        )


def upgrade() -> None:
    _repair_phase9_schema_drift()
    op.create_table(
        "career_entity_confirmations",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('needs_review','confirmed')",
            name=op.f("ck_career_entity_confirmations_state_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_career_entity_confirmations_version_positive"),
        ),
        sa.CheckConstraint(
            "(state = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(state = 'needs_review' AND confirmed_at IS NULL)",
            name=op.f("ck_career_entity_confirmations_confirmation_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_entity_confirmations_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_confirmations_owner_entity",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id", name=op.f("pk_career_entity_confirmations")),
        sa.UniqueConstraint(
            "owner_user_id",
            "entity_id",
            name="uq_career_entity_confirmations_owner_entity",
        ),
    )
    op.create_table(
        "career_personal_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("value_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("confirmation", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('name','email','phone','location','link')",
            name=op.f("ck_career_personal_facts_kind_valid"),
        ),
        sa.CheckConstraint(
            "confirmation IN ('needs_review','confirmed')",
            name=op.f("ck_career_personal_facts_confirmation_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_career_personal_facts_version_positive"),
        ),
        sa.CheckConstraint(
            "(confirmation = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(confirmation = 'needs_review' AND confirmed_at IS NULL)",
            name=op.f("ck_career_personal_facts_confirmation_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_personal_facts_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_personal_facts_owner_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_personal_facts")),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_personal_facts_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "profile_id",
            "kind",
            "value_sha256",
            name="uq_career_personal_facts_owner_value",
        ),
    )
    op.create_index(
        "ix_career_personal_facts_owner_profile_kind",
        "career_personal_facts",
        ["owner_user_id", "profile_id", "kind", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_career_personal_facts_owner_primary_kind",
        "career_personal_facts",
        ["owner_user_id", "profile_id", "kind"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_table(
        "career_skill_confirmations",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('needs_review','confirmed')",
            name=op.f("ck_career_skill_confirmations_state_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_career_skill_confirmations_version_positive"),
        ),
        sa.CheckConstraint(
            "(state = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(state = 'needs_review' AND confirmed_at IS NULL)",
            name=op.f("ck_career_skill_confirmations_confirmation_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_skill_confirmations_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_skill_confirmations_owner_skill",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("skill_id", name=op.f("pk_career_skill_confirmations")),
        sa.UniqueConstraint(
            "owner_user_id",
            "skill_id",
            name="uq_career_skill_confirmations_owner_skill",
        ),
    )
    op.create_table(
        "career_semantic_import_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=24), nullable=False),
        sa.Column("target_record_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=120), nullable=False),
        sa.Column("semantic_entity_id", sa.Uuid(), nullable=False),
        sa.Column("semantic_kind", sa.String(length=24), nullable=False),
        sa.Column("fields_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "accepted_values_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("decision_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("conflict_code", sa.String(length=80), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "target IN ('personal_facts','entity','skill')",
            name=op.f("ck_career_semantic_import_proposals_target_valid"),
        ),
        sa.CheckConstraint(
            "semantic_kind IN "
            "('contact','experience','education','project','skill','certification')",
            name=op.f("ck_career_semantic_import_proposals_semantic_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','rejected')",
            name=op.f("ck_career_semantic_import_proposals_status_valid"),
        ),
        sa.CheckConstraint(
            "snapshot_revision > 0",
            name=op.f("ck_career_semantic_import_proposals_snapshot_revision_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_career_semantic_import_proposals_version_positive"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL "
            "AND accepted_values_json IS NULL AND decision_idempotency_key IS NULL) OR "
            "(status = 'accepted' AND reviewed_at IS NOT NULL "
            "AND accepted_values_json IS NOT NULL AND decision_idempotency_key IS NOT NULL) OR "
            "(status = 'rejected' AND reviewed_at IS NOT NULL "
            "AND accepted_values_json IS NULL AND decision_idempotency_key IS NOT NULL)",
            name=op.f("ck_career_semantic_import_proposals_decision_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_semantic_import_proposals_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_semantic_import_proposals_owner_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_semantic_import_proposals")),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_semantic_proposals_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "snapshot_id",
            "semantic_entity_id",
            name="uq_career_semantic_proposals_owner_snapshot_entity",
        ),
    )
    op.create_index(
        "ix_career_semantic_proposals_owner_status_created",
        "career_semantic_import_proposals",
        ["owner_user_id", "status", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "career_entity_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('experience_project')",
            name=op.f("ck_career_entity_relationships_kind_valid"),
        ),
        sa.CheckConstraint(
            "source_entity_id <> target_entity_id",
            name=op.f("ck_career_entity_relationships_different_entities"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_entity_relationships_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_entity_relationships_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "source_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_relationships_owner_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "target_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_relationships_owner_target",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_entity_relationships")),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_entity_relationships_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "source_entity_id",
            "target_entity_id",
            "kind",
            name="uq_career_entity_relationships_owner_pair_kind",
        ),
    )
    op.create_table(
        "career_field_provenance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=24), nullable=False),
        sa.Column("personal_fact_id", sa.Uuid(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("value_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_revision", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.String(length=80), nullable=True),
        sa.Column("parser_version", sa.String(length=120), nullable=True),
        sa.Column("semantic_entity_id", sa.Uuid(), nullable=True),
        sa.Column("semantic_field_id", sa.Uuid(), nullable=True),
        sa.Column(
            "anchors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target IN ('personal_fact','entity','skill')",
            name=op.f("ck_career_field_provenance_target_valid"),
        ),
        sa.CheckConstraint(
            "origin IN ('resume_parser','resume_user_added','owner_edit','owner_attestation')",
            name=op.f("ck_career_field_provenance_origin_valid"),
        ),
        sa.CheckConstraint(
            "octet_length(value_sha256) = 32",
            name=op.f("ck_career_field_provenance_value_sha256_length"),
        ),
        sa.CheckConstraint(
            "(target = 'personal_fact' AND personal_fact_id IS NOT NULL "
            "AND entity_id IS NULL AND skill_id IS NULL) OR "
            "(target = 'entity' AND personal_fact_id IS NULL "
            "AND entity_id IS NOT NULL AND skill_id IS NULL) OR "
            "(target = 'skill' AND personal_fact_id IS NULL "
            "AND entity_id IS NULL AND skill_id IS NOT NULL)",
            name=op.f("ck_career_field_provenance_target_reference_valid"),
        ),
        sa.CheckConstraint(
            "(origin = 'owner_attestation' AND document_id IS NULL "
            "AND snapshot_id IS NULL AND snapshot_revision IS NULL "
            "AND schema_version IS NULL AND parser_version IS NULL "
            "AND semantic_entity_id IS NULL AND semantic_field_id IS NULL "
            "AND anchors_json = '[]'::jsonb) OR "
            "(origin <> 'owner_attestation' AND document_id IS NOT NULL "
            "AND snapshot_id IS NOT NULL AND snapshot_revision > 0 "
            "AND schema_version IS NOT NULL AND parser_version IS NOT NULL "
            "AND semantic_entity_id IS NOT NULL AND semantic_field_id IS NOT NULL)",
            name=op.f("ck_career_field_provenance_semantic_identity_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_career_field_provenance_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_field_provenance_owner_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "personal_fact_id"],
            ["career_personal_facts.owner_user_id", "career_personal_facts.id"],
            name="fk_career_field_provenance_owner_fact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_field_provenance_owner_entity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_field_provenance_owner_skill",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_field_provenance")),
    )
    op.create_index(
        "ix_career_field_provenance_owner_target",
        "career_field_provenance",
        ["owner_user_id", "personal_fact_id", "entity_id", "skill_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_career_field_provenance_owner_target",
        table_name="career_field_provenance",
    )
    op.drop_table("career_field_provenance")
    op.drop_table("career_entity_relationships")
    op.drop_index(
        "ix_career_semantic_proposals_owner_status_created",
        table_name="career_semantic_import_proposals",
    )
    op.drop_table("career_semantic_import_proposals")
    op.drop_table("career_skill_confirmations")
    op.drop_index(
        "uq_career_personal_facts_owner_primary_kind",
        table_name="career_personal_facts",
    )
    op.drop_index(
        "ix_career_personal_facts_owner_profile_kind",
        table_name="career_personal_facts",
    )
    op.drop_table("career_personal_facts")
    op.drop_table("career_entity_confirmations")
