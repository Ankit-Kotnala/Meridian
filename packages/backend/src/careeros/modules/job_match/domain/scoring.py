"""Deterministic Phase 5 job extraction, matching, and scoring."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from uuid import UUID

from .entities import (
    ApplicationReadinessLabel,
    JobPosting,
    OpportunityPriorityLabel,
    PreferenceFit,
    RequirementImportance,
    RequirementMatchState,
    RequirementType,
    TailoringEffort,
)

ENGINE_VERSION = "job-match/1.0.0"
CONFIGURATION_VERSION = "job-match-default/1"
FEATURE_SCHEMA_VERSION = "job-match-features/1"

COMPONENT_WEIGHTS: dict[str, int] = {
    "requirement_coverage": 2_500,
    "responsibility_alignment": 1_500,
    "seniority_alignment": 1_000,
    "domain_alignment": 1_000,
    "evidence_strength": 1_500,
    "ats_readiness": 1_000,
    "content_impact": 1_000,
    "truth_confidence": 500,
}

MATCH_CREDITS: dict[RequirementMatchState, int] = {
    RequirementMatchState.STRONG: 10_000,
    RequirementMatchState.TRANSFERABLE: 6_500,
    RequirementMatchState.PARTIAL: 5_000,
    RequirementMatchState.UNKNOWN: 0,
    RequirementMatchState.MISSING: 0,
    RequirementMatchState.NOT_APPLICABLE: 0,
}

IMPORTANCE_WEIGHTS = {
    RequirementImportance.MANDATORY: 3_000,
    RequirementImportance.PREFERRED: 2_000,
    RequirementImportance.HELPFUL: 1_000,
}

EVIDENCE_STRENGTH_CEILINGS = {
    "verified": 10_000,
    "confirmed": 9_000,
    "supported": 7_000,
}

STOPWORDS = {
    "and",
    "are",
    "can",
    "for",
    "have",
    "must",
    "our",
    "that",
    "the",
    "this",
    "to",
    "with",
    "will",
    "you",
}


@dataclass(frozen=True, slots=True)
class ExtractedRequirement:
    requirement_type: RequirementType
    text: str
    normalized_text: str
    importance: RequirementImportance
    source_start: int
    source_end: int
    confidence_basis_points: int
    sort_order: int


@dataclass(frozen=True, slots=True)
class ExtractedJobContent:
    title: str | None
    company: str | None
    location: str | None
    requirements: tuple[ExtractedRequirement, ...]


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
class CareerMatchSnapshot:
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
class RequirementMatchScore:
    requirement_id: UUID
    requirement_text: str
    requirement_type: RequirementType
    importance: RequirementImportance
    state: RequirementMatchState
    score_basis_points: int
    explanation: str
    recommended_action: str
    hard_gap: bool
    evidence: tuple[EvidenceMatch, ...]


@dataclass(frozen=True, slots=True)
class ComponentScore:
    dimension: str
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class JobMatchScore:
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    feature_set_hash: bytes
    input_snapshot: dict[str, object]
    raw_score_basis_points: int | None
    display_score: int | None
    readiness_label: ApplicationReadinessLabel
    hard_gap_count: int
    insufficient_reason: str | None
    summary: str
    components: tuple[ComponentScore, ...]
    requirement_matches: tuple[RequirementMatchScore, ...]


@dataclass(frozen=True, slots=True)
class OpportunityPriorityInput:
    user_interest: int
    career_direction_fit: int
    compensation_fit: PreferenceFit
    location_fit: PreferenceFit
    work_model_fit: PreferenceFit
    tailoring_effort: TailoringEffort
    existing_contacts: int


@dataclass(frozen=True, slots=True)
class OpportunityPriorityScore:
    priority_label: OpportunityPriorityLabel
    priority_score_basis_points: int
    input_snapshot: dict[str, object]
    reasons_for: tuple[str, ...]
    reconsiderations: tuple[str, ...]
    blockers: tuple[str, ...]
    next_action: str


def extract_job_content(source_text: str, *, max_requirements: int = 80) -> ExtractedJobContent:
    """Extract explicit metadata and source-spanned requirements from user/job text."""

    title: str | None = None
    company: str | None = None
    location: str | None = None
    requirements: list[ExtractedRequirement] = []
    seen: set[str] = set()
    section: str | None = None
    line_start = 0

    for raw_line in source_text.splitlines(keepends=True):
        line_end = line_start + len(raw_line)
        stripped = raw_line.strip()
        if stripped:
            key, value = _metadata_pair(stripped)
            if key == "title":
                title = value
            elif key == "company":
                company = value
            elif key == "location":
                location = value
            else:
                maybe_section = _section(stripped)
                if maybe_section is not None:
                    section = maybe_section
                elif _looks_like_requirement(stripped, section):
                    requirement = _requirement_from_text(
                        stripped,
                        start=line_start + len(raw_line) - len(raw_line.lstrip()),
                        end=line_start + len(raw_line.rstrip()),
                        section=section,
                        sort_order=(len(requirements) + 1) * 10,
                    )
                    if requirement.normalized_text not in seen:
                        requirements.append(requirement)
                        seen.add(requirement.normalized_text)
        line_start = line_end

    if not requirements:
        for match in re.finditer(r"[^.!?\n]{20,240}[.!?]?", source_text):
            text = match.group(0).strip()
            if _looks_like_requirement(text, None):
                requirement = _requirement_from_text(
                    text,
                    start=match.start() + len(match.group(0)) - len(match.group(0).lstrip()),
                    end=match.start() + len(match.group(0).rstrip()),
                    section=None,
                    sort_order=(len(requirements) + 1) * 10,
                )
                if requirement.normalized_text not in seen:
                    requirements.append(requirement)
                    seen.add(requirement.normalized_text)
            if len(requirements) >= max_requirements:
                break

    return ExtractedJobContent(
        title=title,
        company=company,
        location=location,
        requirements=tuple(requirements[:max_requirements]),
    )


def score_job_match(
    job: JobPosting,
    requirements: tuple[tuple[UUID, ExtractedRequirement], ...],
    snapshot: CareerMatchSnapshot,
) -> JobMatchScore:
    """Compare one exact job requirement set with an owned career snapshot."""

    matches = tuple(
        _match_requirement(requirement_id, requirement, snapshot)
        for requirement_id, requirement in requirements
    )
    hard_gap_count = sum(1 for match in matches if match.hard_gap)
    input_snapshot = _snapshot_payload(job, requirements, snapshot)
    feature_hash = _hash(input_snapshot)
    if not requirements:
        return JobMatchScore(
            engine_version=ENGINE_VERSION,
            configuration_version=CONFIGURATION_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_set_hash=feature_hash,
            input_snapshot=input_snapshot,
            raw_score_basis_points=None,
            display_score=None,
            readiness_label=ApplicationReadinessLabel.INSUFFICIENT_DATA,
            hard_gap_count=0,
            insufficient_reason="job_has_no_extractable_requirements",
            summary="Add explicit job requirements before calculating Application Readiness.",
            components=(),
            requirement_matches=(),
        )
    if not snapshot.has_signal:
        return JobMatchScore(
            engine_version=ENGINE_VERSION,
            configuration_version=CONFIGURATION_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_set_hash=feature_hash,
            input_snapshot=input_snapshot,
            raw_score_basis_points=None,
            display_score=None,
            readiness_label=ApplicationReadinessLabel.INSUFFICIENT_DATA,
            hard_gap_count=hard_gap_count,
            insufficient_reason="career_profile_has_no_job_match_inputs",
            summary="Add skills or confirmed evidence before calculating Application Readiness.",
            components=(),
            requirement_matches=matches,
        )

    components = tuple(
        _component(dimension, matches, requirements, job) for dimension in COMPONENT_WEIGHTS
    )
    raw = sum(component.contribution_basis_points for component in components)
    display = _display(raw)
    label = (
        ApplicationReadinessLabel.STRONG
        if display >= 80 and hard_gap_count == 0
        else ApplicationReadinessLabel.VIABLE
        if display >= 60
        else ApplicationReadinessLabel.NEEDS_WORK
    )
    strong = sum(1 for match in matches if match.state is RequirementMatchState.STRONG)
    summary = (
        f"{job.title} match is based on {strong} strong requirement matches "
        f"and {hard_gap_count} mandatory gaps or unknowns."
    )
    return JobMatchScore(
        engine_version=ENGINE_VERSION,
        configuration_version=CONFIGURATION_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_set_hash=feature_hash,
        input_snapshot=input_snapshot,
        raw_score_basis_points=raw,
        display_score=display,
        readiness_label=label,
        hard_gap_count=hard_gap_count,
        insufficient_reason=None,
        summary=summary,
        components=components,
        requirement_matches=matches,
    )


def score_opportunity_priority(
    job: JobPosting,
    match_score: JobMatchScore,
    priority_input: OpportunityPriorityInput,
) -> OpportunityPriorityScore:
    readiness = match_score.raw_score_basis_points or 0
    preference = _average(
        (
            _one_to_five(priority_input.user_interest),
            _one_to_five(priority_input.career_direction_fit),
            _fit(priority_input.compensation_fit),
            _fit(priority_input.location_fit),
            _fit(priority_input.work_model_fit),
        )
    )
    effort_adjustment = {
        TailoringEffort.LOW: 1_000,
        TailoringEffort.MEDIUM: 0,
        TailoringEffort.HIGH: -1_500,
    }[priority_input.tailoring_effort]
    contact_bonus = min(priority_input.existing_contacts, 5) * 250
    raw = max(
        0,
        min(
            10_000,
            (readiness * 45 + preference * 45) // 100 + effort_adjustment + contact_bonus,
        ),
    )
    if match_score.hard_gap_count > 0 and raw < 6_500:
        label = OpportunityPriorityLabel.DEFER
    elif raw >= 7_500 and match_score.hard_gap_count == 0:
        label = OpportunityPriorityLabel.HIGH
    elif raw >= 5_500:
        label = OpportunityPriorityLabel.MEDIUM
    else:
        label = OpportunityPriorityLabel.LOW

    reasons_for = [
        f"Application Readiness is {match_score.display_score}/100."
        if match_score.display_score is not None
        else "Application Readiness needs more career evidence.",
        f"Interest is {priority_input.user_interest}/5.",
    ]
    if priority_input.existing_contacts:
        reasons_for.append("Existing contacts may reduce preparation friction.")
    reconsiderations = []
    if priority_input.tailoring_effort is TailoringEffort.HIGH:
        reconsiderations.append("Tailoring effort is high for this opportunity.")
    for name, fit in (
        ("Compensation", priority_input.compensation_fit),
        ("Location", priority_input.location_fit),
        ("Work model", priority_input.work_model_fit),
    ):
        if fit is PreferenceFit.MISMATCH:
            reconsiderations.append(f"{name} preference is currently a mismatch.")
    blockers = (
        (f"{match_score.hard_gap_count} mandatory requirement gaps remain.",)
        if match_score.hard_gap_count
        else ()
    )
    next_action = (
        "Address mandatory gaps before tailoring."
        if blockers
        else "Prepare a tailored resume and application materials."
        if label in {OpportunityPriorityLabel.HIGH, OpportunityPriorityLabel.MEDIUM}
        else "Compare against another opportunity before investing deeply."
    )
    input_snapshot = {
        "job": {"id": str(job.id), "version": job.version},
        "analysis": {
            "engine": match_score.engine_version,
            "configuration": match_score.configuration_version,
            "displayScore": match_score.display_score,
            "hardGapCount": match_score.hard_gap_count,
        },
        "preferences": {
            "userInterest": priority_input.user_interest,
            "careerDirectionFit": priority_input.career_direction_fit,
            "compensationFit": priority_input.compensation_fit.value,
            "locationFit": priority_input.location_fit.value,
            "workModelFit": priority_input.work_model_fit.value,
            "tailoringEffort": priority_input.tailoring_effort.value,
            "existingContacts": priority_input.existing_contacts,
        },
        "configuration": "opportunity-priority-default/1",
    }
    return OpportunityPriorityScore(
        priority_label=label,
        priority_score_basis_points=raw,
        input_snapshot=input_snapshot,
        reasons_for=tuple(reasons_for),
        reconsiderations=tuple(reconsiderations),
        blockers=blockers,
        next_action=next_action,
    )


def _metadata_pair(text: str) -> tuple[str | None, str | None]:
    match = re.match(r"^(job\s+title|title|company|location)\s*[:\-]\s*(.+)$", text, re.I)
    if match is None:
        return None, None
    key = match.group(1).casefold().replace("job ", "")
    value = match.group(2).strip()
    return key, value[:200] if value else None


def _section(text: str) -> str | None:
    normalized = _normalize(text.rstrip(":"))
    if normalized in {
        "requirements",
        "required qualifications",
        "qualifications",
        "responsibilities",
        "what you will do",
        "preferred qualifications",
        "nice to have",
    }:
        return normalized
    return None


def _looks_like_requirement(text: str, section: str | None) -> bool:
    normalized = _normalize(text)
    if len(normalized) < 12:
        return False
    if section is not None:
        return True
    return any(
        token in normalized
        for token in (
            "required",
            "must",
            "experience",
            "responsible",
            "build",
            "manage",
            "lead",
            "skill",
            "proficient",
            "familiar",
            "degree",
            "certification",
            "authorization",
            "travel",
        )
    )


def _requirement_from_text(
    text: str, *, start: int, end: int, section: str | None, sort_order: int
) -> ExtractedRequirement:
    cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", text).strip()
    normalized = _normalize(cleaned)
    return ExtractedRequirement(
        requirement_type=_requirement_type(normalized),
        text=cleaned,
        normalized_text=normalized,
        importance=_importance(normalized, section),
        source_start=start,
        source_end=end,
        confidence_basis_points=9_000 if _has_explicit_signal(normalized) else 7_000,
        sort_order=sort_order,
    )


def _importance(normalized: str, section: str | None) -> RequirementImportance:
    if any(token in normalized for token in ("preferred", "nice to have", "bonus")):
        return RequirementImportance.PREFERRED
    if section == "preferred qualifications":
        return RequirementImportance.PREFERRED
    if any(token in normalized for token in ("must", "required", "minimum", "need to")):
        return RequirementImportance.MANDATORY
    if section in {
        "requirements",
        "required qualifications",
        "responsibilities",
        "what you will do",
    }:
        return RequirementImportance.MANDATORY
    return RequirementImportance.HELPFUL


def _requirement_type(normalized: str) -> RequirementType:
    if any(token in normalized for token in ("degree", "education", "bachelor", "master")):
        return RequirementType.EDUCATION
    if any(token in normalized for token in ("certification", "certified", "license")):
        return RequirementType.CERTIFICATION
    if any(token in normalized for token in ("years", "senior", "lead", "level")):
        return RequirementType.SENIORITY
    if any(token in normalized for token in ("authorized", "visa", "work authorization")):
        return RequirementType.WORK_AUTHORIZATION
    if "travel" in normalized:
        return RequirementType.TRAVEL
    if any(token in normalized for token in ("salary", "compensation", "pay")):
        return RequirementType.COMPENSATION
    if any(
        token in normalized for token in ("industry", "domain", "saas", "finance", "healthcare")
    ):
        return RequirementType.DOMAIN
    if any(
        token in normalized
        for token in ("python", "sql", "typescript", "dashboard", "api", "testing")
    ):
        return RequirementType.SKILL
    if any(
        token in normalized
        for token in ("own", "manage", "build", "lead", "collaborate", "deliver")
    ):
        return RequirementType.RESPONSIBILITY
    if "experience" in normalized:
        return RequirementType.EXPERIENCE
    return RequirementType.OTHER


def _has_explicit_signal(normalized: str) -> bool:
    return any(
        token in normalized
        for token in ("must", "required", "preferred", "responsible", "experience")
    )


def _match_requirement(
    requirement_id: UUID,
    requirement: ExtractedRequirement,
    snapshot: CareerMatchSnapshot,
) -> RequirementMatchScore:
    if not snapshot.has_signal:
        return RequirementMatchScore(
            requirement_id=requirement_id,
            requirement_text=requirement.text,
            requirement_type=requirement.requirement_type,
            importance=requirement.importance,
            state=RequirementMatchState.UNKNOWN,
            score_basis_points=0,
            explanation=(
                "CareerOS needs profile skills or eligible evidence before evaluating this "
                "requirement."
            ),
            recommended_action="Add career evidence that addresses this requirement.",
            hard_gap=requirement.importance is RequirementImportance.MANDATORY,
            evidence=(),
        )

    requirement_tokens = _tokens(requirement.normalized_text)
    direct = tuple(
        sorted(
            (
                (evidence, _relevance(requirement_tokens, _tokens(_evidence_text(evidence))))
                for evidence in snapshot.evidence
            ),
            key=lambda item: item[1],
            reverse=True,
        )
    )
    direct = tuple(item for item in direct if item[1] >= 4_000)
    if direct:
        best = direct[0][1]
        state = RequirementMatchState.STRONG if best >= 6_000 else RequirementMatchState.PARTIAL
        links = tuple(
            EvidenceMatch(
                evidence_id=evidence.id,
                evidence_title=evidence.title,
                evidence_strength=evidence.strength,
                relevance_basis_points=relevance,
                rationale="Eligible evidence overlaps this exact job requirement.",
            )
            for evidence, relevance in direct[:5]
        )
        return RequirementMatchScore(
            requirement_id=requirement_id,
            requirement_text=requirement.text,
            requirement_type=requirement.requirement_type,
            importance=requirement.importance,
            state=state,
            score_basis_points=MATCH_CREDITS[state],
            explanation=(
                "Eligible evidence directly supports this requirement."
                if state is RequirementMatchState.STRONG
                else "Eligible evidence partially supports this requirement."
            ),
            recommended_action=(
                "Use the linked evidence when tailoring."
                if state is RequirementMatchState.STRONG
                else "Add more specific evidence before relying on this requirement."
            ),
            hard_gap=False,
            evidence=links,
        )

    skill_overlap = any(
        _tokens(_skill_text(skill)).intersection(requirement_tokens) for skill in snapshot.skills
    )
    if skill_overlap:
        return RequirementMatchScore(
            requirement_id=requirement_id,
            requirement_text=requirement.text,
            requirement_type=requirement.requirement_type,
            importance=requirement.importance,
            state=RequirementMatchState.PARTIAL,
            score_basis_points=MATCH_CREDITS[RequirementMatchState.PARTIAL],
            explanation=(
                "A related skill is listed, but no eligible evidence currently proves the "
                "requirement."
            ),
            recommended_action="Add or confirm evidence that demonstrates this listed skill.",
            hard_gap=requirement.importance is RequirementImportance.MANDATORY,
            evidence=(),
        )

    transferable = any(
        _tokens(_entity_text(entity)).intersection(requirement_tokens)
        for entity in snapshot.entities
    )
    if transferable:
        return RequirementMatchScore(
            requirement_id=requirement_id,
            requirement_text=requirement.text,
            requirement_type=requirement.requirement_type,
            importance=requirement.importance,
            state=RequirementMatchState.TRANSFERABLE,
            score_basis_points=MATCH_CREDITS[RequirementMatchState.TRANSFERABLE],
            explanation=(
                "Career context suggests a transferable capability, but direct evidence is missing."
            ),
            recommended_action="Explain the transfer with evidence before applying.",
            hard_gap=False,
            evidence=(),
        )

    return RequirementMatchScore(
        requirement_id=requirement_id,
        requirement_text=requirement.text,
        requirement_type=requirement.requirement_type,
        importance=requirement.importance,
        state=RequirementMatchState.MISSING,
        score_basis_points=0,
        explanation="No eligible evidence currently supports this requirement.",
        recommended_action="Add confirmed evidence or treat this as a gap.",
        hard_gap=requirement.importance is RequirementImportance.MANDATORY,
        evidence=(),
    )


def _component(
    dimension: str,
    matches: tuple[RequirementMatchScore, ...],
    requirements: tuple[tuple[UUID, ExtractedRequirement], ...],
    job: JobPosting,
) -> ComponentScore:
    if dimension == "requirement_coverage":
        score = _weighted(
            tuple(
                (match.score_basis_points, IMPORTANCE_WEIGHTS[match.importance])
                for match in matches
                if match.state is not RequirementMatchState.NOT_APPLICABLE
            )
        )
    elif dimension == "responsibility_alignment":
        score = _typed_score(matches, {RequirementType.RESPONSIBILITY, RequirementType.EXPERIENCE})
    elif dimension == "seniority_alignment":
        score = _typed_score(matches, {RequirementType.SENIORITY, RequirementType.EXPERIENCE})
    elif dimension == "domain_alignment":
        score = _typed_score(matches, {RequirementType.DOMAIN})
    elif dimension == "evidence_strength":
        score = _evidence_strength(matches)
    elif dimension == "ats_readiness":
        score = _job_source_quality(requirements, job)
    elif dimension == "content_impact":
        score = _content_impact(matches)
    else:
        score = _truth_confidence(matches)
    weight = COMPONENT_WEIGHTS[dimension]
    return ComponentScore(
        dimension=dimension,
        weight_basis_points=weight,
        score_basis_points=score,
        contribution_basis_points=_multiply(score, weight),
        explanation=_dimension_explanation(dimension),
    )


def _typed_score(
    matches: tuple[RequirementMatchScore, ...], requirement_types: set[RequirementType]
) -> int:
    scoped = tuple(match for match in matches if match.requirement_type in requirement_types)
    if not scoped:
        return _weighted(tuple((match.score_basis_points, 1_000) for match in matches))
    return _weighted(
        tuple((match.score_basis_points, IMPORTANCE_WEIGHTS[match.importance]) for match in scoped)
    )


def _evidence_strength(matches: tuple[RequirementMatchScore, ...]) -> int:
    values = [
        min(EVIDENCE_STRENGTH_CEILINGS.get(link.evidence_strength, 0), link.relevance_basis_points)
        for match in matches
        for link in match.evidence
    ]
    if not values:
        return 0
    return _weighted(tuple((value, 1_000) for value in values))


def _job_source_quality(
    requirements: tuple[tuple[UUID, ExtractedRequirement], ...], job: JobPosting
) -> int:
    if not requirements:
        return 0
    span_quality = _average(
        tuple(requirement.confidence_basis_points for _, requirement in requirements)
    )
    structure_bonus = 1_000 if len(requirements) >= 3 and job.title != "Imported job" else 0
    return min(10_000, span_quality + structure_bonus)


def _content_impact(matches: tuple[RequirementMatchScore, ...]) -> int:
    impact_matches = tuple(
        match
        for match in matches
        if any(
            token in _normalize(match.requirement_text)
            for token in ("impact", "metric", "improve", "growth", "revenue", "cost")
        )
    )
    if not impact_matches:
        return _weighted(tuple((match.score_basis_points, 1_000) for match in matches))
    return _weighted(
        tuple(
            (match.score_basis_points, IMPORTANCE_WEIGHTS[match.importance])
            for match in impact_matches
        )
    )


def _truth_confidence(matches: tuple[RequirementMatchScore, ...]) -> int:
    direct_count = sum(1 for match in matches if match.evidence)
    if not matches:
        return 0
    coverage = (direct_count * 10_000) // len(matches)
    hard_gap_penalty = min(4_000, sum(1 for match in matches if match.hard_gap) * 1_000)
    return max(0, min(10_000, coverage + 2_000 - hard_gap_penalty))


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


def _average(values: tuple[int, ...]) -> int:
    if not values:
        return 0
    return (sum(values) + len(values) // 2) // len(values)


def _one_to_five(value: int) -> int:
    return max(0, min(10_000, value * 2_000))


def _fit(value: PreferenceFit) -> int:
    return {
        PreferenceFit.STRONG: 10_000,
        PreferenceFit.ACCEPTABLE: 7_000,
        PreferenceFit.UNKNOWN: 5_000,
        PreferenceFit.MISMATCH: 0,
    }[value]


def _dimension_explanation(dimension: str) -> str:
    return {
        "requirement_coverage": "Weighted coverage across applicable job requirements.",
        "responsibility_alignment": "Evidence for responsibilities and experience in the posting.",
        "seniority_alignment": "Signals that match the level or experience requirements.",
        "domain_alignment": "Evidence of domain, industry, or contextual fit.",
        "evidence_strength": "Strength and directness of eligible supporting evidence.",
        "ats_readiness": "Clarity and structure of extracted source-spanned requirements.",
        "content_impact": "Evidence for impact-oriented requirements and outcomes.",
        "truth_confidence": "How much of the match is grounded in eligible evidence.",
    }[dimension]


def _snapshot_payload(
    job: JobPosting,
    requirements: tuple[tuple[UUID, ExtractedRequirement], ...],
    snapshot: CareerMatchSnapshot,
) -> dict[str, object]:
    return {
        "job": {
            "id": str(job.id),
            "version": job.version,
            "sourceSha256": job.source_sha256.hex(),
            "targetRoleId": str(job.target_role_id) if job.target_role_id else None,
        },
        "requirements": [
            {
                "id": str(requirement_id),
                "type": requirement.requirement_type.value,
                "importance": requirement.importance.value,
                "normalizedText": requirement.normalized_text,
                "sourceStart": requirement.source_start,
                "sourceEnd": requirement.source_end,
                "confidenceBasisPoints": requirement.confidence_basis_points,
            }
            for requirement_id, requirement in requirements
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


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", value.casefold())
        if token not in STOPWORDS and len(token) > 2
    }


def _relevance(requirement_tokens: set[str], evidence_tokens: set[str]) -> int:
    if not requirement_tokens or not evidence_tokens:
        return 0
    overlap = len(requirement_tokens.intersection(evidence_tokens))
    if overlap == 0:
        return 0
    return min(10_000, 3_000 + (overlap * 2_000))


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
