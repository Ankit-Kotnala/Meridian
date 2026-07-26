"""Celery entry points with identifier-only payloads and durable job state."""

import asyncio
import hashlib
from typing import NoReturn, TypedDict
from uuid import UUID, uuid4

import structlog
from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from careeros.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    CareerAnalyticsConflict,
)
from careeros.modules.career_record.application import (
    CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
    DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
    AttachmentProcessingOutcome,
    CleanupBatchResult,
    SafeAttachmentError,
)
from careeros.modules.resume_builder.domain import ResumeExportOperation
from careeros.modules.resume_health.application import (
    CLEANUP_RESUME_TASK,
    DISPATCH_OUTBOX_TASK,
    PROCESS_RESUME_TASK,
    RECONCILE_RESUME_TASK,
    JobReconciliationResult,
    ProcessingOutcome,
)
from structlog.contextvars import bind_contextvars

from careeros_worker import __version__
from careeros_worker.app import celery_app
from careeros_worker.base import RetryableTaskError, SafeTask
from careeros_worker.config import WorkerSettings, get_settings
from careeros_worker.payloads import parse_identifier_payload, parse_job_payload
from careeros_worker.runtime import (
    AnalyticsProcessingResult,
    cleanup_attachment_objects,
    cleanup_expired_resume_data,
    dispatch_attachment_outbox,
    dispatch_career_analytics_outbox,
    dispatch_resume_export_outbox,
    dispatch_resume_outbox,
    process_attachment_job,
    process_career_analytics_job,
    process_due_networking_reminders,
    process_resume_export,
    process_resume_export_cleanup,
    process_resume_job,
    reconcile_career_analytics,
    reconcile_networking_reminders,
    reconcile_resume_exports,
    reconcile_stale_attachment_jobs,
    reconcile_stale_resume_jobs,
    record_attachment_failure,
    record_resume_failure,
)
from careeros_worker.task_names import (
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    PROCESS_RESUME_EXPORT_TASK,
    RECONCILE_CAREER_ANALYTICS_TASK,
    RECONCILE_NETWORKING_REMINDERS_TASK,
    RECONCILE_RESUME_EXPORTS_TASK,
)

PING_TASK_NAME = "careeros.worker.health.ping"
_MAINTENANCE_LIMIT = 100
logger = structlog.get_logger(__name__)


class PingResult(TypedDict):
    status: str
    service: str
    version: str


class ProcessingTaskResult(TypedDict):
    job_id: str
    status: str
    retryable: bool
    safe_error_code: str | None


class ResumeExportTaskResult(TypedDict):
    export_id: str
    status: str
    retryable: bool
    safe_error_code: str | None


class OutboxResult(TypedDict):
    published: int
    failed: int
    dead_lettered: int


class CleanupTaskResult(TypedDict):
    expired_uploads: int
    queued_guest_deletions: int
    revoked_guest_sessions: int
    object_cleanups_completed: int
    object_cleanup_failures: int
    object_cleanup_dead_letters: int


class ReconciliationTaskResult(TypedDict):
    requeued: int
    dead_lettered: int


class ResumeExportReconciliationTaskResult(TypedDict):
    requeued: int
    dead_lettered: int
    object_cleanups_completed: int
    object_cleanup_failures: int
    object_cleanup_dead_letters: int


class AttachmentCleanupTaskResult(TypedDict):
    completed: int
    failed: int
    dead_lettered: int


class AnalyticsReconciliationTaskResult(TypedDict):
    recovered_jobs: int
    dead_lettered_jobs: int
    recovered_outbox: int
    dead_lettered_outbox: int
    requeued_deliveries: int


class NetworkingReminderTaskResult(TypedDict):
    claimed: int
    processed: int
    deferred: int
    failed: int
    dead_lettered: int


class NetworkingReminderRecoveryTaskResult(TypedDict):
    recovered: int
    dead_lettered: int


