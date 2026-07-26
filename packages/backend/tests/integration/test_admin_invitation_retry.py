"""Real PostgreSQL coverage for allowlisted invitation delivery recovery."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.administration.application import AdministrationService, RequestContext
from careeros.modules.administration.domain import AdminRole
from careeros.modules.administration.infrastructure import (
    SqlAlchemyAdministrationUnitOfWorkFactory,
    SystemClock,
    UuidIdentifierFactory,
)
from careeros.modules.administration.infrastructure.models import (
    PlatformAdminAuditEventModel,
    PlatformOperatorAssignmentModel,
)
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.organizations.infrastructure.models import (
    OrganizationInvitationModel,
    OrganizationInvitationOutboxModel,
    OrganizationModel,
)

_PEPPER = "fictional-admin-audit-pepper-at-least-32-bytes"
_REASON = "Approved fictional invitation recovery integration verification."


def _database() -> Database:
    value = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required")
    return Database(DatabaseOptions(url=value, pool_size=2, max_overflow=0))


@pytest.mark.asyncio
async def test_job_operator_rearms_dead_lettered_invitation_once() -> None:
    database = _database()
    now = datetime.now(UTC)
    user_id = uuid4()
    organization_id = uuid4()
    invitation_id = uuid4()
    outbox_id = uuid4()
    principal = AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=now,
        auth_method=AuthMethod.PASSWORD,
    )
    factory = SqlAlchemyAdministrationUnitOfWorkFactory(database, _PEPPER)
    service = AdministrationService(
        unit_of_work=factory,
        clock=SystemClock(),
        identifiers=UuidIdentifierFactory(),
    )
    try:
        async with database.session() as session:
            session.add(
                UserModel(
                    id=user_id,
                    email_normalized=f"fictional-invitation-admin-{user_id}@example.test",
                    password_hash="fictional-password-hash",  # noqa: S106
                    status="active",
                    email_verified_at=now,
                    auth_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                PlatformOperatorAssignmentModel(
                    user_id=user_id,
                    role=AdminRole.JOB_OPERATOR.value,
                    grant_reason="Approved fictional invitation job-operator grant.",
                    granted_at=now,
                )
            )
            session.add(
                OrganizationModel(
                    id=organization_id,
                    name="Fictional invitation recovery organization",
                    created_by_user_id=user_id,
                    status="active",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                OrganizationInvitationModel(
                    id=invitation_id,
                    organization_id=organization_id,
                    invited_email_normalized="fictional-invitee@example.test",
                    invited_email_digest=b"e" * 32,
                    role="member",
                    status="delivery_dead_lettered",
                    invited_by_user_id=user_id,
                    expires_at=now + timedelta(days=1),
                    version=2,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                OrganizationInvitationOutboxModel(
                    id=outbox_id,
                    invitation_id=invitation_id,
                    organization_id=organization_id,
                    trace_id="f" * 32,
                    attempts=3,
                    max_attempts=3,
                    next_attempt_at=now,
                    dead_lettered_at=now,
                    last_error_code="organization_invitation_delivery_failed",
                    created_at=now,
                )
            )
            await session.commit()

        result = await service.retry_dead_letter(
            principal,
            RequestContext("admin-invitation-retry", "1" * 32),
            kind="organization_invitation",
            target_id=invitation_id,
            reason=_REASON,
            idempotency_key="fictional-invitation-admin-retry",
        )
        assert result.status == "pending_delivery"

        async with database.session() as session:
            invitation = await session.get(OrganizationInvitationModel, invitation_id)
            outbox = await session.get(OrganizationInvitationOutboxModel, outbox_id)
            assert invitation is not None and invitation.status == "pending_delivery"
            assert invitation.version == 3
            assert outbox is not None and outbox.dead_lettered_at is None
            assert outbox.attempts == 2
            assert outbox.last_error_code is None
    finally:
        async with database.session() as session:
            await session.execute(
                delete(OrganizationModel).where(OrganizationModel.id == organization_id)
            )
            await session.execute(
                delete(PlatformAdminAuditEventModel).where(
                    PlatformAdminAuditEventModel.actor_reference.is_not(None)
                )
            )
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
        await database.dispose()
