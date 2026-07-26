"""Career Growth aggregates, immutable review history, and Career Health records."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from .errors import CareerGrowthValidationError

MAX_INT32 = 2_147_483_647
CANONICAL_SCORE_DISCLAIMER = (
    "CareerOS scores are internal readiness measurements. They are not scores "
    "provided by an employer or applicant tracking system and do not guarantee "
    "interviews or employment outcomes."
)
PROMOTION_READINESS_DISCLAIMER = (
    "Promotion Readiness summarizes CareerOS preparation signals from current eligible "
    "evidence and owner-maintained records. It is not an employer decision, hiring "
    "probability, promotion guarantee, or assessment of job-market value."
)


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise CareerGrowthValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise CareerGrowthValidationError(f"{field} contains unsupported characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return _text(normalized, field, maximum) if normalized else None


def _positive_version(value: int, field: str = "version") -> None:
    if not 1 <= value <= MAX_INT32:
        raise CareerGrowthValidationError(f"{field} must be a positive int32")


def _basis_points(value: int, field: str) -> None:
    if not 0 <= value <= 10_000:
        raise CareerGrowthValidationError(f"{field} must be between 0 and 10000")


def _sha256(value: str, field: str) -> str:
    normalized = value.removeprefix("sha256:").strip().lower()
    if re.fullmatch(r"[a-f0-9]{64}", normalized) is None:
        raise CareerGrowthValidationError(f"{field} must be a SHA-256 hex digest")
    return normalized


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MilestoneStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DevelopmentKind(StrEnum):
    LEARNING = "learning"
    CERTIFICATION = "certification"
    PERFORMANCE_REVIEW = "performance_review"
    PROMOTION = "promotion"
    INTERNAL_MOBILITY = "internal_mobility"
    ANNUAL_RESUME_REFRESH = "annual_resume_refresh"


class DevelopmentStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewCadence(StrEnum):
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ReviewVersionStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class EvidenceTargetKind(StrEnum):
    GOAL = "goal"
    MILESTONE = "milestone"
    DEVELOPMENT_ITEM = "development_item"
    REVIEW_VERSION = "review_version"


class CareerHealthStatus(StrEnum):
    COMPLETE = "complete"
    INSUFFICIENT_DATA = "insufficient_data"


class CareerHealthLabel(StrEnum):
    WELL_MAINTAINED = "well_maintained"
    DEVELOPING = "developing"
    NEEDS_ATTENTION = "needs_attention"
    INSUFFICIENT_DATA = "insufficient_data"


class CareerHealthDimension(StrEnum):
    EVIDENCE_CURRENCY = "evidence_currency"
    GOAL_PROGRESS = "goal_progress"
    DEVELOPMENT_FOLLOW_THROUGH = "development_follow_through"
    REVIEW_CADENCE = "review_cadence"
    READINESS_MAINTENANCE = "readiness_maintenance"


class FindingSeverity(StrEnum):
    INFORMATION = "information"
    ATTENTION = "attention"


class PromotionReadinessStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BUILDING = "building"
    REVIEW_READY = "review_ready"


class PromotionCheckStatus(StrEnum):
    SUPPORTED = "supported"
    NEEDS_EVIDENCE = "needs_evidence"
    NEEDS_ACTION = "needs_action"


class GrowthAuditAction(StrEnum):
    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    GOAL_DELETED = "goal_deleted"
    MILESTONE_CREATED = "milestone_created"
    MILESTONE_UPDATED = "milestone_updated"
    MILESTONE_DELETED = "milestone_deleted"
    DEVELOPMENT_ITEM_CREATED = "development_item_created"
    DEVELOPMENT_ITEM_UPDATED = "development_item_updated"
    DEVELOPMENT_ITEM_DELETED = "development_item_deleted"
    REVIEW_CREATED = "review_created"
    REVIEW_REVISED = "review_revised"
    REVIEW_FINALIZED = "review_finalized"
    REVIEW_DELETED = "review_deleted"
    CAREER_HEALTH_ANALYZED = "career_health_analyzed"
    CAREER_HEALTH_DELETED = "career_health_deleted"


@dataclass(slots=True)
class CareerGoal:
    id: UUID
    owner_user_id: UUID
    title: str
    description: str | None
    status: GoalStatus
    target_date: date | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "goal title", 240)
        self.description = _optional_text(self.description, "goal description", 4_000)
        _positive_version(self.version)

    def edit(
        self,
        *,
        title: str,
        description: str | None,
        status: GoalStatus,
        target_date: date | None,
        now: datetime,
    ) -> None:
        self.title = _text(title, "goal title", 240)
        self.description = _optional_text(description, "goal description", 4_000)
        self.status = status
        self.target_date = target_date
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(slots=True)
class GoalMilestone:
    id: UUID
    owner_user_id: UUID
    goal_id: UUID
    title: str
    status: MilestoneStatus
    target_date: date | None
    completed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "milestone title", 240)
        _positive_version(self.version)
        if self.status is MilestoneStatus.COMPLETED and self.completed_at is None:
            raise CareerGrowthValidationError("completed milestone requires completion time")
        if self.status is not MilestoneStatus.COMPLETED and self.completed_at is not None:
            raise CareerGrowthValidationError("only a completed milestone may have completion time")

    def edit(
        self,
        *,
        title: str,
        status: MilestoneStatus,
        target_date: date | None,
        now: datetime,
    ) -> None:
        previous_status = self.status
        previous_completed_at = self.completed_at
        self.title = _text(title, "milestone title", 240)
        self.status = status
        self.target_date = target_date
        self.completed_at = (
            previous_completed_at
            if status is MilestoneStatus.COMPLETED and previous_status is MilestoneStatus.COMPLETED
            else now
            if status is MilestoneStatus.COMPLETED
            else None
        )
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(slots=True)
class DevelopmentItem:
    id: UUID
    owner_user_id: UUID
    kind: DevelopmentKind
    title: str
    description: str | None
    status: DevelopmentStatus
    target_date: date | None
    completed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "development item title", 240)
        self.description = _optional_text(self.description, "development item description", 4_000)
        _positive_version(self.version)
        if self.status is DevelopmentStatus.COMPLETED and self.completed_at is None:
            raise CareerGrowthValidationError("completed development item requires completion time")
        if self.status is not DevelopmentStatus.COMPLETED and self.completed_at is not None:
            raise CareerGrowthValidationError(
                "only a completed development item may have completion time"
            )

    def edit(
        self,
        *,
        kind: DevelopmentKind,
        title: str,
        description: str | None,
        status: DevelopmentStatus,
        target_date: date | None,
        now: datetime,
    ) -> None:
        previous_status = self.status
        previous_completed_at = self.completed_at
        self.kind = kind
        self.title = _text(title, "development item title", 240)
        self.description = _optional_text(description, "development item description", 4_000)
        self.status = status
        self.target_date = target_date
        self.completed_at = (
            previous_completed_at
            if status is DevelopmentStatus.COMPLETED
            and previous_status is DevelopmentStatus.COMPLETED
            else now
            if status is DevelopmentStatus.COMPLETED
            else None
        )
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class CareerGrowthEvidenceLink:
    id: UUID
    owner_user_id: UUID
    target_kind: EvidenceTargetKind
    target_id: UUID
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    evidence_revised_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        _positive_version(self.revision_number, "evidence revision number")
        object.__setattr__(
            self,
            "statement_sha256",
            _sha256(self.statement_sha256, "evidence statement hash"),
        )


@dataclass(slots=True)
class CareerReview:
    id: UUID
    owner_user_id: UUID
    cadence: ReviewCadence
    period_start: date
    period_end: date
    latest_version_id: UUID
    latest_version_number: int
    latest_status: ReviewVersionStatus
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.period_end < self.period_start:
            raise CareerGrowthValidationError("review period end cannot precede start")
        if (
            self.cadence is ReviewCadence.QUARTERLY
            and (self.period_end - self.period_start).days > 120
        ):
            raise CareerGrowthValidationError("quarterly review period cannot exceed 120 days")
        if (
            self.cadence is ReviewCadence.ANNUAL
            and (self.period_end - self.period_start).days > 370
        ):
            raise CareerGrowthValidationError("annual review period cannot exceed 370 days")
        _positive_version(self.latest_version_number, "latest review version")
        _positive_version(self.version)

    def advance(
        self,
        *,
        next_version_id: UUID,
        next_version_number: int,
        status: ReviewVersionStatus,
        now: datetime,
    ) -> None:
        if next_version_number != self.latest_version_number + 1:
            raise CareerGrowthValidationError("review versions must be contiguous")
        self.latest_version_id = next_version_id
        self.latest_version_number = next_version_number
        self.latest_status = status
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class CareerReviewVersion:
    id: UUID
    owner_user_id: UUID
    review_id: UUID
    version_number: int
    status: ReviewVersionStatus
    title: str
    summary: str
    achievements: str | None
    growth_areas: str | None
    next_focus: str | None
    change_reason: str
    material_change: bool
    supersedes_version_id: UUID | None
    content_sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        _positive_version(self.version_number, "review version number")
        object.__setattr__(self, "title", _text(self.title, "review title", 240))
        object.__setattr__(self, "summary", _text(self.summary, "review summary", 8_000))
        object.__setattr__(
            self, "achievements", _optional_text(self.achievements, "review achievements", 8_000)
        )
        object.__setattr__(
            self, "growth_areas", _optional_text(self.growth_areas, "review growth areas", 8_000)
        )
        object.__setattr__(
            self, "next_focus", _optional_text(self.next_focus, "review next focus", 8_000)
        )
        object.__setattr__(
            self, "change_reason", _text(self.change_reason, "review change reason", 500)
        )
        object.__setattr__(
            self,
            "content_sha256",
            _sha256(self.content_sha256, "review content hash"),
        )
        if self.content_sha256 != review_content_hash(
            title=self.title,
            summary=self.summary,
            achievements=self.achievements,
            growth_areas=self.growth_areas,
            next_focus=self.next_focus,
        ):
            raise CareerGrowthValidationError("review content hash does not match its content")
        if self.version_number == 1 and self.supersedes_version_id is not None:
            raise CareerGrowthValidationError("first review version cannot supersede another")
        if self.version_number > 1 and self.supersedes_version_id is None:
            raise CareerGrowthValidationError("later review version must identify its predecessor")


def review_content_hash(
    *,
    title: str,
    summary: str,
    achievements: str | None,
    growth_areas: str | None,
    next_focus: str | None,
) -> str:
    payload = json.dumps(
        {
            "achievements": achievements.strip() if achievements else None,
            "growthAreas": growth_areas.strip() if growth_areas else None,
            "nextFocus": next_focus.strip() if next_focus else None,
            "summary": summary.strip(),
            "title": title.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def career_health_snapshot_hash(
    *,
    input_snapshot: dict[str, object],
    configuration_snapshot: dict[str, object],
    formula_snapshot: dict[str, object],
) -> bytes:
    """Hash the complete immutable Career Health calculation input."""

    payload = json.dumps(
        {
            "configuration": configuration_snapshot,
            "formula": formula_snapshot,
            "input": input_snapshot,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).digest()


@dataclass(frozen=True, slots=True)
class CareerGrowthIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_fingerprint: str
    operation: str
    result_id: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", self.idempotency_key) is None:
            raise CareerGrowthValidationError("idempotency key is invalid")
        object.__setattr__(
            self,
            "request_fingerprint",
            _sha256(self.request_fingerprint, "request fingerprint"),
        )
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.operation) is None:
            raise CareerGrowthValidationError("idempotency operation is invalid")


@dataclass(frozen=True, slots=True)
class CareerHealthAnalysis:
    id: UUID
    owner_user_id: UUID
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    input_snapshot: dict[str, object]
    configuration_snapshot: dict[str, object]
    formula_snapshot: dict[str, object]
    snapshot_sha256: bytes
    status: CareerHealthStatus
    raw_score_basis_points: int | None
    display_score: int | None
    label: CareerHealthLabel
    applicable_component_count: int
    applicable_weight_basis_points: int
    insufficient_reason: str | None
    disclaimer: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.engine_version, "engine version", 120)
        _text(self.configuration_version, "configuration version", 120)
        _text(self.feature_schema_version, "feature schema version", 120)
        if len(self.snapshot_sha256) != 32:
            raise CareerGrowthValidationError("career health snapshot hash must contain 32 bytes")
        if self.snapshot_sha256 != career_health_snapshot_hash(
            input_snapshot=self.input_snapshot,
            configuration_snapshot=self.configuration_snapshot,
            formula_snapshot=self.formula_snapshot,
        ):
            raise CareerGrowthValidationError(
                "career health snapshot hash does not match its immutable payload"
            )
        if not 0 <= self.applicable_component_count <= 5:
            raise CareerGrowthValidationError("applicable component count is invalid")
        _basis_points(self.applicable_weight_basis_points, "applicable component weight")
        if self.status is CareerHealthStatus.COMPLETE:
            if self.raw_score_basis_points is None or self.display_score is None:
                raise CareerGrowthValidationError(
                    "complete career health analysis requires a score"
                )
            _basis_points(self.raw_score_basis_points, "career health score")
            if not 0 <= self.display_score <= 100:
                raise CareerGrowthValidationError("career health display score is out of range")
            if self.label is CareerHealthLabel.INSUFFICIENT_DATA:
                raise CareerGrowthValidationError("complete analysis cannot use insufficient label")
            if self.insufficient_reason is not None:
                raise CareerGrowthValidationError(
                    "complete analysis cannot contain an insufficient-data reason"
                )
        else:
            if (
                self.raw_score_basis_points is not None
                or self.display_score is not None
                or self.label is not CareerHealthLabel.INSUFFICIENT_DATA
                or not self.insufficient_reason
            ):
                raise CareerGrowthValidationError(
                    "insufficient analysis must omit scores and include a reason"
                )
        if self.disclaimer != CANONICAL_SCORE_DISCLAIMER:
            raise CareerGrowthValidationError("career health disclaimer is not canonical")


@dataclass(frozen=True, slots=True)
class CareerHealthComponent:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    dimension: CareerHealthDimension
    configured_weight_basis_points: int
    applicable: bool
    score_basis_points: int | None
    contribution_basis_points: int | None
    explanation: str

    def __post_init__(self) -> None:
        _basis_points(self.configured_weight_basis_points, "component weight")
        if self.applicable and (self.score_basis_points is None) != (
            self.contribution_basis_points is None
        ):
            raise CareerGrowthValidationError(
                "component score and contribution must both be present or absent"
            )
        if not self.applicable and (
            self.score_basis_points is not None or self.contribution_basis_points is not None
        ):
            raise CareerGrowthValidationError(
                "unavailable component cannot contain score or contribution"
            )
        if self.score_basis_points is not None and self.contribution_basis_points is not None:
            _basis_points(self.score_basis_points, "component score")
            _basis_points(self.contribution_basis_points, "component contribution")
        object.__setattr__(
            self, "explanation", _text(self.explanation, "component explanation", 1_000)
        )


@dataclass(frozen=True, slots=True)
class CareerHealthFinding:
    id: UUID
    owner_user_id: UUID
    analysis_id: UUID
    code: str
    severity: FindingSeverity
    message: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9_]{3,80}", self.code) is None:
            raise CareerGrowthValidationError("career health finding code is invalid")
        object.__setattr__(self, "message", _text(self.message, "finding message", 500))


@dataclass(frozen=True, slots=True)
class CareerGrowthAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: GrowthAuditAction
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
            "goal_id",
            "milestone_id",
            "development_item_id",
            "review_id",
            "review_version_id",
            "analysis_id",
            "status",
            "reason_code",
            "version",
        }
        for key, value in self.details:
            if key not in allowed:
                raise CareerGrowthValidationError("audit detail key is not allowlisted")
            _text(value, f"audit detail {key}", 120)
