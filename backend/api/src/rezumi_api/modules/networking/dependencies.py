"""FastAPI dependencies for the authenticated Networking CRM boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.networking.application import NetworkingService, RequestContext
from rezumi.modules.networking.domain import NetworkingUnavailable

from rezumi_api.modules.identity.dependencies import current_principal


def networking_service(request: Request) -> NetworkingService:
    service = getattr(request.app.state, "networking_service", None)
    if service is None:
        raise NetworkingUnavailable
    return cast(NetworkingService, service)


def networking_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
