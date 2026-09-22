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

from rezumi.modules.career_record.application import (
    AcceptSemanticImportProposal,
    CareerEntityData,
    CareerRecordService,
    CreateAchievement,
    CreateEvidence,
    CreateImportProposal,
    CreateSemanticImportProposals,
    CreateSkill,
    LinkCareerEntityRelationship,
    MetricInput,
    RequestContext,
    ResumeSourceLocator,
    UpdateReminderPreferences,
    UpdateSkill,
    ValidatedResumeSource,
)
from rezumi.modules.career_record.domain import (
    AchievementStatus,
    CareerEntityKind,
    CareerFieldTarget,
    CareerRecordIdempotencyConflict,
    CareerRecordNotFound,
    CareerRecordSourceUnavailable,
    CareerRecordTransitionRejected,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
    CareerRelationshipKind,
    ConfirmationState,
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
    SemanticCandidateKind,
    SemanticFieldOrigin,
    SemanticImportAnchor,
    SemanticImportField,
    SemanticImportFieldState,
    SemanticImportStatus,
    SemanticImportTarget,
    TimelineFindingKind,
    ValidatedSemanticCandidate,
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


def _semantic_field(
    name: str,
    value: str,
    *,
    field_type: str = "text",
    precision: str | None = None,
    user_added: bool = False,
) -> SemanticImportField:
    anchor = SemanticImportAnchor(
        block_id=uuid4(),
        page=1,
        start_offset=10,
        end_offset=10 + len(value),
        source_sha256=exact_claim_sha256(value),
        source_excerpt=value,
    )
    return SemanticImportField(
        semantic_field_id=uuid4(),
        name=name,
        field_type=field_type,
        value=value,
        review_state=(
            SemanticImportFieldState.USER_ADDED
            if user_added
            else SemanticImportFieldState.CONFIRMED
        ),
        confidence_basis_points=9_000,
        date_precision=precision,
        anchors=() if user_added else (anchor,),
    )


def _semantic_candidate(
    document_id: UUID,
    snapshot_id: UUID,
    kind: SemanticCandidateKind,
    fields: tuple[SemanticImportField, ...],
) -> ValidatedSemanticCandidate:
    return ValidatedSemanticCandidate(
        document_id=document_id,
        snapshot_id=snapshot_id,
        snapshot_revision=3,
        schema_version="canonical-semantics/1.0.0",
        parser_version="local-semantic/1",
        semantic_entity_id=uuid4(),
        kind=kind,
        fields=fields,
    )


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
async def test_manual_entity_requires_explicit_confirmation_for_readiness() -> None:
    owner = uuid4()
    memory = MemoryCareerRecord()
    service = _service(memory, FakeResumeSourceQuery())
    await service.get_or_create_profile(owner, _context(owner))

    entity = await service.create_entity(
        owner,
        _experience(),
        _context(owner),
    )

    assert memory.entity_confirmations[entity.id].state is ConfirmationState.NEEDS_REVIEW
    assert (await service.readiness_snapshot(owner)).entities == ()

    confirmed, confirmation = await service.confirm_entity(
        owner,
        entity.id,
        entity.version,
        _context(owner),
    )
    assert confirmation.state is ConfirmationState.CONFIRMED
    assert [item.id for item in (await service.readiness_snapshot(owner)).entities] == [entity.id]
    provenance = await memory.list_field_provenance(owner, entity.id)
    assert provenance
    assert {item.origin for item in provenance} == {SemanticFieldOrigin.OWNER_ATTESTATION}

    updated = await service.update_entity(
        owner,
        entity.id,
        confirmed.version,
        _experience("Senior Engineer"),
        _context(owner),
    )
    assert updated.title == "Senior Engineer"
    assert memory.entity_confirmations[entity.id].state is ConfirmationState.NEEDS_REVIEW
    assert (await service.readiness_snapshot(owner)).entities == ()

    skill = await service.create_skill(
        owner,
        CreateSkill("Python"),
        _context(owner),
    )
    assert (await service.readiness_snapshot(owner)).skills == ()
    confirmed_skill, skill_confirmation = await service.confirm_skill(
        owner,
        skill.id,
        skill.version,
        _context(owner),
    )
    assert skill_confirmation.state is ConfirmationState.CONFIRMED
    assert [item.id for item in (await service.readiness_snapshot(owner)).skills] == [skill.id]
    await service.update_skill(
        owner,
        skill.id,
        confirmed_skill.version,
        UpdateSkill("Python", "Programming", None),
        _context(owner),
    )
    assert memory.skill_confirmations[skill.id].state is ConfirmationState.NEEDS_REVIEW
    assert (await service.readiness_snapshot(owner)).skills == ()

    project = await service.create_entity(
        owner,
        CareerEntityData(
            kind=CareerEntityKind.PROJECT,
            title="Fictional project",
            description="Owner-entered project.",
        ),
        _context(owner),
    )
    confirmed_project, _ = await service.confirm_entity(
        owner,
        project.id,
        project.version,
        _context(owner),
    )
    relationship = await service.link_entity_relationship(
        owner,
        LinkCareerEntityRelationship(
            source_entity_id=updated.id,
            target_entity_id=confirmed_project.id,
            kind=CareerRelationshipKind.EXPERIENCE_PROJECT,
        ),
        _context(owner),
    )
    assert (await service.readiness_snapshot(owner)).relationships == ()
    reconfirmed, _ = await service.confirm_entity(
        owner,
        updated.id,
        updated.version,
        _context(owner),
    )
    readiness = await service.readiness_snapshot(owner)
    assert readiness.relationships[0].id == relationship.id
    assert {item.id for item in readiness.entities} == {
        reconfirmed.id,
        confirmed_project.id,
    }
    await service.unlink_entity_relationship(
        owner,
        relationship.id,
        _context(owner),
    )
    assert await service.list_entity_relationships(owner) == ()


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
async def test_reviewed_semantic_import_preserves_field_provenance_and_requires_acceptance() -> (
    None
):
    owner = uuid4()
    other = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    fields = (
        _semantic_field("title", "Software Engineer"),
        _semantic_field("employer", "Example Corp"),
        _semantic_field(
            "start_date",
            "Jan 2022",
            field_type="date",
            precision="month",
        ),
        _semantic_field(
            "end_date",
            "Present",
            field_type="date",
            precision="unknown",
        ),
        _semantic_field(
            "achievement",
            "Built an owner-reviewed workflow.",
            field_type="bullet",
            user_added=True,
        ),
    )
    candidate = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.EXPERIENCE,
        fields,
    )
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    sources.add_semantic(owner, document_id, snapshot_id, (candidate,))
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))

    with pytest.raises(CareerRecordSourceUnavailable):
        await service.create_semantic_import_proposals(
            other,
            CreateSemanticImportProposals(document_id, snapshot_id),
            _context(other),
        )

    batch = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )
    assert batch.questions == ()
    assert len(batch.proposals) == 1
    proposal = batch.proposals[0]
    assert proposal.target is SemanticImportTarget.ENTITY
    assert proposal.status is SemanticImportStatus.PENDING
    assert memory.entities == {}

    repeat = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )
    assert repeat.proposals == batch.proposals

    values = {field.semantic_field_id: field.value for field in fields}
    values[fields[4].semantic_field_id] = "Built a reviewed workflow."
    accepted = await service.accept_semantic_import_proposal(
        owner,
        proposal.id,
        proposal.version,
        AcceptSemanticImportProposal(values, "semantic:accept:experience"),
        _context(owner),
    )

    assert accepted.entity is not None
    assert accepted.entity.organization == "Example Corp"
    assert len(memory.achievements) == 1
    assert next(iter(memory.achievements.values())).delivered == "Built a reviewed workflow."
    assert accepted.entity.start_date == PartialDate(2022, 1)
    assert accepted.entity.is_current
    assert accepted.proposal.status is SemanticImportStatus.ACCEPTED
    confirmation = memory.entity_confirmations[accepted.entity.id]
    assert confirmation.state.value == "confirmed"
    provenance = await memory.list_field_provenance(owner, accepted.entity.id)
    assert all(item.target is CareerFieldTarget.ENTITY for item in provenance)
    assert {item.origin for item in provenance} == {
        SemanticFieldOrigin.RESUME_PARSER,
        SemanticFieldOrigin.OWNER_EDIT,
    }
    user_edit = next(item for item in provenance if item.origin is SemanticFieldOrigin.OWNER_EDIT)
    assert user_edit.anchors == ()
    current_provenance = await service.current_field_provenance(owner, accepted.entity.id)
    assert {item.field_name for item in current_provenance} == {
        "title",
        "official_title",
        "display_title",
        "organization",
        "start_date",
        "description",
        "is_current",
    }
    assert all(
        [
            await service.field_provenance_source_available(owner, item)
            for item in current_provenance
        ]
    )

    replay = await service.accept_semantic_import_proposal(
        owner,
        proposal.id,
        1,
        AcceptSemanticImportProposal(values, "semantic:accept:experience"),
        _context(owner),
    )
    assert replay.entity is not None and replay.entity.id == accepted.entity.id
    with pytest.raises(CareerRecordIdempotencyConflict):
        await service.accept_semantic_import_proposal(
            owner,
            proposal.id,
            1,
            AcceptSemanticImportProposal(values, "semantic:accept:different"),
            _context(owner),
        )