@celery_app.task(name=PING_TASK_NAME, ignore_result=False)  # type: ignore[untyped-decorator]
def ping() -> PingResult:
    """Return deterministic liveness metadata without touching infrastructure."""
    return {
        "status": "ok",
        "service": "careeros-worker",
        "version": __version__,
    }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=PROCESS_RESUME_EXPORT_TASK,
)
def process_resume_builder_export(
    task: SafeTask,
    *,
    export_id: str,
    operation: str = ResumeExportOperation.RENDER.value,
    trace_id: str,
) -> ResumeExportTaskResult:
    """Render and verify one pinned resume version from durable state."""

    parsed_export_id, parsed_trace_id = parse_job_payload(export_id, trace_id)
    bind_contextvars(export_id=str(parsed_export_id), trace_id=parsed_trace_id)
    parsed_operation = ResumeExportOperation(operation)
    try:
        processor = (
            process_resume_export_cleanup
            if parsed_operation is ResumeExportOperation.DELETE
            else process_resume_export
        )
        outcome = asyncio.run(processor(get_settings(), parsed_export_id, _execution_token(task)))
    except Exception:
        raise RetryableTaskError("resume_export_runtime_unavailable") from None
    return {
        "export_id": str(outcome.export_id),
        "status": outcome.status.value,
        "retryable": outcome.retryable,
        "safe_error_code": outcome.safe_error_code,
    }


@celery_app.task(name=DISPATCH_RESUME_EXPORT_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_resume_builder_export_outbox(
    limit: int = _MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Publish bounded identifier-only export jobs from the transactional outbox."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(
            dispatch_resume_export_outbox(get_settings(), celery_app, validated_limit)
        )
    except Exception:
        raise RetryableTaskError("resume_export_outbox_dispatch_unavailable") from None
    if result.failed:
        logger.warning("resume_export_outbox_publish_deferred", failed=result.failed)
    if result.dead_lettered:
        logger.error("resume_export_outbox_publish_dead_lettered", count=result.dead_lettered)
    return {
        "published": result.published,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_RESUME_EXPORTS_TASK)  # type: ignore[untyped-decorator]
def reconcile_resume_builder_exports(
    limit: int = _MAINTENANCE_LIMIT,
) -> ResumeExportReconciliationTaskResult:
    """Recover lost export deliveries, expired leases, and orphan objects."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(reconcile_resume_exports(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("resume_export_reconciliation_unavailable") from None
    if result.requeued:
        logger.warning("resume_exports_requeued", count=result.requeued)
    if result.dead_lettered:
        logger.error("resume_exports_recovery_dead_lettered", count=result.dead_lettered)
    if result.object_cleanup_failures:
        logger.warning(
            "resume_export_object_cleanup_deferred",
            count=result.object_cleanup_failures,
        )
    if result.object_cleanup_dead_letters:
        logger.error(
            "resume_export_object_cleanup_dead_lettered",
            count=result.object_cleanup_dead_letters,
        )
    return {
        "requeued": result.requeued,
        "dead_lettered": result.dead_lettered,
        "object_cleanups_completed": result.object_cleanups_completed,
        "object_cleanup_failures": result.object_cleanup_failures,
        "object_cleanup_dead_letters": result.object_cleanup_dead_letters,
    }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
)
def process_career_analytics_refresh(
    task: SafeTask,
    *,
    job_id: str,
) -> ProcessingTaskResult:
    """Aggregate one durable refresh using a UUID-only broker payload."""

    parsed_job_id = parse_identifier_payload(job_id)
    bind_contextvars(job_id=str(parsed_job_id))
    settings = get_settings()
    try:
        outcome = asyncio.run(process_career_analytics_job(settings, parsed_job_id))
    except SoftTimeLimitExceeded:
        _schedule_analytics_retry(
            task,
            settings,
            "analytics_soft_time_limit",
            countdown=(
                settings.analytics_job_lease_seconds
                + settings.analytics_reconciliation_interval_seconds
                + 5
            ),
        )
    except CareerAnalyticsConflict:
        _schedule_analytics_retry(
            task,
            settings,
            "analytics_lease_active",
            countdown=(
                settings.analytics_job_lease_seconds
                + settings.analytics_reconciliation_interval_seconds
                + 5
            ),
        )
    except Exception:
        raise RetryableTaskError("analytics_runtime_unavailable") from None
    bind_contextvars(trace_id=outcome.trace_id)
    if outcome.retryable:
        logger.warning(
            "analytics_job_durable_retry_queued",
            safe_error_code=outcome.safe_error_code or "analytics_retry_scheduled",
        )
    elif outcome.status is AnalyticsJobStatus.DEAD_LETTER:
        logger.error(
            "analytics_job_dead_lettered",
            safe_error_code=outcome.safe_error_code or "analytics_retry_exhausted",
            attempts=outcome.attempts,
            max_attempts=outcome.max_attempts,
        )
    return _analytics_processing_result(outcome)


@celery_app.task(name=DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_career_analytics_refresh_outbox(
    limit: int = _MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Dispatch a bounded analytics outbox batch with UUID-only messages."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(
            dispatch_career_analytics_outbox(
                get_settings(),
                celery_app,
                validated_limit,
            )
        )
    except Exception:
        raise RetryableTaskError("analytics_outbox_dispatch_unavailable") from None
    if result.failed:
        logger.warning("analytics_outbox_publish_deferred", count=result.failed)
    if result.dead_lettered:
        logger.error("analytics_outbox_publish_dead_lettered", count=result.dead_lettered)
    return {
        "published": result.published,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_CAREER_ANALYTICS_TASK)  # type: ignore[untyped-decorator]
def reconcile_career_analytics_jobs(
    limit: int = _MAINTENANCE_LIMIT,
) -> AnalyticsReconciliationTaskResult:
    """Recover expired analytics leases and due lost deliveries."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(
            reconcile_career_analytics(
                get_settings(),
                validated_limit,
            )
        )
    except Exception:
        raise RetryableTaskError("analytics_reconciliation_unavailable") from None
    if result.recovered_jobs or result.recovered_outbox or result.requeued_deliveries:
        logger.warning(
            "analytics_work_recovered",
            jobs=result.recovered_jobs,
            outbox=result.recovered_outbox,
            deliveries=result.requeued_deliveries,
        )
    if result.dead_lettered_jobs or result.dead_lettered_outbox:
        logger.error(
            "analytics_recovery_dead_lettered",
            jobs=result.dead_lettered_jobs,
            outbox=result.dead_lettered_outbox,
        )
    return {
        "recovered_jobs": result.recovered_jobs,
        "dead_lettered_jobs": result.dead_lettered_jobs,
        "recovered_outbox": result.recovered_outbox,
        "dead_lettered_outbox": result.dead_lettered_outbox,
        "requeued_deliveries": result.requeued_deliveries,
    }


