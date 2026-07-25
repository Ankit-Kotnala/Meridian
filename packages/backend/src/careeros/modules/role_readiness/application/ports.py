"""Inward-facing ports for Role Explorer application use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.role_readiness.domain import (
    RoleCompetency,
    RoleDefinition,
    RoleReadinessAuditEvent,
    RoleTaxonomyVersion,
    SavedRole,
)
from careeros.modules.role_readiness.domain.scoring import CareerReadinessSnapshot

from .models import (
    AnalysisRecord,
    PageCursor,
    RoleFilter,
    RoleReadinessAnalyticsPoint,
    RoleReadinessAnalyticsSourceState,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class CareerSnapshotProvider(Protocol):
    async def snapshot(self, owner_user_id: UUID) -> CareerReadinessSnapshot: ...


class RoleReadinessUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_taxonomy_version(self, taxonomy_id: UUID) -> RoleTaxonomyVersion | None: ...

    async def get_active_taxonomy(self) -> RoleTaxonomyVersion | None: ...

    async def get_role(self, role_id: UUID) -> RoleDefinition | None: ...

    async def list_roles(
        self, filter_by: RoleFilter, after: PageCursor | None, limit: int
    ) -> list[RoleDefinition]: ...

    async def list_role_competencies(self, role_id: UUID) -> list[RoleCompetency]: ...

    async def get_saved_role(
        self, owner_user_id: UUID, saved_role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None: ...

    async def get_saved_role_by_role(
        self, owner_user_id: UUID, role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None: ...

    async def list_saved_roles(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[SavedRole]: ...

    async def add_saved_role(self, saved_role: SavedRole) -> None: ...

    async def save_saved_role(self, saved_role: SavedRole) -> None: ...

    async def delete_saved_role(self, owner_user_id: UUID, saved_role_id: UUID) -> None: ...

    async def add_analysis(self, record: AnalysisRecord) -> None: ...

    async def get_analysis(
        self, owner_user_id: UUID, analysis_id: UUID
    ) -> AnalysisRecord | None: ...

    async def list_analyses(
        self, owner_user_id: UUID, role_id: UUID | None, after: PageCursor | None, limit: int
    ) -> list[AnalysisRecord]: ...

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None: ...

    async def list_analytics_history(
        self,
        owner_user_id: UUID,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> list[RoleReadinessAnalyticsPoint]: ...

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> RoleReadinessAnalyticsSourceState: ...

    async def add_audit(self, event: RoleReadinessAuditEvent) -> None: ...

    async def commit(self) -> None: ...


RoleReadinessUnitOfWorkFactory = Callable[[], RoleReadinessUnitOfWork]
