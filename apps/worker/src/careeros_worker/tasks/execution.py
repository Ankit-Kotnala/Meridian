"""Bounded validation and delivery-fencing primitives for Celery adapters."""

import hashlib
from uuid import uuid4

from careeros_worker.base import RetryableTaskError, SafeTask
from careeros_worker.config import WorkerSettings

MAINTENANCE_LIMIT = 100


def validate_maintenance_limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 500:
        raise ValueError("maintenance limit must be an integer between 1 and 500")
    return value


def retries_exhausted(task: SafeTask, settings: WorkerSettings) -> bool:
    retries = int(getattr(task.request, "retries", 0))
    return retries >= settings.task_max_retries


def execution_token(task: SafeTask) -> str:
    value = getattr(task.request, "id", None)
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        raise RetryableTaskError("worker_delivery_id_unavailable")
    # Celery preserves its logical task ID across retries and redelivery. Add a
    # per-invocation nonce so overlapping deliveries cannot share a live lease,
    # then hash into the backend's bounded fencing-token contract.
    return hashlib.sha256(f"{value}\0{uuid4().hex}".encode()).hexdigest()
