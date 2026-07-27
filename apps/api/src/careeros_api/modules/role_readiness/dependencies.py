"""FastAPI dependencies for the authenticated Role Readiness boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.role_readiness.application import RequestContext, RoleReadinessService
from careeros.modules.role_readiness.domain import RoleReadinessUnavailable
from fastapi import Depends, Request

from careeros_api.modules.identity.dependencies import current_principal


def role_readiness_service(request: Request) -> RoleReadinessService:
    service = getattr(request.app.state, "role_readiness_service", None)
    if service is None:
        raise RoleReadinessUnavailable
    return cast(RoleReadinessService, service)


def role_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
