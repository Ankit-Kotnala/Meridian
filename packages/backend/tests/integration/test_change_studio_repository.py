"""PostgreSQL integration coverage for Change Studio persistence and ownership."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import delete, select

from change_studio_memory import (
    ANALYSIS_ID,
    OTHER_ID,
    OWNER_ID,
    FixedClock,
    StaticEvidenceProvider,
    StaticJobAnalysisProvider,
    UuidFactory,
)
from rezumi.foundation.config import DatabaseOptions
from rezumi.foundation.database import Database
from rezumi.modules.change_studio.application import (
    ChangeStudioService,
    CreateChangeSet,
    RequestContext,
)
from rezumi.modules.change_studio.domain import ChangeStudioNotFound
from rezumi.modules.change_studio.infrastructure import (
    DeterministicSuggestionProvider,
)
from rezumi.modules.change_studio.infrastructure.models import (
    ChangeClaimModel,
    ChangeSetModel,
    ChangeStudioAuditEventModel,
    ProviderRunModel,
)
from rezumi.modules.change_studio.infrastructure.repository import (
    SqlAlchemyChangeStudioUnitOfWorkFactory,
)
from rezumi.modules.identity.infrastructure.models import UserModel


def _context(owner_id) -> RequestContext:
    return RequestContext(owner_id, f"integration-{owner_id.hex[:8]}", "6" * 32)


@pytest.mark.asyncio
async def test_repository_persists_change_studio_and_denies_cross_user_access() -> None:
    database_url = os.environ.get("REZUMI_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("REZUMI_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    service = ChangeStudioService(
        unit_of_work=SqlAlchemyChangeStudioUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        provider=DeterministicSuggestionProvider(),
        evidence=StaticEvidenceProvider(),
        job_matches=StaticJobAnalysisProvider(),
    )
    try:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([OWNER_ID, OTHER_ID])))
            session.add_all(
                [
                    UserModel(
                        id=OWNER_ID,
                        email_normalized="change-owner@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                    UserModel(
                        id=OTHER_ID,
                        email_normalized="change-other@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                ]
            )
            await session.commit()

        created = await service.create_change_set(
            OWNER_ID,
            CreateChangeSet(analysis_id=ANALYSIS_ID),
            "integration-change-create",
            _context(OWNER_ID),
        )
        accepted = await service.accept_operation(
            OWNER_ID,
            created.change_set.id,
            created.operations[0].id,
            created.change_set.version,
            "integration-change-accept",
            _context(OWNER_ID),
        )

        fetched = await service.get_change_set(OWNER_ID, created.change_set.id)
        assert fetched.change_set.id == created.change_set.id
        assert fetched.change_set.current_version_id == accepted.change_set.current_version_id
        assert fetched.claims[0].evidence_title == "Confirmed discovery program"
        with pytest.raises(ChangeStudioNotFound):
            await service.get_change_set(OTHER_ID, created.change_set.id)

        async with database.session() as session:
            persisted = await session.scalar(
                select(ChangeSetModel).where(ChangeSetModel.id == created.change_set.id)
            )
            assert persisted is not None
            assert persisted.owner_user_id == OWNER_ID
            claim = await session.scalar(
                select(ChangeClaimModel).where(
                    ChangeClaimModel.change_set_id == created.change_set.id
                )
            )
            assert claim is not None
            provider_run = await session.scalar(
                select(ProviderRunModel).where(
                    ProviderRunModel.change_set_id == created.change_set.id
                )
            )
            assert provider_run is not None
            assert provider_run.input_evidence_ids
            audit = await session.scalar(
                select(ChangeStudioAuditEventModel).where(
                    ChangeStudioAuditEventModel.owner_user_id == OWNER_ID,
                    ChangeStudioAuditEventModel.target_id == created.change_set.id,
                )
            )
            assert audit is not None
            assert "Confirmed evidence" not in repr(audit.details)
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([OWNER_ID, OTHER_ID])))
            await session.commit()
        await database.dispose()
