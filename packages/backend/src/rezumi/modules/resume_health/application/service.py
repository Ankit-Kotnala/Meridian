"""Resume upload, review, processing, analysis, outbox, and retention use cases."""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from rezumi.modules.resume_health.application.models import (
    AnalysisView,
    CanonicalSnapshotView,
    ClaimGuestDocument,
    CleanupResult,
    CorrectionOperation,
    CreateUploadIntent,
    DocumentLimits,
    DocumentView,
    ExtractedBlock,
    FeatureContributionView,
    FinalizedUpload,
    FindingView,
    IssuedGuestSession,
    JobReconciliationResult,
    OutboxDispatchResult,
    ProcessingJobView,
    ProcessingOutcome,
    ResumeRequestContext,
    ScoreComponentView,
    SemanticReviewOperation,
    UploadIntentView,
)
from rezumi.modules.resume_health.application.ports import (
    CapabilityManager,
    Clock,
    DocumentExtractor,
    JobPublisher,
    MalwareScanner,
    ObjectStorage,
    OcrProvider,
    ResumeParserProvider,
    ResumeUnitOfWork,
    UnitOfWorkFactory,
)
from rezumi.modules.resume_health.application.semantic_review import apply_semantic_review
from rezumi.modules.resume_health.application.semantic_validation import (
    validate_parser_semantics,
)
from rezumi.modules.resume_health.application.task_names import PROCESS_RESUME_TASK
from rezumi.modules.resume_health.domain import (
    AnalysisStatus,
    ArtifactKind,
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    CanonicalSnapshot,
    DatePrecision,
    DocumentArtifact,
    DocumentStatus,
    FeatureContribution,
    FindingSeverity,
    GuestSession,
    JobKind,
    JobStatus,
    MalwareStatus,
    ObjectCleanupPurpose,
    OutboxMessage,
    OwnerScope,
    ProcessingJob,
    ProcessingStage,
    ResumeAuditEvent,
    ResumeFinding,
    ResumeHealthAnalysis,
    ResumeMediaType,
    ScoreComponent,
    SectionKind,
    SemanticReviewState,
    SourceDocument,
    SourceSpan,
    StorageObjectCleanup,
    UploadIntent,
    UploadStatus,
)
from rezumi.modules.resume_health.domain.errors import (
    GuestCapabilityRejected,
    IdempotencyConflict,
    ProcessingCancelled,
    ResumeResourceNotFound,
    ResumeStateConflict,
    ResumeVersionConflict,
    RetryableProcessingFailure,
    UnsafeDocument,
    UploadExpired,
    UploadRejected,
)
from rezumi.modules.resume_health.domain.scoring import (
    ResumeHealthFeatures,
    score_resume_health,
)

_CANONICAL_NAMESPACE = UUID("f704e80e-d209-45e0-9243-937a2b049baf")
_SAFE_KEY_PART = re.compile(r"[^a-zA-Z0-9_-]")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_EXECUTION_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ACTION_WORDS = re.compile(
    r"\b(?:built|created|delivered|designed|developed|drove|improved|implemented|led|launched|managed|optimized|reduced|increased|owned|supported)\b",
    re.IGNORECASE,
)
_OUTCOME_WORDS = re.compile(
    r"\b(?:result(?:ed)?|outcome|increased|reduced|improved|saved|grew|accelerated|revenue|cost|time|quality|adoption)\b",
    re.IGNORECASE,
)
_DATE_SIGNAL = re.compile(r"\b(?:19|20)\d{2}\b")
_SECTION_NAMES: dict[str, SectionKind] = {
    "summary": SectionKind.SUMMARY,
    "profile": SectionKind.SUMMARY,
    "experience": SectionKind.EXPERIENCE,
    "work experience": SectionKind.EXPERIENCE,
    "professional experience": SectionKind.EXPERIENCE,
    "education": SectionKind.EDUCATION,
    "skills": SectionKind.SKILLS,
    "technical skills": SectionKind.SKILLS,
    "projects": SectionKind.PROJECTS,
    "certifications": SectionKind.CERTIFICATIONS,
    "contact": SectionKind.CONTACT,
}


@dataclass(frozen=True, slots=True)
class ResumeHealthPolicy:
    upload_ttl_seconds: int = 900
    guest_session_ttl_seconds: int = 86_400
    guest_document_retention_seconds: int = 86_400
    max_job_attempts: int = 3
    artifact_read_limit_bytes: int = 2 * 1024 * 1024
    max_registered_documents: int = 25
    max_guest_documents: int = 1
    max_canonical_revisions: int = 50
    max_analysis_jobs_per_document: int = 100
    claim_cleanup_grace_seconds: int = 900
    upload_cleanup_grace_seconds: int = 900
    max_object_cleanup_attempts: int = 10

    def __post_init__(self) -> None:
        if self.max_registered_documents < 1 or self.max_guest_documents != 1:
            raise ValueError("document quotas must allow one guest and registered document")
        if self.max_canonical_revisions < 2 or self.max_analysis_jobs_per_document < 1:
            raise ValueError("resume history limits must be positive and bounded")
        if (
            self.claim_cleanup_grace_seconds < 1
            or self.upload_cleanup_grace_seconds < 1
            or self.max_object_cleanup_attempts < 1
        ):
            raise ValueError("object cleanup policy must be positive")


