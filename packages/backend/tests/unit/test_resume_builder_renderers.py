"""Renderer and round-trip extraction tests for Phase 7 exports."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from rezumi.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeEntityFact,
    ResumeFontFamily,
    ResumeFormat,
    ResumeLayout,
    ResumeLineSpacing,
    ResumeMarginSize,
    ResumePageSize,
    ResumePartialDate,
    ResumePersonalFact,
    ResumeSection,
    ResumeTemplate,
    ResumeVersion,
)
from rezumi.modules.resume_builder.infrastructure import (
    DeterministicResumeRenderer,
    ResumeBuilderDocumentExtractor,
    ResumeExportExtractionError,
    ResumeExportExtractionLimits,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000721")
RESUME_ID = UUID("00000000-0000-4000-8000-000000000722")
VERSION_ID = UUID("00000000-0000-4000-8000-000000000723")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000724")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fmt", "media_type", "suffix"),
    [
        (ResumeFormat.PDF, "application/pdf", ".pdf"),
        (
            ResumeFormat.DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        ),
    ],
)
async def test_pdf_and_docx_exports_round_trip_searchable_text(
    tmp_path: Path, fmt: ResumeFormat, media_type: str, suffix: str
) -> None:
    version = ResumeVersion(
        id=VERSION_ID,
        owner_user_id=OWNER_ID,
        resume_id=RESUME_ID,
        version_number=1,
        parent_version_id=None,
        title="Internal working title",
        target_role="Senior Product Manager",
        template=ResumeTemplate.STANDARD_PROFESSIONAL,
        sections=(
            ResumeSection(
                id=UUID("00000000-0000-4000-8000-000000000725"),
                title="Experience",
                kind="experience",
                items=(
                    ResumeBullet(
                        id=UUID("00000000-0000-4000-8000-000000000726"),
                        text="Improved café onboarding for customers in München.",
                        evidence_ids=(EVIDENCE_ID,),
                        source="career_record",
                        entity_id=UUID("00000000-0000-4000-8000-000000000727"),
                    ),
                ),
            ),
        ),
        plain_text="Searchable Product Resume\nSenior Product Manager",
        source_evidence_ids=(EVIDENCE_ID,),
        source_change_set_id=None,
        source_change_set_version_id=None,
        created_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        personal_facts=(
            ResumePersonalFact(
                id=UUID("00000000-0000-4000-8000-000000000728"),
                kind="name",
                value="José Núñez",
                label=None,
                is_primary=True,
            ),
            ResumePersonalFact(
                id=UUID("00000000-0000-4000-8000-000000000729"),
                kind="email",
                value="jose@example.test",
                label=None,
                is_primary=True,
            ),
        ),
        entities=(
            ResumeEntityFact(
                id=UUID("00000000-0000-4000-8000-000000000727"),
                kind="experience",
                title="Ingénieur logiciel",
                organization="Société Exemple",
                official_title="Software Engineer",
                display_title="Ingénieur logiciel",
                location="München",
                start_date=ResumePartialDate(2024, 2),
                end_date=None,
                is_current=True,
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
        layout=ResumeLayout(
            page_size=ResumePageSize.A4,
            page_limit=2,
            font_family=ResumeFontFamily.SANS,
            font_size_pt=10,
            line_spacing=ResumeLineSpacing.STANDARD,
            margins=ResumeMarginSize.STANDARD,
        ),
    )
    rendered = DeterministicResumeRenderer().render(version, fmt=fmt.value)
    path = tmp_path / f"resume{suffix}"
    path.write_bytes(rendered.content)
    extracted = await ResumeBuilderDocumentExtractor(
        ResumeExportExtractionLimits(
            max_bytes=2_000_000,
            max_pdf_pages=3,
            max_archive_entries=200,
            max_archive_uncompressed_bytes=10_000_000,
            max_archive_ratio=100,
            processing_timeout_seconds=5,
        )
    ).extract(
        path,
        media_type,
    )
    for line in rendered.expected_lines:
        assert line in extracted.plain_text
    assert "Internal working title" not in extracted.plain_text


@pytest.mark.asyncio
async def test_export_verifier_rejects_oversized_and_malformed_bytes(
    tmp_path: Path,
) -> None:
    limits = ResumeExportExtractionLimits(
        max_bytes=64,
        max_pdf_pages=2,
        max_archive_entries=20,
        max_archive_uncompressed_bytes=2_000,
        max_archive_ratio=20,
        processing_timeout_seconds=2,
    )
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"%PDF-" + b"x" * 80)

    with pytest.raises(ResumeExportExtractionError, match="resume_export_too_large"):
        await ResumeBuilderDocumentExtractor(limits).extract(path, "application/pdf")

    path.write_bytes(b"%PDF-1.7\nnot-a-complete-document")
    with pytest.raises(
        ResumeExportExtractionError,
        match="malformed_resume_export_pdf",
    ):
        await ResumeBuilderDocumentExtractor(limits).extract(path, "application/pdf")


def test_all_five_templates_have_distinct_pdf_and_docx_presentations() -> None:
    version = _multi_section_version()
    renderer = DeterministicResumeRenderer()

    pdf_digests = {
        hashlib.sha256(
            renderer.render(
                replace(version, template=template),
                fmt=ResumeFormat.PDF.value,
            ).content
        ).hexdigest()
        for template in ResumeTemplate
    }
    docx_digests = {
        hashlib.sha256(
            renderer.render(
                replace(version, template=template),
                fmt=ResumeFormat.DOCX.value,
            ).content
        ).hexdigest()
        for template in ResumeTemplate
    }

    assert len(pdf_digests) == len(ResumeTemplate)
    assert len(docx_digests) == len(ResumeTemplate)


def test_text_and_json_exports_follow_template_order_and_embed_fidelity_manifest() -> None:
    renderer = DeterministicResumeRenderer()
    version = _multi_section_version()
    standard = renderer.render(version, fmt=ResumeFormat.TEXT.value)
    graduate = renderer.render(
        replace(version, template=ResumeTemplate.GRADUATE),
        fmt=ResumeFormat.TEXT.value,
    )
    structured = renderer.render(version, fmt=ResumeFormat.JSON.value)

    assert standard.content != graduate.content
    assert b'"fidelityManifest"' in structured.content
    assert b'"schemaVersion": "resume-export-json-v3"' in structured.content


def _multi_section_version() -> ResumeVersion:
    sections = tuple(
        ResumeSection(
            id=UUID(f"00000000-0000-4000-8000-{0x730 + index:012x}"),
            title=title,
            kind=kind,
            items=(
                ResumeBullet(
                    id=UUID(f"00000000-0000-4000-8000-{0x740 + index:012x}"),
                    text=f"Confirmed {kind} result.",
                    evidence_ids=(EVIDENCE_ID,),
                    source="career_record",
                ),
            ),
        )
        for index, (title, kind) in enumerate(
            (
                ("Experience", "experience"),
                ("Education", "education"),
                ("Skills", "skills"),
                ("Projects", "projects"),
                ("Credentials", "credentials"),
            )
        )
    )
    return ResumeVersion(
        id=VERSION_ID,
        owner_user_id=OWNER_ID,
        resume_id=RESUME_ID,
        version_number=1,
        parent_version_id=None,
        title="Internal template comparison",
        target_role="Product Lead",
        template=ResumeTemplate.STANDARD_PROFESSIONAL,
        sections=sections,
        plain_text="",
        source_evidence_ids=(EVIDENCE_ID,),
        source_change_set_id=None,
        source_change_set_version_id=None,
        created_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        personal_facts=(
            ResumePersonalFact(
                id=UUID("00000000-0000-4000-8000-000000000750"),
                kind="name",
                value="Taylor Morgan",
                label=None,
                is_primary=True,
            ),
        ),
    )
