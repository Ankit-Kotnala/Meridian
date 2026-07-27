"""Worker runtime composition and resource-lifecycle tests."""

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from careeros.foundation.database import Base
from careeros.modules.career_record.application import (
    AttachmentJobStatus,
    AttachmentProcessingOutcome,
    AttachmentReconciliationResult,
    CleanupBatchResult,
    SafeAttachmentError,
)
from careeros.modules.resume_builder.application import (
    ExportObjectCleanupResult,
    ExportReconciliationResult,
)
from careeros.modules.resume_health.application import (
    JobReconciliationResult,
    OutboxDispatchResult,
    ProcessingOutcome,
)
from careeros.modules.resume_health.domain import JobStatus

from careeros_worker import runtime
from careeros_worker.config import WorkerSettings

_TEST_TEMP_ROOT = Path.cwd().resolve() / "worker-runtime-test"


def test_runtime_registers_cross_module_database_metadata() -> None:
    assert "users" in Base.metadata.tables
    assert "resume_audit_events" in Base.metadata.tables
    assert "evidence_attachments" in Base.metadata.tables
    assert "evidence_attachment_processing_jobs" in Base.metadata.tables
    assert "evidence_attachment_outbox" in Base.metadata.tables
    assert "career_analytics_refresh_jobs" in Base.metadata.tables
    assert "career_analytics_outbox" in Base.metadata.tables
    assert "networking_reminders" in Base.metadata.tables
    assert "networking_reminder_occurrences" in Base.metadata.tables
    assert "networking_reminder_outbox" in Base.metadata.tables
    assert "resume_export_object_cleanups" in Base.metadata.tables


def test_runtime_translates_validated_settings_and_disposes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, Any] = {}

    class FakeDatabase:
        def __init__(self, options: object) -> None:
            captured["database_options"] = options

        async def dispose(self) -> None:
            events.append("database")

    class FakeStorage:
        def __init__(self, options: object) -> None:
            captured["storage_options"] = options

        async def dispose(self) -> None:
            events.append("storage")

    class FakeProcessor:
        def __init__(self, **options: object) -> None:
            captured["processor_options"] = options

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "S3ObjectStorage", FakeStorage)
    monkeypatch.setattr(runtime, "ResumeHealthProcessor", FakeProcessor)
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "malware_scanner_provider": "clamav",
            "document_temp_root": _TEST_TEMP_ROOT,
            "document_processing_timeout_seconds": 90,
        }
    )

    async def exercise() -> None:
        async with runtime._runtime_resources(settings) as resources:
            assert resources.limits.temp_root == _TEST_TEMP_ROOT
            assert resources.limits.processing_timeout_seconds == 90
            runtime._processor(resources, settings)

    asyncio.run(exercise())

    assert events == ["storage", "database"]
    assert captured["database_options"].pool_size == settings.database_pool_size
    assert captured["storage_options"].bucket == settings.s3_bucket
    assert captured["processor_options"]["execution_lease_seconds"] == 330


def test_database_is_disposed_even_when_storage_disposal_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FailingStorage:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("storage")
            raise RuntimeError("safe test failure")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "S3ObjectStorage", FailingStorage)

    async def exercise() -> None:
        async with runtime._runtime_resources(
            WorkerSettings.model_validate(
                {"environment": "test", "malware_scanner_provider": "clamav"}
            )
        ):
            pass

    with pytest.raises(RuntimeError, match="safe test failure"):
        asyncio.run(exercise())

    assert events == ["storage", "database"]


def test_database_is_disposed_when_storage_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FailingStorage:
        def __init__(self, _options: object) -> None:
            raise RuntimeError("safe constructor failure")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "S3ObjectStorage", FailingStorage)

    async def exercise() -> None:
        async with runtime._runtime_resources(
            WorkerSettings.model_validate(
                {"environment": "test", "malware_scanner_provider": "clamav"}
            )
        ):
            raise AssertionError("failed storage construction must not yield")

    with pytest.raises(RuntimeError, match="safe constructor failure"):
        asyncio.run(exercise())

    assert events == ["database"]


def test_failure_recording_uses_database_only_when_provider_assembly_is_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}
    job_id = uuid4()

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeFailureRecorder:
        def __init__(self, **options: object) -> None:
            captured["options"] = options

        async def record_task_failure(
            self, received_job_id: object, _trace_id: str, error_code: str, **options: object
        ) -> ProcessingOutcome:
            captured.update(
                job_id=received_job_id,
                error_code=error_code,
                record_options=options,
            )
            return ProcessingOutcome(job_id, JobStatus.DEAD_LETTERED, False, error_code)

    class ForbiddenStorage:
        def __init__(self, _options: object) -> None:
            raise AssertionError("failure recording must not assemble object storage")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "ResumeJobFailureRecorder", FakeFailureRecorder)
    monkeypatch.setattr(runtime, "S3ObjectStorage", ForbiddenStorage)
    settings = WorkerSettings.model_validate(
        {"environment": "test", "malware_scanner_provider": "clamav"}
    )

    outcome = asyncio.run(
        runtime.record_resume_failure(
            settings,
            job_id,
            "a" * 32,
            "worker_runtime_unavailable",
            retryable=True,
            exhausted=True,
            execution_token="b" * 64,
        )
    )

    assert outcome.status is JobStatus.DEAD_LETTERED
    assert captured["job_id"] == job_id
    assert events == ["database"]


