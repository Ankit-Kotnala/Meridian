"""Async SQLAlchemy unit of work for Career Growth."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from types import TracebackType
from typing import Any, NoReturn, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.career_growth.application.models import (
    CareerHealthRecord,
    CareerHealthSummary,
    PageCursor,
    ReviewListMetadata,
)
from careeros.modules.career_growth.application.ports import CareerGrowthUnitOfWork
from careeros.modules.career_growth.domain import (
    CareerGoal,
    CareerGrowthAuditEvent,
    CareerGrowthConflict,
    CareerGrowthEvidenceLink,
    CareerGrowthIdempotencyConflict,
    CareerGrowthIdempotencyRecord,
    CareerHealthAnalysis,
    CareerHealthComponent,
    CareerHealthDimension,
    CareerHealthFinding,
    CareerHealthLabel,
    CareerHealthStatus,
    CareerReview,
    CareerReviewVersion,
    DevelopmentItem,
    DevelopmentKind,
    DevelopmentStatus,
    EvidenceTargetKind,
    FindingSeverity,
    GoalMilestone,
    GoalStatus,
    MilestoneStatus,
    ReviewCadence,
    ReviewVersionStatus,
)

from .models import (
    CareerGoalModel,
    CareerGrowthAuditEventModel,
    CareerGrowthEvidenceLinkModel,
    CareerGrowthIdempotencyModel,
    CareerHealthAnalysisModel,
    CareerHealthComponentModel,
    CareerHealthFindingModel,
    CareerReviewModel,
    CareerReviewVersionModel,
    DevelopmentItemModel,
    GoalMilestoneModel,
)


class SqlAlchemyCareerGrowthUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyCareerGrowthUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("career growth unit of work is not active")
        return self._session

    async def lock_owner(self, owner_user_id: UUID) -> None:
        """Use a transaction-scoped advisory lock for quotas and idempotency."""

        lock_key = int.from_bytes(
            hashlib.sha256(b"career-growth:" + owner_user_id.bytes).digest()[:8],
            byteorder="big",
            signed=True,
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def get_goal(
        self, owner_user_id: UUID, goal_id: UUID, *, for_update: bool = False
    ) -> CareerGoal | None:
        statement = select(CareerGoalModel).where(
            CareerGoalModel.owner_user_id == owner_user_id,
            CareerGoalModel.id == goal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _goal(model) if model is not None else None

    async def list_goals(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerGoal]:
        models = (
            await self.session.scalars(
                select(CareerGoalModel)
                .where(CareerGoalModel.owner_user_id == owner_user_id)
                .order_by(CareerGoalModel.updated_at.desc(), CareerGoalModel.id.desc())
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_goal(model) for model in models]

    async def add_goal(self, goal: CareerGoal) -> None:
        self.session.add(CareerGoalModel(**_goal_values(goal)))
        await self._flush()

    async def save_goal(self, goal: CareerGoal) -> None:
        await self._execute(
            update(CareerGoalModel)
            .where(
                CareerGoalModel.owner_user_id == goal.owner_user_id,
                CareerGoalModel.id == goal.id,
            )
            .values(**_goal_values(goal, include_identity=False))
        )

    async def delete_goal(self, owner_user_id: UUID, goal_id: UUID) -> None:
        milestone_ids = list(
            (
                await self.session.scalars(
                    select(GoalMilestoneModel.id).where(
                        GoalMilestoneModel.owner_user_id == owner_user_id,
                        GoalMilestoneModel.goal_id == goal_id,
                    )
                )
            ).all()
        )
        await self._delete_links(owner_user_id, EvidenceTargetKind.MILESTONE, milestone_ids)
        await self._delete_links(owner_user_id, EvidenceTargetKind.GOAL, [goal_id])
        await self._execute(
            delete(CareerGoalModel).where(
                CareerGoalModel.owner_user_id == owner_user_id,
                CareerGoalModel.id == goal_id,
            )
        )

    async def get_milestone(
        self,
        owner_user_id: UUID,
        goal_id: UUID,
        milestone_id: UUID,
        *,
        for_update: bool = False,
    ) -> GoalMilestone | None:
        statement = select(GoalMilestoneModel).where(
            GoalMilestoneModel.owner_user_id == owner_user_id,
            GoalMilestoneModel.goal_id == goal_id,
            GoalMilestoneModel.id == milestone_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _milestone(model) if model is not None else None

    async def list_milestones(
        self, owner_user_id: UUID, goal_ids: tuple[UUID, ...]
    ) -> list[GoalMilestone]:
        if not goal_ids:
            return []
        models = (
            await self.session.scalars(
                select(GoalMilestoneModel)
                .where(
                    GoalMilestoneModel.owner_user_id == owner_user_id,
                    GoalMilestoneModel.goal_id.in_(goal_ids),
                )
                .order_by(
                    GoalMilestoneModel.goal_id,
                    GoalMilestoneModel.target_date.asc().nulls_last(),
                    GoalMilestoneModel.id,
                )
            )
        ).all()
        return [_milestone(model) for model in models]

    async def count_milestones(self, owner_user_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count(GoalMilestoneModel.id)).where(
                GoalMilestoneModel.owner_user_id == owner_user_id
            )
        )
        return int(value or 0)

    async def count_milestones_by_goal(
        self,
        owner_user_id: UUID,
        goal_ids: tuple[UUID, ...],
    ) -> dict[UUID, int]:
        if not goal_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    GoalMilestoneModel.goal_id,
                    func.count(GoalMilestoneModel.id),
                )
                .where(
                    GoalMilestoneModel.owner_user_id == owner_user_id,
                    GoalMilestoneModel.goal_id.in_(goal_ids),
                )
                .group_by(GoalMilestoneModel.goal_id)
            )
        ).all()
        counts = {goal_id: 0 for goal_id in goal_ids}
        counts.update({goal_id: int(count) for goal_id, count in rows})
        return counts

    async def add_milestone(self, milestone: GoalMilestone) -> None:
        self.session.add(GoalMilestoneModel(**_milestone_values(milestone)))
        await self._flush()

    async def save_milestone(self, milestone: GoalMilestone) -> None:
        await self._execute(
            update(GoalMilestoneModel)
            .where(
                GoalMilestoneModel.owner_user_id == milestone.owner_user_id,
                GoalMilestoneModel.goal_id == milestone.goal_id,
                GoalMilestoneModel.id == milestone.id,
            )
            .values(**_milestone_values(milestone, include_identity=False))
        )

    async def delete_milestone(
        self, owner_user_id: UUID, goal_id: UUID, milestone_id: UUID
    ) -> None:
        await self._delete_links(owner_user_id, EvidenceTargetKind.MILESTONE, [milestone_id])
        await self._execute(
            delete(GoalMilestoneModel).where(
                GoalMilestoneModel.owner_user_id == owner_user_id,
                GoalMilestoneModel.goal_id == goal_id,
                GoalMilestoneModel.id == milestone_id,
            )
        )

    async def get_development_item(
        self, owner_user_id: UUID, item_id: UUID, *, for_update: bool = False
    ) -> DevelopmentItem | None:
        statement = select(DevelopmentItemModel).where(
            DevelopmentItemModel.owner_user_id == owner_user_id,
            DevelopmentItemModel.id == item_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _development_item(model) if model is not None else None

    async def list_development_items(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[DevelopmentItem]:
        models = (
            await self.session.scalars(
                select(DevelopmentItemModel)
                .where(DevelopmentItemModel.owner_user_id == owner_user_id)
                .order_by(
                    DevelopmentItemModel.updated_at.desc(),
                    DevelopmentItemModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_development_item(model) for model in models]

    async def add_development_item(self, item: DevelopmentItem) -> None:
        self.session.add(DevelopmentItemModel(**_development_values(item)))
        await self._flush()

    async def save_development_item(self, item: DevelopmentItem) -> None:
        await self._execute(
            update(DevelopmentItemModel)
            .where(
                DevelopmentItemModel.owner_user_id == item.owner_user_id,
                DevelopmentItemModel.id == item.id,
            )
            .values(**_development_values(item, include_identity=False))
        )

    async def delete_development_item(self, owner_user_id: UUID, item_id: UUID) -> None:
        await self._delete_links(owner_user_id, EvidenceTargetKind.DEVELOPMENT_ITEM, [item_id])
        await self._execute(
            delete(DevelopmentItemModel).where(
                DevelopmentItemModel.owner_user_id == owner_user_id,
                DevelopmentItemModel.id == item_id,
            )
        )

    async def get_review(
        self, owner_user_id: UUID, review_id: UUID, *, for_update: bool = False
    ) -> CareerReview | None:
        statement = select(CareerReviewModel).where(
            CareerReviewModel.owner_user_id == owner_user_id,
            CareerReviewModel.id == review_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _review(model) if model is not None else None

    async def list_reviews(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerReview]:
        models = (
            await self.session.scalars(
                select(CareerReviewModel)
                .where(CareerReviewModel.owner_user_id == owner_user_id)
                .order_by(CareerReviewModel.period_end.desc(), CareerReviewModel.id.desc())
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_review(model) for model in models]

    async def add_review(self, review: CareerReview, version: CareerReviewVersion) -> None:
        if (
            version.owner_user_id != review.owner_user_id
            or version.review_id != review.id
            or review.latest_version_id != version.id
        ):
            raise CareerGrowthConflict("initial review version does not match its review")
        self.session.add(CareerReviewModel(**_review_values(review)))
        await self._flush()
        self.session.add(CareerReviewVersionModel(**_review_version_values(version)))
        await self._flush()

    async def save_review(self, review: CareerReview) -> None:
        await self._execute(
            update(CareerReviewModel)
            .where(
                CareerReviewModel.owner_user_id == review.owner_user_id,
                CareerReviewModel.id == review.id,
            )
            .values(**_review_values(review, include_identity=False))
        )

    async def add_review_version(self, version: CareerReviewVersion) -> None:
        self.session.add(CareerReviewVersionModel(**_review_version_values(version)))
        await self._flush()

    async def get_review_version(
        self, owner_user_id: UUID, version_id: UUID
    ) -> CareerReviewVersion | None:
        model = await self.session.scalar(
            select(CareerReviewVersionModel).where(
                CareerReviewVersionModel.owner_user_id == owner_user_id,
                CareerReviewVersionModel.id == version_id,
            )
        )
        return _review_version(model) if model is not None else None

    async def get_review_versions(
        self, owner_user_id: UUID, review_ids: tuple[UUID, ...]
    ) -> list[CareerReviewVersion]:
        if not review_ids:
            return []
        models = (
            await self.session.scalars(
                select(CareerReviewVersionModel)
                .where(
                    CareerReviewVersionModel.owner_user_id == owner_user_id,
                    CareerReviewVersionModel.review_id.in_(review_ids),
                )
                .order_by(
                    CareerReviewVersionModel.review_id,
                    CareerReviewVersionModel.version_number,
                )
            )
        ).all()
        return [_review_version(model) for model in models]

    async def get_review_list_metadata(
        self,
        owner_user_id: UUID,
        review_ids: tuple[UUID, ...],
    ) -> list[ReviewListMetadata]:
        if not review_ids:
            return []
        history_count = (
            select(func.count(CareerReviewVersionModel.id))
            .where(
                CareerReviewVersionModel.owner_user_id == owner_user_id,
                CareerReviewVersionModel.review_id == CareerReviewModel.id,
            )
            .correlate(CareerReviewModel)
            .scalar_subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    CareerReviewModel.id.label("review_id"),
                    CareerReviewVersionModel.id.label("current_version_id"),
                    CareerReviewVersionModel.title.label("current_title"),
                    history_count.label("history_count"),
                )
                .join(
                    CareerReviewVersionModel,
                    (CareerReviewVersionModel.owner_user_id == CareerReviewModel.owner_user_id)
                    & (CareerReviewVersionModel.review_id == CareerReviewModel.id)
                    & (CareerReviewVersionModel.id == CareerReviewModel.latest_version_id),
                )
                .where(
                    CareerReviewModel.owner_user_id == owner_user_id,
                    CareerReviewModel.id.in_(review_ids),
                )
            )
        ).all()
        return [
            ReviewListMetadata(
                review_id=row.review_id,
                current_version_id=row.current_version_id,
                current_title=row.current_title,
                history_count=int(row.history_count),
            )
            for row in rows
        ]

    async def delete_review(self, owner_user_id: UUID, review_id: UUID) -> None:
        version_ids = list(
            (
                await self.session.scalars(
                    select(CareerReviewVersionModel.id).where(
                        CareerReviewVersionModel.owner_user_id == owner_user_id,
                        CareerReviewVersionModel.review_id == review_id,
                    )
                )
            ).all()
        )
        await self._delete_links(owner_user_id, EvidenceTargetKind.REVIEW_VERSION, version_ids)
        await self._execute(
            delete(CareerReviewModel).where(
                CareerReviewModel.owner_user_id == owner_user_id,
                CareerReviewModel.id == review_id,
            )
        )

    async def list_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_ids: tuple[UUID, ...],
    ) -> list[CareerGrowthEvidenceLink]:
        if not target_ids:
            return []
        models = (
            await self.session.scalars(
                select(CareerGrowthEvidenceLinkModel)
                .where(
                    CareerGrowthEvidenceLinkModel.owner_user_id == owner_user_id,
                    CareerGrowthEvidenceLinkModel.target_kind == target_kind.value,
                    CareerGrowthEvidenceLinkModel.target_id.in_(target_ids),
                )
                .order_by(
                    CareerGrowthEvidenceLinkModel.target_id,
                    CareerGrowthEvidenceLinkModel.id,
                )
            )
        ).all()
        return [_evidence_link(model) for model in models]

    async def replace_evidence_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_id: UUID,
        links: tuple[CareerGrowthEvidenceLink, ...],
    ) -> None:
        if any(
            link.owner_user_id != owner_user_id
            or link.target_kind is not target_kind
            or link.target_id != target_id
            for link in links
        ):
            raise CareerGrowthConflict("evidence links do not match their owned target")
        if len({link.evidence_id for link in links}) != len(links):
            raise CareerGrowthConflict("evidence links contain duplicates")
        await self._delete_links(owner_user_id, target_kind, [target_id])
        self.session.add_all(_evidence_link_model(link) for link in links)
        await self._flush()

    async def get_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> CareerGrowthIdempotencyRecord | None:
        model = await self.session.scalar(
            select(CareerGrowthIdempotencyModel).where(
                CareerGrowthIdempotencyModel.owner_user_id == owner_user_id,
                CareerGrowthIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_idempotency(self, record: CareerGrowthIdempotencyRecord) -> None:
        self.session.add(_idempotency_model(record))
        await self._flush()

    async def add_health_record(self, record: CareerHealthRecord) -> None:
        _validate_health_ownership(record)
        self.session.add(_health_analysis_model(record.analysis))
        await self._flush()
        self.session.add_all(_health_component_model(item) for item in record.components)
        self.session.add_all(_health_finding_model(item) for item in record.findings)
        await self._flush()

    async def get_health_record(
        self, owner_user_id: UUID, analysis_id: UUID
    ) -> CareerHealthRecord | None:
        model = await self.session.scalar(
            select(CareerHealthAnalysisModel).where(
                CareerHealthAnalysisModel.owner_user_id == owner_user_id,
                CareerHealthAnalysisModel.id == analysis_id,
            )
        )
        records = await self._health_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def list_health_records(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[CareerHealthRecord]:
        models = (
            await self.session.scalars(
                select(CareerHealthAnalysisModel)
                .where(CareerHealthAnalysisModel.owner_user_id == owner_user_id)
                .order_by(
                    CareerHealthAnalysisModel.created_at.desc(),
                    CareerHealthAnalysisModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return await self._health_records(owner_user_id, list(models))

    async def list_health_summaries(
        self,
        owner_user_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[CareerHealthSummary]:
        finding_count = (
            select(func.count(CareerHealthFindingModel.id))
            .where(
                CareerHealthFindingModel.owner_user_id == owner_user_id,
                CareerHealthFindingModel.analysis_id == CareerHealthAnalysisModel.id,
            )
            .correlate(CareerHealthAnalysisModel)
            .scalar_subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    CareerHealthAnalysisModel.id,
                    CareerHealthAnalysisModel.engine_version,
                    CareerHealthAnalysisModel.status,
                    CareerHealthAnalysisModel.raw_score_basis_points,
                    CareerHealthAnalysisModel.display_score,
                    CareerHealthAnalysisModel.label,
                    CareerHealthAnalysisModel.applicable_component_count,
                    CareerHealthAnalysisModel.applicable_weight_basis_points,
                    CareerHealthAnalysisModel.insufficient_reason,
                    CareerHealthAnalysisModel.disclaimer,
                    finding_count.label("finding_count"),
                    CareerHealthAnalysisModel.created_at,
                )
                .where(CareerHealthAnalysisModel.owner_user_id == owner_user_id)
                .order_by(
                    CareerHealthAnalysisModel.created_at.desc(),
                    CareerHealthAnalysisModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [
            CareerHealthSummary(
                id=row.id,
                engine_version=row.engine_version,
                status=CareerHealthStatus(row.status),
                raw_score_basis_points=row.raw_score_basis_points,
                display_score=row.display_score,
                label=CareerHealthLabel(row.label),
                applicable_component_count=row.applicable_component_count,
                applicable_weight_basis_points=row.applicable_weight_basis_points,
                insufficient_reason=row.insufficient_reason,
                disclaimer=row.disclaimer,
                finding_count=row.finding_count,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def count_health_records(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(CareerHealthAnalysisModel.id)).where(
                    CareerHealthAnalysisModel.owner_user_id == owner_user_id
                )
            )
            or 0
        )

    async def delete_health_record(self, owner_user_id: UUID, analysis_id: UUID) -> None:
        await self._execute(
            delete(CareerHealthAnalysisModel).where(
                CareerHealthAnalysisModel.owner_user_id == owner_user_id,
                CareerHealthAnalysisModel.id == analysis_id,
            )
        )

    async def add_audit(self, event: CareerGrowthAuditEvent) -> None:
        self.session.add(_audit_model(event))

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _health_records(
        self, owner_user_id: UUID, analyses: list[CareerHealthAnalysisModel]
    ) -> list[CareerHealthRecord]:
        if not analyses:
            return []
        ids = [analysis.id for analysis in analyses]
        component_models = (
            await self.session.scalars(
                select(CareerHealthComponentModel)
                .where(
                    CareerHealthComponentModel.owner_user_id == owner_user_id,
                    CareerHealthComponentModel.analysis_id.in_(ids),
                )
                .order_by(
                    CareerHealthComponentModel.analysis_id,
                    CareerHealthComponentModel.id,
                )
            )
        ).all()
        finding_models = (
            await self.session.scalars(
                select(CareerHealthFindingModel)
                .where(
                    CareerHealthFindingModel.owner_user_id == owner_user_id,
                    CareerHealthFindingModel.analysis_id.in_(ids),
                )
                .order_by(
                    CareerHealthFindingModel.analysis_id,
                    CareerHealthFindingModel.id,
                )
            )
        ).all()
        components: defaultdict[UUID, list[CareerHealthComponentModel]] = defaultdict(list)
        findings: defaultdict[UUID, list[CareerHealthFindingModel]] = defaultdict(list)
        for component_model in component_models:
            components[component_model.analysis_id].append(component_model)
        for finding_model in finding_models:
            findings[finding_model.analysis_id].append(finding_model)
        return [
            CareerHealthRecord(
                analysis=_health_analysis(analysis),
                components=tuple(_health_component(model) for model in components[analysis.id]),
                findings=tuple(_health_finding(model) for model in findings[analysis.id]),
            )
            for analysis in analyses
        ]

    async def _delete_links(
        self,
        owner_user_id: UUID,
        target_kind: EvidenceTargetKind,
        target_ids: list[UUID],
    ) -> None:
        if not target_ids:
            return
        await self._execute(
            delete(CareerGrowthEvidenceLinkModel).where(
                CareerGrowthEvidenceLinkModel.owner_user_id == owner_user_id,
                CareerGrowthEvidenceLinkModel.target_kind == target_kind.value,
                CareerGrowthEvidenceLinkModel.target_id.in_(target_ids),
            )
        )

    async def _execute(self, statement: Any) -> None:
        try:
            await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyCareerGrowthUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> CareerGrowthUnitOfWork:
        return SqlAlchemyCareerGrowthUnitOfWork(self._database)


def _goal(model: CareerGoalModel) -> CareerGoal:
    return CareerGoal(
        id=model.id,
        owner_user_id=model.owner_user_id,
        title=model.title,
        description=model.description,
        status=GoalStatus(model.status),
        target_date=model.target_date,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _goal_values(goal: CareerGoal, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "title": goal.title,
        "description": goal.description,
        "status": goal.status.value,
        "target_date": goal.target_date,
        "version": goal.version,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }
    if include_identity:
        values.update(id=goal.id, owner_user_id=goal.owner_user_id)
    return values


def _milestone(model: GoalMilestoneModel) -> GoalMilestone:
    return GoalMilestone(
        id=model.id,
        owner_user_id=model.owner_user_id,
        goal_id=model.goal_id,
        title=model.title,
        status=MilestoneStatus(model.status),
        target_date=model.target_date,
        completed_at=model.completed_at,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _milestone_values(
    milestone: GoalMilestone, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "goal_id": milestone.goal_id,
        "title": milestone.title,
        "status": milestone.status.value,
        "target_date": milestone.target_date,
        "completed_at": milestone.completed_at,
        "version": milestone.version,
        "created_at": milestone.created_at,
        "updated_at": milestone.updated_at,
    }
    if include_identity:
        values.update(id=milestone.id, owner_user_id=milestone.owner_user_id)
    return values


def _development_item(model: DevelopmentItemModel) -> DevelopmentItem:
    return DevelopmentItem(
        id=model.id,
        owner_user_id=model.owner_user_id,
        kind=DevelopmentKind(model.kind),
        title=model.title,
        description=model.description,
        status=DevelopmentStatus(model.status),
        target_date=model.target_date,
        completed_at=model.completed_at,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _development_values(
    item: DevelopmentItem, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "kind": item.kind.value,
        "title": item.title,
        "description": item.description,
        "status": item.status.value,
        "target_date": item.target_date,
        "completed_at": item.completed_at,
        "version": item.version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
    if include_identity:
        values.update(id=item.id, owner_user_id=item.owner_user_id)
    return values


def _review(model: CareerReviewModel) -> CareerReview:
    return CareerReview(
        id=model.id,
        owner_user_id=model.owner_user_id,
        cadence=ReviewCadence(model.cadence),
        period_start=model.period_start,
        period_end=model.period_end,
        latest_version_id=model.latest_version_id,
        latest_version_number=model.latest_version_number,
        latest_status=ReviewVersionStatus(model.latest_status),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _review_values(review: CareerReview, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "cadence": review.cadence.value,
        "period_start": review.period_start,
        "period_end": review.period_end,
        "latest_version_id": review.latest_version_id,
        "latest_version_number": review.latest_version_number,
        "latest_status": review.latest_status.value,
        "version": review.version,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }
    if include_identity:
        values.update(id=review.id, owner_user_id=review.owner_user_id)
    return values


def _review_version(model: CareerReviewVersionModel) -> CareerReviewVersion:
    return CareerReviewVersion(
        id=model.id,
        owner_user_id=model.owner_user_id,
        review_id=model.review_id,
        version_number=model.version_number,
        status=ReviewVersionStatus(model.status),
        title=model.title,
        summary=model.summary,
        achievements=model.achievements,
        growth_areas=model.growth_areas,
        next_focus=model.next_focus,
        change_reason=model.change_reason,
        material_change=model.material_change,
        supersedes_version_id=model.supersedes_version_id,
        content_sha256=model.content_sha256.hex(),
        created_at=model.created_at,
    )


def _review_version_values(version: CareerReviewVersion) -> dict[str, object]:
    return {
        "id": version.id,
        "owner_user_id": version.owner_user_id,
        "review_id": version.review_id,
        "version_number": version.version_number,
        "status": version.status.value,
        "title": version.title,
        "summary": version.summary,
        "achievements": version.achievements,
        "growth_areas": version.growth_areas,
        "next_focus": version.next_focus,
        "change_reason": version.change_reason,
        "material_change": version.material_change,
        "supersedes_version_id": version.supersedes_version_id,
        "content_sha256": bytes.fromhex(version.content_sha256),
        "created_at": version.created_at,
    }


def _evidence_link(model: CareerGrowthEvidenceLinkModel) -> CareerGrowthEvidenceLink:
    return CareerGrowthEvidenceLink(
        id=model.id,
        owner_user_id=model.owner_user_id,
        target_kind=EvidenceTargetKind(model.target_kind),
        target_id=model.target_id,
        evidence_id=model.evidence_id,
        evidence_revision_id=model.evidence_revision_id,
        revision_number=model.revision_number,
        statement_sha256=model.statement_sha256.hex(),
        evidence_revised_at=model.evidence_revised_at,
        created_at=model.created_at,
    )


def _evidence_link_model(
    link: CareerGrowthEvidenceLink,
) -> CareerGrowthEvidenceLinkModel:
    return CareerGrowthEvidenceLinkModel(
        id=link.id,
        owner_user_id=link.owner_user_id,
        target_kind=link.target_kind.value,
        target_id=link.target_id,
        evidence_id=link.evidence_id,
        evidence_revision_id=link.evidence_revision_id,
        revision_number=link.revision_number,
        statement_sha256=bytes.fromhex(link.statement_sha256),
        evidence_revised_at=link.evidence_revised_at,
        created_at=link.created_at,
    )


def _idempotency(
    model: CareerGrowthIdempotencyModel,
) -> CareerGrowthIdempotencyRecord:
    return CareerGrowthIdempotencyRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint.hex(),
        operation=model.operation,
        result_id=model.result_id,
        created_at=model.created_at,
    )


def _idempotency_model(
    record: CareerGrowthIdempotencyRecord,
) -> CareerGrowthIdempotencyModel:
    return CareerGrowthIdempotencyModel(
        id=record.id,
        owner_user_id=record.owner_user_id,
        idempotency_key=record.idempotency_key,
        request_fingerprint=bytes.fromhex(record.request_fingerprint),
        operation=record.operation,
        result_id=record.result_id,
        created_at=record.created_at,
    )


def _health_analysis(model: CareerHealthAnalysisModel) -> CareerHealthAnalysis:
    return CareerHealthAnalysis(
        id=model.id,
        owner_user_id=model.owner_user_id,
        engine_version=model.engine_version,
        configuration_version=model.configuration_version,
        feature_schema_version=model.feature_schema_version,
        input_snapshot=dict(model.input_snapshot),
        configuration_snapshot=dict(model.configuration_snapshot),
        formula_snapshot=dict(model.formula_snapshot),
        snapshot_sha256=model.snapshot_sha256,
        status=CareerHealthStatus(model.status),
        raw_score_basis_points=model.raw_score_basis_points,
        display_score=model.display_score,
        label=CareerHealthLabel(model.label),
        applicable_component_count=model.applicable_component_count,
        applicable_weight_basis_points=model.applicable_weight_basis_points,
        insufficient_reason=model.insufficient_reason,
        disclaimer=model.disclaimer,
        created_at=model.created_at,
    )


def _health_analysis_model(
    analysis: CareerHealthAnalysis,
) -> CareerHealthAnalysisModel:
    return CareerHealthAnalysisModel(
        id=analysis.id,
        owner_user_id=analysis.owner_user_id,
        engine_version=analysis.engine_version,
        configuration_version=analysis.configuration_version,
        feature_schema_version=analysis.feature_schema_version,
        input_snapshot=analysis.input_snapshot,
        configuration_snapshot=analysis.configuration_snapshot,
        formula_snapshot=analysis.formula_snapshot,
        snapshot_sha256=analysis.snapshot_sha256,
        status=analysis.status.value,
        raw_score_basis_points=analysis.raw_score_basis_points,
        display_score=analysis.display_score,
        label=analysis.label.value,
        applicable_component_count=analysis.applicable_component_count,
        applicable_weight_basis_points=analysis.applicable_weight_basis_points,
        insufficient_reason=analysis.insufficient_reason,
        disclaimer=analysis.disclaimer,
        created_at=analysis.created_at,
    )


def _health_component(model: CareerHealthComponentModel) -> CareerHealthComponent:
    return CareerHealthComponent(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        dimension=CareerHealthDimension(model.dimension),
        configured_weight_basis_points=model.configured_weight_basis_points,
        applicable=model.applicable,
        score_basis_points=model.score_basis_points,
        contribution_basis_points=model.contribution_basis_points,
        explanation=model.explanation,
    )


def _health_component_model(
    component: CareerHealthComponent,
) -> CareerHealthComponentModel:
    return CareerHealthComponentModel(
        id=component.id,
        owner_user_id=component.owner_user_id,
        analysis_id=component.analysis_id,
        dimension=component.dimension.value,
        configured_weight_basis_points=component.configured_weight_basis_points,
        applicable=component.applicable,
        score_basis_points=component.score_basis_points,
        contribution_basis_points=component.contribution_basis_points,
        explanation=component.explanation,
    )


def _health_finding(model: CareerHealthFindingModel) -> CareerHealthFinding:
    return CareerHealthFinding(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        code=model.code,
        severity=FindingSeverity(model.severity),
        message=model.message,
    )


def _health_finding_model(finding: CareerHealthFinding) -> CareerHealthFindingModel:
    return CareerHealthFindingModel(
        id=finding.id,
        owner_user_id=finding.owner_user_id,
        analysis_id=finding.analysis_id,
        code=finding.code,
        severity=finding.severity.value,
        message=finding.message,
    )


def _audit_model(event: CareerGrowthAuditEvent) -> CareerGrowthAuditEventModel:
    return CareerGrowthAuditEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        action=event.action.value,
        target_kind=event.target_kind,
        target_id=event.target_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        details=dict(event.details),
        created_at=event.created_at,
    )


def _validate_health_ownership(record: CareerHealthRecord) -> None:
    owner_user_id = record.analysis.owner_user_id
    analysis_id = record.analysis.id
    if any(
        component.owner_user_id != owner_user_id or component.analysis_id != analysis_id
        for component in record.components
    ) or any(
        finding.owner_user_id != owner_user_id or finding.analysis_id != analysis_id
        for finding in record.findings
    ):
        raise CareerGrowthConflict("career health record ownership does not match")
    if len({item.dimension for item in record.components}) != len(record.components):
        raise CareerGrowthConflict("career health components contain duplicates")
    if len({item.code for item in record.findings}) != len(record.findings):
        raise CareerGrowthConflict("career health findings contain duplicates")


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    constraint_name = _constraint_name(exc)
    if "idempotency" in constraint_name:
        raise CareerGrowthIdempotencyConflict from exc
    raise CareerGrowthConflict from exc


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        direct_name = getattr(current, "constraint_name", None)
        if isinstance(direct_name, str):
            return direct_name
        diag = getattr(current, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if isinstance(name, str):
            return name
        current = cast(
            BaseException | None,
            getattr(current, "__cause__", None) or getattr(current, "__context__", None),
        )
    return ""
