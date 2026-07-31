"""Least-privilege operator authority and immutable audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from .errors import AdministrationValidationError


class AdminCapability(StrEnum):
    SYSTEM_READ = "system.read"
    JOBS_READ = "jobs.read"
    JOBS_RETRY = "jobs.retry"
    CATALOG_READ = "catalog.read"
    AUDIT_READ = "audit.read"
    AUDIT_VERIFY = "audit.verify"


class AdminRole(StrEnum):
    OPERATIONS_VIEWER = "operations_viewer"
    JOB_OPERATOR = "job_operator"
    CATALOG_AUDITOR = "catalog_auditor"
    SECURITY_AUDITOR = "security_auditor"


_ROLE_CAPABILITIES = MappingProxyType(
    {
        AdminRole.OPERATIONS_VIEWER: frozenset(
            {AdminCapability.SYSTEM_READ, AdminCapability.JOBS_READ}
        ),
        AdminRole.JOB_OPERATOR: frozenset(
            {
                AdminCapability.SYSTEM_READ,
                AdminCapability.JOBS_READ,
                AdminCapability.JOBS_RETRY,
            }
        ),
        AdminRole.CATALOG_AUDITOR: frozenset(
            {AdminCapability.SYSTEM_READ, AdminCapability.CATALOG_READ}
        ),
        AdminRole.SECURITY_AUDITOR: frozenset(
            {
                AdminCapability.SYSTEM_READ,
                AdminCapability.JOBS_READ,
                AdminCapability.CATALOG_READ,
                AdminCapability.AUDIT_READ,
                AdminCapability.AUDIT_VERIFY,
            }
        ),
    }
)


@dataclass(frozen=True, slots=True)
class OperatorAssignment:
    user_id: UUID
    role: AdminRole
    granted_at: datetime
    grant_reason: str
    granted_by_user_id: UUID | None = None
    revoked_at: datetime | None = None
    revoked_by_user_id: UUID | None = None
    revoke_reason: str | None = None

    def __post_init__(self) -> None:
        _aware(self.granted_at, "grant time")
        _reason(self.grant_reason, "grant reason")
        if self.revoked_at is not None:
            _aware(self.revoked_at, "revocation time")
            if self.revoked_at < self.granted_at:
                raise AdministrationValidationError("revocation precedes grant")
            _reason(self.revoke_reason, "revocation reason")
        elif self.revoked_by_user_id is not None or self.revoke_reason is not None:
            raise AdministrationValidationError("active assignment contains revocation data")

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    @property
    def capabilities(self) -> frozenset[AdminCapability]:
        if not self.active:
            return frozenset()
        return _ROLE_CAPABILITIES[self.role]

    def allows(self, capability: AdminCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True, slots=True)
class AdminAuditEvent:
    id: UUID
    actor_user_id: UUID | None
    actor_role: AdminRole | None
    capability: AdminCapability
    action: str
    outcome: str
    reason: str
    request_id: str
    trace_id: str
    occurred_at: datetime
    target_kind: str | None = None
    target_id: UUID | None = None
    sequence: int | None = None
    actor_reference: str | None = None
    previous_hash: str | None = None
    event_hash: str | None = None

    def __post_init__(self) -> None:
        _key(self.action, "audit action", 80)
        if self.outcome not in {"accepted", "success", "denied", "failed"}:
            raise AdministrationValidationError("admin audit outcome is invalid")
        _reason(self.reason, "audit reason")
        _context(self.request_id, "request id", 128)
        _context(self.trace_id, "trace id", 64)
        _aware(self.occurred_at, "audit time")
        if self.target_kind is not None:
            _key(self.target_kind, "target kind", 64)
        if (self.previous_hash is None) != (self.event_hash is None):
            raise AdministrationValidationError("audit hash state is inconsistent")
        if self.actor_reference is not None and (
            len(self.actor_reference) != 64
            or any(character not in "0123456789abcdef" for character in self.actor_reference)
        ):
            raise AdministrationValidationError("audit actor reference is invalid")


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AdministrationValidationError(f"{field} must be timezone-aware")


def _key(value: str, field: str, maximum: int) -> None:
    if (
        not value
        or len(value) > maximum
        or any(
            not (character.islower() or character.isdigit() or character in "._-")
            for character in value
        )
    ):
        raise AdministrationValidationError(f"{field} is invalid")


def _reason(value: str | None, field: str) -> None:
    if value is None or not 12 <= len(value.strip()) <= 500:
        raise AdministrationValidationError(f"{field} must be between 12 and 500 characters")
    if any(ord(character) < 32 and character not in "\t" for character in value):
        raise AdministrationValidationError(f"{field} contains control characters")


def _context(value: str, field: str, maximum: int) -> None:
    if (
        not value
        or len(value) > maximum
        or any(character.isspace() or not character.isprintable() for character in value)
    ):
        raise AdministrationValidationError(f"{field} is invalid")
