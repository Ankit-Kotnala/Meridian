"""Organization role, invitation, grant, and denial tests."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from careeros.modules.organizations.application import (
    AcceptOrganizationInvitation,
    CreateOrganization,
    CreateOrganizationGrant,
    InviteOrganizationMember,
    OrganizationService,
    RequestContext,
    UpdateOrganization,
)
from careeros.modules.organizations.domain import (
    GrantPurpose,
    GrantScope,
    OrganizationForbidden,
    OrganizationIdempotencyConflict,
    OrganizationInvitationRejected,
    OrganizationNotFound,
    OrganizationRole,
    OrganizationVersionConflict,
)
from careeros.modules.organizations.infrastructure import HmacOrganizationInvitationManager
from organization_memory import (
    NOW,
    FixedClock,
    LowercaseEmails,
    MemoryAccounts,
    MemoryOrganizations,
    SequentialIds,
)

_SECRET = "fictional-organization-invitation-secret-at-least-32-bytes"  # noqa: S105  # gitleaks:allow


def _context(user_id: UUID) -> RequestContext:
    return RequestContext(
        actor_user_id=user_id,
        request_id=f"organization-request-{user_id.hex[:8]}",
        trace_id=f"organization-trace-{user_id.hex[:8]}",
    )


def _service(
    state: MemoryOrganizations,
    accounts: MemoryAccounts,
) -> tuple[OrganizationService, HmacOrganizationInvitationManager]:
    tokens = HmacOrganizationInvitationManager(_SECRET)
    return (
        OrganizationService(
            unit_of_work=state,
            clock=FixedClock(),
            identifiers=SequentialIds(),
            accounts=accounts,
            emails=LowercaseEmails(),
            invitation_tokens=tokens,
        ),
        tokens,
    )


@pytest.mark.asyncio
async def test_organization_creation_is_owner_scoped_versioned_and_idempotent() -> None:
    owner_id = uuid4()
    outsider_id = uuid4()
    state = MemoryOrganizations()
    service, _tokens = _service(state, MemoryAccounts())

    first = await service.create_organization(
        CreateOrganization("Fictional Career Studio"),
        idempotency_key="organization-create-test",
        context=_context(owner_id),
    )
    replay = await service.create_organization(
        CreateOrganization("Fictional Career Studio"),
        idempotency_key="organization-create-test",
        context=_context(owner_id),
    )

    assert replay.organization.id == first.organization.id
    assert first.membership.role is OrganizationRole.OWNER
    assert len(state.organizations) == 1
    assert len(state.audits) == 1
    assert await service.list_organizations(outsider_id) == ()
    with pytest.raises(OrganizationNotFound):
        await service.get_organization(first.organization.id, outsider_id)
    with pytest.raises(OrganizationIdempotencyConflict):
        await service.create_organization(
            CreateOrganization("Different fictional studio"),
            idempotency_key="organization-create-test",
            context=_context(owner_id),
        )

    updated = await service.update_organization(
        first.organization.id,
        UpdateOrganization("Fictional Career Collective"),
        expected_version=1,
        context=_context(owner_id),
    )
    assert updated.organization.version == 2
    with pytest.raises(OrganizationVersionConflict):
        await service.update_organization(
            first.organization.id,
            UpdateOrganization("Another name"),
            expected_version=1,
            context=_context(owner_id),
        )


@pytest.mark.asyncio
async def test_invitation_acceptance_binds_exact_active_account_without_disclosure() -> None:
    owner_id = uuid4()
    coach_id = uuid4()
    wrong_account_id = uuid4()
    accounts = MemoryAccounts()
    accounts.emails[coach_id] = "coach@example.test"
    accounts.emails[wrong_account_id] = "other@example.test"
    state = MemoryOrganizations()
    service, tokens = _service(state, accounts)
    organization = await service.create_organization(
        CreateOrganization("Fictional Coaching Organization"),
        idempotency_key="organization-owner-create",
        context=_context(owner_id),
    )

    queued = await service.invite_member(
        organization.organization.id,
        InviteOrganizationMember("Coach@Example.Test", OrganizationRole.COACH),
        idempotency_key="organization-invite-coach",
        context=_context(owner_id),
    )
    assert queued.delivery_status == "queued"
    assert queued.invitation.token_hash is None
    assert queued.invitation.id in state.outboxes
    token, token_hash = tokens.issue_for_id(queued.invitation.id)
    queued.invitation.mark_delivered(token_hash, NOW)

    with pytest.raises(OrganizationInvitationRejected):
        await service.accept_invitation(
            AcceptOrganizationInvitation(token),
            idempotency_key="organization-accept-wrong",
            context=_context(wrong_account_id),
        )
    accepted = await service.accept_invitation(
        AcceptOrganizationInvitation(token),
        idempotency_key="organization-accept-coach",
        context=_context(coach_id),
    )
    assert accepted.membership.role is OrganizationRole.COACH
    assert (
        await service.authorize_delegated_scope(
            organization.organization.id,
            subject_user_id=owner_id,
            grantee_user_id=coach_id,
            scope=GrantScope.CAREER_PROFILE_SUMMARY,
        )
        is False
    )

    coach_roster = await service.roster(organization.organization.id, coach_id)
    assert [member.user_id for member in coach_roster.members] == [coach_id]
    with pytest.raises(OrganizationForbidden):
        await service.invite_member(
            organization.organization.id,
            InviteOrganizationMember("member@example.test", OrganizationRole.MEMBER),
            idempotency_key="organization-coach-invite",
            context=_context(coach_id),
        )


@pytest.mark.asyncio
async def test_explicit_summary_grant_is_rechecked_after_revoke_or_membership_suspend() -> None:
    owner_id = uuid4()
    coach_id = uuid4()
    accounts = MemoryAccounts()
    accounts.emails[coach_id] = "coach@example.test"
    state = MemoryOrganizations()
    service, tokens = _service(state, accounts)
    organization = await service.create_organization(
        CreateOrganization("Fictional Grant Organization"),
        idempotency_key="organization-grant-owner",
        context=_context(owner_id),
    )
    queued = await service.invite_member(
        organization.organization.id,
        InviteOrganizationMember("coach@example.test", OrganizationRole.COACH),
        idempotency_key="organization-grant-invite",
        context=_context(owner_id),
    )
    token, token_hash = tokens.issue_for_id(queued.invitation.id)
    queued.invitation.mark_delivered(token_hash, NOW)
    coach = await service.accept_invitation(
        AcceptOrganizationInvitation(token),
        idempotency_key="organization-grant-accept",
        context=_context(coach_id),
    )

    grant = await service.create_grant(
        organization.organization.id,
        CreateOrganizationGrant(
            grantee_user_id=coach_id,
            purpose=GrantPurpose.COACHING,
            scope=GrantScope.RESUME_HEALTH_SUMMARY,
            expires_at=NOW + timedelta(days=30),
        ),
        idempotency_key="organization-grant-create",
        context=_context(owner_id),
    )
    assert grant.active
    assert await service.authorize_delegated_scope(
        organization.organization.id,
        subject_user_id=owner_id,
        grantee_user_id=coach_id,
        scope=GrantScope.RESUME_HEALTH_SUMMARY,
    )

    revoked = await service.revoke_grant(
        organization.organization.id,
        grant.grant.id,
        expected_version=grant.grant.version,
        context=_context(owner_id),
    )
    assert not revoked.active
    assert not await service.authorize_delegated_scope(
        organization.organization.id,
        subject_user_id=owner_id,
        grantee_user_id=coach_id,
        scope=GrantScope.RESUME_HEALTH_SUMMARY,
    )

    second = await service.create_grant(
        organization.organization.id,
        CreateOrganizationGrant(
            grantee_user_id=coach_id,
            purpose=GrantPurpose.PROGRAM_SUPPORT,
            scope=GrantScope.CAREER_GROWTH_SUMMARY,
            expires_at=NOW + timedelta(days=10),
        ),
        idempotency_key="organization-grant-second",
        context=_context(owner_id),
    )
    assert second.active
    await service.suspend_member(
        organization.organization.id,
        coach_id,
        expected_version=coach.membership.version,
        context=_context(owner_id),
    )
    assert not await service.authorize_delegated_scope(
        organization.organization.id,
        subject_user_id=owner_id,
        grantee_user_id=coach_id,
        scope=GrantScope.CAREER_GROWTH_SUMMARY,
    )
