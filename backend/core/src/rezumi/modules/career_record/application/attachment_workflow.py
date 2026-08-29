"""Private evidence-attachment admission, processing, access, and deletion.

This module deliberately owns provider-neutral contracts instead of importing the
Resume Health bounded context. Object keys and document payloads remain internal to
the application/infrastructure boundary; worker messages contain identifiers only.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

PROCESS_EVIDENCE_ATTACHMENT_TASK = "rezumi.career_record.process_evidence_attachment"
DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK = (
    "rezumi.career_record.dispatch_evidence_attachment_outbox"
)
CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK = (
    "rezumi.career_record.cleanup_evidence_attachment_objects"
)
RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK = "rezumi.career_record.reconcile_evidence_attachment_jobs"

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_EXECUTION_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_RANDOM_KEY_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class AttachmentMediaType(StrEnum):
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AttachmentStatus(StrEnum):
    ADMITTED = "admitted"
    QUARANTINED = "quarantined"
    PROCESSING = "processing"
    CLEAN = "clean"
    REJECTED = "rejected"
    DELETING = "deleting"
    DELETED = "deleted"


class AttachmentJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"


class AttachmentJobStage(StrEnum):
    QUEUED = "queued"
    MALWARE_SCAN = "malware_scan"
    EXTRACTION = "extraction"
    COMPLETE = "complete"


class ScanVerdict(StrEnum):
    CLEAN = "clean"
    INFECTED = "infected"
    UNAVAILABLE = "unavailable"


class AttachmentDownloadPurpose(StrEnum):
    OWNER_EVIDENCE_REVIEW = "owner_evidence_review"


class CleanupPurpose(StrEnum):
    REJECTED_STAGING = "rejected_staging"
    FINALIZED_STAGING = "finalized_staging"
    REJECTED_QUARANTINE = "rejected_quarantine"
    OWNER_DELETION = "owner_deletion"


class CleanupStatus(StrEnum):
    PENDING = "pending"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    DEAD_LETTERED = "dead_lettered"


class AttachmentAuditAction(StrEnum):
    ADMISSION_CREATED = "evidence_attachment.admission_created"
    ADMISSION_REJECTED = "evidence_attachment.admission_rejected"
    FINALIZED = "evidence_attachment.finalized"
    PROCESSING_RETRY = "evidence_attachment.processing_retry"
    PROCESSING_REJECTED = "evidence_attachment.processing_rejected"
    PROCESSING_DEAD_LETTERED = "evidence_attachment.processing_dead_lettered"
    CLEAN = "evidence_attachment.clean"
    DELETION_REQUESTED = "evidence_attachment.deletion_requested"
    DELETED = "evidence_attachment.deleted"
    CLEANUP_DEAD_LETTERED = "evidence_attachment.cleanup_dead_lettered"


class SafeAttachmentError(StrEnum):
    ATTACHMENT_NOT_CLEAN = "attachment_not_clean"
    ATTACHMENT_PROCESSING_RETRY = "attachment_processing_retry"
    ATTACHMENT_PROCESSING_DEAD_LETTERED = "attachment_processing_dead_lettered"
    EXECUTION_FENCED = "attachment_execution_fenced"
    EXTRACTION_FAILED = "attachment_extraction_failed"
    INVALID_DOCUMENT_STRUCTURE = "attachment_invalid_document_structure"
    MALWARE_DETECTED = "attachment_malware_detected"
    MALWARE_SCANNER_UNAVAILABLE = "attachment_malware_scanner_unavailable"
    OBJECT_CLEANUP_FAILED = "attachment_object_cleanup_failed"
    PROCESSING_TIMEOUT = "attachment_processing_timeout"
    QUARANTINE_OBJECT_MISSING = "attachment_quarantine_object_missing"
    QUARANTINE_INTEGRITY_MISMATCH = "attachment_quarantine_integrity_mismatch"
    STORAGE_UNAVAILABLE = "attachment_storage_unavailable"
    TASK_PUBLISH_FAILED = "attachment_task_publish_failed"
    UPLOAD_EXPIRED = "attachment_upload_expired"
    UPLOAD_MEDIA_TYPE_MISMATCH = "attachment_upload_media_type_mismatch"
    UPLOAD_MISSING = "attachment_upload_missing"
    UPLOAD_SIGNATURE_MISMATCH = "attachment_upload_signature_mismatch"
    UPLOAD_SIZE_MISMATCH = "attachment_upload_size_mismatch"
    UPLOAD_SIZE_OUT_OF_RANGE = "attachment_upload_size_out_of_range"
    UPLOAD_TYPE_UNSUPPORTED = "attachment_upload_type_unsupported"
    UPLOAD_FILENAME_INVALID = "attachment_upload_filename_invalid"


_PERMANENT_PROCESSING_ERRORS = frozenset(
    {
        SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE,
        SafeAttachmentError.MALWARE_DETECTED,
        SafeAttachmentError.QUARANTINE_OBJECT_MISSING,
        SafeAttachmentError.QUARANTINE_INTEGRITY_MISMATCH,
    }
)
_AUDIT_DETAIL_KEYS = frozenset({"status", "safe_error_code", "job_status"})


class AttachmentWorkflowError(Exception):
    """Base class for expected attachment failures."""


class AttachmentNotFound(AttachmentWorkflowError):
    """The resource is absent from the authenticated owner's scope."""


class AttachmentConflict(AttachmentWorkflowError):
    """The requested transition conflicts with durable state."""


class AttachmentIdempotencyConflict(AttachmentConflict):
    """An idempotency key was reused for another finalization."""


class AttachmentRejected(AttachmentWorkflowError):
    def __init__(self, code: SafeAttachmentError) -> None:
        super().__init__(code.value)
        self.code = code


class AttachmentTemporarilyUnavailable(AttachmentWorkflowError):
    def __init__(self, code: SafeAttachmentError) -> None:
        super().__init__(code.value)
        self.code = code


class AttachmentFenced(AttachmentConflict):
    """The worker lease was replaced or expired before a state commit."""


class AttachmentObjectMissing(Exception):
    """Provider-neutral signal that an expected private object does not exist."""


class AttachmentStorageUnavailable(Exception):
    """Provider-neutral transient object-storage failure."""


class UnsafeAttachment(Exception):
    """Extractor/scanner signal for an allowlisted permanent rejection."""

    def __init__(self, code: SafeAttachmentError) -> None:
        if code not in _PERMANENT_PROCESSING_ERRORS:
            raise ValueError("unsafe attachment code must be permanently rejectable")
        super().__init__(code.value)
        self.code = code


class _RetryableProcessing(Exception):
    def __init__(self, code: SafeAttachmentError) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class AttachmentLimits:
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    max_archive_entries: int = 256
    max_archive_uncompressed_bytes: int = 50 * 1024 * 1024
    max_archive_ratio: int = 100
    max_extracted_characters: int = 500_000
    max_extracted_blocks: int = 5_000
    processing_timeout_seconds: float = 120.0
    # Configurable local scratch root; randomized subpaths created at runtime.
    temp_root: Path = Path("/tmp/rezumi").resolve() / "rezumi-attachments"  # noqa: S108

    def __post_init__(self) -> None:
        integer_limits = (
            self.max_upload_bytes,
            self.max_pdf_pages,
            self.max_archive_entries,
            self.max_archive_uncompressed_bytes,
            self.max_archive_ratio,
            self.max_extracted_characters,
            self.max_extracted_blocks,
        )
        if any(value < 1 for value in integer_limits):
            raise ValueError("attachment limits must be positive")
        if self.processing_timeout_seconds <= 0:
            raise ValueError("attachment processing timeout must be positive")
        if not self.temp_root.is_absolute():
            raise ValueError("attachment temporary root must be absolute")


@dataclass(frozen=True, slots=True)
class AttachmentPolicy:
    admission_ttl_seconds: int = 600
    download_ttl_seconds: int = 120
    execution_lease_seconds: int = 330
    max_processing_attempts: int = 3
    max_outbox_attempts: int = 8
    max_cleanup_attempts: int = 10
    max_attachments_per_evidence: int = 20

    def __post_init__(self) -> None:
        if any(
            value < 1
            for value in (
                self.admission_ttl_seconds,
                self.download_ttl_seconds,
                self.execution_lease_seconds,
                self.max_processing_attempts,
                self.max_outbox_attempts,
                self.max_cleanup_attempts,
                self.max_attachments_per_evidence,
            )
        ):
            raise ValueError("attachment policy values must be positive")
        if self.admission_ttl_seconds > 900 or self.download_ttl_seconds > 300:
            raise ValueError("attachment signed-operation TTL exceeds the security bound")


