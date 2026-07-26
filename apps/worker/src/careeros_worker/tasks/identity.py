"""Celery delivery adapters for durable account privacy operations."""

import asyncio

import structlog

from careeros_worker.app import celery_app
from careeros_worker.base import RetryableTaskError
from careeros_worker.config import get_settings
from careeros_worker.runtime import cleanup_account_exports, process_account_operations
from careeros_worker.task_names import (
    CLEANUP_ACCOUNT_EXPORTS_TASK,
    PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK,
)
from careeros_worker.tasks.contracts import (
    AccountExportCleanupTaskResult,
    AccountPrivacyTaskResult,
)
from careeros_worker.tasks.execution import validate_maintenance_limit

logger = structlog.get_logger(__name__)


@celery_app.task(name=PROCESS_ACCOUNT_PRIVACY_OPERATIONS_TASK)  # type: ignore[untyped-decorator]
def process_account_privacy_operations(
    limit: int | None = None,
) -> AccountPrivacyTaskResult:
    """Process a bounded durable batch without broker-carried user data."""

    settings = get_settings()
    validated_limit = validate_maintenance_limit(
        settings.account_operation_batch_size if limit is None else limit
    )
    try:
        result = asyncio.run(process_account_operations(settings, validated_limit))
    except Exception:
        raise RetryableTaskError("account_privacy_processing_unavailable") from None
    if result.blocked:
        logger.warning("account_privacy_operations_blocked", count=result.blocked)
    if result.deferred:
        logger.warning("account_privacy_operations_deferred", count=result.deferred)
    if result.dead_lettered:
        logger.error("account_privacy_operations_dead_lettered", count=result.dead_lettered)
    return {
        "claimed": result.claimed,
        "succeeded": result.succeeded,
        "blocked": result.blocked,
        "deferred": result.deferred,
        "dead_lettered": result.dead_lettered,
    }


@celery_app.task(name=CLEANUP_ACCOUNT_EXPORTS_TASK)  # type: ignore[untyped-decorator]
def cleanup_expired_account_exports(
    limit: int | None = None,
) -> AccountExportCleanupTaskResult:
    """Delete expired private archives before redacting retained metadata."""

    settings = get_settings()
    validated_limit = validate_maintenance_limit(
        settings.account_export_cleanup_batch_size if limit is None else limit
    )
    try:
        result = asyncio.run(cleanup_account_exports(settings, validated_limit))
    except Exception:
        raise RetryableTaskError("account_export_cleanup_unavailable") from None
    if result.failed:
        logger.warning("account_export_cleanup_deferred", count=result.failed)
    return {"completed": result.completed, "failed": result.failed}