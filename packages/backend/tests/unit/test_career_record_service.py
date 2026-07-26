"""Application-level Phase 3 tests using only deterministic inward ports."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from career_record_memory import (
    AllowingVerificationAuthority,
    FakeResumeSourceQuery,
    FixedClock,
    MemoryCareerRecord,
    UuidFactory,
)

from careeros.modules.career_record.application import (
    CareerEntityData,
    CareerRecordService,
    CreateAchievement,
    CreateEvidence,
    CreateImportProposal,
    CreateSkill,
    MetricInput,
    RequestContext,
    ResumeSourceLocator,
    UpdateReminderPreferences,
    ValidatedResumeSource,
)
from careeros.modules.career_record.domain import (
    AchievementStatus,
    CareerEntityKind,
    CareerRecordNotFound,
    CareerRecordSourceUnavailable,
    CareerRecordTransitionRejected,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
    ConflictResolution,
    EmploymentType,
    EvidenceConflictKind,
    EvidenceInputKind,
    EvidenceLifecycle,
    EvidenceStrength,
    EvidenceType,
    MetricPrecision,
    PartialDate,
    ProposalStatus,
    ReminderCadence,
    TimelineFindingKind,
    VerificationDecision,
    VerificationMethod,
    exact_claim_sha256,
)

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


def _context(owner: UUID) -> RequestContext:
    return RequestContext(owner, f"request-{owner.hex[:8]}", "a" * 32)


def _service(
    memory: MemoryCareerRecord,
    sources: FakeResumeSourceQuery,
    *,
    verification: bool = False,
) -> CareerRecordService:
    return CareerRecordService(
        unit_of_work=memory,
        clock=FixedClock(NOW),
        identifiers=UuidFactory(),
        resume_sources=sources,
        verification_authority=(AllowingVerificationAuthority() if verification else None),
    )


def _experience(title: str = "Software Engineer") -> CareerEntityData:
    return CareerEntityData(
        kind=CareerEntityKind.EXPERIENCE,
        title=title,
        organization="Example Corp",
        official_title=title,
        employment_type=EmploymentType.FULL_TIME,
        start_date=PartialDate(2022, 1),
        is_current=True,
    )


def _metric() -> MetricInput:
    return MetricInput(
        name="Preparation time reduction",
        value=Decimal("30.0"),
        value_max=None,
        unit="percent",
        currency=None,
        period="Q2 2026",
        baseline=None,
        comparator="prior manual workflow",
        comparison_applicable=True,
        precision=MetricPrecision.EXACT,
        attribution="My reporting automation",
    )


def _validated_source() -> tuple[ResumeSourceLocator, ValidatedResumeSource]:
    document_id = uuid4()
    snapshot_id = uuid4()
    block_id = uuid4()
    locator = ResumeSourceLocator(document_id, snapshot_id, block_id, 1, 10, 40)
    source = ValidatedResumeSource(
        document_id=document_id,
        snapshot_id=snapshot_id,
        snapshot_revision=2,
        schema_version="canonical-resume/1",
        parser_version="local-parser/1",
        block_id=block_id,
        page=1,
        start_offset=10,
        end_offset=40,
        source_sha256=exact_claim_sha256("Built a deterministic reporting workflow."),
        review_excerpt="Built a deterministic reporting workflow.",
    )
    return locator, source


@pytest.mark.asyncio
async def test_profile_initializes_once_and_enforces_owner_and_versions() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())

    first = await service.get_or_create_profile(owner, _context(owner))
    second = await service.get_or_create_profile(owner, _context(owner))
    assert first.profile.id == second.profile.id
    assert first.profile.professional_headline is None
    assert not hasattr(first.profile, "target_role")

    with pytest.raises(CareerRecordNotFound):
        await service.create_entity(owner, _experience(), _context(other))
    entity = await service.create_entity(owner, _experience(), _context(owner))
    with pytest.raises(CareerRecordVersionConflict):
        await service.update_entity(
            owner, entity.id, 99, _experience("Senior Engineer"), _context(owner)
        )


@pytest.mark.asyncio
async def test_complete_reorder_and_skill_crud_are_owned_and_audited() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    profile = (await service.get_or_create_profile(owner, _context(owner))).profile
    first = await service.create_entity(owner, _experience("Engineer I"), _context(owner))
    second = await service.create_entity(owner, _experience("Engineer II"), _context(owner))
    reordered = await service.reorder_entity_list(
        owner, (second.id, first.id), profile.version, _context(owner)
    )
    assert [item.id for item in reordered.entities] == [second.id, first.id]

    skill = await service.create_skill(owner, CreateSkill("Python", "Technical"), _context(owner))
    await service.link_entity_skill(owner, second.id, skill.id, _context(owner))
    assert memory.entity_skill_links[0].owner_user_id == owner
    assert all(event.owner_user_id == owner for event in memory.audits)


@pytest.mark.asyncio
async def test_explicit_experience_grouping_is_owned_and_classified() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    await service.get_or_create_profile(owner, _context(owner))
    await service.get_or_create_profile(other, _context(other))

    earlier = await service.create_entity(
        owner,
        replace(
            _experience("Engineer I"),
            end_date=PartialDate(2024, 6),
            is_current=False,
        ),
        _context(owner),
    )
    earlier_version = earlier.version
    promoted = await service.create_entity(
        owner,
        replace(_experience("Engineer II"), start_date=PartialDate(2024, 4)),
        _context(owner),
        group_with_entity_id=earlier.id,
    )
    refreshed_earlier = await service.get_entity(owner, earlier.id)
    assert promoted.group_id is not None
    assert refreshed_earlier.group_id == promoted.group_id
    assert refreshed_earlier.version == earlier_version + 1
    assert any(
        finding.kind is TimelineFindingKind.PROMOTION_SEQUENCE
        for finding in (await service.get_profile(owner)).findings
    )

    outside = await service.create_entity(other, _experience(), _context(other))
    with pytest.raises(CareerRecordNotFound):
        await service.create_entity(
            owner,
            replace(_experience("Consultant"), organization="Other Corp"),
            _context(owner),
            group_with_entity_id=outside.id,
        )

    concurrent = await service.create_entity(
        owner,
        replace(_experience("Consultant"), organization="Other Corp"),
        _context(owner),
        group_with_entity_id=promoted.id,
    )
    assert concurrent.group_id == promoted.group_id
    assert any(
        finding.kind is TimelineFindingKind.CONCURRENT_ROLES and concurrent.id in finding.entity_ids
        for finding in (await service.get_profile(owner)).findings
    )


@pytest.mark.asyncio
async def test_resume_import_stays_pending_until_explicit_acceptance() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))
    locator, source = _validated_source()
    sources.add(owner, source)

    proposal = await service.create_import_proposal(
        owner,
        CreateImportProposal(_experience("Imported Engineer"), locator),
        _context(owner),
    )
    assert proposal.status is ProposalStatus.PENDING
    assert await service.list_entities(owner) == ()

    accepted = await service.accept_import_proposal(
        owner, proposal.id, proposal.version, _context(owner)
    )
    assert accepted.title == "Imported Engineer"
    assert (await service.get_import_proposal(owner, proposal.id)).status is ProposalStatus.ACCEPTED


@pytest.mark.asyncio
async def test_deleted_resume_blocks_pending_proposal_and_supported_eligibility() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))
    locator, source = _validated_source()
    sources.add(owner, source)
    proposal = await service.create_import_proposal(
        owner, CreateImportProposal(_experience(), locator), _context(owner)
    )
    evidence = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.RESUME_STATEMENT,
            title="Reporting workflow",
            statement="Built a deterministic reporting workflow.",
            input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
            resume_source=locator,
        ),
        _context(owner),
    )
    assert evidence.revision.strength is EvidenceStrength.SUPPORTED
    assert (await service.evaluate_evidence(owner, evidence.item.id)).factual_eligible

    sources.available.remove(source.snapshot_id)
    with pytest.raises(CareerRecordSourceUnavailable):
        await service.accept_import_proposal(owner, proposal.id, proposal.version, _context(owner))
    decision = await service.evaluate_evidence(owner, evidence.item.id)
    assert not decision.factual_eligible
    assert "source_unavailable" in decision.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "spoofed_statement",
    [
        "Built a deterministic reporting Workflow.",
        "Built 2 deterministic reporting workflows.",
        "Built a deterministic reporting workflow!",
        "Built a  deterministic reporting workflow.",
        "Built a deterministic reporting workflow. Extra claim.",
        "deterministic reporting workflow",
    ],
)
async def test_exact_resume_evidence_rejects_any_nonexact_claim_without_persistence(
    spoofed_statement: str,
) -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    service = _service(memory, sources)
    locator, source = _validated_source()
    sources.add(owner, source)

    with pytest.raises(CareerRecordSourceUnavailable):
        await service.create_evidence(
            owner,
            CreateEvidence(
                evidence_type=EvidenceType.RESUME_STATEMENT,
                title="Client-controlled title",
                statement=spoofed_statement,
                input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
                resume_source=locator,
            ),
            _context(owner),
        )

    assert memory.evidence == {}
    assert memory.audits == []


@pytest.mark.asyncio
async def test_exact_resume_evidence_is_statement_only_and_derives_its_title() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    service = _service(memory, sources)
    locator, source = _validated_source()
    sources.add(owner, source)

    exact = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.RESUME_STATEMENT,
            title="Untrusted client label",
            statement="  Built a deterministic reporting workflow.  ",
            input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
            resume_source=locator,
        ),
        _context(owner),
    )

    assert exact.revision.title == exact.revision.statement
    assert exact.revision.strength is EvidenceStrength.SUPPORTED
    assert (await service.evaluate_evidence(owner, exact.item.id)).eligible

    with pytest.raises(CareerRecordValidationError):
        await service.create_evidence(
            owner,
            CreateEvidence(
                evidence_type=EvidenceType.ACHIEVEMENT,
                title="Injected metadata",
                statement=source.review_excerpt,
                organization="Unproven organization",
                input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
                resume_source=locator,
                skill_ids=(uuid4(),),
            ),
            _context(owner),
        )


@pytest.mark.asyncio
async def test_legacy_supported_claim_mismatch_is_readable_but_ineligible() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    service = _service(memory, sources)
    locator, source = _validated_source()
    sources.add(owner, source)
    exact = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.RESUME_STATEMENT,
            title="Ignored",
            statement=source.review_excerpt,
            input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
            resume_source=locator,
        ),
        _context(owner),
    )
    spoofed_revision = replace(
        exact.revision,
        title="Kubernetes",
        statement="Led an unrelated Kubernetes migration.",
    )
    memory.evidence[exact.item.id] = replace(
        exact,
        revision=spoofed_revision,
        revisions=(spoofed_revision,),
    )

    stored = await service.get_evidence(owner, exact.item.id)
    decision = await service.evaluate_evidence(owner, exact.item.id)

    assert stored.revision.strength is EvidenceStrength.SUPPORTED
    assert not decision.eligible
    assert "supported_scope_mismatch" in decision.reason_codes


@pytest.mark.asyncio
async def test_manual_and_url_evidence_remain_inferred_until_owner_confirmation() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    record = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.PORTFOLIO,
            title="Portfolio project",
            statement="Published a fictional demonstration project.",
            external_url_source="https://example.com/portfolio",
        ),
        _context(owner),
    )
    assert record.revision.strength is EvidenceStrength.INFERRED
    assert not (await service.evaluate_evidence(owner, record.item.id)).factual_eligible

    confirmed = await service.confirm_evidence(
        owner, record.item.id, record.item.version, _context(owner)
    )
    assert confirmed.revision.strength is EvidenceStrength.CONFIRMED
    assert (await service.evaluate_evidence(owner, record.item.id)).factual_eligible


@pytest.mark.asyncio
async def test_analytics_growth_uses_canonical_eligibility_and_achievement_type() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    achievement = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.ACHIEVEMENT,
            title="Fictional delivery milestone",
            statement="Completed the explicitly supported delivery milestone.",
        ),
        _context(owner),
    )
    confirmed = await service.confirm_evidence(
        owner,
        achievement.item.id,
        achievement.item.version,
        _context(owner),
    )
    note = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.NOTE,
            title="Fictional note",
            statement="Captured a confirmed note that is not an achievement.",
        ),
        _context(owner),
    )
    await service.confirm_evidence(
        owner,
        note.item.id,
        note.item.version,
        _context(owner),
    )

    eligible = await service.list_analytics_growth(
        owner,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
    )
    assert [point.evidence_revision_id for point in eligible] == [confirmed.revision.id]
    assert all(point.category == EvidenceType.ACHIEVEMENT.value for point in eligible)
    assert (await service.analytics_watermark(owner)).record_count == 1

    memory.evidence[confirmed.item.id] = replace(
        confirmed,
        sources=tuple(replace(source, available=False) for source in confirmed.sources),
    )
    assert (
        await service.list_analytics_growth(
            owner,
            window_start=date(2026, 1, 1),
            window_end=date(2026, 12, 31),
        )
        == ()
    )

    guarded_start = date(2010, 1, 1)
    assert (
        await service.list_analytics_growth(
            owner,
            window_start=guarded_start,
            window_end=guarded_start + timedelta(days=3_652),
        )
        == ()
    )
    with pytest.raises(CareerRecordValidationError, match="timezone guard"):
        await service.list_analytics_growth(
            owner,
            window_start=guarded_start,
            window_end=guarded_start + timedelta(days=3_653),
        )


@pytest.mark.asyncio
async def test_numeric_confirmation_requires_complete_decimal_dimensions() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    incomplete = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.METRIC,
            title="Reporting result",
            statement="Reduced review time by 30%.",
        ),
        _context(owner),
    )
    with pytest.raises(CareerRecordValidationError):
        await service.confirm_evidence(
            owner, incomplete.item.id, incomplete.item.version, _context(owner)
        )

    complete = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.METRIC,
            title="Measured reporting result",
            statement="Reduced preparation time by 30%.",
            metrics=(_metric(),),
        ),
        _context(owner),
    )
    confirmed = await service.confirm_evidence(
        owner, complete.item.id, complete.item.version, _context(owner)
    )
    decision = await service.evaluate_evidence(owner, confirmed.item.id)
    assert decision.factual_eligible and decision.numeric_eligible
    assert confirmed.metrics[0].value == Decimal("30.0")


@pytest.mark.asyncio
async def test_internal_verification_is_disabled_unless_authority_is_configured() -> None:
    owner = uuid4()
    decision = VerificationDecision(
        VerificationMethod.APPROVED_MANUAL_REVIEW,
        "review-123",
        "internal-review-record",
        "exact claim",
        NOW,
    )
    memory = MemoryCareerRecord()
    disabled = _service(memory, FakeResumeSourceQuery())
    record = await disabled.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.NOTE,
            title="Confirmed fact",
            statement="Created an internal tool.",
        ),
        _context(owner),
    )
    confirmed = await disabled.confirm_evidence(
        owner, record.item.id, record.item.version, _context(owner)
    )
    with pytest.raises(CareerRecordTransitionRejected):
        await disabled.verify_evidence_internal(
            owner, confirmed.item.id, confirmed.item.version, decision, _context(owner)
        )

    enabled = _service(memory, FakeResumeSourceQuery(), verification=True)
    verified = await enabled.verify_evidence_internal(
        owner, confirmed.item.id, confirmed.item.version, decision, _context(owner)
    )
    assert verified.revision.strength is EvidenceStrength.VERIFIED


@pytest.mark.asyncio
async def test_exact_conflicts_are_detected_and_resolution_is_explicit() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    first = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.ACHIEVEMENT,
            title="Launch result",
            statement="Improved a fictional launch workflow.",
            organization="Example Corp",
            start_date=PartialDate(2025, 1),
        ),
        _context(owner),
    )
    second = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.ACHIEVEMENT,
            title="Launch result",
            statement="Improved a fictional launch workflow.",
            organization="Example Corp",
            start_date=PartialDate(2025, 2),
        ),
        _context(owner),
    )
    assert len(second.conflicts) == 1
    conflict = second.conflicts[0]
    assert conflict.kind is EvidenceConflictKind.DATE
    assert "open_conflict" in (await service.evaluate_evidence(owner, first.item.id)).reason_codes
    resolved = await service.resolve_evidence_conflict(
        owner,
        conflict.id,
        conflict.version,
        ConflictResolution.KEEP_BOTH,
        _context(owner),
    )
    assert resolved.resolution is ConflictResolution.KEEP_BOTH
    assert first.item.id != second.item.id


@pytest.mark.asyncio
async def test_achievement_conversion_is_explicit_idempotent_and_preserves_unanswered_fields() -> (
    None
):
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    await service.get_or_create_profile(owner, _context(owner))
    draft = await service.create_achievement(
        owner,
        CreateAchievement(
            title="Reporting automation",
            delivered="Built a reporting automation workflow.",
            problem="Weekly preparation was manual.",
            measurement=None,
            reminder_cadence=ReminderCadence.MONTHLY,
        ),
        _context(owner),
    )
    converted = await service.convert_achievement(
        owner, draft.id, draft.version, "achievement:convert:1", _context(owner)
    )
    repeated = await service.convert_achievement(
        owner, draft.id, draft.version, "achievement:convert:1", _context(owner)
    )
    assert converted.item.id == repeated.item.id
    assert converted.revision.strength is EvidenceStrength.CONFIRMED
    assert "Measurement:" not in (converted.revision.context or "")
    assert (await service.get_achievement(owner, draft.id)).status is AchievementStatus.CONVERTED


@pytest.mark.asyncio
async def test_archive_and_recurring_reminder_preferences_are_versioned() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    record = await service.create_evidence(
        owner,
        CreateEvidence(
            evidence_type=EvidenceType.NOTE,
            title="Draft note",
            statement="Captured a factual draft.",
        ),
        _context(owner),
    )
    archived = await service.archive_evidence(
        owner, record.item.id, record.item.version, _context(owner)
    )
    assert archived.lifecycle is EvidenceLifecycle.ARCHIVED
    assert not (await service.evaluate_evidence(owner, record.item.id)).factual_eligible

    preferences = await service.get_or_create_reminder_preferences(owner, _context(owner))
    updated = await service.update_reminder_preferences(
        owner,
        preferences.version,
        UpdateReminderPreferences(True, 12, "Asia/Kolkata"),
        _context(owner),
    )
    assert updated.enabled and updated.day_of_month == 12
