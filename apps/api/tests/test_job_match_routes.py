"""Authenticated Phase 5 HTTP workflow and ownership contract tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import uuid4

from fastapi.testclient import TestClient
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from rezumi.modules.identity.domain.errors import AuthenticationRequired
from rezumi.modules.job_match.application import JobMatchService

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.constants import SCORING_DISCLAIMER
from rezumi_api.main import create_app

_BACKEND_TEST_SUPPORT = Path(__file__).resolve().parents[3] / "packages/backend/tests"
sys.path.insert(0, str(_BACKEND_TEST_SUPPORT))
from job_match_memory import (  # noqa: E402
    FixedClock,
    MemoryJobMatch,
    StaticImporter,
    StaticRoleContextProvider,
    StaticSnapshotProvider,
    UuidFactory,
    sample_job_text,
    sample_snapshot,
)

_ORIGIN = "http://localhost:3000"


def _principal(user_id=None) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id or uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _services(owner_id):
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    state = MemoryJobMatch()
    job_match = JobMatchService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=StaticSnapshotProvider(sample_snapshot()),
        role_context=StaticRoleContextProvider(),
        importer=StaticImporter(),
    )
    return identity, job_match


def _write_headers(*, version: int | None = None, idempotency: str | None = None):
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        **({"If-Match": f'"{version}"'} if version is not None else {}),
        **({"Idempotency-Key": idempotency} if idempotency is not None else {}),
    }


def _authenticated_client(
    settings: Settings,
    fake_database: FakeDatabase,
    identity: IdentityService,
    job_match: JobMatchService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            job_match=job_match,
        )
    )
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def test_job_match_primary_workflow_is_authenticated_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    other_id = uuid4()
    identity, job_match = _services(owner_id)

    with _authenticated_client(settings, fake_database, identity, job_match) as client:
        created = client.post(
            "/api/v1/jobs",
            json={
                "title": "Product Manager",
                "company": "Example Co",
                "location": "Remote",
                "workModel": "remote",
                "employmentType": "full_time",
                "compensation": None,
                "applicationDeadline": None,
                "sourceKind": "paste",
                "sourceUrl": None,
                "sourceText": sample_job_text(),
                "targetRoleId": None,
            },
            headers=_write_headers(idempotency="api-job-create-key"),
        )
        assert created.status_code == 201
        assert created.headers["Cache-Control"] == "no-store"
        job_body = created.json()
        assert job_body["title"] == "Product Manager"
        assert "sourceText" not in job_body
        assert job_body["requirements"]

        analysis = client.post(
            f"/api/v1/jobs/{job_body['id']}/analyze",
            headers=_write_headers(idempotency="api-job-analysis-key"),
        )
        assert analysis.status_code == 201
        analysis_body = analysis.json()
        assert analysis_body["displayScore"] is not None
        assert analysis_body["scoringDisclaimer"] == SCORING_DISCLAIMER
        assert analysis_body["requirements"][0]["evidence"]

        requirements = client.get(f"/api/v1/job-match-analyses/{analysis_body['id']}/requirements")
        assert requirements.status_code == 200
        assert requirements.json()["data"][0]["requirementText"]

        priority = client.post(
            f"/api/v1/jobs/{job_body['id']}/opportunity-priority",
            json={
                "analysisId": analysis_body["id"],
                "userInterest": 5,
                "careerDirectionFit": 4,
                "compensationFit": "unknown",
                "locationFit": "strong",
                "workModelFit": "strong",
                "tailoringEffort": "low",
                "existingContacts": 1,
            },
            headers=_write_headers(idempotency="api-job-priority-key"),
        )
        assert priority.status_code == 201
        assert priority.json()["scoringDisclaimer"] == SCORING_DISCLAIMER

        identity.authenticate.return_value = _principal(other_id)
        hidden = client.get(f"/api/v1/job-match-analyses/{analysis_body['id']}")
        assert hidden.status_code == 404


def test_job_match_mutation_requires_authenticated_session_and_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, job_match = _services(owner_id)
    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            job_match=job_match,
        )
    ) as client:
        response = client.post(
            "/api/v1/jobs",
            json={
                "title": "Product Manager",
                "sourceKind": "paste",
                "sourceText": sample_job_text(),
            },
            headers=_write_headers(idempotency="api-job-rejected"),
        )
    assert response.status_code == 401


class _MemoryJobCatalogStore:
    def __init__(self, listings):
        from datetime import UTC as _UTC
        from datetime import datetime as _datetime

        self._now = _datetime(2026, 8, 23, tzinfo=_UTC)
        self.documents = {(listing.platform, listing.external_id): listing for listing in listings}

    async def ping(self) -> None:
        return None

    async def upsert_listing(self, listing, *, fetched_at) -> None:
        self.documents[(listing.platform, listing.external_id)] = listing

    async def search(self, *, keywords, limit, offset=0):
        if not keywords:
            return tuple(self.documents.values())[offset : offset + limit]
        lowered = {word.casefold() for word in keywords}
        matches = [
            listing
            for listing in self.documents.values()
            if lowered & set(listing.title.casefold().split())
        ]
        return tuple(matches[offset : offset + limit])

    async def get_listing(self, platform: str, external_id: str):
        return self.documents.get((platform, external_id))

    async def dispose(self) -> None:
        return None


def test_job_catalog_search_and_save_is_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
    from rezumi.modules.job_match.application.job_catalog_query import JobCatalogQueryService

    owner_id = uuid4()
    identity, job_match = _services(owner_id)
    listing = CatalogJobListing(
        platform="fake",
        external_id="fake-1",
        title="Software Engineer",
        company="Fixture Co",
        location="Remote",
        remote=True,
        application_url="https://example.test/jobs/fake-1",
        source_text="Build backend services.",
        posted_at=None,
    )
    store = _MemoryJobCatalogStore([listing])

    class _StaticTargetRoles:
        async def target_role_titles(self, owner_user_id):
            return ("Software Engineer",)

    catalog = JobCatalogQueryService(store=store, target_roles=_StaticTargetRoles())

    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            job_match=job_match,
            job_catalog_query=catalog,
        )
    ) as client:
        client.cookies.set("rezumi_session", "opaque-session")
        client.cookies.set("rezumi_csrf", "opaque-csrf")

        search = client.get("/api/v1/job-catalog")
        assert search.status_code == 200
        body = search.json()
        assert body["targetRoleTitles"] == ["Software Engineer"]
        assert len(body["listings"]) == 1
        assert body["listings"][0]["externalId"] == "fake-1"

        saved = client.post(
            "/api/v1/job-catalog/fake/fake-1/save",
            headers=_write_headers(idempotency="unused-but-required-header-not-sent"),
        )
        assert saved.status_code == 201
        assert saved.json()["sourceUrl"] == "https://example.test/jobs/fake-1"

        # Saving the same listing again is idempotent, not duplicated.
        saved_again = client.post("/api/v1/job-catalog/fake/fake-1/save", headers=_write_headers())
        assert saved_again.status_code == 201
        assert saved_again.json()["id"] == saved.json()["id"]

        missing = client.post(
            "/api/v1/job-catalog/fake/does-not-exist/save", headers=_write_headers()
        )
        assert missing.status_code == 404

        browse = client.get("/api/v1/job-catalog/search", params={"limit": 1})
        assert browse.status_code == 200
        browse_body = browse.json()
        assert browse_body["listings"][0]["externalId"] == "fake-1"
        assert browse_body["hasMore"] is False
        assert browse_body["nextOffset"] == 1


def test_job_catalog_role_preferences_round_trip_and_filter_precedence(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
    from rezumi.modules.job_match.application.job_catalog_query import JobCatalogQueryService

    owner_id = uuid4()
    identity, job_match = _services(owner_id)
    suggested = CatalogJobListing(
        platform="fake",
        external_id="suggested-1",
        title="Software Engineer",
        company="Fixture Co",
        location="Remote",
        remote=True,
        application_url=None,
        source_text="Build backend services.",
        posted_at=None,
    )
    selected = CatalogJobListing(
        platform="fake",
        external_id="selected-1",
        title="Product Manager",
        company="Fixture Co",
        location="Remote",
        remote=True,
        application_url=None,
        source_text="Own the roadmap.",
        posted_at=None,
    )
    store = _MemoryJobCatalogStore([suggested, selected])

    class _StaticTargetRoles:
        async def target_role_titles(self, owner_user_id):
            return ("Software Engineer",)

    catalog = JobCatalogQueryService(
        store=store, target_roles=_StaticTargetRoles(), role_preferences=job_match
    )

    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            job_match=job_match,
            job_catalog_query=catalog,
        )
    ) as client:
        client.cookies.set("rezumi_session", "opaque-session")
        client.cookies.set("rezumi_csrf", "opaque-csrf")

        initial = client.get("/api/v1/job-catalog/role-preferences")
        assert initial.status_code == 200
        assert initial.json()["roleTitles"] == []

        default_search = client.get("/api/v1/job-catalog")
        assert default_search.json()["selectedRoleTitles"] == []
        assert default_search.json()["suggestedRoleTitles"] == ["Software Engineer"]

        updated = client.put(
            "/api/v1/job-catalog/role-preferences",
            json={"roleTitles": ["Product Manager"]},
            headers=_write_headers(),
        )
        assert updated.status_code == 200
        assert updated.json()["roleTitles"] == ["Product Manager"]

        filtered_search = client.get("/api/v1/job-catalog")
        body = filtered_search.json()
        assert body["selectedRoleTitles"] == ["Product Manager"]
        assert body["targetRoleTitles"] == ["Product Manager"]
        assert [listing["externalId"] for listing in body["listings"]] == ["selected-1"]
