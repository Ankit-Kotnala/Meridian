"""In-memory Job Match ports for unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from rezumi.modules.job_match.application import (
    AnalysisRecord,
    ImportedJobSource,
    JobFilter,
    JobRecord,
    PageCursor,
)
from rezumi.modules.job_match.domain import (
    CareerMatchSnapshot,
    JobMatchAuditEvent,
    JobPosting,
    JobRequirement,
    JobSourceKind,
    OpportunityPriorityAnalysis,
    RolePreference,
    SnapshotEvidence,
    SnapshotSkill,
)

PRODUCT_ROLE_ID = UUID("00000000-0000-4000-8000-000000000411")


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticSnapshotProvider:
    def __init__(self, snapshot: CareerMatchSnapshot) -> None:
        self.snapshot_value = snapshot
        self.requests: list[UUID] = []

    async def snapshot(self, owner_user_id: UUID) -> CareerMatchSnapshot:
        self.requests.append(owner_user_id)
        return self.snapshot_value


class StaticRoleContextProvider:
    async def role_title(self, owner_user_id: UUID, role_id: UUID) -> str:
        _ = owner_user_id
        if role_id != PRODUCT_ROLE_ID:
            from rezumi.modules.job_match.domain import JobMatchNotFound

            raise JobMatchNotFound
        return "Product Manager"


class StaticImporter:
    async def fetch(self, url: str) -> ImportedJobSource:
        return ImportedJobSource(
            final_url=url,
            title="Imported Product Manager",
            company="Example Co",
            location="Remote",
            source_text=sample_job_text("Imported Product Manager"),
        )


class MemoryJobMatch:
    def __init__(self) -> None:
        self.jobs: dict[UUID, JobPosting] = {}
        self.requirements: dict[UUID, tuple[JobRequirement, ...]] = {}
        self.analyses: dict[UUID, AnalysisRecord] = {}
        self.priorities: dict[UUID, OpportunityPriorityAnalysis] = {}
        self.audits: list[JobMatchAuditEvent] = []
        self.role_preferences: dict[UUID, RolePreference] = {}

    def __call__(self) -> MemoryJobMatch:
        return self

    async def __aenter__(self) -> MemoryJobMatch:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def add_job(self, record: JobRecord) -> None:
        self.jobs[record.job.id] = deepcopy(record.job)
        self.requirements[record.job.id] = deepcopy(record.requirements)

    async def save_job(self, record: JobRecord) -> None:
        self.jobs[record.job.id] = deepcopy(record.job)
        self.requirements[record.job.id] = deepcopy(record.requirements)

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID, *, for_update: bool = False
    ) -> JobRecord | None:
        _ = for_update
        job = self.jobs.get(job_id)
        if job is None or job.owner_user_id != owner_user_id:
            return None
        return JobRecord(job=deepcopy(job), requirements=deepcopy(self.requirements[job_id]))

    async def list_jobs(
        self, owner_user_id: UUID, filter_by: JobFilter, after: PageCursor | None, limit: int
    ) -> list[JobRecord]:
        offset = after.offset if after is not None else 0
        records = [
            JobRecord(job=deepcopy(job), requirements=deepcopy(self.requirements[job.id]))
            for job in sorted(self.jobs.values(), key=lambda item: item.updated_at, reverse=True)
            if job.owner_user_id == owner_user_id
            and (filter_by.source_kind is None or job.source_kind is filter_by.source_kind)
            and (filter_by.target_role_id is None or job.target_role_id == filter_by.target_role_id)
            and (
                filter_by.query is None
                or filter_by.query.casefold() in job.title.casefold()
                or (
                    job.company is not None and filter_by.query.casefold() in job.company.casefold()
                )
            )
        ]
        return records[offset : offset + limit]

    async def delete_job(self, owner_user_id: UUID, job_id: UUID) -> None:
        job = self.jobs.get(job_id)
        if job is not None and job.owner_user_id == owner_user_id:
            del self.jobs[job_id]
            self.requirements.pop(job_id, None)

    async def find_job_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> JobRecord | None:
        for job in self.jobs.values():
            if job.owner_user_id == owner_user_id and job.idempotency_key == idempotency_key:
                return JobRecord(
                    job=deepcopy(job), requirements=deepcopy(self.requirements[job.id])
                )
        return None

    async def find_job_by_external(
        self,
        owner_user_id: UUID,
        source_kind: JobSourceKind,
        external_id: str,
    ) -> JobRecord | None:
        for job in self.jobs.values():
            if (
                job.owner_user_id == owner_user_id
                and job.source_kind is source_kind
                and job.external_id == external_id
            ):
                return JobRecord(
                    job=deepcopy(job),
                    requirements=deepcopy(self.requirements[job.id]),
                )
        return None

    async def add_analysis(self, record: AnalysisRecord) -> None:
        self.analyses[record.analysis.id] = deepcopy(record)

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> AnalysisRecord | None:
        record = self.analyses.get(analysis_id)
        if record is None or record.analysis.owner_user_id != owner_user_id:
            return None
        return deepcopy(record)

    async def latest_analysis_for_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> AnalysisRecord | None:
        records = [
            record
            for record in self.analyses.values()
            if record.analysis.owner_user_id == owner_user_id and record.analysis.job_id == job_id
        ]
        if not records:
            return None
        return deepcopy(max(records, key=lambda item: item.analysis.created_at))

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None:
        for record in self.analyses.values():
            if (
                record.analysis.owner_user_id == owner_user_id
                and record.analysis.idempotency_key == idempotency_key
            ):
                return deepcopy(record)
        return None

    async def add_priority(self, priority: OpportunityPriorityAnalysis) -> None:
        self.priorities[priority.id] = deepcopy(priority)

    async def get_priority(
        self, owner_user_id: UUID, priority_id: UUID
    ) -> OpportunityPriorityAnalysis | None:
        priority = self.priorities.get(priority_id)
        if priority is None or priority.owner_user_id != owner_user_id:
            return None
        return deepcopy(priority)

    async def find_priority_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> OpportunityPriorityAnalysis | None:
        for priority in self.priorities.values():
            if (
                priority.owner_user_id == owner_user_id
                and priority.idempotency_key == idempotency_key
            ):
                return deepcopy(priority)
        return None

    async def add_audit(self, event: JobMatchAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def get_role_preference(self, owner_user_id: UUID) -> RolePreference | None:
        preference = self.role_preferences.get(owner_user_id)
        return deepcopy(preference) if preference is not None else None

    async def upsert_role_preference(self, preference: RolePreference) -> None:
        self.role_preferences[preference.owner_user_id] = deepcopy(preference)

    async def commit(self) -> None:
        return None


def sample_snapshot() -> CareerMatchSnapshot:
    skill_id = UUID("00000000-0000-4000-8000-000000000501")
    evidence_id = UUID("00000000-0000-4000-8000-000000000502")
    return CareerMatchSnapshot(
        skills=(SnapshotSkill(skill_id, "User research", "Product", "advanced"),),
        entities=(),
        evidence=(
            SnapshotEvidence(
                id=evidence_id,
                title="Confirmed discovery program",
                statement=(
                    "Confirmed evidence for user research, customer discovery, "
                    "and product experiments."
                ),
                context=None,
                strength="confirmed",
                skill_ids=(skill_id,),
                entity_ids=(),
                has_numeric_claim=False,
            ),
        ),
    )


def sample_job_text(title: str = "Product Manager") -> str:
    return "\n".join(
        [
            f"Title: {title}",
            "Company: Example Co",
            "Location: Remote",
            "Requirements:",
            "- Must have experience with user research and customer discovery.",
            "- Build product experiments with engineering and design.",
            "- Preferred experience with SaaS analytics.",
        ]
    )


def _uuids() -> Iterator[UUID]:
    counter = 0x600
    while True:
        counter += 1
        yield UUID(f"00000000-0000-4000-8000-{counter:012x}")
