"""Celery delivery adapters for durable Resume Builder exports."""

import asyncio

import structlog
from rezumi.modules.resume_builder.domain import ResumeExportOperation
from structlog.contextvars import bind_contextvars

from rezumi_worker.app import celery_app
from rezumi_worker.base import RetryableTaskError, SafeTask
from rezumi_worker.config import get_settings
from rezumi_worker.payloads import parse_job_payload
from rezumi_worker.runtime import (
    dispatch_resume_export_outbox,
    process_resume_export,
    process_resume_export_cleanup,
    reconcile_resume_exports,
)
from rezumi_worker.task_names import (
    DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
    PROCESS_RESUME_EXPORT_TASK,
    RECONCILE_RESUME_EXPORTS_TASK,
)
from rezumi_worker.tasks.contracts import (
    OutboxResult,
    ResumeExportReconciliationTaskResult,
    ResumeExportTaskResult,
)
from rezumi_worker.tasks.execution import (
    MAINTENANCE_LIMIT,
    execution_token,
    validate_maintenance_limit,
)

logger = structlog.get_logger(__name__)


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
        outcome = asyncio.run(processor(get_settings(), parsed_export_id, execution_token(task)))
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
    limit: int = MAINTENANCE_LIMIT,
) -> OutboxResult:
    """Publish bounded identifier-only export jobs from the transactional outbox."""

    validated_limit = validate_maintenance_limit(limit)
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
    limit: int = MAINTENANCE_LIMIT,
) -> ResumeExportReconciliationTaskResult:
    """Recover lost export deliveries, expired leases, and orphan objects."""

    validated_limit = validate_maintenance_limit(limit)
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
