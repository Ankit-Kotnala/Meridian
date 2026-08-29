"""SQLAlchemy persistence for private Career Record evidence attachments."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import NoReturn
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentAuditEvent,
    AttachmentConflict,
    AttachmentExtractionSummary,
    AttachmentFinalizationReceipt,
    AttachmentIdempotencyConflict,
    AttachmentJobStage,
    AttachmentJobStatus,
    AttachmentMediaType,
    AttachmentObjectCleanup,
    AttachmentOutboxMessage,
    AttachmentProcessingJob,
    AttachmentRecord,
    AttachmentStatus,
    CleanupPurpose,
    CleanupStatus,
    SafeAttachmentError,
)

from .models import (
    EvidenceAttachmentAuditEventModel,
    EvidenceAttachmentFinalizationModel,
    EvidenceAttachmentModel,
    EvidenceAttachmentObjectCleanupModel,
    EvidenceAttachmentOutboxModel,
    EvidenceAttachmentProcessingJobModel,
    EvidenceItemModel,
)


class SystemClock:
    """UTC clock local to this bounded context's infrastructure."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class SqlAlchemyAttachmentUnitOfWork:
    """Owner-scoped transactional persistence with worker-only system lookups."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyAttachmentUnitOfWork:
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
            raise RuntimeError("attachment unit of work is not active")
        return self._session

    async def lock_admission(self, owner_user_id: UUID, evidence_id: UUID) -> None:
        # The pair-specific transaction lock serializes quota checks even when no
        # attachment row exists yet. A hash collision can only serialize work.
        lock_key = (owner_user_id.int ^ evidence_id.int) & ((1 << 63) - 1)
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def evidence_exists(self, owner_user_id: UUID, evidence_id: UUID) -> bool:
        value = await self.session.scalar(
            select(EvidenceItemModel.id)
            .where(
                EvidenceItemModel.owner_user_id == owner_user_id,
                EvidenceItemModel.id == evidence_id,
                EvidenceItemModel.lifecycle != "deleted",
            )
            .with_for_update()
        )
        return value is not None

    async def count_active_attachments(self, owner_user_id: UUID, evidence_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count(EvidenceAttachmentModel.id)).where(
                EvidenceAttachmentModel.owner_user_id == owner_user_id,
                EvidenceAttachmentModel.evidence_id == evidence_id,
                EvidenceAttachmentModel.workflow_status.not_in(("rejected", "deleted")),
            )
        )
        return int(value or 0)

    async def add_attachment(self, attachment: AttachmentRecord) -> None:
        self.session.add(EvidenceAttachmentModel(**_attachment_values(attachment)))
        await self._flush()

    async def get_attachment(
        self, owner_user_id: UUID, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None:
        statement = select(EvidenceAttachmentModel).where(
            EvidenceAttachmentModel.owner_user_id == owner_user_id,
            EvidenceAttachmentModel.id == attachment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _attachment(model) if model is not None else None

    async def get_attachment_system(
        self, attachment_id: UUID, *, for_update: bool = False
    ) -> AttachmentRecord | None:
        statement = select(EvidenceAttachmentModel).where(
            EvidenceAttachmentModel.id == attachment_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _attachment(model) if model is not None else None

    async def save_attachment(self, attachment: AttachmentRecord) -> None:
        values = _attachment_values(attachment)
        for immutable in ("id", "owner_user_id", "evidence_id", "created_at"):
            values.pop(immutable)
        await self.session.execute(
            update(EvidenceAttachmentModel)
            .where(
                EvidenceAttachmentModel.owner_user_id == attachment.owner_user_id,
                EvidenceAttachmentModel.id == attachment.id,
            )
            .values(**values)
        )

    async def add_finalization_receipt(self, receipt: AttachmentFinalizationReceipt) -> None:
        self.session.add(
            EvidenceAttachmentFinalizationModel(
                id=receipt.id,
                owner_user_id=receipt.owner_user_id,
                idempotency_key=receipt.idempotency_key,
                request_hash=receipt.request_hash,
                attachment_id=receipt.attachment_id,
                job_id=receipt.job_id,
                created_at=receipt.created_at,
            )
        )
        await self._flush(idempotency=True)

    async def get_finalization_receipt(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AttachmentFinalizationReceipt | None:
        model = await self.session.scalar(
            select(EvidenceAttachmentFinalizationModel).where(
                EvidenceAttachmentFinalizationModel.owner_user_id == owner_user_id,
                EvidenceAttachmentFinalizationModel.idempotency_key == idempotency_key,
            )
        )
        if model is None:
            return None
        return AttachmentFinalizationReceipt(
            model.id,
            model.owner_user_id,
            model.idempotency_key,
            model.request_hash,
            model.attachment_id,
            model.job_id,
            model.created_at,
        )

    async def add_job(self, job: AttachmentProcessingJob) -> None:
        self.session.add(EvidenceAttachmentProcessingJobModel(**_job_values(job)))
        await self._flush()

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> AttachmentProcessingJob | None:
        statement = select(EvidenceAttachmentProcessingJobModel).where(
            EvidenceAttachmentProcessingJobModel.id == job_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def list_jobs_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentProcessingJob]:
        models = (
            await self.session.scalars(
                select(EvidenceAttachmentProcessingJobModel)
                .where(
                    EvidenceAttachmentProcessingJobModel.owner_user_id == owner_user_id,
                    EvidenceAttachmentProcessingJobModel.attachment_id == attachment_id,
                )
                .order_by(
                    EvidenceAttachmentProcessingJobModel.created_at,
                    EvidenceAttachmentProcessingJobModel.id,
                )
            )
        ).all()
        return [_job(model) for model in models]

    async def save_job(self, job: AttachmentProcessingJob) -> None:
        values = _job_values(job)
        for immutable in ("id", "owner_user_id", "attachment_id", "trace_id", "created_at"):
            values.pop(immutable)
        await self.session.execute(
            update(EvidenceAttachmentProcessingJobModel)
            .where(
                EvidenceAttachmentProcessingJobModel.owner_user_id == job.owner_user_id,
                EvidenceAttachmentProcessingJobModel.id == job.id,
            )
            .values(**values)
        )

    async def list_reconcilable_jobs(
        self, now: datetime, stale_before: datetime, limit: int
    ) -> list[AttachmentProcessingJob]:
        pending_outbox = (
            select(EvidenceAttachmentOutboxModel.id)
            .where(
                EvidenceAttachmentOutboxModel.owner_user_id
                == EvidenceAttachmentProcessingJobModel.owner_user_id,
                EvidenceAttachmentOutboxModel.job_id == EvidenceAttachmentProcessingJobModel.id,
                EvidenceAttachmentOutboxModel.published_at.is_(None),
                EvidenceAttachmentOutboxModel.dead_lettered_at.is_(None),
                EvidenceAttachmentOutboxModel.cancelled_at.is_(None),
            )
            .exists()
        )
        models = (
            await self.session.scalars(
                select(EvidenceAttachmentProcessingJobModel)
                .where(
                    ~pending_outbox,
                    or_(
                        and_(
                            EvidenceAttachmentProcessingJobModel.status == "running",
                            EvidenceAttachmentProcessingJobModel.lease_expires_at <= now,
                        ),
                        and_(
                            EvidenceAttachmentProcessingJobModel.status.in_(
                                ("queued", "retry_wait")
                            ),
                            EvidenceAttachmentProcessingJobModel.updated_at <= stale_before,
                            or_(
                                EvidenceAttachmentProcessingJobModel.next_attempt_at.is_(None),
                                EvidenceAttachmentProcessingJobModel.next_attempt_at <= now,
                            ),
                        ),
                    ),
                )
                .order_by(
                    EvidenceAttachmentProcessingJobModel.updated_at,
                    EvidenceAttachmentProcessingJobModel.id,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_job(model) for model in models]

    async def next_outbox_generation(self, owner_user_id: UUID, job_id: UUID) -> int:
        generation = await self.session.scalar(
            select(func.max(EvidenceAttachmentOutboxModel.generation)).where(
                EvidenceAttachmentOutboxModel.owner_user_id == owner_user_id,
                EvidenceAttachmentOutboxModel.job_id == job_id,
            )
        )
        return int(generation if generation is not None else -1) + 1

    async def add_outbox(self, message: AttachmentOutboxMessage) -> None:
        self.session.add(EvidenceAttachmentOutboxModel(**_outbox_values(message)))
        await self._flush()

    async def list_pending_outbox(self, now: datetime, limit: int) -> list[AttachmentOutboxMessage]:
        models = (
            await self.session.scalars(
                select(EvidenceAttachmentOutboxModel)
                .where(
                    EvidenceAttachmentOutboxModel.published_at.is_(None),
                    EvidenceAttachmentOutboxModel.dead_lettered_at.is_(None),
                    EvidenceAttachmentOutboxModel.cancelled_at.is_(None),
                    EvidenceAttachmentOutboxModel.next_attempt_at <= now,
                )
                .order_by(
                    EvidenceAttachmentOutboxModel.next_attempt_at,
                    EvidenceAttachmentOutboxModel.created_at,
                    EvidenceAttachmentOutboxModel.id,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_outbox(model) for model in models]

    async def save_outbox(self, message: AttachmentOutboxMessage) -> None:
        values = _outbox_values(message)
        for immutable in (
            "id",
            "owner_user_id",
            "job_id",
            "task_name",
            "trace_id",
            "generation",
            "created_at",
        ):
            values.pop(immutable)
        await self.session.execute(
            update(EvidenceAttachmentOutboxModel)
            .where(
                EvidenceAttachmentOutboxModel.owner_user_id == message.owner_user_id,
                EvidenceAttachmentOutboxModel.id == message.id,
            )
            .values(**values)
        )

    async def add_cleanup(self, cleanup: AttachmentObjectCleanup) -> None:
        self.session.add(EvidenceAttachmentObjectCleanupModel(**_cleanup_values(cleanup)))
        await self._flush()

    async def has_cleanup_for_object(
        self, owner_user_id: UUID, attachment_id: UUID, object_key: str
    ) -> bool:
        value = await self.session.scalar(
            select(EvidenceAttachmentObjectCleanupModel.id).where(
                EvidenceAttachmentObjectCleanupModel.owner_user_id == owner_user_id,
                EvidenceAttachmentObjectCleanupModel.attachment_id == attachment_id,
                EvidenceAttachmentObjectCleanupModel.object_key == object_key,
            )
        )
        return value is not None

    async def get_cleanup_system(
        self, cleanup_id: UUID, *, for_update: bool = False
    ) -> AttachmentObjectCleanup | None:
        statement = select(EvidenceAttachmentObjectCleanupModel).where(
            EvidenceAttachmentObjectCleanupModel.id == cleanup_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _cleanup(model) if model is not None else None

    async def list_cleanups_for_attachment(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> list[AttachmentObjectCleanup]:
        models = (
            await self.session.scalars(
                select(EvidenceAttachmentObjectCleanupModel)
                .where(
                    EvidenceAttachmentObjectCleanupModel.owner_user_id == owner_user_id,
                    EvidenceAttachmentObjectCleanupModel.attachment_id == attachment_id,
                )
                .order_by(
                    EvidenceAttachmentObjectCleanupModel.created_at,
                    EvidenceAttachmentObjectCleanupModel.id,
                )
            )
        ).all()
        return [_cleanup(model) for model in models]

    async def list_due_cleanups(self, now: datetime, limit: int) -> list[AttachmentObjectCleanup]:
        models = (
            await self.session.scalars(
                select(EvidenceAttachmentObjectCleanupModel)
                .where(
                    EvidenceAttachmentObjectCleanupModel.status.in_(("pending", "retry_wait")),
                    EvidenceAttachmentObjectCleanupModel.next_attempt_at <= now,
                )
                .order_by(
                    EvidenceAttachmentObjectCleanupModel.next_attempt_at,
                    EvidenceAttachmentObjectCleanupModel.created_at,
                    EvidenceAttachmentObjectCleanupModel.id,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_cleanup(model) for model in models]

    async def save_cleanup(self, cleanup: AttachmentObjectCleanup) -> None:
        values = _cleanup_values(cleanup)
        for immutable in (
            "id",
            "owner_user_id",
            "attachment_id",
            "object_key",
            "purpose",
            "created_at",
        ):
            values.pop(immutable)
        await self.session.execute(
            update(EvidenceAttachmentObjectCleanupModel)
            .where(
                EvidenceAttachmentObjectCleanupModel.owner_user_id == cleanup.owner_user_id,
                EvidenceAttachmentObjectCleanupModel.id == cleanup.id,
            )
            .values(**values)
        )

    async def add_audit(self, event: AttachmentAuditEvent) -> None:
        self.session.add(
            EvidenceAttachmentAuditEventModel(
                id=event.id,
                owner_user_id=event.owner_user_id,
                actor_user_id=event.actor_user_id,
                action=event.action.value,
                attachment_id=event.attachment_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                safe_details=dict(event.safe_details),
                created_at=event.created_at,
            )
        )
        await self._flush()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _flush(self, *, idempotency: bool = False) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if idempotency:
                raise AttachmentIdempotencyConflict from exc
            _raise_integrity(exc)


class SqlAlchemyAttachmentUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyAttachmentUnitOfWork:
        return SqlAlchemyAttachmentUnitOfWork(self._database)


def _attachment(model: EvidenceAttachmentModel) -> AttachmentRecord:
    if model.upload_expires_at is None:
        raise AttachmentConflict("stored attachment admission is incomplete")
    extraction = None
    if model.extraction_format_valid is not None:
        extraction = AttachmentExtractionSummary(
            format_valid=model.extraction_format_valid,
            page_count=_required(model.extraction_page_count, "page count"),
            extracted_characters=_required(
                model.extraction_extracted_characters, "extracted characters"
            ),
            extracted_blocks=_required(model.extraction_extracted_blocks, "extracted blocks"),
            archive_entries=_required(model.extraction_archive_entries, "archive entries"),
            archive_uncompressed_bytes=_required(
                model.extraction_archive_uncompressed_bytes, "archive size"
            ),
            max_archive_ratio=_required(
                model.extraction_max_archive_ratio, "archive compression ratio"
            ),
            parser_version=_required_text(model.extraction_parser_version, "parser version"),
        )
    return AttachmentRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        display_filename=model.display_filename,
        media_type=(
            AttachmentMediaType(model.media_type) if model.media_type is not None else None
        ),
        expected_size=model.size_bytes,
        staging_object_key=model.staging_object_key,
        quarantine_object_key=model.quarantine_object_key,
        status=AttachmentStatus(model.workflow_status),
        created_at=model.created_at,
        updated_at=model.updated_at,
        admission_expires_at=model.upload_expires_at,
        version=model.version,
        safe_error_code=(
            SafeAttachmentError(model.safe_error_code)
            if model.safe_error_code is not None
            else None
        ),
        content_sha256=model.content_sha256,
        extraction=extraction,
        finalized_at=model.finalized_at,
        deleted_at=model.deleted_at,
    )


def _attachment_values(attachment: AttachmentRecord) -> dict[str, object]:
    extraction = attachment.extraction
    return {
        "id": attachment.id,
        "owner_user_id": attachment.owner_user_id,
        "evidence_id": attachment.evidence_id,
        "display_filename": attachment.display_filename,
        "media_type": attachment.media_type.value if attachment.media_type is not None else None,
        "size_bytes": attachment.expected_size,
        "content_sha256": attachment.content_sha256,
        "status": _core_status(attachment.status),
        "workflow_status": attachment.status.value,
        "staging_object_key": attachment.staging_object_key,
        "quarantine_object_key": attachment.quarantine_object_key,
        "upload_expires_at": attachment.admission_expires_at,
        "safe_error_code": (
            attachment.safe_error_code.value if attachment.safe_error_code is not None else None
        ),
        "extraction_format_valid": extraction.format_valid if extraction is not None else None,
        "extraction_page_count": extraction.page_count if extraction is not None else None,
        "extraction_extracted_characters": (
            extraction.extracted_characters if extraction is not None else None
        ),
        "extraction_extracted_blocks": (
            extraction.extracted_blocks if extraction is not None else None
        ),
        "extraction_archive_entries": extraction.archive_entries
        if extraction is not None
        else None,
        "extraction_archive_uncompressed_bytes": (
            extraction.archive_uncompressed_bytes if extraction is not None else None
        ),
        "extraction_max_archive_ratio": (
            extraction.max_archive_ratio if extraction is not None else None
        ),
        "extraction_parser_version": extraction.parser_version if extraction is not None else None,
        "finalized_at": attachment.finalized_at,
        "deleted_at": attachment.deleted_at,
        "version": attachment.version,
        "created_at": attachment.created_at,
        "updated_at": attachment.updated_at,
    }


def _job(model: EvidenceAttachmentProcessingJobModel) -> AttachmentProcessingJob:
    return AttachmentProcessingJob(
        id=model.id,
        owner_user_id=model.owner_user_id,
        attachment_id=model.attachment_id,
        trace_id=model.trace_id,
        status=AttachmentJobStatus(model.status),
        stage=AttachmentJobStage(model.stage),
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        fence=model.fence,
        created_at=model.created_at,
        updated_at=model.updated_at,
        execution_token_hash=model.execution_token_hash,
        lease_expires_at=model.lease_expires_at,
        next_attempt_at=model.next_attempt_at,
        completed_at=model.completed_at,
        dead_lettered_at=model.dead_lettered_at,
        safe_error_code=(
            SafeAttachmentError(model.safe_error_code)
            if model.safe_error_code is not None
            else None
        ),
    )


def _job_values(job: AttachmentProcessingJob) -> dict[str, object]:
    return {
        "id": job.id,
        "owner_user_id": job.owner_user_id,
        "attachment_id": job.attachment_id,
        "trace_id": job.trace_id,
        "status": job.status.value,
        "stage": job.stage.value,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "fence": job.fence,
        "execution_token_hash": job.execution_token_hash,
        "lease_expires_at": job.lease_expires_at,
        "next_attempt_at": job.next_attempt_at,
        "completed_at": job.completed_at,
        "dead_lettered_at": job.dead_lettered_at,
        "safe_error_code": job.safe_error_code.value if job.safe_error_code is not None else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _outbox(model: EvidenceAttachmentOutboxModel) -> AttachmentOutboxMessage:
    return AttachmentOutboxMessage(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        task_name=model.task_name,
        trace_id=model.trace_id,
        generation=model.generation,
        created_at=model.created_at,
        next_attempt_at=model.next_attempt_at,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        published_at=model.published_at,
        dead_lettered_at=model.dead_lettered_at,
        last_error_code=(
            SafeAttachmentError(model.last_error_code)
            if model.last_error_code is not None
            else None
        ),
        cancelled_at=model.cancelled_at,
    )


def _outbox_values(message: AttachmentOutboxMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "owner_user_id": message.owner_user_id,
        "job_id": message.job_id,
        "task_name": message.task_name,
        "trace_id": message.trace_id,
        "generation": message.generation,
        "attempts": message.attempts,
        "max_attempts": message.max_attempts,
        "next_attempt_at": message.next_attempt_at,
        "last_error_code": (
            message.last_error_code.value if message.last_error_code is not None else None
        ),
        "published_at": message.published_at,
        "dead_lettered_at": message.dead_lettered_at,
        "cancelled_at": message.cancelled_at,
        "created_at": message.created_at,
    }


def _cleanup(model: EvidenceAttachmentObjectCleanupModel) -> AttachmentObjectCleanup:
    return AttachmentObjectCleanup(
        id=model.id,
        owner_user_id=model.owner_user_id,
        attachment_id=model.attachment_id,
        object_key=model.object_key,
        purpose=CleanupPurpose(model.purpose),
        status=CleanupStatus(model.status),
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        next_attempt_at=model.next_attempt_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
        dead_lettered_at=model.dead_lettered_at,
        safe_error_code=(
            SafeAttachmentError(model.safe_error_code)
            if model.safe_error_code is not None
            else None
        ),
    )


def _cleanup_values(cleanup: AttachmentObjectCleanup) -> dict[str, object]:
    return {
        "id": cleanup.id,
        "owner_user_id": cleanup.owner_user_id,
        "attachment_id": cleanup.attachment_id,
        "object_key": cleanup.object_key,
        "purpose": cleanup.purpose.value,
        "status": cleanup.status.value,
        "attempts": cleanup.attempts,
        "max_attempts": cleanup.max_attempts,
        "next_attempt_at": cleanup.next_attempt_at,
        "safe_error_code": (
            cleanup.safe_error_code.value if cleanup.safe_error_code is not None else None
        ),
        "completed_at": cleanup.completed_at,
        "dead_lettered_at": cleanup.dead_lettered_at,
        "created_at": cleanup.created_at,
        "updated_at": cleanup.updated_at,
    }


def _core_status(status: AttachmentStatus) -> str:
    if status is AttachmentStatus.ADMITTED:
        return "pending"
    if status is AttachmentStatus.PROCESSING:
        return "quarantined"
    return status.value


def _required(value: int | None, field: str) -> int:
    if value is None:
        raise AttachmentConflict(f"stored attachment {field} is incomplete")
    return value


def _required_text(value: str | None, field: str) -> str:
    if value is None:
        raise AttachmentConflict(f"stored attachment {field} is incomplete")
    return value


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    diagnostic = getattr(getattr(exc, "orig", None), "diag", None)
    constraint = getattr(diagnostic, "constraint_name", "")
    if constraint == "uq_evidence_attachment_finalizations_owner_key":
        raise AttachmentIdempotencyConflict from exc
    raise AttachmentConflict("attachment persistence constraint rejected the transition") from exc
