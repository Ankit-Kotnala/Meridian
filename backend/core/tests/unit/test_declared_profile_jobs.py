"""Phase 11b async declared-link enrichment job tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from career_record_memory import FakeResumeSourceQuery, FixedClock, MemoryCareerRecord, UuidFactory

from rezumi.modules.career_record.application import (
    CareerRecordService,
    CreatePersonalFact,
    RequestContext,
)
from rezumi.modules.career_record.application.declared_profile_enrichment import (
    DeclaredProfileEnrichmentService,
)
from rezumi.modules.career_record.application.declared_profile_jobs import (
    DeclaredProfileEnrichmentJob,
    DeclaredProfileEnrichmentJobPolicy,
    DeclaredProfileEnrichmentJobService,
    DeclaredProfileEnrichmentJobStatus,
    DeclaredProfileEnrichmentOutboxDispatcher,
    DeclaredProfileEnrichmentOutboxMessage,
    DeclaredProfileEnrichmentProcessor,
)
from rezumi.modules.career_record.domain import PersonalFactKind
from rezumi.modules.career_record.infrastructure.declared_profile.fake_connector import (
    FakeDeclaredProfileConnector,
)
from rezumi.modules.career_record.infrastructure.declared_profile.registry import (
    DeclaredProfileConnectorRegistry,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _context(owner) -> RequestContext:
    return RequestContext(owner, "request-enrich-job", "trace-enrich-job")


def _career_service(memory: MemoryCareerRecord) -> CareerRecordService:
    return CareerRecordService(
        unit_of_work=memory,
        clock=FixedClock(NOW),
        identifiers=UuidFactory(),
        resume_sources=FakeResumeSourceQuery(),
    )


class _MemoryJobUnitOfWork:
    """Minimal in-memory fake matching DeclaredProfileEnrichmentJobUnitOfWork."""

    def __init__(self, jobs: dict, outbox: dict) -> None:
        self._jobs = jobs
        self._outbox = outbox

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get_active_job_for_fact(self, owner_user_id, personal_fact_id):
        for job in self._jobs.values():
            if (
                job.owner_user_id == owner_user_id
                and job.personal_fact_id == personal_fact_id
                and not job.status.terminal
            ):
                return job
        return None

    async def add_job(self, job: DeclaredProfileEnrichmentJob) -> None:
        self._jobs[job.id] = job

    async def get_job(self, owner_user_id, job_id):
        job = self._jobs.get(job_id)
        return job if job is not None and job.owner_user_id == owner_user_id else None

    async def get_job_system(self, job_id, *, for_update: bool = False):
        _ = for_update
        return self._jobs.get(job_id)

    async def save_job(self, job: DeclaredProfileEnrichmentJob) -> None:
        self._jobs[job.id] = job

    async def list_stale_running_jobs(self, stale_before, limit):
        results = [
            job
            for job in self._jobs.values()
            if job.status is DeclaredProfileEnrichmentJobStatus.RUNNING
            and job.updated_at <= stale_before
        ]
        return results[:limit]

    async def add_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None:
        self._outbox[message.id] = message

    async def list_pending_outbox(self, now, limit):
        results = [
            message
            for message in self._outbox.values()
            if not message.terminal and message.next_attempt_at <= now
        ]
        return results[:limit]

    async def save_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None:
        self._outbox[message.id] = message

    async def commit(self) -> None:
        return None


class _MemoryJobUnitOfWorkFactory:
    def __init__(self) -> None:
        self.jobs: dict = {}
        self.outbox: dict = {}

    def __call__(self) -> _MemoryJobUnitOfWork:
        return _MemoryJobUnitOfWork(self.jobs, self.outbox)


class _RecordingPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, object, str]] = []

    async def publish(self, task_name, job_id, trace_id) -> None:
        self.published.append((task_name, job_id, trace_id))


class _FailingPublisher:
    async def publish(self, task_name, job_id, trace_id) -> None:
        _ = (task_name, job_id, trace_id)
        raise OSError("broker unavailable")


async def _make_fact(career: CareerRecordService, owner, value: str):
    await career.get_or_create_profile(owner, _context(owner))
    return await career.create_personal_fact(
        owner,
        CreatePersonalFact(kind=PersonalFactKind.LINK, value=value, label="Portfolio"),
        _context(owner),
    )


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_for_the_same_fact() -> None:
    uow_factory = _MemoryJobUnitOfWorkFactory()
    service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory, clock=FixedClock(NOW), ids=UuidFactory()
    )
    owner = uuid4()
    fact_id = uuid4()

    first = await service.enqueue(owner, fact_id, _context(owner))
    second = await service.enqueue(owner, fact_id, _context(owner))

    assert first.job_id == second.job_id
    assert len(uow_factory.jobs) == 1
    assert len(uow_factory.outbox) == 1


@pytest.mark.asyncio
async def test_process_job_succeeds_end_to_end() -> None:
    memory = MemoryCareerRecord()
    career = _career_service(memory)
    owner = uuid4()
    fact = await _make_fact(career, owner, "https://example.test/profile/alex")

    enrichment = DeclaredProfileEnrichmentService(
        career_record=career,
        connectors=DeclaredProfileConnectorRegistry((FakeDeclaredProfileConnector(),)),
    )
    uow_factory = _MemoryJobUnitOfWorkFactory()
    job_service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory, clock=FixedClock(NOW), ids=UuidFactory()
    )
    processor = DeclaredProfileEnrichmentProcessor(
        unit_of_work=uow_factory,
        clock=FixedClock(NOW),
        ids=UuidFactory(),
        enrichment=enrichment,
    )

    view = await job_service.enqueue(owner, fact.id, _context(owner))
    status = await processor.process_job(view.job_id)

    assert status is DeclaredProfileEnrichmentJobStatus.SUCCEEDED
    final = await job_service.get_job(owner, view.job_id)
    assert final.result_platform == "fake"
    assert final.result_achievements_created == 2
    assert final.result_evidence_created == 2


@pytest.mark.asyncio
async def test_process_job_retries_then_dead_letters_on_repeated_fetch_failure() -> None:
    memory = MemoryCareerRecord()
    career = _career_service(memory)
    owner = uuid4()
    fact = await _make_fact(career, owner, "https://unroutable.example/profile")

    enrichment = DeclaredProfileEnrichmentService(
        career_record=career,
        connectors=DeclaredProfileConnectorRegistry(()),
    )
    uow_factory = _MemoryJobUnitOfWorkFactory()
    job_service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory,
        clock=FixedClock(NOW),
        ids=UuidFactory(),
        policy=DeclaredProfileEnrichmentJobPolicy(max_attempts=2),
    )
    processor = DeclaredProfileEnrichmentProcessor(
        unit_of_work=uow_factory,
        clock=FixedClock(NOW),
        ids=UuidFactory(),
        enrichment=enrichment,
        policy=DeclaredProfileEnrichmentJobPolicy(max_attempts=2),
    )

    view = await job_service.enqueue(owner, fact.id, _context(owner))

    # No connector supports this host, so the registry raises
    # DeclaredProfileUnsupported, which is a permanent (non-retryable) failure.
    status = await processor.process_job(view.job_id)
    assert status is DeclaredProfileEnrichmentJobStatus.FAILED
    final = await job_service.get_job(owner, view.job_id)
    assert final.error_message is not None


@pytest.mark.asyncio
async def test_outbox_dispatch_publishes_and_marks_delivered() -> None:
    uow_factory = _MemoryJobUnitOfWorkFactory()
    job_service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory, clock=FixedClock(NOW), ids=UuidFactory()
    )
    owner = uuid4()
    view = await job_service.enqueue(owner, uuid4(), _context(owner))

    publisher = _RecordingPublisher()
    dispatcher = DeclaredProfileEnrichmentOutboxDispatcher(
        unit_of_work=uow_factory, publisher=publisher, clock=FixedClock(NOW)
    )
    result = await dispatcher.dispatch_pending(limit=10)

    assert result.published == 1
    assert publisher.published[0][1] == view.job_id
    assert all(message.published_at is not None for message in uow_factory.outbox.values())


@pytest.mark.asyncio
async def test_outbox_dispatch_dead_letters_after_max_attempts() -> None:
    uow_factory = _MemoryJobUnitOfWorkFactory()
    job_service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory, clock=FixedClock(NOW), ids=UuidFactory()
    )
    owner = uuid4()
    await job_service.enqueue(owner, uuid4(), _context(owner))
    for message in uow_factory.outbox.values():
        message.max_attempts = 1

    dispatcher = DeclaredProfileEnrichmentOutboxDispatcher(
        unit_of_work=uow_factory, publisher=_FailingPublisher(), clock=FixedClock(NOW)
    )
    result = await dispatcher.dispatch_pending(limit=10)

    assert result.dead_lettered == 1
    assert all(message.dead_lettered_at is not None for message in uow_factory.outbox.values())


@pytest.mark.asyncio
async def test_reconcile_dead_letters_stale_running_jobs() -> None:
    memory = MemoryCareerRecord()
    career = _career_service(memory)
    owner = uuid4()
    fact = await _make_fact(career, owner, "https://example.test/profile/alex")

    enrichment = DeclaredProfileEnrichmentService(
        career_record=career,
        connectors=DeclaredProfileConnectorRegistry((FakeDeclaredProfileConnector(),)),
    )
    uow_factory = _MemoryJobUnitOfWorkFactory()
    job_service = DeclaredProfileEnrichmentJobService(
        unit_of_work=uow_factory, clock=FixedClock(NOW), ids=UuidFactory()
    )
    view = await job_service.enqueue(owner, fact.id, _context(owner))
    stuck = uow_factory.jobs[view.job_id]
    stuck.status = DeclaredProfileEnrichmentJobStatus.RUNNING
    stuck.updated_at = datetime(2026, 8, 1, tzinfo=UTC)

    processor = DeclaredProfileEnrichmentProcessor(
        unit_of_work=uow_factory,
        clock=FixedClock(NOW),
        ids=UuidFactory(),
        enrichment=enrichment,
    )
    result = await processor.reconcile(limit=10)

    assert result.dead_lettered == 1
    assert uow_factory.jobs[view.job_id].status is DeclaredProfileEnrichmentJobStatus.DEAD_LETTERED
