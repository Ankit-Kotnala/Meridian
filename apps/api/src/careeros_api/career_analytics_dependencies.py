"""FastAPI dependencies for the private Career Analytics boundary."""

from __future__ import annotations

from typing import Annotated, cast

from careeros.modules.career_analytics.application import CareerAnalyticsService, RequestContext
from careeros.modules.career_analytics.domain import CareerAnalyticsUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.identity_dependencies import current_principal


def career_analytics_service(request: Request) -> CareerAnalyticsService:
    service = getattr(request.app.state, "career_analytics_service", None)
    if service is None:
        raise CareerAnalyticsUnavailable
    return cast(CareerAnalyticsService, service)


def career_analytics_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
