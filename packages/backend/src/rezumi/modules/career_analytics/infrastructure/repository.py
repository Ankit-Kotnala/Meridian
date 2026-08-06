"""Async SQLAlchemy persistence for Phase 9 Career Analytics."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.career_analytics.domain import (
    AnalyticsAuditEvent,
    AnalyticsJobStatus,
    AnalyticsOutboxMessage,
    AnalyticsOutboxStatus,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
    AnalyticsSnapshotStatus,
    CareerAnalyticsConflict,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsUnavailable,
)

from .models import (
    AnalyticsAuditEventModel,
    AnalyticsOutboxModel,
    AnalyticsRefreshJobModel,
    AnalyticsSnapshotModel,
)


class SqlAlchemyCareerAnalyticsUnitOfWork:
    """One transaction per owner-scoped analytics use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyCareerAnalyticsUnitOfWork:
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
            raise RuntimeError("career analytics unit of work is not active")
        return self._session

    async def lock_owner(self, owner_user_id: UUID) -> None:
        digest = hashlib.sha256(f"career-analytics:{owner_user_id}".encode()).digest()
        key = int.from_bytes(digest[:8], "big", signed=True)
        await self.session.execute(select(func.pg_advisory_xact_lock(key)))

    async def get_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None:
        statement = select(AnalyticsRefreshJobModel).where(
            AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
            AnalyticsRefreshJobModel.id == job_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def get_job_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None:
        statement = select(AnalyticsRefreshJobModel).where(
            AnalyticsRefreshJobModel.id == job_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _job(model) if model is not None else None

    async def find_job_by_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> AnalyticsRefreshJob | None:
        model = await self.session.scalar(
            select(AnalyticsRefreshJobModel).where(
                AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
                AnalyticsRefreshJobModel.idempotency_key == idempotency_key,
            )
        )
        return _job(model) if model is not None else None

    async def find_latest_job(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
    ) -> AnalyticsRefreshJob | None:
        model = await self.session.scalar(
            select(AnalyticsRefreshJobModel)
            .where(
                AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
                AnalyticsRefreshJobModel.scope == scope.value,
                AnalyticsRefreshJobModel.window_start == window_start,
                AnalyticsRefreshJobModel.window_end == window_end,
                AnalyticsRefreshJobModel.timezone == timezone,
            )
            .order_by(
                AnalyticsRefreshJobModel.created_at.desc(),
                AnalyticsRefreshJobModel.id.desc(),
            )
            .limit(1)
        )
        return _job(model) if model is not None else None

    async def job_capacity(
        self,
        owner_user_id: UUID,
        *,
        since: datetime,
    ) -> tuple[int, int]:
        active, replay = (
            await self.session.execute(
                select(
                    func.count().filter(
                        AnalyticsRefreshJobModel.status.in_(
                            (
                                AnalyticsJobStatus.QUEUED.value,
                                AnalyticsJobStatus.RUNNING.value,
                                AnalyticsJobStatus.RETRY_WAIT.value,
                            )
                        )
                    ),
                    func.count().filter(AnalyticsRefreshJobModel.created_at >= since),
                )
                .select_from(AnalyticsRefreshJobModel)
                .where(AnalyticsRefreshJobModel.owner_user_id == owner_user_id)
            )
        ).one()
        return int(active or 0), int(replay or 0)

    async def count_active_jobs(self, owner_user_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(AnalyticsRefreshJobModel)
            .where(
                AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
                AnalyticsRefreshJobModel.status.in_(
                    (
                        AnalyticsJobStatus.QUEUED.value,
                        AnalyticsJobStatus.RUNNING.value,
                        AnalyticsJobStatus.RETRY_WAIT.value,
                    )
                ),
            )
        )
        return int(value or 0)

    async def compact_terminal_job_history(
        self,
        owner_user_id: UUID,
        *,
        older_than: datetime,
        limit: int,
    ) -> int:
        """Delete bounded old terminal jobs while retaining the newest snapshot."""

        latest_snapshot_job = (
            select(AnalyticsSnapshotModel.job_id)
            .where(AnalyticsSnapshotModel.owner_user_id == owner_user_id)
            .order_by(
                AnalyticsSnapshotModel.created_at.desc(),
                AnalyticsSnapshotModel.id.desc(),
            )
            .limit(1)
        )
        candidate_ids = list(
            (
                await self.session.scalars(
                    select(AnalyticsRefreshJobModel.id)
                    .where(
                        AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
                        AnalyticsRefreshJobModel.status.in_(
                            (
                                AnalyticsJobStatus.COMPLETED.value,
                                AnalyticsJobStatus.DEAD_LETTER.value,
                            )
                        ),
                        AnalyticsRefreshJobModel.updated_at < older_than,
                        AnalyticsRefreshJobModel.id.not_in(latest_snapshot_job),
                    )
                    .order_by(
                        AnalyticsRefreshJobModel.updated_at.asc(),
                        AnalyticsRefreshJobModel.id.asc(),
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if not candidate_ids:
            return 0
        await self.session.execute(
            delete(AnalyticsRefreshJobModel).where(
                AnalyticsRefreshJobModel.owner_user_id == owner_user_id,
                AnalyticsRefreshJobModel.id.in_(candidate_ids),
            )
        )
        await self.session.flush()
        return len(candidate_ids)

    async def add_job(
        self,
        job: AnalyticsRefreshJob,
        outbox: AnalyticsOutboxMessage,
    ) -> None:
        self.session.add(_job_model(job))
        await self._flush()
        self.session.add(_outbox_model(outbox))
        await self._flush()

    async def save_job(self, job: AnalyticsRefreshJob) -> None:
        await self._execute(
            update(AnalyticsRefreshJobModel)
            .where(
                AnalyticsRefreshJobModel.owner_user_id == job.owner_user_id,
                AnalyticsRefreshJobModel.id == job.id,
            )
            .values(**_job_values(job, include_identity=False))
        )

    async def get_outbox(
        self,
        message_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None:
        statement = select(AnalyticsOutboxModel).where(AnalyticsOutboxModel.id == message_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _outbox(model) if model is not None else None

    async def get_outbox_for_job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None:
        statement = select(AnalyticsOutboxModel).where(AnalyticsOutboxModel.job_id == job_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _outbox(model) if model is not None else None

    async def claim_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        rows = (
            await self.session.execute(
                select(AnalyticsOutboxModel, AnalyticsRefreshJobModel)
                .join(
                    AnalyticsRefreshJobModel,
                    AnalyticsRefreshJobModel.id == AnalyticsOutboxModel.job_id,
                )
                .where(
                    AnalyticsOutboxModel.status == AnalyticsOutboxStatus.PENDING.value,
                    AnalyticsOutboxModel.next_attempt_at <= now,
                    AnalyticsRefreshJobModel.owner_user_id == AnalyticsOutboxModel.owner_user_id,
                )
                .order_by(
                    AnalyticsOutboxModel.next_attempt_at.asc(),
                    AnalyticsOutboxModel.id.asc(),
                )
                .limit(limit)
                .with_for_update(
                    skip_locked=True,
                    of=(AnalyticsOutboxModel, AnalyticsRefreshJobModel),
                )
            )
        ).all()
        return [(_outbox(outbox), _job(job)) for outbox, job in rows]

    async def save_outbox(self, message: AnalyticsOutboxMessage) -> None:
        await self._execute(
            update(AnalyticsOutboxModel)
            .where(AnalyticsOutboxModel.id == message.id)
            .values(**_outbox_values(message, include_identity=False))
        )

    async def add_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        self.session.add(_snapshot_model(snapshot))
        await self._flush()

    async def get_latest_snapshot(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
        *,
        for_update: bool = False,
    ) -> AnalyticsSnapshot | None:
        statement = (
            select(AnalyticsSnapshotModel)
            .where(
                AnalyticsSnapshotModel.owner_user_id == owner_user_id,
                AnalyticsSnapshotModel.scope == scope.value,
                AnalyticsSnapshotModel.window_start == window_start,
                AnalyticsSnapshotModel.window_end == window_end,
                AnalyticsSnapshotModel.timezone == timezone,
            )
            .order_by(
                AnalyticsSnapshotModel.created_at.desc(),
                AnalyticsSnapshotModel.id.desc(),
            )
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _snapshot(model) if model is not None else None

    async def save_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        await self._execute(
            update(AnalyticsSnapshotModel)
            .where(
                AnalyticsSnapshotModel.owner_user_id == snapshot.owner_user_id,
                AnalyticsSnapshotModel.id == snapshot.id,
            )
            .values(**_snapshot_values(snapshot, include_identity=False))
        )

    async def add_audit(self, event: AnalyticsAuditEvent) -> None:
        self.session.add(
            AnalyticsAuditEventModel(
                id=event.id,
                owner_user_id=event.owner_user_id,
                action=event.action.value,
                target_type=event.target_type,
                target_id=event.target_id,
                actor_user_id=event.actor_user_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                metadata_=event.metadata,
                created_at=event.created_at,
            )
        )
        await self._flush()

    async def claim_expired_job_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        rows = (
            await self.session.execute(
                select(AnalyticsOutboxModel, AnalyticsRefreshJobModel)
                .join(
                    AnalyticsRefreshJobModel,
                    AnalyticsRefreshJobModel.id == AnalyticsOutboxModel.job_id,
                )
                .where(
                    AnalyticsRefreshJobModel.status == AnalyticsJobStatus.RUNNING.value,
                    AnalyticsRefreshJobModel.leased_until < now,
                )
                .order_by(
                    AnalyticsRefreshJobModel.leased_until.asc(),
                    AnalyticsRefreshJobModel.id.asc(),
                )
                .limit(limit)
                .with_for_update(
                    skip_locked=True,
                    of=(AnalyticsOutboxModel, AnalyticsRefreshJobModel),
                )
            )
        ).all()
        return [(_outbox(outbox), _job(job)) for outbox, job in rows]

    async def claim_expired_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[AnalyticsOutboxMessage]:
        models = (
            await self.session.scalars(
                select(AnalyticsOutboxModel)
                .where(
                    AnalyticsOutboxModel.status == AnalyticsOutboxStatus.LEASED.value,
                    AnalyticsOutboxModel.leased_until < now,
                )
                .order_by(AnalyticsOutboxModel.leased_until.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [_outbox(model) for model in models]

    async def claim_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        rows = (
            await self.session.execute(
                select(AnalyticsOutboxModel, AnalyticsRefreshJobModel)
                .join(
                    AnalyticsRefreshJobModel,
                    AnalyticsRefreshJobModel.id == AnalyticsOutboxModel.job_id,
                )
                .where(
                    AnalyticsOutboxModel.status == AnalyticsOutboxStatus.PUBLISHED.value,
                    AnalyticsOutboxModel.next_attempt_at <= now,
                    AnalyticsRefreshJobModel.status.in_(
                        (
                            AnalyticsJobStatus.QUEUED.value,
                            AnalyticsJobStatus.RETRY_WAIT.value,
                        )
                    ),
                    AnalyticsRefreshJobModel.next_attempt_at <= now,
                )
                .order_by(
                    AnalyticsOutboxModel.next_attempt_at.asc(),
                    AnalyticsOutboxModel.id.asc(),
                )
                .limit(limit)
                .with_for_update(
                    skip_locked=True,
                    of=(AnalyticsOutboxModel, AnalyticsRefreshJobModel),
                )
            )
        ).all()
        return [(_outbox(outbox), _job(job)) for outbox, job in rows]

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def _execute(self, statement: Any) -> Any:
        try:
            return await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyCareerAnalyticsUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyCareerAnalyticsUnitOfWork:
        return SqlAlchemyCareerAnalyticsUnitOfWork(self._database)


def _job_values(
    job: AnalyticsRefreshJob,
    *,
    include_identity: bool,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "attempts": job.attempts,
        "completed_at": job.completed_at,
        "idempotency_key": job.idempotency_key,
        "lease_token": job.lease_token,
        "leased_until": job.leased_until,
        "max_attempts": job.max_attempts,
        "next_attempt_at": job.next_attempt_at,
        "request_fingerprint": job.request_fingerprint,
        "safe_error_code": job.safe_error_code,
        "scope": job.scope.value,
        "source_watermark_after": job.source_watermark_after,
        "source_watermark_before": job.source_watermark_before,
        "status": job.status.value,
        "timezone": job.timezone,
        "trace_id": job.trace_id,
        "updated_at": job.updated_at,
        "version": job.version,
        "window_end": job.window_end,
        "window_start": job.window_start,
    }
    if include_identity:
        values.update(
            {
                "created_at": job.created_at,
                "id": job.id,
                "owner_user_id": job.owner_user_id,
            }
        )
    return values


def _job_model(job: AnalyticsRefreshJob) -> AnalyticsRefreshJobModel:
    return AnalyticsRefreshJobModel(**_job_values(job, include_identity=True))


def _job(model: AnalyticsRefreshJobModel) -> AnalyticsRefreshJob:
    return AnalyticsRefreshJob(
        id=model.id,
        owner_user_id=model.owner_user_id,
        scope=AnalyticsScope(model.scope),
        window_start=model.window_start,
        window_end=model.window_end,
        timezone=model.timezone,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        status=AnalyticsJobStatus(model.status),
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        trace_id=model.trace_id,
        source_watermark_before=cast(dict[str, object] | None, model.source_watermark_before),
        source_watermark_after=cast(dict[str, object] | None, model.source_watermark_after),
        lease_token=model.lease_token,
        leased_until=model.leased_until,
        next_attempt_at=model.next_attempt_at,
        safe_error_code=model.safe_error_code,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
    )


def _outbox_values(
    message: AnalyticsOutboxMessage,
    *,
    include_identity: bool,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "attempts": message.attempts,
        "job_id": message.job_id,
        "lease_token": message.lease_token,
        "leased_until": message.leased_until,
        "max_attempts": message.max_attempts,
        "next_attempt_at": message.next_attempt_at,
        "published_at": message.published_at,
        "safe_error_code": message.safe_error_code,
        "status": message.status.value,
        "updated_at": message.updated_at,
    }
    if include_identity:
        values.update(
            {
                "created_at": message.created_at,
                "id": message.id,
                "owner_user_id": message.owner_user_id,
            }
        )
    return values


def _outbox_model(message: AnalyticsOutboxMessage) -> AnalyticsOutboxModel:
    return AnalyticsOutboxModel(**_outbox_values(message, include_identity=True))


def _outbox(model: AnalyticsOutboxModel) -> AnalyticsOutboxMessage:
    return AnalyticsOutboxMessage(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        status=AnalyticsOutboxStatus(model.status),
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        lease_token=model.lease_token,
        leased_until=model.leased_until,
        next_attempt_at=model.next_attempt_at,
        safe_error_code=model.safe_error_code,
        created_at=model.created_at,
        updated_at=model.updated_at,
        published_at=model.published_at,
    )


def _snapshot_values(
    snapshot: AnalyticsSnapshot,
    *,
    include_identity: bool,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "job_id": snapshot.job_id,
        "metric_definition_version": snapshot.metric_definition_version,
        "payload": snapshot.payload,
        "payload_sha256": snapshot.payload_sha256,
        "scope": snapshot.scope.value,
        "source_watermark": snapshot.source_watermark,
        "stale_at": snapshot.stale_at,
        "status": snapshot.status.value,
        "timezone": snapshot.timezone,
        "window_end": snapshot.window_end,
        "window_start": snapshot.window_start,
    }
    if include_identity:
        values.update(
            {
                "created_at": snapshot.created_at,
                "id": snapshot.id,
                "owner_user_id": snapshot.owner_user_id,
            }
        )
    return values


def _snapshot_model(snapshot: AnalyticsSnapshot) -> AnalyticsSnapshotModel:
    return AnalyticsSnapshotModel(**_snapshot_values(snapshot, include_identity=True))


def _snapshot(model: AnalyticsSnapshotModel) -> AnalyticsSnapshot:
    snapshot = AnalyticsSnapshot(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        scope=AnalyticsScope(model.scope),
        metric_definition_version=model.metric_definition_version,
        window_start=model.window_start,
        window_end=model.window_end,
        timezone=model.timezone,
        source_watermark=cast(dict[str, object], model.source_watermark),
        payload=cast(dict[str, object], model.payload),
        payload_sha256=model.payload_sha256,
        status=AnalyticsSnapshotStatus(model.status),
        created_at=model.created_at,
        stale_at=model.stale_at,
    )
    if not snapshot.verify_payload_hash():
        raise CareerAnalyticsUnavailable("analytics snapshot integrity check failed")
    return snapshot


def _raise_integrity(exc: IntegrityError) -> None:
    code = _exception_attribute(exc, "sqlstate")
    if code in {"40001", "40P01"}:
        raise CareerAnalyticsUnavailable from exc
    constraint = _constraint_name(exc)
    if constraint == "uq_career_analytics_jobs_owner_idempotency":
        raise CareerAnalyticsIdempotencyConflict from exc
    raise CareerAnalyticsConflict("career analytics persistence conflict") from exc


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        direct_name = getattr(current, "constraint_name", None)
        if isinstance(direct_name, str):
            return direct_name
        diag = getattr(current, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if isinstance(name, str):
            return name
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return ""


def _exception_attribute(exc: BaseException, name: str) -> str | None:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = getattr(current, name, None)
        if isinstance(value, str):
            return value
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return None
