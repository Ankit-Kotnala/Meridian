"""Durable, fenced organization invitation delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careeros.modules.organizations.domain import (
    InvitationStatus,
    OrganizationAuditAction,
    OrganizationAuditEvent,
    OrganizationInvitation,
    OrganizationInvitationOutbox,
    OrganizationValidationError,
)

from .ports import (
    Clock,
    IdentifierFactory,
    InvitationTokenManager,
    OrganizationUnitOfWorkFactory,
)

_DELIVERY_ERROR = "invitation_delivery_unavailable"


@dataclass(frozen=True, slots=True)
class InvitationDeliveryMessage:
    """Sensitive delivery material that must never be logged or persisted."""

    invitation_id: UUID
    organization_name: str
    recipient: str = field(repr=False)
    token: str = field(repr=False)


class InvitationSender(Protocol):
    async def send(self, message: InvitationDeliveryMessage) -> None: ...


@dataclass(frozen=True, slots=True)
class InvitationDeliveryBatchResult:
    claimed: int
    delivered: int
    cancelled: int
    deferred: int
    dead_lettered: int


class OrganizationInvitationDeliveryProcessor:
    """Claim and deliver a bounded invitation batch with database fencing."""

    def __init__(
        self,
        *,
        unit_of_work: OrganizationUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        invitation_tokens: InvitationTokenManager,
        sender: InvitationSender,
        lease_seconds: int = 30,
        retry_base_seconds: int = 30,
    ) -> None:
        if not 5 <= lease_seconds <= 900:
            raise ValueError("invitation lease must be between 5 and 900 seconds")
        if not 1 <= retry_base_seconds <= 3_600:
            raise ValueError("invitation retry delay must be between 1 and 3600 seconds")
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._tokens = invitation_tokens
        self._sender = sender
        self._lease_seconds = lease_seconds
        self._retry_base_seconds = retry_base_seconds

    async def process_due(self, limit: int) -> InvitationDeliveryBatchResult:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("invitation delivery limit must be between 1 and 500")
        now = self._clock.now()
        lease_token = self._ids.new()
        async with self._unit_of_work() as uow:
            claimed = await uow.claim_invitation_outbox(
                limit=limit,
                lease_token=lease_token,
                now=now,
                lease_seconds=self._lease_seconds,
            )
            await uow.commit()

        delivered = cancelled = deferred = dead_lettered = 0
        for entry in claimed:
            outcome = await self._process_one(entry.id, lease_token)
            if outcome == "delivered":
                delivered += 1
            elif outcome == "cancelled":
                cancelled += 1
            elif outcome == "dead_lettered":
                dead_lettered += 1
            else:
                deferred += 1
        return InvitationDeliveryBatchResult(
            claimed=len(claimed),
            delivered=delivered,
            cancelled=cancelled,
            deferred=deferred,
            dead_lettered=dead_lettered,
        )

    async def _process_one(self, outbox_id: UUID, lease_token: UUID) -> str:
        now = self._clock.now()
        try:
            async with self._unit_of_work() as uow:
                outbox = await uow.get_invitation_outbox(outbox_id, for_update=True)
                if outbox is None:
                    return "cancelled"
                invitation = await uow.get_invitation(outbox.invitation_id, for_update=True)
                organization = await uow.get_organization(
                    outbox.organization_id,
                    for_update=True,
                )
                if invitation is None or organization is None:
                    outbox.cancel(lease_token, now)
                    await uow.save_invitation_outbox(
                        outbox,
                        expected_lease_token=lease_token,
                    )
                    await uow.commit()
                    return "cancelled"
                if invitation.status not in {
                    InvitationStatus.PENDING_DELIVERY,
                    InvitationStatus.PENDING,
                }:
                    outbox.cancel(lease_token, now)
                    await uow.save_invitation_outbox(
                        outbox,
                        expected_lease_token=lease_token,
                    )
                    await uow.commit()
                    return "cancelled"
                if invitation.expires_at <= now:
                    previous_version = invitation.version
                    invitation.expire(now)
                    outbox.cancel(lease_token, now)
                    await uow.save_invitation(
                        invitation,
                        expected_version=previous_version,
                    )
                    await uow.save_invitation_outbox(
                        outbox,
                        expected_lease_token=lease_token,
                    )
                    await uow.add_audit(
                        self._audit(
                            invitation,
                            outbox,
                            OrganizationAuditAction.INVITATION_EXPIRED,
                            now,
                        )
                    )
                    await uow.commit()
                    return "cancelled"

                token, token_hash = self._tokens.issue_for_delivery(invitation.id)
                if invitation.token_hash is not None and invitation.token_hash != token_hash:
                    raise OrganizationValidationError(
                        "stored invitation token does not match delivery credential"
                    )
                await self._sender.send(
                    InvitationDeliveryMessage(
                        invitation_id=invitation.id,
                        organization_name=organization.name,
                        recipient=invitation.invited_email_normalized,
                        token=token,
                    )
                )
                if invitation.status is InvitationStatus.PENDING_DELIVERY:
                    previous_version = invitation.version
                    invitation.mark_delivered(token_hash, now)
                    await uow.save_invitation(
                        invitation,
                        expected_version=previous_version,
                    )
                outbox.complete(lease_token, now)
                await uow.save_invitation_outbox(
                    outbox,
                    expected_lease_token=lease_token,
                )
                await uow.add_audit(
                    self._audit(
                        invitation,
                        outbox,
                        OrganizationAuditAction.INVITATION_DELIVERED,
                        now,
                    )
                )
                await uow.commit()
                return "delivered"
        except Exception:
            return await self._record_failure(outbox_id, lease_token)

    async def _record_failure(self, outbox_id: UUID, lease_token: UUID) -> str:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            outbox = await uow.get_invitation_outbox(outbox_id, for_update=True)
            if outbox is None or outbox.terminal:
                return "cancelled"
            invitation = await uow.get_invitation(outbox.invitation_id, for_update=True)
            dead_lettered = outbox.fail(
                lease_token,
                now,
                _DELIVERY_ERROR,
                self._retry_base_seconds,
            )
            if dead_lettered and invitation is not None:
                previous_version = invitation.version
                invitation.mark_delivery_dead_lettered(now)
                await uow.save_invitation(
                    invitation,
                    expected_version=previous_version,
                )
            await uow.save_invitation_outbox(
                outbox,
                expected_lease_token=lease_token,
            )
            if invitation is not None:
                await uow.add_audit(
                    self._audit(
                        invitation,
                        outbox,
                        OrganizationAuditAction.INVITATION_DELIVERY_FAILED,
                        now,
                    )
                )
            await uow.commit()
            return "dead_lettered" if dead_lettered else "deferred"

    def _audit(
        self,
        invitation: OrganizationInvitation,
        outbox: OrganizationInvitationOutbox,
        action: OrganizationAuditAction,
        now: datetime,
    ) -> OrganizationAuditEvent:
        return OrganizationAuditEvent(
            id=self._ids.new(),
            organization_id=invitation.organization_id,
            actor_user_id=None,
            subject_user_id=None,
            action=action,
            target_type="organization_invitation",
            target_id=invitation.id,
            request_id=f"worker:{outbox.id}",
            trace_id=outbox.trace_id,
            occurred_at=now,
            metadata={
                "attempt": outbox.attempts,
                "terminal": outbox.terminal,
            },
        )
