"""Killable, credential-free subprocess adapter for evidence attachments."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

from careeros.foundation.sandbox import sanitized_parser_environment
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentExtractionSummary,
    AttachmentLimits,
    AttachmentMediaType,
    SafeAttachmentError,
    UnsafeAttachment,
)

_RUNNER_MODULE = "careeros.modules.career_record.infrastructure.attachment_parser_runner"
_MAX_RESULT_BYTES = 16_384


class IsolatedAttachmentExtractor:
    """Run parser libraries in a child that can be terminated on timeout."""

    def __init__(self, *, runner_module: str = _RUNNER_MODULE) -> None:
        if not runner_module or any(character.isspace() for character in runner_module):
            raise ValueError("attachment parser runner module is invalid")
        self._runner_module = runner_module

    async def extract(
        self,
        path: Path,
        media_type: AttachmentMediaType,
        limits: AttachmentLimits,
    ) -> AttachmentExtractionSummary:
        source = path.resolve(strict=True)
        temp_root = limits.temp_root.resolve(strict=True)
        if source != temp_root and temp_root not in source.parents:
            raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
        with tempfile.TemporaryDirectory(
            prefix="attachment-parser-",
            dir=temp_root,
        ) as directory:
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
                env=sanitized_parser_environment(workspace),
                close_fds=True,
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
                raise RuntimeError("attachment parser timed out") from exc
            if (
                result_path.is_symlink()
                or not result_path.is_file()
                or result_path.resolve(strict=True).parent != workspace.resolve(strict=True)
                or result_path.stat().st_size > _MAX_RESULT_BYTES
            ):
                raise RuntimeError("attachment parser produced no bounded result")
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("attachment parser result was invalid") from exc
            if not isinstance(result, dict):
                raise RuntimeError("attachment parser result was invalid")
            if process.returncode != 0 or result.get("status") != "ok":
                if (
                    result.get("safeErrorCode")
                    == SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE.value
                ):
                    raise UnsafeAttachment(SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE)
                raise RuntimeError("attachment parser failed")
            return _result_from_dict(result.get("extraction"), limits)


def _limits_to_dict(limits: AttachmentLimits) -> dict[str, object]:
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


def _result_from_dict(
    value: object,
    limits: AttachmentLimits,
) -> AttachmentExtractionSummary:
    if not isinstance(value, dict):
        raise RuntimeError("attachment parser extraction was invalid")
    fields = (
        "pageCount",
        "extractedCharacters",
        "extractedBlocks",
        "archiveEntries",
        "archiveUncompressedBytes",
        "maxArchiveRatio",
    )
    if (
        value.get("formatValid") is not True
        or any(
            not isinstance(value.get(field), int)
            or isinstance(value.get(field), bool)
            or int(value[field]) < 0
            for field in fields
        )
        or int(value["pageCount"]) > limits.max_pdf_pages
        or int(value["extractedCharacters"]) > limits.max_extracted_characters
        or int(value["extractedBlocks"]) > limits.max_extracted_blocks
        or int(value["archiveEntries"]) > limits.max_archive_entries
        or int(value["archiveUncompressedBytes"]) > limits.max_archive_uncompressed_bytes
        or int(value["maxArchiveRatio"]) > limits.max_archive_ratio
        or not isinstance(value.get("parserVersion"), str)
        or not 1 <= len(str(value["parserVersion"])) <= 80
    ):
        raise RuntimeError("attachment parser extraction exceeded its contract")
    return AttachmentExtractionSummary(
        format_valid=True,
        page_count=int(value["pageCount"]),
        extracted_characters=int(value["extractedCharacters"]),
        extracted_blocks=int(value["extractedBlocks"]),
        archive_entries=int(value["archiveEntries"]),
        archive_uncompressed_bytes=int(value["archiveUncompressedBytes"]),
        max_archive_ratio=int(value["maxArchiveRatio"]),
        parser_version=str(value["parserVersion"]),
    )
