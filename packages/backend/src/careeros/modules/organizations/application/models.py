"""Organization tenancy application commands and views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from careeros.modules.organizations.domain import (
    GrantPurpose,
    GrantScope,
    Organization,
    OrganizationAccessGrant,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationRole,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class CreateOrganization:
    name: str


@dataclass(frozen=True, slots=True)
class UpdateOrganization:
    name: str


@dataclass(frozen=True, slots=True)
class InviteOrganizationMember:
    email: str
    role: OrganizationRole


@dataclass(frozen=True, slots=True)
class AcceptOrganizationInvitation:
    token: str


@dataclass(frozen=True, slots=True)
class CreateOrganizationGrant:
    grantee_user_id: UUID
    purpose: GrantPurpose
    scope: GrantScope
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OrganizationView:
    organization: Organization
    membership: OrganizationMembership


@dataclass(frozen=True, slots=True)
class OrganizationRoster:
    organization: Organization
    members: tuple[OrganizationMembership, ...]


@dataclass(frozen=True, slots=True)
class InvitationView:
    invitation: OrganizationInvitation
    delivery_status: str


@dataclass(frozen=True, slots=True)
class GrantView:
    grant: OrganizationAccessGrant
    active: bool
