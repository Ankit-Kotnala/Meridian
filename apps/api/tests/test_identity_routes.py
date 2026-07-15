"""HTTP adapter tests for CSRF, cookies, validation, ownership calls, and safe errors."""

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.models import (
    CurrentUser,
    IssuedSession,
    OAuthCompletion,
    OAuthStart,
)
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.domain.errors import AuthenticationRequired
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_PASSWORD = "a long test-only password"  # noqa: S105


def _service():
    service = create_autospec(IdentityService, instance=True)
    service.issue_pre_auth_csrf.return_value = (
        "00000000-0000-4000-8000-000000000001.test-csrf-secret"
    )
    return service


def _user(*, version: int = 1, target_role: str | None = None) -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        email="alex@example.com",
        display_name="Alex Example",
        email_verified=True,
        locale="en",
        timezone="UTC",
        target_role=target_role,
        preferred_location=None,
        work_model=None,
        seniority=None,
        industry=None,
        language="en",
        writing_style="balanced",
        version=version,
    )


def _principal(user_id=None) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id or uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["csrfToken"]


def test_registration_requires_exact_origin_and_double_submit_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        csrf = _csrf(client)
        payload = {
            "email": "alex@example.com",
            "password": _PASSWORD,
            "displayName": "Alex Example",
        }
        rejected = client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        accepted = client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )

    assert rejected.status_code == 403
    assert rejected.headers["content-type"].startswith("application/problem+json")
    assert accepted.status_code == 202
    service.validate_pre_auth_csrf.assert_called_once_with(csrf)
    service.register.assert_awaited_once()


def test_login_sets_host_only_http_only_rotating_cookies(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    principal = _principal()
    user = _user()
    principal = _principal(user.id)
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    service.login.return_value = IssuedSession(
        principal=principal,
        access_token="access-token",  # noqa: S106
        refresh_token="refresh-token",  # noqa: S106
        csrf_token="session-csrf-token",  # noqa: S106
        expires_at=now + timedelta(days=30),
    )
    service.get_current_user.return_value = user

    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        csrf = _csrf(client)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": _PASSWORD},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)
    cookies = response.headers.get_list("set-cookie")
    assert any("careeros_session=access-token" in item and "HttpOnly" in item for item in cookies)
    assert any("careeros_refresh=refresh-token" in item and "HttpOnly" in item for item in cookies)
    assert any(
        "careeros_csrf=session-csrf-token" in item and "HttpOnly" not in item for item in cookies
    )
    assert all("Domain=" not in item for item in cookies)
    assert all("SameSite=lax" in item for item in cookies)


def test_authenticated_profile_update_passes_owner_principal_and_version(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    before = _user()
    principal = _principal(before.id)
    service.authenticate.return_value = principal
    service.get_current_user.return_value = before
    service.update_current_user.return_value = CurrentUser(
        id=before.id,
        email=before.email,
        display_name=before.display_name,
        email_verified=True,
        locale="en",
        timezone="UTC",
        target_role="Product Manager",
        preferred_location=None,
        work_model=None,
        seniority=None,
        industry=None,
        language="en",
        writing_style="balanced",
        version=2,
    )

    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.patch(
            "/api/v1/me",
            json={"targetRole": "Product Manager"},
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "If-Match": '"1"',
            },
        )

    assert response.status_code == 200
    assert response.headers["etag"] == '"2"'
    assert response.json()["targetRole"] == "Product Manager"
    service.verify_csrf.assert_awaited_once_with(principal, "opaque-csrf")
    call = service.update_current_user.await_args
    assert call.args[0] == principal
    assert call.kwargs["expected_version"] == 1
    assert call.kwargs["updates"] == {"target_role": "Product Manager"}


def test_authentication_failure_clears_stale_browser_credentials(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    service.authenticate.side_effect = AuthenticationRequired

    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        client.cookies.set("careeros_session", "stale")
        client.cookies.set("careeros_refresh", "stale")
        client.cookies.set("careeros_csrf", "stale")
        response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    cookies = response.headers.get_list("set-cookie")
    assert {item.split("=", 1)[0] for item in cookies} == {
        "careeros_session",
        "careeros_refresh",
        "careeros_csrf",
    }
    assert all("Max-Age=0" in item for item in cookies)


def test_validation_problem_never_echoes_submitted_values(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        csrf = _csrf(client)
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "private-invalid-address",
                "password": "short-secret",
                "displayName": "Alex",
                "unexpected": "private-payload-value",
            },
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "private-invalid-address" not in response.text
    assert "short-secret" not in response.text
    assert "private-payload-value" not in response.text


def test_cors_preflight_allows_only_configured_origin(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        allowed = client.options(
            "/api/v1/me",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "X-CSRF-Token,If-Match",
            },
        )
        denied = client.options(
            "/api/v1/me",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "PATCH",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == _ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_google_oauth_state_is_bound_to_an_http_only_callback_cookie(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    service.authenticate.side_effect = AuthenticationRequired
    state = "test-state-that-is-long-and-unpredictable"
    service.start_google_oauth.return_value = OAuthStart(
        authorization_url=f"https://accounts.example/authorize?state={state}",
        state=state,
    )
    principal = _principal()
    issued = IssuedSession(
        principal=principal,
        access_token="google-access",  # noqa: S106
        refresh_token="google-refresh",  # noqa: S106
        csrf_token="google-csrf",  # noqa: S106
        expires_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )
    service.complete_google_oauth.return_value = OAuthCompletion(
        session=issued,
        return_to="/dashboard",
    )

    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        started = client.get(
            "/api/v1/auth/google/start?returnTo=/dashboard",
            follow_redirects=False,
        )
        state_cookie = next(
            item
            for item in started.headers.get_list("set-cookie")
            if item.startswith("careeros_oauth_state=")
        )
        assert "HttpOnly" in state_cookie
        assert "Path=/api/v1/auth/google/callback" in state_cookie
        assert "SameSite=lax" in state_cookie

        completed = client.get(
            f"/api/v1/auth/google/callback?code=test-code&state={state}",
            follow_redirects=False,
        )

    assert started.status_code == 302
    assert completed.status_code == 302
    assert completed.headers["location"] == "/dashboard"
    service.complete_google_oauth.assert_awaited_once()
    assert any(
        item.startswith("careeros_oauth_state=") and "Max-Age=0" in item
        for item in completed.headers.get_list("set-cookie")
    )


def test_google_callback_rejects_state_not_bound_to_the_browser(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    service = _service()
    service.authenticate.side_effect = AuthenticationRequired

    with TestClient(create_app(settings, database=fake_database, identity=service)) as client:
        response = client.get(
            "/api/v1/auth/google/callback?code=test-code&state=unbound-state-that-is-long-enough",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert response.json()["code"] == "oauth_flow_rejected"
    service.complete_google_oauth.assert_not_awaited()
