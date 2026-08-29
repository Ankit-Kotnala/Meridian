"""Strict Phase 8 Application Workspace wire schemas."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


def _safe_text(value: str, *, required: bool = False) -> str:
    normalized = value.strip()
    if required and not normalized:
        raise ValueError("a value is required")
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise ValueError("control characters are not accepted")
    return normalized


class ApplicationWorkspaceSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
ApplicationStageValue = Literal[
    "saved",
    "researching",
    "preparing",
    "ready_to_apply",
    "applied",
    "recruiter_screen",
    "interview",
    "assessment",
    "offer",
    "rejected",
    "withdrawn",
]
ReferralStatusValue = Literal["none", "needed", "requested", "referred"]
OutcomeStatusValue = Literal["none", "offer", "rejected", "withdrawn"]
ApplicationEventKindValue = Literal[
    "created",
    "stage_changed",
    "deadline_changed",
    "follow_up_changed",
    "note_added",
    "task_added",
    "task_completed",
    "pack_generated",
    "outcome_recorded",
    "resume_version_changed",
    "interview",
    "contact",
    "custom",
]
ManualApplicationEventKindValue = Literal["interview", "contact", "custom"]
ApplicationDocumentKindValue = Literal[
    "tailored_resume",
    "cover_letter",
    "professional_bio",
    "interest_answer",
    "fit_answer",
    "recruiter_message",
    "hiring_manager_message",
    "referral_request",
    "linkedin_connection_note",
    "follow_up_email",
    "interview_introduction",
    "achievement_summary",
    "assisted_apply_handoff",
]
ApplicationDocumentStatusValue = Literal["generated", "blocked", "deleted"]
ApplicationPackStatusValue = Literal["generated", "blocked"]
ConsistencyStatusValue = Literal["passed", "warning", "failed"]
ConsistencySeverityValue = Literal["warning", "blocking"]
CalendarItemKind = Literal["application_deadline", "follow_up", "task"]
RequirementImportanceValue = Literal["mandatory", "preferred", "helpful"]
EvidenceStrengthValue = Literal["supported", "confirmed", "verified"]


class PageResponse(ApplicationWorkspaceSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class ApplicationContactInput(ApplicationWorkspaceSchema):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    url: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("role", "email", "url")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @model_validator(mode="after")
    def validate_contact(self) -> ApplicationContactInput:
        if self.email is not None and (
            "@" not in self.email or self.email.startswith("@") or self.email.endswith("@")
        ):
            raise ValueError("email is invalid")
        if self.url is not None and not self.url.startswith(("https://", "http://")):
            raise ValueError("url must use HTTP(S)")
        return self


class ApplicationCreateRequest(ApplicationWorkspaceSchema):
    job_id: UUID
    resume_version_id: UUID
    stage: ApplicationStageValue = "saved"
    application_deadline: date | None = None
    follow_up_at: date | None = None
    contacts: list[ApplicationContactInput] = Field(default_factory=list, max_length=20)
    referral_status: ReferralStatusValue = "none"
    source: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=120)

    @field_validator("source", "industry")
    @classmethod
    def validate_optional_classification(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)


class ApplicationUpdateRequest(ApplicationWorkspaceSchema):
    resume_version_id: UUID | None = None
    resume_change_reason: str | None = Field(default=None, max_length=500)
    application_deadline: date | None = None
    follow_up_at: date | None = None
    contacts: list[ApplicationContactInput] | None = Field(default=None, max_length=20)
    referral_status: ReferralStatusValue | None = None
    outcome_status: OutcomeStatusValue | None = None
    rejection_reason: str | None = Field(default=None, max_length=500)
    offer_summary: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=120)

    @field_validator(
        "resume_change_reason",
        "rejection_reason",
        "offer_summary",
        "source",
        "industry",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @model_validator(mode="after")
    def validate_present_non_nullable_fields(self) -> ApplicationUpdateRequest:
        for field in ("resume_version_id", "referral_status", "outcome_status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ApplicationStageUpdateRequest(ApplicationWorkspaceSchema):
    stage: ApplicationStageValue
    outcome_status: OutcomeStatusValue | None = None
    rejection_reason: str | None = Field(default=None, max_length=500)
    offer_summary: str | None = Field(default=None, max_length=500)
    reopen_reason: str | None = Field(default=None, max_length=500)

    @field_validator("rejection_reason", "offer_summary", "reopen_reason")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @model_validator(mode="after")
    def validate_outcome(self) -> ApplicationStageUpdateRequest:
        if "outcome_status" in self.model_fields_set and self.outcome_status is None:
            raise ValueError("outcome_status cannot be null")
        return self


class ApplicationTaskCreateRequest(ApplicationWorkspaceSchema):
    title: str = Field(min_length=1, max_length=200)
    due_at: date | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ApplicationTaskUpdateRequest(ApplicationWorkspaceSchema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_at: date | None = None
    completed: bool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_update(self) -> ApplicationTaskUpdateRequest:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        if "completed" in self.model_fields_set and self.completed is None:
            raise ValueError("completed cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ApplicationNoteCreateRequest(ApplicationWorkspaceSchema):
    body: str = Field(min_length=1, max_length=2_000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ApplicationEventCreateRequest(ApplicationWorkspaceSchema):
    event_kind: ManualApplicationEventKindValue
    occurred_at: datetime | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1_000)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("occurredAt must include a UTC offset")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if re.fullmatch(r"[a-z0-9_]{3,80}", key) is None:
                raise ValueError("metadata keys must use lowercase snake_case")
            if len(item) > 200:
                raise ValueError("metadata values must not exceed 200 characters")
            _safe_text(item)
        return value


class ApplicationPackCreateRequest(ApplicationWorkspaceSchema):
    include_kinds: list[ApplicationDocumentKindValue] = Field(default_factory=list, max_length=12)

    @field_validator("include_kinds")
    @classmethod
    def validate_unique_kinds(
        cls, value: list[ApplicationDocumentKindValue]
    ) -> list[ApplicationDocumentKindValue]:
        if len(value) != len(set(value)):
            raise ValueError("includeKinds must not contain duplicates")
        return value


class ApplicationContactResponse(ApplicationWorkspaceSchema):
    name: str
    role: str | None
    email: str | None
    url: str | None


class ApplicationClaimEvidenceLinkResponse(ApplicationWorkspaceSchema):
    evidence_id: UUID
    evidence_revision_id: UUID


class ApplicationClaimResponse(ApplicationWorkspaceSchema):
    id: UUID
    text: str
    evidence_links: list[ApplicationClaimEvidenceLinkResponse] = Field(max_length=20)
    requirement_ids: list[UUID] = Field(max_length=100)


class ApplicationRequirementResponse(ApplicationWorkspaceSchema):
    id: UUID
    requirement_type: str
    importance: RequirementImportanceValue
    text: str
    source_start: int = Field(ge=0)
    source_end: int = Field(gt=0)


class ApplicationEvidencePinResponse(ApplicationWorkspaceSchema):
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: PositiveVersion
    statement: str
    statement_sha256: str = Field(min_length=64, max_length=64)
    strength: EvidenceStrengthValue
    has_numeric_claim: bool


class ApplicationTaskResponse(ApplicationWorkspaceSchema):
    id: UUID
    application_id: UUID
    title: str
    due_at: date | None
    completed_at: datetime | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ApplicationNoteResponse(ApplicationWorkspaceSchema):
    id: UUID
    application_id: UUID
    body: str
    created_at: datetime


class ApplicationEventResponse(ApplicationWorkspaceSchema):
    id: UUID
    application_id: UUID
    event_kind: ApplicationEventKindValue
    occurred_at: datetime
    title: str
    description: str | None
    metadata: dict[str, str]
    created_at: datetime


class ConsistencyFindingResponse(ApplicationWorkspaceSchema):
    code: str
    severity: ConsistencySeverityValue
    message: str
    claim_id: UUID | None


class ApplicationDocumentResponse(ApplicationWorkspaceSchema):
    id: UUID
    application_id: UUID
    pack_id: UUID
    kind: ApplicationDocumentKindValue
    title: str
    body: str
    source_evidence_ids: list[UUID] = Field(max_length=200)
    source_requirement_ids: list[UUID] = Field(max_length=200)
    claims: list[ApplicationClaimResponse] = Field(max_length=288)
    status: ApplicationDocumentStatusValue
    consistency_status: ConsistencyStatusValue
    consistency_findings: list[ConsistencyFindingResponse] = Field(max_length=1_000)
    content_sha256: str = Field(min_length=64, max_length=64)
    created_at: datetime
    deleted_at: datetime | None


class ApplicationPackSummaryResponse(ApplicationWorkspaceSchema):
    id: UUID
    application_id: UUID
    job_id: UUID
    job_version: PositiveVersion
    resume_version_id: UUID
    resume_version_number: PositiveVersion
    application_version: PositiveVersion
    evidence_revision_ids: list[UUID] = Field(max_length=200)
    requirement_ids: list[UUID] = Field(max_length=200)
    status: ApplicationPackStatusValue
    consistency_status: ConsistencyStatusValue
    consistency_findings: list[ConsistencyFindingResponse] = Field(max_length=1_000)
    created_at: datetime


class ApplicationPackResponse(ApplicationPackSummaryResponse):
    documents: list[ApplicationDocumentResponse] = Field(max_length=20)


class ApplicationConsistencyResponse(ApplicationWorkspaceSchema):
    pack_id: UUID
    status: ConsistencyStatusValue
    findings: list[ConsistencyFindingResponse] = Field(max_length=1_000)


class ApplicationSummaryResponse(ApplicationWorkspaceSchema):
    id: UUID
    job_id: UUID
    job_version: PositiveVersion
    job_title: str
    company: str | None
    location: str | None
    job_analysis_id: UUID | None
    resume_id: UUID
    resume_version_id: UUID
    resume_version_number: PositiveVersion
    resume_title: str
    source: str | None
    industry: str | None
    stage: ApplicationStageValue
    application_deadline: date | None
    follow_up_at: date | None
    referral_status: ReferralStatusValue
    outcome_status: OutcomeStatusValue
    rejection_reason: str | None
    offer_summary: str | None
    task_count: int = Field(ge=0)
    open_task_count: int = Field(ge=0)
    note_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    pack_count: int = Field(ge=0)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ApplicationResponse(ApplicationSummaryResponse):
    job_source_sha256: str = Field(min_length=64, max_length=64)
    job_requirements: list[ApplicationRequirementResponse] = Field(max_length=200)
    resume_evidence_ids: list[UUID] = Field(max_length=200)
    evidence_pins: list[ApplicationEvidencePinResponse] = Field(max_length=200)
    resume_claims: list[ApplicationClaimResponse] = Field(max_length=288)
    contacts: list[ApplicationContactResponse] = Field(max_length=20)


class ApplicationPageResponse(ApplicationWorkspaceSchema):
    data: list[ApplicationSummaryResponse] = Field(max_length=100)
    page: PageResponse


class ApplicationTaskPageResponse(ApplicationWorkspaceSchema):
    data: list[ApplicationTaskResponse] = Field(max_length=100)
    page: PageResponse


class ApplicationNotePageResponse(ApplicationWorkspaceSchema):
    data: list[ApplicationNoteResponse] = Field(max_length=100)
    page: PageResponse


class ApplicationEventPageResponse(ApplicationWorkspaceSchema):
    data: list[ApplicationEventResponse] = Field(max_length=100)
    page: PageResponse


class ApplicationPackPageResponse(ApplicationWorkspaceSchema):
    data: list[ApplicationPackSummaryResponse] = Field(max_length=100)
    page: PageResponse


class ApplicationCalendarItemResponse(ApplicationWorkspaceSchema):
    id: UUID
    kind: CalendarItemKind
    application_id: UUID
    title: str
    on_date: date
    completed: bool


class ApplicationCalendarResponse(ApplicationWorkspaceSchema):
    start: date
    end: date
    data: list[ApplicationCalendarItemResponse] = Field(max_length=1_000)


class ApplicationProfileLinkInput(ApplicationWorkspaceSchema):
    label: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=500)


class ApplicationProfileResponse(ApplicationWorkspaceSchema):
    id: UUID
    work_authorization: str | None = None
    notice_period_days: int | None = Field(default=None, ge=0, le=730)
    compensation_min: int | None = Field(default=None, ge=0)
    compensation_max: int | None = Field(default=None, ge=0)
    compensation_currency: str = Field(min_length=3, max_length=3)
    preferred_locations: list[str] = Field(default_factory=list, max_length=50)
    profile_links: list[ApplicationProfileLinkInput] = Field(default_factory=list, max_length=30)
    voluntary_disclosures: dict[str, str] = Field(default_factory=dict)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ApplicationProfileUpsertRequest(ApplicationWorkspaceSchema):
    work_authorization: str | None = Field(default=None, max_length=500)
    notice_period_days: int | None = Field(default=None, ge=0, le=730)
    compensation_min: int | None = Field(default=None, ge=0)
    compensation_max: int | None = Field(default=None, ge=0)
    compensation_currency: str = Field(default="USD", min_length=3, max_length=3)
    preferred_locations: list[str] = Field(default_factory=list, max_length=50)
    profile_links: list[ApplicationProfileLinkInput] = Field(default_factory=list, max_length=30)
    voluntary_disclosures: dict[str, str] = Field(default_factory=dict)
