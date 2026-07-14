"""Safe common behavior for future background jobs."""

from celery import Task


class RetryableTaskError(Exception):
    """Explicit signal that an infrastructure failure is safe to retry."""


class SafeTask(Task):  # type: ignore[misc]
    """Retry only explicitly transient failures with bounded exponential backoff."""

    abstract = True
    autoretry_for = (RetryableTaskError,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    max_retries = 3
