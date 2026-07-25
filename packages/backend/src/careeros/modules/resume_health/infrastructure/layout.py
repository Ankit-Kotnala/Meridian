"""Deterministic local layout-analysis adapter."""

from __future__ import annotations

from dataclasses import replace
from itertools import pairwise
from pathlib import Path

from careeros.modules.resume_health.application.models import (
    DocumentLimits,
    ExtractionResult,
)

LAYOUT_ANALYZER_VERSION = "careeros-layout-analyzer/1.0.0"


class LocalLayoutAnalyzer:
    """Flag layouts the local text extractor cannot represent reliably."""

    async def analyze(
        self,
        path: Path,
        media_type: str,
        extraction: ExtractionResult,
        limits: DocumentLimits,
    ) -> ExtractionResult:
        del path, media_type, limits
        return analyze_local_layout(extraction)


def analyze_local_layout(extraction: ExtractionResult) -> ExtractionResult:
    warnings = list(extraction.warnings)
    signal_warnings = {
        "bidirectional_controls_present": "bidirectional_controls_removed",
        "header_footer_present": "header_footer_excluded",
        "multi_column_candidate": "multi_column_layout",
    }
    warnings.extend(
        signal_warnings[signal] for signal in extraction.layout_signals if signal in signal_warnings
    )
    if "multi_column_candidate" in extraction.layout_signals:
        warnings.append("reading_order_uncertain")
    blocks = extraction.reading_order
    table_count = sum(block.kind == "table" for block in blocks)
    if table_count >= 2 and table_count * 3 >= len(blocks):
        warnings.append("table_heavy_layout")
    positions = [(span.page, span.start, span.end) for block in blocks for span in block.spans[:1]]
    if any(
        current[:2] < previous[:2] or current[1] < previous[2]
        for previous, current in pairwise(positions)
    ):
        warnings.append("reading_order_uncertain")
    return replace(
        extraction,
        warnings=tuple(dict.fromkeys(warnings)),
        parser_version=f"{extraction.parser_version}+{LAYOUT_ANALYZER_VERSION}",
    )