@dataclass(frozen=True, slots=True)
class AttachmentRequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str

    def __post_init__(self) -> None:
        _bounded_identifier(self.request_id, "request ID")
        _bounded_identifier(self.trace_id, "trace ID")


@dataclass(frozen=True, slots=True)
class AdmitAttachment:
    evidence_id: UUID
    display_filename: str
    media_type: str
    expected_size: int


@dataclass(frozen=True, slots=True)
class PresignedOperation:
    method: str
    url: str
    required_headers: tuple[tuple[str, str], ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AttachmentAdmissionView:
    attachment_id: UUID
    evidence_id: UUID
    display_filename: str
    media_type: AttachmentMediaType
    expected_size: int
    expires_at: datetime
    upload: PresignedOperation


@dataclass(frozen=True, slots=True)
class AttachmentView:
    attachment_id: UUID
    evidence_id: UUID
    display_filename: str | None
    media_type: AttachmentMediaType | None
    expected_size: int | None
    status: AttachmentStatus
    safe_error_code: SafeAttachmentError | None
    content_sha256: bytes | None
    page_count: int | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FinalizedAttachment:
    attachment_id: UUID
    job_id: UUID
    attachment_status: AttachmentStatus
    job_status: AttachmentJobStatus


@dataclass(frozen=True, slots=True)
class AttachmentDownloadGrant:
    attachment_id: UUID
    display_filename: str
    purpose: AttachmentDownloadPurpose
    operation: PresignedOperation


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    size_bytes: int
    media_type: str | None


@dataclass(frozen=True, slots=True)
class DownloadedObject:
    path: Path
    size_bytes: int
    sha256_digest: bytes


@dataclass(frozen=True, slots=True)
class MalwareScanResult:
    verdict: ScanVerdict


@dataclass(frozen=True, slots=True)
class AttachmentExtractionSummary:
    format_valid: bool
    page_count: int
    extracted_characters: int
    extracted_blocks: int
    archive_entries: int
    archive_uncompressed_bytes: int
    max_archive_ratio: int
    parser_version: str

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.page_count,
                self.extracted_characters,
                self.extracted_blocks,
                self.archive_entries,
                self.archive_uncompressed_bytes,
                self.max_archive_ratio,
            )
        ):
            raise ValueError("extraction summary values cannot be negative")
        _bounded_identifier(self.parser_version, "parser version")


@dataclass(frozen=True, slots=True)
class AttachmentJobLease:
    job_id: UUID
    attachment_id: UUID
    fence: int
    execution_token_hash: bytes
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AttachmentProcessingOutcome:
    job_id: UUID
    status: AttachmentJobStatus
    safe_error_code: SafeAttachmentError | None
    retryable: bool


@dataclass(frozen=True, slots=True)
class OutboxDispatchResult:
    published: int
    failed: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class CleanupOutcome:
    cleanup_id: UUID
    status: CleanupStatus
    safe_error_code: SafeAttachmentError | None


@dataclass(frozen=True, slots=True)
class CleanupBatchResult:
    completed: int
    failed: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class AttachmentReconciliationResult:
    requeued: int
    dead_lettered: int


@dataclass(slots=True)
class AttachmentRecord:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    display_filename: str | None
    media_type: AttachmentMediaType | None
    expected_size: int | None
    staging_object_key: str | None
    quarantine_object_key: str | None
    status: AttachmentStatus
    created_at: datetime
    updated_at: datetime
    admission_expires_at: datetime
    version: int = 1
    safe_error_code: SafeAttachmentError | None = None
    content_sha256: bytes | None = None
    extraction: AttachmentExtractionSummary | None = None
    finalized_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AttachmentFinalizationReceipt:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_hash: bytes
    attachment_id: UUID
    job_id: UUID
    created_at: datetime


@dataclass(slots=True)
class AttachmentProcessingJob:
    id: UUID
    owner_user_id: UUID
    attachment_id: UUID
    trace_id: str
    status: AttachmentJobStatus
    stage: AttachmentJobStage
    attempts: int
    max_attempts: int
    fence: int
    created_at: datetime
    updated_at: datetime
    execution_token_hash: bytes | None = None
    lease_expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    completed_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    safe_error_code: SafeAttachmentError | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {
            AttachmentJobStatus.SUCCEEDED,
            AttachmentJobStatus.REJECTED,
            AttachmentJobStatus.DEAD_LETTERED,
            AttachmentJobStatus.CANCELLED,
        }


@dataclass(slots=True)
class AttachmentOutboxMessage:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    task_name: str
    trace_id: str
    generation: int
    created_at: datetime
    next_attempt_at: datetime
    attempts: int
    max_attempts: int
    published_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    last_error_code: SafeAttachmentError | None = None
    cancelled_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        return any(
            value is not None
            for value in (self.published_at, self.dead_lettered_at, self.cancelled_at)
        )


@dataclass(slots=True)
class AttachmentObjectCleanup:
    id: UUID
    owner_user_id: UUID
    attachment_id: UUID
    object_key: str
    purpose: CleanupPurpose
    status: CleanupStatus
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    safe_error_code: SafeAttachmentError | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {CleanupStatus.COMPLETED, CleanupStatus.DEAD_LETTERED}


