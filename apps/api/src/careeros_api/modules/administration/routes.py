"""Thin HTTP delivery for least-privilege platform administration."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.administration.application import AdministrationService, RequestContext
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Header, Query, Response, status

from careeros_api.modules.administration.dependencies import (
    administration_request_context,
    administration_service,
)
from careeros_api.modules.administration.presenters import (
    audit_page_response,
    catalog_response,
    dead_letter_page_response,
    retry_response,
    system_response,
)
from careeros_api.modules.administration.schemas import (
    AdminAuditIntegrityResponse,
    AdminAuditPageResponse,
    AdminCatalogResponse,
    AdminDeadLetterPageResponse,
    AdminRetryRequest,
    AdminRetryResponse,
    AdminSystemResponse,
)
from careeros_api.modules.identity.dependencies import (
    current_principal,
    require_authenticated_csrf,
)
from careeros_api.modules.identity.schemas import ProblemResponse

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}
AdminReason = Annotated[
    str,
    Header(alias="X-Admin-Reason", min_length=12, max_length=500),
]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/system",
    response_model=AdminSystemResponse,
    operation_id="adminSystemGet",
    responses=_PROBLEMS,
)
async def get_system(
    response: Response,
    reason: AdminReason,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
) -> AdminSystemResponse:
    result = await service.system_snapshot(principal, context, reason=reason)
    _private(response)
    return system_response(result)


@router.get(
    "/catalog",
    response_model=AdminCatalogResponse,
    operation_id="adminCatalogGet",
    responses=_PROBLEMS,
)
async def get_catalog(
    response: Response,
    reason: AdminReason,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
) -> AdminCatalogResponse:
    result = await service.catalog_snapshot(principal, context, reason=reason)
    _private(response)
    return catalog_response(result)


@router.get(
    "/dead-letters",
    response_model=AdminDeadLetterPageResponse,
    operation_id="adminDeadLettersList",
    responses=_PROBLEMS,
)
async def list_dead_letters(
    response: Response,
    reason: AdminReason,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminDeadLetterPageResponse:
    result = await service.list_dead_letters(
        principal,
        context,
        reason=reason,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return dead_letter_page_response(result)


@router.post(
    "/dead-letters/{kind}/{target_id}/retry",
    response_model=AdminRetryResponse,
    operation_id="adminDeadLetterRetry",
    responses=_PROBLEMS,
)
async def retry_dead_letter(
    kind: str,
    target_id: UUID,
    payload: AdminRetryRequest,
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> AdminRetryResponse:
    result = await service.retry_dead_letter(
        principal,
        context,
        kind=kind,
        target_id=target_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )
    _private(response)
    return retry_response(result)


@router.get(
    "/audit-events",
    response_model=AdminAuditPageResponse,
    operation_id="adminAuditEventsList",
    responses=_PROBLEMS,
)
async def list_audit_events(
    response: Response,
    reason: AdminReason,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminAuditPageResponse:
    result = await service.list_audit_events(
        principal,
        context,
        reason=reason,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return audit_page_response(result)


@router.post(
    "/audit-integrity/verify",
    response_model=AdminAuditIntegrityResponse,
    operation_id="adminAuditIntegrityVerify",
    responses=_PROBLEMS,
)
async def verify_audit_integrity(
    response: Response,
    reason: AdminReason,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(administration_request_context)],
    service: Annotated[AdministrationService, Depends(administration_service)],
) -> AdminAuditIntegrityResponse:
    result = await service.verify_audit_integrity(
        principal,
        context,
        reason=reason,
    )
    _private(response)
    return AdminAuditIntegrityResponse(valid=result)
