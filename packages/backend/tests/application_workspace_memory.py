"""Deterministic in-memory Phase 8 ports for service tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from rezumi.modules.application_workspace.application import (
    ApplicationAnalyticsCursor,
    ApplicationAnalyticsSourceState,
    ApplicationCalendarEntry,
    ApplicationFilter,
    ApplicationInterviewEvidenceReference,
    ApplicationJobSnapshot,
    ApplicationMilestones,
    ApplicationPackView,
    ApplicationReference,
    ApplicationResumeSnapshot,
    ApplicationSourceClaim,
    ApplicationSourceEvidenceReference,
    ApplicationSummary,
    PageCursor,
)
from rezumi.modules.application_workspace.domain import (
    ApplicationAuditEvent,
    ApplicationDocument,
    ApplicationEvent,
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationIdempotencyRecord,
    ApplicationNote,
    ApplicationPack,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationRequirementSupport,
    ApplicationStage,
    ApplicationTask,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000801")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000802")
JOB_ID = UUID("00000000-0000-4000-8000-000000000803")
RESUME_ID = UUID("00000000-0000-4000-8000-000000000804")
RESUME_VERSION_ID = UUID("00000000-0000-4000-8000-000000000805")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000806")
EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-000000000807")
REQUIREMENT_ID = UUID("00000000-0000-4000-8000-000000000808")
CLAIM_ID = UUID("00000000-0000-4000-8000-000000000809")
ANALYSIS_ID = UUID("00000000-0000-4000-8000-00000000080a")
NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticJobProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        job_id: UUID,
    ) -> ApplicationJobSnapshot:
        assert owner_user_id == OWNER_ID
        assert job_id == JOB_ID
        requirement = ApplicationRequirementSnapshot(
            id=REQUIREMENT_ID,
            requirement_type="responsibility",
            importance="mandatory",
            text="Lead cross-functional product delivery.",
            source_start=20,
            source_end=59,
        )
        return ApplicationJobSnapshot(
            job_id=JOB_ID,
            version=4,
            title="Principal Product Engineer",
            company="Example Co",
            location="Remote",
            application_deadline=date(2026, 8, 15),
            latest_analysis_id=ANALYSIS_ID,
            source_sha256="a" * 64,
            source="referral",
            industry="software",
            requirements=(requirement,),
            requirement_support=(
                ApplicationRequirementSupport(
                    analysis_id=ANALYSIS_ID,
                    requirement_id=REQUIREMENT_ID,
                    evidence_id=EVIDENCE_ID,
                ),
            ),
        )


class StaticResumeProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        version_id: UUID,
    ) -> ApplicationResumeSnapshot:
        assert owner_user_id == OWNER_ID
        assert version_id == RESUME_VERSION_ID
        statement = "Led cross-functional product delivery."
        reference = ApplicationSourceEvidenceReference(
            evidence_id=EVIDENCE_ID,
            evidence_revision_id=EVIDENCE_REVISION_ID,
            revision_number=3,
            statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
            claim_sha256=hashlib.sha256(statement.encode()).hexdigest(),
            link_basis="evidence_statement",
            source_skill_id=None,
        )
        return ApplicationResumeSnapshot(
            resume_id=RESUME_ID,
            version_id=RESUME_VERSION_ID,
            version_number=7,
            title="Product resume",
            target_role="Principal Product Engineer",
            evidence_references=(reference,),
            claims=(
                ApplicationSourceClaim(
                    id=CLAIM_ID,
                    text=statement,
                    evidence_references=(reference,),
                ),
            ),
            plain_text=statement,
        )


class StaticEvidenceProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]:
        assert owner_user_id == OWNER_ID
        assert tuple(reference.evidence_id for reference in references) == (EVIDENCE_ID,)
        statement = "Led cross-functional product delivery."
        return (
            ApplicationEvidencePin(
                evidence_id=EVIDENCE_ID,
                evidence_revision_id=EVIDENCE_REVISION_ID,
                revision_number=3,
                statement=statement,
                statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
                strength="confirmed",
                has_numeric_claim=False,
            ),
        )

    async def validate_current(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationInterviewEvidenceReference, ...],
    ) -> None:
        assert owner_user_id == OWNER_ID
        assert tuple(reference.evidence_id for reference in references) == (EVIDENCE_ID,)


class MemoryApplicationWorkspace:
    def __init__(self) -> None:
        self.applications: dict[UUID, ApplicationRecord] = {}
        self.tasks: dict[UUID, ApplicationTask] = {}
        self.notes: dict[UUID, ApplicationNote] = {}
        self.events: dict[UUID, ApplicationEvent] = {}
        self.packs: dict[UUID, ApplicationPack] = {}
        self.documents: dict[UUID, ApplicationDocument] = {}
        self.idempotency: dict[tuple[UUID, str], ApplicationIdempotencyRecord] = {}
        self.audits: list[ApplicationAuditEvent] = []

    def __call__(self) -> MemoryApplicationWorkspace:
        return self

    async def __aenter__(self) -> MemoryApplicationWorkspace:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def lock_owner_quota(self, owner_user_id: UUID) -> None:
        _ = owner_user_id

    async def lock_application_quota(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None:
        _ = owner_user_id, application_id

    async def list_application_summaries(
        self,
        owner_user_id: UUID,
        filter_by: ApplicationFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationSummary]:
        records = [
            record
            for record in self.applications.values()
            if self._active(record, owner_user_id)
            and (filter_by.stage is None or record.stage == filter_by.stage)
            and (filter_by.outcome is None or record.outcome_status == filter_by.outcome)
            and (filter_by.source is None or record.source == filter_by.source)
            and (filter_by.industry is None or record.industry == filter_by.industry)
            and (
                filter_by.query is None
                or filter_by.query.casefold()
                in " ".join(
                    (
                        record.job_title,
                        record.company or "",
                        record.location or "",
                        record.resume_title,
                    )
                ).casefold()
            )
        ]
        records.sort(
            key=lambda record: (record.updated_at, str(record.id)),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return [self._summary(record) for record in records[offset : offset + limit]]

    async def count_applications(self, owner_user_id: UUID) -> int:
        return sum(self._active(record, owner_user_id) for record in self.applications.values())

    async def count_manual_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        manual_kinds = {
            ApplicationEventKind.INTERVIEW,
            ApplicationEventKind.CONTACT,
            ApplicationEventKind.CUSTOM,
        }
        return sum(
            event.owner_user_id == owner_user_id
            and event.application_id == application_id
            and event.event_kind in manual_kinds
            and self._active_parent(application_id, owner_user_id)
            for event in self.events.values()
        )

    async def count_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return sum(
            task.owner_user_id == owner_user_id
            and task.application_id == application_id
            and self._active_parent(application_id, owner_user_id)
            for task in self.tasks.values()
        )

    async def count_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return sum(
            note.owner_user_id == owner_user_id
            and note.application_id == application_id
            and self._active_parent(application_id, owner_user_id)
            for note in self.notes.values()
        )

    async def count_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> int:
        return sum(
            pack.owner_user_id == owner_user_id
            and pack.application_id == application_id
            and self._active_parent(application_id, owner_user_id)
            for pack in self.packs.values()
        )

    async def list_application_records(
        self,
        owner_user_id: UUID,
        after: ApplicationAnalyticsCursor | None,
        limit: int,
    ) -> list[ApplicationRecord]:
        records = [
            deepcopy(record)
            for record in sorted(
                self.applications.values(),
                key=lambda item: (item.created_at, str(item.id)),
            )
            if self._active(record, owner_user_id)
            and (
                after is None
                or (record.created_at, str(record.id))
                > (after.created_at, str(after.application_id))
            )
        ]
        return records[:limit]

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> ApplicationAnalyticsSourceState:
        applications = [
            record for record in self.applications.values() if self._active(record, owner_user_id)
        ]
        events = [
            event
            for event in self.events.values()
            if event.owner_user_id == owner_user_id
            and self._active_parent(event.application_id, owner_user_id)
        ]
        return ApplicationAnalyticsSourceState(
            application_count=len(applications),
            application_version_sum=sum(record.version for record in applications),
            event_count=len(events),
            max_application_updated_at=max(
                (record.updated_at for record in applications),
                default=None,
            ),
            max_event_created_at=max(
                (event.created_at for event in events),
                default=None,
            ),
        )

    async def list_application_milestones(
        self,
        owner_user_id: UUID,
        application_ids: tuple[UUID, ...],
    ) -> dict[UUID, ApplicationMilestones]:
        results: dict[UUID, ApplicationMilestones] = {}
        for application_id in application_ids:
            events = sorted(
                (
                    event
                    for event in self.events.values()
                    if event.owner_user_id == owner_user_id
                    and event.application_id == application_id
                ),
                key=lambda event: (event.occurred_at, str(event.id)),
            )
            applied = response = interview = offer = outcome = None
            for event in events:
                stage = (
                    event.metadata.get("stage")
                    if event.event_kind == ApplicationEventKind.CREATED
                    else event.metadata.get("to_stage")
                    if event.event_kind == ApplicationEventKind.STAGE_CHANGED
                    else None
                )
                if stage == ApplicationStage.APPLIED.value and applied is None:
                    applied = event.occurred_at
                if (
                    stage
                    in {
                        ApplicationStage.RECRUITER_SCREEN.value,
                        ApplicationStage.INTERVIEW.value,
                        ApplicationStage.ASSESSMENT.value,
                        ApplicationStage.OFFER.value,
                        ApplicationStage.REJECTED.value,
                    }
                    or event.event_kind == ApplicationEventKind.INTERVIEW
                ) and response is None:
                    response = event.occurred_at
                if (
                    stage == ApplicationStage.INTERVIEW.value
                    or event.event_kind == ApplicationEventKind.INTERVIEW
                ) and interview is None:
                    interview = event.occurred_at
                if stage == ApplicationStage.OFFER.value and offer is None:
                    offer = event.occurred_at
                if (
                    stage
                    in {
                        ApplicationStage.OFFER.value,
                        ApplicationStage.REJECTED.value,
                        ApplicationStage.WITHDRAWN.value,
                    }
                    or event.event_kind == ApplicationEventKind.OUTCOME_RECORDED
                ):
                    outcome = event.occurred_at
            results[application_id] = ApplicationMilestones(
                first_applied_at=applied,
                first_response_at=response,
                first_interview_at=interview,
                first_offer_at=offer,
                outcome_at=outcome,
            )
        return results

    async def list_calendar_entries(
        self,
        owner_user_id: UUID,
        start: date,
        end: date,
        limit: int,
    ) -> list[ApplicationCalendarEntry]:
        entries: list[ApplicationCalendarEntry] = []
        for record in self.applications.values():
            if not self._active(record, owner_user_id):
                continue
            for kind, value, title in (
                (
                    "application_deadline",
                    record.application_deadline,
                    f"{record.job_title} application deadline",
                ),
                (
                    "follow_up",
                    record.follow_up_at,
                    f"Follow up on {record.job_title}",
                ),
            ):
                if value is not None and start <= value <= end:
                    entries.append(
                        ApplicationCalendarEntry(
                            id=uuid5(NAMESPACE_URL, f"{record.id}:{kind}"),
                            application_id=record.id,
                            kind=kind,
                            title=title,
                            on_date=value,
                            completed=False,
                        )
                    )
        for task in self.tasks.values():
            if (
                task.owner_user_id == owner_user_id
                and self._active_parent(task.application_id, owner_user_id)
                and task.due_at is not None
                and start <= task.due_at <= end
            ):
                entries.append(
                    ApplicationCalendarEntry(
                        id=task.id,
                        application_id=task.application_id,
                        kind="task",
                        title=task.title,
                        on_date=task.due_at,
                        completed=task.completed_at is not None,
                    )
                )
        entries.sort(key=lambda item: (item.on_date, item.kind, str(item.id)))
        return entries[:limit]

    async def get_application_summary(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationSummary | None:
        record = self.applications.get(application_id)
        if record is None or not self._active(record, owner_user_id):
            return None
        return deepcopy(self._summary(record))

    async def get_application_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationReference | None:
        record = self.applications.get(application_id)
        if record is None or not self._active(record, owner_user_id):
            return None
        return ApplicationReference(
            application_id=record.id,
            stage=record.stage,
        )

    async def get_application_record(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        for_update: bool = False,
    ) -> ApplicationRecord | None:
        _ = for_update
        record = self.applications.get(application_id)
        if record is None or not self._active(record, owner_user_id):
            return None
        return deepcopy(record)

    async def add_application(self, record: ApplicationRecord) -> None:
        self.applications[record.id] = deepcopy(record)

    async def save_application(self, record: ApplicationRecord) -> None:
        self.applications[record.id] = deepcopy(record)

    async def delete_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None:
        record = self.applications.get(application_id)
        if record is None or record.owner_user_id != owner_user_id:
            return
        self.applications.pop(application_id)
        self.tasks = {
            item_id: item
            for item_id, item in self.tasks.items()
            if item.application_id != application_id
        }
        self.notes = {
            item_id: item
            for item_id, item in self.notes.items()
            if item.application_id != application_id
        }
        self.events = {
            item_id: item
            for item_id, item in self.events.items()
            if item.application_id != application_id
        }
        pack_ids = {
            pack.id for pack in self.packs.values() if pack.application_id == application_id
        }
        self.packs = {
            item_id: item
            for item_id, item in self.packs.items()
            if item.application_id != application_id
        }
        self.documents = {
            item_id: item
            for item_id, item in self.documents.items()
            if item.pack_id not in pack_ids
        }

    async def add_task(self, task: ApplicationTask) -> None:
        self.tasks[task.id] = deepcopy(task)

    async def list_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationTask]:
        if not self._active_parent(application_id, owner_user_id):
            return []
        tasks = sorted(
            (
                task
                for task in self.tasks.values()
                if task.owner_user_id == owner_user_id and task.application_id == application_id
            ),
            key=lambda task: (
                task.due_at is None,
                task.due_at or date.max,
                task.created_at,
                str(task.id),
            ),
        )
        offset = after.offset if after is not None else 0
        return deepcopy(tasks[offset : offset + limit])

    async def get_task(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        task_id: UUID,
        *,
        for_update: bool = False,
    ) -> ApplicationTask | None:
        _ = for_update
        task = self.tasks.get(task_id)
        if (
            task is None
            or task.owner_user_id != owner_user_id
            or task.application_id != application_id
            or not self._active_parent(application_id, owner_user_id)
        ):
            return None
        return deepcopy(task)

    async def save_task(self, task: ApplicationTask) -> None:
        self.tasks[task.id] = deepcopy(task)

    async def add_note(self, note: ApplicationNote) -> None:
        self.notes[note.id] = deepcopy(note)

    async def list_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationNote]:
        if not self._active_parent(application_id, owner_user_id):
            return []
        notes = sorted(
            (
                note
                for note in self.notes.values()
                if note.owner_user_id == owner_user_id and note.application_id == application_id
            ),
            key=lambda note: (note.created_at, str(note.id)),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return deepcopy(notes[offset : offset + limit])

    async def get_note(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        note_id: UUID,
    ) -> ApplicationNote | None:
        note = self.notes.get(note_id)
        if (
            note is None
            or note.owner_user_id != owner_user_id
            or note.application_id != application_id
            or not self._active_parent(application_id, owner_user_id)
        ):
            return None
        return deepcopy(note)

    async def add_event(self, event: ApplicationEvent) -> None:
        self.events[event.id] = deepcopy(event)

    async def list_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        before_occurred_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> list[ApplicationEvent]:
        if (before_occurred_at is None) != (before_id is None):
            raise ValueError("event cursor fields must be provided together")
        if not self._active_parent(application_id, owner_user_id):
            return []
        events = [
            event
            for event in self.events.values()
            if event.owner_user_id == owner_user_id and event.application_id == application_id
        ]
        if before_occurred_at is not None and before_id is not None:
            events = [
                event
                for event in events
                if (event.occurred_at, event.id) < (before_occurred_at, before_id)
            ]
        events.sort(
            key=lambda event: (event.occurred_at, event.id),
            reverse=True,
        )
        return deepcopy(events[:limit])

    async def get_event(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        event_id: UUID,
    ) -> ApplicationEvent | None:
        event = self.events.get(event_id)
        if (
            event is None
            or event.owner_user_id != owner_user_id
            or event.application_id != application_id
            or not self._active_parent(application_id, owner_user_id)
        ):
            return None
        return deepcopy(event)

    async def add_pack(
        self,
        pack: ApplicationPack,
        documents: tuple[ApplicationDocument, ...],
    ) -> None:
        self.packs[pack.id] = deepcopy(pack)
        for document in documents:
            self.documents[document.id] = deepcopy(document)

    async def list_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        after: PageCursor | None,
        limit: int,
    ) -> list[ApplicationPack]:
        if not self._active_parent(application_id, owner_user_id):
            return []
        packs = sorted(
            (
                pack
                for pack in self.packs.values()
                if pack.owner_user_id == owner_user_id and pack.application_id == application_id
            ),
            key=lambda pack: (pack.created_at, str(pack.id)),
            reverse=True,
        )
        offset = after.offset if after is not None else 0
        return deepcopy(packs[offset : offset + limit])

    async def get_pack(
        self,
        owner_user_id: UUID,
        pack_id: UUID,
    ) -> ApplicationPackView | None:
        pack = self.packs.get(pack_id)
        if (
            pack is None
            or pack.owner_user_id != owner_user_id
            or not self._active_parent(pack.application_id, owner_user_id)
        ):
            return None
        return deepcopy(self._pack_view(pack))

    async def find_pack_by_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> ApplicationPackView | None:
        for pack in self.packs.values():
            if pack.owner_user_id == owner_user_id and pack.idempotency_key == idempotency_key:
                return await self.get_pack(owner_user_id, pack.id)
        return None

    async def get_document(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        document_id: UUID,
    ) -> ApplicationDocument | None:
        document = self.documents.get(document_id)
        if (
            document is None
            or document.owner_user_id != owner_user_id
            or document.application_id != application_id
            or not self._active_parent(application_id, owner_user_id)
        ):
            return None
        return deepcopy(document)

    async def save_document(self, document: ApplicationDocument) -> None:
        self.documents[document.id] = deepcopy(document)

    async def add_idempotency(
        self,
        record: ApplicationIdempotencyRecord,
    ) -> None:
        self.idempotency[(record.owner_user_id, record.idempotency_key)] = deepcopy(record)

    async def find_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> ApplicationIdempotencyRecord | None:
        record = self.idempotency.get((owner_user_id, idempotency_key))
        return deepcopy(record) if record is not None else None

    async def add_audit(self, event: ApplicationAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def commit(self) -> None:
        return None

    def _active(self, record: ApplicationRecord, owner_user_id: UUID) -> bool:
        return record.owner_user_id == owner_user_id

    def _active_parent(self, application_id: UUID, owner_user_id: UUID) -> bool:
        record = self.applications.get(application_id)
        return record is not None and self._active(record, owner_user_id)

    def _pack_view(self, pack: ApplicationPack) -> ApplicationPackView:
        return ApplicationPackView(
            pack=pack,
            documents=tuple(
                document
                for document in self.documents.values()
                if document.pack_id == pack.id
                and document.owner_user_id == pack.owner_user_id
                and document.deleted_at is None
            ),
        )

    def _summary(self, record: ApplicationRecord) -> ApplicationSummary:
        tasks = [
            task
            for task in self.tasks.values()
            if task.application_id == record.id and task.owner_user_id == record.owner_user_id
        ]
        return ApplicationSummary(
            application=deepcopy(record),
            task_count=len(tasks),
            open_task_count=sum(task.completed_at is None for task in tasks),
            note_count=sum(
                note.application_id == record.id and note.owner_user_id == record.owner_user_id
                for note in self.notes.values()
            ),
            event_count=sum(
                event.application_id == record.id and event.owner_user_id == record.owner_user_id
                for event in self.events.values()
            ),
            pack_count=sum(
                pack.application_id == record.id and pack.owner_user_id == record.owner_user_id
                for pack in self.packs.values()
            ),
        )


def _uuids() -> Iterator[UUID]:
    counter = 0x900
    while True:
        counter += 1
        yield UUID(f"00000000-0000-4000-8000-{counter:012x}")