@dataclass(frozen=True, slots=True)
class AttachmentAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: AttachmentAuditAction
    attachment_id: UUID
    request_id: str
    trace_id: str
    safe_details: tuple[tuple[str, str], ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _bounded_identifier(self.request_id, "audit request ID")
        _bounded_identifier(self.trace_id, "audit trace ID")
        for key, value in self.safe_details:
            if key not in _AUDIT_DETAIL_KEYS or not 1 <= len(value) <= 80:
                raise ValueError("attachment audit details are not allowlisted")


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierGenerator(Protocol):
    def new(self) -> UUID: ...


class RandomTokenGenerator(Protocol):
    def token_urlsafe(self, entropy_bytes: int) -> str: ...


class AttachmentObjectStorage(Protocol):
    async def presign_put(
        self,
        object_key: str,
        media_type: str,
        expected_size: int,
        expires_at: datetime,
    ) -> PresignedOperation: ...

    async def head(self, object_key: str) -> ObjectMetadata: ...

    async def read_prefix(self, object_key: str, length: int) -> bytes: ...

    async def promote(self, staging_key: str, quarantine_key: str) -> None: ...

    async def download(
        self, object_key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject: ...

    async def presign_get(
        self,
        object_key: str,
        display_filename: str,
        purpose: AttachmentDownloadPurpose,
        expires_at: datetime,
    ) -> PresignedOperation: ...

    async def delete(self, object_key: str) -> None: ...


class AttachmentMalwareScanner(Protocol):
    async def scan(self, path: Path) -> MalwareScanResult: ...


class AttachmentExtractor(Protocol):
    async def extract(
        self, path: Path, media_type: AttachmentMediaType, limits: AttachmentLimits
    ) -> AttachmentExtractionSummary: ...


class AttachmentJobPublisher(Protocol):
    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None: ...


class AttachmentUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_admission(self, owner_user_id: UUID, evidence_id: UUID) -> None: ...

    async def evidence_exists(self, owner_user_id: UUID, evidence_id: UUID) -> bool: ...

    async def count_active_attachments(self, owner_user_id: UUID, evidence_id: UUID) -> int: ...

    async def add_attachment(self, attachment: AttachmentRecord) -> None: ...

    async def get_attachment(
        self, owner_user_id: UUID, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None: ...

    async def get_attachment_system(
        self, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None: ...

    async def save_attachment(self, attachment: AttachmentRecord) -> None: ...

    async def add_finalization_receipt(self, receipt: AttachmentFinalizationReceipt) -> None: ...

    async def get_finalization_receipt(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AttachmentFinalizationReceipt | None: ...

    async def add_job(self, job: AttachmentProcessingJob) -> None: ...

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> AttachmentProcessingJob | None: ...

    async def list_jobs_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentProcessingJob]: ...

    async def save_job(self, job: AttachmentProcessingJob) -> None: ...

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[AttachmentProcessingJob]: ...

    async def next_outbox_generation(self, owner_user_id: UUID, job_id: UUID) -> int: ...

    async def add_outbox(self, message: AttachmentOutboxMessage) -> None: ...

    async def list_pending_outbox(
        self, now: datetime, limit: int
    ) -> list[AttachmentOutboxMessage]: ...

    async def save_outbox(self, message: AttachmentOutboxMessage) -> None: ...

    async def add_cleanup(self, cleanup: AttachmentObjectCleanup) -> None: ...

    async def has_cleanup_for_object(
        self, owner_user_id: UUID, attachment_id: UUID, object_key: str
    ) -> bool: ...

    async def get_cleanup_system(
        self, cleanup_id: UUID, *, for_update: bool = False
    ) -> AttachmentObjectCleanup | None: ...

    async def list_cleanups_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentObjectCleanup]: ...

    async def list_due_cleanups(
        self, now: datetime, limit: int
    ) -> list[AttachmentObjectCleanup]: ...

    async def save_cleanup(self, cleanup: AttachmentObjectCleanup) -> None: ...

    async def add_audit(self, event: AttachmentAuditEvent) -> None: ...

    async def commit(self) -> None: ...


class AttachmentUnitOfWorkFactory(Protocol):
    def __call__(self) -> AttachmentUnitOfWork: ...


class _UuidGenerator:
    def new(self) -> UUID:
        return uuid4()


class _SecureTokenGenerator:
    def token_urlsafe(self, entropy_bytes: int) -> str:
        return secrets.token_urlsafe(entropy_bytes)


class AttachmentWorkflowService:
    """Owner-facing short transactions for private attachment objects."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        clock: Clock,
        storage: AttachmentObjectStorage,
        limits: AttachmentLimits,
        policy: AttachmentPolicy | None = None,
        ids: IdentifierGenerator | None = None,
        tokens: RandomTokenGenerator | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._storage = storage
        self._limits = limits
        self._policy = policy or AttachmentPolicy()
        self._ids = ids or _UuidGenerator()
        self._tokens = tokens or _SecureTokenGenerator()

    async def admit(
        self,
        owner_user_id: UUID,
        command: AdmitAttachment,
        context: AttachmentRequestContext,
    ) -> AttachmentAdmissionView:
        _authorize(owner_user_id, context)
        media_type = _media_type(command.media_type)
        filename = _filename(command.display_filename, media_type)
        if not 1 <= command.expected_size <= self._limits.max_upload_bytes:
            raise AttachmentRejected(SafeAttachmentError.UPLOAD_SIZE_OUT_OF_RANGE)
        now = self._clock.now()
        expires_at = now + timedelta(seconds=self._policy.admission_ttl_seconds)
        staging_key, quarantine_key = self._private_object_keys()
        attachment = AttachmentRecord(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            evidence_id=command.evidence_id,
            display_filename=filename,
            media_type=media_type,
            expected_size=command.expected_size,
            staging_object_key=staging_key,
            quarantine_object_key=quarantine_key,
            status=AttachmentStatus.ADMITTED,
            created_at=now,
            updated_at=now,
            admission_expires_at=expires_at,
        )
        try:
            async with self._uow() as uow:
                await uow.lock_admission(owner_user_id, command.evidence_id)
                if not await uow.evidence_exists(owner_user_id, command.evidence_id):
                    raise AttachmentNotFound
                active = await uow.count_active_attachments(owner_user_id, command.evidence_id)
                if active >= self._policy.max_attachments_per_evidence:
                    raise AttachmentConflict("attachment limit reached")
                target = await self._storage.presign_put(
                    staging_key, media_type.value, command.expected_size, expires_at
                )
                _validate_presigned_put(target, media_type, command.expected_size, expires_at)
                await uow.add_attachment(attachment)
                await uow.add_audit(
                    self._audit(
                        attachment,
                        context.actor_user_id,
                        AttachmentAuditAction.ADMISSION_CREATED,
                        context.request_id,
                        context.trace_id,
                        now,
                        (("status", attachment.status.value),),
                    )
                )
                await uow.commit()
        except AttachmentWorkflowError:
            raise
        except Exception as exc:
            raise AttachmentTemporarilyUnavailable(SafeAttachmentError.STORAGE_UNAVAILABLE) from exc
        return AttachmentAdmissionView(
            attachment.id,
            attachment.evidence_id,
            filename,
            media_type,
            command.expected_size,
            expires_at,
            target,
        )

    async def finalize(
        self,
        owner_user_id: UUID,
        attachment_id: UUID,
        idempotency_key: str,
        context: AttachmentRequestContext,
    ) -> FinalizedAttachment:
        _authorize(owner_user_id, context)
        _validate_idempotency_key(idempotency_key)
        request_hash = _finalize_request_hash(attachment_id)
        now = self._clock.now()
        promoted_key: str | None = None
        rejection: SafeAttachmentError | None = None
        result: FinalizedAttachment | None = None
        try:
            async with self._uow() as uow:
                replay = await self._replay(uow, owner_user_id, idempotency_key, request_hash)
                if replay is not None:
                    return replay
                attachment = await uow.get_attachment(owner_user_id, attachment_id, for_update=True)
                if attachment is None or attachment.status is AttachmentStatus.DELETED:
                    raise AttachmentNotFound
                if attachment.status is not AttachmentStatus.ADMITTED:
                    raise AttachmentConflict("attachment admission is not finalizable")
                if now >= attachment.admission_expires_at:
                    rejection = SafeAttachmentError.UPLOAD_EXPIRED
                else:
                    rejection = await self._admission_rejection(attachment)
                if rejection is not None:
                    await self._reject_admission(uow, attachment, rejection, context, now)
                    await uow.commit()
                else:
                    if (
                        attachment.staging_object_key is None
                        or attachment.quarantine_object_key is None
                    ):
                        raise AttachmentConflict("attachment object admission is incomplete")
                    try:
                        await self._storage.promote(
                            attachment.staging_object_key, attachment.quarantine_object_key
                        )
                    except Exception as exc:
                        raise AttachmentStorageUnavailable from exc
                    promoted_key = attachment.quarantine_object_key
                    job = AttachmentProcessingJob(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        attachment_id=attachment.id,
                        trace_id=context.trace_id,
                        status=AttachmentJobStatus.QUEUED,
                        stage=AttachmentJobStage.QUEUED,
                        attempts=0,
                        max_attempts=self._policy.max_processing_attempts,
                        fence=0,
                        created_at=now,
                        updated_at=now,
                    )
                    receipt = AttachmentFinalizationReceipt(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                        attachment_id=attachment.id,
                        job_id=job.id,
                        created_at=now,
                    )
                    attachment.status = AttachmentStatus.QUARANTINED
                    attachment.finalized_at = now
                    attachment.updated_at = now
                    attachment.version += 1
                    await uow.save_attachment(attachment)
                    await uow.add_job(job)
                    await uow.add_finalization_receipt(receipt)
                    await uow.add_outbox(self._outbox(job, now, generation=0))
                    await _queue_cleanup(
                        uow,
                        self._ids,
                        self._policy,
                        attachment,
                        attachment.staging_object_key,
                        CleanupPurpose.FINALIZED_STAGING,
                        now,
                    )
                    await uow.add_audit(
                        self._audit(
                            attachment,
                            context.actor_user_id,
                            AttachmentAuditAction.FINALIZED,
                            context.request_id,
                            context.trace_id,
                            now,
                            (
                                ("status", attachment.status.value),
                                ("job_status", job.status.value),
                            ),
                        )
                    )
                    await uow.commit()
                    result = FinalizedAttachment(
                        attachment.id, job.id, attachment.status, job.status
                    )
        except AttachmentStorageUnavailable as exc:
            raise AttachmentTemporarilyUnavailable(SafeAttachmentError.STORAGE_UNAVAILABLE) from exc
        except Exception:
            if promoted_key is not None:
                replay = await self._recover_finalization(
                    owner_user_id, idempotency_key, request_hash
                )
                if replay is not None:
                    return replay
                with suppress(Exception):
                    await self._storage.delete(promoted_key)
            raise
        if rejection is not None:
            raise AttachmentRejected(rejection)
        if result is None:
            raise RuntimeError("attachment finalization produced no durable result")
        return result

    async def get(
        self,
        owner_user_id: UUID,
        attachment_id: UUID,
        context: AttachmentRequestContext,
    ) -> AttachmentView:
        _authorize(owner_user_id, context)
        async with self._uow() as uow:
            attachment = await uow.get_attachment(owner_user_id, attachment_id)
        if attachment is None or attachment.status is AttachmentStatus.DELETED:
            raise AttachmentNotFound
        return _view(attachment)

    async def download(
        self,
        owner_user_id: UUID,
        attachment_id: UUID,
        purpose: AttachmentDownloadPurpose,
        context: AttachmentRequestContext,
    ) -> AttachmentDownloadGrant:
        _authorize(owner_user_id, context)
        expires_at = self._clock.now() + timedelta(seconds=self._policy.download_ttl_seconds)
        try:
            async with self._uow() as uow:
                attachment = await uow.get_attachment(owner_user_id, attachment_id, for_update=True)
                if attachment is None or attachment.status is AttachmentStatus.DELETED:
                    raise AttachmentNotFound
                if (
                    attachment.status is not AttachmentStatus.CLEAN
                    or attachment.quarantine_object_key is None
                    or attachment.display_filename is None
                ):
                    raise AttachmentConflict(SafeAttachmentError.ATTACHMENT_NOT_CLEAN.value)
                target = await self._storage.presign_get(
                    attachment.quarantine_object_key,
                    attachment.display_filename,
                    purpose,
                    expires_at,
                )
                _validate_presigned_get(target, expires_at)
        except AttachmentWorkflowError:
            raise
        except Exception as exc:
            raise AttachmentTemporarilyUnavailable(SafeAttachmentError.STORAGE_UNAVAILABLE) from exc
        return AttachmentDownloadGrant(attachment.id, attachment.display_filename, purpose, target)

    async def delete(
        self,
        owner_user_id: UUID,
        attachment_id: UUID,
        context: AttachmentRequestContext,
    ) -> AttachmentView:
        _authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            attachment = await uow.get_attachment(owner_user_id, attachment_id, for_update=True)
            if attachment is None:
                raise AttachmentNotFound
            if attachment.status is AttachmentStatus.DELETED:
                return _view(attachment)
            if attachment.status is not AttachmentStatus.DELETING:
                attachment.status = AttachmentStatus.DELETING
                attachment.safe_error_code = None
                attachment.updated_at = now
                attachment.version += 1
                for job in await uow.list_jobs_for_attachment(owner_user_id, attachment.id):
                    if not job.terminal:
                        job.status = AttachmentJobStatus.CANCELLED
                        job.execution_token_hash = None
                        job.lease_expires_at = None
                        job.completed_at = now
                        job.updated_at = now
                        await uow.save_job(job)
                for object_key in (
                    attachment.staging_object_key,
                    attachment.quarantine_object_key,
                ):
                    if object_key is not None:
                        await _queue_cleanup(
                            uow,
                            self._ids,
                            self._policy,
                            attachment,
                            object_key,
                            CleanupPurpose.OWNER_DELETION,
                            now,
                        )
                cleanups = await uow.list_cleanups_for_attachment(owner_user_id, attachment.id)
                if not cleanups or all(
                    cleanup.status is CleanupStatus.COMPLETED for cleanup in cleanups
                ):
                    _redact_deleted_attachment(attachment, now)
                await uow.save_attachment(attachment)
                await uow.add_audit(
                    self._audit(
                        attachment,
                        context.actor_user_id,
                        AttachmentAuditAction.DELETION_REQUESTED,
                        context.request_id,
                        context.trace_id,
                        now,
                        (("status", attachment.status.value),),
                    )
                )
                await uow.commit()
        return _view(attachment)

    async def _admission_rejection(
        self, attachment: AttachmentRecord
    ) -> SafeAttachmentError | None:
        if attachment.staging_object_key is None or attachment.media_type is None:
            return SafeAttachmentError.UPLOAD_MISSING
        try:
            metadata = await self._storage.head(attachment.staging_object_key)
        except AttachmentObjectMissing:
            return SafeAttachmentError.UPLOAD_MISSING
        except Exception as exc:
            raise AttachmentStorageUnavailable from exc
        if metadata.size_bytes != attachment.expected_size:
            return SafeAttachmentError.UPLOAD_SIZE_MISMATCH
        if metadata.media_type != attachment.media_type.value:
            return SafeAttachmentError.UPLOAD_MEDIA_TYPE_MISMATCH
        try:
            prefix = await self._storage.read_prefix(attachment.staging_object_key, 1_024)
        except AttachmentObjectMissing:
            return SafeAttachmentError.UPLOAD_MISSING
        except Exception as exc:
            raise AttachmentStorageUnavailable from exc
        return _signature_error(prefix, attachment.media_type)

    async def _reject_admission(
        self,
        uow: AttachmentUnitOfWork,
        attachment: AttachmentRecord,
        code: SafeAttachmentError,
        context: AttachmentRequestContext,
        now: datetime,
    ) -> None:
        attachment.status = AttachmentStatus.REJECTED
        attachment.safe_error_code = code
        attachment.updated_at = now
        attachment.version += 1
        if attachment.staging_object_key is not None:
            await _queue_cleanup(
                uow,
                self._ids,
                self._policy,
                attachment,
                attachment.staging_object_key,
                CleanupPurpose.REJECTED_STAGING,
                now,
            )
        await uow.save_attachment(attachment)
        await uow.add_audit(
            self._audit(
                attachment,
                context.actor_user_id,
                AttachmentAuditAction.ADMISSION_REJECTED,
                context.request_id,
                context.trace_id,
                now,
                (("status", attachment.status.value), ("safe_error_code", code.value)),
            )
        )

    async def _replay(
        self,
        uow: AttachmentUnitOfWork,
        owner_user_id: UUID,
        idempotency_key: str,
        request_hash: bytes,
    ) -> FinalizedAttachment | None:
        receipt = await uow.get_finalization_receipt(owner_user_id, idempotency_key)
        if receipt is None:
            return None
        if receipt.request_hash != request_hash:
            raise AttachmentIdempotencyConflict
        return FinalizedAttachment(
            receipt.attachment_id,
            receipt.job_id,
            AttachmentStatus.QUARANTINED,
            AttachmentJobStatus.QUEUED,
        )

    async def _recover_finalization(
        self, owner_user_id: UUID, idempotency_key: str, request_hash: bytes
    ) -> FinalizedAttachment | None:
        try:
            async with self._uow() as uow:
                return await self._replay(uow, owner_user_id, idempotency_key, request_hash)
        except AttachmentIdempotencyConflict:
            raise
        except Exception:
            # An unknown commit result must not trigger destructive compensation.
            raise

    def _private_object_keys(self) -> tuple[str, str]:
        staging_token = self._tokens.token_urlsafe(32)
        quarantine_token = self._tokens.token_urlsafe(32)
        if (
            not _RANDOM_KEY_TOKEN.fullmatch(staging_token)
            or not _RANDOM_KEY_TOKEN.fullmatch(quarantine_token)
            or staging_token == quarantine_token
        ):
            raise RuntimeError("attachment object-key generator violated randomness contract")
        return (
            f"career-record/attachments/staging/{staging_token}.bin",
            f"career-record/attachments/quarantine/{quarantine_token}.bin",
        )

    def _outbox(
        self, job: AttachmentProcessingJob, now: datetime, *, generation: int
    ) -> AttachmentOutboxMessage:
        return AttachmentOutboxMessage(
            id=self._ids.new(),
            owner_user_id=job.owner_user_id,
            job_id=job.id,
            task_name=PROCESS_EVIDENCE_ATTACHMENT_TASK,
            trace_id=job.trace_id,
            generation=generation,
            created_at=now,
            next_attempt_at=now,
            attempts=0,
            max_attempts=self._policy.max_outbox_attempts,
        )

    def _audit(
        self,
        attachment: AttachmentRecord,
        actor_user_id: UUID | None,
        action: AttachmentAuditAction,
        request_id: str,
        trace_id: str,
        now: datetime,
        details: tuple[tuple[str, str], ...],
    ) -> AttachmentAuditEvent:
        return AttachmentAuditEvent(
            self._ids.new(),
            attachment.owner_user_id,
            actor_user_id,
            action,
            attachment.id,
            request_id,
            trace_id,
            details,
            now,
        )


class AttachmentProcessor:
    """Restricted-worker use case with durable leases and commit fencing."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        clock: Clock,
        storage: AttachmentObjectStorage,
        scanner: AttachmentMalwareScanner,
        extractor: AttachmentExtractor,
        limits: AttachmentLimits,
        policy: AttachmentPolicy | None = None,
        ids: IdentifierGenerator | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._storage = storage
        self._scanner = scanner
        self._extractor = extractor
        self._limits = limits
        self._policy = policy or AttachmentPolicy()
        self._ids = ids or _UuidGenerator()
        self._limits.temp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._limits.temp_root.is_symlink():
            raise ValueError("attachment temporary root must not be a symbolic link")

    async def process_job(self, job_id: UUID, execution_token: str) -> AttachmentProcessingOutcome:
        lease = await self.claim_job(job_id, execution_token)
        if lease is None:
            return await self._current_outcome(job_id)
        return await self.process_claimed_job(lease)

    async def claim_job(self, job_id: UUID, execution_token: str) -> AttachmentJobLease | None:
        token_hash = _execution_token_hash(execution_token)
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id, for_update=True)
            if job is None:
                raise AttachmentNotFound
            if job.terminal:
                return None
            if (
                job.status is AttachmentJobStatus.RUNNING
                and job.lease_expires_at is not None
                and job.lease_expires_at > now
            ):
                return None
            if (
                job.status is AttachmentJobStatus.RETRY_WAIT
                and job.next_attempt_at is not None
                and job.next_attempt_at > now
            ):
                return None
            attachment = await uow.get_attachment_system(job.attachment_id, for_update=True)
            if attachment is None or attachment.owner_user_id != job.owner_user_id:
                raise AttachmentNotFound
            if attachment.status in {AttachmentStatus.DELETING, AttachmentStatus.DELETED}:
                job.status = AttachmentJobStatus.CANCELLED
                job.completed_at = now
                job.updated_at = now
                job.execution_token_hash = None
                job.lease_expires_at = None
                await uow.save_job(job)
                await uow.commit()
                return None
            if job.attempts >= job.max_attempts:
                await self._dead_letter_locked(uow, job, attachment, now)
                await uow.commit()
                return None
            job.status = AttachmentJobStatus.RUNNING
            job.stage = AttachmentJobStage.MALWARE_SCAN
            job.attempts += 1
            job.fence += 1
            job.execution_token_hash = token_hash
            job.lease_expires_at = now + timedelta(seconds=self._policy.execution_lease_seconds)
            job.next_attempt_at = None
            job.safe_error_code = None
            job.updated_at = now
            attachment.status = AttachmentStatus.PROCESSING
            attachment.safe_error_code = None
            attachment.updated_at = now
            attachment.version += 1
            await uow.save_job(job)
            await uow.save_attachment(attachment)
            await uow.commit()
        return AttachmentJobLease(
            job.id,
            job.attachment_id,
            job.fence,
            token_hash,
            job.lease_expires_at,
        )

    async def process_claimed_job(self, lease: AttachmentJobLease) -> AttachmentProcessingOutcome:
        try:
            attachment = await self._attachment_for_lease(lease)
            if (
                attachment.quarantine_object_key is None
                or attachment.media_type is None
                or attachment.expected_size is None
            ):
                raise UnsafeAttachment(SafeAttachmentError.QUARANTINE_OBJECT_MISSING)
            with tempfile.TemporaryDirectory(
                prefix=f"rezumi-attachment-{uuid4().hex}-", dir=self._limits.temp_root
            ) as directory:
                path = Path(directory) / "source.bin"
                async with asyncio.timeout(self._limits.processing_timeout_seconds):
                    try:
                        downloaded = await self._storage.download(
                            attachment.quarantine_object_key,
                            path,
                            self._limits.max_upload_bytes,
                        )
                    except AttachmentObjectMissing:
                        raise
                    except Exception as exc:
                        raise _RetryableProcessing(SafeAttachmentError.STORAGE_UNAVAILABLE) from exc
                    self._validate_download(downloaded, attachment, path)
                    try:
                        scan = await self._scanner.scan(path)
                    except Exception as exc:
                        raise _RetryableProcessing(
                            SafeAttachmentError.MALWARE_SCANNER_UNAVAILABLE
                        ) from exc
                    if scan.verdict is ScanVerdict.INFECTED:
                        raise UnsafeAttachment(SafeAttachmentError.MALWARE_DETECTED)
                    if scan.verdict is not ScanVerdict.CLEAN:
                        raise _RetryableProcessing(SafeAttachmentError.MALWARE_SCANNER_UNAVAILABLE)
                    await self._advance_stage(lease, AttachmentJobStage.EXTRACTION)
                    try:
                        extraction = await self._extractor.extract(
                            path, attachment.media_type, self._limits
                        )
                    except UnsafeAttachment:
                        raise
                    except Exception as exc:
                        raise _RetryableProcessing(SafeAttachmentError.EXTRACTION_FAILED) from exc
                    _validate_extraction(extraction, attachment.media_type, self._limits)
            return await self._complete(lease, downloaded.sha256_digest, extraction)
        except AttachmentFenced:
            return AttachmentProcessingOutcome(
                lease.job_id,
                AttachmentJobStatus.RUNNING,
                SafeAttachmentError.EXECUTION_FENCED,
                True,
            )
        except UnsafeAttachment as exc:
            return await self._reject(lease, exc.code)
        except AttachmentObjectMissing:
            return await self._reject(lease, SafeAttachmentError.QUARANTINE_OBJECT_MISSING)
        except _RetryableProcessing as exc:
            return await self._retry(lease, exc.code)
        except AttachmentStorageUnavailable:
            return await self._retry(lease, SafeAttachmentError.STORAGE_UNAVAILABLE)
        except TimeoutError:
            return await self._retry(lease, SafeAttachmentError.PROCESSING_TIMEOUT)
        except Exception:
            return await self._retry(lease, SafeAttachmentError.EXTRACTION_FAILED)

    async def _attachment_for_lease(self, lease: AttachmentJobLease) -> AttachmentRecord:
        async with self._uow() as uow:
            job = await uow.get_job_system(lease.job_id)
            attachment = await uow.get_attachment_system(lease.attachment_id)
        if job is None or attachment is None or attachment.owner_user_id != job.owner_user_id:
            raise AttachmentNotFound
        _ensure_lease(job, lease, self._clock.now())
        if attachment.status is not AttachmentStatus.PROCESSING:
            raise AttachmentFenced
        return attachment

    def _validate_download(
        self,
        downloaded: DownloadedObject,
        attachment: AttachmentRecord,
        expected_path: Path,
    ) -> None:
        if (
            attachment.expected_size is None
            or attachment.media_type is None
            or downloaded.size_bytes != attachment.expected_size
            or len(downloaded.sha256_digest) != 32
            or downloaded.path != expected_path.resolve()
            or not downloaded.path.is_file()
            or downloaded.path.stat().st_size != downloaded.size_bytes
        ):
            raise UnsafeAttachment(SafeAttachmentError.QUARANTINE_INTEGRITY_MISMATCH)
        prefix = downloaded.path.read_bytes()[:1_024]
        if _signature_error(prefix, attachment.media_type) is not None:
            raise UnsafeAttachment(SafeAttachmentError.QUARANTINE_INTEGRITY_MISMATCH)

    async def _advance_stage(self, lease: AttachmentJobLease, stage: AttachmentJobStage) -> None:
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(lease.job_id, for_update=True)
            if job is None:
                raise AttachmentNotFound
            _ensure_lease(job, lease, now)
            job.stage = stage
            job.updated_at = now
            await uow.save_job(job)
            await uow.commit()

    async def _complete(
        self,
        lease: AttachmentJobLease,
        digest: bytes,
        extraction: AttachmentExtractionSummary,
    ) -> AttachmentProcessingOutcome:
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(lease.job_id, for_update=True)
            attachment = await uow.get_attachment_system(lease.attachment_id, for_update=True)
            if job is None or attachment is None:
                raise AttachmentNotFound
            _ensure_lease(job, lease, now)
            if attachment.status is not AttachmentStatus.PROCESSING:
                raise AttachmentFenced
            attachment.status = AttachmentStatus.CLEAN
            attachment.safe_error_code = None
            attachment.content_sha256 = digest
            attachment.extraction = extraction
            attachment.updated_at = now
            attachment.version += 1
            job.status = AttachmentJobStatus.SUCCEEDED
            job.stage = AttachmentJobStage.COMPLETE
            job.safe_error_code = None
            job.completed_at = now
            job.updated_at = now
            job.execution_token_hash = None
            job.lease_expires_at = None
            await uow.save_attachment(attachment)
            await uow.save_job(job)
            await uow.add_audit(
                self._audit(
                    attachment,
                    AttachmentAuditAction.CLEAN,
                    job,
                    now,
                    (("status", attachment.status.value), ("job_status", job.status.value)),
                )
            )
            await uow.commit()
        return _job_outcome(job)

    async def _retry(
        self, lease: AttachmentJobLease, code: SafeAttachmentError
    ) -> AttachmentProcessingOutcome:
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(lease.job_id, for_update=True)
            attachment = await uow.get_attachment_system(lease.attachment_id, for_update=True)
            if job is None or attachment is None:
                raise AttachmentNotFound
            try:
                _ensure_lease(job, lease, now)
            except AttachmentFenced:
                return AttachmentProcessingOutcome(
                    job.id,
                    job.status,
                    SafeAttachmentError.EXECUTION_FENCED,
                    not job.terminal,
                )
            if job.attempts >= job.max_attempts:
                await self._dead_letter_locked(uow, job, attachment, now)
            else:
                delay = min(900, 5 * (2 ** max(0, job.attempts - 1)))
                retry_at = now + timedelta(seconds=delay)
                job.status = AttachmentJobStatus.RETRY_WAIT
                job.safe_error_code = code
                job.next_attempt_at = retry_at
                job.execution_token_hash = None
                job.lease_expires_at = None
                job.updated_at = now
                attachment.status = AttachmentStatus.QUARANTINED
                attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
                attachment.updated_at = now
                attachment.version += 1
                await uow.save_job(job)
                await uow.save_attachment(attachment)
                await uow.add_outbox(self._outbox(job, now, retry_at))
                await uow.add_audit(
                    self._audit(
                        attachment,
                        AttachmentAuditAction.PROCESSING_RETRY,
                        job,
                        now,
                        (
                            ("status", attachment.status.value),
                            ("job_status", job.status.value),
                            ("safe_error_code", code.value),
                        ),
                    )
                )
            await uow.commit()
        return _job_outcome(job)

    async def _reject(
        self, lease: AttachmentJobLease, code: SafeAttachmentError
    ) -> AttachmentProcessingOutcome:
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(lease.job_id, for_update=True)
            attachment = await uow.get_attachment_system(lease.attachment_id, for_update=True)
            if job is None or attachment is None:
                raise AttachmentNotFound
            try:
                _ensure_lease(job, lease, now)
            except AttachmentFenced:
                return AttachmentProcessingOutcome(
                    job.id,
                    job.status,
                    SafeAttachmentError.EXECUTION_FENCED,
                    not job.terminal,
                )
            job.status = AttachmentJobStatus.REJECTED
            job.safe_error_code = code
            job.completed_at = now
            job.updated_at = now
            job.execution_token_hash = None
            job.lease_expires_at = None
            attachment.status = AttachmentStatus.REJECTED
            attachment.safe_error_code = code
            attachment.updated_at = now
            attachment.version += 1
            await uow.save_job(job)
            await uow.save_attachment(attachment)
            if attachment.quarantine_object_key is not None:
                await _queue_cleanup(
                    uow,
                    self._ids,
                    self._policy,
                    attachment,
                    attachment.quarantine_object_key,
                    CleanupPurpose.REJECTED_QUARANTINE,
                    now,
                )
            await uow.add_audit(
                self._audit(
                    attachment,
                    AttachmentAuditAction.PROCESSING_REJECTED,
                    job,
                    now,
                    (
                        ("status", attachment.status.value),
                        ("job_status", job.status.value),
                        ("safe_error_code", code.value),
                    ),
                )
            )
            await uow.commit()
        return _job_outcome(job)

    async def _dead_letter_locked(
        self,
        uow: AttachmentUnitOfWork,
        job: AttachmentProcessingJob,
        attachment: AttachmentRecord,
        now: datetime,
    ) -> None:
        job.status = AttachmentJobStatus.DEAD_LETTERED
        job.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        job.completed_at = now
        job.dead_lettered_at = now
        job.updated_at = now
        job.execution_token_hash = None
        job.lease_expires_at = None
        attachment.status = AttachmentStatus.REJECTED
        attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        attachment.updated_at = now
        attachment.version += 1
        await uow.save_job(job)
        await uow.save_attachment(attachment)
        if attachment.quarantine_object_key is not None:
            await _queue_cleanup(
                uow,
                self._ids,
                self._policy,
                attachment,
                attachment.quarantine_object_key,
                CleanupPurpose.REJECTED_QUARANTINE,
                now,
            )
        await uow.add_audit(
            self._audit(
                attachment,
                AttachmentAuditAction.PROCESSING_DEAD_LETTERED,
                job,
                now,
                (
                    ("status", attachment.status.value),
                    ("job_status", job.status.value),
                    (
                        "safe_error_code",
                        SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED.value,
                    ),
                ),
            )
        )

    async def _current_outcome(self, job_id: UUID) -> AttachmentProcessingOutcome:
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id)
        if job is None:
            raise AttachmentNotFound
        return _job_outcome(job)

    def _outbox(
        self, job: AttachmentProcessingJob, now: datetime, retry_at: datetime
    ) -> AttachmentOutboxMessage:
        return AttachmentOutboxMessage(
            self._ids.new(),
            job.owner_user_id,
            job.id,
            PROCESS_EVIDENCE_ATTACHMENT_TASK,
            job.trace_id,
            job.attempts,
            now,
            retry_at,
            0,
            self._policy.max_outbox_attempts,
        )

    def _audit(
        self,
        attachment: AttachmentRecord,
        action: AttachmentAuditAction,
        job: AttachmentProcessingJob,
        now: datetime,
        details: tuple[tuple[str, str], ...],
    ) -> AttachmentAuditEvent:
        return AttachmentAuditEvent(
            self._ids.new(),
            attachment.owner_user_id,
            None,
            action,
            attachment.id,
            "attachment-worker",
            job.trace_id,
            details,
            now,
        )


class AttachmentOutboxDispatcher:
    """Publishes identifier-only jobs and durably bounds broker failures."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        publisher: AttachmentJobPublisher,
        clock: Clock,
        ids: IdentifierGenerator | None = None,
        policy: AttachmentPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._publisher = publisher
        self._clock = clock
        self._ids = ids or _UuidGenerator()
        self._policy = policy or AttachmentPolicy()

    async def dispatch_pending(self, limit: int = 100) -> OutboxDispatchResult:
        if not 1 <= limit <= 500:
            raise ValueError("attachment outbox limit must be between 1 and 500")
        now = self._clock.now()
        published = failed = dead_lettered = 0
        async with self._uow() as uow:
            for message in await uow.list_pending_outbox(now, limit):
                try:
                    await self._publisher.publish(
                        message.task_name, message.job_id, message.trace_id
                    )
                except Exception:
                    message.attempts += 1
                    message.last_error_code = SafeAttachmentError.TASK_PUBLISH_FAILED
                    if message.attempts >= message.max_attempts:
                        message.dead_lettered_at = now
                        job = await uow.get_job_system(message.job_id, for_update=True)
                        if job is not None and not job.terminal:
                            attachment = await uow.get_attachment_system(
                                job.attachment_id, for_update=True
                            )
                            if attachment is not None:
                                await self._dead_letter_publish(uow, job, attachment, now)
                        dead_lettered += 1
                    else:
                        delay = min(900, 5 * (2 ** min(message.attempts - 1, 8)))
                        message.next_attempt_at = now + timedelta(seconds=delay)
                    failed += 1
                else:
                    message.attempts += 1
                    message.published_at = now
                    message.last_error_code = None
                    published += 1
                await uow.save_outbox(message)
            await uow.commit()
        return OutboxDispatchResult(published, failed, dead_lettered)

    async def _dead_letter_publish(
        self,
        uow: AttachmentUnitOfWork,
        job: AttachmentProcessingJob,
        attachment: AttachmentRecord,
        now: datetime,
    ) -> None:
        job.status = AttachmentJobStatus.DEAD_LETTERED
        job.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        job.dead_lettered_at = now
        job.completed_at = now
        job.updated_at = now
        attachment.status = AttachmentStatus.REJECTED
        attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        attachment.updated_at = now
        attachment.version += 1
        await uow.save_job(job)
        await uow.save_attachment(attachment)
        if attachment.quarantine_object_key is not None:
            await _queue_cleanup(
                uow,
                self._ids,
                self._policy,
                attachment,
                attachment.quarantine_object_key,
                CleanupPurpose.REJECTED_QUARANTINE,
                now,
            )
        await uow.add_audit(
            AttachmentAuditEvent(
                self._ids.new(),
                attachment.owner_user_id,
                None,
                AttachmentAuditAction.PROCESSING_DEAD_LETTERED,
                attachment.id,
                "attachment-outbox",
                job.trace_id,
                (
                    ("status", attachment.status.value),
                    ("job_status", job.status.value),
                    (
                        "safe_error_code",
                        SafeAttachmentError.TASK_PUBLISH_FAILED.value,
                    ),
                ),
                now,
            )
        )


class AttachmentFailureRecorder:
    """Database-only fallback when worker provider composition cannot complete."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        clock: Clock,
        ids: IdentifierGenerator | None = None,
        policy: AttachmentPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = ids or _UuidGenerator()
        self._policy = policy or AttachmentPolicy()

    async def record_failure(
        self,
        job_id: UUID,
        execution_token: str,
        code: SafeAttachmentError,
        *,
        exhausted: bool,
    ) -> AttachmentProcessingOutcome:
        token_hash = _execution_token_hash(execution_token)
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id, for_update=True)
            if job is None:
                raise AttachmentNotFound
            if job.terminal:
                return _job_outcome(job)
            attachment = await uow.get_attachment_system(job.attachment_id, for_update=True)
            if attachment is None or attachment.owner_user_id != job.owner_user_id:
                raise AttachmentNotFound
            if job.status is AttachmentJobStatus.RUNNING and job.execution_token_hash != token_hash:
                return AttachmentProcessingOutcome(
                    job.id,
                    job.status,
                    SafeAttachmentError.EXECUTION_FENCED,
                    True,
                )
            if job.status is not AttachmentJobStatus.RUNNING:
                job.attempts += 1
            job.execution_token_hash = None
            job.lease_expires_at = None
            job.safe_error_code = code
            job.updated_at = now
            if exhausted or job.attempts >= job.max_attempts:
                job.status = AttachmentJobStatus.DEAD_LETTERED
                job.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
                job.dead_lettered_at = now
                job.completed_at = now
                attachment.status = AttachmentStatus.REJECTED
                attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
                action = AttachmentAuditAction.PROCESSING_DEAD_LETTERED
                if attachment.quarantine_object_key is not None:
                    await _queue_cleanup(
                        uow,
                        self._ids,
                        self._policy,
                        attachment,
                        attachment.quarantine_object_key,
                        CleanupPurpose.REJECTED_QUARANTINE,
                        now,
                    )
            else:
                delay = min(900, 5 * (2 ** max(0, job.attempts - 1)))
                retry_at = now + timedelta(seconds=delay)
                job.status = AttachmentJobStatus.RETRY_WAIT
                job.next_attempt_at = retry_at
                attachment.status = AttachmentStatus.QUARANTINED
                attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
                action = AttachmentAuditAction.PROCESSING_RETRY
                await uow.add_outbox(
                    AttachmentOutboxMessage(
                        self._ids.new(),
                        job.owner_user_id,
                        job.id,
                        PROCESS_EVIDENCE_ATTACHMENT_TASK,
                        job.trace_id,
                        job.attempts,
                        now,
                        retry_at,
                        0,
                        self._policy.max_outbox_attempts,
                    )
                )
            attachment.updated_at = now
            attachment.version += 1
            await uow.save_job(job)
            await uow.save_attachment(attachment)
            await uow.add_audit(
                AttachmentAuditEvent(
                    self._ids.new(),
                    attachment.owner_user_id,
                    None,
                    action,
                    attachment.id,
                    "attachment-worker-runtime",
                    job.trace_id,
                    (
                        ("status", attachment.status.value),
                        ("job_status", job.status.value),
                        ("safe_error_code", code.value),
                    ),
                    now,
                )
            )
            await uow.commit()
        return _job_outcome(job)


