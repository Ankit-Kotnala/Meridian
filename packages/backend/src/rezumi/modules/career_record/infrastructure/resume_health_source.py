"""Explicit Resume Health application query used by Career Record."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from rezumi.modules.resume_health.application import (
    CanonicalSnapshotView,
    DocumentStatus,
    DocumentView,
    OwnerScope,
    ResumeHealthError,
    SemanticReviewState,
)

from ..application.models import (
    ResumeSourceLocator,
    ValidatedResumeSource,
)
from ..domain import (
    SemanticCandidateKind,
    SemanticImportAnchor,
    SemanticImportField,
    SemanticImportFieldState,
    ValidatedSemanticCandidate,
    exact_claim_sha256,
)


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

    async def reviewed_semantic_candidates(
        self,
        owner_user_id: UUID,
        document_id: UUID,
        snapshot_id: UUID,
    ) -> tuple[ValidatedSemanticCandidate, ...]:
        scope = OwnerScope(user_id=owner_user_id)
        try:
            document = await self._reader.get_document(scope, document_id)
            snapshot = await self._reader.get_canonical_resume(scope, document_id)
        except ResumeHealthError:
            return ()
        semantics = snapshot.resume.semantics
        if (
            document.status is not DocumentStatus.READY
            or snapshot.id != snapshot_id
            or snapshot.document_id != document_id
            or semantics is None
            or semantics.review_state
            not in {SemanticReviewState.CONFIRMED, SemanticReviewState.CORRECTED}
        ):
            return ()

        candidates: list[ValidatedSemanticCandidate] = []
        for entity in semantics.entities:
            if entity.review_state is SemanticReviewState.REMOVED:
                continue
            fields: list[SemanticImportField] = []
            for field in entity.fields:
                if field.review_state not in {
                    SemanticReviewState.CONFIRMED,
                    SemanticReviewState.CORRECTED,
                    SemanticReviewState.USER_ADDED,
                }:
                    continue
                try:
                    anchors = tuple(
                        SemanticImportAnchor(
                            block_id=anchor.block_id,
                            page=anchor.page,
                            start_offset=anchor.start,
                            end_offset=anchor.end,
                            source_sha256=bytes.fromhex(anchor.source_sha256),
                            source_excerpt=_semantic_source_excerpt(
                                snapshot, anchor.block_id, anchor.page, anchor.start, anchor.end
                            ),
                        )
                        for anchor in field.anchors
                    )
                except (ValueError, TypeError):
                    # A reviewed semantic value is not importable when its exact
                    # original source can no longer be revalidated. Fail the
                    # snapshot closed instead of returning a partially grounded
                    # candidate or surfacing an internal parsing error.
                    return ()
                fields.append(
                    SemanticImportField(
                        semantic_field_id=field.id,
                        name=field.name,
                        field_type=field.field_type.value,
                        value=field.value,
                        review_state=SemanticImportFieldState(field.review_state.value),
                        confidence_basis_points=field.confidence_basis_points,
                        date_precision=(
                            field.date_precision.value if field.date_precision is not None else None
                        ),
                        anchors=anchors,
                    )
                )
            if fields:
                candidates.append(
                    ValidatedSemanticCandidate(
                        document_id=document_id,
                        snapshot_id=snapshot.id,
                        snapshot_revision=snapshot.revision,
                        schema_version=semantics.schema_version,
                        parser_version=semantics.parser_version,
                        semantic_entity_id=entity.id,
                        kind=SemanticCandidateKind(entity.kind.value),
                        fields=tuple(fields),
                    )
                )
        return tuple(candidates)


def _semantic_source_excerpt(
    snapshot: CanonicalSnapshotView,
    block_id: UUID,
    page: int,
    start: int,
    end: int,
) -> str:
    block = next(
        (
            candidate
            for section in snapshot.original_resume.sections
            for candidate in section.blocks
            if candidate.id == block_id
        ),
        None,
    )
    if block is None:
        raise ValueError("semantic source block is unavailable")
    span = next(
        (
            candidate
            for candidate in block.spans
            if candidate.page == page and candidate.start <= start and candidate.end >= end
        ),
        None,
    )
    if span is None:
        raise ValueError("semantic source span is unavailable")
    excerpt = block.text[start - span.start : end - span.start].strip()
    if not excerpt:
        raise ValueError("semantic source excerpt is unavailable")
    return excerpt[:1_000]