class ResumeHealthSourceReader:
    """Purpose-limited owned resume reads for another application context."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work

    async def get_document(self, scope: OwnerScope, document_id: UUID) -> DocumentView:
        async with self._uow() as uow:
            document = await uow.get_document(scope, document_id)
            snapshot = await uow.get_latest_snapshot(scope, document_id)
            analysis = await uow.get_latest_analysis_for_document(scope, document_id)
        if document is None:
            raise ResumeResourceNotFound
        return _document_view(
            document,
            snapshot.id if snapshot is not None else None,
            analysis[0].id if analysis is not None else None,
        )

    async def get_canonical_resume(
        self,
        scope: OwnerScope,
        document_id: UUID,
    ) -> CanonicalSnapshotView:
        async with self._uow() as uow:
            current = await uow.get_latest_snapshot(scope, document_id)
            original = await uow.get_first_snapshot(scope, document_id)
        if current is None or original is None:
            raise ResumeResourceNotFound
        return _snapshot_view(current, original.resume)


class ResumeHealthService:
    """Short request/transaction use cases; document bytes stay in object storage."""

    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        capabilities: CapabilityManager,
        storage: ObjectStorage,
        limits: DocumentLimits,
        policy: ResumeHealthPolicy | None = None,
        semantic_parser: ResumeParserProvider | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._capabilities = capabilities
        self._storage = storage
        self._limits = limits
        self._policy = policy or ResumeHealthPolicy()
        self._semantic_parser = semantic_parser
        self._source_reader = ResumeHealthSourceReader(unit_of_work)

    async def begin_guest_session(self) -> IssuedGuestSession:
        now = self._clock.now()
        issued = self._capabilities.issue()
        guest = GuestSession(
            id=issued.id,
            capability_hash=issued.digest,
            created_at=now,
            expires_at=now + timedelta(seconds=self._policy.guest_session_ttl_seconds),
        )
        async with self._uow() as uow:
            await uow.add_guest_session(guest)
            await uow.commit()
        return IssuedGuestSession(guest.id, issued.encoded, guest.expires_at)

    async def authenticate_guest(self, raw_token: str | None) -> OwnerScope:
        if raw_token is None:
            raise GuestCapabilityRejected
        parsed = self._capabilities.parse(raw_token)
        if parsed is None:
            raise GuestCapabilityRejected
        guest_id, secret = parsed
        async with self._uow() as uow:
            guest = await uow.get_guest_session(guest_id)
        if (
            guest is None
            or not guest.active_at(self._clock.now())
            or not self._capabilities.verify(guest.capability_hash, secret)
        ):
            raise GuestCapabilityRejected
        return OwnerScope(guest_session_id=guest.id)

    async def create_upload_intent(
        self,
        scope: OwnerScope,
        command: CreateUploadIntent,
        context: ResumeRequestContext | None = None,
    ) -> UploadIntentView:
        filename = _validate_filename(command.display_filename, command.media_type)
        if not 1 <= command.expected_size <= self._limits.max_upload_bytes:
            raise UploadRejected("upload_size_out_of_range")
        now = self._clock.now()
        upload_id = uuid4()
        key = _object_key("staging", scope, upload_id)
        upload = UploadIntent(
            id=upload_id,
            owner=scope,
            display_filename=filename,
            expected_media_type=command.media_type,
            expected_size=command.expected_size,
            staging_object_key=key,
            status=UploadStatus.ISSUED,
            created_at=now,
            expires_at=now + timedelta(seconds=self._policy.upload_ttl_seconds),
        )
        async with self._uow() as uow:
            await uow.lock_intake_admission(scope)
            quota = (
                self._policy.max_registered_documents
                if scope.user_id is not None
                else self._policy.max_guest_documents
            )
            if await uow.count_active_intakes(scope, now) >= quota:
                raise ResumeStateConflict
            # Generate the signed request only after quota admission, but before any
            # durable intake row is committed. A signer outage therefore cannot consume
            # quota, and a quota rejection never exposes an otherwise untracked object key.
            target = await self._storage.presign_upload(
                key, command.media_type.value, command.expected_size, upload.expires_at
            )
            await uow.add_upload(upload)
            await uow.add_audit(
                _audit(
                    scope, "upload.intent_created", "accepted", "upload", upload.id, context, now
                )
            )
            await uow.commit()
        return UploadIntentView(
            id=upload.id,
            display_filename=upload.display_filename,
            media_type=upload.expected_media_type,
            expected_size=upload.expected_size,
            expires_at=upload.expires_at,
            target=target,
        )

    async def finalize_upload(
        self,
        scope: OwnerScope,
        upload_id: UUID,
        idempotency_key: str,
        context: ResumeRequestContext,
    ) -> FinalizedUpload:
        _validate_idempotency(idempotency_key)
        now = self._clock.now()
        request_hash = _request_hash("finalize", upload_id)
        promoted: tuple[str, str] | None = None
        try:
            async with self._uow() as uow:
                await uow.lock_intake_admission(scope)
                replay = await _finalized_upload_replay(
                    uow, scope, upload_id, idempotency_key, request_hash
                )
                if replay is not None:
                    return replay
                upload = await uow.get_upload(scope, upload_id, for_update=True)
                if upload is None:
                    raise ResumeResourceNotFound
                if upload.status != UploadStatus.ISSUED:
                    raise ResumeStateConflict
                if now >= upload.expires_at:
                    upload.status = UploadStatus.EXPIRED
                    await uow.save_upload(upload)
                    await uow.commit()
                    raise UploadExpired
                metadata = await self._storage.head(upload.staging_object_key)
                if metadata.size_bytes != upload.expected_size:
                    await self._reject_upload(uow, upload, "upload_size_mismatch", now)
                if metadata.media_type != upload.expected_media_type.value:
                    await self._reject_upload(uow, upload, "upload_media_type_mismatch", now)
                prefix = await self._storage.read_prefix(upload.staging_object_key, 1_024)
                try:
                    _validate_signature(prefix, upload.expected_media_type)
                except UploadRejected as exc:
                    await self._reject_upload(uow, upload, exc.code, now)
                document_id = uuid4()
                quarantine_key = _object_key("quarantine", scope, upload.id)
                promoted = (upload.staging_object_key, quarantine_key)
                await self._storage.promote(upload.staging_object_key, quarantine_key)
                retention = (
                    now + timedelta(seconds=self._policy.guest_document_retention_seconds)
                    if scope.guest_session_id is not None
                    else None
                )
                document = SourceDocument(
                    id=document_id,
                    upload_id=upload.id,
                    owner=scope,
                    display_filename=upload.display_filename,
                    media_type=upload.expected_media_type,
                    size_bytes=upload.expected_size,
                    quarantine_object_key=quarantine_key,
                    status=DocumentStatus.QUARANTINED,
                    malware_status=MalwareStatus.PENDING,
                    created_at=now,
                    updated_at=now,
                    retention_expires_at=retention,
                )
                job = _new_job(
                    document,
                    JobKind.PARSE,
                    idempotency_key,
                    request_hash,
                    context.trace_id,
                    now,
                    self._policy.max_job_attempts,
                )
                upload.status = UploadStatus.FINALIZED
                upload.finalized_document_id = document.id
                await uow.add_document(document)
                await uow.add_job(job)
                await uow.add_outbox(_outbox(job, now))
                await uow.add_audit(
                    _audit(
                        scope,
                        "upload.finalized",
                        "accepted",
                        "document",
                        document.id,
                        context,
                        now,
                    )
                )
                await uow.save_upload(upload)
                await uow.commit()
                return FinalizedUpload(document.id, job.id, document.status, job.status)
        except Exception:
            if promoted is not None:
                # A connection can raise after PostgreSQL committed. Re-read the durable
                # idempotency record before compensation; inability to prove rollback is
                # intentionally non-destructive and leaves recovery to a client replay.
                replay = None
                try:
                    async with self._uow() as recovery_uow:
                        replay = await _finalized_upload_replay(
                            recovery_uow,
                            scope,
                            upload_id,
                            idempotency_key,
                            request_hash,
                        )
                except Exception:
                    raise
                if replay is not None:
                    return replay
                await _restore_promoted_object(self._storage, *promoted)
            raise

    async def _reject_upload(
        self,
        uow: ResumeUnitOfWork,
        upload: UploadIntent,
        safe_error_code: str,
        now: Any,
    ) -> None:
        """Persist permanent admission rejection before best-effort object cleanup."""
        upload.status = UploadStatus.REJECTED
        upload.safe_error_code = safe_error_code
        await uow.add_object_cleanup(
            _new_object_cleanup(
                upload.owner,
                upload.staging_object_key,
                ObjectCleanupPurpose.UPLOAD_STAGING_BACKSTOP,
                now,
                max(
                    upload.expires_at
                    + timedelta(seconds=self._policy.upload_cleanup_grace_seconds),
                    now + timedelta(seconds=self._policy.upload_cleanup_grace_seconds),
                ),
                self._policy.max_object_cleanup_attempts,
            )
        )
        await uow.save_upload(upload)
        await uow.commit()
        cleaned = False
        try:
            await self._storage.delete(upload.staging_object_key)
        except Exception:
            cleaned = False
        else:
            cleaned = True
        if cleaned:
            try:
                async with self._uow() as cleanup_uow:
                    current = await cleanup_uow.get_upload(upload.owner, upload.id, for_update=True)
                    if current is not None and current.status == UploadStatus.REJECTED:
                        current.display_filename = "deleted"
                        current.staging_cleaned_at = now
                        await cleanup_uow.save_upload(current)
                        await cleanup_uow.commit()
            except Exception:
                raise UploadRejected(safe_error_code) from None
        raise UploadRejected(safe_error_code)

    async def list_documents(self, scope: OwnerScope) -> tuple[DocumentView, ...]:
        limit = (
            self._policy.max_registered_documents
            if scope.user_id is not None
            else self._policy.max_guest_documents
        )
        async with self._uow() as uow:
            documents = await uow.list_documents(scope, limit)
            views: list[DocumentView] = []
            for item in documents:
                snapshot = await uow.get_latest_snapshot(scope, item.id)
                analysis = await uow.get_latest_analysis_for_document(scope, item.id)
                views.append(
                    _document_view(
                        item,
                        snapshot.id if snapshot is not None else None,
                        analysis[0].id if analysis is not None else None,
                    )
                )
        return tuple(views)

    async def get_document(self, scope: OwnerScope, document_id: UUID) -> DocumentView:
        return await self._source_reader.get_document(scope, document_id)

    async def get_plain_text(self, scope: OwnerScope, document_id: UUID) -> str:
        artifact = await self._artifact(scope, document_id, ArtifactKind.PLAIN_TEXT)
        value = await self._storage.get_bytes(
            artifact.object_key, self._policy.artifact_read_limit_bytes
        )
        return value.decode("utf-8", errors="strict")

    async def get_reading_order(
        self, scope: OwnerScope, document_id: UUID
    ) -> tuple[ExtractedBlock, ...]:
        artifact = await self._artifact(scope, document_id, ArtifactKind.READING_ORDER)
        value = await self._storage.get_bytes(
            artifact.object_key, self._policy.artifact_read_limit_bytes
        )
        try:
            parsed = json.loads(value)
            return tuple(_extracted_block(item) for item in parsed)
        except (ValueError, TypeError, KeyError) as exc:
            raise ResumeStateConflict from exc

    async def _artifact(
        self, scope: OwnerScope, document_id: UUID, kind: ArtifactKind
    ) -> DocumentArtifact:
        async with self._uow() as uow:
            if await uow.get_document(scope, document_id) is None:
                raise ResumeResourceNotFound
            artifacts = await uow.list_artifacts(scope, document_id)
        artifact = next((item for item in artifacts if item.kind == kind), None)
        if artifact is None:
            raise ResumeResourceNotFound
        return artifact

    async def get_canonical_resume(
        self, scope: OwnerScope, document_id: UUID
    ) -> CanonicalSnapshotView:
        return await self._source_reader.get_canonical_resume(scope, document_id)

    async def correct_canonical_resume(
        self,
        scope: OwnerScope,
        document_id: UUID,
        expected_revision: int,
        corrections: tuple[CorrectionOperation, ...],
        context: ResumeRequestContext,
    ) -> CanonicalSnapshotView:
        if not corrections or len(corrections) > 250:
            raise ResumeStateConflict
        replacements: dict[UUID, str] = {}
        for correction in corrections:
            text = correction.text.strip()
            if not text or len(text) > 10_000 or "\x00" in text:
                raise ResumeStateConflict
            if correction.block_id in replacements:
                raise ResumeStateConflict
            replacements[correction.block_id] = text
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_intake_admission(scope)
            document = await uow.get_document(scope, document_id, for_update=True)
            current = await uow.get_latest_snapshot(scope, document_id, for_update=True)
            original = await uow.get_first_snapshot(scope, document_id)
            if document is None or current is None or original is None:
                raise ResumeResourceNotFound
            if document.status != DocumentStatus.READY:
                raise ResumeStateConflict
            if current.revision != expected_revision:
                raise ResumeVersionConflict
            if current.revision >= self._policy.max_canonical_revisions:
                raise ResumeStateConflict
            if current.resume.semantics is not None:
                raise ResumeStateConflict
            found: set[UUID] = set()
            text_changed = False
            sections: list[CanonicalSection] = []
            for section in current.resume.sections:
                blocks: list[CanonicalBlock] = []
                for block in section.blocks:
                    replacement = replacements.get(block.id)
                    if replacement is not None:
                        found.add(block.id)
                        if replacement == block.text:
                            blocks.append(block)
                        else:
                            text_changed = True
                            blocks.append(
                                replace(block, text=replacement, confidence_basis_points=10_000)
                            )
                    else:
                        blocks.append(block)
                sections.append(replace(section, blocks=tuple(blocks)))
            if found != set(replacements) or not text_changed:
                raise ResumeStateConflict
            revised_resume = replace(current.resume, sections=tuple(sections))
            if revised_resume == current.resume:
                raise ResumeStateConflict
            if (
                sum(
                    len(block.text)
                    for section in revised_resume.sections
                    for block in section.blocks
                )
                > self._limits.max_extracted_characters
                or len(
                    json.dumps(
                        revised_resume.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                > self._limits.max_serialized_artifact_bytes
            ):
                raise ResumeStateConflict
            snapshot = CanonicalSnapshot(
                id=uuid4(),
                document_id=document.id,
                owner=scope,
                revision=current.revision + 1,
                resume=revised_resume,
                plain_text_sha256=current.plain_text_sha256,
                parser_version=current.parser_version,
                based_on_snapshot_id=current.id,
                corrected_by_user=True,
                created_at=now,
            )
            document.version += 1
            document.updated_at = now
            await uow.add_snapshot(snapshot)
            await uow.save_document(document)
            await uow.add_audit(
                _audit(
                    scope,
                    "canonical_resume.corrected",
                    "succeeded",
                    "document",
                    document.id,
                    context,
                    now,
                    {"revision": str(snapshot.revision)},
                )
            )
            await uow.commit()
        return _snapshot_view(snapshot, original.resume)

    async def review_canonical_semantics(
        self,
        scope: OwnerScope,
        document_id: UUID,
        expected_revision: int,
        operations: tuple[SemanticReviewOperation, ...],
        context: ResumeRequestContext,
        *,
        confirm_no_changes: bool = False,
    ) -> CanonicalSnapshotView:
        if len(operations) > 250 or (not operations and not confirm_no_changes):
            raise ResumeStateConflict
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_intake_admission(scope)
            document = await uow.get_document(scope, document_id, for_update=True)
            current = await uow.get_latest_snapshot(scope, document_id, for_update=True)
            original = await uow.get_first_snapshot(scope, document_id)
            if document is None or current is None or original is None:
                raise ResumeResourceNotFound
            if document.status != DocumentStatus.READY:
                raise ResumeStateConflict
            if current.revision != expected_revision:
                raise ResumeVersionConflict
            if current.revision >= self._policy.max_canonical_revisions:
                raise ResumeStateConflict
            resume = current.resume
            if resume.semantics is None:
                if self._semantic_parser is None or document.content_sha256 is None:
                    raise ResumeStateConflict
                source_sections = original.resume.source_sections or original.resume.sections
                parser_source = replace(resume, sections=source_sections)
                semantics = await self._semantic_parser.parse(
                    document.id,
                    parser_source,
                    document.content_sha256.hex(),
                )
                try:
                    validate_parser_semantics(
                        parser_source,
                        semantics,
                        document.content_sha256.hex(),
                    )
                except ValueError as exc:
                    raise ResumeStateConflict from exc
                resume = replace(
                    resume,
                    schema_version="canonical-resume/2.0.0",
                    source_sections=source_sections,
                    semantics=semantics,
                )
            current_semantics = resume.semantics
            if current_semantics is None:
                raise ResumeStateConflict
            reviewed = apply_semantic_review(
                current_semantics,
                operations,
                confirm_no_changes=confirm_no_changes,
            )
            revised_resume = replace(resume, semantics=reviewed)
            if (
                len(
                    json.dumps(
                        revised_resume.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                > self._limits.max_serialized_artifact_bytes
            ):
                raise ResumeStateConflict
            snapshot = CanonicalSnapshot(
                id=uuid4(),
                document_id=document.id,
                owner=scope,
                revision=current.revision + 1,
                resume=revised_resume,
                plain_text_sha256=current.plain_text_sha256,
                parser_version=current.parser_version,
                based_on_snapshot_id=current.id,
                corrected_by_user=bool(operations),
                created_at=now,
            )
            document.version += 1
            document.updated_at = now
            await uow.add_snapshot(snapshot)
            await uow.save_document(document)
            await uow.add_audit(
                _audit(
                    scope,
                    "canonical_resume.reviewed",
                    "succeeded",
                    "document",
                    document.id,
                    context,
                    now,
                    {
                        "revision": str(snapshot.revision),
                        "operation_count": str(len(operations)),
                        "confirmed_no_changes": str(confirm_no_changes).lower(),
                    },
                )
            )
            await uow.commit()
        return _snapshot_view(snapshot, original.resume)

    async def get_job(self, scope: OwnerScope, job_id: UUID) -> ProcessingJobView:
        async with self._uow() as uow:
            job = await uow.get_job(scope, job_id)
        if job is None:
            raise ResumeResourceNotFound
        return _job_view(job)

    async def cancel_job(
        self, scope: OwnerScope, job_id: UUID, context: ResumeRequestContext
    ) -> ProcessingJobView:
        async with self._uow() as uow:
            job = await uow.get_job(scope, job_id, for_update=True)
            if job is None:
                raise ResumeResourceNotFound
            if job.kind == JobKind.DELETE:
                raise ResumeStateConflict
            job.request_cancel(self._clock.now())
            await uow.save_job(job)
            await uow.add_audit(
                _audit(
                    scope,
                    "processing_job.cancel_requested",
                    "accepted",
                    "processing_job",
                    job.id,
                    context,
                    self._clock.now(),
                )
            )
            await uow.commit()
        return _job_view(job)

    async def start_analysis(
        self,
        scope: OwnerScope,
        document_id: UUID,
        idempotency_key: str,
        context: ResumeRequestContext,
    ) -> ProcessingJobView:
        _validate_idempotency(idempotency_key)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_intake_admission(scope)
            document = await uow.get_document(scope, document_id, for_update=True)
            snapshot = await uow.get_latest_snapshot(scope, document_id)
            if document is None or snapshot is None:
                raise ResumeResourceNotFound
            if document.status != DocumentStatus.READY:
                raise ResumeStateConflict
            request_hash = _request_hash("analyze", document.id, snapshot.id)
            existing = await uow.get_job_by_idempotency(scope, idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict
                return _job_view(existing)
            completed = await uow.get_analysis_for_snapshot(scope, snapshot.id)
            if completed is not None:
                completed_job = await uow.get_job(scope, completed[0].job_id)
                if completed_job is None:
                    raise ResumeStateConflict
                return _job_view(completed_job)
            if (
                await uow.count_jobs(scope, document.id, JobKind.ANALYZE)
                >= self._policy.max_analysis_jobs_per_document
            ):
                raise ResumeStateConflict
            if await uow.has_active_jobs(scope, document.id):
                raise ResumeStateConflict
            job = _new_job(
                document,
                JobKind.ANALYZE,
                idempotency_key,
                request_hash,
                context.trace_id,
                now,
                self._policy.max_job_attempts,
                input_snapshot_id=snapshot.id,
            )
            await uow.add_job(job)
            await uow.add_outbox(_outbox(job, now))
            await uow.add_audit(
                _audit(
                    scope,
                    "resume_health.requested",
                    "accepted",
                    "document",
                    document.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return _job_view(job)

    async def get_analysis(self, scope: OwnerScope, analysis_id: UUID) -> AnalysisView:
        async with self._uow() as uow:
            bundle = await uow.get_analysis(scope, analysis_id)
        if bundle is None:
            raise ResumeResourceNotFound
        return _analysis_view(*bundle)

    async def get_latest_analysis(self, scope: OwnerScope, document_id: UUID) -> AnalysisView:
        async with self._uow() as uow:
            if await uow.get_document(scope, document_id) is None:
                raise ResumeResourceNotFound
            bundle = await uow.get_latest_analysis_for_document(scope, document_id)
        if bundle is None:
            raise ResumeResourceNotFound
        return _analysis_view(*bundle)

    async def request_delete(
        self,
        scope: OwnerScope,
        document_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: ResumeRequestContext,
    ) -> ProcessingJobView:
        _validate_idempotency(idempotency_key)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_intake_admission(scope)
            request_hash = _request_hash("delete", document_id, expected_version)
            existing = await uow.get_job_by_idempotency(scope, idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict
                return _job_view(existing)
            document = await uow.get_document(scope, document_id, for_update=True)
            if document is None:
                raise ResumeResourceNotFound
            if document.status == DocumentStatus.DELETING:
                raise ResumeStateConflict
            if document.version != expected_version:
                raise ResumeVersionConflict
            if await uow.has_active_jobs(scope, document.id):
                raise ResumeStateConflict
            document.status = DocumentStatus.DELETING
            document.updated_at = now
            document.version += 1
            job = _new_job(
                document,
                JobKind.DELETE,
                idempotency_key,
                request_hash,
                context.trace_id,
                now,
                self._policy.max_job_attempts,
            )
            await uow.save_document(document)
            await uow.add_job(job)
            await uow.add_outbox(_outbox(job, now))
            await uow.add_audit(
                _audit(
                    scope,
                    "document.deletion_requested",
                    "accepted",
                    "document",
                    document.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return _job_view(job)

    async def claim_guest_document(
        self,
        user_id: UUID,
        raw_capability: str,
        document_id: UUID,
        command: ClaimGuestDocument,
        context: ResumeRequestContext,
    ) -> DocumentView:
        if not command.consent or not command.policy_version.strip():
            raise ResumeStateConflict
        parsed = self._capabilities.parse(raw_capability)
        if parsed is None:
            raise GuestCapabilityRejected
        guest_id, secret = parsed
        async with self._uow() as uow:
            guest = await uow.get_guest_session(guest_id)
        if guest is None or not self._capabilities.verify(guest.capability_hash, secret):
            raise GuestCapabilityRejected
        if guest.claimed_by_user_id is not None:
            if guest.claimed_by_user_id != user_id or guest.claimed_document_id != document_id:
                raise GuestCapabilityRejected
            return await self.get_document(OwnerScope(user_id=user_id), document_id)
        if not guest.active_at(self._clock.now()):
            raise GuestCapabilityRejected
        guest_scope = OwnerScope(guest_session_id=guest.id)
        async with self._uow() as uow:
            document = await uow.get_document(guest_scope, document_id)
            artifacts = await uow.list_artifacts(guest_scope, document_id)
            analysis = await uow.get_latest_analysis_for_document(guest_scope, document_id)
            active_jobs = await uow.has_active_jobs(guest_scope, document_id)
        if document is None:
            raise ResumeResourceNotFound
        if document.status != DocumentStatus.READY or analysis is None or active_jobs:
            raise ResumeStateConflict
        new_scope = OwnerScope(user_id=user_id)
        original_old_key = document.quarantine_object_key
        original_new_key = _object_key("quarantine", new_scope, uuid4())
        copied = tuple(
            (artifact.object_key, _object_key("derivatives", new_scope, uuid4()))
            for artifact in artifacts
        )
        planned_keys = (original_new_key, *(new for _, new in copied))
        claim_now = self._clock.now()
        planned_cleanups = tuple(
            _new_object_cleanup(
                new_scope,
                key,
                ObjectCleanupPurpose.CLAIM_COMPENSATION,
                claim_now,
                claim_now + timedelta(seconds=self._policy.claim_cleanup_grace_seconds),
                self._policy.max_object_cleanup_attempts,
            )
            for key in planned_keys
        )
        # Persist compensation before the first copy. If this process disappears or a
        # commit result is ambiguous, maintenance decides safely from the task state.
        async with self._uow() as uow:
            for cleanup in planned_cleanups:
                await uow.add_object_cleanup(cleanup)
            await uow.commit()
        try:
            await self._storage.copy(original_old_key, original_new_key)
            for old_key, new_key in copied:
                await self._storage.copy(old_key, new_key)
        except BaseException:
            with suppress(Exception):
                await _attempt_object_cleanup_batch(
                    self._uow, self._storage, self._clock, planned_cleanups
                )
            raise
        source_cleanups = tuple(
            _new_object_cleanup(
                new_scope,
                key,
                ObjectCleanupPurpose.CLAIM_SOURCE,
                claim_now,
                claim_now,
                self._policy.max_object_cleanup_attempts,
            )
            for key in (original_old_key, *(old for old, _ in copied))
        )
        async with self._uow() as uow:
            await uow.lock_intake_admission(new_scope)
            if (
                await uow.count_active_intakes(new_scope, self._clock.now())
                >= self._policy.max_registered_documents
            ):
                raise ResumeStateConflict
            locked = await uow.get_document(guest_scope, document_id, for_update=True)
            if locked is None:
                raise ResumeResourceNotFound
            if locked.status != DocumentStatus.READY:
                raise ResumeStateConflict
            if await uow.get_latest_analysis_for_document(guest_scope, document_id) is None:
                raise ResumeStateConflict
            if await uow.has_active_jobs(guest_scope, document_id):
                raise ResumeStateConflict
            locked.quarantine_object_key = original_new_key
            locked.retention_expires_at = None
            locked.updated_at = self._clock.now()
            locked.version += 1
            await uow.save_document(locked)
            locked_artifacts = await uow.list_artifacts(guest_scope, document_id)
            by_old = {old: new for old, new in copied}
            for artifact in locked_artifacts:
                artifact.object_key = by_old[artifact.object_key]
                await uow.save_artifact(artifact)
            await uow.claim_guest_resources(
                guest_scope._guest_id, user_id, document_id, self._clock.now()
            )
            for cleanup in planned_cleanups:
                cleanup.cancel(self._clock.now())
                await uow.save_object_cleanup(cleanup)
            for cleanup in source_cleanups:
                await uow.add_object_cleanup(cleanup)
            await uow.add_audit(
                _audit(
                    new_scope,
                    "guest_document.claimed",
                    "succeeded",
                    "document",
                    document_id,
                    context,
                    self._clock.now(),
                    {"policy_version": command.policy_version[:40]},
                )
            )
            await uow.commit()
        with suppress(Exception):
            await _attempt_object_cleanup_batch(
                self._uow, self._storage, self._clock, source_cleanups
            )
        return await self.get_document(new_scope, document_id)


class ResumeJobFailureRecorder:
    """Minimal DB+clock use case for failures before provider assembly succeeds."""

    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        execution_lease_seconds: int = 330,
    ) -> None:
        if execution_lease_seconds < 1:
            raise ValueError("execution lease must be positive")
        self._uow = unit_of_work
        self._clock = clock
        self._execution_lease_seconds = execution_lease_seconds

    async def record_task_failure(
        self,
        job_id: UUID,
        trace_id: str,
        safe_error_code: str,
        *,
        retryable: bool,
        exhausted: bool = False,
        execution_token: str | None = None,
    ) -> ProcessingOutcome:
        return await _record_job_failure(
            self._uow,
            self._clock,
            self._execution_lease_seconds,
            job_id,
            trace_id,
            safe_error_code,
            retryable=retryable,
            exhausted=exhausted,
            execution_token=execution_token,
        )


class ResumeHealthProcessor:
    """Worker-facing idempotent processor; task payloads contain IDs and trace only."""

    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        storage: ObjectStorage,
        scanner: MalwareScanner,
        extractor: DocumentExtractor,
        limits: DocumentLimits,
        semantic_parser: ResumeParserProvider | None = None,
        ocr: OcrProvider | None = None,
        execution_lease_seconds: int = 330,
        upload_cleanup_grace_seconds: int = 900,
        max_object_cleanup_attempts: int = 10,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._storage = storage
        self._scanner = scanner
        self._extractor = extractor
        self._limits = limits
        self._semantic_parser = semantic_parser
        self._ocr = ocr
        if (
            execution_lease_seconds < 1
            or upload_cleanup_grace_seconds < 1
            or max_object_cleanup_attempts < 1
        ):
            raise ValueError("processor lease and cleanup policy must be positive")
        self._execution_lease_seconds = execution_lease_seconds
        self._upload_cleanup_grace_seconds = upload_cleanup_grace_seconds
        self._max_object_cleanup_attempts = max_object_cleanup_attempts
        self._limits.temp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._limits.temp_root.is_symlink():
            raise ValueError("temporary root must not be a symbolic link")

    async def process_job(
        self, job_id: UUID, trace_id: str, execution_token: str | None = None
    ) -> ProcessingOutcome:
        del trace_id  # durable job trace remains authoritative; never attach document content.
        normalized_token = _normalize_execution_token(execution_token, job_id)
        token_hash = sha256(normalized_token.encode()).digest()
        job, claimed = await self._start(job_id, token_hash)
        if not claimed:
            if (
                job.status == JobStatus.RUNNING
                and job.lease_expires_at is not None
                and job.lease_expires_at > self._clock.now()
            ):
                return ProcessingOutcome(
                    job.id,
                    JobStatus.RUNNING,
                    True,
                    "execution_lease_active",
                )
            return _outcome(job)
        try:
            if job.kind == JobKind.PARSE:
                await self._parse(job, token_hash)
            elif job.kind == JobKind.ANALYZE:
                await self._analyze(job, token_hash)
            elif job.kind == JobKind.DELETE:
                await self._delete(job, token_hash)
            else:
                raise UnsafeDocument("unsupported_job_kind")
        except ProcessingCancelled:
            return await self.record_task_failure(
                job.id,
                job.trace_id,
                "processing_cancelled",
                retryable=False,
                execution_token=normalized_token,
            )
        except UnsafeDocument as exc:
            return await self.record_task_failure(
                job.id,
                job.trace_id,
                exc.code,
                retryable=False,
                execution_token=normalized_token,
            )
        except RetryableProcessingFailure as exc:
            exhausted = job.attempts >= job.max_attempts
            return await self.record_task_failure(
                job.id,
                job.trace_id,
                exc.code,
                retryable=True,
                exhausted=exhausted,
                execution_token=normalized_token,
            )
        except Exception:
            exhausted = job.attempts >= job.max_attempts
            return await self.record_task_failure(
                job.id,
                job.trace_id,
                "processing_failed",
                retryable=True,
                exhausted=exhausted,
                execution_token=normalized_token,
            )
        async with self._uow() as uow:
            completed = await uow.get_job_system(job.id)
        if completed is None:
            raise ResumeResourceNotFound
        return _outcome(completed)

    async def record_task_failure(
        self,
        job_id: UUID,
        trace_id: str,
        safe_error_code: str,
        *,
        retryable: bool,
        exhausted: bool = False,
        execution_token: str | None = None,
    ) -> ProcessingOutcome:
        return await _record_job_failure(
            self._uow,
            self._clock,
            self._execution_lease_seconds,
            job_id,
            trace_id,
            safe_error_code,
            retryable=retryable,
            exhausted=exhausted,
            execution_token=execution_token,
        )

    async def _start(self, job_id: UUID, token_hash: bytes) -> tuple[ProcessingJob, bool]:
        now = self._clock.now()
        lease_expires_at = now + timedelta(seconds=self._execution_lease_seconds)
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id, for_update=True)
            if job is None:
                raise ResumeResourceNotFound
            if job.terminal:
                return job, False
            if job.status == JobStatus.RUNNING:
                if job.lease_expires_at is not None and job.lease_expires_at > now:
                    return job, False
                document = await uow.get_document_system(job.document_id, for_update=True)
                if document is None or document.owner != job.owner:
                    raise ResumeResourceNotFound
                if job.attempts >= job.max_attempts:
                    job.fail("execution_lease_expired", True, now, exhausted=True)
                    if job.kind == JobKind.PARSE:
                        document.status = DocumentStatus.REJECTED
                    elif job.kind == JobKind.ANALYZE:
                        document.status = DocumentStatus.READY
                    else:
                        document.status = DocumentStatus.FAILED
                    document.safe_error_code = (
                        None if job.kind == JobKind.ANALYZE else "execution_lease_expired"
                    )
                    document.updated_at = now
                    document.version += 1
                    await uow.save_document(document)
                    await uow.save_job(job)
                    await uow.add_audit(
                        _audit(
                            job.owner,
                            "processing_job.failed",
                            "failed",
                            "processing_job",
                            job.id,
                            ResumeRequestContext("worker", job.trace_id),
                            now,
                            {"safe_error_code": "execution_lease_expired"},
                        )
                    )
                    await uow.commit()
                    return job, False
                job.acquire_execution_lease(token_hash, lease_expires_at, now, recovered=True)
                await uow.save_job(job)
                await uow.commit()
                return job, True
            job.start(now)
            document = await uow.get_document_system(job.document_id, for_update=True)
            if document is None or document.owner != job.owner:
                raise ResumeResourceNotFound
            if job.status == JobStatus.CANCELLED:
                await uow.save_job(job)
                await uow.commit()
                return job, False
            job.acquire_execution_lease(token_hash, lease_expires_at, now)
            if job.kind == JobKind.PARSE:
                document.status = DocumentStatus.PROCESSING
                document.updated_at = now
                document.version += 1
                await uow.save_document(document)
            await uow.save_job(job)
            await uow.commit()
        return job, True

    async def _parse(self, job: ProcessingJob, token_hash: bytes) -> None:
        document = await self._document(job)
        with tempfile.TemporaryDirectory(
            prefix=f"rezumi-{uuid4().hex}-", dir=self._limits.temp_root
        ) as directory:
            path = Path(directory) / "source.bin"
            digest = await self._storage.download(
                document.quarantine_object_key, path, self._limits.max_upload_bytes
            )
            await self._advance(job.id, ProcessingStage.MALWARE_SCAN, 20, token_hash)
            scan = await self._scanner.scan(path)
            if scan.infected:
                raise UnsafeDocument("malware_detected")
            if not scan.clean:
                raise RetryableProcessingFailure("malware_scanner_error")
            await self._advance(job.id, ProcessingStage.EXTRACTION, 40, token_hash)
            extraction = await self._extractor.extract(
                path, document.media_type.value, self._limits
            )
            if extraction.image_only and self._ocr is not None:
                ocr_result = await self._ocr.extract(path, document.media_type.value, self._limits)
                if ocr_result is not None:
                    extraction = ocr_result
        await self._advance(job.id, ProcessingStage.CANONICALIZATION, 70, token_hash)
        if len(extraction.reading_order) > self._limits.max_extracted_blocks:
            raise UnsafeDocument("extracted_block_limit_exceeded")
        if len(extraction.plain_text) > self._limits.max_extracted_characters:
            raise UnsafeDocument("extracted_text_limit_exceeded")
        canonical = _canonicalize(document.id, extraction)
        if self._semantic_parser is not None:
            semantics = await self._semantic_parser.parse(document.id, canonical, digest.hex())
            try:
                validate_parser_semantics(canonical, semantics, digest.hex())
            except ValueError as exc:
                raise UnsafeDocument("semantic_parser_invalid_output") from exc
            canonical = replace(
                canonical,
                schema_version="canonical-resume/2.0.0",
                source_sections=canonical.sections,
                semantics=semantics,
            )
        plain_bytes = extraction.plain_text.encode("utf-8")
        reading_bytes = json.dumps(
            [_block_to_json(item) for item in extraction.reading_order],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        canonical_bytes = json.dumps(
            canonical.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if any(
            len(value) > self._limits.max_serialized_artifact_bytes
            for value in (plain_bytes, reading_bytes, canonical_bytes)
        ):
            raise UnsafeDocument("extracted_artifact_limit_exceeded")
        now = self._clock.now()
        plain_artifact = _artifact(document, ArtifactKind.PLAIN_TEXT, plain_bytes, now)
        reading_artifact = _artifact(document, ArtifactKind.READING_ORDER, reading_bytes, now)
        committed = False
        try:
            await self._storage.put_bytes(
                plain_artifact.object_key, plain_bytes, "text/plain; charset=utf-8"
            )
            await self._storage.put_bytes(
                reading_artifact.object_key, reading_bytes, "application/json"
            )
            snapshot = CanonicalSnapshot(
                id=uuid4(),
                document_id=document.id,
                owner=document.owner,
                revision=1,
                resume=canonical,
                plain_text_sha256=sha256(plain_bytes).digest(),
                parser_version=extraction.parser_version,
                created_at=now,
            )
            async with self._uow() as uow:
                locked_job = await uow.get_job_system(job.id, for_update=True)
                locked_document = await uow.get_document_system(document.id, for_update=True)
                if locked_job is None or locked_document is None:
                    raise ResumeResourceNotFound
                _ensure_execution(locked_job, token_hash)
                _ensure_not_cancelled(locked_job)
                if (
                    locked_document.owner != document.owner
                    or locked_document.status != DocumentStatus.PROCESSING
                    or locked_document.version != document.version
                ):
                    raise ProcessingCancelled
                locked_document.content_sha256 = digest
                locked_document.page_count = extraction.page_count
                locked_document.malware_status = MalwareStatus.CLEAN
                locked_document.status = DocumentStatus.READY
                locked_document.safe_error_code = None
                locked_document.updated_at = now
                locked_document.version += 1
                locked_job.result_id = document.id
                locked_job.succeed(now)
                await uow.add_artifact(plain_artifact)
                await uow.add_artifact(reading_artifact)
                await uow.add_snapshot(snapshot)
                await uow.save_document(locked_document)
                await uow.save_job(locked_job)
                await uow.add_audit(
                    _audit(
                        job.owner,
                        "document.parsed",
                        "succeeded",
                        "document",
                        document.id,
                        ResumeRequestContext("worker", job.trace_id),
                        now,
                    )
                )
                await uow.commit()
                committed = True
        finally:
            if not committed:
                await self._delete_uncommitted_artifacts(
                    document,
                    (plain_artifact.object_key, reading_artifact.object_key),
                )

    async def _delete_uncommitted_artifacts(
        self, document: SourceDocument, candidate_keys: tuple[str, ...]
    ) -> None:
        """Compensate writes without deleting a replacement worker's committed output."""
        try:
            async with self._uow() as uow:
                committed_keys = {
                    item.object_key
                    for item in await uow.list_artifacts(document.owner, document.id)
                }
        except Exception:
            # A repository outage makes deletion unsafe: deterministic keys may already
            # have been committed by a lease successor. Retention/deletion owns cleanup.
            return
        await asyncio.gather(
            *(self._storage.delete(key) for key in candidate_keys if key not in committed_keys),
            return_exceptions=True,
        )

    async def _analyze(self, job: ProcessingJob, token_hash: bytes) -> None:
        await self._advance(job.id, ProcessingStage.ANALYSIS, 50, token_hash)
        now = self._clock.now()
        async with self._uow() as uow:
            document = await uow.get_document_system(job.document_id)
            if document is None or document.owner != job.owner:
                raise ResumeResourceNotFound
            snapshot = (
                await uow.get_snapshot(job.owner, job.input_snapshot_id)
                if job.input_snapshot_id is not None
                else None
            )
        if snapshot is None:
            raise ResumeStateConflict
        features = _features(snapshot.resume, document.page_count or 0)
        scored = score_resume_health(features)
        analysis_id = uuid4()
        analysis = ResumeHealthAnalysis(
            id=analysis_id,
            job_id=job.id,
            document_id=document.id,
            snapshot_id=snapshot.id,
            owner=document.owner,
            status=(
                AnalysisStatus.INSUFFICIENT_DATA
                if scored.raw_score_basis_points is None
                else AnalysisStatus.SUCCEEDED
            ),
            engine_version=scored.engine_version,
            configuration_version=scored.configuration_version,
            feature_schema_version=scored.feature_schema_version,
            feature_values=scored.feature_values,
            feature_set_hash=scored.feature_set_hash,
            raw_score_basis_points=scored.raw_score_basis_points,
            display_score=scored.display_score,
            computed_at=now,
        )
        components = tuple(
            ScoreComponent(
                id=uuid4(),
                analysis_id=analysis_id,
                code=item.code,
                weight_basis_points=item.weight_basis_points,
                score_basis_points=item.score_basis_points,
                contribution_basis_points=item.contribution_basis_points,
                explanation=item.explanation,
            )
            for item in scored.components
        )
        feature_contributions = tuple(
            FeatureContribution(
                id=uuid4(),
                analysis_id=analysis_id,
                component_code=item.component_code,
                feature_code=item.feature_code,
                feature_value_basis_points=item.feature_value_basis_points,
                weight_basis_points=item.weight_basis_points,
                contribution_basis_points=item.contribution_basis_points,
            )
            for item in scored.feature_contributions
        )
        findings = tuple(
            ResumeFinding(
                id=uuid4(),
                analysis_id=analysis_id,
                code=item.code,
                severity=FindingSeverity(item.severity),
                component_code=item.component_code,
                message=item.message,
                quick_win=item.quick_win,
                sort_order=index,
            )
            for index, item in enumerate(scored.findings)
        )
        async with self._uow() as uow:
            locked_job = await uow.get_job_system(job.id, for_update=True)
            locked_document = await uow.get_document_system(document.id, for_update=True)
            if locked_job is None or locked_document is None:
                raise ResumeResourceNotFound
            _ensure_execution(locked_job, token_hash)
            _ensure_not_cancelled(locked_job)
            if (
                locked_document.owner != document.owner
                or locked_document.status != DocumentStatus.READY
                or locked_document.version != document.version
            ):
                raise ProcessingCancelled
            await uow.add_analysis(analysis, components, feature_contributions, findings)
            locked_job.result_id = analysis.id
            locked_job.succeed(now)
            await uow.save_job(locked_job)
            await uow.add_audit(
                _audit(
                    job.owner,
                    "resume_health.completed",
                    "succeeded",
                    "analysis",
                    analysis.id,
                    ResumeRequestContext("worker", job.trace_id),
                    now,
                    {"status": analysis.status.value},
                )
            )
            await uow.commit()

    async def _delete(self, job: ProcessingJob, token_hash: bytes) -> None:
        await self._advance(job.id, ProcessingStage.CLEANUP, 30, token_hash)
        document = await self._document(job)
        async with self._uow() as uow:
            artifacts = await uow.list_artifacts(job.owner, document.id)
            upload = await uow.get_upload(job.owner, document.upload_id)
        if upload is None:
            raise ResumeStateConflict
        await self._storage.delete(document.quarantine_object_key)
        await self._storage.delete(upload.staging_object_key)
        for artifact in artifacts:
            await self._storage.delete(artifact.object_key)
        now = self._clock.now()
        async with self._uow() as uow:
            locked_job = await uow.get_job_system(job.id, for_update=True)
            locked_document = await uow.get_document_system(document.id, for_update=True)
            locked_upload = await uow.get_upload(job.owner, document.upload_id, for_update=True)
            if locked_job is None or locked_document is None or locked_upload is None:
                raise ResumeResourceNotFound
            _ensure_execution(locked_job, token_hash)
            if (
                locked_document.owner != document.owner
                or locked_document.status != DocumentStatus.DELETING
                or locked_document.version != document.version
            ):
                raise ProcessingCancelled
            await uow.purge_document_content(job.owner, document.id, job.id)
            locked_document.display_filename = "deleted"
            locked_document.quarantine_object_key = f"deleted/{document.id}"
            locked_document.content_sha256 = None
            locked_document.page_count = None
            locked_document.status = DocumentStatus.DELETED
            locked_document.deleted_at = now
            locked_document.updated_at = now
            locked_document.version += 1
            locked_upload.display_filename = "deleted"
            locked_upload.status = UploadStatus.DELETED
            locked_upload.staging_cleaned_at = now
            await uow.add_object_cleanup(
                _new_object_cleanup(
                    job.owner,
                    upload.staging_object_key,
                    ObjectCleanupPurpose.UPLOAD_STAGING_BACKSTOP,
                    now,
                    max(
                        upload.expires_at + timedelta(seconds=self._upload_cleanup_grace_seconds),
                        now + timedelta(seconds=self._upload_cleanup_grace_seconds),
                    ),
                    self._max_object_cleanup_attempts,
                )
            )
            locked_job.result_id = document.id
            locked_job.succeed(now)
            await uow.save_document(locked_document)
            await uow.save_upload(locked_upload)
            await uow.save_job(locked_job)
            await uow.add_audit(
                _audit(
                    job.owner,
                    "document.deleted",
                    "succeeded",
                    "document",
                    document.id,
                    ResumeRequestContext("worker", job.trace_id),
                    now,
                )
            )
            await uow.commit()

    async def _document(self, job: ProcessingJob) -> SourceDocument:
        async with self._uow() as uow:
            document = await uow.get_document_system(job.document_id)
        if document is None or document.owner != job.owner:
            raise ResumeResourceNotFound
        return document

    async def _advance(
        self, job_id: UUID, stage: ProcessingStage, progress: int, token_hash: bytes
    ) -> None:
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id, for_update=True)
            if job is None:
                raise ResumeResourceNotFound
            _ensure_execution(job, token_hash)
            _ensure_not_cancelled(job)
            now = self._clock.now()
            job.advance(stage, progress, now)
            job.refresh_execution_lease(
                token_hash,
                now + timedelta(seconds=self._execution_lease_seconds),
                now,
            )
            await uow.save_job(job)
            await uow.commit()


