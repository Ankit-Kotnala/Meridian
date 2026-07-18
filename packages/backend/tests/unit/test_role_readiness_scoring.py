"""Deterministic Role Readiness scoring policy tests."""

from __future__ import annotations

from uuid import UUID, uuid4

from role_readiness_memory import PRODUCT_ROLE_ID, MemoryRoleReadiness

from careeros.modules.role_readiness.domain import ReadinessLabel, SkillMatchState
from careeros.modules.role_readiness.domain.scoring import (
    CareerReadinessSnapshot,
    SnapshotEvidence,
    SnapshotSkill,
    score_role_readiness,
)


def _role_and_competencies():
    memory = MemoryRoleReadiness()
    role = memory.roles[PRODUCT_ROLE_ID]
    return role, tuple(memory.competencies[PRODUCT_ROLE_ID])


def test_readiness_score_requires_career_signal() -> None:
    role, competencies = _role_and_competencies()

    result = score_role_readiness(
        role,
        competencies,
        CareerReadinessSnapshot(skills=(), entities=(), evidence=()),
    )

    assert result.display_score is None
    assert result.raw_score_basis_points is None
    assert result.readiness_label is ReadinessLabel.INSUFFICIENT_DATA
    assert result.insufficient_reason == "career_profile_has_no_role_readiness_inputs"
    assert result.components == ()


def test_listed_skill_without_eligible_evidence_is_not_demonstrated() -> None:
    role, competencies = _role_and_competencies()
    skill_id = uuid4()

    result = score_role_readiness(
        role,
        competencies,
        CareerReadinessSnapshot(
            skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
            entities=(),
            evidence=(),
        ),
    )

    matches = {match.competency.label: match for match in result.competency_matches}
    assert matches["Customer discovery"].state is SkillMatchState.LISTED
    assert matches["Customer discovery"].gap_kind == "add_confirmed_evidence"
    assert result.display_score is not None
    assert (
        result.feature_set_hash
        == score_role_readiness(
            role,
            competencies,
            CareerReadinessSnapshot(
                skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
                entities=(),
                evidence=(),
            ),
        ).feature_set_hash
    )


def test_eligible_evidence_demonstrates_competency_and_caps_strength() -> None:
    role, competencies = _role_and_competencies()
    skill_id = UUID("00000000-0000-4000-8000-000000000701")
    evidence_id = UUID("00000000-0000-4000-8000-000000000801")

    result = score_role_readiness(
        role,
        competencies,
        CareerReadinessSnapshot(
            skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
            entities=(),
            evidence=(
                SnapshotEvidence(
                    id=evidence_id,
                    title="Confirmed customer discovery",
                    statement="Confirmed evidence about user research with customers.",
                    context=None,
                    strength="confirmed",
                    skill_ids=(skill_id,),
                    entity_ids=(),
                    has_numeric_claim=False,
                ),
            ),
        ),
    )

    matches = {match.competency.label: match for match in result.competency_matches}
    assert matches["Customer discovery"].state is SkillMatchState.DEMONSTRATED
    assert matches["Customer discovery"].evidence[0].evidence_id == evidence_id
    strength = next(
        component
        for component in result.components
        if component.dimension.value == "evidence_strength"
    )
    assert strength.score_basis_points == 9_000
    assert len(result.feature_set_hash) == 32
