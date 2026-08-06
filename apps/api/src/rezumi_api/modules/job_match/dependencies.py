"""FastAPI dependencies for the authenticated Job Match boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.job_match.application import JobMatchService, RequestContext
from rezumi.modules.job_match.domain import JobMatchUnavailable

from rezumi_api.modules.identity.dependencies import current_principal


def job_match_service(request: Request) -> JobMatchService:
    service = getattr(request.app.state, "job_match_service", None)
    if service is None:
        raise JobMatchUnavailable
    return cast(JobMatchService, service)


def job_match_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
