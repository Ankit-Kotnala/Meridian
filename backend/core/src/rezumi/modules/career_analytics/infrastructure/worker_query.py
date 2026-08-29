"""SQL implementation of the content-free analytics worker query contract."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from rezumi.foundation.database import Database
from rezumi.modules.career_analytics.application.worker_query import (
    AnalyticsWorkerJobReference,
)
from rezumi.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsOutboxStatus,
    CareerAnalyticsNotFound,
)

from .models import AnalyticsOutboxModel, AnalyticsRefreshJobModel


class SqlAlchemyCareerAnalyticsWorkerQuery:
    """Return no user content, payload snapshot, or ownership PII."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_job_reference(self, job_id: UUID) -> AnalyticsWorkerJobReference:
        async with self._database.session() as session:
            row = (
                await session.execute(
                    select(
                        AnalyticsRefreshJobModel.id,
                        AnalyticsRefreshJobModel.trace_id,
                        AnalyticsRefreshJobModel.status,
                        AnalyticsRefreshJobModel.attempts,
                        AnalyticsRefreshJobModel.max_attempts,
                        AnalyticsRefreshJobModel.safe_error_code,
                    ).where(AnalyticsRefreshJobModel.id == job_id)
                )
            ).one_or_none()
        if row is None:
            raise CareerAnalyticsNotFound
        return _reference(row)

    async def get_outbox_status(self, message_id: UUID) -> AnalyticsOutboxStatus:
        async with self._database.session() as session:
            value = await session.scalar(
                select(AnalyticsOutboxModel.status).where(AnalyticsOutboxModel.id == message_id)
            )
        if value is None:
            raise CareerAnalyticsNotFound
        return AnalyticsOutboxStatus(value)


def _reference(row: object) -> AnalyticsWorkerJobReference:
    values = row._mapping  # type: ignore[attr-defined]
    return AnalyticsWorkerJobReference(
        job_id=values["id"],
        trace_id=values["trace_id"],
        status=AnalyticsJobStatus(values["status"]),
        attempts=values["attempts"],
        max_attempts=values["max_attempts"],
        safe_error_code=values["safe_error_code"],
    )