@pytest.mark.asyncio
async def test_semantic_contact_and_skill_candidates_do_not_overwrite_or_invent_missing_data() -> (
    None
):
    owner = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    contact = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.CONTACT,
        (
            _semantic_field("name", "Alex Example"),
            _semantic_field("email", "alex@example.test", field_type="email"),
        ),
    )
    skill = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.SKILL,
        (_semantic_field("name", "Python"),),
    )
    incomplete = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.EXPERIENCE,
        (_semantic_field("title", "Engineer"),),
    )
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    sources.add_semantic(owner, document_id, snapshot_id, (contact, skill, incomplete))
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))

    batch = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )

    assert len(batch.proposals) == 2
    assert batch.questions[0].missing_fields == ("employer",)
    for proposal in batch.proposals:
        values = {field.semantic_field_id: field.value for field in proposal.fields}
        await service.accept_semantic_import_proposal(
            owner,
            proposal.id,
            proposal.version,
            AcceptSemanticImportProposal(values, f"semantic:accept:{proposal.id}"),
            _context(owner),
        )
    assert {fact.kind.value for fact in memory.personal_facts.values()} == {
        "name",
        "email",
    }
    readiness = await service.readiness_snapshot(owner)
    assert {fact.kind for fact in readiness.personal_facts} == {
        "name",
        "email",
    }
    assert {fact.value for fact in readiness.personal_facts} == {
        "Alex Example",
        "alex@example.test",
    }
    assert {skill.name for skill in memory.skills.values()} == {"Python"}
    assert memory.entities == {}


