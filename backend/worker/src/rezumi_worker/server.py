"""Stateless, QStash-authenticated delivery surface for cloud job execution.

This is intentionally a worker-owned HTTP application, not an API route.  It
keeps job composition out of ``backend/api`` while letting QStash invoke one
bounded durable task at a time on a conventional container web service.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rezumi.modules.career_record.application import (
    CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
    DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK,
    DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
    PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK,
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK,
    RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
)
from rezumi.modules.career_record.application.attachment_workflow import SafeAttachmentError
from rezumi.modules.resume_builder.domain import ResumeExportOperation
from rezumi.modules.resume_health.application import (
    CLEANUP_RESUME_TASK,
    DISPATCH_OUTBOX_TASK,
    PROCESS_RESUME_TASK,
    RECONCILE_RESUME_TASK,
)
from structlog.contextvars import bind_contextvars

from rezumi_worker.config import WorkerSettings, get_settings
from rezumi_worker.logging import configure_worker_logging
from rezumi_worker.qstash import QStashSignatureError, QStashSignatureVerifier
from rezumi_worker.runtime import (
    cleanup_attachment_objects,
    cleanup_expired_resume_data,
    dispatch_attachment_outbox,
    dispatch_career_analytics_outbox,
    dispatch_declared_profile_enrichment_outbox,
    dispatch_resume_export_outbox,
    dispatch_resume_outbox,
    process_attachment_job,
    process_career_analytics_job,
    process_declared_profile_enrichment_job,
    process_due_networking_reminders,
    process_resume_export,
    process_resume_export_cleanup,
    process_resume_job,
    reconcile_career_analytics,
    reconcile_networking_reminders,
    reconcile_resume_exports,
    reconcile_stale_attachment_jobs,
    reconcile_stale_declared_profile_enrichment_jobs,
    reconcile_stale_resume_jobs,
    record_attachment_failure,
    record_resume_failure,
    sync_job_catalog,
)
from rezumi_worker.task_names import (
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    PROCESS_RESUME_EXPORT_TASK,
    RECONCILE_CAREER_ANALYTICS_TASK,
    RECONCILE_NETWORKING_REMINDERS_TASK,
    RECONCILE_RESUME_EXPORTS_TASK,
    SYNC_JOB_CATALOG_TASK,
)
from rezumi_worker.tasks.execution import MAINTENANCE_LIMIT, validate_maintenance_limit

logger = structlog.get_logger(__name__)
_MAINTENANCE_SWEEP_TASK = "rezumi.cloud.maintenance.sweep"


class JobEnvelope(BaseModel):
    """The only message format admitted from the public queue provider."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    task: str = Field(min_length=1, max_length=128)
    job_id: UUID | None = Field(default=None, alias="jobId")
    export_id: UUID | None = Field(default=None, alias="exportId")
    trace_id: str | None = Field(default=None, alias="traceId", max_length=64)
    operation: Literal["render", "delete"] = "render"
    limit: int = Field(default=MAINTENANCE_LIMIT, ge=1, le=100)


class RetryableJobFailure(RuntimeError):
    """Return a 503 so QStash applies its bounded delivery retry policy."""


def create_app(settings: WorkerSettings | None = None) -> FastAPI:
    """Create the worker-owned HTTP runner without importing the public API."""

    resolved_settings = settings or get_settings()
    configure_worker_logging(resolved_settings)
    application = FastAPI(
        title="Rezumi job runner",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = resolved_settings

    @application.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.service_name}

    @application.post("/internal/jobs/qstash", include_in_schema=False)
    async def receive_qstash_job(request: Request) -> Response:
        if resolved_settings.job_delivery_provider != "qstash":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        verifier = _signature_verifier(resolved_settings)
        body = await request.body()
        try:
            verifier.verify(signature=request.headers.get("Upstash-Signature"), body=body)
        except QStashSignatureError as exc:
            logger.warning("qstash_job_rejected", safe_error_code=str(exc))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc
        try:
            raw_envelope = json.loads(body)
            envelope = JobEnvelope.model_validate(raw_envelope)
        except (json.JSONDecodeError, ValidationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from None
        try:
            result = await execute_job(envelope, resolved_settings)
        except RetryableJobFailure as exc:
            logger.warning("qstash_job_retryable_failure", safe_error_code=str(exc))
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE) from exc
        except ValueError:
            # The envelope is signed but invalid for this allowlisted operation.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from None
        except Exception:
            logger.exception("qstash_job_unavailable")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE) from None
        return Response(
            content=json.dumps(result, separators=(",", ":")),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )

    return application


