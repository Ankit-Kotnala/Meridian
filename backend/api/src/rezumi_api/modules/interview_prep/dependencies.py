"""FastAPI dependencies for the authenticated Interview Prep boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.interview_prep.application import InterviewPrepService, RequestContext
from rezumi.modules.interview_prep.domain import InterviewPrepUnavailable

from rezumi_api.modules.identity.dependencies import current_principal


def interview_prep_service(request: Request) -> InterviewPrepService:
    service = getattr(request.app.state, "interview_prep_service", None)
    if service is None:
        raise InterviewPrepUnavailable
    return cast(InterviewPrepService, service)


def interview_prep_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
