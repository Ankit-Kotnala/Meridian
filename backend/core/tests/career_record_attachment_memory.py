"""In-memory Career Record attachment collaborators shared by focused tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import TracebackType
from uuid import UUID

from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentAuditEvent,
    AttachmentDownloadPurpose,
    AttachmentExtractionSummary,
    AttachmentFinalizationReceipt,
    AttachmentJobPublisher,
    AttachmentJobStatus,
    AttachmentLimits,
    AttachmentMediaType,
    AttachmentObjectCleanup,
    AttachmentObjectMissing,
    AttachmentObjectStorage,
    AttachmentOutboxMessage,
    AttachmentProcessingJob,
    AttachmentRecord,
    AttachmentStatus,
    AttachmentStorageUnavailable,
    AttachmentUnitOfWork,
    CleanupStatus,
    DownloadedObject,
    MalwareScanResult,
    ObjectMetadata,
    PresignedOperation,
    ScanVerdict,
)


@dataclass(slots=True)
class AttachmentMemoryState:
    evidence: set[tuple[UUID, UUID]] = field(default_factory=set)
    attachments: dict[UUID, AttachmentRecord] = field(default_factory=dict)
    receipts: dict[tuple[UUID, str], AttachmentFinalizationReceipt] = field(default_factory=dict)
    jobs: dict[UUID, AttachmentProcessingJob] = field(default_factory=dict)
    outbox: dict[UUID, AttachmentOutboxMessage] = field(default_factory=dict)
    cleanups: dict[UUID, AttachmentObjectCleanup] = field(default_factory=dict)
    audits: list[AttachmentAuditEvent] = field(default_factory=list)


class InMemoryAttachmentUnitOfWorkFactory:
    def __init__(self) -> None:
        self._state = AttachmentMemoryState()

    @property
    def state(self) -> AttachmentMemoryState:
        return self._state

    def add_evidence(self, owner_user_id: UUID, evidence_id: UUID) -> None:
        self._state.evidence.add((owner_user_id, evidence_id))

    def __call__(self) -> AttachmentUnitOfWork:
        return InMemoryAttachmentUnitOfWork(self)

    def replace_state(self, state: AttachmentMemoryState) -> None:
        self._state = deepcopy(state)


class InMemoryAttachmentUnitOfWork:
    def __init__(self, factory: InMemoryAttachmentUnitOfWorkFactory) -> None:
        self._factory = factory
        self._working = deepcopy(factory.state)

    async def __aenter__(self) -> InMemoryAttachmentUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def lock_admission(self, owner_user_id: UUID, evidence_id: UUID) -> None:
        del owner_user_id, evidence_id

    async def evidence_exists(self, owner_user_id: UUID, evidence_id: UUID) -> bool:
        return (owner_user_id, evidence_id) in self._working.evidence

    async def count_active_attachments(self, owner_user_id: UUID, evidence_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id
            and item.evidence_id == evidence_id
            and item.status not in {AttachmentStatus.REJECTED, AttachmentStatus.DELETED}
            for item in self._working.attachments.values()
        )

    async def add_attachment(self, attachment: AttachmentRecord) -> None:
        if attachment.id in self._working.attachments:
            raise RuntimeError("duplicate attachment")
        self._working.attachments[attachment.id] = attachment

    async def get_attachment(
        self, owner_user_id: UUID, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None:
        del for_update
        attachment = self._working.attachments.get(attachment_id)
        if attachment is None or attachment.owner_user_id != owner_user_id:
            return None
        return attachment

    async def get_attachment_system(
        self, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None:
        del for_update
        return self._working.attachments.get(attachment_id)

    async def save_attachment(self, attachment: AttachmentRecord) -> None:
        self._working.attachments[attachment.id] = attachment

    async def add_finalization_receipt(self, receipt: AttachmentFinalizationReceipt) -> None:
        key = (receipt.owner_user_id, receipt.idempotency_key)
        if key in self._working.receipts:
            raise RuntimeError("duplicate finalization receipt")
        self._working.receipts[key] = receipt

    async def get_finalization_receipt(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AttachmentFinalizationReceipt | None:
        return self._working.receipts.get((owner_user_id, idempotency_key))

    async def add_job(self, job: AttachmentProcessingJob) -> None:
        if job.id in self._working.jobs:
            raise RuntimeError("duplicate attachment job")
        self._working.jobs[job.id] = job

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> AttachmentProcessingJob | None:
        del for_update
        return self._working.jobs.get(job_id)

    async def list_jobs_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentProcessingJob]:
        return [
            item
            for item in self._working.jobs.values()
            if item.owner_user_id == owner_user_id and item.attachment_id == attachment_id
        ]

    async def save_job(self, job: AttachmentProcessingJob) -> None:
        self._working.jobs[job.id] = job

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[AttachmentProcessingJob]:
        pending_job_ids = {
            message.job_id for message in self._working.outbox.values() if not message.terminal
        }
        return sorted(
            (
                job
                for job in self._working.jobs.values()
                if job.id not in pending_job_ids
                and (
                    (
                        job.status is AttachmentJobStatus.RUNNING
                        and job.lease_expires_at is not None
                        and job.lease_expires_at <= now
                    )
                    or (
                        job.status
                        in {
                            AttachmentJobStatus.QUEUED,
                            AttachmentJobStatus.RETRY_WAIT,
                        }
                        and job.updated_at <= stale_before
                        and (job.next_attempt_at is None or job.next_attempt_at <= now)
                    )
                )
            ),
            key=lambda job: (job.updated_at, job.id.int),
        )[:limit]

    async def next_outbox_generation(self, owner_user_id: UUID, job_id: UUID) -> int:
        generations = [
            message.generation
            for message in self._working.outbox.values()
            if message.owner_user_id == owner_user_id and message.job_id == job_id
        ]
        return max(generations, default=-1) + 1

    async def add_outbox(self, message: AttachmentOutboxMessage) -> None:
        if message.id in self._working.outbox:
            raise RuntimeError("duplicate attachment outbox message")
        self._working.outbox[message.id] = message

    async def list_pending_outbox(self, now: datetime, limit: int) -> list[AttachmentOutboxMessage]:
        return sorted(
            (
                item
                for item in self._working.outbox.values()
                if not item.terminal and item.next_attempt_at <= now
            ),
            key=lambda item: (item.next_attempt_at, item.created_at, item.id.int),
        )[:limit]

    async def save_outbox(self, message: AttachmentOutboxMessage) -> None:
        self._working.outbox[message.id] = message

    async def add_cleanup(self, cleanup: AttachmentObjectCleanup) -> None:
        if cleanup.id in self._working.cleanups:
            raise RuntimeError("duplicate attachment cleanup")
        self._working.cleanups[cleanup.id] = cleanup

    async def has_cleanup_for_object(
        self, owner_user_id: UUID, attachment_id: UUID, object_key: str
    ) -> bool:
        return any(
            item.owner_user_id == owner_user_id
            and item.attachment_id == attachment_id
            and item.object_key == object_key
            for item in self._working.cleanups.values()
        )

    async def get_cleanup_system(
        self, cleanup_id: UUID, *, for_update: bool = False
    ) -> AttachmentObjectCleanup | None:
        del for_update
        return self._working.cleanups.get(cleanup_id)

    async def list_cleanups_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentObjectCleanup]:
        return [
            item
            for item in self._working.cleanups.values()
            if item.owner_user_id == owner_user_id and item.attachment_id == attachment_id
        ]

    async def list_due_cleanups(self, now: datetime, limit: int) -> list[AttachmentObjectCleanup]:
        return sorted(
            (
                item
                for item in self._working.cleanups.values()
                if not item.terminal and item.next_attempt_at <= now
            ),
            key=lambda item: (item.next_attempt_at, item.created_at, item.id.int),
        )[:limit]

    async def save_cleanup(self, cleanup: AttachmentObjectCleanup) -> None:
        self._working.cleanups[cleanup.id] = cleanup

    async def add_audit(self, event: AttachmentAuditEvent) -> None:
        self._working.audits.append(event)

    async def commit(self) -> None:
        self._factory.replace_state(self._working)


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class SequentialIds:
    def __init__(self) -> None:
        self.value = 10_000

    def new(self) -> UUID:
        self.value += 1
        return UUID(int=self.value)


class SequentialTokens:
    def __init__(self) -> None:
        self.value = 0

    def token_urlsafe(self, entropy_bytes: int) -> str:
        assert entropy_bytes >= 32
        self.value += 1
        return sha256(f"attachment-token-{self.value}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredObject:
    value: bytes
    media_type: str


class FakeAttachmentStorage(AttachmentObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.put_requests: list[tuple[str, str, int, datetime]] = []
        self.get_requests: list[tuple[str, str, AttachmentDownloadPurpose, datetime]] = []
        self.promotions: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.fail_delete = False
        self.fail_download = False

    async def presign_put(
        self,
        object_key: str,
        media_type: str,
        expected_size: int,
        expires_at: datetime,
    ) -> PresignedOperation:
        self.put_requests.append((object_key, media_type, expected_size, expires_at))
        return PresignedOperation(
            "PUT",
            f"https://objects.invalid/private-upload/{len(self.put_requests)}",
            (("content-type", media_type), ("content-length", str(expected_size))),
            expires_at,
        )

    def upload_latest(self, value: bytes, media_type: str | None = None) -> str:
        object_key, expected_type, _, _ = self.put_requests[-1]
        self.objects[object_key] = StoredObject(value, media_type or expected_type)
        return object_key

    async def head(self, object_key: str) -> ObjectMetadata:
        stored = self.objects.get(object_key)
        if stored is None:
            raise AttachmentObjectMissing
        return ObjectMetadata(len(stored.value), stored.media_type)

    async def read_prefix(self, object_key: str, length: int) -> bytes:
        stored = self.objects.get(object_key)
        if stored is None:
            raise AttachmentObjectMissing
        return stored.value[:length]

    async def promote(self, staging_key: str, quarantine_key: str) -> None:
        stored = self.objects.get(staging_key)
        if stored is None:
            raise AttachmentObjectMissing
        self.objects[quarantine_key] = stored
        self.promotions.append((staging_key, quarantine_key))

    async def download(
        self, object_key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject:
        if self.fail_download:
            raise AttachmentStorageUnavailable
        stored = self.objects.get(object_key)
        if stored is None:
            raise AttachmentObjectMissing
        if len(stored.value) > max_bytes:
            raise RuntimeError("download exceeded limit")
        destination.write_bytes(stored.value)
        return DownloadedObject(
            destination.resolve(), len(stored.value), sha256(stored.value).digest()
        )

    async def presign_get(
        self,
        object_key: str,
        display_filename: str,
        purpose: AttachmentDownloadPurpose,
        expires_at: datetime,
    ) -> PresignedOperation:
        if object_key not in self.objects:
            raise AttachmentObjectMissing
        self.get_requests.append((object_key, display_filename, purpose, expires_at))
        return PresignedOperation(
            "GET",
            f"https://objects.invalid/private-download/{len(self.get_requests)}",
            (("content-disposition", f'attachment; filename="{display_filename}"'),),
            expires_at,
        )

    async def delete(self, object_key: str) -> None:
        if self.fail_delete:
            raise RuntimeError("delete unavailable")
        self.objects.pop(object_key, None)
        self.deleted.append(object_key)


class FakeScanner:
    def __init__(self) -> None:
        self.verdict = ScanVerdict.CLEAN
        self.calls = 0
        self.error: Exception | None = None

    async def scan(self, path: Path) -> MalwareScanResult:
        assert path.is_file()
        self.calls += 1
        if self.error is not None:
            raise self.error
        return MalwareScanResult(self.verdict)


class FakeExtractor:
    def __init__(self) -> None:
        self.summary = AttachmentExtractionSummary(
            format_valid=True,
            page_count=1,
            extracted_characters=100,
            extracted_blocks=2,
            archive_entries=0,
            archive_uncompressed_bytes=0,
            max_archive_ratio=0,
            parser_version="fake-1",
        )
        self.calls = 0
        self.error: Exception | None = None

    async def extract(
        self, path: Path, media_type: AttachmentMediaType, limits: AttachmentLimits
    ) -> AttachmentExtractionSummary:
        del limits
        assert path.is_file()
        assert media_type in {AttachmentMediaType.PDF, AttachmentMediaType.DOCX}
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.summary


class FakePublisher(AttachmentJobPublisher):
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, str]] = []
        self.fail = False

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.calls.append((task_name, job_id, trace_id))


def pending_cleanups(
    factory: InMemoryAttachmentUnitOfWorkFactory, attachment_id: UUID
) -> list[AttachmentObjectCleanup]:
    return [
        item
        for item in factory.state.cleanups.values()
        if item.attachment_id == attachment_id and item.status is not CleanupStatus.COMPLETED
    ]
