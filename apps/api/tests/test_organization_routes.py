"""Organization HTTP contract, CSRF, and non-disclosure tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.organizations.application import (
    InvitationView,
    OrganizationService,
    OrganizationView,
)
from careeros.modules.organizations.domain import (
    InvitationStatus,
    Organization,
    OrganizationForbidden,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationMembershipStatus,
    OrganizationRole,
    OrganizationStatus,
)
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_NOW = datetime(2026, 7, 26, 20, tzinfo=UTC)
_ORIGIN = "http://localhost:3000"


def _principal(user_id: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _view(owner_id: UUID) -> OrganizationView:
    organization_id = uuid4()
    return OrganizationView(
        organization=Organization(
            id=organization_id,
            name="Fictional API Organization",
            created_by_user_id=owner_id,
            status=OrganizationStatus.ACTIVE,
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        membership=OrganizationMembership(
            id=uuid4(),
            organization_id=organization_id,
            user_id=owner_id,
            role=OrganizationRole.OWNER,
            status=OrganizationMembershipStatus.ACTIVE,
            version=1,
            accepted_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _client(
    settings: Settings,
    database: FakeDatabase,
    identity: IdentityService,
    organizations: OrganizationService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=database,
            identity=identity,
            organizations=organizations,
        )
    )
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def _write_headers() -> dict[str, str]:
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        "Idempotency-Key": "organization-api-test-key",
    }


def test_organization_create_and_list_contract(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    view = _view(owner_id)
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    service = create_autospec(OrganizationService, instance=True)
    service.create_organization.return_value = view
    service.list_organizations.return_value = (view,)

    with _client(settings, fake_database, identity, service) as client:
        created = client.post(
            "/api/v1/organizations",
            json={"name": "Fictional API Organization"},
            headers=_write_headers(),
        )
        assert created.status_code == 201
        assert created.headers["Cache-Control"] == "no-store"
        assert created.headers["ETag"] == '"1"'
        assert created.json()["role"] == "owner"
        assert "manageOrganization" not in created.json()
        assert "manage_organization" in created.json()["capabilities"]
        assert service.create_organization.await_args.kwargs["idempotency_key"] == (
            "organization-api-test-key"
        )

        listed = client.get("/api/v1/organizations")
        assert listed.status_code == 200
        assert listed.json()["organizations"][0]["id"] == str(view.organization.id)
        service.list_organizations.assert_awaited_once_with(owner_id)


def test_invitation_response_never_discloses_email_or_token(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    view = _view(owner_id)
    invitation = OrganizationInvitation(
        id=uuid4(),
        organization_id=view.organization.id,
        invited_email_normalized="private-coach@example.test",
        invited_email_digest="a" * 64,
        role=OrganizationRole.COACH,
        token_hash=None,
        status=InvitationStatus.PENDING_DELIVERY,
        invited_by_user_id=owner_id,
        expires_at=_NOW + timedelta(days=7),
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    service = create_autospec(OrganizationService, instance=True)
    service.invite_member.return_value = InvitationView(invitation, "queued")

    with _client(settings, fake_database, identity, service) as client:
        response = client.post(
            f"/api/v1/organizations/{view.organization.id}/invitations",
            json={"email": "private-coach@example.test", "role": "coach"},
            headers=_write_headers(),
        )

        assert response.status_code == 202
        assert response.json()["deliveryStatus"] == "queued"
        assert "email" not in response.json()
        assert "token" not in response.json()
        assert "private-coach@example.test" not in response.text


def test_organization_mutations_require_csrf_and_return_safe_role_denial(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    service = create_autospec(OrganizationService, instance=True)
    service.create_organization.side_effect = OrganizationForbidden("private role detail")

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/organizations",
            json={"name": "Fictional API Organization"},
            headers={"Idempotency-Key": "organization-api-test-key"},
        )
        assert missing_csrf.status_code == 403
        service.create_organization.assert_not_awaited()

        denied = client.post(
            "/api/v1/organizations",
            json={"name": "Fictional API Organization"},
            headers=_write_headers(),
        )
        assert denied.status_code == 403
        assert denied.headers["content-type"].startswith("application/problem+json")
        assert denied.json()["code"] == "organization_forbidden"
        assert "private role detail" not in denied.text


def test_organization_openapi_has_explicit_mutation_contracts(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity = create_autospec(IdentityService, instance=True)
    service = create_autospec(OrganizationService, instance=True)

    with _client(settings, fake_database, identity, service) as client:
        schema = client.app.openapi()

    paths = schema["paths"]
    assert paths["/api/v1/organizations"]["post"]["operationId"] == "organizationsCreate"
    assert paths["/api/v1/organizations/{organization_id}/invitations"]["post"]["responses"]["202"][
        "content"
    ]["application/json"]["schema"]
    assert (
        paths["/api/v1/organizations/{organization_id}/grants"]["post"]["operationId"]
        == "organizationGrantsCreate"
    )
