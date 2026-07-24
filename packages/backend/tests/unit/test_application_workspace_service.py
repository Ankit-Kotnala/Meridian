"""Service-level tests for the grounded Phase 8 application workspace."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from uuid import UUID

import pytest

from application_workspace_memory import (
    ANALYSIS_ID,
    CLAIM_ID,
    EVIDENCE_ID,
    EVIDENCE_REVISION_ID,
    JOB_ID,
    NOW,
    OTHER_ID,
    OWNER_ID,
    REQUIREMENT_ID,
    RESUME_ID,
    RESUME_VERSION_ID,
    FixedClock,
    MemoryApplicationWorkspace,
    StaticEvidenceProvider,
    StaticJobProvider,
    StaticResumeProvider,
    UuidFactory,
)
from careeros.modules.application_workspace.application import (
    ApplicationEventCursor,
    ApplicationFilter,
    ApplicationResumeSnapshot,
    ApplicationSourceClaim,
    ApplicationSourceEvidenceReference,
    ApplicationWorkspacePolicy,
    ApplicationWorkspaceService,
    CreateApplication,
    CreateApplicationEvent,
    CreateApplicationNote,
    CreateApplicationTask,
    GenerateApplicationPack,
    PageCursor,
    RequestContext,
    UpdateApplication,
    UpdateApplicationTask,
)
from careeros.modules.application_workspace.application.service import (
    _pack_findings,
    _status,
)
from careeros.modules.application_workspace.domain import (
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationIdempotencyRecord,
    ApplicationStage,
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceValidationError,
    ConsistencyStatus,
    OutcomeStatus,
)

_NEXT_RESUME_VERSION_ID = UUID("00000000-0000-4000-8000-0000000008f1")
_NEXT_EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-0000000008f2")


def _context(user_id: UUID = OWNER_ID) -> RequestContext:
    return RequestContext(
        actor_user_id=user_id,
        request_id="req-phase8-test",
        trace_id="trace-phase8-test",
    )


class _AdvancingClock:
    def __init__(self) -> None:
        self._value = NOW

    def now(self) -> datetime:
        value = self._value
        self._value += timedelta(seconds=1)
        return value


def _service(
    state: MemoryApplicationWorkspace,
    *,
    policy: ApplicationWorkspacePolicy | None = None,
    clock: FixedClock | _AdvancingClock | None = None,
) -> ApplicationWorkspaceService:
    return ApplicationWorkspaceService(
        unit_of_work=state,
        clock=clock or FixedClock(),
        identifiers=UuidFactory(),
        jobs=StaticJobProvider(),
        resumes=StaticResumeProvider(),
        evidence=StaticEvidenceProvider(),
        policy=policy,
    )


class _RacingMemoryApplicationWorkspace(MemoryApplicationWorkspace):
    def __init__(self) -> None:
        super().__init__()
        self._raise_once = True

    async def add_idempotency(
        self,
        record: ApplicationIdempotencyRecord,
    ) -> None:
        await super().add_idempotency(record)
        if self._raise_once and record.response_kind == "application":
            self._raise_once = False
            raise ApplicationWorkspaceIdempotencyConflict


class _VersionedResumeProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        version_id: UUID,
    ) -> ApplicationResumeSnapshot:
        if version_id == RESUME_VERSION_ID:
            return await StaticResumeProvider().snapshot(owner_user_id, version_id)
        assert owner_user_id == OWNER_ID
        assert version_id == _NEXT_RESUME_VERSION_ID
        statement = "Led cross-functional product delivery."
        reference = ApplicationSourceEvidenceReference(
            evidence_id=EVIDENCE_ID,
            evidence_revision_id=_NEXT_EVIDENCE_REVISION_ID,
            revision_number=4,
            statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
            claim_sha256=hashlib.sha256(statement.encode()).hexdigest(),
            link_basis="evidence_statement",
            source_skill_id=None,
        )
        return ApplicationResumeSnapshot(
            resume_id=RESUME_ID,
            version_id=version_id,
            version_number=8,
            title="Updated product resume",
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


class _VersionedEvidenceProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]:
        assert owner_user_id == OWNER_ID
        statement = "Led cross-functional product delivery."
        return tuple(
            ApplicationEvidencePin(
                evidence_id=reference.evidence_id,
                evidence_revision_id=reference.evidence_revision_id,
                revision_number=reference.revision_number,
                statement=statement,
                statement_sha256=reference.statement_sha256,
                strength="confirmed",
                has_numeric_claim=False,
            )
            for reference in references
        )


async def _create(
    service: ApplicationWorkspaceService,
    *,
    follow_up_at: date | None = date(2026, 8, 10),
):
    return await service.create_application(
        OWNER_ID,
        CreateApplication(
            job_id=JOB_ID,
            resume_version_id=RESUME_VERSION_ID,
            follow_up_at=follow_up_at,
        ),
        idempotency_key="application-create-key",
        context=_context(),
    )


@pytest.mark.asyncio
async def test_create_snapshots_exact_inputs_and_replays_idempotently() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)

    created = await _create(service)
    replay = await _create(service)

    record = created.application
    assert replay.application.id == record.id
    assert len(state.applications) == 1
    assert record.job_version == 4
    assert record.job_source_sha256 == "a" * 64
    assert tuple(pin.evidence_revision_id for pin in record.evidence_pins) == (
        EVIDENCE_REVISION_ID,
    )
    assert record.resume_claims[0].evidence_revision_ids == (EVIDENCE_REVISION_ID,)
    assert record.resume_claims[0].requirement_ids == (REQUIREMENT_ID,)
    assert record.source == "referral"
    assert record.industry == "software"

    listed = await service.list_applications(
        OWNER_ID,
        ApplicationFilter(query=" product ", source=" referral "),
    )
    assert listed.data[0].application.id == record.id
    assert listed.data[0].event_count == 1


@pytest.mark.asyncio
async def test_concurrent_idempotency_conflict_converges_to_committed_result() -> None:
    state = _RacingMemoryApplicationWorkspace()
    service = _service(state)

    created = await _create(service)

    assert created.application.id in state.applications
    assert len(state.applications) == 1
    assert len(state.idempotency) == 1


@pytest.mark.asyncio
async def test_resume_change_audit_pins_old_and_new_evidence_revisions() -> None:
    state = MemoryApplicationWorkspace()
    service = ApplicationWorkspaceService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        jobs=StaticJobProvider(),
        resumes=_VersionedResumeProvider(),
        evidence=_VersionedEvidenceProvider(),
    )
    created = await _create(service)
    updated = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(
            resume_version_id=_NEXT_RESUME_VERSION_ID,
            resume_change_reason="Use the newly reviewed evidence revision.",
        ),
        expected_version=created.application.version,
        context=_context(),
    )

    assert updated.application.resume_version_id == _NEXT_RESUME_VERSION_ID
    audit = state.audits[-1]
    assert audit.action.value == "resume_version_changed"
    assert audit.metadata["previous_resume_version_id"] == str(RESUME_VERSION_ID)
    assert audit.metadata["next_resume_version_id"] == str(_NEXT_RESUME_VERSION_ID)
    assert audit.metadata["previous_evidence_revision_ids"] == [str(EVIDENCE_REVISION_ID)]
    assert audit.metadata["next_evidence_revision_ids"] == [str(_NEXT_EVIDENCE_REVISION_ID)]
    assert audit.metadata["resume_change_reason"] == ("Use the newly reviewed evidence revision.")


def test_offset_cursor_rejects_boolean_and_unbounded_offsets() -> None:
    def encoded(offset: object) -> str:
        payload = json.dumps({"offset": offset}, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        PageCursor.decode(encoded(True))
    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        PageCursor.decode(encoded(10_001))
    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        PageCursor.decode(
            base64.urlsafe_b64encode(b'{"offset":0,"ignored":true}').decode().rstrip("=")
        )


def test_cursors_reject_non_ascii_input_as_validation_errors() -> None:
    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        PageCursor.decode("☃")
    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        ApplicationEventCursor.decode("☃", application_id=JOB_ID)


@pytest.mark.asyncio
async def test_manual_event_without_time_replays_with_an_advancing_clock() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state, clock=_AdvancingClock())
    created = await _create(service)
    command = CreateApplicationEvent(
        event_kind=ApplicationEventKind.CONTACT,
        occurred_at=None,
        title="Contacted recruiter",
    )

    first = await service.record_event(
        OWNER_ID,
        created.application.id,
        command,
        idempotency_key="manual-event-replay",
        context=_context(),
    )
    replay = await service.record_event(
        OWNER_ID,
        created.application.id,
        command,
        idempotency_key="manual-event-replay",
        context=_context(),
    )

    assert replay == first
    assert replay.occurred_at == first.occurred_at


@pytest.mark.asyncio
async def test_manual_event_limit_never_blocks_system_lifecycle_history() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(
        state,
        policy=ApplicationWorkspacePolicy(
            max_manual_events_per_application=1,
        ),
    )
    created = await _create(service)
    await service.record_event(
        OWNER_ID,
        created.application.id,
        CreateApplicationEvent(
            event_kind=ApplicationEventKind.CONTACT,
            occurred_at=None,
            title="Contacted recruiter",
        ),
        idempotency_key="manual-event-one",
        context=_context(),
    )
    with pytest.raises(ApplicationWorkspaceConflict, match="manual event limit"):
        await service.record_event(
            OWNER_ID,
            created.application.id,
            CreateApplicationEvent(
                event_kind=ApplicationEventKind.CUSTOM,
                occurred_at=None,
                title="Second manual event",
            ),
            idempotency_key="manual-event-two",
            context=_context(),
        )
    with pytest.raises(ApplicationWorkspaceValidationError, match="recorded manually"):
        await service.record_event(
            OWNER_ID,
            created.application.id,
            CreateApplicationEvent(
                event_kind=ApplicationEventKind.STAGE_CHANGED,
                occurred_at=None,
                title="Forged lifecycle event",
            ),
            idempotency_key="manual-system-event",
            context=_context(),
        )

    applied = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(stage=ApplicationStage.APPLIED),
        expected_version=created.application.version,
        context=_context(),
    )
    await service.create_task(
        OWNER_ID,
        created.application.id,
        CreateApplicationTask(title="Prepare interview notes"),
        idempotency_key="system-event-task",
        context=_context(),
    )
    await service.create_note(
        OWNER_ID,
        created.application.id,
        CreateApplicationNote(body="A bounded private note."),
        idempotency_key="system-event-note",
        context=_context(),
    )
    await service.generate_pack(
        OWNER_ID,
        created.application.id,
        GenerateApplicationPack(include_kinds=("cover_letter",)),
        idempotency_key="system-event-pack",
        context=_context(),
    )

    detail = await service.get_application(OWNER_ID, created.application.id)
    assert detail.application.version == applied.application.version
    assert detail.event_count >= 6
    assert await state.count_manual_events(OWNER_ID, created.application.id) == 1


@pytest.mark.asyncio
async def test_child_collections_are_separately_paged_and_event_history_is_keyset() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)
    for index in range(2):
        await service.create_task(
            OWNER_ID,
            created.application.id,
            CreateApplicationTask(title=f"Task {index}"),
            idempotency_key=f"paged-task-{index}",
            context=_context(),
        )
        await service.create_note(
            OWNER_ID,
            created.application.id,
            CreateApplicationNote(body=f"Note {index}"),
            idempotency_key=f"paged-note-{index}",
            context=_context(),
        )
        await service.generate_pack(
            OWNER_ID,
            created.application.id,
            GenerateApplicationPack(include_kinds=("cover_letter",)),
            idempotency_key=f"paged-pack-{index}",
            context=_context(),
        )

    detail = await service.get_application(OWNER_ID, created.application.id)
    assert detail.task_count == 2
    assert detail.note_count == 2
    assert detail.pack_count == 2
    assert not hasattr(detail, "tasks")
    assert not hasattr(detail, "packs")

    first_tasks = await service.list_tasks(
        OWNER_ID,
        created.application.id,
        limit=1,
    )
    second_tasks = await service.list_tasks(
        OWNER_ID,
        created.application.id,
        cursor=first_tasks.page.next_cursor,
        limit=1,
    )
    assert first_tasks.page.has_more
    assert first_tasks.data[0].id != second_tasks.data[0].id

    first_events = await service.list_events(
        OWNER_ID,
        created.application.id,
        limit=2,
    )
    second_events = await service.list_events(
        OWNER_ID,
        created.application.id,
        cursor=first_events.page.next_cursor,
        limit=2,
    )
    assert first_events.page.has_more
    assert {item.id for item in first_events.data}.isdisjoint(
        item.id for item in second_events.data
    )
    with pytest.raises(ApplicationWorkspaceValidationError, match="cursor"):
        await service.list_events(
            OWNER_ID,
            UUID("00000000-0000-4000-8000-000000009999"),
            cursor=first_events.page.next_cursor,
        )
    with pytest.raises(ApplicationWorkspaceNotFound):
        await service.list_notes(
            OTHER_ID,
            created.application.id,
        )

    packs = await service.list_packs(
        OWNER_ID,
        created.application.id,
        limit=1,
    )
    assert packs.page.has_more
    assert not hasattr(packs.data[0], "documents")


@pytest.mark.asyncio
async def test_patch_can_explicitly_clear_dates_and_task_due_date() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)

    updated = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(
            application_deadline=None,
            follow_up_at=None,
            source=None,
            industry=None,
        ),
        expected_version=created.application.version,
        context=_context(),
    )
    assert updated.application.application_deadline is None
    assert updated.application.follow_up_at is None
    assert updated.application.source is None
    assert updated.application.industry is None

    task = await service.create_task(
        OWNER_ID,
        created.application.id,
        CreateApplicationTask(
            title="Request a referral",
            due_at=date(2026, 8, 3),
        ),
        idempotency_key="application-task-key",
        context=_context(),
    )
    cleared = await service.update_task(
        OWNER_ID,
        created.application.id,
        task.id,
        UpdateApplicationTask(due_at=None, completed=True),
        expected_version=task.version,
        context=_context(),
    )
    assert cleared.due_at is None
    assert cleared.completed_at is not None


@pytest.mark.asyncio
async def test_terminal_reopen_is_explicit_and_audited() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)
    applied = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(stage=ApplicationStage.APPLIED),
        expected_version=created.application.version,
        context=_context(),
    )
    rejected = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(
            outcome_status=OutcomeStatus.REJECTED,
            rejection_reason="Role was closed.",
        ),
        expected_version=applied.application.version,
        context=_context(),
    )
    assert rejected.application.stage == ApplicationStage.REJECTED
    assert rejected.application.outcome_status == OutcomeStatus.REJECTED

    with pytest.raises(
        ApplicationWorkspaceValidationError,
        match="requires a reason",
    ):
        await service.update_application(
            OWNER_ID,
            created.application.id,
            UpdateApplication(stage=ApplicationStage.APPLIED),
            expected_version=rejected.application.version,
            context=_context(),
        )

    reopened = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(
            stage=ApplicationStage.APPLIED,
            reopen_reason="Recruiter reopened the role.",
        ),
        expected_version=rejected.application.version,
        context=_context(),
    )
    assert reopened.application.stage == ApplicationStage.APPLIED
    assert reopened.application.outcome_status == OutcomeStatus.NONE
    assert reopened.application.rejection_reason is None
    events = await service.list_events(OWNER_ID, created.application.id)
    assert any(event.description == "Recruiter reopened the role." for event in events.data)


@pytest.mark.asyncio
async def test_pack_is_grounded_to_exact_versions_and_never_submits() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)

    generated = await service.generate_pack(
        OWNER_ID,
        created.application.id,
        GenerateApplicationPack(
            include_kinds=("tailored_resume", "cover_letter"),
        ),
        idempotency_key="application-pack-key",
        context=_context(),
    )
    replay = await service.generate_pack(
        OWNER_ID,
        created.application.id,
        GenerateApplicationPack(
            include_kinds=("tailored_resume", "cover_letter"),
        ),
        idempotency_key="application-pack-key",
        context=_context(),
    )

    assert replay.pack.id == generated.pack.id
    assert len(state.packs) == 1
    assert generated.pack.application_version == created.application.version
    assert generated.pack.job_version == created.application.job_version
    assert generated.pack.resume_version_id == RESUME_VERSION_ID
    assert generated.pack.evidence_revision_ids == (EVIDENCE_REVISION_ID,)
    assert generated.pack.requirement_ids == (REQUIREMENT_ID,)
    assert all(
        document.claims[0].evidence_revision_ids == (EVIDENCE_REVISION_ID,)
        and document.source_requirement_ids == (REQUIREMENT_ID,)
        for document in generated.documents
    )
    assert not any("submit" in name for name in dir(service) if not name.startswith("_"))


@pytest.mark.asyncio
async def test_pack_consistency_blocks_cross_document_fact_drift() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)
    generated = await service.generate_pack(
        OWNER_ID,
        created.application.id,
        GenerateApplicationPack(
            include_kinds=("tailored_resume", "cover_letter"),
        ),
        idempotency_key="fact-drift-pack",
        context=_context(),
    )
    cover = generated.documents[1]
    drifted_claim = replace(
        cover.claims[0],
        text=f"{cover.claims[0].text} Increased impact 10% in 2025.",
    )
    drifted_body = cover.body.replace(
        created.application.job_title,
        "A different target title",
    )
    drifted_cover = replace(
        cover,
        body=drifted_body,
        content_sha256=hashlib.sha256(drifted_body.encode("utf-8")).hexdigest(),
        source_evidence_ids=(),
        claims=(drifted_claim,),
    )

    findings = _pack_findings(
        created.application,
        (generated.documents[0], drifted_cover),
    )
    codes = {finding.code for finding in findings}
    assert {
        "cross_document_claim_text_mismatch",
        "cross_document_metric_mismatch",
        "cross_document_date_mismatch",
        "target_title_missing",
        "source_ledger_coverage_mismatch",
    }.issubset(codes)
    assert _status(findings) == ConsistencyStatus.FAILED


@pytest.mark.asyncio
async def test_child_access_requires_owner_and_active_parent() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)
    task = await service.create_task(
        OWNER_ID,
        created.application.id,
        CreateApplicationTask(title="Review pack"),
        idempotency_key="active-parent-task",
        context=_context(),
    )
    await service.generate_pack(
        OWNER_ID,
        created.application.id,
        GenerateApplicationPack(include_kinds=("cover_letter",)),
        idempotency_key="delete-parent-pack",
        context=_context(),
    )

    with pytest.raises(ApplicationWorkspaceNotFound):
        await service.get_application(OTHER_ID, created.application.id)
    with pytest.raises(ApplicationWorkspaceNotFound):
        await service.update_task(
            OWNER_ID,
            UUID("00000000-0000-4000-8000-000000009999"),
            task.id,
            UpdateApplicationTask(completed=True),
            expected_version=task.version,
            context=_context(),
        )
    await service.delete_application(
        OWNER_ID,
        created.application.id,
        expected_version=created.application.version,
        context=_context(),
    )
    with pytest.raises(ApplicationWorkspaceNotFound):
        await service.update_task(
            OWNER_ID,
            created.application.id,
            task.id,
            UpdateApplicationTask(completed=True),
            expected_version=task.version,
            context=_context(),
        )
    assert not state.applications
    assert not state.tasks
    assert not state.events
    assert not state.packs
    assert not state.documents
    assert state.audits[-1].action.value == "application_deleted"
    assert state.audits[-1].metadata == {}


@pytest.mark.asyncio
async def test_downstream_dtos_are_purpose_minimized() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    created = await _create(service)
    applied = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(stage=ApplicationStage.APPLIED),
        expected_version=created.application.version,
        context=_context(),
    )
    interview_stage = await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(stage=ApplicationStage.INTERVIEW),
        expected_version=applied.application.version,
        context=_context(),
    )
    await service.update_application(
        OWNER_ID,
        created.application.id,
        UpdateApplication(stage=ApplicationStage.OFFER),
        expected_version=interview_stage.application.version,
        context=_context(),
    )

    interview = await service.get_interview_context(
        OWNER_ID,
        created.application.id,
    )
    analytics = await service.list_analytics_snapshots(OWNER_ID)

    assert interview.claims[0].evidence_revision_ids == (EVIDENCE_REVISION_ID,)
    assert interview.evidence_pins[0].evidence_revision_id == EVIDENCE_REVISION_ID
    assert interview.evidence_pins[0].statement
    assert len(interview.evidence_pins[0].statement_sha256) == 64
    assert not hasattr(interview, "notes")
    assert not hasattr(interview, "contacts")
    assert len(analytics) == 1
    assert analytics[0].job_version == 4
    assert analytics[0].job_analysis_id == ANALYSIS_ID
    assert analytics[0].first_applied_at is not None
    assert analytics[0].first_response_at is not None
    assert analytics[0].first_interview_at is not None
    assert analytics[0].first_offer_at is not None
    assert analytics[0].outcome_at is not None
    assert not hasattr(analytics[0], "company")
    assert not hasattr(analytics[0], "offer_summary")
