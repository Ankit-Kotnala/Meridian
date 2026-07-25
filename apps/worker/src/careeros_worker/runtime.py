"""Per-task assembly for Resume Health application services.

Celery's prefork workers call synchronous task functions while the backend uses
async database ports.  Each invocation therefore owns one event loop and one
set of adapters; no asyncpg pool is ever reused by a later ``asyncio.run`` loop.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

import structlog
from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.application_workspace.application import (
    ApplicationWorkspaceService,
)
from careeros.modules.application_workspace.application.models import (
    ApplicationInterviewEvidenceReference,
    ApplicationJobSnapshot,
    ApplicationResumeSnapshot,
    ApplicationSourceEvidenceReference,
)
from careeros.modules.application_workspace.domain import ApplicationEvidencePin
from careeros.modules.application_workspace.infrastructure import (
    SqlAlchemyApplicationWorkspaceUnitOfWorkFactory,
)
from careeros.modules.application_workspace.infrastructure import (
    SystemClock as ApplicationWorkspaceClock,
)
from careeros.modules.application_workspace.infrastructure import (
    UuidIdentifierFactory as ApplicationWorkspaceUuidFactory,
)
from careeros.modules.application_workspace.infrastructure import (
    models as application_workspace_models,  # noqa: F401
)
from careeros.modules.career_analytics.application import (
    AnalyticsRefreshView,
    CareerAnalyticsPolicy,
    CareerAnalyticsService,
)
from careeros.modules.career_analytics.application.worker_query import (
    AnalyticsWorkerJobReference,
)
from careeros.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsOutboxStatus,
    CareerAnalyticsUnavailable,
)
from careeros.modules.career_analytics.infrastructure import (
    ApplicationWorkspaceAnalyticsSource,
    CareerRecordAnalyticsProvider,
    CompositeSupplementalAnalyticsSource,
    RoleReadinessAnalyticsProvider,
    SqlAlchemyCareerAnalyticsUnitOfWorkFactory,
)
from careeros.modules.career_analytics.infrastructure import (
    SystemClock as CareerAnalyticsClock,
)
from careeros.modules.career_analytics.infrastructure import (
    Uuid4IdentifierFactory as CareerAnalyticsUuidFactory,
)
from careeros.modules.career_analytics.infrastructure import (
    models as career_analytics_models,  # noqa: F401
)
from careeros.modules.career_analytics.infrastructure.worker_query import (
    SqlAlchemyCareerAnalyticsWorkerQuery,
)
from careeros.modules.career_record.application import (
    AttachmentCleanupProcessor,
    AttachmentFailureRecorder,
    AttachmentJobReconciler,
    AttachmentLimits,
    AttachmentOutboxDispatcher,
    AttachmentPolicy,
    AttachmentProcessingOutcome,
    AttachmentProcessor,
    AttachmentReconciliationResult,
    AttachmentWorkflowService,
    CareerRecordService,
    CleanupBatchResult,
    SafeAttachmentError,
)
from careeros.modules.career_record.infrastructure import (
    AttachmentAdmissionBridge,
    AttachmentClamAvOptions,
    AttachmentClamAvScanner,
    AttachmentS3ObjectStorage,
    AttachmentS3Options,
    BoundedAttachmentExtractor,
    ResumeHealthSourceQuery,
    SqlAlchemyAttachmentUnitOfWorkFactory,
    SqlAlchemyCareerRecordUnitOfWorkFactory,
)
from careeros.modules.career_record.infrastructure import (
    SystemClock as AttachmentSystemClock,
)
from careeros.modules.career_record.infrastructure import (
    UuidIdentifierFactory as CareerRecordUuidFactory,
)
from careeros.modules.career_record.infrastructure import (
    models as career_record_models,  # noqa: F401
)

# The worker is a composition root: register identity mappings so the shared
# SQLAlchemy metadata can resolve resume-health foreign keys to ``users``.
from careeros.modules.identity.infrastructure import models as identity_models  # noqa: F401
from careeros.modules.networking.application import NetworkingService
from careeros.modules.networking.application.models import NetworkingApplicationReference
from careeros.modules.networking.domain import (
    NetworkingLeaseConflict,
    NetworkingNotFound,
    NetworkingReminderOutboxEntry,
    ReminderOutboxStatus,
)
from careeros.modules.networking.infrastructure import (
    SqlAlchemyNetworkingUnitOfWorkFactory,
)
from careeros.modules.networking.infrastructure import SystemClock as NetworkingClock
from careeros.modules.networking.infrastructure import (
    UuidIdentifierFactory as NetworkingUuidFactory,
)
from careeros.modules.networking.infrastructure import models as networking_models  # noqa: F401
from careeros.modules.resume_health.application import (
    CleanupResult,
    DocumentLimits,
    JobReconciliationResult,
    OutboxDispatcher,
    ProcessingOutcome,
    ResumeHealthProcessor,
    ResumeHealthSourceReader,
    ResumeJobFailureRecorder,
    ResumeJobReconciler,
    ResumeMaintenance,
)
from careeros.modules.resume_health.infrastructure import (
    ClamAvOptions,
    ClamAvScanner,
    LocalDocumentExtractor,
    S3ObjectStorage,
    S3Options,
    SqlAlchemyResumeUnitOfWorkFactory,
    SystemClock,
)
from careeros.modules.role_readiness.application import RoleReadinessService
from careeros.modules.role_readiness.domain.scoring import CareerReadinessSnapshot
from careeros.modules.role_readiness.infrastructure import (
    SqlAlchemyRoleReadinessUnitOfWorkFactory,
)
from careeros.modules.role_readiness.infrastructure import (
    SystemClock as RoleReadinessClock,
)
from careeros.modules.role_readiness.infrastructure import (
    UuidIdentifierFactory as RoleReadinessUuidFactory,
)
from careeros.modules.role_readiness.infrastructure import (
    models as role_readiness_models,  # noqa: F401
)
from celery import Celery  # type: ignore[import-untyped,unused-ignore]
from structlog.contextvars import bind_contextvars

from careeros_worker.config import WorkerSettings
from careeros_worker.publisher import CeleryAnalyticsPublisher, CeleryJobPublisher

logger = structlog.get_logger(__name__)
_EXECUTION_LEASE_GRACE_SECONDS = 30


@dataclass(frozen=True, slots=True)
class OutboxTaskResult:
    published: int
    failed: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class AnalyticsProcessingResult:
    job_id: UUID
    trace_id: str
    status: AnalyticsJobStatus
    attempts: int
    max_attempts: int
    safe_error_code: str | None

    @property
    def retryable(self) -> bool:
        return self.status is AnalyticsJobStatus.RETRY_WAIT


@dataclass(frozen=True, slots=True)
class AnalyticsReconciliationResult:
    recovered_jobs: int
    dead_lettered_jobs: int
    recovered_outbox: int
    dead_lettered_outbox: int
    requeued_deliveries: int


@dataclass(frozen=True, slots=True)
class NetworkingReminderBatchResult:
    claimed: int
    processed: int
    deferred: int
    failed: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class NetworkingReminderRecoveryResult:
    recovered: int
    dead_lettered: int


@dataclass(slots=True)
class _RuntimeResources:
    database: Database
    storage: S3ObjectStorage
    unit_of_work: SqlAlchemyResumeUnitOfWorkFactory
    clock: SystemClock
    scanner: ClamAvScanner
    extractor: LocalDocumentExtractor
    limits: DocumentLimits


@dataclass(slots=True)
class _AttachmentStorageResources:
    database: Database
    storage: AttachmentS3ObjectStorage
    unit_of_work: SqlAlchemyAttachmentUnitOfWorkFactory
    clock: AttachmentSystemClock


@dataclass(slots=True)
class _AttachmentRuntimeResources(_AttachmentStorageResources):
    scanner: AttachmentClamAvScanner
    extractor: BoundedAttachmentExtractor
    limits: AttachmentLimits


class _UnavailableJobSnapshotProvider:
    async def snapshot(self, owner_user_id: UUID, job_id: UUID) -> ApplicationJobSnapshot:
        raise RuntimeError("job snapshots are unavailable in the analytics worker")


class _UnavailableResumeSnapshotProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        version_id: UUID,
    ) -> ApplicationResumeSnapshot:
        raise RuntimeError("resume snapshots are unavailable in the analytics worker")


class _UnavailableEvidenceSnapshotProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]:
        raise RuntimeError("evidence snapshots are unavailable in the analytics worker")

    async def validate_current(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationInterviewEvidenceReference, ...],
    ) -> None:
        raise RuntimeError("evidence validation is unavailable in the analytics worker")


class _UnavailableCareerSnapshotProvider:
    async def snapshot(self, owner_user_id: UUID) -> CareerReadinessSnapshot:
        raise RuntimeError("career snapshots are unavailable in the analytics worker")


class _NoApplicationReferenceProvider:
    async def get_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> NetworkingApplicationReference | None:
        return None


@asynccontextmanager
async def _runtime_resources(settings: WorkerSettings) -> AsyncIterator[_RuntimeResources]:
    if settings.malware_scanner_provider != "clamav":
        raise RuntimeError("a fail-closed malware scanner is required for document processing")

    database = _database(settings)
    storage: S3ObjectStorage | None = None
    try:
        storage = S3ObjectStorage(
            S3Options(
                internal_endpoint_url=settings.s3_endpoint_url,
                public_endpoint_url=settings.s3_public_endpoint_url,
                region=settings.s3_region,
                bucket=settings.s3_bucket,
                access_key_id=settings.s3_access_key_id.get_secret_value(),
                secret_access_key=settings.s3_secret_access_key.get_secret_value(),
                use_ssl=settings.s3_use_ssl,
                connect_timeout_seconds=settings.database_connect_timeout_seconds,
                read_timeout_seconds=settings.database_command_timeout_seconds,
            )
        )
        yield _RuntimeResources(
            database=database,
            storage=storage,
            unit_of_work=SqlAlchemyResumeUnitOfWorkFactory(database),
            clock=SystemClock(),
            scanner=ClamAvScanner(
                ClamAvOptions(
                    host=settings.clamav_host,
                    port=settings.clamav_port,
                    timeout_seconds=settings.clamav_timeout_seconds,
                )
            ),
            extractor=LocalDocumentExtractor(),
            limits=DocumentLimits(
                max_upload_bytes=settings.document_max_bytes,
                max_pdf_pages=settings.document_max_pages,
                max_archive_entries=settings.document_max_archive_entries,
                max_archive_uncompressed_bytes=settings.document_max_uncompressed_bytes,
                max_archive_ratio=settings.document_max_compression_ratio,
                max_extracted_characters=settings.document_max_extracted_characters,
                max_extracted_blocks=settings.document_max_extracted_blocks,
                max_serialized_artifact_bytes=(settings.document_max_serialized_artifact_bytes),
                processing_timeout_seconds=settings.document_processing_timeout_seconds,
                temp_root=settings.document_temp_root,
            ),
        )
    finally:
        try:
            if storage is not None:
                await storage.dispose()
        finally:
            await database.dispose()


@asynccontextmanager
async def _attachment_storage_resources(
    settings: WorkerSettings,
) -> AsyncIterator[_AttachmentStorageResources]:
    database = _database(settings)
    storage: AttachmentS3ObjectStorage | None = None
    try:
        storage = _attachment_storage(settings)
        yield _AttachmentStorageResources(
            database=database,
            storage=storage,
            unit_of_work=SqlAlchemyAttachmentUnitOfWorkFactory(database),
            clock=AttachmentSystemClock(),
        )
    finally:
        try:
            if storage is not None:
                await storage.dispose()
        finally:
            await database.dispose()


@asynccontextmanager
async def _attachment_runtime_resources(
    settings: WorkerSettings,
) -> AsyncIterator[_AttachmentRuntimeResources]:
    if settings.malware_scanner_provider != "clamav":
        raise RuntimeError("a fail-closed malware scanner is required for attachment processing")
    async with _attachment_storage_resources(settings) as resources:
        yield _AttachmentRuntimeResources(
            database=resources.database,
            storage=resources.storage,
            unit_of_work=resources.unit_of_work,
            clock=resources.clock,
            scanner=AttachmentClamAvScanner(
                AttachmentClamAvOptions(
                    host=settings.clamav_host,
                    port=settings.clamav_port,
                    timeout_seconds=settings.clamav_timeout_seconds,
                )
            ),
            extractor=BoundedAttachmentExtractor(),
            limits=_attachment_limits(settings),
        )


async def process_resume_job(
    settings: WorkerSettings,
    job_id: UUID,
    trace_id: str,
    execution_token: str,
) -> ProcessingOutcome:
    async with _runtime_resources(settings) as resources:
        processor = _processor(resources, settings)
        return await processor.process_job(job_id, trace_id, execution_token=execution_token)


async def process_attachment_job(
    settings: WorkerSettings,
    job_id: UUID,
    execution_token: str,
) -> AttachmentProcessingOutcome:
    async with _attachment_runtime_resources(settings) as resources:
        processor = AttachmentProcessor(
            unit_of_work=resources.unit_of_work,
            clock=resources.clock,
            storage=resources.storage,
            scanner=resources.scanner,
            extractor=resources.extractor,
            limits=resources.limits,
            policy=_attachment_policy(settings),
        )
        return await processor.process_job(job_id, execution_token)


async def process_career_analytics_job(
    settings: WorkerSettings,
    job_id: UUID,
) -> AnalyticsProcessingResult:
    """Process one persisted analytics refresh without broker-carried content."""

    database = _database(settings)
    try:
        query = SqlAlchemyCareerAnalyticsWorkerQuery(database)
        before = await query.get_job_reference(job_id)
        bind_contextvars(job_id=str(job_id), trace_id=before.trace_id)
        if before.status in {
            AnalyticsJobStatus.COMPLETED,
            AnalyticsJobStatus.DEAD_LETTER,
        }:
            return _analytics_result_from_reference(before)
        service = _career_analytics_service(database, settings)
        try:
            view = await service.process_refresh(job_id, trace_id=before.trace_id)
        except CareerAnalyticsUnavailable:
            # Aggregation failures are recorded durably by the application
            # service before it raises. Read only safe state for task control.
            after = await query.get_job_reference(job_id)
            if after.status in {
                AnalyticsJobStatus.RETRY_WAIT,
                AnalyticsJobStatus.DEAD_LETTER,
            }:
                return _analytics_result_from_reference(after)
            raise
        return _analytics_result_from_view(view, trace_id=before.trace_id)
    finally:
        await database.dispose()


async def dispatch_career_analytics_outbox(
    settings: WorkerSettings,
    application: Celery,
    limit: int,
) -> OutboxTaskResult:
    """Publish a bounded batch and durably acknowledge each broker handoff."""

    database = _database(settings)
    try:
        service = _career_analytics_service(database, settings)
        query = SqlAlchemyCareerAnalyticsWorkerQuery(database)
        publisher = CeleryAnalyticsPublisher(application)
        claimed = await service.claim_outbox(limit=limit)
        published = 0
        failed = 0
        dead_lettered = 0
        for message in claimed:
            try:
                await publisher.publish(message.job_id)
            except Exception:
                await service.mark_outbox_failed(
                    message.message_id,
                    lease_token=message.lease_token,
                    safe_error_code="publish_failed",
                )
                status = await query.get_outbox_status(message.message_id)
                if status is AnalyticsOutboxStatus.DEAD_LETTER:
                    dead_lettered += 1
                else:
                    failed += 1
            else:
                # If this write fails, the lease reconciler safely republishes.
                # The refresh use case makes that duplicate delivery idempotent.
                await service.mark_outbox_published(
                    message.message_id,
                    lease_token=message.lease_token,
                    job_version_at_claim=message.job_version_at_claim,
                )
                published += 1
        return OutboxTaskResult(
            published=published,
            failed=failed,
            dead_lettered=dead_lettered,
        )
    finally:
        await database.dispose()


async def reconcile_career_analytics(
    settings: WorkerSettings,
    limit: int,
) -> AnalyticsReconciliationResult:
    """Recover leases and durably re-arm due identifier-only refresh work."""

    database = _database(settings)
    try:
        service = _career_analytics_service(database, settings)
        outcome = await service.reconcile_expired(limit=limit)
        return AnalyticsReconciliationResult(
            recovered_jobs=outcome.recovered_jobs,
            dead_lettered_jobs=outcome.dead_lettered_jobs,
            recovered_outbox=outcome.recovered_outbox,
            dead_lettered_outbox=outcome.dead_lettered_outbox,
            requeued_deliveries=outcome.requeued_deliveries,
        )
    finally:
        await database.dispose()


async def process_due_networking_reminders(
    settings: WorkerSettings,
    limit: int,
) -> NetworkingReminderBatchResult:
    """Materialize local recurrence state without any external delivery adapter."""

    database = _database(settings)
    clock = NetworkingClock()
    try:
        service = _networking_service(database)
        claimed = await service.claim_due_reminders(
            now=clock.now(),
            lease_seconds=settings.networking_reminder_lease_seconds,
            limit=limit,
        )
        processed = 0
        deferred = 0
        failed = 0
        dead_lettered = 0
        for entry in claimed:
            bind_contextvars(
                trace_id=entry.trace_id,
                networking_occurrence_id=str(entry.occurrence_id),
                networking_outbox_id=str(entry.id),
            )
            try:
                await service.materialize_due_reminder(
                    entry.id,
                    lease_token=_reminder_lease_token(entry),
                    now=clock.now(),
                )
            except (NetworkingLeaseConflict, NetworkingNotFound):
                # Consent withdrawal, cancellation, or duplicate processing won
                # the lock. No local or external action remains to perform.
                deferred += 1
                logger.info("networking_local_reminder_deferred")
            except Exception:
                try:
                    outcome = await _fail_local_reminder(
                        service,
                        entry,
                        clock.now(),
                        settings.networking_reminder_retry_seconds,
                        "local_reminder_processing_failed",
                    )
                except (NetworkingLeaseConflict, NetworkingNotFound):
                    deferred += 1
                    logger.info("networking_local_reminder_deferred")
                else:
                    if outcome is ReminderOutboxStatus.DEAD_LETTER:
                        dead_lettered += 1
                        logger.error("networking_local_reminder_dead_lettered")
                    else:
                        failed += 1
                        logger.warning("networking_local_reminder_retry_scheduled")
            else:
                processed += 1
                logger.info("networking_local_reminder_processed")
        return NetworkingReminderBatchResult(
            claimed=len(claimed),
            processed=processed,
            deferred=deferred,
            failed=failed,
            dead_lettered=dead_lettered,
        )
    finally:
        await database.dispose()


async def reconcile_networking_reminders(
    settings: WorkerSettings,
    limit: int,
) -> NetworkingReminderRecoveryResult:
    """Recover content-free local reminder leases through durable state only."""

    database = _database(settings)
    clock = NetworkingClock()
    try:
        recovered = await _networking_service(database).recover_expired_leases(
            now=clock.now(),
            limit=limit,
        )
        for entry in recovered:
            bind_contextvars(
                trace_id=entry.trace_id,
                networking_occurrence_id=str(entry.occurrence_id),
                networking_outbox_id=str(entry.id),
            )
            logger.warning(
                "networking_local_reminder_lease_reconciled",
                outbox_status=entry.status.value,
                attempt_count=entry.attempt_count,
            )
        return NetworkingReminderRecoveryResult(
            recovered=len(recovered),
            dead_lettered=sum(
                entry.status is ReminderOutboxStatus.DEAD_LETTER for entry in recovered
            ),
        )
    finally:
        await database.dispose()


async def record_resume_failure(
    settings: WorkerSettings,
    job_id: UUID,
    trace_id: str,
    safe_error_code: str,
    *,
    retryable: bool,
    exhausted: bool,
    execution_token: str,
) -> ProcessingOutcome:
    database = _database(settings)
    try:
        recorder = ResumeJobFailureRecorder(
            unit_of_work=SqlAlchemyResumeUnitOfWorkFactory(database),
            clock=SystemClock(),
            execution_lease_seconds=(
                settings.task_time_limit_seconds + _EXECUTION_LEASE_GRACE_SECONDS
            ),
        )
        return await recorder.record_task_failure(
            job_id,
            trace_id,
            safe_error_code,
            retryable=retryable,
            exhausted=exhausted,
            execution_token=execution_token,
        )
    finally:
        await database.dispose()


async def record_attachment_failure(
    settings: WorkerSettings,
    job_id: UUID,
    safe_error_code: SafeAttachmentError,
    *,
    exhausted: bool,
    execution_token: str,
) -> AttachmentProcessingOutcome:
    database = _database(settings)
    try:
        recorder = AttachmentFailureRecorder(
            unit_of_work=SqlAlchemyAttachmentUnitOfWorkFactory(database),
            clock=AttachmentSystemClock(),
            policy=_attachment_policy(settings),
        )
        return await recorder.record_failure(
            job_id,
            execution_token,
            safe_error_code,
            exhausted=exhausted,
        )
    finally:
        await database.dispose()


async def dispatch_resume_outbox(
    settings: WorkerSettings,
    application: Celery,
    limit: int,
) -> OutboxTaskResult:
    database = _database(settings)
    try:
        dispatcher = OutboxDispatcher(
            unit_of_work=SqlAlchemyResumeUnitOfWorkFactory(database),
            publisher=CeleryJobPublisher(application),
            clock=SystemClock(),
        )
        result = await dispatcher.dispatch_pending(limit)
        return OutboxTaskResult(
            published=result.published,
            failed=result.failed,
            dead_lettered=result.dead_lettered,
        )
    finally:
        await database.dispose()


async def dispatch_attachment_outbox(
    settings: WorkerSettings,
    application: Celery,
    limit: int,
) -> OutboxTaskResult:
    database = _database(settings)
    try:
        dispatcher = AttachmentOutboxDispatcher(
            unit_of_work=SqlAlchemyAttachmentUnitOfWorkFactory(database),
            publisher=CeleryJobPublisher(application),
            clock=AttachmentSystemClock(),
            policy=_attachment_policy(settings),
        )
        result = await dispatcher.dispatch_pending(limit)
        return OutboxTaskResult(
            published=result.published,
            failed=result.failed,
            dead_lettered=result.dead_lettered,
        )
    finally:
        await database.dispose()


async def reconcile_stale_attachment_jobs(
    settings: WorkerSettings,
    limit: int,
) -> AttachmentReconciliationResult:
    database = _database(settings)
    try:
        reconciler = AttachmentJobReconciler(
            unit_of_work=SqlAlchemyAttachmentUnitOfWorkFactory(database),
            clock=AttachmentSystemClock(),
            stale_after_seconds=settings.attachment_job_reconciliation_stale_seconds,
            policy=_attachment_policy(settings),
        )
        return await reconciler.reconcile_stale(limit)
    finally:
        await database.dispose()


async def reconcile_stale_resume_jobs(
    settings: WorkerSettings,
    limit: int,
) -> JobReconciliationResult:
    """Recover orphaned deliveries through database-only durable state."""
    database = _database(settings)
    try:
        reconciler = ResumeJobReconciler(
            unit_of_work=SqlAlchemyResumeUnitOfWorkFactory(database),
            clock=SystemClock(),
            stale_after_seconds=settings.resume_job_reconciliation_stale_seconds,
        )
        return await reconciler.reconcile_stale(limit)
    finally:
        await database.dispose()


async def cleanup_expired_resume_data(
    settings: WorkerSettings,
    limit: int,
) -> CleanupResult:
    async with _runtime_resources(settings) as resources:
        maintenance = ResumeMaintenance(
            unit_of_work=resources.unit_of_work,
            clock=resources.clock,
            storage=resources.storage,
        )
        return await maintenance.purge_expired_guest_sessions(limit)


async def cleanup_attachment_objects(
    settings: WorkerSettings,
    limit: int,
) -> CleanupBatchResult:
    async with _attachment_storage_resources(settings) as resources:
        processor = AttachmentCleanupProcessor(
            unit_of_work=resources.unit_of_work,
            storage=resources.storage,
            clock=resources.clock,
        )
        return await processor.process_due(limit)


def _career_analytics_service(
    database: Database,
    settings: WorkerSettings,
) -> CareerAnalyticsService:
    """Compose only owner-scoped query use cases needed for aggregation."""

    attachment_workflow = AttachmentWorkflowService(
        unit_of_work=SqlAlchemyAttachmentUnitOfWorkFactory(database),
        clock=AttachmentSystemClock(),
        storage=_attachment_storage(settings),
        limits=_attachment_limits(settings),
        policy=_attachment_policy(settings),
    )
    career_record = CareerRecordService(
        unit_of_work=SqlAlchemyCareerRecordUnitOfWorkFactory(database),
        clock=AttachmentSystemClock(),
        identifiers=CareerRecordUuidFactory(),
        resume_sources=ResumeHealthSourceQuery(
            ResumeHealthSourceReader(SqlAlchemyResumeUnitOfWorkFactory(database))
        ),
        attachments=AttachmentAdmissionBridge(attachment_workflow),
        verification_authority=None,
    )
    role_readiness = RoleReadinessService(
        unit_of_work=SqlAlchemyRoleReadinessUnitOfWorkFactory(database),
        clock=RoleReadinessClock(),
        identifiers=RoleReadinessUuidFactory(),
        career_snapshots=_UnavailableCareerSnapshotProvider(),
    )
    application_workspace = ApplicationWorkspaceService(
        unit_of_work=SqlAlchemyApplicationWorkspaceUnitOfWorkFactory(database),
        clock=ApplicationWorkspaceClock(),
        identifiers=ApplicationWorkspaceUuidFactory(),
        jobs=_UnavailableJobSnapshotProvider(),
        resumes=_UnavailableResumeSnapshotProvider(),
        evidence=_UnavailableEvidenceSnapshotProvider(),
    )
    return CareerAnalyticsService(
        unit_of_work=SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database),
        clock=CareerAnalyticsClock(),
        identifiers=CareerAnalyticsUuidFactory(),
        applications=ApplicationWorkspaceAnalyticsSource(application_workspace),
        supplemental=CompositeSupplementalAnalyticsSource(
            readiness=cast(RoleReadinessAnalyticsProvider, role_readiness),
            career_record=cast(CareerRecordAnalyticsProvider, career_record),
        ),
        policy=CareerAnalyticsPolicy(
            max_attempts=settings.analytics_max_attempts,
            lease_seconds=settings.analytics_job_lease_seconds,
            retry_seconds=settings.analytics_retry_seconds,
        ),
    )


def _networking_service(database: Database) -> NetworkingService:
    return NetworkingService(
        unit_of_work=SqlAlchemyNetworkingUnitOfWorkFactory(database),
        clock=NetworkingClock(),
        identifiers=NetworkingUuidFactory(),
        applications=_NoApplicationReferenceProvider(),
    )


async def _fail_local_reminder(
    service: NetworkingService,
    entry: NetworkingReminderOutboxEntry,
    now: datetime,
    retry_seconds: int,
    error_code: str,
) -> ReminderOutboxStatus:
    if entry.lease_token is None:
        raise NetworkingLeaseConflict
    failed = await service.fail_reminder(
        entry.id,
        lease_token=entry.lease_token,
        error_code=error_code,
        retry_at=now + timedelta(seconds=retry_seconds),
        now=now,
    )
    return failed.status


def _reminder_lease_token(entry: NetworkingReminderOutboxEntry) -> UUID:
    if entry.lease_token is None:
        raise NetworkingLeaseConflict
    return entry.lease_token


def _analytics_result_from_reference(
    value: AnalyticsWorkerJobReference,
) -> AnalyticsProcessingResult:
    return AnalyticsProcessingResult(
        job_id=value.job_id,
        trace_id=value.trace_id,
        status=value.status,
        attempts=value.attempts,
        max_attempts=value.max_attempts,
        safe_error_code=value.safe_error_code,
    )


def _analytics_result_from_view(
    value: AnalyticsRefreshView,
    *,
    trace_id: str,
) -> AnalyticsProcessingResult:
    return AnalyticsProcessingResult(
        job_id=value.id,
        trace_id=trace_id,
        status=value.status,
        attempts=value.attempts,
        max_attempts=value.max_attempts,
        safe_error_code=value.safe_error_code,
    )


def _processor(resources: _RuntimeResources, settings: WorkerSettings) -> ResumeHealthProcessor:
    return ResumeHealthProcessor(
        unit_of_work=resources.unit_of_work,
        clock=resources.clock,
        storage=resources.storage,
        scanner=resources.scanner,
        extractor=resources.extractor,
        limits=resources.limits,
        execution_lease_seconds=(settings.task_time_limit_seconds + _EXECUTION_LEASE_GRACE_SECONDS),
    )


def _database(settings: WorkerSettings) -> Database:
    return Database(
        DatabaseOptions(
            url=settings.database_url.get_secret_value(),
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            connect_timeout_seconds=settings.database_connect_timeout_seconds,
            command_timeout_seconds=settings.database_command_timeout_seconds,
        )
    )


def _attachment_storage(settings: WorkerSettings) -> AttachmentS3ObjectStorage:
    return AttachmentS3ObjectStorage(
        AttachmentS3Options(
            internal_endpoint_url=settings.s3_endpoint_url,
            public_endpoint_url=settings.s3_public_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id.get_secret_value(),
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            use_ssl=settings.s3_use_ssl,
            connect_timeout_seconds=settings.database_connect_timeout_seconds,
            read_timeout_seconds=settings.database_command_timeout_seconds,
        )
    )


def _attachment_limits(settings: WorkerSettings) -> AttachmentLimits:
    return AttachmentLimits(
        max_upload_bytes=settings.document_max_bytes,
        max_pdf_pages=settings.document_max_pages,
        max_archive_entries=settings.document_max_archive_entries,
        max_archive_uncompressed_bytes=settings.document_max_uncompressed_bytes,
        max_archive_ratio=settings.document_max_compression_ratio,
        max_extracted_characters=settings.document_max_extracted_characters,
        max_extracted_blocks=settings.document_max_extracted_blocks,
        processing_timeout_seconds=settings.document_processing_timeout_seconds,
        temp_root=(settings.document_temp_root / "attachments").resolve(),
    )


def _attachment_policy(settings: WorkerSettings) -> AttachmentPolicy:
    return AttachmentPolicy(
        execution_lease_seconds=(settings.task_time_limit_seconds + _EXECUTION_LEASE_GRACE_SECONDS),
        max_processing_attempts=max(1, settings.task_max_retries + 1),
    )
