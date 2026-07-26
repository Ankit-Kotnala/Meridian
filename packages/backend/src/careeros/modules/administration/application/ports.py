"""Inward-facing ports for protected administration use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.administration.domain import AdminAuditEvent, OperatorAssignment

from .models import (
    AdminAuditPage,
    AdminCatalogSnapshot,
    AdminDeadLetterPage,
    AdminSystemTotals,
    RetryResult,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class AdministrationUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_assignment(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OperatorAssignment | None: ...

    async def append_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent: ...

    async def verify_audit_chain(self) -> bool: ...

    async def get_system_totals(self) -> AdminSystemTotals: ...

    async def get_catalog_snapshot(self, now: datetime) -> AdminCatalogSnapshot: ...

    async def list_dead_letters(self, *, cursor: str | None, limit: int) -> AdminDeadLetterPage: ...

    async def list_audit_events(self, *, cursor: str | None, limit: int) -> AdminAuditPage: ...

    async def get_idempotency(
        self, actor_user_id: UUID, operation: str, idempotency_key: str
    ) -> tuple[str, RetryResult] | None: ...

    async def add_idempotency(
        self,
        *,
        id: UUID,
        actor_user_id: UUID,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        result: RetryResult,
        created_at: datetime,
    ) -> None: ...

    async def retry_dead_letter(
        self, *, kind: str, target_id: UUID, now: datetime
    ) -> RetryResult | None: ...

    async def has_successful_retry(self, *, kind: str, target_id: UUID) -> bool: ...

    async def commit(self) -> None: ...


AdministrationUnitOfWorkFactory = Callable[[], AdministrationUnitOfWork]
