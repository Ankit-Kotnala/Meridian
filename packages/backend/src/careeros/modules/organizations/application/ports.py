"""Inward-facing organization tenancy ports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.organizations.domain import (
    GrantScope,
    Organization,
    OrganizationAccessGrant,
    OrganizationAuditEvent,
    OrganizationIdempotencyRecord,
    OrganizationInvitation,
    OrganizationInvitationOutbox,
    OrganizationMembership,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class AccountDirectory(Protocol):
    async def normalized_email(self, user_id: UUID) -> str | None: ...


class EmailNormalizer(Protocol):
    def normalize(self, value: str) -> str: ...


class InvitationTokenManager(Protocol):
    def issue_for_id(self, invitation_id: UUID) -> tuple[str, str]: ...

    def issue_for_delivery(self, invitation_id: UUID) -> tuple[str, str]: ...

    def parse(self, encoded: str) -> tuple[UUID, str] | None: ...

    def digest(self, secret: str) -> str: ...

    def verify(self, expected_digest: str, secret: str) -> bool: ...

    def email_digest(self, normalized_email: str) -> str: ...


class OrganizationUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def count_owned_organizations(self, user_id: UUID) -> int: ...

    async def add_organization(self, organization: Organization) -> None: ...

    async def get_organization(
        self,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> Organization | None: ...

    async def save_organization(
        self,
        organization: Organization,
        *,
        expected_version: int,
    ) -> None: ...

    async def list_organizations_for_user(self, user_id: UUID) -> list[Organization]: ...

    async def add_membership(self, membership: OrganizationMembership) -> None: ...

    async def get_membership(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationMembership | None: ...

    async def save_membership(
        self,
        membership: OrganizationMembership,
        *,
        expected_version: int,
    ) -> None: ...

    async def list_memberships(
        self,
        organization_id: UUID,
    ) -> list[OrganizationMembership]: ...

    async def count_active_members(self, organization_id: UUID) -> int: ...

    async def get_invitation(
        self,
        invitation_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None: ...

    async def find_open_invitation(
        self,
        organization_id: UUID,
        email_digest: str,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None: ...

    async def add_invitation(self, invitation: OrganizationInvitation) -> None: ...

    async def save_invitation(
        self,
        invitation: OrganizationInvitation,
        *,
        expected_version: int,
    ) -> None: ...

    async def add_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
    ) -> None: ...

    async def claim_invitation_outbox(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[OrganizationInvitationOutbox]: ...

    async def get_invitation_outbox(
        self,
        outbox_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitationOutbox | None: ...

    async def save_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
        *,
        expected_lease_token: UUID,
    ) -> None: ...

    async def add_grant(self, grant: OrganizationAccessGrant) -> None: ...

    async def get_grant(
        self,
        organization_id: UUID,
        grant_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None: ...

    async def find_active_grant(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
        grantee_user_id: UUID,
        scope: GrantScope,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None: ...

    async def list_grants_for_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[OrganizationAccessGrant]: ...

    async def count_active_grants(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
    ) -> int: ...

    async def save_grant(
        self,
        grant: OrganizationAccessGrant,
        *,
        expected_version: int,
    ) -> None: ...

    async def get_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> OrganizationIdempotencyRecord | None: ...

    async def add_idempotency(
        self,
        record: OrganizationIdempotencyRecord,
    ) -> None: ...

    async def add_audit(self, event: OrganizationAuditEvent) -> None: ...

    async def flush(self) -> None: ...

    async def commit(self) -> None: ...


OrganizationUnitOfWorkFactory = Callable[[], OrganizationUnitOfWork]
