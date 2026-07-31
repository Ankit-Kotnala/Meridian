"""Private subprocess entrypoint for hostile evidence-attachment parsing."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from careeros.foundation.sandbox import install_parser_egress_guard
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentExtractionSummary,
    AttachmentLimits,
    AttachmentMediaType,
    UnsafeAttachment,
)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        request_path = Path(sys.argv[1]).resolve(strict=True)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        workspace = request_path.parent.resolve(strict=True)
        result_path = Path(str(request["resultPath"])).resolve()
        if result_path.parent != workspace:
            return 2
        limits = _limits_from_dict(request["limits"])
        _apply_resource_limits(limits)
        install_parser_egress_guard()
        source_path = Path(str(request["sourcePath"])).resolve(strict=True)
        temp_root = limits.temp_root.resolve(strict=True)
        if source_path != temp_root and temp_root not in source_path.parents:
            return 2
        media_type = AttachmentMediaType(str(request["mediaType"]))
        from careeros.modules.career_record.infrastructure.attachment_extractor import (
            extract_local_attachment,
        )

        extraction = extract_local_attachment(source_path, media_type, limits)
        result = {"status": "ok", "extraction": _result_to_dict(extraction)}
        exit_code = 0
    except UnsafeAttachment as exc:
        result = {"status": "failed", "safeErrorCode": exc.code.value}
        exit_code = 1
    except Exception:
        result = {"status": "failed", "safeErrorCode": "attachment_parser_crashed"}
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
    memory_bytes = max(
        512 * 1024 * 1024,
        limits.max_archive_uncompressed_bytes * 4,
    )
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_048_576, 1_048_576))


def _result_to_dict(result: AttachmentExtractionSummary) -> dict[str, object]:
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
