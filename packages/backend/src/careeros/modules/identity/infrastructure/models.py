"""SQLAlchemy persistence mappings for Phase 1 identity data."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careeros.foundation.database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','disabled')", name="status_valid"),
        CheckConstraint("auth_version > 0", name="auth_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email_normalized: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountOperationModel(Base):
    __tablename__ = "account_operations"
    __table_args__ = (
        CheckConstraint("kind IN ('export','deletion')", name="kind_valid"),
        CheckConstraint(
            "status IN ('queued','running','retry_wait','succeeded','blocked',"
            "'dead_lettered','expired')",
            name="status_valid",
        ),
        CheckConstraint(
            "attempts BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10",
            name="attempts_valid",
        ),
        CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="lease_pair_valid",
        ),
        CheckConstraint(
            "(status = 'running') = (lease_token IS NOT NULL)",
            name="running_lease_valid",
        ),
        CheckConstraint(
            "num_nonnulls(artifact_object_key, artifact_sha256, artifact_size_bytes, "
            "artifact_expires_at) IN (0, 4)",
            name="artifact_metadata_valid",
        ),
        CheckConstraint(
            "artifact_object_key IS NULL OR (kind = 'export' AND status = 'succeeded')",
            name="artifact_state_valid",
        ),
        CheckConstraint(
            "status <> 'expired' OR kind = 'export'",
            name="expired_export_only",
        ),
        CheckConstraint(
            "(blocked_reason IS NOT NULL) = (status = 'blocked')",
            name="blocked_reason_state_valid",
        ),
        CheckConstraint(
            "status NOT IN ('succeeded','blocked','dead_lettered','expired') "
            "OR completed_at IS NOT NULL",
            name="terminal_timestamp_valid",
        ),
        UniqueConstraint(
            "user_id",
            "kind",
            "idempotency_key",
            name="uq_account_operations_user_kind_idempotency",
        ),
        Index("ix_account_operations_user_requested", "user_id", "requested_at"),
        Index(
            "ix_account_operations_due",
            "next_attempt_at",
            "lease_expires_at",
            postgresql_where=text("status IN ('queued','retry_wait','running')"),
        ),
        Index(
            "ix_account_operations_expired_artifacts",
            "artifact_expires_at",
            postgresql_where=text("kind = 'export' AND status = 'succeeded'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    user_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    capability_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_object_key: Mapped[str | None] = mapped_column(String(500))
    artifact_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    artifact_size_bytes: Mapped[int | None] = mapped_column(Integer)
    artifact_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String(80))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserProfileModel(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "work_model IS NULL OR work_model IN ('onsite','hybrid','remote','flexible')",
            name="work_model_valid",
        ),
        CheckConstraint(
            "seniority IS NULL OR seniority IN ('entry','mid','senior','lead','executive')",
            name="seniority_valid",
        ),
        CheckConstraint(
            "writing_style IN ('concise','balanced','detailed')",
            name="writing_style_valid",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(35), server_default=text("'en'"))
    timezone: Mapped[str] = mapped_column(String(64), server_default=text("'UTC'"))
    target_role: Mapped[str | None] = mapped_column(String(160))
    preferred_location: Mapped[str | None] = mapped_column(String(160))
    work_model: Mapped[str | None] = mapped_column(String(16))
    seniority: Mapped[str | None] = mapped_column(String(16))
    industry: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(35), server_default=text("'en'"))
    writing_style: Mapped[str] = mapped_column(String(16), server_default=text("'balanced'"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("auth_method IN ('password','google')", name="auth_method_valid"),
        CheckConstraint("access_expires_at > created_at", name="access_expiry_valid"),
        CheckConstraint("expires_at > access_expires_at", name="session_expiry_valid"),
        Index("ix_auth_sessions_user_active", "user_id", "revoked_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    access_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    csrf_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    auth_method: Mapped[str] = mapped_column(String(16))
    device_label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthRefreshTokenModel(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        CheckConstraint("expires_at > issued_at", name="expiry_valid"),
        Index("ix_auth_refresh_tokens_session_active", "session_id", "revoked_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    parent_token_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL")
    )
    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL")
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthOneTimeTokenModel(Base):
    __tablename__ = "auth_one_time_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('verify_email','reset_password')", name="purpose_valid"),
        CheckConstraint("expires_at > created_at", name="expiry_valid"),
        Index("ix_auth_one_time_tokens_user_purpose", "user_id", "purpose", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAccountModel(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        CheckConstraint("provider IN ('google')", name="provider_valid"),
        UniqueConstraint("provider", "provider_subject"),
        UniqueConstraint("user_id", "provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(24))
    provider_subject: Mapped[str] = mapped_column(String(255))
    provider_email_normalized: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsentEventModel(Base):
    __tablename__ = "consent_events"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('model_training','product_analytics','product_email')",
            name="purpose_valid",
        ),
        CheckConstraint("decision IN ('granted','withdrawn')", name="decision_valid"),
        Index("ix_consent_events_user_purpose_recorded", "user_id", "purpose", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(16))
    policy_version: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[str] = mapped_column(String(128))
    trace_id: Mapped[str] = mapped_column(String(32))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success','accepted','denied','failed')", name="outcome_valid"
        ),
        Index("ix_audit_events_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_subject_occurred", "subject_user_id", "occurred_at"),
        Index("ix_audit_events_type_occurred", "event_type", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    subject_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("auth_sessions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(16))
    target_type: Mapped[str | None] = mapped_column(String(48))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str] = mapped_column(String(128))
    trace_id: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OnboardingProgressModel(Base):
    __tablename__ = "onboarding_progress"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed')", name="status_valid"),
        CheckConstraint(
            "current_step IN ('profile','resume','parsed_review','preferences','complete')",
            name="current_step_valid",
        ),
        CheckConstraint("resume_handoff IN ('not_started','skipped')", name="resume_handoff_valid"),
        CheckConstraint(
            "parsed_review_handoff IN ('not_started','skipped')",
            name="parsed_review_handoff_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'completed' AND current_step = 'complete' AND completed_at IS NOT NULL) "
            "OR (status = 'in_progress' AND completed_at IS NULL)",
            name="completion_state_valid",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16))
    current_step: Mapped[str] = mapped_column(String(24))
    resume_handoff: Mapped[str] = mapped_column(String(16))
    parsed_review_handoff: Mapped[str] = mapped_column(String(16))
    skipped_steps: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
