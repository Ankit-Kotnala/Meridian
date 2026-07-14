"""PostgreSQL integration coverage for identity persistence and owner scoping."""

# ruff: noqa: S105 -- all credentials are isolated test fixtures.

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.application.models import RequestContext
from careeros.modules.identity.application.service import IdentityPolicy, IdentityService
from careeros.modules.identity.domain.errors import ResourceNotFound
from careeros.modules.identity.infrastructure.fakes import (
    CapturingEmailSender,
    DisabledGoogleOAuthProvider,
    InMemoryAbuseLimiter,
    utc_test_clock,
)
from careeros.modules.identity.infrastructure.models import AuthSessionModel, UserModel
from careeros.modules.identity.infrastructure.repository import (
    SqlAlchemyIdentityUnitOfWorkFactory,
)
from careeros.modules.identity.infrastructure.security import (
    HmacTokenManager,
    NormalizedEmailValidator,
)


class FastPasswordHasher:
    async def hash(self, password: str) -> str:
        return f"integration-hash::{password}"

    async def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == await self.hash(password)

    async def verify_dummy(self, password: str) -> None:
        del password


def _context(source: str) -> RequestContext:
    return RequestContext(
        request_id=f"integration-{source}",
        trace_id="2" * 32,
        device_label="Integration browser",
        source_key=source,
    )


def _email_token(emails: CapturingEmailSender) -> str:
    return emails.messages[-1].text_body.split("#token=", 1)[1].splitlines()[0]


@pytest.mark.asyncio
async def test_repository_persists_rotation_and_denies_cross_user_session_access() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    emails = CapturingEmailSender()
    service = IdentityService(
        unit_of_work=SqlAlchemyIdentityUnitOfWorkFactory(database),
        clock=utc_test_clock(),
        passwords=FastPasswordHasher(),
        tokens=HmacTokenManager("integration-pepper-that-is-longer-than-thirty-two-bytes"),
        emails=emails,
        email_normalizer=NormalizedEmailValidator(),
        limiter=InMemoryAbuseLimiter(),
        google=DisabledGoogleOAuthProvider(),
        policy=IdentityPolicy(public_app_url="https://integration.example.com"),
    )
    suffix = uuid4().hex
    first_email = f"integration-{suffix[:12]}@example.com"
    second_email = f"integration-{suffix[12:24]}@example.com"
    password = "integration password value"

    try:
        await service.register(first_email, password, "First User", _context("first"))
        await service.verify_email(_email_token(emails), _context("first"))
        first = await service.login(first_email, password, _context("first"))
        rotated = await service.refresh(first.refresh_token, _context("first"))
        assert await service.authenticate(rotated.access_token) == rotated.principal

        await service.register(second_email, password, "Second User", _context("second"))
        await service.verify_email(_email_token(emails), _context("second"))
        second = await service.login(second_email, password, _context("second"))
        with pytest.raises(ResourceNotFound):
            await service.revoke_session(
                first.principal,
                second.principal.session_id,
                _context("first"),
            )
        assert await service.authenticate(second.access_token) == second.principal

        async with database.session() as session:
            persisted = await session.scalar(
                select(AuthSessionModel).where(AuthSessionModel.id == first.principal.session_id)
            )
            assert persisted is not None
            assert isinstance(persisted.access_token_hash, bytes)
            assert rotated.access_token not in repr(persisted)
            assert rotated.refresh_token not in repr(persisted)
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.email_normalized.in_([first_email, second_email]))
            )
            await session.commit()
        await database.dispose()
