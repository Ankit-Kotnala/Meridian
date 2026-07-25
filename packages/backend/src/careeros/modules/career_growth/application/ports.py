"""Inward-facing ports for Career Growth use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.career_growth.domain import (
    CareerGoal,
    CareerGrowthAuditEvent,
    CareerGrowthEvidenceLink,
    CareerGrowthIdempotencyRecord,
    CareerGrowthSourceSnapshot,
    CareerReview,
    CareerReviewVersion,
    DevelopmentItem,
    EvidenceTargetKind,
    GoalMilestone,
    GrowthEvidenceSnapshot,
)

from .models import (
    CareerGrowthInsightSource,
    CareerHealthRecord,
    CareerHealthSummary,
    PageCursor,
    ReviewListMetadata,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class CareerGrowthSourceProvider(Protocol):
    """Purpose-minimized, owner-scoped Career Record query boundary."""

    async def snapshot(self, owner_user_id: UUID) -> CareerGrowthSourceSnapshot: ...

    async def resolve_evidence(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[GrowthEvidenceSnapshot, ...]: ...

    async def current_evidence(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        """Return only currently eligible requested evidence without failing on stale IDs."""

        ...

    async def insights(self, owner_user_id: UUID) -> CareerGrowthInsightSource: ...


class CareerGrowthUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_owner(self, owner_user_id: UUID) -> None:
        """Serialize an owner's growth mutations inside the current transaction."""

        ...

    async def get_goal(
        self, owner_user_id: UUID, goal_id: UUID, *, for_update: bool = False
    ) -> CareerGoal | None: ...

    async def list_goals(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerGoal]: ...

    async def add_goal(self, goal: CareerGoal) -> None: ...

    async def save_goal(self, goal: CareerGoal) -> None: ...

    async def delete_goal(self, owner_user_id: UUID, goal_id: UUID) -> None: ...

    async def get_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
        *,
        for_update: bool = False,
    ) -> GoalMilestone | None: ...

    async def list_milestones(
        self, owner_user_id: UUID, goal_ids: tuple[UUID, ...]
    ) -> list[GoalMilestone]: ...

    async def count_milestones(self, owner_user_id: UUID) -> int: ...

    async def count_milestones_by_goal(
        self,
        owner_user_id: UUID,
        goal_ids: tuple[UUID, ...],
    ) -> dict[UUID, int]: ...

    async def add_milestone(self, milestone: GoalMilestone) -> None: ...

    async def save_milestone(self, milestone: GoalMilestone) -> None: ...

    async def delete_milestone(
        self, owner_user_id: UUID, goal_id: UUID, milestone_id: UUID
    ) -> None: ...

    async def get_development_item(
        self, owner_user_id: UUID, item_id: UUID, *, for_update: bool = False
    ) -> DevelopmentItem | None: ...

    async def list_development_items(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[DevelopmentItem]: ...

    async def add_development_item(self, item: DevelopmentItem) -> None: ...

    async def save_development_item(self, item: DevelopmentItem) -> None: ...

    async def delete_development_item(self, owner_user_id: UUID, item_id: UUID) -> None: ...

    async def get_review(
        self, owner_user_id: UUID, review_id: UUID, *, for_update: bool = False
    ) -> CareerReview | None: ...

    async def list_reviews(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerReview]: ...

    async def add_review(self, review: CareerReview, version: CareerReviewVersion) -> None: ...

    async def save_review(self, review: CareerReview) -> None: ...

    async def add_review_version(self, version: CareerReviewVersion) -> None: ...

    async def get_review_version(
        self, owner_user_id: UUID, version_id: UUID
    ) -> CareerReviewVersion | None: ...

    async def get_review_versions(
        self, owner_user_id: UUID, review_ids: tuple[UUID, ...]
    ) -> list[CareerReviewVersion]: ...

    async def get_review_list_metadata(
        self,
        owner_user_id: UUID,
        review_ids: tuple[UUID, ...],
    ) -> list[ReviewListMetadata]: ...

    async def delete_review(self, owner_user_id: UUID, review_id: UUID) -> None: ...

    async def list_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_ids: tuple[UUID, ...],
    ) -> list[CareerGrowthEvidenceLink]: ...

    async def replace_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_id: UUID,
        links: tuple[CareerGrowthEvidenceLink, ...],
    ) -> None: ...

    async def get_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> CareerGrowthIdempotencyRecord | None: ...

    async def add_idempotency(self, record: CareerGrowthIdempotencyRecord) -> None: ...

    async def add_health_record(self, record: CareerHealthRecord) -> None: ...

    async def get_health_record(
        self, owner_user_id: UUID, analysis_id: UUID
    ) -> CareerHealthRecord | None: ...

    async def list_health_records(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerHealthRecord]: ...

    async def list_health_summaries(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerHealthSummary]: ...

    async def count_health_records(self, owner_user_id: UUID) -> int: ...

    async def delete_health_record(self, owner_user_id: UUID, analysis_id: UUID) -> None: ...

    async def add_audit(self, event: CareerGrowthAuditEvent) -> None: ...

    async def commit(self) -> None: ...


CareerGrowthUnitOfWorkFactory = Callable[[], CareerGrowthUnitOfWork]
