"""SQLAlchemy mappings for owned resume processing and deterministic analyses."""

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

from rezumi.foundation.database import Base

_OWNER_CHECK = "(owner_user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)"


class GuestResumeSessionModel(Base):
    __tablename__ = "guest_resume_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    capability_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    claimed_document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="SET NULL")
    )


class ResumeUploadModel(Base):
    __tablename__ = "resume_uploads"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint(
            "status IN ('issued','finalized','rejected','expired','deleted')",
            name="status_valid",
        ),
        CheckConstraint("expected_size > 0", name="expected_size_positive"),
        UniqueConstraint("staging_object_key", name="uq_resume_uploads_staging_object_key"),
        Index("ix_resume_uploads_owner_user_created", "owner_user_id", "created_at"),
        Index("ix_resume_uploads_guest_created", "guest_session_id", "created_at"),
        Index(
            "ix_resume_uploads_staging_cleanup",
            "expires_at",
            "staging_cleaned_at",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_size: Mapped[int] = mapped_column(Integer, nullable=False)
    staging_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    staging_cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="SET NULL")
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(80))


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint(
            "status IN ('quarantined','processing','ready','rejected','failed',"
            "'deleting','deleted')",
            name="status_valid",
        ),
        CheckConstraint(
            "malware_status IN ('pending','clean','infected','unavailable')",
            name="malware_status_valid",
        ),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("upload_id", name="uq_source_documents_upload_id"),
        UniqueConstraint("quarantine_object_key", name="uq_source_documents_quarantine_object_key"),
        Index("ix_source_documents_owner_status", "owner_user_id", "status"),
        Index("ix_source_documents_guest_status", "guest_session_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    upload_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_uploads.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    quarantine_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    malware_status: Mapped[str] = mapped_column(String(16), nullable=False)
    content_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    page_count: Mapped[int | None] = mapped_column(Integer)
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentArtifactModel(Base):
    __tablename__ = "document_artifacts"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint("kind IN ('plain_text','reading_order')", name="kind_valid"),
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        UniqueConstraint("document_id", "kind", name="uq_document_artifacts_document_kind"),
        UniqueConstraint("object_key", name="uq_document_artifacts_object_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeProcessingJobModel(Base):
    __tablename__ = "resume_processing_jobs"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint("kind IN ('parse','analyze','delete')", name="kind_valid"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','dead_lettered')",
            name="status_valid",
        ),
        CheckConstraint(
            "stage IN ('queued','admission','malware_scan','extraction','canonicalization',"
            "'analysis','complete','cleanup')",
            name="stage_valid",
        ),
        CheckConstraint(
            "progress IS NULL OR (progress >= 0 AND progress <= 100)", name="progress_valid"
        ),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="attempts_valid"),
        CheckConstraint(
            "recovery_attempts >= 0 AND max_recovery_attempts > 0 "
            "AND recovery_attempts <= max_recovery_attempts",
            name="recovery_attempts_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(execution_token_hash IS NULL) = (lease_expires_at IS NULL)",
            name="execution_lease_pair",
        ),
        CheckConstraint(
            "(status = 'running') = (execution_token_hash IS NOT NULL)",
            name="running_requires_execution_lease",
        ),
        CheckConstraint(
            "execution_token_hash IS NULL OR octet_length(execution_token_hash) = 32",
            name="execution_token_hash_length",
        ),
        CheckConstraint(
            "(kind = 'analyze') = (input_snapshot_id IS NOT NULL)",
            name="analysis_snapshot_required",
        ),
        Index(
            "uq_resume_processing_jobs_user_idempotency",
            "owner_user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "uq_resume_processing_jobs_guest_idempotency",
            "guest_session_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("guest_session_id IS NOT NULL"),
        ),
        Index("ix_resume_processing_jobs_status_created", "status", "created_at"),
        Index("ix_resume_processing_jobs_document_status", "document_id", "status"),
        Index("ix_resume_processing_jobs_lease", "status", "lease_expires_at"),
        Index("ix_resume_processing_jobs_recovery", "status", "next_recovery_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    progress: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    retryable: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_id: Mapped[UUID | None] = mapped_column(Uuid)
    input_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_resume_snapshots.id", ondelete="RESTRICT")
    )
    execution_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_recovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeProcessingOutboxModel(Base):
    __tablename__ = "resume_processing_outbox"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "task_name",
            "generation",
            name="uq_resume_processing_outbox_job_task_generation",
        ),
        CheckConstraint(
            "generation >= 0 AND attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="terminal_state_valid",
        ),
        Index(
            "ix_resume_processing_outbox_pending",
            "published_at",
            "dead_lettered_at",
            "next_attempt_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_processing_jobs.id", ondelete="CASCADE"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(120), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResumeObjectCleanupModel(Base):
    __tablename__ = "resume_object_cleanups"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint(
            "purpose IN ('claim_compensation','claim_source','upload_staging_backstop',"
            "'upload_quarantine_cleanup')",
            name="purpose_valid",
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint(
            "num_nonnulls(completed_at, cancelled_at, dead_lettered_at) <= 1",
            name="terminal_state_valid",
        ),
        Index(
            "ix_resume_object_cleanups_due",
            "completed_at",
            "cancelled_at",
            "dead_lettered_at",
            "not_before",
        ),
        Index("ix_resume_object_cleanups_owner", "owner_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CanonicalResumeSnapshotModel(Base):
    __tablename__ = "canonical_resume_snapshots"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint("revision > 0", name="revision_positive"),
        UniqueConstraint("document_id", "revision", name="uq_canonical_resume_document_revision"),
        Index("ix_canonical_resume_owner_document", "owner_user_id", "document_id"),
        Index("ix_canonical_resume_guest_document", "guest_session_id", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plain_text_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    based_on_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_resume_snapshots.id", ondelete="SET NULL")
    )
    corrected_by_user: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeHealthAnalysisModel(Base):
    __tablename__ = "resume_health_analyses"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint("status IN ('succeeded','insufficient_data')", name="status_valid"),
        CheckConstraint(
            "raw_score_basis_points IS NULL OR "
            "(raw_score_basis_points >= 0 AND raw_score_basis_points <= 10000)",
            name="raw_score_valid",
        ),
        CheckConstraint(
            "display_score IS NULL OR (display_score >= 0 AND display_score <= 100)",
            name="display_score_valid",
        ),
        CheckConstraint("jsonb_typeof(feature_values) = 'object'", name="feature_values_object"),
        UniqueConstraint("job_id", name="uq_resume_health_analyses_job_id"),
        UniqueConstraint("snapshot_id", name="uq_resume_health_analyses_snapshot_id"),
        Index("ix_resume_health_analyses_owner_document", "owner_user_id", "document_id"),
        Index("ix_resume_health_analyses_guest_document", "guest_session_id", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_processing_jobs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("canonical_resume_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(80), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    feature_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_set_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    raw_score_basis_points: Mapped[int | None] = mapped_column(Integer)
    display_score: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeHealthComponentModel(Base):
    __tablename__ = "resume_health_components"
    __table_args__ = (
        CheckConstraint(
            "weight_basis_points > 0 AND weight_basis_points <= 10000", name="weight_valid"
        ),
        CheckConstraint(
            "score_basis_points >= 0 AND score_basis_points <= 10000", name="score_valid"
        ),
        CheckConstraint(
            "contribution_basis_points >= 0 AND contribution_basis_points <= 10000",
            name="contribution_valid",
        ),
        UniqueConstraint("analysis_id", "code", name="uq_resume_health_components_analysis_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_health_analyses.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class ResumeHealthFeatureContributionModel(Base):
    __tablename__ = "resume_health_feature_contributions"
    __table_args__ = (
        CheckConstraint(
            "feature_value_basis_points >= 0 AND feature_value_basis_points <= 10000",
            name="feature_value_valid",
        ),
        CheckConstraint(
            "weight_basis_points > 0 AND weight_basis_points <= 10000",
            name="weight_valid",
        ),
        CheckConstraint(
            "contribution_basis_points >= 0 AND contribution_basis_points <= 10000",
            name="contribution_valid",
        ),
        UniqueConstraint(
            "analysis_id",
            "component_code",
            "feature_code",
            name="uq_health_feature_contributions_analysis_component_feature",
        ),
        Index(
            "ix_resume_health_feature_contributions_analysis_component",
            "analysis_id",
            "component_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_health_analyses.id", ondelete="CASCADE"), nullable=False
    )
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_code: Mapped[str] = mapped_column(String(80), nullable=False)
    feature_value_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)


class ResumeHealthFindingModel(Base):
    __tablename__ = "resume_health_findings"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','critical')", name="severity_valid"),
        UniqueConstraint("analysis_id", "code", name="uq_resume_health_findings_analysis_code"),
        Index("ix_resume_health_findings_analysis_sort", "analysis_id", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_health_analyses.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    quick_win: Mapped[bool] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ResumeAuditEventModel(Base):
    __tablename__ = "resume_audit_events"
    __table_args__ = (
        CheckConstraint(_OWNER_CHECK, name="owner_exactly_one"),
        CheckConstraint(
            "outcome IN ('accepted','succeeded','failed','cancelled')", name="outcome_valid"
        ),
        Index("ix_resume_audit_events_owner_created", "owner_user_id", "created_at"),
        Index("ix_resume_audit_events_guest_created", "guest_session_id", "created_at"),
        Index("ix_resume_audit_events_resource", "resource_type", "resource_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("guest_resume_sessions.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_metadata: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
