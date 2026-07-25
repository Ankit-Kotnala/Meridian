"""Strict Phase 9 Interview Prep wire schemas."""

from __future__ import annotations

from datetime import datetime
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


class InterviewPrepSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
StoryStatusValue = Literal["draft", "ready", "archived"]
StoryOriginValue = Literal["user_authored", "generated"]
StoryFieldValue = Literal[
    "situation",
    "task",
    "action",
    "result",
    "personal_contribution",
    "metric_explanation",
]
DefenseStatusValue = Literal["defended", "partial", "undefended"]
InterviewSessionKindValue = Literal[
    "recruiter_screen",
    "behavioral",
    "technical",
    "hiring_manager",
    "panel",
    "other",
]
QuestionKindValue = Literal[
    "behavioral",
    "role_specific",
    "technical",
    "company",
    "follow_up",
    "custom",
]
SessionNoteKindValue = Literal["private_note", "reflection"]
RequirementImportanceValue = Literal["mandatory", "preferred", "helpful"]
EvidenceStrengthValue = Literal["supported", "confirmed", "verified"]
GroundingStatusValue = Literal["current", "needs_review", "unknown"]


class PageResponse(InterviewPrepSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class StoryClaimSelectionInput(InterviewPrepSchema):
    claim_id: UUID
    field_names: list[StoryFieldValue] = Field(min_length=1, max_length=6)

    @field_validator("field_names")
    @classmethod
    def validate_distinct_fields(cls, value: list[StoryFieldValue]) -> list[StoryFieldValue]:
        if len(value) != len(set(value)):
            raise ValueError("fieldNames must contain distinct values")
        return value


class StarStoryMutationRequest(InterviewPrepSchema):
    title: str = Field(min_length=1, max_length=200)
    situation: str = Field(min_length=1, max_length=2_000)
    task: str = Field(min_length=1, max_length=2_000)
    action: str = Field(min_length=1, max_length=3_000)
    result: str = Field(min_length=1, max_length=2_000)
    personal_contribution: str = Field(min_length=1, max_length=2_000)
    metric_explanation: str | None = Field(default=None, max_length=2_000)
    confidence: int = Field(strict=True, ge=1, le=5)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=12)
    status: StoryStatusValue = "draft"
    claim_selections: list[StoryClaimSelectionInput] = Field(
        default_factory=list,
        max_length=288,
    )

    @field_validator(
        "title",
        "situation",
        "task",
        "action",
        "result",
        "personal_contribution",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("metric_explanation")
    @classmethod
    def validate_metric_explanation(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @field_validator("follow_up_questions")
    @classmethod
    def validate_follow_up_questions(cls, value: list[str]) -> list[str]:
        normalized = [_safe_text(item, required=True) for item in value]
        if any(len(item) > 500 for item in normalized):
            raise ValueError("a follow-up question must not exceed 500 characters")
        if len(normalized) != len(set(normalized)):
            raise ValueError("followUpQuestions must contain distinct values")
        return normalized

    @field_validator("claim_selections")
    @classmethod
    def validate_distinct_claims(
        cls, value: list[StoryClaimSelectionInput]
    ) -> list[StoryClaimSelectionInput]:
        claim_ids = [item.claim_id for item in value]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claimSelections must contain distinct claim IDs")
        return value


class StarStoryCreateRequest(StarStoryMutationRequest):
    application_id: UUID


class StarStoryUpdateRequest(StarStoryMutationRequest):
    pass


class InterviewSessionMutationRequest(InterviewPrepSchema):
    title: str = Field(min_length=1, max_length=200)
    kind: InterviewSessionKindValue
    scheduled_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("scheduledAt must include a UTC offset")
        return value


class InterviewSessionCreateRequest(InterviewSessionMutationRequest):
    application_id: UUID


class InterviewSessionUpdateRequest(InterviewSessionMutationRequest):
    pass


class InterviewQuestionCreateRequest(InterviewPrepSchema):
    prompt: str = Field(min_length=1, max_length=1_000)
    kind: QuestionKindValue = "custom"
    source_requirement_ids: list[UUID] = Field(default_factory=list, max_length=200)
    source_claim_ids: list[UUID] = Field(default_factory=list, max_length=288)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_distinct_sources(self) -> InterviewQuestionCreateRequest:
        if len(self.source_requirement_ids) != len(set(self.source_requirement_ids)):
            raise ValueError("sourceRequirementIds must contain distinct values")
        if len(self.source_claim_ids) != len(set(self.source_claim_ids)):
            raise ValueError("sourceClaimIds must contain distinct values")
        return self


class InterviewSessionNoteRequest(InterviewPrepSchema):
    kind: SessionNoteKindValue
    body: str = Field(min_length=1, max_length=8_000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return _safe_text(value, required=True)


class FollowUpDraftGenerateRequest(InterviewPrepSchema):
    source_claim_ids: list[UUID] = Field(min_length=1, max_length=288)

    @field_validator("source_claim_ids")
    @classmethod
    def validate_distinct_claims(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("sourceClaimIds must contain distinct values")
        return value


class EvidenceRevisionPinResponse(InterviewPrepSchema):
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: PositiveVersion
    statement: str
    statement_sha256: Sha256Digest
    strength: EvidenceStrengthValue
    has_numeric_claim: bool


class StoryClaimPinResponse(InterviewPrepSchema):
    source_claim_id: UUID
    claim_text: str
    claim_sha256: Sha256Digest
    strong: bool
    field_names: list[StoryFieldValue] = Field(min_length=1, max_length=6)
    evidence_pins: list[EvidenceRevisionPinResponse] = Field(min_length=1, max_length=200)


class StarStoryResponse(InterviewPrepSchema):
    id: UUID
    application_id: UUID
    title: str
    situation: str
    task: str
    action: str
    result: str
    personal_contribution: str
    metric_explanation: str | None
    confidence: int = Field(ge=1, le=5)
    follow_up_questions: list[str] = Field(max_length=12)
    status: StoryStatusValue
    origin: StoryOriginValue
    claim_pins: list[StoryClaimPinResponse] = Field(max_length=288)
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class StarStorySummaryResponse(InterviewPrepSchema):
    id: UUID
    application_id: UUID
    title: str
    confidence: int = Field(ge=1, le=5)
    status: StoryStatusValue
    origin: StoryOriginValue
    claim_count: int = Field(ge=0, le=288)
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class StarStoryPageResponse(InterviewPrepSchema):
    data: list[StarStorySummaryResponse] = Field(max_length=100)
    page: PageResponse


class DefenseMapEntryResponse(InterviewPrepSchema):
    claim_id: UUID
    claim_text: str
    strong: bool
    status: DefenseStatusValue
    story_ids: list[UUID] = Field(max_length=500)
    evidence_revision_ids: list[UUID] = Field(max_length=200)
    warning: str | None


class DefenseMapResponse(InterviewPrepSchema):
    application_id: UUID
    entries: list[DefenseMapEntryResponse] = Field(max_length=288)
    defended_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    undefended_count: int = Field(ge=0)
    strong_claim_warning_count: int = Field(ge=0)


class SessionContextClaimResponse(InterviewPrepSchema):
    source_claim_id: UUID
    text: str
    text_sha256: Sha256Digest
    strong: bool
    requirement_ids: list[UUID] = Field(max_length=200)
    evidence_pins: list[EvidenceRevisionPinResponse] = Field(min_length=1, max_length=200)


class SessionContextRequirementResponse(InterviewPrepSchema):
    requirement_id: UUID
    text: str
    importance: RequirementImportanceValue


class SessionContextResponse(InterviewPrepSchema):
    application_id: UUID
    job_id: UUID
    job_version: PositiveVersion
    job_title: str
    company: str | None
    resume_version_id: UUID
    resume_version_number: PositiveVersion
    claims: list[SessionContextClaimResponse] = Field(max_length=288)
    requirements: list[SessionContextRequirementResponse] = Field(max_length=200)
    snapshot_sha256: Sha256Digest


class InterviewSessionResponse(InterviewPrepSchema):
    id: UUID
    application_id: UUID
    title: str
    kind: InterviewSessionKindValue
    scheduled_at: datetime | None
    context: SessionContextResponse
    question_count: int = Field(ge=0)
    note_count: int = Field(ge=0)
    follow_up_draft_count: int = Field(ge=0)
    question_bank_generated: bool
    question_bank_id: UUID | None
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class InterviewSessionSummaryResponse(InterviewPrepSchema):
    id: UUID
    application_id: UUID
    title: str
    kind: InterviewSessionKindValue
    scheduled_at: datetime | None
    job_title: str
    company: str | None
    question_count: int = Field(ge=0)
    note_count: int = Field(ge=0)
    follow_up_draft_count: int = Field(ge=0)
    question_bank_generated: bool
    question_bank_id: UUID | None
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class InterviewSessionPageResponse(InterviewPrepSchema):
    data: list[InterviewSessionSummaryResponse] = Field(max_length=100)
    page: PageResponse


class InterviewQuestionResponse(InterviewPrepSchema):
    id: UUID
    session_id: UUID
    ordinal: PositiveVersion
    prompt: str
    kind: QuestionKindValue
    source_requirement_ids: list[UUID] = Field(max_length=200)
    source_claim_ids: list[UUID] = Field(max_length=288)
    generated: bool
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    created_at: datetime


class InterviewQuestionSummaryResponse(InterviewPrepSchema):
    id: UUID
    session_id: UUID
    ordinal: PositiveVersion
    prompt: str
    kind: QuestionKindValue
    generated: bool
    source_requirement_count: int = Field(ge=0, le=200)
    source_claim_count: int = Field(ge=0, le=288)
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    created_at: datetime


class InterviewQuestionPageResponse(InterviewPrepSchema):
    data: list[InterviewQuestionSummaryResponse] = Field(max_length=100)
    page: PageResponse


class GeneratedQuestionBankResponse(InterviewPrepSchema):
    data: list[InterviewQuestionResponse] = Field(max_length=20)


class InterviewSessionNoteResponse(InterviewPrepSchema):
    id: UUID
    session_id: UUID
    kind: SessionNoteKindValue
    body: str
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class InterviewSessionNotePageResponse(InterviewPrepSchema):
    data: list[InterviewSessionNoteResponse] = Field(max_length=100)
    page: PageResponse


class FollowUpDraftResponse(InterviewPrepSchema):
    id: UUID
    session_id: UUID
    subject: str
    body: str
    source_claims: list[SessionContextClaimResponse] = Field(min_length=1, max_length=288)
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    content_sha256: Sha256Digest
    created_at: datetime


class FollowUpDraftSummaryResponse(InterviewPrepSchema):
    id: UUID
    session_id: UUID
    subject: str
    body: str
    source_claim_count: int = Field(ge=1, le=288)
    grounding_status: GroundingStatusValue
    grounding_warning: str | None
    content_sha256: Sha256Digest
    created_at: datetime


class FollowUpDraftPageResponse(InterviewPrepSchema):
    data: list[FollowUpDraftSummaryResponse] = Field(max_length=100)
    page: PageResponse
