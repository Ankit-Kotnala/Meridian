"""FastAPI dependencies for the authenticated Application Workspace boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.application_workspace.application import (
    ApplicationWorkspaceService,
    RequestContext,
)
from rezumi.modules.application_workspace.domain import ApplicationWorkspaceUnavailable
from rezumi.modules.identity.domain import AuthenticatedPrincipal

from rezumi_api.modules.identity.dependencies import current_principal


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
