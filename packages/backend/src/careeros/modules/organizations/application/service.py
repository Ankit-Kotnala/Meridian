"""Organization tenant, invitation, membership, and grant orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from careeros.modules.organizations.domain import (
    GrantScope,
    GrantStatus,
    InvitationStatus,
    Organization,
    OrganizationAccessGrant,
    OrganizationAuditAction,
    OrganizationAuditEvent,
    OrganizationCapability,
    OrganizationConflict,
    OrganizationForbidden,
    OrganizationIdempotencyConflict,
    OrganizationIdempotencyRecord,
    OrganizationInvitation,
    OrganizationInvitationOutbox,
    OrganizationInvitationRejected,
    OrganizationMembership,
    OrganizationMembershipStatus,
    OrganizationNotFound,
    OrganizationQuotaExceeded,
    OrganizationRole,
    OrganizationStatus,
    OrganizationValidationError,
    OrganizationVersionConflict,
)

from .models import (
    AcceptOrganizationInvitation,
    CreateOrganization,
    CreateOrganizationGrant,
    GrantView,
    InvitationView,
    InviteOrganizationMember,
    OrganizationRoster,
    OrganizationView,
    RequestContext,
    UpdateOrganization,
)
from .ports import (
    AccountDirectory,
    Clock,
    EmailNormalizer,
    IdentifierFactory,
    InvitationTokenManager,
    OrganizationUnitOfWork,
    OrganizationUnitOfWorkFactory,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class OrganizationPolicy:
    invitation_ttl_seconds: int = 7 * 24 * 60 * 60
    max_organizations_per_owner: int = 10
    max_members_per_organization: int = 250
    max_active_grants_per_member: int = 100
    max_grant_lifetime_seconds: int = 366 * 24 * 60 * 60
    invitation_delivery_max_attempts: int = 5

    def __post_init__(self) -> None:
        if not 300 <= self.invitation_ttl_seconds <= 30 * 24 * 60 * 60:
            raise ValueError("organization invitation TTL is invalid")
        if not 1 <= self.max_organizations_per_owner <= 100:
            raise ValueError("organization ownership safety limit is invalid")
        if not 2 <= self.max_members_per_organization <= 10_000:
            raise ValueError("organization membership safety limit is invalid")
        if not 1 <= self.max_active_grants_per_member <= 1_000:
            raise ValueError("organization grant safety limit is invalid")
        if not 3600 <= self.max_grant_lifetime_seconds <= 2 * 366 * 24 * 60 * 60:
            raise ValueError("organization grant lifetime is invalid")
        if not 1 <= self.invitation_delivery_max_attempts <= 20:
            raise ValueError("organization invitation attempt budget is invalid")


class OrganizationService:
    """Least-privilege organization operations with explicit subject grants."""

    def __init__(
        self,
        *,
        unit_of_work: OrganizationUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        accounts: AccountDirectory,
        emails: EmailNormalizer,
        invitation_tokens: InvitationTokenManager,
        policy: OrganizationPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._accounts = accounts
        self._emails = emails
        self._tokens = invitation_tokens
        self._policy = policy or OrganizationPolicy()

    async def create_organization(
        self,
        command: CreateOrganization,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> OrganizationView:
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint({"name": command.name.strip()})
        now = self._clock.now()
        async with self._uow() as uow:
            replay = await uow.get_idempotency(
                context.actor_user_id,
                "create_organization",
                idempotency_key,
            )
            if replay is not None:
                self._assert_replay(replay, fingerprint)
                organization = await uow.get_organization(replay.resource_id)
                if organization is None:
                    raise OrganizationConflict("organization replay target is unavailable")
                membership = await uow.get_membership(
                    organization.id,
                    context.actor_user_id,
                )
                if membership is None:
                    raise OrganizationConflict("organization owner membership is unavailable")
                return OrganizationView(organization, membership)
            if (
                await uow.count_owned_organizations(context.actor_user_id)
                >= self._policy.max_organizations_per_owner
            ):
                raise OrganizationQuotaExceeded
            organization = Organization(
                id=self._ids.new(),
                name=command.name,
                created_by_user_id=context.actor_user_id,
                status=OrganizationStatus.ACTIVE,
                version=1,
                created_at=now,
                updated_at=now,
            )
            membership = OrganizationMembership(
                id=self._ids.new(),
                organization_id=organization.id,
                user_id=context.actor_user_id,
                role=OrganizationRole.OWNER,
                status=OrganizationMembershipStatus.ACTIVE,
                version=1,
                created_at=now,
                updated_at=now,
                accepted_at=now,
            )
            await uow.add_organization(organization)
            await uow.flush()
            await uow.add_membership(membership)
            await uow.flush()
            await self._record_idempotency(
                uow,
                context,
                "create_organization",
                idempotency_key,
                fingerprint,
                organization.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    organization.id,
                    context,
                    OrganizationAuditAction.CREATED,
                    "organization",
                    organization.id,
                    subject_user_id=context.actor_user_id,
                    metadata={"role": OrganizationRole.OWNER.value},
                    now=now,
                )
            )
            await uow.commit()
            return OrganizationView(organization, membership)

    async def list_organizations(self, actor_user_id: UUID) -> tuple[OrganizationView, ...]:
        async with self._uow() as uow:
            organizations = await uow.list_organizations_for_user(actor_user_id)
            views: list[OrganizationView] = []
            for organization in organizations:
                membership = await uow.get_membership(organization.id, actor_user_id)
                if (
                    membership is not None
                    and membership.status is OrganizationMembershipStatus.ACTIVE
                ):
                    views.append(OrganizationView(organization, membership))
        return tuple(views)

    async def get_organization(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
    ) -> OrganizationView:
        async with self._uow() as uow:
            organization, membership = await self._load_active(
                uow,
                organization_id,
                actor_user_id,
            )
        return OrganizationView(organization, membership)

    async def update_organization(
        self,
        organization_id: UUID,
        command: UpdateOrganization,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> OrganizationView:
        now = self._clock.now()
        async with self._uow() as uow:
            organization, membership = await self._load_active(
                uow,
                organization_id,
                context.actor_user_id,
                for_update=True,
            )
            self._require(membership, OrganizationCapability.MANAGE_ORGANIZATION)
            if organization.version != expected_version:
                raise OrganizationVersionConflict
            previous_version = organization.version
            organization.rename(command.name, now)
            await uow.save_organization(
                organization,
                expected_version=previous_version,
            )
            await uow.add_audit(
                self._audit(
                    organization.id,
                    context,
                    OrganizationAuditAction.UPDATED,
                    "organization",
                    organization.id,
                    subject_user_id=None,
                    metadata={"version": organization.version},
                    now=now,
                )
            )
            await uow.commit()
            return OrganizationView(organization, membership)

    async def roster(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
    ) -> OrganizationRoster:
        async with self._uow() as uow:
            organization, actor = await self._load_active(
                uow,
                organization_id,
                actor_user_id,
            )
            members = tuple(await uow.list_memberships(organization_id))
            if actor.role in {OrganizationRole.COACH, OrganizationRole.MEMBER}:
                members = tuple(item for item in members if item.user_id == actor_user_id)
        return OrganizationRoster(organization, members)

    async def invite_member(
        self,
        organization_id: UUID,
        command: InviteOrganizationMember,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> InvitationView:
        self._idempotency_key(idempotency_key)
        if command.role is OrganizationRole.OWNER:
            raise OrganizationValidationError("owner role cannot be invited")
        try:
            email = self._emails.normalize(command.email)
        except ValueError as exc:
            raise OrganizationValidationError("invitation email is invalid") from exc
        email_digest = self._tokens.email_digest(email)
        fingerprint = _fingerprint({"emailDigest": email_digest, "role": command.role.value})
        now = self._clock.now()
        async with self._uow() as uow:
            _organization, actor = await self._load_active(
                uow,
                organization_id,
                context.actor_user_id,
                for_update=True,
            )
            self._require(actor, OrganizationCapability.MANAGE_MEMBERS)
            replay = await uow.get_idempotency(
                context.actor_user_id,
                "invite_member",
                idempotency_key,
            )
            if replay is not None:
                self._assert_replay(replay, fingerprint)
                invitation = await uow.get_invitation(replay.resource_id)
                if invitation is None or invitation.organization_id != organization_id:
                    raise OrganizationConflict("invitation replay target is unavailable")
                return InvitationView(invitation, _delivery_status(invitation))
            if (
                await uow.count_active_members(organization_id)
                >= self._policy.max_members_per_organization
            ):
                raise OrganizationQuotaExceeded
            existing = await uow.find_open_invitation(
                organization_id,
                email_digest,
                for_update=True,
            )
            if existing is not None:
                raise OrganizationConflict("an open invitation already exists")
            invitation = OrganizationInvitation(
                id=self._ids.new(),
                organization_id=organization_id,
                invited_email_normalized=email,
                invited_email_digest=email_digest,
                role=command.role,
                token_hash=None,
                status=InvitationStatus.PENDING_DELIVERY,
                invited_by_user_id=context.actor_user_id,
                expires_at=now + timedelta(seconds=self._policy.invitation_ttl_seconds),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_invitation(invitation)
            await uow.flush()
            await uow.add_invitation_outbox(
                OrganizationInvitationOutbox(
                    id=self._ids.new(),
                    invitation_id=invitation.id,
                    organization_id=organization_id,
                    trace_id=context.trace_id,
                    attempts=0,
                    max_attempts=self._policy.invitation_delivery_max_attempts,
                    next_attempt_at=now,
                    created_at=now,
                )
            )
            await self._record_idempotency(
                uow,
                context,
                "invite_member",
                idempotency_key,
                fingerprint,
                invitation.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    organization_id,
                    context,
                    OrganizationAuditAction.INVITATION_CREATED,
                    "organization_invitation",
                    invitation.id,
                    subject_user_id=None,
                    metadata={"role": invitation.role.value},
                    now=now,
                )
            )
            await uow.commit()
            return InvitationView(invitation, "queued")

    async def accept_invitation(
        self,
        command: AcceptOrganizationInvitation,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> OrganizationView:
        self._idempotency_key(idempotency_key)
        parsed = self._tokens.parse(command.token)
        if parsed is None:
            raise OrganizationInvitationRejected
        invitation_id, secret = parsed
        fingerprint = _fingerprint({"invitationId": str(invitation_id)})
        now = self._clock.now()
        email = await self._accounts.normalized_email(context.actor_user_id)
        if email is None:
            raise OrganizationInvitationRejected
        async with self._uow() as uow:
            replay = await uow.get_idempotency(
                context.actor_user_id,
                "accept_invitation",
                idempotency_key,
            )
            if replay is not None:
                self._assert_replay(replay, fingerprint)
                organization = await uow.get_organization(replay.resource_id)
                if organization is None:
                    raise OrganizationInvitationRejected
                membership = await uow.get_membership(
                    organization.id,
                    context.actor_user_id,
                )
                if membership is None:
                    raise OrganizationInvitationRejected
                return OrganizationView(organization, membership)
            invitation = await uow.get_invitation(invitation_id, for_update=True)
            if (
                invitation is None
                or invitation.status is not InvitationStatus.PENDING
                or invitation.token_hash is None
                or invitation.expires_at <= now
                or not self._tokens.verify(invitation.token_hash, secret)
                or not self._tokens.verify_email_digest(invitation.invited_email_digest, email)
            ):
                raise OrganizationInvitationRejected
            existing = await uow.get_membership(
                invitation.organization_id,
                context.actor_user_id,
                for_update=True,
            )
            if existing is not None and existing.status is OrganizationMembershipStatus.ACTIVE:
                raise OrganizationConflict("account is already an active member")
            if (
                await uow.count_active_members(invitation.organization_id)
                >= self._policy.max_members_per_organization
            ):
                raise OrganizationQuotaExceeded
            invitation_previous = invitation.version
            invitation.accept(context.actor_user_id, now)
            if existing is None:
                membership = OrganizationMembership(
                    id=self._ids.new(),
                    organization_id=invitation.organization_id,
                    user_id=context.actor_user_id,
                    role=invitation.role,
                    status=OrganizationMembershipStatus.ACTIVE,
                    version=1,
                    created_at=now,
                    updated_at=now,
                    accepted_at=now,
                )
                await uow.add_membership(membership)
            else:
                previous = existing.version
                existing.role = invitation.role
                existing.status = OrganizationMembershipStatus.ACTIVE
                existing.accepted_at = now
                existing.suspended_at = None
                existing.left_at = None
                existing.version += 1
                existing.updated_at = now
                existing.__post_init__()
                await uow.save_membership(existing, expected_version=previous)
                membership = existing
            await uow.save_invitation(
                invitation,
                expected_version=invitation_previous,
            )
            await self._record_idempotency(
                uow,
                context,
                "accept_invitation",
                idempotency_key,
                fingerprint,
                invitation.organization_id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    invitation.organization_id,
                    context,
                    OrganizationAuditAction.INVITATION_ACCEPTED,
                    "organization_membership",
                    membership.id,
                    subject_user_id=context.actor_user_id,
                    metadata={"role": membership.role.value},
                    now=now,
                )
            )
            organization = await uow.get_organization(invitation.organization_id)
            if organization is None:
                raise OrganizationInvitationRejected
            await uow.commit()
            return OrganizationView(organization, membership)

    async def suspend_member(
        self,
        organization_id: UUID,
        member_user_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> OrganizationMembership:
        now = self._clock.now()
        async with self._uow() as uow:
            _organization, actor = await self._load_active(
                uow,
                organization_id,
                context.actor_user_id,
                for_update=True,
            )
            self._require(actor, OrganizationCapability.MANAGE_MEMBERS)
            member = await uow.get_membership(
                organization_id,
                member_user_id,
                for_update=True,
            )
            if member is None:
                raise OrganizationNotFound
            if member.version != expected_version:
                raise OrganizationVersionConflict
            previous = member.version
            member.suspend(now)
            await uow.save_membership(member, expected_version=previous)
            await uow.add_audit(
                self._audit(
                    organization_id,
                    context,
                    OrganizationAuditAction.MEMBER_SUSPENDED,
                    "organization_membership",
                    member.id,
                    subject_user_id=member.user_id,
                    metadata={"role": member.role.value},
                    now=now,
                )
            )
            await uow.commit()
            return member

    async def create_grant(
        self,
        organization_id: UUID,
        command: CreateOrganizationGrant,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> GrantView:
        self._idempotency_key(idempotency_key)
        now = self._clock.now()
        if (
            not now
            < command.expires_at
            <= now + timedelta(seconds=self._policy.max_grant_lifetime_seconds)
        ):
            raise OrganizationValidationError("grant expiry is out of range")
        fingerprint = _fingerprint(
            {
                "organizationId": str(organization_id),
                "granteeUserId": str(command.grantee_user_id),
                "purpose": command.purpose.value,
                "scope": command.scope.value,
                "expiresAt": command.expires_at.isoformat(),
            }
        )
        async with self._uow() as uow:
            _organization, subject = await self._load_active(
                uow,
                organization_id,
                context.actor_user_id,
                for_update=True,
            )
            if subject.role not in {OrganizationRole.MEMBER, OrganizationRole.OWNER}:
                raise OrganizationForbidden
            replay = await uow.get_idempotency(
                context.actor_user_id,
                "create_grant",
                idempotency_key,
            )
            if replay is not None:
                self._assert_replay(replay, fingerprint)
                existing_replay = await uow.get_grant(
                    organization_id,
                    replay.resource_id,
                )
                if existing_replay is None:
                    raise OrganizationConflict("grant replay target is unavailable")
                return GrantView(existing_replay, existing_replay.is_active(now))
            grantee = await uow.get_membership(
                organization_id,
                command.grantee_user_id,
                for_update=True,
            )
            if (
                grantee is None
                or grantee.status is not OrganizationMembershipStatus.ACTIVE
                or grantee.role not in {OrganizationRole.COACH, OrganizationRole.ADMIN}
            ):
                raise OrganizationNotFound
            existing = await uow.find_active_grant(
                organization_id,
                context.actor_user_id,
                command.grantee_user_id,
                command.scope,
                for_update=True,
            )
            if existing is not None and existing.is_active(now):
                raise OrganizationConflict("an active grant already exists")
            if (
                await uow.count_active_grants(
                    organization_id,
                    context.actor_user_id,
                )
                >= self._policy.max_active_grants_per_member
            ):
                raise OrganizationQuotaExceeded
            grant = OrganizationAccessGrant(
                id=self._ids.new(),
                organization_id=organization_id,
                subject_user_id=context.actor_user_id,
                grantee_user_id=command.grantee_user_id,
                purpose=command.purpose,
                scope=command.scope,
                status=GrantStatus.ACTIVE,
                granted_by_user_id=context.actor_user_id,
                expires_at=command.expires_at,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_grant(grant)
            await self._record_idempotency(
                uow,
                context,
                "create_grant",
                idempotency_key,
                fingerprint,
                grant.id,
                now,
            )
            await uow.add_audit(
                self._audit(
                    organization_id,
                    context,
                    OrganizationAuditAction.GRANT_CREATED,
                    "organization_access_grant",
                    grant.id,
                    subject_user_id=context.actor_user_id,
                    metadata={
                        "purpose": grant.purpose.value,
                        "scope": grant.scope.value,
                    },
                    now=now,
                )
            )
            await uow.commit()
            return GrantView(grant, True)

    async def list_grants(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
    ) -> tuple[GrantView, ...]:
        now = self._clock.now()
        async with self._uow() as uow:
            await self._load_active(uow, organization_id, actor_user_id)
            grants = await uow.list_grants_for_user(organization_id, actor_user_id)
        return tuple(GrantView(grant, grant.is_active(now)) for grant in grants)

    async def revoke_grant(
        self,
        organization_id: UUID,
        grant_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> GrantView:
        now = self._clock.now()
        async with self._uow() as uow:
            _organization, actor = await self._load_active(
                uow,
                organization_id,
                context.actor_user_id,
                for_update=True,
            )
            grant = await uow.get_grant(organization_id, grant_id, for_update=True)
            if grant is None:
                raise OrganizationNotFound
            if grant.subject_user_id != context.actor_user_id and not actor.has(
                OrganizationCapability.MANAGE_GRANTS
            ):
                raise OrganizationNotFound
            if grant.version != expected_version:
                raise OrganizationVersionConflict
            previous = grant.version
            grant.revoke(now)
            await uow.save_grant(grant, expected_version=previous)
            await uow.add_audit(
                self._audit(
                    organization_id,
                    context,
                    OrganizationAuditAction.GRANT_REVOKED,
                    "organization_access_grant",
                    grant.id,
                    subject_user_id=grant.subject_user_id,
                    metadata={"scope": grant.scope.value},
                    now=now,
                )
            )
            await uow.commit()
            return GrantView(grant, False)

    async def authorize_delegated_scope(
        self,
        organization_id: UUID,
        *,
        subject_user_id: UUID,
        grantee_user_id: UUID,
        scope: GrantScope,
    ) -> bool:
        now = self._clock.now()
        async with self._uow() as uow:
            grantee = await uow.get_membership(organization_id, grantee_user_id)
            subject = await uow.get_membership(organization_id, subject_user_id)
            if (
                grantee is None
                or subject is None
                or grantee.status is not OrganizationMembershipStatus.ACTIVE
                or subject.status is not OrganizationMembershipStatus.ACTIVE
                or grantee.role not in {OrganizationRole.COACH, OrganizationRole.ADMIN}
            ):
                return False
            grant = await uow.find_active_grant(
                organization_id,
                subject_user_id,
                grantee_user_id,
                scope,
            )
        return grant is not None and grant.is_active(now)

    async def _load_active(
        self,
        uow: OrganizationUnitOfWork,
        organization_id: UUID,
        actor_user_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[Organization, OrganizationMembership]:
        organization = await uow.get_organization(
            organization_id,
            for_update=for_update,
        )
        membership = await uow.get_membership(
            organization_id,
            actor_user_id,
            for_update=for_update,
        )
        if (
            organization is None
            or organization.status is not OrganizationStatus.ACTIVE
            or membership is None
            or membership.status is not OrganizationMembershipStatus.ACTIVE
        ):
            raise OrganizationNotFound
        return organization, membership

    def _require(
        self,
        membership: OrganizationMembership,
        capability: OrganizationCapability,
    ) -> None:
        if not membership.has(capability):
            raise OrganizationForbidden

    def _idempotency_key(self, value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise OrganizationValidationError("idempotency key is invalid")

    def _assert_replay(
        self,
        record: OrganizationIdempotencyRecord,
        fingerprint: str,
    ) -> None:
        if record.request_fingerprint != fingerprint:
            raise OrganizationIdempotencyConflict

    async def _record_idempotency(
        self,
        uow: OrganizationUnitOfWork,
        context: RequestContext,
        operation: str,
        idempotency_key: str,
        fingerprint: str,
        resource_id: UUID,
        now: datetime,
    ) -> None:
        await uow.add_idempotency(
            OrganizationIdempotencyRecord(
                id=self._ids.new(),
                actor_user_id=context.actor_user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                resource_id=resource_id,
                created_at=now,
            )
        )

    def _audit(
        self,
        organization_id: UUID,
        context: RequestContext,
        action: OrganizationAuditAction,
        target_type: str,
        target_id: UUID | None,
        *,
        subject_user_id: UUID | None,
        metadata: dict[str, object],
        now: datetime,
    ) -> OrganizationAuditEvent:
        return OrganizationAuditEvent(
            id=self._ids.new(),
            organization_id=organization_id,
            actor_user_id=context.actor_user_id,
            subject_user_id=subject_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            metadata=metadata,
            occurred_at=now,
        )


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _delivery_status(invitation: OrganizationInvitation) -> str:
    return {
        InvitationStatus.PENDING_DELIVERY: "queued",
        InvitationStatus.PENDING: "delivered",
        InvitationStatus.DELIVERY_DEAD_LETTERED: "failed",
    }.get(invitation.status, invitation.status.value)
