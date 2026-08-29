"""Inward-facing ports for Change Studio use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from rezumi.modules.change_studio.domain import (
    ChangeStudioAuditEvent,
    ChangeStudioIdempotencyRecord,
    EvidenceGroundingContext,
    ProviderRun,
)

from .models import (
    AiGenerationRequest,
    AiProviderResponse,
    ChangeSetRecord,
    JobMatchAnalysisContext,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class SuggestionProvider(Protocol):
    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse: ...


class CareerEvidenceProvider(Protocol):
    async def evidence_contexts(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[EvidenceGroundingContext, ...]: ...


class JobMatchAnalysisProvider(Protocol):
    async def analysis(self, owner_user_id: UUID, analysis_id: UUID) -> JobMatchAnalysisContext: ...


class ChangeStudioUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def add_record(self, record: ChangeSetRecord) -> None: ...

    async def save_record(self, record: ChangeSetRecord) -> None: ...

    async def get_record(
        self, owner_user_id: UUID, change_set_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None: ...

    async def get_record_for_question(
        self, owner_user_id: UUID, question_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None: ...

    async def find_change_set_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeSetRecord | None: ...

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeStudioIdempotencyRecord | None: ...

    async def add_idempotency(self, record: ChangeStudioIdempotencyRecord) -> None: ...

    async def add_provider_run(self, run: ProviderRun) -> None: ...

    async def add_audit(self, event: ChangeStudioAuditEvent) -> None: ...

    async def commit(self) -> None: ...


ChangeStudioUnitOfWorkFactory = Callable[[], ChangeStudioUnitOfWork]
