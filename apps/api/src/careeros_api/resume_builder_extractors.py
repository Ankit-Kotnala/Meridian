"""API composition adapter for Phase 7 export round-trip extraction."""

from __future__ import annotations

from pathlib import Path

from careeros.modules.resume_builder.application import ExtractedDocumentText
from careeros.modules.resume_builder.application.ports import ResumeDocumentExtractor
from careeros.modules.resume_health.application import DocumentLimits
from careeros.modules.resume_health.infrastructure.extractors import LocalDocumentExtractor


class ResumeBuilderDocumentExtractor(ResumeDocumentExtractor):
    """Reuse the bounded local PDF/DOCX extractor through a Phase 7 port."""

    def __init__(self, limits: DocumentLimits) -> None:
        self._limits = limits
        self._extractor = LocalDocumentExtractor()

    async def extract(self, path: Path, media_type: str) -> ExtractedDocumentText:
        result = await self._extractor.extract(path, media_type, self._limits)
        return ExtractedDocumentText(
            plain_text=result.plain_text,
            reading_order=tuple(block.text for block in result.reading_order),
            parser_version=result.parser_version,
            warnings=result.warnings,
        )
