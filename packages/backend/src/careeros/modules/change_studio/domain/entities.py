"""Framework-independent Change Studio entities and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .errors import ChangeStudioValidationError

MAX_INT32 = 2_147_483_647
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_BIDI_CONTROLS = {
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ChangeStudioValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        (ord(character) < 32 and character not in {"\n", "\r", "\t"}) or character in _BIDI_CONTROLS
        for character in normalized
    ):
        raise ChangeStudioValidationError(f"{field} contains unsupported control characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return _text(normalized, field, maximum) if normalized else None


def _basis_points(value: int | None, field: str) -> None:
    if value is not None and not 0 <= value <= 10_000:
        raise ChangeStudioValidationError(f"{field} must be between 0 and 10000")


def _positive_version(value: int) -> None:
    if not 1 <= value <= MAX_INT32:
        raise ChangeStudioValidationError("version must be a positive int32")


def _idempotency(value: str) -> str:
    normalized = _text(value, "idempotency key", 128)
    if _IDEMPOTENCY_KEY.fullmatch(normalized) is None:
        raise ChangeStudioValidationError("idempotency key is invalid")
    return normalized


class ChangeSetPurpose(StrEnum):
    JOB_TAILORING = "job_tailoring"


class ChangeTargetKind(StrEnum):
    TAILORED_RESUME_BULLET = "tailored_resume_bullet"
    PROFILE_SUMMARY = "profile_summary"


class ChangeSetStatus(StrEnum):
    DRAFT = "draft"
    APPLIED = "applied"


class ChangeOperationType(StrEnum):
    ADD_BULLET = "add_bullet"
    REPLACE_BULLET = "replace_bullet"
    REPLACE_SUMMARY = "replace_summary"


class ChangeOperationStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    BLOCKED = "blocked"


class GroundingStatus(StrEnum):
    GROUNDED = "grounded"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimKind(StrEnum):
    RESPONSIBILITY = "responsibility"
    ACHIEVEMENT = "achievement"
    METRIC_OUTCOME = "metric_outcome"
    SKILL = "skill"
    CREDENTIAL = "credential"
    EXPERIENCE = "experience"
    OTHER = "other"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ClarificationStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class ProviderRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class ChangeAuditAction(StrEnum):
    CHANGE_SET_CREATED = "change_set_created"
    OPERATION_ACCEPTED = "operation_accepted"
    OPERATION_REJECTED = "operation_rejected"
    OPERATION_EDITED = "operation_edited"
    OPERATION_ALTERNATIVE_CREATED = "operation_alternative_created"
    OPERATION_LOCKED = "operation_locked"
    OPERATION_UNLOCKED = "operation_unlocked"
    SAFE_CHANGES_APPLIED = "safe_changes_applied"
    CHANGE_SET_UNDONE = "change_set_undone"
    CHANGE_SET_REDONE = "change_set_redone"
    VERSION_RESTORED = "version_restored"
    CLARIFICATION_ANSWERED = "clarification_answered"


@dataclass(slots=True)
class ChangeSet:
    id: UUID
    owner_user_id: UUID
    purpose: ChangeSetPurpose
    target_kind: ChangeTargetKind
    status: ChangeSetStatus
    job_id: UUID | None
    analysis_id: UUID | None
    current_version_id: UUID | None
    provider_name: str
    provider_model: str
    prompt_version: str
    policy_version: str
    schema_version: str
    grounding_version: str
    idempotency_key: str
    idempotency_fingerprint: str
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.provider_name = _text(self.provider_name, "provider name", 80)
        self.provider_model = _text(self.provider_model, "provider model", 120)
        self.prompt_version = _text(self.prompt_version, "prompt version", 120)
        self.policy_version = _text(self.policy_version, "policy version", 120)
        self.schema_version = _text(self.schema_version, "schema version", 120)
        self.grounding_version = _text(self.grounding_version, "grounding version", 120)
        self.idempotency_key = _idempotency(self.idempotency_key)
        self.idempotency_fingerprint = _text(
            self.idempotency_fingerprint, "idempotency fingerprint", 128
        )
        _positive_version(self.version)

    def touch(self, now: datetime) -> None:
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(slots=True)
class ChangeOperation:
    id: UUID
    owner_user_id: UUID
    change_set_id: UUID
    operation_type: ChangeOperationType
    target_kind: ChangeTargetKind
    target_id: UUID
    before_text: str
    after_text: str
    reason: str
    status: ChangeOperationStatus
    risk: RiskLevel
    confidence_basis_points: int
    requires_confirmation: bool
    grounding_status: GroundingStatus
    grounding_codes: tuple[str, ...]
    expected_score_delta_basis_points: int | None
    requirement_id: UUID | None
    requirement_text: str | None
    locked: bool
    sort_order: int
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.before_text = _text(self.before_text, "original text", 2_000, minimum=0)
        self.after_text = _text(self.after_text, "suggested text", 2_000, minimum=0)
        self.reason = _text(self.reason, "operation reason", 1_000)
        self.requirement_text = _optional_text(self.requirement_text, "requirement text", 1_000)
        for code in self.grounding_codes:
            _text(code, "grounding code", 80)
        _basis_points(self.confidence_basis_points, "confidence")
        if (
            self.expected_score_delta_basis_points is not None
            and not -10_000 <= self.expected_score_delta_basis_points <= 10_000
        ):
            raise ChangeStudioValidationError("expected score delta is out of range")
        if not 0 <= self.sort_order <= MAX_INT32:
            raise ChangeStudioValidationError("sort order is invalid")
        _positive_version(self.version)

    @property
    def acceptable(self) -> bool:
        return (
            self.status in {ChangeOperationStatus.PROPOSED, ChangeOperationStatus.EDITED}
            and self.grounding_status is GroundingStatus.GROUNDED
            and not self.locked
        )

    def mark_accepted(self, now: datetime) -> None:
        if not self.acceptable:
            raise ChangeStudioValidationError("operation is not acceptable")
        self.status = ChangeOperationStatus.ACCEPTED
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now

    def mark_rejected(self, now: datetime) -> None:
        if self.status is ChangeOperationStatus.ACCEPTED:
            raise ChangeStudioValidationError("accepted operations cannot be rejected")
        self.status = ChangeOperationStatus.REJECTED
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now

    def edit(
        self,
        *,
        after_text: str,
        reason: str,
        risk: RiskLevel,
        confidence_basis_points: int,
        grounding_status: GroundingStatus,
        grounding_codes: tuple[str, ...],
        expected_score_delta_basis_points: int | None,
        now: datetime,
    ) -> None:
        if self.locked:
            raise ChangeStudioValidationError("locked operations cannot be edited")
        if self.status is ChangeOperationStatus.ACCEPTED:
            raise ChangeStudioValidationError("accepted operations cannot be edited")
        self.after_text = _text(after_text, "suggested text", 2_000)
        self.reason = _text(reason, "operation reason", 1_000)
        self.risk = risk
        self.confidence_basis_points = confidence_basis_points
        self.grounding_status = grounding_status
        self.grounding_codes = grounding_codes
        self.expected_score_delta_basis_points = expected_score_delta_basis_points
        self.status = (
            ChangeOperationStatus.EDITED
            if grounding_status is GroundingStatus.GROUNDED
            else ChangeOperationStatus.BLOCKED
        )
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now
        self.__post_init__()

    def set_locked(self, locked: bool, now: datetime) -> None:
        if self.status is ChangeOperationStatus.ACCEPTED:
            raise ChangeStudioValidationError("accepted operations cannot be locked")
        self.locked = locked
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class ChangeClaim:
    id: UUID
    owner_user_id: UUID
    change_set_id: UUID
    operation_id: UUID
    claim_kind: ClaimKind
    text: str
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    source_excerpt: str
    validation_status: ValidationStatus
    validation_codes: tuple[str, ...]
    sort_order: int
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.text, "claim text", 1_000)
        _text(self.evidence_title, "evidence title", 300)
        _text(self.evidence_strength, "evidence strength", 40)
        _text(self.source_excerpt, "source excerpt", 1_500)
        for code in self.validation_codes:
            _text(code, "claim validation code", 80)
        if not 0 <= self.sort_order <= MAX_INT32:
            raise ChangeStudioValidationError("claim sort order is invalid")


@dataclass(slots=True)
class ClarifyingQuestion:
    id: UUID
    owner_user_id: UUID
    change_set_id: UUID
    operation_id: UUID | None
    requirement_id: UUID | None
    evidence_id: UUID | None
    question: str
    reason: str
    status: ClarificationStatus
    answer_text: str | None
    answered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.question = _text(self.question, "clarifying question", 1_000)
        self.reason = _text(self.reason, "clarifying reason", 1_000)
        self.answer_text = _optional_text(self.answer_text, "clarifying answer", 2_000)

    def answer(self, text: str, now: datetime) -> None:
        self.answer_text = _text(text, "clarifying answer", 2_000)
        self.status = ClarificationStatus.ANSWERED
        self.answered_at = now
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class ChangeSetVersion:
    id: UUID
    owner_user_id: UUID
    change_set_id: UUID
    version_number: int
    parent_version_id: UUID | None
    created_by_operation_id: UUID | None
    title: str
    content: str
    operation_ids: tuple[UUID, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not 1 <= self.version_number <= MAX_INT32:
            raise ChangeStudioValidationError("version number is invalid")
        _text(self.title, "version title", 200)
        _text(self.content, "version content", 8_000, minimum=0)


@dataclass(frozen=True, slots=True)
class ProviderRun:
    id: UUID
    owner_user_id: UUID
    change_set_id: UUID
    provider_name: str
    provider_model: str
    operation: str
    prompt_version: str
    policy_version: str
    schema_version: str
    grounding_version: str
    request_fingerprint: str
    input_evidence_ids: tuple[UUID, ...]
    input_requirement_ids: tuple[UUID, ...]
    output_operation_count: int
    status: ProviderRunStatus
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_micros: int | None
    validation_codes: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.provider_name, "provider name", 80)
        _text(self.provider_model, "provider model", 120)
        _text(self.operation, "provider operation", 80)
        _text(self.prompt_version, "prompt version", 120)
        _text(self.policy_version, "policy version", 120)
        _text(self.schema_version, "schema version", 120)
        _text(self.grounding_version, "grounding version", 120)
        _text(self.request_fingerprint, "request fingerprint", 128)
        if not 0 <= self.output_operation_count <= 100:
            raise ChangeStudioValidationError("provider output count is invalid")
        if self.latency_ms < 0:
            raise ChangeStudioValidationError("provider latency is invalid")
        for value in (self.prompt_tokens, self.completion_tokens, self.cost_micros):
            if value is not None and value < 0:
                raise ChangeStudioValidationError("provider usage cannot be negative")
        for code in self.validation_codes:
            _text(code, "provider validation code", 80)


@dataclass(frozen=True, slots=True)
class ChangeStudioIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    idempotency_fingerprint: str
    target_kind: str
    target_id: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        _idempotency(self.idempotency_key)
        _text(self.idempotency_fingerprint, "idempotency fingerprint", 128)
        _text(self.target_kind, "idempotency target kind", 80)


@dataclass(frozen=True, slots=True)
class ChangeStudioAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: ChangeAuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    details: tuple[tuple[str, str], ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.target_kind, "audit target kind", 80)
        _text(self.request_id, "request ID", 128)
        _text(self.trace_id, "trace ID", 128)
        allowed = {
            "change_set_id",
            "operation_id",
            "version_id",
            "question_id",
            "analysis_id",
            "job_id",
            "reason",
            "status",
        }
        for key, value in self.details:
            if key not in allowed:
                raise ChangeStudioValidationError("audit detail key is not allowlisted")
            _text(value, f"audit detail {key}", 160)
