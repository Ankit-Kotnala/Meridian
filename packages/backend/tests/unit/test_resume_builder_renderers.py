"""Renderer and round-trip extraction tests for Phase 7 exports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from careeros.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeFormat,
    ResumeSection,
    ResumeTemplate,
    ResumeVersion,
)
from careeros.modules.resume_builder.infrastructure.renderers import DeterministicResumeRenderer
from careeros.modules.resume_health.application import DocumentLimits
from careeros.modules.resume_health.infrastructure.extractors import LocalDocumentExtractor

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
        title="Searchable Product Resume",
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
                        text="Confirmed customer discovery and product experiments.",
                        evidence_ids=(EVIDENCE_ID,),
                        source="career_record",
                    ),
                ),
            ),
        ),
        plain_text="Searchable Product Resume\nSenior Product Manager",
        source_evidence_ids=(EVIDENCE_ID,),
        source_change_set_id=None,
        source_change_set_version_id=None,
        created_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
    )
    rendered = DeterministicResumeRenderer().render(version, fmt=fmt.value)
    path = tmp_path / f"resume{suffix}"
    path.write_bytes(rendered.content)
    extracted = await LocalDocumentExtractor().extract(
        path,
        media_type,
        DocumentLimits(
            max_upload_bytes=2_000_000,
            max_pdf_pages=3,
            max_archive_entries=200,
            max_archive_uncompressed_bytes=10_000_000,
            max_archive_ratio=100,
            processing_timeout_seconds=5,
        ),
    )
    for line in rendered.expected_lines:
        assert line in extracted.plain_text
