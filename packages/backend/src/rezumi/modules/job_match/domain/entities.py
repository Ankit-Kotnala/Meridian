"""Job Match domain entities and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from .errors import JobMatchValidationError

MAX_INT32 = 2_147_483_647


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise JobMatchValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise JobMatchValidationError(f"{field} contains unsupported characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return _text(normalized, field, maximum) if normalized else None


def _bounded(value: int, field: str, minimum: int = 0, maximum: int = 10_000) -> None:
    if not minimum <= value <= maximum:
        raise JobMatchValidationError(f"{field} is out of range")


def _positive_version(value: int) -> None:
    if not 1 <= value <= MAX_INT32:
        raise JobMatchValidationError("version must be a positive int32")


class JobSourceKind(StrEnum):
    PASTE = "paste"
    URL = "url"
    MANUAL = "manual"
    GREENHOUSE = "greenhouse"
    FAKE = "fake"


class WorkModel(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class RequirementType(StrEnum):
    RESPONSIBILITY = "responsibility"
    SKILL = "skill"
    EXPERIENCE = "experience"
    SENIORITY = "seniority"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    DOMAIN = "domain"
    WORK_AUTHORIZATION = "work_authorization"
    TRAVEL = "travel"
    COMPENSATION = "compensation"
    OTHER = "other"


class RequirementImportance(StrEnum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"
    HELPFUL = "helpful"


class RequirementMatchState(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    TRANSFERABLE = "transferable"
    UNKNOWN = "unknown"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ApplicationReadinessLabel(StrEnum):
    STRONG = "strong"
    VIABLE = "viable"
    NEEDS_WORK = "needs_work"
    INSUFFICIENT_DATA = "insufficient_data"


class PreferenceFit(StrEnum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    UNKNOWN = "unknown"
    MISMATCH = "mismatch"


class TailoringEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OpportunityPriorityLabel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFER = "defer"


class JobAuditAction(StrEnum):
    JOB_IMPORTED = "job_imported"
    JOB_CREATED = "job_created"
    JOB_UPDATED = "job_updated"
    JOB_DELETED = "job_deleted"
    JOB_ANALYZED = "job_analyzed"
    OPPORTUNITY_PRIORITIZED = "opportunity_prioritized"
    JOBS_SYNCED_FROM_SOURCE = "jobs_synced_from_source"


_MAX_ROLE_PREFERENCE_TITLES = 20


@dataclass(frozen=True, slots=True)
class RolePreference:
    """An owner's explicit opt-in/opt-out of role titles used to filter the shared job catalog.

    Free-text, not limited to any curated role taxonomy — an owner must be
    able to filter toward a role that hasn't been seeded anywhere else in the
    product. An empty ``role_titles`` means the owner explicitly cleared
    their selection (the query service then falls back to the auto-suggested
    role from Role Readiness / Career Record).
    """

    id: UUID
    owner_user_id: UUID
    role_titles: tuple[str, ...]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _positive_version(self.version)
        normalized: list[str] = []
        for title in self.role_titles:
            candidate = _text(title, "role title", 200)
            if candidate not in normalized:
                normalized.append(candidate)
        if len(normalized) > _MAX_ROLE_PREFERENCE_TITLES:
            raise JobMatchValidationError("role preference exceeds the supported limit")
        object.__setattr__(self, "role_titles", tuple(normalized))


@dataclass(slots=True)
class JobPosting:
    id: UUID
    owner_user_id: UUID
    title: str
    company: str | None
    location: str | None
    work_model: WorkModel
    employment_type: EmploymentType
    compensation: str | None
    application_deadline: date | None
    source_kind: JobSourceKind
    source_url: str | None
    external_id: str | None
    source_text: str
    source_sha256: bytes
    idempotency_key: str
    idempotency_fingerprint: str
    target_role_id: UUID | None
    target_role_title: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "job title", 200)
        self.company = _optional_text(self.company, "company", 200)
        self.location = _optional_text(self.location, "job location", 200)
        self.compensation = _optional_text(self.compensation, "compensation", 200)
        self.source_url = _optional_text(self.source_url, "source URL", 2_048)
        self.external_id = _optional_text(self.external_id, "external id", 200)
        self.source_text = _text(self.source_text, "source text", 50_000, minimum=20)
        self.idempotency_key = _text(self.idempotency_key, "idempotency key", 128)
        self.idempotency_fingerprint = _text(
            self.idempotency_fingerprint, "idempotency fingerprint", 128
        )
        self.target_role_title = _optional_text(self.target_role_title, "target role", 200)
        if len(self.source_sha256) != 32:
            raise JobMatchValidationError("source hash must be sha256")
        _positive_version(self.version)

    def edit(
        self,
        *,
        title: str,
        company: str | None,
        location: str | None,
        work_model: WorkModel,
        employment_type: EmploymentType,
        compensation: str | None,
        application_deadline: date | None,
        source_text: str,
        source_sha256: bytes,
        target_role_id: UUID | None,
        target_role_title: str | None,
        now: datetime,
    ) -> None:
        self.title = _text(title, "job title", 200)
        self.company = _optional_text(company, "company", 200)
        self.location = _optional_text(location, "job location", 200)
        self.work_model = work_model
        self.employment_type = employment_type
        self.compensation = _optional_text(compensation, "compensation", 200)
        self.application_deadline = application_deadline
        self.source_text = _text(source_text, "source text", 50_000, minimum=20)
        if len(source_sha256) != 32:
            raise JobMatchValidationError("source hash must be sha256")
        self.source_sha256 = source_sha256
        self.target_role_id = target_role_id
        self.target_role_title = _optional_text(target_role_title, "target role", 200)
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class JobRequirement:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    requirement_type: RequirementType
    text: str
    normalized_text: str
    importance: RequirementImportance
    source_start: int
    source_end: int
    confidence_basis_points: int
    sort_order: int

    def __post_init__(self) -> None:
        _text(self.text, "requirement text", 1_000)
        _text(self.normalized_text, "normalized requirement", 1_000)
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise JobMatchValidationError("requirement source span is invalid")
        _bounded(self.confidence_basis_points, "requirement confidence")
        if not 0 <= self.sort_order <= MAX_INT32:
            raise JobMatchValidationError("requirement sort order is invalid")


@dataclass(frozen=True, slots=True)
class JobMatchAnalysis:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    idempotency_key: str
    idempotency_fingerprint: str
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    input_snapshot: dict[str, object]
    feature_set_hash: bytes
    raw_score_basis_points: int | None
    display_score: int | None
    readiness_label: ApplicationReadinessLabel
    hard_gap_count: int
    insufficient_reason: str | None
    summary: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.idempotency_key, "idempotency key", 128)
        _text(self.idempotency_fingerprint, "idempotency fingerprint", 128)
        _text(self.engine_version, "engine version", 120)
        _text(self.configuration_version, "configuration version", 120)
        _text(self.feature_schema_version, "feature schema version", 120)
        if len(self.feature_set_hash) != 32:
            raise JobMatchValidationError("feature hash must be sha256")
        if self.raw_score_basis_points is not None:
            _bounded(self.raw_score_basis_points, "raw score")
        if self.display_score is not None:
            _bounded(self.display_score, "display score", maximum=100)
        if self.hard_gap_count < 0:
            raise JobMatchValidationError("hard gap count is invalid")
        self.insufficient_reason and _text(self.insufficient_reason, "insufficient reason", 160)
        _text(self.summary, "match summary", 1_000)


@dataclass(frozen=True, slots=True)
class JobMatchComponent:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    dimension: str
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z_]{3,80}", self.dimension) is None:
            raise JobMatchValidationError("component dimension is invalid")
        _bounded(self.weight_basis_points, "component weight")
        _bounded(self.score_basis_points, "component score")
        _bounded(self.contribution_basis_points, "component contribution")
        _text(self.explanation, "component explanation", 1_000)


@dataclass(frozen=True, slots=True)
class RequirementMatch:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    requirement_id: UUID
    requirement_text: str
    requirement_type: RequirementType
    importance: RequirementImportance
    match_state: RequirementMatchState
    score_basis_points: int
    explanation: str
    recommended_action: str
    hard_gap: bool

    def __post_init__(self) -> None:
        _text(self.requirement_text, "requirement text", 1_000)
        _bounded(self.score_basis_points, "requirement score")
        _text(self.explanation, "requirement match explanation", 1_000)
        _text(self.recommended_action, "recommended action", 500)


@dataclass(frozen=True, slots=True)
class RequirementEvidenceLink:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    requirement_match_id: UUID
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    relevance_basis_points: int
    rationale: str

    def __post_init__(self) -> None:
        _text(self.evidence_title, "evidence title", 300)
        _text(self.evidence_strength, "evidence strength", 40)
        _bounded(self.relevance_basis_points, "evidence relevance")
        _text(self.rationale, "evidence rationale", 1_000)


@dataclass(frozen=True, slots=True)
class OpportunityPriorityAnalysis:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    analysis_id: UUID
    idempotency_key: str
    idempotency_fingerprint: str
    priority_label: OpportunityPriorityLabel
    priority_score_basis_points: int
    input_snapshot: dict[str, object]
    reasons_for: tuple[str, ...]
    reconsiderations: tuple[str, ...]
    blockers: tuple[str, ...]
    next_action: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.idempotency_key, "idempotency key", 128)
        _text(self.idempotency_fingerprint, "idempotency fingerprint", 128)
        _bounded(self.priority_score_basis_points, "priority score")
        for value in (*self.reasons_for, *self.reconsiderations, *self.blockers):
            _text(value, "priority reason", 500)
        _text(self.next_action, "next action", 500)


@dataclass(frozen=True, slots=True)
class JobMatchAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: JobAuditAction
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
        for key, value in self.details:
            if key not in {"job_id", "analysis_id", "priority_id", "target_role_id", "reason"}:
                raise JobMatchValidationError("audit detail key is not allowlisted")
            _text(value, f"audit detail {key}", 120)
