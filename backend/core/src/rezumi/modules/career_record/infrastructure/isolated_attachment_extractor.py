"""Killable subprocess isolation for hostile evidence-attachment parsers."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentExtractionSummary,
    AttachmentLimits,
    AttachmentMediaType,
    SafeAttachmentError,
    UnsafeAttachment,
)

_RUNNER_MODULE = "rezumi.modules.career_record.infrastructure.attachment_parser_runner"
_MAX_RESULT_BYTES = 64_000
_SAFE_ERROR_CODES = frozenset({item.value for item in SafeAttachmentError})


class IsolatedAttachmentExtractor:
    """Execute attachment parser libraries in a process that can be killed."""

    def __init__(self, *, runner_module: str = _RUNNER_MODULE) -> None:
        if not runner_module or any(character.isspace() for character in runner_module):
            raise ValueError("attachment parser runner module is invalid")
        self._runner_module = runner_module

    async def extract(
        self, path: Path, media_type: AttachmentMediaType, limits: AttachmentLimits
    ) -> AttachmentExtractionSummary:
        source = path.resolve(strict=True)
        temp_root = limits.temp_root.resolve(strict=True)
        if source != temp_root and temp_root not in source.parents:
            raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
        with tempfile.TemporaryDirectory(prefix="attachment-parser-", dir=temp_root) as directory:
            workspace = Path(directory)
            request_path = workspace / "request.json"
            result_path = workspace / "result.json"
            request_path.write_text(
                json.dumps(
                    {
                        "sourcePath": str(source),
                        "mediaType": media_type.value,
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
                raise TimeoutError("attachment extraction timed out") from exc
            if (
                result_path.is_symlink()
                or not result_path.is_file()
                or result_path.resolve(strict=True).parent != workspace.resolve(strict=True)
            ):
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
            if result_path.stat().st_size > _MAX_RESULT_BYTES:
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE) from exc
            if not isinstance(result, dict):
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
            if process.returncode != 0 or result.get("status") != "ok":
                code = result.get("safeErrorCode")
                if isinstance(code, str) and code in _SAFE_ERROR_CODES:
                    raise UnsafeAttachment(SafeAttachmentError(code))
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
            try:
                return _summary_from_dict(result["extraction"])
            except (KeyError, TypeError, ValueError) as exc:
                raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE) from exc


def _limits_to_dict(limits: AttachmentLimits) -> dict[str, Any]:
    return {
        "maxUploadBytes": limits.max_upload_bytes,
        "maxPdfPages": limits.max_pdf_pages,
        "maxArchiveEntries": limits.max_archive_entries,
        "maxArchiveUncompressedBytes": limits.max_archive_uncompressed_bytes,
        "maxArchiveRatio": limits.max_archive_ratio,
        "maxExtractedCharacters": limits.max_extracted_characters,
        "maxExtractedBlocks": limits.max_extracted_blocks,
        "processingTimeoutSeconds": limits.processing_timeout_seconds,
        "tempRoot": str(limits.temp_root),
    }


def _summary_from_dict(value: object) -> AttachmentExtractionSummary:
    if not isinstance(value, dict):
        raise ValueError("attachment extraction must be an object")
    return AttachmentExtractionSummary(
        format_valid=bool(value["formatValid"]),
        page_count=int(value["pageCount"]),
        extracted_characters=int(value["extractedCharacters"]),
        extracted_blocks=int(value["extractedBlocks"]),
        archive_entries=int(value["archiveEntries"]),
        archive_uncompressed_bytes=int(value["archiveUncompressedBytes"]),
        max_archive_ratio=int(value["maxArchiveRatio"]),
        parser_version=str(value["parserVersion"]),
    )
