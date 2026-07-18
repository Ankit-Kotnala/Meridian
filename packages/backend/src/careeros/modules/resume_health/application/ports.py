"""Inward-facing ports for resume ingestion, processing, and analysis."""

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.resume_health.application.models import (
    CapabilitySecret,
    DocumentLimits,
    ExtractionResult,
    MalwareScanResult,
    ObjectMetadata,
    StorageUploadTarget,
)
from careeros.modules.resume_health.domain import (
    CanonicalSnapshot,
    DocumentArtifact,
    FeatureContribution,
    GuestSession,
    JobKind,
    OutboxMessage,
    OwnerScope,
    ProcessingJob,
    ResumeAuditEvent,
    ResumeFinding,
    ResumeHealthAnalysis,
    ScoreComponent,
    SourceDocument,
    StorageObjectCleanup,
    UploadIntent,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class CapabilityManager(Protocol):
    def issue(self) -> CapabilitySecret: ...

    def parse(self, encoded: str) -> tuple[UUID, str] | None: ...

    def verify(self, expected: bytes, secret: str) -> bool: ...


class ObjectStorage(Protocol):
    async def ping(self) -> None: ...

    async def presign_upload(
        self,
        object_key: str,
        media_type: str,
        expected_size: int,
        expires_at: datetime,
    ) -> StorageUploadTarget: ...

    async def head(self, object_key: str) -> ObjectMetadata: ...

    async def read_prefix(self, object_key: str, length: int) -> bytes: ...

    async def promote(self, staging_key: str, quarantine_key: str) -> None: ...

    async def download(self, object_key: str, destination: Path, max_bytes: int) -> bytes: ...

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None: ...

    async def get_bytes(self, object_key: str, max_bytes: int) -> bytes: ...

    async def copy(self, source_key: str, destination_key: str) -> None: ...

    async def delete(self, object_key: str) -> None: ...

    async def dispose(self) -> None: ...


class MalwareScanner(Protocol):
    async def scan(self, path: Path) -> MalwareScanResult: ...


class DocumentExtractor(Protocol):
    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult: ...


class OcrProvider(Protocol):
    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult | None: ...


class JobPublisher(Protocol):
    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None: ...


class ResumeUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def add_guest_session(self, guest: GuestSession) -> None: ...

    async def get_guest_session(
        self, guest_id: UUID, *, for_update: bool = False
    ) -> GuestSession | None: ...

    async def save_guest_session(self, guest: GuestSession) -> None: ...

    async def add_upload(self, upload: UploadIntent) -> None: ...

    async def get_upload(
        self, scope: OwnerScope, upload_id: UUID, *, for_update: bool = False
    ) -> UploadIntent | None: ...

    async def save_upload(self, upload: UploadIntent) -> None: ...

    async def lock_intake_admission(self, scope: OwnerScope) -> None: ...

    async def count_active_intakes(self, scope: OwnerScope, now: datetime) -> int: ...

    async def add_document(self, document: SourceDocument) -> None: ...

    async def get_document(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None: ...

    async def get_document_system(
        self, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None: ...

    async def list_documents(self, scope: OwnerScope, limit: int) -> list[SourceDocument]: ...

    async def save_document(self, document: SourceDocument) -> None: ...

    async def add_job(self, job: ProcessingJob) -> None: ...

    async def get_job(
        self, scope: OwnerScope, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None: ...

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None: ...

    async def get_job_by_idempotency(
        self, scope: OwnerScope, idempotency_key: str
    ) -> ProcessingJob | None: ...

    async def has_active_jobs(self, scope: OwnerScope, document_id: UUID) -> bool: ...

    async def count_jobs(self, scope: OwnerScope, document_id: UUID, kind: JobKind) -> int: ...

    async def save_job(self, job: ProcessingJob) -> None: ...

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[ProcessingJob]: ...

    async def add_artifact(self, artifact: DocumentArtifact) -> None: ...

    async def save_artifact(self, artifact: DocumentArtifact) -> None: ...

    async def list_artifacts(
        self, scope: OwnerScope, document_id: UUID
    ) -> list[DocumentArtifact]: ...

    async def add_snapshot(self, snapshot: CanonicalSnapshot) -> None: ...

    async def get_latest_snapshot(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> CanonicalSnapshot | None: ...

    async def get_first_snapshot(
        self, scope: OwnerScope, document_id: UUID
    ) -> CanonicalSnapshot | None: ...

    async def get_snapshot(
        self, scope: OwnerScope, snapshot_id: UUID
    ) -> CanonicalSnapshot | None: ...

    async def add_analysis(
        self,
        analysis: ResumeHealthAnalysis,
        components: tuple[ScoreComponent, ...],
        feature_contributions: tuple[FeatureContribution, ...],
        findings: tuple[ResumeFinding, ...],
    ) -> None: ...

    async def get_analysis(
        self, scope: OwnerScope, analysis_id: UUID
    ) -> (
        tuple[
            ResumeHealthAnalysis,
            list[ScoreComponent],
            list[FeatureContribution],
            list[ResumeFinding],
        ]
        | None
    ): ...

    async def get_latest_analysis_for_document(
        self, scope: OwnerScope, document_id: UUID
    ) -> (
        tuple[
            ResumeHealthAnalysis,
            list[ScoreComponent],
            list[FeatureContribution],
            list[ResumeFinding],
        ]
        | None
    ): ...

    async def get_analysis_for_snapshot(
        self, scope: OwnerScope, snapshot_id: UUID
    ) -> (
        tuple[
            ResumeHealthAnalysis,
            list[ScoreComponent],
            list[FeatureContribution],
            list[ResumeFinding],
        ]
        | None
    ): ...

    async def add_outbox(self, message: OutboxMessage) -> None: ...

    async def add_audit(self, event: ResumeAuditEvent) -> None: ...

    async def list_pending_outbox(self, now: datetime, limit: int) -> list[OutboxMessage]: ...

    async def save_outbox(self, message: OutboxMessage) -> None: ...

    async def add_object_cleanup(self, cleanup: StorageObjectCleanup) -> None: ...

    async def save_object_cleanup(self, cleanup: StorageObjectCleanup) -> None: ...

    async def list_due_object_cleanups(
        self, now: datetime, limit: int
    ) -> list[StorageObjectCleanup]: ...

    async def claim_guest_resources(
        self, guest_session_id: UUID, user_id: UUID, document_id: UUID, now: datetime
    ) -> None: ...

    async def purge_document_content(
        self, scope: OwnerScope, document_id: UUID, keep_job_id: UUID
    ) -> None: ...

    async def list_expired_uploads(self, now: datetime, limit: int) -> list[UploadIntent]: ...

    async def list_expired_guest_documents(
        self, now: datetime, limit: int
    ) -> list[SourceDocument]: ...

    async def list_expired_guests(self, now: datetime, limit: int) -> list[GuestSession]: ...

    async def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> ResumeUnitOfWork: ...


class AsyncSessionProvider(Protocol):
    def session(self) -> AsyncIterator[object]: ...
