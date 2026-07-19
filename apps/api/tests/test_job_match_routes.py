"""Authenticated Phase 5 HTTP workflow and ownership contract tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.domain.errors import AuthenticationRequired
from careeros.modules.job_match.application import JobMatchService
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.constants import SCORING_DISCLAIMER
from careeros_api.main import create_app
from conftest import FakeDatabase

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
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
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
