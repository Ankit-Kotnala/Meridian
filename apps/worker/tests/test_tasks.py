"""Resume Health Celery adapter tests with no broker or infrastructure calls."""

import re
from uuid import uuid4

import pytest
from careeros.modules.career_record.application import (
    AttachmentJobStatus,
    AttachmentProcessingOutcome,
    AttachmentReconciliationResult,
    CleanupBatchResult,
    SafeAttachmentError,
)
from careeros.modules.resume_builder.application import (
    ExportOutboxDispatchResult,
    ExportProcessingOutcome,
    ExportReconciliationResult,
)
from careeros.modules.resume_builder.domain import ResumeExportStatus
from careeros.modules.resume_health.application import (
    CleanupResult,
    JobReconciliationResult,
    ProcessingOutcome,
)
from careeros.modules.resume_health.domain import JobStatus

from careeros_worker import tasks
from careeros_worker.base import RetryableTaskError
from careeros_worker.config import WorkerSettings
from careeros_worker.runtime import OutboxTaskResult

_DELIVERY_ID = "delivery-test-id"


@pytest.fixture(autouse=True)
def _delivery_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tasks.process_resume_health.request, "id", _DELIVERY_ID)
    monkeypatch.setattr(tasks.process_evidence_attachment.request, "id", _DELIVERY_ID)
    monkeypatch.setattr(tasks.process_resume_builder_export.request, "id", _DELIVERY_ID)


def _settings(*, max_retries: int = 3) -> WorkerSettings:
    return WorkerSettings.model_validate(
        {
            "environment": "test",
            "malware_scanner_provider": "clamav",
            "task_max_retries": max_retries,
        }
    )


def test_process_task_returns_only_durable_status_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()

    async def fake_process(
        _settings: WorkerSettings,
        received_job_id: object,
        trace_id: str,
        execution_token: str,
    ) -> ProcessingOutcome:
        assert received_job_id == job_id
        assert trace_id == "a" * 32
        assert execution_token != _DELIVERY_ID
        assert re.fullmatch(r"[0-9a-f]{64}", execution_token)
        return ProcessingOutcome(job_id, JobStatus.SUCCEEDED, False, None)

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_resume_job", fake_process)

    result = tasks.process_resume_health.run(job_id=str(job_id), trace_id="A" * 32)

    assert result == {
        "job_id": str(job_id),
        "status": "succeeded",
        "retryable": False,
        "safe_error_code": None,
    }


