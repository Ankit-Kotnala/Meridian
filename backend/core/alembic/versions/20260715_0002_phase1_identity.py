"""Add Phase 1 identity, access, consent, audit, and onboarding data.

Revision ID: 20260715_0002
Revises: 20260714_0001
Create Date: 2026-07-15 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0002"
down_revision: str | None = "20260714_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auth_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("auth_version > 0", name="ck_users_auth_version_positive"),
        sa.CheckConstraint(
            "status IN ('pending','active','disabled')", name="ck_users_status_valid"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("locale", sa.String(length=35), server_default=sa.text("'en'"), nullable=False),
        sa.Column(
            "timezone", sa.String(length=64), server_default=sa.text("'UTC'"), nullable=False
        ),
        sa.Column("target_role", sa.String(length=160), nullable=True),
        sa.Column("preferred_location", sa.String(length=160), nullable=True),
        sa.Column("work_model", sa.String(length=16), nullable=True),
        sa.Column("seniority", sa.String(length=16), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("language", sa.String(length=35), server_default=sa.text("'en'"), nullable=False),
        sa.Column(
            "writing_style",
            sa.String(length=16),
            server_default=sa.text("'balanced'"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "seniority IS NULL OR seniority IN ('entry','mid','senior','lead','executive')",
            name="ck_user_profiles_seniority_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_user_profiles_version_positive"),
        sa.CheckConstraint(
            "work_model IS NULL OR work_model IN ('onsite','hybrid','remote','flexible')",
            name="ck_user_profiles_work_model_valid",
        ),
        sa.CheckConstraint(
            "writing_style IN ('concise','balanced','detailed')",
            name="ck_user_profiles_writing_style_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profiles_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_profiles"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("auth_method", sa.String(length=16), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "access_expires_at > created_at", name="ck_auth_sessions_access_expiry_valid"
        ),
        sa.CheckConstraint(
            "auth_method IN ('password','google')",
            name="ck_auth_sessions_auth_method_valid",
        ),
        sa.CheckConstraint(
            "expires_at > access_expires_at", name="ck_auth_sessions_session_expiry_valid"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("access_token_hash", name="uq_auth_sessions_access_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("parent_token_id", sa.Uuid(), nullable=True),
        sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_auth_refresh_tokens_expiry_valid"),
        sa.ForeignKeyConstraint(
            ["parent_token_id"],
            ["auth_refresh_tokens.id"],
            name="fk_auth_refresh_tokens_parent_token_id_auth_refresh_tokens",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_token_id"],
            ["auth_refresh_tokens.id"],
            name="fk_auth_refresh_tokens_replaced_by_token_id_auth_refresh_tokens",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name="fk_auth_refresh_tokens_session_id_auth_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
    )
    op.create_index("ix_auth_refresh_tokens_session_id", "auth_refresh_tokens", ["session_id"])
    op.create_index(
        "ix_auth_refresh_tokens_session_active",
        "auth_refresh_tokens",
        ["session_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "auth_one_time_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_one_time_tokens_expiry_valid"),
        sa.CheckConstraint(
            "purpose IN ('verify_email','reset_password')",
            name="ck_auth_one_time_tokens_purpose_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_one_time_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_one_time_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_one_time_tokens_token_hash"),
    )
    op.create_index("ix_auth_one_time_tokens_user_id", "auth_one_time_tokens", ["user_id"])
    op.create_index(
        "ix_auth_one_time_tokens_user_purpose",
        "auth_one_time_tokens",
        ["user_id", "purpose", "expires_at"],
    )

    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email_normalized", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google')", name="ck_oauth_accounts_provider_valid"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_oauth_accounts_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_oauth_accounts"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_oauth_accounts_provider"),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_accounts_user_id"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_organizations_version_positive"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_organizations_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_index("ix_organizations_created_by_user_id", "organizations", ["created_by_user_id"])

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner','member')", name="ck_organization_memberships_role_valid"
        ),
        sa.CheckConstraint(
            "status IN ('active','invited','suspended')",
            name="ck_organization_memberships_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_memberships_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_organization_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="uq_organization_memberships_organization_id"
        ),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
    op.create_index(
        "ix_organization_memberships_user_status",
        "organization_memberships",
        ["user_id", "status"],
    )

    op.create_table(
        "consent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('granted','withdrawn')", name="ck_consent_events_decision_valid"
        ),
        sa.CheckConstraint(
            "purpose IN ('model_training','product_analytics','product_email')",
            name="ck_consent_events_purpose_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_consent_events_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consent_events"),
    )
    op.create_index("ix_consent_events_user_id", "consent_events", ["user_id"])
    op.create_index(
        "ix_consent_events_user_purpose_recorded",
        "consent_events",
        ["user_id", "purpose", "recorded_at"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('success','accepted','denied','failed')",
            name="ck_audit_events_outcome_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name="fk_audit_events_session_id_auth_sessions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"],
            ["users.id"],
            name="fk_audit_events_subject_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_actor_occurred", "audit_events", ["actor_user_id", "occurred_at"]
    )
    op.create_index(
        "ix_audit_events_subject_occurred", "audit_events", ["subject_user_id", "occurred_at"]
    )
    op.create_index("ix_audit_events_type_occurred", "audit_events", ["event_type", "occurred_at"])

    op.create_table(
        "onboarding_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_step", sa.String(length=24), nullable=False),
        sa.Column("resume_handoff", sa.String(length=16), nullable=False),
        sa.Column("parsed_review_handoff", sa.String(length=16), nullable=False),
        sa.Column(
            "skipped_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'completed' AND current_step = 'complete' AND completed_at IS NOT NULL) "
            "OR (status = 'in_progress' AND completed_at IS NULL)",
            name="ck_onboarding_progress_completion_state_valid",
        ),
        sa.CheckConstraint(
            "current_step IN ('profile','resume','parsed_review','preferences','complete')",
            name="ck_onboarding_progress_current_step_valid",
        ),
        sa.CheckConstraint(
            "parsed_review_handoff IN ('not_started','skipped')",
            name="ck_onboarding_progress_parsed_review_handoff_valid",
        ),
        sa.CheckConstraint(
            "resume_handoff IN ('not_started','skipped')",
            name="ck_onboarding_progress_resume_handoff_valid",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','completed')",
            name="ck_onboarding_progress_status_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_onboarding_progress_version_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_onboarding_progress_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_onboarding_progress"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_progress")
    op.drop_index("ix_audit_events_type_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_subject_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_consent_events_user_purpose_recorded", table_name="consent_events")
    op.drop_index("ix_consent_events_user_id", table_name="consent_events")
    op.drop_table("consent_events")
    op.drop_index("ix_organization_memberships_user_status", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index(
        "ix_organization_memberships_organization_id", table_name="organization_memberships"
    )
    op.drop_table("organization_memberships")
    op.drop_index("ix_organizations_created_by_user_id", table_name="organizations")
    op.drop_table("organizations")
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
    op.drop_index("ix_auth_one_time_tokens_user_purpose", table_name="auth_one_time_tokens")
    op.drop_index("ix_auth_one_time_tokens_user_id", table_name="auth_one_time_tokens")
    op.drop_table("auth_one_time_tokens")
    op.drop_index("ix_auth_refresh_tokens_session_active", table_name="auth_refresh_tokens")
    op.drop_index("ix_auth_refresh_tokens_session_id", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_index("ix_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_profiles")
    op.drop_table("users")
