"""Content-minimized administration read and command models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careeros.modules.administration.domain import AdminAuditEvent


class AdminPrincipal(Protocol):
    """Minimum authenticated actor contract required by administration."""

    @property
    def user_id(self) -> UUID: ...

    def was_recently_authenticated(self, now: datetime, max_age_seconds: int) -> bool: ...


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class AdminSystemTotals:
    users_active: int
    users_disabled: int
    organizations_active: int
    subscriptions_active: int
    queued_jobs: int
    retry_wait_jobs: int
    running_jobs: int
    dead_letter_jobs: int


@dataclass(frozen=True, slots=True)
class AdminSystemSnapshot:
    generated_at: datetime
    totals: AdminSystemTotals
    audit_chain_valid: bool


@dataclass(frozen=True, slots=True)
class AdminCatalogSnapshot:
    generated_at: datetime
    configured_plans: int
    owner_decision_required_plans: int
    enabled_feature_flags: tuple[str, ...]
    role_taxonomy_versions: int
    active_role_definitions: int
    resume_template_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdminDeadLetter:
    kind: str
    id: UUID
    status: str
    safe_error_code: str | None
    attempts: int
    max_attempts: int
    occurred_at: datetime
    retry_supported: bool


@dataclass(frozen=True, slots=True)
class AdminDeadLetterPage:
    items: tuple[AdminDeadLetter, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AdminAuditPage:
    items: tuple[AdminAuditEvent, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class RetryResult:
    kind: str
    id: UUID
    status: str
    replayed: bool
