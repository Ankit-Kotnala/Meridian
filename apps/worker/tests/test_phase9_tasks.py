"""Phase 9 Celery adapters stay identifier-only and defer policy to services."""

import inspect
from uuid import uuid4

import pytest
from careeros.modules.career_analytics.domain import AnalyticsJobStatus

from careeros_worker import runtime, tasks
from careeros_worker.config import WorkerSettings


def _settings() -> WorkerSettings:
    return WorkerSettings.model_validate({"environment": "test"})


def test_analytics_duplicate_redelivery_returns_the_same_durable_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    calls = 0

    async def completed(
        _settings: WorkerSettings,
        received_job_id: object,
    ) -> runtime.AnalyticsProcessingResult:
        nonlocal calls
        calls += 1
        assert received_job_id == job_id
        return runtime.AnalyticsProcessingResult(
            job_id=job_id,
            trace_id="a" * 32,
            status=AnalyticsJobStatus.COMPLETED,
            attempts=1,
            max_attempts=3,
            safe_error_code=None,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_career_analytics_job", completed)

    first = tasks.process_career_analytics_refresh.run(job_id=str(job_id))
    redelivery = tasks.process_career_analytics_refresh.run(job_id=str(job_id))

    expected = {
        "job_id": str(job_id),
        "status": "completed",
        "retryable": False,
        "safe_error_code": None,
    }
    assert first == expected
    assert redelivery == expected
    assert calls == 2


def test_analytics_retry_wait_returns_after_durable_outbox_requeue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    bound_context: list[dict[str, str]] = []

    async def retry_wait(
        *_args: object,
    ) -> runtime.AnalyticsProcessingResult:
        return runtime.AnalyticsProcessingResult(
            job_id=job_id,
            trace_id="b" * 32,
            status=AnalyticsJobStatus.RETRY_WAIT,
            attempts=1,
            max_attempts=3,
            safe_error_code="source_changed",
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_career_analytics_job", retry_wait)
    monkeypatch.setattr(
        tasks,
        "bind_contextvars",
        lambda **values: bound_context.append(values),
    )

    result = tasks.process_career_analytics_refresh.run(job_id=str(job_id))

    assert result == {
        "job_id": str(job_id),
        "status": "retry_wait",
        "retryable": True,
        "safe_error_code": "source_changed",
    }
    assert bound_context == [
        {"job_id": str(job_id)},
        {"trace_id": "b" * 32},
    ]


def test_analytics_durable_retry_exhaustion_returns_dead_letter_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    errors: list[tuple[str, dict[str, object]]] = []

    async def dead_letter(
        *_args: object,
    ) -> runtime.AnalyticsProcessingResult:
        return runtime.AnalyticsProcessingResult(
            job_id=job_id,
            trace_id="c" * 32,
            status=AnalyticsJobStatus.DEAD_LETTER,
            attempts=3,
            max_attempts=3,
            safe_error_code="aggregation_failed",
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_career_analytics_job", dead_letter)
    monkeypatch.setattr(
        tasks.logger,
        "error",
        lambda event, **values: errors.append((event, values)),
    )

    result = tasks.process_career_analytics_refresh.run(job_id=str(job_id))

    assert result == {
        "job_id": str(job_id),
        "status": "dead_letter",
        "retryable": False,
        "safe_error_code": "aggregation_failed",
    }
    assert errors == [
        (
            "analytics_job_dead_lettered",
            {
                "safe_error_code": "aggregation_failed",
                "attempts": 3,
                "max_attempts": 3,
            },
        )
    ]


def test_analytics_task_rejects_content_or_noncanonical_identifiers_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(*_args: object) -> runtime.AnalyticsProcessingResult:
        raise AssertionError("invalid payload reached analytics runtime")

    monkeypatch.setattr(tasks, "process_career_analytics_job", forbidden)

    with pytest.raises(ValueError, match="job_id"):
        tasks.process_career_analytics_refresh.run(job_id="not-a-uuid")


def test_phase9_maintenance_tasks_return_counts_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def dispatch(*_args: object) -> runtime.OutboxTaskResult:
        return runtime.OutboxTaskResult(published=3, failed=1, dead_lettered=1)

    async def reconcile_analytics(
        *_args: object,
    ) -> runtime.AnalyticsReconciliationResult:
        return runtime.AnalyticsReconciliationResult(
            recovered_jobs=2,
            dead_lettered_jobs=1,
            recovered_outbox=1,
            dead_lettered_outbox=1,
            requeued_deliveries=2,
        )

    async def reminders(*_args: object) -> runtime.NetworkingReminderBatchResult:
        return runtime.NetworkingReminderBatchResult(
            claimed=4,
            processed=2,
            deferred=1,
            failed=0,
            dead_lettered=1,
        )

    async def recover(*_args: object) -> runtime.NetworkingReminderRecoveryResult:
        return runtime.NetworkingReminderRecoveryResult(recovered=3, dead_lettered=1)

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "dispatch_career_analytics_outbox", dispatch)
    monkeypatch.setattr(tasks, "reconcile_career_analytics", reconcile_analytics)
    monkeypatch.setattr(tasks, "process_due_networking_reminders", reminders)
    monkeypatch.setattr(tasks, "reconcile_networking_reminders", recover)

    assert tasks.dispatch_career_analytics_refresh_outbox.run(limit=25) == {
        "published": 3,
        "failed": 1,
        "dead_lettered": 1,
    }
    assert tasks.reconcile_career_analytics_jobs.run(limit=25) == {
        "recovered_jobs": 2,
        "dead_lettered_jobs": 1,
        "recovered_outbox": 1,
        "dead_lettered_outbox": 1,
        "requeued_deliveries": 2,
    }
    assert tasks.process_networking_local_reminders.run(limit=25) == {
        "claimed": 4,
        "processed": 2,
        "deferred": 1,
        "failed": 0,
        "dead_lettered": 1,
    }
    assert tasks.reconcile_networking_local_reminders.run(limit=25) == {
        "recovered": 3,
        "dead_lettered": 1,
    }


@pytest.mark.parametrize("limit", [True, 0, 501, "25"])
def test_phase9_maintenance_tasks_reject_unbounded_or_mistyped_limits(
    limit: object,
) -> None:
    for task in (
        tasks.dispatch_career_analytics_refresh_outbox,
        tasks.reconcile_career_analytics_jobs,
        tasks.process_networking_local_reminders,
        tasks.reconcile_networking_local_reminders,
    ):
        with pytest.raises(ValueError, match="maintenance limit"):
            task.run(limit=limit)


def test_phase9_task_payloads_expose_no_content_or_external_delivery_fields() -> None:
    analytics_parameters = set(
        inspect.signature(tasks.process_career_analytics_refresh.run).parameters
    )
    reminder_parameters = set(
        inspect.signature(tasks.process_networking_local_reminders.run).parameters
    )
    recovery_parameters = set(
        inspect.signature(tasks.reconcile_networking_local_reminders.run).parameters
    )

    assert analytics_parameters == {"job_id"}
    assert reminder_parameters == {"limit"}
    assert recovery_parameters == {"limit"}

    networking_source = inspect.getsource(runtime.process_due_networking_reminders)
    for forbidden in ("send_task", "CeleryAnalyticsPublisher", "http://", "https://", "email"):
        assert forbidden not in networking_source
