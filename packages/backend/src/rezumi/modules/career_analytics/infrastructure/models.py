"""SQLAlchemy mappings for Phase 9 Career Analytics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base

_SCOPES = ("overview", "applications", "readiness")
_JOB_STATUSES = ("queued", "running", "retry_wait", "completed", "dead_letter")
_OUTBOX_STATUSES = ("pending", "leased", "published", "dead_letter")
_SNAPSHOT_STATUSES = ("ready", "stale", "failed")
_AUDIT_ACTIONS = (
    "refresh_requested",
    "refresh_started",
    "snapshot_created",
    "refresh_retry_scheduled",
    "refresh_dead_lettered",
    "snapshot_marked_stale",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class AnalyticsRefreshJobModel(Base):
    __tablename__ = "career_analytics_refresh_jobs"
    __table_args__ = (
        CheckConstraint(f"scope IN ({_values(_SCOPES)})", name="scope_valid"),
        CheckConstraint(f"status IN ({_values(_JOB_STATUSES)})", name="status_valid"),
        CheckConstraint("window_end >= window_start", name="window_ordered"),
        CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 10",
            name="attempts_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("length(request_fingerprint) = 64", name="fingerprint_length"),
        CheckConstraint("length(trace_id) = 32", name="trace_id_length"),
        CheckConstraint(
            "(lease_token IS NULL AND leased_until IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_until IS NOT NULL)",
            name="lease_complete",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_analytics_jobs_owner_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_analytics_jobs_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_career_analytics_jobs_owner_idempotency",
        ),
        Index(
            "ix_career_analytics_jobs_owner_scope_created",
            "owner_user_id",
            "scope",
            "created_at",
            "id",
        ),
        Index(
            "ix_career_analytics_jobs_status_due",
            "status",
            "next_attempt_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_watermark_before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_watermark_after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalyticsOutboxModel(Base):
    __tablename__ = "career_analytics_outbox"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_OUTBOX_STATUSES)})", name="status_valid"),
        CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 10",
            name="attempts_valid",
        ),
        CheckConstraint(
            "(lease_token IS NULL AND leased_until IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_until IS NOT NULL)",
            name="lease_complete",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "career_analytics_refresh_jobs.owner_user_id",
                "career_analytics_refresh_jobs.id",
            ],
            name="fk_career_analytics_outbox_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_analytics_outbox_owner_id",
        ),
        UniqueConstraint("job_id", name="uq_career_analytics_outbox_job"),
        Index(
            "ix_career_analytics_outbox_status_due",
            "status",
            "next_attempt_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalyticsSnapshotModel(Base):
    __tablename__ = "career_analytics_snapshots"
    __table_args__ = (
        CheckConstraint(f"scope IN ({_values(_SCOPES)})", name="scope_valid"),
        CheckConstraint(
            f"status IN ({_values(_SNAPSHOT_STATUSES)})",
            name="status_valid",
        ),
        CheckConstraint("window_end >= window_start", name="window_ordered"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_hash_length"),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "career_analytics_refresh_jobs.owner_user_id",
                "career_analytics_refresh_jobs.id",
            ],
            name="fk_career_analytics_snapshots_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_analytics_snapshots_owner_id",
        ),
        UniqueConstraint("job_id", name="uq_career_analytics_snapshots_job"),
        Index(
            "ix_career_analytics_snapshots_owner_scope_window",
            "owner_user_id",
            "scope",
            "window_start",
            "window_end",
            "timezone",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    metric_definition_version: Mapped[str] = mapped_column(String(120), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    source_watermark: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalyticsAuditEventModel(Base):
    __tablename__ = "career_analytics_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        CheckConstraint("length(trace_id) = 32", name="trace_id_length"),
        CheckConstraint(
            "(actor_user_id IS NULL AND request_id IS NULL) OR "
            "(actor_user_id = owner_user_id AND request_id IS NOT NULL)",
            name="actor_context_complete",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_career_analytics_audits_actor_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_career_analytics_audits_owner_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_analytics_audits_owner_id",
        ),
        Index(
            "ix_career_analytics_audits_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str | None] = mapped_column(String(128))
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_: Mapped[dict[str, str]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
