"""FastAPI dependencies for identity, ownership, origin, and CSRF enforcement."""

import re
from typing import Annotated, cast

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.models import RequestContext
from careeros.modules.identity.application.privacy_service import AccountPrivacyService
from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.identity.domain.errors import (
    AuthenticationRequired,
    CsrfRejected,
    IdentityUnavailable,
)
from fastapi import Cookie, Depends, Header, Request

from careeros_api.client_signal import verified_client_source_key
from careeros_api.config import Settings

SESSION_COOKIE = "careeros_session"
REFRESH_COOKIE = "careeros_refresh"
CSRF_COOKIE = "careeros_csrf"
CSRF_HEADER = "X-CSRF-Token"

_SAFE_CONTEXT = re.compile(r"[^A-Za-z0-9 ._/-]")


def identity_service(request: Request) -> IdentityService:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise IdentityUnavailable
    return cast(IdentityService, service)


def account_privacy_service(request: Request) -> AccountPrivacyService:
    service = getattr(request.app.state, "account_privacy_service", None)
    if service is None:
        # Create on the fly using identity uow factory
        id_svc = identity_service(request)
        uow_factory = getattr(id_svc, "_uow_factory", None)
        if uow_factory is None:
            raise IdentityUnavailable
        service = AccountPrivacyService(uow_factory)
    return cast(AccountPrivacyService, service)


def request_context(request: Request) -> RequestContext:
    user_agent = request.headers.get("user-agent", "")
    return RequestContext(
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
        device_label=_device_label(user_agent),
        source_key=verified_client_source_key(request),
    )


async def current_principal(
    service: Annotated[IdentityService, Depends(identity_service)],
    access_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthenticatedPrincipal:
    return await service.authenticate(access_cookie)


async def optional_principal(
    service: Annotated[IdentityService, Depends(identity_service)],
    access_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthenticatedPrincipal | None:
    try:
        return await service.authenticate(access_cookie)
    except AuthenticationRequired:
        return None


def require_allowed_origin(request: Request) -> None:
    settings = cast(Settings, request.app.state.settings)
    origin = request.headers.get("origin")
    if origin is None or origin.rstrip("/") not in settings.allowed_origins:
        raise CsrfRejected


def require_pre_auth_csrf(
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    require_allowed_origin(request)
    if csrf_cookie is None or csrf_header is None or not secrets_equal(csrf_cookie, csrf_header):
        raise CsrfRejected
    service.validate_pre_auth_csrf(csrf_cookie)


async def require_authenticated_csrf(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IdentityService, Depends(identity_service)],
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> AuthenticatedPrincipal:
    require_allowed_origin(request)
    if csrf_cookie is None or csrf_header is None or not secrets_equal(csrf_cookie, csrf_header):
        raise CsrfRejected
    await service.verify_csrf(principal, csrf_cookie)
    return principal


def secrets_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _device_label(user_agent: str) -> str:
    lower = user_agent.casefold()
    if "edg/" in lower:
        browser = "Edge"
    elif "firefox/" in lower:
        browser = "Firefox"
    elif "chrome/" in lower:
        browser = "Chrome"
    elif "safari/" in lower:
        browser = "Safari"
    else:
        browser = "Browser"
    if "android" in lower:
        platform = "Android"
    elif "iphone" in lower or "ipad" in lower:
        platform = "iOS"
    elif "windows" in lower:
        platform = "Windows"
    elif "mac os" in lower or "macintosh" in lower:
        platform = "macOS"
    elif "linux" in lower:
        platform = "Linux"
    else:
        platform = "device"
    return _SAFE_CONTEXT.sub("", f"{browser} on {platform}")[:120]
