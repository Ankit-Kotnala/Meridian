"""HTTP contracts for durable account export and deletion operations."""

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from careeros.modules.identity.application import (
    AccountOperationsService,
    AccountOperationView,
    IdentityService,
)
from careeros.modules.identity.domain import (
    AccountOperation,
    AccountOperationKind,
    AccountOperationStatus,
    AuthenticatedPrincipal,
    AuthMethod,
)
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_CSRF = "privacy-csrf-token"
_IDEMPOTENCY_KEY = "privacy-request-0001"
_OPERATION_TOKEN = f"00000000-0000-4000-8000-000000000001.{('a' * 43)}"


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime.now(UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _operation(
    operation_id: UUID,
    user_id: UUID,
    *,
    kind: AccountOperationKind,
    succeeded: bool = False,
) -> AccountOperation:
    now = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    return AccountOperation(
        id=operation_id,
        user_id=user_id,
        user_fingerprint="1" * 64,
        capability_hash="2" * 64,
        kind=kind,
        status=(AccountOperationStatus.SUCCEEDED if succeeded else AccountOperationStatus.QUEUED),
        idempotency_key=_IDEMPOTENCY_KEY,
        request_id="privacy-request-id",
        trace_id="3" * 32,
        attempts=0,
        max_attempts=5,
        next_attempt_at=now,
        artifact_object_key=("account-exports/test.zip" if succeeded else None),
        artifact_sha256=("4" * 64 if succeeded else None),
        artifact_size_bytes=(4_096 if succeeded else None),
        artifact_expires_at=(now + timedelta(hours=24) if succeeded else None),
        completed_at=(now if succeeded else None),
        requested_at=now,
        updated_at=now,
    )


def _services(
    principal: AuthenticatedPrincipal,
) -> tuple[IdentityService, AccountOperationsService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = principal
    operations = create_autospec(AccountOperationsService, instance=True)
    return identity, operations


def test_export_request_status_and_download_are_capability_scoped(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    principal = _principal()
    identity, operations = _services(principal)
    operation_id = uuid4()
    queued = _operation(
        operation_id,
        principal.user_id,
        kind=AccountOperationKind.EXPORT,
    )
    succeeded = _operation(
        operation_id,
        principal.user_id,
        kind=AccountOperationKind.EXPORT,
        succeeded=True,
    )
    operations.request_export.return_value = AccountOperationView(
        queued,
        _OPERATION_TOKEN,
    )
    operations.get_status.return_value = AccountOperationView(succeeded)
    operations.create_download_url.return_value = "https://objects.example.test/private-export"

    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            account_operations=operations,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", _CSRF)
        created = client.post(
            "/api/v1/account-exports",
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": _CSRF,
                "Idempotency-Key": _IDEMPOTENCY_KEY,
            },
        )
        status_response = client.get(
            f"/api/v1/account-operations/{operation_id}",
            headers={"X-Account-Operation-Token": _OPERATION_TOKEN},
        )
        download = client.get(
            f"/api/v1/account-operations/{operation_id}/download",
            headers={"X-Account-Operation-Token": _OPERATION_TOKEN},
        )

    assert created.status_code == 202
    assert created.headers["cache-control"] == "no-store"
    assert created.json()["operationToken"] == _OPERATION_TOKEN
    assert created.json()["status"] == "queued"
    assert status_response.status_code == 200
    assert status_response.headers["cache-control"] == "no-store"
    assert status_response.json()["artifactSha256"] == "4" * 64
    assert download.status_code == 200
    assert download.headers["cache-control"] == "no-store"
    assert download.json() == {
        "downloadUrl": "https://objects.example.test/private-export",
        "expiresInSeconds": 120,
    }
    operations.request_export.assert_awaited_once()
    assert operations.request_export.await_args.kwargs["idempotency_key"] == (_IDEMPOTENCY_KEY)
    context = operations.request_export.await_args.kwargs["context"]
    assert context.request_id
    assert len(context.trace_id) == 32
    operations.get_status.assert_awaited_once_with(operation_id, _OPERATION_TOKEN)
    operations.create_download_url.assert_awaited_once_with(
        operation_id,
        _OPERATION_TOKEN,
        expires_in_seconds=120,
    )


def test_deletion_request_revokes_browser_cookies_immediately(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    principal = _principal()
    identity, operations = _services(principal)
    operation_id = uuid4()
    operations.request_deletion.return_value = AccountOperationView(
        _operation(
            operation_id,
            principal.user_id,
            kind=AccountOperationKind.DELETION,
        ),
        _OPERATION_TOKEN,
    )

    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            account_operations=operations,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_refresh", "opaque-refresh")
        client.cookies.set("careeros_csrf", _CSRF)
        response = client.post(
            "/api/v1/account-deletions",
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": _CSRF,
                "Idempotency-Key": _IDEMPOTENCY_KEY,
            },
        )

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["kind"] == "deletion"
    assert sum("Max-Age=0" in item for item in response.headers.get_list("set-cookie")) == 3
    operations.request_deletion.assert_awaited_once()
