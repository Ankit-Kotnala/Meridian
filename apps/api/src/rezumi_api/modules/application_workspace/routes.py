"""Authenticated HTTP delivery for Phase 8 application workflows and packs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from rezumi.modules.application_workspace.application import (
    UNSET,
    ApplicationFilter,
    ApplicationWorkspaceService,
    CreateApplication,
    CreateApplicationEvent,
    CreateApplicationNote,
    CreateApplicationTask,
    GenerateApplicationPack,
    RequestContext,
    UnsetType,
    UpdateApplication,
    UpdateApplicationTask,
)
from rezumi.modules.application_workspace.domain import (
    ApplicationContact,
    ApplicationEventKind,
    ApplicationStage,
    ApplicationWorkspaceValidationError,
    OutcomeStatus,
    ReferralStatus,
)
from rezumi.modules.identity.domain import AuthenticatedPrincipal

from rezumi_api.conditional_requests import parse_if_match_version
from rezumi_api.modules.application_workspace.dependencies import (
    application_workspace_request_context,
    application_workspace_service,
)
from rezumi_api.modules.application_workspace.presenters import (
    application_page_response,
    application_response,
    calendar_response,
    consistency_response,
    event_page_response,
    event_response,
    note_page_response,
    note_response,
    pack_page_response,
    pack_response,
    task_page_response,
    task_response,
)
from rezumi_api.modules.application_workspace.schemas import (
    ApplicationCalendarResponse,
    ApplicationConsistencyResponse,
    ApplicationContactInput,
    ApplicationCreateRequest,
    ApplicationEventCreateRequest,
    ApplicationEventPageResponse,
    ApplicationEventResponse,
    ApplicationNoteCreateRequest,
    ApplicationNotePageResponse,
    ApplicationNoteResponse,
    ApplicationPackCreateRequest,
    ApplicationPackPageResponse,
    ApplicationPackResponse,
    ApplicationPageResponse,
    ApplicationResponse,
    ApplicationStageUpdateRequest,
    ApplicationTaskCreateRequest,
    ApplicationTaskPageResponse,
    ApplicationTaskResponse,
    ApplicationTaskUpdateRequest,
    ApplicationUpdateRequest,
)
from rezumi_api.modules.identity.dependencies import current_principal, require_authenticated_csrf
from rezumi_api.modules.identity.schemas import ProblemResponse

router = APIRouter(prefix="/api/v1", tags=["Application Workspace"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _contact(value: ApplicationContactInput) -> ApplicationContact:
    return ApplicationContact(
        name=value.name,
        role=value.role,
        email=value.email,
        url=value.url,
    )


def _nullable_updated_field[T](
    payload: ApplicationUpdateRequest | ApplicationTaskUpdateRequest,
    name: str,
    value: T | None,
) -> T | None | UnsetType:
    if name not in payload.model_fields_set:
        return UNSET
    return value


def _required_updated_field[T](
    payload: ApplicationUpdateRequest | ApplicationTaskUpdateRequest,
    name: str,
    value: T | None,
) -> T | UnsetType:
    if name not in payload.model_fields_set:
        return UNSET
    if value is None:
        raise ApplicationWorkspaceValidationError(f"{name} cannot be null")
    return value


def _converted_updated_field[T, R](
    payload: ApplicationUpdateRequest,
    name: str,
    value: T | None,
    converter: Callable[[T], R],
) -> R | UnsetType:
    selected = _required_updated_field(payload, name, value)
    return selected if isinstance(selected, UnsetType) else converter(selected)


@router.get(
    "/applications",
    response_model=ApplicationPageResponse,
    operation_id="applicationsList",
    responses=_PROBLEMS,
)
async def list_applications(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    stage: Annotated[ApplicationStage | None, Query()] = None,
    outcome: Annotated[OutcomeStatus | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=120)] = None,
    industry: Annotated[str | None, Query(max_length=120)] = None,
    sort: Annotated[Literal["updated_desc", "deadline_asc"], Query()] = "updated_desc",
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ApplicationPageResponse:
    page = await service.list_applications(
        principal.user_id,
        ApplicationFilter(
            query=_clean(q),
            stage=stage,
            outcome=outcome,
            source=_clean(source),
            industry=_clean(industry),
            sort=sort,
        ),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return application_page_response(page)


@router.post(
    "/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="applicationCreate",
    responses=_PROBLEMS,
)
async def create_application(
    payload: ApplicationCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationResponse:
    value = await service.create_application(
        principal.user_id,
        CreateApplication(
            job_id=payload.job_id,
            resume_version_id=payload.resume_version_id,
            stage=ApplicationStage(payload.stage),
            application_deadline=payload.application_deadline,
            follow_up_at=payload.follow_up_at,
            contacts=tuple(_contact(item) for item in payload.contacts),
            referral_status=ReferralStatus(payload.referral_status),
            source=payload.source,
            industry=payload.industry,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.application.version)
    return application_response(value)


@router.get(
    "/applications/calendar",
    response_model=ApplicationCalendarResponse,
    operation_id="applicationCalendarList",
    responses=_PROBLEMS,
)
async def list_application_calendar(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> ApplicationCalendarResponse:
    if start > end:
        raise ApplicationWorkspaceValidationError("calendar start must not follow end")
    if (end - start).days > 366:
        raise ApplicationWorkspaceValidationError("calendar range must not exceed 366 days")
    values = await service.list_calendar(
        principal.user_id,
        start=start,
        end=end,
        limit=500,
    )
    _private(response)
    return calendar_response(values, start=start, end=end)


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    operation_id="applicationGet",
    responses=_PROBLEMS,
)
async def get_application(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationResponse:
    value = await service.get_application(principal.user_id, application_id)
    _private(response, value.application.version)
    return application_response(value)


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    operation_id="applicationUpdate",
    responses=_PROBLEMS,
)
async def update_application(
    application_id: UUID,
    payload: ApplicationUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationResponse:
    contacts: tuple[ApplicationContact, ...] | UnsetType = UNSET
    if "contacts" in payload.model_fields_set:
        contacts = tuple(_contact(item) for item in payload.contacts or ())
    value = await service.update_application(
        principal.user_id,
        application_id,
        UpdateApplication(
            resume_version_id=_required_updated_field(
                payload,
                "resume_version_id",
                payload.resume_version_id,
            ),
            resume_change_reason=payload.resume_change_reason,
            application_deadline=_nullable_updated_field(
                payload,
                "application_deadline",
                payload.application_deadline,
            ),
            follow_up_at=_nullable_updated_field(
                payload,
                "follow_up_at",
                payload.follow_up_at,
            ),
            contacts=contacts,
            referral_status=_converted_updated_field(
                payload,
                "referral_status",
                payload.referral_status,
                ReferralStatus,
            ),
            outcome_status=_converted_updated_field(
                payload,
                "outcome_status",
                payload.outcome_status,
                OutcomeStatus,
            ),
            rejection_reason=_nullable_updated_field(
                payload,
                "rejection_reason",
                payload.rejection_reason,
            ),
            offer_summary=_nullable_updated_field(
                payload,
                "offer_summary",
                payload.offer_summary,
            ),
            source=_nullable_updated_field(payload, "source", payload.source),
            industry=_nullable_updated_field(payload, "industry", payload.industry),
        ),
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, value.application.version)
    return application_response(value)


@router.patch(
    "/applications/{application_id}/stage",
    response_model=ApplicationResponse,
    operation_id="applicationStageUpdate",
    responses=_PROBLEMS,
)
async def update_application_stage(
    application_id: UUID,
    payload: ApplicationStageUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationResponse:
    value = await service.update_application(
        principal.user_id,
        application_id,
        UpdateApplication(
            stage=ApplicationStage(payload.stage),
            outcome_status=(
                OutcomeStatus(payload.outcome_status)
                if "outcome_status" in payload.model_fields_set
                and payload.outcome_status is not None
                else UNSET
            ),
            rejection_reason=(
                payload.rejection_reason
                if "rejection_reason" in payload.model_fields_set
                else UNSET
            ),
            offer_summary=(
                payload.offer_summary if "offer_summary" in payload.model_fields_set else UNSET
            ),
            reopen_reason=payload.reopen_reason,
        ),
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, value.application.version)
    return application_response(value)


@router.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="applicationDelete",
    responses=_PROBLEMS,
)
async def delete_application(
    application_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> None:
    await service.delete_application(
        principal.user_id,
        application_id,
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response)


@router.get(
    "/applications/{application_id}/tasks",
    response_model=ApplicationTaskPageResponse,
    operation_id="applicationTasksList",
    responses=_PROBLEMS,
)
async def list_application_tasks(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ApplicationTaskPageResponse:
    value = await service.list_tasks(
        principal.user_id,
        application_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return task_page_response(value)


@router.post(
    "/applications/{application_id}/tasks",
    response_model=ApplicationTaskResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="applicationTaskCreate",
    responses=_PROBLEMS,
)
async def create_application_task(
    application_id: UUID,
    payload: ApplicationTaskCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationTaskResponse:
    value = await service.create_task(
        principal.user_id,
        application_id,
        CreateApplicationTask(title=payload.title, due_at=payload.due_at),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return task_response(value)


@router.patch(
    "/applications/{application_id}/tasks/{task_id}",
    response_model=ApplicationTaskResponse,
    operation_id="applicationTaskUpdate",
    responses=_PROBLEMS,
)
async def update_application_task(
    application_id: UUID,
    task_id: UUID,
    payload: ApplicationTaskUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationTaskResponse:
    value = await service.update_task(
        principal.user_id,
        application_id,
        task_id,
        UpdateApplicationTask(
            title=_required_updated_field(payload, "title", payload.title),
            due_at=_nullable_updated_field(payload, "due_at", payload.due_at),
            completed=_required_updated_field(payload, "completed", payload.completed),
        ),
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, value.version)
    return task_response(value)


@router.get(
    "/applications/{application_id}/notes",
    response_model=ApplicationNotePageResponse,
    operation_id="applicationNotesList",
    responses=_PROBLEMS,
)
async def list_application_notes(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ApplicationNotePageResponse:
    value = await service.list_notes(
        principal.user_id,
        application_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return note_page_response(value)


@router.post(
    "/applications/{application_id}/notes",
    response_model=ApplicationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="applicationNoteCreate",
    responses=_PROBLEMS,
)
async def create_application_note(
    application_id: UUID,
    payload: ApplicationNoteCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationNoteResponse:
    value = await service.create_note(
        principal.user_id,
        application_id,
        CreateApplicationNote(body=payload.body),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return note_response(value)


@router.get(
    "/applications/{application_id}/events",
    response_model=ApplicationEventPageResponse,
    operation_id="applicationEventsList",
    responses=_PROBLEMS,
)
async def list_application_events(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ApplicationEventPageResponse:
    value = await service.list_events(
        principal.user_id,
        application_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return event_page_response(value)


@router.post(
    "/applications/{application_id}/events",
    response_model=ApplicationEventResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="applicationEventCreate",
    responses=_PROBLEMS,
)
async def create_application_event(
    application_id: UUID,
    payload: ApplicationEventCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationEventResponse:
    value = await service.record_event(
        principal.user_id,
        application_id,
        CreateApplicationEvent(
            event_kind=ApplicationEventKind(payload.event_kind),
            occurred_at=payload.occurred_at,
            title=payload.title,
            description=payload.description,
            metadata=payload.metadata,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return event_response(value)


@router.post(
    "/applications/{application_id}/application-packs",
    response_model=ApplicationPackResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="applicationPackCreate",
    responses=_PROBLEMS,
)
async def create_application_pack(
    application_id: UUID,
    payload: ApplicationPackCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationPackResponse:
    value = await service.generate_pack(
        principal.user_id,
        application_id,
        GenerateApplicationPack(include_kinds=tuple(payload.include_kinds)),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return pack_response(value)


@router.get(
    "/applications/{application_id}/application-packs",
    response_model=ApplicationPackPageResponse,
    operation_id="applicationPacksList",
    responses=_PROBLEMS,
)
async def list_application_packs(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ApplicationPackPageResponse:
    value = await service.list_packs(
        principal.user_id,
        application_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return pack_page_response(value)


@router.get(
    "/application-packs/{pack_id}",
    response_model=ApplicationPackResponse,
    operation_id="applicationPackGet",
    responses=_PROBLEMS,
)
async def get_application_pack(
    pack_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationPackResponse:
    value = await service.get_pack(principal.user_id, pack_id)
    _private(response)
    return pack_response(value)


@router.get(
    "/application-packs/{pack_id}/consistency",
    response_model=ApplicationConsistencyResponse,
    operation_id="applicationPackConsistencyGet",
    responses=_PROBLEMS,
)
async def get_application_pack_consistency(
    pack_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> ApplicationConsistencyResponse:
    value = await service.get_pack(principal.user_id, pack_id)
    _private(response)
    return consistency_response(value)


@router.delete(
    "/applications/{application_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="applicationDocumentDelete",
    responses=_PROBLEMS,
)
async def delete_application_document(
    application_id: UUID,
    document_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(application_workspace_request_context)],
    service: Annotated[ApplicationWorkspaceService, Depends(application_workspace_service)],
) -> None:
    await service.delete_document(
        principal.user_id,
        application_id,
        document_id,
        context=context,
    )
    _private(response)
