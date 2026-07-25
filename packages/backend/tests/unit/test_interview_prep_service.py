"""Grounding, ownership, concurrency, and privacy tests for Interview Prep."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from careeros.modules.application_workspace.application import (
    ApplicationInterviewContext,
    ApplicationInterviewEvidenceReference,
)
from careeros.modules.application_workspace.domain import (
    ApplicationClaimEvidenceLink,
    ApplicationDocumentClaim,
    ApplicationEvidencePin,
    ApplicationRequirementSnapshot,
    ApplicationStage,
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceUnavailable,
    ApplicationWorkspaceValidationError,
    ApplicationWorkspaceVersionConflict,
)
from careeros.modules.interview_prep.application import (
    CreateInterviewQuestion,
    CreateInterviewSession,
    CreateSessionNote,
    CreateStarStory,
    GenerateFollowUpDraft,
    GroundingStatus,
    InterviewPrepPolicy,
    InterviewPrepService,
    RequestContext,
    StoryClaimSelection,
    UpdateSessionNote,
    UpdateStarStory,
)
from careeros.modules.interview_prep.application.models import PageCursor
from careeros.modules.interview_prep.domain import (
    DefenseStatus,
    InterviewPrepConflict,
    InterviewPrepIdempotencyConflict,
    InterviewPrepNotFound,
    InterviewPrepQuotaExceeded,
    InterviewPrepUnavailable,
    InterviewPrepValidationError,
    InterviewPrepVersionConflict,
    InterviewSessionKind,
    QuestionKind,
    SessionNoteKind,
    StoryField,
    StoryOrigin,
    StoryStatus,
)
from careeros.modules.interview_prep.infrastructure.sources import (
    ApplicationWorkspaceInterviewContextProvider,
)
from interview_prep_memory import (
    APPLICATION_ID,
    CLAIM_ID,
    EVIDENCE_REVISION_ID,
    OTHER_ID,
    OWNER_ID,
    REQUIREMENT_ID,
    FixedClock,
    MemoryInterviewPrep,
    StaticApplicationContext,
    UuidFactory,
    source_snapshot,
)

ALL_FIELDS = (
    StoryField.SITUATION,
    StoryField.TASK,
    StoryField.ACTION,
    StoryField.RESULT,
    StoryField.PERSONAL_CONTRIBUTION,
    StoryField.METRIC_EXPLANATION,
)
CANONICAL_INELIGIBLE_STATES = (
    "revoked",
    "revised",
    "downgraded",
    "unavailable",
    "conflicted",
    "unsafe",
    "numeric",
)


def _service(
    state: MemoryInterviewPrep | None = None,
    source: StaticApplicationContext | None = None,
    policy: InterviewPrepPolicy | None = None,
) -> tuple[InterviewPrepService, MemoryInterviewPrep, StaticApplicationContext]:
    memory = state or MemoryInterviewPrep()
    applications = source or StaticApplicationContext()
    return (
        InterviewPrepService(
            unit_of_work=memory,
            clock=FixedClock(),
            identifiers=UuidFactory(),
            application_context=applications,
            policy=policy,
        ),
        memory,
        applications,
    )


def _context(actor_user_id: object = OWNER_ID) -> RequestContext:
    assert isinstance(actor_user_id, type(OWNER_ID))
    return RequestContext(
        actor_user_id=actor_user_id,
        request_id="request-interview-1",
        trace_id="trace-interview-1",
    )


def _story_command(
    *,
    title: str = "Launch leadership",
    status: StoryStatus = StoryStatus.READY,
    origin: StoryOrigin = StoryOrigin.USER_AUTHORED,
    result: str = "Improved adoption by 25%.",
    metric_explanation: str | None = (
        "The confirmed evidence records a 12-person launch and 25% adoption improvement."
    ),
    selections: tuple[StoryClaimSelection, ...] | None = None,
) -> CreateStarStory:
    return CreateStarStory(
        application_id=APPLICATION_ID,
        title=title,
        situation="A cross-functional product launch needed coordination.",
        task="Lead the launch work across the participating functions.",
        action="I led the 12-person launch team.",
        result=result,
        personal_contribution="I owned the cross-functional coordination.",
        metric_explanation=metric_explanation,
        confidence=4,
        follow_up_questions=("How did you coordinate decisions?",),
        status=status,
        origin=origin,
        claim_selections=(
            (
                StoryClaimSelection(
                    claim_id=CLAIM_ID,
                    field_names=ALL_FIELDS,
                ),
            )
            if selections is None
            else selections
        ),
    )


def _story_update(status: StoryStatus) -> UpdateStarStory:
    command = _story_command(status=status)
    return UpdateStarStory(
        title=command.title,
        situation=command.situation,
        task=command.task,
        action=command.action,
        result=command.result,
        personal_contribution=command.personal_contribution,
        metric_explanation=command.metric_explanation,
        confidence=command.confidence,
        follow_up_questions=command.follow_up_questions,
        status=status,
        claim_selections=command.claim_selections,
    )


def _make_story_evidence_not_current(
    source: StaticApplicationContext,
    current_state: str,
) -> None:
    current = source.current_evidence_pins[0]
    if current_state == "revised":
        source.current_evidence_pins = (
            replace(
                current,
                evidence_revision_id=OTHER_ID,
                revision_number=current.revision_number + 1,
            ),
        )
    elif current_state == "numeric":
        source.current_evidence_pins = (
            replace(current, has_numeric_claim=not current.has_numeric_claim),
        )
    else:
        source.validation_error = InterviewPrepConflict(f"current evidence is {current_state}")


@pytest.mark.asyncio
async def test_ready_story_pins_exact_revisions_and_defense_map_is_deterministic() -> None:
    service, state, source = _service()

    initial = await service.defense_map(OWNER_ID, APPLICATION_ID)
    assert initial.entries[0].status is DefenseStatus.UNDEFENDED
    assert initial.entries[0].warning == ("Strong claim is not backed by a ready STAR story.")

    draft = await service.create_story(
        OWNER_ID,
        _story_command(status=StoryStatus.DRAFT),
        idempotency_key="story-draft-001",
        context=_context(),
    )
    assert not source.validation_calls
    partial = await service.defense_map(OWNER_ID, APPLICATION_ID)
    assert partial.entries[0].status is DefenseStatus.PARTIAL
    assert partial.entries[0].story_ids == (draft.id,)
    assert partial.entries[0].evidence_revision_ids == (EVIDENCE_REVISION_ID,)
    assert partial.strong_claim_warning_count == 1

    ready = await service.update_story(
        OWNER_ID,
        draft.id,
        _story_update(StoryStatus.READY),
        expected_version=draft.version,
        context=_context(),
    )
    assert len(source.validation_calls) == 1
    final = await service.defense_map(OWNER_ID, APPLICATION_ID)

    assert ready.version == 2
    assert ready.claim_pins[0].source_claim_id == CLAIM_ID
    assert ready.claim_pins[0].evidence_pins[0].evidence_revision_id == (EVIDENCE_REVISION_ID)
    assert len(ready.claim_pins[0].claim_sha256) == 64
    assert final.entries[0].status is DefenseStatus.DEFENDED
    assert final.entries[0].warning is None
    assert final.defended_count == 1
    assert len(source.validation_calls) == 2
    assert state.audits[-1].metadata == (
        ("application_id", str(APPLICATION_ID)),
        ("story_id", str(draft.id)),
        ("status", "ready"),
        ("version", "2"),
        ("claim_count", "1"),
    )


@pytest.mark.asyncio
async def test_defense_map_never_treats_a_stale_revision_as_current_support() -> None:
    service, _state, source = _service()
    await service.create_story(
        OWNER_ID,
        _story_command(),
        idempotency_key="story-exact-pin-001",
        context=_context(),
    )
    current = await service.defense_map(OWNER_ID, APPLICATION_ID)
    assert current.entries[0].status is DefenseStatus.DEFENDED

    next_snapshot = source_snapshot()
    next_pin = replace(
        next_snapshot.claims[0].evidence_pins[0],
        evidence_revision_id=OTHER_ID,
    )
    source.value = replace(
        next_snapshot,
        claims=(replace(next_snapshot.claims[0], evidence_pins=(next_pin,)),),
    )

    refreshed = await service.defense_map(OWNER_ID, APPLICATION_ID)
    assert refreshed.entries[0].status is DefenseStatus.UNDEFENDED
    assert refreshed.entries[0].evidence_revision_ids == (OTHER_ID,)
    assert refreshed.strong_claim_warning_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("current_state", CANONICAL_INELIGIBLE_STATES)
async def test_new_ready_story_requires_live_current_evidence(
    current_state: str,
) -> None:
    service, state, source = _service()
    _make_story_evidence_not_current(source, current_state)

    with pytest.raises(InterviewPrepConflict):
        await service.create_story(
            OWNER_ID,
            _story_command(),
            idempotency_key=f"story-current-create-{current_state}",
            context=_context(),
        )

    assert len(source.validation_calls) == 1
    assert not state.stories
    assert not state.idempotency
    assert not state.audits
    assert state.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("current_state", CANONICAL_INELIGIBLE_STATES)
async def test_promoting_draft_to_ready_requires_live_current_evidence(
    current_state: str,
) -> None:
    service, state, source = _service()
    draft = await service.create_story(
        OWNER_ID,
        _story_command(status=StoryStatus.DRAFT),
        idempotency_key=f"story-current-draft-{current_state}",
        context=_context(),
    )
    assert not source.validation_calls
    _make_story_evidence_not_current(source, current_state)

    with pytest.raises(InterviewPrepConflict):
        await service.update_story(
            OWNER_ID,
            draft.id,
            _story_update(StoryStatus.READY),
            expected_version=draft.version,
            context=_context(),
        )

    persisted = await service.get_story(OWNER_ID, draft.id)
    assert persisted.status is StoryStatus.DRAFT
    assert persisted.version == 1
    assert len(source.validation_calls) == 1
    assert len(state.audits) == 1
    assert state.commits == 1


@pytest.mark.asyncio
async def test_draft_story_preserves_historical_pins_without_live_validation() -> None:
    service, state, source = _service()
    source.validation_error = InterviewPrepConflict("current evidence is revoked")

    draft = await service.create_story(
        OWNER_ID,
        _story_command(status=StoryStatus.DRAFT),
        idempotency_key="story-historical-draft-001",
        context=_context(),
    )

    assert draft.status is StoryStatus.DRAFT
    assert draft.id in state.stories
    assert not source.validation_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("current_state", CANONICAL_INELIGIBLE_STATES)
async def test_defense_map_marks_non_current_ready_stories_for_review(
    current_state: str,
) -> None:
    service, state, source = _service()
    story = await service.create_story(
        OWNER_ID,
        _story_command(),
        idempotency_key=f"story-defense-current-{current_state}",
        context=_context(),
    )
    _make_story_evidence_not_current(source, current_state)

    defense = await service.defense_map(OWNER_ID, APPLICATION_ID)

    assert defense.entries[0].status is DefenseStatus.PARTIAL
    assert defense.entries[0].story_ids == (story.id,)
    assert defense.entries[0].warning == (
        "Ready STAR story evidence is no longer current; review and re-ground it."
    )
    assert defense.defended_count == 0
    assert defense.partial_count == 1
    assert defense.strong_claim_warning_count == 1
    persisted = await service.get_story(OWNER_ID, story.id)
    assert persisted.status is StoryStatus.READY
    assert persisted.version == story.version
    assert len(state.audits) == 1


@pytest.mark.asyncio
async def test_defense_map_isolates_a_stale_story_from_other_current_stories() -> None:
    snapshot = source_snapshot()
    second_claim_id = UUID("00000000-0000-4000-8000-000000000920")
    second_evidence_id = UUID("00000000-0000-4000-8000-000000000921")
    second_revision_id = UUID("00000000-0000-4000-8000-000000000922")
    first_claim = snapshot.claims[0]
    second_pin = replace(
        first_claim.evidence_pins[0],
        evidence_id=second_evidence_id,
        evidence_revision_id=second_revision_id,
    )
    second_claim = replace(
        first_claim,
        id=second_claim_id,
        evidence_pins=(second_pin,),
    )
    source = StaticApplicationContext(replace(snapshot, claims=(first_claim, second_claim)))
    service, _state, source = _service(source=source)
    stale_story = await service.create_story(
        OWNER_ID,
        _story_command(title="Story that later becomes stale"),
        idempotency_key="story-defense-isolation-stale",
        context=_context(),
    )
    current_story = await service.create_story(
        OWNER_ID,
        _story_command(
            title="Story that remains current",
            selections=(
                StoryClaimSelection(
                    claim_id=second_claim_id,
                    field_names=ALL_FIELDS,
                ),
            ),
        ),
        idempotency_key="story-defense-isolation-current",
        context=_context(),
    )
    source.current_evidence_pins = (
        replace(
            first_claim.evidence_pins[0],
            evidence_revision_id=OTHER_ID,
            revision_number=first_claim.evidence_pins[0].revision_number + 1,
        ),
        second_pin,
    )

    defense = await service.defense_map(OWNER_ID, APPLICATION_ID)

    by_claim = {entry.claim_id: entry for entry in defense.entries}
    assert by_claim[CLAIM_ID].status is DefenseStatus.PARTIAL
    assert by_claim[CLAIM_ID].story_ids == (stale_story.id,)
    assert by_claim[second_claim_id].status is DefenseStatus.DEFENDED
    assert by_claim[second_claim_id].story_ids == (current_story.id,)
    assert defense.defended_count == 1
    assert defense.partial_count == 1
    assert len(source.validation_calls) == 4


@pytest.mark.asyncio
async def test_ready_story_replay_remains_immutable_after_evidence_withdrawal() -> None:
    service, state, source = _service()
    command = _story_command()
    created = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key="story-current-replay-001",
        context=_context(),
    )
    source.validation_error = InterviewPrepConflict("current evidence is revoked")

    replay = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key="story-current-replay-001",
        context=_context(),
    )

    assert replay == created
    assert len(source.validation_calls) == 1
    assert len(state.stories) == 1
    assert len(state.audits) == 1


@pytest.mark.asyncio
async def test_story_create_replay_returns_exact_snapshot_after_edit() -> None:
    service, state, _source = _service()
    command = _story_command()
    key = "story-create-exact-replay"
    created = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key=key,
        context=_context(),
    )
    updated = await service.update_story(
        OWNER_ID,
        created.id,
        replace(
            _story_update(StoryStatus.READY),
            title="Edited launch leadership",
        ),
        expected_version=created.version,
        context=_context(),
    )

    replay = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key=key,
        context=_context(),
    )

    assert replay == created
    assert replay.version == 1
    assert replay.title == "Launch leadership"
    assert updated.version == 2
    assert (await service.get_story(OWNER_ID, created.id)).title == ("Edited launch leadership")
    record = state.idempotency[(OWNER_ID, key)]
    assert record.response_snapshot is not None
    assert record.response_snapshot.restore() == created
    with pytest.raises(
        InterviewPrepValidationError,
        match="does not match its owned resource",
    ):
        replace(
            record,
            response_snapshot=replace(
                record.response_snapshot,
                owner_user_id=OTHER_ID,
            ),
        )


@pytest.mark.asyncio
async def test_story_deletion_redacts_replay_but_preserves_conflict_barrier() -> None:
    service, state, _source = _service()
    command = _story_command()
    key = "story-create-delete-replay"
    created = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key=key,
        context=_context(),
    )

    await service.delete_story(
        OWNER_ID,
        created.id,
        expected_version=created.version,
        context=_context(),
    )

    record = state.idempotency[(OWNER_ID, key)]
    assert record.response_snapshot is None
    with pytest.raises(InterviewPrepConflict, match="redacted after deletion"):
        await service.create_story(
            OWNER_ID,
            command,
            idempotency_key=key,
            context=_context(),
        )
    with pytest.raises(InterviewPrepIdempotencyConflict):
        await service.create_story(
            OWNER_ID,
            _story_command(title="Conflicting replacement story"),
            idempotency_key=key,
            context=_context(),
        )
    assert not state.stories


@pytest.mark.asyncio
async def test_provider_outage_never_returns_or_persists_a_ready_defense() -> None:
    service, state, source = _service()
    source.validation_error = InterviewPrepUnavailable("source unavailable")
    with pytest.raises(InterviewPrepUnavailable):
        await service.create_story(
            OWNER_ID,
            _story_command(),
            idempotency_key="story-provider-outage-001",
            context=_context(),
        )
    assert not state.stories

    source.validation_error = None
    story = await service.create_story(
        OWNER_ID,
        _story_command(),
        idempotency_key="story-provider-outage-002",
        context=_context(),
    )
    source.validation_error = InterviewPrepUnavailable("source unavailable")
    with pytest.raises(InterviewPrepUnavailable):
        await service.defense_map(OWNER_ID, APPLICATION_ID)
    assert state.stories[story.id].status is StoryStatus.READY


@pytest.mark.asyncio
async def test_ready_and_generated_stories_fail_closed_on_missing_grounding() -> None:
    service, _state, _source = _service()

    with pytest.raises(InterviewPrepConflict, match="provenance for every STAR field"):
        await service.create_story(
            OWNER_ID,
            _story_command(selections=()),
            idempotency_key="story-ungrounded-001",
            context=_context(),
        )

    with pytest.raises(InterviewPrepConflict, match="absent from its pinned evidence"):
        await service.create_story(
            OWNER_ID,
            _story_command(result="Improved adoption by 40%."),
            idempotency_key="story-number-001",
            context=_context(),
        )

    with pytest.raises(InterviewPrepConflict, match="metric explanation"):
        await service.create_story(
            OWNER_ID,
            _story_command(metric_explanation=None),
            idempotency_key="story-metric-001",
            context=_context(),
        )

    with pytest.raises(InterviewPrepValidationError, match="generated stories must be ready"):
        await service.create_story(
            OWNER_ID,
            _story_command(
                status=StoryStatus.DRAFT,
                origin=StoryOrigin.GENERATED,
            ),
            idempotency_key="story-generated-001",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_owner_scope_idempotency_version_and_cursor_limits() -> None:
    service, state, source = _service()
    command = _story_command()

    created = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key="story-replay-001",
        context=_context(),
    )
    replay = await service.create_story(
        OWNER_ID,
        command,
        idempotency_key="story-replay-001",
        context=_context(),
    )
    assert replay.id == created.id
    assert len(state.stories) == 1
    assert source.calls == 1
    assert len(source.validation_calls) == 1

    with pytest.raises(InterviewPrepIdempotencyConflict):
        await service.create_story(
            OWNER_ID,
            replace(command, title="A changed intent"),
            idempotency_key="story-replay-001",
            context=_context(),
        )
    with pytest.raises(InterviewPrepNotFound):
        await service.get_story(OTHER_ID, created.id)
    with pytest.raises(InterviewPrepNotFound):
        await service.create_story(
            OWNER_ID,
            command,
            idempotency_key="story-owner-001",
            context=_context(OTHER_ID),
        )
    with pytest.raises(InterviewPrepNotFound):
        await service.create_story(
            OTHER_ID,
            command,
            idempotency_key="story-owner-002",
            context=_context(OTHER_ID),
        )
    with pytest.raises(InterviewPrepNotFound):
        await service.update_story(
            OTHER_ID,
            created.id,
            _story_update(StoryStatus.READY),
            expected_version=created.version,
            context=_context(OTHER_ID),
        )
    with pytest.raises(InterviewPrepNotFound):
        await service.defense_map(OTHER_ID, APPLICATION_ID)
    with pytest.raises(InterviewPrepVersionConflict):
        await service.update_story(
            OWNER_ID,
            created.id,
            _story_update(StoryStatus.READY),
            expected_version=99,
            context=_context(),
        )
    assert len(source.validation_calls) == 1
    with pytest.raises(InterviewPrepValidationError, match="cursor"):
        PageCursor.decode("\u2603")
    with pytest.raises(InterviewPrepValidationError, match="page limit"):
        await service.list_stories(OWNER_ID, limit=101)


@pytest.mark.asyncio
async def test_session_snapshot_is_immutable_minimized_and_questions_are_grounded() -> None:
    service, state, source = _service()
    created = await service.create_session(
        OWNER_ID,
        CreateInterviewSession(
            application_id=APPLICATION_ID,
            title="Hiring manager preparation",
            kind=InterviewSessionKind.HIRING_MANAGER,
        ),
        idempotency_key="session-create-001",
        context=_context(),
    )
    session = created.session

    assert session.context.claims[0].evidence_pins[0].evidence_revision_id == (EVIDENCE_REVISION_ID)
    assert session.context.requirements[0].requirement_id == REQUIREMENT_ID
    assert not hasattr(session.context, "notes")
    assert not hasattr(session.context, "contacts")
    assert not hasattr(session.context, "offer_summary")
    original_hash = session.context.snapshot_sha256

    source.value = source_snapshot(
        statement="A later evidence revision with no historical rewrite.",
        strong=False,
    )
    reread = await service.get_session(OWNER_ID, session.id)
    assert reread.session.context.snapshot_sha256 == original_hash
    assert reread.session.context.claims[0].text.startswith("Led a 12-person")

    generated = await service.generate_question_bank(
        OWNER_ID,
        session.id,
        idempotency_key="unit-test-00000001",
        context=_context(),
    )
    assert len(source.validation_calls) == 1
    assert source.validation_calls[0][2][0].evidence_revision_id == EVIDENCE_REVISION_ID
    source.validation_error = InterviewPrepConflict("evidence was revoked after generation")
    replay = await service.generate_question_bank(
        OWNER_ID,
        session.id,
        idempotency_key="unit-test-00000001",
        context=_context(),
    )
    assert replay == generated
    assert len(source.validation_calls) == 1
    source.validation_error = None
    assert len(state.questions) == 1
    assert generated[0].source_requirement_ids == (REQUIREMENT_ID,)
    assert generated[0].source_claim_ids == (CLAIM_ID,)

    with pytest.raises(InterviewPrepConflict, match="already exists"):
        await service.generate_question_bank(
            OWNER_ID,
            session.id,
            idempotency_key="unit-test-00000002",
            context=_context(),
        )

    with pytest.raises(InterviewPrepConflict, match="unknown claim"):
        await service.create_question(
            OWNER_ID,
            session.id,
            CreateInterviewQuestion(
                prompt="Unsupported source?",
                kind=QuestionKind.CUSTOM,
                source_claim_ids=(OTHER_ID,),
            ),
            idempotency_key="question-custom-001",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_session_children_lock_owner_then_parent_before_idempotency() -> None:
    service, state, _source = _service()
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Concurrency preparation",
                kind=InterviewSessionKind.TECHNICAL,
            ),
            idempotency_key="session-lock-order-001",
            context=_context(),
        )
    ).session

    state.lock_events.clear()
    question = await service.create_question(
        OWNER_ID,
        session.id,
        CreateInterviewQuestion(prompt="How did you make the decision?"),
        idempotency_key="question-lock-order-001",
        context=_context(),
    )

    assert state.lock_events[:3] == [
        ("owner", OWNER_ID, None),
        ("session", OWNER_ID, session.id),
        ("idempotency", OWNER_ID, "question-lock-order-001"),
    ]
    with pytest.raises(InterviewPrepNotFound):
        await service.create_question(
            OTHER_ID,
            session.id,
            CreateInterviewQuestion(prompt="Attempt to cross the ownership boundary."),
            idempotency_key="question-cross-owner-001",
            context=_context(OTHER_ID),
        )
    assert len(state.questions) == 1
    assert state.questions[question.id].owner_user_id == OWNER_ID


@pytest.mark.asyncio
async def test_all_interview_collections_enforce_bounded_policy_quotas() -> None:
    policy = InterviewPrepPolicy(
        max_stories_per_owner=1,
        max_sessions_per_owner=1,
        max_questions_per_generation=1,
        max_questions_per_session=1,
        max_notes_per_session=1,
        max_follow_up_drafts_per_session=1,
    )
    service, state, _source = _service(policy=policy)
    session_command = CreateInterviewSession(
        application_id=APPLICATION_ID,
        title="Quota preparation",
        kind=InterviewSessionKind.BEHAVIORAL,
    )
    session = (
        await service.create_session(
            OWNER_ID,
            session_command,
            idempotency_key="session-quota-first-001",
            context=_context(),
        )
    ).session
    with pytest.raises(InterviewPrepQuotaExceeded, match="session limit"):
        await service.create_session(
            OWNER_ID,
            session_command,
            idempotency_key="session-quota-second-001",
            context=_context(),
        )

    await service.create_story(
        OWNER_ID,
        _story_command(),
        idempotency_key="story-quota-first-001",
        context=_context(),
    )
    with pytest.raises(InterviewPrepQuotaExceeded, match="story limit"):
        await service.create_story(
            OWNER_ID,
            _story_command(title="Second bounded story"),
            idempotency_key="story-quota-second-001",
            context=_context(),
        )

    await service.create_question(
        OWNER_ID,
        session.id,
        CreateInterviewQuestion(prompt="First bounded question?"),
        idempotency_key="question-quota-first-001",
        context=_context(),
    )
    with pytest.raises(InterviewPrepQuotaExceeded, match="question limit"):
        await service.create_question(
            OWNER_ID,
            session.id,
            CreateInterviewQuestion(prompt="Second bounded question?"),
            idempotency_key="unit-test-00000003",
            context=_context(),
        )

    note_command = CreateSessionNote(
        kind=SessionNoteKind.PRIVATE_NOTE,
        body="First bounded private note.",
    )
    await service.create_note(
        OWNER_ID,
        session.id,
        note_command,
        idempotency_key="note-quota-first-001",
        context=_context(),
    )
    with pytest.raises(InterviewPrepQuotaExceeded, match="note limit"):
        await service.create_note(
            OWNER_ID,
            session.id,
            note_command,
            idempotency_key="note-quota-second-001",
            context=_context(),
        )

    draft_command = GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,))
    await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        draft_command,
        idempotency_key="draft-quota-first-001",
        context=_context(),
    )
    with pytest.raises(InterviewPrepQuotaExceeded, match="draft limit"):
        await service.generate_follow_up_draft(
            OWNER_ID,
            session.id,
            draft_command,
            idempotency_key="draft-quota-second-001",
            context=_context(),
        )

    assert (len(state.stories), len(state.sessions)) == (1, 1)
    assert (len(state.questions), len(state.notes), len(state.drafts)) == (1, 1, 1)


@pytest.mark.asyncio
async def test_private_notes_grounded_follow_up_and_no_send_surface() -> None:
    service, state, source = _service()
    session_view = await service.create_session(
        OWNER_ID,
        CreateInterviewSession(
            application_id=APPLICATION_ID,
            title="Behavioral interview",
            kind=InterviewSessionKind.BEHAVIORAL,
        ),
        idempotency_key="session-private-001",
        context=_context(),
    )
    session = session_view.session
    note = await service.create_note(
        OWNER_ID,
        session.id,
        CreateSessionNote(
            kind=SessionNoteKind.PRIVATE_NOTE,
            body="A sensitive observation for my own preparation.",
        ),
        idempotency_key="private-note-001",
        context=_context(),
    )
    with pytest.raises(InterviewPrepVersionConflict):
        await service.update_note(
            OWNER_ID,
            session.id,
            note.id,
            UpdateSessionNote(
                kind=SessionNoteKind.REFLECTION,
                body="Reflect privately.",
            ),
            expected_version=2,
            context=_context(),
        )

    draft = await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
        idempotency_key="follow-up-draft-001",
        context=_context(),
    )
    assert len(source.validation_calls) == 1
    source.validation_error = InterviewPrepConflict("evidence was revoked after generation")
    replay = await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
        idempotency_key="follow-up-draft-001",
        context=_context(),
    )

    assert replay.id == draft.id
    assert len(source.validation_calls) == 1
    assert draft.source_claims[0].source_claim_id == CLAIM_ID
    assert draft.source_claims[0].evidence_pins[0].evidence_revision_id == (EVIDENCE_REVISION_ID)
    assert "25%" in draft.body
    assert len(state.drafts) == 1
    assert not any("send" in name for name in dir(service) if not name.startswith("_"))
    audit_payload = repr([event.metadata for event in state.audits])
    assert "sensitive observation" not in audit_payload.casefold()
    assert "25%" not in audit_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["question_bank", "follow_up"])
@pytest.mark.parametrize(
    "current_state",
    ["revoked", "revised", "downgraded", "unavailable"],
)
async def test_new_generation_fails_closed_when_session_evidence_is_no_longer_current(
    operation: str,
    current_state: str,
) -> None:
    service, state, source = _service()
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Current evidence enforcement",
                kind=InterviewSessionKind.HIRING_MANAGER,
            ),
            idempotency_key=f"session-current-{operation}-{current_state}",
            context=_context(),
        )
    ).session
    if current_state == "revised":
        source.current_evidence_pins = (
            replace(
                source.current_evidence_pins[0],
                evidence_revision_id=OTHER_ID,
                revision_number=5,
            ),
        )
    else:
        source.validation_error = InterviewPrepConflict(f"current evidence is {current_state}")

    with pytest.raises(InterviewPrepConflict):
        if operation == "question_bank":
            await service.generate_question_bank(
                OWNER_ID,
                session.id,
                idempotency_key=f"bank-current-{current_state}",
                context=_context(),
            )
        else:
            await service.generate_follow_up_draft(
                OWNER_ID,
                session.id,
                GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
                idempotency_key=f"draft-current-{current_state}",
                context=_context(),
            )

    assert len(source.validation_calls) == 1
    assert not state.questions
    assert not state.drafts


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["question_bank", "follow_up"])
async def test_new_generation_hides_cross_owner_sessions_before_evidence_lookup(
    operation: str,
) -> None:
    service, _state, source = _service()
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Owner scoped generation",
                kind=InterviewSessionKind.BEHAVIORAL,
            ),
            idempotency_key=f"session-owner-{operation}",
            context=_context(),
        )
    ).session

    with pytest.raises(InterviewPrepNotFound):
        if operation == "question_bank":
            await service.generate_question_bank(
                OTHER_ID,
                session.id,
                idempotency_key="bank-cross-owner-001",
                context=_context(OTHER_ID),
            )
        else:
            await service.generate_follow_up_draft(
                OTHER_ID,
                session.id,
                GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
                idempotency_key="draft-cross-owner-001",
                context=_context(OTHER_ID),
            )
    assert not source.validation_calls


@pytest.mark.asyncio
async def test_session_delete_cascades_sensitive_children_and_leaves_redacted_audit() -> None:
    service, state, _source = _service()
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Panel preparation",
                kind=InterviewSessionKind.PANEL,
            ),
            idempotency_key="session-delete-001",
            context=_context(),
        )
    ).session
    await service.create_question(
        OWNER_ID,
        session.id,
        CreateInterviewQuestion(prompt="What did you personally lead?"),
        idempotency_key="question-delete-001",
        context=_context(),
    )
    await service.create_note(
        OWNER_ID,
        session.id,
        CreateSessionNote(
            kind=SessionNoteKind.REFLECTION,
            body="Private reflection that must be removed with the session.",
        ),
        idempotency_key="note-delete-001",
        context=_context(),
    )
    await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
        idempotency_key="draft-delete-001",
        context=_context(),
    )

    await service.delete_session(
        OWNER_ID,
        session.id,
        expected_version=session.version,
        context=_context(),
    )

    assert not state.sessions
    assert not state.questions
    assert not state.notes
    assert not state.drafts
    audit = state.audits[-1]
    assert audit.action.value == "session_deleted"
    assert dict(audit.metadata) == {
        "application_id": str(APPLICATION_ID),
        "session_id": str(session.id),
        "version": "1",
    }
    with pytest.raises(InterviewPrepNotFound):
        await service.get_session(OWNER_ID, session.id)


@pytest.mark.asyncio
async def test_application_adapter_copies_only_exact_purpose_limited_context() -> None:
    source = source_snapshot()
    evidence = source.claims[0].evidence_pins[0]
    validation_calls: list[tuple[ApplicationInterviewEvidenceReference, ...]] = []

    class FakeApplicationService:
        async def get_interview_context(
            self, owner_user_id: object, application_id: object
        ) -> ApplicationInterviewContext:
            assert owner_user_id == OWNER_ID
            assert application_id == APPLICATION_ID
            return ApplicationInterviewContext(
                application_id=APPLICATION_ID,
                stage=ApplicationStage.INTERVIEW,
                job_id=source.job_id,
                job_version=source.job_version,
                job_title=source.job_title,
                company=source.company,
                requirements=(
                    ApplicationRequirementSnapshot(
                        id=REQUIREMENT_ID,
                        requirement_type="responsibility",
                        importance="mandatory",
                        text=source.requirements[0].text,
                        source_start=0,
                        source_end=len(source.requirements[0].text),
                    ),
                ),
                resume_version_id=source.resume_version_id,
                resume_version_number=source.resume_version_number,
                claims=(
                    ApplicationDocumentClaim(
                        id=CLAIM_ID,
                        text=source.claims[0].text,
                        evidence_links=(
                            ApplicationClaimEvidenceLink(
                                evidence_id=evidence.evidence_id,
                                evidence_revision_id=evidence.evidence_revision_id,
                            ),
                        ),
                        requirement_ids=(REQUIREMENT_ID,),
                    ),
                ),
                evidence_pins=(
                    ApplicationEvidencePin(
                        evidence_id=evidence.evidence_id,
                        evidence_revision_id=evidence.evidence_revision_id,
                        revision_number=evidence.revision_number,
                        statement=evidence.statement,
                        statement_sha256=evidence.statement_sha256,
                        strength=evidence.strength,
                        has_numeric_claim=evidence.has_numeric_claim,
                    ),
                ),
            )

        async def validate_interview_evidence(
            self,
            owner_user_id: UUID,
            application_id: UUID,
            references: tuple[ApplicationInterviewEvidenceReference, ...],
        ) -> None:
            assert owner_user_id == OWNER_ID
            assert application_id == APPLICATION_ID
            validation_calls.append(references)

    provider = ApplicationWorkspaceInterviewContextProvider(FakeApplicationService())
    copied = await provider.snapshot(OWNER_ID, APPLICATION_ID)
    await provider.validate_current_evidence(
        OWNER_ID,
        APPLICATION_ID,
        copied.claims[0].evidence_pins,
    )

    assert copied.claims[0].text_sha256 == source.claims[0].text_sha256
    assert copied.claims[0].strong
    assert copied.claims[0].evidence_pins[0].statement_sha256 == (evidence.statement_sha256)
    assert copied.requirements[0].id == REQUIREMENT_ID
    references = validation_calls[0]
    assert references[0].statement_sha256 == evidence.statement_sha256
    assert not hasattr(references[0], "statement")
    assert not hasattr(copied, "stage")
    assert not hasattr(copied, "notes")
    assert not hasattr(copied, "contacts")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_error", "expected_error"),
    [
        (ApplicationWorkspaceConflict(), InterviewPrepConflict),
        (ApplicationWorkspaceVersionConflict(), InterviewPrepConflict),
        (ApplicationWorkspaceIdempotencyConflict(), InterviewPrepConflict),
        (ApplicationWorkspaceValidationError(), InterviewPrepConflict),
        (ApplicationWorkspaceNotFound(), InterviewPrepNotFound),
        (ApplicationWorkspaceUnavailable(), InterviewPrepUnavailable),
    ],
)
async def test_application_adapter_translates_live_evidence_boundary_failures(
    source_error: Exception,
    expected_error: type[Exception],
) -> None:
    source = source_snapshot()

    class FailingApplicationService:
        async def get_interview_context(
            self,
            owner_user_id: UUID,
            application_id: UUID,
        ) -> ApplicationInterviewContext:
            del owner_user_id, application_id
            raise AssertionError("snapshot is not used by this boundary test")

        async def validate_interview_evidence(
            self,
            owner_user_id: UUID,
            application_id: UUID,
            references: tuple[ApplicationInterviewEvidenceReference, ...],
        ) -> None:
            assert owner_user_id == OWNER_ID
            assert application_id == APPLICATION_ID
            assert references
            raise source_error

    provider = ApplicationWorkspaceInterviewContextProvider(FailingApplicationService())

    with pytest.raises(expected_error):
        await provider.validate_current_evidence(
            OWNER_ID,
            APPLICATION_ID,
            source.claims[0].evidence_pins,
        )


@pytest.mark.asyncio
async def test_read_models_fail_closed_when_pinned_evidence_becomes_stale() -> None:
    service, _, applications = _service()
    story = await service.create_story(
        OWNER_ID,
        _story_command(),
        idempotency_key="story-live-grounding-001",
        context=_context(),
    )
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Evidence lifecycle interview",
                kind=InterviewSessionKind.BEHAVIORAL,
            ),
            idempotency_key="session-live-grounding-001",
            context=_context(),
        )
    ).session
    questions = await service.generate_question_bank(
        OWNER_ID,
        session.id,
        idempotency_key="test-key-11111111",
        context=_context(),
    )
    draft = await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
        idempotency_key="draft-live-grounding-001",
        context=_context(),
    )

    applications.validation_error = InterviewPrepConflict("evidence was revoked")

    story_read = await service.get_story_read(OWNER_ID, story.id)
    session_read = await service.get_session_read(OWNER_ID, session.id)
    question_read = await service.get_question_read(
        OWNER_ID,
        session.id,
        questions[0].id,
    )
    draft_read = await service.get_follow_up_draft_read(
        OWNER_ID,
        session.id,
        draft.id,
    )
    assert story_read.grounding.status is GroundingStatus.NEEDS_REVIEW
    assert session_read.grounding.status is GroundingStatus.NEEDS_REVIEW
    assert question_read.grounding.status is GroundingStatus.NEEDS_REVIEW
    assert draft_read.grounding.status is GroundingStatus.NEEDS_REVIEW
    assert all(
        "no longer current" in (item.grounding.warning or "")
        for item in (story_read, session_read, question_read, draft_read)
    )

    applications.validation_error = InterviewPrepUnavailable()
    unavailable = await service.get_story_read(OWNER_ID, story.id)
    assert unavailable.grounding.status is GroundingStatus.UNKNOWN
    assert "could not be checked" in (unavailable.grounding.warning or "")


@pytest.mark.asyncio
async def test_session_collection_uses_bounded_batch_counts() -> None:
    service, state, _ = _service()
    for index in range(2):
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title=f"Bounded session {index}",
                kind=InterviewSessionKind.BEHAVIORAL,
            ),
            idempotency_key=f"session-batch-count-{index:03d}",
            context=_context(),
        )
    original = state.count_session_children_batch
    state.count_session_children_batch = AsyncMock(wraps=original)  # type: ignore[method-assign]
    state.count_session_children = AsyncMock(  # type: ignore[method-assign]
        side_effect=AssertionError("per-session count queries are forbidden")
    )

    result = await service.list_sessions(OWNER_ID, limit=25)

    assert len(result.data) == 2
    state.count_session_children_batch.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_question_bank_replay_preserves_persisted_ordinal_order() -> None:
    service, _, _ = _service()
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Stable question order",
                kind=InterviewSessionKind.BEHAVIORAL,
            ),
            idempotency_key="session-question-order-001",
            context=_context(),
        )
    ).session
    custom = await service.create_question(
        OWNER_ID,
        session.id,
        CreateInterviewQuestion(prompt="First user-authored question?"),
        idempotency_key="custom-question-order-001",
        context=_context(),
    )
    generated = await service.generate_question_bank(
        OWNER_ID,
        session.id,
        idempotency_key="test-key-22222222",
        context=_context(),
    )
    replay = await service.generate_question_bank(
        OWNER_ID,
        session.id,
        idempotency_key="test-key-22222222",
        context=_context(),
    )
    listed = await service.list_questions(OWNER_ID, session.id, limit=25)

    assert custom.ordinal == 1
    assert [item.ordinal for item in generated] == list(range(2, 2 + len(generated)))
    assert [item.id for item in replay] == [item.id for item in generated]
    assert [item.ordinal for item in listed.data] == list(range(1, 1 + len(listed.data)))


@pytest.mark.asyncio
async def test_follow_up_renderer_never_silently_truncates_factual_text() -> None:
    long_title = "T" * 300
    applications = StaticApplicationContext(replace(source_snapshot(), job_title=long_title))
    service, _, _ = _service(source=applications)
    session = (
        await service.create_session(
            OWNER_ID,
            CreateInterviewSession(
                application_id=APPLICATION_ID,
                title="Long-title rendering",
                kind=InterviewSessionKind.BEHAVIORAL,
            ),
            idempotency_key="session-long-title-001",
            context=_context(),
        )
    ).session
    draft = await service.generate_follow_up_draft(
        OWNER_ID,
        session.id,
        GenerateFollowUpDraft(source_claim_ids=(CLAIM_ID,)),
        idempotency_key="draft-long-title-001",
        context=_context(),
    )
    assert draft.subject == "Thank you for the conversation"
    assert long_title in draft.body

    with pytest.raises(
        InterviewPrepValidationError,
        match="select fewer claims",
    ):
        service._render_follow_up_draft(
            long_title,
            session.context.claims * 140,
        )
