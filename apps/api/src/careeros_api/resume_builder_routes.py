"""Authenticated HTTP delivery for Phase 7 resume builder use cases."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.resume_builder.application import (
    CreateResume,
    ExportResume,
    RequestContext,
    ResumeBuilderService,
    UpdateResume,
)
from careeros.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeFormat,
    ResumeSection,
    ResumeTemplate,
)
from fastapi import APIRouter, Depends, Header, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.identity_dependencies import current_principal, require_authenticated_csrf
from careeros_api.identity_schemas import ProblemResponse
from careeros_api.resume_builder_dependencies import (
    resume_builder_request_context,
    resume_builder_service,
)
from careeros_api.resume_builder_presenters import (
    download_intent_response,
    export_record_response,
    resume_list_response,
    resume_response,
    resume_version_list_response,
    resume_version_response,
    verification_response,
)
from careeros_api.resume_builder_schemas import (
    ResumeCreateRequest,
    ResumeDownloadIntentResponse,
    ResumeExportRecordResponse,
    ResumeExportRequest,
    ResumeListResponse,
    ResumeResponse,
    ResumeSectionRequest,
    ResumeUpdateRequest,
    ResumeVerificationResponse,
    ResumeVersionListResponse,
    ResumeVersionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Resume Builder"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


@router.get(
    "/resumes",
    response_model=ResumeListResponse,
    operation_id="resumeList",
    responses=_PROBLEMS,
)
async def list_resumes(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeListResponse:
    value = await service.list_resumes(principal.user_id)
    _private(response)
    return resume_list_response(value)


@router.post(
    "/resumes",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="resumeCreate",
    responses=_PROBLEMS,
)
async def create_resume(
    payload: ResumeCreateRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeResponse:
    value = await service.create_resume(
        principal.user_id,
        CreateResume(
            title=payload.title,
            target_role=payload.target_role,
            template=ResumeTemplate(payload.template),
            change_set_id=payload.change_set_id,
            change_set_version_id=payload.change_set_version_id,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.resume.version)
    return resume_response(value)


@router.get(
    "/resumes/{resume_id}",
    response_model=ResumeResponse,
    operation_id="resumeGet",
    responses=_PROBLEMS,
)
async def get_resume(
    resume_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeResponse:
    value = await service.get_resume(principal.user_id, resume_id)
    _private(response, value.resume.version)
    return resume_response(value)


@router.patch(
    "/resumes/{resume_id}",
    response_model=ResumeResponse,
    operation_id="resumeUpdate",
    responses=_PROBLEMS,
)
async def update_resume(
    resume_id: UUID,
    payload: ResumeUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeResponse:
    value = await service.update_resume(
        principal.user_id,
        resume_id,
        UpdateResume(
            title=payload.title,
            target_role=payload.target_role,
            template=ResumeTemplate(payload.template) if payload.template is not None else None,
            sections=(
                tuple(_section(section) for section in payload.sections)
                if payload.sections is not None
                else None
            ),
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.resume.version)
    return resume_response(value)


@router.get(
    "/resumes/{resume_id}/versions",
    response_model=ResumeVersionListResponse,
    operation_id="resumeVersionList",
    responses=_PROBLEMS,
)
async def list_versions(
    resume_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeVersionListResponse:
    value = await service.list_versions(principal.user_id, resume_id)
    _private(response)
    return resume_version_list_response(value)


@router.post(
    "/resumes/{resume_id}/versions",
    response_model=ResumeVersionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="resumeVersionCreate",
    responses=_PROBLEMS,
)
async def create_version(
    resume_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeVersionResponse:
    value = await service.create_version(
        principal.user_id,
        resume_id,
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return resume_version_response(value)


@router.get(
    "/resume-versions/{version_id}",
    response_model=ResumeVersionResponse,
    operation_id="resumeVersionGet",
    responses=_PROBLEMS,
)
async def get_version(
    version_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeVersionResponse:
    value = await service.get_version(principal.user_id, version_id)
    _private(response)
    return resume_version_response(value)


@router.post(
    "/resumes/{resume_id}/restore/{version_id}",
    response_model=ResumeResponse,
    operation_id="resumeVersionRestore",
    responses=_PROBLEMS,
)
async def restore_version(
    resume_id: UUID,
    version_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeResponse:
    value = await service.restore_version(
        principal.user_id,
        resume_id,
        version_id,
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.resume.version)
    return resume_response(value)


@router.post(
    "/resume-versions/{version_id}/export",
    response_model=ResumeExportRecordResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="resumeVersionExport",
    responses=_PROBLEMS,
)
async def export_version(
    version_id: UUID,
    payload: ResumeExportRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeExportRecordResponse:
    value = await service.export_version(
        principal.user_id,
        version_id,
        ExportResume(format=ResumeFormat(payload.format)),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return export_record_response(value)


@router.get(
    "/exports/{export_id}",
    response_model=ResumeExportRecordResponse,
    operation_id="resumeExportGet",
    responses=_PROBLEMS,
)
async def get_export(
    export_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeExportRecordResponse:
    value = await service.get_export(principal.user_id, export_id)
    _private(response)
    return export_record_response(value)


@router.get(
    "/exports/{export_id}/verification",
    response_model=ResumeVerificationResponse,
    operation_id="resumeExportVerificationGet",
    responses=_PROBLEMS,
)
async def get_verification(
    export_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeVerificationResponse:
    value = await service.get_verification(principal.user_id, export_id)
    _private(response)
    return verification_response(value)


@router.post(
    "/exports/{export_id}/download-intent",
    response_model=ResumeDownloadIntentResponse,
    operation_id="resumeExportDownloadIntentCreate",
    responses=_PROBLEMS,
)
async def create_download_intent(
    export_id: UUID,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeDownloadIntentResponse:
    value = await service.create_download_intent(
        principal.user_id,
        export_id,
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return download_intent_response(value)


@router.delete(
    "/exports/{export_id}",
    response_model=ResumeExportRecordResponse,
    operation_id="resumeExportDelete",
    responses=_PROBLEMS,
)
async def delete_export(
    export_id: UUID,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(resume_builder_request_context)],
    service: Annotated[ResumeBuilderService, Depends(resume_builder_service)],
) -> ResumeExportRecordResponse:
    value = await service.delete_export(
        principal.user_id,
        export_id,
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return export_record_response(value)


def _section(value: ResumeSectionRequest) -> ResumeSection:
    return ResumeSection(
        id=value.id,
        title=value.title,
        kind=value.kind,
        items=tuple(
            ResumeBullet(
                id=item.id,
                text=item.text,
                evidence_ids=tuple(item.evidence_ids),
                source=item.source,
            )
            for item in value.items
        ),
    )
