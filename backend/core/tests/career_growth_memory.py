"""Deterministic in-memory Career Growth ports for focused service tests."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from rezumi.modules.career_growth.application.models import (
    CareerGrowthInsightSource,
    CareerHealthRecord,
    CareerHealthSummary,
    GrowthAchievementSnapshot,
    GrowthSkillSnapshot,
    PageCursor,
    ReviewListMetadata,
)
from rezumi.modules.career_growth.domain import (
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

NOW = datetime(2026, 7, 25, 12, tzinfo=UTC)


class FixedClock:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value or NOW

    def now(self) -> datetime:
        return self.value


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


class StaticCareerGrowthSource:
    def __init__(self, snapshot: CareerGrowthSourceSnapshot | None = None) -> None:
        self.snapshot_value = snapshot or CareerGrowthSourceSnapshot(evidence=(), skill_ids=())
        self.snapshot_requests: list[UUID] = []
        self.resolve_requests: list[tuple[UUID, tuple[UUID, ...]]] = []

    async def snapshot(self, owner_user_id: UUID) -> CareerGrowthSourceSnapshot:
        self.snapshot_requests.append(owner_user_id)
        return self.snapshot_value

    async def resolve_evidence(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        self.resolve_requests.append((owner_user_id, evidence_ids))
        by_id = {item.evidence_id: item for item in self.snapshot_value.evidence}
        return tuple(by_id[item] for item in evidence_ids if item in by_id)

    async def current_evidence(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        self.resolve_requests.append((owner_user_id, evidence_ids))
        by_id = {item.evidence_id: item for item in self.snapshot_value.evidence}
        return tuple(by_id[item] for item in evidence_ids if item in by_id)

    async def insights(self, owner_user_id: UUID) -> CareerGrowthInsightSource:
        self.snapshot_requests.append(owner_user_id)
        achievements = tuple(
            GrowthAchievementSnapshot(
                evidence_id=item.evidence_id,
                evidence_revision_id=item.evidence_revision_id,
                revision_number=item.revision_number,
                title=f"Eligible evidence {item.evidence_id}",
                statement=f"Eligible owner-authored statement {item.evidence_id}.",
                evidence_type="achievement",
                strength="confirmed",
                revised_at=item.revised_at,
                skill_ids=item.skill_ids,
            )
            for item in self.snapshot_value.evidence
        )
        return CareerGrowthInsightSource(
            achievements=achievements,
            skills=tuple(
                GrowthSkillSnapshot(
                    skill_id=skill_id,
                    name=f"Skill {skill_id}",
                    category=None,
                    proficiency=None,
                    evidence_count=sum(skill_id in item.skill_ids for item in achievements),
                    evidence_ids=tuple(
                        item.evidence_id for item in achievements if skill_id in item.skill_ids
                    )[:25],
                    latest_evidence_at=max(
                        (item.revised_at for item in achievements if skill_id in item.skill_ids),
                        default=None,
                    ),
                )
                for skill_id in self.snapshot_value.skill_ids
            ),
            eligible_evidence=self.snapshot_value.evidence,
        )


class MemoryCareerGrowth:
    def __init__(self) -> None:
        self.goals: dict[UUID, CareerGoal] = {}
        self.milestones: dict[UUID, GoalMilestone] = {}
        self.development_items: dict[UUID, DevelopmentItem] = {}
        self.reviews: dict[UUID, CareerReview] = {}
        self.review_versions: dict[UUID, CareerReviewVersion] = {}
        self.evidence_links: dict[UUID, CareerGrowthEvidenceLink] = {}
        self.idempotency: dict[tuple[UUID, str], CareerGrowthIdempotencyRecord] = {}
        self.health_records: dict[UUID, CareerHealthRecord] = {}
        self.audits: list[CareerGrowthAuditEvent] = []
        self.locked_owners: list[UUID] = []
        self.query_counts: defaultdict[str, int] = defaultdict(int)

    def __call__(self) -> MemoryCareerGrowth:
        return self

    async def __aenter__(self) -> MemoryCareerGrowth:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def lock_owner(self, owner_user_id: UUID) -> None:
        self.locked_owners.append(owner_user_id)

    async def get_goal(
        self, owner_user_id: UUID, goal_id: UUID, *, for_update: bool = False
    ) -> CareerGoal | None:
        del for_update
        goal = self.goals.get(goal_id)
        return goal if goal is not None and goal.owner_user_id == owner_user_id else None

    async def list_goals(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerGoal]:
        values = sorted(
            [item for item in self.goals.values() if item.owner_user_id == owner_user_id],
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def add_goal(self, goal: CareerGoal) -> None:
        self.goals[goal.id] = goal

    async def save_goal(self, goal: CareerGoal) -> None:
        self.goals[goal.id] = goal

    async def delete_goal(self, owner_user_id: UUID, goal_id: UUID) -> None:
        goal = await self.get_goal(owner_user_id, goal_id)
        if goal is None:
            return
        milestone_ids = [
            item.id
            for item in self.milestones.values()
            if item.owner_user_id == owner_user_id and item.goal_id == goal_id
        ]
        for milestone_id in milestone_ids:
            del self.milestones[milestone_id]
        target_ids = {goal_id, *milestone_ids}
        self.evidence_links = {
            key: link
            for key, link in self.evidence_links.items()
            if not (link.owner_user_id == owner_user_id and link.target_id in target_ids)
        }
        del self.goals[goal_id]

    async def get_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
        *,
        for_update: bool = False,
    ) -> GoalMilestone | None:
        del for_update
        item = self.milestones.get(milestone_id)
        return (
            item
            if item is not None and item.owner_user_id == owner_user_id and item.goal_id == goal_id
            else None
        )

    async def list_milestones(
        self, owner_user_id: UUID, goal_ids: tuple[UUID, ...]
    ) -> list[GoalMilestone]:
        return sorted(
            [
                item
                for item in self.milestones.values()
                if item.owner_user_id == owner_user_id and item.goal_id in goal_ids
            ],
            key=lambda item: (
                str(item.goal_id),
                item.target_date is None,
                item.target_date,
                item.id,
            ),
        )

    async def count_milestones(self, owner_user_id: UUID) -> int:
        return sum(item.owner_user_id == owner_user_id for item in self.milestones.values())

    async def count_milestones_by_goal(
        self,
        owner_user_id: UUID,
        goal_ids: tuple[UUID, ...],
    ) -> dict[UUID, int]:
        self.query_counts["count_milestones_by_goal"] += 1
        counts = {goal_id: 0 for goal_id in goal_ids}
        for milestone in self.milestones.values():
            if milestone.owner_user_id == owner_user_id and milestone.goal_id in counts:
                counts[milestone.goal_id] += 1
        return counts

    async def add_milestone(self, milestone: GoalMilestone) -> None:
        self.milestones[milestone.id] = milestone

    async def save_milestone(self, milestone: GoalMilestone) -> None:
        self.milestones[milestone.id] = milestone

    async def delete_milestone(
        self, owner_user_id: UUID, goal_id: UUID, milestone_id: UUID
    ) -> None:
        item = await self.get_milestone(owner_user_id, goal_id, milestone_id)
        if item is not None:
            del self.milestones[item.id]
            self._delete_links(owner_user_id, EvidenceTargetKind.MILESTONE, (item.id,))

    async def get_development_item(
        self, owner_user_id: UUID, item_id: UUID, *, for_update: bool = False
    ) -> DevelopmentItem | None:
        del for_update
        item = self.development_items.get(item_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def list_development_items(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[DevelopmentItem]:
        values = sorted(
            [
                item
                for item in self.development_items.values()
                if item.owner_user_id == owner_user_id
            ],
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def add_development_item(self, item: DevelopmentItem) -> None:
        self.development_items[item.id] = item

    async def save_development_item(self, item: DevelopmentItem) -> None:
        self.development_items[item.id] = item

    async def delete_development_item(self, owner_user_id: UUID, item_id: UUID) -> None:
        item = await self.get_development_item(owner_user_id, item_id)
        if item is not None:
            del self.development_items[item.id]
            self._delete_links(owner_user_id, EvidenceTargetKind.DEVELOPMENT_ITEM, (item.id,))

    async def get_review(
        self, owner_user_id: UUID, review_id: UUID, *, for_update: bool = False
    ) -> CareerReview | None:
        del for_update
        review = self.reviews.get(review_id)
        return review if review is not None and review.owner_user_id == owner_user_id else None

    async def list_reviews(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerReview]:
        values = sorted(
            [item for item in self.reviews.values() if item.owner_user_id == owner_user_id],
            key=lambda item: (item.period_end, item.id),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def add_review(self, review: CareerReview, version: CareerReviewVersion) -> None:
        self.reviews[review.id] = review
        self.review_versions[version.id] = version

    async def save_review(self, review: CareerReview) -> None:
        self.reviews[review.id] = review

    async def add_review_version(self, version: CareerReviewVersion) -> None:
        self.review_versions[version.id] = version

    async def get_review_version(
        self, owner_user_id: UUID, version_id: UUID
    ) -> CareerReviewVersion | None:
        version = self.review_versions.get(version_id)
        if version is None or version.owner_user_id != owner_user_id:
            return None
        return version

    async def get_review_versions(
        self, owner_user_id: UUID, review_ids: tuple[UUID, ...]
    ) -> list[CareerReviewVersion]:
        self.query_counts["get_review_versions"] += 1
        return sorted(
            [
                item
                for item in self.review_versions.values()
                if item.owner_user_id == owner_user_id and item.review_id in review_ids
            ],
            key=lambda item: (str(item.review_id), item.version_number),
        )

    async def get_review_list_metadata(
        self,
        owner_user_id: UUID,
        review_ids: tuple[UUID, ...],
    ) -> list[ReviewListMetadata]:
        self.query_counts["get_review_list_metadata"] += 1
        result: list[ReviewListMetadata] = []
        for review_id in review_ids:
            review = await self.get_review(owner_user_id, review_id)
            if review is None:
                continue
            current = await self.get_review_version(
                owner_user_id,
                review.latest_version_id,
            )
            if current is None:
                continue
            result.append(
                ReviewListMetadata(
                    review_id=review.id,
                    current_version_id=current.id,
                    current_title=current.title,
                    history_count=sum(
                        version.owner_user_id == owner_user_id and version.review_id == review.id
                        for version in self.review_versions.values()
                    ),
                )
            )
        return result

    async def delete_review(self, owner_user_id: UUID, review_id: UUID) -> None:
        review = await self.get_review(owner_user_id, review_id)
        if review is None:
            return
        version_ids = [
            item.id
            for item in self.review_versions.values()
            if item.owner_user_id == owner_user_id and item.review_id == review_id
        ]
        for version_id in version_ids:
            del self.review_versions[version_id]
        self._delete_links(owner_user_id, EvidenceTargetKind.REVIEW_VERSION, tuple(version_ids))
        del self.reviews[review_id]

    async def list_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_ids: tuple[UUID, ...],
    ) -> list[CareerGrowthEvidenceLink]:
        self.query_counts["list_evidence_links"] += 1
        return sorted(
            [
                link
                for link in self.evidence_links.values()
                if link.owner_user_id == owner_user_id
                and link.target_kind is target_kind
                and link.target_id in target_ids
            ],
            key=lambda item: (str(item.target_id), str(item.id)),
        )

    async def replace_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_id: UUID,
        links: tuple[CareerGrowthEvidenceLink, ...],
    ) -> None:
        self._delete_links(owner_user_id, target_kind, (target_id,))
        self.evidence_links.update((link.id, link) for link in links)

    async def get_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> CareerGrowthIdempotencyRecord | None:
        return self.idempotency.get((owner_user_id, idempotency_key))

    async def add_idempotency(self, record: CareerGrowthIdempotencyRecord) -> None:
        self.idempotency[(record.owner_user_id, record.idempotency_key)] = record

    async def add_health_record(self, record: CareerHealthRecord) -> None:
        self.health_records[record.analysis.id] = record

    async def get_health_record(
        self, owner_user_id: UUID, analysis_id: UUID
    ) -> CareerHealthRecord | None:
        record = self.health_records.get(analysis_id)
        return (
            record
            if record is not None and record.analysis.owner_user_id == owner_user_id
            else None
        )

    async def list_health_records(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerHealthRecord]:
        values = sorted(
            [
                item
                for item in self.health_records.values()
                if item.analysis.owner_user_id == owner_user_id
            ],
            key=lambda item: (item.analysis.created_at, item.analysis.id),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return values[offset : offset + limit]

    async def list_health_summaries(
        self,
        owner_user_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[CareerHealthSummary]:
        records = await self.list_health_records(owner_user_id, after, limit)
        return [
            CareerHealthSummary(
                id=record.analysis.id,
                engine_version=record.analysis.engine_version,
                status=record.analysis.status,
                raw_score_basis_points=record.analysis.raw_score_basis_points,
                display_score=record.analysis.display_score,
                label=record.analysis.label,
                applicable_component_count=record.analysis.applicable_component_count,
                applicable_weight_basis_points=record.analysis.applicable_weight_basis_points,
                insufficient_reason=record.analysis.insufficient_reason,
                disclaimer=record.analysis.disclaimer,
                finding_count=len(record.findings),
                created_at=record.analysis.created_at,
            )
            for record in records
        ]

    async def count_health_records(self, owner_user_id: UUID) -> int:
        self.query_counts["count_health_records"] += 1
        return sum(
            record.analysis.owner_user_id == owner_user_id
            for record in self.health_records.values()
        )

    async def delete_health_record(self, owner_user_id: UUID, analysis_id: UUID) -> None:
        record = await self.get_health_record(owner_user_id, analysis_id)
        if record is not None:
            del self.health_records[record.analysis.id]

    async def add_audit(self, event: CareerGrowthAuditEvent) -> None:
        self.audits.append(event)

    async def commit(self) -> None:
        return None

    def _delete_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_ids: tuple[UUID, ...],
    ) -> None:
        self.evidence_links = {
            key: link
            for key, link in self.evidence_links.items()
            if not (
                link.owner_user_id == owner_user_id
                and link.target_kind is target_kind
                and link.target_id in target_ids
            )
        }
