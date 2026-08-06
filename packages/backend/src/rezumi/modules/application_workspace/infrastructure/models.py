"""SQLAlchemy mappings for Phase 8 application workspace and packs."""

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
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base

_STAGES = (
    "saved",
    "researching",
    "preparing",
    "ready_to_apply",
    "applied",
    "recruiter_screen",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
)
_REFERRAL_STATUSES = ("none", "needed", "requested", "referred")
_OUTCOME_STATUSES = ("none", "offer", "rejected", "withdrawn")
_EVENT_KINDS = (
    "created",
    "stage_changed",
    "deadline_changed",
    "follow_up_changed",
    "note_added",
    "task_added",
    "task_completed",
    "pack_generated",
    "outcome_recorded",
    "resume_version_changed",
    "interview",
    "contact",
    "custom",
)
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
)
_DOCUMENT_STATUSES = ("generated", "blocked", "deleted")
_PACK_STATUSES = ("generated", "blocked")
_CONSISTENCY_STATUSES = ("passed", "warning", "failed")
_AUDIT_ACTIONS = (
    "application_created",
    "application_updated",
    "application_stage_changed",
    "resume_version_changed",
    "application_deleted",
    "task_created",
    "task_updated",
    "note_created",
    "event_recorded",
    "pack_generated",
    "document_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class ApplicationRecordModel(Base):
    __tablename__ = "application_records"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_values(_STAGES)})", name="stage_valid"),
        CheckConstraint(
            f"referral_status IN ({_values(_REFERRAL_STATUSES)})",
            name="referral_status_valid",
        ),
        CheckConstraint(
            f"outcome_status IN ({_values(_OUTCOME_STATUSES)})",
            name="outcome_status_valid",
        ),
        CheckConstraint(
            "("
            "(stage = 'offer' AND outcome_status = 'offer') OR "
            "(stage = 'rejected' AND outcome_status = 'rejected') OR "
            "(stage = 'withdrawn' AND outcome_status = 'withdrawn') OR "
            "("
            "stage NOT IN ('offer','rejected','withdrawn') "
            "AND outcome_status = 'none'"
            ")"
            ")",
            name="stage_outcome_consistent",
        ),
        CheckConstraint("job_version > 0", name="job_version_positive"),
        CheckConstraint("length(job_source_sha256) = 64", name="job_source_sha256_length"),
        CheckConstraint("resume_version_number > 0", name="resume_version_number_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_records_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "resume_version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_application_records_owner_resume_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_records_owner_id"),
        Index("ix_application_records_owner_updated", "owner_user_id", "updated_at", "id"),
        Index("ix_application_records_owner_stage", "owner_user_id", "stage", "updated_at"),
        Index("ix_application_records_owner_deadline", "owner_user_id", "application_deadline"),
        Index("ix_application_records_owner_follow_up", "owner_user_id", "follow_up_at"),
        Index("ix_application_records_owner_source", "owner_user_id", "source"),
        Index("ix_application_records_owner_industry", "owner_user_id", "industry"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    job_analysis_id: Mapped[UUID | None] = mapped_column(Uuid)
    job_source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    job_requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    requirement_support: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    resume_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resume_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resume_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_title: Mapped[str] = mapped_column(String(120), nullable=False)
    resume_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_pins: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    resume_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    application_deadline: Mapped[date | None] = mapped_column(Date)
    follow_up_at: Mapped[date | None] = mapped_column(Date)
    contacts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    referral_status: Mapped[str] = mapped_column(String(24), nullable=False)
    outcome_status: Mapped[str] = mapped_column(String(24), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    offer_summary: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationTaskModel(Base):
    __tablename__ = "application_tasks"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_tasks_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_tasks_owner_application",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_tasks_owner_id"),
        Index(
            "ix_application_tasks_application_due",
            "owner_user_id",
            "application_id",
            "due_at",
            "created_at",
            "id",
        ),
        Index("ix_application_tasks_owner_due", "owner_user_id", "due_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationNoteModel(Base):
    __tablename__ = "application_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_notes_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_notes_owner_application",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_notes_owner_id"),
        Index(
            "ix_application_notes_application_created",
            "owner_user_id",
            "application_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationEventModel(Base):
    __tablename__ = "application_events"
    __table_args__ = (
        CheckConstraint(f"event_kind IN ({_values(_EVENT_KINDS)})", name="event_kind_valid"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_events_owner_application",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_events_owner_id"),
        Index(
            "ix_application_events_application_occurred",
            "owner_user_id",
            "application_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_application_events_application_kind",
            "owner_user_id",
            "application_id",
            "event_kind",
        ),
        Index("ix_application_events_owner_occurred", "owner_user_id", "occurred_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, str]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationPackModel(Base):
    __tablename__ = "application_packs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_PACK_STATUSES)})", name="status_valid"),
        CheckConstraint(
            f"consistency_status IN ({_values(_CONSISTENCY_STATUSES)})",
            name="consistency_status_valid",
        ),
        CheckConstraint("job_version > 0", name="job_version_positive"),
        CheckConstraint("resume_version_number > 0", name="resume_version_number_positive"),
        CheckConstraint("application_version > 0", name="application_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_packs_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_packs_owner_application",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_packs_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "id",
            "application_id",
            name="uq_application_packs_owner_id_application",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_application_packs_owner_idempotency",
        ),
        Index(
            "ix_application_packs_application_created",
            "owner_user_id",
            "application_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resume_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    application_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_revision_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    requirement_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    consistency_status: Mapped[str] = mapped_column(String(16), nullable=False)
    consistency_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationDocumentModel(Base):
    __tablename__ = "application_documents"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_DOCUMENT_KINDS)})", name="kind_valid"),
        CheckConstraint(f"status IN ({_values(_DOCUMENT_STATUSES)})", name="status_valid"),
        CheckConstraint(
            f"consistency_status IN ({_values(_CONSISTENCY_STATUSES)})",
            name="consistency_status_valid",
        ),
        CheckConstraint("length(content_sha256) = 64", name="content_sha256_length"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_documents_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "application_id"],
            ["application_records.owner_user_id", "application_records.id"],
            name="fk_application_documents_owner_application",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "pack_id", "application_id"],
            [
                "application_packs.owner_user_id",
                "application_packs.id",
                "application_packs.application_id",
            ],
            name="fk_application_documents_owner_pack_application",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_application_documents_owner_id"),
        Index(
            "ix_application_documents_application_kind",
            "owner_user_id",
            "application_id",
            "kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    pack_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_requirement_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    consistency_status: Mapped[str] = mapped_column(String(16), nullable=False)
    consistency_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApplicationIdempotencyModel(Base):
    __tablename__ = "application_workspace_idempotency"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_workspace_idempotency_owner_user_id_users",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_application_workspace_idempotency_owner_key",
        ),
        Index(
            "ix_application_workspace_idempotency_owner_created",
            "owner_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    response_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    response_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationAuditEventModel(Base):
    __tablename__ = "application_workspace_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_application_workspace_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_application_workspace_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        Index(
            "ix_application_workspace_audit_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
