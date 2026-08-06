"""Celery delivery adapters for Career Record evidence attachments."""

import asyncio
from typing import NoReturn
from uuid import UUID

import structlog
from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from rezumi.modules.career_record.application import (
    CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
    DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
    AttachmentProcessingOutcome,
    CleanupBatchResult,
    SafeAttachmentError,
)
from structlog.contextvars import bind_contextvars

from rezumi_worker.app import celery_app
from rezumi_worker.base import RetryableTaskError, SafeTask
from rezumi_worker.config import WorkerSettings, get_settings
from rezumi_worker.payloads import parse_job_payload
from rezumi_worker.runtime import (
    cleanup_attachment_objects,
    dispatch_attachment_outbox,
    process_attachment_job,
    reconcile_stale_attachment_jobs,
    record_attachment_failure,
)
from rezumi_worker.tasks.contracts import (
    AttachmentCleanupTaskResult,
    OutboxResult,
    ProcessingTaskResult,
    ReconciliationTaskResult,
)
from rezumi_worker.tasks.execution import (
    MAINTENANCE_LIMIT,
    execution_token,
    retries_exhausted,
    validate_maintenance_limit,
)

logger = structlog.get_logger(__name__)


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
    task_execution_token = execution_token(task)
    bind_contextvars(job_id=str(parsed_job_id), trace_id=parsed_trace_id)
    settings = get_settings()
    try:
        outcome = asyncio.run(process_attachment_job(settings, parsed_job_id, task_execution_token))
    except SoftTimeLimitExceeded:
        return _record_attachment_runtime_failure(
            task,
            settings,
            parsed_job_id,
            SafeAttachmentError.PROCESSING_TIMEOUT,
            task_execution_token,
        )
    except Exception:
        return _record_attachment_runtime_failure(
            task,
            settings,
            parsed_job_id,
            SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
            task_execution_token,
        )
    # Retryable processor outcomes already have durable retry/outbox state. A
    # second Celery retry path would duplicate work and weaken fencing.
    return _attachment_processing_result(outcome)


@celery_app.task(name=DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_evidence_attachment_outbox(
    limit: int = MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Publish bounded identifier-only Career Record attachment jobs."""
    validated_limit = validate_maintenance_limit(limit)
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


@celery_app.task(name=RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK)  # type: ignore[untyped-decorator]
def reconcile_evidence_attachment_jobs(
    limit: int = MAINTENANCE_LIMIT,
) -> ReconciliationTaskResult:
    """Recover lost attachment deliveries and expired execution leases."""
    validated_limit = validate_maintenance_limit(limit)
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


@celery_app.task(name=CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK)  # type: ignore[untyped-decorator]
def cleanup_evidence_attachment_objects(
    limit: int = MAINTENANCE_LIMIT,
) -> AttachmentCleanupTaskResult:
    """Delete due private objects before attachment tombstone redaction."""
    validated_limit = validate_maintenance_limit(limit)
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


def _record_attachment_runtime_failure(
    task: SafeTask,
    settings: WorkerSettings,
    job_id: UUID,
    safe_error_code: SafeAttachmentError,
    task_execution_token: str,
) -> ProcessingTaskResult:
    exhausted = retries_exhausted(task, settings)
    try:
        outcome = asyncio.run(
            record_attachment_failure(
                settings,
                job_id,
                safe_error_code,
                exhausted=exhausted,
                execution_token=task_execution_token,
            )
        )
    except Exception:
        if exhausted:
            raise RetryableTaskError("durable_attachment_failure_record_unavailable") from None
        _schedule_attachment_retry(task, safe_error_code.value)
    return _attachment_processing_result(outcome)


def _schedule_attachment_retry(task: SafeTask, safe_error_code: str) -> NoReturn:
    retry_number = int(getattr(task.request, "retries", 0)) + 1
    logger.warning(
        "attachment_job_retry_scheduled",
        retry_number=retry_number,
        safe_error_code=safe_error_code,
    )
    raise RetryableTaskError(safe_error_code)


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
