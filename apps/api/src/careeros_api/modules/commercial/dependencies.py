"""FastAPI dependencies for the commercial boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.commercial.application import CommercialService, RequestContext
from careeros.modules.commercial.domain import CommercialUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.modules.identity.dependencies import current_principal


def commercial_service(request: Request) -> CommercialService:
    service = getattr(request.app.state, "commercial_service", None)
    if service is None:
        raise CommercialUnavailable("commercial services are unavailable")
    return cast(CommercialService, service)


def commercial_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )


def commercial_webhook_context(request: Request) -> RequestContext:
    return RequestContext(
        actor_user_id=None,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
