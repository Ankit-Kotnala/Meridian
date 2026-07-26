"""Celery application factory and command-line entry point."""

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
from celery import Celery  # type: ignore[import-untyped,unused-ignore]

from careeros_worker.base import SafeTask
from careeros_worker.config import WorkerSettings, get_settings
from careeros_worker.logging import configure_worker_logging
from careeros_worker.task_names import (
    CLEANUP_ACCOUNT_EXPORTS_TASK,
    DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK,
    DISPATCH_RESUME_EXPORT_OUTBOX_TASK,
    PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK,
    PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    PROCESS_ORGANIZATION_INVITATIONS_TASK,
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
        "careeros_worker",
        broker=resolved.broker_url.get_secret_value(),
        backend=resolved.result_backend.get_secret_value(),
        include=["careeros_worker.tasks"],
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
    privacy_time_limit = min(
        resolved.task_time_limit_seconds,
        resolved.account_operation_lease_seconds - 5,
    )
    privacy_soft_time_limit = min(
        resolved.task_soft_time_limit_seconds,
        privacy_time_limit - 1,
    )
    invitation_time_limit = min(
        resolved.task_time_limit_seconds,
        resolved.organization_invitation_lease_seconds - 5,
    )
    invitation_soft_time_limit = min(
        resolved.task_soft_time_limit_seconds,
        invitation_time_limit - 1,
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
            PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK: {
                "soft_time_limit": privacy_soft_time_limit,
                "time_limit": privacy_time_limit,
            },
            PROCESS_NETWORKING_LOCAL_REMINDERS_TASK: {
                "soft_time_limit": networking_soft_time_limit,
                "time_limit": networking_time_limit,
            },
            PROCESS_ORGANIZATION_INVITATIONS_TASK: {
                "soft_time_limit": invitation_soft_time_limit,
                "time_limit": invitation_time_limit,
            },
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
            PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK: {"queue": "maintenance"},
            CLEANUP_ACCOUNT_EXPORTS_TASK: {"queue": "maintenance"},
            PROCESS_CAREER_ANALYTICS_REFRESH_TASK: {"queue": "default"},
            DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK: {"queue": "maintenance"},
            RECONCILE_CAREER_ANALYTICS_TASK: {"queue": "maintenance"},
            PROCESS_NETWORKING_LOCAL_REMINDERS_TASK: {"queue": "maintenance"},
            PROCESS_ORGANIZATION_INVITATIONS_TASK: {"queue": "maintenance"},
            RECONCILE_NETWORKING_REMINDERS_TASK: {"queue": "maintenance"},
            PROCESS_EVIDENCE_ATTACHMENT_TASK: {"queue": "career-record"},
            DISPATCH_EVIDENCE_ATTACHMENT_OUTBOX_TASK: {"queue": "maintenance"},
            CLEANUP_EVIDENCE_ATTACHMENT_OBJECTS_TASK: {"queue": "maintenance"},
            RECONCILE_EVIDENCE_ATTACHMENT_JOBS_TASK: {"queue": "maintenance"},
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
            "process-account-privacy-operations": {
                "task": PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK,
                "schedule": float(resolved.account_operation_interval_seconds),
            },
            "cleanup-expired-account-exports": {
                "task": CLEANUP_ACCOUNT_EXPORTS_TASK,
                "schedule": float(resolved.account_export_cleanup_interval_seconds),
            },
            "deliver-organization-invitations": {
                "task": PROCESS_ORGANIZATION_INVITATIONS_TASK,
                "schedule": float(resolved.organization_invitation_interval_seconds),
            },
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
