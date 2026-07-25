"""Inward-facing ports for application workspace use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.application_workspace.domain import (
    ApplicationAuditEvent,
    ApplicationDocument,
    ApplicationEvent,
    ApplicationEvidencePin,
    ApplicationIdempotencyRecord,
    ApplicationNote,
    ApplicationPack,
    ApplicationRecord,
    ApplicationTask,
)

from .models import (
    ApplicationAnalyticsCursor,
    ApplicationAnalyticsSourceState,
    ApplicationCalendarEntry,
    ApplicationFilter,
    ApplicationInterviewEvidenceReference,
    ApplicationJobSnapshot,
    ApplicationMilestones,
    ApplicationPackView,
    ApplicationReference,
    ApplicationResumeSnapshot,
    ApplicationSourceEvidenceReference,
    ApplicationSummary,
    PageCursor,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class JobSnapshotProvider(Protocol):
    async def snapshot(self, owner_user_id: UUID, job_id: UUID) -> ApplicationJobSnapshot: ...


class ResumeVersionSnapshotProvider(Protocol):
    async def snapshot(
        self, owner_user_id: UUID, version_id: UUID
    ) -> ApplicationResumeSnapshot: ...


class EvidenceSnapshotProvider(Protocol):
    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]: ...

    async def validate_current(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationInterviewEvidenceReference, ...],
    ) -> None: ...


class ApplicationWorkspaceUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_owner_quota(self, owner_user_id: UUID) -> None: ...

    async def lock_application_quota(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None: ...

    async def list_application_summaries(
        self,
        owner_user_id: UUID,
        filter_by: ApplicationFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationSummary]: ...

    async def count_applications(self, owner_user_id: UUID) -> int: ...

    async def count_manual_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int: ...

    async def count_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int: ...

    async def count_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int: ...

    async def count_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int: ...

    async def list_application_records(
        self,
        owner_user_id: UUID,
        after: ApplicationAnalyticsCursor | None,
        limit: int,
    ) -> list[ApplicationRecord]: ...

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> ApplicationAnalyticsSourceState: ...

    async def list_application_milestones(
        self,
        owner_user_id: UUID,
        application_ids: tuple[UUID, ...],
    ) -> dict[UUID, ApplicationMilestones]: ...

    async def list_calendar_entries(
        self,
        owner_user_id: UUID,
        start: date,
        end: date,
        limit: int,
    ) -> list[ApplicationCalendarEntry]: ...

    async def get_application_summary(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationSummary | None: ...

    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference | None: ...

    async def get_application_record(
        self, owner_user_id: UUID, application_id: UUID, *, for_update: bool = False
    ) -> ApplicationRecord | None: ...

    async def add_application(self, record: ApplicationRecord) -> None: ...

    async def save_application(self, record: ApplicationRecord) -> None: ...

    async def delete_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None: ...

    async def add_task(self, task: ApplicationTask) -> None: ...

    async def list_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationTask]: ...

    async def get_task(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        task_id: UUID,
        *,
        for_update: bool = False,
    ) -> ApplicationTask | None: ...

    async def save_task(self, task: ApplicationTask) -> None: ...

    async def add_note(self, note: ApplicationNote) -> None: ...

    async def list_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationNote]: ...

    async def get_note(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        note_id: UUID,
    ) -> ApplicationNote | None: ...

    async def add_event(self, event: ApplicationEvent) -> None: ...

    async def list_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        before_occurred_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> list[ApplicationEvent]: ...

    async def get_event(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        event_id: UUID,
    ) -> ApplicationEvent | None: ...

    async def add_pack(
        self, pack: ApplicationPack, documents: tuple[ApplicationDocument, ...]
    ) -> None: ...

    async def list_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationPack]: ...

    async def get_pack(self, owner_user_id: UUID, pack_id: UUID) -> ApplicationPackView | None: ...

    async def find_pack_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ApplicationPackView | None: ...

    async def get_document(
        self, owner_user_id: UUID, application_id: UUID, document_id: UUID
    ) -> ApplicationDocument | None: ...

    async def save_document(self, document: ApplicationDocument) -> None: ...

    async def add_idempotency(self, record: ApplicationIdempotencyRecord) -> None: ...

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ApplicationIdempotencyRecord | None: ...

    async def add_audit(self, event: ApplicationAuditEvent) -> None: ...

    async def commit(self) -> None: ...


ApplicationWorkspaceUnitOfWorkFactory = Callable[[], ApplicationWorkspaceUnitOfWork]
