"""Transport-neutral commands and results for identity use cases."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from careeros.modules.identity.domain import (
    AuthenticatedPrincipal,
    AuthMethod,
    ConsentDecision,
    ObservedResumeStatus,
    OnboardingStatus,
    OnboardingStep,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    trace_id: str
    device_label: str
    source_key: str = "unknown"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    id: UUID
    encoded: str
    digest: bytes


@dataclass(frozen=True, slots=True)
class IssuedSession:
    principal: AuthenticatedPrincipal
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    email: str
    display_name: str
    email_verified: bool
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


@dataclass(frozen=True, slots=True)
class SessionSummary:
    id: UUID
    current: bool
    auth_method: AuthMethod
    device_label: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OnboardingView:
    status: OnboardingStatus
    current_step: OnboardingStep
    resume_handoff: ObservedResumeStatus
    parsed_review_handoff: ObservedResumeStatus
    latest_resume_document_id: UUID | None
    resume_safe_error_code: str | None
    skipped_steps: tuple[OnboardingStep, ...]
    version: int
    display_name: str
    target_role: str | None
    preferred_location: str | None
    work_model: str | None
    seniority: str | None
    industry: str | None
    language: str
    writing_style: str


@dataclass(frozen=True, slots=True)
class OnboardingResumeObservation:
    """Owner-scoped Resume Health state; no document content crosses this boundary."""

    resume_status: ObservedResumeStatus
    parsed_review_status: ObservedResumeStatus
    document_id: UUID | None = None
    safe_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ConsentView:
    purpose: str
    decision: ConsentDecision
    policy_version: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AccountSecurityView:
    has_password: bool
    google_connected: bool


@dataclass(frozen=True, slots=True)
class SecurityActivityView:
    id: UUID
    event_type: str
    outcome: str
    occurred_at: datetime
    current_session: bool


@dataclass(frozen=True, slots=True)
class EmailMessage:
    recipient: str
    subject: str
    text_body: str
    html_body: str


@dataclass(frozen=True, slots=True)
class OAuthStart:
    authorization_url: str
    state: str


@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    subject: str
    email: str
    email_verified: bool
    display_name: str
    return_to: str
    link_user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class OAuthCompletion:
    session: IssuedSession
    return_to: str