class OutboxDispatcher:
    def __init__(
        self, *, unit_of_work: UnitOfWorkFactory, publisher: JobPublisher, clock: Clock
    ) -> None:
        self._uow = unit_of_work
        self._publisher = publisher
        self._clock = clock

    async def dispatch_pending(self, limit: int = 100) -> OutboxDispatchResult:
        if not 1 <= limit <= 500:
            raise ValueError("outbox dispatch limit must be between 1 and 500")
        published = 0
        failed = 0
        dead_lettered = 0
        now = self._clock.now()
        async with self._uow() as uow:
            messages = await uow.list_pending_outbox(now, limit)
            for message in messages:
                try:
                    await self._publisher.publish(
                        message.task_name, message.job_id, message.trace_id
                    )
                except Exception:
                    delay = min(900, 5 * (2 ** min(message.attempts, 8)))
                    message.fail(
                        "task_publish_failed",
                        now,
                        now + timedelta(seconds=delay),
                    )
                    if message.dead_lettered_at is not None:
                        await self._dead_letter_job(uow, message, now)
                        dead_lettered += 1
                    failed += 1
                else:
                    message.publish(now)
                    published += 1
                await uow.save_outbox(message)
            await uow.commit()
        return OutboxDispatchResult(
            published=published,
            failed=failed,
            dead_lettered=dead_lettered,
        )

    async def _dead_letter_job(
        self, uow: ResumeUnitOfWork, message: OutboxMessage, now: Any
    ) -> None:
        job = await uow.get_job_system(message.job_id, for_update=True)
        if job is None or job.terminal or job.status == JobStatus.RUNNING:
            return
        job.fail("task_publish_failed", True, now, exhausted=True)
        document = await uow.get_document_system(job.document_id, for_update=True)
        if document is not None and document.status != DocumentStatus.DELETED:
            if job.kind == JobKind.PARSE:
                document.status = DocumentStatus.REJECTED
                document.safe_error_code = "task_publish_failed"
            elif job.kind == JobKind.ANALYZE:
                document.status = DocumentStatus.READY
                document.safe_error_code = None
            else:
                document.status = DocumentStatus.FAILED
                document.safe_error_code = "task_publish_failed"
            document.updated_at = now
            document.version += 1
            await uow.save_document(document)
        await uow.save_job(job)
        await uow.add_audit(
            _audit(
                job.owner,
                "processing_job.publish_dead_lettered",
                "failed",
                "processing_job",
                job.id,
                ResumeRequestContext("outbox", job.trace_id),
                now,
                {"safe_error_code": "task_publish_failed"},
            )
        )


