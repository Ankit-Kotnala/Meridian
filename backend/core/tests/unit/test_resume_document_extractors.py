"""Hostile PDF/DOCX admission and local extraction tests."""

import hashlib
import json
import time
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from pypdf import PdfWriter

from rezumi.modules.resume_health.application.models import DocumentLimits
from rezumi.modules.resume_health.domain import ResumeMediaType
from rezumi.modules.resume_health.domain.errors import UnsafeDocument
from rezumi.modules.resume_health.infrastructure.extractors import (
    LocalDocumentExtractor,
    LocalDocumentTextExtractor,
)
from rezumi.modules.resume_health.infrastructure.isolated_extractor import (
    IsolatedDocumentExtractor,
)
from rezumi.modules.resume_health.infrastructure.layout import LocalLayoutAnalyzer

FIXTURES = Path(__file__).resolve().parents[4] / "frontend" / "test-fixtures" / "generated"


def test_committed_fixture_manifest_matches_bounded_fictional_corpus() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

    assert set(manifest) == {
        "adversarial-layout.docx",
        "fictional-resume.docx",
        "fictional-resume.pdf",
        "image-only.pdf",
        "long-resume.docx",
        "two-column.pdf",
    }
    for filename, expected in manifest.items():
        value = (FIXTURES / filename).read_bytes()
        assert len(value) == expected["bytes"]
        assert hashlib.sha256(value).hexdigest() == expected["sha256"]


@pytest.mark.asyncio
async def test_wrong_signature_fails_before_parser(tmp_path: Path) -> None:
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(UnsafeDocument, match="document_signature_mismatch"):
        await LocalDocumentExtractor().extract(path, ResumeMediaType.PDF.value, DocumentLimits())


@pytest.mark.asyncio
async def test_docx_macro_traversal_and_expansion_fail_closed(tmp_path: Path) -> None:
    cases = [
        (
            "macro.docx",
            [
                ("[Content_Types].xml", b"x"),
                ("word/document.xml", b"x"),
                ("word/vbaProject.bin", b"x"),
            ],
            "macro_document_rejected",
        ),
        (
            "traversal.docx",
            [("[Content_Types].xml", b"x"), ("word/document.xml", b"x"), ("../escape", b"x")],
            "archive_path_traversal",
        ),
    ]
    for filename, members, code in cases:
        path = tmp_path / filename
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for name, value in members:
                archive.writestr(name, value)
        with pytest.raises(UnsafeDocument, match=code):
            await LocalDocumentExtractor().extract(
                path, ResumeMediaType.DOCX.value, DocumentLimits()
            )


@pytest.mark.asyncio
async def test_clean_docx_extracts_text_blocks_and_spans(tmp_path: Path) -> None:
    path = tmp_path / "fictional-resume.docx"
    document = Document()
    document.add_heading("Experience", level=1)
    document.add_paragraph(
        "Built a fictional service and improved delivery quality.", style="List Bullet"
    )
    document.add_heading("Education", level=1)
    document.add_paragraph("Fictional University, 2024")
    document.save(path)

    result = await LocalDocumentExtractor().extract(
        path, ResumeMediaType.DOCX.value, DocumentLimits()
    )

    assert "fictional service" in result.plain_text
    assert result.reading_order
    assert all(block.spans and block.spans[0].page == 1 for block in result.reading_order)
    assert not result.image_only


