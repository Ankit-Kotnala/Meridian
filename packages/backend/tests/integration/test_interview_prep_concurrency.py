"""Live PostgreSQL concurrency contracts for Interview Prep mutations."""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.interview_prep.application import (
    CreateInterviewQuestion,
    CreateInterviewSession,
    CreateSessionNote,
    CreateStarStory,
    GenerateFollowUpDraft,
    InterviewPrepPolicy,
    InterviewPrepService,
    InterviewSourceSnapshot,
    RequestContext,
    SourceClaim,
    SourceRequirement,
    StoryClaimSelection,
    UpdateStarStory,
)
from careeros.modules.interview_prep.domain import (
    DefenseStatus,
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewPrepConflict,
    InterviewPrepNotFound,
    InterviewPrepQuotaExceeded,
    InterviewQuestion,
    InterviewSessionKind,
    InterviewSessionNote,
    SessionNoteKind,
    StoryField,
    StoryStatus,
)
from careeros.modules.interview_prep.infrastructure import (
    SqlAlchemyInterviewPrepUnitOfWorkFactory,
)
from careeros.modules.interview_prep.infrastructure.models import (
    FollowUpDraftModel,
    InterviewAuditEventModel,
    InterviewIdempotencyModel,
    InterviewQuestionModel,
    InterviewSessionNoteModel,
    StarStoryModel,
)

