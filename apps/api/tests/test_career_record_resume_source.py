"""Application-boundary tests for Career Record resume provenance."""

from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

import pytest
from careeros.modules.career_record.application.models import ResumeSourceLocator
from careeros.modules.career_record.domain.errors import (
    CareerRecordError,
    CareerRecordNotFound,
    CareerRecordUnavailable,
    CareerRecordVersionConflict,
)
from careeros.modules.resume_health.application import CanonicalSnapshotView, ResumeHealthService
from careeros.modules.resume_health.application.models import DocumentView
from careeros.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    DocumentStatus,
    MalwareStatus,
    ResumeMediaType,
    SectionKind,
    SourceSpan,
)
from careeros.modules.resume_health.domain.errors import ResumeResourceNotFound

from careeros_api.career_record_resume_source import ResumeHealthSourceQuery
from careeros_api.problems import _career_record_problem_details


def _snapshot(document_id: UUID, snapshot_id: UUID, block: CanonicalBlock) -> CanonicalSnapshotView:
    resume = CanonicalResume(
        schema_version="canonical-resume/1.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.EXPERIENCE,
                title="Experience",
                confidence_basis_points=9_500,
                blocks=(block,),
            ),
        ),
        warnings=(),
    )
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    return CanonicalSnapshotView(
        id=snapshot_id,
        document_id=document_id,
        revision=2,
        resume=resume,
        original_resume=resume,
        parser_version="local/1",
        corrected_by_user=True,
        created_at=now,
        based_on_snapshot_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_exact_owned_span_is_copied_as_bounded_immutable_provenance() -> None:
    service = create_autospec(ResumeHealthService, instance=True)
    owner_id, document_id, snapshot_id, block_id = (uuid4() for _ in range(4))
    block = CanonicalBlock(
        id=block_id,
        kind=BlockKind.BULLET,
        text="Reduced fictional processing time after a measured workflow change.",
        confidence_basis_points=9_000,
        spans=(SourceSpan(page=1, start=42, end=108),),
    )
    service.get_canonical_resume.return_value = _snapshot(document_id, snapshot_id, block)
    query = ResumeHealthSourceQuery(service)

    result = await query.resolve_exact_span(
        owner_id,
        ResumeSourceLocator(
            document_id=document_id,
            snapshot_id=snapshot_id,
            block_id=block_id,
            page=1,
            start_offset=42,
            end_offset=108,
        ),
    )

    assert result is not None
    assert result.review_excerpt == block.text
    assert len(result.source_sha256) == 32
    service.get_canonical_resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_mismatched_span_or_deleted_source_is_unavailable() -> None:
    service = create_autospec(ResumeHealthService, instance=True)
    owner_id, document_id, snapshot_id, block_id = (uuid4() for _ in range(4))
    block = CanonicalBlock(
        id=block_id,
        kind=BlockKind.BULLET,
        text="Fictional source text",
        confidence_basis_points=9_000,
        spans=(SourceSpan(page=1, start=0, end=22),),
    )
    service.get_canonical_resume.return_value = _snapshot(document_id, snapshot_id, block)
    service.get_document.side_effect = ResumeResourceNotFound
    query = ResumeHealthSourceQuery(service)
    locator = ResumeSourceLocator(
        document_id=document_id,
        snapshot_id=snapshot_id,
        block_id=block_id,
        page=1,
        start_offset=1,
        end_offset=22,
    )

    assert await query.resolve_exact_span(owner_id, locator) is None

    valid = await ResumeHealthSourceQuery(
        _available_service(document_id, snapshot_id, block)
    ).resolve_exact_span(
        owner_id,
        ResumeSourceLocator(
            document_id=document_id,
            snapshot_id=snapshot_id,
            block_id=block_id,
            page=1,
            start_offset=0,
            end_offset=22,
        ),
    )
    assert valid is not None
    assert await query.is_available(owner_id, valid) is False


def _available_service(
    document_id: UUID, snapshot_id: UUID, block: CanonicalBlock
) -> ResumeHealthService:
    service = create_autospec(ResumeHealthService, instance=True)
    service.get_canonical_resume.return_value = _snapshot(document_id, snapshot_id, block)
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    service.get_document.return_value = DocumentView(
        id=document_id,
        display_filename="fictional.pdf",
        media_type=ResumeMediaType.PDF,
        size_bytes=1_024,
        status=DocumentStatus.READY,
        malware_status=MalwareStatus.CLEAN,
        page_count=1,
        safe_error_code=None,
        retention_expires_at=None,
        version=1,
        created_at=now,
        updated_at=now,
        current_snapshot_id=snapshot_id,
        latest_analysis_id=None,
    )
    return service


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (CareerRecordNotFound(), (404, "career_record_not_found")),
        (CareerRecordVersionConflict(), (409, "career_record_version_conflict")),
        (CareerRecordUnavailable(), (503, "career_record_unavailable")),
    ],
)
def test_career_record_problem_mapping_is_stable_and_redacted(
    error: CareerRecordError, expected: tuple[int, str]
) -> None:
    status_code, code, _title, detail = _career_record_problem_details(error)

    assert (status_code, code) == expected
    assert "secret" not in detail.casefold()
