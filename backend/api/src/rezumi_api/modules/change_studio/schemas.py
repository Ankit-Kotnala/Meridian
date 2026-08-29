"""Strict Phase 6 Change Studio wire schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rezumi_api.constants import SCORING_DISCLAIMER


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


_BIDI_CONTROLS = {
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def _safe_text(value: str, *, required: bool = False) -> str:
    normalized = value.strip()
    if required and not normalized:
        raise ValueError("a value is required")
    if "\x00" in normalized or any(
        (ord(character) < 32 and character not in {"\n", "\r", "\t"}) or character in _BIDI_CONTROLS
        for character in normalized
    ):
        raise ValueError("control characters are not accepted")
    return normalized


class ChangeStudioSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
BasisPoints = Annotated[int, Field(ge=0, le=10_000)]
ScoreDeltaBasisPoints = Annotated[int, Field(ge=-10_000, le=10_000)]
ChangeTargetKind = Literal["tailored_resume_bullet", "profile_summary"]
ChangeSetPurpose = Literal["job_tailoring"]
ChangeSetStatus = Literal["draft", "applied"]
ChangeOperationType = Literal["add_bullet", "replace_bullet", "replace_summary"]
ChangeOperationStatus = Literal["proposed", "accepted", "rejected", "edited", "blocked"]
GroundingStatus = Literal["grounded", "blocked", "needs_clarification"]
RiskLevel = Literal["low", "medium", "high"]
ClaimKind = Literal[
    "responsibility",
    "achievement",
    "metric_outcome",
    "skill",
    "credential",
    "experience",
    "other",
]
ValidationStatus = Literal["passed", "failed"]
ClarificationStatus = Literal["open", "answered", "dismissed"]
ProviderRunStatus = Literal["succeeded", "failed", "blocked"]
Tone = Literal["direct", "warm", "technical"]
SuggestionLength = Literal["concise", "standard"]


class ChangeSetCreateRequest(ChangeStudioSchema):
    analysis_id: UUID
    target_kind: ChangeTargetKind = "tailored_resume_bullet"
    tone: Tone = "direct"
    length: SuggestionLength = "standard"
    max_operations: int = Field(default=5, ge=1, le=8)


class OperationEditRequest(ChangeStudioSchema):
    after_text: str = Field(min_length=1, max_length=2_000)

    @field_validator("after_text")
    @classmethod
    def validate_after_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class OperationAlternativeRequest(ChangeStudioSchema):
    tone: Tone = "direct"
    length: SuggestionLength = "standard"
    preserve_terms: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("preserve_terms")
    @classmethod
    def validate_preserve_terms(cls, value: list[str]) -> list[str]:
        normalized = [_safe_text(item) for item in value]
        return [item for item in normalized if item]


class ClarificationAnswerRequest(ChangeStudioSchema):
    answer_text: str = Field(min_length=1, max_length=2_000)

    @field_validator("answer_text")
    @classmethod
    def validate_answer_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ChangeClaimResponse(ChangeStudioSchema):
    id: UUID
    claim_kind: ClaimKind
    text: str
    evidence_id: UUID
    evidence_revision_id: UUID | None
    evidence_revision_number: PositiveVersion | None
    evidence_statement_sha256: str | None = Field(min_length=64, max_length=64)
    evidence_title: str
    evidence_strength: str
    source_excerpt: str
    validation_status: ValidationStatus
    validation_codes: list[str] = Field(max_length=20)
    sort_order: int = Field(ge=0)
    created_at: datetime


class ChangeOperationResponse(ChangeStudioSchema):
    id: UUID
    operation_type: ChangeOperationType
    target_kind: ChangeTargetKind
    target_id: UUID
    before_text: str
    after_text: str
    reason: str
    status: ChangeOperationStatus
    risk: RiskLevel
    confidence_basis_points: BasisPoints
    requires_confirmation: bool
    grounding_status: GroundingStatus
    grounding_codes: list[str] = Field(max_length=40)
    expected_score_delta_basis_points: ScoreDeltaBasisPoints | None
    requirement_id: UUID | None
    requirement_text: str | None
    locked: bool
    sort_order: int = Field(ge=0)
    version: PositiveVersion
    claims: list[ChangeClaimResponse] = Field(max_length=20)
    created_at: datetime
    updated_at: datetime


class ClarifyingQuestionResponse(ChangeStudioSchema):
    id: UUID
    operation_id: UUID | None
    requirement_id: UUID | None
    evidence_id: UUID | None
    question: str
    reason: str
    status: ClarificationStatus
    answer_text: str | None
    answered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChangeSetVersionResponse(ChangeStudioSchema):
    id: UUID
    version_number: PositiveVersion
    parent_version_id: UUID | None
    created_by_operation_id: UUID | None
    title: str
    content: str
    operation_ids: list[UUID] = Field(max_length=100)
    created_at: datetime


class ProviderRunResponse(ChangeStudioSchema):
    id: UUID
    provider_name: str
    provider_model: str
    operation: str
    prompt_version: str
    policy_version: str
    schema_version: str
    grounding_version: str
    input_evidence_ids: list[UUID] = Field(max_length=100)
    input_requirement_ids: list[UUID] = Field(max_length=100)
    output_operation_count: int = Field(ge=0, le=100)
    status: ProviderRunStatus
    latency_ms: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    cost_micros: int | None = Field(default=None, ge=0)
    validation_codes: list[str] = Field(max_length=40)
    created_at: datetime


class ChangeSetResponse(ChangeStudioSchema):
    id: UUID
    purpose: ChangeSetPurpose
    target_kind: ChangeTargetKind
    status: ChangeSetStatus
    job_id: UUID | None
    analysis_id: UUID | None
    current_version_id: UUID | None
    current_version: ChangeSetVersionResponse | None
    provider_name: str
    provider_model: str
    prompt_version: str
    policy_version: str
    schema_version: str
    grounding_version: str
    version: PositiveVersion
    operations: list[ChangeOperationResponse] = Field(max_length=100)
    questions: list[ClarifyingQuestionResponse] = Field(max_length=100)
    versions: list[ChangeSetVersionResponse] = Field(max_length=100)
    provider_runs: list[ProviderRunResponse] = Field(max_length=20)
    scoring_disclaimer: str = SCORING_DISCLAIMER
    created_at: datetime
    updated_at: datetime
