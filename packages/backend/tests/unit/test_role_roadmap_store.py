"""Unit tests for the Mongo-backed role-roadmap skill matcher."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rezumi.modules.career_growth.infrastructure.role_roadmap_store import (
    DisabledRoleRoadmapProvider,
    MongoRoleRoadmapProvider,
)

_DOCUMENTS = [
    {
        "roleSlug": "devops-sre-engineer",
        "title": "DevOps / SRE Engineer",
        "stages": [
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Kubernetes",
                        "why": "Container orchestration underpins most deployments.",
                        "howToStart": "Deploy one small app to a local cluster.",
                    },
                    {
                        "name": "CI/CD pipelines",
                        "why": "Fast pipelines let teams ship safely.",
                        "howToStart": "Build a pipeline that tests and deploys on merge.",
                    },
                ],
            }
        ],
    },
    {
        "roleSlug": "software-engineer",
        "title": "Software Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Data structures and algorithms",
                        "why": "Core to most engineering work.",
                        "howToStart": "Re-implement one structure a week.",
                    }
                ],
            }
        ],
    },
]


def _provider_with_mocked_collection() -> tuple[MongoRoleRoadmapProvider, MagicMock]:
    # Bypass __init__ (which opens a real MongoClient) and inject a fake
    # collection directly -- this test is about the in-process matching
    # logic, not the pymongo wiring.
    provider = MongoRoleRoadmapProvider.__new__(MongoRoleRoadmapProvider)
    mock_collection = MagicMock()
    provider._client = MagicMock()
    provider._collection = mock_collection
    return provider, mock_collection


@pytest.mark.asyncio
async def test_exact_match_returns_the_right_skill() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    guidance = await provider.find_skill_guidance("Kubernetes")

    assert guidance is not None
    assert guidance.role_slug == "devops-sre-engineer"
    assert guidance.how_to_start == "Deploy one small app to a local cluster."


@pytest.mark.asyncio
async def test_case_insensitive_match() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    guidance = await provider.find_skill_guidance("kubernetes")

    assert guidance is not None
    assert guidance.skill_name == "Kubernetes"


@pytest.mark.asyncio
async def test_substring_fallback_match() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    guidance = await provider.find_skill_guidance("Kubernetes platform operations")

    assert guidance is not None
    assert guidance.skill_name == "Kubernetes"


@pytest.mark.asyncio
async def test_no_match_returns_none() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    guidance = await provider.find_skill_guidance("Completely unrelated topic")

    assert guidance is None


@pytest.mark.asyncio
async def test_disabled_provider_always_returns_none() -> None:
    provider = DisabledRoleRoadmapProvider()

    assert await provider.find_skill_guidance("Kubernetes") is None
    assert await provider.get_roadmap("Software Engineer") is None
    await provider.ping()
    await provider.dispose()


@pytest.mark.asyncio
async def test_get_roadmap_matches_by_exact_title() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    roadmap = await provider.get_roadmap("Software Engineer")

    assert roadmap is not None
    assert roadmap.role_slug == "software-engineer"
    assert roadmap.stages[0].stage == "Foundations"
    assert roadmap.stages[0].skills[0].name == "Data structures and algorithms"


@pytest.mark.asyncio
async def test_get_roadmap_matches_by_role_slug() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    roadmap = await provider.get_roadmap("devops-sre-engineer")

    assert roadmap is not None
    assert roadmap.title == "DevOps / SRE Engineer"


@pytest.mark.asyncio
async def test_get_roadmap_returns_none_when_unmatched() -> None:
    provider, collection = _provider_with_mocked_collection()
    collection.find.return_value.limit.return_value = _DOCUMENTS

    assert await provider.get_roadmap("Astronaut") is None
