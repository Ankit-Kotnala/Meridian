"""Thin HTTP delivery for organization tenancy and delegated grants."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.organizations.application import (
    AcceptOrganizationInvitation,
    CreateOrganization,
    CreateOrganizationGrant,
    InviteOrganizationMember,
    OrganizationService,
    RequestContext,
    UpdateOrganization,
)
from careeros.modules.organizations.domain import GrantPurpose, GrantScope, OrganizationRole
from fastapi import APIRouter, Depends, Header, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.modules.identity.dependencies import current_principal, require_authenticated_csrf
from careeros_api.modules.identity.schemas import ProblemResponse
from careeros_api.modules.organizations.dependencies import (
    organization_request_context,
    organization_service,
)
from careeros_api.modules.organizations.presenters import (
    grant_list_response,
    grant_response,
    invitation_response,
    membership_response,
    organization_list_response,
    organization_response,
    roster_response,
)
from careeros_api.modules.organizations.schemas import (
    AcceptInvitationRequest,
    CreateGrantRequest,
    CreateOrganizationRequest,
    GrantListResponse,
    GrantResponse,
    InvitationResponse,
    InviteMemberRequest,
    MembershipResponse,
    OrganizationListResponse,
    OrganizationRosterResponse,
    TenantOrganizationResponse,
    UpdateOrganizationRequest,
)

router = APIRouter(prefix="/api/v1", tags=["Organizations"])
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
    "/organizations",
    response_model=OrganizationListResponse,
    operation_id="organizationsList",
    responses=_PROBLEMS,
)
async def list_organizations(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[OrganizationService, Depends(organization_service)],
) -> OrganizationListResponse:
    result = await service.list_organizations(principal.user_id)
    _private(response)
    return organization_list_response(result)


@router.post(
    "/organizations",
    response_model=TenantOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="organizationsCreate",
    responses=_PROBLEMS,
)
async def create_organization(
    payload: CreateOrganizationRequest,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> TenantOrganizationResponse:
    result = await service.create_organization(
        CreateOrganization(name=payload.name),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, result.organization.version)
    return organization_response(result)


@router.get(
    "/organizations/{organization_id}",
    response_model=TenantOrganizationResponse,
    operation_id="organizationsGet",
    responses=_PROBLEMS,
)
async def get_organization(
    organization_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[OrganizationService, Depends(organization_service)],
) -> TenantOrganizationResponse:
    result = await service.get_organization(organization_id, principal.user_id)
    _private(response, result.organization.version)
    return organization_response(result)


@router.patch(
    "/organizations/{organization_id}",
    response_model=TenantOrganizationResponse,
    operation_id="organizationsUpdate",
    responses=_PROBLEMS,
)
async def update_organization(
    organization_id: UUID,
    payload: UpdateOrganizationRequest,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> TenantOrganizationResponse:
    result = await service.update_organization(
        organization_id,
        UpdateOrganization(name=payload.name),
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, result.organization.version)
    return organization_response(result)


@router.get(
    "/organizations/{organization_id}/members",
    response_model=OrganizationRosterResponse,
    operation_id="organizationMembersList",
    responses=_PROBLEMS,
)
async def list_members(
    organization_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[OrganizationService, Depends(organization_service)],
) -> OrganizationRosterResponse:
    result = await service.roster(organization_id, principal.user_id)
    _private(response)
    return roster_response(result)


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="organizationInvitationsCreate",
    responses=_PROBLEMS,
)
async def invite_member(
    organization_id: UUID,
    payload: InviteMemberRequest,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> InvitationResponse:
    result = await service.invite_member(
        organization_id,
        InviteOrganizationMember(
            email=payload.email,
            role=OrganizationRole(payload.role),
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, result.invitation.version)
    return invitation_response(result)


@router.post(
    "/organization-invitations/accept",
    response_model=TenantOrganizationResponse,
    operation_id="organizationInvitationsAccept",
    responses=_PROBLEMS,
)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> TenantOrganizationResponse:
    result = await service.accept_invitation(
        AcceptOrganizationInvitation(token=payload.token),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, result.organization.version)
    return organization_response(result)


@router.post(
    "/organizations/{organization_id}/members/{member_user_id}/suspend",
    response_model=MembershipResponse,
    operation_id="organizationMembersSuspend",
    responses=_PROBLEMS,
)
async def suspend_member(
    organization_id: UUID,
    member_user_id: UUID,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> MembershipResponse:
    result = await service.suspend_member(
        organization_id,
        member_user_id,
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, result.version)
    return membership_response(result)


@router.get(
    "/organizations/{organization_id}/grants",
    response_model=GrantListResponse,
    operation_id="organizationGrantsList",
    responses=_PROBLEMS,
)
async def list_grants(
    organization_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[OrganizationService, Depends(organization_service)],
) -> GrantListResponse:
    result = await service.list_grants(organization_id, principal.user_id)
    _private(response)
    return grant_list_response(result)


@router.post(
    "/organizations/{organization_id}/grants",
    response_model=GrantResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="organizationGrantsCreate",
    responses=_PROBLEMS,
)
async def create_grant(
    organization_id: UUID,
    payload: CreateGrantRequest,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> GrantResponse:
    result = await service.create_grant(
        organization_id,
        CreateOrganizationGrant(
            grantee_user_id=payload.grantee_user_id,
            purpose=GrantPurpose(payload.purpose),
            scope=GrantScope(payload.scope),
            expires_at=payload.expires_at,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, result.grant.version)
    return grant_response(result)


@router.delete(
    "/organizations/{organization_id}/grants/{grant_id}",
    response_model=GrantResponse,
    operation_id="organizationGrantsRevoke",
    responses=_PROBLEMS,
)
async def revoke_grant(
    organization_id: UUID,
    grant_id: UUID,
    response: Response,
    _principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(organization_request_context)],
    service: Annotated[OrganizationService, Depends(organization_service)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> GrantResponse:
    result = await service.revoke_grant(
        organization_id,
        grant_id,
        expected_version=parse_if_match_version(if_match),
        context=context,
    )
    _private(response, result.grant.version)
    return grant_response(result)
