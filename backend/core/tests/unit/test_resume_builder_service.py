"""Service-level tests for Phase 7 resume builder."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resume_builder_memory import (
    EVIDENCE_ID,
    OTHER_ID,
    OWNER_ID,
    FixedClock,
    MemoryResumeBuilder,
    MemoryStorage,
    PlainTextExtractor,
    StaticResumeSourceProvider,
    TextOnlyRenderer,
    UuidFactory,
)
from rezumi.modules.resume_builder.application import (
    CreateResume,
    ExportResume,
    RequestContext,
    ResumeBuilderPolicy,
    ResumeBuilderService,
    ResumeExportProcessor,
    UpdateResume,
    version_provenance_failures,
)
from rezumi.modules.resume_builder.domain import (
    ResumeBuilderNotFound,
    ResumeBuilderValidationError,
    ResumeExportBlocked,
    ResumeExportStatus,
    ResumeFormat,
    ResumeTemplate,
)


def _service(
    *,
    state: MemoryResumeBuilder | None = None,
    source: StaticResumeSourceProvider | None = None,
) -> ResumeBuilderService:
    return ResumeBuilderService(
        unit_of_work=state or MemoryResumeBuilder(),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        sources=source or StaticResumeSourceProvider(),
        storage=MemoryStorage(),
        policy=ResumeBuilderPolicy(),
    )


def _context(user_id=OWNER_ID) -> RequestContext:
    return RequestContext(actor_user_id=user_id, request_id="req-test", trace_id="trace-test")


@pytest.mark.asyncio
async def test_create_update_version_export_and_download_are_grounded_and_idempotent() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
        policy=ResumeBuilderPolicy(),
    )
    created = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Launch PM Resume",
            target_role="Senior Product Manager",
            template=ResumeTemplate.STANDARD_PROFESSIONAL,
        ),
        idempotency_key="resume-create-key",
        context=_context(),
    )
    replay = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Launch PM Resume",
            target_role="Senior Product Manager",
            template=ResumeTemplate.STANDARD_PROFESSIONAL,
        ),
        idempotency_key="resume-create-key",
        context=_context(),
    )
    assert replay.resume.id == created.resume.id
    assert created.current_version.source_evidence_ids
    assert created.current_version.sections[0].items[0].evidence_ids == (EVIDENCE_ID,)

    edited_section = created.current_version.sections[0]
    grounded_edit = await service.update_resume(
        OWNER_ID,
        created.resume.id,
        UpdateResume(
            title="Launch PM Resume",
            sections=(edited_section,),
            template=ResumeTemplate.COMPACT_TECHNICAL,
        ),
        expected_version=created.resume.version,
        idempotency_key="resume-update-key",
        context=_context(),
    )
    assert grounded_edit.resume.version == 2
    assert grounded_edit.current_version.id != created.current_version.id
    assert grounded_edit.current_version.parent_version_id == created.current_version.id

    checkpoint = await service.create_version(
        OWNER_ID,
        grounded_edit.resume.id,
        expected_version=grounded_edit.resume.version,
        idempotency_key="resume-version-key",
        context=_context(),
    )
    exported = await service.export_version(
        OWNER_ID,
        checkpoint.id,
        ExportResume(format=ResumeFormat.TEXT),
        idempotency_key="resume-export-key",
        context=_context(),
    )
    assert exported.export.status == ResumeExportStatus.PENDING
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    outcome = await processor.process(exported.export.id, "worker-execution-token")
    assert outcome.status == ResumeExportStatus.VERIFIED
    exported = await service.get_export(OWNER_ID, exported.export.id)
    assert exported.verification is not None
    assert exported.verification.status.value == "passed"
    assert exported.export.sha256_digest is not None

    intent = await service.create_download_intent(
        OWNER_ID,
        exported.export.id,
        idempotency_key="resume-download-key",
        context=_context(),
    )
    assert intent.url.startswith("https://downloads.invalid/resume-exports/")


@pytest.mark.asyncio
async def test_creation_requires_eligible_evidence() -> None:
    service = _service(source=StaticResumeSourceProvider(with_evidence=False))
    with pytest.raises(ResumeBuilderValidationError, match="eligible career evidence"):
        await service.create_resume(
            OWNER_ID,
            CreateResume(
                title="No Evidence Resume",
                target_role=None,
                template=ResumeTemplate.EXECUTIVE,
            ),
            idempotency_key="resume-no-evidence",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_preview_source_returns_empty_when_career_evidence_is_missing() -> None:
    service = _service(source=StaticResumeSourceProvider(with_evidence=False))
    snapshot = await service.preview_source(OWNER_ID)
    assert snapshot.bullets == ()
    assert snapshot.source_evidence_ids == ()


@pytest.mark.asyncio
async def test_update_rejects_ungrounded_bullets_and_cross_user_reads_are_hidden() -> None:
    service = _service()
    created = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Grounded Resume",
            target_role=None,
            template=ResumeTemplate.GRADUATE,
        ),
        idempotency_key="resume-grounded",
        context=_context(),
    )
    section = created.current_version.sections[0]
    ungrounded = (
        section.__class__(
            id=section.id,
            title=section.title,
            kind=section.kind,
            items=(
                section.items[0].__class__(
                    id=section.items[0].id,
                    text="Invented unsupported ownership of billing systems.",
                    evidence_ids=(OTHER_ID,),
                    source="manual",
                ),
            ),
        ),
    )
    with pytest.raises(ResumeBuilderValidationError):
        await service.update_resume(
            OWNER_ID,
            created.resume.id,
            UpdateResume(sections=ungrounded),
            expected_version=created.resume.version,
            idempotency_key="resume-bad-edit",
            context=_context(),
        )
    with pytest.raises(ResumeBuilderNotFound):
        await service.get_resume(OTHER_ID, created.resume.id)


@pytest.mark.asyncio
async def test_blocked_export_cannot_create_download_intent() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
        policy=ResumeBuilderPolicy(),
    )
    created = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Blocked Resume",
            target_role=None,
            template=ResumeTemplate.CONSULTING_FINANCE,
        ),
        idempotency_key="resume-blocked",
        context=_context(),
    )
    exported = await service.export_version(
        OWNER_ID,
        created.current_version.id,
        ExportResume(format=ResumeFormat.TEXT),
        idempotency_key="resume-blocked-export",
        context=_context(),
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(omit_expected=True),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    await processor.process(exported.export.id, "worker-execution-token")
    exported = await service.get_export(OWNER_ID, exported.export.id)
    assert exported.export.status == ResumeExportStatus.BLOCKED
    assert exported.verification is not None
    assert exported.verification.critical_failures
    with pytest.raises(ResumeExportBlocked):
        await service.create_download_intent(
            OWNER_ID,
            exported.export.id,
            idempotency_key="resume-blocked-download",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_bullet_ids_are_globally_unique_across_sections() -> None:
    service = _service()
    created = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Unique claim ledger",
            target_role=None,
            template=ResumeTemplate.STANDARD_PROFESSIONAL,
        ),
        idempotency_key="resume-global-claim-id",
        context=_context(),
    )
    experience, skills = created.current_version.sections
    duplicate_skill = replace(
        skills.items[0],
        id=experience.items[0].id,
    )
    with pytest.raises(
        ResumeBuilderValidationError,
        match="globally unique",
    ):
        await service.update_resume(
            OWNER_ID,
            created.resume.id,
            UpdateResume(
                sections=(
                    experience,
                    replace(skills, items=(duplicate_skill,)),
                )
            ),
            expected_version=created.resume.version,
            idempotency_key="resume-global-claim-id-update",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_verifier_never_claims_grounding_for_legacy_missing_references() -> None:
    service = _service()
    created = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Legacy provenance check",
            target_role=None,
            template=ResumeTemplate.STANDARD_PROFESSIONAL,
        ),
        idempotency_key="resume-legacy-provenance",
        context=_context(),
    )
    section = created.current_version.sections[0]
    legacy = replace(
        created.current_version,
        sections=(
            replace(
                section,
                items=(
                    replace(
                        section.items[0],
                        evidence_references=(),
                    ),
                ),
            ),
        ),
    )
    failures = version_provenance_failures(legacy)
    assert any(value.startswith("invalid_provenance:") for value in failures)