async def execute_job(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    """Run exactly one known durable job, with no queue-carried user content."""

    bind_contextvars(trace_id=_trace_id(envelope))
    handlers: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        PROCESS_RESUME_TASK: lambda: _process_resume(envelope, settings),
        PROCESS_EVIDENCE_ATTACHMENT_TASK: lambda: _process_attachment(envelope, settings),
        PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK: lambda: _process_declared_profile(
            envelope, settings
        ),
        PROCESS_CAREER_ANALYTICS_REFRESH_TASK: lambda: _process_analytics(envelope, settings),
        PROCESS_RESUME_EXPORT_TASK: lambda: _process_export(envelope, settings),
        DISPATCH_OUTBOX_TASK: lambda: _dispatch_resume(envelope, settings),
        DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK: lambda: _dispatch_attachments(envelope, settings),
        DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK: lambda: _dispatch_declared_profiles(
            envelope, settings
        ),
        DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK: lambda: _dispatch_analytics(envelope, settings),
        DISPATCH_RESUME_EXPORT_OUTBOX_TASK: lambda: _dispatch_exports(envelope, settings),
        RECONCILE_RESUME_TASK: lambda: _reconcile_resume(envelope, settings),
        RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK: lambda: _reconcile_attachments(envelope, settings),
        RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK: lambda: _reconcile_declared_profiles(
            envelope, settings
        ),
        RECONCILE_CAREER_ANALYTICS_TASK: lambda: _reconcile_analytics(envelope, settings),
        RECONCILE_RESUME_EXPORTS_TASK: lambda: _reconcile_exports(envelope, settings),
        CLEANUP_RESUME_TASK: lambda: _cleanup_resume(envelope, settings),
        CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK: lambda: _cleanup_attachments(envelope, settings),
        PROCESS_NETWORKING_LOCAL_REMINDERS_TASK: lambda: _process_networking(envelope, settings),
        RECONCILE_NETWORKING_REMINDERS_TASK: lambda: _reconcile_networking(envelope, settings),
        SYNC_JOB_CATALOG_TASK: lambda: _sync_job_catalog(settings),
        _MAINTENANCE_SWEEP_TASK: lambda: _maintenance_sweep(envelope, settings),
    }
    handler = handlers.get(envelope.task)
    if handler is None:
        raise ValueError("unknown_qstash_task")
    try:
        return await asyncio.wait_for(handler(), timeout=settings.task_time_limit_seconds)
    except TimeoutError as exc:
        raise RetryableJobFailure("job_timeout") from exc


