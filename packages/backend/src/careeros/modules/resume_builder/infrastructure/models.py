"""SQLAlchemy mappings for Phase 7 resume builder and verified export."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
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

from careeros.foundation.database import Base

_TEMPLATES = (
    "standard_professional",
    "compact_technical",
    "executive",
    "graduate",
    "consulting_finance",
)
_FORMATS = ("pdf", "docx", "text", "json")
_EXPORT_STATUSES = ("pending", "rendering", "verified", "blocked", "failed", "deleted")
_VERIFICATION_STATUSES = ("passed", "warning", "failed")
_AUDIT_ACTIONS = (
    "resume_created",
    "resume_updated",
    "version_created",
    "version_restored",
    "export_requested",
    "export_verified",
    "export_blocked",
    "download_intent_created",
    "export_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class ResumeModel(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint(f"template IN ({_values(_TEMPLATES)})", name="template_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_resumes_owner_id"),
        Index("ix_resumes_owner_updated", "owner_user_id", "updated_at", "id"),
        Index("ix_resumes_owner_source_change", "owner_user_id", "source_change_set_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    target_role: Mapped[str | None] = mapped_column(String(120))
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_change_set_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_change_set_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeVersionModel(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        CheckConstraint(f"template IN ({_values(_TEMPLATES)})", name="template_valid"),
        CheckConstraint("version_number > 0", name="version_number_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "resume_id"],
            ["resumes.owner_user_id", "resumes.id"],
            name="fk_resume_versions_owner_resume",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_versions_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "resume_id",
            "version_number",
            name="uq_resume_versions_owner_resume_number",
        ),
        Index(
            "ix_resume_versions_resume_number",
            "owner_user_id",
            "resume_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    target_role: Mapped[str | None] = mapped_column(String(120))
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    sections: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_change_set_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_change_set_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeExportModel(Base):
    __tablename__ = "resume_exports"
    __table_args__ = (
        CheckConstraint(f"format IN ({_values(_FORMATS)})", name="format_valid"),
        CheckConstraint(f"status IN ({_values(_EXPORT_STATUSES)})", name="status_valid"),
        CheckConstraint(
            "verification_status IS NULL OR "
            f"verification_status IN ({_values(_VERIFICATION_STATUSES)})",
            name="verification_status_valid",
        ),
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        ForeignKeyConstraint(
            ["owner_user_id", "resume_id"],
            ["resumes.owner_user_id", "resumes.id"],
            name="fk_resume_exports_owner_resume",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_resume_exports_owner_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_exports_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_exports_owner_idempotency",
        ),
        Index("ix_resume_exports_version", "owner_user_id", "version_id", "requested_at"),
        Index("ix_resume_exports_status", "status", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(140), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_digest: Mapped[str | None] = mapped_column(String(64))
    verification_status: Mapped[str | None] = mapped_column(String(16))
    verification_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    critical_failures: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class ResumeVerificationReportModel(Base):
    __tablename__ = "resume_export_verification_reports"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_VERIFICATION_STATUSES)})", name="status_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_verifications_owner_export",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "version_id"],
            ["resume_versions.owner_user_id", "resume_versions.id"],
            name="fk_resume_verifications_owner_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_verifications_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "export_id",
            name="uq_resume_verifications_owner_export",
        ),
        Index("ix_resume_verifications_export", "owner_user_id", "export_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    critical_failures: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    detected_lines: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    missing_lines: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    duplicate_lines: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reading_order: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    grounding_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeDownloadIntentModel(Base):
    __tablename__ = "resume_export_download_intents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_download_intents_owner_export",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_download_intents_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_download_intents_owner_idempotency",
        ),
        Index("ix_resume_download_intents_export", "owner_user_id", "export_id", "created_at"),
        Index("ix_resume_download_intents_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeBuilderIdempotencyModel(Base):
    __tablename__ = "resume_builder_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_resume_builder_idempotency_owner_key",
        ),
        Index(
            "ix_resume_builder_idempotency_target",
            "owner_user_id",
            "target_kind",
            "target_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    response_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    response_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeBuilderAuditEventModel(Base):
    __tablename__ = "resume_builder_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_builder_audit_owner_id"),
        Index("ix_resume_builder_audit_owner_created", "owner_user_id", "created_at"),
        Index("ix_resume_builder_audit_target", "owner_user_id", "target_kind", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
