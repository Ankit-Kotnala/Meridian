"""PostgreSQL integration coverage for Role Readiness persistence and ownership."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from rezumi.foundation.config import DatabaseOptions
from rezumi.foundation.database import Database
from rezumi.modules.identity.infrastructure.models import UserModel
from rezumi.modules.role_readiness.application import (
    AnalyzeRoleReadiness,
    RequestContext,
    RoleFilter,
    RoleReadinessService,
    SaveRole,
)
from rezumi.modules.role_readiness.domain import RoleReadinessNotFound
from rezumi.modules.role_readiness.domain.scoring import (
    CareerReadinessSnapshot,
    SnapshotEvidence,
    SnapshotSkill,
)
from rezumi.modules.role_readiness.infrastructure.models import (
    RoleReadinessAnalysisModel,
    RoleReadinessAuditEventModel,
)
from rezumi.modules.role_readiness.infrastructure.repository import (
    SqlAlchemyRoleReadinessUnitOfWorkFactory,
)
from role_readiness_memory import (
    PRODUCT_ROLE_ID,
    FixedClock,
    StaticSnapshotProvider,
    UuidFactory,
)


def _context(owner_id):
    return RequestContext(owner_id, f"integration-{owner_id.hex[:8]}", "4" * 32)


def _snapshot() -> CareerReadinessSnapshot:
    skill_id = uuid4()
    return CareerReadinessSnapshot(
        skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
        entities=(),
        evidence=(
            SnapshotEvidence(
                id=uuid4(),
                title="Confirmed product discovery",
                statement="Confirmed evidence about user research and customer discovery.",
                context=None,
                strength="confirmed",
                skill_ids=(skill_id,),
                entity_ids=(),
                has_numeric_claim=False,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_repository_persists_role_analysis_and_denies_cross_user_access() -> None:
    database_url = os.environ.get("REZUMI_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("REZUMI_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    owner_id = uuid4()
    other_id = uuid4()
    service = RoleReadinessService(
        unit_of_work=SqlAlchemyRoleReadinessUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=StaticSnapshotProvider(_snapshot()),
    )
    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=owner_id,
                        email_normalized=f"role-owner-{owner_id.hex[:8]}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                    UserModel(
                        id=other_id,
                        email_normalized=f"role-other-{other_id.hex[:8]}@example.test",
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

        listed = await service.list_roles(RoleFilter(query="product"))
        assert any(role.role.id == PRODUCT_ROLE_ID for role in listed.data)
        saved = await service.save_role(
            owner_id, SaveRole(PRODUCT_ROLE_ID, "Integration target"), _context(owner_id)
        )
        analysis = await service.analyze_role(
            owner_id,
            AnalyzeRoleReadiness(saved_role_id=saved.saved_role.id),
            "integration-role-readiness-key",
            _context(owner_id),
        )
        fetched = await service.get_analysis(owner_id, analysis.analysis.id)

        assert fetched.analysis.id == analysis.analysis.id
        assert fetched.saved_role is not None
        assert fetched.evidence_links[0].evidence_strength == "confirmed"
        with pytest.raises(RoleReadinessNotFound):
            await service.get_analysis(other_id, analysis.analysis.id)

        async with database.session() as session:
            persisted = await session.scalar(
                select(RoleReadinessAnalysisModel).where(
                    RoleReadinessAnalysisModel.id == analysis.analysis.id
                )
            )
            assert persisted is not None
            assert isinstance(persisted.feature_set_hash, bytes)
            audit = await session.scalar(
                select(RoleReadinessAuditEventModel).where(
                    RoleReadinessAuditEventModel.owner_user_id == owner_id,
                    RoleReadinessAuditEventModel.target_id == analysis.analysis.id,
                )
            )
            assert audit is not None
            assert "Confirmed evidence" not in repr(audit.details)
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
            await session.commit()
        await database.dispose()
