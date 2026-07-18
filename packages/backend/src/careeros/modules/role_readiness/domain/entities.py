"""Role Explorer and Role Readiness domain entities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .errors import RoleReadinessValidationError

MAX_INT32 = 2_147_483_647


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise RoleReadinessValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise RoleReadinessValidationError(f"{field} contains unsupported characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return _text(normalized, field, maximum)


def _positive_version(value: int) -> None:
    if not 1 <= value <= MAX_INT32:
        raise RoleReadinessValidationError("version must be a positive int32")


def _keywords(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(_text(value, field, 80).casefold() for value in values if value.strip())
    )
    if len(normalized) > 24:
        raise RoleReadinessValidationError(f"{field} has too many values")
    return normalized


class RoleSeniority(StrEnum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class CompetencyDimension(StrEnum):
    CORE_COMPETENCY = "core_competency"
    RESPONSIBILITY_ALIGNMENT = "responsibility_alignment"
    SENIORITY_ALIGNMENT = "seniority_alignment"
    LEADERSHIP_EVIDENCE = "leadership_evidence"
    DOMAIN_KNOWLEDGE = "domain_knowledge"
    TECHNICAL_SKILLS = "technical_skills"
    BUSINESS_IMPACT = "business_impact"
    EDUCATION_CERTIFICATION = "education_certification"
    EVIDENCE_STRENGTH = "evidence_strength"


class CompetencyImportance(StrEnum):
    REQUIRED = "required"
    HELPFUL = "helpful"


class SkillMatchState(StrEnum):
    DEMONSTRATED = "demonstrated"
    LISTED = "listed"
    TRANSFERABLE = "transferable"
    ADJACENT = "adjacent"
    MISSING = "missing"
    UNKNOWN = "unknown"


class ReadinessLabel(StrEnum):
    STRONG = "strong"
    DEVELOPING = "developing"
    NEEDS_EVIDENCE = "needs_evidence"
    INSUFFICIENT_DATA = "insufficient_data"


class RoleAuditAction(StrEnum):
    SAVED_ROLE_CREATED = "saved_role_created"
    SAVED_ROLE_UPDATED = "saved_role_updated"
    SAVED_ROLE_DELETED = "saved_role_deleted"
    READINESS_ANALYZED = "readiness_analyzed"


@dataclass(frozen=True, slots=True)
class RoleTaxonomyVersion:
    id: UUID
    version: str
    source_name: str
    source_license: str
    description: str
    active: bool
    published_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.version, "taxonomy version", 80)
        _text(self.source_name, "taxonomy source", 160)
        _text(self.source_license, "taxonomy license", 240)
        _text(self.description, "taxonomy description", 1_000)


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    id: UUID
    taxonomy_version_id: UUID
    slug: str
    title: str
    seniority: RoleSeniority
    industry: str
    domain: str
    location_scope: str
    company_type: str | None
    description: str
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.slug) is None:
            raise RoleReadinessValidationError("role slug is invalid")
        _text(self.title, "role title", 160)
        _text(self.industry, "role industry", 120)
        _text(self.domain, "role domain", 120)
        _text(self.location_scope, "role location scope", 120)
        _optional_text(self.company_type, "company type", 120)
        _text(self.description, "role description", 1_000)
        _positive_version(self.version)


@dataclass(frozen=True, slots=True)
class RoleCompetency:
    id: UUID
    role_id: UUID
    dimension: CompetencyDimension
    label: str
    description: str
    importance: CompetencyImportance
    skill_keywords: tuple[str, ...]
    evidence_keywords: tuple[str, ...]
    transferable_keywords: tuple[str, ...]
    adjacent_keywords: tuple[str, ...]
    sort_order: int

    def __post_init__(self) -> None:
        _text(self.label, "competency label", 180)
        _text(self.description, "competency description", 1_000)
        if not 0 <= self.sort_order <= MAX_INT32:
            raise RoleReadinessValidationError("competency sort order is invalid")
        object.__setattr__(self, "skill_keywords", _keywords(self.skill_keywords, "skill keyword"))
        object.__setattr__(
            self, "evidence_keywords", _keywords(self.evidence_keywords, "evidence keyword")
        )
        object.__setattr__(
            self,
            "transferable_keywords",
            _keywords(self.transferable_keywords, "transferable keyword"),
        )
        object.__setattr__(
            self, "adjacent_keywords", _keywords(self.adjacent_keywords, "adjacent keyword")
        )


@dataclass(slots=True)
class SavedRole:
    id: UUID
    owner_user_id: UUID
    role_id: UUID
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.notes = _optional_text(self.notes, "saved role notes", 1_000)
        _positive_version(self.version)

    def edit(self, *, notes: str | None, now: datetime) -> None:
        self.notes = _optional_text(notes, "saved role notes", 1_000)
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class RoleReadinessAnalysis:
    id: UUID
    owner_user_id: UUID
    role_id: UUID
    saved_role_id: UUID | None
    idempotency_key: str
    idempotency_fingerprint: str
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    taxonomy_version: str
    input_snapshot: dict[str, object]
    feature_set_hash: bytes
    raw_score_basis_points: int | None
    display_score: int | None
    readiness_label: ReadinessLabel
    insufficient_reason: str | None
    summary: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.idempotency_key, "idempotency key", 128)
        _text(self.idempotency_fingerprint, "idempotency fingerprint", 128)
        _text(self.engine_version, "engine version", 120)
        _text(self.configuration_version, "configuration version", 120)
        _text(self.feature_schema_version, "feature schema version", 120)
        _text(self.taxonomy_version, "taxonomy version", 80)
        _text(self.summary, "readiness summary", 1_000)
        if (
            self.raw_score_basis_points is not None
            and not 0 <= self.raw_score_basis_points <= 10_000
        ):
            raise RoleReadinessValidationError("raw readiness score is out of range")
        if self.display_score is not None and not 0 <= self.display_score <= 100:
            raise RoleReadinessValidationError("display readiness score is out of range")


@dataclass(frozen=True, slots=True)
class ReadinessComponent:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    dimension: CompetencyDimension
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str

    def __post_init__(self) -> None:
        for value in (
            self.weight_basis_points,
            self.score_basis_points,
            self.contribution_basis_points,
        ):
            if not 0 <= value <= 10_000:
                raise RoleReadinessValidationError("component basis points are out of range")
        _text(self.explanation, "component explanation", 1_000)


@dataclass(frozen=True, slots=True)
class CompetencyResult:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    competency_id: UUID
    dimension: CompetencyDimension
    label: str
    importance: CompetencyImportance
    match_state: SkillMatchState
    score_basis_points: int
    explanation: str
    gap_kind: str | None

    def __post_init__(self) -> None:
        _text(self.label, "competency result label", 180)
        if not 0 <= self.score_basis_points <= 10_000:
            raise RoleReadinessValidationError("competency score is out of range")
        _text(self.explanation, "competency explanation", 1_000)
        _optional_text(self.gap_kind, "gap kind", 80)


@dataclass(frozen=True, slots=True)
class CompetencyEvidenceLink:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    competency_result_id: UUID
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    relevance_basis_points: int
    rationale: str

    def __post_init__(self) -> None:
        _text(self.evidence_title, "evidence title", 300)
        _text(self.evidence_strength, "evidence strength", 40)
        if not 0 <= self.relevance_basis_points <= 10_000:
            raise RoleReadinessValidationError("evidence relevance is out of range")
        _text(self.rationale, "evidence rationale", 1_000)


@dataclass(frozen=True, slots=True)
class RoleReadinessAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: RoleAuditAction
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
            if key not in {"role_id", "saved_role_id", "analysis_id", "reason"}:
                raise RoleReadinessValidationError("audit detail key is not allowlisted")
            _text(value, f"audit detail {key}", 120)
