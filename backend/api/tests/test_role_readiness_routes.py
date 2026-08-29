"""Authenticated Phase 4 HTTP workflow and ownership contract tests."""

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
from rezumi.modules.role_readiness.application import RoleReadinessService

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.constants import SCORING_DISCLAIMER
from rezumi_api.main import create_app

_BACKEND_TEST_SUPPORT = Path(__file__).resolve().parents[3] / "backend/core/tests"
sys.path.insert(0, str(_BACKEND_TEST_SUPPORT))
from role_readiness_memory import (  # noqa: E402
    ENGINEER_ROLE_ID,
    PRODUCT_ROLE_ID,
    FixedClock,
    MemoryRoleReadiness,
    StaticSnapshotProvider,
    UuidFactory,
    sample_readiness_snapshot,
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
    state = MemoryRoleReadiness()
    role_readiness = RoleReadinessService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=StaticSnapshotProvider(sample_readiness_snapshot()),
    )
    return identity, role_readiness


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
    role_readiness: RoleReadinessService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            role_readiness=role_readiness,
        )
    )
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def test_role_readiness_primary_workflow_is_authenticated_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    other_id = uuid4()
    identity, role_readiness = _services(owner_id)

    with _authenticated_client(settings, fake_database, identity, role_readiness) as client:
        roles = client.get("/api/v1/roles?q=product")
        assert roles.status_code == 200
        role = roles.json()["data"][0]
        assert role["id"] == str(PRODUCT_ROLE_ID)
        assert role["competencies"]

        saved = client.post(
            "/api/v1/saved-roles",
            json={"roleId": str(PRODUCT_ROLE_ID), "notes": "Primary target"},
            headers=_write_headers(),
        )
        assert saved.status_code == 201
        assert saved.headers["Cache-Control"] == "no-store"
        assert saved.json()["notes"] == "Primary target"
        saved_role_id = saved.json()["id"]
        saved_version = saved.json()["version"]

        updated = client.patch(
            f"/api/v1/saved-roles/{saved_role_id}",
            json={"notes": "Product transition"},
            headers=_write_headers(version=saved_version),
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == saved_version + 1

        analysis = client.post(
            "/api/v1/role-readiness",
            json={"savedRoleId": saved_role_id},
            headers=_write_headers(idempotency="api-role-readiness-key"),
        )
        assert analysis.status_code == 201
        body = analysis.json()
        assert body["role"]["id"] == str(PRODUCT_ROLE_ID)
        assert body["displayScore"] is not None
        assert body["scoringDisclaimer"] == SCORING_DISCLAIMER
        assert body["competencies"][0]["evidence"]

        history = client.get(f"/api/v1/role-readiness?roleId={PRODUCT_ROLE_ID}")
        assert history.status_code == 200
        assert history.json()["data"][0]["id"] == body["id"]

        comparison = client.get(
            "/api/v1/role-readiness/compare",
            params=[("roleId", str(PRODUCT_ROLE_ID)), ("roleId", str(ENGINEER_ROLE_ID))],
        )
        assert comparison.status_code == 200
        assert len(comparison.json()["entries"]) == 2

        identity.authenticate.return_value = _principal(other_id)
        hidden = client.get(f"/api/v1/role-readiness/{body['id']}")
        assert hidden.status_code == 404


def test_role_readiness_mutation_requires_authenticated_session_and_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, role_readiness = _services(owner_id)
    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            role_readiness=role_readiness,
        )
    ) as client:
        response = client.post(
            "/api/v1/saved-roles",
            json={"roleId": str(PRODUCT_ROLE_ID), "notes": None},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": "opaque-csrf"},
        )
    assert response.status_code == 401
