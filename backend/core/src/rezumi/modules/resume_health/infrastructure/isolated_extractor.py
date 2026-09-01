"""Killable subprocess isolation for hostile PDF and DOCX parsers."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from rezumi.modules.resume_health.application.models import (
    DocumentLimits,
    ExtractedBlock,
    ExtractionResult,
    SourceSpanView,
)
from rezumi.modules.resume_health.domain.errors import UnsafeDocument

_RUNNER_MODULE = "rezumi.modules.resume_health.infrastructure.parser_runner"
_SAFE_PARSER_ERROR_CODES = frozenset(
    {
        "archive_entry_limit_exceeded",
        "archive_expansion_limit_exceeded",
        "archive_path_traversal",
        "archive_ratio_limit_exceeded",
        "archive_symlink_rejected",
        "active_content_rejected",
        "document_parser_crashed",
        "document_signature_mismatch",
        "embedded_object_rejected",
        "encrypted_document",
        "extracted_block_limit_exceeded",
        "extracted_text_limit_exceeded",
        "invalid_docx_package",
        "macro_document_rejected",
        "malformed_docx",
        "malformed_pdf",
        "pdf_page_limit_exceeded",
        "polyglot_document_rejected",
        "unsupported_document_type",
        "upload_too_large",
    }
)
_BLOCK_KINDS = frozenset({"bullet", "heading", "paragraph", "table"})


class IsolatedDocumentExtractor:
    """Execute parser libraries in a process that can be forcefully terminated."""

    def __init__(self, *, runner_module: str = _RUNNER_MODULE) -> None:
        if not runner_module or any(character.isspace() for character in runner_module):
            raise ValueError("parser runner module is invalid")
        self._runner_module = runner_module

    async def extract(
        self, path: Path, media_type: str, limits: DocumentLimits
    ) -> ExtractionResult:
        source = path.resolve(strict=True)
        temp_root = limits.temp_root.resolve(strict=True)
        if source != temp_root and temp_root not in source.parents:
            raise UnsafeDocument("unsafe_parser_source_path")
        with tempfile.TemporaryDirectory(prefix="parser-", dir=temp_root) as directory:
            workspace = Path(directory)
            request_path = workspace / "request.json"
            result_path = workspace / "result.json"
            request_path.write_text(
                json.dumps(
                    {
                        "sourcePath": str(source),
                        "mediaType": media_type,
                        "limits": _limits_to_dict(limits),
                        "resultPath": str(result_path),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                self._runner_module,
                str(request_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=str(workspace),
            )
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=limits.processing_timeout_seconds,
                )
            except TimeoutError as exc:
                if process.returncode is None:
                    with suppress(ProcessLookupError):
                        process.kill()
                await process.wait()
                raise UnsafeDocument("document_processing_timeout") from exc
            if (
                result_path.is_symlink()
                or not result_path.is_file()
                or result_path.resolve(strict=True).parent != workspace.resolve(strict=True)
            ):
                raise UnsafeDocument("document_parser_crashed")
            if result_path.stat().st_size > limits.max_serialized_artifact_bytes:
                raise UnsafeDocument("document_parser_output_limit_exceeded")
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise UnsafeDocument("document_parser_invalid_output") from exc
            if not isinstance(result, dict):
                raise UnsafeDocument("document_parser_invalid_output")
            if process.returncode != 0 or result.get("status") != "ok":
                code = result.get("safeErrorCode")
                allowed = (
                    code if isinstance(code, str) and code in _SAFE_PARSER_ERROR_CODES else None
                )
                raise UnsafeDocument(allowed or "document_parser_failed")
            try:
                return _result_from_dict(result["extraction"], limits)
            except (KeyError, TypeError, ValueError) as exc:
                raise UnsafeDocument("document_parser_invalid_output") from exc


def _limits_to_dict(limits: DocumentLimits) -> dict[str, Any]:
    return {
        "maxUploadBytes": limits.max_upload_bytes,
        "maxPdfPages": limits.max_pdf_pages,
        "maxArchiveEntries": limits.max_archive_entries,
        "maxArchiveUncompressedBytes": limits.max_archive_uncompressed_bytes,
        "maxArchiveRatio": limits.max_archive_ratio,
        "maxExtractedCharacters": limits.max_extracted_characters,
        "maxExtractedBlocks": limits.max_extracted_blocks,
        "maxSerializedArtifactBytes": limits.max_serialized_artifact_bytes,
        "processingTimeoutSeconds": limits.processing_timeout_seconds,
        "tempRoot": str(limits.temp_root),
    }


def _result_from_dict(value: dict[str, Any], limits: DocumentLimits) -> ExtractionResult:
    if not isinstance(value, dict):
        raise ValueError("parser extraction must be an object")
    plain_text = value["plainText"]
    reading_order = value["readingOrder"]
    warnings = value["warnings"]
    layout_signals = value.get("layoutSignals", [])
    parser_version = value["parserVersion"]
    page_count = value["pageCount"]
    if (
        not isinstance(plain_text, str)
        or len(plain_text) > limits.max_extracted_characters
        or not isinstance(reading_order, list)
        or len(reading_order) > limits.max_extracted_blocks
        or not isinstance(page_count, int)
        or isinstance(page_count, bool)
        or not 1 <= page_count <= limits.max_pdf_pages
        or not isinstance(value["imageOnly"], bool)
        or not _bounded_strings(warnings, 160)
        or not _bounded_strings(layout_signals, 80)
        or not isinstance(parser_version, str)
        or not 1 <= len(parser_version) <= 80
    ):
        raise ValueError("parser extraction is outside its bounded contract")
    return ExtractionResult(
        plain_text=plain_text,
        reading_order=tuple(_block_from_dict(block, page_count) for block in reading_order),
        page_count=page_count,
        image_only=value["imageOnly"],
        warnings=tuple(warnings),
        parser_version=parser_version,
        layout_signals=tuple(layout_signals),
    )


def _block_from_dict(value: object, page_count: int) -> ExtractedBlock:
    if not isinstance(value, dict):
        raise ValueError("parser block must be an object")
    kind = value["kind"]
    text = value["text"]
    confidence = value["confidenceBasisPoints"]
    spans = value["spans"]
    if (
        kind not in _BLOCK_KINDS
        or not isinstance(text, str)
        or not text
        or len(text) > 10_000
        or "\x00" in text
        or not isinstance(confidence, int)
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 10_000
        or not isinstance(spans, list)
        or not spans
    ):
        raise ValueError("parser block is invalid")
    return ExtractedBlock(
        kind=kind,
        text=text,
        confidence_basis_points=confidence,
        spans=tuple(_span_from_dict(span, page_count) for span in spans),
    )


def _span_from_dict(value: object, page_count: int) -> SourceSpanView:
    if not isinstance(value, dict):
        raise ValueError("parser span must be an object")
    page = value["page"]
    start = value["start"]
    end = value["end"]
    if (
        not isinstance(page, int)
        or isinstance(page, bool)
        or not 1 <= page <= page_count
        or not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
    ):
        raise ValueError("parser span is invalid")
    return SourceSpanView(page=page, start=start, end=end)


def _bounded_strings(value: object, maximum: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= 100
        and all(
            isinstance(item, str) and 1 <= len(item) <= maximum and "\x00" not in item
            for item in value
        )
    )