class ResumeJobReconciler:
    """Scheduled recovery for deliveries lost after durable outbox publication."""

    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        stale_after_seconds: int = 300,
    ) -> None:
        if stale_after_seconds < 1:
            raise ValueError("job reconciliation staleness must be positive")
        self._uow = unit_of_work
        self._clock = clock
        self._stale_after_seconds = stale_after_seconds

    async def reconcile_stale(self, limit: int = 100) -> JobReconciliationResult:
        if not 1 <= limit <= 500:
            raise ValueError("job reconciliation limit must be between 1 and 500")
        now = self._clock.now()
        stale_before = now - timedelta(seconds=self._stale_after_seconds)
        requeued = 0
        dead_lettered = 0
        async with self._uow() as uow:
            jobs = await uow.list_reconcilable_jobs(now, stale_before, limit)
            for job in jobs:
                if (
                    job.recovery_attempts >= job.max_recovery_attempts
                    or job.attempts >= job.max_attempts
                ):
                    await self._dead_letter(uow, job, now)
                    dead_lettered += 1
                    continue
                if job.status == JobStatus.RUNNING:
                    await self._fence_expired_execution(uow, job, now)
                job.recovery_attempts += 1
                job.next_recovery_at = now + timedelta(seconds=self._stale_after_seconds)
                job.updated_at = now
                job.version += 1
                await uow.save_job(job)
                await uow.add_outbox(_outbox(job, now, generation=job.recovery_attempts))
                await uow.add_audit(
                    _audit(
                        job.owner,
                        "processing_job.requeued",
                        "accepted",
                        "processing_job",
                        job.id,
                        ResumeRequestContext("reconciler", job.trace_id),
                        now,
                        {"recovery_attempt": str(job.recovery_attempts)},
                    )
                )
                requeued += 1
            await uow.commit()
        return JobReconciliationResult(requeued=requeued, dead_lettered=dead_lettered)

    async def _fence_expired_execution(
        self, uow: ResumeUnitOfWork, job: ProcessingJob, now: Any
    ) -> None:
        """Invalidate the old delivery before making a replacement visible."""
        job.fail("execution_lease_expired", True, now)
        document = await uow.get_document_system(job.document_id, for_update=True)
        if document is None or document.status == DocumentStatus.DELETED:
            return
        if job.kind == JobKind.PARSE:
            document.status = DocumentStatus.QUARANTINED
        elif job.kind == JobKind.ANALYZE:
            document.status = DocumentStatus.READY
        document.safe_error_code = (
            None if job.kind == JobKind.ANALYZE else "execution_lease_expired"
        )
        document.updated_at = now
        document.version += 1
        await uow.save_document(document)

    async def _dead_letter(self, uow: ResumeUnitOfWork, job: ProcessingJob, now: Any) -> None:
        job.fail("job_recovery_exhausted", True, now, exhausted=True)
        document = await uow.get_document_system(job.document_id, for_update=True)
        if document is not None and document.status != DocumentStatus.DELETED:
            if job.kind == JobKind.PARSE:
                document.status = DocumentStatus.REJECTED
                document.safe_error_code = "job_recovery_exhausted"
            elif job.kind == JobKind.ANALYZE:
                document.status = DocumentStatus.READY
                document.safe_error_code = None
            else:
                document.status = DocumentStatus.FAILED
                document.safe_error_code = "job_recovery_exhausted"
            document.updated_at = now
            document.version += 1
            await uow.save_document(document)
        await uow.save_job(job)
        await uow.add_audit(
            _audit(
                job.owner,
                "processing_job.recovery_dead_lettered",
                "failed",
                "processing_job",
                job.id,
                ResumeRequestContext("reconciler", job.trace_id),
                now,
                {"safe_error_code": "job_recovery_exhausted"},
            )
        )


