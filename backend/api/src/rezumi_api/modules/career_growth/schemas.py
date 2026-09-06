"""Strict wire schemas for Career Growth and deterministic Career Health."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _safe_text(value) or None


def _distinct_ids(value: list[UUID]) -> list[UUID]:
    if len(value) != len(set(value)):
        raise ValueError("evidenceIds must contain distinct values")
    return value


class CareerGrowthSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
BasisPoints = Annotated[int, Field(strict=True, ge=0, le=10_000)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GoalStatusValue = Literal["active", "paused", "completed", "cancelled"]
MilestoneStatusValue = Literal["pending", "in_progress", "completed", "cancelled"]
DevelopmentKindValue = Literal[
    "learning",
    "certification",
    "performance_review",
    "promotion",
    "internal_mobility",
    "annual_resume_refresh",
]
DevelopmentStatusValue = Literal[
    "planned",
    "in_progress",
    "paused",
    "completed",
    "cancelled",
]
ReviewCadenceValue = Literal["quarterly", "annual"]
ReviewVersionStatusValue = Literal["draft", "finalized"]
EvidenceTargetKindValue = Literal[
    "goal",
    "milestone",
    "development_item",
    "review_version",
]
CareerHealthStatusValue = Literal["complete", "insufficient_data"]
CareerHealthLabelValue = Literal[
    "well_maintained",
    "developing",
    "needs_attention",
    "insufficient_data",
]
CareerHealthDimensionValue = Literal[
    "evidence_currency",
    "goal_progress",
    "development_follow_through",
    "review_cadence",
    "readiness_maintenance",
]
FindingSeverityValue = Literal["information", "attention"]
PromotionReadinessStatusValue = Literal[
    "insufficient_evidence",
    "building",
    "review_ready",
]
PromotionCheckStatusValue = Literal["supported", "needs_evidence", "needs_action"]
CanonicalScoreDisclaimerValue = Literal[
    "Rezumi scores are internal readiness measurements. They are not scores provided by "
    "an employer or applicant tracking system and do not guarantee interviews or employment "
    "outcomes."
]
PromotionReadinessDisclaimerValue = Literal[
    "Promotion Readiness summarizes Rezumi preparation signals from current eligible "
    "evidence and owner-maintained records. It is not an employer decision, hiring "
    "probability, promotion guarantee, or assessment of job-market value."
]


class PageResponse(CareerGrowthSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class EvidenceLinkResponse(CareerGrowthSchema):
    id: UUID
    target_kind: EvidenceTargetKindValue
    target_id: UUID
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: PositiveVersion
    statement_sha256: Sha256Digest
    evidence_revised_at: datetime
    created_at: datetime
    support_status: Literal["current", "needs_review"]


class GoalMutationRequest(CareerGrowthSchema):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4_000)
    status: GoalStatusValue = "active"
    target_date: date | None = None
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        return _distinct_ids(value)


class GoalCreateRequest(GoalMutationRequest):
    pass


class GoalUpdateRequest(GoalMutationRequest):
    status: GoalStatusValue


class MilestoneMutationRequest(CareerGrowthSchema):
    title: str = Field(min_length=1, max_length=240)
    status: MilestoneStatusValue = "pending"
    target_date: date | None = None
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        return _distinct_ids(value)


class MilestoneCreateRequest(MilestoneMutationRequest):
    pass


class MilestoneUpdateRequest(MilestoneMutationRequest):
    status: MilestoneStatusValue


class DevelopmentItemMutationRequest(CareerGrowthSchema):
    kind: DevelopmentKindValue
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4_000)
    status: DevelopmentStatusValue = "planned"
    target_date: date | None = None
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        return _distinct_ids(value)


class DevelopmentItemCreateRequest(DevelopmentItemMutationRequest):
    pass


class DevelopmentItemFromGapCreateRequest(CareerGrowthSchema):
    gap_kind: str = Field(min_length=3, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    role_profile_id: UUID | None = None


class DevelopmentItemUpdateRequest(DevelopmentItemMutationRequest):
    status: DevelopmentStatusValue


class ReviewContentRequest(CareerGrowthSchema):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=8_000)
    achievements: str | None = Field(default=None, max_length=8_000)
    growth_areas: str | None = Field(default=None, max_length=8_000)
    next_focus: str | None = Field(default=None, max_length=8_000)

    @field_validator("title", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("achievements", "growth_areas", "next_focus")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class CareerReviewCreateRequest(CareerGrowthSchema):
    cadence: ReviewCadenceValue
    period_start: date
    period_end: date
    content: ReviewContentRequest
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        return _distinct_ids(value)

    @model_validator(mode="after")
    def validate_period(self) -> CareerReviewCreateRequest:
        if self.period_end < self.period_start:
            raise ValueError("periodEnd cannot precede periodStart")
        maximum_days = 120 if self.cadence == "quarterly" else 370
        if (self.period_end - self.period_start).days > maximum_days:
            raise ValueError(f"{self.cadence} review period is too long")
        return self


class CareerReviewReviseRequest(CareerGrowthSchema):
    content: ReviewContentRequest
    change_reason: str = Field(min_length=1, max_length=500)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("change_reason")
    @classmethod
    def validate_change_reason(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        return _distinct_ids(value)


class GoalMilestoneResponse(CareerGrowthSchema):
    id: UUID
    goal_id: UUID
    title: str
    status: MilestoneStatusValue
    target_date: date | None
    completed_at: datetime | None
    evidence_links: list[EvidenceLinkResponse] = Field(max_length=100)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class GoalResponse(CareerGrowthSchema):
    id: UUID
    title: str
    description: str | None
    status: GoalStatusValue
    target_date: date | None
    evidence_links: list[EvidenceLinkResponse] = Field(max_length=100)
    milestones: list[GoalMilestoneResponse] = Field(max_length=100)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class GoalSummaryResponse(CareerGrowthSchema):
    id: UUID
    title: str
    status: GoalStatusValue
    target_date: date | None
    milestone_count: int = Field(ge=0, le=2_000)
    evidence_link_count: int = Field(ge=0, le=100)
    evidence_needs_review_count: int = Field(ge=0, le=100)
    version: PositiveVersion
    updated_at: datetime


class GoalPageResponse(CareerGrowthSchema):
    data: list[GoalSummaryResponse] = Field(max_length=100)
    page: PageResponse


class DevelopmentItemResponse(CareerGrowthSchema):
    id: UUID
    kind: DevelopmentKindValue
    title: str
    description: str | None
    status: DevelopmentStatusValue
    target_date: date | None
    completed_at: datetime | None
    evidence_links: list[EvidenceLinkResponse] = Field(max_length=100)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class DevelopmentItemPageResponse(CareerGrowthSchema):
    data: list[DevelopmentItemResponse] = Field(max_length=100)
    page: PageResponse


class GrowthAchievementResponse(CareerGrowthSchema):
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: PositiveVersion
    title: str
    statement: str
    evidence_type: str
    strength: str
    revised_at: datetime
    skill_ids: list[UUID] = Field(max_length=1_000)


class GrowthSkillEvidenceResponse(CareerGrowthSchema):
    skill_id: UUID
    name: str
    category: str | None
    proficiency: str | None
    evidence_count: int = Field(ge=0, le=2_000)
    evidence_ids: list[UUID] = Field(max_length=25)
    latest_evidence_at: datetime | None


class PromotionReadinessCheckResponse(CareerGrowthSchema):
    code: str
    label: str
    status: PromotionCheckStatusValue
    explanation: str
    evidence_count: int = Field(ge=0, le=2_000_000)
    evidence_ids: list[UUID] = Field(max_length=25)


class PromotionReadinessResponse(CareerGrowthSchema):
    status: PromotionReadinessStatusValue
    generated_at: datetime
    checks: list[PromotionReadinessCheckResponse] = Field(min_length=6, max_length=6)
    disclaimer: PromotionReadinessDisclaimerValue


class CareerGrowthInsightsResponse(CareerGrowthSchema):
    achievements: list[GrowthAchievementResponse] = Field(max_length=200)
    skills: list[GrowthSkillEvidenceResponse] = Field(max_length=1_000)
    promotion_readiness: PromotionReadinessResponse
    annual_resume_refreshes: list[DevelopmentItemResponse] = Field(max_length=1_000)


class ReviewVersionResponse(CareerGrowthSchema):
    id: UUID
    review_id: UUID
    version_number: PositiveVersion
    status: ReviewVersionStatusValue
    title: str
    summary: str
    achievements: str | None
    growth_areas: str | None
    next_focus: str | None
    change_reason: str
    material_change: bool
    supersedes_version_id: UUID | None
    content_sha256: Sha256Digest
    evidence_links: list[EvidenceLinkResponse] = Field(max_length=100)
    created_at: datetime


class CareerReviewResponse(CareerGrowthSchema):
    id: UUID
    cadence: ReviewCadenceValue
    period_start: date
    period_end: date
    latest_version_id: UUID
    latest_version_number: PositiveVersion
    latest_status: ReviewVersionStatusValue
    current_version: ReviewVersionResponse
    history: list[ReviewVersionResponse] = Field(min_length=1, max_length=100)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class CareerReviewSummaryResponse(CareerGrowthSchema):
    id: UUID
    cadence: ReviewCadenceValue
    period_start: date
    period_end: date
    latest_version_id: UUID
    latest_version_number: PositiveVersion
    latest_status: ReviewVersionStatusValue
    current_title: str
    history_count: int = Field(ge=1, le=100)
    evidence_link_count: int = Field(ge=0, le=100)
    evidence_needs_review_count: int = Field(ge=0, le=100)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class CareerReviewPageResponse(CareerGrowthSchema):
    data: list[CareerReviewSummaryResponse] = Field(max_length=100)
    page: PageResponse


class CareerHealthComponentResponse(CareerGrowthSchema):
    id: UUID
    dimension: CareerHealthDimensionValue
    configured_weight_basis_points: BasisPoints
    applicable: bool
    score_basis_points: BasisPoints | None
    contribution_basis_points: BasisPoints | None
    explanation: str


class CareerHealthFindingResponse(CareerGrowthSchema):
    id: UUID
    code: str
    severity: FindingSeverityValue
    message: str


class CareerHealthResponse(CareerGrowthSchema):
    id: UUID
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    input_snapshot: dict[str, object]
    configuration_snapshot: dict[str, object]
    formula_snapshot: dict[str, object]
    snapshot_sha256: Sha256Digest
    status: CareerHealthStatusValue
    raw_score_basis_points: BasisPoints | None
    display_score: int | None = Field(default=None, ge=0, le=100)
    label: CareerHealthLabelValue
    applicable_component_count: int = Field(ge=0, le=5)
    applicable_weight_basis_points: BasisPoints
    insufficient_reason: str | None
    disclaimer: CanonicalScoreDisclaimerValue
    components: list[CareerHealthComponentResponse] = Field(max_length=5)
    findings: list[CareerHealthFindingResponse] = Field(max_length=20)
    created_at: datetime


class CareerHealthSummaryResponse(CareerGrowthSchema):
    id: UUID
    engine_version: str
    status: CareerHealthStatusValue
    raw_score_basis_points: BasisPoints | None
    display_score: int | None = Field(default=None, ge=0, le=100)
    label: CareerHealthLabelValue
    applicable_component_count: int = Field(ge=0, le=5)
    applicable_weight_basis_points: BasisPoints
    insufficient_reason: str | None
    disclaimer: CanonicalScoreDisclaimerValue
    finding_count: int = Field(ge=0, le=20)
    created_at: datetime


class CareerHealthPageResponse(CareerGrowthSchema):
    data: list[CareerHealthSummaryResponse] = Field(max_length=100)
    page: PageResponse


class SkillLibraryResourceResponse(CareerGrowthSchema):
    title: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=12, max_length=2_000)
    kind: str = Field(min_length=1, max_length=40)


class SkillLibraryNoteResponse(CareerGrowthSchema):
    title: str = Field(min_length=1, max_length=200)
    format: str = Field(min_length=1, max_length=40)
    file_name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=50_000)


class SkillLibraryContentsResponse(CareerGrowthSchema):
    free_courses: list[SkillLibraryResourceResponse] = Field(max_length=40)
    paid_courses: list[SkillLibraryResourceResponse] = Field(max_length=20)
    notes: list[SkillLibraryNoteResponse] = Field(max_length=10)


class RoadmapSkillResponse(CareerGrowthSchema):
    name: str
    why: str
    how_to_start: str
    already_demonstrated: bool
    library: SkillLibraryContentsResponse


class RoadmapStageResponse(CareerGrowthSchema):
    stage: str
    skills: list[RoadmapSkillResponse] = Field(max_length=50)


class RoleRoadmapResponse(CareerGrowthSchema):
    role_title: str
    stages: list[RoadmapStageResponse] = Field(max_length=20)


class SkillLibraryResponse(CareerGrowthSchema):
    skill_name: str
    why: str
    how_to_start: str
    library: SkillLibraryContentsResponse
    disclaimer: str = Field(min_length=1, max_length=500)


class ConfirmRoadmapRequest(CareerGrowthSchema):
    role_title: str = Field(min_length=1, max_length=300)
    included_skill_names: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("role_title")
    @classmethod
    def validate_role_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("included_skill_names")
    @classmethod
    def validate_skill_names(cls, value: list[str]) -> list[str]:
        cleaned = []
        for name in value:
            normalized = _safe_text(name, required=True)
            if len(normalized) > 200:
                raise ValueError("skill name must be 200 characters or fewer")
            if normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


class ConfirmRoadmapResponse(CareerGrowthSchema):
    created: list[DevelopmentItemResponse] = Field(max_length=100)
