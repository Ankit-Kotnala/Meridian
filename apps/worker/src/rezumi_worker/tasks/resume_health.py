"""Celery delivery adapters for durable Resume Health processing."""

import asyncio
from typing import NoReturn
from uuid import UUID

import structlog
from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from rezumi.modules.resume_health.application import (
    CLEANUP_RESUME_TASK,
    DISPATCH_OUTBOX_TASK,
    PROCESS_RESUME_TASK,
    RECONCILE_RESUME_TASK,
    JobReconciliationResult,
    ProcessingOutcome,
)
from structlog.contextvars import bind_contextvars

from rezumi_worker.app import celery_app
from rezumi_worker.base import RetryableTaskError, SafeTask
from rezumi_worker.config import WorkerSettings, get_settings
from rezumi_worker.payloads import parse_job_payload
from rezumi_worker.runtime import (
    cleanup_expired_resume_data,
    dispatch_resume_outbox,
    process_resume_job,
    reconcile_stale_resume_jobs,
    record_resume_failure,
)
from rezumi_worker.tasks.contracts import (
    CleanupTaskResult,
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
    task_execution_token = execution_token(task)
    bind_contextvars(job_id=str(parsed_job_id), trace_id=parsed_trace_id)
    settings = get_settings()
    try:
        outcome = asyncio.run(
            process_resume_job(
                settings,
                parsed_job_id,
                parsed_trace_id,
                task_execution_token,
            )
        )
    except SoftTimeLimitExceeded:
        return _record_runtime_failure(
            task,
            settings,
            parsed_job_id,
            parsed_trace_id,
            "worker_soft_time_limit",
            task_execution_token,
        )
    except Exception:
        return _record_runtime_failure(
            task,
            settings,
            parsed_job_id,
            parsed_trace_id,
            "worker_runtime_unavailable",
            task_execution_token,
        )

    if outcome.retryable:
        if outcome.safe_error_code == "execution_lease_active":
            _schedule_lease_retry(task, settings)
        if retries_exhausted(task, settings):
            try:
                outcome = asyncio.run(
                    record_resume_failure(
                        settings,
                        parsed_job_id,
                        parsed_trace_id,
                        outcome.safe_error_code or "processing_retry_exhausted",
                        retryable=True,
                        exhausted=True,
                        execution_token=task_execution_token,
                    )
                )
            except Exception:
                raise RetryableTaskError("durable_failure_record_unavailable") from None
        else:
            _schedule_retry(task, outcome.safe_error_code or "processing_retryable_failure")
    return _processing_result(outcome)


@celery_app.task(name=DISPATCH_OUTBOX_TASK)  # type: ignore[untyped-decorator]
def dispatch_resume_health_outbox(limit: int = MAINTENANCE_LIMIT) -> OutboxResult:
    """Publish pending transactional-outbox rows using the allowlisted task adapter."""
    validated_limit = validate_maintenance_limit(limit)
    try:
        result = asyncio.run(dispatch_resume_outbox(get_settings(), celery_app, validated_limit))
    except Exception as exc:
        logger.error("resume_outbox_dispatch_failed", error=str(exc))
        return {
            "published": 0,
            "failed": 1,
            "dead_lettered": 0,
        }
    if result.failed:
        logger.warning("resume_outbox_publish_deferred", failed=result.failed)
    if result.dead_lettered:
        logger.error("resume_outbox_publish_dead_lettered", count=result.dead_lettered)
    return {
        "published": result.published,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_RESUME_TASK)  # type: ignore[untyped-decorator]
def reconcile_resume_health_jobs(
    limit: int = MAINTENANCE_LIMIT,
) -> ReconciliationTaskResult:
    """Recover bounded stale jobs whose broker delivery or retry was lost."""
    validated_limit = validate_maintenance_limit(limit)
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


@celery_app.task(name=CLEANUP_RESUME_TASK)  # type: ignore[untyped-decorator]
def cleanup_expired_resume_health_data(
    limit: int = MAINTENANCE_LIMIT,
) -> CleanupTaskResult:
    """Expire abandoned uploads and queue deletion before guest capability revocation."""
    validated_limit = validate_maintenance_limit(limit)
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


def _record_runtime_failure(
    task: SafeTask,
    settings: WorkerSettings,
    job_id: UUID,
    trace_id: str,
    safe_error_code: str,
    task_execution_token: str,
) -> ProcessingTaskResult:
    exhausted = retries_exhausted(task, settings)
    try:
        outcome = asyncio.run(
            record_resume_failure(
                settings,
                job_id,
                trace_id,
                safe_error_code,
                retryable=True,
                exhausted=exhausted,
                execution_token=task_execution_token,
            )
        )
    except Exception:
        if exhausted:
            raise RetryableTaskError("durable_failure_record_unavailable") from None
        _schedule_retry(task, safe_error_code)
    if not exhausted:
        _schedule_retry(task, safe_error_code)
    return _processing_result(outcome)


def _schedule_retry(task: SafeTask, safe_error_code: str) -> NoReturn:
    retry_number = int(getattr(task.request, "retries", 0)) + 1
    logger.warning(
        "resume_job_retry_scheduled",
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


def _processing_result(outcome: ProcessingOutcome) -> ProcessingTaskResult:
    return {
        "job_id": str(outcome.job_id),
        "status": outcome.status.value,
        "retryable": outcome.retryable,
        "safe_error_code": outcome.safe_error_code,
    }
