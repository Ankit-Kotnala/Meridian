"""Transport-neutral Interview Prep commands and purpose-limited views."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from rezumi.modules.interview_prep.domain import (
    DefenseStatus,
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewPrepValidationError,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionKind,
    InterviewSessionNote,
    QuestionKind,
    SessionContextClaim,
    SessionNoteKind,
    StarStory,
    StoryField,
    StoryOrigin,
    StoryStatus,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class PageCursor:
    offset: int

    def __post_init__(self) -> None:
        if type(self.offset) is not int or not 0 <= self.offset <= 10_000:
            raise InterviewPrepValidationError("cursor is invalid")

    @classmethod
    def decode(cls, value: str | None) -> PageCursor | None:
        if value is None:
            return None
        if len(value) > 256:
            raise InterviewPrepValidationError("cursor is invalid")
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii") + b"===")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {"offset"}:
                raise ValueError
            offset = payload["offset"]
        except (
            binascii.Error,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise InterviewPrepValidationError("cursor is invalid") from exc
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise InterviewPrepValidationError("cursor is invalid")
        return cls(offset)

    def encode(self) -> str:
        payload = json.dumps({"offset": self.offset}, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    has_more: bool
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class PagedResult[T]:
    data: tuple[T, ...]
    page: Page


class GroundingStatus(StrEnum):
    CURRENT = "current"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GroundingAssessment:
    status: GroundingStatus
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class StoryReadView:
    story: StarStory
    grounding: GroundingAssessment


@dataclass(frozen=True, slots=True)
class QuestionReadView:
    question: InterviewQuestion
    grounding: GroundingAssessment


@dataclass(frozen=True, slots=True)
class FollowUpDraftReadView:
    draft: FollowUpDraft
    grounding: GroundingAssessment


def page_result[T](items: list[T], *, cursor: PageCursor | None, limit: int) -> PagedResult[T]:
    visible = tuple(items[:limit])
    has_more = len(items) > limit
    offset = cursor.offset if cursor else 0
    return PagedResult(
        data=visible,
        page=Page(
            limit=limit,
            has_more=has_more,
            next_cursor=PageCursor(offset + limit).encode() if has_more else None,
        ),
    )


@dataclass(frozen=True, slots=True)
class SourceRequirement:
    id: UUID
    text: str
    importance: str


@dataclass(frozen=True, slots=True)
class SourceClaim:
    id: UUID
    text: str
    text_sha256: str
    strong: bool
    requirement_ids: tuple[UUID, ...]
    evidence_pins: tuple[EvidenceRevisionPin, ...]


@dataclass(frozen=True, slots=True)
class InterviewSourceSnapshot:
    """Only the grounded Phase 8 fields needed by Interview Prep."""

    application_id: UUID
    job_id: UUID
    job_version: int
    job_title: str
    company: str | None
    resume_version_id: UUID
    resume_version_number: int
    claims: tuple[SourceClaim, ...]
    requirements: tuple[SourceRequirement, ...]


@dataclass(frozen=True, slots=True)
class StoryClaimSelection:
    claim_id: UUID
    field_names: tuple[StoryField, ...]


@dataclass(frozen=True, slots=True)
class CreateStarStory:
    application_id: UUID
    title: str
    situation: str
    task: str
    action: str
    result: str
    personal_contribution: str
    metric_explanation: str | None
    confidence: int
    follow_up_questions: tuple[str, ...] = ()
    status: StoryStatus = StoryStatus.DRAFT
    origin: StoryOrigin = StoryOrigin.USER_AUTHORED
    claim_selections: tuple[StoryClaimSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateStarStory:
    title: str
    situation: str
    task: str
    action: str
    result: str
    personal_contribution: str
    metric_explanation: str | None
    confidence: int
    follow_up_questions: tuple[str, ...]
    status: StoryStatus
    claim_selections: tuple[StoryClaimSelection, ...]


@dataclass(frozen=True, slots=True)
class StoryFilter:
    application_id: UUID | None = None
    status: StoryStatus | None = None


@dataclass(frozen=True, slots=True)
class DefenseMapEntry:
    claim_id: UUID
    claim_text: str
    strong: bool
    status: DefenseStatus
    story_ids: tuple[UUID, ...]
    evidence_revision_ids: tuple[UUID, ...]
    warning: str | None


@dataclass(frozen=True, slots=True)
class DefenseMap:
    application_id: UUID
    entries: tuple[DefenseMapEntry, ...]
    defended_count: int
    partial_count: int
    undefended_count: int
    strong_claim_warning_count: int


@dataclass(frozen=True, slots=True)
class CreateInterviewSession:
    application_id: UUID
    title: str
    kind: InterviewSessionKind
    scheduled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UpdateInterviewSession:
    title: str
    kind: InterviewSessionKind
    scheduled_at: datetime | None


@dataclass(frozen=True, slots=True)
class SessionView:
    session: InterviewSession
    question_count: int
    note_count: int
    follow_up_draft_count: int
    question_bank_generated: bool = False
    question_bank_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SessionReadView:
    view: SessionView
    grounding: GroundingAssessment


@dataclass(frozen=True, slots=True)
class CreateInterviewQuestion:
    prompt: str
    kind: QuestionKind = QuestionKind.CUSTOM
    source_requirement_ids: tuple[UUID, ...] = ()
    source_claim_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateSessionNote:
    kind: SessionNoteKind
    body: str


@dataclass(frozen=True, slots=True)
class UpdateSessionNote:
    kind: SessionNoteKind
    body: str


@dataclass(frozen=True, slots=True)
class GenerateFollowUpDraft:
    source_claim_ids: tuple[UUID, ...]


def as_session_claim(source: SourceClaim) -> SessionContextClaim:
    return SessionContextClaim(
        source_claim_id=source.id,
        text=source.text,
        text_sha256=source.text_sha256,
        strong=source.strong,
        requirement_ids=source.requirement_ids,
        evidence_pins=source.evidence_pins,
    )


InterviewResource = (
    StarStory | InterviewSession | InterviewQuestion | InterviewSessionNote | FollowUpDraft
)
