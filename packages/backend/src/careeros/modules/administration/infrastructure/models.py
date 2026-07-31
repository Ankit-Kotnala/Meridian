"""SQLAlchemy mappings for protected platform administration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careeros.foundation.database import Base

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


class PlatformOperatorAssignmentModel(Base):
    __tablename__ = "platform_operator_assignments"
    __table_args__ = (
        CheckConstraint(f"role IN ({_values(_ROLES)})", name="role_valid"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL AND revoke_reason IS NULL) "
            "OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation_state_valid",
        ),
        CheckConstraint("length(grant_reason) BETWEEN 12 AND 500", name="grant_reason_valid"),
        CheckConstraint(
            "revoke_reason IS NULL OR length(revoke_reason) BETWEEN 12 AND 500",
            name="revoke_reason_valid",
        ),
        Index("ix_platform_operator_assignments_active", "role", "revoked_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    grant_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformAdminAuditEventModel(Base):
    __tablename__ = "platform_admin_audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('accepted','success','denied','failed')",
            name="outcome_valid",
        ),
        CheckConstraint(
            f"actor_role IS NULL OR actor_role IN ({_values(_ROLES)})",
            name="actor_role_valid",
        ),
        CheckConstraint(f"capability IN ({_values(_CAPABILITIES)})", name="capability_valid"),
        CheckConstraint("length(reason) BETWEEN 12 AND 500", name="reason_valid"),
        CheckConstraint("length(previous_hash) = 64", name="previous_hash_valid"),
        CheckConstraint("length(event_hash) = 64", name="event_hash_valid"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        UniqueConstraint("sequence", name="uq_platform_admin_audit_sequence"),
        Index("ix_platform_admin_audit_actor_time", "actor_user_id", "occurred_at"),
        Index("ix_platform_admin_audit_action_time", "action", "occurred_at"),
        Index(
            "ix_platform_admin_audit_target",
            "target_kind",
            "target_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(32))
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlatformAdminIdempotencyModel(Base):
    __tablename__ = "platform_admin_idempotency"
    __table_args__ = (
        CheckConstraint("length(request_fingerprint) = 64", name="fingerprint_valid"),
        UniqueConstraint(
            "actor_user_id",
            "operation",
            "idempotency_key",
            name="uq_platform_admin_idempotency_scope",
        ),
        Index("ix_platform_admin_idempotency_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlatformFeatureFlagModel(Base):
    __tablename__ = "platform_feature_flags"
    __table_args__ = (
        CheckConstraint("key ~ '^[a-z][a-z0-9_.-]{2,79}$'", name="key_valid"),
        CheckConstraint("state IN ('disabled','enabled')", name="state_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_platform_feature_flags_state", "state", "key"),
    )

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'disabled'")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
