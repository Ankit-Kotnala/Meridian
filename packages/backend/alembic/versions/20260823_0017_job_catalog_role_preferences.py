"""Owner-scoped job catalog role preferences.

Revision ID: 20260823_0017
Revises: 20260823_0016
Create Date: 2026-08-23 00:00:02.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260823_0017"
down_revision: str | None = "20260823_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_catalog_role_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("role_titles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_job_catalog_role_preferences_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_catalog_role_preferences"),
        sa.UniqueConstraint(
            "owner_user_id", name="uq_job_catalog_role_preferences_owner_user_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("job_catalog_role_preferences")
