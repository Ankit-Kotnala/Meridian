"""Add durable account export/erasure operations and nullable provenance actors.

Revision ID: 20260727_0018
Revises: 20260727_0017
Create Date: 2026-07-27 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0018"
down_revision: str | None = "20260727_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("user_fingerprint", sa.LargeBinary(length=32), nullable=False),
        sa.Column("capability_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_object_key", sa.String(length=500), nullable=True),
        sa.Column("artifact_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
        sa.Column("artifact_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reason", sa.String(length=80), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('export','deletion')",
            name="ck_account_operations_kind_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','retry_wait','succeeded','blocked',"
            "'dead_lettered','expired')",
            name="ck_account_operations_status_valid",
        ),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10",
            name="ck_account_operations_attempts_valid",
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_account_operations_lease_pair_valid",
        ),
        sa.CheckConstraint(
            "(status = 'running') = (lease_token IS NOT NULL)",
            name="ck_account_operations_running_lease_valid",
        ),
        sa.CheckConstraint(
            "num_nonnulls(artifact_object_key, artifact_sha256, artifact_size_bytes, "
            "artifact_expires_at) IN (0, 4)",
            name="ck_account_operations_artifact_metadata_valid",
        ),
        sa.CheckConstraint(
            "artifact_object_key IS NULL OR (kind = 'export' AND status = 'succeeded')",
            name="ck_account_operations_artifact_state_valid",
        ),
        sa.CheckConstraint(
            "status <> 'expired' OR kind = 'export'",
            name="ck_account_operations_expired_export_only",
        ),
        sa.CheckConstraint(
            "(blocked_reason IS NOT NULL) = (status = 'blocked')",
            name="ck_account_operations_blocked_reason_state_valid",
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded','blocked','dead_lettered','expired') "
            "OR completed_at IS NOT NULL",
            name="ck_account_operations_terminal_timestamp_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_account_operations_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_operations"),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "idempotency_key",
            name="uq_account_operations_user_kind_idempotency",
        ),
    )
    op.create_index(
        "ix_account_operations_user_requested",
        "account_operations",
        ["user_id", "requested_at"],
    )
    op.create_index(
        "ix_account_operations_due",
        "account_operations",
        ["next_attempt_at", "lease_expires_at"],
        postgresql_where=sa.text("status IN ('queued','retry_wait','running')"),
    )
    op.create_index(
        "ix_account_operations_expired_artifacts",
        "account_operations",
        ["artifact_expires_at"],
        postgresql_where=sa.text("kind = 'export' AND status = 'succeeded'"),
    )

    op.drop_constraint(
        "fk_organizations_created_by_user_id_users",
        "organizations",
        type_="foreignkey",
    )
    op.alter_column("organizations", "created_by_user_id", nullable=True)
    op.create_foreign_key(
        "fk_organizations_created_by_user_id_users",
        "organizations",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "fk_organization_invitations_invited_by_user_id_users",
        "organization_invitations",
        type_="foreignkey",
    )
    op.alter_column("organization_invitations", "invited_by_user_id", nullable=True)
    op.create_foreign_key(
        "fk_organization_invitations_invited_by_user_id_users",
        "organization_invitations",
        "users",
        ["invited_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    connection = op.get_bind()
    retained_operations = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM account_operations)")
    )
    nullable_provenance = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM organizations WHERE created_by_user_id IS NULL) "
            "OR EXISTS (SELECT 1 FROM organization_invitations "
            "WHERE invited_by_user_id IS NULL)"
        )
    )
    if retained_operations or nullable_provenance:
        raise RuntimeError(
            "Cannot downgrade account privacy operations while retained operation "
            "or nullable provenance state exists"
        )

    op.drop_constraint(
        "fk_organization_invitations_invited_by_user_id_users",
        "organization_invitations",
        type_="foreignkey",
    )
    op.alter_column("organization_invitations", "invited_by_user_id", nullable=False)
    op.create_foreign_key(
        "fk_organization_invitations_invited_by_user_id_users",
        "organization_invitations",
        "users",
        ["invited_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "fk_organizations_created_by_user_id_users",
        "organizations",
        type_="foreignkey",
    )
    op.alter_column("organizations", "created_by_user_id", nullable=False)
    op.create_foreign_key(
        "fk_organizations_created_by_user_id_users",
        "organizations",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_index(
        "ix_account_operations_expired_artifacts",
        table_name="account_operations",
    )
    op.drop_index("ix_account_operations_due", table_name="account_operations")
    op.drop_index(
        "ix_account_operations_user_requested",
        table_name="account_operations",
    )
    op.drop_table("account_operations")
