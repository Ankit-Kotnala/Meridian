"""Inward-facing ports for Career Analytics."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from rezumi.modules.career_analytics.domain import (
    AnalyticsAuditEvent,
    AnalyticsOutboxMessage,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
)

from .models import (
    AnalyticsSourceWatermark,
    ApplicationAnalyticsSourcePage,
    ApplicationSourceCursor,
    SupplementalAnalyticsSnapshot,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class ApplicationAnalyticsSource(Protocol):
    async def watermark(self, owner_user_id: UUID) -> AnalyticsSourceWatermark: ...

    async def page(
        self,
        owner_user_id: UUID,
        *,
        cursor: ApplicationSourceCursor | None,
        limit: int,
    ) -> ApplicationAnalyticsSourcePage: ...


class SupplementalAnalyticsSource(Protocol):
    async def watermark(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> AnalyticsSourceWatermark: ...

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> SupplementalAnalyticsSnapshot: ...


class CareerAnalyticsUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_owner(self, owner_user_id: UUID) -> None: ...

    async def get_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None: ...

    async def get_job_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None: ...

    async def find_job_by_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> AnalyticsRefreshJob | None: ...

    async def find_latest_job(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
    ) -> AnalyticsRefreshJob | None: ...

    async def job_capacity(
        self,
        owner_user_id: UUID,
        *,
        since: datetime,
    ) -> tuple[int, int]: ...

    async def compact_terminal_job_history(
        self,
        owner_user_id: UUID,
        *,
        older_than: datetime,
        limit: int,
    ) -> int: ...

    async def add_job(
        self,
        job: AnalyticsRefreshJob,
        outbox: AnalyticsOutboxMessage,
    ) -> None: ...

    async def save_job(self, job: AnalyticsRefreshJob) -> None: ...

    async def get_outbox(
        self,
        message_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None: ...

    async def get_outbox_for_job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None: ...

    async def claim_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]: ...

    async def save_outbox(self, message: AnalyticsOutboxMessage) -> None: ...

    async def add_snapshot(self, snapshot: AnalyticsSnapshot) -> None: ...

    async def get_latest_snapshot(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
        *,
        for_update: bool = False,
    ) -> AnalyticsSnapshot | None: ...

    async def save_snapshot(self, snapshot: AnalyticsSnapshot) -> None: ...

    async def add_audit(self, event: AnalyticsAuditEvent) -> None: ...

    async def claim_expired_job_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]: ...

    async def claim_expired_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[AnalyticsOutboxMessage]: ...

    async def claim_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]: ...

    async def commit(self) -> None: ...


CareerAnalyticsUnitOfWorkFactory = Callable[[], CareerAnalyticsUnitOfWork]
