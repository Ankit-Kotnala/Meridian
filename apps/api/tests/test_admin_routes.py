"""HTTP contracts for protected platform administration."""

from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.modules.administration.application import (
    AdministrationService,
    AdminSystemSnapshot,
    AdminSystemTotals,
    RetryResult,
)
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_REASON = "Approved fictional administration API contract verification."


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime.now(UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _services(
    principal: AuthenticatedPrincipal,
) -> tuple[IdentityService, AdministrationService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = principal
    identity.verify_csrf.return_value = None
    administration = create_autospec(AdministrationService, instance=True)
    return identity, administration


def test_admin_system_is_private_and_requires_authenticated_operator_service(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    principal = _principal()
    identity, administration = _services(principal)
    now = datetime.now(UTC)
    administration.system_snapshot.return_value = AdminSystemSnapshot(  # type: ignore[attr-defined]
        generated_at=now,
        totals=AdminSystemTotals(1, 0, 0, 0, 0, 0, 0, 0),
        audit_chain_valid=True,
    )
    app = create_app(
        settings,
        database=fake_database,
        identity=identity,
        administration=administration,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/system",
            headers={
                "cookie": "careeros_session=fake-session",
                "X-Admin-Reason": _REASON,
            },
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["auditChainValid"] is True
    administration.system_snapshot.assert_awaited_once()  # type: ignore[attr-defined]


def test_admin_retry_requires_csrf_reason_and_idempotency(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    principal = _principal()
    identity, administration = _services(principal)
    target_id = uuid4()
    administration.retry_dead_letter.return_value = RetryResult(  # type: ignore[attr-defined]
        "account_privacy", target_id, "retry_wait", False
    )
    app = create_app(
        settings,
        database=fake_database,
        identity=identity,
        administration=administration,
    )

    with TestClient(app) as client:
        missing_csrf = client.post(
            f"/api/v1/admin/dead-letters/account_privacy/{target_id}/retry",
            headers={
                "cookie": "careeros_session=fake-session",
                "Origin": _ORIGIN,
                "Idempotency-Key": "fictional-admin-retry",
            },
            json={"reason": _REASON},
        )
        accepted = client.post(
            f"/api/v1/admin/dead-letters/account_privacy/{target_id}/retry",
            headers={
                "cookie": ("careeros_session=fake-session; careeros_csrf=fictional-admin-csrf"),
                "Origin": _ORIGIN,
                "X-CSRF-Token": "fictional-admin-csrf",
                "Idempotency-Key": "fictional-admin-retry",
            },
            json={"reason": _REASON},
        )

    assert missing_csrf.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json() == {
        "kind": "account_privacy",
        "id": str(target_id),
        "status": "retry_wait",
        "replayed": False,
    }
