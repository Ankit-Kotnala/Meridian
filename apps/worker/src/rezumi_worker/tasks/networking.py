"""Celery delivery adapters for local Networking reminders."""

import asyncio

import structlog

from rezumi_worker.app import celery_app
from rezumi_worker.base import RetryableTaskError
from rezumi_worker.config import get_settings
from rezumi_worker.runtime import (
    process_due_networking_reminders,
    reconcile_networking_reminders,
)
from rezumi_worker.task_names import (
    PROCESS_NETWORKING_LOCAL_REMINDERS_TASK,
    RECONCILE_NETWORKING_REMINDERS_TASK,
)
from rezumi_worker.tasks.contracts import (
    NetworkingReminderRecoveryTaskResult,
    NetworkingReminderTaskResult,
)
from rezumi_worker.tasks.execution import MAINTENANCE_LIMIT, validate_maintenance_limit

logger = structlog.get_logger(__name__)


@celery_app.task(name=PROCESS_NETWORKING_LOCAL_REMINDERS_TASK)  # type: ignore[untyped-decorator]
def process_networking_local_reminders(
    limit: int = MAINTENANCE_LIMIT,
) -> NetworkingReminderTaskResult:
    """Advance local reminder occurrences without an external-send capability."""

    validated_limit = validate_maintenance_limit(limit)
    try:
        result = asyncio.run(process_due_networking_reminders(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("networking_reminder_processing_unavailable") from None
    if result.failed:
        logger.warning("networking_local_reminders_deferred", count=result.failed)
    if result.dead_lettered:
        logger.error(
            "networking_local_reminders_dead_lettered",
            count=result.dead_lettered,
        )
    return {
        "claimed": result.claimed,
        "processed": result.processed,
        "deferred": result.deferred,
        "failed": result.failed,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=RECONCILE_NETWORKING_REMINDERS_TASK)  # type: ignore[untyped-decorator]
def reconcile_networking_local_reminders(
    limit: int = MAINTENANCE_LIMIT,
) -> NetworkingReminderRecoveryTaskResult:
    """Recover expired local reminder leases with no content payload."""

    validated_limit = validate_maintenance_limit(limit)
    try:
        result = asyncio.run(reconcile_networking_reminders(get_settings(), validated_limit))
    except Exception:
        raise RetryableTaskError("networking_reminder_reconciliation_unavailable") from None
    if result.recovered:
        logger.warning("networking_local_reminder_leases_recovered", count=result.recovered)
    if result.dead_lettered:
        logger.error(
            "networking_local_reminders_recovery_dead_lettered",
            count=result.dead_lettered,
        )
    return {
        "recovered": result.recovered,
        "dead_lettered": result.dead_lettered,
    }
