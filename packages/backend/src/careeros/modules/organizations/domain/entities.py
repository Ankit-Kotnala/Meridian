"""Framework-independent organization tenancy entities and invariants."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from .errors import OrganizationValidationError

_NAME = re.compile(r"^[^\x00-\x1f\x7f]{2,160}$")
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")


def _bounded_text(value: str, field_name: str, maximum: int) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > maximum:
        raise OrganizationValidationError(f"{field_name} is invalid")
    if "\x00" in normalized or any(ord(character) < 32 for character in normalized):
        raise OrganizationValidationError(f"{field_name} contains unsupported characters")
    return normalized


def _key(value: str, field_name: str) -> str:
    normalized = value.strip()
    if _KEY.fullmatch(normalized) is None:
        raise OrganizationValidationError(f"{field_name} is invalid")
    return normalized


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    COACH = "coach"
    MEMBER = "member"


class OrganizationMembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    LEFT = "left"


class OrganizationCapability(StrEnum):
    MANAGE_ORGANIZATION = "manage_organization"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_GRANTS = "manage_grants"
    MANAGE_BILLING = "manage_billing"
    VIEW_AGGREGATES = "view_aggregates"
    COACH_COLLABORATE = "coach_collaborate"
    MANAGE_OWN_GRANTS = "manage_own_grants"


ROLE_CAPABILITIES: Mapping[OrganizationRole, frozenset[OrganizationCapability]] = MappingProxyType(
    {
        OrganizationRole.OWNER: frozenset(OrganizationCapability),
        OrganizationRole.ADMIN: frozenset(
            {
                OrganizationCapability.MANAGE_ORGANIZATION,
                OrganizationCapability.MANAGE_MEMBERS,
                OrganizationCapability.MANAGE_GRANTS,
                OrganizationCapability.VIEW_AGGREGATES,
                OrganizationCapability.COACH_COLLABORATE,
            }
        ),
        OrganizationRole.COACH: frozenset(
            {
                OrganizationCapability.COACH_COLLABORATE,
            }
        ),
        OrganizationRole.MEMBER: frozenset(
            {
                OrganizationCapability.MANAGE_OWN_GRANTS,
            }
        ),
    }
)


class InvitationStatus(StrEnum):
    PENDING_DELIVERY = "pending_delivery"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"
    DELIVERY_DEAD_LETTERED = "delivery_dead_lettered"


class GrantPurpose(StrEnum):
    COACHING = "coaching"
    CAREER_SERVICES = "career_services"
    PROGRAM_SUPPORT = "program_support"


class GrantScope(StrEnum):
    CAREER_PROFILE_SUMMARY = "career_profile_summary"
    RESUME_HEALTH_SUMMARY = "resume_health_summary"
    ROLE_READINESS_SUMMARY = "role_readiness_summary"
    APPLICATION_STATUS = "application_status"
    CAREER_GROWTH_SUMMARY = "career_growth_summary"
    COLLABORATION_COMMENT = "collaboration_comment"


class GrantStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OrganizationAuditAction(StrEnum):
    CREATED = "organization_created"
    UPDATED = "organization_updated"
    INVITATION_CREATED = "invitation_created"
    INVITATION_DELIVERED = "invitation_delivered"
    INVITATION_DELIVERY_FAILED = "invitation_delivery_failed"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
    MEMBER_SUSPENDED = "member_suspended"
    GRANT_CREATED = "grant_created"
    GRANT_REVOKED = "grant_revoked"


@dataclass(slots=True)
class Organization:
    id: UUID
    name: str
    created_by_user_id: UUID
    status: OrganizationStatus
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        normalized = " ".join(self.name.strip().split())
        if _NAME.fullmatch(normalized) is None:
            raise OrganizationValidationError("organization name is invalid")
        self.name = normalized
        if not 1 <= self.version <= 2_147_483_647:
            raise OrganizationValidationError("organization version is invalid")
        if self.created_at > self.updated_at:
            raise OrganizationValidationError("organization timestamps are invalid")

    def rename(self, name: str, now: datetime) -> None:
        normalized = " ".join(name.strip().split())
        if _NAME.fullmatch(normalized) is None:
            raise OrganizationValidationError("organization name is invalid")
        if normalized == self.name:
            raise OrganizationValidationError("organization name did not change")
        self.name = normalized
        self.version += 1
        self.updated_at = now
        self.__post_init__()


@dataclass(slots=True)
class OrganizationMembership:
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    status: OrganizationMembershipStatus
    version: int
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None
    suspended_at: datetime | None = None
    left_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.version <= 2_147_483_647:
            raise OrganizationValidationError("membership version is invalid")
        if self.created_at > self.updated_at:
            raise OrganizationValidationError("membership timestamps are invalid")
        if self.status is OrganizationMembershipStatus.ACTIVE and self.accepted_at is None:
            raise OrganizationValidationError("active membership requires acceptance")
        if self.status is OrganizationMembershipStatus.SUSPENDED and self.suspended_at is None:
            raise OrganizationValidationError("suspended membership requires timestamp")
        if self.status is OrganizationMembershipStatus.LEFT and self.left_at is None:
            raise OrganizationValidationError("left membership requires timestamp")

    @property
    def capabilities(self) -> frozenset[OrganizationCapability]:
        if self.status is not OrganizationMembershipStatus.ACTIVE:
            return frozenset()
        return ROLE_CAPABILITIES[self.role]

    def has(self, capability: OrganizationCapability) -> bool:
        return capability in self.capabilities

    def suspend(self, now: datetime) -> None:
        if self.role is OrganizationRole.OWNER:
            raise OrganizationValidationError("organization owner cannot be suspended")
        if self.status is not OrganizationMembershipStatus.ACTIVE:
            raise OrganizationValidationError("membership is not active")
        self.status = OrganizationMembershipStatus.SUSPENDED
        self.suspended_at = now
        self.version += 1
        self.updated_at = now
        self.__post_init__()


@dataclass(slots=True)
class OrganizationInvitation:
    id: UUID
    organization_id: UUID
    invited_email_normalized: str
    invited_email_digest: str
    role: OrganizationRole
    token_hash: str | None
    status: InvitationStatus
    invited_by_user_id: UUID
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime
    accepted_by_user_id: UUID | None = None
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 3 <= len(self.invited_email_normalized) <= 254:
            raise OrganizationValidationError("invitation email is invalid")
        if _HASH.fullmatch(self.invited_email_digest) is None:
            raise OrganizationValidationError("invitation email digest is invalid")
        if self.role is OrganizationRole.OWNER:
            raise OrganizationValidationError("owner role cannot be invited")
        if self.token_hash is not None and _HASH.fullmatch(self.token_hash) is None:
            raise OrganizationValidationError("invitation token hash is invalid")
        if not 1 <= self.version <= 2_147_483_647:
            raise OrganizationValidationError("invitation version is invalid")
        if self.created_at >= self.expires_at or self.created_at > self.updated_at:
            raise OrganizationValidationError("invitation timestamps are invalid")
        if self.status is InvitationStatus.PENDING and self.token_hash is None:
            raise OrganizationValidationError("pending invitation requires a token")
        accepted = self.accepted_by_user_id is not None or self.accepted_at is not None
        if self.status is InvitationStatus.ACCEPTED:
            if self.accepted_by_user_id is None or self.accepted_at is None:
                raise OrganizationValidationError("accepted invitation is incomplete")
        elif accepted:
            raise OrganizationValidationError("non-accepted invitation has acceptance data")
        if (self.status is InvitationStatus.REVOKED) != (self.revoked_at is not None):
            raise OrganizationValidationError("invitation revocation state is inconsistent")

    def mark_delivered(self, token_hash: str, now: datetime) -> None:
        if self.status is not InvitationStatus.PENDING_DELIVERY:
            raise OrganizationValidationError("invitation cannot be delivered")
        if _HASH.fullmatch(token_hash) is None:
            raise OrganizationValidationError("invitation token hash is invalid")
        self.token_hash = token_hash
        self.status = InvitationStatus.PENDING
        self.version += 1
        self.updated_at = now
        self.__post_init__()

    def accept(self, user_id: UUID, now: datetime) -> None:
        if self.status is not InvitationStatus.PENDING or self.expires_at <= now:
            raise OrganizationValidationError("invitation is unavailable")
        self.status = InvitationStatus.ACCEPTED
        self.accepted_by_user_id = user_id
        self.accepted_at = now
        self.version += 1
        self.updated_at = now
        self.__post_init__()

    def revoke(self, now: datetime) -> None:
        if self.status not in {
            InvitationStatus.PENDING_DELIVERY,
            InvitationStatus.PENDING,
            InvitationStatus.DELIVERY_DEAD_LETTERED,
        }:
            raise OrganizationValidationError("invitation cannot be revoked")
        self.status = InvitationStatus.REVOKED
        self.revoked_at = now
        self.version += 1
        self.updated_at = now
        self.__post_init__()


@dataclass(slots=True)
class OrganizationAccessGrant:
    id: UUID
    organization_id: UUID
    subject_user_id: UUID
    grantee_user_id: UUID
    purpose: GrantPurpose
    scope: GrantScope
    status: GrantStatus
    granted_by_user_id: UUID
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.subject_user_id == self.grantee_user_id:
            raise OrganizationValidationError("self grants are not allowed")
        if self.granted_by_user_id != self.subject_user_id:
            raise OrganizationValidationError("only the subject can create a grant")
        if self.created_at >= self.expires_at or self.created_at > self.updated_at:
            raise OrganizationValidationError("grant timestamps are invalid")
        if not 1 <= self.version <= 2_147_483_647:
            raise OrganizationValidationError("grant version is invalid")
        if (self.status is GrantStatus.REVOKED) != (self.revoked_at is not None):
            raise OrganizationValidationError("grant revocation state is inconsistent")

    def is_active(self, now: datetime) -> bool:
        return self.status is GrantStatus.ACTIVE and self.expires_at > now

    def revoke(self, now: datetime) -> None:
        if self.status is not GrantStatus.ACTIVE:
            raise OrganizationValidationError("grant is not active")
        self.status = GrantStatus.REVOKED
        self.revoked_at = now
        self.version += 1
        self.updated_at = now
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class OrganizationAuditEvent:
    id: UUID
    organization_id: UUID
    actor_user_id: UUID | None
    subject_user_id: UUID | None
    action: OrganizationAuditAction
    target_type: str
    target_id: UUID | None
    request_id: str
    trace_id: str
    occurred_at: datetime
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        _key(self.target_type, "audit target type")
        _bounded_text(self.request_id, "request id", 128)
        _bounded_text(self.trace_id, "trace id", 128)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(slots=True)
class OrganizationInvitationOutbox:
    id: UUID
    invitation_id: UUID
    organization_id: UUID
    trace_id: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    published_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        _bounded_text(self.trace_id, "trace id", 128)
        if not 0 <= self.attempts <= self.max_attempts <= 20:
            raise OrganizationValidationError("invitation outbox attempts are invalid")
        if (self.lease_token is None) != (self.lease_expires_at is None):
            raise OrganizationValidationError("invitation outbox lease is inconsistent")
        if self.published_at is not None and self.dead_lettered_at is not None:
            raise OrganizationValidationError("invitation outbox terminal state is invalid")


@dataclass(frozen=True, slots=True)
class OrganizationIdempotencyRecord:
    id: UUID
    actor_user_id: UUID
    operation: str
    idempotency_key: str
    request_fingerprint: str
    resource_id: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        _key(self.operation, "idempotency operation")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise OrganizationValidationError("idempotency key is invalid")
        if _HASH.fullmatch(self.request_fingerprint) is None:
            raise OrganizationValidationError("idempotency fingerprint is invalid")
