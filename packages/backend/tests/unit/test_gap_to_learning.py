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
from rezumi.modules.career_growth.application.ports import GapSnapshot
from rezumi.modules.career_growth.application.role_roadmap_ports import RoadmapSkillGuidance
from rezumi.modules.career_growth.domain import CareerGrowthNotFound, DevelopmentKind


class StaticRoadmapProvider:
    def __init__(self, guidance: RoadmapSkillGuidance | None) -> None:
        self.guidance = guidance
        self.requested_labels: list[str] = []

    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None:
        self.requested_labels.append(skill_label)
        return self.guidance


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
