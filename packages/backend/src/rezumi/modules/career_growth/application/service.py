"""Owner-scoped Career Growth workflows and deterministic Career Health orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from rezumi.modules.career_growth.domain import (
    PROMOTION_READINESS_DISCLAIMER,
    CareerGoal,
    CareerGrowthAuditEvent,
    CareerGrowthConflict,
    CareerGrowthEvidenceLink,
    CareerGrowthIdempotencyConflict,
    CareerGrowthIdempotencyRecord,
    CareerGrowthNotFound,
    CareerGrowthQuotaExceeded,
    CareerGrowthValidationError,
    CareerGrowthVersionConflict,
    CareerHealthAnalysis,
    CareerHealthComponent,
    CareerHealthFinding,
    CareerHealthInput,
    CareerReview,
    CareerReviewVersion,
    DevelopmentHealthSignal,
    DevelopmentItem,
    DevelopmentKind,
    DevelopmentStatus,
    EvidenceTargetKind,
    GoalHealthSignal,
    GoalMilestone,
    GrowthAuditAction,
    GrowthEvidenceSnapshot,
    MilestoneStatus,
    PromotionCheckStatus,
    PromotionReadinessStatus,
    ReviewHealthSignal,
    ReviewVersionStatus,
    review_content_hash,
    score_career_health,
)

from .models import (
    CareerGrowthInsights,
    CareerHealthRecord,
    CareerHealthSummary,
    CareerReviewSummaryView,
    CareerReviewView,
    CreateCareerReview,
    CreateDevelopmentItem,
    CreateDevelopmentItemFromGap,
    CreateGoal,
    CreateMilestone,
    DevelopmentItemView,
    EvidenceLinkView,
    GoalMilestoneView,
    GoalSummaryView,
    GoalView,
    PageCursor,
    PagedResult,
    PromotionReadinessCheck,
    PromotionReadinessReport,
    RequestContext,
    ReviewContent,
    ReviewVersionView,
    ReviseCareerReview,
    UpdateDevelopmentItem,
    UpdateGoal,
    UpdateMilestone,
    page_result,
)
from .ports import (
    CareerGrowthSourceProvider,
    CareerGrowthUnitOfWork,
    CareerGrowthUnitOfWorkFactory,
    Clock,
    GapSnapshot,
    IdentifierFactory,
    RoleReadinessGapSource,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class CareerGrowthPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_goals: int = 500
    max_milestones: int = 2_000
    max_milestones_per_goal: int = 100
    max_development_items: int = 1_000
    max_reviews: int = 200
    max_versions_per_review: int = 100
    max_evidence_links_per_target: int = 100
    max_health_history: int = 2_000
    max_insight_achievements: int = 200
    max_insight_skills: int = 1_000
    max_insight_evidence_detail: int = 25

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("career growth page limits are invalid")
        values = (
            self.max_goals,
            self.max_milestones,
            self.max_milestones_per_goal,
            self.max_development_items,
            self.max_reviews,
            self.max_versions_per_review,
            self.max_evidence_links_per_target,
            self.max_health_history,
            self.max_insight_achievements,
            self.max_insight_skills,
            self.max_insight_evidence_detail,
        )
        if any(value < 1 or value > 10_000 for value in values):
            raise ValueError("career growth collection limits are invalid")
        if self.max_milestones_per_goal > self.max_milestones:
            raise ValueError("per-goal milestone limit cannot exceed the global limit")
        if self.max_insight_evidence_detail > 100:
            raise ValueError("career growth insight evidence detail cannot exceed 100")


class CareerGrowthService:
    """Phase 9 goals, development, review history, and Career Health use cases."""

    def __init__(
        self,
        *,
        unit_of_work: CareerGrowthUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        career_source: CareerGrowthSourceProvider,
        gap_source: RoleReadinessGapSource | None = None,
        policy: CareerGrowthPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._source = career_source
        self._gaps = gap_source
        self._policy = policy or CareerGrowthPolicy()

    async def create_goal(
        self,
        owner_user_id: UUID,
        command: CreateGoal,
        idempotency_key: str,
        context: RequestContext,
    ) -> GoalView:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint("create_goal", _goal_payload(command))
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, "create_goal", fingerprint
            )
            if replay is not None:
                return await self._goal_view(uow, owner_user_id, replay)
            existing = await uow.list_goals(owner_user_id, None, self._policy.max_goals + 1)
            if len(existing) >= self._policy.max_goals:
                raise CareerGrowthQuotaExceeded("career goal limit reached")
            goal = CareerGoal(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                title=command.title,
                description=command.description,
                status=command.status,
                target_date=command.target_date,
                version=1,
                created_at=now,
                updated_at=now,
            )
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.GOAL,
                goal.id,
                command.evidence_ids,
                now,
            )
            await uow.add_goal(goal)
            await uow.replace_evidence_links(owner_user_id, EvidenceTargetKind.GOAL, goal.id, links)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "create_goal",
                goal.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.GOAL_CREATED,
                    "career_goal",
                    goal.id,
                    context,
                    now,
                    goal_id=goal.id,
                    status=goal.status.value,
                    version=goal.version,
                )
            )
            await uow.commit()
            return GoalView(
                goal=goal,
                evidence_links=_known_current_link_views(links),
                milestones=(),
            )

    async def update_goal(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        expected_version: int,
        command: UpdateGoal,
        context: RequestContext,
    ) -> GoalView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            goal = await uow.get_goal(owner_user_id, goal_id, for_update=True)
            if goal is None:
                raise CareerGrowthNotFound
            self._version(goal.version, expected_version)
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.GOAL,
                goal.id,
                command.evidence_ids,
                now,
            )
            goal.edit(
                title=command.title,
                description=command.description,
                status=command.status,
                target_date=command.target_date,
                now=now,
            )
            await uow.save_goal(goal)
            await uow.replace_evidence_links(owner_user_id, EvidenceTargetKind.GOAL, goal.id, links)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.GOAL_UPDATED,
                    "career_goal",
                    goal.id,
                    context,
                    now,
                    goal_id=goal.id,
                    status=goal.status.value,
                    version=goal.version,
                )
            )
            result = await self._goal_view(uow, owner_user_id, goal.id)
            await uow.commit()
            return result

    async def get_goal(self, owner_user_id: UUID, goal_id: UUID) -> GoalView:
        async with self._uow() as uow:
            return await self._goal_view(uow, owner_user_id, goal_id)

    async def list_goals(
        self, owner_user_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> PagedResult[GoalSummaryView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            goals = await uow.list_goals(owner_user_id, after, page_size + 1)
            goal_ids = tuple(goal.id for goal in goals)
            milestone_counts = await uow.count_milestones_by_goal(
                owner_user_id,
                goal_ids,
            )
            links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.GOAL,
                goal_ids,
            )
        grouped = _links_by_target(links)
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        summaries = [
            GoalSummaryView(
                goal=goal,
                milestone_count=milestone_counts.get(goal.id, 0),
                evidence_link_count=len(grouped[goal.id]),
                evidence_needs_review_count=sum(
                    not _evidence_link_is_current(link, current_by_id) for link in grouped[goal.id]
                ),
            )
            for goal in goals
        ]
        return page_result(summaries, cursor=after, limit=page_size)

    async def delete_goal(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            goal = await uow.get_goal(owner_user_id, goal_id, for_update=True)
            if goal is None:
                raise CareerGrowthNotFound
            self._version(goal.version, expected_version)
            await uow.delete_goal(owner_user_id, goal.id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.GOAL_DELETED,
                    "career_goal",
                    goal.id,
                    context,
                    now,
                    goal_id=goal.id,
                    version=goal.version,
                )
            )
            await uow.commit()

    async def create_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        command: CreateMilestone,
        idempotency_key: str,
        context: RequestContext,
    ) -> GoalMilestoneView:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint(
            "create_milestone", {"goalId": goal_id, **_milestone_payload(command)}
        )
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                "create_milestone",
                fingerprint,
            )
            if replay is not None:
                return await self._milestone_view(uow, owner_user_id, goal_id, replay)
            goal = await uow.get_goal(owner_user_id, goal_id)
            if goal is None:
                raise CareerGrowthNotFound
            current = await uow.list_milestones(owner_user_id, (goal.id,))
            if len(current) >= self._policy.max_milestones_per_goal:
                raise CareerGrowthQuotaExceeded("goal milestone limit reached")
            if await uow.count_milestones(owner_user_id) >= self._policy.max_milestones:
                raise CareerGrowthQuotaExceeded("career milestone limit reached")
            milestone = GoalMilestone(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                goal_id=goal.id,
                title=command.title,
                status=command.status,
                target_date=command.target_date,
                completed_at=now if command.status is MilestoneStatus.COMPLETED else None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.MILESTONE,
                milestone.id,
                command.evidence_ids,
                now,
            )
            await uow.add_milestone(milestone)
            await uow.replace_evidence_links(
                owner_user_id, EvidenceTargetKind.MILESTONE, milestone.id, links
            )
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "create_milestone",
                milestone.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.MILESTONE_CREATED,
                    "goal_milestone",
                    milestone.id,
                    context,
                    now,
                    goal_id=goal.id,
                    milestone_id=milestone.id,
                    status=milestone.status.value,
                    version=milestone.version,
                )
            )
            await uow.commit()
            return GoalMilestoneView(
                milestone=milestone,
                evidence_links=_known_current_link_views(links),
            )

    async def update_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
        expected_version: int,
        command: UpdateMilestone,
        context: RequestContext,
    ) -> GoalMilestoneView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            milestone = await uow.get_milestone(
                owner_user_id, goal_id, milestone_id, for_update=True
            )
            if milestone is None:
                raise CareerGrowthNotFound
            self._version(milestone.version, expected_version)
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.MILESTONE,
                milestone.id,
                command.evidence_ids,
                now,
            )
            milestone.edit(
                title=command.title,
                status=command.status,
                target_date=command.target_date,
                now=now,
            )
            await uow.save_milestone(milestone)
            await uow.replace_evidence_links(
                owner_user_id, EvidenceTargetKind.MILESTONE, milestone.id, links
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.MILESTONE_UPDATED,
                    "goal_milestone",
                    milestone.id,
                    context,
                    now,
                    goal_id=goal_id,
                    milestone_id=milestone.id,
                    status=milestone.status.value,
                    version=milestone.version,
                )
            )
            await uow.commit()
            return GoalMilestoneView(
                milestone=milestone,
                evidence_links=_known_current_link_views(links),
            )

    async def delete_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            milestone = await uow.get_milestone(
                owner_user_id, goal_id, milestone_id, for_update=True
            )
            if milestone is None:
                raise CareerGrowthNotFound
            self._version(milestone.version, expected_version)
            await uow.delete_milestone(owner_user_id, goal_id, milestone.id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.MILESTONE_DELETED,
                    "goal_milestone",
                    milestone.id,
                    context,
                    now,
                    goal_id=goal_id,
                    milestone_id=milestone.id,
                    version=milestone.version,
                )
            )
            await uow.commit()

    async def create_development_item(
        self,
        owner_user_id: UUID,
        command: CreateDevelopmentItem,
        idempotency_key: str,
        context: RequestContext,
    ) -> DevelopmentItemView:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint("create_development_item", _development_payload(command))
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                "create_development_item",
                fingerprint,
            )
            if replay is not None:
                return await self._development_view(uow, owner_user_id, replay)
            existing = await uow.list_development_items(
                owner_user_id, None, self._policy.max_development_items + 1
            )
            if len(existing) >= self._policy.max_development_items:
                raise CareerGrowthQuotaExceeded("development item limit reached")
            item_id = self._ids.new()
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.DEVELOPMENT_ITEM,
                item_id,
                command.evidence_ids,
                now,
            )
            self._completed_item_evidence(command.kind, command.status, links)
            item = DevelopmentItem(
                id=item_id,
                owner_user_id=owner_user_id,
                kind=command.kind,
                title=command.title,
                description=command.description,
                status=command.status,
                target_date=command.target_date,
                completed_at=now if command.status is DevelopmentStatus.COMPLETED else None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_development_item(item)
            await uow.replace_evidence_links(
                owner_user_id, EvidenceTargetKind.DEVELOPMENT_ITEM, item.id, links
            )
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "create_development_item",
                item.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.DEVELOPMENT_ITEM_CREATED,
                    "development_item",
                    item.id,
                    context,
                    now,
                    development_item_id=item.id,
                    status=item.status.value,
                    version=item.version,
                )
            )
            await uow.commit()
            return DevelopmentItemView(
                item=item,
                evidence_links=_known_current_link_views(links),
            )

    async def create_development_item_from_gap(
        self,
        owner_user_id: UUID,
        command: CreateDevelopmentItemFromGap,
        idempotency_key: str,
        context: RequestContext,
    ) -> DevelopmentItemView:
        self._authorize(owner_user_id, context)
        if self._gaps is None:
            raise CareerGrowthValidationError("gap source is unavailable")
        gaps = await self._gaps.list_gaps(owner_user_id, command.role_profile_id)
        selected = next(
            (
                gap
                for gap in gaps
                if gap.gap_kind == command.gap_kind and gap.label == command.label
            ),
            None,
        )
        if selected is None:
            raise CareerGrowthNotFound
        create = CreateDevelopmentItem(
            kind=_development_kind_for_gap(selected.gap_kind),
            title=_development_title_from_gap(selected.label),
            description=selected.requirement_text,
            status=DevelopmentStatus.PLANNED,
        )
        return await self.create_development_item(
            owner_user_id,
            create,
            idempotency_key,
            context,
        )

    async def update_development_item(
        self,
        owner_user_id: UUID,
        item_id: UUID,
        expected_version: int,
        command: UpdateDevelopmentItem,
        context: RequestContext,
    ) -> DevelopmentItemView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            item = await uow.get_development_item(owner_user_id, item_id, for_update=True)
            if item is None:
                raise CareerGrowthNotFound
            self._version(item.version, expected_version)
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.DEVELOPMENT_ITEM,
                item.id,
                command.evidence_ids,
                now,
            )
            self._completed_item_evidence(command.kind, command.status, links)
            item.edit(
                kind=command.kind,
                title=command.title,
                description=command.description,
                status=command.status,
                target_date=command.target_date,
                now=now,
            )
            await uow.save_development_item(item)
            await uow.replace_evidence_links(
                owner_user_id, EvidenceTargetKind.DEVELOPMENT_ITEM, item.id, links
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.DEVELOPMENT_ITEM_UPDATED,
                    "development_item",
                    item.id,
                    context,
                    now,
                    development_item_id=item.id,
                    status=item.status.value,
                    version=item.version,
                )
            )
            await uow.commit()
            return DevelopmentItemView(
                item=item,
                evidence_links=_known_current_link_views(links),
            )

    async def get_development_item(self, owner_user_id: UUID, item_id: UUID) -> DevelopmentItemView:
        async with self._uow() as uow:
            return await self._development_view(uow, owner_user_id, item_id)

    async def list_development_items(
        self, owner_user_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> PagedResult[DevelopmentItemView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            items = await uow.list_development_items(owner_user_id, after, page_size + 1)
            links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.DEVELOPMENT_ITEM,
                tuple(item.id for item in items),
            )
        grouped = _links_by_target(links)
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        views = [
            DevelopmentItemView(
                item=item,
                evidence_links=_link_views(grouped[item.id], current_by_id),
            )
            for item in items
        ]
        return page_result(views, cursor=after, limit=page_size)

    async def delete_development_item(
        self,
        owner_user_id: UUID,
        item_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            item = await uow.get_development_item(owner_user_id, item_id, for_update=True)
            if item is None:
                raise CareerGrowthNotFound
            self._version(item.version, expected_version)
            await uow.delete_development_item(owner_user_id, item.id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.DEVELOPMENT_ITEM_DELETED,
                    "development_item",
                    item.id,
                    context,
                    now,
                    development_item_id=item.id,
                    version=item.version,
                )
            )
            await uow.commit()

    async def create_review(
        self,
        owner_user_id: UUID,
        command: CreateCareerReview,
        idempotency_key: str,
        context: RequestContext,
    ) -> CareerReviewView:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint("create_review", _review_payload(command))
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, "create_review", fingerprint
            )
            if replay is not None:
                return await self._review_view(uow, owner_user_id, replay)
            existing = await uow.list_reviews(owner_user_id, None, self._policy.max_reviews + 1)
            if len(existing) >= self._policy.max_reviews:
                raise CareerGrowthQuotaExceeded("career review limit reached")
            review_id = self._ids.new()
            version_id = self._ids.new()
            version = self._review_version(
                owner_user_id=owner_user_id,
                review_id=review_id,
                version_id=version_id,
                version_number=1,
                status=ReviewVersionStatus.DRAFT,
                content=command.content,
                change_reason="review_created",
                material_change=False,
                supersedes=None,
                now=now,
            )
            review = CareerReview(
                id=review_id,
                owner_user_id=owner_user_id,
                cadence=command.cadence,
                period_start=command.period_start,
                period_end=command.period_end,
                latest_version_id=version.id,
                latest_version_number=version.version_number,
                latest_status=version.status,
                version=1,
                created_at=now,
                updated_at=now,
            )
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                version.id,
                command.evidence_ids,
                now,
            )
            await uow.add_review(review, version)
            await uow.replace_evidence_links(
                owner_user_id, EvidenceTargetKind.REVIEW_VERSION, version.id, links
            )
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "create_review",
                review.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.REVIEW_CREATED,
                    "career_review",
                    review.id,
                    context,
                    now,
                    review_id=review.id,
                    review_version_id=version.id,
                    status=version.status.value,
                    version=review.version,
                )
            )
            await uow.commit()
            version_view = ReviewVersionView(
                version=version,
                evidence_links=_known_current_link_views(links),
            )
            return CareerReviewView(
                review=review,
                current_version=version_view,
                history=(version_view,),
            )

    async def revise_review(
        self,
        owner_user_id: UUID,
        review_id: UUID,
        expected_version: int,
        command: ReviseCareerReview,
        context: RequestContext,
    ) -> CareerReviewView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            review = await uow.get_review(owner_user_id, review_id, for_update=True)
            if review is None:
                raise CareerGrowthNotFound
            self._version(review.version, expected_version)
            versions = await uow.get_review_versions(owner_user_id, (review.id,))
            if len(versions) >= self._policy.max_versions_per_review:
                raise CareerGrowthQuotaExceeded("career review version limit reached")
            current = _current_version(review, versions)
            next_id = self._ids.new()
            next_version = self._review_version(
                owner_user_id=owner_user_id,
                review_id=review.id,
                version_id=next_id,
                version_number=review.latest_version_number + 1,
                status=ReviewVersionStatus.DRAFT,
                content=command.content,
                change_reason=command.change_reason,
                material_change=True,
                supersedes=current.id,
                now=now,
            )
            links = await self._resolve_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                next_version.id,
                command.evidence_ids,
                now,
            )
            current_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                (current.id,),
            )
            if next_version.content_sha256 == current.content_sha256 and {
                (
                    link.evidence_id,
                    link.evidence_revision_id,
                    link.revision_number,
                    link.statement_sha256,
                )
                for link in links
            } == {
                (
                    link.evidence_id,
                    link.evidence_revision_id,
                    link.revision_number,
                    link.statement_sha256,
                )
                for link in current_links
            }:
                raise CareerGrowthValidationError(
                    "review revision must contain a material content or evidence change"
                )
            review.advance(
                next_version_id=next_version.id,
                next_version_number=next_version.version_number,
                status=next_version.status,
                now=now,
            )
            await uow.add_review_version(next_version)
            await uow.save_review(review)
            await uow.replace_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                next_version.id,
                links,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.REVIEW_REVISED,
                    "career_review",
                    review.id,
                    context,
                    now,
                    review_id=review.id,
                    review_version_id=next_version.id,
                    status=next_version.status.value,
                    reason_code="owner_material_edit",
                    version=review.version,
                )
            )
            result = await self._review_view(uow, owner_user_id, review.id)
            await uow.commit()
            return result

    async def finalize_review(
        self,
        owner_user_id: UUID,
        review_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> CareerReviewView:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint(
            "finalize_review",
            {"expectedVersion": expected_version, "reviewId": review_id},
        )
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                "finalize_review",
                fingerprint,
            )
            if replay is not None:
                return await self._finalized_review_view(
                    uow,
                    owner_user_id,
                    review_id,
                    replay,
                )
            review = await uow.get_review(owner_user_id, review_id, for_update=True)
            if review is None:
                raise CareerGrowthNotFound
            self._version(review.version, expected_version)
            versions = await uow.get_review_versions(owner_user_id, (review.id,))
            if len(versions) >= self._policy.max_versions_per_review:
                raise CareerGrowthQuotaExceeded("career review version limit reached")
            current = _current_version(review, versions)
            if current.status is ReviewVersionStatus.FINALIZED:
                raise CareerGrowthConflict("review is already finalized")
            content = ReviewContent(
                title=current.title,
                summary=current.summary,
                achievements=current.achievements,
                growth_areas=current.growth_areas,
                next_focus=current.next_focus,
            )
            finalized = self._review_version(
                owner_user_id=owner_user_id,
                review_id=review.id,
                version_id=self._ids.new(),
                version_number=review.latest_version_number + 1,
                status=ReviewVersionStatus.FINALIZED,
                content=content,
                change_reason="owner_finalized",
                material_change=False,
                supersedes=current.id,
                now=now,
            )
            current_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                (current.id,),
            )
            await self._validate_current_evidence(owner_user_id, current_links)
            copied_links = tuple(
                CareerGrowthEvidenceLink(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    target_kind=EvidenceTargetKind.REVIEW_VERSION,
                    target_id=finalized.id,
                    evidence_id=link.evidence_id,
                    evidence_revision_id=link.evidence_revision_id,
                    revision_number=link.revision_number,
                    statement_sha256=link.statement_sha256,
                    evidence_revised_at=link.evidence_revised_at,
                    created_at=now,
                )
                for link in current_links
            )
            review.advance(
                next_version_id=finalized.id,
                next_version_number=finalized.version_number,
                status=finalized.status,
                now=now,
            )
            await uow.add_review_version(finalized)
            await uow.save_review(review)
            await uow.replace_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                finalized.id,
                copied_links,
            )
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "finalize_review",
                finalized.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.REVIEW_FINALIZED,
                    "career_review",
                    review.id,
                    context,
                    now,
                    review_id=review.id,
                    review_version_id=finalized.id,
                    status=finalized.status.value,
                    reason_code="owner_finalized",
                    version=review.version,
                )
            )
            result = await self._review_view(uow, owner_user_id, review.id)
            await uow.commit()
            return result

    async def get_review(self, owner_user_id: UUID, review_id: UUID) -> CareerReviewView:
        async with self._uow() as uow:
            return await self._review_view(uow, owner_user_id, review_id)

    async def list_reviews(
        self, owner_user_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> PagedResult[CareerReviewSummaryView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            reviews = await uow.list_reviews(owner_user_id, after, page_size + 1)
            review_ids = tuple(review.id for review in reviews)
            metadata = await uow.get_review_list_metadata(owner_user_id, review_ids)
            metadata_by_review = {item.review_id: item for item in metadata}
            if set(metadata_by_review) != set(review_ids):
                raise CareerGrowthConflict("career review list metadata is incomplete")
            links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                tuple(item.current_version_id for item in metadata),
            )
        grouped = _links_by_target(links)
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        summaries = [
            CareerReviewSummaryView(
                review=review,
                current_title=metadata_by_review[review.id].current_title,
                history_count=metadata_by_review[review.id].history_count,
                evidence_link_count=len(grouped[metadata_by_review[review.id].current_version_id]),
                evidence_needs_review_count=sum(
                    not _evidence_link_is_current(link, current_by_id)
                    for link in grouped[metadata_by_review[review.id].current_version_id]
                ),
            )
            for review in reviews
        ]
        return page_result(summaries, cursor=after, limit=page_size)

    async def delete_review(
        self,
        owner_user_id: UUID,
        review_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            review = await uow.get_review(owner_user_id, review_id, for_update=True)
            if review is None:
                raise CareerGrowthNotFound
            self._version(review.version, expected_version)
            await uow.delete_review(owner_user_id, review.id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.REVIEW_DELETED,
                    "career_review",
                    review.id,
                    context,
                    now,
                    review_id=review.id,
                    version=review.version,
                )
            )
            await uow.commit()

    async def get_insights(self, owner_user_id: UUID) -> CareerGrowthInsights:
        """Build derived achievement, skill-evidence, promotion, and refresh views."""

        source = await self._source.insights(owner_user_id)
        if (
            len(source.achievements) > 2_000
            or len(source.eligible_evidence) > 2_000
            or len(source.skills) > self._policy.max_insight_skills
        ):
            raise CareerGrowthConflict("Career Record insight snapshot exceeds supported bounds")

        async with self._uow() as uow:
            goals = await uow.list_goals(owner_user_id, None, self._policy.max_goals + 1)
            development = await uow.list_development_items(
                owner_user_id,
                None,
                self._policy.max_development_items + 1,
            )
            reviews = await uow.list_reviews(owner_user_id, None, self._policy.max_reviews + 1)
            if (
                len(goals) > self._policy.max_goals
                or len(development) > self._policy.max_development_items
                or len(reviews) > self._policy.max_reviews
            ):
                raise CareerGrowthConflict("career growth insight inputs exceed supported bounds")
            milestones = await uow.list_milestones(
                owner_user_id,
                tuple(goal.id for goal in goals),
            )
            if len(milestones) > self._policy.max_milestones:
                raise CareerGrowthConflict("career growth insight milestones exceed bounds")
            review_versions = await uow.get_review_versions(
                owner_user_id,
                tuple(review.id for review in reviews),
            )
            milestone_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.MILESTONE,
                tuple(item.id for item in milestones),
            )
            development_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.DEVELOPMENT_ITEM,
                tuple(item.id for item in development),
            )
            review_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.REVIEW_VERSION,
                tuple(item.id for item in review_versions),
            )

        milestone_links_by_target = _links_by_target(milestone_links)
        development_links_by_target = _links_by_target(development_links)
        review_links_by_target = _links_by_target(review_links)
        eligible_evidence_by_id = {item.evidence_id: item for item in source.eligible_evidence}
        completed_milestone_evidence = tuple(
            evidence_id
            for item in milestones
            if item.status is MilestoneStatus.COMPLETED
            for evidence_id in _current_evidence_ids(
                milestone_links_by_target[item.id],
                eligible_evidence_by_id,
            )
        )
        promotion_items = [
            item
            for item in development
            if item.kind is DevelopmentKind.PROMOTION
            and item.status is not DevelopmentStatus.CANCELLED
        ]
        completed_promotion_evidence = tuple(
            evidence_id
            for item in promotion_items
            if item.status is DevelopmentStatus.COMPLETED
            for evidence_id in _current_evidence_ids(
                development_links_by_target[item.id],
                eligible_evidence_by_id,
            )
        )
        finalized_review_evidence = tuple(
            evidence_id
            for version in review_versions
            if version.status is ReviewVersionStatus.FINALIZED
            for evidence_id in _current_evidence_ids(
                review_links_by_target[version.id],
                eligible_evidence_by_id,
            )
        )
        annual_items = [
            item for item in development if item.kind is DevelopmentKind.ANNUAL_RESUME_REFRESH
        ]
        completed_refresh_evidence = tuple(
            evidence_id
            for item in annual_items
            if item.status is DevelopmentStatus.COMPLETED
            for evidence_id in _current_evidence_ids(
                development_links_by_target[item.id],
                eligible_evidence_by_id,
            )
        )
        evidenced_skills = [item for item in source.skills if item.evidence_count > 0]
        achievement_evidence_ids = tuple(item.evidence_id for item in source.achievements)
        skill_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id for item in evidenced_skills for evidence_id in item.evidence_ids
            )
        )
        completed_milestone_evidence = tuple(dict.fromkeys(completed_milestone_evidence))
        completed_promotion_evidence = tuple(dict.fromkeys(completed_promotion_evidence))
        finalized_review_evidence = tuple(dict.fromkeys(finalized_review_evidence))
        completed_refresh_evidence = tuple(dict.fromkeys(completed_refresh_evidence))

        checks = (
            PromotionReadinessCheck(
                code="eligible_achievement_evidence",
                label="Eligible achievement evidence",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if len(source.achievements) >= 3
                    else PromotionCheckStatus.NEEDS_EVIDENCE
                ),
                explanation=(
                    f"{len(source.achievements)} currently eligible Career Record "
                    "evidence revision(s) are available; three provide a useful review baseline."
                ),
                evidence_count=len(achievement_evidence_ids),
                evidence_ids=achievement_evidence_ids[: self._policy.max_insight_evidence_detail],
            ),
            PromotionReadinessCheck(
                code="skill_evidence_coverage",
                label="Skill-to-evidence coverage",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if evidenced_skills
                    else PromotionCheckStatus.NEEDS_EVIDENCE
                ),
                explanation=(
                    f"{len(evidenced_skills)} of {len(source.skills)} documented skill(s) "
                    "have currently eligible evidence."
                ),
                evidence_count=sum(item.evidence_count for item in evidenced_skills),
                evidence_ids=skill_evidence_ids[: self._policy.max_insight_evidence_detail],
            ),
            PromotionReadinessCheck(
                code="evidence_backed_milestones",
                label="Evidence-backed milestone progress",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if completed_milestone_evidence
                    else PromotionCheckStatus.NEEDS_ACTION
                ),
                explanation=(
                    "At least one completed milestone has eligible evidence."
                    if completed_milestone_evidence
                    else "Complete a goal milestone and link eligible evidence."
                ),
                evidence_count=len(completed_milestone_evidence),
                evidence_ids=completed_milestone_evidence[
                    : self._policy.max_insight_evidence_detail
                ],
            ),
            PromotionReadinessCheck(
                code="promotion_plan",
                label="Promotion preparation plan",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if completed_promotion_evidence
                    else PromotionCheckStatus.NEEDS_ACTION
                ),
                explanation=(
                    "A completed promotion-preparation item has eligible evidence."
                    if completed_promotion_evidence
                    else (
                        "Finish the active promotion-preparation plan with eligible evidence."
                        if promotion_items
                        else "Create a promotion-preparation development item."
                    )
                ),
                evidence_count=len(completed_promotion_evidence),
                evidence_ids=completed_promotion_evidence[
                    : self._policy.max_insight_evidence_detail
                ],
            ),
            PromotionReadinessCheck(
                code="finalized_career_review",
                label="Finalized evidence-backed review",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if finalized_review_evidence
                    else PromotionCheckStatus.NEEDS_ACTION
                ),
                explanation=(
                    "A finalized career review is pinned to eligible evidence."
                    if finalized_review_evidence
                    else "Finalize an evidence-backed quarterly or annual career review."
                ),
                evidence_count=len(finalized_review_evidence),
                evidence_ids=finalized_review_evidence[: self._policy.max_insight_evidence_detail],
            ),
            PromotionReadinessCheck(
                code="annual_resume_refresh",
                label="Annual resume refresh",
                status=(
                    PromotionCheckStatus.SUPPORTED
                    if completed_refresh_evidence
                    else PromotionCheckStatus.NEEDS_ACTION
                ),
                explanation=(
                    "A completed annual resume refresh has eligible evidence."
                    if completed_refresh_evidence
                    else (
                        "Complete the annual resume refresh and link eligible evidence."
                        if annual_items
                        else "Schedule an annual resume refresh workflow."
                    )
                ),
                evidence_count=len(completed_refresh_evidence),
                evidence_ids=completed_refresh_evidence[: self._policy.max_insight_evidence_detail],
            ),
        )
        supported = sum(item.status is PromotionCheckStatus.SUPPORTED for item in checks)
        status = (
            PromotionReadinessStatus.INSUFFICIENT_EVIDENCE
            if checks[0].status is PromotionCheckStatus.NEEDS_EVIDENCE
            or checks[1].status is PromotionCheckStatus.NEEDS_EVIDENCE
            else PromotionReadinessStatus.REVIEW_READY
            if supported >= 5
            else PromotionReadinessStatus.BUILDING
        )
        annual_views = tuple(
            DevelopmentItemView(
                item=item,
                evidence_links=_link_views(
                    development_links_by_target[item.id],
                    eligible_evidence_by_id,
                ),
            )
            for item in annual_items
        )
        return CareerGrowthInsights(
            achievements=source.achievements[: self._policy.max_insight_achievements],
            skills=source.skills,
            promotion_readiness=PromotionReadinessReport(
                status=status,
                generated_at=self._clock.now(),
                checks=checks,
                disclaimer=PROMOTION_READINESS_DISCLAIMER,
            ),
            annual_resume_refreshes=annual_views,
        )

    async def analyze_career_health(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        context: RequestContext,
    ) -> CareerHealthRecord:
        self._authorize(owner_user_id, context)
        fingerprint = _fingerprint("analyze_career_health", {})
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                "analyze_career_health",
                fingerprint,
            )
            if replay is not None:
                record = await uow.get_health_record(owner_user_id, replay)
                if record is None:
                    raise CareerGrowthConflict("idempotent analysis result was deleted")
                return record
            if await uow.count_health_records(owner_user_id) >= self._policy.max_health_history:
                raise CareerGrowthQuotaExceeded("career health history limit reached")
            goals = await uow.list_goals(owner_user_id, None, self._policy.max_goals + 1)
            development = await uow.list_development_items(
                owner_user_id, None, self._policy.max_development_items + 1
            )
            reviews = await uow.list_reviews(owner_user_id, None, self._policy.max_reviews + 1)
            if (
                len(goals) > self._policy.max_goals
                or len(development) > self._policy.max_development_items
                or len(reviews) > self._policy.max_reviews
            ):
                raise CareerGrowthConflict("career growth collection exceeds analysis bounds")
            milestones = await uow.list_milestones(owner_user_id, tuple(goal.id for goal in goals))
            if len(milestones) > self._policy.max_milestones:
                raise CareerGrowthConflict("career milestones exceed analysis bounds")
            goal_target_ids = tuple(goal.id for goal in goals)
            milestone_target_ids = tuple(item.id for item in milestones)
            development_target_ids = tuple(item.id for item in development)
            goal_links = await uow.list_evidence_links(
                owner_user_id, EvidenceTargetKind.GOAL, goal_target_ids
            )
            milestone_links = await uow.list_evidence_links(
                owner_user_id, EvidenceTargetKind.MILESTONE, milestone_target_ids
            )
            development_links = await uow.list_evidence_links(
                owner_user_id,
                EvidenceTargetKind.DEVELOPMENT_ITEM,
                development_target_ids,
            )
            review_versions = await uow.get_review_versions(
                owner_user_id, tuple(review.id for review in reviews)
            )
            source = await self._source.snapshot(owner_user_id)
            milestones_by_goal: defaultdict[UUID, list[GoalMilestone]] = defaultdict(list)
            for milestone in milestones:
                milestones_by_goal[milestone.goal_id].append(milestone)
            if any(
                len(items) > self._policy.max_milestones_per_goal
                for items in milestones_by_goal.values()
            ):
                raise CareerGrowthConflict("a career goal exceeds the supported milestone bound")
            links_by_target = _links_by_target([*goal_links, *milestone_links, *development_links])
            goals_signal = tuple(
                GoalHealthSignal(
                    goal_id=goal.id,
                    version=goal.version,
                    status=goal.status,
                    milestone_statuses=tuple(
                        item.status
                        for item in sorted(
                            milestones_by_goal[goal.id], key=lambda item: str(item.id)
                        )
                    ),
                    evidence_revision_ids=tuple(
                        dict.fromkeys(
                            [link.evidence_revision_id for link in links_by_target[goal.id]]
                            + [
                                link.evidence_revision_id
                                for milestone in milestones_by_goal[goal.id]
                                for link in links_by_target[milestone.id]
                            ]
                        )
                    ),
                )
                for goal in goals
            )
            development_signal = tuple(
                DevelopmentHealthSignal(
                    item_id=item.id,
                    version=item.version,
                    kind=item.kind,
                    status=item.status,
                    target_date=item.target_date,
                    evidence_revision_ids=tuple(
                        link.evidence_revision_id for link in links_by_target[item.id]
                    ),
                )
                for item in development
            )
            versions_by_review: defaultdict[UUID, list[CareerReviewVersion]] = defaultdict(list)
            for version in review_versions:
                versions_by_review[version.review_id].append(version)
            if any(
                len(items) > self._policy.max_versions_per_review
                for items in versions_by_review.values()
            ):
                raise CareerGrowthConflict("a career review exceeds the supported version bound")
            review_signal = tuple(
                _review_health_signal(review, versions_by_review[review.id]) for review in reviews
            )
            scored = score_career_health(
                CareerHealthInput(
                    as_of=now.date(),
                    source=source,
                    goals=goals_signal,
                    development_items=development_signal,
                    reviews=review_signal,
                )
            )
            analysis = CareerHealthAnalysis(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                engine_version=scored.engine_version,
                configuration_version=scored.configuration_version,
                feature_schema_version=scored.feature_schema_version,
                input_snapshot=scored.input_snapshot,
                configuration_snapshot=scored.configuration_snapshot,
                formula_snapshot=scored.formula_snapshot,
                snapshot_sha256=scored.snapshot_sha256,
                status=scored.status,
                raw_score_basis_points=scored.raw_score_basis_points,
                display_score=scored.display_score,
                label=scored.label,
                applicable_component_count=scored.applicable_component_count,
                applicable_weight_basis_points=scored.applicable_weight_basis_points,
                insufficient_reason=scored.insufficient_reason,
                disclaimer=scored.disclaimer,
                created_at=now,
            )
            components = tuple(
                CareerHealthComponent(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    analysis_id=analysis.id,
                    dimension=item.dimension,
                    configured_weight_basis_points=item.configured_weight_basis_points,
                    applicable=item.applicable,
                    score_basis_points=item.score_basis_points,
                    contribution_basis_points=item.contribution_basis_points,
                    explanation=item.explanation,
                )
                for item in scored.components
            )
            findings = tuple(
                CareerHealthFinding(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    analysis_id=analysis.id,
                    code=item.code,
                    severity=item.severity,
                    message=item.message,
                )
                for item in scored.findings
            )
            record = CareerHealthRecord(analysis=analysis, components=components, findings=findings)
            await uow.add_health_record(record)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "analyze_career_health",
                analysis.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.CAREER_HEALTH_ANALYZED,
                    "career_health_analysis",
                    analysis.id,
                    context,
                    now,
                    analysis_id=analysis.id,
                    status=analysis.status.value,
                )
            )
            await uow.commit()
            return record

    async def get_career_health(self, owner_user_id: UUID, analysis_id: UUID) -> CareerHealthRecord:
        async with self._uow() as uow:
            record = await uow.get_health_record(owner_user_id, analysis_id)
        if record is None:
            raise CareerGrowthNotFound
        return record

    async def list_career_health(
        self, owner_user_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> PagedResult[CareerHealthSummary]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            summaries = await uow.list_health_summaries(
                owner_user_id,
                after,
                page_size + 1,
            )
        return page_result(summaries, cursor=after, limit=page_size)

    async def delete_career_health(
        self, owner_user_id: UUID, analysis_id: UUID, context: RequestContext
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            record = await uow.get_health_record(owner_user_id, analysis_id)
            if record is None:
                raise CareerGrowthNotFound
            await uow.delete_health_record(owner_user_id, analysis_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    GrowthAuditAction.CAREER_HEALTH_DELETED,
                    "career_health_analysis",
                    analysis_id,
                    context,
                    now,
                    analysis_id=analysis_id,
                )
            )
            await uow.commit()

    async def _goal_view(
        self, uow: CareerGrowthUnitOfWork, owner_user_id: UUID, goal_id: UUID
    ) -> GoalView:
        goal = await uow.get_goal(owner_user_id, goal_id)
        if goal is None:
            raise CareerGrowthNotFound
        return (await self._goal_views(uow, owner_user_id, [goal]))[0]

    async def _goal_views(
        self,
        uow: CareerGrowthUnitOfWork,
        owner_user_id: UUID,
        goals: list[CareerGoal],
    ) -> list[GoalView]:
        if not goals:
            return []
        goal_ids = tuple(goal.id for goal in goals)
        milestones = await uow.list_milestones(owner_user_id, goal_ids)
        goal_links = await uow.list_evidence_links(owner_user_id, EvidenceTargetKind.GOAL, goal_ids)
        milestone_links = await uow.list_evidence_links(
            owner_user_id,
            EvidenceTargetKind.MILESTONE,
            tuple(item.id for item in milestones),
        )
        grouped_milestones: defaultdict[UUID, list[GoalMilestone]] = defaultdict(list)
        for milestone in milestones:
            grouped_milestones[milestone.goal_id].append(milestone)
        grouped_links = _links_by_target([*goal_links, *milestone_links])
        current_by_id = await self._current_evidence_by_id(
            owner_user_id,
            [*goal_links, *milestone_links],
        )
        return [
            GoalView(
                goal=goal,
                evidence_links=_link_views(grouped_links[goal.id], current_by_id),
                milestones=tuple(
                    GoalMilestoneView(
                        milestone=milestone,
                        evidence_links=_link_views(
                            grouped_links[milestone.id],
                            current_by_id,
                        ),
                    )
                    for milestone in sorted(
                        grouped_milestones[goal.id],
                        key=lambda item: (item.target_date is None, item.target_date, str(item.id)),
                    )
                ),
            )
            for goal in goals
        ]

    async def _milestone_view(
        self,
        uow: CareerGrowthUnitOfWork,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
    ) -> GoalMilestoneView:
        milestone = await uow.get_milestone(owner_user_id, goal_id, milestone_id)
        if milestone is None:
            raise CareerGrowthNotFound
        links = await uow.list_evidence_links(
            owner_user_id, EvidenceTargetKind.MILESTONE, (milestone.id,)
        )
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        return GoalMilestoneView(
            milestone=milestone,
            evidence_links=_link_views(links, current_by_id),
        )

    async def _development_view(
        self, uow: CareerGrowthUnitOfWork, owner_user_id: UUID, item_id: UUID
    ) -> DevelopmentItemView:
        item = await uow.get_development_item(owner_user_id, item_id)
        if item is None:
            raise CareerGrowthNotFound
        links = await uow.list_evidence_links(
            owner_user_id, EvidenceTargetKind.DEVELOPMENT_ITEM, (item.id,)
        )
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        return DevelopmentItemView(
            item=item,
            evidence_links=_link_views(links, current_by_id),
        )

    async def _review_view(
        self, uow: CareerGrowthUnitOfWork, owner_user_id: UUID, review_id: UUID
    ) -> CareerReviewView:
        review = await uow.get_review(owner_user_id, review_id)
        if review is None:
            raise CareerGrowthNotFound
        versions = sorted(
            await uow.get_review_versions(owner_user_id, (review.id,)),
            key=lambda item: item.version_number,
        )
        if len(versions) > self._policy.max_versions_per_review:
            raise CareerGrowthConflict("career review history exceeds supported bounds")
        current = _current_version(review, versions)
        links = await uow.list_evidence_links(
            owner_user_id,
            EvidenceTargetKind.REVIEW_VERSION,
            tuple(version.id for version in versions),
        )
        grouped = _links_by_target(links)
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        history = tuple(
            ReviewVersionView(
                version=version,
                evidence_links=_link_views(grouped[version.id], current_by_id),
            )
            for version in versions
        )
        current_view = next(item for item in history if item.version.id == current.id)
        return CareerReviewView(review=review, current_version=current_view, history=history)

    async def _finalized_review_view(
        self,
        uow: CareerGrowthUnitOfWork,
        owner_user_id: UUID,
        review_id: UUID,
        finalized_version_id: UUID,
    ) -> CareerReviewView:
        finalized = await uow.get_review_version(owner_user_id, finalized_version_id)
        if (
            finalized is None
            or finalized.review_id != review_id
            or finalized.status is not ReviewVersionStatus.FINALIZED
        ):
            raise CareerGrowthConflict("idempotent finalized review result is unavailable")
        persisted_review = await uow.get_review(owner_user_id, review_id)
        if persisted_review is None:
            raise CareerGrowthConflict("idempotent finalized review result is unavailable")
        versions = sorted(
            (
                version
                for version in await uow.get_review_versions(owner_user_id, (review_id,))
                if version.version_number <= finalized.version_number
            ),
            key=lambda item: item.version_number,
        )
        if (
            len(versions) != finalized.version_number
            or versions[-1].id != finalized.id
            or [version.version_number for version in versions]
            != list(range(1, finalized.version_number + 1))
            or len(versions) > self._policy.max_versions_per_review
        ):
            raise CareerGrowthConflict("idempotent finalized review history is unavailable")
        links = await uow.list_evidence_links(
            owner_user_id,
            EvidenceTargetKind.REVIEW_VERSION,
            tuple(version.id for version in versions),
        )
        grouped = _links_by_target(links)
        current_by_id = await self._current_evidence_by_id(owner_user_id, links)
        history = tuple(
            ReviewVersionView(
                version=version,
                evidence_links=_link_views(grouped[version.id], current_by_id),
            )
            for version in versions
        )
        replay_review = CareerReview(
            id=persisted_review.id,
            owner_user_id=persisted_review.owner_user_id,
            cadence=persisted_review.cadence,
            period_start=persisted_review.period_start,
            period_end=persisted_review.period_end,
            latest_version_id=finalized.id,
            latest_version_number=finalized.version_number,
            latest_status=finalized.status,
            version=finalized.version_number,
            created_at=persisted_review.created_at,
            updated_at=finalized.created_at,
        )
        return CareerReviewView(
            review=replay_review,
            current_version=history[-1],
            history=history,
        )

    async def _current_evidence_by_id(
        self,
        owner_user_id: UUID,
        links: list[CareerGrowthEvidenceLink],
    ) -> dict[UUID, GrowthEvidenceSnapshot]:
        evidence_ids = tuple(dict.fromkeys(link.evidence_id for link in links))
        if not evidence_ids:
            return {}
        current = await self._source.current_evidence(owner_user_id, evidence_ids)
        return {item.evidence_id: item for item in current}

    async def _resolve_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_id: UUID,
        evidence_ids: tuple[UUID, ...],
        now: datetime,
    ) -> tuple[CareerGrowthEvidenceLink, ...]:
        if len(evidence_ids) != len(set(evidence_ids)):
            raise CareerGrowthValidationError("evidence links must be unique")
        if len(evidence_ids) > self._policy.max_evidence_links_per_target:
            raise CareerGrowthValidationError("too many evidence links")
        if not evidence_ids:
            return ()
        snapshots = await self._source.resolve_evidence(owner_user_id, evidence_ids)
        snapshots_by_id = {item.evidence_id: item for item in snapshots}
        if set(snapshots_by_id) != set(evidence_ids) or len(snapshots) != len(evidence_ids):
            raise CareerGrowthConflict(
                "Career Record did not return every requested eligible evidence revision"
            )
        return tuple(
            CareerGrowthEvidenceLink(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                target_kind=target_kind,
                target_id=target_id,
                evidence_id=evidence_id,
                evidence_revision_id=snapshots_by_id[evidence_id].evidence_revision_id,
                revision_number=snapshots_by_id[evidence_id].revision_number,
                statement_sha256=snapshots_by_id[evidence_id].statement_sha256,
                evidence_revised_at=snapshots_by_id[evidence_id].revised_at,
                created_at=now,
            )
            for evidence_id in evidence_ids
        )

    async def _validate_current_evidence(
        self,
        owner_user_id: UUID,
        links: list[CareerGrowthEvidenceLink],
    ) -> None:
        """Require finalized factual reviews to retain eligible exact revisions."""

        if not links:
            raise CareerGrowthValidationError(
                "finalized career review requires at least one eligible evidence link"
            )
        evidence_ids = tuple(link.evidence_id for link in links)
        current = await self._source.resolve_evidence(owner_user_id, evidence_ids)
        by_id = {item.evidence_id: item for item in current}
        if len(by_id) != len(links):
            raise CareerGrowthConflict(
                "career review evidence changed before finalization; revise the draft"
            )
        for link in links:
            snapshot = by_id.get(link.evidence_id)
            if (
                snapshot is None
                or snapshot.evidence_revision_id != link.evidence_revision_id
                or snapshot.revision_number != link.revision_number
                or snapshot.statement_sha256 != link.statement_sha256
            ):
                raise CareerGrowthConflict(
                    "career review evidence changed before finalization; revise the draft"
                )

    async def _replay(
        self,
        uow: CareerGrowthUnitOfWork,
        owner_user_id: UUID,
        idempotency_key: str,
        operation: str,
        fingerprint: str,
    ) -> UUID | None:
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise CareerGrowthValidationError("idempotency key is invalid")
        existing = await uow.get_idempotency(owner_user_id, idempotency_key)
        if existing is None:
            return None
        if existing.operation != operation or existing.request_fingerprint != fingerprint:
            raise CareerGrowthIdempotencyConflict
        return existing.result_id

    async def _record_idempotency(
        self,
        uow: CareerGrowthUnitOfWork,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
        operation: str,
        result_id: UUID,
        now: datetime,
    ) -> None:
        await uow.add_idempotency(
            CareerGrowthIdempotencyRecord(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                operation=operation,
                result_id=result_id,
                created_at=now,
            )
        )

    def _review_version(
        self,
        *,
        owner_user_id: UUID,
        review_id: UUID,
        version_id: UUID,
        version_number: int,
        status: ReviewVersionStatus,
        content: ReviewContent,
        change_reason: str,
        material_change: bool,
        supersedes: UUID | None,
        now: datetime,
    ) -> CareerReviewVersion:
        return CareerReviewVersion(
            id=version_id,
            owner_user_id=owner_user_id,
            review_id=review_id,
            version_number=version_number,
            status=status,
            title=content.title,
            summary=content.summary,
            achievements=content.achievements,
            growth_areas=content.growth_areas,
            next_focus=content.next_focus,
            change_reason=change_reason,
            material_change=material_change,
            supersedes_version_id=supersedes,
            content_sha256=review_content_hash(
                title=content.title,
                summary=content.summary,
                achievements=content.achievements,
                growth_areas=content.growth_areas,
                next_focus=content.next_focus,
            ),
            created_at=now,
        )

    @staticmethod
    def _completed_item_evidence(
        kind: DevelopmentKind,
        status: DevelopmentStatus,
        links: tuple[CareerGrowthEvidenceLink, ...],
    ) -> None:
        if (
            kind
            in {
                DevelopmentKind.CERTIFICATION,
                DevelopmentKind.ANNUAL_RESUME_REFRESH,
            }
            and status is DevelopmentStatus.COMPLETED
            and not links
        ):
            raise CareerGrowthValidationError(
                f"completed {kind.value.replace('_', ' ')} requires eligible evidence"
            )

    def _page_size(self, value: int | None) -> int:
        if value is None:
            return self._policy.default_page_size
        if not 1 <= value <= self._policy.max_page_size:
            raise CareerGrowthValidationError("page limit is out of range")
        return value

    @staticmethod
    def _authorize(owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise CareerGrowthNotFound

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if not 1 <= expected <= 2_147_483_647:
            raise CareerGrowthValidationError("expected version must be a positive int32")
        if actual != expected:
            raise CareerGrowthVersionConflict

    def _audit(
        self,
        owner_user_id: UUID,
        action: GrowthAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        **details: UUID | str | int | None,
    ) -> CareerGrowthAuditEvent:
        return CareerGrowthAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            details=tuple((key, str(value)) for key, value in details.items() if value is not None),
            created_at=created_at,
        )


def _current_version(
    review: CareerReview, versions: list[CareerReviewVersion]
) -> CareerReviewVersion:
    current = next(
        (version for version in versions if version.id == review.latest_version_id), None
    )
    if (
        current is None
        or current.version_number != review.latest_version_number
        or current.status is not review.latest_status
    ):
        raise CareerGrowthConflict("career review version history is incomplete")
    return current


def _review_health_signal(
    review: CareerReview, versions: list[CareerReviewVersion]
) -> ReviewHealthSignal:
    finalized = [version for version in versions if version.status is ReviewVersionStatus.FINALIZED]
    latest = max(finalized, key=lambda item: (item.created_at, str(item.id)), default=None)
    return ReviewHealthSignal(
        review_id=review.id,
        version=review.version,
        cadence=review.cadence,
        has_review_data=bool(versions),
        latest_finalized_at=latest.created_at if latest is not None else None,
        latest_finalized_version_id=latest.id if latest is not None else None,
    )


def _links_by_target(
    links: list[CareerGrowthEvidenceLink],
) -> defaultdict[UUID, list[CareerGrowthEvidenceLink]]:
    grouped: defaultdict[UUID, list[CareerGrowthEvidenceLink]] = defaultdict(list)
    for link in sorted(links, key=lambda item: (str(item.target_id), str(item.id))):
        grouped[link.target_id].append(link)
    return grouped


def _known_current_link_views(
    links: tuple[CareerGrowthEvidenceLink, ...],
) -> tuple[EvidenceLinkView, ...]:
    return tuple(EvidenceLinkView(link=link, is_current=True) for link in links)


def _link_views(
    links: list[CareerGrowthEvidenceLink],
    eligible_evidence_by_id: dict[UUID, GrowthEvidenceSnapshot],
) -> tuple[EvidenceLinkView, ...]:
    return tuple(
        EvidenceLinkView(
            link=link,
            is_current=_evidence_link_is_current(link, eligible_evidence_by_id),
        )
        for link in links
    )


def _evidence_link_is_current(
    link: CareerGrowthEvidenceLink,
    eligible_evidence_by_id: dict[UUID, GrowthEvidenceSnapshot],
) -> bool:
    current = eligible_evidence_by_id.get(link.evidence_id)
    return (
        current is not None
        and current.evidence_revision_id == link.evidence_revision_id
        and current.revision_number == link.revision_number
        and current.statement_sha256 == link.statement_sha256
        and current.revised_at == link.evidence_revised_at
    )


def _current_evidence_ids(
    links: list[CareerGrowthEvidenceLink],
    eligible_evidence_by_id: dict[UUID, GrowthEvidenceSnapshot],
) -> tuple[UUID, ...]:
    return tuple(
        link.evidence_id
        for link in links
        if _evidence_link_is_current(link, eligible_evidence_by_id)
    )


def _goal_payload(command: CreateGoal | UpdateGoal) -> dict[str, object]:
    return {
        "description": _clean(command.description),
        "evidenceIds": sorted(str(item) for item in command.evidence_ids),
        "status": command.status.value,
        "targetDate": command.target_date,
        "title": _clean(command.title),
    }


def _milestone_payload(command: CreateMilestone | UpdateMilestone) -> dict[str, object]:
    return {
        "evidenceIds": sorted(str(item) for item in command.evidence_ids),
        "status": command.status.value,
        "targetDate": command.target_date,
        "title": _clean(command.title),
    }


def _development_payload(
    command: CreateDevelopmentItem | UpdateDevelopmentItem,
) -> dict[str, object]:
    return {
        "description": _clean(command.description),
        "evidenceIds": sorted(str(item) for item in command.evidence_ids),
        "kind": command.kind.value,
        "status": command.status.value,
        "targetDate": command.target_date,
        "title": _clean(command.title),
    }


def _review_payload(command: CreateCareerReview) -> dict[str, object]:
    return {
        "cadence": command.cadence.value,
        "content": _review_content_payload(command.content),
        "evidenceIds": sorted(str(item) for item in command.evidence_ids),
        "periodEnd": command.period_end,
        "periodStart": command.period_start,
    }


def _review_content_payload(content: ReviewContent) -> dict[str, object]:
    return {
        "achievements": _clean(content.achievements),
        "growthAreas": _clean(content.growth_areas),
        "nextFocus": _clean(content.next_focus),
        "summary": _clean(content.summary),
        "title": _clean(content.title),
    }


def _clean(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else None
    return normalized or None


def _fingerprint(operation: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        {"operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def _development_kind_for_gap(gap_kind: str) -> DevelopmentKind:
    normalized = gap_kind.strip().casefold()
    if "cert" in normalized:
        return DevelopmentKind.CERTIFICATION
    return DevelopmentKind.LEARNING


def _development_title_from_gap(label: str) -> str:
    cleaned = " ".join(label.strip().split())
    return f"Address readiness gap: {cleaned}"
