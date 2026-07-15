"""Bounded local PDF/DOCX validation and deterministic text extraction."""

import asyncio
import re
import stat
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5
from zipfile import BadZipFile, ZipFile

from docx import Document
from pypdf import PdfReader

from careeros.modules.resume_health.application.models import (
    DocumentLimits,
    ExtractedBlock,
    ExtractionResult,
    SourceSpanView,
)
from careeros.modules.resume_health.domain import ResumeMediaType
from careeros.modules.resume_health.domain.errors import UnsafeDocument

PARSER_VERSION = "careeros-local-parser/1.0.0"
_BLOCK_NAMESPACE = UUID("5f80ce6a-096a-44e9-b4d1-335f2da30c32")
_BULLET_PREFIX = re.compile(r"^(?:[-*•▪◦]|\d+[.)])\s+")


class LocalDocumentExtractor:
    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._extract, path, media_type, limits),
                limits.processing_timeout_seconds,
            )
        except TimeoutError as exc:
            raise UnsafeDocument("document_processing_timeout") from exc

    def _extract(self, path: Path, media_type: str, limits: DocumentLimits) -> ExtractionResult:
        if path.stat().st_size > limits.max_upload_bytes:
            raise UnsafeDocument("upload_too_large")
        if media_type == ResumeMediaType.PDF.value:
            return _extract_pdf(path, limits)
        if media_type == ResumeMediaType.DOCX.value:
            return _extract_docx(path, limits)
        raise UnsafeDocument("unsupported_document_type")


def _extract_pdf(path: Path, limits: DocumentLimits) -> ExtractionResult:
    raw = path.read_bytes()
    raw_head = raw[:1024]
    if not raw_head.startswith(b"%PDF-"):
        raise UnsafeDocument("document_signature_mismatch")
    if b"PK\x03\x04" in raw:
        raise UnsafeDocument("polyglot_document_rejected")
    with path.open("rb") as source:
        source.seek(max(0, path.stat().st_size - 2048))
        if b"%%EOF" not in source.read():
            raise UnsafeDocument("malformed_pdf")
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            raise UnsafeDocument("encrypted_document")
        if not 1 <= len(reader.pages) <= limits.max_pdf_pages:
            raise UnsafeDocument("pdf_page_limit_exceeded")
        page_texts = [(page.extract_text() or "").replace("\x00", "") for page in reader.pages]
    except UnsafeDocument:
        raise
    except Exception as exc:
        raise UnsafeDocument("malformed_pdf") from exc
    plain_text = "\n\f\n".join(page_texts).strip()
    if len(plain_text) > limits.max_extracted_characters:
        raise UnsafeDocument("extracted_text_limit_exceeded")
    blocks = _blocks_from_pages(page_texts, limits.max_extracted_blocks)
    image_only = len(plain_text.strip()) < 40
    warnings = ("image_only_pdf",) if image_only else ()
    return ExtractionResult(
        plain_text=plain_text,
        reading_order=blocks,
        page_count=len(page_texts),
        image_only=image_only,
        warnings=warnings,
        parser_version=PARSER_VERSION,
    )


def _extract_docx(path: Path, limits: DocumentLimits) -> ExtractionResult:
    raw = path.read_bytes()
    if not raw.startswith(b"PK\x03\x04"):
        raise UnsafeDocument("document_signature_mismatch")
    if b"%PDF-" in raw:
        raise UnsafeDocument("polyglot_document_rejected")
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_archive_entries:
                raise UnsafeDocument("archive_entry_limit_exceeded")
            total_uncompressed = 0
            total_compressed = 0
            names: set[str] = set()
            for info in infos:
                normalized = PurePosixPath(info.filename.replace("\\", "/"))
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise UnsafeDocument("archive_path_traversal")
                mode = info.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    raise UnsafeDocument("archive_symlink_rejected")
                if info.flag_bits & 0x1:
                    raise UnsafeDocument("encrypted_document")
                total_uncompressed += info.file_size
                total_compressed += max(1, info.compress_size)
                names.add(info.filename.casefold())
            if total_uncompressed > limits.max_archive_uncompressed_bytes:
                raise UnsafeDocument("archive_expansion_limit_exceeded")
            if total_uncompressed > total_compressed * limits.max_archive_ratio:
                raise UnsafeDocument("archive_ratio_limit_exceeded")
            if "word/vbaproject.bin" in names or any("macroenabled" in name for name in names):
                raise UnsafeDocument("macro_document_rejected")
            if "[content_types].xml" not in names or "word/document.xml" not in names:
                raise UnsafeDocument("invalid_docx_package")
            if archive.testzip() is not None:
                raise UnsafeDocument("malformed_docx")
    except UnsafeDocument:
        raise
    except (BadZipFile, OSError) as exc:
        raise UnsafeDocument("malformed_docx") from exc

    try:
        document = Document(str(path))
        paragraphs = [
            paragraph.text.replace("\x00", "").strip() for paragraph in document.paragraphs
        ]
        for table in document.tables:
            for row in table.rows:
                value = " | ".join(cell.text.replace("\x00", "").strip() for cell in row.cells)
                if value.strip(" |"):
                    paragraphs.append(value)
    except Exception as exc:
        raise UnsafeDocument("malformed_docx") from exc
    paragraphs = [value for value in paragraphs if value]
    plain_text = "\n".join(paragraphs)
    if len(plain_text) > limits.max_extracted_characters:
        raise UnsafeDocument("extracted_text_limit_exceeded")
    blocks = _blocks_from_pages([plain_text], limits.max_extracted_blocks)
    return ExtractionResult(
        plain_text=plain_text,
        reading_order=blocks,
        page_count=1,
        image_only=len(plain_text.strip()) < 40,
        warnings=("limited_extractable_text",) if len(plain_text.strip()) < 40 else (),
        parser_version=PARSER_VERSION,
    )


def _blocks_from_pages(page_texts: Iterable[str], max_blocks: int) -> tuple[ExtractedBlock, ...]:
    blocks: list[ExtractedBlock] = []
    global_offset = 0
    for page_number, page_text in enumerate(page_texts, start=1):
        cursor = 0
        for raw_line in page_text.splitlines():
            text = raw_line.strip()
            if not text:
                cursor += len(raw_line) + 1
                continue
            relative = page_text.find(text, cursor)
            relative = cursor if relative < 0 else relative
            cursor = relative + len(text)
            kind = "bullet" if _BULLET_PREFIX.match(text) else _guess_block_kind(text)
            if len(blocks) >= max_blocks:
                raise UnsafeDocument("extracted_block_limit_exceeded")
            blocks.append(
                ExtractedBlock(
                    kind=kind,
                    text=text,
                    confidence_basis_points=9_000,
                    spans=(
                        SourceSpanView(
                            page=page_number,
                            start=global_offset + relative,
                            end=global_offset + relative + len(text),
                        ),
                    ),
                )
            )
        global_offset += len(page_text) + 3
    return tuple(blocks)


def _guess_block_kind(text: str) -> str:
    if len(text) <= 64 and (text.isupper() or text.endswith(":")):
        return "heading"
    return "paragraph"


def stable_block_id(document_id: UUID, block: ExtractedBlock, index: int) -> UUID:
    span = block.spans[0] if block.spans else None
    material = f"{document_id}:{index}:{span.page if span else 0}:{span.start if span else 0}"
    return uuid5(_BLOCK_NAMESPACE, material)
