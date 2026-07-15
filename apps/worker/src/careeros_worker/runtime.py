"""Per-task assembly for Resume Health application services.

Celery's prefork workers call synchronous task functions while the backend uses
async database ports.  Each invocation therefore owns one event loop and one
set of adapters; no asyncpg pool is ever reused by a later ``asyncio.run`` loop.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database

# The worker is a composition root: register identity mappings so the shared
# SQLAlchemy metadata can resolve resume-health foreign keys to ``users``.
from careeros.modules.identity.infrastructure import models as identity_models  # noqa: F401
from careeros.modules.resume_health.application import (
    CleanupResult,
    DocumentLimits,
    JobReconciliationResult,
    OutboxDispatcher,
    ProcessingOutcome,
    ResumeHealthProcessor,
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
from celery import Celery

from careeros_worker.config import WorkerSettings
from careeros_worker.publisher import CeleryJobPublisher

_EXECUTION_LEASE_GRACE_SECONDS = 30


@dataclass(frozen=True, slots=True)
class OutboxTaskResult:
    published: int
    failed: int
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


async def process_resume_job(
    settings: WorkerSettings,
    job_id: UUID,
    trace_id: str,
    execution_token: str,
) -> ProcessingOutcome:
    async with _runtime_resources(settings) as resources:
        processor = _processor(resources, settings)
        return await processor.process_job(job_id, trace_id, execution_token=execution_token)


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
