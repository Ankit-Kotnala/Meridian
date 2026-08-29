"""FastAPI dependencies for the authenticated Career Growth boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.career_growth.application import CareerGrowthService, RequestContext
from rezumi.modules.career_growth.domain import CareerGrowthUnavailable
from rezumi.modules.identity.domain import AuthenticatedPrincipal

from rezumi_api.modules.identity.dependencies import current_principal


def career_growth_service(request: Request) -> CareerGrowthService:
    service = getattr(request.app.state, "career_growth_service", None)
    if service is None:
        raise CareerGrowthUnavailable
    return cast(CareerGrowthService, service)


def career_growth_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
