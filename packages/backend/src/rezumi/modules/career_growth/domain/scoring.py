"""Deterministic, versioned Career Health calculation."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from .entities import (
    CANONICAL_SCORE_DISCLAIMER,
    CareerHealthDimension,
    CareerHealthLabel,
    CareerHealthStatus,
    DevelopmentKind,
    DevelopmentStatus,
    FindingSeverity,
    GoalStatus,
    MilestoneStatus,
    ReviewCadence,
    career_health_snapshot_hash,
)
from .errors import CareerGrowthValidationError

ENGINE_VERSION = "career-health/1.1.0"
CONFIGURATION_VERSION = "career-health-default/2"
FEATURE_SCHEMA_VERSION = "career-health-features/2"
MAX_INPUT_SNAPSHOT_BYTES = 16_384

COMPONENT_WEIGHTS: dict[CareerHealthDimension, int] = {
    CareerHealthDimension.EVIDENCE_CURRENCY: 2_500,
    CareerHealthDimension.GOAL_PROGRESS: 3_000,
    CareerHealthDimension.DEVELOPMENT_FOLLOW_THROUGH: 2_000,
    CareerHealthDimension.REVIEW_CADENCE: 1_500,
    CareerHealthDimension.READINESS_MAINTENANCE: 1_000,
}
MINIMUM_APPLICABLE_COMPONENTS = 3
MINIMUM_APPLICABLE_WEIGHT = 6_000

CONFIGURATION_SNAPSHOT: dict[str, object] = {
    "componentWeightsBasisPoints": {
        dimension.value: weight for dimension, weight in COMPONENT_WEIGHTS.items()
    },
    "minimumApplicableComponents": MINIMUM_APPLICABLE_COMPONENTS,
    "minimumApplicableWeightBasisPoints": MINIMUM_APPLICABLE_WEIGHT,
    "labels": {
        "wellMaintainedMinimumBasisPoints": 8_000,
        "developingMinimumBasisPoints": 6_000,
    },
    "aggregateRounding": "integer-half-up",
    "contributionAllocation": ("nonnegative-largest-remainder; ties use canonical component order"),
    "maximumInputSnapshotBytes": MAX_INPUT_SNAPSHOT_BYTES,
    "scope": (
        "Longitudinal career-record maintenance only; never job-market value, "
        "an employer or ATS score, or a hiring probability."
    ),
}

FORMULA_SNAPSHOT: dict[str, object] = {
    "aggregate": ("round_half_up(sum(component_score * configured_weight) / applicable_weight)"),
    "componentContributions": (
        "largest_remainder(component_score * configured_weight / applicable_weight, "
        "target=aggregate)"
    ),
    "developmentStatusCreditsBasisPoints": {
        "planned": 0,
        "in_progress": 5_000,
        "paused": 2_500,
        "completed": 10_000,
        "overdueIncomplete": 0,
    },
    "evidenceAgeCreditsBasisPoints": {
        "0To90Days": 10_000,
        "91To180Days": 7_500,
        "181To365Days": 5_000,
        "366To730Days": 2_500,
        "Over730Days": 0,
    },
    "goalMilestoneCreditsBasisPoints": {
        "pending": 0,
        "in_progress": 5_000,
        "completed": 10_000,
    },
    "readinessMaintenance": "eligible-evidence-covered-skills / documented-skills",
    "reviewCadenceCreditsBasisPoints": {
        "quarterly": {"currentThroughDays": 100, "partialThroughDays": 190},
        "annual": {"currentThroughDays": 400, "partialThroughDays": 550},
        "current": 10_000,
        "partial": 5_000,
        "stale": 0,
    },
}


@dataclass(frozen=True, slots=True)
class GrowthEvidenceSnapshot:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    revised_at: datetime
    skill_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if self.revision_number < 1:
            raise CareerGrowthValidationError("evidence revision number must be positive")
        normalized = self.statement_sha256.removeprefix("sha256:").lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise CareerGrowthValidationError("evidence statement hash is invalid")
        object.__setattr__(self, "statement_sha256", normalized)
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise CareerGrowthValidationError("evidence skill links must be unique")


@dataclass(frozen=True, slots=True)
class CareerGrowthSourceSnapshot:
    """Purpose-minimized Career Record facts; no statement or evidence title is copied."""

    evidence: tuple[GrowthEvidenceSnapshot, ...]
    skill_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise CareerGrowthValidationError("source evidence snapshot contains duplicates")
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise CareerGrowthValidationError("source skill snapshot contains duplicates")


@dataclass(frozen=True, slots=True)
class GoalHealthSignal:
    goal_id: UUID
    version: int
    status: GoalStatus
    milestone_statuses: tuple[MilestoneStatus, ...]
    evidence_revision_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class DevelopmentHealthSignal:
    item_id: UUID
    version: int
    kind: DevelopmentKind
    status: DevelopmentStatus
    target_date: date | None
    evidence_revision_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ReviewHealthSignal:
    review_id: UUID
    version: int
    cadence: ReviewCadence
    has_review_data: bool
    latest_finalized_at: datetime | None
    latest_finalized_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class CareerHealthInput:
    as_of: date
    source: CareerGrowthSourceSnapshot
    goals: tuple[GoalHealthSignal, ...]
    development_items: tuple[DevelopmentHealthSignal, ...]
    reviews: tuple[ReviewHealthSignal, ...]


@dataclass(frozen=True, slots=True)
class ScoredComponent:
    dimension: CareerHealthDimension
    configured_weight_basis_points: int
    applicable: bool
    score_basis_points: int | None
    contribution_basis_points: int | None
    explanation: str


@dataclass(frozen=True, slots=True)
class ScoredFinding:
    code: str
    severity: FindingSeverity
    message: str


@dataclass(frozen=True, slots=True)
class ScoredCareerHealth:
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
    components: tuple[ScoredComponent, ...]
    findings: tuple[ScoredFinding, ...]


def score_career_health(value: CareerHealthInput) -> ScoredCareerHealth:
    """Calculate a non-predictive maintenance score using only integer arithmetic."""

    if sum(COMPONENT_WEIGHTS.values()) != 10_000:
        raise CareerGrowthValidationError("career health component weights must total 10000")

    input_snapshot = _input_snapshot(value)
    snapshot_size = len(
        json.dumps(
            input_snapshot,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if snapshot_size > MAX_INPUT_SNAPSHOT_BYTES:
        raise CareerGrowthValidationError("career health input snapshot exceeds byte limit")
    snapshot_sha256 = career_health_snapshot_hash(
        input_snapshot=input_snapshot,
        configuration_snapshot=CONFIGURATION_SNAPSHOT,
        formula_snapshot=FORMULA_SNAPSHOT,
    )
    calculated = (
        _evidence_currency(value),
        _goal_progress(value),
        _development_follow_through(value),
        _review_cadence(value),
        _readiness_maintenance(value),
    )
    applicable = [item for item in calculated if item.applicable]
    applicable_weight = sum(item.configured_weight_basis_points for item in applicable)
    sufficient = (
        len(applicable) >= MINIMUM_APPLICABLE_COMPONENTS
        and applicable_weight >= MINIMUM_APPLICABLE_WEIGHT
    )

    findings = _findings(calculated, sufficient)
    if not sufficient:
        hidden_components = tuple(
            ScoredComponent(
                dimension=item.dimension,
                configured_weight_basis_points=item.configured_weight_basis_points,
                applicable=item.applicable,
                score_basis_points=None,
                contribution_basis_points=None,
                explanation=item.explanation,
            )
            for item in calculated
        )
        return ScoredCareerHealth(
            engine_version=ENGINE_VERSION,
            configuration_version=CONFIGURATION_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            input_snapshot=input_snapshot,
            configuration_snapshot=CONFIGURATION_SNAPSHOT,
            formula_snapshot=FORMULA_SNAPSHOT,
            snapshot_sha256=snapshot_sha256,
            status=CareerHealthStatus.INSUFFICIENT_DATA,
            raw_score_basis_points=None,
            display_score=None,
            label=CareerHealthLabel.INSUFFICIENT_DATA,
            applicable_component_count=len(applicable),
            applicable_weight_basis_points=applicable_weight,
            insufficient_reason=(
                "Career Health requires at least three available components totaling "
                "6000 configured basis points."
            ),
            disclaimer=CANONICAL_SCORE_DISCLAIMER,
            components=hidden_components,
            findings=findings,
        )

    weighted_total = sum(
        _required_score(item) * item.configured_weight_basis_points for item in applicable
    )
    raw_score = _round_half_up(weighted_total, applicable_weight)
    contributions = _largest_remainder_contributions(
        tuple(_required_score(item) * item.configured_weight_basis_points for item in applicable),
        denominator=applicable_weight,
        target=raw_score,
    )
    contribution_by_dimension = {
        item.dimension: contribution
        for item, contribution in zip(applicable, contributions, strict=True)
    }
    components = tuple(
        ScoredComponent(
            dimension=item.dimension,
            configured_weight_basis_points=item.configured_weight_basis_points,
            applicable=item.applicable,
            score_basis_points=item.score_basis_points,
            contribution_basis_points=contribution_by_dimension.get(item.dimension),
            explanation=item.explanation,
        )
        for item in calculated
    )
    return ScoredCareerHealth(
        engine_version=ENGINE_VERSION,
        configuration_version=CONFIGURATION_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        input_snapshot=input_snapshot,
        configuration_snapshot=CONFIGURATION_SNAPSHOT,
        formula_snapshot=FORMULA_SNAPSHOT,
        snapshot_sha256=snapshot_sha256,
        status=CareerHealthStatus.COMPLETE,
        raw_score_basis_points=raw_score,
        display_score=_round_half_up(raw_score, 100),
        label=_label(raw_score),
        applicable_component_count=len(applicable),
        applicable_weight_basis_points=applicable_weight,
        insufficient_reason=None,
        disclaimer=CANONICAL_SCORE_DISCLAIMER,
        components=components,
        findings=findings,
    )


def _evidence_currency(value: CareerHealthInput) -> ScoredComponent:
    evidence = value.source.evidence
    if not evidence:
        return _unavailable(
            CareerHealthDimension.EVIDENCE_CURRENCY,
            "No currently eligible evidence revisions are available for a currency measure.",
        )
    credits = [
        _evidence_age_credit((value.as_of - item.revised_at.date()).days) for item in evidence
    ]
    score = _round_half_up(sum(credits), len(credits))
    return _available(
        CareerHealthDimension.EVIDENCE_CURRENCY,
        score,
        "Average age-band credit across exact, currently eligible evidence revisions.",
    )


def _goal_progress(value: CareerHealthInput) -> ScoredComponent:
    goals = [item for item in value.goals if item.status is not GoalStatus.CANCELLED]
    if not goals:
        return _unavailable(
            CareerHealthDimension.GOAL_PROGRESS,
            "No active, paused, or completed goals are available.",
        )
    scores = [_goal_credit(goal) for goal in goals]
    return _available(
        CareerHealthDimension.GOAL_PROGRESS,
        _round_half_up(sum(scores), len(scores)),
        "Equal-weight mean of non-cancelled goal milestone completion; "
        "completed goals receive full credit.",
    )


def _development_follow_through(value: CareerHealthInput) -> ScoredComponent:
    items = [
        item for item in value.development_items if item.status is not DevelopmentStatus.CANCELLED
    ]
    if not items:
        return _unavailable(
            CareerHealthDimension.DEVELOPMENT_FOLLOW_THROUGH,
            "No non-cancelled learning, certification, review, promotion, "
            "or mobility item is available.",
        )
    credits = [_development_credit(item, value.as_of) for item in items]
    return _available(
        CareerHealthDimension.DEVELOPMENT_FOLLOW_THROUGH,
        _round_half_up(sum(credits), len(credits)),
        "Equal-weight status credit across non-cancelled development items; "
        "overdue incomplete items receive no credit.",
    )


def _review_cadence(value: CareerHealthInput) -> ScoredComponent:
    reviews = [item for item in value.reviews if item.has_review_data]
    if not reviews:
        return _unavailable(
            CareerHealthDimension.REVIEW_CADENCE,
            "No quarterly or annual review record is available.",
        )
    credits = [credit for _cadence, credit in _review_credits(tuple(reviews), value.as_of)]
    return _available(
        CareerHealthDimension.REVIEW_CADENCE,
        _round_half_up(sum(credits), len(credits)),
        "Mean cadence credit for each review cadence present, using immutable finalized versions.",
    )


def _readiness_maintenance(value: CareerHealthInput) -> ScoredComponent:
    if not value.source.skill_ids:
        return _unavailable(
            CareerHealthDimension.READINESS_MAINTENANCE,
            "No documented skills are available for an evidence-coverage maintenance measure.",
        )
    documented_skill_ids = set(value.source.skill_ids)
    covered = {
        skill_id
        for evidence in value.source.evidence
        for skill_id in evidence.skill_ids
        if skill_id in documented_skill_ids
    }
    score = _round_half_up(len(covered) * 10_000, len(value.source.skill_ids))
    return _available(
        CareerHealthDimension.READINESS_MAINTENANCE,
        score,
        "Share of documented skills connected to currently eligible exact evidence revisions.",
    )


def _findings(
    components: tuple[ScoredComponent, ...], sufficient: bool
) -> tuple[ScoredFinding, ...]:
    findings: list[ScoredFinding] = []
    if not sufficient:
        findings.append(
            ScoredFinding(
                code="insufficient_component_coverage",
                severity=FindingSeverity.INFORMATION,
                message=(
                    "Add or maintain enough evidence, goals, development items, reviews, "
                    "and skill evidence links before interpreting a Career Health score."
                ),
            )
        )
    codes = {
        CareerHealthDimension.EVIDENCE_CURRENCY: (
            "evidence_currency_attention",
            "Some eligible evidence is aging; review and update only facts you can support.",
        ),
        CareerHealthDimension.GOAL_PROGRESS: (
            "goal_progress_attention",
            "Goal milestones show limited progress; update milestones to reflect actual work.",
        ),
        CareerHealthDimension.DEVELOPMENT_FOLLOW_THROUGH: (
            "development_follow_through_attention",
            "Development items show limited follow-through or overdue work.",
        ),
        CareerHealthDimension.REVIEW_CADENCE: (
            "review_cadence_attention",
            "Finalized quarterly or annual review history is stale or incomplete.",
        ),
        CareerHealthDimension.READINESS_MAINTENANCE: (
            "skill_evidence_coverage_attention",
            "Some documented skills are not connected to currently eligible evidence.",
        ),
    }
    for component in components:
        if component.score_basis_points is not None and component.score_basis_points < 6_000:
            code, message = codes[component.dimension]
            findings.append(
                ScoredFinding(
                    code=code,
                    severity=FindingSeverity.ATTENTION,
                    message=message,
                )
            )
    return tuple(findings)


def _input_snapshot(value: CareerHealthInput) -> dict[str, object]:
    """Persist only canonical features that can affect the formula.

    Entity IDs, evidence text hashes, and version-history payloads are useful
    provenance elsewhere, but they cannot alter this calculation. Excluding
    them keeps immutable analyses bounded while retaining exact replay inputs.
    """

    evidence_credits = [
        _evidence_age_credit((value.as_of - item.revised_at.date()).days)
        for item in value.source.evidence
    ]
    goal_credits = [
        _goal_credit(goal) for goal in value.goals if goal.status is not GoalStatus.CANCELLED
    ]
    development_credits = [
        _development_credit(item, value.as_of)
        for item in value.development_items
        if item.status is not DevelopmentStatus.CANCELLED
    ]
    review_credits = _review_credits(value.reviews, value.as_of)
    documented_skill_ids = set(value.source.skill_ids)
    covered_skill_ids = {
        skill_id
        for evidence in value.source.evidence
        for skill_id in evidence.skill_ids
        if skill_id in documented_skill_ids
    }
    return {
        "asOf": value.as_of.isoformat(),
        "evidenceCurrencyCreditCounts": _credit_counts(evidence_credits),
        "goalProgressCreditCounts": _credit_counts(goal_credits),
        "developmentFollowThroughCreditCounts": _credit_counts(development_credits),
        "reviewCadenceCredits": {cadence.value: credit for cadence, credit in review_credits},
        "readinessMaintenance": {
            "coveredSkillCount": len(covered_skill_ids),
            "documentedSkillCount": len(documented_skill_ids),
        },
    }


def _credit_counts(values: list[int]) -> dict[str, int]:
    return {str(credit): count for credit, count in sorted(Counter(values).items())}


def _goal_credit(goal: GoalHealthSignal) -> int:
    if goal.status is GoalStatus.COMPLETED:
        return 10_000
    milestones = [
        status for status in goal.milestone_statuses if status is not MilestoneStatus.CANCELLED
    ]
    if not milestones:
        return 0
    return _round_half_up(
        sum(
            {
                MilestoneStatus.PENDING: 0,
                MilestoneStatus.IN_PROGRESS: 5_000,
                MilestoneStatus.COMPLETED: 10_000,
            }[status]
            for status in milestones
        ),
        len(milestones),
    )


def _development_credit(item: DevelopmentHealthSignal, as_of: date) -> int:
    if (
        item.target_date is not None
        and item.target_date < as_of
        and item.status is not DevelopmentStatus.COMPLETED
    ):
        return 0
    return {
        DevelopmentStatus.PLANNED: 0,
        DevelopmentStatus.IN_PROGRESS: 5_000,
        DevelopmentStatus.PAUSED: 2_500,
        DevelopmentStatus.COMPLETED: 10_000,
        DevelopmentStatus.CANCELLED: 0,
    }[item.status]


def _review_credits(
    reviews: tuple[ReviewHealthSignal, ...],
    as_of: date,
) -> tuple[tuple[ReviewCadence, int], ...]:
    latest_by_cadence: dict[ReviewCadence, datetime | None] = {}
    for review in reviews:
        if not review.has_review_data:
            continue
        existing = latest_by_cadence.get(review.cadence)
        if review.latest_finalized_at is not None and (
            existing is None or review.latest_finalized_at > existing
        ):
            latest_by_cadence[review.cadence] = review.latest_finalized_at
        else:
            latest_by_cadence.setdefault(review.cadence, existing)
    result: list[tuple[ReviewCadence, int]] = []
    for cadence in sorted(latest_by_cadence, key=lambda item: item.value):
        finalized_at = latest_by_cadence[cadence]
        if finalized_at is None:
            result.append((cadence, 0))
            continue
        age = max(0, (as_of - finalized_at.date()).days)
        current, partial = (100, 190) if cadence is ReviewCadence.QUARTERLY else (400, 550)
        result.append((cadence, 10_000 if age <= current else 5_000 if age <= partial else 0))
    return tuple(result)


def _available(dimension: CareerHealthDimension, score: int, explanation: str) -> ScoredComponent:
    return ScoredComponent(
        dimension=dimension,
        configured_weight_basis_points=COMPONENT_WEIGHTS[dimension],
        applicable=True,
        score_basis_points=score,
        contribution_basis_points=None,
        explanation=explanation,
    )


def _unavailable(dimension: CareerHealthDimension, explanation: str) -> ScoredComponent:
    return ScoredComponent(
        dimension=dimension,
        configured_weight_basis_points=COMPONENT_WEIGHTS[dimension],
        applicable=False,
        score_basis_points=None,
        contribution_basis_points=None,
        explanation=explanation,
    )


def _evidence_age_credit(age_days: int) -> int:
    age = max(0, age_days)
    if age <= 90:
        return 10_000
    if age <= 180:
        return 7_500
    if age <= 365:
        return 5_000
    if age <= 730:
        return 2_500
    return 0


def _required_score(value: ScoredComponent) -> int:
    if value.score_basis_points is None:
        raise CareerGrowthValidationError("applicable component score is unavailable")
    return value.score_basis_points


def _round_half_up(numerator: int, denominator: int) -> int:
    if denominator <= 0 or numerator < 0:
        raise CareerGrowthValidationError("career health rounding inputs are invalid")
    return (numerator + denominator // 2) // denominator


def _largest_remainder_contributions(
    numerators: tuple[int, ...],
    *,
    denominator: int,
    target: int,
) -> list[int]:
    """Allocate a rounded total without negative or order-dependent residuals."""

    if denominator <= 0 or target < 0 or any(value < 0 for value in numerators):
        raise CareerGrowthValidationError("career health contribution inputs are invalid")
    floors = [value // denominator for value in numerators]
    remaining = target - sum(floors)
    if not 0 <= remaining <= len(numerators):
        raise CareerGrowthValidationError("career health contribution target is invalid")
    ranked = sorted(
        range(len(numerators)),
        key=lambda index: (-(numerators[index] % denominator), index),
    )
    for index in ranked[:remaining]:
        floors[index] += 1
    if any(value < 0 for value in floors) or sum(floors) != target:
        raise CareerGrowthValidationError("career health contribution allocation failed")
    return floors


def _label(score: int) -> CareerHealthLabel:
    if score >= 8_000:
        return CareerHealthLabel.WELL_MAINTAINED
    if score >= 6_000:
        return CareerHealthLabel.DEVELOPING
    return CareerHealthLabel.NEEDS_ATTENTION
