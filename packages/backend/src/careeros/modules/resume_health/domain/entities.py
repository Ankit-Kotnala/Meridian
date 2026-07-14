"""Framework-free entities and state machines for Phase 2 resume processing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from careeros.modules.resume_health.domain.errors import ResumeStateConflict


class ResumeMediaType(StrEnum):
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class UploadStatus(StrEnum):
    ISSUED = "issued"
    FINALIZED = "finalized"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


class DocumentStatus(StrEnum):
    QUARANTINED = "quarantined"
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"


class MalwareStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    UNAVAILABLE = "unavailable"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


class JobKind(StrEnum):
    PARSE = "parse"
    ANALYZE = "analyze"
    DELETE = "delete"


class ProcessingStage(StrEnum):
    QUEUED = "queued"
    ADMISSION = "admission"
    MALWARE_SCAN = "malware_scan"
    EXTRACTION = "extraction"
    CANONICALIZATION = "canonicalization"
    ANALYSIS = "analysis"
    COMPLETE = "complete"
    CLEANUP = "cleanup"


class ArtifactKind(StrEnum):
    PLAIN_TEXT = "plain_text"
    READING_ORDER = "reading_order"


class AnalysisStatus(StrEnum):
    SUCCEEDED = "succeeded"
    INSUFFICIENT_DATA = "insufficient_data"


class ObjectCleanupPurpose(StrEnum):
    CLAIM_COMPENSATION = "claim_compensation"
    CLAIM_SOURCE = "claim_source"
    UPLOAD_STAGING_BACKSTOP = "upload_staging_backstop"
    UPLOAD_QUARANTINE_CLEANUP = "upload_quarantine_cleanup"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SectionKind(StrEnum):
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    OTHER = "other"


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET = "bullet"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class OwnerScope:
    """Exactly one durable owner; resource UUIDs are never authorization."""

    user_id: UUID | None = None
    guest_session_id: UUID | None = None

    def __post_init__(self) -> None:
        if (self.user_id is None) == (self.guest_session_id is None):
            raise ValueError("exactly one user or guest owner is required")

    @property
    def owner_id(self) -> UUID:
        return self.user_id if self.user_id is not None else self._guest_id

    @property
    def _guest_id(self) -> UUID:
        if self.guest_session_id is None:
            raise RuntimeError("guest owner is unavailable")
        return self.guest_session_id

    @property
    def kind(self) -> str:
        return "user" if self.user_id is not None else "guest"


@dataclass(slots=True)
class GuestSession:
    id: UUID
    capability_hash: bytes
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    claimed_by_user_id: UUID | None = None
    claimed_document_id: UUID | None = None

    def active_at(self, now: datetime) -> bool:
        return self.revoked_at is None and self.claimed_by_user_id is None and now < self.expires_at


@dataclass(slots=True)
class UploadIntent:
    id: UUID
    owner: OwnerScope
    display_filename: str
    expected_media_type: ResumeMediaType
    expected_size: int
    staging_object_key: str
    status: UploadStatus
    created_at: datetime
    expires_at: datetime
    finalized_document_id: UUID | None = None
    safe_error_code: str | None = None
    staging_cleaned_at: datetime | None = None


@dataclass(slots=True)
class SourceDocument:
    id: UUID
    upload_id: UUID
    owner: OwnerScope
    display_filename: str
    media_type: ResumeMediaType
    size_bytes: int
    quarantine_object_key: str
    status: DocumentStatus
    malware_status: MalwareStatus
    created_at: datetime
    updated_at: datetime
    retention_expires_at: datetime | None
    content_sha256: bytes | None = None
    page_count: int | None = None
    safe_error_code: str | None = None
    deleted_at: datetime | None = None
    version: int = 1


@dataclass(slots=True)
class ProcessingJob:
    id: UUID
    document_id: UUID
    owner: OwnerScope
    kind: JobKind
    idempotency_key: str
    request_hash: bytes
    trace_id: str
    status: JobStatus
    stage: ProcessingStage
    progress: int | None
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    safe_error_code: str | None = None
    retryable: bool = False
    dead_lettered_at: datetime | None = None
    version: int = 1
    result_id: UUID | None = None
    input_snapshot_id: UUID | None = None
    execution_token_hash: bytes | None = None
    lease_expires_at: datetime | None = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    next_recovery_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {
            JobStatus.SUCCEEDED,
            JobStatus.CANCELLED,
            JobStatus.DEAD_LETTERED,
        } or (self.status == JobStatus.FAILED and not self.retryable)

    def start(self, now: datetime) -> None:
        if self.terminal:
            return
        if self.cancellation_requested_at is not None:
            self.cancel(now)
            return
        if self.status not in {JobStatus.QUEUED, JobStatus.FAILED}:
            raise ResumeStateConflict
        self.status = JobStatus.RUNNING
        self.stage = ProcessingStage.ADMISSION
        self.progress = 5
        self.attempts += 1
        self.started_at = self.started_at or now
        self.updated_at = now
        self.safe_error_code = None
        self.retryable = False
        self.version += 1

    def acquire_execution_lease(
        self,
        token_hash: bytes,
        lease_expires_at: datetime,
        now: datetime,
        *,
        recovered: bool = False,
    ) -> None:
        if self.status != JobStatus.RUNNING or len(token_hash) != 32 or lease_expires_at <= now:
            raise ResumeStateConflict
        if recovered:
            if self.attempts >= self.max_attempts:
                raise ResumeStateConflict
            self.attempts += 1
            self.stage = ProcessingStage.ADMISSION
            self.progress = 5
        self.execution_token_hash = token_hash
        self.lease_expires_at = lease_expires_at
        self.updated_at = now
        self.version += 1

    def refresh_execution_lease(
        self, token_hash: bytes, lease_expires_at: datetime, now: datetime
    ) -> None:
        if (
            self.status != JobStatus.RUNNING
            or self.execution_token_hash != token_hash
            or lease_expires_at <= now
        ):
            raise ResumeStateConflict
        self.lease_expires_at = lease_expires_at
        self.updated_at = now
        self.version += 1

    def _clear_execution_lease(self) -> None:
        self.execution_token_hash = None
        self.lease_expires_at = None

    def advance(self, stage: ProcessingStage, progress: int, now: datetime) -> None:
        if self.status != JobStatus.RUNNING:
            raise ResumeStateConflict
        if not 0 <= progress <= 100:
            raise ValueError("progress must be between 0 and 100")
        self.stage = stage
        self.progress = progress
        self.updated_at = now
        self.version += 1

    def request_cancel(self, now: datetime) -> None:
        if self.terminal:
            return
        self.cancellation_requested_at = self.cancellation_requested_at or now
        if self.status in {JobStatus.QUEUED, JobStatus.FAILED}:
            self.cancel(now)
        else:
            self.updated_at = now
            self.version += 1

    def cancel(self, now: datetime) -> None:
        self.status = JobStatus.CANCELLED
        self.progress = None
        self.safe_error_code = "processing_cancelled"
        self.retryable = False
        self.completed_at = now
        self.updated_at = now
        self._clear_execution_lease()
        self.version += 1

    def fail(self, code: str, retryable: bool, now: datetime, *, exhausted: bool = False) -> None:
        self.status = JobStatus.DEAD_LETTERED if exhausted else JobStatus.FAILED
        self.safe_error_code = code
        self.retryable = retryable and not exhausted
        self.progress = None
        self.updated_at = now
        self.completed_at = now if exhausted or not retryable else None
        self.dead_lettered_at = now if exhausted else None
        self._clear_execution_lease()
        self.version += 1

    def succeed(self, now: datetime) -> None:
        if self.status != JobStatus.RUNNING:
            raise ResumeStateConflict
        self.status = JobStatus.SUCCEEDED
        self.stage = ProcessingStage.COMPLETE
        self.progress = 100
        self.retryable = False
        self.completed_at = now
        self.updated_at = now
        self._clear_execution_lease()
        self.version += 1


@dataclass(frozen=True, slots=True)
class SourceSpan:
    page: int
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.page < 1 or self.start < 0 or self.end < self.start:
            raise ValueError("invalid source span")


@dataclass(frozen=True, slots=True)
class CanonicalBlock:
    id: UUID
    kind: BlockKind
    text: str
    confidence_basis_points: int
    spans: tuple[SourceSpan, ...]

    def __post_init__(self) -> None:
        if not self.text or len(self.text) > 10_000:
            raise ValueError("canonical block text is empty or too long")
        if not 0 <= self.confidence_basis_points <= 10_000:
            raise ValueError("confidence must be between 0 and 10000")


@dataclass(frozen=True, slots=True)
class CanonicalSection:
    id: UUID
    kind: SectionKind
    title: str
    confidence_basis_points: int
    blocks: tuple[CanonicalBlock, ...]


@dataclass(frozen=True, slots=True)
class CanonicalResume:
    schema_version: str
    sections: tuple[CanonicalSection, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "sections": [
                {
                    "id": str(section.id),
                    "kind": section.kind.value,
                    "title": section.title,
                    "confidenceBasisPoints": section.confidence_basis_points,
                    "blocks": [
                        {
                            "id": str(block.id),
                            "kind": block.kind.value,
                            "text": block.text,
                            "confidenceBasisPoints": block.confidence_basis_points,
                            "spans": [
                                {"page": span.page, "start": span.start, "end": span.end}
                                for span in block.spans
                            ],
                        }
                        for block in section.blocks
                    ],
                }
                for section in self.sections
            ],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CanonicalResume:
        return cls(
            schema_version=str(value["schemaVersion"]),
            sections=tuple(
                CanonicalSection(
                    id=UUID(str(section["id"])),
                    kind=SectionKind(str(section["kind"])),
                    title=str(section["title"]),
                    confidence_basis_points=int(section["confidenceBasisPoints"]),
                    blocks=tuple(
                        CanonicalBlock(
                            id=UUID(str(block["id"])),
                            kind=BlockKind(str(block["kind"])),
                            text=str(block["text"]),
                            confidence_basis_points=int(block["confidenceBasisPoints"]),
                            spans=tuple(
                                SourceSpan(
                                    page=int(span["page"]),
                                    start=int(span["start"]),
                                    end=int(span["end"]),
                                )
                                for span in block.get("spans", [])
                            ),
                        )
                        for block in section.get("blocks", [])
                    ),
                )
                for section in value.get("sections", [])
            ),
            warnings=tuple(str(item) for item in value.get("warnings", [])),
        )


@dataclass(slots=True)
class CanonicalSnapshot:
    id: UUID
    document_id: UUID
    owner: OwnerScope
    revision: int
    resume: CanonicalResume
    plain_text_sha256: bytes
    parser_version: str
    created_at: datetime
    based_on_snapshot_id: UUID | None = None
    corrected_by_user: bool = False


@dataclass(slots=True)
class DocumentArtifact:
    id: UUID
    document_id: UUID
    owner: OwnerScope
    kind: ArtifactKind
    object_key: str
    size_bytes: int
    sha256: bytes
    created_at: datetime


@dataclass(slots=True)
class ResumeHealthAnalysis:
    id: UUID
    job_id: UUID
    document_id: UUID
    snapshot_id: UUID
    owner: OwnerScope
    status: AnalysisStatus
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    feature_values: dict[str, int | bool]
    feature_set_hash: bytes
    raw_score_basis_points: int | None
    display_score: int | None
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    id: UUID
    analysis_id: UUID
    code: str
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class FeatureContribution:
    id: UUID
    analysis_id: UUID
    component_code: str
    feature_code: str
    feature_value_basis_points: int
    weight_basis_points: int
    contribution_basis_points: int


@dataclass(frozen=True, slots=True)
class ResumeFinding:
    id: UUID
    analysis_id: UUID
    code: str
    severity: FindingSeverity
    component_code: str
    message: str
    quick_win: bool
    sort_order: int


@dataclass(slots=True)
class OutboxMessage:
    id: UUID
    job_id: UUID
    task_name: str
    trace_id: str
    created_at: datetime
    next_attempt_at: datetime
    generation: int = 0
    max_attempts: int = 8
    published_at: datetime | None = None
    attempts: int = 0
    last_error_code: str | None = None
    dead_lettered_at: datetime | None = None

    def __post_init__(self) -> None:
        if (
            self.generation < 0
            or self.max_attempts < 1
            or not 0 <= self.attempts <= self.max_attempts
        ):
            raise ValueError("invalid outbox attempt bounds")

    @property
    def terminal(self) -> bool:
        return self.published_at is not None or self.dead_lettered_at is not None

    def publish(self, now: datetime) -> None:
        if self.terminal:
            return
        self.attempts += 1
        self.published_at = now
        self.last_error_code = None

    def fail(self, code: str, now: datetime, next_attempt_at: datetime) -> None:
        if self.terminal:
            return
        self.attempts += 1
        self.last_error_code = code
        if self.attempts >= self.max_attempts:
            self.dead_lettered_at = now
        else:
            self.next_attempt_at = next_attempt_at


@dataclass(slots=True)
class StorageObjectCleanup:
    """Durable, idempotent deletion intent for sensitive object-store data."""

    id: UUID
    owner: OwnerScope
    object_key: str
    purpose: ObjectCleanupPurpose
    not_before: datetime
    created_at: datetime
    attempts: int = 0
    max_attempts: int = 10
    last_error_code: str | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    dead_lettered_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.object_key or len(self.object_key) > 512 or self.max_attempts < 1:
            raise ValueError("invalid object cleanup task")

    @property
    def terminal(self) -> bool:
        return any(
            value is not None
            for value in (self.completed_at, self.cancelled_at, self.dead_lettered_at)
        )

    def complete(self, now: datetime) -> None:
        if self.terminal:
            return
        self.attempts += 1
        self.last_error_code = None
        self.completed_at = now

    def cancel(self, now: datetime) -> None:
        if self.terminal:
            return
        self.cancelled_at = now

    def fail(self, code: str, now: datetime, next_attempt_at: datetime) -> None:
        if self.terminal:
            return
        self.attempts += 1
        self.last_error_code = code
        if self.attempts >= self.max_attempts:
            self.dead_lettered_at = now
        else:
            self.not_before = next_attempt_at


@dataclass(frozen=True, slots=True)
class ResumeAuditEvent:
    id: UUID
    owner: OwnerScope
    action: str
    outcome: str
    resource_type: str
    resource_id: UUID
    request_id: str
    trace_id: str
    safe_metadata: dict[str, str]
    created_at: datetime
