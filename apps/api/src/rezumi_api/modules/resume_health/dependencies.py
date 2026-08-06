"""Cookie, ownership, and mutation dependencies for Resume Health routes."""

import secrets
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Cookie, Depends, Header, Request, Response
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.identity.domain.errors import CsrfRejected, ResourceNotFound

from rezumi_api.config import Settings
from rezumi_api.modules.identity.dependencies import (
    current_principal,
    require_allowed_origin,
    secrets_equal,
)

GUEST_CAPABILITY_COOKIE = "rezumi_guest_capability"
GUEST_CSRF_COOKIE = "rezumi_guest_csrf"
GUEST_CSRF_HEADER = "X-Guest-CSRF"


@dataclass(frozen=True, slots=True)
class GuestCredentials:
    capability: str


def guest_credentials(
    capability: Annotated[str | None, Cookie(alias=GUEST_CAPABILITY_COOKIE)] = None,
) -> GuestCredentials:
    if capability is None or not 32 <= len(capability) <= 512:
        raise ResourceNotFound
    return GuestCredentials(capability=capability)


def require_guest_csrf(
    request: Request,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    csrf_cookie: Annotated[str | None, Cookie(alias=GUEST_CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias=GUEST_CSRF_HEADER)] = None,
) -> GuestCredentials:
    require_allowed_origin(request)
    if csrf_cookie is None or csrf_header is None or not secrets_equal(csrf_cookie, csrf_header):
        raise CsrfRejected
    return credentials


def account_principal(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> AuthenticatedPrincipal:
    return principal


def set_guest_cookies(
    response: Response,
    *,
    capability: str,
    csrf_token: str,
    max_age_seconds: int,
    settings: Settings,
) -> None:
    response.set_cookie(
        GUEST_CAPABILITY_COOKIE,
        capability,
        max_age=max_age_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/api/v1/guest",
    )
    response.set_cookie(
        GUEST_CSRF_COOKIE,
        csrf_token,
        max_age=max_age_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_guest_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        GUEST_CAPABILITY_COOKIE,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/api/v1/guest",
    )
    response.delete_cookie(
        GUEST_CSRF_COOKIE,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def issue_guest_csrf() -> str:
    return secrets.token_urlsafe(32)


def settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)
