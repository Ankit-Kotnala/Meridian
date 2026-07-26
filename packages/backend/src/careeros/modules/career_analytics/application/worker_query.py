"""Purpose-minimized query contract for Career Analytics worker delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from careeros.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsOutboxStatus,
)


@dataclass(frozen=True, slots=True)
class AnalyticsWorkerJobReference:
    """Content-free durable state required to deliver or recover one refresh."""

    job_id: UUID
    trace_id: str
    status: AnalyticsJobStatus
    attempts: int
    max_attempts: int
    safe_error_code: str | None


class CareerAnalyticsWorkerQuery(Protocol):
    """Read only identifiers and machine-readable state needed by the worker."""

    async def get_job_reference(self, job_id: UUID) -> AnalyticsWorkerJobReference: ...

    async def get_outbox_status(self, message_id: UUID) -> AnalyticsOutboxStatus: ...
