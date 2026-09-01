"""Private subprocess entrypoint for isolated evidence-attachment parsing."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentExtractionSummary,
    AttachmentLimits,
    UnsafeAttachment,
)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        request_path = Path(sys.argv[1]).resolve(strict=True)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result_path = Path(str(request["resultPath"])).resolve()
        workspace = request_path.parent
        if result_path.parent != workspace:
            return 2
        limits = _limits_from_dict(request["limits"])
        _apply_resource_limits(limits)
        source_path = Path(str(request["sourcePath"])).resolve(strict=True)
        temp_root = limits.temp_root.resolve(strict=True)
        if source_path != temp_root and temp_root not in source_path.parents:
            return 2
        from rezumi.modules.career_record.infrastructure.attachment_extractor import (
            extract_attachment_document,
        )

        extraction = extract_attachment_document(
            source_path,
            str(request["mediaType"]),
            limits,
        )
        result = {"status": "ok", "extraction": _summary_to_dict(extraction)}
        exit_code = 0
    except UnsafeAttachment as exc:
        result = {"status": "failed", "safeErrorCode": exc.code.value}
        exit_code = 1
    except Exception:
        result = {"status": "failed", "safeErrorCode": "attachment_invalid_document_structure"}
        exit_code = 1
    try:
        result_path.write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    except (NameError, OSError):
        return 2
    return exit_code


def _limits_from_dict(value: dict[str, Any]) -> AttachmentLimits:
    return AttachmentLimits(
        max_upload_bytes=int(value["maxUploadBytes"]),
        max_pdf_pages=int(value["maxPdfPages"]),
        max_archive_entries=int(value["maxArchiveEntries"]),
        max_archive_uncompressed_bytes=int(value["maxArchiveUncompressedBytes"]),
        max_archive_ratio=int(value["maxArchiveRatio"]),
        max_extracted_characters=int(value["maxExtractedCharacters"]),
        max_extracted_blocks=int(value["maxExtractedBlocks"]),
        processing_timeout_seconds=float(value["processingTimeoutSeconds"]),
        temp_root=Path(str(value["tempRoot"])),
    )


def _apply_resource_limits(limits: AttachmentLimits) -> None:
    if platform.system() == "Windows":
        return
    resource = importlib.import_module("resource")
    cpu_seconds = max(1, round(limits.processing_timeout_seconds) + 1)
    memory_bytes = max(256 * 1024 * 1024, limits.max_archive_uncompressed_bytes * 4)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))


def _summary_to_dict(result: AttachmentExtractionSummary) -> dict[str, Any]:
    return {
        "formatValid": result.format_valid,
        "pageCount": result.page_count,
        "extractedCharacters": result.extracted_characters,
        "extractedBlocks": result.extracted_blocks,
        "archiveEntries": result.archive_entries,
        "archiveUncompressedBytes": result.archive_uncompressed_bytes,
        "maxArchiveRatio": result.max_archive_ratio,
        "parserVersion": result.parser_version,
    }


if __name__ == "__main__":
    raise SystemExit(main())
