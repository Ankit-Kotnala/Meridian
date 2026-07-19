"""PostgreSQL integration coverage for Job Match persistence and ownership."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.job_match.application import (
    CreateJob,
    JobMatchService,
    PrioritizeOpportunity,
    RequestContext,
)
from careeros.modules.job_match.domain import (
    EmploymentType,
    JobMatchNotFound,
    JobSourceKind,
    PreferenceFit,
    TailoringEffort,
    WorkModel,
)
from careeros.modules.job_match.infrastructure.models import (
    JobMatchAuditEventModel,
    JobPostingModel,
)
from careeros.modules.job_match.infrastructure.repository import (
    SqlAlchemyJobMatchUnitOfWorkFactory,
)
from job_match_memory import (
    FixedClock,
    StaticImporter,
    StaticRoleContextProvider,
    StaticSnapshotProvider,
    UuidFactory,
    sample_job_text,
    sample_snapshot,
)


def _context(owner_id):
    return RequestContext(owner_id, f"integration-{owner_id.hex[:8]}", "5" * 32)


def _command() -> CreateJob:
    return CreateJob(
        title="Product Manager",
        company="Example Co",
        location="Remote",
        work_model=WorkModel.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        compensation=None,
        application_deadline=None,
        source_kind=JobSourceKind.PASTE,
        source_url=None,
        source_text=sample_job_text(),
        target_role_id=None,
    )


@pytest.mark.asyncio
async def test_repository_persists_job_match_and_denies_cross_user_access() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    owner_id = uuid4()
    other_id = uuid4()
    service = JobMatchService(
        unit_of_work=SqlAlchemyJobMatchUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        career_snapshots=StaticSnapshotProvider(sample_snapshot()),
        role_context=StaticRoleContextProvider(),
        importer=StaticImporter(),
    )
    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=owner_id,
                        email_normalized=f"job-owner-{owner_id.hex[:8]}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                    UserModel(
                        id=other_id,
                        email_normalized=f"job-other-{other_id.hex[:8]}@example.test",
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

        job = await service.create_job(
            owner_id, _command(), "integration-job-create", _context(owner_id)
        )
        analysis = await service.analyze_job(
            owner_id, job.job.id, "integration-job-analysis", _context(owner_id)
        )
        priority = await service.prioritize_opportunity(
            owner_id,
            job.job.id,
            PrioritizeOpportunity(
                analysis_id=analysis.analysis.id,
                user_interest=5,
                career_direction_fit=4,
                compensation_fit=PreferenceFit.UNKNOWN,
                location_fit=PreferenceFit.STRONG,
                work_model_fit=PreferenceFit.STRONG,
                tailoring_effort=TailoringEffort.LOW,
                existing_contacts=1,
            ),
            "integration-job-priority",
            _context(owner_id),
        )

        fetched = await service.get_analysis(owner_id, analysis.analysis.id)
        assert fetched.analysis.id == analysis.analysis.id
        assert fetched.evidence_links[0].evidence_strength == "confirmed"
        assert priority.priority.analysis_id == analysis.analysis.id
        with pytest.raises(JobMatchNotFound):
            await service.get_analysis(other_id, analysis.analysis.id)

        async with database.session() as session:
            persisted = await session.scalar(
                select(JobPostingModel).where(JobPostingModel.id == job.job.id)
            )
            assert persisted is not None
            assert isinstance(persisted.source_sha256, bytes)
            audit = await session.scalar(
                select(JobMatchAuditEventModel).where(
                    JobMatchAuditEventModel.owner_user_id == owner_id,
                    JobMatchAuditEventModel.target_id == analysis.analysis.id,
                )
            )
            assert audit is not None
            assert "Must have experience" not in repr(audit.details)
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
            await session.commit()
        await database.dispose()
