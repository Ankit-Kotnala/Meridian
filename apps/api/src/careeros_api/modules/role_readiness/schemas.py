"""Strict Phase 4 Role Explorer and Role Readiness wire schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from careeros_api.constants import SCORING_DISCLAIMER


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


class RoleReadinessSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
BasisPoints = Annotated[int, Field(ge=0, le=10_000)]
DisplayScore = Annotated[int, Field(ge=0, le=100)]
RoleSeniority = Literal["entry", "mid", "senior", "lead", "executive"]
CompetencyDimension = Literal[
    "core_competency",
    "responsibility_alignment",
    "seniority_alignment",
    "leadership_evidence",
    "domain_knowledge",
    "technical_skills",
    "business_impact",
    "education_certification",
    "evidence_strength",
]
CompetencyImportance = Literal["required", "helpful"]
SkillMatchState = Literal[
    "demonstrated", "listed", "transferable", "adjacent", "missing", "unknown"
]
ReadinessLabel = Literal["strong", "developing", "needs_evidence", "insufficient_data"]


class PageResponse(RoleReadinessSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class TaxonomyResponse(RoleReadinessSchema):
    id: UUID
    version: str
    source_name: str
    source_license: str
    description: str
    published_at: datetime


class RoleCompetencyResponse(RoleReadinessSchema):
    id: UUID
    dimension: CompetencyDimension
    label: str
    description: str
    importance: CompetencyImportance
    skill_keywords: list[str] = Field(max_length=24)
    evidence_keywords: list[str] = Field(max_length=24)
    transferable_keywords: list[str] = Field(max_length=24)
    adjacent_keywords: list[str] = Field(max_length=24)
    order: int = Field(ge=0)


class RoleResponse(RoleReadinessSchema):
    id: UUID
    slug: str
    title: str
    seniority: RoleSeniority
    industry: str
    domain: str
    location_scope: str
    company_type: str | None
    description: str
    version: PositiveVersion
    taxonomy: TaxonomyResponse
    competencies: list[RoleCompetencyResponse] = Field(max_length=100)


class RolePageResponse(RoleReadinessSchema):
    data: list[RoleResponse] = Field(max_length=100)
    page: PageResponse


class SavedRoleCreateRequest(RoleReadinessSchema):
    role_id: UUID
    notes: str | None = Field(default=None, max_length=1_000)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)


class SavedRoleUpdateRequest(RoleReadinessSchema):
    notes: str | None = Field(max_length=1_000)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)


class SavedRoleResponse(RoleReadinessSchema):
    id: UUID
    role: RoleResponse
    notes: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class SavedRolePageResponse(RoleReadinessSchema):
    data: list[SavedRoleResponse] = Field(max_length=100)
    page: PageResponse


class RoleReadinessRequest(RoleReadinessSchema):
    role_id: UUID | None = None
    saved_role_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> Self:
        if (self.role_id is None) == (self.saved_role_id is None):
            raise ValueError("provide exactly one role or saved role")
        return self


class ComponentResponse(RoleReadinessSchema):
    dimension: CompetencyDimension
    weight_basis_points: BasisPoints
    score_basis_points: BasisPoints
    contribution_basis_points: BasisPoints
    explanation: str


class CompetencyEvidenceResponse(RoleReadinessSchema):
    id: UUID
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    relevance_basis_points: BasisPoints
    rationale: str


class CompetencyResultResponse(RoleReadinessSchema):
    id: UUID
    competency_id: UUID
    dimension: CompetencyDimension
    label: str
    importance: CompetencyImportance
    match_state: SkillMatchState
    score_basis_points: BasisPoints
    explanation: str
    gap_kind: str | None
    evidence: list[CompetencyEvidenceResponse] = Field(max_length=20)


class RoleReadinessResponse(RoleReadinessSchema):
    id: UUID
    role: RoleResponse
    saved_role_id: UUID | None
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    taxonomy_version: str
    raw_score_basis_points: BasisPoints | None
    display_score: DisplayScore | None
    readiness_label: ReadinessLabel
    insufficient_reason: str | None
    summary: str
    scoring_disclaimer: str = SCORING_DISCLAIMER
    components: list[ComponentResponse] = Field(max_length=20)
    competencies: list[CompetencyResultResponse] = Field(max_length=200)
    created_at: datetime


class RoleReadinessPageResponse(RoleReadinessSchema):
    data: list[RoleReadinessResponse] = Field(max_length=100)
    page: PageResponse


class RoleComparisonEntryResponse(RoleReadinessSchema):
    role: RoleResponse
    latest_analysis: RoleReadinessResponse | None
    required_gap_count: int = Field(ge=0)
    helpful_gap_count: int = Field(ge=0)
    demonstrated_count: int = Field(ge=0)
    strongest_evidence_count: int = Field(ge=0)


class RoleComparisonResponse(RoleReadinessSchema):
    entries: list[RoleComparisonEntryResponse] = Field(min_length=2, max_length=3)
    note: str
    scoring_disclaimer: str = SCORING_DISCLAIMER