class ResumeMaintenance:
    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        storage: ObjectStorage,
        policy: ResumeHealthPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._storage = storage
        self._policy = policy or ResumeHealthPolicy()

    async def cleanup_expired(self, limit: int = 100) -> CleanupResult:
        if not 1 <= limit <= 500:
            raise ValueError("cleanup limit must be between 1 and 500")
        now = self._clock.now()
        cleanup_completed = 0
        cleanup_failed = 0
        cleanup_dead_lettered = 0
        async with self._uow() as uow:
            object_cleanups = await uow.list_due_object_cleanups(now, limit)
            uploads = await uow.list_expired_uploads(
                now - timedelta(seconds=self._policy.upload_cleanup_grace_seconds), limit
            )
            documents = await uow.list_expired_guest_documents(now, limit)
            guests = await uow.list_expired_guests(now, limit)
            for cleanup in object_cleanups:
                result = await _attempt_object_cleanup(self._storage, cleanup, now)
                cleanup_completed += result == "completed"
                cleanup_failed += result == "failed"
                cleanup_dead_lettered += result == "dead_lettered"
                await uow.save_object_cleanup(cleanup)
            for upload in uploads:
                staging_cleanup = _new_object_cleanup(
                    upload.owner,
                    upload.staging_object_key,
                    ObjectCleanupPurpose.UPLOAD_STAGING_BACKSTOP,
                    now,
                    now,
                    self._policy.max_object_cleanup_attempts,
                )
                await uow.add_object_cleanup(staging_cleanup)
                result = await _attempt_object_cleanup(self._storage, staging_cleanup, now)
                cleanup_completed += result == "completed"
                cleanup_failed += result == "failed"
                cleanup_dead_lettered += result == "dead_lettered"
                await uow.save_object_cleanup(staging_cleanup)
                upload.staging_cleaned_at = now
                if upload.status != UploadStatus.FINALIZED:
                    quarantine_cleanup = _new_object_cleanup(
                        upload.owner,
                        _object_key("quarantine", upload.owner, upload.id),
                        ObjectCleanupPurpose.UPLOAD_QUARANTINE_CLEANUP,
                        now,
                        now,
                        self._policy.max_object_cleanup_attempts,
                    )
                    await uow.add_object_cleanup(quarantine_cleanup)
                    result = await _attempt_object_cleanup(self._storage, quarantine_cleanup, now)
                    cleanup_completed += result == "completed"
                    cleanup_failed += result == "failed"
                    cleanup_dead_lettered += result == "dead_lettered"
                    await uow.save_object_cleanup(quarantine_cleanup)
                    upload.display_filename = "deleted"
                    upload.status = UploadStatus.DELETED
                await uow.add_object_cleanup(
                    _new_object_cleanup(
                        upload.owner,
                        upload.staging_object_key,
                        ObjectCleanupPurpose.UPLOAD_STAGING_BACKSTOP,
                        now,
                        now + timedelta(seconds=self._policy.upload_cleanup_grace_seconds),
                        self._policy.max_object_cleanup_attempts,
                    )
                )
                await uow.save_upload(upload)
            queued = 0
            for document in documents:
                if await uow.has_active_jobs(document.owner, document.id):
                    continue
                document.status = DocumentStatus.DELETING
                document.updated_at = now
                document.version += 1
                job = _new_job(
                    document,
                    JobKind.DELETE,
                    f"retention:{document.id}:{document.version}",
                    _request_hash("retention-delete", document.id),
                    document.id.hex,
                    now,
                    3,
                )
                await uow.save_document(document)
                await uow.add_job(job)
                await uow.add_outbox(_outbox(job, now))
                queued += 1
            for guest in guests:
                guest.revoked_at = now
                await uow.save_guest_session(guest)
            await uow.commit()
        return CleanupResult(
            len(uploads),
            queued,
            len(guests),
            cleanup_completed,
            cleanup_failed,
            cleanup_dead_lettered,
        )

    async def purge_expired_guest_sessions(self, limit: int = 100) -> CleanupResult:
        """Stable worker entry point; queues durable deletion before revoking capabilities."""
        return await self.cleanup_expired(limit)


