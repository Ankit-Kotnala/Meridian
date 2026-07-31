"""Celery delivery adapter for organization invitation delivery."""

import asyncio

import structlog

from careeros_worker.app import celery_app
from careeros_worker.base import RetryableTaskError
from careeros_worker.config import get_settings
from careeros_worker.runtime import process_organization_invitations
from careeros_worker.task_names import PROCESS_ORGANIZATION_INVITATIONS_TASK
from careeros_worker.tasks.contracts import OrganizationInvitationTaskResult
from careeros_worker.tasks.execution import validate_maintenance_limit

logger = structlog.get_logger(__name__)


@celery_app.task(name=PROCESS_ORGANIZATION_INVITATIONS_TASK)  # type: ignore[untyped-decorator]
def deliver_organization_invitations(
    limit: int | None = None,
) -> OrganizationInvitationTaskResult:
    """Deliver due invitations using database-owned retry and terminal state."""

    settings = get_settings()
    validated_limit = validate_maintenance_limit(
        settings.organization_invitation_batch_size if limit is None else limit
    )
    try:
        result = asyncio.run(process_organization_invitations(settings, validated_limit))
    except Exception:
        raise RetryableTaskError("organization_invitation_delivery_unavailable") from None
    if result.deferred:
        logger.warning("organization_invitations_deferred", count=result.deferred)
    if result.dead_lettered:
        logger.error("organization_invitations_dead_lettered", count=result.dead_lettered)
    return {
        "claimed": result.claimed,
        "delivered": result.delivered,
        "cancelled": result.cancelled,
        "deferred": result.deferred,
        "dead_lettered": result.dead_lettered,
    }
