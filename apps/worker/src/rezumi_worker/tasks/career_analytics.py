"""Celery delivery adapters for durable Career Analytics refreshes."""

import asyncio
from typing import NoReturn

import structlog
from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from rezumi.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    CareerAnalyticsConflict,
)
from structlog.contextvars import bind_contextvars

from rezumi_worker.app import celery_app
from rezumi_worker.base import RetryableTaskError, SafeTask
from rezumi_worker.config import WorkerSettings, get_settings
from rezumi_worker.payloads import parse_identifier_payload
from rezumi_worker.runtime import (
    AnalyticsProcessingResult,
    dispatch_career_analytics_outbox,
    process_career_analytics_job,
    reconcile_career_analytics,
)
from rezumi_worker.task_names import (
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    RECONCILE_CAREER_ANALYTICS_TASK,
)
from rezumi_worker.tasks.contracts import (
    AnalyticsReconciliationTaskResult,
    OutboxResult,
    ProcessingTaskResult,
)
from rezumi_worker.tasks.execution import MAINTENANCE_LIMIT, validate_maintenance_limit

logger = structlog.get_logger(__name__)


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
    limit: int = MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Dispatch a bounded analytics outbox batch with UUID-only messages."""

    validated_limit = validate_maintenance_limit(limit)
    try:
        result = asyncio.run(
            dispatch_career_analytics_outbox(
                get_settings(),
                celery_app,
                validated_limit,
            )
        )
    except Exception as exc:
        logger.error("analytics_outbox_dispatch_failed", error=str(exc))
        return {
            "published": 0,
            "failed": 1,
            "dead_lettered": 0,
        }
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
    limit: int = MAINTENANCE_LIMIT,
) -> AnalyticsReconciliationTaskResult:
    """Recover expired analytics leases and due lost deliveries."""

    validated_limit = validate_maintenance_limit(limit)
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