def test_job_reconciliation_uses_database_only_and_disposes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeReconciler:
        def __init__(self, **options: object) -> None:
            captured.update(options)

        async def reconcile_stale(self, limit: int) -> JobReconciliationResult:
            captured["limit"] = limit
            return JobReconciliationResult(requeued=2, dead_lettered=1)

    class ForbiddenStorage:
        def __init__(self, _options: object) -> None:
            raise AssertionError("reconciliation must not assemble object storage")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "ResumeJobReconciler", FakeReconciler)
    monkeypatch.setattr(runtime, "S3ObjectStorage", ForbiddenStorage)
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "resume_job_reconciliation_stale_seconds": 900,
        }
    )

    result = asyncio.run(runtime.reconcile_stale_resume_jobs(settings, 25))

    assert result == JobReconciliationResult(requeued=2, dead_lettered=1)
    assert captured["limit"] == 25
    assert captured["stale_after_seconds"] == 900
    assert events == ["database"]


def test_outbox_dispatch_uses_database_only_and_disposes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeDispatcher:
        def __init__(self, **_options: object) -> None:
            pass

        async def dispatch_pending(self, limit: int) -> OutboxDispatchResult:
            assert limit == 25
            return OutboxDispatchResult(published=3, failed=1, dead_lettered=0)

    class ForbiddenStorage:
        def __init__(self, _options: object) -> None:
            raise AssertionError("outbox dispatch must not assemble object storage")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "OutboxDispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "S3ObjectStorage", ForbiddenStorage)
    settings = WorkerSettings.model_validate({"environment": "test"})

    result = asyncio.run(runtime.dispatch_resume_outbox(settings, object(), 25))

    assert result == runtime.OutboxTaskResult(published=3, failed=1, dead_lettered=0)
    assert events == ["database"]


def test_resume_export_reconciliation_cleans_orphan_objects_and_disposes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeStorage:
        def __init__(self, options: object) -> None:
            captured["storage_options"] = options

        async def dispose(self) -> None:
            events.append("storage")

    class FakeReconciler:
        def __init__(self, **options: object) -> None:
            captured["reconciler_policy"] = options["policy"]

        async def reconcile(self, limit: int) -> ExportReconciliationResult:
            assert limit == 25
            return ExportReconciliationResult(requeued=2, dead_lettered=1)

    class FakeCleaner:
        def __init__(self, **options: object) -> None:
            captured["cleaner_policy"] = options["policy"]
            assert isinstance(options["storage"], FakeStorage)

        async def cleanup_due(self, limit: int) -> ExportObjectCleanupResult:
            assert limit == 25
            return ExportObjectCleanupResult(completed=3, failed=1, dead_lettered=1)

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "ResumeExportS3Storage", FakeStorage)
    monkeypatch.setattr(runtime, "ResumeExportReconciler", FakeReconciler)
    monkeypatch.setattr(runtime, "ResumeExportObjectCleanupProcessor", FakeCleaner)
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "database_connect_timeout_seconds": 4,
            "database_command_timeout_seconds": 20,
            "resume_export_orphan_cleanup_grace_seconds": 45,
        }
    )

    result = asyncio.run(runtime.reconcile_resume_exports(settings, 25))

    assert result == ExportReconciliationResult(
        requeued=2,
        dead_lettered=1,
        object_cleanups_completed=3,
        object_cleanup_failures=1,
        object_cleanup_dead_letters=1,
    )
    assert captured["reconciler_policy"].orphan_cleanup_grace_seconds == 45
    assert captured["cleaner_policy"].orphan_cleanup_grace_seconds == 45
    assert captured["storage_options"].connect_timeout_seconds == 4
    assert captured["storage_options"].read_timeout_seconds == 20
    assert events == ["storage", "database"]


def test_resume_export_reconciliation_disposes_database_when_storage_assembly_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FailingStorage:
        def __init__(self, _options: object) -> None:
            raise RuntimeError("safe storage assembly failure")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "ResumeExportS3Storage", FailingStorage)

    with pytest.raises(RuntimeError, match="safe storage assembly failure"):
        asyncio.run(
            runtime.reconcile_resume_exports(
                WorkerSettings.model_validate({"environment": "test"}),
                25,
            )
        )

    assert events == ["database"]


def test_runtime_fails_closed_when_scanning_is_disabled() -> None:
    settings = WorkerSettings.model_validate(
        {"environment": "test", "malware_scanner_provider": "disabled"}
    )

    async def exercise() -> None:
        async with runtime._runtime_resources(settings):
            raise AssertionError("disabled scanning must not yield resources")

    with pytest.raises(RuntimeError, match="fail-closed malware scanner"):
        asyncio.run(exercise())