async def _restore_promoted_object(
    storage: ObjectStorage, staging_key: str, quarantine_key: str
) -> None:
    """Discard only an uncommitted copy; copy-only promotion preserves staging."""
    del staging_key
    try:
        await storage.delete(quarantine_key)
    except Exception:
        return


def _new_job(
    document: SourceDocument,
    kind: JobKind,
    idempotency_key: str,
    request_hash: bytes,
    trace_id: str,
    now: Any,
    max_attempts: int,
    *,
    input_snapshot_id: UUID | None = None,
) -> ProcessingJob:
    return ProcessingJob(
        id=uuid4(),
        document_id=document.id,
        owner=document.owner,
        kind=kind,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        trace_id=trace_id[:64] or "unavailable",
        status=JobStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
        progress=None,
        attempts=0,
        max_attempts=max_attempts,
        created_at=now,
        updated_at=now,
        input_snapshot_id=input_snapshot_id,
    )


def _outbox(job: ProcessingJob, now: Any, *, generation: int = 0) -> OutboxMessage:
    return OutboxMessage(
        id=uuid4(),
        job_id=job.id,
        task_name=PROCESS_RESUME_TASK,
        trace_id=job.trace_id,
        created_at=now,
        next_attempt_at=now,
        generation=generation,
    )


