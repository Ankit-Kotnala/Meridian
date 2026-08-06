"""Deterministic in-memory ports for Interview Prep service tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from rezumi.modules.interview_prep.application import (
    InterviewSourceSnapshot,
    PageCursor,
    SourceClaim,
    SourceRequirement,
    StoryFilter,
)
from rezumi.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewAuditEvent,
    InterviewIdempotencyRecord,
    InterviewPrepConflict,
    InterviewPrepNotFound,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionNote,
    StarStory,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000901")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000902")
APPLICATION_ID = UUID("00000000-0000-4000-8000-000000000903")
JOB_ID = UUID("00000000-0000-4000-8000-000000000904")
RESUME_VERSION_ID = UUID("00000000-0000-4000-8000-000000000905")
CLAIM_ID = UUID("00000000-0000-4000-8000-000000000906")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000907")
EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-000000000908")
REQUIREMENT_ID = UUID("00000000-0000-4000-8000-000000000909")
NOW = datetime(2026, 7, 25, 9, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticApplicationContext:
    def __init__(self, snapshot: InterviewSourceSnapshot | None = None) -> None:
        self.value = snapshot or source_snapshot()
        self.calls = 0
        self.current_evidence_pins = tuple(
            {
                pin.evidence_id: pin for claim in self.value.claims for pin in claim.evidence_pins
            }.values()
        )
        self.validation_calls: list[tuple[UUID, UUID, tuple[EvidenceRevisionPin, ...]]] = []
        self.validation_error: Exception | None = None

    async def snapshot(self, owner_user_id: UUID, application_id: UUID) -> InterviewSourceSnapshot:
        if owner_user_id != OWNER_ID or application_id != APPLICATION_ID:
            raise InterviewPrepNotFound
        self.calls += 1
        return deepcopy(self.value)

    async def validate_current_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None:
        if owner_user_id != OWNER_ID or application_id != APPLICATION_ID:
            raise InterviewPrepNotFound
        self.validation_calls.append((owner_user_id, application_id, deepcopy(evidence_pins)))
        if self.validation_error is not None:
            raise self.validation_error
        current_by_evidence_id = {pin.evidence_id: pin for pin in self.current_evidence_pins}
        if len(evidence_pins) != len({pin.evidence_id for pin in evidence_pins}) or any(
            current_by_evidence_id.get(pin.evidence_id) != pin for pin in evidence_pins
        ):
            raise InterviewPrepConflict("test evidence is not the exact current evidence")


class MemoryInterviewPrep:
    def __init__(self) -> None:
        self.stories: dict[UUID, StarStory] = {}
        self.sessions: dict[UUID, InterviewSession] = {}
        self.questions: dict[UUID, InterviewQuestion] = {}
        self.notes: dict[UUID, InterviewSessionNote] = {}
        self.drafts: dict[UUID, FollowUpDraft] = {}
        self.idempotency: dict[tuple[UUID, str], InterviewIdempotencyRecord] = {}
        self.audits: list[InterviewAuditEvent] = []
        self.lock_events: list[tuple[str, UUID, object]] = []
        self.commits = 0

    def __call__(self) -> MemoryInterviewPrep:
        return self

    async def __aenter__(self) -> MemoryInterviewPrep:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def lock_owner(self, owner_user_id: UUID) -> None:
        self.lock_events.append(("owner", owner_user_id, None))

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None:
        self.lock_events.append(("idempotency", owner_user_id, idempotency_key))

    async def count_stories(self, owner_user_id: UUID) -> int:
        return sum(story.owner_user_id == owner_user_id for story in self.stories.values())

    async def add_story(self, story: StarStory) -> None:
        self.stories[story.id] = deepcopy(story)

    async def save_story(self, story: StarStory) -> None:
        self.stories[story.id] = deepcopy(story)

    async def get_story(
        self, owner_user_id: UUID, story_id: UUID, *, for_update: bool = False
    ) -> StarStory | None:
        if for_update:
            self.lock_events.append(("story", owner_user_id, story_id))
        story = self.stories.get(story_id)
        if story is None or story.owner_user_id != owner_user_id:
            return None
        return deepcopy(story)

    async def list_stories(
        self,
        owner_user_id: UUID,
        filter_by: StoryFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[StarStory]:
        stories = [
            story
            for story in self.stories.values()
            if story.owner_user_id == owner_user_id
            and (
                filter_by.application_id is None or story.application_id == filter_by.application_id
            )
            and (filter_by.status is None or story.status == filter_by.status)
        ]
        stories.sort(key=lambda item: (item.updated_at, str(item.id)), reverse=True)
        offset = after.offset if after else 0
        return deepcopy(stories[offset : offset + limit])

    async def delete_story(self, owner_user_id: UUID, story_id: UUID) -> None:
        story = self.stories.get(story_id)
        if story is not None and story.owner_user_id == owner_user_id:
            self.stories.pop(story_id)

    async def redact_story_replay_snapshot(self, owner_user_id: UUID, story_id: UUID) -> None:
        for key, record in tuple(self.idempotency.items()):
            if (
                record.owner_user_id == owner_user_id
                and record.resource_kind == "star_story"
                and record.resource_id == story_id
            ):
                self.idempotency[key] = replace(record, response_snapshot=None)

    async def count_sessions(self, owner_user_id: UUID) -> int:
        return sum(session.owner_user_id == owner_user_id for session in self.sessions.values())

    async def add_session(self, session: InterviewSession) -> None:
        self.sessions[session.id] = deepcopy(session)

    async def save_session(self, session: InterviewSession) -> None:
        self.sessions[session.id] = deepcopy(session)

    async def get_session(
        self, owner_user_id: UUID, session_id: UUID, *, for_update: bool = False
    ) -> InterviewSession | None:
        if for_update:
            self.lock_events.append(("session", owner_user_id, session_id))
        session = self.sessions.get(session_id)
        if session is None or session.owner_user_id != owner_user_id:
            return None
        return deepcopy(session)

    async def list_sessions(
        self,
        owner_user_id: UUID,
        application_id: UUID | None,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSession]:
        sessions = [
            session
            for session in self.sessions.values()
            if session.owner_user_id == owner_user_id
            and (application_id is None or session.application_id == application_id)
        ]
        sessions.sort(key=lambda item: (item.updated_at, str(item.id)), reverse=True)
        offset = after.offset if after else 0
        return deepcopy(sessions[offset : offset + limit])

    async def delete_session(self, owner_user_id: UUID, session_id: UUID) -> None:
        session = self.sessions.get(session_id)
        if session is None or session.owner_user_id != owner_user_id:
            return
        self.sessions.pop(session_id)
        self.questions = {
            item_id: item
            for item_id, item in self.questions.items()
            if item.session_id != session_id
        }
        self.notes = {
            item_id: item for item_id, item in self.notes.items() if item.session_id != session_id
        }
        self.drafts = {
            item_id: item for item_id, item in self.drafts.items() if item.session_id != session_id
        }

    async def add_question(self, question: InterviewQuestion) -> None:
        self.questions[question.id] = deepcopy(question)

    async def add_questions(self, questions: tuple[InterviewQuestion, ...]) -> None:
        for question in questions:
            self.questions[question.id] = deepcopy(question)

    async def get_question(
        self, owner_user_id: UUID, session_id: UUID, question_id: UUID
    ) -> InterviewQuestion | None:
        question = self.questions.get(question_id)
        if (
            question is None
            or question.owner_user_id != owner_user_id
            or question.session_id != session_id
            or not self._owned_session(owner_user_id, session_id)
        ):
            return None
        return deepcopy(question)

    async def list_questions(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewQuestion]:
        if not self._owned_session(owner_user_id, session_id):
            return []
        items = sorted(
            (
                item
                for item in self.questions.values()
                if item.owner_user_id == owner_user_id and item.session_id == session_id
            ),
            key=lambda item: item.ordinal,
        )
        offset = after.offset if after else 0
        return deepcopy(items[offset : offset + limit])

    async def add_note(self, note: InterviewSessionNote) -> None:
        self.notes[note.id] = deepcopy(note)

    async def save_note(self, note: InterviewSessionNote) -> None:
        self.notes[note.id] = deepcopy(note)

    async def get_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        note_id: UUID,
        *,
        for_update: bool = False,
    ) -> InterviewSessionNote | None:
        if for_update:
            self.lock_events.append(("note", owner_user_id, note_id))
        note = self.notes.get(note_id)
        if (
            note is None
            or note.owner_user_id != owner_user_id
            or note.session_id != session_id
            or not self._owned_session(owner_user_id, session_id)
        ):
            return None
        return deepcopy(note)

    async def list_notes(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSessionNote]:
        if not self._owned_session(owner_user_id, session_id):
            return []
        items = sorted(
            (
                item
                for item in self.notes.values()
                if item.owner_user_id == owner_user_id and item.session_id == session_id
            ),
            key=lambda item: (item.created_at, str(item.id)),
            reverse=True,
        )
        offset = after.offset if after else 0
        return deepcopy(items[offset : offset + limit])

    async def delete_note(self, owner_user_id: UUID, session_id: UUID, note_id: UUID) -> None:
        note = self.notes.get(note_id)
        if (
            note is not None
            and note.owner_user_id == owner_user_id
            and note.session_id == session_id
        ):
            self.notes.pop(note_id)

    async def add_follow_up_draft(self, draft: FollowUpDraft) -> None:
        self.drafts[draft.id] = deepcopy(draft)

    async def get_follow_up_draft(
        self, owner_user_id: UUID, session_id: UUID, draft_id: UUID
    ) -> FollowUpDraft | None:
        draft = self.drafts.get(draft_id)
        if (
            draft is None
            or draft.owner_user_id != owner_user_id
            or draft.session_id != session_id
            or not self._owned_session(owner_user_id, session_id)
        ):
            return None
        return deepcopy(draft)

    async def list_follow_up_drafts(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[FollowUpDraft]:
        if not self._owned_session(owner_user_id, session_id):
            return []
        items = sorted(
            (
                item
                for item in self.drafts.values()
                if item.owner_user_id == owner_user_id and item.session_id == session_id
            ),
            key=lambda item: (item.created_at, str(item.id)),
            reverse=True,
        )
        offset = after.offset if after else 0
        return deepcopy(items[offset : offset + limit])

    async def count_session_children(
        self, owner_user_id: UUID, session_id: UUID
    ) -> tuple[int, int, int]:
        if not self._owned_session(owner_user_id, session_id):
            return 0, 0, 0
        return (
            sum(item.session_id == session_id for item in self.questions.values()),
            sum(item.session_id == session_id for item in self.notes.values()),
            sum(item.session_id == session_id for item in self.drafts.values()),
        )

    async def count_session_children_batch(
        self,
        owner_user_id: UUID,
        session_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[int, int, int, int]]:
        result: dict[UUID, tuple[int, int, int, int]] = {}
        for session_id in dict.fromkeys(session_ids):
            if not self._owned_session(owner_user_id, session_id):
                continue
            questions = [
                item
                for item in self.questions.values()
                if item.owner_user_id == owner_user_id and item.session_id == session_id
            ]
            result[session_id] = (
                len(questions),
                sum(
                    item.owner_user_id == owner_user_id and item.session_id == session_id
                    for item in self.notes.values()
                ),
                sum(
                    item.owner_user_id == owner_user_id and item.session_id == session_id
                    for item in self.drafts.values()
                ),
                sum(item.generated for item in questions),
            )
        return result

    async def add_idempotency(self, record: InterviewIdempotencyRecord) -> None:
        self.idempotency[(record.owner_user_id, record.idempotency_key)] = deepcopy(record)

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> InterviewIdempotencyRecord | None:
        return deepcopy(self.idempotency.get((owner_user_id, idempotency_key)))

    async def add_audit(self, event: InterviewAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def commit(self) -> None:
        self.commits += 1

    def _owned_session(self, owner_user_id: UUID, session_id: UUID) -> bool:
        session = self.sessions.get(session_id)
        return session is not None and session.owner_user_id == owner_user_id


def source_snapshot(
    *,
    statement: str = "Led a 12-person launch and improved adoption by 25%.",
    claim_text: str | None = None,
    strong: bool = True,
) -> InterviewSourceSnapshot:
    claim = (claim_text or statement).strip()
    evidence = statement.strip()
    pin = EvidenceRevisionPin(
        evidence_id=EVIDENCE_ID,
        evidence_revision_id=EVIDENCE_REVISION_ID,
        revision_number=4,
        statement=evidence,
        statement_sha256=hashlib.sha256(evidence.encode()).hexdigest(),
        strength="confirmed",
        has_numeric_claim=bool(any(character.isdigit() for character in evidence)),
    )
    return InterviewSourceSnapshot(
        application_id=APPLICATION_ID,
        job_id=JOB_ID,
        job_version=3,
        job_title="Principal Product Engineer",
        company="Example Co",
        resume_version_id=RESUME_VERSION_ID,
        resume_version_number=7,
        claims=(
            SourceClaim(
                id=CLAIM_ID,
                text=claim,
                text_sha256=hashlib.sha256(claim.encode()).hexdigest(),
                strong=strong,
                requirement_ids=(REQUIREMENT_ID,),
                evidence_pins=(pin,),
            ),
        ),
        requirements=(
            SourceRequirement(
                id=REQUIREMENT_ID,
                text="Lead cross-functional product delivery.",
                importance="mandatory",
            ),
        ),
    )


def _uuids() -> Iterator[UUID]:
    index = 1
    while True:
        yield uuid5(NAMESPACE_URL, f"rezumi-interview-test:{index}")
        index += 1
