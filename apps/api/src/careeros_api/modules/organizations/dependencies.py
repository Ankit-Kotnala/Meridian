"""FastAPI dependencies for the organization tenancy boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.organizations.application import OrganizationService, RequestContext
from careeros.modules.organizations.domain import OrganizationUnavailable
from fastapi import Depends, Request

from careeros_api.modules.identity.dependencies import current_principal


def organization_service(request: Request) -> OrganizationService:
    service = getattr(request.app.state, "organization_service", None)
    if service is None:
        raise OrganizationUnavailable("organization services are unavailable")
    return cast(OrganizationService, service)


def organization_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
