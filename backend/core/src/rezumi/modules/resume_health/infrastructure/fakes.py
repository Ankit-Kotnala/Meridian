"""Deterministic in-memory adapters for unit and delivery-layer tests."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Self
from uuid import UUID

from rezumi.modules.resume_health.application.models import (
    DocumentLimits,
    ExtractionResult,
    MalwareScanResult,
    ObjectMetadata,
    StorageUploadTarget,
)
from rezumi.modules.resume_health.domain import (
    CanonicalSnapshot,
    DocumentArtifact,
    DocumentStatus,
    FeatureContribution,
    GuestSession,
    JobKind,
    JobStatus,
    OutboxMessage,
    OwnerScope,
    ProcessingJob,
    ResumeFinding,
    ResumeHealthAnalysis,
    ScoreComponent,
    SourceDocument,
    StorageObjectCleanup,
    UploadIntent,
    UploadStatus,
)


class FixedClock:
    def __init__(self, now: datetime | None = None) -> None:
        self.value = now or datetime(2026, 7, 15, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []

    async def ping(self) -> None:
        return None

    async def presign_upload(
        self, object_key: str, media_type: str, expected_size: int, expires_at: datetime
    ) -> StorageUploadTarget:
        return StorageUploadTarget(
            method="PUT",
            url=f"https://uploads.invalid/{object_key}",
            headers={"Content-Type": media_type, "x-expected-size": str(expected_size)},
            expires_at=expires_at,
        )

    async def head(self, object_key: str) -> ObjectMetadata:
        value, media_type = self.objects[object_key]
        return ObjectMetadata(len(value), media_type)

    async def read_prefix(self, object_key: str, length: int) -> bytes:
        return self.objects[object_key][0][:length]

    async def promote(self, staging_key: str, quarantine_key: str) -> None:
        self.objects[quarantine_key] = self.objects[staging_key]

    async def download(self, object_key: str, destination: Path, max_bytes: int) -> bytes:
        value = self.objects[object_key][0]
        if len(value) > max_bytes:
            raise ValueError("object too large")
        destination.write_bytes(value)
        return sha256(value).digest()

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        self.objects[object_key] = (bytes(value), media_type)

    async def get_bytes(self, object_key: str, max_bytes: int) -> bytes:
        value = self.objects[object_key][0]
        if len(value) > max_bytes:
            raise ValueError("object too large")
        return value

    async def copy(self, source_key: str, destination_key: str) -> None:
        self.objects[destination_key] = self.objects[source_key]

    async def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)
        self.deleted.append(object_key)

    async def dispose(self) -> None:
        return None


class FakeMalwareScanner:
    def __init__(self, result: MalwareScanResult | None = None) -> None:
        self.result = result or MalwareScanResult(clean=True, infected=False)

    async def scan(self, path: Path) -> MalwareScanResult:
        del path
        return self.result


class FakeDocumentExtractor:
    def __init__(self, result: ExtractionResult) -> None:
        self.result = result

    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult:
        del path, media_type, limits
        return self.result


class DisabledOcrProvider:
    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult | None:
        del path, media_type, limits
        return None


class FakeJobPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, UUID, str]] = []
        self.fail = False

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        if self.fail:
            raise OSError("fake publish failure")
        self.messages.append((task_name, job_id, trace_id))


class InMemoryResumeUnitOfWork:
    def __init__(self, state: "InMemoryResumeState") -> None:
        self.state = state

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def add_guest_session(self, guest: GuestSession) -> None:
        self.state.guests[guest.id] = guest

    async def get_guest_session(
        self, guest_id: UUID, *, for_update: bool = False
    ) -> GuestSession | None:
        del for_update
        return self.state.guests.get(guest_id)

    async def save_guest_session(self, guest: GuestSession) -> None:
        self.state.guests[guest.id] = guest

    async def add_upload(self, upload: UploadIntent) -> None:
        self.state.uploads[upload.id] = upload

    async def get_upload(
        self, scope: OwnerScope, upload_id: UUID, *, for_update: bool = False
    ) -> UploadIntent | None:
        del for_update
        item = self.state.uploads.get(upload_id)
        return item if item is not None and item.owner == scope else None

    async def save_upload(self, upload: UploadIntent) -> None:
        self.state.uploads[upload.id] = upload

    async def lock_intake_admission(self, scope: OwnerScope) -> None:
        del scope

    async def count_active_intakes(self, scope: OwnerScope, now: datetime) -> int:
        documents = sum(
            item.owner == scope and item.status != DocumentStatus.DELETED
            for item in self.state.documents.values()
        )
        uploads = sum(
            item.owner == scope and item.status == UploadStatus.ISSUED and item.expires_at > now
            for item in self.state.uploads.values()
        )
        return documents + uploads

    async def add_document(self, document: SourceDocument) -> None:
        self.state.documents[document.id] = document

    async def get_document(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None:
        del for_update
        item = self.state.documents.get(document_id)
        return (
            item if item is not None and item.owner == scope and item.deleted_at is None else None
        )

    async def get_document_system(
        self, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None:
        del for_update
        return self.state.documents.get(document_id)

    async def list_documents(self, scope: OwnerScope, limit: int) -> list[SourceDocument]:
        return [
            item
            for item in self.state.documents.values()
            if item.owner == scope and item.status != DocumentStatus.DELETED
        ][:limit]

    async def save_document(self, document: SourceDocument) -> None:
        self.state.documents[document.id] = document

    async def add_job(self, job: ProcessingJob) -> None:
        existing = await self.get_job_by_idempotency(job.owner, job.idempotency_key)
        if existing is not None and existing.id != job.id:
            raise ValueError("duplicate idempotency key")
        self.state.jobs[job.id] = job

    async def get_job(
        self, scope: OwnerScope, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None:
        del for_update
        item = self.state.jobs.get(job_id)
        return item if item is not None and item.owner == scope else None

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None:
        del for_update
        return self.state.jobs.get(job_id)

    async def get_job_by_idempotency(
        self, scope: OwnerScope, idempotency_key: str
    ) -> ProcessingJob | None:
        return next(
            (
                item
                for item in self.state.jobs.values()
                if item.owner == scope and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def has_active_jobs(self, scope: OwnerScope, document_id: UUID) -> bool:
        return any(
            item.owner == scope
            and item.document_id == document_id
            and (
                item.status in {JobStatus.QUEUED, JobStatus.RUNNING}
                or (item.status == JobStatus.FAILED and item.retryable)
            )
            for item in self.state.jobs.values()
        )

    async def count_jobs(self, scope: OwnerScope, document_id: UUID, kind: JobKind) -> int:
        return sum(
            item.owner == scope and item.document_id == document_id and item.kind == kind
            for item in self.state.jobs.values()
        )

    async def save_job(self, job: ProcessingJob) -> None:
        self.state.jobs[job.id] = job

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[ProcessingJob]:
        matches: list[ProcessingJob] = []
        for job in self.state.jobs.values():
            messages = [item for item in self.state.outbox.values() if item.job_id == job.id]
            pending = any(not item.terminal for item in messages)
            stale_published = any(
                item.published_at is not None and item.published_at <= stale_before
                for item in messages
            )
            recovery_due = job.next_recovery_at is None or job.next_recovery_at <= now
            eligible = (
                (job.status == JobStatus.QUEUED and stale_published)
                or (
                    job.status == JobStatus.FAILED
                    and job.retryable
                    and job.updated_at <= stale_before
                )
                or (
                    job.status == JobStatus.RUNNING
                    and job.lease_expires_at is not None
                    and job.lease_expires_at <= now
                )
            )
            if not pending and recovery_due and eligible:
                matches.append(job)
        return matches[:limit]

    async def add_artifact(self, artifact: DocumentArtifact) -> None:
        self.state.artifacts[artifact.id] = artifact

    async def save_artifact(self, artifact: DocumentArtifact) -> None:
        self.state.artifacts[artifact.id] = artifact

    async def list_artifacts(self, scope: OwnerScope, document_id: UUID) -> list[DocumentArtifact]:
        return [
            item
            for item in self.state.artifacts.values()
            if item.owner == scope and item.document_id == document_id
        ]

    async def add_snapshot(self, snapshot: CanonicalSnapshot) -> None:
        self.state.snapshots[snapshot.id] = snapshot

    async def get_latest_snapshot(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> CanonicalSnapshot | None:
        del for_update
        matches = [
            item
            for item in self.state.snapshots.values()
            if item.owner == scope and item.document_id == document_id
        ]
        return max(matches, key=lambda item: item.revision, default=None)

    async def get_first_snapshot(
        self, scope: OwnerScope, document_id: UUID
    ) -> CanonicalSnapshot | None:
        matches = [
            item
            for item in self.state.snapshots.values()
            if item.owner == scope and item.document_id == document_id
        ]
        return min(matches, key=lambda item: item.revision, default=None)

    async def get_snapshot(self, scope: OwnerScope, snapshot_id: UUID) -> CanonicalSnapshot | None:
        item = self.state.snapshots.get(snapshot_id)
        return item if item is not None and item.owner == scope else None

    async def add_analysis(
        self,
        analysis: ResumeHealthAnalysis,
        components: tuple[ScoreComponent, ...],
        feature_contributions: tuple[FeatureContribution, ...],
        findings: tuple[ResumeFinding, ...],
    ) -> None:
        self.state.analyses[analysis.id] = analysis
        self.state.components[analysis.id] = list(components)
        self.state.feature_contributions[analysis.id] = list(feature_contributions)
        self.state.findings[analysis.id] = list(findings)

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
    ):
        item = self.state.analyses.get(analysis_id)
        if item is None or item.owner != scope:
            return None
        return (
            item,
            self.state.components[analysis_id],
            self.state.feature_contributions[analysis_id],
            self.state.findings[analysis_id],
        )

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
    ):
        matches = [
            item
            for item in self.state.analyses.values()
            if item.owner == scope and item.document_id == document_id
        ]
        item = max(matches, key=lambda value: value.computed_at, default=None)
        if item is None:
            return None
        return (
            item,
            self.state.components[item.id],
            self.state.feature_contributions[item.id],
            self.state.findings[item.id],
        )

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
    ):
        item = next(
            (
                value
                for value in self.state.analyses.values()
                if value.owner == scope and value.snapshot_id == snapshot_id
            ),
            None,
        )
        if item is None:
            return None
        return (
            item,
            self.state.components[item.id],
            self.state.feature_contributions[item.id],
            self.state.findings[item.id],
        )

    async def add_outbox(self, message: OutboxMessage) -> None:
        self.state.outbox[message.id] = message

    async def add_audit(self, event: object) -> None:
        self.state.audit.append(event)

    async def list_pending_outbox(self, now: datetime, limit: int) -> list[OutboxMessage]:
        return [
            item
            for item in self.state.outbox.values()
            if not item.terminal and item.next_attempt_at <= now
        ][:limit]

    async def save_outbox(self, message: OutboxMessage) -> None:
        self.state.outbox[message.id] = message

    async def add_object_cleanup(self, cleanup: StorageObjectCleanup) -> None:
        self.state.object_cleanups[cleanup.id] = cleanup

    async def save_object_cleanup(self, cleanup: StorageObjectCleanup) -> None:
        self.state.object_cleanups[cleanup.id] = cleanup

    async def list_due_object_cleanups(
        self, now: datetime, limit: int
    ) -> list[StorageObjectCleanup]:
        return [
            item
            for item in self.state.object_cleanups.values()
            if not item.terminal and item.not_before <= now
        ][:limit]

    async def claim_guest_resources(
        self, guest_session_id: UUID, user_id: UUID, document_id: UUID, now: datetime
    ) -> None:
        old = OwnerScope(guest_session_id=guest_session_id)
        new = OwnerScope(user_id=user_id)
        for collection in (
            self.state.uploads,
            self.state.documents,
            self.state.jobs,
            self.state.artifacts,
            self.state.snapshots,
            self.state.analyses,
        ):
            for item in collection.values():
                if item.owner == old:
                    item.owner = new
        guest = self.state.guests[guest_session_id]
        guest.claimed_by_user_id = user_id
        guest.claimed_document_id = document_id
        guest.revoked_at = now

    async def purge_document_content(
        self, scope: OwnerScope, document_id: UUID, keep_job_id: UUID
    ) -> None:
        del scope
        self.state.artifacts = {
            key: value
            for key, value in self.state.artifacts.items()
            if value.document_id != document_id
        }
        self.state.snapshots = {
            key: value
            for key, value in self.state.snapshots.items()
            if value.document_id != document_id
        }
        deleted_analyses = {
            key for key, value in self.state.analyses.items() if value.document_id == document_id
        }
        for analysis_id in deleted_analyses:
            self.state.analyses.pop(analysis_id, None)
            self.state.components.pop(analysis_id, None)
            self.state.feature_contributions.pop(analysis_id, None)
            self.state.findings.pop(analysis_id, None)
        self.state.jobs = {
            key: value
            for key, value in self.state.jobs.items()
            if value.document_id != document_id or key == keep_job_id
        }

    async def list_expired_uploads(self, now: datetime, limit: int) -> list[UploadIntent]:
        return [
            item
            for item in self.state.uploads.values()
            if (
                (
                    item.status
                    in {UploadStatus.ISSUED, UploadStatus.EXPIRED, UploadStatus.FINALIZED}
                    and item.expires_at <= now
                )
                or item.status == UploadStatus.REJECTED
            )
            and item.staging_cleaned_at is None
        ][:limit]

    async def list_expired_guest_documents(self, now: datetime, limit: int) -> list[SourceDocument]:
        return [
            item
            for item in self.state.documents.values()
            if item.owner.guest_session_id is not None
            and item.retention_expires_at is not None
            and item.retention_expires_at <= now
            and item.status not in {DocumentStatus.DELETING, DocumentStatus.DELETED}
        ][:limit]

    async def list_expired_guests(self, now: datetime, limit: int) -> list[GuestSession]:
        return [
            item
            for item in self.state.guests.values()
            if item.expires_at <= now and item.revoked_at is None
        ][:limit]

    async def commit(self) -> None:
        return None


class InMemoryResumeState:
    def __init__(self) -> None:
        self.guests: dict[UUID, GuestSession] = {}
        self.uploads: dict[UUID, UploadIntent] = {}
        self.documents: dict[UUID, SourceDocument] = {}
        self.jobs: dict[UUID, ProcessingJob] = {}
        self.artifacts: dict[UUID, DocumentArtifact] = {}
        self.snapshots: dict[UUID, CanonicalSnapshot] = {}
        self.analyses: dict[UUID, ResumeHealthAnalysis] = {}
        self.components: dict[UUID, list[ScoreComponent]] = {}
        self.feature_contributions: dict[UUID, list[FeatureContribution]] = {}
        self.findings: dict[UUID, list[ResumeFinding]] = {}
        self.outbox: dict[UUID, OutboxMessage] = {}
        self.object_cleanups: dict[UUID, StorageObjectCleanup] = {}
        self.audit: list[object] = []


class InMemoryResumeUnitOfWorkFactory:
    def __init__(self, state: InMemoryResumeState | None = None) -> None:
        self.state = state or InMemoryResumeState()

    def __call__(self) -> InMemoryResumeUnitOfWork:
        return InMemoryResumeUnitOfWork(self.state)


class InMemoryParsedResumeDocumentStore:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []

    async def ping(self) -> None:
        return None

    async def upsert(self, document: dict[str, Any]) -> None:
        resume_id = str(document["resumeId"])
        existing = self.documents.get(resume_id)
        if existing is None:
            self.documents[resume_id] = {**document, "createdAt": document.get("updatedAt")}
            return
        self.documents[resume_id] = {**existing, **document}

    async def delete(self, resume_id: UUID) -> None:
        key = str(resume_id)
        self.documents.pop(key, None)
        self.deleted.append(key)

    async def dispose(self) -> None:
        return None
