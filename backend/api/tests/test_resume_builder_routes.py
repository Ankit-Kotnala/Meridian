"""Authenticated Phase 7 HTTP workflow and ownership contract tests."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from rezumi.modules.identity.domain.errors import AuthenticationRequired
from rezumi.modules.resume_builder.application import (
    ResumeBuilderPolicy,
    ResumeBuilderService,
    ResumeExportProcessor,
)

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.main import create_app

_BACKEND_TEST_SUPPORT = Path(__file__).resolve().parents[3] / "backend/core/tests"
sys.path.insert(0, str(_BACKEND_TEST_SUPPORT))
from resume_builder_memory import (  # noqa: E402
    OWNER_ID,
    FixedClock,
    MemoryResumeBuilder,
    MemoryStorage,
    PlainTextExtractor,
    StaticResumeSourceProvider,
    TextOnlyRenderer,
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


def _services(owner_id, *, renderer: TextOnlyRenderer | None = None):
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    resume_builder = ResumeBuilderService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
        policy=ResumeBuilderPolicy(),
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        renderer=renderer or TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    return identity, resume_builder, processor


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
    resume_builder: ResumeBuilderService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            resume_builder=resume_builder,
        )
    )
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def test_resume_builder_primary_workflow_is_authenticated_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    identity, resume_builder, processor = _services(OWNER_ID)
    with _authenticated_client(settings, fake_database, identity, resume_builder) as client:
        empty = client.get("/api/v1/resumes")
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        created = client.post(
            "/api/v1/resumes",
            json={
                "title": "API Resume",
                "targetRole": "Senior Product Manager",
                "template": "standard_professional",
            },
            headers=_write_headers(idempotency="api-resume-create"),
        )
        assert created.status_code == 201
        assert created.headers["Cache-Control"] == "no-store"
        assert created.headers["ETag"] == '"1"'
        body = created.json()
        assert body["currentVersion"]["sections"][0]["items"][0]["evidenceIds"]
        assert body["layout"]["pageLimit"] == 1
        assert body["currentVersion"]["personalFacts"][0]["kind"] == "name"

        options = client.get(f"/api/v1/resumes/{body['id']}/source-options")
        assert options.status_code == 200
        assert options.json()["personalFacts"][0]["value"] == "Taylor Morgan"
        assert options.json()["bullets"][0]["evidenceReferences"]

        updated = client.patch(
            f"/api/v1/resumes/{body['id']}",
            json={
                "template": "compact_technical",
                "title": "API Resume v2",
                "targetRole": None,
                "layout": {
                    "pageSize": "a4",
                    "pageLimit": 2,
                    "fontFamily": "serif",
                    "fontSizePt": 11,
                    "lineSpacing": "relaxed",
                    "margins": "wide",
                },
            },
            headers=_write_headers(version=body["version"], idempotency="api-resume-update"),
        )
        assert updated.status_code == 200
        updated_body = updated.json()
        assert updated_body["version"] == 2
        assert updated_body["currentVersion"]["id"] != body["currentVersion"]["id"]
        assert updated_body["targetRole"] is None
        assert updated_body["layout"]["pageSize"] == "a4"

        versions = client.get(f"/api/v1/resumes/{body['id']}/versions")
        assert versions.status_code == 200
        assert len(versions.json()["items"]) == 2

        checkpoint = client.post(
            f"/api/v1/resumes/{body['id']}/versions",
            headers=_write_headers(
                version=updated_body["version"],
                idempotency="api-resume-version",
            ),
        )
        assert checkpoint.status_code == 201

        exported = client.post(
            f"/api/v1/resume-versions/{checkpoint.json()['id']}/export",
            json={"format": "text"},
            headers=_write_headers(idempotency="api-resume-export"),
        )
        assert exported.status_code == 202
        export_body = exported.json()
        assert export_body["export"]["status"] == "pending"
        assert export_body["verification"] is None
        outcome = asyncio.run(
            processor.process(UUID(export_body["export"]["id"]), "api-worker-token")
        )
        assert outcome.status.value == "verified"

        intent = client.post(
            f"/api/v1/exports/{export_body['export']['id']}/download-intent",
            headers=_write_headers(idempotency="api-resume-download"),
        )
        assert intent.status_code == 200
        assert intent.json()["url"].startswith("https://downloads.invalid/")

        deletion = client.delete(
            f"/api/v1/exports/{export_body['export']['id']}",
            headers=_write_headers(idempotency="api-resume-delete"),
        )
        assert deletion.status_code == 202
        assert deletion.json()["export"]["status"] == "deletion_pending"
        assert deletion.json()["export"]["cleanupAttempts"] == 0
        assert deletion.json()["export"]["deletedAt"] is None

        identity.authenticate.return_value = _principal(uuid4())
        hidden = client.get(f"/api/v1/resumes/{body['id']}")
        assert hidden.status_code == 404


def test_resume_builder_blocks_download_when_verification_fails(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    identity, resume_builder, processor = _services(
        OWNER_ID, renderer=TextOnlyRenderer(omit_expected=True)
    )
    with _authenticated_client(settings, fake_database, identity, resume_builder) as client:
        created = client.post(
            "/api/v1/resumes",
            json={"title": "Blocked API Resume", "template": "executive"},
            headers=_write_headers(idempotency="api-blocked-create"),
        )
        assert created.status_code == 201
        exported = client.post(
            f"/api/v1/resume-versions/{created.json()['currentVersion']['id']}/export",
            json={"format": "text"},
            headers=_write_headers(idempotency="api-blocked-export"),
        )
        assert exported.status_code == 202
        assert exported.json()["export"]["status"] == "pending"
        outcome = asyncio.run(
            processor.process(UUID(exported.json()["export"]["id"]), "api-worker-token")
        )
        assert outcome.status.value == "blocked"
        blocked = client.post(
            f"/api/v1/exports/{exported.json()['export']['id']}/download-intent",
            headers=_write_headers(idempotency="api-blocked-download"),
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "resume_export_blocked"


def test_resume_builder_mutation_requires_authenticated_session_and_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    identity, resume_builder, _processor = _services(OWNER_ID)
    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            resume_builder=resume_builder,
        )
    ) as client:
        response = client.post(
            "/api/v1/resumes",
            json={"title": "Rejected", "template": "graduate"},
            headers=_write_headers(idempotency="api-rejected"),
        )
    assert response.status_code == 401
