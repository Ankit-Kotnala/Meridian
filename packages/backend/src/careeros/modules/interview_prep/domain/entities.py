"""Interview Prep domain entities and truth-locking policies."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .errors import InterviewPrepConflict, InterviewPrepValidationError

MAX_INT32 = 2_147_483_647
ELIGIBLE_EVIDENCE_STRENGTHS = frozenset({"supported", "confirmed", "verified"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NUMERIC_TOKEN = re.compile(r"(?<!\w)(?:[$€£]?[-+]?\d[\d,]*(?:\.\d+)?%?)(?!\w)")


def normalize_text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise InterviewPrepValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise InterviewPrepValidationError(f"{field} contains unsupported characters")
    return normalized


def optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None or not value.strip():
        return None
    return normalize_text(value, field, maximum)


def positive_version(value: int, field: str = "version") -> None:
    if type(value) is not int or not 1 <= value <= MAX_INT32:
        raise InterviewPrepValidationError(f"{field} must be a positive int32")


def aware_datetime(value: datetime | None, field: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise InterviewPrepValidationError(f"{field} must include a timezone")


def sha256(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if _SHA256.fullmatch(normalized) is None:
        raise InterviewPrepValidationError(f"{field} must be a lowercase SHA-256 digest")
    return normalized


class StoryStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"


class StoryOrigin(StrEnum):
    USER_AUTHORED = "user_authored"
    GENERATED = "generated"


class StoryField(StrEnum):
    SITUATION = "situation"
    TASK = "task"
    ACTION = "action"
    RESULT = "result"
    PERSONAL_CONTRIBUTION = "personal_contribution"
    METRIC_EXPLANATION = "metric_explanation"


class DefenseStatus(StrEnum):
    DEFENDED = "defended"
    PARTIAL = "partial"
    UNDEFENDED = "undefended"


class InterviewSessionKind(StrEnum):
    RECRUITER_SCREEN = "recruiter_screen"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    HIRING_MANAGER = "hiring_manager"
    PANEL = "panel"
    OTHER = "other"


class QuestionKind(StrEnum):
    BEHAVIORAL = "behavioral"
    ROLE_SPECIFIC = "role_specific"
    TECHNICAL = "technical"
    COMPANY = "company"
    FOLLOW_UP = "follow_up"
    CUSTOM = "custom"


class SessionNoteKind(StrEnum):
    PRIVATE_NOTE = "private_note"
    REFLECTION = "reflection"


class InterviewAuditAction(StrEnum):
    STORY_CREATED = "story_created"
    STORY_UPDATED = "story_updated"
    STORY_DELETED = "story_deleted"
    SESSION_CREATED = "session_created"
    SESSION_UPDATED = "session_updated"
    SESSION_DELETED = "session_deleted"
    QUESTION_CREATED = "question_created"
    QUESTIONS_GENERATED = "questions_generated"
    NOTE_CREATED = "note_created"
    NOTE_UPDATED = "note_updated"
    NOTE_DELETED = "note_deleted"
    FOLLOW_UP_DRAFT_GENERATED = "follow_up_draft_generated"


@dataclass(frozen=True, slots=True)
class EvidenceRevisionPin:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement: str
    statement_sha256: str
    strength: str
    has_numeric_claim: bool

    def __post_init__(self) -> None:
        positive_version(self.revision_number, "evidence revision number")
        object.__setattr__(
            self, "statement", normalize_text(self.statement, "evidence statement", 8_000)
        )
        object.__setattr__(
            self,
            "statement_sha256",
            sha256(self.statement_sha256, "evidence statement hash"),
        )
        expected = hashlib.sha256(self.statement.encode("utf-8")).hexdigest()
        if self.statement_sha256 != expected:
            raise InterviewPrepValidationError(
                "evidence statement hash must match the pinned statement"
            )
        if self.strength not in ELIGIBLE_EVIDENCE_STRENGTHS:
            raise InterviewPrepValidationError(
                "only generation-eligible evidence may ground interview content"
            )


@dataclass(frozen=True, slots=True)
class StoryClaimPin:
    source_claim_id: UUID
    claim_text: str
    claim_sha256: str
    strong: bool
    field_names: tuple[StoryField, ...]
    evidence_pins: tuple[EvidenceRevisionPin, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claim_text", normalize_text(self.claim_text, "source claim", 1_000)
        )
        object.__setattr__(
            self,
            "claim_sha256",
            sha256(self.claim_sha256, "source claim hash"),
        )
        if self.claim_sha256 != hashlib.sha256(self.claim_text.encode("utf-8")).hexdigest():
            raise InterviewPrepValidationError("source claim hash must match the pinned claim text")
        if not self.field_names or len(set(self.field_names)) != len(self.field_names):
            raise InterviewPrepValidationError(
                "a story claim must map to distinct structured fields"
            )
        if not self.evidence_pins:
            raise InterviewPrepValidationError("a story claim requires exact evidence revisions")
        evidence_ids = [pin.evidence_id for pin in self.evidence_pins]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InterviewPrepValidationError("story claim evidence links must be unique")


@dataclass(slots=True)
class StarStory:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
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
    origin: StoryOrigin
    claim_pins: tuple[StoryClaimPin, ...]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self._normalize()
        positive_version(self.version)
        aware_datetime(self.created_at, "story created time")
        aware_datetime(self.updated_at, "story updated time")
        validate_story_grounding(self)

    def _normalize(self) -> None:
        self.title = normalize_text(self.title, "story title", 200)
        self.situation = normalize_text(self.situation, "story situation", 2_000)
        self.task = normalize_text(self.task, "story task", 2_000)
        self.action = normalize_text(self.action, "story action", 3_000)
        self.result = normalize_text(self.result, "story result", 2_000)
        self.personal_contribution = normalize_text(
            self.personal_contribution, "personal contribution", 2_000
        )
        self.metric_explanation = optional_text(
            self.metric_explanation, "metric explanation", 2_000
        )
        if type(self.confidence) is not int or not 1 <= self.confidence <= 5:
            raise InterviewPrepValidationError("story confidence must be between 1 and 5")
        normalized_questions = tuple(
            dict.fromkeys(
                normalize_text(question, "follow-up question", 500)
                for question in self.follow_up_questions
            )
        )
        if len(normalized_questions) > 12:
            raise InterviewPrepValidationError("a story may have at most 12 follow-up questions")
        self.follow_up_questions = normalized_questions
        claim_ids = [pin.source_claim_id for pin in self.claim_pins]
        if len(set(claim_ids)) != len(claim_ids):
            raise InterviewPrepValidationError("story source claims must be unique")

    def edit(
        self,
        *,
        title: str,
        situation: str,
        task: str,
        action: str,
        result: str,
        personal_contribution: str,
        metric_explanation: str | None,
        confidence: int,
        follow_up_questions: tuple[str, ...],
        status: StoryStatus,
        claim_pins: tuple[StoryClaimPin, ...],
        now: datetime,
    ) -> None:
        self.title = title
        self.situation = situation
        self.task = task
        self.action = action
        self.result = result
        self.personal_contribution = personal_contribution
        self.metric_explanation = metric_explanation
        self.confidence = confidence
        self.follow_up_questions = follow_up_questions
        self.status = status
        self.claim_pins = claim_pins
        self.version += 1
        self.updated_at = now
        self._normalize()
        positive_version(self.version)
        aware_datetime(now, "story updated time")
        validate_story_grounding(self)


@dataclass(frozen=True, slots=True)
class StarStoryReplaySnapshot:
    """Immutable, validated response captured for an exact create replay."""

    id: UUID
    owner_user_id: UUID
    application_id: UUID
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
    origin: StoryOrigin
    claim_pins: tuple[StoryClaimPin, ...]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        restored = self.restore()
        if self.version != 1 or self.created_at != self.updated_at:
            raise InterviewPrepValidationError(
                "story replay snapshot must represent the exact create response"
            )
        for field_name in (
            "title",
            "situation",
            "task",
            "action",
            "result",
            "personal_contribution",
            "metric_explanation",
            "confidence",
            "follow_up_questions",
            "status",
            "origin",
            "claim_pins",
        ):
            if getattr(restored, field_name) != getattr(self, field_name):
                raise InterviewPrepValidationError("story replay snapshot is not canonical")

    @classmethod
    def capture(cls, story: StarStory) -> StarStoryReplaySnapshot:
        return cls(
            id=story.id,
            owner_user_id=story.owner_user_id,
            application_id=story.application_id,
            title=story.title,
            situation=story.situation,
            task=story.task,
            action=story.action,
            result=story.result,
            personal_contribution=story.personal_contribution,
            metric_explanation=story.metric_explanation,
            confidence=story.confidence,
            follow_up_questions=story.follow_up_questions,
            status=story.status,
            origin=story.origin,
            claim_pins=story.claim_pins,
            version=story.version,
            created_at=story.created_at,
            updated_at=story.updated_at,
        )

    def restore(self) -> StarStory:
        return StarStory(
            id=self.id,
            owner_user_id=self.owner_user_id,
            application_id=self.application_id,
            title=self.title,
            situation=self.situation,
            task=self.task,
            action=self.action,
            result=self.result,
            personal_contribution=self.personal_contribution,
            metric_explanation=self.metric_explanation,
            confidence=self.confidence,
            follow_up_questions=self.follow_up_questions,
            status=self.status,
            origin=self.origin,
            claim_pins=self.claim_pins,
            version=self.version,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


def validate_story_grounding(story: StarStory) -> None:
    """Fail closed when a ready/generated story lacks exact eligible support."""

    if story.status is not StoryStatus.READY and story.origin is not StoryOrigin.GENERATED:
        return
    if story.origin is StoryOrigin.GENERATED and story.status is not StoryStatus.READY:
        raise InterviewPrepValidationError("generated stories must be ready and fully grounded")
    required_fields = {
        StoryField.SITUATION,
        StoryField.TASK,
        StoryField.ACTION,
        StoryField.RESULT,
        StoryField.PERSONAL_CONTRIBUTION,
    }
    covered = {field_name for pin in story.claim_pins for field_name in pin.field_names}
    if required_fields - covered:
        raise InterviewPrepConflict("ready stories require claim provenance for every STAR field")
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
    if not numeric_fields.issubset(covered):
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


@dataclass(frozen=True, slots=True)
class SessionContextClaim:
    source_claim_id: UUID
    text: str
    text_sha256: str
    strong: bool
    requirement_ids: tuple[UUID, ...]
    evidence_pins: tuple[EvidenceRevisionPin, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", normalize_text(self.text, "session claim", 1_000))
        object.__setattr__(self, "text_sha256", sha256(self.text_sha256, "session claim hash"))
        if self.text_sha256 != hashlib.sha256(self.text.encode("utf-8")).hexdigest():
            raise InterviewPrepValidationError("session claim hash must match its immutable text")
        if not self.evidence_pins:
            raise InterviewPrepValidationError("session claim requires exact evidence revisions")
        if len(set(self.requirement_ids)) != len(self.requirement_ids):
            raise InterviewPrepValidationError("session claim requirements must be unique")


@dataclass(frozen=True, slots=True)
class SessionContextRequirement:
    requirement_id: UUID
    text: str
    importance: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", normalize_text(self.text, "session requirement", 1_000))
        if self.importance not in {"mandatory", "preferred", "helpful"}:
            raise InterviewPrepValidationError("session requirement importance is invalid")


@dataclass(frozen=True, slots=True)
class SessionContextSnapshot:
    application_id: UUID
    job_id: UUID
    job_version: int
    job_title: str
    company: str | None
    resume_version_id: UUID
    resume_version_number: int
    claims: tuple[SessionContextClaim, ...]
    requirements: tuple[SessionContextRequirement, ...]
    snapshot_sha256: str

    def __post_init__(self) -> None:
        positive_version(self.job_version, "job version")
        positive_version(self.resume_version_number, "resume version number")
        object.__setattr__(
            self, "job_title", normalize_text(self.job_title, "session job title", 300)
        )
        object.__setattr__(self, "company", optional_text(self.company, "session company", 300))
        object.__setattr__(
            self,
            "snapshot_sha256",
            sha256(self.snapshot_sha256, "session context hash"),
        )
        claim_ids = [claim.source_claim_id for claim in self.claims]
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(set(claim_ids)) != len(claim_ids):
            raise InterviewPrepValidationError("session context claims must be unique")
        if len(set(requirement_ids)) != len(requirement_ids):
            raise InterviewPrepValidationError("session context requirements must be unique")
        if self.snapshot_sha256 != _session_context_digest(self):
            raise InterviewPrepValidationError(
                "session context hash must match the immutable context"
            )


@dataclass(slots=True)
class InterviewSession:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    title: str
    kind: InterviewSessionKind
    scheduled_at: datetime | None
    context: SessionContextSnapshot
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = normalize_text(self.title, "session title", 200)
        if self.context.application_id != self.application_id:
            raise InterviewPrepValidationError("session context belongs to another application")
        positive_version(self.version)
        aware_datetime(self.scheduled_at, "session schedule")
        aware_datetime(self.created_at, "session created time")
        aware_datetime(self.updated_at, "session updated time")

    def edit(
        self,
        *,
        title: str,
        kind: InterviewSessionKind,
        scheduled_at: datetime | None,
        now: datetime,
    ) -> None:
        self.title = normalize_text(title, "session title", 200)
        self.kind = kind
        aware_datetime(scheduled_at, "session schedule")
        self.scheduled_at = scheduled_at
        self.version += 1
        positive_version(self.version)
        aware_datetime(now, "session updated time")
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class InterviewQuestion:
    id: UUID
    owner_user_id: UUID
    session_id: UUID
    ordinal: int
    prompt: str
    kind: QuestionKind
    source_requirement_ids: tuple[UUID, ...]
    source_claim_ids: tuple[UUID, ...]
    generated: bool
    created_at: datetime

    def __post_init__(self) -> None:
        positive_version(self.ordinal, "question ordinal")
        # User-authored prompts remain capped at 1,000 characters at the HTTP
        # boundary. The extra renderer budget preserves a complete 1,000-character
        # immutable requirement/claim when a generated question adds its prefix.
        object.__setattr__(self, "prompt", normalize_text(self.prompt, "question", 1_100))
        if len(set(self.source_requirement_ids)) != len(self.source_requirement_ids):
            raise InterviewPrepValidationError("question requirements must be unique")
        if len(set(self.source_claim_ids)) != len(self.source_claim_ids):
            raise InterviewPrepValidationError("question claims must be unique")
        if self.generated and not (self.source_requirement_ids or self.source_claim_ids):
            raise InterviewPrepValidationError("generated questions require source context")
        aware_datetime(self.created_at, "question created time")


@dataclass(slots=True)
class InterviewSessionNote:
    id: UUID
    owner_user_id: UUID
    session_id: UUID
    kind: SessionNoteKind
    body: str
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.body = normalize_text(self.body, "private session note", 8_000)
        positive_version(self.version)
        aware_datetime(self.created_at, "note created time")
        aware_datetime(self.updated_at, "note updated time")

    def edit(self, *, kind: SessionNoteKind, body: str, now: datetime) -> None:
        self.kind = kind
        self.body = normalize_text(body, "private session note", 8_000)
        self.version += 1
        positive_version(self.version)
        aware_datetime(now, "note updated time")
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class FollowUpDraft:
    id: UUID
    owner_user_id: UUID
    session_id: UUID
    subject: str
    body: str
    source_claims: tuple[SessionContextClaim, ...]
    content_sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", normalize_text(self.subject, "draft subject", 300))
        object.__setattr__(self, "body", normalize_text(self.body, "draft body", 8_000))
        object.__setattr__(
            self, "content_sha256", sha256(self.content_sha256, "draft content hash")
        )
        expected = hashlib.sha256(f"{self.subject}\n{self.body}".encode()).hexdigest()
        if self.content_sha256 != expected:
            raise InterviewPrepValidationError(
                "follow-up draft hash must match its immutable content"
            )
        if not self.source_claims:
            raise InterviewPrepValidationError("follow-up draft requires grounded source claims")
        supported = {
            token
            for claim in self.source_claims
            for pin in claim.evidence_pins
            for token in _numeric_tokens(pin.statement)
        }
        used = {token for claim in self.source_claims for token in _numeric_tokens(claim.text)}
        if not used.issubset(supported):
            raise InterviewPrepConflict(
                "follow-up draft contains a number absent from pinned evidence"
            )
        aware_datetime(self.created_at, "follow-up draft created time")


@dataclass(frozen=True, slots=True)
class InterviewIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_fingerprint: str
    resource_kind: str
    resource_id: UUID
    created_at: datetime
    response_snapshot: StarStoryReplaySnapshot | None = None

    def __post_init__(self) -> None:
        normalize_text(self.idempotency_key, "idempotency key", 128, minimum=8)
        if re.fullmatch(r"sha256:[0-9a-f]{64}", self.request_fingerprint) is None:
            raise InterviewPrepValidationError("idempotency fingerprint is invalid")
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.resource_kind) is None:
            raise InterviewPrepValidationError("idempotency resource kind is invalid")
        if self.response_snapshot is not None and (
            self.resource_kind != "star_story"
            or self.response_snapshot.owner_user_id != self.owner_user_id
            or self.response_snapshot.id != self.resource_id
        ):
            raise InterviewPrepValidationError(
                "idempotency response snapshot does not match its owned resource"
            )
        aware_datetime(self.created_at, "idempotency created time")


@dataclass(frozen=True, slots=True)
class InterviewAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: InterviewAuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    metadata: tuple[tuple[str, str], ...]
    created_at: datetime

    def __post_init__(self) -> None:
        normalize_text(self.target_kind, "audit target kind", 80)
        normalize_text(self.request_id, "request ID", 128)
        normalize_text(self.trace_id, "trace ID", 128)
        allowed = {
            "application_id",
            "session_id",
            "story_id",
            "status",
            "version",
            "question_count",
            "claim_count",
        }
        for key, value in self.metadata:
            if key not in allowed:
                raise InterviewPrepValidationError("audit metadata key is not allowlisted")
            normalize_text(value, f"audit metadata {key}", 120)
        aware_datetime(self.created_at, "audit created time")


def _numeric_tokens(value: str) -> frozenset[str]:
    return frozenset(match.group(0).replace(",", "") for match in _NUMERIC_TOKEN.finditer(value))


def _session_context_digest(context: SessionContextSnapshot) -> str:
    payload = {
        "applicationId": str(context.application_id),
        "jobId": str(context.job_id),
        "jobVersion": context.job_version,
        "jobTitle": context.job_title,
        "company": context.company,
        "resumeVersionId": str(context.resume_version_id),
        "resumeVersionNumber": context.resume_version_number,
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
            for claim in context.claims
        ],
        "requirements": [
            {
                "id": str(item.requirement_id),
                "text": item.text,
                "importance": item.importance,
            }
            for item in context.requirements
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
