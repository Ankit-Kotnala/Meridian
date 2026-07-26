"""Strict Phase 1 identity request and response schemas."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class IdentitySchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


class RegisterRequest(IdentitySchema):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value or len(value.encode("utf-8")) > 1024:
            raise ValueError("password contains unsupported content")
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display name is required")
        return normalized


class EmailRequest(IdentitySchema):
    email: EmailStr


class VerifyEmailRequest(IdentitySchema):
    token: str = Field(min_length=20, max_length=256)


class LoginRequest(IdentitySchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value or len(value.encode("utf-8")) > 1024:
            raise ValueError("password contains unsupported content")
        return value


class ResetPasswordRequest(IdentitySchema):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value or len(value.encode("utf-8")) > 1024:
            raise ValueError("password contains unsupported content")
        return value


class ChangePasswordRequest(IdentitySchema):
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is not None and ("\x00" in value or len(value.encode("utf-8")) > 1024):
            raise ValueError("password contains unsupported content")
        return value


class CsrfResponse(IdentitySchema):
    csrf_token: str


class GenericMessage(IdentitySchema):
    message: str


class VerificationResponse(IdentitySchema):
    status: Literal["verified"] = "verified"


WorkModel = Literal["onsite", "hybrid", "remote", "flexible"]
Seniority = Literal["entry", "mid", "senior", "lead", "executive"]
WritingStyle = Literal["concise", "balanced", "detailed"]


class MeResponse(IdentitySchema):
    id: UUID
    email: str
    display_name: str
    email_verified: bool
    locale: str
    timezone: str
    target_role: str | None
    preferred_location: str | None
    work_model: WorkModel | None
    seniority: Seniority | None
    industry: str | None
    language: str
    writing_style: WritingStyle
    version: int


class MeUpdateRequest(IdentitySchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: str | None = Field(default=None, min_length=2, max_length=35)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    target_role: str | None = Field(default=None, max_length=160)
    preferred_location: str | None = Field(default=None, max_length=160)
    work_model: WorkModel | None = None
    seniority: Seniority | None = None
    industry: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, min_length=2, max_length=35)
    writing_style: WritingStyle | None = None

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field_name in {
            "display_name",
            "locale",
            "timezone",
            "language",
            "writing_style",
        }:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display name is required")
        return normalized


class SessionInfo(IdentitySchema):
    id: UUID
    expires_at: datetime
    authenticated_at: datetime
    recent_authentication: bool


class AuthResponse(IdentitySchema):
    user: MeResponse
    session: SessionInfo


class SessionSummaryResponse(IdentitySchema):
    id: UUID
    current: bool
    auth_method: Literal["password", "google"]
    device_label: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


class SessionListResponse(IdentitySchema):
    data: list[SessionSummaryResponse]


class SecurityActivityResponse(IdentitySchema):
    id: UUID
    event_type: str
    outcome: Literal["success", "accepted", "denied", "failed"]
    occurred_at: datetime
    current_session: bool


class SecurityActivityListResponse(IdentitySchema):
    data: list[SecurityActivityResponse] = Field(max_length=100)


class SettingsCapabilitiesResponse(IdentitySchema):
    has_password: bool
    google_connected: bool
    google_oauth_available: bool
    reminder_preferences_available: Literal[True] = True
    scheduled_notification_delivery_available: Literal[False] = False
    account_export_available: bool
    account_deletion_available: bool
    billing_available: bool
    guest_resume_retention_hours: int = Field(ge=1, le=168)
    account_resume_retention: Literal["untilDeleted"] = "untilDeleted"


class AccountOperationResponse(IdentitySchema):
    id: UUID
    kind: Literal["export", "deletion"]
    status: Literal[
        "queued",
        "running",
        "retryWait",
        "succeeded",
        "blocked",
        "deadLettered",
        "expired",
    ]
    attempts: int = Field(ge=0, le=10)
    max_attempts: int = Field(ge=1, le=10)
    requested_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    blocked_reason: str | None = Field(default=None, max_length=80)
    artifact_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    artifact_size_bytes: int | None = Field(default=None, gt=0)
    artifact_expires_at: datetime | None = None


class AccountOperationCreatedResponse(AccountOperationResponse):
    operation_token: str = Field(min_length=80, max_length=128, repr=False)


class AccountExportDownloadResponse(IdentitySchema):
    download_url: str = Field(min_length=1, max_length=4096, repr=False)
    expires_in_seconds: int = Field(ge=30, le=300)


WireOnboardingStatus = Literal["inProgress", "completed"]
WireOnboardingStep = Literal["profile", "resume", "parsedReview", "preferences", "complete"]
WireHandoffStatus = Literal[
    "notStarted",
    "skipped",
    "processing",
    "reviewRequired",
    "reviewed",
    "analysisReady",
    "failed",
]


class OnboardingResponse(IdentitySchema):
    status: WireOnboardingStatus
    current_step: WireOnboardingStep
    resume_handoff: WireHandoffStatus
    parsed_review_handoff: WireHandoffStatus
    latest_resume_document_id: UUID | None
    resume_safe_error_code: str | None
    skipped_steps: list[WireOnboardingStep]
    version: int
    display_name: str
    target_role: str | None
    preferred_location: str | None
    work_model: WorkModel | None
    seniority: Seniority | None
    industry: str | None
    language: str
    writing_style: WritingStyle


class OnboardingUpdateRequest(IdentitySchema):
    current_step: WireOnboardingStep
    skipped_steps: list[WireOnboardingStep] = Field(default_factory=list, max_length=5)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    target_role: str | None = Field(default=None, max_length=160)
    preferred_location: str | None = Field(default=None, max_length=160)
    work_model: WorkModel | None = None
    seniority: Seniority | None = None
    industry: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, min_length=2, max_length=35)
    writing_style: WritingStyle | None = None

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if len(set(self.skipped_steps)) != len(self.skipped_steps):
            raise ValueError("skipped steps must be unique")
        for field_name in {"display_name", "language", "writing_style"}:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display name is required")
        return normalized


ConsentPurpose = Literal["modelTraining", "productAnalytics", "productEmail"]


class ConsentRequest(IdentitySchema):
    purpose: ConsentPurpose
    granted: bool


class ConsentResponse(IdentitySchema):
    purpose: ConsentPurpose
    granted: bool
    policy_version: str
    recorded_at: datetime


class ConsentListResponse(IdentitySchema):
    data: list[ConsentResponse]


class ProblemField(IdentitySchema):
    field: str
    code: str
    message: str


class ProblemResponse(IdentitySchema):
    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str
    request_id: str
    errors: list[ProblemField] = Field(default_factory=list)