def test_attachment_runtime_translates_limits_and_disposes_private_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, options: object) -> None:
            captured["database_options"] = options

        async def dispose(self) -> None:
            events.append("database")

    class FakeStorage:
        def __init__(self, options: object) -> None:
            captured["storage_options"] = options

        async def dispose(self) -> None:
            events.append("storage")

    class FakeScanner:
        def __init__(self, options: object) -> None:
            captured["scanner_options"] = options

    class FakeExtractor:
        pass

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "AttachmentS3ObjectStorage", FakeStorage)
    monkeypatch.setattr(runtime, "AttachmentClamAvScanner", FakeScanner)
    monkeypatch.setattr(runtime, "BoundedAttachmentExtractor", FakeExtractor)
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "malware_scanner_provider": "clamav",
            "document_temp_root": _TEST_TEMP_ROOT,
            "document_max_pages": 12,
            "document_processing_timeout_seconds": 75,
        }
    )

    async def exercise() -> None:
        async with runtime._attachment_runtime_resources(settings) as resources:
            assert resources.limits.temp_root == (_TEST_TEMP_ROOT / "attachments").resolve()
            assert resources.limits.max_pdf_pages == 12
            assert resources.limits.processing_timeout_seconds == 75

    asyncio.run(exercise())

    assert events == ["storage", "database"]
    storage_options: Any = captured["storage_options"]
    assert storage_options.bucket == settings.s3_bucket


def test_attachment_failure_and_outbox_composition_are_database_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}
    job_id = uuid4()

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeFailureRecorder:
        def __init__(self, **_options: object) -> None:
            pass

        async def record_failure(
            self,
            received_job_id: object,
            execution_token: str,
            error_code: SafeAttachmentError,
            *,
            exhausted: bool,
        ) -> AttachmentProcessingOutcome:
            captured.update(
                job_id=received_job_id,
                execution_token=execution_token,
                error_code=error_code,
                exhausted=exhausted,
            )
            return AttachmentProcessingOutcome(
                job_id, AttachmentJobStatus.DEAD_LETTERED, error_code, False
            )

    class ForbiddenStorage:
        def __init__(self, _options: object) -> None:
            raise AssertionError("database-only composition must not assemble storage")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "AttachmentFailureRecorder", FakeFailureRecorder)
    monkeypatch.setattr(runtime, "AttachmentS3ObjectStorage", ForbiddenStorage)
    settings = WorkerSettings.model_validate({"environment": "test"})

    outcome = asyncio.run(
        runtime.record_attachment_failure(
            settings,
            job_id,
            SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
            exhausted=True,
            execution_token="c" * 64,
        )
    )

    assert outcome.status is AttachmentJobStatus.DEAD_LETTERED
    assert captured["job_id"] == job_id
    assert events == ["database"]


def test_attachment_cleanup_assembles_storage_without_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeStorage:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("storage")

    class FakeCleanup:
        def __init__(self, **_options: object) -> None:
            pass

        async def process_due(self, limit: int) -> CleanupBatchResult:
            assert limit == 25
            return CleanupBatchResult(completed=4, failed=1, dead_lettered=0)

    class ForbiddenScanner:
        def __init__(self, _options: object) -> None:
            raise AssertionError("cleanup must not assemble a malware scanner")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "AttachmentS3ObjectStorage", FakeStorage)
    monkeypatch.setattr(runtime, "AttachmentCleanupProcessor", FakeCleanup)
    monkeypatch.setattr(runtime, "AttachmentClamAvScanner", ForbiddenScanner)

    result = asyncio.run(
        runtime.cleanup_attachment_objects(
            WorkerSettings.model_validate({"environment": "test"}), 25
        )
    )

    assert result == CleanupBatchResult(completed=4, failed=1, dead_lettered=0)
    assert events == ["storage", "database"]


def test_attachment_reconciliation_is_database_only_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, _options: object) -> None:
            pass

        async def dispose(self) -> None:
            events.append("database")

    class FakeReconciler:
        def __init__(self, **options: object) -> None:
            captured.update(options)

        async def reconcile_stale(self, limit: int) -> AttachmentReconciliationResult:
            captured["limit"] = limit
            return AttachmentReconciliationResult(requeued=2, dead_lettered=1)

    class ForbiddenStorage:
        def __init__(self, _options: object) -> None:
            raise AssertionError("reconciliation must not assemble object storage")

    monkeypatch.setattr(runtime, "Database", FakeDatabase)
    monkeypatch.setattr(runtime, "AttachmentJobReconciler", FakeReconciler)
    monkeypatch.setattr(runtime, "AttachmentS3ObjectStorage", ForbiddenStorage)
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "attachment_job_reconciliation_stale_seconds": 900,
        }
    )

    result = asyncio.run(runtime.reconcile_stale_attachment_jobs(settings, 25))

    assert result == AttachmentReconciliationResult(requeued=2, dead_lettered=1)
    assert captured["limit"] == 25
    assert captured["stale_after_seconds"] == 900
    assert events == ["database"]
