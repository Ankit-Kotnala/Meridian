"""Phase 11 async declared-profile enrichment jobs + outbox.

Revision ID: 20260823_0016
Revises: 20260823_0015
Create Date: 2026-08-23 00:00:01.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0016"
down_revision: str | None = "20260823_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "declared_profile_enrichment_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("personal_fact_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_platform", sa.String(length=40), nullable=True),
        sa.Column("result_achievements_created", sa.Integer(), nullable=True),
        sa.Column("result_evidence_created", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','dead_lettered')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded','failed','dead_lettered') AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running') AND completed_at IS NULL)",
            name="completion_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_declared_profile_enrichment_jobs_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_declared_profile_enrichment_jobs"),
        sa.UniqueConstraint(
            "owner_user_id", "id", name="uq_declared_profile_enrichment_jobs_owner_id"
        ),
    )
    op.create_index(
        "ix_declared_profile_enrichment_jobs_owner_fact_active",
        "declared_profile_enrichment_jobs",
        ["owner_user_id", "personal_fact_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
    )

    op.create_table(
        "declared_profile_enrichment_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=160), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        sa.CheckConstraint(
            "published_at IS NULL OR dead_lettered_at IS NULL",
            name="terminal_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_declared_profile_enrichment_outbox_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_declared_profile_enrichment_outbox"),
        sa.UniqueConstraint(
            "owner_user_id", "id", name="uq_declared_profile_enrichment_outbox_owner_id"
        ),
    )
    op.create_index(
        "ix_declared_profile_enrichment_outbox_due",
        "declared_profile_enrichment_outbox",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("published_at IS NULL AND dead_lettered_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_declared_profile_enrichment_outbox_due",
        table_name="declared_profile_enrichment_outbox",
        postgresql_where=sa.text("published_at IS NULL AND dead_lettered_at IS NULL"),
    )
    op.drop_table("declared_profile_enrichment_outbox")
    op.drop_index(
        "ix_declared_profile_enrichment_jobs_owner_fact_active",
        table_name="declared_profile_enrichment_jobs",
        postgresql_where=sa.text("status IN ('queued','running')"),
    )
    op.drop_table("declared_profile_enrichment_jobs")
