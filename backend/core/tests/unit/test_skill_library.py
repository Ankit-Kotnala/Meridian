"""Skill library catalog coverage and lookup tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from career_growth_memory import (
    FixedClock,
    MemoryCareerGrowth,
    StaticCareerGrowthSource,
    UuidFactory,
)
from rezumi.development.seed_role_roadmaps import unique_roadmap_skills
from rezumi.modules.career_growth.application import CareerGrowthService, RequestContext
from rezumi.modules.career_growth.application.role_roadmap_ports import (
    RoadmapSkill,
    RoadmapStage,
    RoleRoadmap,
    SkillLibraryRecord,
)
from rezumi.modules.career_growth.domain import CareerGrowthNotFound, CareerGrowthValidationError
from rezumi.modules.career_growth.infrastructure.skill_library_catalog import (
    _https_url,
    library_for_skill,
)


class StaticRoadmapProvider:
    def __init__(self, roadmap: RoleRoadmap | None) -> None:
        self.roadmap = roadmap

    async def find_skill_guidance(self, skill_label: str):
        del skill_label
        return None

    async def get_roadmap(self, role_title: str) -> RoleRoadmap | None:
        del role_title
        return self.roadmap

    async def find_skill_library(self, skill_label: str):
        if self.roadmap is None:
            return None
        target = skill_label.strip().casefold()
        for stage in self.roadmap.stages:
            for skill in stage.skills:
                if skill.name.casefold() == target:
                    return SkillLibraryRecord(
                        how_to_start=skill.how_to_start,
                        library=skill.library,
                        skill_name=skill.name,
                        why=skill.why,
                    )
        return None


class StaticTargetRoleResolver:
    def __init__(self, titles: tuple[str, ...]) -> None:
        self.titles = titles

    async def target_role_titles(self, owner_user_id):
        del owner_user_id
        return self.titles


class StaticSkillsProvider:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names

    async def list_demonstrated_skill_names(self, owner_user_id):
        del owner_user_id
        return self.names


def _context(owner):
    return RequestContext(actor_user_id=owner, request_id="req", trace_id="trc")


def test_every_stored_roadmap_skill_has_a_complete_library() -> None:
    skills = unique_roadmap_skills()
    assert len(skills) >= 40
    names = [name.casefold() for name, _, _ in skills]
    assert len(names) == len(set(names))
    for name, why, how_to_start in skills:
        library = library_for_skill(name, how_to_start=how_to_start, why=why)
        assert len(library.free_courses) >= 20
        assert len(library.paid_courses) >= 12
        assert len(library.notes) >= 3
        assert any(
            item.kind == "youtube" or "youtube.com" in item.url for item in library.free_courses
        )
        providers = {item.provider.casefold() for item in library.paid_courses}
        assert any("coursera" in provider for provider in providers)
        assert any("udemy" in provider for provider in providers)
        direct_free = [
            item
            for item in library.free_courses
            if "results?search" not in item.url and "/search" not in item.url
        ]
        assert len(direct_free) >= 8
        for note in library.notes:
            assert note.file_name.endswith(".pdf")
            assert note.format == "article"
            assert name.split()[0] in note.title or name in note.content
            assert len(note.content) >= 800
            assert "Career Record evidence" in note.content
            assert not note.file_name.endswith(".md")
            assert ".md" not in note.file_name


def test_dsa_library_uses_known_public_course_pages() -> None:
    library = library_for_skill("Data structures and algorithms")
    urls = {item.url for item in (*library.free_courses, *library.paid_courses)}
    assert "https://www.youtube.com/watch?v=8hly31xKli0" in urls
    assert "https://www.coursera.org/specializations/algorithms" in urls
    assert any("udemy.com" in url for url in urls)


def test_library_rejects_non_https_urls() -> None:
    with pytest.raises(CareerGrowthValidationError):
        _https_url("http://www.youtube.com/watch?v=8hly31xKli0")


@pytest.mark.asyncio
async def test_get_skill_library_returns_mapped_resources() -> None:
    owner = uuid4()
    skill = RoadmapSkill(
        how_to_start="Re-implement one structure a week.",
        library=library_for_skill("Data structures and algorithms"),
        name="Data structures and algorithms",
        why="Core to most engineering work.",
    )
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        role_roadmaps=StaticRoadmapProvider(
            roadmap=RoleRoadmap(
                role_slug="software-engineer",
                stages=(RoadmapStage(skills=(skill,), stage="Foundations"),),
                title="Software Engineer",
            ),
        ),
        target_roles=StaticTargetRoleResolver(("Software Engineer",)),
        skills=StaticSkillsProvider(()),
    )

    view = await service.get_skill_library(
        owner,
        "Data structures and algorithms",
        _context(owner),
    )

    assert view.skill_name == "Data structures and algorithms"
    assert view.library.free_courses
    assert view.library.notes[0].file_name.endswith(".pdf")
    assert view.library.notes[0].format == "article"
    assert len(view.library.free_courses) >= 20
    assert len(view.library.notes) >= 3


@pytest.mark.asyncio
async def test_get_skill_library_unknown_skill_is_not_found() -> None:
    owner = uuid4()
    service = CareerGrowthService(
        unit_of_work=MemoryCareerGrowth(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_source=StaticCareerGrowthSource(),
        role_roadmaps=StaticRoadmapProvider(roadmap=None),
        target_roles=StaticTargetRoleResolver(("Software Engineer",)),
        skills=StaticSkillsProvider(()),
    )

    with pytest.raises(CareerGrowthNotFound):
        await service.get_skill_library(owner, "Unmapped skill", _context(owner))
