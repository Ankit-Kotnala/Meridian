"""FastAPI dependencies for protected administration."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.administration.application import AdministrationService, RequestContext
from careeros.modules.administration.domain import AdministrationUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.modules.identity.dependencies import current_principal


def administration_service(request: Request) -> AdministrationService:
    service = getattr(request.app.state, "administration_service", None)
    if service is None:
        raise AdministrationUnavailable("administration services are unavailable")
    return cast(AdministrationService, service)


def administration_request_context(
    request: Request,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