def _new_object_cleanup(
    owner: OwnerScope,
    object_key: str,
    purpose: ObjectCleanupPurpose,
    created_at: Any,
    not_before: Any,
    max_attempts: int,
) -> StorageObjectCleanup:
    return StorageObjectCleanup(
        id=uuid4(),
        owner=owner,
        object_key=object_key,
        purpose=purpose,
        not_before=not_before,
        created_at=created_at,
        max_attempts=max_attempts,
    )


async def _attempt_object_cleanup_batch(
    unit_of_work: UnitOfWorkFactory,
    storage: ObjectStorage,
    clock: Clock,
    cleanups: tuple[StorageObjectCleanup, ...],
) -> None:
    now = clock.now()
    changed: list[StorageObjectCleanup] = []
    for cleanup in cleanups:
        if cleanup.terminal:
            continue
        await _attempt_object_cleanup(storage, cleanup, now)
        changed.append(cleanup)
    if not changed:
        return
    async with unit_of_work() as uow:
        for cleanup in changed:
            await uow.save_object_cleanup(cleanup)
        await uow.commit()


async def _attempt_object_cleanup(
    storage: ObjectStorage, cleanup: StorageObjectCleanup, now: Any
) -> str:
    try:
        await storage.delete(cleanup.object_key)
    except Exception:
        delay = min(3_600, 60 * (2 ** min(cleanup.attempts, 5)))
        cleanup.fail(
            "object_storage_unavailable",
            now,
            now + timedelta(seconds=delay),
        )
        return "dead_lettered" if cleanup.dead_lettered_at is not None else "failed"
    cleanup.complete(now)
    return "completed"


async def _record_job_failure(
    unit_of_work: UnitOfWorkFactory,
    clock: Clock,
    execution_lease_seconds: int,
    job_id: UUID,
    trace_id: str,
    safe_error_code: str,
    *,
    retryable: bool,
    exhausted: bool,
    execution_token: str | None,
) -> ProcessingOutcome:
    del trace_id
    if not re.fullmatch(r"[a-z0-9_]{1,80}", safe_error_code):
        safe_error_code = "processing_failed"
    now = clock.now()
    async with unit_of_work() as uow:
        job = await uow.get_job_system(job_id, for_update=True)
        if job is None:
            raise ResumeResourceNotFound
        if job.terminal:
            return _outcome(job)
        if execution_token is not None:
            token_hash = sha256(
                _normalize_execution_token(execution_token, job.id).encode()
            ).digest()
            if job.status == JobStatus.RUNNING:
                if job.execution_token_hash != token_hash:
                    return _outcome(job)
            elif job.status in {JobStatus.QUEUED, JobStatus.FAILED}:
                job.start(now)
                if _job_is_terminal(job):
                    await uow.save_job(job)
                    await uow.commit()
                    return _outcome(job)
                job.acquire_execution_lease(
                    token_hash,
                    now + timedelta(seconds=execution_lease_seconds),
                    now,
                )
            else:
                return _outcome(job)
        elif job.status == JobStatus.RUNNING and job.execution_token_hash is not None:
            return _outcome(job)
        if safe_error_code == "processing_cancelled":
            job.cancel(now)
        else:
            job.fail(
                safe_error_code,
                retryable,
                now,
                exhausted=exhausted or (retryable and job.attempts >= job.max_attempts),
            )
        document = await uow.get_document_system(job.document_id, for_update=True)
        if document is not None and document.status != DocumentStatus.DELETED:
            if safe_error_code == "malware_detected":
                document.malware_status = MalwareStatus.INFECTED
                document.status = DocumentStatus.REJECTED
            elif safe_error_code.startswith("malware_scanner_"):
                document.malware_status = MalwareStatus.UNAVAILABLE
                document.status = (
                    DocumentStatus.REJECTED
                    if job.status == JobStatus.DEAD_LETTERED or not retryable
                    else DocumentStatus.QUARANTINED
                )
            elif job.kind == JobKind.ANALYZE:
                document.status = DocumentStatus.READY
            elif not retryable or job.status == JobStatus.DEAD_LETTERED:
                document.status = (
                    DocumentStatus.REJECTED if job.kind == JobKind.PARSE else DocumentStatus.FAILED
                )
            elif job.kind == JobKind.PARSE:
                document.status = DocumentStatus.QUARANTINED
            document.safe_error_code = None if job.kind == JobKind.ANALYZE else safe_error_code
            document.updated_at = now
            document.version += 1
            await uow.save_document(document)
        await uow.save_job(job)
        await uow.add_audit(
            _audit(
                job.owner,
                "processing_job.failed"
                if job.status != JobStatus.CANCELLED
                else "processing_job.cancelled",
                "cancelled" if job.status == JobStatus.CANCELLED else "failed",
                "processing_job",
                job.id,
                ResumeRequestContext("worker", job.trace_id),
                now,
                {"safe_error_code": safe_error_code},
            )
        )
        await uow.commit()
    return _outcome(job)


def _request_hash(*parts: object) -> bytes:
    return sha256("\x1f".join(str(item) for item in parts).encode()).digest()


def _validate_idempotency(value: str) -> None:
    if not _IDEMPOTENCY.fullmatch(value):
        raise ResumeStateConflict


def _validate_filename(value: str, media_type: ResumeMediaType) -> str:
    filename = value.strip()
    if (
        not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or any(ord(character) < 32 for character in filename)
    ):
        raise UploadRejected("invalid_filename")
    expected = ".pdf" if media_type == ResumeMediaType.PDF else ".docx"
    if not filename.casefold().endswith(expected):
        raise UploadRejected("filename_type_mismatch")
    return filename


def _validate_signature(prefix: bytes, media_type: ResumeMediaType) -> None:
    valid = (
        prefix.startswith(b"%PDF-")
        if media_type == ResumeMediaType.PDF
        else prefix.startswith(b"PK\x03\x04")
    )
    if not valid:
        raise UploadRejected("document_signature_mismatch")


async def _finalized_upload_replay(
    uow: ResumeUnitOfWork,
    scope: OwnerScope,
    upload_id: UUID,
    idempotency_key: str,
    request_hash: bytes,
) -> FinalizedUpload | None:
    existing = await uow.get_job_by_idempotency(scope, idempotency_key)
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise IdempotencyConflict
    upload = await uow.get_upload(scope, upload_id)
    if (
        upload is None
        or upload.status != UploadStatus.FINALIZED
        or upload.finalized_document_id != existing.document_id
    ):
        raise ResumeStateConflict
    document = await uow.get_document(scope, existing.document_id)
    if document is None:
        raise ResumeStateConflict
    return FinalizedUpload(document.id, existing.id, document.status, existing.status)


