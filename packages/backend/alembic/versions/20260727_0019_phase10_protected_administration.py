"""Add least-privilege platform operators and tamper-evident admin audit.

Revision ID: 20260727_0019
Revises: 20260727_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0019"
down_revision: str | None = "20260727_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES = (
    "operations_viewer",
    "job_operator",
    "catalog_auditor",
    "security_auditor",
)
_CAPABILITIES = (
    "system.read",
    "jobs.read",
    "jobs.retry",
    "catalog.read",
    "audit.read",
    "audit.verify",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "platform_operator_assignments",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("grant_reason", sa.String(length=500), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"role IN ({_values(_ROLES)})", name="role_valid"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL AND revoke_reason IS NULL) "
            "OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation_state_valid",
        ),
        sa.CheckConstraint("length(grant_reason) BETWEEN 12 AND 500", name="grant_reason_valid"),
        sa.CheckConstraint(
            "revoke_reason IS NULL OR length(revoke_reason) BETWEEN 12 AND 500",
            name="revoke_reason_valid",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="fk_platform_operator_assignments_granted_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name="fk_platform_operator_assignments_revoked_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_platform_operator_assignments_user_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_platform_operator_assignments"),
    )
    op.create_index(
        "ix_platform_operator_assignments_active",
        "platform_operator_assignments",
        ["role", "revoked_at"],
    )

    op.create_table(
        "platform_feature_flags",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column(
            "state",
            sa.String(length=16),
            server_default=sa.text("'disabled'"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_.-]{2,79}$'", name="key_valid"),
        sa.CheckConstraint("state IN ('disabled','enabled')", name="state_valid"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_platform_feature_flags_updated_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name="pk_platform_feature_flags"),
    )
    op.create_index(
        "ix_platform_feature_flags_state",
        "platform_feature_flags",
        ["state", "key"],
    )

    op.create_table(
        "platform_admin_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_reference", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("target_kind", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('accepted','success','denied','failed')",
            name="outcome_valid",
        ),
        sa.CheckConstraint(
            f"actor_role IS NULL OR actor_role IN ({_values(_ROLES)})",
            name="actor_role_valid",
        ),
        sa.CheckConstraint(f"capability IN ({_values(_CAPABILITIES)})", name="capability_valid"),
        sa.CheckConstraint("length(reason) BETWEEN 12 AND 500", name="reason_valid"),
        sa.CheckConstraint("length(previous_hash) = 64", name="previous_hash_valid"),
        sa.CheckConstraint("length(event_hash) = 64", name="event_hash_valid"),
        sa.CheckConstraint("sequence > 0", name="sequence_positive"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_platform_admin_audit_actor_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_admin_audit_events"),
        sa.UniqueConstraint("sequence", name="uq_platform_admin_audit_sequence"),
    )
    op.create_index(
        "ix_platform_admin_audit_actor_time",
        "platform_admin_audit_events",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_platform_admin_audit_action_time",
        "platform_admin_audit_events",
        ["action", "occurred_at"],
    )
    op.create_index(
        "ix_platform_admin_audit_target",
        "platform_admin_audit_events",
        ["target_kind", "target_id", "occurred_at"],
    )

    op.create_table(
        "platform_admin_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="fingerprint_valid"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_platform_admin_idempotency_actor_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_admin_idempotency"),
        sa.UniqueConstraint(
            "actor_user_id",
            "operation",
            "idempotency_key",
            name="uq_platform_admin_idempotency_scope",
        ),
    )
    op.create_index(
        "ix_platform_admin_idempotency_created",
        "platform_admin_idempotency",
        ["created_at"],
    )


def downgrade() -> None:
    retained = (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM platform_admin_audit_events LIMIT 1)"))
        .scalar_one()
    )
    if retained:
        raise RuntimeError("refusing to drop retained platform administration audit history")
    op.drop_index(
        "ix_platform_admin_idempotency_created",
        table_name="platform_admin_idempotency",
    )
    op.drop_table("platform_admin_idempotency")
    op.drop_index(
        "ix_platform_admin_audit_target",
        table_name="platform_admin_audit_events",
    )
    op.drop_index(
        "ix_platform_admin_audit_action_time",
        table_name="platform_admin_audit_events",
    )
    op.drop_index(
        "ix_platform_admin_audit_actor_time",
        table_name="platform_admin_audit_events",
    )
    op.drop_table("platform_admin_audit_events")
    op.drop_index("ix_platform_feature_flags_state", table_name="platform_feature_flags")
    op.drop_table("platform_feature_flags")
    op.drop_index(
        "ix_platform_operator_assignments_active",
        table_name="platform_operator_assignments",
    )
    op.drop_table("platform_operator_assignments")
