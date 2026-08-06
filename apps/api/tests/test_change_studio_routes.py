"""Authenticated Phase 6 HTTP workflow and ownership contract tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import uuid4

from fastapi.testclient import TestClient
from rezumi.modules.change_studio.application import ChangeStudioService
from rezumi.modules.change_studio.infrastructure import DeterministicSuggestionProvider
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from rezumi.modules.identity.domain.errors import AuthenticationRequired

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.constants import SCORING_DISCLAIMER
from rezumi_api.main import create_app

_BACKEND_TEST_SUPPORT = Path(__file__).resolve().parents[3] / "packages/backend/tests"
sys.path.insert(0, str(_BACKEND_TEST_SUPPORT))
from change_studio_memory import (  # noqa: E402
    ANALYSIS_ID,
    OWNER_ID,
    FixedClock,
    MemoryChangeStudio,
    StaticEvidenceProvider,
    StaticJobAnalysisProvider,
    UuidFactory,
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
    state = MemoryChangeStudio()
    change_studio = ChangeStudioService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        provider=DeterministicSuggestionProvider(),
        evidence=StaticEvidenceProvider(),
        job_matches=StaticJobAnalysisProvider(),
    )
    return identity, change_studio


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
    change_studio: ChangeStudioService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            change_studio=change_studio,
        )
    )
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def test_change_studio_primary_workflow_is_authenticated_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = OWNER_ID
    other_id = uuid4()
    identity, change_studio = _services(owner_id)

    with _authenticated_client(settings, fake_database, identity, change_studio) as client:
        created = client.post(
            "/api/v1/change-sets",
            json={
                "analysisId": str(ANALYSIS_ID),
                "targetKind": "tailored_resume_bullet",
                "tone": "direct",
                "length": "standard",
                "maxOperations": 5,
            },
            headers=_write_headers(idempotency="api-change-create-key"),
        )
        assert created.status_code == 201
        assert created.headers["Cache-Control"] == "no-store"
        assert created.headers["ETag"] == '"1"'
        body = created.json()
        assert body["scoringDisclaimer"] == SCORING_DISCLAIMER
        assert body["operations"][0]["groundingStatus"] == "grounded"
        assert body["operations"][0]["requiresConfirmation"] is True
        claim = body["operations"][0]["claims"][0]
        assert claim["evidenceTitle"]
        assert claim["evidenceRevisionId"]
        assert claim["evidenceRevisionNumber"] > 0
        assert len(claim["evidenceStatementSha256"]) == 64
        assert body["questions"][0]["status"] == "open"

        ungrounded = client.post(
            f"/api/v1/change-sets/{body['id']}/operations/{body['operations'][0]['id']}/edit",
            json={"afterText": "Invented an unsupported billing ownership claim."},
            headers=_write_headers(version=body["version"], idempotency="api-change-edit-key"),
        )
        assert ungrounded.status_code == 422
        assert ungrounded.json()["code"] == "grounding_failed"

        accepted = client.post(
            f"/api/v1/change-sets/{body['id']}/operations/{body['operations'][0]['id']}/accept",
            headers=_write_headers(version=body["version"], idempotency="api-change-accept-key"),
        )
        assert accepted.status_code == 200
        accepted_body = accepted.json()
        assert accepted_body["version"] == 2
        assert accepted_body["operations"][0]["status"] == "accepted"
        assert accepted_body["currentVersion"]["content"]

        undone = client.post(
            f"/api/v1/change-sets/{body['id']}/undo",
            headers=_write_headers(
                version=accepted_body["version"],
                idempotency="api-change-undo-key",
            ),
        )
        assert undone.status_code == 200
        undone_body = undone.json()
        assert undone_body["currentVersion"]["content"] == ""

        answered = client.post(
            f"/api/v1/clarifications/{body['questions'][0]['id']}/answer",
            json={"answerText": "I do not have eligible evidence for billing systems yet."},
            headers=_write_headers(
                version=undone_body["version"],
                idempotency="api-change-answer-key",
            ),
        )
        assert answered.status_code == 200
        assert answered.json()["questions"][0]["status"] == "answered"

        fetched = client.get(f"/api/v1/change-sets/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.headers["Cache-Control"] == "no-store"

        identity.authenticate.return_value = _principal(other_id)
        hidden = client.get(f"/api/v1/change-sets/{body['id']}")
        assert hidden.status_code == 404


def test_change_studio_mutation_requires_authenticated_session_and_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, change_studio = _services(owner_id)
    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            change_studio=change_studio,
        )
    ) as client:
        response = client.post(
            "/api/v1/change-sets",
            json={"analysisId": str(ANALYSIS_ID)},
            headers=_write_headers(idempotency="api-change-rejected"),
        )
    assert response.status_code == 401
