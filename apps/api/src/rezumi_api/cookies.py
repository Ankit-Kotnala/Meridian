"""Central cookie policy for API-owned opaque browser sessions."""

from fastapi import Response
from rezumi.modules.identity.application.models import IssuedSession

from rezumi_api.config import Settings
from rezumi_api.modules.identity.dependencies import CSRF_COOKIE, REFRESH_COOKIE, SESSION_COOKIE

OAUTH_STATE_COOKIE = "rezumi_oauth_state"
OAUTH_CALLBACK_PATH = "/api/v1/auth/google/callback"


def set_pre_auth_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=settings.session_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def set_session_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issued.access_token,
        max_age=settings.session_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=settings.refresh_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        issued.csrf_token,
        max_age=settings.refresh_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name, http_only in (
        (SESSION_COOKIE, True),
        (REFRESH_COOKIE, True),
        (CSRF_COOKIE, False),
    ):
        response.delete_cookie(
            name,
            secure=settings.cookie_secure,
            httponly=http_only,
            samesite="lax",
            path="/",
        )


def set_oauth_state_cookie(response: Response, state: str, settings: Settings) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=settings.oauth_flow_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path=OAUTH_CALLBACK_PATH,
    )


def clear_oauth_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path=OAUTH_CALLBACK_PATH,
    )
