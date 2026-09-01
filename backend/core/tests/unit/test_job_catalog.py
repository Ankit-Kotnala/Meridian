"""Shared job catalog: connectors, sync, query, and target-role resolution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from career_record_memory import FakeResumeSourceQuery, FixedClock, MemoryCareerRecord, UuidFactory

from rezumi.modules.career_record.application import CareerRecordService, RequestContext
from rezumi.modules.career_record.application.models import CareerEntityData
from rezumi.modules.career_record.domain import CareerEntityKind, EmploymentType
from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.application.job_catalog_query import JobCatalogQueryService
from rezumi.modules.job_match.application.job_catalog_sync import JobCatalogSyncService
from rezumi.modules.job_match.infrastructure.job_catalog.arbeitnow_connector import (
    ArbeitnowCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.ashby_connector import (
    AshbyIndiaCatalogConnector,
    AshbyIndiaCatalogOptions,
)
from rezumi.modules.job_match.infrastructure.job_catalog.fake_connector import (
    FakeCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.greenhouse_connector import (
    GreenhouseIndiaCatalogConnector,
    GreenhouseIndiaCatalogOptions,
)
from rezumi.modules.job_match.infrastructure.job_catalog.himalayas_connector import (
    HimalayasCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.jobicy_connector import (
    JobicyCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.registry import (
    default_job_catalog_connectors,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remoteok_connector import (
    RemoteOkCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.job_catalog.remotive_connector import (
    RemotiveCatalogConnector,
)
from rezumi.modules.job_match.infrastructure.target_role_provider import (
    CompositeTargetRoleProvider,
)
from rezumi.modules.role_readiness.application import RoleReadinessService, SaveRole
from role_readiness_memory import (
    PRODUCT_ROLE_ID,
    MemoryRoleReadiness,
    StaticSnapshotProvider,
    sample_readiness_snapshot,
)
from role_readiness_memory import FixedClock as RoleReadinessFixedClock
from role_readiness_memory import UuidFactory as RoleReadinessUuidFactory

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


class _FakeHttpResponse:
    def __init__(self, payload: object) -> None:
        self._buffer = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, _size: int) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class _MemoryJobCatalogStore:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, str], CatalogJobListing] = {}

    async def ping(self) -> None:
        return None

    async def upsert_listing(self, listing: CatalogJobListing, *, fetched_at: datetime) -> None:
        _ = fetched_at
        self.documents[(listing.platform, listing.external_id)] = listing

    async def search(
        self, *, keywords: tuple[str, ...], limit: int, offset: int = 0
    ) -> tuple[CatalogJobListing, ...]:
        if not keywords:
            return tuple(self.documents.values())[offset : offset + limit]
        lowered = {word.casefold() for word in keywords}
        matches = [
            listing
            for listing in self.documents.values()
            if lowered & set(listing.title.casefold().split())
        ]
        return tuple(matches[offset : offset + limit])

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        return self.documents.get((platform, external_id))

    async def dispose(self) -> None:
        return None


# --- Connectors -------------------------------------------------------------


@pytest.mark.asyncio
async def test_greenhouse_india_connector_filters_configured_public_boards() -> None:
    connector = GreenhouseIndiaCatalogConnector(
        GreenhouseIndiaCatalogOptions(board_tokens=("highradius",))
    )
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Platform Engineer",
                "absolute_url": "https://boards.greenhouse.io/highradius/jobs/123",
                "location": {"name": "Hyderabad, Telangana, India"},
                "content": "<p>Build <b>reliable</b> systems.</p>",
                "updated_at": "2026-08-20T00:00:00Z",
            },
            {
                "id": 124,
                "title": "US-only Engineer",
                "absolute_url": "https://boards.greenhouse.io/highradius/jobs/124",
                "location": {"name": "Austin, Texas, United States"},
            },
        ]
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.greenhouse_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    listing = listings[0]
    assert listing.platform == "greenhouse"
    assert listing.external_id == "highradius:123"
    assert listing.location == "Hyderabad, Telangana, India"
    assert "Build reliable systems" in listing.source_text
    assert listing.posted_at is not None


@pytest.mark.asyncio
async def test_greenhouse_global_connector_keeps_non_india_roles() -> None:
    connector = GreenhouseIndiaCatalogConnector(
        GreenhouseIndiaCatalogOptions(board_tokens=("stripe",), include_global=True)
    )
    payload = {
        "jobs": [
            {
                "id": 125,
                "title": "Platform Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/125",
                "location": {"name": "Seattle, Washington, United States"},
                "content": "<p>Build global systems.</p>",
                "updated_at": "2026-08-20T00:00:00Z",
            }
        ]
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.greenhouse_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    assert listings[0].location == "Seattle, Washington, United States"


@pytest.mark.asyncio
async def test_ashby_india_connector_filters_configured_public_boards() -> None:
    connector = AshbyIndiaCatalogConnector(AshbyIndiaCatalogOptions(board_names=("riveron",)))
    payload = {
        "jobs": [
            {
                "id": "india-1",
                "title": "Data Engineer",
                "applyUrl": "https://jobs.ashbyhq.com/riveron/india-1/application",
                "location": "Pune, India",
                "isRemote": False,
                "descriptionPlain": "Build reliable data products.",
                "publishedAt": "2026-08-20T00:00:00Z",
            },
            {
                "id": "us-1",
                "title": "US-only Engineer",
                "applyUrl": "https://jobs.ashbyhq.com/riveron/us-1/application",
                "location": "Austin, Texas, United States",
            },
        ]
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.ashby_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    listing = listings[0]
    assert listing.platform == "ashby"
    assert listing.external_id == "riveron:india-1"
    assert listing.location == "Pune, India"
    assert "Build reliable data products" in listing.source_text
    assert listing.posted_at is not None


@pytest.mark.asyncio
async def test_remotive_connector_parses_and_rejects_malformed_entries() -> None:
    connector = RemotiveCatalogConnector()
    payload = {
        "jobs": [
            {
                "id": 1,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "url": "https://remotive.com/jobs/1",
                "candidate_required_location": "Worldwide",
                "category": "Software Development",
                "description": "<p>Build <b>APIs</b>.</p>",
                "publication_date": "2026-08-20T00:00:00",
            },
            {"id": "", "title": "Missing id", "url": "https://remotive.com/jobs/2"},
            {"id": 3, "title": "No URL"},
        ]
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.remotive_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    listing = listings[0]
    assert listing.platform == "remotive"
    assert listing.external_id == "1"
    assert listing.application_url == "https://remotive.com/jobs/1"
    assert "Build APIs" in listing.source_text
    assert listing.remote is True
    assert listing.posted_at is not None


@pytest.mark.asyncio
async def test_remoteok_connector_skips_the_legal_notice_entry() -> None:
    connector = RemoteOkCatalogConnector()
    payload = [
        {"legal": "notice"},
        {
            "id": "42",
            "position": "Frontend Engineer",
            "company": "Acme",
            "url": "https://remoteok.com/remote-jobs/42",
            "location": "Remote",
            "tags": ["react", "typescript"],
            "description": "Ship UI features.",
            "date": "2026-08-20T00:00:00",
        },
    ]
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.remoteok_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    assert listings[0].external_id == "42"
    assert listings[0].platform == "remoteok"


@pytest.mark.asyncio
async def test_arbeitnow_connector_stops_when_there_is_no_next_page() -> None:
    connector = ArbeitnowCatalogConnector()
    payload = {
        "data": [
            {
                "slug": "acme-engineer",
                "title": "Platform Engineer",
                "company_name": "Acme",
                "url": "https://arbeitnow.com/jobs/acme-engineer",
                "location": "Berlin",
                "remote": True,
                "tags": ["kubernetes"],
                "job_types": ["full_time"],
                "description": "Operate the platform.",
                "created_at": 1_755_648_000,
            }
        ],
        "links": {},
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.arbeitnow_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    assert listings[0].platform == "arbeitnow"
    assert listings[0].remote is True


@pytest.mark.asyncio
async def test_jobicy_connector_parses_and_rejects_malformed_entries() -> None:
    connector = JobicyCatalogConnector()
    payload = {
        "jobs": [
            {
                "id": 101,
                "jobTitle": "Data Analyst",
                "companyName": "Acme",
                "url": "https://jobicy.com/jobs/101-data-analyst",
                "jobGeo": "USA",
                "jobIndustry": ["Data Science"],
                "jobType": ["Full-Time"],
                "jobDescription": "<p>Analyze <b>data</b>.</p>",
                "pubDate": "2026-08-20T00:00:00+00:00",
            },
            {"id": "", "jobTitle": "Missing id", "url": "https://jobicy.com/jobs/102"},
            {"id": 103, "jobTitle": "No URL"},
        ]
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.jobicy_connector.urlopen",
        return_value=_FakeHttpResponse(payload),
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert len(listings) == 1
    listing = listings[0]
    assert listing.platform == "jobicy"
    assert listing.external_id == "101"
    assert listing.application_url == "https://jobicy.com/jobs/101-data-analyst"
    assert "Analyze data" in listing.source_text
    assert listing.remote is True
    assert listing.posted_at is not None


@pytest.mark.asyncio
async def test_himalayas_connector_follows_cursor_pagination() -> None:
    connector = HimalayasCatalogConnector()
    first_page = {
        "jobs": [
            {
                "guid": "https://himalayas.app/companies/acme/jobs/backend-engineer",
                "title": "Backend Engineer",
                "companyName": "Acme",
                "applicationLink": "https://himalayas.app/companies/acme/jobs/backend-engineer",
                "locationRestrictions": ["United States"],
                "categories": ["Engineering"],
                "description": "Build the platform.",
                "pubDate": 1_755_648_000,
            },
            {"guid": "", "title": "Missing guid"},
        ],
        "nextCursor": "cursor-2",
    }
    second_page = {
        "jobs": [
            {
                "guid": "https://himalayas.app/companies/acme/jobs/data-scientist",
                "title": "Data Scientist",
                "companyName": "Acme",
                "applicationLink": "https://himalayas.app/companies/acme/jobs/data-scientist",
                "locationRestrictions": ["Worldwide"],
                "categories": ["Data"],
                "description": "Model the data.",
                "pubDate": 1_755_648_100,
            },
        ],
        "nextCursor": None,
    }
    with patch(
        "rezumi.modules.job_match.infrastructure.job_catalog.himalayas_connector.urlopen",
        side_effect=[_FakeHttpResponse(first_page), _FakeHttpResponse(second_page)],
    ):
        listings = [listing async for listing in connector.iter_listings()]

    assert [listing.title for listing in listings] == ["Backend Engineer", "Data Scientist"]
    assert all(listing.platform == "himalayas" for listing in listings)
    assert all(listing.remote is True for listing in listings)


def test_catalog_save_keys_hash_url_ids_that_are_not_legal_idempotency_keys() -> None:
    from rezumi.modules.job_match.application.job_catalog_query import catalog_save_keys

    short_key, short_tracked = catalog_save_keys("fake", "fake-1")
    assert short_key == "catalog:fake:fake-1"
    assert short_tracked == "fake:fake-1"

    listing_id = "https://himalayas.app/companies/acme/jobs/backend-engineer"
    hashed_key, tracked = catalog_save_keys("himalayas", listing_id)
    assert hashed_key.startswith("catalog:")
    assert "/" not in hashed_key
    assert len(hashed_key) <= 128
    assert tracked.startswith("himalayas:")
    assert len(tracked) <= 200


def test_default_registry_has_five_zero_config_connectors() -> None:
    connectors = default_job_catalog_connectors()
    assert {connector.platform for connector in connectors} == {
        "remotive",
        "remoteok",
        "arbeitnow",
        "himalayas",
        "jobicy",
    }


# --- Sync service -------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_service_upserts_every_listing_from_every_connector() -> None:
    store = _MemoryJobCatalogStore()
    service = JobCatalogSyncService(
        connectors=(FakeCatalogConnector(),), store=store, clock=FixedClock(NOW)
    )

    results = await service.sync_all()

    assert len(results) == 1
    assert results[0].platform == "fake"
    assert results[0].fetched == 2
    assert results[0].upserted == 2
    assert results[0].rejected == 0
    assert len(store.documents) == 2


# --- Query service -------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_service_matches_by_target_role_keywords() -> None:
    store = _MemoryJobCatalogStore()
    sync = JobCatalogSyncService(
        connectors=(FakeCatalogConnector(),), store=store, clock=FixedClock(NOW)
    )
    await sync.sync_all()

    class _StaticTargetRoles:
        async def target_role_titles(self, owner_user_id):
            _ = owner_user_id
            return ("Software Engineer",)

    query = JobCatalogQueryService(store=store, target_roles=_StaticTargetRoles())
    result = await query.search_for_owner(uuid4())

    assert result.target_role_titles == ("Software Engineer",)
    assert result.suggested_role_titles == ("Software Engineer",)
    assert result.selected_role_titles == ()
    assert len(result.listings) == 1
    assert result.listings[0].title == "Software Engineer"


@pytest.mark.asyncio
async def test_query_service_prefers_explicit_role_preference_over_suggestion() -> None:
    store = _MemoryJobCatalogStore()
    sync = JobCatalogSyncService(
        connectors=(FakeCatalogConnector(),), store=store, clock=FixedClock(NOW)
    )
    await sync.sync_all()

    class _StaticTargetRoles:
        async def target_role_titles(self, owner_user_id):
            _ = owner_user_id
            return ("Backend Engineer",)

    class _StaticRolePreference:
        async def get_role_preference(self, owner_user_id):
            _ = owner_user_id
            return ("Software Engineer",)

    query = JobCatalogQueryService(
        store=store,
        target_roles=_StaticTargetRoles(),
        role_preferences=_StaticRolePreference(),
    )
    result = await query.search_for_owner(uuid4())

    assert result.suggested_role_titles == ("Backend Engineer",)
    assert result.selected_role_titles == ("Software Engineer",)
    assert result.target_role_titles == ("Software Engineer",)
    assert len(result.listings) == 1
    assert result.listings[0].title == "Software Engineer"


@pytest.mark.asyncio
async def test_query_service_browse_paginates_with_has_more() -> None:
    store = _MemoryJobCatalogStore()
    for index in range(3):
        await store.upsert_listing(
            CatalogJobListing(
                platform="fake",
                external_id=f"listing-{index}",
                title=f"Widget Engineer {index}",
                company="Fixture Co",
                location=None,
                remote=True,
                application_url=None,
                source_text="Build widgets.",
                posted_at=None,
            ),
            fetched_at=NOW,
        )

    class _EmptyTargetRoles:
        async def target_role_titles(self, owner_user_id):
            _ = owner_user_id
            return ()

    query = JobCatalogQueryService(store=store, target_roles=_EmptyTargetRoles())

    first_page, first_has_more = await query.browse(query="", limit=2, offset=0)
    assert len(first_page) == 2
    assert first_has_more is True

    second_page, second_has_more = await query.browse(query="", limit=2, offset=2)
    assert len(second_page) == 1
    assert second_has_more is False


# --- Target-role provider -------------------------------------------------------------


def _context(owner):
    return RequestContext(owner, "request-target-role", "trace-target-role")


@pytest.mark.asyncio
async def test_target_role_provider_prefers_saved_role_over_experience() -> None:
    owner = uuid4()
    role_memory = MemoryRoleReadiness()
    role_readiness = RoleReadinessService(
        unit_of_work=role_memory,
        clock=RoleReadinessFixedClock(),
        identifiers=RoleReadinessUuidFactory(),
        career_snapshots=StaticSnapshotProvider(sample_readiness_snapshot()),
    )
    await role_readiness.save_role(owner, SaveRole(PRODUCT_ROLE_ID), _context(owner))

    career_memory = MemoryCareerRecord()
    career_record = CareerRecordService(
        unit_of_work=career_memory,
        clock=FixedClock(NOW),
        identifiers=UuidFactory(),
        resume_sources=FakeResumeSourceQuery(),
    )
    await career_record.get_or_create_profile(owner, _context(owner))

    provider = CompositeTargetRoleProvider(
        role_readiness=role_readiness, career_record=career_record
    )
    titles = await provider.target_role_titles(owner)

    assert titles != ()
    role_view = await role_readiness.get_role(PRODUCT_ROLE_ID)
    assert titles == (role_view.role.title,)


@pytest.mark.asyncio
async def test_target_role_provider_falls_back_to_current_experience_title() -> None:
    owner = uuid4()
    role_readiness = RoleReadinessService(
        unit_of_work=MemoryRoleReadiness(),
        clock=RoleReadinessFixedClock(),
        identifiers=RoleReadinessUuidFactory(),
        career_snapshots=StaticSnapshotProvider(sample_readiness_snapshot()),
    )

    career_memory = MemoryCareerRecord()
    career_record = CareerRecordService(
        unit_of_work=career_memory,
        clock=FixedClock(NOW),
        identifiers=UuidFactory(),
        resume_sources=FakeResumeSourceQuery(),
    )
    await career_record.get_or_create_profile(owner, _context(owner))
    await career_record.create_entity(
        owner,
        CareerEntityData(
            kind=CareerEntityKind.EXPERIENCE,
            title="Staff Data Engineer",
            organization="Fixture Co",
            employment_type=EmploymentType.FULL_TIME,
            is_current=True,
        ),
        _context(owner),
    )

    provider = CompositeTargetRoleProvider(
        role_readiness=role_readiness, career_record=career_record
    )
    titles = await provider.target_role_titles(owner)

    assert titles == ("Staff Data Engineer",)


@pytest.mark.asyncio
async def test_target_role_provider_prefers_resume_target_role() -> None:
    owner = uuid4()

    class ResumeSource:
        async def list_resumes(self, owner_user_id):
            assert owner_user_id == owner
            return SimpleNamespace(
                items=(
                    SimpleNamespace(
                        resume=SimpleNamespace(target_role=None),
                        current_version=SimpleNamespace(target_role="AI Engineer"),
                    ),
                )
            )

    provider = CompositeTargetRoleProvider(
        role_readiness=object(),  # type: ignore[arg-type]
        career_record=object(),  # type: ignore[arg-type]
        resume_builder=ResumeSource(),  # type: ignore[arg-type]
    )

    assert await provider.target_role_titles(owner) == ("AI Engineer",)


@pytest.mark.asyncio
async def test_target_role_provider_uses_resume_current_experience_when_target_is_empty() -> None:
    owner = uuid4()

    class ResumeSource:
        async def list_resumes(self, owner_user_id):
            assert owner_user_id == owner
            return SimpleNamespace(
                items=(
                    SimpleNamespace(
                        resume=SimpleNamespace(target_role=None),
                        current_version=SimpleNamespace(
                            target_role=None,
                            entities=(
                                SimpleNamespace(
                                    kind="experience",
                                    is_current=True,
                                    display_title="AI Engineer",
                                    official_title="Machine Learning Engineer",
                                    title="Engineer",
                                ),
                            ),
                        ),
                    ),
                )
            )

    provider = CompositeTargetRoleProvider(
        role_readiness=object(),  # type: ignore[arg-type]
        career_record=object(),  # type: ignore[arg-type]
        resume_builder=ResumeSource(),  # type: ignore[arg-type]
    )

    assert await provider.target_role_titles(owner) == ("AI Engineer",)


@pytest.mark.asyncio
async def test_target_role_provider_prefers_career_profile_target_role() -> None:
    owner = uuid4()

    class IdentitySource:
        async def get_target_role_preference(self, owner_user_id):
            assert owner_user_id == owner
            return "Software Engineer"

    provider = CompositeTargetRoleProvider(
        role_readiness=object(),  # type: ignore[arg-type]
        career_record=object(),  # type: ignore[arg-type]
        identity=IdentitySource(),  # type: ignore[arg-type]
    )

    assert await provider.target_role_titles(owner) == ("Software Engineer",)
