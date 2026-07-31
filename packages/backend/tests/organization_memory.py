"""Explicitly fictional in-memory organization adapters for focused tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from careeros.modules.organizations.application.ports import OrganizationUnitOfWork
from careeros.modules.organizations.domain import (
    GrantScope,
    GrantStatus,
    InvitationStatus,
    Organization,
    OrganizationAccessGrant,
    OrganizationAuditEvent,
    OrganizationIdempotencyRecord,
    OrganizationInvitation,
    OrganizationInvitationOutbox,
    OrganizationMembership,
    OrganizationMembershipStatus,
    OrganizationRole,
    OrganizationStatus,
)

NOW = datetime(2026, 7, 26, 20, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequentialIds:
    def __init__(self) -> None:
        self._value = 500

    def new(self) -> UUID:
        self._value += 1
        return UUID(int=self._value)


class MemoryAccounts:
    def __init__(self) -> None:
        self.emails: dict[UUID, str] = {}

    async def normalized_email(self, user_id: UUID) -> str | None:
        return self.emails.get(user_id)


class LowercaseEmails:
    def normalize(self, value: str) -> str:
        normalized = value.strip().casefold()
        if "@" not in normalized or len(normalized) > 254:
            raise ValueError("fictional email is invalid")
        return normalized


class MemoryOrganizations:
    def __init__(self) -> None:
        self.organizations: dict[UUID, Organization] = {}
        self.memberships: dict[tuple[UUID, UUID], OrganizationMembership] = {}
        self.invitations: dict[UUID, OrganizationInvitation] = {}
        self.outboxes: dict[UUID, OrganizationInvitationOutbox] = {}
        self.grants: dict[UUID, OrganizationAccessGrant] = {}
        self.idempotency: dict[
            tuple[UUID, str, str],
            OrganizationIdempotencyRecord,
        ] = {}
        self.audits: list[OrganizationAuditEvent] = []

    def __call__(self) -> OrganizationUnitOfWork:
        return self

    async def __aenter__(self) -> MemoryOrganizations:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def count_owned_organizations(self, user_id: UUID) -> int:
        return sum(
            item.user_id == user_id
            and item.role is OrganizationRole.OWNER
            and item.status is OrganizationMembershipStatus.ACTIVE
            for item in self.memberships.values()
        )

    async def add_organization(self, organization: Organization) -> None:
        self.organizations[organization.id] = organization

    async def get_organization(
        self,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> Organization | None:
        del for_update
        return self.organizations.get(organization_id)

    async def save_organization(
        self,
        organization: Organization,
        *,
        expected_version: int,
    ) -> None:
        del expected_version
        self.organizations[organization.id] = organization

    async def list_organizations_for_user(self, user_id: UUID) -> list[Organization]:
        organization_ids = {
            membership.organization_id
            for membership in self.memberships.values()
            if membership.user_id == user_id
            and membership.status is OrganizationMembershipStatus.ACTIVE
        }
        return sorted(
            (
                organization
                for organization_id in organization_ids
                if (organization := self.organizations.get(organization_id)) is not None
                and organization.status is OrganizationStatus.ACTIVE
            ),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )

    async def add_membership(self, membership: OrganizationMembership) -> None:
        self.memberships[(membership.organization_id, membership.user_id)] = membership

    async def get_membership(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationMembership | None:
        del for_update
        return self.memberships.get((organization_id, user_id))

    async def save_membership(
        self,
        membership: OrganizationMembership,
        *,
        expected_version: int,
    ) -> None:
        del expected_version
        self.memberships[(membership.organization_id, membership.user_id)] = membership

    async def list_memberships(
        self,
        organization_id: UUID,
    ) -> list[OrganizationMembership]:
        return [
            item
            for item in self.memberships.values()
            if item.organization_id == organization_id
            and item.status is not OrganizationMembershipStatus.LEFT
        ]

    async def count_active_members(self, organization_id: UUID) -> int:
        return sum(
            item.organization_id == organization_id
            and item.status is OrganizationMembershipStatus.ACTIVE
            for item in self.memberships.values()
        )

    async def get_invitation(
        self,
        invitation_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None:
        del for_update
        return self.invitations.get(invitation_id)

    async def find_open_invitation(
        self,
        organization_id: UUID,
        email_digest: str,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None:
        del for_update
        return next(
            (
                item
                for item in self.invitations.values()
                if item.organization_id == organization_id
                and item.invited_email_digest == email_digest
                and item.status
                in {
                    InvitationStatus.PENDING_DELIVERY,
                    InvitationStatus.PENDING,
                    InvitationStatus.DELIVERY_DEAD_LETTERED,
                }
            ),
            None,
        )

    async def add_invitation(self, invitation: OrganizationInvitation) -> None:
        self.invitations[invitation.id] = invitation

    async def save_invitation(
        self,
        invitation: OrganizationInvitation,
        *,
        expected_version: int,
    ) -> None:
        del expected_version
        self.invitations[invitation.id] = invitation

    async def add_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
    ) -> None:
        self.outboxes[outbox.invitation_id] = outbox

    async def claim_invitation_outbox(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[OrganizationInvitationOutbox]:
        claimed: list[OrganizationInvitationOutbox] = []
        for item in sorted(
            self.outboxes.values(),
            key=lambda outbox: (outbox.next_attempt_at, outbox.created_at, outbox.id),
        ):
            if len(claimed) >= limit:
                break
            if (
                not item.terminal
                and item.next_attempt_at <= now
                and (item.lease_expires_at is None or item.lease_expires_at <= now)
            ):
                item.claim(lease_token, now, lease_seconds)
                claimed.append(item)
        return claimed

    async def get_invitation_outbox(
        self,
        outbox_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitationOutbox | None:
        del for_update
        return next((item for item in self.outboxes.values() if item.id == outbox_id), None)

    async def save_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
        *,
        expected_lease_token: UUID,
    ) -> None:
        del expected_lease_token
        self.outboxes[outbox.invitation_id] = outbox

    async def add_grant(self, grant: OrganizationAccessGrant) -> None:
        self.grants[grant.id] = grant

    async def get_grant(
        self,
        organization_id: UUID,
        grant_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None:
        del for_update
        grant = self.grants.get(grant_id)
        return grant if grant is not None and grant.organization_id == organization_id else None

    async def find_active_grant(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
        grantee_user_id: UUID,
        scope: GrantScope,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None:
        del for_update
        return next(
            (
                item
                for item in self.grants.values()
                if item.organization_id == organization_id
                and item.subject_user_id == subject_user_id
                and item.grantee_user_id == grantee_user_id
                and item.scope is scope
                and item.status is GrantStatus.ACTIVE
            ),
            None,
        )

    async def list_grants_for_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[OrganizationAccessGrant]:
        return [
            item
            for item in self.grants.values()
            if item.organization_id == organization_id
            and user_id in {item.subject_user_id, item.grantee_user_id}
        ]

    async def count_active_grants(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
    ) -> int:
        return sum(
            item.organization_id == organization_id
            and item.subject_user_id == subject_user_id
            and item.status is GrantStatus.ACTIVE
            for item in self.grants.values()
        )

    async def save_grant(
        self,
        grant: OrganizationAccessGrant,
        *,
        expected_version: int,
    ) -> None:
        del expected_version
        self.grants[grant.id] = grant

    async def get_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> OrganizationIdempotencyRecord | None:
        return self.idempotency.get((actor_user_id, operation, idempotency_key))

    async def add_idempotency(
        self,
        record: OrganizationIdempotencyRecord,
    ) -> None:
        self.idempotency[(record.actor_user_id, record.operation, record.idempotency_key)] = record

    async def add_audit(self, event: OrganizationAuditEvent) -> None:
        self.audits.append(event)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None
