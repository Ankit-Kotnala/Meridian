"""Authenticated HTTP delivery for Phase 4 Role Explorer use cases."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.role_readiness.application import (
    AnalyzeRoleReadiness,
    RequestContext,
    RoleFilter,
    RoleReadinessService,
    SaveRole,
    UpdateSavedRole,
)
from careeros.modules.role_readiness.domain import RoleCompetency, RoleSeniority
from fastapi import APIRouter, Depends, Header, Query, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.identity_dependencies import current_principal, require_authenticated_csrf
from careeros_api.identity_schemas import ProblemResponse
from careeros_api.role_readiness_dependencies import (
    role_readiness_service,
    role_request_context,
)
from careeros_api.role_readiness_presenters import (
    analysis_page_response,
    analysis_response,
    comparison_response,
    role_detail_response,
    role_page_response,
    saved_role_page_response,
    saved_role_response,
)
from careeros_api.role_readiness_schemas import (
    RoleComparisonResponse,
    RolePageResponse,
    RoleReadinessPageResponse,
    RoleReadinessRequest,
    RoleReadinessResponse,
    RoleResponse,
    SavedRoleCreateRequest,
    SavedRolePageResponse,
    SavedRoleResponse,
    SavedRoleUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["Role Explorer"])
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


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _competencies_by_role(
    service: RoleReadinessService, role_ids: set[UUID]
) -> dict[UUID, tuple[RoleCompetency, ...]]:
    result: dict[UUID, tuple[RoleCompetency, ...]] = {}
    for role_id in role_ids:
        result[role_id] = (await service.get_role(role_id)).competencies
    return result


@router.get(
    "/roles",
    response_model=RolePageResponse,
    operation_id="rolesList",
    responses=_PROBLEMS,
)
async def list_roles(
    response: Response,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    seniority: Annotated[RoleSeniority | None, Query()] = None,
    industry: Annotated[str | None, Query(max_length=120)] = None,
    domain: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> RolePageResponse:
    page = await service.list_roles(
        RoleFilter(
            query=_clean(q),
            seniority=seniority,
            industry=_clean(industry),
            domain=_clean(domain),
        ),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return role_page_response(page)


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    operation_id="roleGet",
    responses=_PROBLEMS,
)
async def get_role(
    role_id: UUID,
    response: Response,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> RoleResponse:
    detail = await service.get_role(role_id)
    _private(response, detail.role.version)
    return role_detail_response(detail)


@router.get(
    "/saved-roles",
    response_model=SavedRolePageResponse,
    operation_id="savedRolesList",
    responses=_PROBLEMS,
)
async def list_saved_roles(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> SavedRolePageResponse:
    page = await service.list_saved_roles(principal.user_id, cursor=cursor, limit=limit)
    competencies = await _competencies_by_role(service, {item.role.id for item in page.data})
    _private(response)
    return saved_role_page_response(page, competencies)


@router.post(
    "/saved-roles",
    response_model=SavedRoleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="savedRoleCreate",
    responses=_PROBLEMS,
)
async def create_saved_role(
    payload: SavedRoleCreateRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(role_request_context)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> SavedRoleResponse:
    value = await service.save_role(
        principal.user_id, SaveRole(payload.role_id, payload.notes), context
    )
    competencies = (await service.get_role(value.role.id)).competencies
    _private(response, value.saved_role.version)
    return saved_role_response(value, competencies)


@router.patch(
    "/saved-roles/{saved_role_id}",
    response_model=SavedRoleResponse,
    operation_id="savedRoleUpdate",
    responses=_PROBLEMS,
)
async def update_saved_role(
    saved_role_id: UUID,
    payload: SavedRoleUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(role_request_context)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> SavedRoleResponse:
    value = await service.update_saved_role(
        principal.user_id,
        saved_role_id,
        parse_if_match_version(if_match),
        UpdateSavedRole(payload.notes),
        context,
    )
    competencies = (await service.get_role(value.role.id)).competencies
    _private(response, value.saved_role.version)
    return saved_role_response(value, competencies)


@router.delete(
    "/saved-roles/{saved_role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="savedRoleDelete",
    responses=_PROBLEMS,
)
async def delete_saved_role(
    saved_role_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(role_request_context)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> None:
    await service.delete_saved_role(
        principal.user_id, saved_role_id, parse_if_match_version(if_match), context
    )
    _private(response)


@router.get(
    "/role-readiness",
    response_model=RoleReadinessPageResponse,
    operation_id="roleReadinessHistoryList",
    responses=_PROBLEMS,
)
async def list_role_readiness_history(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
    role_id: Annotated[UUID | None, Query(alias="roleId")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> RoleReadinessPageResponse:
    page = await service.list_history(
        principal.user_id,
        role_id=role_id,
        cursor=cursor,
        limit=limit,
    )
    competencies = await _competencies_by_role(service, {item.role.id for item in page.data})
    _private(response)
    return analysis_page_response(page, competencies)


@router.post(
    "/role-readiness",
    response_model=RoleReadinessResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="roleReadinessAnalyze",
    responses=_PROBLEMS,
)
async def analyze_role_readiness(
    payload: RoleReadinessRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(role_request_context)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> RoleReadinessResponse:
    value = await service.analyze_role(
        principal.user_id,
        AnalyzeRoleReadiness(role_id=payload.role_id, saved_role_id=payload.saved_role_id),
        idempotency_key,
        context,
    )
    competencies = (await service.get_role(value.role.id)).competencies
    _private(response)
    return analysis_response(value, competencies)


@router.get(
    "/role-readiness/compare",
    response_model=RoleComparisonResponse,
    operation_id="roleReadinessCompare",
    responses=_PROBLEMS,
)
async def compare_role_readiness(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
    role_ids: Annotated[list[UUID], Query(alias="roleId", min_length=2, max_length=3)],
) -> RoleComparisonResponse:
    value = await service.compare_roles(principal.user_id, tuple(role_ids))
    competencies = await _competencies_by_role(service, {entry.role.id for entry in value.entries})
    _private(response)
    return comparison_response(value, competencies)


@router.get(
    "/role-readiness/{analysis_id}",
    response_model=RoleReadinessResponse,
    operation_id="roleReadinessGet",
    responses=_PROBLEMS,
)
async def get_role_readiness(
    analysis_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RoleReadinessService, Depends(role_readiness_service)],
) -> RoleReadinessResponse:
    value = await service.get_analysis(principal.user_id, analysis_id)
    competencies = (await service.get_role(value.role.id)).competencies
    _private(response)
    return analysis_response(value, competencies)