@pytest.mark.asyncio
async def test_table_heavy_docx_is_preserved_and_flagged_for_layout_review(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table-heavy.docx"
    document = Document()
    for index in range(3):
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = f"Fictional role {index}"
        table.cell(0, 1).text = "2024"
    document.save(path)

    result = await LocalDocumentExtractor().extract(
        path,
        ResumeMediaType.DOCX.value,
        DocumentLimits(),
    )

    assert [block.kind for block in result.reading_order] == ["table", "table", "table"]
    assert "table_heavy_layout" in result.warnings

    text_only = await LocalDocumentTextExtractor().extract_text(
        path,
        ResumeMediaType.DOCX.value,
        DocumentLimits(),
    )
    analyzed = await LocalLayoutAnalyzer().analyze(
        path,
        ResumeMediaType.DOCX.value,
        text_only,
        DocumentLimits(),
    )
    assert "table_heavy_layout" not in text_only.warnings
    assert "table_heavy_layout" in analyzed.warnings


@pytest.mark.asyncio
async def test_header_footer_unusual_font_and_bidi_controls_are_handled_safely(
    tmp_path: Path,
) -> None:
    path = tmp_path / "hostile-layout.docx"
    document = Document()
    document.sections[0].header.paragraphs[0].text = "FICTIONAL HEADER"
    document.sections[0].footer.paragraphs[0].text = "FICTIONAL FOOTER"
    paragraph = document.add_paragraph("Experience")
    paragraph.runs[0].font.name = "Papyrus"
    document.add_paragraph("Principal\u202e Engineer | Fictional Labs | 2024")
    document.save(path)

    result = await LocalDocumentExtractor().extract(
        path,
        ResumeMediaType.DOCX.value,
        DocumentLimits(),
    )

    assert "\u202e" not in result.plain_text
    assert "FICTIONAL HEADER" not in result.plain_text
    assert "FICTIONAL FOOTER" not in result.plain_text
    assert {"header_footer_excluded", "bidirectional_controls_removed"} <= set(result.warnings)


@pytest.mark.asyncio
async def test_long_document_fails_at_character_boundary(tmp_path: Path) -> None:
    path = tmp_path / "long.docx"
    document = Document()
    for index in range(60):
        document.add_paragraph(f"Fictional achievement {index} " + "x" * 80)
    document.save(path)

    with pytest.raises(UnsafeDocument, match="extracted_text_limit_exceeded"):
        await LocalDocumentExtractor().extract(
            path,
            ResumeMediaType.DOCX.value,
            DocumentLimits(max_extracted_characters=1_000),
        )


@pytest.mark.asyncio
async def test_committed_clean_pdf_and_image_only_pdf_are_classified() -> None:
    extractor = LocalDocumentExtractor()
    clean = await extractor.extract(
        FIXTURES / "fictional-resume.pdf", ResumeMediaType.PDF.value, DocumentLimits()
    )
    image_only = await extractor.extract(
        FIXTURES / "image-only.pdf", ResumeMediaType.PDF.value, DocumentLimits()
    )

    assert "ALEX RIVERA" in clean.plain_text
    assert clean.reading_order
    assert not clean.image_only
    assert image_only.image_only
    assert image_only.warnings == ("image_only_pdf",)


@pytest.mark.asyncio
async def test_committed_adversarial_layout_corpus_has_expected_safe_signals() -> None:
    extractor = LocalDocumentExtractor()
    two_column = await extractor.extract(
        FIXTURES / "two-column.pdf",
        ResumeMediaType.PDF.value,
        DocumentLimits(),
    )
    adversarial = await extractor.extract(
        FIXTURES / "adversarial-layout.docx",
        ResumeMediaType.DOCX.value,
        DocumentLimits(),
    )

    assert {"multi_column_layout", "reading_order_uncertain"} <= set(two_column.warnings)
    assert {
        "bidirectional_controls_removed",
        "header_footer_excluded",
        "table_heavy_layout",
    } <= set(adversarial.warnings)
    assert "\u202e" not in adversarial.plain_text
    assert "FICTIONAL REPEATED HEADER" not in adversarial.plain_text

    long_resume = await extractor.extract(
        FIXTURES / "long-resume.docx",
        ResumeMediaType.DOCX.value,
        DocumentLimits(),
    )
    assert len(long_resume.reading_order) == 601
    assert len(long_resume.plain_text) < DocumentLimits().max_extracted_characters


@pytest.mark.asyncio
async def test_encrypted_malformed_and_polyglot_pdf_fail_closed(tmp_path: Path) -> None:
    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("test-only-password")
    with encrypted.open("wb") as output:
        writer.write(output)
    malformed = tmp_path / "malformed.pdf"
    malformed.write_bytes(b"%PDF-1.7\ntruncated")
    polyglot = tmp_path / "polyglot.pdf"
    polyglot.write_bytes(
        (FIXTURES / "fictional-resume.pdf").read_bytes() + b"PK\x03\x04embedded-archive"
    )

    for path, code in (
        (encrypted, "encrypted_document"),
        (malformed, "malformed_pdf"),
        (polyglot, "polyglot_document_rejected"),
    ):
        with pytest.raises(UnsafeDocument, match=code):
            await LocalDocumentExtractor().extract(
                path, ResumeMediaType.PDF.value, DocumentLimits()
            )


@pytest.mark.asyncio
async def test_docx_entry_expansion_and_ratio_limits_fail_before_open(tmp_path: Path) -> None:
    path = tmp_path / "bounded.docx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"x" * 100)
        archive.writestr("word/document.xml", b"y" * 100)
        archive.writestr("word/styles.xml", b"z" * 100)

    cases = (
        (DocumentLimits(max_archive_entries=2), "archive_entry_limit_exceeded"),
        (
            DocumentLimits(max_archive_uncompressed_bytes=150),
            "archive_expansion_limit_exceeded",
        ),
        (DocumentLimits(max_archive_ratio=1), "archive_ratio_limit_exceeded"),
    )
    for limits, code in cases:
        with pytest.raises(UnsafeDocument, match=code):
            await LocalDocumentExtractor().extract(path, ResumeMediaType.DOCX.value, limits)


@pytest.mark.asyncio
async def test_extraction_timeout_returns_safe_failure(tmp_path: Path) -> None:
    class SlowExtractor(LocalDocumentExtractor):
        def _extract(self, path: Path, media_type: str, limits: DocumentLimits) -> object:
            del path, media_type, limits
            time.sleep(0.05)
            raise AssertionError("late parser result must be ignored")

    path = tmp_path / "slow.pdf"
    path.write_bytes(b"%PDF-1.7\n%%EOF")
    with pytest.raises(UnsafeDocument, match="document_processing_timeout"):
        await SlowExtractor().extract(
            path,
            ResumeMediaType.PDF.value,
            DocumentLimits(processing_timeout_seconds=0.001),
        )


@pytest.mark.asyncio
async def test_isolated_extractor_returns_validated_child_result(tmp_path: Path) -> None:
    source = tmp_path / "fictional-resume.pdf"
    source.write_bytes((FIXTURES / "fictional-resume.pdf").read_bytes())

    result = await IsolatedDocumentExtractor().extract(
        source,
        ResumeMediaType.PDF.value,
        DocumentLimits(temp_root=tmp_path),
    )

    assert "ALEX RIVERA" in result.plain_text
    assert result.parser_version == ("rezumi-local-parser/1.0.0+rezumi-layout-analyzer/1.0.0")
    assert not list(tmp_path.glob("parser-*"))


@pytest.mark.asyncio
async def test_isolated_extractor_kills_timed_out_child_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fictional-resume.pdf"
    source.write_bytes((FIXTURES / "fictional-resume.pdf").read_bytes())

    with pytest.raises(UnsafeDocument, match="document_processing_timeout"):
        await IsolatedDocumentExtractor().extract(
            source,
            ResumeMediaType.PDF.value,
            DocumentLimits(
                processing_timeout_seconds=0.000_001,
                temp_root=tmp_path,
            ),
        )

    assert not list(tmp_path.glob("parser-*"))
