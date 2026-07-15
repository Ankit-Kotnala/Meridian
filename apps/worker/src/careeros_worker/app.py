"""Celery application factory and command-line entry point."""

from celery import Celery

from careeros_worker.base import SafeTask
from careeros_worker.config import WorkerSettings, get_settings
from careeros_worker.logging import configure_worker_logging


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
        timezone="UTC",
        worker_hijack_root_logger=False,
        worker_max_tasks_per_child=resolved.worker_max_tasks_per_child,
        worker_prefetch_multiplier=resolved.worker_prefetch_multiplier,
        worker_send_task_events=True,
    )
    application.Task.max_retries = resolved.task_max_retries
    application.Task.retry_backoff_max = resolved.retry_backoff_max_seconds
    return application


celery_app = create_celery_app()
