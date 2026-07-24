"""Application-level Job Match tests using deterministic inward ports."""

from __future__ import annotations

from uuid import uuid4

import pytest

from careeros.modules.job_match.application import (
    CreateJob,
    JobMatchService,
    PrioritizeOpportunity,
    RequestContext,
)
from careeros.modules.job_match.domain import (
    EmploymentType,
    JobMatchIdempotencyConflict,
    JobMatchNotFound,
    JobSourceKind,
    PreferenceFit,
    RequirementMatchState,
    TailoringEffort,
    WorkModel,
)
from job_match_memory import (
    FixedClock,
    MemoryJobMatch,
    StaticImporter,
    StaticRoleContextProvider,
    StaticSnapshotProvider,
    UuidFactory,
    sample_job_text,
    sample_snapshot,
)


def _context(owner):
    return RequestContext(owner, f"job-match-{owner.hex[:8]}", "5" * 32)


def _service(memory: MemoryJobMatch, provider: StaticSnapshotProvider | None = None):
    snapshot_provider = provider or StaticSnapshotProvider(sample_snapshot())
    return (
        JobMatchService(
            unit_of_work=memory,
            clock=FixedClock(),
            identifiers=UuidFactory(),
            career_snapshots=snapshot_provider,
            role_context=StaticRoleContextProvider(),
            importer=StaticImporter(),
        ),
        snapshot_provider,
    )


def _create_command(title: str = "Product Manager") -> CreateJob:
    return CreateJob(
        title=title,
        company="Example Co",
        location="Remote",
        work_model=WorkModel.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        compensation=None,
        application_deadline=None,
        source_kind=JobSourceKind.PASTE,
        source_url=None,
        source_text=sample_job_text(title),
        target_role_id=None,
    )


@pytest.mark.asyncio
async def test_job_create_extracts_requirements_and_is_owner_scoped() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryJobMatch()
    service, _ = _service(memory)

    with pytest.raises(JobMatchNotFound):
        await service.create_job(owner, _create_command(), "job-create-key", _context(other))

    created = await service.create_job(owner, _create_command(), "job-create-key", _context(owner))
    repeated = await service.create_job(owner, _create_command(), "job-create-key", _context(owner))

    assert repeated.job.id == created.job.id
    assert created.job.owner_user_id == owner
    assert len(created.requirements) == 3
    assert memory.audits[-1].target_id == created.job.id

    with pytest.raises(JobMatchIdempotencyConflict):
        await service.create_job(
            owner,
            _create_command("Different Product Role"),
            "job-create-key",
            _context(owner),
        )


@pytest.mark.asyncio
async def test_job_analysis_uses_snapshot_once_and_links_evidence() -> None:
    owner = uuid4()
    memory = MemoryJobMatch()
    provider = StaticSnapshotProvider(sample_snapshot())
    service, provider = _service(memory, provider)
    job = await service.create_job(owner, _create_command(), "job-create-analysis", _context(owner))

    first = await service.analyze_job(owner, job.job.id, "job-analysis-key", _context(owner))
    second = await service.analyze_job(owner, job.job.id, "job-analysis-key", _context(owner))

    assert first.analysis.id == second.analysis.id
    assert provider.requests == [owner]
    assert first.analysis.display_score is not None
    assert any(
        requirement.match_state is RequirementMatchState.STRONG
        for requirement in first.requirement_matches
    )
    assert first.evidence_links[0].evidence_title == "Confirmed discovery program"


@pytest.mark.asyncio
async def test_opportunity_priority_uses_latest_analysis_and_denies_cross_user() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryJobMatch()
    service, _ = _service(memory)
    job = await service.create_job(owner, _create_command(), "job-priority-create", _context(owner))
    analysis = await service.analyze_job(
        owner, job.job.id, "job-priority-analysis", _context(owner)
    )

    with pytest.raises(JobMatchNotFound):
        await service.prioritize_opportunity(
            other,
            job.job.id,
            PrioritizeOpportunity(
                analysis_id=analysis.analysis.id,
                user_interest=4,
                career_direction_fit=4,
                compensation_fit=PreferenceFit.UNKNOWN,
                location_fit=PreferenceFit.STRONG,
                work_model_fit=PreferenceFit.STRONG,
                tailoring_effort=TailoringEffort.MEDIUM,
                existing_contacts=1,
            ),
            "other-priority-key",
            _context(other),
        )

    priority = await service.prioritize_opportunity(
        owner,
        job.job.id,
        PrioritizeOpportunity(
            analysis_id=None,
            user_interest=5,
            career_direction_fit=4,
            compensation_fit=PreferenceFit.ACCEPTABLE,
            location_fit=PreferenceFit.STRONG,
            work_model_fit=PreferenceFit.STRONG,
            tailoring_effort=TailoringEffort.LOW,
            existing_contacts=2,
        ),
        "job-priority-key",
        _context(owner),
    )

    assert priority.priority.job_id == job.job.id
    assert priority.priority.analysis_id == analysis.analysis.id
    assert priority.priority.next_action
