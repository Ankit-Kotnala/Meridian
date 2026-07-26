"""Inward-facing ports for resume builder use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.resume_builder.domain import (
    ResumeBuilderAuditEvent,
    ResumeBuilderIdempotencyRecord,
    ResumeDownloadIntent,
    ResumeExport,
    ResumeExportObjectCleanup,
    ResumeExportOperation,
    ResumeExportOutboxMessage,
    ResumeVerificationReport,
    ResumeVersion,
)

from .models import (
    ExtractedDocumentText,
    RenderedResume,
    ResumeRecord,
    ResumeSourceSnapshot,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class ResumeSourceProvider(Protocol):
    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        change_set_id: UUID | None = None,
        change_set_version_id: UUID | None = None,
    ) -> ResumeSourceSnapshot: ...


class ResumeRenderer(Protocol):
    def render(self, version: ResumeVersion, *, fmt: str) -> RenderedResume: ...


class ResumeDocumentExtractor(Protocol):
    async def extract(self, path: Path, media_type: str) -> ExtractedDocumentText: ...


class ResumeObjectStorage(Protocol):
    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None: ...

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes: ...

    async def delete(self, object_key: str) -> None: ...

    async def presign_get(self, object_key: str, *, expires_in_seconds: int) -> str: ...

    async def dispose(self) -> None: ...


class ResumeExportJobPublisher(Protocol):
    async def publish(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None: ...


class ResumeBuilderUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def list_resumes(self, owner_user_id: UUID) -> tuple[ResumeRecord, ...]: ...

    async def add_resume(self, record: ResumeRecord) -> None: ...

    async def save_resume(self, record: ResumeRecord) -> None: ...

    async def get_resume(
        self, owner_user_id: UUID, resume_id: UUID, *, for_update: bool = False
    ) -> ResumeRecord | None: ...

    async def list_versions(
        self, owner_user_id: UUID, resume_id: UUID
    ) -> tuple[ResumeVersion, ...]: ...

    async def get_version(self, owner_user_id: UUID, version_id: UUID) -> ResumeVersion | None: ...

    async def add_version(self, version: ResumeVersion) -> None: ...

    async def set_current_version(
        self, owner_user_id: UUID, resume_id: UUID, version_id: UUID, *, now: datetime
    ) -> ResumeRecord | None: ...

    async def find_export_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeExport | None: ...

    async def add_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None: ...

    async def save_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None: ...

    async def get_export(self, owner_user_id: UUID, export_id: UUID) -> ResumeExport | None: ...

    async def get_export_system(
        self, export_id: UUID, *, for_update: bool = False
    ) -> ResumeExport | None: ...

    async def list_recoverable_exports(
        self, now: datetime, limit: int
    ) -> tuple[ResumeExport, ...]: ...

    async def get_verification(
        self, owner_user_id: UUID, export_id: UUID
    ) -> ResumeVerificationReport | None: ...

    async def find_download_intent_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeDownloadIntent | None: ...

    async def add_download_intent(self, intent: ResumeDownloadIntent) -> None: ...

    async def add_export_outbox(self, message: ResumeExportOutboxMessage) -> None: ...

    async def claim_export_outbox(
        self, now: datetime, lease_expires_at: datetime, limit: int
    ) -> tuple[ResumeExportOutboxMessage, ...]: ...

    async def save_export_outbox(
        self,
        message: ResumeExportOutboxMessage,
        *,
        expected_lease_token: UUID,
    ) -> bool: ...

    async def has_active_export_outbox(
        self,
        export_id: UUID,
        operation: ResumeExportOperation,
    ) -> bool: ...

    async def add_export_object_cleanup(self, cleanup: ResumeExportObjectCleanup) -> None: ...

    async def get_export_object_cleanup(
        self,
        owner_user_id: UUID,
        export_id: UUID,
        attempt_fence: int,
        *,
        for_update: bool = False,
    ) -> ResumeExportObjectCleanup | None: ...

    async def list_due_export_object_cleanups(
        self, now: datetime, limit: int
    ) -> tuple[ResumeExportObjectCleanup, ...]: ...

    async def save_export_object_cleanup(self, cleanup: ResumeExportObjectCleanup) -> None: ...

    async def add_idempotency(self, record: ResumeBuilderIdempotencyRecord) -> None: ...

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeBuilderIdempotencyRecord | None: ...

    async def add_audit(self, event: ResumeBuilderAuditEvent) -> None: ...

    async def commit(self) -> None: ...


ResumeBuilderUnitOfWorkFactory = Callable[[], ResumeBuilderUnitOfWork]
