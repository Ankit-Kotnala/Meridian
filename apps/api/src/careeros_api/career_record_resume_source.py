"""Explicit Resume Health application query used by the Career Record context."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from careeros.modules.career_record.application.models import (
    ResumeSourceLocator,
    ValidatedResumeSource,
)
from careeros.modules.resume_health.application import ResumeHealthService
from careeros.modules.resume_health.domain import DocumentStatus, OwnerScope
from careeros.modules.resume_health.domain.errors import ResumeHealthError


class ResumeHealthSourceQuery:
    """Validate exact owned source spans without reaching into Resume Health storage."""

    def __init__(self, service: ResumeHealthService) -> None:
        self._service = service

    async def resolve_exact_span(
        self, owner_user_id: UUID, locator: ResumeSourceLocator
    ) -> ValidatedResumeSource | None:
        scope = OwnerScope(user_id=owner_user_id)
        try:
            snapshot = await self._service.get_canonical_resume(scope, locator.document_id)
        except ResumeHealthError:
            return None
        if snapshot.id != locator.snapshot_id:
            return None

        block = next(
            (
                candidate
                for section in snapshot.resume.sections
                for candidate in section.blocks
                if candidate.id == locator.block_id
            ),
            None,
        )
        if block is None or not any(
            span.page == locator.page
            and span.start == locator.start_offset
            and span.end == locator.end_offset
            for span in block.spans
        ):
            return None

        excerpt = block.text.strip()[:1_000]
        if not excerpt:
            return None
        return ValidatedResumeSource(
            document_id=locator.document_id,
            snapshot_id=snapshot.id,
            snapshot_revision=snapshot.revision,
            schema_version=snapshot.resume.schema_version,
            parser_version=snapshot.parser_version,
            block_id=block.id,
            page=locator.page,
            start_offset=locator.start_offset,
            end_offset=locator.end_offset,
            source_sha256=sha256(block.text.encode("utf-8")).digest(),
            review_excerpt=excerpt,
        )

    async def is_available(self, owner_user_id: UUID, source: ValidatedResumeSource) -> bool:
        try:
            document = await self._service.get_document(
                OwnerScope(user_id=owner_user_id), source.document_id
            )
        except ResumeHealthError:
            return False
        return document.status is DocumentStatus.READY
