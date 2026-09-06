"""Transport-neutral Career Growth commands and views."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from rezumi.modules.career_growth.domain import (
    CareerGoal,
    CareerGrowthEvidenceLink,
    CareerHealthAnalysis,
    CareerHealthComponent,
    CareerHealthFinding,
    CareerHealthLabel,
    CareerHealthStatus,
    CareerReview,
    CareerReviewVersion,
    DevelopmentItem,
    DevelopmentKind,
    DevelopmentStatus,
    GoalMilestone,
    GoalStatus,
    GrowthEvidenceSnapshot,
    MilestoneStatus,
    PromotionCheckStatus,
    PromotionReadinessStatus,
    ReviewCadence,
)
from rezumi.modules.career_growth.domain.errors import CareerGrowthValidationError

from .role_roadmap_ports import SkillLibrary

MAX_CURSOR_OFFSET = 10_000


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class PageCursor:
    offset: int

    @classmethod
    def decode(cls, value: str | None) -> PageCursor | None:
        if value is None:
            return None
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii") + b"===")
            payload = json.loads(raw)
            offset = payload["offset"]
        except (
            UnicodeEncodeError,
            binascii.Error,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise CareerGrowthValidationError("cursor is invalid") from exc
        if not isinstance(offset, int) or not 0 <= offset <= MAX_CURSOR_OFFSET:
            raise CareerGrowthValidationError("cursor is invalid")
        return cls(offset=offset)

    def encode(self) -> str:
        if not 0 <= self.offset <= MAX_CURSOR_OFFSET:
            raise CareerGrowthValidationError("cursor is invalid")
        payload = json.dumps({"offset": self.offset}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    has_more: bool
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class PagedResult[T]:
    data: tuple[T, ...]
    page: Page


def page_result[T](items: list[T], *, cursor: PageCursor | None, limit: int) -> PagedResult[T]:
    has_more = len(items) > limit
    visible = tuple(items[:limit])
    offset = cursor.offset if cursor is not None else 0
    next_offset = offset + limit
    if has_more and next_offset > MAX_CURSOR_OFFSET:
        raise CareerGrowthValidationError("collection exceeds the supported cursor window")
    return PagedResult(
        data=visible,
        page=Page(
            limit=limit,
            has_more=has_more,
            next_cursor=PageCursor(next_offset).encode() if has_more else None,
        ),
    )


@dataclass(frozen=True, slots=True)
class CreateGoal:
    title: str
    description: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    target_date: date | None = None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateGoal:
    title: str
    description: str | None
    status: GoalStatus
    target_date: date | None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateMilestone:
    title: str
    status: MilestoneStatus = MilestoneStatus.PENDING
    target_date: date | None = None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateMilestone:
    title: str
    status: MilestoneStatus
    target_date: date | None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateDevelopmentItem:
    kind: DevelopmentKind
    title: str
    description: str | None = None
    status: DevelopmentStatus = DevelopmentStatus.PLANNED
    target_date: date | None = None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateDevelopmentItemFromGap:
    gap_kind: str
    label: str
    role_profile_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateDevelopmentItem:
    kind: DevelopmentKind
    title: str
    description: str | None
    status: DevelopmentStatus
    target_date: date | None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewContent:
    title: str
    summary: str
    achievements: str | None = None
    growth_areas: str | None = None
    next_focus: str | None = None


@dataclass(frozen=True, slots=True)
class CreateCareerReview:
    cadence: ReviewCadence
    period_start: date
    period_end: date
    content: ReviewContent
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviseCareerReview:
    content: ReviewContent
    change_reason: str
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class GoalMilestoneView:
    milestone: GoalMilestone
    evidence_links: tuple[EvidenceLinkView, ...]


@dataclass(frozen=True, slots=True)
class GoalView:
    goal: CareerGoal
    evidence_links: tuple[EvidenceLinkView, ...]
    milestones: tuple[GoalMilestoneView, ...]


@dataclass(frozen=True, slots=True)
class DevelopmentItemView:
    item: DevelopmentItem
    evidence_links: tuple[EvidenceLinkView, ...]


@dataclass(frozen=True, slots=True)
class ReviewVersionView:
    version: CareerReviewVersion
    evidence_links: tuple[EvidenceLinkView, ...]


@dataclass(frozen=True, slots=True)
class CareerReviewView:
    review: CareerReview
    current_version: ReviewVersionView
    history: tuple[ReviewVersionView, ...]


@dataclass(frozen=True, slots=True)
class EvidenceLinkView:
    link: CareerGrowthEvidenceLink
    is_current: bool


@dataclass(frozen=True, slots=True)
class GoalSummaryView:
    goal: CareerGoal
    milestone_count: int
    evidence_link_count: int
    evidence_needs_review_count: int


@dataclass(frozen=True, slots=True)
class CareerReviewSummaryView:
    review: CareerReview
    current_title: str
    history_count: int
    evidence_link_count: int
    evidence_needs_review_count: int


@dataclass(frozen=True, slots=True)
class ReviewListMetadata:
    review_id: UUID
    current_version_id: UUID
    current_title: str
    history_count: int


@dataclass(frozen=True, slots=True)
class CareerHealthRecord:
    analysis: CareerHealthAnalysis
    components: tuple[CareerHealthComponent, ...]
    findings: tuple[CareerHealthFinding, ...]


@dataclass(frozen=True, slots=True)
class CareerHealthSummary:
    id: UUID
    engine_version: str
    status: CareerHealthStatus
    raw_score_basis_points: int | None
    display_score: int | None
    label: CareerHealthLabel
    applicable_component_count: int
    applicable_weight_basis_points: int
    insufficient_reason: str | None
    disclaimer: str
    finding_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GrowthAchievementSnapshot:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    title: str
    statement: str
    evidence_type: str
    strength: str
    revised_at: datetime
    skill_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class GrowthSkillSnapshot:
    skill_id: UUID
    name: str
    category: str | None
    proficiency: str | None
    evidence_count: int
    evidence_ids: tuple[UUID, ...]
    latest_evidence_at: datetime | None


@dataclass(frozen=True, slots=True)
class CareerGrowthInsightSource:
    achievements: tuple[GrowthAchievementSnapshot, ...]
    skills: tuple[GrowthSkillSnapshot, ...]
    eligible_evidence: tuple[GrowthEvidenceSnapshot, ...]


@dataclass(frozen=True, slots=True)
class PromotionReadinessCheck:
    code: str
    label: str
    status: PromotionCheckStatus
    explanation: str
    evidence_count: int = 0
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class PromotionReadinessReport:
    status: PromotionReadinessStatus
    generated_at: datetime
    checks: tuple[PromotionReadinessCheck, ...]
    disclaimer: str


@dataclass(frozen=True, slots=True)
class CareerGrowthInsights:
    achievements: tuple[GrowthAchievementSnapshot, ...]
    skills: tuple[GrowthSkillSnapshot, ...]
    promotion_readiness: PromotionReadinessReport
    annual_resume_refreshes: tuple[DevelopmentItemView, ...]


@dataclass(frozen=True, slots=True)
class RoadmapSkillView:
    name: str
    why: str
    how_to_start: str
    already_demonstrated: bool
    library: SkillLibrary


@dataclass(frozen=True, slots=True)
class RoadmapStageView:
    stage: str
    skills: tuple[RoadmapSkillView, ...]


@dataclass(frozen=True, slots=True)
class RoleRoadmapView:
    role_title: str
    stages: tuple[RoadmapStageView, ...]


@dataclass(frozen=True, slots=True)
class SkillLibraryView:
    skill_name: str
    why: str
    how_to_start: str
    library: SkillLibrary
    disclaimer: str


@dataclass(frozen=True, slots=True)
class ConfirmRoadmapSelection:
    role_title: str
    included_skill_names: tuple[str, ...]
