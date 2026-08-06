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

from rezumi.foundation.database import Base

_TEMPLATES = (
    "standard_professional",
    "compact_technical",
    "executive",
    "graduate",
    "consulting_finance",
)
_FORMATS = ("pdf", "docx", "text", "json")
_EXPORT_STATUSES = (
    "pending",
    "rendering",
    "retry_wait",
    "verified",
    "blocked",
    "failed",
    "dead_lettered",
    "deletion_pending",
    "deleting",
    "deletion_retry_wait",
    "deletion_dead_lettered",
    "deleted",
)
_EXPORT_OPERATIONS = ("render", "delete")
_VERIFICATION_STATUSES = ("passed", "warning", "failed")
_AUDIT_ACTIONS = (
    "resume_created",
    "resume_updated",
    "version_created",
    "version_restored",
    "export_requested",
    "export_verified",
    "export_blocked",
    "export_retry_scheduled",
    "export_dead_lettered",
    "export_dispatched",
    "export_dispatch_retry_scheduled",
    "export_dispatch_dead_lettered",
    "export_recovery_scheduled",
    "export_deletion_requested",
    "export_deletion_retry_scheduled",
    "export_deletion_dead_lettered",
    "export_deletion_recovery_scheduled",
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
    layout: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
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
    layout: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    personal_facts: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    entities: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
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
        CheckConstraint("cleanup_attempts >= 0", name="cleanup_attempts_nonnegative"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="max_attempts_valid"),
        CheckConstraint(
            "cleanup_max_attempts BETWEEN 1 AND 10",
            name="cleanup_max_attempts_valid",
        ),
        CheckConstraint("fence >= 0", name="fence_nonnegative"),
        CheckConstraint(
            "(execution_token_hash IS NULL) = (lease_expires_at IS NULL)",
            name="execution_lease_pair",
        ),
        CheckConstraint(
            "(status IN ('rendering','deleting') AND execution_token_hash IS NOT NULL) OR "
            "(status NOT IN ('rendering','deleting') AND execution_token_hash IS NULL)",
            name="rendering_requires_lease",
        ),
        CheckConstraint(
            "(status IN ('retry_wait','deletion_retry_wait') AND retry_at IS NOT NULL) OR "
            "(status NOT IN ('retry_wait','deletion_retry_wait') AND retry_at IS NULL)",
            name="retry_state_valid",
        ),
        CheckConstraint(
            "(status IN ('dead_lettered','deletion_dead_lettered') "
            "AND dead_lettered_at IS NOT NULL) OR "
            "(status NOT IN ('dead_lettered','deletion_dead_lettered') "
            "AND dead_lettered_at IS NULL)",
            name="dead_letter_state_valid",
        ),
        CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL AND object_key IS NULL) OR "
            "(status <> 'deleted' AND deleted_at IS NULL)",
            name="deleted_state_valid",
        ),
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
        Index("ix_resume_exports_retry", "status", "retry_at"),
        Index("ix_resume_exports_lease", "status", "lease_expires_at"),
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
    version_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fidelity_manifest: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    fidelity_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str | None] = mapped_column(String(16))
    verification_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    critical_failures: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_token_hash: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class ResumeExportOutboxModel(Base):
    __tablename__ = "resume_export_outbox"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="max_attempts_valid"),
        CheckConstraint(
            f"operation IN ({_values(_EXPORT_OPERATIONS)})",
            name="operation_valid",
        ),
        CheckConstraint(
            "(lease_token IS NULL AND leased_at IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND leased_at IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="lease_state_valid",
        ),
        CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="terminal_state_exclusive",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_export_outbox_owner_export",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_resume_export_outbox_owner_id"),
        Index(
            "ix_resume_export_outbox_available",
            "available_at",
            "created_at",
            postgresql_where=text(
                "published_at IS NULL AND dead_lettered_at IS NULL AND lease_token IS NULL"
            ),
        ),
        Index(
            "uq_resume_export_outbox_active",
            "owner_user_id",
            "export_id",
            "operation",
            unique=True,
            postgresql_where=text("published_at IS NULL AND dead_lettered_at IS NULL"),
        ),
        Index("ix_resume_export_outbox_lease", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeExportObjectCleanupModel(Base):
    __tablename__ = "resume_export_object_cleanups"
    __table_args__ = (
        CheckConstraint("attempt_fence > 0", name="attempt_fence_positive"),
        CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint(
            "num_nonnulls(completed_at, cancelled_at, dead_lettered_at) <= 1",
            name="terminal_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "export_id"],
            ["resume_exports.owner_user_id", "resume_exports.id"],
            name="fk_resume_export_object_cleanups_owner_export",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_resume_export_object_cleanups_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "export_id",
            "attempt_fence",
            name="uq_resume_export_object_cleanups_owner_export_fence",
        ),
        Index(
            "ix_resume_export_object_cleanups_due",
            "not_before",
            "created_at",
            postgresql_where=text(
                "completed_at IS NULL AND cancelled_at IS NULL AND dead_lettered_at IS NULL"
            ),
        ),
        Index(
            "ix_resume_export_object_cleanups_owner",
            "owner_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    attempt_fence: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeVerificationReportModel(Base):
    __tablename__ = "resume_export_verification_reports"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_VERIFICATION_STATUSES)})", name="status_valid"),
        CheckConstraint("page_count >= 0", name="page_count_nonnegative"),
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
    occurrence_mismatches: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reading_order_failures: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
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
