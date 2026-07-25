"""Async SQLAlchemy unit of work for Interview Prep."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from types import TracebackType
from typing import Any, NoReturn
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.interview_prep.application.models import PageCursor, StoryFilter
from careeros.modules.interview_prep.application.ports import InterviewPrepUnitOfWork
from careeros.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewAuditEvent,
    InterviewIdempotencyRecord,
    InterviewPrepConflict,
    InterviewPrepIdempotencyConflict,
    InterviewPrepUnavailable,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionKind,
    InterviewSessionNote,
    QuestionKind,
    SessionContextClaim,
    SessionContextRequirement,
    SessionContextSnapshot,
    SessionNoteKind,
    StarStory,
    StarStoryReplaySnapshot,
    StoryClaimPin,
    StoryField,
    StoryOrigin,
    StoryStatus,
)

from .models import (
    FollowUpDraftModel,
    InterviewAuditEventModel,
    InterviewIdempotencyModel,
    InterviewQuestionModel,
    InterviewSessionModel,
    InterviewSessionNoteModel,
    StarStoryModel,
    StoryClaimPinModel,
)


class SqlAlchemyInterviewPrepUnitOfWork:
    """One owner-scoped transaction per Interview Prep use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyInterviewPrepUnitOfWork:
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
            raise RuntimeError("Interview Prep unit of work is not active")
        return self._session

    async def lock_owner(self, owner_user_id: UUID) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(_owner_lock_key(owner_user_id)))
        )

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_xact_lock(_idempotency_lock_key(owner_user_id, idempotency_key))
            )
        )

    async def count_stories(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(StarStoryModel)
                .where(StarStoryModel.owner_user_id == owner_user_id)
            )
            or 0
        )

    async def add_story(self, story: StarStory) -> None:
        self.session.add(StarStoryModel(**_story_values(story)))
        await self._flush()
        self.session.add_all(_story_pin_model(story, pin) for pin in story.claim_pins)
        await self._flush()

    async def save_story(self, story: StarStory) -> None:
        await self._execute(
            update(StarStoryModel)
            .where(
                StarStoryModel.owner_user_id == story.owner_user_id,
                StarStoryModel.id == story.id,
            )
            .values(**_story_values(story, include_identity=False))
        )
        await self._execute(
            delete(StoryClaimPinModel).where(
                StoryClaimPinModel.owner_user_id == story.owner_user_id,
                StoryClaimPinModel.story_id == story.id,
            )
        )
        self.session.add_all(_story_pin_model(story, pin) for pin in story.claim_pins)
        await self._flush()

    async def get_story(
        self, owner_user_id: UUID, story_id: UUID, *, for_update: bool = False
    ) -> StarStory | None:
        statement = select(StarStoryModel).where(
            StarStoryModel.owner_user_id == owner_user_id,
            StarStoryModel.id == story_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        pins = await self._story_pins(owner_user_id, (model.id,))
        return _story(model, pins[model.id])

    async def list_stories(
        self,
        owner_user_id: UUID,
        filter_by: StoryFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[StarStory]:
        statement = select(StarStoryModel).where(StarStoryModel.owner_user_id == owner_user_id)
        if filter_by.application_id is not None:
            statement = statement.where(StarStoryModel.application_id == filter_by.application_id)
        if filter_by.status is not None:
            statement = statement.where(StarStoryModel.status == filter_by.status.value)
        models = list(
            (
                await self.session.scalars(
                    statement.order_by(StarStoryModel.updated_at.desc(), StarStoryModel.id.desc())
                    .offset(after.offset if after else 0)
                    .limit(limit)
                )
            ).all()
        )
        pins = await self._story_pins(owner_user_id, tuple(model.id for model in models))
        return [_story(model, pins[model.id]) for model in models]

    async def delete_story(self, owner_user_id: UUID, story_id: UUID) -> None:
        await self._execute(
            delete(StarStoryModel).where(
                StarStoryModel.owner_user_id == owner_user_id,
                StarStoryModel.id == story_id,
            )
        )

    async def redact_story_replay_snapshot(self, owner_user_id: UUID, story_id: UUID) -> None:
        await self._execute(
            update(InterviewIdempotencyModel)
            .where(
                InterviewIdempotencyModel.owner_user_id == owner_user_id,
                InterviewIdempotencyModel.resource_kind == "star_story",
                InterviewIdempotencyModel.resource_id == story_id,
            )
            .values(response_snapshot=None)
        )

    async def count_sessions(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(InterviewSessionModel)
                .where(InterviewSessionModel.owner_user_id == owner_user_id)
            )
            or 0
        )

    async def add_session(self, session: InterviewSession) -> None:
        self.session.add(InterviewSessionModel(**_session_values(session)))
        await self._flush()

    async def save_session(self, session: InterviewSession) -> None:
        await self._execute(
            update(InterviewSessionModel)
            .where(
                InterviewSessionModel.owner_user_id == session.owner_user_id,
                InterviewSessionModel.id == session.id,
            )
            .values(
                title=session.title,
                kind=session.kind.value,
                scheduled_at=session.scheduled_at,
                version=session.version,
                updated_at=session.updated_at,
            )
        )

    async def get_session(
        self, owner_user_id: UUID, session_id: UUID, *, for_update: bool = False
    ) -> InterviewSession | None:
        statement = select(InterviewSessionModel).where(
            InterviewSessionModel.owner_user_id == owner_user_id,
            InterviewSessionModel.id == session_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _session(model) if model is not None else None

    async def list_sessions(
        self,
        owner_user_id: UUID,
        application_id: UUID | None,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSession]:
        statement = select(InterviewSessionModel).where(
            InterviewSessionModel.owner_user_id == owner_user_id
        )
        if application_id is not None:
            statement = statement.where(InterviewSessionModel.application_id == application_id)
        models = (
            await self.session.scalars(
                statement.order_by(
                    InterviewSessionModel.updated_at.desc(),
                    InterviewSessionModel.id.desc(),
                )
                .offset(after.offset if after else 0)
                .limit(limit)
            )
        ).all()
        return [_session(model) for model in models]

    async def delete_session(self, owner_user_id: UUID, session_id: UUID) -> None:
        await self._execute(
            delete(InterviewSessionModel).where(
                InterviewSessionModel.owner_user_id == owner_user_id,
                InterviewSessionModel.id == session_id,
            )
        )

    async def add_question(self, question: InterviewQuestion) -> None:
        self.session.add(_question_model(question))
        await self._flush()

    async def add_questions(self, questions: tuple[InterviewQuestion, ...]) -> None:
        self.session.add_all(_question_model(question) for question in questions)
        await self._flush()

    async def get_question(
        self, owner_user_id: UUID, session_id: UUID, question_id: UUID
    ) -> InterviewQuestion | None:
        model = await self.session.scalar(
            select(InterviewQuestionModel).where(
                InterviewQuestionModel.owner_user_id == owner_user_id,
                InterviewQuestionModel.session_id == session_id,
                InterviewQuestionModel.id == question_id,
            )
        )
        return _question(model) if model is not None else None

    async def list_questions(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewQuestion]:
        models = (
            await self.session.scalars(
                select(InterviewQuestionModel)
                .where(
                    InterviewQuestionModel.owner_user_id == owner_user_id,
                    InterviewQuestionModel.session_id == session_id,
                )
                .order_by(InterviewQuestionModel.ordinal)
                .offset(after.offset if after else 0)
                .limit(limit)
            )
        ).all()
        return [_question(model) for model in models]

    async def add_note(self, note: InterviewSessionNote) -> None:
        self.session.add(_note_model(note))
        await self._flush()

    async def save_note(self, note: InterviewSessionNote) -> None:
        await self._execute(
            update(InterviewSessionNoteModel)
            .where(
                InterviewSessionNoteModel.owner_user_id == note.owner_user_id,
                InterviewSessionNoteModel.session_id == note.session_id,
                InterviewSessionNoteModel.id == note.id,
            )
            .values(
                kind=note.kind.value,
                body=note.body,
                version=note.version,
                updated_at=note.updated_at,
            )
        )

    async def get_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        note_id: UUID,
        *,
        for_update: bool = False,
    ) -> InterviewSessionNote | None:
        statement = select(InterviewSessionNoteModel).where(
            InterviewSessionNoteModel.owner_user_id == owner_user_id,
            InterviewSessionNoteModel.session_id == session_id,
            InterviewSessionNoteModel.id == note_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _note(model) if model is not None else None

    async def list_notes(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSessionNote]:
        models = (
            await self.session.scalars(
                select(InterviewSessionNoteModel)
                .where(
                    InterviewSessionNoteModel.owner_user_id == owner_user_id,
                    InterviewSessionNoteModel.session_id == session_id,
                )
                .order_by(
                    InterviewSessionNoteModel.created_at.desc(),
                    InterviewSessionNoteModel.id.desc(),
                )
                .offset(after.offset if after else 0)
                .limit(limit)
            )
        ).all()
        return [_note(model) for model in models]

    async def delete_note(self, owner_user_id: UUID, session_id: UUID, note_id: UUID) -> None:
        await self._execute(
            delete(InterviewSessionNoteModel).where(
                InterviewSessionNoteModel.owner_user_id == owner_user_id,
                InterviewSessionNoteModel.session_id == session_id,
                InterviewSessionNoteModel.id == note_id,
            )
        )

    async def add_follow_up_draft(self, draft: FollowUpDraft) -> None:
        self.session.add(_draft_model(draft))
        await self._flush()

    async def get_follow_up_draft(
        self, owner_user_id: UUID, session_id: UUID, draft_id: UUID
    ) -> FollowUpDraft | None:
        model = await self.session.scalar(
            select(FollowUpDraftModel).where(
                FollowUpDraftModel.owner_user_id == owner_user_id,
                FollowUpDraftModel.session_id == session_id,
                FollowUpDraftModel.id == draft_id,
            )
        )
        return _draft(model) if model is not None else None

    async def list_follow_up_drafts(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[FollowUpDraft]:
        models = (
            await self.session.scalars(
                select(FollowUpDraftModel)
                .where(
                    FollowUpDraftModel.owner_user_id == owner_user_id,
                    FollowUpDraftModel.session_id == session_id,
                )
                .order_by(FollowUpDraftModel.created_at.desc(), FollowUpDraftModel.id.desc())
                .offset(after.offset if after else 0)
                .limit(limit)
            )
        ).all()
        return [_draft(model) for model in models]

    async def count_session_children(
        self, owner_user_id: UUID, session_id: UUID
    ) -> tuple[int, int, int]:
        counts: list[int] = []
        for model_type in (
            InterviewQuestionModel,
            InterviewSessionNoteModel,
            FollowUpDraftModel,
        ):
            count = await self.session.scalar(
                select(func.count())
                .select_from(model_type)
                .where(
                    model_type.owner_user_id == owner_user_id,
                    model_type.session_id == session_id,
                )
            )
            counts.append(int(count or 0))
        return counts[0], counts[1], counts[2]

    async def count_session_children_batch(
        self,
        owner_user_id: UUID,
        session_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[int, int, int, int]]:
        unique_ids = tuple(dict.fromkeys(session_ids))
        if not unique_ids:
            return {}
        mutable: dict[UUID, list[int]] = {session_id: [0, 0, 0, 0] for session_id in unique_ids}
        question_rows = (
            await self.session.execute(
                select(
                    InterviewQuestionModel.session_id,
                    func.count(),
                    func.count().filter(InterviewQuestionModel.generated.is_(True)),
                )
                .where(
                    InterviewQuestionModel.owner_user_id == owner_user_id,
                    InterviewQuestionModel.session_id.in_(unique_ids),
                )
                .group_by(InterviewQuestionModel.session_id)
            )
        ).all()
        for session_id, total, generated in question_rows:
            mutable[session_id][0] = int(total)
            mutable[session_id][3] = int(generated)
        for index, model_type in (
            (1, InterviewSessionNoteModel),
            (2, FollowUpDraftModel),
        ):
            rows = (
                await self.session.execute(
                    select(model_type.session_id, func.count())
                    .where(
                        model_type.owner_user_id == owner_user_id,
                        model_type.session_id.in_(unique_ids),
                    )
                    .group_by(model_type.session_id)
                )
            ).all()
            for session_id, total in rows:
                mutable[session_id][index] = int(total)
        return {
            session_id: (counts[0], counts[1], counts[2], counts[3])
            for session_id, counts in mutable.items()
        }

    async def add_idempotency(self, record: InterviewIdempotencyRecord) -> None:
        self.session.add(
            InterviewIdempotencyModel(
                id=record.id,
                owner_user_id=record.owner_user_id,
                idempotency_key=record.idempotency_key,
                request_fingerprint=record.request_fingerprint,
                resource_kind=record.resource_kind,
                resource_id=record.resource_id,
                response_snapshot=(
                    _story_replay_snapshot_json(record.response_snapshot)
                    if record.response_snapshot is not None
                    else None
                ),
                created_at=record.created_at,
            )
        )
        await self._flush()

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> InterviewIdempotencyRecord | None:
        model = await self.session.scalar(
            select(InterviewIdempotencyModel).where(
                InterviewIdempotencyModel.owner_user_id == owner_user_id,
                InterviewIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_audit(self, event: InterviewAuditEvent) -> None:
        self.session.add(
            InterviewAuditEventModel(
                id=event.id,
                owner_user_id=event.owner_user_id,
                actor_user_id=event.actor_user_id,
                action=event.action.value,
                target_kind=event.target_kind,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                metadata_json=dict(event.metadata),
                created_at=event.created_at,
            )
        )

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _story_pins(
        self, owner_user_id: UUID, story_ids: tuple[UUID, ...]
    ) -> defaultdict[UUID, tuple[StoryClaimPin, ...]]:
        grouped: defaultdict[UUID, list[StoryClaimPin]] = defaultdict(list)
        if story_ids:
            models = (
                await self.session.scalars(
                    select(StoryClaimPinModel)
                    .where(
                        StoryClaimPinModel.owner_user_id == owner_user_id,
                        StoryClaimPinModel.story_id.in_(story_ids),
                    )
                    .order_by(StoryClaimPinModel.story_id, StoryClaimPinModel.id)
                )
            ).all()
            for model in models:
                grouped[model.story_id].append(_story_pin(model))
        return defaultdict(tuple, {key: tuple(value) for key, value in grouped.items()})

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


class SqlAlchemyInterviewPrepUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> InterviewPrepUnitOfWork:
        return SqlAlchemyInterviewPrepUnitOfWork(self._database)


def _owner_lock_key(owner_user_id: UUID) -> int:
    return int.from_bytes(
        hashlib.sha256(f"interview_prep:{owner_user_id}".encode("ascii")).digest()[:8],
        "big",
        signed=True,
    )


def _idempotency_lock_key(owner_user_id: UUID, idempotency_key: str) -> int:
    return int.from_bytes(
        hashlib.sha256(
            f"interview_prep:idempotency:{owner_user_id}:{idempotency_key}".encode("ascii")
        ).digest()[:8],
        "big",
        signed=True,
    )


def _story_values(story: StarStory, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "application_id": story.application_id,
        "title": story.title,
        "situation": story.situation,
        "task": story.task,
        "action": story.action,
        "result": story.result,
        "personal_contribution": story.personal_contribution,
        "metric_explanation": story.metric_explanation,
        "confidence": story.confidence,
        "follow_up_questions": list(story.follow_up_questions),
        "status": story.status.value,
        "origin": story.origin.value,
        "version": story.version,
        "created_at": story.created_at,
        "updated_at": story.updated_at,
    }
    if include_identity:
        values.update(id=story.id, owner_user_id=story.owner_user_id)
    return values


def _story(model: StarStoryModel, pins: tuple[StoryClaimPin, ...]) -> StarStory:
    return StarStory(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        title=model.title,
        situation=model.situation,
        task=model.task,
        action=model.action,
        result=model.result,
        personal_contribution=model.personal_contribution,
        metric_explanation=model.metric_explanation,
        confidence=model.confidence,
        follow_up_questions=_string_tuple(model.follow_up_questions),
        status=StoryStatus(model.status),
        origin=StoryOrigin(model.origin),
        claim_pins=pins,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _story_pin_model(story: StarStory, pin: StoryClaimPin) -> StoryClaimPinModel:
    return StoryClaimPinModel(
        id=uuid5(NAMESPACE_URL, f"careeros:story-pin:{story.id}:{pin.source_claim_id}"),
        owner_user_id=story.owner_user_id,
        story_id=story.id,
        source_claim_id=pin.source_claim_id,
        claim_text=pin.claim_text,
        claim_sha256=pin.claim_sha256,
        strong=pin.strong,
        field_names=[item.value for item in pin.field_names],
        evidence_pins=[_evidence_json(item) for item in pin.evidence_pins],
    )


def _story_pin(model: StoryClaimPinModel) -> StoryClaimPin:
    return StoryClaimPin(
        source_claim_id=model.source_claim_id,
        claim_text=model.claim_text,
        claim_sha256=model.claim_sha256,
        strong=model.strong,
        field_names=tuple(StoryField(item) for item in _string_tuple(model.field_names)),
        evidence_pins=_evidence_tuple(model.evidence_pins),
    )


def _session_values(session: InterviewSession) -> dict[str, object]:
    return {
        "id": session.id,
        "owner_user_id": session.owner_user_id,
        "application_id": session.application_id,
        "title": session.title,
        "kind": session.kind.value,
        "scheduled_at": session.scheduled_at,
        "context_snapshot": _context_json(session.context),
        "context_sha256": session.context.snapshot_sha256,
        "version": session.version,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _session(model: InterviewSessionModel) -> InterviewSession:
    context = _context(model.context_snapshot, model.context_sha256)
    return InterviewSession(
        id=model.id,
        owner_user_id=model.owner_user_id,
        application_id=model.application_id,
        title=model.title,
        kind=InterviewSessionKind(model.kind),
        scheduled_at=model.scheduled_at,
        context=context,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _question_model(question: InterviewQuestion) -> InterviewQuestionModel:
    return InterviewQuestionModel(
        id=question.id,
        owner_user_id=question.owner_user_id,
        session_id=question.session_id,
        ordinal=question.ordinal,
        prompt=question.prompt,
        kind=question.kind.value,
        source_requirement_ids=[str(item) for item in question.source_requirement_ids],
        source_claim_ids=[str(item) for item in question.source_claim_ids],
        generated=question.generated,
        created_at=question.created_at,
    )


def _question(model: InterviewQuestionModel) -> InterviewQuestion:
    return InterviewQuestion(
        id=model.id,
        owner_user_id=model.owner_user_id,
        session_id=model.session_id,
        ordinal=model.ordinal,
        prompt=model.prompt,
        kind=QuestionKind(model.kind),
        source_requirement_ids=_uuid_tuple(model.source_requirement_ids),
        source_claim_ids=_uuid_tuple(model.source_claim_ids),
        generated=model.generated,
        created_at=model.created_at,
    )


def _note_model(note: InterviewSessionNote) -> InterviewSessionNoteModel:
    return InterviewSessionNoteModel(
        id=note.id,
        owner_user_id=note.owner_user_id,
        session_id=note.session_id,
        kind=note.kind.value,
        body=note.body,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _note(model: InterviewSessionNoteModel) -> InterviewSessionNote:
    return InterviewSessionNote(
        id=model.id,
        owner_user_id=model.owner_user_id,
        session_id=model.session_id,
        kind=SessionNoteKind(model.kind),
        body=model.body,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _draft_model(draft: FollowUpDraft) -> FollowUpDraftModel:
    return FollowUpDraftModel(
        id=draft.id,
        owner_user_id=draft.owner_user_id,
        session_id=draft.session_id,
        subject=draft.subject,
        body=draft.body,
        source_claims=[_session_claim_json(item) for item in draft.source_claims],
        content_sha256=draft.content_sha256,
        created_at=draft.created_at,
    )


def _draft(model: FollowUpDraftModel) -> FollowUpDraft:
    return FollowUpDraft(
        id=model.id,
        owner_user_id=model.owner_user_id,
        session_id=model.session_id,
        subject=model.subject,
        body=model.body,
        source_claims=_session_claim_tuple(model.source_claims),
        content_sha256=model.content_sha256,
        created_at=model.created_at,
    )


def _idempotency(model: InterviewIdempotencyModel) -> InterviewIdempotencyRecord:
    try:
        return InterviewIdempotencyRecord(
            id=model.id,
            owner_user_id=model.owner_user_id,
            idempotency_key=model.idempotency_key,
            request_fingerprint=model.request_fingerprint,
            resource_kind=model.resource_kind,
            resource_id=model.resource_id,
            created_at=model.created_at,
            response_snapshot=_story_replay_snapshot(model.response_snapshot),
        )
    except (TypeError, ValueError) as exc:
        raise InterviewPrepUnavailable("stored idempotency record is invalid") from exc


_STORY_REPLAY_KEYS = frozenset(
    {
        "schemaVersion",
        "id",
        "ownerUserId",
        "applicationId",
        "title",
        "situation",
        "task",
        "action",
        "result",
        "personalContribution",
        "metricExplanation",
        "confidence",
        "followUpQuestions",
        "status",
        "origin",
        "claimPins",
        "version",
        "createdAt",
        "updatedAt",
    }
)
_STORY_CLAIM_REPLAY_KEYS = frozenset(
    {
        "sourceClaimId",
        "claimText",
        "claimSha256",
        "strong",
        "fieldNames",
        "evidencePins",
    }
)
_EVIDENCE_REPLAY_KEYS = frozenset(
    {
        "evidenceId",
        "evidenceRevisionId",
        "revisionNumber",
        "statement",
        "statementSha256",
        "strength",
        "hasNumericClaim",
    }
)


def _story_replay_snapshot_json(snapshot: StarStoryReplaySnapshot) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "id": str(snapshot.id),
        "ownerUserId": str(snapshot.owner_user_id),
        "applicationId": str(snapshot.application_id),
        "title": snapshot.title,
        "situation": snapshot.situation,
        "task": snapshot.task,
        "action": snapshot.action,
        "result": snapshot.result,
        "personalContribution": snapshot.personal_contribution,
        "metricExplanation": snapshot.metric_explanation,
        "confidence": snapshot.confidence,
        "followUpQuestions": list(snapshot.follow_up_questions),
        "status": snapshot.status.value,
        "origin": snapshot.origin.value,
        "claimPins": [_story_claim_replay_json(pin) for pin in snapshot.claim_pins],
        "version": snapshot.version,
        "createdAt": snapshot.created_at.isoformat(),
        "updatedAt": snapshot.updated_at.isoformat(),
    }


def _story_replay_snapshot(value: object) -> StarStoryReplaySnapshot | None:
    if value is None:
        return None
    try:
        stored = _exact_stored_object(value, _STORY_REPLAY_KEYS)
        if _stored_int(stored, "schemaVersion") != 1:
            raise TypeError
        metric_explanation = stored["metricExplanation"]
        if metric_explanation is not None and not isinstance(metric_explanation, str):
            raise TypeError
        raw_claim_pins = stored["claimPins"]
        if not isinstance(raw_claim_pins, list):
            raise TypeError
        return StarStoryReplaySnapshot(
            id=UUID(_stored_str(stored, "id")),
            owner_user_id=UUID(_stored_str(stored, "ownerUserId")),
            application_id=UUID(_stored_str(stored, "applicationId")),
            title=_stored_str(stored, "title"),
            situation=_stored_str(stored, "situation"),
            task=_stored_str(stored, "task"),
            action=_stored_str(stored, "action"),
            result=_stored_str(stored, "result"),
            personal_contribution=_stored_str(stored, "personalContribution"),
            metric_explanation=metric_explanation,
            confidence=_stored_int(stored, "confidence"),
            follow_up_questions=_string_tuple(stored["followUpQuestions"]),
            status=StoryStatus(_stored_str(stored, "status")),
            origin=StoryOrigin(_stored_str(stored, "origin")),
            claim_pins=tuple(_story_claim_replay(item) for item in raw_claim_pins),
            version=_stored_int(stored, "version"),
            created_at=datetime.fromisoformat(_stored_str(stored, "createdAt")),
            updated_at=datetime.fromisoformat(_stored_str(stored, "updatedAt")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InterviewPrepUnavailable("stored story replay snapshot is invalid") from exc


def _story_claim_replay_json(pin: StoryClaimPin) -> dict[str, object]:
    return {
        "sourceClaimId": str(pin.source_claim_id),
        "claimText": pin.claim_text,
        "claimSha256": pin.claim_sha256,
        "strong": pin.strong,
        "fieldNames": [item.value for item in pin.field_names],
        "evidencePins": [_evidence_json(item) for item in pin.evidence_pins],
    }


def _story_claim_replay(value: object) -> StoryClaimPin:
    stored = _exact_stored_object(value, _STORY_CLAIM_REPLAY_KEYS)
    raw_evidence = stored["evidencePins"]
    if not isinstance(raw_evidence, list):
        raise TypeError
    return StoryClaimPin(
        source_claim_id=UUID(_stored_str(stored, "sourceClaimId")),
        claim_text=_stored_str(stored, "claimText"),
        claim_sha256=_stored_str(stored, "claimSha256"),
        strong=_stored_bool(stored, "strong"),
        field_names=tuple(StoryField(item) for item in _string_tuple(stored["fieldNames"])),
        evidence_pins=tuple(_evidence_replay(item) for item in raw_evidence),
    )


def _evidence_replay(value: object) -> EvidenceRevisionPin:
    return _evidence(_exact_stored_object(value, _EVIDENCE_REPLAY_KEYS))


def _exact_stored_object(value: object, expected_keys: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise TypeError
    return value


def _evidence_json(pin: EvidenceRevisionPin) -> dict[str, object]:
    return {
        "evidenceId": str(pin.evidence_id),
        "evidenceRevisionId": str(pin.evidence_revision_id),
        "revisionNumber": pin.revision_number,
        "statement": pin.statement,
        "statementSha256": pin.statement_sha256,
        "strength": pin.strength,
        "hasNumericClaim": pin.has_numeric_claim,
    }


def _evidence(value: object) -> EvidenceRevisionPin:
    if not isinstance(value, dict):
        raise InterviewPrepUnavailable("stored evidence pin is invalid")
    try:
        return EvidenceRevisionPin(
            evidence_id=UUID(_stored_str(value, "evidenceId")),
            evidence_revision_id=UUID(_stored_str(value, "evidenceRevisionId")),
            revision_number=_stored_int(value, "revisionNumber"),
            statement=_stored_str(value, "statement"),
            statement_sha256=_stored_str(value, "statementSha256"),
            strength=_stored_str(value, "strength"),
            has_numeric_claim=_stored_bool(value, "hasNumericClaim"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InterviewPrepUnavailable("stored evidence pin is invalid") from exc


def _evidence_tuple(value: object) -> tuple[EvidenceRevisionPin, ...]:
    if not isinstance(value, list):
        raise InterviewPrepUnavailable("stored evidence pins are invalid")
    return tuple(_evidence(item) for item in value)


def _session_claim_json(claim: SessionContextClaim) -> dict[str, object]:
    return {
        "sourceClaimId": str(claim.source_claim_id),
        "text": claim.text,
        "textSha256": claim.text_sha256,
        "strong": claim.strong,
        "requirementIds": [str(item) for item in claim.requirement_ids],
        "evidencePins": [_evidence_json(pin) for pin in claim.evidence_pins],
    }


def _session_claim(value: object) -> SessionContextClaim:
    if not isinstance(value, dict):
        raise InterviewPrepUnavailable("stored session claim is invalid")
    try:
        return SessionContextClaim(
            source_claim_id=UUID(_stored_str(value, "sourceClaimId")),
            text=_stored_str(value, "text"),
            text_sha256=_stored_str(value, "textSha256"),
            strong=_stored_bool(value, "strong"),
            requirement_ids=_uuid_tuple(value["requirementIds"]),
            evidence_pins=_evidence_tuple(value["evidencePins"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InterviewPrepUnavailable("stored session claim is invalid") from exc


def _session_claim_tuple(value: object) -> tuple[SessionContextClaim, ...]:
    if not isinstance(value, list):
        raise InterviewPrepUnavailable("stored session claims are invalid")
    return tuple(_session_claim(item) for item in value)


def _context_json(context: SessionContextSnapshot) -> dict[str, object]:
    return {
        "applicationId": str(context.application_id),
        "jobId": str(context.job_id),
        "jobVersion": context.job_version,
        "jobTitle": context.job_title,
        "company": context.company,
        "resumeVersionId": str(context.resume_version_id),
        "resumeVersionNumber": context.resume_version_number,
        "claims": [_session_claim_json(item) for item in context.claims],
        "requirements": [
            {
                "requirementId": str(item.requirement_id),
                "text": item.text,
                "importance": item.importance,
            }
            for item in context.requirements
        ],
    }


def _context(value: object, digest: str) -> SessionContextSnapshot:
    if not isinstance(value, dict):
        raise InterviewPrepUnavailable("stored session context is invalid")
    try:
        company = value["company"]
        if company is not None and not isinstance(company, str):
            raise TypeError
        raw_requirements = value["requirements"]
        if not isinstance(raw_requirements, list):
            raise TypeError
        requirements = tuple(
            SessionContextRequirement(
                requirement_id=UUID(_stored_str(item, "requirementId")),
                text=_stored_str(item, "text"),
                importance=_stored_str(item, "importance"),
            )
            for item in raw_requirements
            if isinstance(item, dict)
        )
        if len(requirements) != len(raw_requirements):
            raise TypeError
        return SessionContextSnapshot(
            application_id=UUID(_stored_str(value, "applicationId")),
            job_id=UUID(_stored_str(value, "jobId")),
            job_version=_stored_int(value, "jobVersion"),
            job_title=_stored_str(value, "jobTitle"),
            company=company,
            resume_version_id=UUID(_stored_str(value, "resumeVersionId")),
            resume_version_number=_stored_int(value, "resumeVersionNumber"),
            claims=_session_claim_tuple(value["claims"]),
            requirements=requirements,
            snapshot_sha256=digest,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InterviewPrepUnavailable("stored session context is invalid") from exc


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InterviewPrepUnavailable("stored string collection is invalid")
    return tuple(value)


def _uuid_tuple(value: object) -> tuple[UUID, ...]:
    try:
        return tuple(UUID(item) for item in _string_tuple(value))
    except ValueError as exc:
        raise InterviewPrepUnavailable("stored UUID collection is invalid") from exc


def _stored_str(value: dict[str, Any], key: str) -> str:
    item = value[key]
    if not isinstance(item, str):
        raise TypeError
    return item


def _stored_int(value: dict[str, Any], key: str) -> int:
    item = value[key]
    if type(item) is not int:
        raise TypeError
    return item


def _stored_bool(value: dict[str, Any], key: str) -> bool:
    item = value[key]
    if type(item) is not bool:
        raise TypeError
    return item


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    if "idempotency" in _constraint_name(exc):
        raise InterviewPrepIdempotencyConflict from exc
    raise InterviewPrepConflict from exc


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
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return ""
