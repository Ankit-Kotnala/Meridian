"""In-memory Change Studio ports for unit tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from rezumi.modules.change_studio.application import (
    ChangeSetRecord,
    JobMatchAnalysisContext,
    RequirementMatchContext,
)
from rezumi.modules.change_studio.domain import (
    ChangeStudioAuditEvent,
    ChangeStudioIdempotencyRecord,
    ChangeStudioNotFound,
    EvidenceGroundingContext,
    MetricContext,
    ProviderRun,
    RequirementGroundingContext,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000601")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000602")
JOB_ID = UUID("00000000-0000-4000-8000-000000000603")
ANALYSIS_ID = UUID("00000000-0000-4000-8000-000000000604")
ALT_ANALYSIS_ID = UUID("00000000-0000-4000-8000-000000000605")
REQUIREMENT_ID = UUID("00000000-0000-4000-8000-000000000606")
MISSING_REQUIREMENT_ID = UUID("00000000-0000-4000-8000-000000000607")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000608")
METRIC_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000609")
EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-00000000060a")
METRIC_EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-00000000060b")


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticJobAnalysisProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[UUID, UUID]] = []

    async def analysis(self, owner_user_id: UUID, analysis_id: UUID) -> JobMatchAnalysisContext:
        self.requests.append((owner_user_id, analysis_id))
        if owner_user_id != OWNER_ID or analysis_id not in {ANALYSIS_ID, ALT_ANALYSIS_ID}:
            raise ChangeStudioNotFound
        return sample_analysis(analysis_id)


class StaticEvidenceProvider:
    def __init__(self, values: tuple[EvidenceGroundingContext, ...] | None = None) -> None:
        self.values = {item.id: item for item in (values or sample_evidence())}
        self.requests: list[tuple[UUID, tuple[UUID, ...]]] = []

    async def evidence_contexts(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[EvidenceGroundingContext, ...]:
        self.requests.append((owner_user_id, evidence_ids))
        if owner_user_id != OWNER_ID:
            return ()
        return tuple(self.values[item] for item in evidence_ids if item in self.values)


class MemoryChangeStudio:
    def __init__(self) -> None:
        self.records: dict[UUID, ChangeSetRecord] = {}
        self.idempotency: dict[tuple[UUID, str], ChangeStudioIdempotencyRecord] = {}
        self.audits: list[ChangeStudioAuditEvent] = []

    def __call__(self) -> MemoryChangeStudio:
        return self

    async def __aenter__(self) -> MemoryChangeStudio:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def add_record(self, record: ChangeSetRecord) -> None:
        self.records[record.change_set.id] = deepcopy(record)

    async def save_record(self, record: ChangeSetRecord) -> None:
        existing = self.records.get(record.change_set.id)
        provider_runs = existing.provider_runs if existing is not None else record.provider_runs
        self.records[record.change_set.id] = deepcopy(replace(record, provider_runs=provider_runs))

    async def get_record(
        self, owner_user_id: UUID, change_set_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None:
        _ = for_update
        record = self.records.get(change_set_id)
        if record is None or record.change_set.owner_user_id != owner_user_id:
            return None
        return deepcopy(record)

    async def get_record_for_question(
        self, owner_user_id: UUID, question_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None:
        _ = for_update
        for record in self.records.values():
            if record.change_set.owner_user_id != owner_user_id:
                continue
            if any(question.id == question_id for question in record.questions):
                return deepcopy(record)
        return None

    async def find_change_set_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeSetRecord | None:
        for record in self.records.values():
            if (
                record.change_set.owner_user_id == owner_user_id
                and record.change_set.idempotency_key == idempotency_key
            ):
                return deepcopy(record)
        return None

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeStudioIdempotencyRecord | None:
        record = self.idempotency.get((owner_user_id, idempotency_key))
        return deepcopy(record) if record is not None else None

    async def add_idempotency(self, record: ChangeStudioIdempotencyRecord) -> None:
        self.idempotency[(record.owner_user_id, record.idempotency_key)] = deepcopy(record)

    async def add_provider_run(self, run: ProviderRun) -> None:
        record = self.records[run.change_set_id]
        self.records[run.change_set_id] = deepcopy(
            replace(record, provider_runs=(*record.provider_runs, run))
        )

    async def add_audit(self, event: ChangeStudioAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def commit(self) -> None:
        return None


def sample_analysis(analysis_id: UUID = ANALYSIS_ID) -> JobMatchAnalysisContext:
    return JobMatchAnalysisContext(
        job_id=JOB_ID,
        job_title="Product Manager",
        analysis_id=analysis_id,
        display_score=74,
        requirements=(
            RequirementMatchContext(
                requirement=RequirementGroundingContext(
                    id=REQUIREMENT_ID,
                    text="Must have experience with user research and product experiments.",
                    requirement_type="skill",
                    importance="mandatory",
                ),
                match_state="strong",
                hard_gap=False,
                evidence_ids=(EVIDENCE_ID,),
            ),
            RequirementMatchContext(
                requirement=RequirementGroundingContext(
                    id=MISSING_REQUIREMENT_ID,
                    text="Preferred experience with billing systems.",
                    requirement_type="domain",
                    importance="preferred",
                ),
                match_state="missing",
                hard_gap=False,
                evidence_ids=(),
            ),
        ),
    )


def sample_evidence() -> tuple[EvidenceGroundingContext, ...]:
    statement = "Confirmed evidence for user research, customer discovery, and product experiments."
    metric_statement = "Improved activation by 40%."
    return (
        EvidenceGroundingContext(
            id=EVIDENCE_ID,
            evidence_revision_id=EVIDENCE_REVISION_ID,
            revision_number=2,
            statement_sha256=hashlib.sha256(statement.encode("utf-8")).hexdigest(),
            title="Confirmed discovery program",
            statement=statement,
            context="Career Record evidence only.",
            strength="confirmed",
            metrics=(),
        ),
        EvidenceGroundingContext(
            id=METRIC_EVIDENCE_ID,
            evidence_revision_id=METRIC_EVIDENCE_REVISION_ID,
            revision_number=3,
            statement_sha256=hashlib.sha256(metric_statement.encode("utf-8")).hexdigest(),
            title="Confirmed activation improvement",
            statement=metric_statement,
            context=None,
            strength="confirmed",
            metrics=(
                MetricContext(
                    value=Decimal("40"),
                    value_max=None,
                    unit="percent",
                    period="launch quarter",
                    attribution="Owner confirmed metric",
                ),
            ),
        ),
    )


def _uuids() -> Iterator[UUID]:
    counter = 0x700
    while True:
        counter += 1
        yield UUID(f"00000000-0000-4000-8000-{counter:012x}")
