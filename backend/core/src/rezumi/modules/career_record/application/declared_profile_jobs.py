"""Async job + outbox for declared-link enrichment (Phase 11b).

Unlike evidence-attachment processing, a declared-profile fetch has no
untrusted binary payload, no malware scan, and no object-storage promotion to
fence against double-execution. `DeclaredProfileEnrichmentService.enrich_
personal_fact` is naturally idempotent (it dedupes new achievements against
the owner's existing achievement titles on every call), so re-running the
same job twice is safe. That lets this job model skip the lease/execution-
token fencing the attachment pipeline needs and stay to a plain queued /
running / succeeded / failed / dead-lettered state machine with attempt
counting and backoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from rezumi.modules.career_record.application.declared_profile_enrichment import (
    DeclaredProfileEnrichmentResult,
    DeclaredProfileEnrichmentService,
)
from rezumi.modules.career_record.application.declared_profile_ports import (
    DeclaredProfileFetchFailed,
    DeclaredProfileUnsupported,
)
from rezumi.modules.career_record.application.models import RequestContext
from rezumi.modules.career_record.domain.errors import (
    CareerRecordConflict,
    CareerRecordNotFound,
)

PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK = (
    "rezumi.career_record.process_declared_profile_enrichment"
)
DISPATCH_DECLARED_PROFILE_ENRICHMENT_OUTBOX_TASK = (
    "rezumi.career_record.dispatch_declared_profile_enrichment_outbox"
)
RECONCILE_DECLARED_PROFILE_ENRICHMENT_JOBS_TASK = (
    "rezumi.career_record.reconcile_declared_profile_enrichment_jobs"
)

_MAX_ERROR_MESSAGE = 300


class DeclaredProfileEnrichmentJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"

    @property
    def terminal(self) -> bool:
        return self in {
            DeclaredProfileEnrichmentJobStatus.SUCCEEDED,
            DeclaredProfileEnrichmentJobStatus.FAILED,
            DeclaredProfileEnrichmentJobStatus.DEAD_LETTERED,
        }


class DeclaredProfileEnrichmentJobError(Exception):
    """Base class for expected declared-profile job failures."""


class DeclaredProfileEnrichmentJobNotFound(DeclaredProfileEnrichmentJobError, CareerRecordNotFound):
    """The job is absent from the authenticated owner's scope."""


class DeclaredProfileEnrichmentJobConflict(DeclaredProfileEnrichmentJobError, CareerRecordConflict):
    """A concurrent enqueue raced the active-job uniqueness guard."""


@dataclass(frozen=True, slots=True)
class DeclaredProfileEnrichmentJobPolicy:
    max_attempts: int = 3
    max_outbox_attempts: int = 8
    retry_base_seconds: int = 5
    retry_max_seconds: int = 900

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_outbox_attempts < 1:
            raise ValueError("declared-profile job policy attempts must be positive")
        if self.retry_base_seconds < 1 or self.retry_max_seconds < self.retry_base_seconds:
            raise ValueError("declared-profile job policy retry window is invalid")


@dataclass(slots=True)
class DeclaredProfileEnrichmentJob:
    id: UUID
    owner_user_id: UUID
    personal_fact_id: UUID
    trace_id: str
    status: DeclaredProfileEnrichmentJobStatus
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    next_attempt_at: datetime | None = None
    completed_at: datetime | None = None
    result_platform: str | None = None
    result_achievements_created: int | None = None
    result_evidence_created: int | None = None
    error_message: str | None = None


@dataclass(slots=True)
class DeclaredProfileEnrichmentOutboxMessage:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    task_name: str
    trace_id: str
    attempts: int
    max_attempts: int
    created_at: datetime
    next_attempt_at: datetime
    published_at: datetime | None = None
    dead_lettered_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        return self.published_at is not None or self.dead_lettered_at is not None


@dataclass(frozen=True, slots=True)
class DeclaredProfileEnrichmentJobView:
    job_id: UUID
    personal_fact_id: UUID
    status: DeclaredProfileEnrichmentJobStatus
    attempts: int
    max_attempts: int
    result_platform: str | None
    result_achievements_created: int | None
    result_evidence_created: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DeclaredProfileEnrichmentOutboxDispatchResult:
    published: int
    failed: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class DeclaredProfileEnrichmentReconciliationResult:
    dead_lettered: int


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierGenerator(Protocol):
    def new(self) -> UUID: ...


class DeclaredProfileEnrichmentJobPublisher(Protocol):
    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None: ...


class DeclaredProfileEnrichmentJobUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_active_job_for_fact(
        self, owner_user_id: UUID, personal_fact_id: UUID
    ) -> DeclaredProfileEnrichmentJob | None: ...

    async def add_job(self, job: DeclaredProfileEnrichmentJob) -> None: ...

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> DeclaredProfileEnrichmentJob | None: ...

    async def get_job_system(
        self, job_id: UUID, *, for_update: bool = False
    ) -> DeclaredProfileEnrichmentJob | None: ...

    async def save_job(self, job: DeclaredProfileEnrichmentJob) -> None: ...

    async def list_stale_running_jobs(
        self, stale_before: datetime, limit: int
    ) -> list[DeclaredProfileEnrichmentJob]: ...

    async def add_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None: ...

    async def list_pending_outbox(
        self, now: datetime, limit: int
    ) -> list[DeclaredProfileEnrichmentOutboxMessage]: ...

    async def save_outbox(self, message: DeclaredProfileEnrichmentOutboxMessage) -> None: ...

    async def commit(self) -> None: ...


class DeclaredProfileEnrichmentJobUnitOfWorkFactory(Protocol):
    def __call__(self) -> DeclaredProfileEnrichmentJobUnitOfWork: ...


class DeclaredProfileEnrichmentJobService:
    """Owner-facing enqueue/status API, backed by a durable job + outbox row."""

    def __init__(
        self,
        *,
        unit_of_work: DeclaredProfileEnrichmentJobUnitOfWorkFactory,
        clock: Clock,
        ids: IdentifierGenerator,
        policy: DeclaredProfileEnrichmentJobPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = ids
        self._policy = policy or DeclaredProfileEnrichmentJobPolicy()

    async def enqueue(
        self,
        owner_user_id: UUID,
        personal_fact_id: UUID,
        context: RequestContext,
    ) -> DeclaredProfileEnrichmentJobView:
        now = self._clock.now()
        async with self._uow() as uow:
            active = await uow.get_active_job_for_fact(owner_user_id, personal_fact_id)
            if active is not None:
                return _view(active)
            job = DeclaredProfileEnrichmentJob(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                personal_fact_id=personal_fact_id,
                trace_id=context.trace_id,
                status=DeclaredProfileEnrichmentJobStatus.QUEUED,
                attempts=0,
                max_attempts=self._policy.max_attempts,
                created_at=now,
                updated_at=now,
            )
            await uow.add_job(job)
            await uow.add_outbox(
                DeclaredProfileEnrichmentOutboxMessage(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    job_id=job.id,
                    task_name=PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK,
                    trace_id=context.trace_id,
                    attempts=0,
                    max_attempts=self._policy.max_outbox_attempts,
                    created_at=now,
                    next_attempt_at=now,
                )
            )
            await uow.commit()
        return _view(job)

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> DeclaredProfileEnrichmentJobView:
        async with self._uow() as uow:
            job = await uow.get_job(owner_user_id, job_id)
        if job is None:
            raise DeclaredProfileEnrichmentJobNotFound
        return _view(job)


class DeclaredProfileEnrichmentProcessor:
    """Restricted-worker use case: run one job to completion or reschedule it."""

    def __init__(
        self,
        *,
        unit_of_work: DeclaredProfileEnrichmentJobUnitOfWorkFactory,
        clock: Clock,
        ids: IdentifierGenerator,
        enrichment: DeclaredProfileEnrichmentService,
        policy: DeclaredProfileEnrichmentJobPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = ids
        self._enrichment = enrichment
        self._policy = policy or DeclaredProfileEnrichmentJobPolicy()

    async def process_job(self, job_id: UUID) -> DeclaredProfileEnrichmentJobStatus:
        job = await self._claim(job_id)
        if job is None:
            return DeclaredProfileEnrichmentJobStatus.RUNNING
        try:
            result = await self._enrichment.enrich_personal_fact(
                job.owner_user_id,
                job.personal_fact_id,
                RequestContext(job.owner_user_id, f"job-{job.id}", job.trace_id),
            )
        except (CareerRecordNotFound, DeclaredProfileUnsupported) as exc:
            return await self._fail_permanently(job, _safe_message(exc))
        except DeclaredProfileFetchFailed as exc:
            return await self._retry_or_dead_letter(job, _safe_message(exc))
        except Exception:
            return await self._retry_or_dead_letter(job, "declared profile fetch failed")
        return await self._succeed(job, result)

    async def reconcile(self, limit: int) -> DeclaredProfileEnrichmentReconciliationResult:
        """Dead-letter jobs stuck RUNNING past a worker crash; never silently drop."""
        now = self._clock.now()
        stale_before = now - timedelta(seconds=self._policy.retry_max_seconds)
        dead_lettered = 0
        async with self._uow() as uow:
            for job in await uow.list_stale_running_jobs(stale_before, limit):
                job.status = DeclaredProfileEnrichmentJobStatus.DEAD_LETTERED
                job.error_message = "worker did not report completion before the retry window"
                job.completed_at = now
                job.updated_at = now
                await uow.save_job(job)
                dead_lettered += 1
            await uow.commit()
        return DeclaredProfileEnrichmentReconciliationResult(dead_lettered=dead_lettered)

    async def _claim(self, job_id: UUID) -> DeclaredProfileEnrichmentJob | None:
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_system(job_id, for_update=True)
            if job is None:
                raise DeclaredProfileEnrichmentJobNotFound
            if job.status.terminal:
                return None
            job.status = DeclaredProfileEnrichmentJobStatus.RUNNING
            job.attempts += 1
            job.next_attempt_at = None
            job.updated_at = now
            await uow.save_job(job)
            await uow.commit()
        return job

    async def _succeed(
        self, job: DeclaredProfileEnrichmentJob, result: DeclaredProfileEnrichmentResult
    ) -> DeclaredProfileEnrichmentJobStatus:
        now = self._clock.now()
        async with self._uow() as uow:
            job.status = DeclaredProfileEnrichmentJobStatus.SUCCEEDED
            job.result_platform = result.platform
            job.result_achievements_created = result.achievements_created
            job.result_evidence_created = result.evidence_created
            job.error_message = None
            job.completed_at = now
            job.updated_at = now
            await uow.save_job(job)
            await uow.commit()
        return job.status

    async def _fail_permanently(
        self, job: DeclaredProfileEnrichmentJob, message: str
    ) -> DeclaredProfileEnrichmentJobStatus:
        now = self._clock.now()
        async with self._uow() as uow:
            job.status = DeclaredProfileEnrichmentJobStatus.FAILED
            job.error_message = message
            job.completed_at = now
            job.updated_at = now
            await uow.save_job(job)
            await uow.commit()
        return job.status

    async def _retry_or_dead_letter(
        self, job: DeclaredProfileEnrichmentJob, message: str
    ) -> DeclaredProfileEnrichmentJobStatus:
        now = self._clock.now()
        async with self._uow() as uow:
            if job.attempts >= job.max_attempts:
                job.status = DeclaredProfileEnrichmentJobStatus.DEAD_LETTERED
                job.completed_at = now
            else:
                delay = min(
                    self._policy.retry_max_seconds,
                    self._policy.retry_base_seconds * (2 ** max(0, job.attempts - 1)),
                )
                job.status = DeclaredProfileEnrichmentJobStatus.QUEUED
                job.next_attempt_at = now + timedelta(seconds=delay)
                await uow.add_outbox(
                    DeclaredProfileEnrichmentOutboxMessage(
                        id=self._ids.new(),
                        owner_user_id=job.owner_user_id,
                        job_id=job.id,
                        task_name=PROCESS_DECLARED_PROFILE_ENRICHMENT_TASK,
                        trace_id=job.trace_id,
                        attempts=0,
                        max_attempts=self._policy.max_outbox_attempts,
                        created_at=now,
                        next_attempt_at=job.next_attempt_at,
                    )
                )
            job.error_message = message
            job.updated_at = now
            await uow.save_job(job)
            await uow.commit()
        return job.status


class DeclaredProfileEnrichmentOutboxDispatcher:
    """Publish bounded identifier-only enrichment jobs from the durable outbox."""

    def __init__(
        self,
        *,
        unit_of_work: DeclaredProfileEnrichmentJobUnitOfWorkFactory,
        publisher: DeclaredProfileEnrichmentJobPublisher,
        clock: Clock,
    ) -> None:
        self._uow = unit_of_work
        self._publisher = publisher
        self._clock = clock

    async def dispatch_pending(self, limit: int) -> DeclaredProfileEnrichmentOutboxDispatchResult:
        now = self._clock.now()
        published = 0
        failed = 0
        dead_lettered = 0
        async with self._uow() as uow:
            for message in await uow.list_pending_outbox(now, limit):
                try:
                    await self._publisher.publish(
                        message.task_name, message.job_id, message.trace_id
                    )
                except Exception:
                    message.attempts += 1
                    if message.attempts >= message.max_attempts:
                        message.dead_lettered_at = now
                        dead_lettered += 1
                    else:
                        delay = min(900, 5 * (2 ** max(0, message.attempts - 1)))
                        message.next_attempt_at = now + timedelta(seconds=delay)
                        failed += 1
                    await uow.save_outbox(message)
                    continue
                message.published_at = now
                await uow.save_outbox(message)
                published += 1
            await uow.commit()
        return DeclaredProfileEnrichmentOutboxDispatchResult(published, failed, dead_lettered)


def _view(job: DeclaredProfileEnrichmentJob) -> DeclaredProfileEnrichmentJobView:
    return DeclaredProfileEnrichmentJobView(
        job_id=job.id,
        personal_fact_id=job.personal_fact_id,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        result_platform=job.result_platform,
        result_achievements_created=job.result_achievements_created,
        result_evidence_created=job.result_evidence_created,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _safe_message(exc: Exception) -> str:
    # Never surface fetched page text/content here, only the exception's own
    # user-facing message (declared-profile errors already carry safe copy).
    return str(exc)[:_MAX_ERROR_MESSAGE]