def _object_key(prefix: str, scope: OwnerScope, identifier: UUID) -> str:
    owner = _SAFE_KEY_PART.sub("", str(scope.owner_id))
    return f"{prefix}/{scope.kind}/{owner}/{identifier.hex}"


def _document_view(
    document: SourceDocument,
    current_snapshot_id: UUID | None = None,
    latest_analysis_id: UUID | None = None,
) -> DocumentView:
    return DocumentView(
        id=document.id,
        display_filename=document.display_filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        status=document.status,
        malware_status=document.malware_status,
        page_count=document.page_count,
        safe_error_code=document.safe_error_code,
        retention_expires_at=document.retention_expires_at,
        version=document.version,
        created_at=document.created_at,
        updated_at=document.updated_at,
        current_snapshot_id=current_snapshot_id,
        latest_analysis_id=latest_analysis_id,
    )


def _job_view(job: ProcessingJob) -> ProcessingJobView:
    return ProcessingJobView(
        id=job.id,
        document_id=job.document_id,
        kind=job.kind,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        safe_error_code=job.safe_error_code,
        retryable=job.retryable,
        cancellation_requested=job.cancellation_requested_at is not None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result_id=job.result_id,
    )


def _snapshot_view(snapshot: CanonicalSnapshot, original: CanonicalResume) -> CanonicalSnapshotView:
    return CanonicalSnapshotView(
        id=snapshot.id,
        document_id=snapshot.document_id,
        revision=snapshot.revision,
        resume=snapshot.resume,
        original_resume=original,
        parser_version=snapshot.parser_version,
        corrected_by_user=snapshot.corrected_by_user,
        created_at=snapshot.created_at,
        based_on_snapshot_id=snapshot.based_on_snapshot_id,
    )


def _analysis_view(
    analysis: ResumeHealthAnalysis,
    components: list[ScoreComponent],
    feature_contributions: list[FeatureContribution],
    findings: list[ResumeFinding],
) -> AnalysisView:
    return AnalysisView(
        id=analysis.id,
        document_id=analysis.document_id,
        snapshot_id=analysis.snapshot_id,
        status=analysis.status,
        engine_version=analysis.engine_version,
        configuration_version=analysis.configuration_version,
        feature_schema_version=analysis.feature_schema_version,
        feature_values=dict(analysis.feature_values),
        feature_set_hash=analysis.feature_set_hash,
        raw_score_basis_points=analysis.raw_score_basis_points,
        display_score=analysis.display_score,
        components=tuple(
            ScoreComponentView(
                item.code,
                item.weight_basis_points,
                item.score_basis_points,
                item.contribution_basis_points,
                item.explanation,
            )
            for item in components
        ),
        feature_contributions=tuple(
            FeatureContributionView(
                item.component_code,
                item.feature_code,
                item.feature_value_basis_points,
                item.weight_basis_points,
                item.contribution_basis_points,
            )
            for item in feature_contributions
        ),
        findings=tuple(
            FindingView(
                item.code,
                item.severity,
                item.component_code,
                item.message,
                item.quick_win,
                item.sort_order,
            )
            for item in findings
        ),
        computed_at=analysis.computed_at,
    )


def _outcome(job: ProcessingJob) -> ProcessingOutcome:
    return ProcessingOutcome(job.id, job.status, job.retryable, job.safe_error_code)


def _canonicalize(document_id: UUID, extraction: Any) -> CanonicalResume:
    sections: list[CanonicalSection] = []
    current_kind = SectionKind.OTHER
    current_title = "Resume content"
    current_blocks: list[CanonicalBlock] = []
    section_index = 0

    def flush() -> None:
        nonlocal section_index, current_blocks
        if not current_blocks:
            return
        sections.append(
            CanonicalSection(
                id=uuid5(_CANONICAL_NAMESPACE, f"{document_id}:section:{section_index}"),
                kind=current_kind,
                title=current_title,
                confidence_basis_points=9_000 if current_kind != SectionKind.OTHER else 6_000,
                blocks=tuple(current_blocks),
            )
        )
        section_index += 1
        current_blocks = []

    for index, item in enumerate(extraction.reading_order):
        normalized = item.text.strip().rstrip(":").casefold()
        section_kind = _SECTION_NAMES.get(normalized) if item.kind == "heading" else None
        if section_kind is not None:
            flush()
            current_kind = section_kind
            current_title = item.text.strip().rstrip(":")
            continue
        current_blocks.append(
            CanonicalBlock(
                id=uuid5(_CANONICAL_NAMESPACE, f"{document_id}:block:{index}"),
                kind=BlockKind(item.kind),
                text=item.text,
                confidence_basis_points=item.confidence_basis_points,
                spans=tuple(SourceSpan(span.page, span.start, span.end) for span in item.spans),
            )
        )
    flush()
    return CanonicalResume(
        schema_version="canonical-resume/1.0.0",
        sections=tuple(sections),
        warnings=tuple(extraction.warnings),
    )


def _features(resume: CanonicalResume, page_count: int) -> ResumeHealthFeatures:
    blocks = [block for section in resume.sections for block in section.blocks]
    bullets = [block for block in blocks if block.kind == BlockKind.BULLET]
    normalized = [" ".join(block.text.casefold().split()) for block in blocks]
    duplicates = len(normalized) - len(set(normalized))
    confidences = [block.confidence_basis_points for block in blocks]
    semantic_entities = (
        [
            entity
            for entity in resume.semantics.entities
            if entity.review_state is not SemanticReviewState.REMOVED
        ]
        if resume.semantics is not None
        else []
    )
    semantic_fields = [
        field
        for entity in semantic_entities
        for field in entity.fields
        if field.review_state is not SemanticReviewState.REMOVED
    ]
    parsed_semantic_fields = [
        field
        for field in semantic_fields
        if field.review_state is not SemanticReviewState.USER_ADDED
    ]
    date_fields = [field for field in semantic_fields if field.date_precision is not None]
    return ResumeHealthFeatures(
        text_characters=sum(len(block.text) for block in blocks),
        page_count=page_count,
        image_only="image_only_pdf" in resume.warnings,
        section_count=len(resume.sections),
        recognized_section_count=sum(
            section.kind != SectionKind.OTHER for section in resume.sections
        ),
        block_count=len(blocks),
        concise_block_count=sum(len(block.text) <= 240 for block in blocks),
        bullet_count=len(bullets),
        action_bullet_count=sum(bool(_ACTION_WORDS.search(block.text)) for block in bullets),
        outcome_bullet_count=sum(bool(_OUTCOME_WORDS.search(block.text)) for block in bullets),
        duplicate_block_count=duplicates,
        chronology_signal_count=sum(bool(_DATE_SIGNAL.search(block.text)) for block in blocks),
        warning_count=len(resume.warnings),
        reading_order_violation_count=sum("reading_order" in item for item in resume.warnings),
        average_confidence_basis_points=(
            sum(confidences) // len(confidences) if confidences else 0
        ),
        semantic_entity_count=len(semantic_entities),
        semantic_field_count=len(semantic_fields),
        parsed_semantic_field_count=len(parsed_semantic_fields),
        source_anchored_field_count=sum(bool(field.anchors) for field in parsed_semantic_fields),
        reviewed_semantic_field_count=sum(
            field.review_state is not SemanticReviewState.UNREVIEWED for field in semantic_fields
        ),
        date_field_count=len(date_fields),
        precise_date_field_count=sum(
            field.date_precision is not DatePrecision.UNKNOWN for field in date_fields
        ),
    )


def _artifact(
    document: SourceDocument, kind: ArtifactKind, value: bytes, now: Any
) -> DocumentArtifact:
    artifact_key_id = uuid5(_CANONICAL_NAMESPACE, f"{document.id}:artifact:{kind.value}")
    return DocumentArtifact(
        id=uuid4(),
        document_id=document.id,
        owner=document.owner,
        kind=kind,
        object_key=_object_key("derivatives", document.owner, artifact_key_id),
        size_bytes=len(value),
        sha256=sha256(value).digest(),
        created_at=now,
    )


def _block_to_json(block: ExtractedBlock) -> dict[str, Any]:
    return {
        "kind": block.kind,
        "text": block.text,
        "confidenceBasisPoints": block.confidence_basis_points,
        "spans": [
            {"page": span.page, "start": span.start, "end": span.end} for span in block.spans
        ],
    }


def _extracted_block(value: dict[str, Any]) -> ExtractedBlock:
    from rezumi.modules.resume_health.application.models import SourceSpanView

    return ExtractedBlock(
        kind=str(value["kind"]),
        text=str(value["text"]),
        confidence_basis_points=int(value["confidenceBasisPoints"]),
        spans=tuple(
            SourceSpanView(int(span["page"]), int(span["start"]), int(span["end"]))
            for span in value["spans"]
        ),
    )


def _ensure_not_cancelled(job: ProcessingJob) -> None:
    if job.cancellation_requested_at is not None or job.status == JobStatus.CANCELLED:
        raise ProcessingCancelled


def _job_is_terminal(job: ProcessingJob) -> bool:
    """Keep state-machine mutation checks opaque to static narrowing."""
    return job.terminal


def _ensure_execution(job: ProcessingJob, token_hash: bytes) -> None:
    if job.status != JobStatus.RUNNING or job.execution_token_hash != token_hash:
        raise ProcessingCancelled


def _normalize_execution_token(value: str | None, job_id: UUID) -> str:
    del job_id
    token = value or uuid4().hex
    if not _EXECUTION_TOKEN.fullmatch(token):
        raise ResumeStateConflict
    return token


def _audit(
    scope: OwnerScope,
    action: str,
    outcome: str,
    resource_type: str,
    resource_id: UUID,
    context: ResumeRequestContext | None,
    now: Any,
    safe_metadata: dict[str, str] | None = None,
) -> ResumeAuditEvent:
    return ResumeAuditEvent(
        id=uuid4(),
        owner=scope,
        action=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=context.request_id if context is not None else "unavailable",
        trace_id=context.trace_id if context is not None else "unavailable",
        safe_metadata=safe_metadata or {},
        created_at=now,
    )
