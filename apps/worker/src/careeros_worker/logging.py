"""Structured logging and Celery task context hooks."""

import logging
import sys
from typing import Any

import structlog
from celery import signals
from structlog.contextvars import bind_contextvars, clear_contextvars

from careeros_worker.config import WorkerSettings, get_settings


def configure_logging(settings: WorkerSettings) -> None:
    """Configure application and Celery logs without serializing task arguments."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    renderer: Any
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level]
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@signals.setup_logging.connect  # type: ignore[untyped-decorator]
def configure_celery_logging(**_: object) -> None:
    """Prevent Celery from replacing the structured logging configuration."""
    configure_logging(get_settings())


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
