"""Strict Phase 5 Job Match wire schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from rezumi_api.constants import SCORING_DISCLAIMER


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


class JobMatchSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
BasisPoints = Annotated[int, Field(ge=0, le=10_000)]
DisplayScore = Annotated[int, Field(ge=0, le=100)]
JobSourceKind = Literal["paste", "url", "manual", "greenhouse", "fake"]
WorkModel = Literal["remote", "hybrid", "onsite", "unknown"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship", "temporary", "unknown"]
RequirementType = Literal[
    "responsibility",
    "skill",
    "experience",
    "seniority",
    "education",
    "certification",
    "domain",
    "work_authorization",
    "travel",
    "compensation",
    "other",
]
RequirementImportance = Literal["mandatory", "preferred", "helpful"]
RequirementMatchState = Literal[
    "strong", "partial", "transferable", "unknown", "missing", "not_applicable"
]
ApplicationReadinessLabel = Literal["strong", "viable", "needs_work", "insufficient_data"]
PreferenceFit = Literal["strong", "acceptable", "unknown", "mismatch"]
TailoringEffort = Literal["low", "medium", "high"]
OpportunityPriorityLabel = Literal["high", "medium", "low", "defer"]


class PageResponse(JobMatchSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class JobCreateRequest(JobMatchSchema):
    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    work_model: WorkModel = "unknown"
    employment_type: EmploymentType = "unknown"
    compensation: str | None = Field(default=None, max_length=200)
    application_deadline: date | None = None
    source_kind: JobSourceKind = "paste"
    source_url: str | None = Field(default=None, max_length=2048)
    source_text: str = Field(min_length=20, max_length=50_000)
    target_role_id: UUID | None = None

    @field_validator("title", "company", "location", "compensation", "source_url")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class JobImportRequest(JobMatchSchema):
    url: HttpUrl
    target_role_id: UUID | None = None


class JobUpdateRequest(JobMatchSchema):
    title: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    work_model: WorkModel = "unknown"
    employment_type: EmploymentType = "unknown"
    compensation: str | None = Field(default=None, max_length=200)
    application_deadline: date | None = None
    source_text: str = Field(min_length=20, max_length=50_000)
    target_role_id: UUID | None = None

    @field_validator("title", "company", "location", "compensation")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value, required=value is not None) or None)

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class JobRequirementResponse(JobMatchSchema):
    id: UUID
    requirement_type: RequirementType
    text: str
    normalized_text: str
    importance: RequirementImportance
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=1)
    confidence_basis_points: BasisPoints
    order: int = Field(ge=0)


class JobResponse(JobMatchSchema):
    id: UUID
    title: str
    company: str | None
    location: str | None
    work_model: WorkModel
    employment_type: EmploymentType
    compensation: str | None
    application_deadline: date | None
    source_kind: JobSourceKind
    source_url: str | None
    target_role_id: UUID | None
    target_role_title: str | None
    version: PositiveVersion
    requirements: list[JobRequirementResponse] = Field(max_length=100)
    created_at: datetime
    updated_at: datetime


class JobPageResponse(JobMatchSchema):
    data: list[JobResponse] = Field(max_length=100)
    page: PageResponse


class JobCatalogListingResponse(JobMatchSchema):
    platform: str = Field(min_length=1, max_length=40)
    external_id: str = Field(min_length=1, max_length=2_048)
    title: str = Field(min_length=1, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=240)
    remote: bool | None = None
    application_url: str | None = Field(default=None, max_length=2_048)
    source_text: str = Field(max_length=4_000)
    posted_at: datetime | None = None


class JobCatalogSearchResponse(JobMatchSchema):
    target_role_titles: list[str] = Field(max_length=5)
    listings: list[JobCatalogListingResponse] = Field(max_length=200)
    matched_target_role: bool
    suggested_role_titles: list[str] = Field(default_factory=list, max_length=5)
    selected_role_titles: list[str] = Field(default_factory=list, max_length=20)


class JobCatalogSaveRequest(JobMatchSchema):
    platform: str = Field(min_length=1, max_length=40)
    external_id: str = Field(min_length=1, max_length=2_048)

    @field_validator("platform", "external_id")
    @classmethod
    def validate_catalog_save_ids(cls, value: str) -> str:
        return _safe_text(value, required=True)


class RolePreferenceRequest(JobMatchSchema):
    role_titles: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("role_titles")
    @classmethod
    def validate_role_titles(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for title in value:
            normalized = _safe_text(title, required=True)
            if len(normalized) > 200:
                raise ValueError("role title must be 200 characters or fewer")
            if normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


class RolePreferenceResponse(JobMatchSchema):
    role_titles: list[str] = Field(default_factory=list, max_length=20)


class JobCatalogBrowseResponse(JobMatchSchema):
    listings: list[JobCatalogListingResponse] = Field(max_length=100)
    has_more: bool
    next_offset: int = Field(ge=0)
    total_count: int = Field(ge=0)


class JobMatchComponentResponse(JobMatchSchema):
    dimension: str
    weight_basis_points: BasisPoints
    score_basis_points: BasisPoints
    contribution_basis_points: BasisPoints
    explanation: str


class RequirementEvidenceResponse(JobMatchSchema):
    id: UUID
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    relevance_basis_points: BasisPoints
    rationale: str


class RequirementMatchResponse(JobMatchSchema):
    id: UUID
    requirement_id: UUID
    requirement_text: str
    requirement_type: RequirementType
    importance: RequirementImportance
    match_state: RequirementMatchState
    score_basis_points: BasisPoints
    explanation: str
    recommended_action: str
    hard_gap: bool
    evidence: list[RequirementEvidenceResponse] = Field(max_length=20)


class JobMatchAnalysisResponse(JobMatchSchema):
    id: UUID
    job: JobResponse
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    raw_score_basis_points: BasisPoints | None
    display_score: DisplayScore | None
    readiness_label: ApplicationReadinessLabel
    hard_gap_count: int = Field(ge=0)
    insufficient_reason: str | None
    summary: str
    scoring_disclaimer: str = SCORING_DISCLAIMER
    components: list[JobMatchComponentResponse] = Field(max_length=20)
    requirements: list[RequirementMatchResponse] = Field(max_length=200)
    created_at: datetime


class RequirementMatchPageResponse(JobMatchSchema):
    data: list[RequirementMatchResponse] = Field(max_length=200)
    scoring_disclaimer: str = SCORING_DISCLAIMER


class OpportunityPriorityRequest(JobMatchSchema):
    analysis_id: UUID | None = None
    user_interest: int = Field(ge=1, le=5)
    career_direction_fit: int = Field(ge=1, le=5)
    compensation_fit: PreferenceFit = "unknown"
    location_fit: PreferenceFit = "unknown"
    work_model_fit: PreferenceFit = "unknown"
    tailoring_effort: TailoringEffort = "medium"
    existing_contacts: int = Field(default=0, ge=0, le=100)


class OpportunityPriorityResponse(JobMatchSchema):
    id: UUID
    job_id: UUID
    analysis_id: UUID
    priority_label: OpportunityPriorityLabel
    priority_score_basis_points: BasisPoints
    reasons_for: list[str] = Field(max_length=20)
    reconsiderations: list[str] = Field(max_length=20)
    blockers: list[str] = Field(max_length=20)
    next_action: str
    scoring_disclaimer: str = SCORING_DISCLAIMER
    created_at: datetime


class JobSyncFromSourceRequest(JobMatchSchema):
    platform: str = Field(min_length=1, max_length=40)
    query: str = Field(default="", max_length=200)
    target_role_id: UUID | None = None


class JobSyncFromSourceResponse(JobMatchSchema):
    created: list[JobResponse] = Field(max_length=100)
    skipped: int = Field(ge=0)
