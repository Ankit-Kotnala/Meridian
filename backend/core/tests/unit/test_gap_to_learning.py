"""Unit tests for gap-to-learning development item creation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from career_growth_memory import (
    FixedClock,
    MemoryCareerGrowth,
    StaticCareerGrowthSource,
    UuidFactory,
)
from rezumi.modules.career_growth.application import (
    CareerGrowthService,
    CreateDevelopmentItemFromGap,
    RequestContext,
)
from rezumi.modules.career_growth.application.models import ConfirmRoadmapSelection
from rezumi.modules.career_growth.application.ports import GapSnapshot
from rezumi.modules.career_growth.application.role_roadmap_ports import (
    RoadmapSkill,
    RoadmapSkillGuidance,
    RoadmapStage,
    RoleRoadmap,
)
from rezumi.modules.career_growth.domain import CareerGrowthNotFound, DevelopmentKind


class StaticRoadmapProvider:
    def __init__(
        self,
        guidance: RoadmapSkillGuidance | None,
        roadmap: RoleRoadmap | None = None,
    ) -> None:
        self.guidance = guidance
        self.roadmap = roadmap
        self.requested_labels: list[str] = []

    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None:
        self.requested_labels.append(skill_label)
        return self.guidance

    async def get_roadmap(self, role_title: str) -> RoleRoadmap | None:
        del role_title
        return self.roadmap


class StaticTargetRoleResolver:
    def __init__(self, titles: tuple[str, ...]) -> None:
        self.titles = titles

    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]:
        del owner_user_id
        return self.titles


class StaticSkillsProvider:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names

    async def list_skill_names(self, owner_user_id: UUID) -> tuple[str, ...]:
        del owner_user_id
        return self.names


class StaticGapSource:
    def __init__(self, gaps: tuple[GapSnapshot, ...]) -> None:
        self.gaps = gaps
        self.requests: list[tuple[UUID, UUID | None]] = []

    async def list_gaps(
        self,
        owner_user_id: UUID,
        role_profile_id: UUID | None = None,
    ) -> tuple[GapSnapshot, ...]:
        self.requests.append((owner_user_id, role_profile_id))
        return self.gaps


def _context(owner: UUID) -> RequestContext:
    return RequestContext(owner, "request-gap", "trace-gap")


@pytest.mark.asyncio
async def test_create_development_item_from_gap_maps_learning_kind() -> None:
    owner = uuid4()
    role_id = uuid4()
    gaps = (
        GapSnapshot(
            gap_kind="add_confirmed_evidence",
            label="Kubernetes platform operations",
            requirement_text="Eligible evidence is not currently present for this competency.",
            role_profile_id=role_id,
        ),
    )
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        gap_source=StaticGapSource(gaps),
    )
    created = await service.create_development_item_from_gap(
        owner,
        CreateDevelopmentItemFromGap(
            gap_kind="add_confirmed_evidence",
            label="Kubernetes platform operations",
            role_profile_id=role_id,
        ),
        "gap-to-learning-001",
        _context(owner),
    )
    assert created.item.kind is DevelopmentKind.LEARNING
    assert created.item.title == "Address readiness gap: Kubernetes platform operations"
    assert "Eligible evidence" in (created.item.description or "")


@pytest.mark.asyncio
async def test_create_development_item_from_gap_maps_certification_kind() -> None:
    owner = uuid4()
    gaps = (
        GapSnapshot(
            gap_kind="missing_certification",
            label="AWS Solutions Architect",
            requirement_text="A required certification is not documented.",
            role_profile_id=None,
        ),
    )
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        gap_source=StaticGapSource(gaps),
    )
    created = await service.create_development_item_from_gap(
        owner,
        CreateDevelopmentItemFromGap(
            gap_kind="missing_certification",
            label="AWS Solutions Architect",
        ),
        "gap-to-cert-001",
        _context(owner),
    )
    assert created.item.kind is DevelopmentKind.CERTIFICATION


@pytest.mark.asyncio
async def test_create_development_item_from_gap_appends_roadmap_guidance() -> None:
    owner = uuid4()
    gaps = (
        GapSnapshot(
            gap_kind="add_confirmed_evidence",
            label="Kubernetes",
            requirement_text="Eligible evidence is not currently present for this competency.",
            role_profile_id=None,
        ),
    )
    roadmaps = StaticRoadmapProvider(
        RoadmapSkillGuidance(
            role_slug="devops-sre-engineer",
            stage="Core skills",
            skill_name="Kubernetes",
            why="Container orchestration underpins most modern deployments.",
            how_to_start="Deploy one small app to a local Kubernetes cluster end-to-end.",
        )
    )
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        gap_source=StaticGapSource(gaps),
        role_roadmaps=roadmaps,
    )
    created = await service.create_development_item_from_gap(
        owner,
        CreateDevelopmentItemFromGap(gap_kind="add_confirmed_evidence", label="Kubernetes"),
        "gap-to-roadmap-001",
        _context(owner),
    )
    assert "Eligible evidence" in (created.item.description or "")
    assert "How to start: Deploy one small app" in (created.item.description or "")
    assert roadmaps.requested_labels == ["Kubernetes"]


@pytest.mark.asyncio
async def test_create_development_item_from_gap_without_roadmap_match_keeps_requirement_text() -> (
    None
):
    owner = uuid4()
    gaps = (
        GapSnapshot(
            gap_kind="add_confirmed_evidence",
            label="Some very niche skill",
            requirement_text="Eligible evidence is not currently present for this competency.",
            role_profile_id=None,
        ),
    )
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        gap_source=StaticGapSource(gaps),
        role_roadmaps=StaticRoadmapProvider(None),
    )
    created = await service.create_development_item_from_gap(
        owner,
        CreateDevelopmentItemFromGap(
            gap_kind="add_confirmed_evidence", label="Some very niche skill"
        ),
        "gap-no-roadmap-001",
        _context(owner),
    )
    assert created.item.description == (
        "Eligible evidence is not currently present for this competency."
    )
    assert "How to start" not in (created.item.description or "")


@pytest.mark.asyncio
async def test_create_development_item_from_gap_requires_matching_gap() -> None:
    owner = uuid4()
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        gap_source=StaticGapSource(()),
    )
    with pytest.raises(CareerGrowthNotFound):
        await service.create_development_item_from_gap(
            owner,
            CreateDevelopmentItemFromGap(
                gap_kind="add_confirmed_evidence",
                label="Unknown gap",
            ),
            "gap-missing-001",
            _context(owner),
        )


def _sample_roadmap() -> RoleRoadmap:
    return RoleRoadmap(
        role_slug="ai-engineer",
        title="AI Engineer",
        stages=(
            RoadmapStage(
                stage="Foundations",
                skills=(
                    RoadmapSkill(
                        name="Python",
                        why="Most ML tooling is Python-first.",
                        how_to_start="Build one small script end to end.",
                    ),
                    RoadmapSkill(
                        name="Prompt engineering",
                        why="Directly shapes LLM output quality.",
                        how_to_start="Iterate on one prompt against a fixed test set.",
                    ),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_get_role_roadmap_marks_already_known_skills() -> None:
    owner = uuid4()
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        role_roadmaps=StaticRoadmapProvider(None, roadmap=_sample_roadmap()),
        target_roles=StaticTargetRoleResolver(("AI Engineer",)),
        skills=StaticSkillsProvider(("Python programming",)),
    )

    roadmap = await service.get_role_roadmap(owner, _context(owner))

    assert roadmap is not None
    assert roadmap.role_title == "AI Engineer"
    skills_by_name = {
        skill.name: skill for stage in roadmap.stages for skill in stage.skills
    }
    assert skills_by_name["Python"].already_demonstrated is True
    assert skills_by_name["Prompt engineering"].already_demonstrated is False


@pytest.mark.asyncio
async def test_get_role_roadmap_returns_none_without_target_role() -> None:
    owner = uuid4()
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        role_roadmaps=StaticRoadmapProvider(None, roadmap=_sample_roadmap()),
        target_roles=StaticTargetRoleResolver(()),
        skills=StaticSkillsProvider(()),
    )

    assert await service.get_role_roadmap(owner, _context(owner)) is None


@pytest.mark.asyncio
async def test_confirm_roadmap_selection_creates_planned_items_idempotently() -> None:
    owner = uuid4()
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        role_roadmaps=StaticRoadmapProvider(
            RoadmapSkillGuidance(
                role_slug="ai-engineer",
                stage="Foundations",
                skill_name="Prompt engineering",
                why="Directly shapes LLM output quality.",
                how_to_start="Iterate on one prompt against a fixed test set.",
            )
        ),
    )
    selection = ConfirmRoadmapSelection(
        role_title="AI Engineer",
        included_skill_names=("Prompt engineering",),
    )

    created = await service.confirm_roadmap_selection(owner, selection, _context(owner))
    assert len(created) == 1
    item = created[0].item
    assert item.kind == DevelopmentKind.LEARNING
    assert item.title == "Learn: Prompt engineering"
    assert "How to start" in (item.description or "")

    replayed = await service.confirm_roadmap_selection(owner, selection, _context(owner))
    assert replayed[0].item.id == item.id