@celery_app.task(name=PROCESS_NETWORKING_LOCAL_REMINDERS_TASK)  # type: ignore[untyped-decorator]
def process_networking_local_reminders(
    limit: int = _MAINTENANCE_LIMIT,
) -> NetworkingReminderTaskResult:
    """Advance local reminder occurrences without an external-send capability."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(process_due_networking_reminders(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("networking_reminder_processing_unavailable") from None
    if result.failed:
        logger.warning("networking_local_reminders_deferred", count=result.failed)
    if result.dead_lettered:
        logger.error(
            "networking_local_reminders_dead_lettered",
            count=result.dead_lettered,
        )
    return {
        "claimed": result.claimed,
        "processed": result.processed,
        "deferred": result.deferred,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_NETWORKING_REMINDERS_TASK)  # type: ignore[untyped-decorator]
def reconcile_networking_local_reminders(
    limit: int = _MAINTENANCE_LIMIT,
) -> NetworkingReminderRecoveryTaskResult:
    """Recover expired local reminder leases with no content payload."""

    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(reconcile_networking_reminders(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("networking_reminder_reconciliation_unavailable") from None
    if result.recovered:
        logger.warning("networking_local_reminder_leases_recovered", count=result.recovered)
    if result.dead_lettered:
        logger.error(
            "networking_local_reminders_recovery_dead_lettered",
            count=result.dead_lettered,
        )
    return {
        "recovered": result.recovered,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=PROCESS_RESUME_TASK,
)
def process_resume_health(
    task: SafeTask,
    *,
    job_id: str,
    trace_id: str,
) -> ProcessingTaskResult:
    """Process one durable job; document bytes and text never enter Celery."""
    parsed_job_id, parsed_trace_id = parse_job_payload(job_id, trace_id)
    execution_token = _execution_token(task)
    bind_contextvars(job_id=str(parsed_job_id), trace_id=parsed_trace_id)
    settings = get_settings()
    try:
        outcome = asyncio.run(
            process_resume_job(
                settings,
                parsed_job_id,
                parsed_trace_id,
                execution_token,
            )
        )
    except SoftTimeLimitExceeded:
        return _record_runtime_failure(
            task,
            settings,
            parsed_job_id,
            parsed_trace_id,
            "worker_soft_time_limit",
            execution_token,
        )
    except Exception:
        return _record_runtime_failure(
            task,
            settings,
            parsed_job_id,
            parsed_trace_id,
            "worker_runtime_unavailable",
            execution_token,
        )

    if outcome.retryable:
        if outcome.safe_error_code == "execution_lease_active":
            _schedule_lease_retry(task, settings)
        if _retries_exhausted(task, settings):
            try:
                outcome = asyncio.run(
                    record_resume_failure(
                        settings,
                        parsed_job_id,
                        parsed_trace_id,
                        outcome.safe_error_code or "processing_retry_exhausted",
                        retryable=True,
                        exhausted=True,
                        execution_token=execution_token,
                    )
                )
            except Exception:
                raise RetryableTaskError("durable_failure_record_unavailable") from None
        else:
            _schedule_retry(task, outcome.safe_error_code or "processing_retryable_failure")
    return _processing_result(outcome)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=PROCESS_EVIDENCE_ATTACHMENT_TASK,
)
def process_evidence_attachment(
    task: SafeTask,
    *,
    job_id: str,
    trace_id: str,
) -> ProcessingTaskResult:
    """Process one private attachment using only durable identifiers."""
    parsed_job_id, parsed_trace_id = parse_job_payload(job_id, trace_id)
    execution_token = _execution_token(task)
    bind_contextvars(job_id=str(parsed_job_id), trace_id=parsed_trace_id)
    settings = get_settings()
    try:
        outcome = asyncio.run(process_attachment_job(settings, parsed_job_id, execution_token))
    except SoftTimeLimitExceeded:
        return _record_attachment_runtime_failure(
            task,
            settings,
            parsed_job_id,
            SafeAttachmentError.PROCESSING_TIMEOUT,
            execution_token,
        )
    except Exception:
        return _record_attachment_runtime_failure(
            task,
            settings,
            parsed_job_id,
            SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
            execution_token,
        )
    # Retryable processor outcomes already have durable retry/outbox state. A
    # second Celery retry path would duplicate work and weaken fencing.
    return _attachment_processing_result(outcome)


@celery_app.task(name=DISPATCH_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_resume_health_outbox(limit: int = _MAINTENANCE_LIMIT) -> OutboxResult:
    """Publish pending transactional-outbox rows using the allowlisted task adapter."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(dispatch_resume_outbox(get_settings(), celery_app, validated_limit))
    except Exception:
        raise RetryableTaskError("resume_outbox_dispatch_unavailable") from None
    if result.failed:
        logger.warning("resume_outbox_publish_deferred", failed=result.failed)
    if result.dead_lettered:
        logger.error("resume_outbox_publish_dead_lettered", count=result.dead_lettered)
    return {
        "published": result.published,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_evidence_attachment_outbox(
    limit: int = _MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Publish bounded identifier-only Career Record attachment jobs."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(
            dispatch_attachment_outbox(get_settings(), celery_app, validated_limit)
        )
    except Exception:
        raise RetryableTaskError("attachment_outbox_dispatch_unavailable") from None
    if result.failed:
        logger.warning("attachment_outbox_publish_deferred", failed=result.failed)
    if result.dead_lettered:
        logger.error("attachment_outbox_publish_dead_lettered", count=result.dead_lettered)
    return {
        "published": result.published,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_RESUME_TASK)  # type: ignore[untyped-decorator]
def reconcile_resume_health_jobs(
    limit: int = _MAINTENANCE_LIMIT,
) -> ReconciliationTaskResult:
    """Recover bounded stale jobs whose broker delivery or retry was lost."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result: JobReconciliationResult = asyncio.run(
            reconcile_stale_resume_jobs(get_settings(), validated_limit)
        )
    except Exception:
        raise RetryableTaskError("resume_job_reconciliation_unavailable") from None
    if result.requeued:
        logger.warning("resume_jobs_requeued", count=result.requeued)
    if result.dead_lettered:
        logger.error("resume_jobs_recovery_dead_lettered", count=result.dead_lettered)
    return {
        "requeued": result.requeued,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK)  # type: ignore[untyped-decorator]
def reconcile_evidence_attachment_jobs(
    limit: int = _MAINTENANCE_LIMIT,
) -> ReconciliationTaskResult:
    """Recover lost attachment deliveries and expired execution leases."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(reconcile_stale_attachment_jobs(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("attachment_job_reconciliation_unavailable") from None
    if result.requeued:
        logger.warning("attachment_jobs_requeued", count=result.requeued)
    if result.dead_lettered:
        logger.error("attachment_jobs_recovery_dead_lettered", count=result.dead_lettered)
    return {
        "requeued": result.requeued,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=CLEANUP_RESUME_TASK)  # type: ignore[untyped-decorator]
def cleanup_expired_resume_health_data(limit: int = _MAINTENANCE_LIMIT) -> CleanupTaskResult:
    """Expire abandoned uploads and queue deletion before guest capability revocation."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result = asyncio.run(cleanup_expired_resume_data(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("resume_cleanup_unavailable") from None
    if result.object_cleanup_failures:
        logger.warning(
            "resume_object_cleanup_deferred",
            count=result.object_cleanup_failures,
        )
    if result.object_cleanup_dead_letters:
        logger.error(
            "resume_object_cleanup_dead_lettered",
            count=result.object_cleanup_dead_letters,
        )
    return {
        "expired_uploads": result.expired_uploads,
        "queued_guest_deletions": result.queued_guest_deletions,
        "revoked_guest_sessions": result.revoked_guest_sessions,
        "object_cleanups_completed": result.object_cleanups_completed,
        "object_cleanup_failures": result.object_cleanup_failures,
        "object_cleanup_dead_letters": result.object_cleanup_dead_letters,
    }


@celery_app.task(name=CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK)  # type: ignore[untyped-decorator]
def cleanup_evidence_attachment_objects(
    limit: int = _MAINTENANCE_LIMIT,
) -> AttachmentCleanupTaskResult:
    """Delete due private objects before attachment tombstone redaction."""
    validated_limit = _validate_maintenance_limit(limit)
    try:
        result: CleanupBatchResult = asyncio.run(
            cleanup_attachment_objects(get_settings(), validated_limit)
        )
    except Exception:
        raise RetryableTaskError("attachment_cleanup_unavailable") from None
    if result.failed:
        logger.warning("attachment_object_cleanup_deferred", count=result.failed)
    if result.dead_lettered:
        logger.error("attachment_object_cleanup_dead_lettered", count=result.dead_lettered)
    return {
        "completed": result.completed,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


def _record_runtime_failure(
    task: SafeTask,
    settings: WorkerSettings,
    job_id: UUID,
    trace_id: str,
    safe_error_code: str,
    execution_token: str,
) -> ProcessingTaskResult:
    exhausted = _retries_exhausted(task, settings)
    try:
        outcome = asyncio.run(
            record_resume_failure(
                settings,
                job_id,
                trace_id,
                safe_error_code,
                retryable=True,
                exhausted=exhausted,
                execution_token=execution_token,
            )
        )
    except Exception:
        if exhausted:
            raise RetryableTaskError("durable_failure_record_unavailable") from None
        _schedule_retry(task, safe_error_code)
    if not exhausted:
        _schedule_retry(task, safe_error_code)
    return _processing_result(outcome)


def _record_attachment_runtime_failure(
    task: SafeTask,
    settings: WorkerSettings,
    job_id: UUID,
    safe_error_code: SafeAttachmentError,
    execution_token: str,
) -> ProcessingTaskResult:
    exhausted = _retries_exhausted(task, settings)
    try:
        outcome = asyncio.run(
            record_attachment_failure(
                settings,
                job_id,
                safe_error_code,
                exhausted=exhausted,
                execution_token=execution_token,
            )
        )
    except Exception:
        if exhausted:
            raise RetryableTaskError("durable_attachment_failure_record_unavailable") from None
        _schedule_attachment_retry(task, safe_error_code.value)
    return _attachment_processing_result(outcome)


def _schedule_retry(task: SafeTask, safe_error_code: str) -> NoReturn:
    retry_number = int(getattr(task.request, "retries", 0)) + 1
    logger.warning(
        "resume_job_retry_scheduled",
        retry_number=retry_number,
        safe_error_code=safe_error_code,
    )
    raise RetryableTaskError(safe_error_code)


def _schedule_attachment_retry(task: SafeTask, safe_error_code: str) -> NoReturn:
    retry_number = int(getattr(task.request, "retries", 0)) + 1
    logger.warning(
        "attachment_job_retry_scheduled",
        retry_number=retry_number,
        safe_error_code=safe_error_code,
    )
    raise RetryableTaskError(safe_error_code)


def _schedule_lease_retry(task: SafeTask, settings: WorkerSettings) -> NoReturn:
    """Retry once the current invocation must be past its hard-limit lease."""

    retries = int(getattr(task.request, "retries", 0))
    countdown = settings.task_time_limit_seconds + 31
    logger.warning(
        "resume_job_execution_lease_busy",
        retry_number=retries + 1,
        retry_after_seconds=countdown,
    )
    raise task.retry(
        exc=RetryableTaskError("execution_lease_active"),
        countdown=countdown,
        max_retries=retries + 1,
    )


def _retries_exhausted(task: SafeTask, settings: WorkerSettings) -> bool:
    retries = int(getattr(task.request, "retries", 0))
    return retries >= settings.task_max_retries


def _processing_result(outcome: ProcessingOutcome) -> ProcessingTaskResult:
    return {
        "job_id": str(outcome.job_id),
        "status": outcome.status.value,
        "retryable": outcome.retryable,
        "safe_error_code": outcome.safe_error_code,
    }


def _attachment_processing_result(
    outcome: AttachmentProcessingOutcome,
) -> ProcessingTaskResult:
    return {
        "job_id": str(outcome.job_id),
        "status": outcome.status.value,
        "retryable": outcome.retryable,
        "safe_error_code": (
            outcome.safe_error_code.value if outcome.safe_error_code is not None else None
        ),
    }


def _analytics_processing_result(
    outcome: AnalyticsProcessingResult,
) -> ProcessingTaskResult:
    return {
        "job_id": str(outcome.job_id),
        "status": outcome.status.value,
        "retryable": outcome.retryable,
        "safe_error_code": outcome.safe_error_code,
    }


def _schedule_analytics_retry(
    task: SafeTask,
    settings: WorkerSettings,
    safe_error_code: str,
    *,
    countdown: int,
) -> NoReturn:
    retries = int(getattr(task.request, "retries", 0))
    logger.warning(
        "analytics_job_retry_scheduled",
        retry_number=retries + 1,
        retry_after_seconds=countdown,
        safe_error_code=safe_error_code,
    )
    raise task.retry(
        exc=RetryableTaskError(safe_error_code),
        countdown=countdown,
        max_retries=settings.analytics_max_attempts + settings.task_max_retries,
    )


def _validate_maintenance_limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 500:
        raise ValueError("maintenance limit must be an integer between 1 and 500")
    return value


def _execution_token(task: SafeTask) -> str:
    value = getattr(task.request, "id", None)
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        raise RetryableTaskError("worker_delivery_id_unavailable")
    # Celery preserves its logical task ID across retries and redelivery. Add a
    # per-invocation nonce so overlapping deliveries cannot share a live lease,
    # then hash into the backend's bounded fencing-token contract.
    return hashlib.sha256(f"{value}\0{uuid4().hex}".encode()).hexdigest()
