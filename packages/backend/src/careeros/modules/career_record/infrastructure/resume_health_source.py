"""Explicit Resume Health application query used by Career Record."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from careeros.modules.resume_health.application import (
    CanonicalSnapshotView,
    DocumentStatus,
    DocumentView,
    OwnerScope,
    ResumeHealthError,
)

from ..application.models import ResumeSourceLocator, ValidatedResumeSource
from ..domain import exact_claim_sha256


class ResumeHealthSourceReader(Protocol):
    """The two owner-scoped Resume Health reads required for provenance."""

    async def get_document(
        self,
        scope: OwnerScope,
        document_id: UUID,
    ) -> DocumentView: ...

    async def get_canonical_resume(
        self,
        scope: OwnerScope,
        document_id: UUID,
    ) -> CanonicalSnapshotView: ...


class ResumeHealthSourceQuery:
    """Validate exact owned source spans without reaching into another store."""

    def __init__(self, reader: ResumeHealthSourceReader) -> None:
        self._reader = reader

    async def resolve_exact_span(
        self,
        owner_user_id: UUID,
        locator: ResumeSourceLocator,
        expected_claim: str | None = None,
    ) -> ValidatedResumeSource | None:
        scope = OwnerScope(user_id=owner_user_id)
        try:
            snapshot = await self._reader.get_canonical_resume(scope, locator.document_id)
        except ResumeHealthError:
            return None
        if snapshot.id != locator.snapshot_id:
            return None

        reviewed_block = next(
            (
                candidate
                for section in snapshot.resume.sections
                for candidate in section.blocks
                if candidate.id == locator.block_id
            ),
            None,
        )
        source_block = next(
            (
                candidate
                for section in snapshot.original_resume.sections
                for candidate in section.blocks
                if candidate.id == locator.block_id
            ),
            None,
        )
        if (
            snapshot.document_id != locator.document_id
            or reviewed_block is None
            or source_block is None
            or reviewed_block.text != source_block.text
            or (
                expected_claim is not None
                and exact_claim_sha256(expected_claim) != exact_claim_sha256(source_block.text)
            )
            or not any(
                span.page == locator.page
                and span.start == locator.start_offset
                and span.end == locator.end_offset
                for span in source_block.spans
            )
        ):
            return None

        excerpt = source_block.text.strip()[:1_000]
        if not excerpt:
            return None
        return ValidatedResumeSource(
            document_id=locator.document_id,
            snapshot_id=snapshot.id,
            snapshot_revision=snapshot.revision,
            schema_version=snapshot.resume.schema_version,
            parser_version=snapshot.parser_version,
            block_id=source_block.id,
            page=locator.page,
            start_offset=locator.start_offset,
            end_offset=locator.end_offset,
            source_sha256=exact_claim_sha256(source_block.text),
            review_excerpt=excerpt,
        )

    async def is_available(
        self,
        owner_user_id: UUID,
        source: ValidatedResumeSource,
    ) -> bool:
        scope = OwnerScope(user_id=owner_user_id)
        try:
            document = await self._reader.get_document(
                scope,
                source.document_id,
            )
            snapshot = await self._reader.get_canonical_resume(scope, source.document_id)
        except ResumeHealthError:
            return False
        if (
            document.status is not DocumentStatus.READY
            or snapshot.id != source.snapshot_id
            or snapshot.revision != source.snapshot_revision
            or snapshot.resume.schema_version != source.schema_version
            or snapshot.parser_version != source.parser_version
        ):
            return False
        reviewed_block = next(
            (
                candidate
                for section in snapshot.resume.sections
                for candidate in section.blocks
                if candidate.id == source.block_id
            ),
            None,
        )
        original_block = next(
            (
                candidate
                for section in snapshot.original_resume.sections
                for candidate in section.blocks
                if candidate.id == source.block_id
            ),
            None,
        )
        return (
            reviewed_block is not None
            and original_block is not None
            and reviewed_block.text == original_block.text
            and exact_claim_sha256(original_block.text) == source.source_sha256
            and any(
                span.page == source.page
                and span.start == source.start_offset
                and span.end == source.end_offset
                for span in original_block.spans
            )
        )
