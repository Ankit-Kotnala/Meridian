"""Phase 9 runtime composition, recovery, and no-send guarantees."""

import asyncio
import inspect
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from rezumi.modules.career_analytics.application import (
    AnalyticsReconciliationOutcome,
    ClaimedAnalyticsOutbox,
)
from rezumi.modules.career_analytics.application.worker_query import (
    AnalyticsWorkerJobReference,
)
from rezumi.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsOutboxStatus,
    CareerAnalyticsUnavailable,
)
from rezumi.modules.networking.domain import (
    NetworkingLeaseConflict,
    NetworkingReminderOutboxEntry,
    ReminderOutboxKind,
    ReminderOutboxStatus,
)

from rezumi_worker import runtime
from rezumi_worker.config import WorkerSettings

_NOW = datetime(2026, 7, 25, 4, 0, tzinfo=UTC)


def _settings() -> WorkerSettings:
    return WorkerSettings.model_validate({"environment": "test"})


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


class _DisposableDatabase:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def dispose(self) -> None:
        self._events.append("database")


def _reminder_entry(*, attempts: int = 1) -> NetworkingReminderOutboxEntry:
    return NetworkingReminderOutboxEntry(
        id=uuid4(),
        owner_user_id=uuid4(),
        occurrence_id=uuid4(),
        kind=ReminderOutboxKind.LOCAL_REMINDER_DUE,
        status=ReminderOutboxStatus.LEASED,
        trace_id="d" * 32,
        available_at=_NOW,
        attempt_count=attempts,
        max_attempts=attempts,
        lease_token=uuid4(),
        lease_expires_at=_NOW.replace(minute=2),
        last_error_code=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_analytics_composition_uses_canonical_resume_and_attachment_status_queries() -> None:
    source = inspect.getsource(runtime._career_analytics_service)

    assert "ResumeHealthSourceReader" in source
    assert "ResumeHealthSourceQuery" in source
    assert "AttachmentAdmissionBridge" in source
    assert "_UnavailableResumeSourceQuery" not in source
    assert "attachments=None" not in source


def test_analytics_process_reads_persisted_trace_and_surfaces_durable_dead_letter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    job_id = uuid4()
    references = iter(
        (
            AnalyticsWorkerJobReference(
                job_id=job_id,
                trace_id="a" * 32,
                status=AnalyticsJobStatus.QUEUED,
                attempts=0,
                max_attempts=3,
                safe_error_code=None,
            ),
            AnalyticsWorkerJobReference(
                job_id=job_id,
                trace_id="a" * 32,
                status=AnalyticsJobStatus.DEAD_LETTER,
                attempts=3,
                max_attempts=3,
                safe_error_code="aggregation_failed",
            ),
        )
    )

    class FakeQuery:
        def __init__(self, _database: object) -> None:
            pass

        async def get_job_reference(
            self,
            received_job_id: UUID,
        ) -> AnalyticsWorkerJobReference:
            assert received_job_id == job_id
            return next(references)

    class FakeService:
        async def process_refresh(self, received_job_id: UUID, *, trace_id: str) -> None:
            assert received_job_id == job_id
            assert trace_id == "a" * 32
            raise CareerAnalyticsUnavailable("safe failure")

    database = _DisposableDatabase(events)
    bound_context: list[dict[str, str]] = []
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(
        runtime,
        "bind_contextvars",
        lambda **values: bound_context.append(values),
    )
    monkeypatch.setattr(runtime, "SqlAlchemyCareerAnalyticsWorkerQuery", FakeQuery)
    monkeypatch.setattr(runtime, "_career_analytics_service", lambda *_args: FakeService())

    result = asyncio.run(runtime.process_career_analytics_job(_settings(), job_id))

    assert result.status is AnalyticsJobStatus.DEAD_LETTER
    assert result.trace_id == "a" * 32
    assert result.safe_error_code == "aggregation_failed"
    assert bound_context == [{"job_id": str(job_id), "trace_id": "a" * 32}]
    assert events == ["database"]


def test_analytics_outbox_dispatch_records_success_failure_and_dead_letter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    published_job = uuid4()
    failed_job = uuid4()
    published_message = ClaimedAnalyticsOutbox(uuid4(), published_job, uuid4(), 1)
    failed_message = ClaimedAnalyticsOutbox(uuid4(), failed_job, uuid4(), 1)
    acknowledged: list[UUID] = []
    failed: list[UUID] = []
    broker_payloads: list[UUID] = []

    class FakeService:
        async def claim_outbox(
            self,
            *,
            limit: int,
        ) -> tuple[ClaimedAnalyticsOutbox, ...]:
            assert limit == 25
            return published_message, failed_message

        async def mark_outbox_published(
            self,
            message_id: UUID,
            *,
            lease_token: UUID,
            job_version_at_claim: int,
        ) -> None:
            assert lease_token == published_message.lease_token
            assert job_version_at_claim == published_message.job_version_at_claim
            acknowledged.append(message_id)

        async def mark_outbox_failed(
            self,
            message_id: UUID,
            *,
            lease_token: UUID,
            safe_error_code: str,
        ) -> None:
            assert lease_token == failed_message.lease_token
            assert safe_error_code == "publish_failed"
            failed.append(message_id)

    class FakeQuery:
        def __init__(self, _database: object) -> None:
            pass

        async def get_outbox_status(self, message_id: UUID) -> AnalyticsOutboxStatus:
            assert message_id == failed_message.message_id
            return AnalyticsOutboxStatus.DEAD_LETTER

    class FakePublisher:
        def __init__(self, _application: object) -> None:
            pass

        async def publish(self, job_id: UUID) -> None:
            broker_payloads.append(job_id)
            if job_id == failed_job:
                raise RuntimeError("safe broker failure")

    database = _DisposableDatabase(events)
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(runtime, "_career_analytics_service", lambda *_args: FakeService())
    monkeypatch.setattr(runtime, "SqlAlchemyCareerAnalyticsWorkerQuery", FakeQuery)
    monkeypatch.setattr(runtime, "CeleryAnalyticsPublisher", FakePublisher)

    result = asyncio.run(runtime.dispatch_career_analytics_outbox(_settings(), object(), 25))

    assert result == runtime.OutboxTaskResult(published=1, failed=0, dead_lettered=1)
    assert broker_payloads == [published_job, failed_job]
    assert acknowledged == [published_message.message_id]
    assert failed == [failed_message.message_id]
    assert events == ["database"]


def test_analytics_reconciliation_reports_durable_recovery_and_disposes_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeService:
        async def reconcile_expired(
            self,
            *,
            limit: int,
        ) -> AnalyticsReconciliationOutcome:
            assert limit == 20
            return AnalyticsReconciliationOutcome(
                recovered_jobs=2,
                dead_lettered_jobs=1,
                recovered_outbox=1,
                dead_lettered_outbox=1,
                requeued_deliveries=2,
            )

    database = _DisposableDatabase(events)
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(runtime, "_career_analytics_service", lambda *_args: FakeService())

    result = asyncio.run(runtime.reconcile_career_analytics(_settings(), 20))

    assert result == runtime.AnalyticsReconciliationResult(
        recovered_jobs=2,
        dead_lettered_jobs=1,
        recovered_outbox=1,
        dead_lettered_outbox=1,
        requeued_deliveries=2,
    )
    assert events == ["database"]


def test_networking_local_processing_materializes_due_state_or_dead_letters_without_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    successful = _reminder_entry()
    exhausted = _reminder_entry()
    due_materializations: list[UUID] = []
    failures: list[UUID] = []
    bound_context: list[dict[str, object]] = []

    class FakeService:
        async def claim_due_reminders(
            self,
            *,
            now: datetime,
            lease_seconds: int,
            limit: int,
        ) -> tuple[NetworkingReminderOutboxEntry, ...]:
            assert now == _NOW
            assert lease_seconds == 120
            assert limit == 10
            return successful, exhausted

        async def materialize_due_reminder(
            self,
            entry_id: UUID,
            *,
            lease_token: UUID,
            now: datetime,
        ) -> None:
            assert now == _NOW
            if entry_id == exhausted.id:
                raise RuntimeError("safe persistence failure")
            assert lease_token == successful.lease_token
            due_materializations.append(entry_id)

        async def fail_reminder(
            self,
            entry_id: UUID,
            *,
            lease_token: UUID,
            error_code: str,
            retry_at: datetime,
            now: datetime,
        ) -> NetworkingReminderOutboxEntry:
            assert lease_token == exhausted.lease_token
            assert error_code == "local_reminder_processing_failed"
            assert retry_at > now
            failures.append(entry_id)
            return replace(
                exhausted,
                status=ReminderOutboxStatus.DEAD_LETTER,
                lease_token=None,
                lease_expires_at=None,
                last_error_code=error_code,
            )

    class ForbiddenPublisher:
        def __init__(self, _application: object) -> None:
            raise AssertionError("networking reminders must not assemble a publisher")

    database = _DisposableDatabase(events)
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(runtime, "_networking_service", lambda _database: FakeService())
    monkeypatch.setattr(runtime, "NetworkingClock", _FixedClock)
    monkeypatch.setattr(runtime, "CeleryAnalyticsPublisher", ForbiddenPublisher)
    monkeypatch.setattr(
        runtime,
        "bind_contextvars",
        lambda **values: bound_context.append(values),
    )

    result = asyncio.run(runtime.process_due_networking_reminders(_settings(), 10))

    assert result == runtime.NetworkingReminderBatchResult(
        claimed=2,
        processed=1,
        deferred=0,
        failed=0,
        dead_lettered=1,
    )
    assert due_materializations == [successful.id]
    assert failures == [exhausted.id]
    assert [value["trace_id"] for value in bound_context] == ["d" * 32, "d" * 32]
    assert [value["networking_occurrence_id"] for value in bound_context] == [
        str(successful.occurrence_id),
        str(exhausted.occurrence_id),
    ]
    assert events == ["database"]


def test_networking_duplicate_or_cancelled_lease_is_safely_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    duplicate = _reminder_entry(attempts=1)

    class FakeService:
        async def claim_due_reminders(
            self,
            **_options: object,
        ) -> tuple[NetworkingReminderOutboxEntry, ...]:
            return (duplicate,)

        async def materialize_due_reminder(self, *_args: object, **_options: object) -> None:
            raise NetworkingLeaseConflict

        async def fail_reminder(
            self,
            *_args: object,
            **_options: object,
        ) -> NetworkingReminderOutboxEntry:
            raise AssertionError("a lost lease must not be overwritten")

    database = _DisposableDatabase(events)
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(runtime, "_networking_service", lambda _database: FakeService())
    monkeypatch.setattr(runtime, "NetworkingClock", _FixedClock)

    result = asyncio.run(runtime.process_due_networking_reminders(_settings(), 10))

    assert result.deferred == 1
    assert result.processed == 0
    assert result.failed == 0
    assert events == ["database"]


def test_networking_reconciliation_reports_recovered_and_exhausted_leases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    pending = replace(
        _reminder_entry(attempts=1),
        status=ReminderOutboxStatus.PENDING,
        max_attempts=2,
        lease_token=None,
        lease_expires_at=None,
    )
    dead = replace(
        _reminder_entry(attempts=1),
        status=ReminderOutboxStatus.DEAD_LETTER,
        lease_token=None,
        lease_expires_at=None,
    )
    bound_context: list[dict[str, object]] = []

    class FakeService:
        async def recover_expired_leases(
            self,
            *,
            now: datetime,
            limit: int,
        ) -> tuple[NetworkingReminderOutboxEntry, ...]:
            assert now == _NOW
            assert limit == 15
            return pending, dead

    database = _DisposableDatabase(events)
    monkeypatch.setattr(runtime, "_database", lambda _settings: database)
    monkeypatch.setattr(runtime, "_networking_service", lambda _database: FakeService())
    monkeypatch.setattr(runtime, "NetworkingClock", _FixedClock)
    monkeypatch.setattr(
        runtime,
        "bind_contextvars",
        lambda **values: bound_context.append(values),
    )

    result = asyncio.run(runtime.reconcile_networking_reminders(_settings(), 15))

    assert result == runtime.NetworkingReminderRecoveryResult(
        recovered=2,
        dead_lettered=1,
    )
    assert [value["trace_id"] for value in bound_context] == ["d" * 32, "d" * 32]
    assert [value["networking_outbox_id"] for value in bound_context] == [
        str(pending.id),
        str(dead.id),
    ]
    assert events == ["database"]
