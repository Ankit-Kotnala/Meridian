"""PostgreSQL organization ownership, invitation, and grant coverage."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.identity.infrastructure.organization_directory import (
    IdentityOrganizationAccountDirectory,
)
from careeros.modules.identity.infrastructure.security import NormalizedEmailValidator
from careeros.modules.organizations.application import (
    AcceptOrganizationInvitation,
    CreateOrganization,
    CreateOrganizationGrant,
    InviteOrganizationMember,
    OrganizationService,
    RequestContext,
)
from careeros.modules.organizations.domain import (
    GrantPurpose,
    GrantScope,
    OrganizationNotFound,
    OrganizationRole,
)
from careeros.modules.organizations.infrastructure import (
    HmacOrganizationInvitationManager,
    SqlAlchemyOrganizationUnitOfWorkFactory,
)
from careeros.modules.organizations.infrastructure.models import (
    OrganizationAuditEventModel,
    OrganizationInvitationOutboxModel,
    OrganizationModel,
)

_NOW = datetime(2026, 7, 26, 23, 30, tzinfo=UTC)
_SECRET = "fictional-integration-organization-secret-at-least-32-bytes"  # noqa: S105


class FixedClock:
    def now(self) -> datetime:
        return _NOW


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


def _context(user_id: UUID) -> RequestContext:
    return RequestContext(
        actor_user_id=user_id,
        request_id=f"organization-{user_id.hex[:8]}",
        trace_id=f"organization-trace-{user_id.hex[:8]}",
    )


@pytest.mark.asyncio
async def test_organization_repository_rechecks_membership_and_explicit_grant() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    owner_id = uuid4()
    coach_id = uuid4()
    outsider_id = uuid4()
    organization_id: UUID | None = None
    tokens = HmacOrganizationInvitationManager(_SECRET)
    uow_factory = SqlAlchemyOrganizationUnitOfWorkFactory(database)
    service = OrganizationService(
        unit_of_work=uow_factory,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        accounts=IdentityOrganizationAccountDirectory(database),
        emails=NormalizedEmailValidator(),
        invitation_tokens=tokens,
    )
    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=user_id,
                        email_normalized=email,
                        password_hash=None,
                        status="active",
                        email_verified_at=_NOW,
                        auth_version=1,
                        created_at=_NOW,
                        updated_at=_NOW,
                    )
                    for user_id, email in (
                        (owner_id, f"org-owner-{owner_id.hex}@example.com"),
                        (coach_id, f"org-coach-{coach_id.hex}@example.com"),
                        (outsider_id, f"org-outsider-{outsider_id.hex}@example.com"),
                    )
                ]
            )
            await session.commit()

        organization = await service.create_organization(
            CreateOrganization("Fictional Integration Organization"),
            idempotency_key="integration-organization-create",
            context=_context(owner_id),
        )
        organization_id = organization.organization.id
        invitation = await service.invite_member(
            organization_id,
            InviteOrganizationMember(
                f"org-coach-{coach_id.hex}@example.com",
                OrganizationRole.COACH,
            ),
            idempotency_key="integration-organization-invite",
            context=_context(owner_id),
        )
        token, token_hash = tokens.issue_for_id(invitation.invitation.id)
        async with uow_factory() as uow:
            stored = await uow.get_invitation(
                invitation.invitation.id,
                for_update=True,
            )
            assert stored is not None
            previous = stored.version
            stored.mark_delivered(token_hash, _NOW)
            await uow.save_invitation(stored, expected_version=previous)
            await uow.commit()

        coach = await service.accept_invitation(
            AcceptOrganizationInvitation(token),
            idempotency_key="integration-organization-accept",
            context=_context(coach_id),
        )
        assert coach.membership.role is OrganizationRole.COACH
        with pytest.raises(OrganizationNotFound):
            await service.get_organization(organization_id, outsider_id)

        grant = await service.create_grant(
            organization_id,
            CreateOrganizationGrant(
                grantee_user_id=coach_id,
                purpose=GrantPurpose.COACHING,
                scope=GrantScope.CAREER_PROFILE_SUMMARY,
                expires_at=_NOW + timedelta(days=30),
            ),
            idempotency_key="integration-organization-grant",
            context=_context(owner_id),
        )
        assert grant.active
        assert await service.authorize_delegated_scope(
            organization_id,
            subject_user_id=owner_id,
            grantee_user_id=coach_id,
            scope=GrantScope.CAREER_PROFILE_SUMMARY,
        )
        assert not await service.authorize_delegated_scope(
            organization_id,
            subject_user_id=owner_id,
            grantee_user_id=outsider_id,
            scope=GrantScope.CAREER_PROFILE_SUMMARY,
        )

        async with database.session() as session:
            outbox = await session.scalar(
                select(OrganizationInvitationOutboxModel).where(
                    OrganizationInvitationOutboxModel.invitation_id == invitation.invitation.id
                )
            )
            assert outbox is not None
            audits = tuple(
                await session.scalars(
                    select(OrganizationAuditEventModel).where(
                        OrganizationAuditEventModel.organization_id == organization_id
                    )
                )
            )
            assert {item.action for item in audits} >= {
                "organization_created",
                "invitation_created",
                "invitation_accepted",
                "grant_created",
            }
            assert all("example.test" not in repr(item.event_metadata) for item in audits)
    finally:
        async with database.session() as session:
            if organization_id is not None:
                await session.execute(
                    delete(OrganizationModel).where(OrganizationModel.id == organization_id)
                )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([owner_id, coach_id, outsider_id]))
            )
            await session.commit()
        await database.dispose()
