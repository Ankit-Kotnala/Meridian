"""SQLAlchemy persistence for declared-profile enrichment jobs + outbox."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.career_record.application.declared_profile_jobs import (
    DeclaredProfileEnrichmentJob,
    DeclaredProfileEnrichmentJobConflict,
    DeclaredProfileEnrichmentJobStatus,
    DeclaredProfileEnrichmentOutboxMessage,
)

from .models import DeclaredProfileEnrichmentJobModel, DeclaredProfileEnrichmentOutboxModel


class SqlAlchemyDeclaredProfileEnrichmentJobUnitOfWork:
    """Owner-scoped transactional persistence with worker-only system lookups."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyDeclaredProfileEnrichmentJobUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("declared-profile job unit of work is not active")

        return self._session

    async def get_active_job_for_fact(
        self, owner_user_id: UUID, personal_fact_id: UUID
    ) -> DeclaredProfileEnrichmentJob | None:
        model = await self.session.scalar(
            select(DeclaredProfileEnrichmentJobModel)
            .where(
                DeclaredProfileEnrichmentJobModel.owner_user_id == owner_user_id,
                DeclaredProfileEnrichmentJobModel.personal_fact_id == personal_fact_id,
                DeclaredProfileEnrichmentJobModel.status.in_(("queued", "running")),
            )
            .with_for_update()
        )
        return _job(model) if model is not None else None

    async def add_job(self, job: DeclaredProfileEnrichmentJob) -> None:
        self.session.add(DeclaredProfileEnrichmentJobModel(**_job_values(job)))
        await self._flush()

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> DeclaredProfileEnrichmentJob | None:
        model = await self.session.scalar(
            select(DeclaredProfileEnrichmentJobModel).where(
                DeclaredProfileEnrichmentJobModel.owner_user_id == owner_user_id,
                DeclaredProfileEnrichmentJobModel.id == job_id,
            )
        )
        return _job(model) if model is not None else None

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> DeclaredProfileEnrichmentJob | None:
        statement = select(DeclaredProfileEnrichmentJobModel).where(
            DeclaredProfileEnrichmentJobModel.id == job_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def save_job(self, job: DeclaredProfileEnrichmentJob) -> None:
        values = _job_values(job)
        for immutable in ("id", "owner_user_id", "personal_fact_id", "created_at"):
            values.pop(immutable)
        await self.session.execute(
            update(DeclaredProfileEnrichmentJobModel)
            .where(
                DeclaredProfileEnrichmentJobModel.owner_user_id == job.owner_user_id,
                DeclaredProfileEnrichmentJobModel.id == job.id,
            )
            .values(**values)
        )

    async def list_stale_running_jobs(
        self, stale_before: datetime, limit: int
    ) -> list[DeclaredProfileEnrichmentJob]:
        models = (
            await self.session.scalars(
                select(DeclaredProfileEnrichmentJobModel)
                .where(
                    DeclaredProfileEnrichmentJobModel.status == "running",
                    DeclaredProfileEnrichmentJobModel.updated_at <= stale_before,
                )
                .order_by(
                    DeclaredProfileEnrichmentJobModel.updated_at,
                    DeclaredProfileEnrichmentJobModel.id,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_job(model) for model in models]

    async def add_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None:
        self.session.add(DeclaredProfileEnrichmentOutboxModel(**_outbox_values(message)))
        await self._flush()

    async def list_pending_outbox(
        self, now: datetime, limit: int
    ) -> list[DeclaredProfileEnrichmentOutboxMessage]:
        models = (
            await self.session.scalars(
                select(DeclaredProfileEnrichmentOutboxModel)
                .where(
                    DeclaredProfileEnrichmentOutboxModel.published_at.is_(None),
                    DeclaredProfileEnrichmentOutboxModel.dead_lettered_at.is_(None),
                    DeclaredProfileEnrichmentOutboxModel.next_attempt_at <= now,
                )
                .order_by(
                    DeclaredProfileEnrichmentOutboxModel.next_attempt_at,
                    DeclaredProfileEnrichmentOutboxModel.created_at,
                    DeclaredProfileEnrichmentOutboxModel.id,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_outbox(model) for model in models]

    async def save_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None:
        values = _outbox_values(message)
        for immutable in (
            "id",
            "owner_user_id",
            "job_id",
            "task_name",
            "trace_id",
            "created_at",
        ):
            values.pop(immutable)
        await self.session.execute(
            update(DeclaredProfileEnrichmentOutboxModel)
            .where(
                DeclaredProfileEnrichmentOutboxModel.owner_user_id == message.owner_user_id,
                DeclaredProfileEnrichmentOutboxModel.id == message.id,
            )
            .values(**values)
        )

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DeclaredProfileEnrichmentJobConflict from exc
        self._committed = True

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DeclaredProfileEnrichmentJobConflict from exc


class SqlAlchemyDeclaredProfileEnrichmentJobUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyDeclaredProfileEnrichmentJobUnitOfWork:
        return SqlAlchemyDeclaredProfileEnrichmentJobUnitOfWork(self._database)


def _job(model: DeclaredProfileEnrichmentJobModel) -> DeclaredProfileEnrichmentJob:
    return DeclaredProfileEnrichmentJob(
        id=model.id,
        owner_user_id=model.owner_user_id,
        personal_fact_id=model.personal_fact_id,
        trace_id=model.trace_id,
        status=DeclaredProfileEnrichmentJobStatus(model.status),
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        created_at=model.created_at,
        updated_at=model.updated_at,
        next_attempt_at=model.next_attempt_at,
        completed_at=model.completed_at,
        result_platform=model.result_platform,
        result_achievements_created=model.result_achievements_created,
        result_evidence_created=model.result_evidence_created,
        error_message=model.error_message,
    )


def _job_values(job: DeclaredProfileEnrichmentJob) -> dict[str, object]:
    return {
        "id": job.id,
        "owner_user_id": job.owner_user_id,
        "personal_fact_id": job.personal_fact_id,
        "trace_id": job.trace_id,
        "status": job.status.value,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "next_attempt_at": job.next_attempt_at,
        "completed_at": job.completed_at,
        "result_platform": job.result_platform,
        "result_achievements_created": job.result_achievements_created,
        "result_evidence_created": job.result_evidence_created,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _outbox(model: DeclaredProfileEnrichmentOutboxModel) -> DeclaredProfileEnrichmentOutboxMessage:
    return DeclaredProfileEnrichmentOutboxMessage(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        task_name=model.task_name,
        trace_id=model.trace_id,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        created_at=model.created_at,
        next_attempt_at=model.next_attempt_at,
        published_at=model.published_at,
        dead_lettered_at=model.dead_lettered_at,
    )


def _outbox_values(message: DeclaredProfileEnrichmentOutboxMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "owner_user_id": message.owner_user_id,
        "job_id": message.job_id,
        "task_name": message.task_name,
        "trace_id": message.trace_id,
        "attempts": message.attempts,
        "max_attempts": message.max_attempts,
        "next_attempt_at": message.next_attempt_at,
        "published_at": message.published_at,
        "dead_lettered_at": message.dead_lettered_at,
        "created_at": message.created_at,
    }
