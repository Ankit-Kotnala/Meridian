"""Framework-independent identity entities and policy enums."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class AuthMethod(StrEnum):
    PASSWORD = "password"  # noqa: S105 -- authentication method label, not a secret
    GOOGLE = "google"


class TokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105 -- token purpose label


class ConsentDecision(StrEnum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


class MembershipRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class OnboardingStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OnboardingStep(StrEnum):
    PROFILE = "profile"
    RESUME = "resume"
    PARSED_REVIEW = "parsed_review"
    PREFERENCES = "preferences"
    COMPLETE = "complete"


class HandoffStatus(StrEnum):
    NOT_STARTED = "not_started"
    SKIPPED = "skipped"


@dataclass(slots=True)
class User:
    id: UUID
    email_normalized: str
    password_hash: str | None
    status: UserStatus
    email_verified_at: datetime | None
    auth_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Profile:
    user_id: UUID
    display_name: str
    locale: str
    timezone: str
    target_role: str | None
    preferred_location: str | None
    work_model: str | None
    seniority: str | None
    industry: str | None
    language: str
    writing_style: str
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Session:
    id: UUID
    user_id: UUID
    access_token_hash: bytes
    csrf_token_hash: bytes
    auth_method: AuthMethod
    device_label: str
    created_at: datetime
    authenticated_at: datetime
    last_seen_at: datetime
    access_expires_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now


@dataclass(slots=True)
class RefreshToken:
    id: UUID
    session_id: UUID
    token_hash: bytes
    issued_at: datetime
    expires_at: datetime
    parent_token_id: UUID | None = None
    replaced_by_token_id: UUID | None = None
    used_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.used_at is None and self.revoked_at is None and self.expires_at > now


@dataclass(slots=True)
class OneTimeToken:
    id: UUID
    user_id: UUID
    purpose: TokenPurpose
    token_hash: bytes
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.consumed_at is None and self.expires_at > now


@dataclass(slots=True)
class OAuthAccount:
    id: UUID
    user_id: UUID
    provider: str
    provider_subject: str
    provider_email_normalized: str
    created_at: datetime
    last_login_at: datetime


@dataclass(slots=True)
class Organization:
    id: UUID
    name: str
    created_by_user_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class OrganizationMembership:
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ConsentEvent:
    id: UUID
    user_id: UUID
    purpose: str
    decision: ConsentDecision
    policy_version: str
    request_id: str
    trace_id: str
    recorded_at: datetime


@dataclass(slots=True)
class AuditEvent:
    id: UUID
    event_type: str
    outcome: str
    request_id: str
    trace_id: str
    occurred_at: datetime
    actor_user_id: UUID | None = None
    subject_user_id: UUID | None = None
    session_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OnboardingProgress:
    user_id: UUID
    status: OnboardingStatus
    current_step: OnboardingStep
    resume_handoff: HandoffStatus
    parsed_review_handoff: HandoffStatus
    skipped_steps: tuple[OnboardingStep, ...]
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    user_id: UUID
    session_id: UUID
    authenticated_at: datetime
    auth_method: AuthMethod
    organization_id: UUID | None = None
    capabilities: frozenset[str] = frozenset()

    def was_recently_authenticated(self, now: datetime, max_age_seconds: int) -> bool:
        return (now - self.authenticated_at).total_seconds() <= max_age_seconds