def test_resume_export_task_returns_identifier_only_durable_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_id = uuid4()

    async def fake_process(
        _settings: WorkerSettings,
        received_export_id: object,
        execution_token: str,
    ) -> ExportProcessingOutcome:
        assert received_export_id == export_id
        assert re.fullmatch(r"[0-9a-f]{64}", execution_token)
        return ExportProcessingOutcome(
            export_id,
            ResumeExportStatus.VERIFIED,
            False,
            None,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_resume_export", fake_process)

    result = tasks.process_resume_builder_export.run(
        export_id=str(export_id),
        trace_id="f" * 32,
    )

    assert result == {
        "export_id": str(export_id),
        "status": "verified",
        "retryable": False,
        "safe_error_code": None,
    }


def test_resume_export_task_routes_allowlisted_cleanup_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_id = uuid4()

    async def fake_cleanup(
        _settings: WorkerSettings,
        received_export_id: object,
        execution_token: str,
    ) -> ExportProcessingOutcome:
        assert received_export_id == export_id
        assert re.fullmatch(r"[0-9a-f]{64}", execution_token)
        return ExportProcessingOutcome(
            export_id,
            ResumeExportStatus.DELETED,
            False,
            None,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_resume_export_cleanup", fake_cleanup)

    result = tasks.process_resume_builder_export.run(
        export_id=str(export_id),
        operation="delete",
        trace_id="e" * 32,
    )

    assert result == {
        "export_id": str(export_id),
        "status": "deleted",
        "retryable": False,
        "safe_error_code": None,
    }


def test_attachment_task_returns_identifier_only_durable_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()

    async def fake_process(
        _settings: WorkerSettings,
        received_job_id: object,
        execution_token: str,
    ) -> AttachmentProcessingOutcome:
        assert received_job_id == job_id
        assert execution_token != _DELIVERY_ID
        assert re.fullmatch(r"[0-9a-f]{64}", execution_token)
        return AttachmentProcessingOutcome(job_id, AttachmentJobStatus.SUCCEEDED, None, False)

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_attachment_job", fake_process)

    result = tasks.process_evidence_attachment.run(job_id=str(job_id), trace_id="A" * 32)

    assert result == {
        "job_id": str(job_id),
        "status": "succeeded",
        "retryable": False,
        "safe_error_code": None,
    }


def test_attachment_durable_retry_does_not_create_a_second_celery_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()

    async def fake_process(*_args: object) -> AttachmentProcessingOutcome:
        return AttachmentProcessingOutcome(
            job_id,
            AttachmentJobStatus.RETRY_WAIT,
            SafeAttachmentError.MALWARE_SCANNER_UNAVAILABLE,
            True,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_attachment_job", fake_process)

    result = tasks.process_evidence_attachment.run(job_id=str(job_id), trace_id="b" * 32)

    assert result["status"] == "retry_wait"
    assert result["retryable"] is True
    assert result["safe_error_code"] == "attachment_malware_scanner_unavailable"


def test_attachment_runtime_failure_is_durably_recorded_before_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    recorded: dict[str, object] = {}

    async def broken_runtime(*_args: object) -> AttachmentProcessingOutcome:
        raise RuntimeError("provider assembly failed")

    async def fake_record(
        _settings: WorkerSettings,
        received_job_id: object,
        error_code: SafeAttachmentError,
        *,
        exhausted: bool,
        execution_token: str,
    ) -> AttachmentProcessingOutcome:
        recorded.update(
            job_id=received_job_id,
            error_code=error_code,
            exhausted=exhausted,
            execution_token=execution_token,
        )
        return AttachmentProcessingOutcome(
            job_id,
            AttachmentJobStatus.RETRY_WAIT,
            SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
            True,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_attachment_job", broken_runtime)
    monkeypatch.setattr(tasks, "record_attachment_failure", fake_record)

    result = tasks.process_evidence_attachment.run(job_id=str(job_id), trace_id="c" * 32)

    assert result["status"] == "retry_wait"
    assert recorded["job_id"] == job_id
    assert recorded["error_code"] is SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
    assert recorded["exhausted"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", str(recorded["execution_token"]))


def test_process_task_schedules_retry_for_durable_retryable_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()

    async def fake_process(*_args: object) -> ProcessingOutcome:
        return ProcessingOutcome(
            job_id,
            JobStatus.FAILED,
            True,
            "malware_scanner_unavailable",
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_resume_job", fake_process)

    with pytest.raises(RetryableTaskError, match="malware_scanner_unavailable"):
        tasks.process_resume_health.run(job_id=str(job_id), trace_id="b" * 32)


def test_process_task_defers_a_busy_execution_until_after_its_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    retry_options: list[dict[str, object]] = []

    async def fake_process(*_args: object) -> ProcessingOutcome:
        return ProcessingOutcome(
            job_id,
            JobStatus.RUNNING,
            True,
            "execution_lease_active",
        )

    def fake_retry(**options: object) -> None:
        retry_options.append(options)
        raise RetryableTaskError("execution_lease_active")

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_resume_job", fake_process)
    monkeypatch.setattr(tasks.process_resume_health, "retry", fake_retry)

    with pytest.raises(RetryableTaskError, match="execution_lease_active"):
        tasks.process_resume_health.run(job_id=str(job_id), trace_id="f" * 32)

    assert retry_options[0]["countdown"] == 331
    assert retry_options[0]["max_retries"] == 1


def test_process_task_dead_letters_when_celery_retries_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    recorded: dict[str, object] = {}

    async def fake_process(*args: object) -> ProcessingOutcome:
        recorded["process_execution_token"] = args[3]
        return ProcessingOutcome(job_id, JobStatus.FAILED, True, "object_download_failed")

    async def fake_record(
        _settings: WorkerSettings,
        received_job_id: object,
        _trace_id: str,
        error_code: str,
        *,
        retryable: bool,
        exhausted: bool,
        execution_token: str,
    ) -> ProcessingOutcome:
        recorded.update(
            job_id=received_job_id,
            error_code=error_code,
            retryable=retryable,
            exhausted=exhausted,
            failure_execution_token=execution_token,
        )
        return ProcessingOutcome(job_id, JobStatus.DEAD_LETTERED, False, error_code)

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings(max_retries=0))
    monkeypatch.setattr(tasks, "process_resume_job", fake_process)
    monkeypatch.setattr(tasks, "record_resume_failure", fake_record)

    result = tasks.process_resume_health.run(job_id=str(job_id), trace_id="c" * 32)

    assert result["status"] == "dead_lettered"
    assert recorded["job_id"] == job_id
    assert recorded["error_code"] == "object_download_failed"
    assert recorded["retryable"] is True
    assert recorded["exhausted"] is True
    assert recorded["process_execution_token"] == recorded["failure_execution_token"]


def test_exhausted_preclaim_runtime_failure_is_durably_dead_lettered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    recorded: dict[str, object] = {}

    async def broken_runtime(*_args: object) -> ProcessingOutcome:
        raise RuntimeError("provider assembly failed")

    async def fake_record(
        _settings: WorkerSettings,
        received_job_id: object,
        _trace_id: str,
        error_code: str,
        *,
        retryable: bool,
        exhausted: bool,
        execution_token: str,
    ) -> ProcessingOutcome:
        recorded.update(
            job_id=received_job_id,
            error_code=error_code,
            retryable=retryable,
            exhausted=exhausted,
            execution_token=execution_token,
        )
        return ProcessingOutcome(job_id, JobStatus.DEAD_LETTERED, False, error_code)

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings(max_retries=0))
    monkeypatch.setattr(tasks, "process_resume_job", broken_runtime)
    monkeypatch.setattr(tasks, "record_resume_failure", fake_record)

    result = tasks.process_resume_health.run(job_id=str(job_id), trace_id="9" * 32)

    assert result["status"] == "dead_lettered"
    assert recorded["job_id"] == job_id
    assert recorded["error_code"] == "worker_runtime_unavailable"
    assert recorded["exhausted"] is True
    assert re.fullmatch(r"[0-9a-f]{64}", str(recorded["execution_token"]))


def test_process_task_rejects_a_missing_delivery_id_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks.process_resume_health.request, "id", None)

    with pytest.raises(RetryableTaskError, match="worker_delivery_id_unavailable"):
        tasks.process_resume_health.run(job_id=str(uuid4()), trace_id="e" * 32)


def test_process_task_rejects_non_identifier_payload_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_runtime(*_args: object) -> ProcessingOutcome:
        raise AssertionError("runtime must not receive an invalid payload")

    monkeypatch.setattr(tasks, "process_resume_job", unexpected_runtime)

    with pytest.raises(ValueError, match="job_id"):
        tasks.process_resume_health.run(job_id="not-a-uuid", trace_id="d" * 32)


def test_maintenance_tasks_return_bounded_operational_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_dispatch(*_args: object) -> OutboxTaskResult:
        return OutboxTaskResult(published=4, failed=1, dead_lettered=1)

    async def fake_cleanup(*_args: object) -> CleanupResult:
        return CleanupResult(
            expired_uploads=2,
            queued_guest_deletions=3,
            revoked_guest_sessions=1,
            object_cleanups_completed=5,
            object_cleanup_failures=2,
            object_cleanup_dead_letters=1,
        )

    async def fake_reconcile(*_args: object) -> JobReconciliationResult:
        return JobReconciliationResult(requeued=2, dead_lettered=1)

    async def fake_attachment_cleanup(*_args: object) -> CleanupBatchResult:
        return CleanupBatchResult(completed=6, failed=2, dead_lettered=1)

    async def fake_attachment_reconcile(
        *_args: object,
    ) -> AttachmentReconciliationResult:
        return AttachmentReconciliationResult(requeued=3, dead_lettered=1)

    async def fake_export_dispatch(*_args: object) -> ExportOutboxDispatchResult:
        return ExportOutboxDispatchResult(published=7, failed=2, dead_lettered=1)

    async def fake_export_reconcile(*_args: object) -> ExportReconciliationResult:
        return ExportReconciliationResult(
            requeued=4,
            dead_lettered=2,
            object_cleanups_completed=3,
            object_cleanup_failures=1,
            object_cleanup_dead_letters=1,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "dispatch_resume_outbox", fake_dispatch)
    monkeypatch.setattr(tasks, "cleanup_expired_resume_data", fake_cleanup)
    monkeypatch.setattr(tasks, "reconcile_stale_resume_jobs", fake_reconcile)
    monkeypatch.setattr(tasks, "dispatch_attachment_outbox", fake_dispatch)
    monkeypatch.setattr(tasks, "cleanup_attachment_objects", fake_attachment_cleanup)
    monkeypatch.setattr(tasks, "reconcile_stale_attachment_jobs", fake_attachment_reconcile)
    monkeypatch.setattr(tasks, "dispatch_resume_export_outbox", fake_export_dispatch)
    monkeypatch.setattr(tasks, "reconcile_resume_exports", fake_export_reconcile)

    assert tasks.dispatch_resume_health_outbox.run(limit=25) == {
        "published": 4,
        "failed": 1,
        "dead_lettered": 1,
    }
    assert tasks.cleanup_expired_resume_health_data.run(limit=25) == {
        "expired_uploads": 2,
        "queued_guest_deletions": 3,
        "revoked_guest_sessions": 1,
        "object_cleanups_completed": 5,
        "object_cleanup_failures": 2,
        "object_cleanup_dead_letters": 1,
    }
    assert tasks.reconcile_resume_health_jobs.run(limit=25) == {
        "requeued": 2,
        "dead_lettered": 1,
    }
    assert tasks.dispatch_evidence_attachment_outbox.run(limit=25) == {
        "published": 4,
        "failed": 1,
        "dead_lettered": 1,
    }
    assert tasks.cleanup_evidence_attachment_objects.run(limit=25) == {
        "completed": 6,
        "failed": 2,
        "dead_lettered": 1,
    }
    assert tasks.reconcile_evidence_attachment_jobs.run(limit=25) == {
        "requeued": 3,
        "dead_lettered": 1,
    }
    assert tasks.dispatch_resume_builder_export_outbox.run(limit=25) == {
        "published": 7,
        "failed": 2,
        "dead_lettered": 1,
    }
    assert tasks.reconcile_resume_builder_exports.run(limit=25) == {
        "requeued": 4,
        "dead_lettered": 2,
        "object_cleanups_completed": 3,
        "object_cleanup_failures": 1,
        "object_cleanup_dead_letters": 1,
    }


@pytest.mark.parametrize("limit", [True, 0, 501, "100"])
def test_maintenance_tasks_reject_unbounded_or_mistyped_limits(limit: object) -> None:
    for task in (
        tasks.dispatch_evidence_attachment_outbox,
        tasks.cleanup_evidence_attachment_objects,
        tasks.reconcile_evidence_attachment_jobs,
        tasks.dispatch_resume_health_outbox,
        tasks.reconcile_resume_health_jobs,
        tasks.cleanup_expired_resume_health_data,
        tasks.dispatch_resume_builder_export_outbox,
        tasks.reconcile_resume_builder_exports,
    ):
        with pytest.raises(ValueError, match="maintenance limit"):
            task.run(limit=limit)
