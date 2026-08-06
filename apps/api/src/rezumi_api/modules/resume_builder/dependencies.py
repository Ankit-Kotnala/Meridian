"""FastAPI dependencies for the authenticated resume builder boundary."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.resume_builder.application import RequestContext, ResumeBuilderService
from rezumi.modules.resume_builder.domain import ResumeBuilderUnavailable

from rezumi_api.modules.identity.dependencies import current_principal


def resume_builder_service(request: Request) -> ResumeBuilderService:
    service = getattr(request.app.state, "resume_builder_service", None)
    if service is None:
        raise ResumeBuilderUnavailable
    return cast(ResumeBuilderService, service)


def resume_builder_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
