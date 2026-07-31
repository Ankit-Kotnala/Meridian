"""Pure organization tenancy wire presenters."""

from typing import cast

from careeros.modules.organizations.application import (
    GrantView,
    InvitationView,
    OrganizationRoster,
    OrganizationView,
)
from careeros.modules.organizations.domain import OrganizationMembership

from careeros_api.modules.organizations.schemas import (
    GrantListResponse,
    GrantResponse,
    InvitationDeliveryStatus,
    InvitationResponse,
    InvitationRole,
    MembershipResponse,
    OrganizationListResponse,
    OrganizationRosterResponse,
    TenantOrganizationResponse,
)


def organization_response(value: OrganizationView) -> TenantOrganizationResponse:
    organization = value.organization
    membership = value.membership
    return TenantOrganizationResponse(
        id=organization.id,
        name=organization.name,
        status=organization.status.value,
        role=membership.role.value,
        capabilities=sorted(item.value for item in membership.capabilities),
        version=organization.version,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
    )


def organization_list_response(
    values: tuple[OrganizationView, ...],
) -> OrganizationListResponse:
    return OrganizationListResponse(
        organizations=[organization_response(value) for value in values]
    )


def membership_response(value: OrganizationMembership) -> MembershipResponse:
    return MembershipResponse(
        id=value.id,
        user_id=value.user_id,
        role=value.role.value,
        status=value.status.value,
        version=value.version,
        accepted_at=value.accepted_at,
        suspended_at=value.suspended_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def roster_response(value: OrganizationRoster) -> OrganizationRosterResponse:
    return OrganizationRosterResponse(
        organization_id=value.organization.id,
        members=[membership_response(member) for member in value.members],
    )


def invitation_response(value: InvitationView) -> InvitationResponse:
    invitation = value.invitation
    return InvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        role=cast(InvitationRole, invitation.role.value),
        status=invitation.status.value,
        delivery_status=cast(InvitationDeliveryStatus, value.delivery_status),
        expires_at=invitation.expires_at,
        version=invitation.version,
    )


def grant_response(value: GrantView) -> GrantResponse:
    grant = value.grant
    return GrantResponse(
        id=grant.id,
        organization_id=grant.organization_id,
        subject_user_id=grant.subject_user_id,
        grantee_user_id=grant.grantee_user_id,
        purpose=grant.purpose.value,
        scope=grant.scope.value,
        status=grant.status.value,
        active=value.active,
        expires_at=grant.expires_at,
        version=grant.version,
        created_at=grant.created_at,
        updated_at=grant.updated_at,
    )


def grant_list_response(values: tuple[GrantView, ...]) -> GrantListResponse:
    return GrantListResponse(grants=[grant_response(value) for value in values])
