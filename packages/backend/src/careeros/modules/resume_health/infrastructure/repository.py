"""Async SQLAlchemy unit of work for the Resume Health module."""

from datetime import datetime
from types import TracebackType
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.resume_health.domain import (
    AnalysisStatus,
    ArtifactKind,
    CanonicalResume,
    CanonicalSnapshot,
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
    SourceDocument,
    StorageObjectCleanup,
    UploadIntent,
    UploadStatus,
)
from careeros.modules.resume_health.domain.errors import IdempotencyConflict, ResumeStateConflict
from careeros.modules.resume_health.infrastructure.models import (
    CanonicalResumeSnapshotModel,
    DocumentArtifactModel,
    GuestResumeSessionModel,
    ResumeAuditEventModel,
    ResumeHealthAnalysisModel,
    ResumeHealthComponentModel,
    ResumeHealthFeatureContributionModel,
    ResumeHealthFindingModel,
    ResumeObjectCleanupModel,
    ResumeProcessingJobModel,
    ResumeProcessingOutboxModel,
    ResumeUploadModel,
    SourceDocumentModel,
)

_FEATURE_VALUE_KEYS = frozenset(
    {
        "text_characters",
        "page_count",
        "image_only",
        "section_count",
        "recognized_section_count",
        "block_count",
        "concise_block_count",
        "bullet_count",
        "action_bullet_count",
        "outcome_bullet_count",
        "duplicate_block_count",
        "chronology_signal_count",
        "warning_count",
        "reading_order_violation_count",
        "average_confidence_basis_points",
    }
)


class SqlAlchemyResumeUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> "SqlAlchemyResumeUnitOfWork":
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("resume unit of work is not active")
        return self._session

    async def add_guest_session(self, guest: GuestSession) -> None:
        self.session.add(
            GuestResumeSessionModel(
                id=guest.id,
                capability_hash=guest.capability_hash,
                created_at=guest.created_at,
                expires_at=guest.expires_at,
                revoked_at=guest.revoked_at,
                claimed_by_user_id=guest.claimed_by_user_id,
                claimed_document_id=guest.claimed_document_id,
            )
        )
        await self._flush()

    async def get_guest_session(
        self, guest_id: UUID, *, for_update: bool = False
    ) -> GuestSession | None:
        statement = select(GuestResumeSessionModel).where(GuestResumeSessionModel.id == guest_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _guest(model) if model is not None else None

    async def save_guest_session(self, guest: GuestSession) -> None:
        await self.session.execute(
            update(GuestResumeSessionModel)
            .where(GuestResumeSessionModel.id == guest.id)
            .values(
                expires_at=guest.expires_at,
                revoked_at=guest.revoked_at,
                claimed_by_user_id=guest.claimed_by_user_id,
                claimed_document_id=guest.claimed_document_id,
            )
        )

    async def add_upload(self, upload: UploadIntent) -> None:
        self.session.add(
            ResumeUploadModel(
                id=upload.id,
                **_owner_values(upload.owner),
                display_filename=upload.display_filename,
                expected_media_type=upload.expected_media_type.value,
                expected_size=upload.expected_size,
                staging_object_key=upload.staging_object_key,
                status=upload.status.value,
                created_at=upload.created_at,
                expires_at=upload.expires_at,
                staging_cleaned_at=upload.staging_cleaned_at,
                finalized_document_id=upload.finalized_document_id,
                safe_error_code=upload.safe_error_code,
            )
        )
        await self._flush()

    async def get_upload(
        self, scope: OwnerScope, upload_id: UUID, *, for_update: bool = False
    ) -> UploadIntent | None:
        statement = select(ResumeUploadModel).where(
            ResumeUploadModel.id == upload_id, _scope_clause(ResumeUploadModel, scope)
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _upload(model) if model is not None else None

    async def save_upload(self, upload: UploadIntent) -> None:
        await self.session.execute(
            update(ResumeUploadModel)
            .where(
                ResumeUploadModel.id == upload.id,
                _scope_clause(ResumeUploadModel, upload.owner),
            )
            .values(
                display_filename=upload.display_filename,
                status=upload.status.value,
                finalized_document_id=upload.finalized_document_id,
                safe_error_code=upload.safe_error_code,
                staging_cleaned_at=upload.staging_cleaned_at,
            )
        )

    async def lock_intake_admission(self, scope: OwnerScope) -> None:
        # PostgreSQL transaction-scoped advisory locks make quota admission atomic even
        # when an owner currently has no rows to lock. UUIDs are reduced to a signed-
        # bigint-safe namespace; an extremely unlikely collision only serializes work.
        lock_key = scope.owner_id.int & ((1 << 63) - 1)
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def count_active_intakes(self, scope: OwnerScope, now: datetime) -> int:
        document_count = await self.session.scalar(
            select(func.count(SourceDocumentModel.id)).where(
                _scope_clause(SourceDocumentModel, scope),
                SourceDocumentModel.status != DocumentStatus.DELETED.value,
            )
        )
        upload_count = await self.session.scalar(
            select(func.count(ResumeUploadModel.id)).where(
                _scope_clause(ResumeUploadModel, scope),
                ResumeUploadModel.status == UploadStatus.ISSUED.value,
                ResumeUploadModel.expires_at > now,
            )
        )
        return int(document_count or 0) + int(upload_count or 0)

    async def add_document(self, document: SourceDocument) -> None:
        self.session.add(SourceDocumentModel(**_document_values(document)))
        await self._flush()

    async def get_document(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None:
        statement = select(SourceDocumentModel).where(
            SourceDocumentModel.id == document_id,
            _scope_clause(SourceDocumentModel, scope),
            SourceDocumentModel.status != DocumentStatus.DELETED.value,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _document(model) if model is not None else None

    async def get_document_system(
        self, document_id: UUID, *, for_update: bool = False
    ) -> SourceDocument | None:
        statement = select(SourceDocumentModel).where(SourceDocumentModel.id == document_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _document(model) if model is not None else None

    async def list_documents(self, scope: OwnerScope, limit: int) -> list[SourceDocument]:
        models = await self.session.scalars(
            select(SourceDocumentModel)
            .where(
                _scope_clause(SourceDocumentModel, scope),
                SourceDocumentModel.status != DocumentStatus.DELETED.value,
            )
            .order_by(SourceDocumentModel.created_at.desc())
            .limit(limit)
        )
        return [_document(model) for model in models]

    async def save_document(self, document: SourceDocument) -> None:
        values = _document_values(document)
        values.pop("id")
        values.pop("upload_id")
        values.pop("owner_user_id")
        values.pop("guest_session_id")
        await self.session.execute(
            update(SourceDocumentModel)
            .where(
                SourceDocumentModel.id == document.id,
                _scope_clause(SourceDocumentModel, document.owner),
            )
            .values(**values)
        )

    async def add_job(self, job: ProcessingJob) -> None:
        self.session.add(ResumeProcessingJobModel(**_job_values(job)))
        await self._flush(idempotency=True)

    async def get_job(
        self, scope: OwnerScope, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None:
        statement = select(ResumeProcessingJobModel).where(
            ResumeProcessingJobModel.id == job_id,
            _scope_clause(ResumeProcessingJobModel, scope),
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> ProcessingJob | None:
        statement = select(ResumeProcessingJobModel).where(ResumeProcessingJobModel.id == job_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def get_job_by_idempotency(
        self, scope: OwnerScope, idempotency_key: str
    ) -> ProcessingJob | None:
        model = await self.session.scalar(
            select(ResumeProcessingJobModel).where(
                ResumeProcessingJobModel.idempotency_key == idempotency_key,
                _scope_clause(ResumeProcessingJobModel, scope),
            )
        )
        return _job(model) if model is not None else None

    async def has_active_jobs(self, scope: OwnerScope, document_id: UUID) -> bool:
        job_id = await self.session.scalar(
            select(ResumeProcessingJobModel.id)
            .where(
                ResumeProcessingJobModel.document_id == document_id,
                _scope_clause(ResumeProcessingJobModel, scope),
                or_(
                    ResumeProcessingJobModel.status.in_(
                        [JobStatus.QUEUED.value, JobStatus.RUNNING.value]
                    ),
                    and_(
                        ResumeProcessingJobModel.status == JobStatus.FAILED.value,
                        ResumeProcessingJobModel.retryable.is_(True),
                    ),
                ),
            )
            .limit(1)
        )
        return job_id is not None

    async def count_jobs(self, scope: OwnerScope, document_id: UUID, kind: JobKind) -> int:
        count = await self.session.scalar(
            select(func.count(ResumeProcessingJobModel.id)).where(
                ResumeProcessingJobModel.document_id == document_id,
                ResumeProcessingJobModel.kind == kind.value,
                _scope_clause(ResumeProcessingJobModel, scope),
            )
        )
        return int(count or 0)

    async def save_job(self, job: ProcessingJob) -> None:
        values = _job_values(job)
        values.pop("id")
        values.pop("document_id")
        values.pop("owner_user_id")
        values.pop("guest_session_id")
        values.pop("idempotency_key")
        values.pop("request_hash")
        values.pop("created_at")
        await self.session.execute(
            update(ResumeProcessingJobModel)
            .where(ResumeProcessingJobModel.id == job.id)
            .values(**values)
        )

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[ProcessingJob]:
        pending_outbox = (
            select(ResumeProcessingOutboxModel.id)
            .where(
                ResumeProcessingOutboxModel.job_id == ResumeProcessingJobModel.id,
                ResumeProcessingOutboxModel.published_at.is_(None),
                ResumeProcessingOutboxModel.dead_lettered_at.is_(None),
            )
            .exists()
        )
        stale_published_outbox = (
            select(ResumeProcessingOutboxModel.id)
            .where(
                ResumeProcessingOutboxModel.job_id == ResumeProcessingJobModel.id,
                ResumeProcessingOutboxModel.published_at <= stale_before,
            )
            .exists()
        )
        models = await self.session.scalars(
            select(ResumeProcessingJobModel)
            .where(
                ~pending_outbox,
                or_(
                    ResumeProcessingJobModel.next_recovery_at.is_(None),
                    ResumeProcessingJobModel.next_recovery_at <= now,
                ),
                or_(
                    and_(
                        ResumeProcessingJobModel.status == JobStatus.QUEUED.value,
                        stale_published_outbox,
                    ),
                    and_(
                        ResumeProcessingJobModel.status == JobStatus.FAILED.value,
                        ResumeProcessingJobModel.retryable.is_(True),
                        ResumeProcessingJobModel.updated_at <= stale_before,
                    ),
                    and_(
                        ResumeProcessingJobModel.status == JobStatus.RUNNING.value,
                        ResumeProcessingJobModel.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(ResumeProcessingJobModel.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_job(model) for model in models]

    async def add_artifact(self, artifact: DocumentArtifact) -> None:
        self.session.add(DocumentArtifactModel(**_artifact_values(artifact)))
        await self._flush()

    async def save_artifact(self, artifact: DocumentArtifact) -> None:
        await self.session.execute(
            update(DocumentArtifactModel)
            .where(
                DocumentArtifactModel.id == artifact.id,
                _scope_clause(DocumentArtifactModel, artifact.owner),
            )
            .values(object_key=artifact.object_key, **_owner_values(artifact.owner))
        )

    async def list_artifacts(self, scope: OwnerScope, document_id: UUID) -> list[DocumentArtifact]:
        models = await self.session.scalars(
            select(DocumentArtifactModel).where(
                DocumentArtifactModel.document_id == document_id,
                _scope_clause(DocumentArtifactModel, scope),
            )
        )
        return [_artifact(model) for model in models]

    async def add_snapshot(self, snapshot: CanonicalSnapshot) -> None:
        self.session.add(
            CanonicalResumeSnapshotModel(
                id=snapshot.id,
                document_id=snapshot.document_id,
                **_owner_values(snapshot.owner),
                revision=snapshot.revision,
                canonical_json=snapshot.resume.to_dict(),
                plain_text_sha256=snapshot.plain_text_sha256,
                parser_version=snapshot.parser_version,
                based_on_snapshot_id=snapshot.based_on_snapshot_id,
                corrected_by_user=snapshot.corrected_by_user,
                created_at=snapshot.created_at,
            )
        )
        await self._flush()

    async def get_latest_snapshot(
        self, scope: OwnerScope, document_id: UUID, *, for_update: bool = False
    ) -> CanonicalSnapshot | None:
        statement = (
            select(CanonicalResumeSnapshotModel)
            .where(
                CanonicalResumeSnapshotModel.document_id == document_id,
                _scope_clause(CanonicalResumeSnapshotModel, scope),
            )
            .order_by(CanonicalResumeSnapshotModel.revision.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _snapshot(model) if model is not None else None

    async def get_first_snapshot(
        self, scope: OwnerScope, document_id: UUID
    ) -> CanonicalSnapshot | None:
        model = await self.session.scalar(
            select(CanonicalResumeSnapshotModel)
            .where(
                CanonicalResumeSnapshotModel.document_id == document_id,
                _scope_clause(CanonicalResumeSnapshotModel, scope),
            )
            .order_by(CanonicalResumeSnapshotModel.revision.asc())
            .limit(1)
        )
        return _snapshot(model) if model is not None else None

    async def get_snapshot(self, scope: OwnerScope, snapshot_id: UUID) -> CanonicalSnapshot | None:
        model = await self.session.scalar(
            select(CanonicalResumeSnapshotModel).where(
                CanonicalResumeSnapshotModel.id == snapshot_id,
                _scope_clause(CanonicalResumeSnapshotModel, scope),
            )
        )
        return _snapshot(model) if model is not None else None

    async def add_analysis(
        self,
        analysis: ResumeHealthAnalysis,
        components: tuple[ScoreComponent, ...],
        feature_contributions: tuple[FeatureContribution, ...],
        findings: tuple[ResumeFinding, ...],
    ) -> None:
        self.session.add(
            ResumeHealthAnalysisModel(
                id=analysis.id,
                job_id=analysis.job_id,
                document_id=analysis.document_id,
                snapshot_id=analysis.snapshot_id,
                **_owner_values(analysis.owner),
                status=analysis.status.value,
                engine_version=analysis.engine_version,
                configuration_version=analysis.configuration_version,
                feature_schema_version=analysis.feature_schema_version,
                feature_values=analysis.feature_values,
                feature_set_hash=analysis.feature_set_hash,
                raw_score_basis_points=analysis.raw_score_basis_points,
                display_score=analysis.display_score,
                computed_at=analysis.computed_at,
            )
        )
        self.session.add_all(
            [
                ResumeHealthFeatureContributionModel(
                    id=item.id,
                    analysis_id=item.analysis_id,
                    component_code=item.component_code,
                    feature_code=item.feature_code,
                    feature_value_basis_points=item.feature_value_basis_points,
                    weight_basis_points=item.weight_basis_points,
                    contribution_basis_points=item.contribution_basis_points,
                )
                for item in feature_contributions
            ]
        )
        self.session.add_all(
            [
                ResumeHealthComponentModel(
                    id=item.id,
                    analysis_id=item.analysis_id,
                    code=item.code,
                    weight_basis_points=item.weight_basis_points,
                    score_basis_points=item.score_basis_points,
                    contribution_basis_points=item.contribution_basis_points,
                    explanation=item.explanation,
                )
                for item in components
            ]
        )
        self.session.add_all(
            [
                ResumeHealthFindingModel(
                    id=item.id,
                    analysis_id=item.analysis_id,
                    code=item.code,
                    severity=item.severity.value,
                    component_code=item.component_code,
                    message=item.message,
                    quick_win=item.quick_win,
                    sort_order=item.sort_order,
                )
                for item in findings
            ]
        )
        await self._flush()

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
        model = await self.session.scalar(
            select(ResumeHealthAnalysisModel).where(
                ResumeHealthAnalysisModel.id == analysis_id,
                _scope_clause(ResumeHealthAnalysisModel, scope),
            )
        )
        return await self._analysis_bundle(model)

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
        model = await self.session.scalar(
            select(ResumeHealthAnalysisModel)
            .where(
                ResumeHealthAnalysisModel.document_id == document_id,
                _scope_clause(ResumeHealthAnalysisModel, scope),
            )
            .order_by(ResumeHealthAnalysisModel.computed_at.desc())
            .limit(1)
        )
        return await self._analysis_bundle(model)

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
        model = await self.session.scalar(
            select(ResumeHealthAnalysisModel).where(
                ResumeHealthAnalysisModel.snapshot_id == snapshot_id,
                _scope_clause(ResumeHealthAnalysisModel, scope),
            )
        )
        return await self._analysis_bundle(model)

    async def _analysis_bundle(
        self, model: ResumeHealthAnalysisModel | None
    ) -> (
        tuple[
            ResumeHealthAnalysis,
            list[ScoreComponent],
            list[FeatureContribution],
            list[ResumeFinding],
        ]
        | None
    ):
        if model is None:
            return None
        component_models = await self.session.scalars(
            select(ResumeHealthComponentModel)
            .where(ResumeHealthComponentModel.analysis_id == model.id)
            .order_by(ResumeHealthComponentModel.code)
        )
        contribution_models = await self.session.scalars(
            select(ResumeHealthFeatureContributionModel)
            .where(ResumeHealthFeatureContributionModel.analysis_id == model.id)
            .order_by(
                ResumeHealthFeatureContributionModel.component_code,
                ResumeHealthFeatureContributionModel.feature_code,
            )
        )
        finding_models = await self.session.scalars(
            select(ResumeHealthFindingModel)
            .where(ResumeHealthFindingModel.analysis_id == model.id)
            .order_by(ResumeHealthFindingModel.sort_order)
        )
        return (
            _analysis(model),
            [_component(item) for item in component_models],
            [_feature_contribution(item) for item in contribution_models],
            [_finding(item) for item in finding_models],
        )

    async def add_outbox(self, message: OutboxMessage) -> None:
        self.session.add(
            ResumeProcessingOutboxModel(
                id=message.id,
                job_id=message.job_id,
                task_name=message.task_name,
                trace_id=message.trace_id,
                created_at=message.created_at,
                next_attempt_at=message.next_attempt_at,
                generation=message.generation,
                published_at=message.published_at,
                attempts=message.attempts,
                max_attempts=message.max_attempts,
                last_error_code=message.last_error_code,
                dead_lettered_at=message.dead_lettered_at,
            )
        )
        await self._flush()

    async def add_audit(self, event: ResumeAuditEvent) -> None:
        self.session.add(
            ResumeAuditEventModel(
                id=event.id,
                **_owner_values(event.owner),
                action=event.action,
                outcome=event.outcome,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                request_id=event.request_id[:64],
                trace_id=event.trace_id[:64],
                safe_metadata=event.safe_metadata,
                created_at=event.created_at,
            )
        )
        await self._flush()

    async def list_pending_outbox(self, now: datetime, limit: int) -> list[OutboxMessage]:
        models = await self.session.scalars(
            select(ResumeProcessingOutboxModel)
            .where(
                ResumeProcessingOutboxModel.published_at.is_(None),
                ResumeProcessingOutboxModel.dead_lettered_at.is_(None),
                ResumeProcessingOutboxModel.next_attempt_at <= now,
            )
            .order_by(
                ResumeProcessingOutboxModel.next_attempt_at,
                ResumeProcessingOutboxModel.created_at,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_outbox(model) for model in models]

    async def save_outbox(self, message: OutboxMessage) -> None:
        await self.session.execute(
            update(ResumeProcessingOutboxModel)
            .where(ResumeProcessingOutboxModel.id == message.id)
            .values(
                published_at=message.published_at,
                attempts=message.attempts,
                max_attempts=message.max_attempts,
                next_attempt_at=message.next_attempt_at,
                last_error_code=message.last_error_code,
                dead_lettered_at=message.dead_lettered_at,
            )
        )

    async def add_object_cleanup(self, cleanup: StorageObjectCleanup) -> None:
        self.session.add(ResumeObjectCleanupModel(**_object_cleanup_values(cleanup)))
        await self._flush()

    async def save_object_cleanup(self, cleanup: StorageObjectCleanup) -> None:
        values = _object_cleanup_values(cleanup)
        values.pop("id")
        values.pop("owner_user_id")
        values.pop("guest_session_id")
        values.pop("object_key")
        values.pop("purpose")
        values.pop("created_at")
        await self.session.execute(
            update(ResumeObjectCleanupModel)
            .where(
                ResumeObjectCleanupModel.id == cleanup.id,
                _scope_clause(ResumeObjectCleanupModel, cleanup.owner),
            )
            .values(**values)
        )

    async def list_due_object_cleanups(
        self, now: datetime, limit: int
    ) -> list[StorageObjectCleanup]:
        models = await self.session.scalars(
            select(ResumeObjectCleanupModel)
            .where(
                ResumeObjectCleanupModel.completed_at.is_(None),
                ResumeObjectCleanupModel.cancelled_at.is_(None),
                ResumeObjectCleanupModel.dead_lettered_at.is_(None),
                ResumeObjectCleanupModel.not_before <= now,
            )
            .order_by(ResumeObjectCleanupModel.not_before, ResumeObjectCleanupModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_object_cleanup(model) for model in models]

    async def claim_guest_resources(
        self, guest_session_id: UUID, user_id: UUID, document_id: UUID, now: datetime
    ) -> None:
        for model in (
            ResumeUploadModel,
            SourceDocumentModel,
            DocumentArtifactModel,
            ResumeProcessingJobModel,
            CanonicalResumeSnapshotModel,
            ResumeHealthAnalysisModel,
        ):
            await self.session.execute(
                update(model)
                .where(model.guest_session_id == guest_session_id)
                .values(owner_user_id=user_id, guest_session_id=None)
            )
        await self.session.execute(
            update(GuestResumeSessionModel)
            .where(GuestResumeSessionModel.id == guest_session_id)
            .values(
                claimed_by_user_id=user_id,
                claimed_document_id=document_id,
                revoked_at=now,
            )
        )

    async def purge_document_content(
        self, scope: OwnerScope, document_id: UUID, keep_job_id: UUID
    ) -> None:
        document = await self.session.scalar(
            select(SourceDocumentModel).where(
                SourceDocumentModel.id == document_id,
                _scope_clause(SourceDocumentModel, scope),
            )
        )
        if document is None:
            raise ResumeStateConflict
        await self.session.execute(
            delete(ResumeProcessingJobModel).where(
                ResumeProcessingJobModel.document_id == document_id,
                ResumeProcessingJobModel.id != keep_job_id,
            )
        )
        await self.session.execute(
            delete(ResumeHealthAnalysisModel).where(
                ResumeHealthAnalysisModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(CanonicalResumeSnapshotModel).where(
                CanonicalResumeSnapshotModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(DocumentArtifactModel).where(DocumentArtifactModel.document_id == document_id)
        )

    async def list_expired_uploads(self, now: datetime, limit: int) -> list[UploadIntent]:
        models = await self.session.scalars(
            select(ResumeUploadModel)
            .where(
                or_(
                    and_(
                        ResumeUploadModel.status.in_(
                            [
                                UploadStatus.ISSUED.value,
                                UploadStatus.EXPIRED.value,
                                UploadStatus.FINALIZED.value,
                            ]
                        ),
                        ResumeUploadModel.expires_at <= now,
                    ),
                    ResumeUploadModel.status == UploadStatus.REJECTED.value,
                ),
                ResumeUploadModel.staging_cleaned_at.is_(None),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_upload(model) for model in models]

    async def list_expired_guest_documents(self, now: datetime, limit: int) -> list[SourceDocument]:
        models = await self.session.scalars(
            select(SourceDocumentModel)
            .where(
                SourceDocumentModel.guest_session_id.is_not(None),
                SourceDocumentModel.retention_expires_at <= now,
                SourceDocumentModel.status.not_in(
                    [DocumentStatus.DELETING.value, DocumentStatus.DELETED.value]
                ),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_document(model) for model in models]

    async def list_expired_guests(self, now: datetime, limit: int) -> list[GuestSession]:
        models = await self.session.scalars(
            select(GuestResumeSessionModel)
            .where(
                GuestResumeSessionModel.expires_at <= now,
                GuestResumeSessionModel.revoked_at.is_(None),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_guest(model) for model in models]

    async def commit(self) -> None:
        await self.session.commit()
        self._committed = True

    async def _flush(self, *, idempotency: bool = False) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if idempotency:
                raise IdempotencyConflict from exc
            raise ResumeStateConflict from exc


class SqlAlchemyResumeUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyResumeUnitOfWork:
        return SqlAlchemyResumeUnitOfWork(self._database)


def _scope_clause(model: Any, scope: OwnerScope) -> Any:
    if scope.user_id is not None:
        return model.owner_user_id == scope.user_id
    return model.guest_session_id == scope.guest_session_id


def _owner_values(scope: OwnerScope) -> dict[str, UUID | None]:
    return {"owner_user_id": scope.user_id, "guest_session_id": scope.guest_session_id}


def _scope(user_id: UUID | None, guest_id: UUID | None) -> OwnerScope:
    return OwnerScope(user_id=user_id, guest_session_id=guest_id)


def _guest(model: GuestResumeSessionModel) -> GuestSession:
    return GuestSession(
        id=model.id,
        capability_hash=model.capability_hash,
        created_at=model.created_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        claimed_by_user_id=model.claimed_by_user_id,
        claimed_document_id=model.claimed_document_id,
    )


def _upload(model: ResumeUploadModel) -> UploadIntent:
    return UploadIntent(
        id=model.id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        display_filename=model.display_filename,
        expected_media_type=ResumeMediaType(model.expected_media_type),
        expected_size=model.expected_size,
        staging_object_key=model.staging_object_key,
        status=UploadStatus(model.status),
        created_at=model.created_at,
        expires_at=model.expires_at,
        finalized_document_id=model.finalized_document_id,
        safe_error_code=model.safe_error_code,
        staging_cleaned_at=model.staging_cleaned_at,
    )


def _document_values(document: SourceDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "upload_id": document.upload_id,
        **_owner_values(document.owner),
        "display_filename": document.display_filename,
        "media_type": document.media_type.value,
        "size_bytes": document.size_bytes,
        "quarantine_object_key": document.quarantine_object_key,
        "status": document.status.value,
        "malware_status": document.malware_status.value,
        "content_sha256": document.content_sha256,
        "page_count": document.page_count,
        "safe_error_code": document.safe_error_code,
        "retention_expires_at": document.retention_expires_at,
        "deleted_at": document.deleted_at,
        "version": document.version,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _document(model: SourceDocumentModel) -> SourceDocument:
    return SourceDocument(
        id=model.id,
        upload_id=model.upload_id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        display_filename=model.display_filename,
        media_type=ResumeMediaType(model.media_type),
        size_bytes=model.size_bytes,
        quarantine_object_key=model.quarantine_object_key,
        status=DocumentStatus(model.status),
        malware_status=MalwareStatus(model.malware_status),
        content_sha256=model.content_sha256,
        page_count=model.page_count,
        safe_error_code=model.safe_error_code,
        retention_expires_at=model.retention_expires_at,
        deleted_at=model.deleted_at,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _job_values(job: ProcessingJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "document_id": job.document_id,
        **_owner_values(job.owner),
        "kind": job.kind.value,
        "idempotency_key": job.idempotency_key,
        "request_hash": job.request_hash,
        "trace_id": job.trace_id,
        "status": job.status.value,
        "stage": job.stage.value,
        "progress": job.progress,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "cancellation_requested_at": job.cancellation_requested_at,
        "safe_error_code": job.safe_error_code,
        "retryable": job.retryable,
        "dead_lettered_at": job.dead_lettered_at,
        "result_id": job.result_id,
        "input_snapshot_id": job.input_snapshot_id,
        "execution_token_hash": job.execution_token_hash,
        "lease_expires_at": job.lease_expires_at,
        "recovery_attempts": job.recovery_attempts,
        "max_recovery_attempts": job.max_recovery_attempts,
        "next_recovery_at": job.next_recovery_at,
        "version": job.version,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _job(model: ResumeProcessingJobModel) -> ProcessingJob:
    return ProcessingJob(
        id=model.id,
        document_id=model.document_id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        kind=JobKind(model.kind),
        idempotency_key=model.idempotency_key,
        request_hash=model.request_hash,
        trace_id=model.trace_id,
        status=JobStatus(model.status),
        stage=ProcessingStage(model.stage),
        progress=model.progress,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        started_at=model.started_at,
        completed_at=model.completed_at,
        cancellation_requested_at=model.cancellation_requested_at,
        safe_error_code=model.safe_error_code,
        retryable=model.retryable,
        dead_lettered_at=model.dead_lettered_at,
        result_id=model.result_id,
        input_snapshot_id=model.input_snapshot_id,
        execution_token_hash=model.execution_token_hash,
        lease_expires_at=model.lease_expires_at,
        recovery_attempts=model.recovery_attempts,
        max_recovery_attempts=model.max_recovery_attempts,
        next_recovery_at=model.next_recovery_at,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _artifact_values(artifact: DocumentArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "document_id": artifact.document_id,
        **_owner_values(artifact.owner),
        "kind": artifact.kind.value,
        "object_key": artifact.object_key,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "created_at": artifact.created_at,
    }


def _artifact(model: DocumentArtifactModel) -> DocumentArtifact:
    return DocumentArtifact(
        id=model.id,
        document_id=model.document_id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        kind=ArtifactKind(model.kind),
        object_key=model.object_key,
        size_bytes=model.size_bytes,
        sha256=model.sha256,
        created_at=model.created_at,
    )


def _snapshot(model: CanonicalResumeSnapshotModel) -> CanonicalSnapshot:
    return CanonicalSnapshot(
        id=model.id,
        document_id=model.document_id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        revision=model.revision,
        resume=CanonicalResume.from_dict(model.canonical_json),
        plain_text_sha256=model.plain_text_sha256,
        parser_version=model.parser_version,
        based_on_snapshot_id=model.based_on_snapshot_id,
        corrected_by_user=model.corrected_by_user,
        created_at=model.created_at,
    )


def _analysis(model: ResumeHealthAnalysisModel) -> ResumeHealthAnalysis:
    return ResumeHealthAnalysis(
        id=model.id,
        job_id=model.job_id,
        document_id=model.document_id,
        snapshot_id=model.snapshot_id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        status=AnalysisStatus(model.status),
        engine_version=model.engine_version,
        configuration_version=model.configuration_version,
        feature_schema_version=model.feature_schema_version,
        feature_values=_analysis_feature_values(model.feature_values),
        feature_set_hash=model.feature_set_hash,
        raw_score_basis_points=model.raw_score_basis_points,
        display_score=model.display_score,
        computed_at=model.computed_at,
    )


def _component(model: ResumeHealthComponentModel) -> ScoreComponent:
    return ScoreComponent(
        id=model.id,
        analysis_id=model.analysis_id,
        code=model.code,
        weight_basis_points=model.weight_basis_points,
        score_basis_points=model.score_basis_points,
        contribution_basis_points=model.contribution_basis_points,
        explanation=model.explanation,
    )


def _feature_contribution(
    model: ResumeHealthFeatureContributionModel,
) -> FeatureContribution:
    return FeatureContribution(
        id=model.id,
        analysis_id=model.analysis_id,
        component_code=model.component_code,
        feature_code=model.feature_code,
        feature_value_basis_points=model.feature_value_basis_points,
        weight_basis_points=model.weight_basis_points,
        contribution_basis_points=model.contribution_basis_points,
    )


def _analysis_feature_values(value: dict[str, Any]) -> dict[str, int | bool]:
    """Reject corrupt or schema-drifted feature JSON at the persistence boundary."""
    if set(value) != _FEATURE_VALUE_KEYS or type(value.get("image_only")) is not bool:
        raise ResumeStateConflict
    normalized: dict[str, int | bool] = {"image_only": value["image_only"]}
    for key in _FEATURE_VALUE_KEYS - {"image_only"}:
        item = value.get(key)
        if type(item) is not int or item < 0:
            raise ResumeStateConflict
        normalized[key] = item
    if normalized["average_confidence_basis_points"] > 10_000:
        raise ResumeStateConflict
    return normalized


def _finding(model: ResumeHealthFindingModel) -> ResumeFinding:
    return ResumeFinding(
        id=model.id,
        analysis_id=model.analysis_id,
        code=model.code,
        severity=FindingSeverity(model.severity),
        component_code=model.component_code,
        message=model.message,
        quick_win=model.quick_win,
        sort_order=model.sort_order,
    )


def _outbox(model: ResumeProcessingOutboxModel) -> OutboxMessage:
    return OutboxMessage(
        id=model.id,
        job_id=model.job_id,
        task_name=model.task_name,
        trace_id=model.trace_id,
        created_at=model.created_at,
        next_attempt_at=model.next_attempt_at,
        generation=model.generation,
        published_at=model.published_at,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        last_error_code=model.last_error_code,
        dead_lettered_at=model.dead_lettered_at,
    )


def _object_cleanup_values(cleanup: StorageObjectCleanup) -> dict[str, Any]:
    return {
        "id": cleanup.id,
        **_owner_values(cleanup.owner),
        "object_key": cleanup.object_key,
        "purpose": cleanup.purpose.value,
        "not_before": cleanup.not_before,
        "attempts": cleanup.attempts,
        "max_attempts": cleanup.max_attempts,
        "last_error_code": cleanup.last_error_code,
        "completed_at": cleanup.completed_at,
        "cancelled_at": cleanup.cancelled_at,
        "dead_lettered_at": cleanup.dead_lettered_at,
        "created_at": cleanup.created_at,
    }


def _object_cleanup(model: ResumeObjectCleanupModel) -> StorageObjectCleanup:
    return StorageObjectCleanup(
        id=model.id,
        owner=_scope(model.owner_user_id, model.guest_session_id),
        object_key=model.object_key,
        purpose=ObjectCleanupPurpose(model.purpose),
        not_before=model.not_before,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        last_error_code=model.last_error_code,
        completed_at=model.completed_at,
        cancelled_at=model.cancelled_at,
        dead_lettered_at=model.dead_lettered_at,
        created_at=model.created_at,
    )