@pytest.mark.asyncio
async def test_semantic_contact_with_bare_profile_links_accepts() -> None:
    owner = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    contact = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.CONTACT,
        (
            _semantic_field("name", "Alex Example"),
            _semantic_field("email", "alex@example.test", field_type="email"),
            _semantic_field(
                "link",
                "linkedin.com/in/alex-example",
                field_type="url",
            ),
        ),
    )
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    sources.add_semantic(owner, document_id, snapshot_id, (contact,))
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))

    batch = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )
    proposal = batch.proposals[0]
    values = {field.semantic_field_id: field.value for field in proposal.fields}
    await service.accept_semantic_import_proposal(
        owner,
        proposal.id,
        proposal.version,
        AcceptSemanticImportProposal(values, f"semantic:accept:{proposal.id}"),
        _context(owner),
    )

    assert {(fact.kind.value, fact.value) for fact in memory.personal_facts.values()} == {
        ("name", "Alex Example"),
        ("email", "alex@example.test"),
        ("link", "https://linkedin.com/in/alex-example"),
    }


@pytest.mark.asyncio
async def test_semantic_skill_proposal_imports_every_reviewed_name() -> None:
    owner = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    skill = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.SKILL,
        (
            _semantic_field("name", "Python"),
            _semantic_field("name", "TypeScript"),
            _semantic_field("name", "FastAPI"),
        ),
    )
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    sources.add_semantic(owner, document_id, snapshot_id, (skill,))
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))

    batch = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )

    assert len(batch.proposals) == 3
    for proposal in batch.proposals:
        values = {field.semantic_field_id: field.value for field in proposal.fields}
        await service.accept_semantic_import_proposal(
            owner,
            proposal.id,
            proposal.version,
            AcceptSemanticImportProposal(values, f"semantic:accept:{proposal.id}"),
            _context(owner),
        )
    assert {skill.name for skill in memory.skills.values()} == {
        "Python",
        "TypeScript",
        "FastAPI",
    }


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
async def test_semantic_import_materializes_resume_bullets_as_achievements_and_evidence() -> None:
    owner = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    block_id = uuid4()
    bullet = "Built an owner-reviewed workflow."
    fields = (
        _semantic_field("title", "Software Engineer"),
        _semantic_field("employer", "Example Corp"),
        SemanticImportField(
            semantic_field_id=uuid4(),
            name="achievement",
            field_type="bullet",
            value=bullet,
            review_state=SemanticImportFieldState.CONFIRMED,
            confidence_basis_points=9_000,
            date_precision=None,
            anchors=(
                SemanticImportAnchor(
                    block_id=block_id,
                    page=1,
                    start_offset=0,
                    end_offset=len(bullet),
                    source_sha256=exact_claim_sha256(bullet),
                    source_excerpt=bullet,
                ),
            ),
        ),
    )
    candidate = _semantic_candidate(
        document_id,
        snapshot_id,
        SemanticCandidateKind.EXPERIENCE,
        fields,
    )
    memory = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    sources.add_semantic(owner, document_id, snapshot_id, (candidate,))
    sources.add(
        owner,
        ValidatedResumeSource(
            document_id=document_id,
            snapshot_id=snapshot_id,
            snapshot_revision=3,
            schema_version="canonical-resume/1",
            parser_version="local-parser/1",
            block_id=block_id,
            page=1,
            start_offset=0,
            end_offset=len(bullet),
            source_sha256=exact_claim_sha256(bullet),
            review_excerpt=bullet,
        ),
    )
    service = _service(memory, sources)
    await service.get_or_create_profile(owner, _context(owner))

    batch = await service.create_semantic_import_proposals(
        owner,
        CreateSemanticImportProposals(document_id, snapshot_id),
        _context(owner),
    )
    proposal = batch.proposals[0]
    values = {field.semantic_field_id: field.value for field in fields}
    await service.accept_semantic_import_proposal(
        owner,
        proposal.id,
        proposal.version,
        AcceptSemanticImportProposal(values, "semantic:accept:experience"),
        _context(owner),
    )

    assert len(memory.achievements) == 1
    achievement = next(iter(memory.achievements.values()))
    assert achievement.delivered == bullet
    assert achievement.entity_id is not None
    assert achievement.title.startswith("Example Corp:")

    assert len(memory.evidence) == 1
    evidence = next(iter(memory.evidence.values()))
    assert evidence.revision.statement == bullet
    assert evidence.revision.strength is EvidenceStrength.SUPPORTED
    assert evidence.entity_ids == (achievement.entity_id,)


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
