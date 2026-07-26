"""Durable organization invitation delivery policy tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from careeros.modules.organizations.application import (
    CreateOrganization,
    InvitationDeliveryMessage,
    InviteOrganizationMember,
    OrganizationInvitationDeliveryProcessor,
    OrganizationPolicy,
    OrganizationService,
    RequestContext,
)
from careeros.modules.organizations.domain import InvitationStatus, OrganizationRole
from careeros.modules.organizations.infrastructure import HmacOrganizationInvitationManager
from organization_memory import (
    NOW,
    LowercaseEmails,
    MemoryAccounts,
    MemoryOrganizations,
    SequentialIds,
)

_SECRET = "fictional-durable-invitation-secret-at-least-32-bytes"  # noqa: S105


@dataclass(slots=True)
class MutableClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


class RecordingSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[InvitationDeliveryMessage] = []

    async def send(self, message: InvitationDeliveryMessage) -> None:
        if self.fail:
            raise RuntimeError("fictional SMTP outage")
        self.messages.append(message)


async def _queued_invitation(
    state: MemoryOrganizations,
    clock: MutableClock,
    ids: SequentialIds,
    tokens: HmacOrganizationInvitationManager,
    *,
    max_attempts: int = 5,
) -> UUID:
    owner_id = uuid4()
    service = OrganizationService(
        unit_of_work=state,
        clock=clock,
        identifiers=ids,
        accounts=MemoryAccounts(),
        emails=LowercaseEmails(),
        invitation_tokens=tokens,
        policy=OrganizationPolicy(invitation_delivery_max_attempts=max_attempts),
    )
    context = RequestContext(
        actor_user_id=owner_id,
        request_id="fictional-invitation-delivery-request",
        trace_id="fictional-invitation-delivery-trace",
    )
    organization = await service.create_organization(
        CreateOrganization(name="Fictional Career Studio"),
        idempotency_key="fictional-create-organization",
        context=context,
    )
    invitation = await service.invite_member(
        organization.organization.id,
        InviteOrganizationMember(
            email="coach@example.test",
            role=OrganizationRole.COACH,
        ),
        idempotency_key="fictional-invite-coach",
        context=context,
    )
    return invitation.invitation.id


@pytest.mark.asyncio
async def test_delivery_is_fenced_replay_safe_and_redacts_credential_repr() -> None:
    state = MemoryOrganizations()
    clock = MutableClock()
    ids = SequentialIds()
    tokens = HmacOrganizationInvitationManager(_SECRET)
    invitation_id = await _queued_invitation(state, clock, ids, tokens)
    sender = RecordingSender()
    processor = OrganizationInvitationDeliveryProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=ids,
        invitation_tokens=tokens,
        sender=sender,
    )

    result = await processor.process_due(10)

    assert result.claimed == result.delivered == 1
    assert result.cancelled == result.deferred == result.dead_lettered == 0
    assert state.invitations[invitation_id].status is InvitationStatus.PENDING
    assert state.outboxes[invitation_id].published_at == NOW
    assert len(sender.messages) == 1
    message = sender.messages[0]
    assert message.token == tokens.issue_for_delivery(invitation_id)[0]
    assert "coach@example.test" not in repr(message)
    assert message.token not in repr(message)

    replay = await processor.process_due(10)
    assert replay.claimed == 0
    assert len(sender.messages) == 1


@pytest.mark.asyncio
async def test_exhausted_delivery_dead_letters_without_exposing_provider_error() -> None:
    state = MemoryOrganizations()
    clock = MutableClock()
    ids = SequentialIds()
    tokens = HmacOrganizationInvitationManager(_SECRET)
    invitation_id = await _queued_invitation(
        state,
        clock,
        ids,
        tokens,
        max_attempts=1,
    )
    processor = OrganizationInvitationDeliveryProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=ids,
        invitation_tokens=tokens,
        sender=RecordingSender(fail=True),
    )

    result = await processor.process_due(1)

    assert result.claimed == result.dead_lettered == 1
    assert state.invitations[invitation_id].status is InvitationStatus.DELIVERY_DEAD_LETTERED
    outbox = state.outboxes[invitation_id]
    assert outbox.last_error_code == "invitation_delivery_unavailable"
    assert outbox.dead_lettered_at == NOW


def test_delivery_token_is_stable_and_context_separated() -> None:
    manager = HmacOrganizationInvitationManager(_SECRET)
    invitation_id = uuid4()

    first = manager.issue_for_delivery(invitation_id)
    second = manager.issue_for_delivery(invitation_id)
    random_token = manager.issue_for_id(invitation_id)

    assert first == second
    assert first != random_token
    parsed = manager.parse(first[0])
    assert parsed is not None
    assert parsed[0] == invitation_id
    assert manager.verify(first[1], parsed[1])
