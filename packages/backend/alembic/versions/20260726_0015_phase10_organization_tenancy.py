"""Add Phase 10 organization tenancy, invitations, and delegated grants.

Revision ID: 20260726_0015
Revises: 20260726_0014
Create Date: 2026-07-26 23:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0015"
down_revision: str | None = "20260726_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_organizations_status_valid",
        "organizations",
        "status IN ('active','archived')",
    )
    op.create_unique_constraint(
        "uq_organizations_id_creator",
        "organizations",
        ["id", "created_by_user_id"],
    )
    op.create_index(
        "ix_organizations_status_updated",
        "organizations",
        ["status", "updated_at"],
    )

    op.drop_constraint(
        "ck_organization_memberships_role_valid",
        "organization_memberships",
        type_="check",
    )
    op.drop_constraint(
        "ck_organization_memberships_status_valid",
        "organization_memberships",
        type_="check",
    )
    op.add_column(
        "organization_memberships",
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE organization_memberships "
            "SET accepted_at = created_at "
            "WHERE status = 'active' AND accepted_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE organization_memberships "
            "SET suspended_at = updated_at "
            "WHERE status = 'suspended' AND suspended_at IS NULL"
        )
    )
    op.create_check_constraint(
        "ck_organization_memberships_role_valid",
        "organization_memberships",
        "role IN ('owner','admin','coach','member')",
    )
    op.create_check_constraint(
        "ck_organization_memberships_status_valid",
        "organization_memberships",
        "status IN ('active','invited','suspended','left')",
    )
    op.create_check_constraint(
        "ck_organization_memberships_version_positive",
        "organization_memberships",
        "version > 0",
    )
    op.create_check_constraint(
        "ck_organization_memberships_state_timestamps_valid",
        "organization_memberships",
        "(status <> 'active' OR accepted_at IS NOT NULL)"
        " AND (status <> 'suspended' OR suspended_at IS NOT NULL)"
        " AND (status <> 'left' OR left_at IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_organization_memberships_organization_id_id",
        "organization_memberships",
        ["organization_id", "id"],
    )
    op.create_index(
        "ix_organization_memberships_org_status_role",
        "organization_memberships",
        ["organization_id", "status", "role"],
    )

    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invited_email_normalized", sa.String(length=254), nullable=False),
        sa.Column("invited_email_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin','coach','member')",
            name="ck_organization_invitations_role_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending_delivery','pending','accepted','revoked','expired',"
            "'delivery_dead_lettered')",
            name="ck_organization_invitations_status_valid",
        ),
        sa.CheckConstraint(
            "octet_length(invited_email_digest) = 32",
            name="ck_organization_invitations_email_digest_length",
        ),
        sa.CheckConstraint(
            "token_hash IS NULL OR octet_length(token_hash) = 32",
            name="ck_organization_invitations_token_hash_length",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_organization_invitations_version_positive",
        ),
        sa.CheckConstraint(
            "created_at < expires_at",
            name="ck_organization_invitations_expiry_valid",
        ),
        sa.CheckConstraint(
            "(status <> 'pending' OR token_hash IS NOT NULL)"
            " AND (status = 'accepted') ="
            " (accepted_by_user_id IS NOT NULL AND accepted_at IS NOT NULL)"
            " AND (status = 'revoked') = (revoked_at IS NOT NULL)",
            name="ck_organization_invitations_state_links_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_invitations_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name="fk_organization_invitations_invited_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["users.id"],
            name="fk_organization_invitations_accepted_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invitations"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_organization_invitations_organization_id",
        ),
    )
    op.create_index(
        "ix_organization_invitations_org_status_expiry",
        "organization_invitations",
        ["organization_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_organization_invitations_email_status",
        "organization_invitations",
        ["organization_id", "invited_email_digest", "status"],
    )
    op.create_index(
        "uq_organization_invitations_open_email",
        "organization_invitations",
        ["organization_id", "invited_email_digest"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending_delivery','pending','delivery_dead_lettered')"
        ),
    )

    op.create_table(
        "organization_access_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("grantee_user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('coaching','career_services','program_support')",
            name="ck_organization_access_grants_purpose_valid",
        ),
        sa.CheckConstraint(
            "scope IN ('career_profile_summary','resume_health_summary',"
            "'role_readiness_summary','application_status','career_growth_summary',"
            "'collaboration_comment')",
            name="ck_organization_access_grants_scope_valid",
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked','expired')",
            name="ck_organization_access_grants_status_valid",
        ),
        sa.CheckConstraint(
            "subject_user_id <> grantee_user_id",
            name="ck_organization_access_grants_distinct_users",
        ),
        sa.CheckConstraint(
            "granted_by_user_id = subject_user_id",
            name="ck_organization_access_grants_subject_is_grantor",
        ),
        sa.CheckConstraint(
            "created_at < expires_at",
            name="ck_organization_access_grants_expiry_valid",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_organization_access_grants_version_positive",
        ),
        sa.CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="ck_organization_access_grants_revocation_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "subject_user_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_organization_access_grants_subject_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "grantee_user_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_organization_access_grants_grantee_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="fk_organization_access_grants_granted_by_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_access_grants"),
    )
    op.create_index(
        "ix_organization_access_grants_subject_status",
        "organization_access_grants",
        ["organization_id", "subject_user_id", "status"],
    )
    op.create_index(
        "ix_organization_access_grants_grantee_status",
        "organization_access_grants",
        ["organization_id", "grantee_user_id", "status"],
    )
    op.create_index(
        "uq_organization_access_grants_active_scope",
        "organization_access_grants",
        [
            "organization_id",
            "subject_user_id",
            "grantee_user_id",
            "scope",
        ],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "organization_invitation_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 20",
            name="ck_organization_invitation_outbox_attempts_valid",
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_organization_invitation_outbox_lease_pair_valid",
        ),
        sa.CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="ck_organization_invitation_outbox_terminal_state_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invitation_id"],
            [
                "organization_invitations.organization_id",
                "organization_invitations.id",
            ],
            name="fk_organization_invitation_outbox_invitation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invitation_outbox"),
        sa.UniqueConstraint(
            "invitation_id",
            name="uq_organization_invitation_outbox_invitation",
        ),
    )
    op.create_index(
        "ix_organization_invitation_outbox_pending",
        "organization_invitation_outbox",
        ["published_at", "dead_lettered_at", "next_attempt_at"],
    )

    op.create_table(
        "organization_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(length=32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('create_organization','invite_member','accept_invitation',"
            "'create_grant','revoke_grant')",
            name="ck_organization_idempotency_records_operation_valid",
        ),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="ck_organization_idempotency_records_request_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_organization_idempotency_records_actor_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_idempotency_records"),
        sa.UniqueConstraint(
            "actor_user_id",
            "operation",
            "idempotency_key",
            name="uq_organization_idempotency_actor_operation_key",
        ),
    )
    op.create_index(
        "ix_organization_idempotency_actor_created",
        "organization_idempotency_records",
        ["actor_user_id", "created_at"],
    )

    op.create_table(
        "organization_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('organization_created','organization_updated',"
            "'invitation_created','invitation_delivered','invitation_delivery_failed',"
            "'invitation_accepted','invitation_revoked','member_suspended',"
            "'grant_created','grant_revoked')",
            name="ck_organization_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_audit_events_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_organization_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"],
            ["users.id"],
            name="fk_organization_audit_events_subject_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_audit_events"),
    )
    op.create_index(
        "ix_organization_audit_events_org_occurred",
        "organization_audit_events",
        ["organization_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_organization_audit_events_actor_occurred",
        "organization_audit_events",
        ["actor_user_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_audit_events_actor_occurred",
        table_name="organization_audit_events",
    )
    op.drop_index(
        "ix_organization_audit_events_org_occurred",
        table_name="organization_audit_events",
    )
    op.drop_table("organization_audit_events")

    op.drop_index(
        "ix_organization_idempotency_actor_created",
        table_name="organization_idempotency_records",
    )
    op.drop_table("organization_idempotency_records")

    op.drop_index(
        "ix_organization_invitation_outbox_pending",
        table_name="organization_invitation_outbox",
    )
    op.drop_table("organization_invitation_outbox")

    op.drop_index(
        "uq_organization_access_grants_active_scope",
        table_name="organization_access_grants",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "ix_organization_access_grants_grantee_status",
        table_name="organization_access_grants",
    )
    op.drop_index(
        "ix_organization_access_grants_subject_status",
        table_name="organization_access_grants",
    )
    op.drop_table("organization_access_grants")

    op.drop_index(
        "uq_organization_invitations_open_email",
        table_name="organization_invitations",
        postgresql_where=sa.text(
            "status IN ('pending_delivery','pending','delivery_dead_lettered')"
        ),
    )
    op.drop_index(
        "ix_organization_invitations_email_status",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_org_status_expiry",
        table_name="organization_invitations",
    )
    op.drop_table("organization_invitations")

    op.drop_index(
        "ix_organization_memberships_org_status_role",
        table_name="organization_memberships",
    )
    op.drop_constraint(
        "uq_organization_memberships_organization_id_id",
        "organization_memberships",
        type_="unique",
    )
    op.drop_constraint(
        "ck_organization_memberships_state_timestamps_valid",
        "organization_memberships",
        type_="check",
    )
    op.drop_constraint(
        "ck_organization_memberships_version_positive",
        "organization_memberships",
        type_="check",
    )
    op.drop_constraint(
        "ck_organization_memberships_status_valid",
        "organization_memberships",
        type_="check",
    )
    op.drop_constraint(
        "ck_organization_memberships_role_valid",
        "organization_memberships",
        type_="check",
    )
    op.execute(
        sa.text(
            "UPDATE organization_memberships SET role = 'member' WHERE role IN ('admin','coach')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE organization_memberships "
            "SET status = 'suspended', suspended_at = COALESCE(suspended_at, left_at, updated_at) "
            "WHERE status = 'left'"
        )
    )
    op.create_check_constraint(
        "ck_organization_memberships_role_valid",
        "organization_memberships",
        "role IN ('owner','member')",
    )
    op.create_check_constraint(
        "ck_organization_memberships_status_valid",
        "organization_memberships",
        "status IN ('active','invited','suspended')",
    )
    op.drop_column("organization_memberships", "left_at")
    op.drop_column("organization_memberships", "suspended_at")
    op.drop_column("organization_memberships", "accepted_at")
    op.drop_column("organization_memberships", "version")

    op.drop_index("ix_organizations_status_updated", table_name="organizations")
    op.drop_constraint(
        "uq_organizations_id_creator",
        "organizations",
        type_="unique",
    )
    op.drop_constraint(
        "ck_organizations_status_valid",
        "organizations",
        type_="check",
    )
    op.drop_column("organizations", "status")
