"""Celery application factory and command-line entry point."""

from celery import Celery  # type: ignore[import-untyped,unused-ignore]
from rezumi.modules.career_record.application import (
    CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
    DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK,
    DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
    PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK,
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK,
    RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
)
from rezumi.modules.resume_health.application import (
    CLEANUP_RESUME_TASK,
    DISPATCH_OUTBOX_TASK,
    PROCESS_RESUME_TASK,
    RECONCILE_RESUME_TASK,
)

from rezumi_worker.base import SafeTask
from rezumi_worker.config import WorkerSettings, get_settings
from rezumi_worker.logging import configure_worker_logging
from rezumi_worker.task_names import (
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    PROCESS_RESUME_EXPORT_TASK,
    RECONCILE_CAREER_ANALYTICS_TASK,
    RECONCILE_NETWORKING_REMINDERS_TASK,
    RECONCILE_RESUME_EXPORTS_TASK,
)


def create_celery_app(settings: WorkerSettings | None = None) -> Celery:
    """Create a JSON-only worker with conservative delivery and resource defaults."""
    resolved = settings or get_settings()
    configure_worker_logging(resolved)
    application = Celery(
        "rezumi_worker",
        broker=resolved.broker_url.get_secret_value(),
        backend=resolved.result_backend.get_secret_value(),
        include=["rezumi_worker.tasks"],
        task_cls=SafeTask,
    )
    visibility_timeout = max(resolved.task_time_limit_seconds * 2, 3600)
    networking_time_limit = min(
        resolved.task_time_limit_seconds,
        resolved.networking_reminder_lease_seconds - 5,
    )
    networking_soft_time_limit = min(
        resolved.task_soft_time_limit_seconds,
        networking_time_limit - 1,
    )
    application.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": visibility_timeout},
        enable_utc=True,
        result_accept_content=["json"],
        result_backend_always_retry=True,
        result_expires=resolved.result_expires_seconds,
        result_serializer="json",
        task_acks_late=True,
        task_acks_on_failure_or_timeout=True,
        task_annotations={
            PROCESS_NETWORKING_LOCAL_REMINDERS_TASK: {
                "soft_time_limit": networking_soft_time_limit,
                "time_limit": networking_time_limit,
            }
        },
        task_default_queue="default",
        task_ignore_result=True,
        task_publish_retry=True,
        task_publish_retry_policy={
            "max_retries": resolved.task_max_retries,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 1,
        },
        task_reject_on_worker_lost=True,
        task_send_sent_event=True,
        task_serializer="json",
        task_soft_time_limit=resolved.task_soft_time_limit_seconds,
        task_time_limit=resolved.task_time_limit_seconds,
        task_track_started=True,
        task_routes={
            PROCESS_CAREER_ANALYTICS_REFRESH_TASK: {"queue": "default"},
            DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK: {"queue": "maintenance"},
            RECONCILE_CAREER_ANALYTICS_TASK: {"queue": "maintenance"},
            PROCESS_NETWORKING_LOCAL_REMINDERS_TASK: {"queue": "maintenance"},
            RECONCILE_NETWORKING_REMINDERS_TASK: {"queue": "maintenance"},
            PROCESS_EVIDENCE_ATTACHMENT_TASK: {"queue": "career-record"},
            DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK: {"queue": "maintenance"},
            CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK: {"queue": "maintenance"},
            RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK: {"queue": "maintenance"},
            PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK: {"queue": "career-record"},
            DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK: {"queue": "maintenance"},
            RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK: {"queue": "maintenance"},
            PROCESS_RESUME_TASK: {"queue": "resume-health"},
            DISPATCH_OUTBOX_TASK: {"queue": "maintenance"},
            RECONCILE_RESUME_TASK: {"queue": "maintenance"},
            CLEANUP_RESUME_TASK: {"queue": "maintenance"},
            PROCESS_RESUME_EXPORT_TASK: {"queue": "resume-builder"},
            DISPATCH_RESUME_EXPORT_OUTBOX_TASK: {"queue": "maintenance"},
            RECONCILE_RESUME_EXPORTS_TASK: {"queue": "maintenance"},
        },
        timezone="UTC",
        worker_hijack_root_logger=False,
        worker_max_tasks_per_child=resolved.worker_max_tasks_per_child,
        worker_prefetch_multiplier=resolved.worker_prefetch_multiplier,
        worker_send_task_events=True,
        worker_cancel_long_running_tasks_on_connection_loss=True,
        beat_schedule={
            "dispatch-career-analytics-outbox": {
                "task": DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
                "schedule": float(resolved.analytics_outbox_interval_seconds),
            },
            "reconcile-career-analytics": {
                "task": RECONCILE_CAREER_ANALYTICS_TASK,
                "schedule": float(resolved.analytics_reconciliation_interval_seconds),
            },
            "process-networking-local-reminders": {
                "task": PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
                "schedule": float(resolved.networking_reminder_interval_seconds),
            },
            "reconcile-networking-local-reminders": {
                "task": RECONCILE_NETWORKING_REMINDERS_TASK,
                "schedule": float(resolved.networking_reconciliation_interval_seconds),
            },
            "dispatch-career-record-attachment-outbox": {
                "task": DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK,
                "schedule": 5.0,
            },
            "cleanup-career-record-attachment-objects": {
                "task": CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK,
                "schedule": 60.0,
            },
            "reconcile-career-record-attachment-jobs": {
                "task": RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK,
                "schedule": float(resolved.attachment_job_reconciliation_interval_seconds),
            },
            "dispatch-declared-profile-enrichment-outbox": {
                "task": DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK,
                "schedule": 5.0,
            },
            "reconcile-declared-profile-enrichment-jobs": {
                "task": RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK,
                "schedule": float(
                    resolved.declared_profile_enrichment_reconciliation_interval_seconds
                ),
            },
            "dispatch-resume-health-outbox": {
                "task": DISPATCH_OUTBOX_TASK,
                "schedule": 5.0,
            },
            "cleanup-expired-resume-health-data": {
                "task": CLEANUP_RESUME_TASK,
                "schedule": 300.0,
            },
            "reconcile-stale-resume-health-jobs": {
                "task": RECONCILE_RESUME_TASK,
                "schedule": float(resolved.resume_job_reconciliation_interval_seconds),
            },
            "dispatch-resume-builder-export-outbox": {
                "task": DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
                "schedule": float(resolved.resume_export_outbox_interval_seconds),
            },
            "reconcile-resume-builder-exports": {
                "task": RECONCILE_RESUME_EXPORTS_TASK,
                "schedule": float(resolved.resume_export_reconciliation_interval_seconds),
            },
        },
    )
    application.Task.max_retries = resolved.task_max_retries
    application.Task.retry_backoff_max = resolved.retry_backoff_max_seconds
    return application


celery_app = create_celery_app()
