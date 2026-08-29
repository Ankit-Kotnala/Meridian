"""SQLAlchemy mappings for Interview Prep."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base

_STORY_STATUSES = ("draft", "ready", "archived")
_STORY_ORIGINS = ("user_authored", "generated")
_SESSION_KINDS = (
    "recruiter_screen",
    "behavioral",
    "technical",
    "hiring_manager",
    "panel",
    "other",
)
_QUESTION_KINDS = (
    "behavioral",
    "role_specific",
    "technical",
    "company",
    "follow_up",
    "custom",
)
_NOTE_KINDS = ("private_note", "reflection")
_AUDIT_ACTIONS = (
    "story_created",
    "story_updated",
    "story_deleted",
    "session_created",
    "session_updated",
    "session_deleted",
    "question_created",
    "questions_generated",
    "note_created",
    "note_updated",
    "note_deleted",
    "follow_up_draft_generated",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class StarStoryModel(Base):
    __tablename__ = "interview_star_stories"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_STORY_STATUSES)})", name="status_valid"),
        CheckConstraint(f"origin IN ({_values(_STORY_ORIGINS)})", name="origin_valid"),
        CheckConstraint("confidence BETWEEN 1 AND 5", name="confidence_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_stories_owner_id"),
        Index(
            "ix_interview_stories_owner_application_updated",
            "owner_user_id",
            "application_id",
            "updated_at",
            "id",
        ),
        Index(
            "ix_interview_stories_owner_status_updated",
            "owner_user_id",
            "status",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    personal_contribution: Mapped[str] = mapped_column(Text, nullable=False)
    metric_explanation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StoryClaimPinModel(Base):
    __tablename__ = "interview_story_claim_pins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "story_id"],
            ["interview_star_stories.owner_user_id", "interview_star_stories.id"],
            name="fk_interview_story_claim_pins_owner_story",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "story_id",
            "source_claim_id",
            name="uq_interview_story_claim_pins_claim",
        ),
        Index(
            "ix_interview_story_claim_pins_source_claim",
            "owner_user_id",
            "source_claim_id",
            "story_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    story_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_claim_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    strong: Mapped[bool] = mapped_column(Boolean, nullable=False)
    field_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_pins: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_SESSION_KINDS)})", name="kind_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_sessions_owner_id"),
        Index(
            "ix_interview_sessions_owner_application_updated",
            "owner_user_id",
            "application_id",
            "updated_at",
            "id",
        ),
        Index(
            "ix_interview_sessions_owner_scheduled",
            "owner_user_id",
            "scheduled_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_QUESTION_KINDS)})", name="kind_valid"),
        CheckConstraint("ordinal > 0", name="ordinal_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_questions_owner_session",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_questions_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "session_id",
            "ordinal",
            name="uq_interview_questions_owner_session_ordinal",
        ),
        Index(
            "ix_interview_questions_owner_session_created",
            "owner_user_id",
            "session_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_requirement_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_claim_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    generated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewSessionNoteModel(Base):
    __tablename__ = "interview_session_notes"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_NOTE_KINDS)})", name="kind_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_session_notes_owner_session",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_session_notes_owner_id"),
        Index(
            "ix_interview_session_notes_owner_session_created",
            "owner_user_id",
            "session_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FollowUpDraftModel(Base):
    __tablename__ = "interview_follow_up_drafts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["interview_sessions.owner_user_id", "interview_sessions.id"],
            name="fk_interview_follow_up_drafts_owner_session",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_follow_up_drafts_owner_id"),
        Index(
            "ix_interview_follow_up_drafts_owner_session_created",
            "owner_user_id",
            "session_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewIdempotencyModel(Base):
    __tablename__ = "interview_idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "response_snapshot IS NULL OR "
            "(resource_kind = 'star_story' AND jsonb_typeof(response_snapshot) = 'object')",
            name="response_snapshot_scope_valid",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_interview_idempotency_owner_key",
        ),
        Index(
            "ix_interview_idempotency_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    response_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewAuditEventModel(Base):
    __tablename__ = "interview_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        UniqueConstraint("owner_user_id", "id", name="uq_interview_audit_events_owner_id"),
        Index(
            "ix_interview_audit_events_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_interview_audit_events_owner_target",
            "owner_user_id",
            "target_kind",
            "target_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, str]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
