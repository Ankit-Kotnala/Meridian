"""Inward-facing ports for Job Match application use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from rezumi.modules.job_match.domain import (
    CareerMatchSnapshot,
    JobMatchAuditEvent,
    JobSourceKind,
    OpportunityPriorityAnalysis,
    RolePreference,
)

from .models import AnalysisRecord, ImportedJobSource, JobFilter, JobRecord, PageCursor


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class CareerSnapshotProvider(Protocol):
    async def snapshot(self, owner_user_id: UUID) -> CareerMatchSnapshot: ...


class RoleContextProvider(Protocol):
    async def role_title(self, owner_user_id: UUID, role_id: UUID) -> str: ...


class JobImportProvider(Protocol):
    async def fetch(self, url: str) -> ImportedJobSource: ...


class JobMatchUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def add_job(self, record: JobRecord) -> None: ...

    async def save_job(self, record: JobRecord) -> None: ...

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID, *, for_update: bool = False
    ) -> JobRecord | None: ...

    async def list_jobs(
        self, owner_user_id: UUID, filter_by: JobFilter, after: PageCursor | None, limit: int
    ) -> list[JobRecord]: ...

    async def delete_job(self, owner_user_id: UUID, job_id: UUID) -> None: ...

    async def find_job_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> JobRecord | None: ...

    async def find_job_by_external(
        self,
        owner_user_id: UUID,
        source_kind: JobSourceKind,
        external_id: str,
    ) -> JobRecord | None: ...

    async def add_analysis(self, record: AnalysisRecord) -> None: ...

    async def get_analysis(
        self, owner_user_id: UUID, analysis_id: UUID
    ) -> AnalysisRecord | None: ...

    async def latest_analysis_for_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> AnalysisRecord | None: ...

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None: ...

    async def add_priority(self, priority: OpportunityPriorityAnalysis) -> None: ...

    async def get_priority(
        self, owner_user_id: UUID, priority_id: UUID
    ) -> OpportunityPriorityAnalysis | None: ...

    async def find_priority_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> OpportunityPriorityAnalysis | None: ...

    async def add_audit(self, event: JobMatchAuditEvent) -> None: ...

    async def get_role_preference(self, owner_user_id: UUID) -> RolePreference | None: ...

    async def upsert_role_preference(self, preference: RolePreference) -> None: ...

    async def commit(self) -> None: ...


JobMatchUnitOfWorkFactory = Callable[[], JobMatchUnitOfWork]
