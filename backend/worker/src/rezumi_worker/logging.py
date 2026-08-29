"""Celery-specific structured logging context hooks."""

from celery import signals  # type: ignore[import-untyped,unused-ignore]
from rezumi.foundation.observability import configure_logging
from structlog.contextvars import bind_contextvars, clear_contextvars

from rezumi_worker.config import WorkerSettings, get_settings


def configure_worker_logging(settings: WorkerSettings) -> None:
    """Configure shared logging while registering this module's Celery hooks."""
    configure_logging(settings)


@signals.setup_logging.connect  # type: ignore[untyped-decorator]
def configure_celery_logging(**_: object) -> None:
    """Prevent Celery from replacing the structured logging configuration."""
    configure_worker_logging(get_settings())


@signals.task_prerun.connect  # type: ignore[untyped-decorator]
def bind_task_context(
    *,
    task_id: str | None = None,
    task: object | None = None,
    **_: object,
) -> None:
    """Bind identifiers only; task arguments may contain private career data."""
    clear_contextvars()
    task_name = getattr(task, "name", "unknown")
    bind_contextvars(task_id=task_id or "unknown", task_name=task_name)


@signals.task_postrun.connect  # type: ignore[untyped-decorator]
def clear_task_context(**_: object) -> None:
    clear_contextvars()


@signals.task_failure.connect  # type: ignore[untyped-decorator]
def clear_failed_task_context(**_: object) -> None:
    clear_contextvars()
