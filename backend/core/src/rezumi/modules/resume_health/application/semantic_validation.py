"""Validation for untrusted semantic-parser provider output."""

from __future__ import annotations

from rezumi.modules.resume_health.domain import (
    CanonicalResume,
    CanonicalSemantics,
    SemanticReviewState,
)

_SEMANTIC_SCHEMA_VERSION = "canonical-semantics/1.0.0"


def validate_parser_semantics(
    resume: CanonicalResume,
    semantics: CanonicalSemantics,
    source_sha256: str,
) -> None:
    """Require every parser claim to map exactly to the supplied immutable source."""
    if (
        semantics.schema_version != _SEMANTIC_SCHEMA_VERSION
        or semantics.review_state is not SemanticReviewState.UNREVIEWED
    ):
        raise ValueError("semantic parser returned an unsupported schema or review state")

    sections = {section.id: section for section in resume.sections}
    if len(sections) != len(resume.sections):
        raise ValueError("semantic parser source section identifiers are not unique")
    blocks = {
        block.id: (section.id, block) for section in resume.sections for block in section.blocks
    }
    if len(blocks) != sum(len(section.blocks) for section in resume.sections):
        raise ValueError("semantic parser source block identifiers are not unique")

    for entity in semantics.entities:
        if (
            entity.review_state is not SemanticReviewState.UNREVIEWED
            or entity.source_section_id not in sections
        ):
            raise ValueError("semantic parser entity is not grounded in a source section")
        for field in entity.fields:
            if field.review_state is not SemanticReviewState.UNREVIEWED or not field.anchors:
                raise ValueError("semantic parser field is not an unreviewed source claim")
            anchor_keys: set[tuple[object, int, int, int]] = set()
            for anchor in field.anchors:
                key = (anchor.block_id, anchor.page, anchor.start, anchor.end)
                if key in anchor_keys:
                    raise ValueError("semantic parser returned a duplicate source anchor")
                anchor_keys.add(key)
                source = blocks.get(anchor.block_id)
                if (
                    source is None
                    or source[0] != entity.source_section_id
                    or anchor.source_sha256 != source_sha256
                ):
                    raise ValueError("semantic parser anchor is outside its immutable source")
                block = source[1]
                matching_spans = [
                    span
                    for span in block.spans
                    if span.page == anchor.page
                    and span.start <= anchor.start
                    and anchor.end <= span.end
                    and anchor.end - span.start <= len(block.text)
                ]
                if len(matching_spans) != 1:
                    raise ValueError("semantic parser anchor is outside its source span")
                span = matching_spans[0]
                relative_start = anchor.start - span.start
                relative_end = anchor.end - span.start
                if block.text[relative_start:relative_end] != field.value:
                    raise ValueError("semantic parser anchor does not match its claimed value")
