"""Celery configuration tests that do not connect to Redis."""

from careeros.modules.career_record.application import (
    CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
    DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
)
from careeros.modules.resume_health.application import (
    CLEANUP_RESUME_TASK,
    DISPATCH_OUTBOX_TASK,
    PROCESS_RESUME_TASK,
    RECONCILE_RESUME_TASK,
)

from careeros_worker.app import create_celery_app
from careeros_worker.config import WorkerSettings
from careeros_worker.task_names import (
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    RECONCILE_CAREER_ANALYTICS_TASK,
    RECONCILE_NETWORKING_REMINDERS_TASK,
)


def test_celery_uses_json_and_safe_delivery_defaults() -> None:
    settings = WorkerSettings.model_validate({"environment": "test"})
    app = create_celery_app(settings)

    assert app.conf.accept_content == ["json"]
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_soft_time_limit == 270
    assert app.conf.task_time_limit == 300
    assert app.conf.task_ignore_result is True
    assert app.conf.task_annotations[PROCESS_NETWORKING_LOCAL_REMINDERS_TASK] == {
        "soft_time_limit": 114,
        "time_limit": 115,
    }
    assert app.conf.task_routes[PROCESS_CAREER_ANALYTICS_REFRESH_TASK] == {"queue": "default"}
    assert app.conf.task_routes[DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[RECONCILE_CAREER_ANALYTICS_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[PROCESS_NETWORKING_LOCAL_REMINDERS_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[RECONCILE_NETWORKING_REMINDERS_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[PROCESS_EVIDENCE_ATTACHMENT_TASK] == {"queue": "career-record"}
    assert app.conf.task_routes[DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK] == {
        "queue": "maintenance"
    }
    assert app.conf.task_routes[CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK] == {
        "queue": "maintenance"
    }
    assert app.conf.task_routes[RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[PROCESS_RESUME_TASK] == {"queue": "resume-health"}
    assert app.conf.task_routes[DISPATCH_OUTBOX_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[RECONCILE_RESUME_TASK] == {"queue": "maintenance"}
    assert app.conf.task_routes[CLEANUP_RESUME_TASK] == {"queue": "maintenance"}
    assert app.conf.beat_schedule["dispatch-resume-health-outbox"]["task"] == (DISPATCH_OUTBOX_TASK)
    assert app.conf.beat_schedule["dispatch-career-record-attachment-outbox"] == {
        "task": DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
        "schedule": 5.0,
    }
    assert app.conf.beat_schedule["cleanup-career-record-attachment-objects"] == {
        "task": CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
        "schedule": 60.0,
    }
    assert app.conf.beat_schedule["reconcile-career-record-attachment-jobs"] == {
        "task": RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
        "schedule": 60.0,
    }
    assert app.conf.beat_schedule["reconcile-stale-resume-health-jobs"] == {
        "task": RECONCILE_RESUME_TASK,
        "schedule": 60.0,
    }
    assert app.conf.beat_schedule["dispatch-career-analytics-outbox"] == {
        "task": DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
        "schedule": 5.0,
    }
    assert app.conf.beat_schedule["reconcile-career-analytics"] == {
        "task": RECONCILE_CAREER_ANALYTICS_TASK,
        "schedule": 60.0,
    }
    assert app.conf.beat_schedule["process-networking-local-reminders"] == {
        "task": PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
        "schedule": 30.0,
    }
    assert app.conf.beat_schedule["reconcile-networking-local-reminders"] == {
        "task": RECONCILE_NETWORKING_REMINDERS_TASK,
        "schedule": 60.0,
    }


def test_task_retry_count_is_bounded() -> None:
    settings = WorkerSettings.model_validate({"environment": "test", "task_max_retries": 4})
    app = create_celery_app(settings)

    assert app.Task.max_retries == 4
