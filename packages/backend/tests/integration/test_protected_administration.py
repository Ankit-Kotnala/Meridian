"""Real PostgreSQL coverage for operator authority, audit integrity, and erasure."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

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
from careeros.modules.identity.infrastructure.models import AccountOperationModel, UserModel

_PEPPER = "fictional-admin-audit-pepper-at-least-32-bytes"
_REASON = "Approved fictional live administration integration verification."


def _database() -> Database:
    value = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required")
    return Database(DatabaseOptions(url=value, pool_size=2, max_overflow=0))


@pytest.mark.asyncio
async def test_admin_audit_survives_user_erasure_without_breaking_chain() -> None:
    database = _database()
    now = datetime.now(UTC)
    user_id = uuid4()
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
                    email_normalized=f"fictional-admin-{user_id}@example.test",
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
                    role=AdminRole.SECURITY_AUDITOR.value,
                    grant_reason="Approved fictional security-auditor integration grant.",
                    granted_at=now,
                )
            )
            await session.commit()

        snapshot = await service.system_snapshot(
            principal,
            RequestContext("admin-live-system", "b" * 32),
            reason=_REASON,
        )
        assert snapshot.audit_chain_valid
        assert await service.verify_audit_integrity(
            principal,
            RequestContext("admin-live-audit", "c" * 32),
            reason=_REASON,
        )

        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
            events = (
                await session.scalars(
                    select(PlatformAdminAuditEventModel).order_by(
                        PlatformAdminAuditEventModel.sequence
                    )
                )
            ).all()
            assert events
            assert all(event.actor_user_id is None for event in events)
            assert all(len(event.actor_reference) == 64 for event in events)

        async with factory() as uow:
            assert await uow.verify_audit_chain()
    finally:
        async with database.session() as session:
            await session.execute(
                delete(PlatformAdminAuditEventModel).where(
                    PlatformAdminAuditEventModel.actor_reference.is_not(None)
                )
            )
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
        await database.dispose()


@pytest.mark.asyncio
async def test_job_operator_rearms_account_privacy_dead_letter_once() -> None:
    database = _database()
    now = datetime.now(UTC)
    user_id = uuid4()
    operation_id = uuid4()
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
                    email_normalized=f"fictional-job-admin-{user_id}@example.test",
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
                    grant_reason="Approved fictional job-operator integration grant.",
                    granted_at=now,
                )
            )
            session.add(
                AccountOperationModel(
                    id=operation_id,
                    user_id=user_id,
                    user_fingerprint=b"u" * 32,
                    capability_hash=b"c" * 32,
                    kind="export",
                    status="dead_lettered",
                    idempotency_key="fictional-dead-letter-operation",
                    request_id="fictional-dead-letter-request",
                    trace_id="d" * 32,
                    attempts=3,
                    max_attempts=3,
                    next_attempt_at=now,
                    completed_at=now,
                    last_error_code="privacy_operation_failed",
                    requested_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        result = await service.retry_dead_letter(
            principal,
            RequestContext("admin-live-retry", "e" * 32),
            kind="account_privacy",
            target_id=operation_id,
            reason=_REASON,
            idempotency_key="fictional-live-admin-retry",
        )
        replay = await service.retry_dead_letter(
            principal,
            RequestContext("admin-live-replay", "f" * 32),
            kind="account_privacy",
            target_id=operation_id,
            reason=_REASON,
            idempotency_key="fictional-live-admin-retry",
        )
        assert result.status == "retry_wait"
        assert replay.replayed

        async with database.session() as session:
            operation = await session.get(AccountOperationModel, operation_id)
            assert operation is not None
            assert operation.status == "retry_wait"
            assert operation.attempts == 2
            assert operation.completed_at is None
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.execute(
                delete(PlatformAdminAuditEventModel).where(
                    PlatformAdminAuditEventModel.actor_reference.is_not(None)
                )
            )
            await session.commit()
        await database.dispose()
