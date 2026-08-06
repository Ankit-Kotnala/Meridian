"""Structured logging shared by HTTP and worker deployables."""

import logging
import sys
from typing import Any, Protocol

import structlog

_PAYLOAD_BEARING_LIBRARY_LOGGERS = (
    "aiobotocore",
    "boto3",
    "botocore",
    "httpcore",
    "httpx",
    "urllib3",
    "uvicorn.access",
)


class LoggingSettings(Protocol):
    """Read-only configuration surface implemented by both service settings models."""

    @property
    def log_level(self) -> str: ...

    @property
    def log_format(self) -> str: ...


def configure_logging(settings: LoggingSettings) -> None:
    """Configure structlog and bridge standard-library logs to the same renderer."""
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

    # Network client/access log messages can embed full URLs, query tokens, raw
    # dynamic paths, or provider payloads. Application adapters emit their own
    # allowlisted operational events, so these unstructured channels stay off.
    for name in _PAYLOAD_BEARING_LIBRARY_LOGGERS:
        logging.getLogger(name).disabled = True

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