async def _process_resume(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    job_id = _require_job_id(envelope)
    trace_id = _trace_id(envelope)
    execution_token = uuid4().hex
    bind_contextvars(job_id=str(job_id), trace_id=trace_id)
    try:
        outcome = await process_resume_job(settings, job_id, trace_id, execution_token)
    except Exception as exc:
        try:
            outcome = await record_resume_failure(
                settings,
                job_id,
                trace_id,
                "worker_runtime_unavailable",
                retryable=True,
                exhausted=False,
                execution_token=execution_token,
            )
        except Exception as record_exc:
            raise RetryableJobFailure("durable_failure_record_unavailable") from record_exc
        if outcome.retryable:
            raise RetryableJobFailure("resume_processing_retryable") from exc
    if outcome.retryable:
        raise RetryableJobFailure(outcome.safe_error_code or "resume_processing_retryable")
    return _outcome(job_id, outcome.status.value, outcome.safe_error_code)


async def _process_attachment(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    job_id = _require_job_id(envelope)
    execution_token = uuid4().hex
    bind_contextvars(job_id=str(job_id))
    try:
        outcome = await process_attachment_job(settings, job_id, execution_token)
    except Exception as exc:
        try:
            outcome = await record_attachment_failure(
                settings,
                job_id,
                SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
                exhausted=False,
                execution_token=execution_token,
            )
        except Exception as record_exc:
            raise RetryableJobFailure("durable_failure_record_unavailable") from record_exc
        if outcome.retryable:
            raise RetryableJobFailure("attachment_processing_retryable") from exc
    return _outcome(
        job_id,
        outcome.status.value,
        outcome.safe_error_code.value if outcome.safe_error_code is not None else None,
    )


async def _process_declared_profile(
    envelope: JobEnvelope, settings: WorkerSettings
) -> dict[str, Any]:
    job_id = _require_job_id(envelope)
    bind_contextvars(job_id=str(job_id))
    try:
        outcome = await process_declared_profile_enrichment_job(settings, job_id)
    except Exception as exc:
        raise RetryableJobFailure("declared_profile_processing_unavailable") from exc
    return _outcome(job_id, outcome.value)


async def _process_analytics(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    job_id = _require_job_id(envelope)
    bind_contextvars(job_id=str(job_id))
    try:
        outcome = await process_career_analytics_job(settings, job_id)
    except Exception as exc:
        raise RetryableJobFailure("analytics_processing_unavailable") from exc
    if outcome.retryable:
        # The use case recorded a durable retry state; QStash also provides a
        # prompt bounded retry in case this invocation is the only delivery.
        raise RetryableJobFailure(outcome.safe_error_code or "analytics_retryable")
    return _outcome(job_id, outcome.status.value, outcome.safe_error_code)


async def _process_export(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    export_id = _require_export_id(envelope)
    bind_contextvars(export_id=str(export_id))
    operation = ResumeExportOperation(envelope.operation)
    processor = (
        process_resume_export_cleanup
        if operation is ResumeExportOperation.DELETE
        else process_resume_export
    )
    try:
        outcome = await processor(settings, export_id, uuid4().hex)
    except Exception as exc:
        raise RetryableJobFailure("resume_export_processing_unavailable") from exc
    if outcome.retryable:
        raise RetryableJobFailure(outcome.safe_error_code or "resume_export_retryable")
    return _outcome(export_id, outcome.status.value, outcome.safe_error_code, key="exportId")


async def _dispatch_resume(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await dispatch_resume_outbox(settings, None, _limit(envelope))
    return _dispatch_result(result)


async def _dispatch_attachments(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await dispatch_attachment_outbox(settings, None, _limit(envelope))
    return _dispatch_result(result)


async def _dispatch_declared_profiles(
    envelope: JobEnvelope, settings: WorkerSettings
) -> dict[str, Any]:
    result = await dispatch_declared_profile_enrichment_outbox(settings, None, _limit(envelope))
    return _dispatch_result(result)


async def _dispatch_analytics(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await dispatch_career_analytics_outbox(settings, None, _limit(envelope))
    return _dispatch_result(result)


async def _dispatch_exports(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await dispatch_resume_export_outbox(settings, None, _limit(envelope))
    return _dispatch_result(result)


async def _reconcile_resume(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await reconcile_stale_resume_jobs(settings, _limit(envelope))
    return {"requeued": result.requeued, "deadLettered": result.dead_lettered}


async def _reconcile_attachments(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await reconcile_stale_attachment_jobs(settings, _limit(envelope))
    return {"requeued": result.requeued, "deadLettered": result.dead_lettered}


async def _reconcile_declared_profiles(
    envelope: JobEnvelope, settings: WorkerSettings
) -> dict[str, Any]:
    result = await reconcile_stale_declared_profile_enrichment_jobs(settings, _limit(envelope))
    return {"deadLettered": result.dead_lettered}


async def _reconcile_analytics(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await reconcile_career_analytics(settings, _limit(envelope))
    return {
        "recoveredJobs": result.recovered_jobs,
        "deadLetteredJobs": result.dead_lettered_jobs,
        "recoveredOutbox": result.recovered_outbox,
        "deadLetteredOutbox": result.dead_lettered_outbox,
        "requeuedDeliveries": result.requeued_deliveries,
    }


async def _reconcile_exports(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await reconcile_resume_exports(settings, _limit(envelope))
    return {
        "requeued": result.requeued,
        "deadLettered": result.dead_lettered,
        "objectCleanupsCompleted": result.object_cleanups_completed,
        "objectCleanupFailures": result.object_cleanup_failures,
        "objectCleanupDeadLetters": result.object_cleanup_dead_letters,
    }


async def _cleanup_resume(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await cleanup_expired_resume_data(settings, _limit(envelope))
    return {
        "expiredUploads": result.expired_uploads,
        "queuedGuestDeletions": result.queued_guest_deletions,
        "revokedGuestSessions": result.revoked_guest_sessions,
        "objectCleanupsCompleted": result.object_cleanups_completed,
        "objectCleanupFailures": result.object_cleanup_failures,
        "objectCleanupDeadLetters": result.object_cleanup_dead_letters,
    }


async def _cleanup_attachments(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await cleanup_attachment_objects(settings, _limit(envelope))
    return {
        "completed": result.completed,
        "failed": result.failed,
        "deadLettered": result.dead_lettered,
    }


async def _process_networking(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await process_due_networking_reminders(settings, _limit(envelope))
    return {
        "claimed": result.claimed,
        "processed": result.processed,
        "deferred": result.deferred,
        "failed": result.failed,
        "deadLettered": result.dead_lettered,
    }


async def _reconcile_networking(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    result = await reconcile_networking_reminders(settings, _limit(envelope))
    return {"recovered": result.recovered, "deadLettered": result.dead_lettered}


async def _sync_job_catalog(settings: WorkerSettings) -> dict[str, Any]:
    results = await sync_job_catalog(settings)
    return {"sources": len(results)}


async def _maintenance_sweep(envelope: JobEnvelope, settings: WorkerSettings) -> dict[str, Any]:
    """Keep one low-frequency schedule within the QStash free-tier budget."""

    limit = _limit(envelope)
    await _dispatch_resume(envelope, settings)
    await _dispatch_attachments(envelope, settings)
    await _dispatch_declared_profiles(envelope, settings)
    await _dispatch_analytics(envelope, settings)
    await _dispatch_exports(envelope, settings)
    await _reconcile_resume(envelope, settings)
    await _reconcile_attachments(envelope, settings)
    await _reconcile_declared_profiles(envelope, settings)
    await _reconcile_analytics(envelope, settings)
    await _reconcile_exports(envelope, settings)
    await _cleanup_resume(envelope, settings)
    await _cleanup_attachments(envelope, settings)
    await _process_networking(envelope, settings)
    await _reconcile_networking(envelope, settings)
    return {"status": "completed", "limit": limit}


def _signature_verifier(settings: WorkerSettings) -> QStashSignatureVerifier:
    current = settings.qstash_current_signing_key
    next_key = settings.qstash_next_signing_key
    endpoint = settings.qstash_job_runner_url
    if current is None or next_key is None or endpoint is None:
        raise RuntimeError("validated QStash signature configuration is unavailable")
    return QStashSignatureVerifier(
        current_signing_key=current.get_secret_value(),
        next_signing_key=next_key.get_secret_value(),
        expected_url=endpoint,
    )


def _require_job_id(envelope: JobEnvelope) -> UUID:
    if envelope.job_id is None or envelope.export_id is not None:
        raise ValueError("invalid_job_envelope")
    return envelope.job_id


def _require_export_id(envelope: JobEnvelope) -> UUID:
    if envelope.export_id is None or envelope.job_id is not None:
        raise ValueError("invalid_export_envelope")
    return envelope.export_id


def _trace_id(envelope: JobEnvelope) -> str:
    return (envelope.trace_id or uuid4().hex)[:64]


def _limit(envelope: JobEnvelope) -> int:
    return validate_maintenance_limit(envelope.limit)


def _outcome(
    identifier: UUID,
    status_value: str,
    safe_error_code: str | None = None,
    *,
    key: str = "jobId",
) -> dict[str, Any]:
    result: dict[str, Any] = {key: str(identifier), "status": status_value}
    if safe_error_code is not None:
        result["safeErrorCode"] = safe_error_code
    return result


def _dispatch_result(result: Any) -> dict[str, int]:
    return {
        "published": result.published,
        "failed": result.failed,
        "deadLettered": result.dead_lettered,
    }


app = create_app()
