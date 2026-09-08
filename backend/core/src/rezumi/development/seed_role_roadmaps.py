"""Seed the curated role-roadmap library (Phase 13).

This content is self-authored and versioned — never scraped from roadmap.sh
or any other third-party roadmap site (their licenses do not permit
reproducing their content elsewhere; see ADR 0019 §5 and the plan that
introduced this feature). Role documents live in
``rezumi.modules.career_growth.infrastructure.role_roadmap_catalog``.

Run with:

    uv run --project backend python -m rezumi.development.seed_role_roadmaps

or, against the running local stack:

    make seed-role-roadmaps
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient

from rezumi.foundation.config.mongodb import MongoOptions
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog import ROLE_ROADMAPS
from rezumi.modules.career_growth.infrastructure.skill_library_catalog import (
    library_document,
    library_for_skill,
)

ROADMAP_VERSION = "role-roadmaps/2026-09-07.1"

__all__ = [
    "ROADMAP_VERSION",
    "ROLE_ROADMAPS",
    "main",
    "seed_role_roadmaps",
    "unique_roadmap_skills",
]


def _mongo_options_from_environment() -> MongoOptions:
    return MongoOptions(
        url=os.environ.get("MONGODB_URL", "mongodb://localhost:27017"),
        database_name=os.environ.get("MONGODB_DATABASE", "Rezumi"),
        collection_name=os.environ.get("MONGODB_ROLE_ROADMAPS_COLLECTION", "role-roadmaps"),
    )


def seed_role_roadmaps(options: MongoOptions | None = None) -> int:
    """Upsert every curated roadmap document, keyed by roleSlug. Returns the count."""
    resolved = options or _mongo_options_from_environment()
    client: MongoClient[Any] = MongoClient(
        resolved.url,
        connectTimeoutMS=resolved.connect_timeout_ms,
        serverSelectionTimeoutMS=resolved.server_selection_timeout_ms,
    )
    try:
        collection = client[resolved.database_name][resolved.collection_name]
        collection.create_index("roleSlug", unique=True)
        now = datetime.now(UTC)
        for role in ROLE_ROADMAPS:
            document = {
                **_with_skill_libraries(role),
                "version": ROADMAP_VERSION,
                "sourceNote": (
                    "Self-authored catalog content, not scraped from any third-party roadmap site. "
                    "Live job listings are a separate employer-board catalog and are not invented here."
                ),
                "updatedAt": now,
            }
            collection.update_one(
                {"roleSlug": role["roleSlug"]},
                {"$set": document, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        return len(ROLE_ROADMAPS)
    finally:
        client.close()


def _with_skill_libraries(role: dict[str, Any]) -> dict[str, Any]:
    stages = []
    for stage in role.get("stages") or []:
        skills = []
        for skill in stage.get("skills") or []:
            name = str(skill.get("name") or "")
            why = str(skill.get("why") or "")
            how_to_start = str(skill.get("howToStart") or "")
            library = library_for_skill(name, how_to_start=how_to_start, why=why)
            skills.append({**skill, "library": library_document(library)})
        stages.append({**stage, "skills": skills})
    return {**role, "stages": stages}


def unique_roadmap_skills() -> tuple[tuple[str, str, str], ...]:
    seen: dict[str, tuple[str, str, str]] = {}
    for role in ROLE_ROADMAPS:
        for stage in role.get("stages") or []:
            for skill in stage.get("skills") or []:
                name = str(skill.get("name") or "").strip()
                if not name:
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen[key] = (name, str(skill.get("why") or ""), str(skill.get("howToStart") or ""))
    return tuple(seen.values())


def main() -> int:
    count = seed_role_roadmaps()
    skills = unique_roadmap_skills()
    print(
        f"Seeded {count} role roadmap documents "
        f"({len(skills)} unique skills, version {ROADMAP_VERSION})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
