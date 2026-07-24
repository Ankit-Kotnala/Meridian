"""FastAPI dependencies for the authenticated Application Workspace boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.application_workspace.application import (
    ApplicationWorkspaceService,
    RequestContext,
)
from careeros.modules.application_workspace.domain import ApplicationWorkspaceUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.identity_dependencies import current_principal


def application_workspace_service(request: Request) -> ApplicationWorkspaceService:
    service = getattr(request.app.state, "application_workspace_service", None)
    if service is None:
        raise ApplicationWorkspaceUnavailable
    return cast(ApplicationWorkspaceService, service)


def application_workspace_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
