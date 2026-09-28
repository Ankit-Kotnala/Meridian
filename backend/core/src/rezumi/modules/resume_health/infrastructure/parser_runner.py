"""Private subprocess entrypoint for isolated document parsing."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from rezumi.modules.resume_health.application.models import DocumentLimits, ExtractionResult
from rezumi.modules.resume_health.domain.errors import UnsafeDocument


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
        from rezumi.modules.resume_health.infrastructure.extractors import (
            extract_local_document,
        )

        extraction = extract_local_document(source_path, str(request["mediaType"]), limits)
        result = {"status": "ok", "extraction": _result_to_dict(extraction)}
        exit_code = 0
    except UnsafeDocument as exc:
        result = {"status": "failed", "safeErrorCode": exc.code}
        exit_code = 1
    except Exception:
        result = {"status": "failed", "safeErrorCode": "document_parser_crashed"}
        exit_code = 1
    try:
        result_path.write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    except (NameError, OSError):
        return 2
    return exit_code


def _limits_from_dict(value: dict[str, Any]) -> DocumentLimits:
    return DocumentLimits(
        max_upload_bytes=int(value["maxUploadBytes"]),
        max_pdf_pages=int(value["maxPdfPages"]),
        max_archive_entries=int(value["maxArchiveEntries"]),
        max_archive_uncompressed_bytes=int(value["maxArchiveUncompressedBytes"]),
        max_archive_ratio=int(value["maxArchiveRatio"]),
        max_extracted_characters=int(value["maxExtractedCharacters"]),
        max_extracted_blocks=int(value["maxExtractedBlocks"]),
        max_serialized_artifact_bytes=int(value["maxSerializedArtifactBytes"]),
        processing_timeout_seconds=float(value["processingTimeoutSeconds"]),
        temp_root=Path(str(value["tempRoot"])),
    )


def _apply_resource_limits(limits: DocumentLimits) -> None:
    if platform.system() == "Windows":
        return
    resource = importlib.import_module("resource")

    cpu_seconds = max(1, round(limits.processing_timeout_seconds) + 1)
    memory_bytes = max(
        512 * 1024 * 1024,
        limits.max_archive_uncompressed_bytes * 4,
    )
    output_bytes = max(
        limits.max_serialized_artifact_bytes * 2,
        4 * 1024 * 1024,
    )
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    # macOS exposes RLIMIT_AS but rejects setting it for this subprocess model.
    # Linux production containers enforce the address-space cap; macOS retains
    # the CPU and output-size caps below for safe local development.
    if platform.system() != "Darwin":
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))


def _result_to_dict(result: ExtractionResult) -> dict[str, Any]:
    return {
        "plainText": result.plain_text,
        "readingOrder": [
            {
                "kind": block.kind,
                "text": block.text,
                "confidenceBasisPoints": block.confidence_basis_points,
                "spans": [
                    {"page": span.page, "start": span.start, "end": span.end}
                    for span in block.spans
                ],
            }
            for block in result.reading_order
        ],
        "pageCount": result.page_count,
        "imageOnly": result.image_only,
        "warnings": list(result.warnings),
        "parserVersion": result.parser_version,
        "layoutSignals": list(result.layout_signals),
    }


if __name__ == "__main__":
    raise SystemExit(main())
