"""Async SQLAlchemy persistence for the Phase 8 application workspace."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime
from types import TracebackType
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.application_workspace.application import (
    ApplicationAnalyticsCursor,
    ApplicationAnalyticsSourceState,
    ApplicationCalendarEntry,
    ApplicationFilter,
    ApplicationMilestones,
    ApplicationPackView,
    ApplicationReference,
    ApplicationSummary,
    PageCursor,
)
from rezumi.modules.application_workspace.domain import (
    ApplicationAuditEvent,
    ApplicationClaimEvidenceLink,
    ApplicationConsistencyFinding,
    ApplicationConsistencySeverity,
    ApplicationContact,
    ApplicationDocument,
    ApplicationDocumentClaim,
    ApplicationDocumentKind,
    ApplicationDocumentStatus,
    ApplicationEvent,
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationIdempotencyRecord,
    ApplicationNote,
    ApplicationPack,
    ApplicationPackStatus,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationRequirementSupport,
    ApplicationStage,
    ApplicationTask,
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceUnavailable,
    ConsistencyStatus,
    OutcomeStatus,
    ReferralStatus,
)

from .models import (
    ApplicationAuditEventModel,
    ApplicationDocumentModel,
    ApplicationEventModel,
    ApplicationIdempotencyModel,
    ApplicationNoteModel,
    ApplicationPackModel,
    ApplicationRecordModel,
    ApplicationTaskModel,
)

_MANUAL_EVENT_KINDS = (
    ApplicationEventKind.INTERVIEW.value,
    ApplicationEventKind.CONTACT.value,
    ApplicationEventKind.CUSTOM.value,
)


class SqlAlchemyApplicationWorkspaceUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyApplicationWorkspaceUnitOfWork:
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
            raise RuntimeError("application workspace unit of work is not active")
        return self._session

    async def lock_owner_quota(self, owner_user_id: UUID) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    _quota_lock_key("owner", owner_user_id),
                )
            )
        )

    async def lock_application_quota(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    _quota_lock_key(
                        "application",
                        owner_user_id,
                        application_id,
                    )
                )
            )
        )

    async def list_application_summaries(
        self,
        owner_user_id: UUID,
        filter_by: ApplicationFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationSummary]:
        statement = self._active_applications(owner_user_id)
        if filter_by.stage is not None:
            statement = statement.where(ApplicationRecordModel.stage == filter_by.stage.value)
        if filter_by.outcome is not None:
            statement = statement.where(
                ApplicationRecordModel.outcome_status == filter_by.outcome.value
            )
        if filter_by.source is not None:
            statement = statement.where(ApplicationRecordModel.source == filter_by.source)
        if filter_by.industry is not None:
            statement = statement.where(ApplicationRecordModel.industry == filter_by.industry)
        if filter_by.query is not None:
            pattern = _pattern(filter_by.query)
            statement = statement.where(
                or_(
                    ApplicationRecordModel.job_title.ilike(pattern, escape="\\"),
                    ApplicationRecordModel.company.ilike(pattern, escape="\\"),
                    ApplicationRecordModel.location.ilike(pattern, escape="\\"),
                    ApplicationRecordModel.resume_title.ilike(pattern, escape="\\"),
                )
            )
        order = (
            (
                ApplicationRecordModel.application_deadline.asc().nulls_last(),
                ApplicationRecordModel.id.asc(),
            )
            if filter_by.sort == "deadline_asc"
            else (
                ApplicationRecordModel.updated_at.desc(),
                ApplicationRecordModel.id.desc(),
            )
        )
        models = (
            await self.session.scalars(
                statement.order_by(*order)
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        if not models:
            return []
        application_ids = [model.id for model in models]
        task_counts = await self._task_counts(owner_user_id, application_ids)
        note_counts = await self._child_counts(
            ApplicationNoteModel,
            owner_user_id,
            application_ids,
        )
        event_counts = await self._child_counts(
            ApplicationEventModel,
            owner_user_id,
            application_ids,
        )
        pack_counts = await self._child_counts(
            ApplicationPackModel,
            owner_user_id,
            application_ids,
        )
        return [
            ApplicationSummary(
                application=_application(model),
                task_count=task_counts[model.id][0],
                open_task_count=task_counts[model.id][1],
                note_count=note_counts[model.id],
                event_count=event_counts[model.id],
                pack_count=pack_counts[model.id],
            )
            for model in models
        ]

    async def count_applications(self, owner_user_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ApplicationRecordModel)
            .where(
                ApplicationRecordModel.owner_user_id == owner_user_id,
            )
        )
        return int(count or 0)

    async def count_manual_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ApplicationEventModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationEventModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationEventModel.application_id),
            )
            .where(
                ApplicationEventModel.owner_user_id == owner_user_id,
                ApplicationEventModel.application_id == application_id,
                ApplicationEventModel.event_kind.in_(_MANUAL_EVENT_KINDS),
            )
        )
        return int(count or 0)

    async def count_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return await self._count_child(
            ApplicationTaskModel,
            owner_user_id,
            application_id,
        )

    async def count_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return await self._count_child(
            ApplicationNoteModel,
            owner_user_id,
            application_id,
        )

    async def count_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return await self._count_child(
            ApplicationPackModel,
            owner_user_id,
            application_id,
        )

    async def get_application_summary(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationSummary | None:
        task_count = (
            select(func.count(ApplicationTaskModel.id))
            .where(
                ApplicationTaskModel.owner_user_id == owner_user_id,
                ApplicationTaskModel.application_id == application_id,
            )
            .scalar_subquery()
        )
        open_task_count = (
            select(func.count(ApplicationTaskModel.id))
            .where(
                ApplicationTaskModel.owner_user_id == owner_user_id,
                ApplicationTaskModel.application_id == application_id,
                ApplicationTaskModel.completed_at.is_(None),
            )
            .scalar_subquery()
        )
        note_count = (
            select(func.count(ApplicationNoteModel.id))
            .where(
                ApplicationNoteModel.owner_user_id == owner_user_id,
                ApplicationNoteModel.application_id == application_id,
            )
            .scalar_subquery()
        )
        event_count = (
            select(func.count(ApplicationEventModel.id))
            .where(
                ApplicationEventModel.owner_user_id == owner_user_id,
                ApplicationEventModel.application_id == application_id,
            )
            .scalar_subquery()
        )
        pack_count = (
            select(func.count(ApplicationPackModel.id))
            .where(
                ApplicationPackModel.owner_user_id == owner_user_id,
                ApplicationPackModel.application_id == application_id,
            )
            .scalar_subquery()
        )
        row = (
            await self.session.execute(
                select(
                    ApplicationRecordModel,
                    task_count,
                    open_task_count,
                    note_count,
                    event_count,
                    pack_count,
                ).where(
                    ApplicationRecordModel.owner_user_id == owner_user_id,
                    ApplicationRecordModel.id == application_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        model, tasks, open_tasks, notes, events, packs = row
        return ApplicationSummary(
            application=_application(model),
            task_count=int(tasks),
            open_task_count=int(open_tasks),
            note_count=int(notes),
            event_count=int(events),
            pack_count=int(packs),
        )

    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference | None:
        row = (
            await self.session.execute(
                select(
                    ApplicationRecordModel.id,
                    ApplicationRecordModel.stage,
                ).where(
                    ApplicationRecordModel.owner_user_id == owner_user_id,
                    ApplicationRecordModel.id == application_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return ApplicationReference(
            application_id=row.id,
            stage=ApplicationStage(row.stage),
        )

    async def list_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationTask]:
        models = (
            await self.session.scalars(
                select(ApplicationTaskModel)
                .join(
                    ApplicationRecordModel,
                    (ApplicationRecordModel.owner_user_id == ApplicationTaskModel.owner_user_id)
                    & (ApplicationRecordModel.id == ApplicationTaskModel.application_id),
                )
                .where(
                    ApplicationTaskModel.owner_user_id == owner_user_id,
                    ApplicationTaskModel.application_id == application_id,
                )
                .order_by(
                    ApplicationTaskModel.due_at.asc().nulls_last(),
                    ApplicationTaskModel.created_at.asc(),
                    ApplicationTaskModel.id.asc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_task(model) for model in models]

    async def list_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationNote]:
        models = (
            await self.session.scalars(
                select(ApplicationNoteModel)
                .join(
                    ApplicationRecordModel,
                    (ApplicationRecordModel.owner_user_id == ApplicationNoteModel.owner_user_id)
                    & (ApplicationRecordModel.id == ApplicationNoteModel.application_id),
                )
                .where(
                    ApplicationNoteModel.owner_user_id == owner_user_id,
                    ApplicationNoteModel.application_id == application_id,
                )
                .order_by(
                    ApplicationNoteModel.created_at.desc(),
                    ApplicationNoteModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_note(model) for model in models]

    async def list_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        before_occurred_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> list[ApplicationEvent]:
        if (before_occurred_at is None) != (before_id is None):
            raise ValueError("event cursor fields must be provided together")
        statement = (
            select(ApplicationEventModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationEventModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationEventModel.application_id),
            )
            .where(
                ApplicationEventModel.owner_user_id == owner_user_id,
                ApplicationEventModel.application_id == application_id,
            )
        )
        if before_occurred_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    ApplicationEventModel.occurred_at < before_occurred_at,
                    and_(
                        ApplicationEventModel.occurred_at == before_occurred_at,
                        ApplicationEventModel.id < before_id,
                    ),
                )
            )
        models = (
            await self.session.scalars(
                statement.order_by(
                    ApplicationEventModel.occurred_at.desc(),
                    ApplicationEventModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_event(model) for model in models]

    async def list_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationPack]:
        models = (
            await self.session.scalars(
                select(ApplicationPackModel)
                .join(
                    ApplicationRecordModel,
                    (ApplicationRecordModel.owner_user_id == ApplicationPackModel.owner_user_id)
                    & (ApplicationRecordModel.id == ApplicationPackModel.application_id),
                )
                .where(
                    ApplicationPackModel.owner_user_id == owner_user_id,
                    ApplicationPackModel.application_id == application_id,
                )
                .order_by(
                    ApplicationPackModel.created_at.desc(),
                    ApplicationPackModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_pack(model) for model in models]

    async def list_application_records(
        self,
        owner_user_id: UUID,
        after: ApplicationAnalyticsCursor | None,
        limit: int,
    ) -> list[ApplicationRecord]:
        statement = self._active_applications(owner_user_id)
        if after is not None:
            statement = statement.where(
                or_(
                    ApplicationRecordModel.created_at > after.created_at,
                    and_(
                        ApplicationRecordModel.created_at == after.created_at,
                        ApplicationRecordModel.id > after.application_id,
                    ),
                )
            )
        models = (
            await self.session.scalars(
                statement.order_by(
                    ApplicationRecordModel.created_at.asc(),
                    ApplicationRecordModel.id.asc(),
                ).limit(limit)
            )
        ).all()
        return [_application(model) for model in models]

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> ApplicationAnalyticsSourceState:
        application_state = (
            await self.session.execute(
                select(
                    func.count(ApplicationRecordModel.id),
                    func.coalesce(func.sum(ApplicationRecordModel.version), 0),
                    func.max(ApplicationRecordModel.updated_at),
                ).where(
                    ApplicationRecordModel.owner_user_id == owner_user_id,
                )
            )
        ).one()
        event_state = (
            await self.session.execute(
                select(
                    func.count(ApplicationEventModel.id),
                    func.max(ApplicationEventModel.created_at),
                )
                .join(
                    ApplicationRecordModel,
                    (ApplicationRecordModel.owner_user_id == ApplicationEventModel.owner_user_id)
                    & (ApplicationRecordModel.id == ApplicationEventModel.application_id),
                )
                .where(
                    ApplicationEventModel.owner_user_id == owner_user_id,
                )
            )
        ).one()
        return ApplicationAnalyticsSourceState(
            application_count=int(application_state[0] or 0),
            application_version_sum=int(application_state[1] or 0),
            event_count=int(event_state[0] or 0),
            max_application_updated_at=application_state[2],
            max_event_created_at=event_state[1],
        )

    async def list_application_milestones(
        self,
        owner_user_id: UUID,
        application_ids: tuple[UUID, ...],
    ) -> dict[UUID, ApplicationMilestones]:
        if not application_ids:
            return {}
        created_stage = ApplicationEventModel.metadata_["stage"].as_string()
        changed_stage = ApplicationEventModel.metadata_["to_stage"].as_string()

        def stage_seen(*stages: str) -> Any:
            return or_(
                and_(
                    ApplicationEventModel.event_kind == ApplicationEventKind.CREATED.value,
                    created_stage.in_(stages),
                ),
                and_(
                    ApplicationEventModel.event_kind == ApplicationEventKind.STAGE_CHANGED.value,
                    changed_stage.in_(stages),
                ),
            )

        interview_seen = or_(
            stage_seen(ApplicationStage.INTERVIEW.value),
            ApplicationEventModel.event_kind == ApplicationEventKind.INTERVIEW.value,
        )
        response_seen = or_(
            stage_seen(
                ApplicationStage.RECRUITER_SCREEN.value,
                ApplicationStage.INTERVIEW.value,
                ApplicationStage.ASSESSMENT.value,
                ApplicationStage.OFFER.value,
                ApplicationStage.REJECTED.value,
            ),
            ApplicationEventModel.event_kind == ApplicationEventKind.INTERVIEW.value,
        )
        outcome_seen = or_(
            stage_seen(
                ApplicationStage.OFFER.value,
                ApplicationStage.REJECTED.value,
                ApplicationStage.WITHDRAWN.value,
            ),
            ApplicationEventModel.event_kind == ApplicationEventKind.OUTCOME_RECORDED.value,
        )
        occurred_at = ApplicationEventModel.occurred_at
        rows = (
            await self.session.execute(
                select(
                    ApplicationEventModel.application_id,
                    func.min(occurred_at).filter(stage_seen(ApplicationStage.APPLIED.value)),
                    func.min(occurred_at).filter(response_seen),
                    func.min(occurred_at).filter(interview_seen),
                    func.min(occurred_at).filter(stage_seen(ApplicationStage.OFFER.value)),
                    func.max(occurred_at).filter(outcome_seen),
                )
                .where(
                    ApplicationEventModel.owner_user_id == owner_user_id,
                    ApplicationEventModel.application_id.in_(application_ids),
                )
                .group_by(ApplicationEventModel.application_id)
            )
        ).all()
        return {
            application_id: ApplicationMilestones(
                first_applied_at=first_applied_at,
                first_response_at=first_response_at,
                first_interview_at=first_interview_at,
                first_offer_at=first_offer_at,
                outcome_at=outcome_at,
            )
            for (
                application_id,
                first_applied_at,
                first_response_at,
                first_interview_at,
                first_offer_at,
                outcome_at,
            ) in rows
        }

    async def list_calendar_entries(
        self,
        owner_user_id: UUID,
        start: date,
        end: date,
        limit: int,
    ) -> list[ApplicationCalendarEntry]:
        deadline_models = (
            await self.session.scalars(
                self._active_applications(owner_user_id)
                .where(ApplicationRecordModel.application_deadline.between(start, end))
                .order_by(
                    ApplicationRecordModel.application_deadline,
                    ApplicationRecordModel.id,
                )
                .limit(limit)
            )
        ).all()
        follow_up_models = (
            await self.session.scalars(
                self._active_applications(owner_user_id)
                .where(ApplicationRecordModel.follow_up_at.between(start, end))
                .order_by(
                    ApplicationRecordModel.follow_up_at,
                    ApplicationRecordModel.id,
                )
                .limit(limit)
            )
        ).all()
        task_models = (
            await self.session.scalars(
                select(ApplicationTaskModel)
                .join(
                    ApplicationRecordModel,
                    (ApplicationRecordModel.owner_user_id == ApplicationTaskModel.owner_user_id)
                    & (ApplicationRecordModel.id == ApplicationTaskModel.application_id),
                )
                .where(
                    ApplicationTaskModel.owner_user_id == owner_user_id,
                    ApplicationTaskModel.due_at.between(start, end),
                )
                .order_by(
                    ApplicationTaskModel.due_at,
                    ApplicationTaskModel.id,
                )
                .limit(limit)
            )
        ).all()
        entries = [
            ApplicationCalendarEntry(
                id=_calendar_id(model.id, "deadline"),
                application_id=model.id,
                kind="application_deadline",
                title=f"{model.job_title} application deadline",
                on_date=model.application_deadline,
                completed=False,
            )
            for model in deadline_models
            if model.application_deadline is not None
        ]
        entries.extend(
            ApplicationCalendarEntry(
                id=_calendar_id(model.id, "follow_up"),
                application_id=model.id,
                kind="follow_up",
                title=f"Follow up on {model.job_title}",
                on_date=model.follow_up_at,
                completed=False,
            )
            for model in follow_up_models
            if model.follow_up_at is not None
        )
        entries.extend(
            ApplicationCalendarEntry(
                id=model.id,
                application_id=model.application_id,
                kind="task",
                title=model.title,
                on_date=model.due_at,
                completed=model.completed_at is not None,
            )
            for model in task_models
            if model.due_at is not None
        )
        entries.sort(key=lambda item: (item.on_date, item.kind, str(item.id)))
        return entries[:limit]

    async def get_application_record(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        for_update: bool = False,
    ) -> ApplicationRecord | None:
        model = await self._get_application_model(
            owner_user_id,
            application_id,
            for_update=for_update,
        )
        return _application(model) if model is not None else None

    async def add_application(self, record: ApplicationRecord) -> None:
        self.session.add(_application_model(record))
        await self._flush()

    async def save_application(self, record: ApplicationRecord) -> None:
        await self._execute(
            update(ApplicationRecordModel)
            .where(
                ApplicationRecordModel.owner_user_id == record.owner_user_id,
                ApplicationRecordModel.id == record.id,
            )
            .values(**_application_values(record, include_identity=False))
        )

    async def delete_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None:
        await self._execute(
            delete(ApplicationRecordModel).where(
                ApplicationRecordModel.owner_user_id == owner_user_id,
                ApplicationRecordModel.id == application_id,
            )
        )

    async def add_task(self, task: ApplicationTask) -> None:
        self.session.add(_task_model(task))
        await self._flush()

    async def get_task(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        task_id: UUID,
        *,
        for_update: bool = False,
    ) -> ApplicationTask | None:
        statement = (
            select(ApplicationTaskModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationTaskModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationTaskModel.application_id),
            )
            .where(
                ApplicationTaskModel.owner_user_id == owner_user_id,
                ApplicationTaskModel.application_id == application_id,
                ApplicationTaskModel.id == task_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ApplicationTaskModel)
        model = await self.session.scalar(statement)
        return _task(model) if model is not None else None

    async def save_task(self, task: ApplicationTask) -> None:
        await self._execute(
            update(ApplicationTaskModel)
            .where(
                ApplicationTaskModel.owner_user_id == task.owner_user_id,
                ApplicationTaskModel.application_id == task.application_id,
                ApplicationTaskModel.id == task.id,
            )
            .values(**_task_values(task, include_identity=False))
        )

    async def add_note(self, note: ApplicationNote) -> None:
        self.session.add(_note_model(note))
        await self._flush()

    async def get_note(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        note_id: UUID,
    ) -> ApplicationNote | None:
        model = await self.session.scalar(
            select(ApplicationNoteModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationNoteModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationNoteModel.application_id),
            )
            .where(
                ApplicationNoteModel.owner_user_id == owner_user_id,
                ApplicationNoteModel.application_id == application_id,
                ApplicationNoteModel.id == note_id,
            )
        )
        return _note(model) if model is not None else None

    async def add_event(self, event: ApplicationEvent) -> None:
        self.session.add(_event_model(event))
        await self._flush()

    async def get_event(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        event_id: UUID,
    ) -> ApplicationEvent | None:
        model = await self.session.scalar(
            select(ApplicationEventModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationEventModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationEventModel.application_id),
            )
            .where(
                ApplicationEventModel.owner_user_id == owner_user_id,
                ApplicationEventModel.application_id == application_id,
                ApplicationEventModel.id == event_id,
            )
        )
        return _event(model) if model is not None else None

    async def add_pack(
        self,
        pack: ApplicationPack,
        documents: tuple[ApplicationDocument, ...],
    ) -> None:
        self.session.add(_pack_model(pack))
        await self._flush()
        self.session.add_all(_document_model(document) for document in documents)
        await self._flush()

    async def get_pack(
        self,
        owner_user_id: UUID,
        pack_id: UUID,
    ) -> ApplicationPackView | None:
        model = await self.session.scalar(
            select(ApplicationPackModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationPackModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationPackModel.application_id),
            )
            .where(
                ApplicationPackModel.owner_user_id == owner_user_id,
                ApplicationPackModel.id == pack_id,
            )
        )
        return await self._pack_view(model) if model is not None else None

    async def find_pack_by_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> ApplicationPackView | None:
        model = await self.session.scalar(
            select(ApplicationPackModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationPackModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationPackModel.application_id),
            )
            .where(
                ApplicationPackModel.owner_user_id == owner_user_id,
                ApplicationPackModel.idempotency_key == idempotency_key,
            )
        )
        return await self._pack_view(model) if model is not None else None

    async def get_document(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        document_id: UUID,
    ) -> ApplicationDocument | None:
        model = await self.session.scalar(
            select(ApplicationDocumentModel)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == ApplicationDocumentModel.owner_user_id)
                & (ApplicationRecordModel.id == ApplicationDocumentModel.application_id),
            )
            .where(
                ApplicationDocumentModel.owner_user_id == owner_user_id,
                ApplicationDocumentModel.application_id == application_id,
                ApplicationDocumentModel.id == document_id,
            )
        )
        return _document(model) if model is not None else None

    async def save_document(self, document: ApplicationDocument) -> None:
        await self._execute(
            update(ApplicationDocumentModel)
            .where(
                ApplicationDocumentModel.owner_user_id == document.owner_user_id,
                ApplicationDocumentModel.application_id == document.application_id,
                ApplicationDocumentModel.id == document.id,
            )
            .values(**_document_values(document, include_identity=False))
        )

    async def add_idempotency(self, record: ApplicationIdempotencyRecord) -> None:
        self.session.add(_idempotency_model(record))
        await self._flush()

    async def find_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> ApplicationIdempotencyRecord | None:
        model = await self.session.scalar(
            select(ApplicationIdempotencyModel).where(
                ApplicationIdempotencyModel.owner_user_id == owner_user_id,
                ApplicationIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_audit(self, event: ApplicationAuditEvent) -> None:
        self.session.add(_audit_model(event))
        await self._flush()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    def _active_applications(self, owner_user_id: UUID) -> Any:
        return select(ApplicationRecordModel).where(
            ApplicationRecordModel.owner_user_id == owner_user_id,
        )

    async def _get_application_model(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        for_update: bool,
    ) -> ApplicationRecordModel | None:
        statement = self._active_applications(owner_user_id).where(
            ApplicationRecordModel.id == application_id
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(
            ApplicationRecordModel | None,
            await self.session.scalar(statement),
        )

    async def _pack_view(
        self,
        model: ApplicationPackModel,
    ) -> ApplicationPackView:
        documents = await self._documents_for_packs(
            model.owner_user_id,
            [model.id],
        )
        return ApplicationPackView(
            pack=_pack(model),
            documents=tuple(_document(document) for document in documents.get(model.id, [])),
        )

    async def _documents_for_packs(
        self,
        owner_user_id: UUID,
        pack_ids: list[UUID],
    ) -> dict[UUID, list[ApplicationDocumentModel]]:
        grouped: dict[UUID, list[ApplicationDocumentModel]] = defaultdict(list)
        if not pack_ids:
            return grouped
        documents = (
            await self.session.scalars(
                select(ApplicationDocumentModel)
                .where(
                    ApplicationDocumentModel.owner_user_id == owner_user_id,
                    ApplicationDocumentModel.pack_id.in_(pack_ids),
                    ApplicationDocumentModel.deleted_at.is_(None),
                )
                .order_by(
                    ApplicationDocumentModel.pack_id,
                    ApplicationDocumentModel.kind,
                    ApplicationDocumentModel.id,
                )
                .limit(len(pack_ids) * len(tuple(ApplicationDocumentKind)))
            )
        ).all()
        for document in documents:
            grouped[document.pack_id].append(document)
        return grouped

    async def _task_counts(
        self,
        owner_user_id: UUID,
        application_ids: list[UUID],
    ) -> defaultdict[UUID, tuple[int, int]]:
        rows = (
            await self.session.execute(
                select(
                    ApplicationTaskModel.application_id,
                    func.count(ApplicationTaskModel.id),
                    func.count(ApplicationTaskModel.id).filter(
                        ApplicationTaskModel.completed_at.is_(None)
                    ),
                )
                .where(
                    ApplicationTaskModel.owner_user_id == owner_user_id,
                    ApplicationTaskModel.application_id.in_(application_ids),
                )
                .group_by(ApplicationTaskModel.application_id)
            )
        ).all()
        result: defaultdict[UUID, tuple[int, int]] = defaultdict(lambda: (0, 0))
        for application_id, total, opened in rows:
            result[application_id] = (int(total), int(opened))
        return result

    async def _count_child(
        self,
        model: Any,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(model)
            .join(
                ApplicationRecordModel,
                (ApplicationRecordModel.owner_user_id == model.owner_user_id)
                & (ApplicationRecordModel.id == model.application_id),
            )
            .where(
                model.owner_user_id == owner_user_id,
                model.application_id == application_id,
            )
        )
        return int(count or 0)

    async def _child_counts(
        self,
        model: Any,
        owner_user_id: UUID,
        application_ids: list[UUID],
    ) -> defaultdict[UUID, int]:
        rows = (
            await self.session.execute(
                select(model.application_id, func.count(model.id))
                .where(
                    model.owner_user_id == owner_user_id,
                    model.application_id.in_(application_ids),
                )
                .group_by(model.application_id)
            )
        ).all()
        result: defaultdict[UUID, int] = defaultdict(int)
        for application_id, count in rows:
            result[application_id] = int(count)
        return result

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


class SqlAlchemyApplicationWorkspaceUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyApplicationWorkspaceUnitOfWork:
        return SqlAlchemyApplicationWorkspaceUnitOfWork(self._database)


def _pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _quota_lock_key(namespace: str, *values: UUID) -> int:
    payload = ":".join((namespace, *(str(value) for value in values)))
    return int.from_bytes(
        hashlib.sha256(payload.encode("ascii")).digest()[:8],
        "big",
        signed=True,
    )


def _calendar_id(application_id: UUID, kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"rezumi:{application_id}:{kind}")


def _application_model(record: ApplicationRecord) -> ApplicationRecordModel:
    return ApplicationRecordModel(**_application_values(record))


def _application_values(
    record: ApplicationRecord,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "job_id": record.job_id,
        "job_version": record.job_version,
        "job_title": record.job_title,
        "company": record.company,
        "location": record.location,
        "job_analysis_id": record.job_analysis_id,
        "job_source_sha256": record.job_source_sha256,
        "job_requirements": [
            _requirement_payload(requirement) for requirement in record.job_requirements
        ],
        "requirement_support": [
            _requirement_support_payload(support) for support in record.requirement_support
        ],
        "resume_id": record.resume_id,
        "resume_version_id": record.resume_version_id,
        "resume_version_number": record.resume_version_number,
        "resume_title": record.resume_title,
        "resume_evidence_ids": [str(value) for value in record.resume_evidence_ids],
        "evidence_pins": [_evidence_pin_payload(pin) for pin in record.evidence_pins],
        "resume_claims": [_claim_payload(claim) for claim in record.resume_claims],
        "source": record.source,
        "industry": record.industry,
        "stage": record.stage.value,
        "application_deadline": record.application_deadline,
        "follow_up_at": record.follow_up_at,
        "contacts": [_contact_payload(contact) for contact in record.contacts],
        "referral_status": record.referral_status.value,
        "outcome_status": record.outcome_status.value,
        "rejection_reason": record.rejection_reason,
        "offer_summary": record.offer_summary,
        "version": record.version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    if include_identity:
        values.update({"id": record.id, "owner_user_id": record.owner_user_id})
    return values


def _application(model: ApplicationRecordModel) -> ApplicationRecord:
    return ApplicationRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        job_version=model.job_version,
        job_title=model.job_title,
        company=model.company,
        location=model.location,
        job_analysis_id=model.job_analysis_id,
        job_source_sha256=model.job_source_sha256,
        job_requirements=tuple(_requirement(value) for value in model.job_requirements),
        requirement_support=tuple(
            _requirement_support(value) for value in model.requirement_support
        ),
        resume_id=model.resume_id,
        resume_version_id=model.resume_version_id,
        resume_version_number=model.resume_version_number,
        resume_title=model.resume_title,
        resume_evidence_ids=tuple(UUID(value) for value in model.resume_evidence_ids),
        evidence_pins=tuple(_evidence_pin(value) for value in model.evidence_pins),
        resume_claims=tuple(_claim(value) for value in model.resume_claims),
        source=model.source,
        industry=model.industry,
        stage=ApplicationStage(model.stage),
        application_deadline=model.application_deadline,
        follow_up_at=model.follow_up_at,
        contacts=tuple(_contact(value) for value in model.contacts),
        referral_status=ReferralStatus(model.referral_status),
        outcome_status=OutcomeStatus(model.outcome_status),
        rejection_reason=model.rejection_reason,
        offer_summary=model.offer_summary,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _task_model(task: ApplicationTask) -> ApplicationTaskModel:
    return ApplicationTaskModel(**_task_values(task))


def _task_values(
    task: ApplicationTask,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "title": task.title,
        "due_at": task.due_at,
        "completed_at": task.completed_at,
        "version": task.version,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if include_identity:
        values.update(
            {
                "id": task.id,
                "owner_user_id": task.owner_user_id,
                "application_id": task.application_id,
            }
        )
    return values


def _task(model: ApplicationTaskModel) -> ApplicationTask:
    return ApplicationTask(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        title=model.title,
        due_at=model.due_at,
        completed_at=model.completed_at,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _note_model(note: ApplicationNote) -> ApplicationNoteModel:
    return ApplicationNoteModel(
        id=note.id,
        owner_user_id=note.owner_user_id,
        application_id=note.application_id,
        body=note.body,
        created_at=note.created_at,
    )


def _note(model: ApplicationNoteModel) -> ApplicationNote:
    return ApplicationNote(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        body=model.body,
        created_at=model.created_at,
    )


def _event_model(event: ApplicationEvent) -> ApplicationEventModel:
    return ApplicationEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        application_id=event.application_id,
        event_kind=event.event_kind.value,
        occurred_at=event.occurred_at,
        title=event.title,
        description=event.description,
        metadata_=event.metadata,
        created_at=event.created_at,
    )


def _event(model: ApplicationEventModel) -> ApplicationEvent:
    return ApplicationEvent(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        event_kind=ApplicationEventKind(model.event_kind),
        occurred_at=model.occurred_at,
        title=model.title,
        description=model.description,
        metadata=model.metadata_,
        created_at=model.created_at,
    )


def _pack_model(pack: ApplicationPack) -> ApplicationPackModel:
    return ApplicationPackModel(
        id=pack.id,
        owner_user_id=pack.owner_user_id,
        application_id=pack.application_id,
        job_id=pack.job_id,
        job_version=pack.job_version,
        resume_version_id=pack.resume_version_id,
        resume_version_number=pack.resume_version_number,
        application_version=pack.application_version,
        evidence_revision_ids=[str(value) for value in pack.evidence_revision_ids],
        requirement_ids=[str(value) for value in pack.requirement_ids],
        status=pack.status.value,
        consistency_status=pack.consistency_status.value,
        consistency_findings=[_finding_payload(finding) for finding in pack.consistency_findings],
        idempotency_key=pack.idempotency_key,
        idempotency_fingerprint=pack.idempotency_fingerprint,
        created_at=pack.created_at,
    )


def _pack(model: ApplicationPackModel) -> ApplicationPack:
    return ApplicationPack(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        job_id=model.job_id,
        job_version=model.job_version,
        resume_version_id=model.resume_version_id,
        resume_version_number=model.resume_version_number,
        application_version=model.application_version,
        evidence_revision_ids=tuple(UUID(value) for value in model.evidence_revision_ids),
        requirement_ids=tuple(UUID(value) for value in model.requirement_ids),
        status=ApplicationPackStatus(model.status),
        consistency_status=ConsistencyStatus(model.consistency_status),
        consistency_findings=tuple(_finding(value) for value in model.consistency_findings),
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        created_at=model.created_at,
    )


def _document_model(document: ApplicationDocument) -> ApplicationDocumentModel:
    return ApplicationDocumentModel(**_document_values(document))


def _document_values(
    document: ApplicationDocument,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "kind": document.kind.value,
        "title": document.title,
        "body": document.body,
        "source_evidence_ids": [str(value) for value in document.source_evidence_ids],
        "source_requirement_ids": [str(value) for value in document.source_requirement_ids],
        "claims": [_claim_payload(claim) for claim in document.claims],
        "status": document.status.value,
        "consistency_status": document.consistency_status.value,
        "consistency_findings": [
            _finding_payload(finding) for finding in document.consistency_findings
        ],
        "content_sha256": document.content_sha256,
        "created_at": document.created_at,
        "deleted_at": document.deleted_at,
    }
    if include_identity:
        values.update(
            {
                "id": document.id,
                "owner_user_id": document.owner_user_id,
                "application_id": document.application_id,
                "pack_id": document.pack_id,
            }
        )
    return values


def _document(model: ApplicationDocumentModel) -> ApplicationDocument:
    return ApplicationDocument(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        pack_id=model.pack_id,
        kind=ApplicationDocumentKind(model.kind),
        title=model.title,
        body=model.body,
        source_evidence_ids=tuple(UUID(value) for value in model.source_evidence_ids),
        source_requirement_ids=tuple(UUID(value) for value in model.source_requirement_ids),
        claims=tuple(_claim(value) for value in model.claims),
        status=ApplicationDocumentStatus(model.status),
        consistency_status=ConsistencyStatus(model.consistency_status),
        consistency_findings=tuple(_finding(value) for value in model.consistency_findings),
        content_sha256=model.content_sha256,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
    )


def _idempotency_model(
    record: ApplicationIdempotencyRecord,
) -> ApplicationIdempotencyModel:
    return ApplicationIdempotencyModel(
        id=record.id,
        owner_user_id=record.owner_user_id,
        idempotency_key=record.idempotency_key,
        request_fingerprint=record.request_fingerprint,
        target_kind=record.target_kind,
        target_id=record.target_id,
        response_kind=record.response_kind,
        response_id=record.response_id,
        created_at=record.created_at,
    )


def _idempotency(
    model: ApplicationIdempotencyModel,
) -> ApplicationIdempotencyRecord:
    return ApplicationIdempotencyRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        target_kind=model.target_kind,
        target_id=model.target_id,
        response_kind=model.response_kind,
        response_id=model.response_id,
        created_at=model.created_at,
    )


def _audit_model(event: ApplicationAuditEvent) -> ApplicationAuditEventModel:
    return ApplicationAuditEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        action=event.action.value,
        target_kind=event.target_kind,
        target_id=event.target_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        metadata_=event.metadata,
        created_at=event.created_at,
    )


def _requirement_payload(
    requirement: ApplicationRequirementSnapshot,
) -> dict[str, Any]:
    return {
        "id": str(requirement.id),
        "type": requirement.requirement_type,
        "importance": requirement.importance,
        "text": requirement.text,
        "sourceStart": requirement.source_start,
        "sourceEnd": requirement.source_end,
    }


def _requirement(payload: dict[str, Any]) -> ApplicationRequirementSnapshot:
    return ApplicationRequirementSnapshot(
        id=UUID(str(payload["id"])),
        requirement_type=str(payload["type"]),
        importance=str(payload["importance"]),
        text=str(payload["text"]),
        source_start=int(payload["sourceStart"]),
        source_end=int(payload["sourceEnd"]),
    )


def _requirement_support_payload(
    support: ApplicationRequirementSupport,
) -> dict[str, str]:
    return {
        "analysisId": str(support.analysis_id),
        "requirementId": str(support.requirement_id),
        "evidenceId": str(support.evidence_id),
    }


def _requirement_support(
    payload: dict[str, str],
) -> ApplicationRequirementSupport:
    return ApplicationRequirementSupport(
        analysis_id=UUID(payload["analysisId"]),
        requirement_id=UUID(payload["requirementId"]),
        evidence_id=UUID(payload["evidenceId"]),
    )


def _evidence_pin_payload(pin: ApplicationEvidencePin) -> dict[str, Any]:
    return {
        "evidenceId": str(pin.evidence_id),
        "evidenceRevisionId": str(pin.evidence_revision_id),
        "revisionNumber": pin.revision_number,
        "statement": pin.statement,
        "statementSha256": pin.statement_sha256,
        "strength": pin.strength,
        "hasNumericClaim": pin.has_numeric_claim,
    }


def _evidence_pin(payload: dict[str, Any]) -> ApplicationEvidencePin:
    return ApplicationEvidencePin(
        evidence_id=UUID(str(payload["evidenceId"])),
        evidence_revision_id=UUID(str(payload["evidenceRevisionId"])),
        revision_number=int(payload["revisionNumber"]),
        statement=str(payload["statement"]),
        statement_sha256=str(payload["statementSha256"]),
        strength=str(payload["strength"]),
        has_numeric_claim=bool(payload["hasNumericClaim"]),
    )


def _claim_payload(claim: ApplicationDocumentClaim) -> dict[str, Any]:
    return {
        "id": str(claim.id),
        "text": claim.text,
        "evidenceLinks": [
            {
                "evidenceId": str(link.evidence_id),
                "evidenceRevisionId": str(link.evidence_revision_id),
            }
            for link in claim.evidence_links
        ],
        "requirementIds": [str(value) for value in claim.requirement_ids],
    }


def _claim(payload: dict[str, Any]) -> ApplicationDocumentClaim:
    return ApplicationDocumentClaim(
        id=UUID(str(payload["id"])),
        text=str(payload["text"]),
        evidence_links=tuple(
            ApplicationClaimEvidenceLink(
                evidence_id=UUID(str(value["evidenceId"])),
                evidence_revision_id=UUID(str(value["evidenceRevisionId"])),
            )
            for value in payload["evidenceLinks"]
        ),
        requirement_ids=tuple(UUID(str(value)) for value in payload["requirementIds"]),
    )


def _contact_payload(contact: ApplicationContact) -> dict[str, str | None]:
    return {
        "name": contact.name,
        "role": contact.role,
        "email": contact.email,
        "url": contact.url,
    }


def _contact(payload: dict[str, Any]) -> ApplicationContact:
    return ApplicationContact(
        name=str(payload["name"]),
        role=str(payload["role"]) if payload.get("role") is not None else None,
        email=str(payload["email"]) if payload.get("email") is not None else None,
        url=str(payload["url"]) if payload.get("url") is not None else None,
    )


def _finding_payload(
    finding: ApplicationConsistencyFinding,
) -> dict[str, str | None]:
    return {
        "code": finding.code,
        "severity": finding.severity.value,
        "message": finding.message,
        "claimId": str(finding.claim_id) if finding.claim_id is not None else None,
    }


def _finding(payload: dict[str, Any]) -> ApplicationConsistencyFinding:
    claim_id = payload.get("claimId")
    return ApplicationConsistencyFinding(
        code=str(payload["code"]),
        severity=ApplicationConsistencySeverity(str(payload["severity"])),
        message=str(payload["message"]),
        claim_id=UUID(str(claim_id)) if claim_id else None,
    )


def _raise_integrity(exc: IntegrityError) -> None:
    original = getattr(exc, "orig", None)
    code = getattr(original, "sqlstate", None)
    if code in {"40001", "40P01"}:
        raise ApplicationWorkspaceUnavailable from exc
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint in {
        "uq_application_packs_owner_idempotency",
        "uq_application_workspace_idempotency_owner_key",
    }:
        raise ApplicationWorkspaceIdempotencyConflict from exc
    raise ApplicationWorkspaceConflict("application workspace persistence conflict") from exc
