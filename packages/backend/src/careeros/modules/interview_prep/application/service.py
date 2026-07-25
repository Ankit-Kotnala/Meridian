"""Owner-scoped Interview Prep orchestration and grounding enforcement."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from careeros.modules.interview_prep.domain import (
    DefenseStatus,
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewAuditAction,
    InterviewAuditEvent,
    InterviewIdempotencyRecord,
    InterviewPrepConflict,
    InterviewPrepIdempotencyConflict,
    InterviewPrepNotFound,
    InterviewPrepQuotaExceeded,
    InterviewPrepUnavailable,
    InterviewPrepValidationError,
    InterviewPrepVersionConflict,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionNote,
    QuestionKind,
    SessionContextClaim,
    SessionContextRequirement,
    SessionContextSnapshot,
    StarStory,
    StarStoryReplaySnapshot,
    StoryClaimPin,
    StoryField,
    StoryOrigin,
    StoryStatus,
)

from .models import (
    CreateInterviewQuestion,
    CreateInterviewSession,
    CreateSessionNote,
    CreateStarStory,
    DefenseMap,
    DefenseMapEntry,
    FollowUpDraftReadView,
    GenerateFollowUpDraft,
    GroundingAssessment,
    GroundingStatus,
    InterviewSourceSnapshot,
    PageCursor,
    PagedResult,
    QuestionReadView,
    RequestContext,
    SessionReadView,
    SessionView,
    SourceClaim,
    StoryClaimSelection,
    StoryFilter,
    StoryReadView,
    UpdateInterviewSession,
    UpdateSessionNote,
    UpdateStarStory,
    as_session_claim,
    page_result,
)
from .ports import (
    ApplicationInterviewContextProvider,
    Clock,
    IdentifierFactory,
    InterviewPrepUnitOfWork,
    InterviewPrepUnitOfWorkFactory,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_NUMERIC_TOKEN = re.compile(r"(?<!\w)(?:[$€£]?[-+]?\d[\d,]*(?:\.\d+)?%?)(?!\w)")
_EVIDENCE_VALIDATION_BATCH_SIZE = 200
_READY_FIELDS = frozenset(
    {
        StoryField.SITUATION,
        StoryField.TASK,
        StoryField.ACTION,
        StoryField.RESULT,
        StoryField.PERSONAL_CONTRIBUTION,
    }
)


@dataclass(frozen=True, slots=True)
class InterviewPrepPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_stories_per_owner: int = 500
    max_sessions_per_owner: int = 500
    max_questions_per_generation: int = 20
    max_questions_per_session: int = 200
    max_notes_per_session: int = 500
    max_follow_up_drafts_per_session: int = 100

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("Interview Prep page limits are invalid")
        if self.max_stories_per_owner < 1 or self.max_sessions_per_owner < 1:
            raise ValueError("Interview Prep collection limits must be positive")
        if not 1 <= self.max_questions_per_generation <= 50:
            raise ValueError("Interview Prep question generation limit is invalid")
        if self.max_questions_per_session < self.max_questions_per_generation:
            raise ValueError("Interview Prep question collection limit is invalid")
        if self.max_notes_per_session < 1 or self.max_follow_up_drafts_per_session < 1:
            raise ValueError("Interview Prep private collection limits must be positive")


class InterviewPrepService:
    """Phase 9 interview workflows with immutable Phase 8 provenance."""

    def __init__(
        self,
        *,
        unit_of_work: InterviewPrepUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        application_context: ApplicationInterviewContextProvider,
        policy: InterviewPrepPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._applications = application_context
        self._policy = policy or InterviewPrepPolicy()

    async def create_story(
        self,
        owner_user_id: UUID,
        command: CreateStarStory,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> StarStory:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint("create_story", command)
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            replay = await self._story_replay(uow, owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            if await uow.count_stories(owner_user_id) >= self._policy.max_stories_per_owner:
                raise InterviewPrepQuotaExceeded("story limit reached")
            source = await self._applications.snapshot(owner_user_id, command.application_id)
            self._validate_source(source, command.application_id)
            now = self._clock.now()
            story = StarStory(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                application_id=command.application_id,
                title=command.title,
                situation=command.situation,
                task=command.task,
                action=command.action,
                result=command.result,
                personal_contribution=command.personal_contribution,
                metric_explanation=command.metric_explanation,
                confidence=command.confidence,
                follow_up_questions=command.follow_up_questions,
                status=command.status,
                origin=command.origin,
                claim_pins=self._story_claim_pins(source, command.claim_selections),
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._validate_story_grounding(story)
            await self._validate_ready_story_evidence(owner_user_id, story)
            await uow.add_story(story)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "star_story",
                story.id,
                InterviewAuditAction.STORY_CREATED,
                context,
                now,
                response_snapshot=StarStoryReplaySnapshot.capture(story),
                application_id=story.application_id,
                story_id=story.id,
                status=story.status.value,
                version=story.version,
                claim_count=len(story.claim_pins),
            )
            await uow.commit()
            return story

    async def get_story(self, owner_user_id: UUID, story_id: UUID) -> StarStory:
        async with self._uow() as uow:
            story = await uow.get_story(owner_user_id, story_id)
        if story is None:
            raise InterviewPrepNotFound
        return story

    async def get_story_read(
        self,
        owner_user_id: UUID,
        story_id: UUID,
    ) -> StoryReadView:
        story = await self.get_story(owner_user_id, story_id)
        return StoryReadView(
            story=story,
            grounding=await self._assess_story(owner_user_id, story),
        )

    async def list_stories(
        self,
        owner_user_id: UUID,
        filter_by: StoryFilter | None = None,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[StarStory]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            stories = await uow.list_stories(
                owner_user_id, filter_by or StoryFilter(), after, page_size + 1
            )
        return page_result(stories, cursor=after, limit=page_size)

    async def list_story_reads(
        self,
        owner_user_id: UUID,
        filter_by: StoryFilter | None = None,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[StoryReadView]:
        result = await self.list_stories(
            owner_user_id,
            filter_by,
            cursor=cursor,
            limit=limit,
        )
        assessments = await self._assess_stories(owner_user_id, result.data)
        return PagedResult(
            data=tuple(
                StoryReadView(story=story, grounding=assessments[story.id]) for story in result.data
            ),
            page=result.page,
        )

    async def update_story(
        self,
        owner_user_id: UUID,
        story_id: UUID,
        command: UpdateStarStory,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> StarStory:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            story = await uow.get_story(owner_user_id, story_id, for_update=True)
            if story is None:
                raise InterviewPrepNotFound
            self._version(story.version, expected_version)
            source = await self._applications.snapshot(owner_user_id, story.application_id)
            self._validate_source(source, story.application_id)
            story.edit(
                title=command.title,
                situation=command.situation,
                task=command.task,
                action=command.action,
                result=command.result,
                personal_contribution=command.personal_contribution,
                metric_explanation=command.metric_explanation,
                confidence=command.confidence,
                follow_up_questions=command.follow_up_questions,
                status=command.status,
                claim_pins=self._story_claim_pins(source, command.claim_selections),
                now=now,
            )
            self._validate_story_grounding(story)
            await self._validate_ready_story_evidence(owner_user_id, story)
            await uow.save_story(story)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.STORY_UPDATED,
                    "star_story",
                    story.id,
                    context,
                    now,
                    application_id=story.application_id,
                    story_id=story.id,
                    status=story.status.value,
                    version=story.version,
                    claim_count=len(story.claim_pins),
                )
            )
            await uow.commit()
            return story

    async def delete_story(
        self,
        owner_user_id: UUID,
        story_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            story = await uow.get_story(owner_user_id, story_id, for_update=True)
            if story is None:
                raise InterviewPrepNotFound
            self._version(story.version, expected_version)
            await uow.redact_story_replay_snapshot(owner_user_id, story_id)
            await uow.delete_story(owner_user_id, story_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.STORY_DELETED,
                    "star_story",
                    story.id,
                    context,
                    now,
                    application_id=story.application_id,
                    story_id=story.id,
                    version=story.version,
                )
            )
            await uow.commit()

    async def defense_map(self, owner_user_id: UUID, application_id: UUID) -> DefenseMap:
        source = await self._applications.snapshot(owner_user_id, application_id)
        self._validate_source(source, application_id)
        async with self._uow() as uow:
            stories = await uow.list_stories(
                owner_user_id,
                StoryFilter(application_id=application_id),
                None,
                self._policy.max_stories_per_owner + 1,
            )
        ready_candidates = tuple(
            story
            for story in stories
            if story.status is StoryStatus.READY
            and any(self._story_matches_claim(story, claim) for claim in source.claims)
        )
        current_ready_story_ids: set[UUID] = set()
        needs_review_story_ids: set[UUID] = set()
        current_by_pin_set: dict[tuple[EvidenceRevisionPin, ...], bool] = {}
        for story in ready_candidates:
            evidence_pins = self._story_evidence_pins((story,))
            if evidence_pins not in current_by_pin_set:
                try:
                    await self._validate_current_evidence_pins(
                        owner_user_id,
                        application_id,
                        evidence_pins,
                    )
                except InterviewPrepConflict:
                    current_by_pin_set[evidence_pins] = False
                else:
                    current_by_pin_set[evidence_pins] = True
            if not current_by_pin_set[evidence_pins]:
                needs_review_story_ids.add(story.id)
            else:
                current_ready_story_ids.add(story.id)
        entries: list[DefenseMapEntry] = []
        for claim in source.claims:
            ready = tuple(
                story.id
                for story in stories
                if story.id in current_ready_story_ids and self._story_matches_claim(story, claim)
            )
            needs_review = tuple(
                story.id
                for story in stories
                if story.id in needs_review_story_ids and self._story_matches_claim(story, claim)
            )
            drafts = tuple(
                story.id
                for story in stories
                if story.status is StoryStatus.DRAFT and self._story_matches_claim(story, claim)
            )
            if ready:
                status = DefenseStatus.DEFENDED
                story_ids = ready
            elif needs_review or drafts:
                status = DefenseStatus.PARTIAL
                story_ids = tuple(dict.fromkeys((*needs_review, *drafts)))
            else:
                status = DefenseStatus.UNDEFENDED
                story_ids = ()
            warning = (
                "Ready STAR story evidence is no longer current; review and re-ground it."
                if needs_review
                else (
                    "Strong claim is not backed by a ready STAR story."
                    if claim.strong and status is not DefenseStatus.DEFENDED
                    else None
                )
            )
            entries.append(
                DefenseMapEntry(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    strong=claim.strong,
                    status=status,
                    story_ids=story_ids,
                    evidence_revision_ids=tuple(
                        pin.evidence_revision_id for pin in claim.evidence_pins
                    ),
                    warning=warning,
                )
            )
        return DefenseMap(
            application_id=application_id,
            entries=tuple(entries),
            defended_count=sum(item.status is DefenseStatus.DEFENDED for item in entries),
            partial_count=sum(item.status is DefenseStatus.PARTIAL for item in entries),
            undefended_count=sum(item.status is DefenseStatus.UNDEFENDED for item in entries),
            strong_claim_warning_count=sum(
                item.strong and item.warning is not None for item in entries
            ),
        )

    async def create_session(
        self,
        owner_user_id: UUID,
        command: CreateInterviewSession,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> SessionView:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint("create_session", command)
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            replay = await self._session_replay(uow, owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return await self._session_view(uow, replay)
            if await uow.count_sessions(owner_user_id) >= self._policy.max_sessions_per_owner:
                raise InterviewPrepQuotaExceeded("interview session limit reached")
            source = await self._applications.snapshot(owner_user_id, command.application_id)
            self._validate_source(source, command.application_id)
            now = self._clock.now()
            session = InterviewSession(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                application_id=command.application_id,
                title=command.title,
                kind=command.kind,
                scheduled_at=command.scheduled_at,
                context=self._session_context(source),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_session(session)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "interview_session",
                session.id,
                InterviewAuditAction.SESSION_CREATED,
                context,
                now,
                application_id=session.application_id,
                session_id=session.id,
                version=session.version,
                claim_count=len(session.context.claims),
            )
            await uow.commit()
            return SessionView(session, 0, 0, 0)

    async def get_session(self, owner_user_id: UUID, session_id: UUID) -> SessionView:
        async with self._uow() as uow:
            session = await uow.get_session(owner_user_id, session_id)
            if session is None:
                raise InterviewPrepNotFound
            return await self._session_view(uow, session)

    async def get_session_read(
        self,
        owner_user_id: UUID,
        session_id: UUID,
    ) -> SessionReadView:
        view = await self.get_session(owner_user_id, session_id)
        return SessionReadView(
            view=view,
            grounding=await self._assess_session(owner_user_id, view.session),
        )

    async def list_sessions(
        self,
        owner_user_id: UUID,
        *,
        application_id: UUID | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[SessionView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            sessions = await uow.list_sessions(owner_user_id, application_id, after, page_size + 1)
            child_counts = await uow.count_session_children_batch(
                owner_user_id,
                tuple(session.id for session in sessions),
            )
            views = [
                self._session_view_from_counts(
                    session,
                    child_counts.get(session.id, (0, 0, 0, 0)),
                )
                for session in sessions
            ]
        return page_result(views, cursor=after, limit=page_size)

    async def list_session_reads(
        self,
        owner_user_id: UUID,
        *,
        application_id: UUID | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[SessionReadView]:
        result = await self.list_sessions(
            owner_user_id,
            application_id=application_id,
            cursor=cursor,
            limit=limit,
        )
        assessments = await self._assess_sessions(
            owner_user_id,
            tuple(view.session for view in result.data),
        )
        return PagedResult(
            data=tuple(
                SessionReadView(view=view, grounding=assessments[view.session.id])
                for view in result.data
            ),
            page=result.page,
        )

    async def update_session(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        command: UpdateInterviewSession,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> SessionView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            self._version(session.version, expected_version)
            session.edit(
                title=command.title,
                kind=command.kind,
                scheduled_at=command.scheduled_at,
                now=now,
            )
            await uow.save_session(session)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.SESSION_UPDATED,
                    "interview_session",
                    session.id,
                    context,
                    now,
                    application_id=session.application_id,
                    session_id=session.id,
                    version=session.version,
                )
            )
            view = await self._session_view(uow, session)
            await uow.commit()
            return view

    async def delete_session(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            self._version(session.version, expected_version)
            await uow.delete_session(owner_user_id, session_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.SESSION_DELETED,
                    "interview_session",
                    session.id,
                    context,
                    now,
                    application_id=session.application_id,
                    session_id=session.id,
                    version=session.version,
                )
            )
            await uow.commit()

    async def create_question(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        command: CreateInterviewQuestion,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> InterviewQuestion:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "create_question", {"session_id": session_id, "command": command}
        )
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            replay = await self._question_replay(
                uow, owner_user_id, idempotency_key, fingerprint, session_id
            )
            if replay is not None:
                return replay
            question_count, _, _ = await uow.count_session_children(owner_user_id, session_id)
            if question_count >= self._policy.max_questions_per_session:
                raise InterviewPrepQuotaExceeded("interview question limit reached")
            self._validate_question_sources(session, command)
            now = self._clock.now()
            question = InterviewQuestion(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                session_id=session_id,
                ordinal=question_count + 1,
                prompt=command.prompt,
                kind=command.kind,
                source_requirement_ids=command.source_requirement_ids,
                source_claim_ids=command.source_claim_ids,
                generated=False,
                created_at=now,
            )
            await uow.add_question(question)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "interview_question",
                question.id,
                InterviewAuditAction.QUESTION_CREATED,
                context,
                now,
                application_id=session.application_id,
                session_id=session.id,
            )
            await uow.commit()
            return question

    async def generate_question_bank(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> tuple[InterviewQuestion, ...]:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint("generate_question_bank", {"session_id": session_id})
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            existing = await uow.find_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                self._assert_replay(existing, fingerprint, "question_bank", session_id)
                current = await uow.list_questions(
                    owner_user_id,
                    session_id,
                    None,
                    self._policy.max_questions_per_session + 1,
                )
                return tuple(question for question in current if question.generated)
            question_count, _, _ = await uow.count_session_children(owner_user_id, session_id)
            current = await uow.list_questions(
                owner_user_id,
                session_id,
                None,
                self._policy.max_questions_per_session + 1,
            )
            if any(question.generated for question in current):
                raise InterviewPrepConflict(
                    "a generated question bank already exists for this session"
                )
            await self._applications.validate_current_evidence(
                owner_user_id,
                session.application_id,
                self._current_evidence_pins(session.context.claims),
            )
            now = self._clock.now()
            questions = self._generated_questions(
                owner_user_id,
                session,
                now,
                starting_ordinal=question_count + 1,
            )
            if question_count + len(questions) > self._policy.max_questions_per_session:
                raise InterviewPrepQuotaExceeded("interview question limit reached")
            await uow.add_questions(questions)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "question_bank",
                session.id,
                InterviewAuditAction.QUESTIONS_GENERATED,
                context,
                now,
                application_id=session.application_id,
                session_id=session.id,
                question_count=len(questions),
            )
            await uow.commit()
            return questions

    async def list_questions(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[InterviewQuestion]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_session(owner_user_id, session_id) is None:
                raise InterviewPrepNotFound
            items = await uow.list_questions(owner_user_id, session_id, after, page_size + 1)
        return page_result(items, cursor=after, limit=page_size)

    async def get_question_read(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        question_id: UUID,
    ) -> QuestionReadView:
        async with self._uow() as uow:
            session = await uow.get_session(owner_user_id, session_id)
            question = await uow.get_question(owner_user_id, session_id, question_id)
        if session is None or question is None:
            raise InterviewPrepNotFound
        return QuestionReadView(
            question=question,
            grounding=await self._assess_question(owner_user_id, session, question),
        )

    async def list_question_reads(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[QuestionReadView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            session = await uow.get_session(owner_user_id, session_id)
            if session is None:
                raise InterviewPrepNotFound
            items = await uow.list_questions(owner_user_id, session_id, after, page_size + 1)
        assessment = await self._assess_session(owner_user_id, session)
        result = page_result(items, cursor=after, limit=page_size)
        return PagedResult(
            data=tuple(
                QuestionReadView(
                    question=item,
                    grounding=(
                        assessment
                        if item.generated or item.source_claim_ids or item.source_requirement_ids
                        else GroundingAssessment(
                            GroundingStatus.UNKNOWN,
                            "This private question has no evidence-linked source context.",
                        )
                    ),
                )
                for item in result.data
            ),
            page=result.page,
        )

    async def create_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        command: CreateSessionNote,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> InterviewSessionNote:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "create_session_note", {"session_id": session_id, "command": command}
        )
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            replay = await self._note_replay(
                uow, owner_user_id, idempotency_key, fingerprint, session_id
            )
            if replay is not None:
                return replay
            _, note_count, _ = await uow.count_session_children(owner_user_id, session_id)
            if note_count >= self._policy.max_notes_per_session:
                raise InterviewPrepQuotaExceeded("private session note limit reached")
            now = self._clock.now()
            note = InterviewSessionNote(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                session_id=session_id,
                kind=command.kind,
                body=command.body,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_note(note)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "session_note",
                note.id,
                InterviewAuditAction.NOTE_CREATED,
                context,
                now,
                application_id=session.application_id,
                session_id=session.id,
                version=note.version,
            )
            await uow.commit()
            return note

    async def update_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        note_id: UUID,
        command: UpdateSessionNote,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> InterviewSessionNote:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            if await uow.get_session(owner_user_id, session_id, for_update=True) is None:
                raise InterviewPrepNotFound
            note = await uow.get_note(owner_user_id, session_id, note_id, for_update=True)
            if note is None:
                raise InterviewPrepNotFound
            self._version(note.version, expected_version)
            note.edit(kind=command.kind, body=command.body, now=now)
            await uow.save_note(note)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.NOTE_UPDATED,
                    "session_note",
                    note.id,
                    context,
                    now,
                    session_id=session_id,
                    version=note.version,
                )
            )
            await uow.commit()
            return note

    async def delete_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        note_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            if await uow.get_session(owner_user_id, session_id, for_update=True) is None:
                raise InterviewPrepNotFound
            note = await uow.get_note(owner_user_id, session_id, note_id, for_update=True)
            if note is None:
                raise InterviewPrepNotFound
            self._version(note.version, expected_version)
            await uow.delete_note(owner_user_id, session_id, note_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    InterviewAuditAction.NOTE_DELETED,
                    "session_note",
                    note.id,
                    context,
                    now,
                    session_id=session_id,
                    version=note.version,
                )
            )
            await uow.commit()

    async def list_notes(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[InterviewSessionNote]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_session(owner_user_id, session_id) is None:
                raise InterviewPrepNotFound
            items = await uow.list_notes(owner_user_id, session_id, after, page_size + 1)
        return page_result(items, cursor=after, limit=page_size)

    async def generate_follow_up_draft(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        command: GenerateFollowUpDraft,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> FollowUpDraft:
        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "generate_follow_up_draft",
            {"session_id": session_id, "command": command},
        )
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            session = await uow.get_session(owner_user_id, session_id, for_update=True)
            if session is None:
                raise InterviewPrepNotFound
            await uow.lock_idempotency(owner_user_id, idempotency_key)
            replay = await self._draft_replay(
                uow, owner_user_id, idempotency_key, fingerprint, session_id
            )
            if replay is not None:
                return replay
            _, _, draft_count = await uow.count_session_children(owner_user_id, session_id)
            if draft_count >= self._policy.max_follow_up_drafts_per_session:
                raise InterviewPrepQuotaExceeded("follow-up draft limit reached")
            source_claims = self._select_session_claims(
                session.context.claims, command.source_claim_ids
            )
            await self._applications.validate_current_evidence(
                owner_user_id,
                session.application_id,
                self._current_evidence_pins(source_claims),
            )
            subject, body = self._render_follow_up_draft(
                session.context.job_title,
                source_claims,
            )
            now = self._clock.now()
            draft = FollowUpDraft(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                session_id=session.id,
                subject=subject,
                body=body,
                source_claims=source_claims,
                content_sha256=hashlib.sha256(f"{subject}\n{body}".encode()).hexdigest(),
                created_at=now,
            )
            self._validate_follow_up_numeric_grounding(draft)
            await uow.add_follow_up_draft(draft)
            await self._record_create(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "follow_up_draft",
                draft.id,
                InterviewAuditAction.FOLLOW_UP_DRAFT_GENERATED,
                context,
                now,
                application_id=session.application_id,
                session_id=session.id,
                claim_count=len(source_claims),
            )
            await uow.commit()
            return draft

    async def list_follow_up_drafts(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[FollowUpDraft]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_session(owner_user_id, session_id) is None:
                raise InterviewPrepNotFound
            items = await uow.list_follow_up_drafts(owner_user_id, session_id, after, page_size + 1)
        return page_result(items, cursor=after, limit=page_size)

    async def get_follow_up_draft_read(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        draft_id: UUID,
    ) -> FollowUpDraftReadView:
        async with self._uow() as uow:
            session = await uow.get_session(owner_user_id, session_id)
            draft = await uow.get_follow_up_draft(
                owner_user_id,
                session_id,
                draft_id,
            )
        if session is None or draft is None:
            raise InterviewPrepNotFound
        return FollowUpDraftReadView(
            draft=draft,
            grounding=await self._assess_claims(
                owner_user_id,
                session.application_id,
                draft.source_claims,
            ),
        )

    async def list_follow_up_draft_reads(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[FollowUpDraftReadView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            session = await uow.get_session(owner_user_id, session_id)
            if session is None:
                raise InterviewPrepNotFound
            items = await uow.list_follow_up_drafts(
                owner_user_id,
                session_id,
                after,
                page_size + 1,
            )
        result = page_result(items, cursor=after, limit=page_size)
        if not result.data:
            return PagedResult(data=(), page=result.page)
        merged_claims = tuple(claim for draft in result.data for claim in draft.source_claims)
        assessment = await self._assess_claims(
            owner_user_id,
            session.application_id,
            merged_claims,
        )
        return PagedResult(
            data=tuple(
                FollowUpDraftReadView(draft=draft, grounding=assessment) for draft in result.data
            ),
            page=result.page,
        )

    async def _assess_story(
        self,
        owner_user_id: UUID,
        story: StarStory,
    ) -> GroundingAssessment:
        if not story.claim_pins:
            return GroundingAssessment(
                GroundingStatus.NEEDS_REVIEW,
                "This story has no exact evidence revision pins.",
            )
        try:
            pins = self._story_evidence_pins((story,))
        except InterviewPrepConflict:
            return self._needs_grounding_review()
        return await self._assess_pins(owner_user_id, story.application_id, pins)

    async def _assess_stories(
        self,
        owner_user_id: UUID,
        stories: tuple[StarStory, ...],
    ) -> dict[UUID, GroundingAssessment]:
        assessments: dict[UUID, GroundingAssessment] = {}
        grouped: dict[UUID, list[StarStory]] = {}
        for story in stories:
            if not story.claim_pins:
                assessments[story.id] = GroundingAssessment(
                    GroundingStatus.NEEDS_REVIEW,
                    "This story has no exact evidence revision pins.",
                )
            else:
                grouped.setdefault(story.application_id, []).append(story)
        for application_id, application_stories in grouped.items():
            try:
                pins = self._story_evidence_pins(tuple(application_stories))
            except InterviewPrepConflict:
                assessment = self._needs_grounding_review()
            else:
                assessment = await self._assess_pins(
                    owner_user_id,
                    application_id,
                    pins,
                )
            for story in application_stories:
                assessments[story.id] = assessment
        return assessments

    async def _assess_session(
        self,
        owner_user_id: UUID,
        session: InterviewSession,
    ) -> GroundingAssessment:
        return await self._assess_claims(
            owner_user_id,
            session.application_id,
            session.context.claims,
        )

    async def _assess_sessions(
        self,
        owner_user_id: UUID,
        sessions: tuple[InterviewSession, ...],
    ) -> dict[UUID, GroundingAssessment]:
        assessments: dict[UUID, GroundingAssessment] = {}
        grouped: dict[tuple[UUID, str], list[InterviewSession]] = {}
        for session in sessions:
            grouped.setdefault(
                (session.application_id, session.context.snapshot_sha256),
                [],
            ).append(session)
        for (application_id, _snapshot), grouped_sessions in grouped.items():
            merged_claims = tuple(
                claim for session in grouped_sessions for claim in session.context.claims
            )
            assessment = await self._assess_claims(
                owner_user_id,
                application_id,
                merged_claims,
            )
            for session in grouped_sessions:
                assessments[session.id] = assessment
        return assessments

    async def _assess_question(
        self,
        owner_user_id: UUID,
        session: InterviewSession,
        question: InterviewQuestion,
    ) -> GroundingAssessment:
        if not (question.generated or question.source_claim_ids or question.source_requirement_ids):
            return GroundingAssessment(
                GroundingStatus.UNKNOWN,
                "This private question has no evidence-linked source context.",
            )
        return await self._assess_session(owner_user_id, session)

    async def _assess_claims(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        claims: tuple[SessionContextClaim, ...],
    ) -> GroundingAssessment:
        pins_by_evidence_id: dict[UUID, EvidenceRevisionPin] = {}
        for claim in claims:
            for pin in claim.evidence_pins:
                existing = pins_by_evidence_id.get(pin.evidence_id)
                if existing is not None and existing != pin:
                    return self._needs_grounding_review()
                pins_by_evidence_id.setdefault(pin.evidence_id, pin)
        if not pins_by_evidence_id:
            return GroundingAssessment(
                GroundingStatus.NEEDS_REVIEW,
                "This artifact has no exact evidence revision pins.",
            )
        return await self._assess_pins(
            owner_user_id,
            application_id,
            tuple(pins_by_evidence_id.values()),
        )

    async def _assess_pins(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        pins: tuple[EvidenceRevisionPin, ...],
    ) -> GroundingAssessment:
        try:
            await self._validate_current_evidence_pins(
                owner_user_id,
                application_id,
                pins,
            )
        except InterviewPrepUnavailable:
            return GroundingAssessment(
                GroundingStatus.UNKNOWN,
                "Current evidence eligibility could not be checked. Review before use.",
            )
        except (InterviewPrepConflict, InterviewPrepNotFound):
            return self._needs_grounding_review()
        return GroundingAssessment(GroundingStatus.CURRENT)

    @staticmethod
    def _needs_grounding_review() -> GroundingAssessment:
        return GroundingAssessment(
            GroundingStatus.NEEDS_REVIEW,
            "Pinned evidence is no longer current or generation-eligible. "
            "Review and re-ground this artifact before use.",
        )

    def _story_claim_pins(
        self,
        source: InterviewSourceSnapshot,
        selections: tuple[StoryClaimSelection, ...],
    ) -> tuple[StoryClaimPin, ...]:
        by_id = {claim.id: claim for claim in source.claims}
        if len({selection.claim_id for selection in selections}) != len(selections):
            raise InterviewPrepValidationError("story claim selections must be unique")
        pins: list[StoryClaimPin] = []
        for selection in selections:
            claim = by_id.get(selection.claim_id)
            if claim is None:
                raise InterviewPrepConflict(
                    "story references a claim outside the pinned application context"
                )
            pins.append(
                StoryClaimPin(
                    source_claim_id=claim.id,
                    claim_text=claim.text,
                    claim_sha256=claim.text_sha256,
                    strong=claim.strong,
                    field_names=selection.field_names,
                    evidence_pins=claim.evidence_pins,
                )
            )
        return tuple(pins)

    def _validate_story_grounding(self, story: StarStory) -> None:
        requires_grounding = (
            story.status is StoryStatus.READY or story.origin is StoryOrigin.GENERATED
        )
        if not requires_grounding:
            return
        if story.origin is StoryOrigin.GENERATED and story.status is not StoryStatus.READY:
            raise InterviewPrepValidationError("generated stories must be ready and fully grounded")
        covered = {field_name for pin in story.claim_pins for field_name in pin.field_names}
        missing = _READY_FIELDS - covered
        if missing:
            raise InterviewPrepConflict(
                "ready stories require claim provenance for every STAR field"
            )
        text_by_field = {
            StoryField.SITUATION: story.situation,
            StoryField.TASK: story.task,
            StoryField.ACTION: story.action,
            StoryField.RESULT: story.result,
            StoryField.PERSONAL_CONTRIBUTION: story.personal_contribution,
            StoryField.METRIC_EXPLANATION: story.metric_explanation or "",
        }
        numeric_fields = {
            field_name for field_name, value in text_by_field.items() if _numeric_tokens(value)
        }
        if numeric_fields and story.metric_explanation is None:
            raise InterviewPrepConflict("ready stories with numbers require a metric explanation")
        if story.metric_explanation is not None:
            numeric_fields.add(StoryField.METRIC_EXPLANATION)
        for field_name in numeric_fields:
            if field_name not in covered:
                raise InterviewPrepConflict(
                    "numeric story fields require exact claim and evidence provenance"
                )
        supported = {
            token
            for claim in story.claim_pins
            for pin in claim.evidence_pins
            for token in _numeric_tokens(pin.statement)
        }
        used = {token for value in text_by_field.values() for token in _numeric_tokens(value)}
        if not used.issubset(supported):
            raise InterviewPrepConflict(
                "story contains a number absent from its pinned evidence revisions"
            )

    async def _validate_ready_story_evidence(
        self,
        owner_user_id: UUID,
        story: StarStory,
    ) -> None:
        if story.status is not StoryStatus.READY:
            return
        await self._validate_current_evidence_pins(
            owner_user_id,
            story.application_id,
            self._story_evidence_pins((story,)),
        )

    async def _validate_current_evidence_pins(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None:
        for start in range(0, len(evidence_pins), _EVIDENCE_VALIDATION_BATCH_SIZE):
            await self._applications.validate_current_evidence(
                owner_user_id,
                application_id,
                evidence_pins[start : start + _EVIDENCE_VALIDATION_BATCH_SIZE],
            )

    def _session_context(self, source: InterviewSourceSnapshot) -> SessionContextSnapshot:
        claims = tuple(as_session_claim(claim) for claim in source.claims)
        requirements = tuple(
            SessionContextRequirement(item.id, item.text, item.importance)
            for item in source.requirements
        )
        payload = {
            "applicationId": str(source.application_id),
            "jobId": str(source.job_id),
            "jobVersion": source.job_version,
            "jobTitle": source.job_title.strip(),
            "company": source.company.strip() if source.company else None,
            "resumeVersionId": str(source.resume_version_id),
            "resumeVersionNumber": source.resume_version_number,
            "claims": [
                {
                    "id": str(claim.source_claim_id),
                    "sha256": claim.text_sha256,
                    "requirements": [str(item) for item in claim.requirement_ids],
                    "evidence": [
                        {
                            "id": str(pin.evidence_id),
                            "revisionId": str(pin.evidence_revision_id),
                            "revision": pin.revision_number,
                            "sha256": pin.statement_sha256,
                        }
                        for pin in claim.evidence_pins
                    ],
                }
                for claim in claims
            ],
            "requirements": [
                {
                    "id": str(item.requirement_id),
                    "text": item.text,
                    "importance": item.importance,
                }
                for item in requirements
            ],
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return SessionContextSnapshot(
            application_id=source.application_id,
            job_id=source.job_id,
            job_version=source.job_version,
            job_title=source.job_title.strip(),
            company=source.company.strip() if source.company else None,
            resume_version_id=source.resume_version_id,
            resume_version_number=source.resume_version_number,
            claims=claims,
            requirements=requirements,
            snapshot_sha256=digest,
        )

    def _generated_questions(
        self,
        owner_user_id: UUID,
        session: InterviewSession,
        now: datetime,
        *,
        starting_ordinal: int,
    ) -> tuple[InterviewQuestion, ...]:
        items: list[InterviewQuestion] = []
        for requirement in session.context.requirements:
            linked_claims = tuple(
                claim.source_claim_id
                for claim in session.context.claims
                if requirement.requirement_id in claim.requirement_ids
            )
            items.append(
                InterviewQuestion(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    session_id=session.id,
                    ordinal=starting_ordinal + len(items),
                    prompt=f"How would you demonstrate: {requirement.text}",
                    kind=QuestionKind.ROLE_SPECIFIC,
                    source_requirement_ids=(requirement.requirement_id,),
                    source_claim_ids=linked_claims,
                    generated=True,
                    created_at=now,
                )
            )
            if len(items) >= self._policy.max_questions_per_generation:
                break
        if not items:
            for claim in session.context.claims:
                items.append(
                    InterviewQuestion(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        session_id=session.id,
                        ordinal=starting_ordinal + len(items),
                        prompt=f"Explain the context and your contribution for: {claim.text}",
                        kind=QuestionKind.BEHAVIORAL,
                        source_requirement_ids=(),
                        source_claim_ids=(claim.source_claim_id,),
                        generated=True,
                        created_at=now,
                    )
                )
                if len(items) >= self._policy.max_questions_per_generation:
                    break
        if not items:
            raise InterviewPrepConflict(
                "grounded application context has no claims or requirements"
            )
        return tuple(items)

    @staticmethod
    def _render_follow_up_draft(
        job_title: str,
        source_claims: tuple[SessionContextClaim, ...],
    ) -> tuple[str, str]:
        normalized_title = " ".join(job_title.split())
        titled_subject = f"Thank you - {normalized_title}"
        # A complete title is preferable, but a generic subject is safer than
        # silently cutting a factual job title to fit the immutable 300-char field.
        subject = titled_subject if len(titled_subject) <= 300 else "Thank you for the conversation"
        claim_lines = " ".join(f"- {claim.text}" for claim in source_claims)
        body = " ".join(
            (
                f"Thank you for the conversation about {normalized_title}.",
                f"A relevant grounded point from my background: {claim_lines}",
                "I appreciate your time and consideration.",
            )
        )
        if len(body) > 8_000:
            raise InterviewPrepValidationError(
                "selected grounded claims exceed the follow-up draft rendering limit; "
                "select fewer claims"
            )
        return subject, body

    @staticmethod
    def _validate_question_sources(
        session: InterviewSession, command: CreateInterviewQuestion
    ) -> None:
        requirement_ids = {item.requirement_id for item in session.context.requirements}
        claim_ids = {item.source_claim_id for item in session.context.claims}
        if not set(command.source_requirement_ids).issubset(requirement_ids):
            raise InterviewPrepConflict("question references an unknown requirement")
        if not set(command.source_claim_ids).issubset(claim_ids):
            raise InterviewPrepConflict("question references an unknown claim")

    @staticmethod
    def _story_matches_claim(story: StarStory, source_claim: SourceClaim) -> bool:
        expected_evidence = tuple(
            (
                pin.evidence_id,
                pin.evidence_revision_id,
                pin.revision_number,
                pin.statement_sha256,
            )
            for pin in source_claim.evidence_pins
        )
        return any(
            pin.source_claim_id == source_claim.id
            and pin.claim_sha256 == source_claim.text_sha256
            and tuple(
                (
                    evidence.evidence_id,
                    evidence.evidence_revision_id,
                    evidence.revision_number,
                    evidence.statement_sha256,
                )
                for evidence in pin.evidence_pins
            )
            == expected_evidence
            for pin in story.claim_pins
        )

    @staticmethod
    def _story_evidence_pins(
        stories: tuple[StarStory, ...],
    ) -> tuple[EvidenceRevisionPin, ...]:
        pins_by_evidence_id: dict[UUID, EvidenceRevisionPin] = {}
        for story in stories:
            for claim in story.claim_pins:
                for pin in claim.evidence_pins:
                    existing = pins_by_evidence_id.get(pin.evidence_id)
                    if existing is not None and existing != pin:
                        raise InterviewPrepConflict(
                            "ready stories disagree on an exact evidence revision"
                        )
                    pins_by_evidence_id.setdefault(pin.evidence_id, pin)
        if not pins_by_evidence_id:
            raise InterviewPrepConflict("ready stories require exact evidence revisions")
        return tuple(pins_by_evidence_id.values())

    @staticmethod
    def _select_session_claims(
        claims: tuple[SessionContextClaim, ...], selected_ids: tuple[UUID, ...]
    ) -> tuple[SessionContextClaim, ...]:
        if not selected_ids or len(set(selected_ids)) != len(selected_ids):
            raise InterviewPrepValidationError("select one or more distinct grounded claims")
        by_id = {claim.source_claim_id: claim for claim in claims}
        try:
            return tuple(by_id[claim_id] for claim_id in selected_ids)
        except KeyError as exc:
            raise InterviewPrepConflict(
                "follow-up draft references a claim outside the immutable session context"
            ) from exc

    @staticmethod
    def _current_evidence_pins(
        claims: tuple[SessionContextClaim, ...],
    ) -> tuple[EvidenceRevisionPin, ...]:
        pins_by_evidence_id: dict[UUID, EvidenceRevisionPin] = {}
        for claim in claims:
            for pin in claim.evidence_pins:
                existing = pins_by_evidence_id.get(pin.evidence_id)
                if existing is not None and existing != pin:
                    raise InterviewPrepConflict(
                        "session claims disagree on an exact evidence revision"
                    )
                pins_by_evidence_id.setdefault(pin.evidence_id, pin)
        if len(pins_by_evidence_id) > 200:
            raise InterviewPrepConflict(
                "session evidence exceeds the supported generation boundary"
            )
        return tuple(pins_by_evidence_id.values())

    @staticmethod
    def _validate_follow_up_numeric_grounding(draft: FollowUpDraft) -> None:
        supported = {
            token
            for claim in draft.source_claims
            for pin in claim.evidence_pins
            for token in _numeric_tokens(pin.statement)
        }
        claim_numbers = {
            token for claim in draft.source_claims for token in _numeric_tokens(claim.text)
        }
        if not claim_numbers.issubset(supported):
            raise InterviewPrepConflict(
                "follow-up draft contains a number absent from pinned evidence"
            )

    @staticmethod
    def _validate_source(source: InterviewSourceSnapshot, application_id: UUID) -> None:
        if source.application_id != application_id:
            raise InterviewPrepConflict("application context scope does not match")
        if (
            type(source.job_version) is not int
            or not 1 <= source.job_version <= 2_147_483_647
            or type(source.resume_version_number) is not int
            or not 1 <= source.resume_version_number <= 2_147_483_647
            or not source.job_title.strip()
        ):
            raise InterviewPrepConflict("application context version is invalid")
        claims = {claim.id: claim for claim in source.claims}
        requirements = {item.id for item in source.requirements}
        if len(claims) != len(source.claims) or len(requirements) != len(source.requirements):
            raise InterviewPrepConflict("application context contains duplicate identifiers")
        for claim in source.claims:
            normalized_claim = claim.text.strip()
            expected = hashlib.sha256(normalized_claim.encode()).hexdigest()
            if not 1 <= len(normalized_claim) <= 1_000 or "\x00" in normalized_claim:
                raise InterviewPrepConflict("application claim text is invalid")
            if claim.text_sha256 != expected:
                raise InterviewPrepConflict("application claim hash is invalid")
            if not claim.evidence_pins:
                raise InterviewPrepConflict("application claim is not grounded")
            evidence_revisions = {
                (pin.evidence_id, pin.evidence_revision_id) for pin in claim.evidence_pins
            }
            if len(evidence_revisions) != len(claim.evidence_pins):
                raise InterviewPrepConflict("application claim evidence revisions are duplicated")
            used_numbers = _numeric_tokens(normalized_claim)
            supported_numbers = {
                token for pin in claim.evidence_pins for token in _numeric_tokens(pin.statement)
            }
            if not used_numbers.issubset(supported_numbers):
                raise InterviewPrepConflict(
                    "application claim contains a number absent from pinned evidence"
                )
            if len(set(claim.requirement_ids)) != len(claim.requirement_ids):
                raise InterviewPrepConflict("application claim requirement links are duplicated")
            if not set(claim.requirement_ids).issubset(requirements):
                raise InterviewPrepConflict("application claim requirement scope is invalid")

    async def _session_view(
        self, uow: InterviewPrepUnitOfWork, session: InterviewSession
    ) -> SessionView:
        counts = await uow.count_session_children_batch(
            session.owner_user_id,
            (session.id,),
        )
        return self._session_view_from_counts(
            session,
            counts.get(session.id, (0, 0, 0, 0)),
        )

    @staticmethod
    def _session_view_from_counts(
        session: InterviewSession,
        counts: tuple[int, int, int, int],
    ) -> SessionView:
        question_count, note_count, draft_count, generated_count = counts
        return SessionView(
            session,
            question_count,
            note_count,
            draft_count,
            generated_count > 0,
            session.id if generated_count > 0 else None,
        )

    async def _story_replay(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
    ) -> StarStory | None:
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        self._assert_replay(record, fingerprint, "star_story")
        if record.response_snapshot is None:
            raise InterviewPrepConflict("idempotent story response was redacted after deletion")
        return record.response_snapshot.restore()

    async def _session_replay(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
    ) -> InterviewSession | None:
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        self._assert_replay(record, fingerprint, "interview_session")
        result = await uow.get_session(owner_user_id, record.resource_id)
        if result is None:
            raise InterviewPrepConflict("idempotent session result was deleted")
        return result

    async def _question_replay(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        session_id: UUID,
    ) -> InterviewQuestion | None:
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        self._assert_replay(record, fingerprint, "interview_question")
        result = await uow.get_question(owner_user_id, session_id, record.resource_id)
        if result is None:
            raise InterviewPrepConflict("idempotent question result is unavailable")
        return result

    async def _note_replay(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        session_id: UUID,
    ) -> InterviewSessionNote | None:
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        self._assert_replay(record, fingerprint, "session_note")
        result = await uow.get_note(owner_user_id, session_id, record.resource_id)
        if result is None:
            raise InterviewPrepConflict("idempotent note result was deleted")
        return result

    async def _draft_replay(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        session_id: UUID,
    ) -> FollowUpDraft | None:
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        self._assert_replay(record, fingerprint, "follow_up_draft")
        result = await uow.get_follow_up_draft(owner_user_id, session_id, record.resource_id)
        if result is None:
            raise InterviewPrepConflict("idempotent follow-up draft is unavailable")
        return result

    @staticmethod
    def _assert_replay(
        record: InterviewIdempotencyRecord,
        fingerprint: str,
        resource_kind: str,
        resource_id: UUID | None = None,
    ) -> None:
        if (
            record.request_fingerprint != fingerprint
            or record.resource_kind != resource_kind
            or (resource_id is not None and record.resource_id != resource_id)
        ):
            raise InterviewPrepIdempotencyConflict

    async def _record_create(
        self,
        uow: InterviewPrepUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        resource_kind: str,
        resource_id: UUID,
        action: InterviewAuditAction,
        context: RequestContext,
        now: datetime,
        response_snapshot: StarStoryReplaySnapshot | None = None,
        **metadata: UUID | int | str,
    ) -> None:
        await uow.add_idempotency(
            InterviewIdempotencyRecord(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                resource_kind=resource_kind,
                resource_id=resource_id,
                created_at=now,
                response_snapshot=response_snapshot,
            )
        )
        await uow.add_audit(
            self._audit(
                owner_user_id,
                action,
                resource_kind,
                resource_id,
                context,
                now,
                **metadata,
            )
        )

    def _audit(
        self,
        owner_user_id: UUID,
        action: InterviewAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        now: datetime,
        **metadata: UUID | int | str,
    ) -> InterviewAuditEvent:
        return InterviewAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            metadata=tuple((key, str(value)) for key, value in metadata.items()),
            created_at=now,
        )

    def _authorize(self, owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise InterviewPrepNotFound

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if type(expected) is not int or not 1 <= expected <= 2_147_483_647:
            raise InterviewPrepValidationError("expected version must be a positive int32")
        if actual != expected:
            raise InterviewPrepVersionConflict

    @staticmethod
    def _idempotency_key(value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise InterviewPrepValidationError("idempotency key is invalid")

    def _page_size(self, value: int | None) -> int:
        if value is None:
            return self._policy.default_page_size
        if type(value) is not int or not 1 <= value <= self._policy.max_page_size:
            raise InterviewPrepValidationError("page limit is out of range")
        return value


def _numeric_tokens(value: str) -> frozenset[str]:
    return frozenset(match.group(0).replace(",", "") for match in _NUMERIC_TOKEN.finditer(value))


def _fingerprint(kind: str, value: object) -> str:
    payload = json.dumps(
        {"kind": kind, "value": _jsonable(value)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _jsonable(value: Any) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (StoryField, StoryStatus, StoryOrigin)):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
