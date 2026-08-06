"""Deterministic fixed-point Role Readiness v1 scoring."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from uuid import UUID

from .entities import (
    CompetencyDimension,
    CompetencyImportance,
    ReadinessLabel,
    RoleCompetency,
    RoleDefinition,
    SkillMatchState,
)

ENGINE_VERSION = "role-readiness/1.0.0"
CONFIGURATION_VERSION = "role-readiness-default/1"
FEATURE_SCHEMA_VERSION = "role-readiness-features/1"

DIMENSION_WEIGHTS: dict[CompetencyDimension, int] = {
    CompetencyDimension.CORE_COMPETENCY: 2_000,
    CompetencyDimension.RESPONSIBILITY_ALIGNMENT: 1_500,
    CompetencyDimension.SENIORITY_ALIGNMENT: 1_000,
    CompetencyDimension.LEADERSHIP_EVIDENCE: 1_000,
    CompetencyDimension.DOMAIN_KNOWLEDGE: 1_000,
    CompetencyDimension.TECHNICAL_SKILLS: 1_000,
    CompetencyDimension.BUSINESS_IMPACT: 1_000,
    CompetencyDimension.EDUCATION_CERTIFICATION: 500,
    CompetencyDimension.EVIDENCE_STRENGTH: 1_000,
}

IMPORTANCE_WEIGHTS = {
    CompetencyImportance.REQUIRED: 3_000,
    CompetencyImportance.HELPFUL: 1_000,
}

MATCH_CREDITS = {
    SkillMatchState.DEMONSTRATED: 10_000,
    SkillMatchState.TRANSFERABLE: 6_500,
    SkillMatchState.ADJACENT: 3_500,
    SkillMatchState.LISTED: 2_500,
    SkillMatchState.MISSING: 0,
    SkillMatchState.UNKNOWN: 0,
}

EVIDENCE_STRENGTH_CEILINGS = {
    "verified": 10_000,
    "confirmed": 9_000,
    "supported": 7_000,
}


@dataclass(frozen=True, slots=True)
class SnapshotSkill:
    id: UUID
    name: str
    category: str | None
    proficiency: str | None


@dataclass(frozen=True, slots=True)
class SnapshotEntity:
    id: UUID
    kind: str
    title: str
    organization: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    id: UUID
    title: str
    statement: str
    context: str | None
    strength: str
    skill_ids: tuple[UUID, ...]
    entity_ids: tuple[UUID, ...]
    has_numeric_claim: bool


@dataclass(frozen=True, slots=True)
class CareerReadinessSnapshot:
    skills: tuple[SnapshotSkill, ...]
    entities: tuple[SnapshotEntity, ...]
    evidence: tuple[SnapshotEvidence, ...]

    @property
    def has_signal(self) -> bool:
        return bool(self.skills or self.entities or self.evidence)


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    evidence_id: UUID
    evidence_title: str
    evidence_strength: str
    relevance_basis_points: int
    rationale: str


@dataclass(frozen=True, slots=True)
class CompetencyMatch:
    competency: RoleCompetency
    state: SkillMatchState
    score_basis_points: int
    explanation: str
    gap_kind: str | None
    evidence: tuple[EvidenceMatch, ...]


@dataclass(frozen=True, slots=True)
class ComponentScore:
    dimension: CompetencyDimension
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class RoleReadinessScore:
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    feature_set_hash: bytes
    input_snapshot: dict[str, object]
    raw_score_basis_points: int | None
    display_score: int | None
    readiness_label: ReadinessLabel
    insufficient_reason: str | None
    summary: str
    components: tuple[ComponentScore, ...]
    competency_matches: tuple[CompetencyMatch, ...]


def score_role_readiness(
    role: RoleDefinition,
    competencies: tuple[RoleCompetency, ...],
    snapshot: CareerReadinessSnapshot,
) -> RoleReadinessScore:
    """Compare an owned career snapshot with one versioned role definition."""

    input_snapshot = _snapshot_payload(role, competencies, snapshot)
    feature_hash = _hash(input_snapshot)
    if not snapshot.has_signal:
        return RoleReadinessScore(
            engine_version=ENGINE_VERSION,
            configuration_version=CONFIGURATION_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_set_hash=feature_hash,
            input_snapshot=input_snapshot,
            raw_score_basis_points=None,
            display_score=None,
            readiness_label=ReadinessLabel.INSUFFICIENT_DATA,
            insufficient_reason="career_profile_has_no_role_readiness_inputs",
            summary="Add skills or confirmed evidence before calculating Role Readiness.",
            components=(),
            competency_matches=(),
        )

    matches = tuple(_match_competency(competency, snapshot) for competency in competencies)
    components = tuple(_component(dimension, matches) for dimension in DIMENSION_WEIGHTS)
    raw = sum(component.contribution_basis_points for component in components)
    display = _display(raw)
    required_gaps = [
        match
        for match in matches
        if match.competency.importance is CompetencyImportance.REQUIRED
        and match.state in {SkillMatchState.MISSING, SkillMatchState.UNKNOWN}
    ]
    label = (
        ReadinessLabel.STRONG
        if display >= 80 and not required_gaps
        else ReadinessLabel.DEVELOPING
        if display >= 55
        else ReadinessLabel.NEEDS_EVIDENCE
    )
    strengths = sum(1 for match in matches if match.state is SkillMatchState.DEMONSTRATED)
    summary = (
        f"{role.title} readiness is based on {strengths} demonstrated competencies "
        f"and {len(required_gaps)} required gaps or unknowns."
    )
    return RoleReadinessScore(
        engine_version=ENGINE_VERSION,
        configuration_version=CONFIGURATION_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_set_hash=feature_hash,
        input_snapshot=input_snapshot,
        raw_score_basis_points=raw,
        display_score=display,
        readiness_label=label,
        insufficient_reason=None,
        summary=summary,
        components=components,
        competency_matches=matches,
    )


def _match_competency(
    competency: RoleCompetency, snapshot: CareerReadinessSnapshot
) -> CompetencyMatch:
    skill_matches = tuple(
        skill
        for skill in snapshot.skills
        if _contains_any(_skill_text(skill), competency.skill_keywords)
    )
    direct_evidence = tuple(
        evidence
        for evidence in snapshot.evidence
        if _evidence_matches(evidence, competency, skill_matches)
    )
    if direct_evidence:
        links = tuple(
            EvidenceMatch(
                evidence_id=evidence.id,
                evidence_title=evidence.title,
                evidence_strength=evidence.strength,
                relevance_basis_points=10_000,
                rationale="Eligible evidence directly matches this competency.",
            )
            for evidence in direct_evidence[:5]
        )
        return CompetencyMatch(
            competency=competency,
            state=SkillMatchState.DEMONSTRATED,
            score_basis_points=MATCH_CREDITS[SkillMatchState.DEMONSTRATED],
            explanation="Eligible evidence demonstrates this competency.",
            gap_kind=None,
            evidence=links,
        )
    if skill_matches:
        return CompetencyMatch(
            competency=competency,
            state=SkillMatchState.LISTED,
            score_basis_points=MATCH_CREDITS[SkillMatchState.LISTED],
            explanation="The skill is listed, but no eligible evidence currently demonstrates it.",
            gap_kind="add_confirmed_evidence",
            evidence=(),
        )
    if _snapshot_contains_any(snapshot, competency.transferable_keywords):
        return CompetencyMatch(
            competency=competency,
            state=SkillMatchState.TRANSFERABLE,
            score_basis_points=MATCH_CREDITS[SkillMatchState.TRANSFERABLE],
            explanation="Related evidence suggests a transferable capability.",
            gap_kind="explain_transfer",
            evidence=(),
        )
    if _snapshot_contains_any(snapshot, competency.adjacent_keywords):
        return CompetencyMatch(
            competency=competency,
            state=SkillMatchState.ADJACENT,
            score_basis_points=MATCH_CREDITS[SkillMatchState.ADJACENT],
            explanation="Adjacent experience is present, but the direct competency is not shown.",
            gap_kind="add_direct_scope",
            evidence=(),
        )
    state = SkillMatchState.MISSING if snapshot.has_signal else SkillMatchState.UNKNOWN
    return CompetencyMatch(
        competency=competency,
        state=state,
        score_basis_points=MATCH_CREDITS[state],
        explanation=(
            "No matching skill or eligible evidence is currently present."
            if state is SkillMatchState.MISSING
            else "Rezumi needs more profile data before evaluating this competency."
        ),
        gap_kind="missing_required_evidence"
        if competency.importance is CompetencyImportance.REQUIRED
        else "optional_evidence_to_add",
        evidence=(),
    )


def _component(
    dimension: CompetencyDimension, matches: tuple[CompetencyMatch, ...]
) -> ComponentScore:
    if dimension is CompetencyDimension.EVIDENCE_STRENGTH:
        score = _evidence_strength_score(matches)
    else:
        scoped = tuple(match for match in matches if match.competency.dimension is dimension)
        score = _weighted(
            tuple(
                (
                    match.score_basis_points,
                    IMPORTANCE_WEIGHTS[match.competency.importance],
                )
                for match in scoped
            )
        )
    weight = DIMENSION_WEIGHTS[dimension]
    return ComponentScore(
        dimension=dimension,
        weight_basis_points=weight,
        score_basis_points=score,
        contribution_basis_points=_multiply(score, weight),
        explanation=_dimension_explanation(dimension),
    )


def _evidence_strength_score(matches: tuple[CompetencyMatch, ...]) -> int:
    direct_scores = [
        min(
            EVIDENCE_STRENGTH_CEILINGS.get(link.evidence_strength, 0),
            link.relevance_basis_points,
        )
        for match in matches
        for link in match.evidence
    ]
    if direct_scores:
        return _weighted(tuple((value, 1_000) for value in direct_scores))
    if any(match.state is SkillMatchState.LISTED for match in matches):
        return MATCH_CREDITS[SkillMatchState.LISTED]
    return 0


def _evidence_matches(
    evidence: SnapshotEvidence,
    competency: RoleCompetency,
    skills: tuple[SnapshotSkill, ...],
) -> bool:
    if skills and set(evidence.skill_ids).intersection(skill.id for skill in skills):
        return True
    keywords = (
        *competency.evidence_keywords,
        *competency.skill_keywords,
    )
    return _contains_any(_evidence_text(evidence), keywords)


def _snapshot_contains_any(snapshot: CareerReadinessSnapshot, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return False
    return (
        any(_contains_any(_skill_text(skill), keywords) for skill in snapshot.skills)
        or any(_contains_any(_entity_text(entity), keywords) for entity in snapshot.entities)
        or any(_contains_any(_evidence_text(evidence), keywords) for evidence in snapshot.evidence)
    )


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    haystack = _normalize(text)
    return any(_normalize(keyword) in haystack for keyword in keywords)


def _skill_text(skill: SnapshotSkill) -> str:
    return " ".join(value for value in (skill.name, skill.category, skill.proficiency) if value)


def _entity_text(entity: SnapshotEntity) -> str:
    return " ".join(
        value
        for value in (
            entity.kind,
            entity.title,
            entity.organization,
            entity.description,
        )
        if value
    )


def _evidence_text(evidence: SnapshotEvidence) -> str:
    return " ".join(
        value for value in (evidence.title, evidence.statement, evidence.context) if value
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _weighted(values: tuple[tuple[int, int], ...]) -> int:
    denominator = sum(weight for _, weight in values)
    if denominator <= 0:
        return 0
    numerator = sum(value * weight for value, weight in values)
    return (numerator + denominator // 2) // denominator


def _multiply(value: int, weight: int) -> int:
    return (value * weight + 5_000) // 10_000


def _display(value: int) -> int:
    return (value + 50) // 100


def _dimension_explanation(dimension: CompetencyDimension) -> str:
    return {
        CompetencyDimension.CORE_COMPETENCY: "Coverage of role-defining competencies.",
        CompetencyDimension.RESPONSIBILITY_ALIGNMENT: (
            "Evidence of responsibilities typical for the role."
        ),
        CompetencyDimension.SENIORITY_ALIGNMENT: (
            "Signals that match the role's expected operating level."
        ),
        CompetencyDimension.LEADERSHIP_EVIDENCE: (
            "Evidence of ownership, influence, or team leadership."
        ),
        CompetencyDimension.DOMAIN_KNOWLEDGE: "Relevant domain or industry knowledge.",
        CompetencyDimension.TECHNICAL_SKILLS: (
            "Tools, methods, or technical capabilities for the role."
        ),
        CompetencyDimension.BUSINESS_IMPACT: (
            "Confirmed outcomes or impact context relevant to the role."
        ),
        CompetencyDimension.EDUCATION_CERTIFICATION: (
            "Explicit education or credential expectations."
        ),
        CompetencyDimension.EVIDENCE_STRENGTH: (
            "Strength and directness of eligible supporting evidence."
        ),
    }[dimension]


def _snapshot_payload(
    role: RoleDefinition,
    competencies: tuple[RoleCompetency, ...],
    snapshot: CareerReadinessSnapshot,
) -> dict[str, object]:
    return {
        "role": {
            "id": str(role.id),
            "version": role.version,
            "taxonomyVersionId": str(role.taxonomy_version_id),
        },
        "competencies": [
            {
                "id": str(competency.id),
                "dimension": competency.dimension.value,
                "importance": competency.importance.value,
                "skillKeywords": list(competency.skill_keywords),
                "evidenceKeywords": list(competency.evidence_keywords),
                "transferableKeywords": list(competency.transferable_keywords),
                "adjacentKeywords": list(competency.adjacent_keywords),
            }
            for competency in competencies
        ],
        "career": {
            "skills": [_json_ready(asdict(skill)) for skill in snapshot.skills],
            "entities": [_json_ready(asdict(entity)) for entity in snapshot.entities],
            "evidence": [_json_ready(asdict(evidence)) for evidence in snapshot.evidence],
        },
        "engine": ENGINE_VERSION,
        "configuration": CONFIGURATION_VERSION,
        "featureSchema": FEATURE_SCHEMA_VERSION,
    }


def _json_ready(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _hash(value: dict[str, object]) -> bytes:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).digest()
