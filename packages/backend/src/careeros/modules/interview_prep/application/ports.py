"""Inward-facing ports for Interview Prep use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewAuditEvent,
    InterviewIdempotencyRecord,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionNote,
    StarStory,
)

from .models import InterviewSourceSnapshot, PageCursor, StoryFilter


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class ApplicationInterviewContextProvider(Protocol):
    async def snapshot(
        self, owner_user_id: UUID, application_id: UUID
    ) -> InterviewSourceSnapshot: ...

    async def validate_current_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None: ...


class InterviewPrepUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_owner(self, owner_user_id: UUID) -> None: ...

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None: ...

    async def count_stories(self, owner_user_id: UUID) -> int: ...

    async def add_story(self, story: StarStory) -> None: ...

    async def save_story(self, story: StarStory) -> None: ...

    async def get_story(
        self, owner_user_id: UUID, story_id: UUID, *, for_update: bool = False
    ) -> StarStory | None: ...

    async def list_stories(
        self,
        owner_user_id: UUID,
        filter_by: StoryFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[StarStory]: ...

    async def delete_story(self, owner_user_id: UUID, story_id: UUID) -> None: ...

    async def redact_story_replay_snapshot(self, owner_user_id: UUID, story_id: UUID) -> None: ...

    async def count_sessions(self, owner_user_id: UUID) -> int: ...

    async def add_session(self, session: InterviewSession) -> None: ...

    async def save_session(self, session: InterviewSession) -> None: ...

    async def get_session(
        self, owner_user_id: UUID, session_id: UUID, *, for_update: bool = False
    ) -> InterviewSession | None: ...

    async def list_sessions(
        self,
        owner_user_id: UUID,
        application_id: UUID | None,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSession]: ...

    async def delete_session(self, owner_user_id: UUID, session_id: UUID) -> None: ...

    async def add_question(self, question: InterviewQuestion) -> None: ...

    async def add_questions(self, questions: tuple[InterviewQuestion, ...]) -> None: ...

    async def get_question(
        self, owner_user_id: UUID, session_id: UUID, question_id: UUID
    ) -> InterviewQuestion | None: ...

    async def list_questions(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewQuestion]: ...

    async def add_note(self, note: InterviewSessionNote) -> None: ...

    async def save_note(self, note: InterviewSessionNote) -> None: ...

    async def get_note(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        note_id: UUID,
        *,
        for_update: bool = False,
    ) -> InterviewSessionNote | None: ...

    async def list_notes(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[InterviewSessionNote]: ...

    async def delete_note(self, owner_user_id: UUID, session_id: UUID, note_id: UUID) -> None: ...

    async def add_follow_up_draft(self, draft: FollowUpDraft) -> None: ...

    async def get_follow_up_draft(
        self, owner_user_id: UUID, session_id: UUID, draft_id: UUID
    ) -> FollowUpDraft | None: ...

    async def list_follow_up_drafts(
        self,
        owner_user_id: UUID,
        session_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[FollowUpDraft]: ...

    async def count_session_children(
        self, owner_user_id: UUID, session_id: UUID
    ) -> tuple[int, int, int]: ...

    async def count_session_children_batch(
        self,
        owner_user_id: UUID,
        session_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[int, int, int, int]]: ...

    async def add_idempotency(self, record: InterviewIdempotencyRecord) -> None: ...

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> InterviewIdempotencyRecord | None: ...

    async def add_audit(self, event: InterviewAuditEvent) -> None: ...

    async def commit(self) -> None: ...


InterviewPrepUnitOfWorkFactory = Callable[[], InterviewPrepUnitOfWork]
