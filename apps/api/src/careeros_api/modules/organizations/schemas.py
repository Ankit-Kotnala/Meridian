"""Strict wire schemas for organization tenancy and delegated grants."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class OrganizationSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


OrganizationRole = Literal["owner", "admin", "coach", "member"]
InvitationRole = Literal["admin", "coach", "member"]
InvitationDeliveryStatus = Literal[
    "queued",
    "delivered",
    "failed",
    "accepted",
    "revoked",
    "expired",
]
MembershipStatus = Literal["active", "invited", "suspended", "left"]
GrantPurpose = Literal["coaching", "career_services", "program_support"]
GrantScope = Literal[
    "career_profile_summary",
    "resume_health_summary",
    "role_readiness_summary",
    "application_status",
    "career_growth_summary",
    "collaboration_comment",
]
GrantStatus = Literal["active", "revoked", "expired"]


class CreateOrganizationRequest(OrganizationSchema):
    name: Annotated[str, Field(min_length=2, max_length=160)]


class UpdateOrganizationRequest(CreateOrganizationRequest):
    pass


class OrganizationResponse(OrganizationSchema):
    id: UUID
    name: str
    status: Literal["active", "archived"]
    role: OrganizationRole
    capabilities: list[str]
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(OrganizationSchema):
    organizations: list[OrganizationResponse] = Field(max_length=100)


class MembershipResponse(OrganizationSchema):
    id: UUID
    user_id: UUID
    role: OrganizationRole
    status: MembershipStatus
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]
    accepted_at: datetime | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrganizationRosterResponse(OrganizationSchema):
    organization_id: UUID
    members: list[MembershipResponse] = Field(max_length=250)


class InviteMemberRequest(OrganizationSchema):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    role: InvitationRole


class InvitationResponse(OrganizationSchema):
    id: UUID
    organization_id: UUID
    role: InvitationRole
    status: Literal[
        "pending_delivery",
        "pending",
        "accepted",
        "revoked",
        "expired",
        "delivery_dead_lettered",
    ]
    delivery_status: InvitationDeliveryStatus
    expires_at: datetime
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]


class AcceptInvitationRequest(OrganizationSchema):
    token: Annotated[str, Field(min_length=32, max_length=128)]


class CreateGrantRequest(OrganizationSchema):
    grantee_user_id: UUID
    purpose: GrantPurpose
    scope: GrantScope
    expires_at: datetime


class GrantResponse(OrganizationSchema):
    id: UUID
    organization_id: UUID
    subject_user_id: UUID
    grantee_user_id: UUID
    purpose: GrantPurpose
    scope: GrantScope
    status: GrantStatus
    active: bool
    expires_at: datetime
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]
    created_at: datetime
    updated_at: datetime


class GrantListResponse(OrganizationSchema):
    grants: list[GrantResponse] = Field(max_length=200)
