"""Phase 12-13 application profile, job source sync, and assisted apply handoff.

Revision ID: 20260823_0015
Revises: 20260731_0014
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0015"
down_revision: str | None = "20260731_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    "assisted_apply_handoff",
)

_SOURCE_KINDS = ("paste", "url", "manual", "greenhouse", "fake")


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "application_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_authorization", sa.Text(), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("compensation_min", sa.Integer(), nullable=True),
        sa.Column("compensation_max", sa.Integer(), nullable=True),
        sa.Column(
            "compensation_currency",
            sa.CHAR(length=3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column(
            "preferred_locations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "profile_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "voluntary_disclosures",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("version > 0", name="ck_application_profiles_version_positive"),
        sa.CheckConstraint(
            "notice_period_days IS NULL OR notice_period_days BETWEEN 0 AND 730",
            name="ck_application_profiles_notice_period_valid",
        ),
        sa.CheckConstraint(
            "compensation_min IS NULL OR compensation_min >= 0",
            name="ck_application_profiles_compensation_min_valid",
        ),
        sa.CheckConstraint(
            "compensation_max IS NULL OR compensation_max >= 0",
            name="ck_application_profiles_compensation_max_valid",
        ),
        sa.CheckConstraint(
            "length(compensation_currency) = 3",
            name="ck_application_profiles_compensation_currency_length",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_profiles_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_application_profiles"),
        sa.UniqueConstraint("owner_user_id", name="uq_application_profiles_owner_user_id"),
    )
    op.create_index(
        "ix_application_profiles_owner_updated",
        "application_profiles",
        ["owner_user_id", "updated_at"],
    )

    op.drop_constraint("kind_valid", "application_documents", type_="check")
    op.create_check_constraint(
        "kind_valid",
        "application_documents",
        f"kind IN ({_values(_DOCUMENT_KINDS)})",
    )

    op.add_column(
        "job_postings",
        sa.Column("external_id", sa.String(length=200), nullable=True),
    )
    op.drop_constraint("source_kind_valid", "job_postings", type_="check")
    op.create_check_constraint(
        "source_kind_valid",
        "job_postings",
        f"source_kind IN ({_values(_SOURCE_KINDS)})",
    )
    op.create_index(
        "ix_job_postings_owner_source_external",
        "job_postings",
        ["owner_user_id", "source_kind", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_postings_owner_source_external",
        table_name="job_postings",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_constraint("source_kind_valid", "job_postings", type_="check")
    op.create_check_constraint(
        "source_kind_valid",
        "job_postings",
        "source_kind IN ('paste','url','manual')",
    )
    op.drop_column("job_postings", "external_id")

    op.drop_constraint("kind_valid", "application_documents", type_="check")
    op.create_check_constraint(
        "kind_valid",
        "application_documents",
        "kind IN ('tailored_resume','cover_letter','professional_bio','interest_answer',"
        "'fit_answer','recruiter_message','hiring_manager_message','referral_request',"
        "'linkedin_connection_note','follow_up_email','interview_introduction',"
        "'achievement_summary')",
    )

    op.drop_index("ix_application_profiles_owner_updated", table_name="application_profiles")
    op.drop_table("application_profiles")
