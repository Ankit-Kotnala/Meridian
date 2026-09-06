"""Read-only port for curated, versioned role-roadmap guidance (Phase 13).

Content behind this port is self-authored and versioned (see
`rezumi.development.seed_role_roadmaps`), never live-scraped — this repo's own
governance (ADR 0019 §5) and third-party roadmap-site licenses (checked before
this feature was built) both rule out reproducing another site's roadmap
content. This composes with the existing gap bridge
(`create_development_item_from_gap`); no new bounded context is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

SKILL_LIBRARY_DISCLAIMER = (
    "These are third-party learning resources. Rezumi does not host the courses, "
    "grade them, or treat completion as Career Record evidence. Study notes are "
    "self-authored readable articles, not copies of paid course materials."
)


@dataclass(frozen=True, slots=True)
class SkillLibraryResource:
    title: str
    provider: str
    url: str
    kind: str


@dataclass(frozen=True, slots=True)
class SkillLibraryNote:
    title: str
    format: str
    file_name: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillLibrary:
    free_courses: tuple[SkillLibraryResource, ...] = ()
    paid_courses: tuple[SkillLibraryResource, ...] = ()
    notes: tuple[SkillLibraryNote, ...] = ()


@dataclass(frozen=True, slots=True)
class RoadmapSkillGuidance:
    role_slug: str
    stage: str
    skill_name: str
    why: str
    how_to_start: str


@dataclass(frozen=True, slots=True)
class SkillLibraryRecord:
    skill_name: str
    why: str
    how_to_start: str
    library: SkillLibrary


@dataclass(frozen=True, slots=True)
class RoadmapSkill:
    name: str
    why: str
    how_to_start: str
    library: SkillLibrary = SkillLibrary()


@dataclass(frozen=True, slots=True)
class RoadmapStage:
    stage: str
    skills: tuple[RoadmapSkill, ...]


@dataclass(frozen=True, slots=True)
class RoleRoadmap:
    role_slug: str
    title: str
    stages: tuple[RoadmapStage, ...]


class RoleRoadmapProvider(Protocol):
    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None: ...

    async def find_skill_library(self, skill_label: str) -> SkillLibraryRecord | None: ...

    async def get_roadmap(self, role_title: str) -> RoleRoadmap | None: ...


class TargetRoleResolver(Protocol):
    """Same shape as job_match's `TargetRoleProvider` — composed structurally,
    not imported across modules; `CompositeTargetRoleProvider` already
    satisfies this without any adapter."""

    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]: ...


class SkillsProvider(Protocol):
    async def list_demonstrated_skill_names(self, owner_user_id: UUID) -> tuple[str, ...]: ...
