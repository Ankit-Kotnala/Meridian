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
import re
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
        documents = await self._run(list, self._collection.find({}).limit(_MAX_DOCUMENTS))
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
        target = _normalize_role_label(role_title)
        if not target:
            return None
        documents = await self._run(list, self._collection.find({}).limit(_MAX_DOCUMENTS))
        chosen = _best_roadmap_match(documents, target)
        return _roadmap(chosen) if chosen is not None else None

    async def dispose(self) -> None:
        await self._run(self._client.close)

    async def _run(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except PyMongoError as exc:
            raise CareerGrowthUnavailable from exc


_SENIORITY_TOKENS = {
    "associate",
    "chief",
    "head",
    "intern",
    "junior",
    "jr",
    "lead",
    "principal",
    "senior",
    "sr",
    "staff",
}
_LEVEL_TOKENS = {"i", "ii", "iii", "iv", "v"}


def _best_roadmap_match(
    documents: list[dict[str, Any]],
    target: str,
) -> dict[str, Any] | None:
    best_document: dict[str, Any] | None = None
    best_score = (0, 0, 0)
    target_without_seniority = _without_seniority(target)
    for document in sorted(
        documents,
        key=lambda item: str(item.get("roleSlug") or ""),
    ):
        for label in _document_labels(document):
            normalized = _normalize_role_label(label)
            if not normalized:
                continue
            score = (0, 0, 0)
            if normalized == target:
                score = (3, len(normalized.split()), len(normalized))
            elif (
                target_without_seniority
                and _without_seniority(normalized) == target_without_seniority
            ):
                score = (2, len(normalized.split()), len(normalized))
            elif _contains_role_phrase(target, normalized) or _contains_role_phrase(
                normalized, target
            ):
                score = (1, len(normalized.split()), len(normalized))
            if score > best_score:
                best_document = document
                best_score = score
    return best_document


def _document_labels(document: dict[str, Any]) -> tuple[str, ...]:
    aliases = document.get("aliases")
    safe_aliases = aliases if isinstance(aliases, list) else ()
    return (
        str(document.get("title") or ""),
        str(document.get("roleSlug") or ""),
        *(str(alias) for alias in safe_aliases if isinstance(alias, str)),
    )


def _normalize_role_label(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _without_seniority(value: str) -> str:
    return " ".join(
        token
        for token in value.split()
        if token not in _SENIORITY_TOKENS and token not in _LEVEL_TOKENS
    )


def _contains_role_phrase(longer: str, shorter: str) -> bool:
    longer_tokens = longer.split()
    shorter_tokens = shorter.split()
    if len(shorter_tokens) < 2 or len(shorter_tokens) >= len(longer_tokens):
        return False
    width = len(shorter_tokens)
    return any(
        longer_tokens[start : start + width] == shorter_tokens
        for start in range(len(longer_tokens) - width + 1)
    )


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
