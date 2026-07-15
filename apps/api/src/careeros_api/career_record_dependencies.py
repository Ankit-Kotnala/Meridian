"""FastAPI dependencies for the authenticated Career Record boundary."""

from typing import Annotated, cast

from careeros.modules.career_record.application import CareerRecordService
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentRequestContext,
    AttachmentWorkflowService,
)
from careeros.modules.career_record.application.models import RequestContext
from careeros.modules.career_record.domain.errors import CareerRecordUnavailable
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import Depends, Request

from careeros_api.identity_dependencies import current_principal


def career_record_service(request: Request) -> CareerRecordService:
    service = getattr(request.app.state, "career_record_service", None)
    if service is None:
        raise CareerRecordUnavailable
    return cast(CareerRecordService, service)


def attachment_workflow_service(request: Request) -> AttachmentWorkflowService:
    service = getattr(request.app.state, "attachment_workflow_service", None)
    if service is None:
        raise CareerRecordUnavailable
    return cast(AttachmentWorkflowService, service)


def career_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> RequestContext:
    return RequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )


def attachment_request_context(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> AttachmentRequestContext:
    return AttachmentRequestContext(
        actor_user_id=principal.user_id,
        request_id=str(request.state.request_id),
        trace_id=str(request.state.trace_id),
    )
