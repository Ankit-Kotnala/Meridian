"""Authenticated HTTP delivery for Phase 6 Change Studio use cases."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.change_studio.application import (
    AlternativeRequest,
    AnswerClarification,
    ChangeStudioService,
    CreateChangeSet,
    EditOperation,
    RequestContext,
)
from careeros.modules.change_studio.domain import ChangeTargetKind
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Header, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.modules.change_studio.dependencies import (
    change_studio_request_context,
    change_studio_service,
)
from careeros_api.modules.change_studio.presenters import change_set_response
from careeros_api.modules.change_studio.schemas import (
    ChangeSetCreateRequest,
    ChangeSetResponse,
    ClarificationAnswerRequest,
    OperationAlternativeRequest,
    OperationEditRequest,
)
from careeros_api.modules.identity.dependencies import current_principal, require_authenticated_csrf
from careeros_api.modules.identity.schemas import ProblemResponse

router = APIRouter(prefix="/api/v1", tags=["Change Studio"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


@router.post(
    "/change-sets",
    response_model=ChangeSetResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="changeSetCreate",
    responses=_PROBLEMS,
)
async def create_change_set(
    payload: ChangeSetCreateRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.create_change_set(
        principal.user_id,
        CreateChangeSet(
            analysis_id=payload.analysis_id,
            target_kind=ChangeTargetKind(payload.target_kind),
            tone=payload.tone,
            length=payload.length,
            max_operations=payload.max_operations,
        ),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.get(
    "/change-sets/{change_set_id}",
    response_model=ChangeSetResponse,
    operation_id="changeSetGet",
    responses=_PROBLEMS,
)
async def get_change_set(
    change_set_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.get_change_set(principal.user_id, change_set_id)
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/accept",
    response_model=ChangeSetResponse,
    operation_id="changeOperationAccept",
    responses=_PROBLEMS,
)
async def accept_operation(
    change_set_id: UUID,
    operation_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.accept_operation(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/reject",
    response_model=ChangeSetResponse,
    operation_id="changeOperationReject",
    responses=_PROBLEMS,
)
async def reject_operation(
    change_set_id: UUID,
    operation_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.reject_operation(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/edit",
    response_model=ChangeSetResponse,
    operation_id="changeOperationEdit",
    responses=_PROBLEMS,
)
async def edit_operation(
    change_set_id: UUID,
    operation_id: UUID,
    payload: OperationEditRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.edit_operation(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        EditOperation(after_text=payload.after_text),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/alternatives",
    response_model=ChangeSetResponse,
    operation_id="changeOperationAlternativeCreate",
    responses=_PROBLEMS,
)
async def create_operation_alternative(
    change_set_id: UUID,
    operation_id: UUID,
    payload: OperationAlternativeRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.create_alternative(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        AlternativeRequest(
            tone=payload.tone,
            length=payload.length,
            preserve_terms=tuple(payload.preserve_terms),
        ),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/lock",
    response_model=ChangeSetResponse,
    operation_id="changeOperationLock",
    responses=_PROBLEMS,
)
async def lock_operation(
    change_set_id: UUID,
    operation_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.lock_operation(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
        locked=True,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/operations/{operation_id}/unlock",
    response_model=ChangeSetResponse,
    operation_id="changeOperationUnlock",
    responses=_PROBLEMS,
)
async def unlock_operation(
    change_set_id: UUID,
    operation_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.lock_operation(
        principal.user_id,
        change_set_id,
        operation_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
        locked=False,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/apply-safe",
    response_model=ChangeSetResponse,
    operation_id="changeSetApplySafe",
    responses=_PROBLEMS,
)
async def apply_safe_changes(
    change_set_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.apply_safe(
        principal.user_id,
        change_set_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/undo",
    response_model=ChangeSetResponse,
    operation_id="changeSetUndo",
    responses=_PROBLEMS,
)
async def undo_change_set(
    change_set_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.undo(
        principal.user_id,
        change_set_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/redo",
    response_model=ChangeSetResponse,
    operation_id="changeSetRedo",
    responses=_PROBLEMS,
)
async def redo_change_set(
    change_set_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.redo(
        principal.user_id,
        change_set_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/change-sets/{change_set_id}/versions/{version_id}/restore",
    response_model=ChangeSetResponse,
    operation_id="changeSetVersionRestore",
    responses=_PROBLEMS,
)
async def restore_change_set_version(
    change_set_id: UUID,
    version_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.restore_version(
        principal.user_id,
        change_set_id,
        version_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)


@router.post(
    "/clarifications/{clarification_id}/answer",
    response_model=ChangeSetResponse,
    operation_id="changeClarificationAnswer",
    responses=_PROBLEMS,
)
async def answer_clarification(
    clarification_id: UUID,
    payload: ClarificationAnswerRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(change_studio_request_context)],
    service: Annotated[ChangeStudioService, Depends(change_studio_service)],
) -> ChangeSetResponse:
    value = await service.answer_clarification(
        principal.user_id,
        clarification_id,
        parse_if_match_version(if_match),
        AnswerClarification(answer_text=payload.answer_text),
        idempotency_key,
        context,
    )
    _private(response, value.change_set.version)
    return change_set_response(value)
