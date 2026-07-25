"""Application workspace use cases and deterministic grounded pack generation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from uuid import UUID

from careeros.modules.application_workspace.domain import (
    TERMINAL_APPLICATION_STAGES,
    ApplicationAuditAction,
    ApplicationAuditEvent,
    ApplicationClaimEvidenceLink,
    ApplicationConsistencyFinding,
    ApplicationConsistencySeverity,
    ApplicationDocument,
    ApplicationDocumentClaim,
    ApplicationDocumentKind,
    ApplicationDocumentStatus,
    ApplicationEvent,
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationIdempotencyRecord,
    ApplicationNote,
    ApplicationPack,
    ApplicationPackStatus,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationRequirementSupport,
    ApplicationStage,
    ApplicationTask,
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceValidationError,
    ApplicationWorkspaceVersionConflict,
    ConsistencyStatus,
    OutcomeStatus,
    validate_stage_transition,
)

from .models import (
    ApplicationAnalyticsSnapshot,
    ApplicationCalendarEntry,
    ApplicationEventCursor,
    ApplicationFilter,
    ApplicationInterviewContext,
    ApplicationMilestones,
    ApplicationPackView,
    ApplicationResumeSnapshot,
    ApplicationSourceClaim,
    ApplicationSummary,
    CreateApplication,
    CreateApplicationEvent,
    CreateApplicationNote,
    CreateApplicationTask,
    GenerateApplicationPack,
    PageCursor,
    PagedResult,
    RequestContext,
    UnsetType,
    UpdateApplication,
    UpdateApplicationTask,
    event_page_result,
    page_result,
)
from .ports import (
    ApplicationWorkspaceUnitOfWorkFactory,
    Clock,
    EvidenceSnapshotProvider,
    IdentifierFactory,
    JobSnapshotProvider,
    ResumeVersionSnapshotProvider,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_DOCUMENT_KINDS = tuple(ApplicationDocumentKind)
_SORTS = frozenset({"updated_desc", "deadline_asc"})
_MANUAL_EVENT_KINDS = frozenset(
    {
        ApplicationEventKind.INTERVIEW,
        ApplicationEventKind.CONTACT,
        ApplicationEventKind.CUSTOM,
    }
)
_SERVER_ASSIGNED_EVENT_TIME = "server_assigned"
_NUMERIC_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,.%]*")
_DATE_TOKEN = re.compile(
    r"\b(?:"
    r"(?:19|20)\d{2}(?:[-/]\d{1,2}(?:[-/]\d{1,2})?)?"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)\s+(?:19|20)\d{2}"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ApplicationWorkspacePolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_applications: int = 300
    max_tasks_per_application: int = 100
    max_notes_per_application: int = 200
    max_manual_events_per_application: int = 300
    max_packs_per_application: int = 100
    max_calendar_entries: int = 500
    max_analytics_records: int = 1_000

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("application workspace page limits are invalid")
        if (
            min(
                self.max_applications,
                self.max_tasks_per_application,
                self.max_notes_per_application,
                self.max_manual_events_per_application,
                self.max_packs_per_application,
                self.max_calendar_entries,
                self.max_analytics_records,
            )
            < 1
        ):
            raise ValueError("application workspace collection limits are invalid")


class ApplicationWorkspaceService:
    """Owner-scoped Phase 8 application workflows with immutable input pins."""

    def __init__(
        self,
        *,
        unit_of_work: ApplicationWorkspaceUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        jobs: JobSnapshotProvider,
        resumes: ResumeVersionSnapshotProvider,
        evidence: EvidenceSnapshotProvider,
        policy: ApplicationWorkspacePolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._jobs = jobs
        self._resumes = resumes
        self._evidence = evidence
        self._policy = policy or ApplicationWorkspacePolicy()

    async def list_applications(
        self,
        owner_user_id: UUID,
        filter_by: ApplicationFilter | None = None,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[ApplicationSummary]:
        selected = _validated_filter(filter_by or ApplicationFilter())
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            items = await uow.list_application_summaries(
                owner_user_id,
                selected,
                after,
                page_size + 1,
            )
        return page_result(items, cursor=after, limit=page_size)

    async def list_calendar(
        self,
        owner_user_id: UUID,
        start: date,
        end: date,
        *,
        limit: int = 500,
    ) -> tuple[ApplicationCalendarEntry, ...]:
        if end < start or (end - start).days > 366:
            raise ApplicationWorkspaceValidationError(
                "calendar range must be ordered and no longer than 366 days"
            )
        if not 1 <= limit <= self._policy.max_calendar_entries:
            raise ApplicationWorkspaceValidationError("calendar limit is out of range")
        async with self._uow() as uow:
            entries = await uow.list_calendar_entries(owner_user_id, start, end, limit)
        return tuple(entries)

    async def list_analytics_snapshots(
        self,
        owner_user_id: UUID,
        *,
        limit: int = 1_000,
    ) -> tuple[ApplicationAnalyticsSnapshot, ...]:
        if not 1 <= limit <= self._policy.max_analytics_records:
            raise ApplicationWorkspaceValidationError("analytics limit is out of range")
        async with self._uow() as uow:
            records = await uow.list_application_records(owner_user_id, limit)
            milestones = await uow.list_application_milestones(
                owner_user_id,
                tuple(record.id for record in records),
            )
        return tuple(
            _analytics_snapshot(
                record,
                milestones.get(record.id, ApplicationMilestones()),
            )
            for record in records
        )

    async def get_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationSummary:
        async with self._uow() as uow:
            summary = await uow.get_application_summary(owner_user_id, application_id)
        if summary is None:
            raise ApplicationWorkspaceNotFound
        return summary

    async def list_tasks(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[ApplicationTask]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_application_record(owner_user_id, application_id) is None:
                raise ApplicationWorkspaceNotFound
            items = await uow.list_tasks(
                owner_user_id,
                application_id,
                after,
                page_size + 1,
            )
        return page_result(items, cursor=after, limit=page_size)

    async def list_notes(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[ApplicationNote]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_application_record(owner_user_id, application_id) is None:
                raise ApplicationWorkspaceNotFound
            items = await uow.list_notes(
                owner_user_id,
                application_id,
                after,
                page_size + 1,
            )
        return page_result(items, cursor=after, limit=page_size)

    async def list_events(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[ApplicationEvent]:
        before = ApplicationEventCursor.decode(
            cursor,
            application_id=application_id,
        )
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_application_record(owner_user_id, application_id) is None:
                raise ApplicationWorkspaceNotFound
            items = await uow.list_events(
                owner_user_id,
                application_id,
                before.occurred_at if before is not None else None,
                before.event_id if before is not None else None,
                page_size + 1,
            )
        return event_page_result(
            items,
            application_id=application_id,
            limit=page_size,
        )

    async def list_packs(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[ApplicationPack]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            if await uow.get_application_record(owner_user_id, application_id) is None:
                raise ApplicationWorkspaceNotFound
            items = await uow.list_packs(
                owner_user_id,
                application_id,
                after,
                page_size + 1,
            )
        return page_result(items, cursor=after, limit=page_size)

    async def get_pack(self, owner_user_id: UUID, pack_id: UUID) -> ApplicationPackView:
        async with self._uow() as uow:
            view = await uow.get_pack(owner_user_id, pack_id)
        if view is None:
            raise ApplicationWorkspaceNotFound
        return view

    async def get_interview_context(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> ApplicationInterviewContext:
        async with self._uow() as uow:
            record = await uow.get_application_record(owner_user_id, application_id)
        if record is None:
            raise ApplicationWorkspaceNotFound
        return ApplicationInterviewContext(
            application_id=record.id,
            stage=record.stage,
            job_id=record.job_id,
            job_version=record.job_version,
            job_title=record.job_title,
            company=record.company,
            requirements=record.job_requirements,
            resume_version_id=record.resume_version_id,
            resume_version_number=record.resume_version_number,
            claims=record.resume_claims,
            evidence_pins=record.evidence_pins,
        )

    async def create_application(
        self,
        owner_user_id: UUID,
        command: CreateApplication,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ApplicationSummary:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "application-create",
            {
                "jobId": str(command.job_id),
                "resumeVersionId": str(command.resume_version_id),
                "stage": command.stage.value,
                "deadline": _date(command.application_deadline),
                "followUpAt": _date(command.follow_up_at),
                "contacts": _contacts_payload(command.contacts),
                "referralStatus": command.referral_status.value,
                "source": command.source,
                "industry": command.industry,
            },
        )
        replay = await self._view_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        job = await self._jobs.snapshot(owner_user_id, command.job_id)
        resume = await self._resumes.snapshot(owner_user_id, command.resume_version_id)
        pins = await self._evidence.snapshot(
            owner_user_id,
            resume.evidence_references,
        )
        claims = _pin_claims(
            resume.claims,
            pins,
            job.requirements,
            job.requirement_support,
        )
        now = self._clock.now()
        application_id = self._ids.new()
        record = ApplicationRecord(
            id=application_id,
            owner_user_id=owner_user_id,
            job_id=job.job_id,
            job_version=job.version,
            job_title=job.title,
            company=job.company,
            location=job.location,
            job_analysis_id=job.latest_analysis_id,
            job_source_sha256=job.source_sha256,
            job_requirements=job.requirements,
            requirement_support=job.requirement_support,
            resume_id=resume.resume_id,
            resume_version_id=resume.version_id,
            resume_version_number=resume.version_number,
            resume_title=resume.title,
            resume_evidence_ids=resume.evidence_ids,
            evidence_pins=pins,
            resume_claims=claims,
            source=command.source if command.source is not None else job.source,
            industry=command.industry if command.industry is not None else job.industry,
            stage=command.stage,
            application_deadline=command.application_deadline or job.application_deadline,
            follow_up_at=command.follow_up_at,
            contacts=command.contacts,
            referral_status=command.referral_status,
            outcome_status=_outcome_for_stage(command.stage),
            rejection_reason=None,
            offer_summary=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        created_event = self._event(
            owner_user_id,
            application_id,
            ApplicationEventKind.CREATED,
            "Application created",
            None,
            {"stage": record.stage.value},
            now,
        )
        try:
            async with self._uow() as uow:
                await uow.lock_owner_quota(owner_user_id)
                if await uow.count_applications(owner_user_id) >= self._policy.max_applications:
                    raise ApplicationWorkspaceConflict("application limit reached")
                await uow.add_application(record)
                await uow.add_event(created_event)
                await uow.add_idempotency(
                    self._idem(
                        owner_user_id,
                        idempotency_key,
                        fingerprint,
                        "application",
                        application_id,
                        "application",
                        application_id,
                        now,
                    )
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        ApplicationAuditAction.APPLICATION_CREATED,
                        "application",
                        application_id,
                        context,
                        now,
                        job_id=str(job.job_id),
                        resume_version_id=str(resume.version_id),
                        evidence_revision_count=len(pins),
                        requirement_count=len(job.requirements),
                    )
                )
                await uow.commit()
        except ApplicationWorkspaceIdempotencyConflict:
            replay = await self._view_replay(owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            raise
        return await self.get_application(owner_user_id, application_id)

    async def update_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        command: UpdateApplication,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> ApplicationSummary:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        resume: ApplicationResumeSnapshot | None = None
        resume_pins: tuple[ApplicationEvidencePin, ...] | None = None
        if not isinstance(command.resume_version_id, UnsetType):
            resume = await self._resumes.snapshot(
                owner_user_id,
                command.resume_version_id,
            )
            resume_pins = await self._evidence.snapshot(
                owner_user_id,
                resume.evidence_references,
            )
        async with self._uow() as uow:
            await uow.lock_application_quota(owner_user_id, application_id)
            record = await uow.get_application_record(
                owner_user_id,
                application_id,
                for_update=True,
            )
            if record is None:
                raise ApplicationWorkspaceNotFound
            self._version(record.version, expected_version)
            resume_changed = resume is not None and resume.version_id != record.resume_version_id
            resume_change_reason = _resume_change_reason(
                command.resume_change_reason,
                changed=resume_changed,
            )

            pins = record.evidence_pins
            claims = record.resume_claims
            if resume is not None and resume_pins is not None:
                pins = resume_pins
                claims = _pin_claims(
                    resume.claims,
                    pins,
                    record.job_requirements,
                    record.requirement_support,
                )

            requested_stage = (
                record.stage if isinstance(command.stage, UnsetType) else command.stage
            )
            requested_outcome = (
                record.outcome_status
                if isinstance(command.outcome_status, UnsetType)
                else command.outcome_status
            )
            stage, outcome, reopen_reason = _stage_and_outcome(
                record,
                requested_stage,
                requested_outcome,
                stage_was_set=not isinstance(command.stage, UnsetType),
                outcome_was_set=not isinstance(command.outcome_status, UnsetType),
                reopen_reason=command.reopen_reason,
            )
            updated = replace(
                record,
                resume_id=resume.resume_id if resume is not None else record.resume_id,
                resume_version_id=(
                    resume.version_id if resume is not None else record.resume_version_id
                ),
                resume_version_number=(
                    resume.version_number if resume is not None else record.resume_version_number
                ),
                resume_title=resume.title if resume is not None else record.resume_title,
                resume_evidence_ids=(
                    resume.evidence_ids if resume is not None else record.resume_evidence_ids
                ),
                evidence_pins=pins,
                resume_claims=claims,
                source=_patch(command.source, record.source),
                industry=_patch(command.industry, record.industry),
                stage=stage,
                application_deadline=_patch(
                    command.application_deadline,
                    record.application_deadline,
                ),
                follow_up_at=_patch(command.follow_up_at, record.follow_up_at),
                contacts=_patch(command.contacts, record.contacts),
                referral_status=_patch(
                    command.referral_status,
                    record.referral_status,
                ),
                outcome_status=outcome,
                rejection_reason=_outcome_text(
                    outcome == OutcomeStatus.REJECTED,
                    command.rejection_reason,
                    record.rejection_reason,
                ),
                offer_summary=_outcome_text(
                    outcome == OutcomeStatus.OFFER,
                    command.offer_summary,
                    record.offer_summary,
                ),
                version=record.version + 1,
                updated_at=now,
            )
            await uow.save_application(updated)
            if updated.stage != record.stage:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.STAGE_CHANGED,
                        f"Moved to {_stage_label(updated.stage)}",
                        reopen_reason,
                        {
                            "from_stage": record.stage.value,
                            "to_stage": updated.stage.value,
                        },
                        now,
                    )
                )
            if updated.application_deadline != record.application_deadline:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.DEADLINE_CHANGED,
                        "Application deadline changed",
                        None,
                        {
                            "previous_date": _date(record.application_deadline) or "none",
                            "next_date": _date(updated.application_deadline) or "none",
                        },
                        now,
                    )
                )
            if updated.follow_up_at != record.follow_up_at:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.FOLLOW_UP_CHANGED,
                        "Follow-up date changed",
                        None,
                        {
                            "previous_date": _date(record.follow_up_at) or "none",
                            "next_date": _date(updated.follow_up_at) or "none",
                        },
                        now,
                    )
                )
            if updated.outcome_status != record.outcome_status:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.OUTCOME_RECORDED,
                        f"Outcome recorded: {updated.outcome_status.value}",
                        updated.rejection_reason or updated.offer_summary,
                        {"outcome": updated.outcome_status.value},
                        now,
                    )
                )
            if resume_changed:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.RESUME_VERSION_CHANGED,
                        "Pinned resume version changed",
                        resume_change_reason,
                        {
                            "previous_resume_version_id": str(record.resume_version_id),
                            "next_resume_version_id": str(updated.resume_version_id),
                        },
                        now,
                    )
                )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    (
                        ApplicationAuditAction.RESUME_VERSION_CHANGED
                        if resume_changed
                        else ApplicationAuditAction.APPLICATION_STAGE_CHANGED
                        if updated.stage != record.stage
                        else ApplicationAuditAction.APPLICATION_UPDATED
                    ),
                    "application",
                    application_id,
                    context,
                    now,
                    stage=updated.stage.value,
                    reopened=record.stage in TERMINAL_APPLICATION_STAGES,
                    previous_resume_version_id=(
                        str(record.resume_version_id) if resume_changed else None
                    ),
                    next_resume_version_id=(
                        str(updated.resume_version_id) if resume_changed else None
                    ),
                    previous_evidence_revision_ids=(
                        [str(pin.evidence_revision_id) for pin in record.evidence_pins]
                        if resume_changed
                        else None
                    ),
                    next_evidence_revision_ids=(
                        [str(pin.evidence_revision_id) for pin in updated.evidence_pins]
                        if resume_changed
                        else None
                    ),
                    resume_change_reason=resume_change_reason,
                )
            )
            await uow.commit()
        return await self.get_application(owner_user_id, application_id)

    async def delete_application(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_application_record(
                owner_user_id,
                application_id,
                for_update=True,
            )
            if record is None:
                raise ApplicationWorkspaceNotFound
            self._version(record.version, expected_version)
            await uow.delete_application(owner_user_id, application_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ApplicationAuditAction.APPLICATION_DELETED,
                    "application",
                    application_id,
                    context,
                    now,
                )
            )
            await uow.commit()

    async def create_task(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        command: CreateApplicationTask,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ApplicationTask:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "application-task-create",
            {
                "applicationId": str(application_id),
                "title": command.title,
                "dueAt": _date(command.due_at),
            },
        )
        replay = await self._task_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay
        now = self._clock.now()
        task = ApplicationTask(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            application_id=application_id,
            title=command.title,
            due_at=command.due_at,
            completed_at=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._uow() as uow:
                await uow.lock_application_quota(owner_user_id, application_id)
                summary = await uow.get_application_summary(
                    owner_user_id,
                    application_id,
                )
                if summary is None:
                    raise ApplicationWorkspaceNotFound
                if summary.task_count >= self._policy.max_tasks_per_application:
                    raise ApplicationWorkspaceConflict("task limit reached")
                await uow.add_task(task)
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.TASK_ADDED,
                        "Task added",
                        None,
                        {"task_id": str(task.id)},
                        now,
                    )
                )
                await uow.add_idempotency(
                    self._idem(
                        owner_user_id,
                        idempotency_key,
                        fingerprint,
                        "application",
                        application_id,
                        "application_task",
                        task.id,
                        now,
                    )
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        ApplicationAuditAction.TASK_CREATED,
                        "application_task",
                        task.id,
                        context,
                        now,
                        application_id=str(application_id),
                    )
                )
                await uow.commit()
        except ApplicationWorkspaceIdempotencyConflict:
            replay = await self._task_replay(owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            raise
        return task

    async def update_task(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        task_id: UUID,
        command: UpdateApplicationTask,
        *,
        expected_version: int,
        context: RequestContext,
    ) -> ApplicationTask:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_application_quota(owner_user_id, application_id)
            task = await uow.get_task(
                owner_user_id,
                application_id,
                task_id,
                for_update=True,
            )
            if task is None:
                raise ApplicationWorkspaceNotFound
            self._version(task.version, expected_version)
            completed_at = task.completed_at
            if not isinstance(command.completed, UnsetType):
                if command.completed and completed_at is None:
                    completed_at = now
                elif not command.completed:
                    completed_at = None
            updated = replace(
                task,
                title=_patch(command.title, task.title),
                due_at=_patch(command.due_at, task.due_at),
                completed_at=completed_at,
                version=task.version + 1,
                updated_at=now,
            )
            adds_event = task.completed_at is None and updated.completed_at is not None
            await uow.save_task(updated)
            if adds_event:
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        task.application_id,
                        ApplicationEventKind.TASK_COMPLETED,
                        "Task completed",
                        None,
                        {"task_id": str(task.id)},
                        now,
                    )
                )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ApplicationAuditAction.TASK_UPDATED,
                    "application_task",
                    task.id,
                    context,
                    now,
                    application_id=str(task.application_id),
                )
            )
            await uow.commit()
        return updated

    async def create_note(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        command: CreateApplicationNote,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ApplicationNote:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "application-note-create",
            {"applicationId": str(application_id), "bodySha256": _sha(command.body)},
        )
        replay = await self._note_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay
        now = self._clock.now()
        note = ApplicationNote(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            application_id=application_id,
            body=command.body,
            created_at=now,
        )
        try:
            async with self._uow() as uow:
                await uow.lock_application_quota(owner_user_id, application_id)
                summary = await uow.get_application_summary(
                    owner_user_id,
                    application_id,
                )
                if summary is None:
                    raise ApplicationWorkspaceNotFound
                if summary.note_count >= self._policy.max_notes_per_application:
                    raise ApplicationWorkspaceConflict("note limit reached")
                await uow.add_note(note)
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.NOTE_ADDED,
                        "Note added",
                        None,
                        {"note_id": str(note.id)},
                        now,
                    )
                )
                await uow.add_idempotency(
                    self._idem(
                        owner_user_id,
                        idempotency_key,
                        fingerprint,
                        "application",
                        application_id,
                        "application_note",
                        note.id,
                        now,
                    )
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        ApplicationAuditAction.NOTE_CREATED,
                        "application_note",
                        note.id,
                        context,
                        now,
                        application_id=str(application_id),
                    )
                )
                await uow.commit()
        except ApplicationWorkspaceIdempotencyConflict:
            replay = await self._note_replay(owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            raise
        return note

    async def record_event(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        command: CreateApplicationEvent,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ApplicationEvent:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        if command.event_kind not in _MANUAL_EVENT_KINDS:
            raise ApplicationWorkspaceValidationError(
                "only interview, contact, and custom events may be recorded manually"
            )
        occurred_at = command.occurred_at or self._clock.now()
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ApplicationWorkspaceValidationError("event time must include a UTC offset")
        metadata = command.metadata or {}
        fingerprint = _fingerprint(
            "application-event-create",
            {
                "applicationId": str(application_id),
                "kind": command.event_kind.value,
                "occurredAt": (
                    command.occurred_at.isoformat()
                    if command.occurred_at is not None
                    else _SERVER_ASSIGNED_EVENT_TIME
                ),
                "title": command.title,
                "description": command.description,
                "metadata": metadata,
            },
        )
        replay = await self._event_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay
        now = self._clock.now()
        event = self._event(
            owner_user_id,
            application_id,
            command.event_kind,
            command.title,
            command.description,
            metadata,
            occurred_at,
            created_at=now,
        )
        try:
            async with self._uow() as uow:
                await uow.lock_application_quota(owner_user_id, application_id)
                if (
                    await uow.get_application_record(
                        owner_user_id,
                        application_id,
                    )
                    is None
                ):
                    raise ApplicationWorkspaceNotFound
                if (
                    await uow.count_manual_events(owner_user_id, application_id)
                    >= self._policy.max_manual_events_per_application
                ):
                    raise ApplicationWorkspaceConflict("manual event limit reached")
                await uow.add_event(event)
                await uow.add_idempotency(
                    self._idem(
                        owner_user_id,
                        idempotency_key,
                        fingerprint,
                        "application",
                        application_id,
                        "application_event",
                        event.id,
                        now,
                    )
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        ApplicationAuditAction.EVENT_RECORDED,
                        "application_event",
                        event.id,
                        context,
                        now,
                        application_id=str(application_id),
                    )
                )
                await uow.commit()
        except ApplicationWorkspaceIdempotencyConflict:
            replay = await self._event_replay(owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            raise
        return event

    async def generate_pack(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        command: GenerateApplicationPack,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ApplicationPackView:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        include_kinds = _pack_kinds(command.include_kinds)
        fingerprint = _fingerprint(
            "application-pack-generate",
            {
                "applicationId": str(application_id),
                "kinds": [kind.value for kind in include_kinds],
            },
        )
        replay = await self._pack_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay
        now = self._clock.now()
        try:
            async with self._uow() as uow:
                await uow.lock_application_quota(owner_user_id, application_id)
                summary = await uow.get_application_summary(
                    owner_user_id,
                    application_id,
                )
                if summary is None:
                    raise ApplicationWorkspaceNotFound
                if summary.pack_count >= self._policy.max_packs_per_application:
                    raise ApplicationWorkspaceConflict("application pack limit reached")
                record = summary.application
                if not record.resume_claims:
                    raise ApplicationWorkspaceConflict("resume version has no grounded claims")
                pack_id = self._ids.new()
                documents = tuple(
                    self._document(
                        owner_user_id,
                        record,
                        pack_id,
                        kind,
                        now,
                    )
                    for kind in include_kinds
                )
                findings = _dedupe_findings(
                    (
                        *_merge_findings(documents),
                        *_pack_findings(record, documents),
                    )
                )
                consistency = _status(findings)
                pack = ApplicationPack(
                    id=pack_id,
                    owner_user_id=owner_user_id,
                    application_id=application_id,
                    job_id=record.job_id,
                    job_version=record.job_version,
                    resume_version_id=record.resume_version_id,
                    resume_version_number=record.resume_version_number,
                    application_version=record.version,
                    evidence_revision_ids=tuple(
                        pin.evidence_revision_id for pin in record.evidence_pins
                    ),
                    requirement_ids=tuple(
                        requirement.id for requirement in record.job_requirements
                    ),
                    status=(
                        ApplicationPackStatus.BLOCKED
                        if consistency == ConsistencyStatus.FAILED
                        else ApplicationPackStatus.GENERATED
                    ),
                    consistency_status=consistency,
                    consistency_findings=findings,
                    idempotency_key=idempotency_key,
                    idempotency_fingerprint=fingerprint,
                    created_at=now,
                )
                await uow.add_pack(pack, documents)
                await uow.add_event(
                    self._event(
                        owner_user_id,
                        application_id,
                        ApplicationEventKind.PACK_GENERATED,
                        "Application pack generated",
                        None,
                        {
                            "pack_id": str(pack.id),
                            "status": pack.consistency_status.value,
                        },
                        now,
                    )
                )
                await uow.add_idempotency(
                    self._idem(
                        owner_user_id,
                        idempotency_key,
                        fingerprint,
                        "application",
                        application_id,
                        "application_pack",
                        pack.id,
                        now,
                    )
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        ApplicationAuditAction.PACK_GENERATED,
                        "application_pack",
                        pack.id,
                        context,
                        now,
                        application_id=str(application_id),
                        resume_version_id=str(record.resume_version_id),
                        job_id=str(record.job_id),
                        evidence_revision_count=len(pack.evidence_revision_ids),
                        requirement_count=len(pack.requirement_ids),
                    )
                )
                await uow.commit()
        except ApplicationWorkspaceIdempotencyConflict:
            replay = await self._pack_replay(owner_user_id, idempotency_key, fingerprint)
            if replay is not None:
                return replay
            raise
        return ApplicationPackView(pack=pack, documents=documents)

    async def delete_document(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        document_id: UUID,
        *,
        context: RequestContext,
    ) -> ApplicationDocument:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            document = await uow.get_document(
                owner_user_id,
                application_id,
                document_id,
            )
            if document is None:
                raise ApplicationWorkspaceNotFound
            if document.status == ApplicationDocumentStatus.DELETED:
                return document
            deleted = replace(
                document,
                title="[deleted]",
                status=ApplicationDocumentStatus.DELETED,
                body="[deleted]",
                source_evidence_ids=(),
                source_requirement_ids=(),
                claims=(),
                consistency_status=ConsistencyStatus.PASSED,
                consistency_findings=(),
                content_sha256=_sha("[deleted]"),
                deleted_at=now,
            )
            await uow.save_document(deleted)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ApplicationAuditAction.DOCUMENT_DELETED,
                    "application_document",
                    document_id,
                    context,
                    now,
                    application_id=str(document.application_id),
                )
            )
            await uow.commit()
        return deleted

    def _document(
        self,
        owner_user_id: UUID,
        record: ApplicationRecord,
        pack_id: UUID,
        kind: ApplicationDocumentKind,
        created_at: datetime,
    ) -> ApplicationDocument:
        claims = _claims_for_kind(record.resume_claims, kind)
        title = _document_title(kind)
        body = _document_body(record, kind, claims)
        findings = _document_findings(record, body, claims)
        consistency = _status(findings)
        return ApplicationDocument(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            application_id=record.id,
            pack_id=pack_id,
            kind=kind,
            title=title,
            body=body,
            source_evidence_ids=tuple(
                dict.fromkeys(evidence_id for claim in claims for evidence_id in claim.evidence_ids)
            ),
            source_requirement_ids=tuple(
                dict.fromkeys(
                    requirement_id for claim in claims for requirement_id in claim.requirement_ids
                )
            ),
            claims=claims,
            status=(
                ApplicationDocumentStatus.BLOCKED
                if consistency == ConsistencyStatus.FAILED
                else ApplicationDocumentStatus.GENERATED
            ),
            consistency_status=consistency,
            consistency_findings=findings,
            content_sha256=_sha(body),
            created_at=created_at,
            deleted_at=None,
        )

    def _event(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        kind: ApplicationEventKind,
        title: str,
        description: str | None,
        metadata: dict[str, str],
        occurred_at: datetime,
        *,
        created_at: datetime | None = None,
    ) -> ApplicationEvent:
        created = occurred_at if created_at is None else created_at
        return ApplicationEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            application_id=application_id,
            event_kind=kind,
            occurred_at=occurred_at,
            title=title,
            description=description,
            metadata=metadata,
            created_at=created,
        )

    def _audit(
        self,
        owner_user_id: UUID,
        action: ApplicationAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        **metadata: object,
    ) -> ApplicationAuditEvent:
        return ApplicationAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            created_at=created_at,
            metadata=metadata,
        )

    def _idem(
        self,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        target_kind: str,
        target_id: UUID | None,
        response_kind: str,
        response_id: UUID | None,
        created_at: datetime,
    ) -> ApplicationIdempotencyRecord:
        return ApplicationIdempotencyRecord(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            target_kind=target_kind,
            target_id=target_id,
            response_kind=response_kind,
            response_id=response_id,
            created_at=created_at,
        )

    async def _view_replay(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationSummary | None:
        record = await self._idempotency_record(
            owner_user_id,
            idempotency_key,
            fingerprint,
        )
        if record is None:
            return None
        if record.response_id is None:
            raise ApplicationWorkspaceNotFound
        return await self.get_application(owner_user_id, record.response_id)

    async def _task_replay(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationTask | None:
        record = await self._idempotency_record(
            owner_user_id,
            idempotency_key,
            fingerprint,
        )
        if record is None:
            return None
        if record.target_id is None or record.response_id is None:
            raise ApplicationWorkspaceNotFound
        async with self._uow() as uow:
            task = await uow.get_task(
                owner_user_id,
                record.target_id,
                record.response_id,
            )
        if task is None:
            raise ApplicationWorkspaceNotFound
        return task

    async def _note_replay(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationNote | None:
        record = await self._idempotency_record(
            owner_user_id,
            idempotency_key,
            fingerprint,
        )
        if record is None:
            return None
        if record.target_id is None or record.response_id is None:
            raise ApplicationWorkspaceNotFound
        async with self._uow() as uow:
            note = await uow.get_note(
                owner_user_id,
                record.target_id,
                record.response_id,
            )
        if note is None:
            raise ApplicationWorkspaceNotFound
        return note

    async def _event_replay(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationEvent | None:
        record = await self._idempotency_record(
            owner_user_id,
            idempotency_key,
            fingerprint,
        )
        if record is None:
            return None
        if record.target_id is None or record.response_id is None:
            raise ApplicationWorkspaceNotFound
        async with self._uow() as uow:
            event = await uow.get_event(
                owner_user_id,
                record.target_id,
                record.response_id,
            )
        if event is None:
            raise ApplicationWorkspaceNotFound
        return event

    async def _pack_replay(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationPackView | None:
        async with self._uow() as uow:
            existing = await uow.find_pack_by_idempotency(
                owner_user_id,
                idempotency_key,
            )
        if existing is None:
            return None
        if existing.pack.idempotency_fingerprint != fingerprint:
            raise ApplicationWorkspaceIdempotencyConflict
        return existing

    async def _idempotency_record(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> ApplicationIdempotencyRecord | None:
        async with self._uow() as uow:
            existing = await uow.find_idempotency(owner_user_id, idempotency_key)
        if existing is None:
            return None
        if existing.request_fingerprint != fingerprint:
            raise ApplicationWorkspaceIdempotencyConflict
        return existing

    def _page_size(self, limit: int | None) -> int:
        if limit is None:
            return self._policy.default_page_size
        if not 1 <= limit <= self._policy.max_page_size:
            raise ApplicationWorkspaceValidationError("limit is out of range")
        return limit

    @staticmethod
    def _authorize(owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise ApplicationWorkspaceNotFound

    @staticmethod
    def _idempotency(value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise ApplicationWorkspaceValidationError("idempotency key is invalid")

    @staticmethod
    def _version(current: int, expected: int) -> None:
        if expected <= 0:
            raise ApplicationWorkspaceValidationError("version is invalid")
        if current != expected:
            raise ApplicationWorkspaceVersionConflict


def _validated_filter(value: ApplicationFilter) -> ApplicationFilter:
    query = value.query.strip() if value.query is not None else None
    source = value.source.strip() if value.source is not None else None
    industry = value.industry.strip() if value.industry is not None else None
    if query is not None and not 1 <= len(query) <= 200:
        raise ApplicationWorkspaceValidationError("query must be 1 to 200 characters")
    if source is not None and not 1 <= len(source) <= 120:
        raise ApplicationWorkspaceValidationError("source filter is invalid")
    if industry is not None and not 1 <= len(industry) <= 120:
        raise ApplicationWorkspaceValidationError("industry filter is invalid")
    if value.sort not in _SORTS:
        raise ApplicationWorkspaceValidationError("sort is invalid")
    return replace(value, query=query, source=source, industry=industry)


def _patch[T](value: T | UnsetType, current: T) -> T:
    return current if isinstance(value, UnsetType) else value


def _outcome_text(
    applicable: bool,
    patch: str | None | UnsetType,
    current: str | None,
) -> str | None:
    if not applicable:
        return None
    return _patch(patch, current)


def _resume_change_reason(value: str | None, *, changed: bool) -> str | None:
    normalized = " ".join(value.strip().split()) if value is not None else None
    if changed:
        if normalized is None or not 1 <= len(normalized) <= 500:
            raise ApplicationWorkspaceValidationError(
                "resume change reason is required and must be 500 characters or fewer"
            )
        return normalized
    if normalized:
        raise ApplicationWorkspaceValidationError(
            "resume change reason requires a different resume version"
        )
    return None


def _stage_and_outcome(
    record: ApplicationRecord,
    requested_stage: ApplicationStage,
    requested_outcome: OutcomeStatus,
    *,
    stage_was_set: bool,
    outcome_was_set: bool,
    reopen_reason: str | None,
) -> tuple[ApplicationStage, OutcomeStatus, str | None]:
    stage = requested_stage
    outcome = requested_outcome
    if outcome_was_set and outcome != OutcomeStatus.NONE:
        outcome_stage = {
            OutcomeStatus.OFFER: ApplicationStage.OFFER,
            OutcomeStatus.REJECTED: ApplicationStage.REJECTED,
            OutcomeStatus.WITHDRAWN: ApplicationStage.WITHDRAWN,
        }[outcome]
        if stage_was_set and stage != outcome_stage:
            raise ApplicationWorkspaceValidationError(
                "stage and outcome patches describe different states"
            )
        stage = outcome_stage
    elif stage_was_set:
        outcome = _outcome_for_stage(stage)
    elif outcome_was_set and outcome == OutcomeStatus.NONE:
        if record.stage in TERMINAL_APPLICATION_STAGES or record.stage == ApplicationStage.OFFER:
            raise ApplicationWorkspaceValidationError(
                "clearing an outcome also requires an active target stage"
            )
    normalized_reason = validate_stage_transition(
        record.stage,
        stage,
        reopen_reason=reopen_reason,
    )
    return stage, _outcome_for_stage(stage), normalized_reason


def _outcome_for_stage(stage: ApplicationStage) -> OutcomeStatus:
    return {
        ApplicationStage.OFFER: OutcomeStatus.OFFER,
        ApplicationStage.REJECTED: OutcomeStatus.REJECTED,
        ApplicationStage.WITHDRAWN: OutcomeStatus.WITHDRAWN,
    }.get(stage, OutcomeStatus.NONE)


def _pin_claims(
    claims: tuple[ApplicationSourceClaim, ...],
    pins: tuple[ApplicationEvidencePin, ...],
    requirements: tuple[ApplicationRequirementSnapshot, ...],
    requirement_support: tuple[ApplicationRequirementSupport, ...],
) -> tuple[ApplicationDocumentClaim, ...]:
    pins_by_id = {pin.evidence_id: pin for pin in pins}
    pinned: list[ApplicationDocumentClaim] = []
    for claim in claims:
        links: list[ApplicationClaimEvidenceLink] = []
        normalized_claim_hash = _sha(" ".join(claim.text.strip().split()))
        for reference in claim.evidence_references:
            pin = pins_by_id.get(reference.evidence_id)
            if (
                pin is None
                or pin.evidence_revision_id != reference.evidence_revision_id
                or pin.revision_number != reference.revision_number
                or pin.statement_sha256 != reference.statement_sha256
                or reference.claim_sha256 != normalized_claim_hash
            ):
                raise ApplicationWorkspaceConflict(
                    "resume claim provenance does not match its immutable evidence revision"
                )
            links.append(
                ApplicationClaimEvidenceLink(
                    evidence_id=reference.evidence_id,
                    evidence_revision_id=pin.evidence_revision_id,
                )
            )
        pinned.append(
            ApplicationDocumentClaim(
                id=claim.id,
                text=claim.text,
                evidence_links=tuple(links),
                requirement_ids=_supported_requirements(
                    claim.evidence_ids,
                    requirements,
                    requirement_support,
                ),
            )
        )
    return tuple(pinned)


def _supported_requirements(
    evidence_ids: tuple[UUID, ...],
    requirements: tuple[ApplicationRequirementSnapshot, ...],
    requirement_support: tuple[ApplicationRequirementSupport, ...],
) -> tuple[UUID, ...]:
    cited = set(evidence_ids)
    supported = {link.requirement_id for link in requirement_support if link.evidence_id in cited}
    return tuple(requirement.id for requirement in requirements if requirement.id in supported)


def _fingerprint(kind: str, payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            {"kind": kind, "payload": payload},
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _date(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _contacts_payload(contacts: tuple[object, ...]) -> list[dict[str, object]]:
    return [
        {
            "name": getattr(contact, "name", None),
            "role": getattr(contact, "role", None),
            "email": getattr(contact, "email", None),
            "url": getattr(contact, "url", None),
        }
        for contact in contacts
    ]


def _pack_kinds(values: tuple[str, ...]) -> tuple[ApplicationDocumentKind, ...]:
    if not values:
        return _DOCUMENT_KINDS
    kinds: list[ApplicationDocumentKind] = []
    for value in values:
        try:
            kind = ApplicationDocumentKind(value)
        except ValueError as exc:
            raise ApplicationWorkspaceValidationError("document kind is invalid") from exc
        if kind not in kinds:
            kinds.append(kind)
    return tuple(kinds)


def _claims_for_kind(
    claims: tuple[ApplicationDocumentClaim, ...],
    kind: ApplicationDocumentKind,
) -> tuple[ApplicationDocumentClaim, ...]:
    if kind == ApplicationDocumentKind.TAILORED_RESUME:
        return claims
    maximum = 4 if kind == ApplicationDocumentKind.ACHIEVEMENT_SUMMARY else 3
    return tuple(
        sorted(
            claims,
            key=lambda claim: (
                -len(claim.requirement_ids),
                str(claim.id),
            ),
        )[:maximum]
    )


def _document_title(kind: ApplicationDocumentKind) -> str:
    return {
        ApplicationDocumentKind.TAILORED_RESUME: "Tailored resume",
        ApplicationDocumentKind.COVER_LETTER: "Cover letter",
        ApplicationDocumentKind.PROFESSIONAL_BIO: "Professional bio",
        ApplicationDocumentKind.INTEREST_ANSWER: "Why interested response",
        ApplicationDocumentKind.FIT_ANSWER: "Why fit response",
        ApplicationDocumentKind.RECRUITER_MESSAGE: "Recruiter message",
        ApplicationDocumentKind.HIRING_MANAGER_MESSAGE: "Hiring-manager message",
        ApplicationDocumentKind.REFERRAL_REQUEST: "Referral request",
        ApplicationDocumentKind.LINKEDIN_CONNECTION_NOTE: "LinkedIn connection note",
        ApplicationDocumentKind.FOLLOW_UP_EMAIL: "Follow-up email",
        ApplicationDocumentKind.INTERVIEW_INTRODUCTION: "Interview introduction",
        ApplicationDocumentKind.ACHIEVEMENT_SUMMARY: "Selected achievement summary",
    }[kind]


def _document_body(
    record: ApplicationRecord,
    kind: ApplicationDocumentKind,
    claims: tuple[ApplicationDocumentClaim, ...],
) -> str:
    company = record.company or "the organization"
    role = record.job_title
    claim_lines = "\n".join(f"- {claim.text}" for claim in claims)
    if kind == ApplicationDocumentKind.TAILORED_RESUME:
        return "\n".join(
            [
                record.resume_title,
                f"Target role: {role}",
                "",
                "Evidence-backed resume claims:",
                claim_lines,
            ]
        )
    if kind == ApplicationDocumentKind.COVER_LETTER:
        return "\n".join(
            [
                f"Dear {company} hiring team,",
                "",
                f"I am applying for {role}. The evidence-backed experience I would emphasize is:",
                claim_lines,
                "",
                "I would welcome the chance to discuss how this background maps to the role.",
            ]
        )
    prefix = {
        ApplicationDocumentKind.PROFESSIONAL_BIO: f"Professional bio for {role}:",
        ApplicationDocumentKind.INTEREST_ANSWER: (
            f"I am interested in {role} at {company}. "
            "The role connects to these evidence-backed career facts:"
        ),
        ApplicationDocumentKind.FIT_ANSWER: (f"My evidence-backed fit for {role} is based on:"),
        ApplicationDocumentKind.RECRUITER_MESSAGE: (
            f"Hello, I am exploring {role} at {company}. Relevant background:"
        ),
        ApplicationDocumentKind.HIRING_MANAGER_MESSAGE: (
            f"Hello, I am interested in the {role} work. Evidence-backed highlights:"
        ),
        ApplicationDocumentKind.REFERRAL_REQUEST: (
            f"I am preparing an application for {role} at {company}. "
            "Would you be comfortable considering a referral based on this background?"
        ),
        ApplicationDocumentKind.LINKEDIN_CONNECTION_NOTE: (
            f"I am applying for {role} at {company} and would value connecting. "
            "Relevant background:"
        ),
        ApplicationDocumentKind.FOLLOW_UP_EMAIL: (
            f"Following up on my interest in {role} at {company}. "
            "The strongest evidence-backed fit points remain:"
        ),
        ApplicationDocumentKind.INTERVIEW_INTRODUCTION: (f"Interview introduction for {role}:"),
        ApplicationDocumentKind.ACHIEVEMENT_SUMMARY: (f"Selected achievement summary for {role}:"),
    }[kind]
    return f"{prefix}\n{claim_lines}"


def _document_findings(
    record: ApplicationRecord,
    body: str,
    claims: tuple[ApplicationDocumentClaim, ...],
) -> tuple[ApplicationConsistencyFinding, ...]:
    findings: list[ApplicationConsistencyFinding] = []
    allowed_claims = {claim.id: claim for claim in record.resume_claims}
    pins_by_id = {pin.evidence_id: pin for pin in record.evidence_pins}
    requirement_ids = {requirement.id for requirement in record.job_requirements}
    for claim in claims:
        source_claim = allowed_claims.get(claim.id)
        if source_claim is None or source_claim.text != claim.text:
            findings.append(
                _finding(
                    "unsupported_claim",
                    "A generated claim is not present in the pinned resume version.",
                    claim.id,
                    blocking=True,
                )
            )
        if claim.text not in body:
            findings.append(
                _finding(
                    "claim_missing_from_document",
                    "The document body does not contain a claim recorded in its ledger.",
                    claim.id,
                    blocking=True,
                )
            )
        for link in claim.evidence_links:
            pin = pins_by_id.get(link.evidence_id)
            if pin is None or pin.evidence_revision_id != link.evidence_revision_id:
                findings.append(
                    _finding(
                        "evidence_revision_not_pinned",
                        "A claim cites an evidence revision outside the application snapshot.",
                        claim.id,
                        blocking=True,
                    )
                )
        if not set(claim.requirement_ids).issubset(requirement_ids):
            findings.append(
                _finding(
                    "requirement_not_pinned",
                    "A claim cites a requirement outside the immutable job snapshot.",
                    claim.id,
                    blocking=True,
                )
            )
        numeric_tokens = set(_NUMERIC_TOKEN.findall(claim.text))
        if numeric_tokens:
            evidence_text = " ".join(
                pins_by_id[link.evidence_id].statement
                for link in claim.evidence_links
                if link.evidence_id in pins_by_id
            )
            if not numeric_tokens.issubset(set(_NUMERIC_TOKEN.findall(evidence_text))):
                findings.append(
                    _finding(
                        "numeric_claim_not_in_evidence",
                        "A generated number is absent from its exact evidence revisions.",
                        claim.id,
                        blocking=True,
                    )
                )
        if record.job_requirements and not claim.requirement_ids:
            findings.append(
                _finding(
                    "requirement_alignment_review",
                    "This grounded claim has no deterministic link to a pinned job requirement.",
                    claim.id,
                    blocking=False,
                )
            )
    if record.resume_title and record.job_title:
        resume_tokens = _tokens(record.resume_title)
        job_tokens = _tokens(record.job_title)
        if resume_tokens and job_tokens and resume_tokens.isdisjoint(job_tokens):
            findings.append(
                _finding(
                    "role_alignment_review",
                    "The pinned resume title and target job title use different role language.",
                    blocking=False,
                )
            )
    return tuple(findings)


def _finding(
    code: str,
    message: str,
    claim_id: UUID | None = None,
    *,
    blocking: bool,
) -> ApplicationConsistencyFinding:
    return ApplicationConsistencyFinding(
        code=code,
        severity=(
            ApplicationConsistencySeverity.BLOCKING
            if blocking
            else ApplicationConsistencySeverity.WARNING
        ),
        message=message,
        claim_id=claim_id,
    )


def _pack_findings(
    record: ApplicationRecord,
    documents: tuple[ApplicationDocument, ...],
) -> tuple[ApplicationConsistencyFinding, ...]:
    """Compare every generated surface against one immutable fact ledger."""

    findings: list[ApplicationConsistencyFinding] = []
    source_claims = {claim.id: claim for claim in record.resume_claims}
    seen_claims: dict[
        UUID,
        tuple[
            str,
            tuple[str, ...],
            tuple[str, ...],
            tuple[tuple[UUID, UUID], ...],
            tuple[UUID, ...],
        ],
    ] = {}
    seen_kinds: set[ApplicationDocumentKind] = set()
    pack_ids = {document.pack_id for document in documents}
    if len(pack_ids) != 1 or any(
        document.owner_user_id != record.owner_user_id or document.application_id != record.id
        for document in documents
    ):
        findings.append(
            _finding(
                "document_pack_scope_mismatch",
                "Generated documents do not belong to one owner-scoped application pack.",
                blocking=True,
            )
        )
    for document in documents:
        if document.kind in seen_kinds:
            findings.append(
                _finding(
                    "duplicate_document_kind",
                    "An application pack contains duplicate document kinds.",
                    blocking=True,
                )
            )
        seen_kinds.add(document.kind)
        if record.job_title not in document.body:
            findings.append(
                _finding(
                    "target_title_missing",
                    "A generated document does not contain the exact pinned target title.",
                    blocking=True,
                )
            )
        claim_evidence_ids = tuple(
            dict.fromkeys(
                link.evidence_id for claim in document.claims for link in claim.evidence_links
            )
        )
        claim_requirement_ids = tuple(
            dict.fromkeys(
                requirement_id
                for claim in document.claims
                for requirement_id in claim.requirement_ids
            )
        )
        if (
            document.source_evidence_ids != claim_evidence_ids
            or document.source_requirement_ids != claim_requirement_ids
        ):
            findings.append(
                _finding(
                    "source_ledger_coverage_mismatch",
                    "A document source ledger does not exactly cover its generated claims.",
                    blocking=True,
                )
            )
        for claim in document.claims:
            source = source_claims.get(claim.id)
            signature = _claim_consistency_signature(claim)
            previous = seen_claims.get(claim.id)
            if previous is not None:
                _compare_claim_signatures(
                    previous,
                    signature,
                    claim.id,
                    findings,
                    prefix="cross_document",
                )
            seen_claims[claim.id] = signature
            if source is not None:
                _compare_claim_signatures(
                    _claim_consistency_signature(source),
                    signature,
                    claim.id,
                    findings,
                    prefix="source_ledger",
                )
    return tuple(findings)


def _claim_consistency_signature(
    claim: ApplicationDocumentClaim,
) -> tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[UUID, UUID], ...],
    tuple[UUID, ...],
]:
    return (
        claim.text,
        tuple(_NUMERIC_TOKEN.findall(claim.text)),
        tuple(match.group(0) for match in _DATE_TOKEN.finditer(claim.text)),
        tuple((link.evidence_id, link.evidence_revision_id) for link in claim.evidence_links),
        claim.requirement_ids,
    )


def _compare_claim_signatures(
    expected: tuple[
        str,
        tuple[str, ...],
        tuple[str, ...],
        tuple[tuple[UUID, UUID], ...],
        tuple[UUID, ...],
    ],
    actual: tuple[
        str,
        tuple[str, ...],
        tuple[str, ...],
        tuple[tuple[UUID, UUID], ...],
        tuple[UUID, ...],
    ],
    claim_id: UUID,
    findings: list[ApplicationConsistencyFinding],
    *,
    prefix: str,
) -> None:
    comparisons = (
        (
            0,
            f"{prefix}_claim_text_mismatch",
            "A claim has inconsistent text across generated surfaces.",
        ),
        (
            1,
            f"{prefix}_metric_mismatch",
            "A claim has inconsistent metric tokens across generated surfaces.",
        ),
        (
            2,
            f"{prefix}_date_mismatch",
            "A claim has inconsistent date tokens across generated surfaces.",
        ),
        (
            3,
            f"{prefix}_evidence_mismatch",
            "A claim has inconsistent evidence revision links across generated surfaces.",
        ),
        (
            4,
            f"{prefix}_requirement_mismatch",
            "A claim has inconsistent job requirement links across generated surfaces.",
        ),
    )
    for index, code, message in comparisons:
        if expected[index] != actual[index]:
            findings.append(
                _finding(
                    code,
                    message,
                    claim_id,
                    blocking=True,
                )
            )


def _merge_findings(
    documents: tuple[ApplicationDocument, ...],
) -> tuple[ApplicationConsistencyFinding, ...]:
    return _dedupe_findings(
        tuple(finding for document in documents for finding in document.consistency_findings)
    )


def _dedupe_findings(
    findings: tuple[ApplicationConsistencyFinding, ...],
) -> tuple[ApplicationConsistencyFinding, ...]:
    seen: set[tuple[str, str, UUID | None]] = set()
    merged: list[ApplicationConsistencyFinding] = []
    for finding in findings:
        key = (finding.code, finding.message, finding.claim_id)
        if key not in seen:
            seen.add(key)
            merged.append(finding)
    return tuple(merged)


def _status(findings: tuple[ApplicationConsistencyFinding, ...]) -> ConsistencyStatus:
    if any(finding.severity == ApplicationConsistencySeverity.BLOCKING for finding in findings):
        return ConsistencyStatus.FAILED
    if findings:
        return ConsistencyStatus.WARNING
    return ConsistencyStatus.PASSED


def _tokens(value: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "senior",
        "lead",
        "principal",
        "manager",
    }
    return {
        part
        for part in re.findall(r"[a-z0-9]+", value.lower())
        if len(part) > 2 and part not in stop
    }


def _stage_label(stage: ApplicationStage) -> str:
    return stage.value.replace("_", " ")


def _analytics_snapshot(
    record: ApplicationRecord,
    milestones: ApplicationMilestones,
) -> ApplicationAnalyticsSnapshot:
    return ApplicationAnalyticsSnapshot(
        application_id=record.id,
        stage=record.stage,
        outcome_status=record.outcome_status,
        role_title=record.job_title,
        source=record.source,
        industry=record.industry,
        job_id=record.job_id,
        job_version=record.job_version,
        job_analysis_id=record.job_analysis_id,
        resume_version_id=record.resume_version_id,
        resume_version_number=record.resume_version_number,
        application_deadline=record.application_deadline,
        first_applied_at=milestones.first_applied_at,
        first_response_at=milestones.first_response_at,
        first_interview_at=milestones.first_interview_at,
        first_offer_at=milestones.first_offer_at,
        outcome_at=(milestones.outcome_at if record.outcome_status != OutcomeStatus.NONE else None),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