class AttachmentJobReconciler:
    """Recover lost deliveries and expired leases through database-only state."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        clock: Clock,
        stale_after_seconds: int = 300,
        ids: IdentifierGenerator | None = None,
        policy: AttachmentPolicy | None = None,
    ) -> None:
        if stale_after_seconds < 1:
            raise ValueError("attachment reconciliation staleness must be positive")
        self._uow = unit_of_work
        self._clock = clock
        self._stale_after_seconds = stale_after_seconds
        self._ids = ids or _UuidGenerator()
        self._policy = policy or AttachmentPolicy()

    async def reconcile_stale(self, limit: int = 100) -> AttachmentReconciliationResult:
        if not 1 <= limit <= 500:
            raise ValueError("attachment reconciliation limit must be between 1 and 500")
        now = self._clock.now()
        stale_before = now - timedelta(seconds=self._stale_after_seconds)
        requeued = dead_lettered = 0
        async with self._uow() as uow:
            jobs = await uow.list_reconcilable_jobs(now, stale_before, limit)
            for job in jobs:
                attachment = await uow.get_attachment_system(job.attachment_id, for_update=True)
                if attachment is None or attachment.owner_user_id != job.owner_user_id:
                    continue
                if attachment.status in {
                    AttachmentStatus.DELETING,
                    AttachmentStatus.DELETED,
                }:
                    job.status = AttachmentJobStatus.CANCELLED
                    job.execution_token_hash = None
                    job.lease_expires_at = None
                    job.completed_at = now
                    job.updated_at = now
                    await uow.save_job(job)
                    continue
                if job.attempts >= job.max_attempts:
                    await self._dead_letter(uow, job, attachment, now)
                    dead_lettered += 1
                    continue
                generation = await uow.next_outbox_generation(job.owner_user_id, job.id)
                job.status = AttachmentJobStatus.QUEUED
                job.stage = AttachmentJobStage.QUEUED
                job.execution_token_hash = None
                job.lease_expires_at = None
                job.next_attempt_at = None
                job.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
                job.updated_at = now
                attachment.status = AttachmentStatus.QUARANTINED
                attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
                attachment.updated_at = now
                attachment.version += 1
                await uow.save_job(job)
                await uow.save_attachment(attachment)
                await uow.add_outbox(
                    AttachmentOutboxMessage(
                        self._ids.new(),
                        job.owner_user_id,
                        job.id,
                        PROCESS_EVIDENCE_ATTACHMENT_TASK,
                        job.trace_id,
                        generation,
                        now,
                        now,
                        0,
                        self._policy.max_outbox_attempts,
                    )
                )
                await uow.add_audit(
                    AttachmentAuditEvent(
                        self._ids.new(),
                        attachment.owner_user_id,
                        None,
                        AttachmentAuditAction.PROCESSING_RETRY,
                        attachment.id,
                        "attachment-reconciler",
                        job.trace_id,
                        (
                            ("status", attachment.status.value),
                            ("job_status", job.status.value),
                            (
                                "safe_error_code",
                                SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY.value,
                            ),
                        ),
                        now,
                    )
                )
                requeued += 1
            await uow.commit()
        return AttachmentReconciliationResult(requeued, dead_lettered)

    async def _dead_letter(
        self,
        uow: AttachmentUnitOfWork,
        job: AttachmentProcessingJob,
        attachment: AttachmentRecord,
        now: datetime,
    ) -> None:
        job.status = AttachmentJobStatus.DEAD_LETTERED
        job.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        job.execution_token_hash = None
        job.lease_expires_at = None
        job.completed_at = now
        job.dead_lettered_at = now
        job.updated_at = now
        attachment.status = AttachmentStatus.REJECTED
        attachment.safe_error_code = SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
        attachment.updated_at = now
        attachment.version += 1
        await uow.save_job(job)
        await uow.save_attachment(attachment)
        if attachment.quarantine_object_key is not None:
            await _queue_cleanup(
                uow,
                self._ids,
                self._policy,
                attachment,
                attachment.quarantine_object_key,
                CleanupPurpose.REJECTED_QUARANTINE,
                now,
            )
        await uow.add_audit(
            AttachmentAuditEvent(
                self._ids.new(),
                attachment.owner_user_id,
                None,
                AttachmentAuditAction.PROCESSING_DEAD_LETTERED,
                attachment.id,
                "attachment-reconciler",
                job.trace_id,
                (
                    ("status", attachment.status.value),
                    ("job_status", job.status.value),
                    (
                        "safe_error_code",
                        SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED.value,
                    ),
                ),
                now,
            )
        )


class AttachmentCleanupProcessor:
    """Idempotent durable object cleanup; deletion redacts only after all objects are gone."""

    def __init__(
        self,
        *,
        unit_of_work: AttachmentUnitOfWorkFactory,
        storage: AttachmentObjectStorage,
        clock: Clock,
        ids: IdentifierGenerator | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._storage = storage
        self._clock = clock
        self._ids = ids or _UuidGenerator()

    async def process_due(self, limit: int = 100) -> CleanupBatchResult:
        if not 1 <= limit <= 500:
            raise ValueError("attachment cleanup limit must be between 1 and 500")
        async with self._uow() as uow:
            cleanup_ids = tuple(
                item.id for item in await uow.list_due_cleanups(self._clock.now(), limit)
            )
        completed = failed = dead_lettered = 0
        for cleanup_id in cleanup_ids:
            outcome = await self.process(cleanup_id)
            if outcome.status is CleanupStatus.COMPLETED:
                completed += 1
            elif outcome.status is CleanupStatus.DEAD_LETTERED:
                dead_lettered += 1
                failed += 1
            else:
                failed += 1
        return CleanupBatchResult(completed, failed, dead_lettered)

    async def process(self, cleanup_id: UUID) -> CleanupOutcome:
        async with self._uow() as uow:
            cleanup = await uow.get_cleanup_system(cleanup_id)
        if cleanup is None:
            raise AttachmentNotFound
        if cleanup.terminal:
            return CleanupOutcome(cleanup.id, cleanup.status, cleanup.safe_error_code)
        now = self._clock.now()
        try:
            await self._storage.delete(cleanup.object_key)
        except AttachmentObjectMissing:
            pass
        except Exception:
            async with self._uow() as uow:
                current = await uow.get_cleanup_system(cleanup.id, for_update=True)
                if current is None:
                    raise AttachmentNotFound from None
                if current.terminal:
                    return CleanupOutcome(current.id, current.status, current.safe_error_code)
                current.attempts += 1
                current.safe_error_code = SafeAttachmentError.OBJECT_CLEANUP_FAILED
                current.updated_at = now
                if current.attempts >= current.max_attempts:
                    current.status = CleanupStatus.DEAD_LETTERED
                    current.dead_lettered_at = now
                    await uow.add_audit(
                        AttachmentAuditEvent(
                            self._ids.new(),
                            current.owner_user_id,
                            None,
                            AttachmentAuditAction.CLEANUP_DEAD_LETTERED,
                            current.attachment_id,
                            "attachment-cleanup",
                            "attachment-cleanup",
                            (
                                ("status", current.status.value),
                                (
                                    "safe_error_code",
                                    SafeAttachmentError.OBJECT_CLEANUP_FAILED.value,
                                ),
                            ),
                            now,
                        )
                    )
                else:
                    current.status = CleanupStatus.RETRY_WAIT
                    delay = min(3_600, 30 * (2 ** min(current.attempts - 1, 8)))
                    current.next_attempt_at = now + timedelta(seconds=delay)
                await uow.save_cleanup(current)
                await uow.commit()
            return CleanupOutcome(current.id, current.status, current.safe_error_code)
        async with self._uow() as uow:
            current = await uow.get_cleanup_system(cleanup.id, for_update=True)
            if current is None:
                raise AttachmentNotFound
            if current.terminal:
                return CleanupOutcome(current.id, current.status, current.safe_error_code)
            current.attempts += 1
            current.status = CleanupStatus.COMPLETED
            current.safe_error_code = None
            current.completed_at = now
            current.updated_at = now
            attachment = await uow.get_attachment_system(current.attachment_id, for_update=True)
            if attachment is not None and attachment.owner_user_id == current.owner_user_id:
                if attachment.staging_object_key == current.object_key:
                    attachment.staging_object_key = None
                if attachment.quarantine_object_key == current.object_key:
                    attachment.quarantine_object_key = None
                attachment.updated_at = now
                attachment.version += 1
                await uow.save_cleanup(current)
                cleanups = await uow.list_cleanups_for_attachment(
                    attachment.owner_user_id, attachment.id
                )
                if attachment.status is AttachmentStatus.DELETING and all(
                    item.status is CleanupStatus.COMPLETED for item in cleanups
                ):
                    _redact_deleted_attachment(attachment, now)
                    await uow.add_audit(
                        AttachmentAuditEvent(
                            self._ids.new(),
                            attachment.owner_user_id,
                            None,
                            AttachmentAuditAction.DELETED,
                            attachment.id,
                            "attachment-cleanup",
                            "attachment-cleanup",
                            (("status", attachment.status.value),),
                            now,
                        )
                    )
                await uow.save_attachment(attachment)
            await uow.save_cleanup(current)
            await uow.commit()
        return CleanupOutcome(current.id, current.status, current.safe_error_code)


async def _queue_cleanup(
    uow: AttachmentUnitOfWork,
    ids: IdentifierGenerator,
    policy: AttachmentPolicy,
    attachment: AttachmentRecord,
    object_key: str,
    purpose: CleanupPurpose,
    now: datetime,
) -> None:
    if await uow.has_cleanup_for_object(attachment.owner_user_id, attachment.id, object_key):
        return
    await uow.add_cleanup(
        AttachmentObjectCleanup(
            ids.new(),
            attachment.owner_user_id,
            attachment.id,
            object_key,
            purpose,
            CleanupStatus.PENDING,
            0,
            policy.max_cleanup_attempts,
            now,
            now,
            now,
        )
    )


def _authorize(owner_user_id: UUID, context: AttachmentRequestContext) -> None:
    if owner_user_id != context.actor_user_id:
        raise AttachmentNotFound


def _media_type(raw: str) -> AttachmentMediaType:
    try:
        return AttachmentMediaType(raw)
    except ValueError as exc:
        raise AttachmentRejected(SafeAttachmentError.UPLOAD_TYPE_UNSUPPORTED) from exc


def _filename(raw: str, media_type: AttachmentMediaType) -> str:
    value = raw.strip()
    expected_suffix = ".pdf" if media_type is AttachmentMediaType.PDF else ".docx"
    if (
        value != raw
        or not 1 <= len(value) <= 255
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
        or not value.lower().endswith(expected_suffix)
    ):
        raise AttachmentRejected(SafeAttachmentError.UPLOAD_FILENAME_INVALID)
    return value


def _validate_idempotency_key(value: str) -> None:
    if _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise ValueError("attachment idempotency key must be 8 to 128 safe characters")


def _execution_token_hash(value: str) -> bytes:
    if _EXECUTION_TOKEN.fullmatch(value) is None:
        raise ValueError("attachment execution token must be 8 to 128 safe characters")
    return sha256(value.encode("ascii")).digest()


def _finalize_request_hash(attachment_id: UUID) -> bytes:
    return sha256(b"attachment-finalize\x00" + attachment_id.bytes).digest()


def _signature_error(prefix: bytes, media_type: AttachmentMediaType) -> SafeAttachmentError | None:
    if media_type is AttachmentMediaType.PDF and not prefix.startswith(b"%PDF-"):
        return SafeAttachmentError.UPLOAD_SIGNATURE_MISMATCH
    if media_type is AttachmentMediaType.DOCX and not prefix.startswith(b"PK\x03\x04"):
        return SafeAttachmentError.UPLOAD_SIGNATURE_MISMATCH
    return None


def _validate_presigned_put(
    target: PresignedOperation,
    media_type: AttachmentMediaType,
    expected_size: int,
    expires_at: datetime,
) -> None:
    headers = {key.lower(): value for key, value in target.required_headers}
    if (
        target.method != "PUT"
        or target.expires_at != expires_at
        or headers.get("content-type") != media_type.value
        or headers.get("content-length") != str(expected_size)
        or not target.url
    ):
        raise RuntimeError("storage provider returned an unbound attachment upload")


def _validate_presigned_get(target: PresignedOperation, expires_at: datetime) -> None:
    if target.method != "GET" or target.expires_at != expires_at or not target.url:
        raise RuntimeError("storage provider returned an invalid attachment download")


def _validate_extraction(
    result: AttachmentExtractionSummary,
    media_type: AttachmentMediaType,
    limits: AttachmentLimits,
) -> None:
    if not result.format_valid:
        raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
    if not 1 <= result.page_count <= limits.max_pdf_pages:
        raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
    if result.extracted_characters > limits.max_extracted_characters:
        raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
    if result.extracted_blocks > limits.max_extracted_blocks:
        raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
    if media_type is AttachmentMediaType.DOCX and (
        not 1 <= result.archive_entries <= limits.max_archive_entries
        or result.archive_uncompressed_bytes > limits.max_archive_uncompressed_bytes
        or result.max_archive_ratio > limits.max_archive_ratio
    ):
        raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)


def _ensure_lease(job: AttachmentProcessingJob, lease: AttachmentJobLease, now: datetime) -> None:
    if (
        job.status is not AttachmentJobStatus.RUNNING
        or job.id != lease.job_id
        or job.attachment_id != lease.attachment_id
        or job.fence != lease.fence
        or job.execution_token_hash != lease.execution_token_hash
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise AttachmentFenced


def _job_outcome(job: AttachmentProcessingJob) -> AttachmentProcessingOutcome:
    return AttachmentProcessingOutcome(
        job.id,
        job.status,
        job.safe_error_code,
        job.status
        in {
            AttachmentJobStatus.QUEUED,
            AttachmentJobStatus.RUNNING,
            AttachmentJobStatus.RETRY_WAIT,
        },
    )


def _view(attachment: AttachmentRecord) -> AttachmentView:
    return AttachmentView(
        attachment.id,
        attachment.evidence_id,
        attachment.display_filename,
        attachment.media_type,
        attachment.expected_size,
        attachment.status,
        attachment.safe_error_code,
        attachment.content_sha256,
        attachment.extraction.page_count if attachment.extraction is not None else None,
        attachment.version,
        attachment.created_at,
        attachment.updated_at,
    )


def _redact_deleted_attachment(attachment: AttachmentRecord, now: datetime) -> None:
    attachment.display_filename = None
    attachment.media_type = None
    attachment.expected_size = None
    attachment.staging_object_key = None
    attachment.quarantine_object_key = None
    attachment.content_sha256 = None
    attachment.extraction = None
    attachment.safe_error_code = None
    attachment.status = AttachmentStatus.DELETED
    attachment.deleted_at = now
    attachment.updated_at = now
    attachment.version += 1


def _bounded_identifier(value: str, field: str) -> None:
    if not 1 <= len(value) <= 128 or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field} must be 1 to 128 printable characters")
