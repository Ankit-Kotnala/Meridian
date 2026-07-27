"""FastAPI dependencies for the authenticated Change Studio boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.change_studio.application import ChangeStudioService, RequestContext
from careeros.modules.change_studio.domain import ChangeStudioUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.modules.identity.dependencies import current_principal


def change_studio_service(request: Request) -> ChangeStudioService:
    service = getattr(request.app.state, "change_studio_service", None)
    if service is None:
        raise ChangeStudioUnavailable
    return cast(ChangeStudioService, service)


def change_studio_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
