"""MongoDB-backed reader for the curated role-roadmap library.

The collection is small by design (an initial curated set of common roles,
see `rezumi.development.seed_role_roadmaps`), so matching is done in-process
in Python rather than via a Mongo query DSL — simpler to get right, and cheap
at this scale. Matching is skill-name based, not role based: a gap's label
(e.g. "Kubernetes") is looked up against every stored role's skills, since a
skill gap is frequently relevant across more than one role.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.career_growth.application.role_roadmap_ports import (
    RoadmapSkill,
    RoadmapSkillGuidance,
    RoadmapStage,
    RoleRoadmap,
)
from rezumi.modules.career_growth.domain.errors import CareerGrowthUnavailable

_MAX_DOCUMENTS = 500


class DisabledRoleRoadmapProvider:
    """No-op adapter used when MongoDB storage is disabled."""

    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None:
        del skill_label
        return None

    async def get_roadmap(self, role_title: str) -> RoleRoadmap | None:
        del role_title
        return None

    async def ping(self) -> None:
        return None

    async def dispose(self) -> None:
        return None


class MongoRoleRoadmapProvider:
    def __init__(self, options: MongoOptions) -> None:
        self._client: MongoClient[Any] = MongoClient(
            options.url,
            connectTimeoutMS=options.connect_timeout_ms,
            serverSelectionTimeoutMS=options.server_selection_timeout_ms,
        )
        self._collection = self._client[options.database_name][options.collection_name]
        self._collection.create_index("roleSlug", unique=True)

    async def ping(self) -> None:
        await self._run(self._client.admin.command, "ping")

    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None:
        documents = await self._run(
            list, self._collection.find({}).limit(_MAX_DOCUMENTS)
        )
        target = skill_label.strip().casefold()
        if not target:
            return None
        substring_match: RoadmapSkillGuidance | None = None
        for document in documents:
            role_slug = str(document.get("roleSlug") or "")
            for stage in document.get("stages") or []:
                stage_name = str(stage.get("stage") or "")
                for skill in stage.get("skills") or []:
                    name = str(skill.get("name") or "")
                    normalized_name = name.casefold()
                    if not name:
                        continue
                    guidance = RoadmapSkillGuidance(
                        role_slug=role_slug,
                        stage=stage_name,
                        skill_name=name,
                        why=str(skill.get("why") or ""),
                        how_to_start=str(skill.get("howToStart") or ""),
                    )
                    if normalized_name == target:
                        return guidance
                    if substring_match is None and (
                        target in normalized_name or normalized_name in target
                    ):
                        substring_match = guidance
        return substring_match

    async def get_roadmap(self, role_title: str) -> RoleRoadmap | None:
        target = role_title.strip().casefold()
        if not target:
            return None
        documents = await self._run(
            list, self._collection.find({}).limit(_MAX_DOCUMENTS)
        )
        exact: dict[str, Any] | None = None
        substring: dict[str, Any] | None = None
        for document in documents:
            title = str(document.get("title") or "").casefold()
            slug = str(document.get("roleSlug") or "").casefold()
            if not title:
                continue
            if title == target or slug == target:
                exact = document
                break
            if substring is None and (target in title or title in target):
                substring = document
        chosen = exact or substring
        return _roadmap(chosen) if chosen is not None else None

    async def dispose(self) -> None:
        await self._run(self._client.close)

    async def _run(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except PyMongoError as exc:
            raise CareerGrowthUnavailable from exc


def _roadmap(document: dict[str, Any]) -> RoleRoadmap:
    stages = []
    for stage in document.get("stages") or []:
        skills = tuple(
            RoadmapSkill(
                how_to_start=str(skill.get("howToStart") or ""),
                name=str(skill.get("name") or ""),
                why=str(skill.get("why") or ""),
            )
            for skill in stage.get("skills") or []
            if skill.get("name")
        )
        if skills:
            stages.append(RoadmapStage(skills=skills, stage=str(stage.get("stage") or "")))
    return RoleRoadmap(
        role_slug=str(document.get("roleSlug") or ""),
        stages=tuple(stages),
        title=str(document.get("title") or ""),
    )
