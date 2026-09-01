"""Unit tests for job source connectors and sync-from-source ingestion."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from job_match_memory import FixedClock, MemoryJobMatch, UuidFactory
from rezumi.modules.job_match.application import JobMatchService, RequestContext, SyncFromSource
from rezumi.modules.job_match.application.job_source_ports import JobSourceListing
from rezumi.modules.job_match.domain import JobSourceKind
from rezumi.modules.job_match.infrastructure.job_source.fake_connector import (
    FakeJobSourceConnector,
)
from rezumi.modules.job_match.infrastructure.job_source.greenhouse_connector import (
    GreenhouseJobSourceConnector,
)
from rezumi.modules.job_match.infrastructure.job_source.registry import (
    DefaultJobSourceConnectorRegistry,
)


class _EmptySnapshotProvider:
    async def snapshot(self, owner_user_id):  # type: ignore[no-untyped-def]
        from rezumi.modules.job_match.domain import CareerMatchSnapshot

        _ = owner_user_id
        return CareerMatchSnapshot(evidence=(), skills=())


class _EmptyRoleContext:
    async def role_title(self, owner_user_id, role_id):  # type: ignore[no-untyped-def]
        _ = owner_user_id, role_id
        return None


class _EmptyImporter:
    async def fetch(self, url: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError(url)


def _context(owner: UUID) -> RequestContext:
    return RequestContext(owner, "request-job-source", "trace-job-source")


@pytest.mark.asyncio
async def test_fake_and_greenhouse_connectors_return_validated_fixtures() -> None:
    fake = await FakeJobSourceConnector().fetch_listings("")
    greenhouse = await GreenhouseJobSourceConnector().fetch_listings("platform")
    assert fake[0].external_id == "fake-2001"
    assert greenhouse[0].external_id == "gh-1001"
    assert len(greenhouse) >= 1


@pytest.mark.asyncio
async def test_sync_from_source_dedupes_by_external_id_and_source_kind() -> None:
    owner = uuid4()
    memory = MemoryJobMatch()
    registry = DefaultJobSourceConnectorRegistry((FakeJobSourceConnector(),))
    service = JobMatchService(
        unit_of_work=memory,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=_EmptySnapshotProvider(),
        role_context=_EmptyRoleContext(),
        importer=_EmptyImporter(),
        job_sources=registry,
    )
    first = await service.sync_from_source(
        owner,
        SyncFromSource(platform="fake", query=""),
        context=_context(owner),
    )
    assert len(first.created) == 1
    assert first.skipped == 0
    assert first.created[0].job.external_id == "fake-2001"
    assert first.created[0].job.source_kind is JobSourceKind.FAKE

    second = await service.sync_from_source(
        owner,
        SyncFromSource(platform="fake", query=""),
        context=_context(owner),
    )
    assert second.created == ()
    assert second.skipped == 1


@pytest.mark.asyncio
async def test_sync_from_source_rejects_hostile_listing_payload() -> None:
    class _BadConnector:
        platform = "fake"

        async def fetch_listings(self, query: str) -> tuple[JobSourceListing, ...]:
            _ = query
            return (
                JobSourceListing(
                    external_id="",
                    title="Broken",
                    company=None,
                    location=None,
                    application_url=None,
                    source_text="too short",
                ),
            )

    owner = uuid4()
    service = JobMatchService(
        unit_of_work=MemoryJobMatch(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=_EmptySnapshotProvider(),
        role_context=_EmptyRoleContext(),
        importer=_EmptyImporter(),
        job_sources=DefaultJobSourceConnectorRegistry((_BadConnector(),)),
    )
    from rezumi.modules.job_match.domain import JobMatchValidationError

    with pytest.raises(JobMatchValidationError):
        await service.sync_from_source(
            owner,
            SyncFromSource(platform="fake", query=""),
            context=_context(owner),
        )