_NOW = datetime(2026, 7, 25, 9, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Identifiers:
    def new(self) -> UUID:
        return uuid4()


class _InterviewContext:
    def __init__(self, value: InterviewSourceSnapshot) -> None:
        self.value = value
        self.validation_error: Exception | None = None

    async def snapshot(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> InterviewSourceSnapshot:
        del owner_user_id
        if application_id != self.value.application_id:
            raise InterviewPrepNotFound
        return self.value

    async def validate_current_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None:
        del owner_user_id
        if application_id != self.value.application_id:
            raise InterviewPrepNotFound
        if self.validation_error is not None:
            raise self.validation_error
        expected = tuple(
            {
                pin.evidence_id: pin for claim in self.value.claims for pin in claim.evidence_pins
            }.values()
        )
        if evidence_pins != expected:
            raise InterviewPrepConflict("evidence is no longer current")


def _database() -> Database:
    url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return Database(DatabaseOptions(url=url, pool_size=6, max_overflow=0))


def _source(application_id: UUID) -> InterviewSourceSnapshot:
    requirement_id = uuid4()
    statement = "Led a verified cross-functional launch with secure delivery controls."
    digest = hashlib.sha256(statement.encode()).hexdigest()
    evidence = EvidenceRevisionPin(
        evidence_id=uuid4(),
        evidence_revision_id=uuid4(),
        revision_number=1,
        statement=statement,
        statement_sha256=digest,
        strength="confirmed",
        has_numeric_claim=False,
    )
    return InterviewSourceSnapshot(
        application_id=application_id,
        job_id=uuid4(),
        job_version=1,
        job_title="Principal Product Engineer",
        company="Example Co",
        resume_version_id=uuid4(),
        resume_version_number=1,
        claims=(
            SourceClaim(
                id=uuid4(),
                text=statement,
                text_sha256=digest,
                strong=True,
                requirement_ids=(requirement_id,),
                evidence_pins=(evidence,),
            ),
        ),
        requirements=(
            SourceRequirement(
                id=requirement_id,
                text="Lead secure cross-functional product delivery.",
                importance="mandatory",
            ),
        ),
    )


def _service(
    database: Database,
    source: InterviewSourceSnapshot,
    *,
    policy: InterviewPrepPolicy | None = None,
    context: _InterviewContext | None = None,
) -> InterviewPrepService:
    return InterviewPrepService(
        unit_of_work=SqlAlchemyInterviewPrepUnitOfWorkFactory(database),
        clock=_Clock(),
        identifiers=_Identifiers(),
        application_context=context or _InterviewContext(source),
        policy=policy,
    )


def _user(user_id: UUID) -> UserModel:
    return UserModel(
        id=user_id,
        email_normalized=f"{user_id}@interview-concurrency.example.test",
        password_hash=None,
        status="active",
        email_verified_at=None,
        auth_version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def _add_users(database: Database, *user_ids: UUID) -> None:
    async with database.session() as session:
        session.add_all(_user(user_id) for user_id in user_ids)
        await session.commit()


async def _delete_users(database: Database, *user_ids: UUID) -> None:
    async with database.session() as session:
        await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        await session.commit()


def _context(owner_user_id: UUID, suffix: str) -> RequestContext:
    return RequestContext(
        actor_user_id=owner_user_id,
        request_id=f"interview-concurrency-{suffix}",
        trace_id=f"trace-interview-concurrency-{suffix}",
    )


def _story_command(
    source: InterviewSourceSnapshot,
    status: StoryStatus,
) -> CreateStarStory:
    statement = source.claims[0].text
    return CreateStarStory(
        application_id=source.application_id,
        title="Evidence-backed launch leadership",
        situation=statement,
        task=statement,
        action=statement,
        result=statement,
        personal_contribution=statement,
        metric_explanation=None,
        confidence=4,
        status=status,
        claim_selections=(
            StoryClaimSelection(
                claim_id=source.claims[0].id,
                field_names=(
                    StoryField.SITUATION,
                    StoryField.TASK,
                    StoryField.ACTION,
                    StoryField.RESULT,
                    StoryField.PERSONAL_CONTRIBUTION,
                ),
            ),
        ),
    )


def _story_update(
    source: InterviewSourceSnapshot,
    status: StoryStatus,
) -> UpdateStarStory:
    command = _story_command(source, status)
    return UpdateStarStory(
        title=command.title,
        situation=command.situation,
        task=command.task,
        action=command.action,
        result=command.result,
        personal_contribution=command.personal_contribution,
        metric_explanation=command.metric_explanation,
        confidence=command.confidence,
        follow_up_questions=command.follow_up_questions,
        status=status,
        claim_selections=command.claim_selections,
    )


@pytest.mark.asyncio
async def test_ready_story_live_validation_precedes_postgresql_persistence() -> None:
    database = _database()
    owner_user_id = uuid4()
    source = _source(uuid4())
    application_context = _InterviewContext(source)
    service = _service(database, source, context=application_context)
    try:
        await _add_users(database, owner_user_id)
        application_context.validation_error = InterviewPrepConflict(
            "evidence is no longer current"
        )

        with pytest.raises(InterviewPrepConflict):
            await service.create_story(
                owner_user_id,
                _story_command(source, StoryStatus.READY),
                idempotency_key=f"story-ready-rejected-{uuid4().hex}",
                context=_context(owner_user_id, "ready-rejected"),
            )

        async with database.session() as db_session:
            rejected_story_count = await db_session.scalar(
                select(func.count())
                .select_from(StarStoryModel)
                .where(StarStoryModel.owner_user_id == owner_user_id)
            )
            rejected_idempotency_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewIdempotencyModel)
                .where(InterviewIdempotencyModel.owner_user_id == owner_user_id)
            )
            rejected_audit_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewAuditEventModel)
                .where(InterviewAuditEventModel.owner_user_id == owner_user_id)
            )
        assert rejected_story_count == 0
        assert rejected_idempotency_count == 0
        assert rejected_audit_count == 0

        draft = await service.create_story(
            owner_user_id,
            _story_command(source, StoryStatus.DRAFT),
            idempotency_key=f"story-draft-historical-{uuid4().hex}",
            context=_context(owner_user_id, "draft-historical"),
        )
        with pytest.raises(InterviewPrepConflict):
            await service.update_story(
                owner_user_id,
                draft.id,
                _story_update(source, StoryStatus.READY),
                expected_version=draft.version,
                context=_context(owner_user_id, "draft-ready-rejected"),
            )

        persisted_draft = await service.get_story(owner_user_id, draft.id)
        assert persisted_draft.status is StoryStatus.DRAFT
        assert persisted_draft.version == 1

        application_context.validation_error = None
        ready = await service.update_story(
            owner_user_id,
            draft.id,
            _story_update(source, StoryStatus.READY),
            expected_version=draft.version,
            context=_context(owner_user_id, "draft-ready"),
        )
        application_context.validation_error = InterviewPrepConflict(
            "evidence was revoked after readiness"
        )

        defense = await service.defense_map(owner_user_id, source.application_id)
        assert defense.entries[0].status is DefenseStatus.PARTIAL
        assert defense.entries[0].story_ids == (ready.id,)
        persisted_ready = await service.get_story(owner_user_id, ready.id)
        assert persisted_ready.status is StoryStatus.READY
        assert persisted_ready.version == ready.version

        async with database.session() as db_session:
            story_count = await db_session.scalar(
                select(func.count())
                .select_from(StarStoryModel)
                .where(StarStoryModel.owner_user_id == owner_user_id)
            )
            idempotency_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewIdempotencyModel)
                .where(InterviewIdempotencyModel.owner_user_id == owner_user_id)
            )
            audit_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewAuditEventModel)
                .where(InterviewAuditEventModel.owner_user_id == owner_user_id)
            )
        assert story_count == 1
        assert idempotency_count == 1
        assert audit_count == 2
    finally:
        await _delete_users(database, owner_user_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_session_parent_lock_serializes_idempotency_and_child_quotas() -> None:
    database = _database()
    owner_user_id, other_user_id = uuid4(), uuid4()
    source = _source(uuid4())
    policy = InterviewPrepPolicy(
        max_questions_per_generation=1,
        max_questions_per_session=1,
        max_notes_per_session=1,
        max_follow_up_drafts_per_session=1,
    )
    service = _service(database, source, policy=policy)
    try:
        await _add_users(database, owner_user_id, other_user_id)
        session = (
            await service.create_session(
                owner_user_id,
                CreateInterviewSession(
                    application_id=source.application_id,
                    title="Concurrent child mutation test",
                    kind=InterviewSessionKind.TECHNICAL,
                ),
                idempotency_key=f"session-{uuid4().hex}",
                context=_context(owner_user_id, "session"),
            )
        ).session

        note_key = f"note-{uuid4().hex}"

        async def create_same_note(suffix: str) -> InterviewSessionNote:
            return await service.create_note(
                owner_user_id,
                session.id,
                CreateSessionNote(
                    kind=SessionNoteKind.PRIVATE_NOTE,
                    body="One owner-private idempotent note.",
                ),
                idempotency_key=note_key,
                context=_context(owner_user_id, suffix),
            )

        first_note, replayed_note = await asyncio.gather(
            create_same_note("note-a"),
            create_same_note("note-b"),
        )
        assert first_note.id == replayed_note.id

        note_quota_session = (
            await service.create_session(
                owner_user_id,
                CreateInterviewSession(
                    application_id=source.application_id,
                    title="Concurrent note quota test",
                    kind=InterviewSessionKind.BEHAVIORAL,
                ),
                idempotency_key=f"session-{uuid4().hex}",
                context=_context(owner_user_id, "note-quota-session"),
            )
        ).session

        async def create_distinct_note(suffix: str) -> InterviewSessionNote:
            return await service.create_note(
                owner_user_id,
                note_quota_session.id,
                CreateSessionNote(
                    kind=SessionNoteKind.REFLECTION,
                    body=f"Concurrent bounded reflection {suffix}.",
                ),
                idempotency_key=f"note-{suffix}-{uuid4().hex}",
                context=_context(owner_user_id, f"note-{suffix}"),
            )

        note_results = await asyncio.gather(
            create_distinct_note("quota-a"),
            create_distinct_note("quota-b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, InterviewSessionNote) for result in note_results) == 1
        assert sum(isinstance(result, InterviewPrepQuotaExceeded) for result in note_results) == 1

        async def create_question(suffix: str) -> InterviewQuestion:
            return await service.create_question(
                owner_user_id,
                session.id,
                CreateInterviewQuestion(prompt=f"Concurrent bounded question {suffix}?"),
                idempotency_key=f"question-{suffix}-{uuid4().hex}",
                context=_context(owner_user_id, suffix),
            )

        results = await asyncio.gather(
            create_question("a"),
            create_question("b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, InterviewQuestion) for result in results) == 1
        assert sum(isinstance(result, InterviewPrepQuotaExceeded) for result in results) == 1

        async def generate_draft(suffix: str) -> FollowUpDraft:
            return await service.generate_follow_up_draft(
                owner_user_id,
                session.id,
                GenerateFollowUpDraft(source_claim_ids=(source.claims[0].id,)),
                idempotency_key=f"draft-{suffix}-{uuid4().hex}",
                context=_context(owner_user_id, f"draft-{suffix}"),
            )

        draft_results = await asyncio.gather(
            generate_draft("a"),
            generate_draft("b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, FollowUpDraft) for result in draft_results) == 1
        assert sum(isinstance(result, InterviewPrepQuotaExceeded) for result in draft_results) == 1

        with pytest.raises(InterviewPrepNotFound):
            await service.create_question(
                other_user_id,
                session.id,
                CreateInterviewQuestion(prompt="Cross-owner child mutation attempt?"),
                idempotency_key=f"question-cross-owner-{uuid4().hex}",
                context=_context(other_user_id, "cross-owner"),
            )

        async with database.session() as db_session:
            question_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewQuestionModel)
                .where(
                    InterviewQuestionModel.owner_user_id == owner_user_id,
                    InterviewQuestionModel.session_id == session.id,
                )
            )
            note_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewSessionNoteModel)
                .where(
                    InterviewSessionNoteModel.owner_user_id == owner_user_id,
                    InterviewSessionNoteModel.session_id == session.id,
                )
            )
            quota_note_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewSessionNoteModel)
                .where(
                    InterviewSessionNoteModel.owner_user_id == owner_user_id,
                    InterviewSessionNoteModel.session_id == note_quota_session.id,
                )
            )
            draft_count = await db_session.scalar(
                select(func.count())
                .select_from(FollowUpDraftModel)
                .where(
                    FollowUpDraftModel.owner_user_id == owner_user_id,
                    FollowUpDraftModel.session_id == session.id,
                )
            )
        assert question_count == 1
        assert note_count == 1
        assert quota_note_count == 1
        assert draft_count == 1
    finally:
        await _delete_users(database, owner_user_id, other_user_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_session_parent_lock_prevents_concurrent_duplicate_question_banks() -> None:
    database = _database()
    owner_user_id = uuid4()
    source = _source(uuid4())
    service = _service(database, source)
    try:
        await _add_users(database, owner_user_id)
        session = (
            await service.create_session(
                owner_user_id,
                CreateInterviewSession(
                    application_id=source.application_id,
                    title="Concurrent generated question bank test",
                    kind=InterviewSessionKind.HIRING_MANAGER,
                ),
                idempotency_key=f"session-{uuid4().hex}",
                context=_context(owner_user_id, "bank-session"),
            )
        ).session
        keys = (f"bank-{uuid4().hex}", f"bank-{uuid4().hex}")

        async def generate(key: str, suffix: str) -> tuple[InterviewQuestion, ...]:
            return await service.generate_question_bank(
                owner_user_id,
                session.id,
                idempotency_key=key,
                context=_context(owner_user_id, suffix),
            )

        results = await asyncio.gather(
            generate(keys[0], "bank-a"),
            generate(keys[1], "bank-b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, tuple) for result in results) == 1
        assert (
            sum(
                isinstance(result, InterviewPrepConflict) and "already exists" in str(result)
                for result in results
            )
            == 1
        )

        successful_index = next(
            index for index, result in enumerate(results) if isinstance(result, tuple)
        )
        replay = await generate(keys[successful_index], "bank-replay")
        assert replay == results[successful_index]

        async with database.session() as db_session:
            generated_count = await db_session.scalar(
                select(func.count())
                .select_from(InterviewQuestionModel)
                .where(
                    InterviewQuestionModel.owner_user_id == owner_user_id,
                    InterviewQuestionModel.session_id == session.id,
                    InterviewQuestionModel.generated.is_(True),
                )
            )
        assert generated_count == 1
        assert not any("send" in name for name in dir(service) if not name.startswith("_"))
    finally:
        await _delete_users(database, owner_user_id)
        await database.dispose()
