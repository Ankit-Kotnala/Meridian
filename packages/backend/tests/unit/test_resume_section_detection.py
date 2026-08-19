"""Section-heading recognition over realistically typeset resume headings."""

from uuid import uuid4

from rezumi.modules.resume_health.application.models import (
    ExtractedBlock,
    ExtractionResult,
    SourceSpanView,
)
from rezumi.modules.resume_health.application.service import _canonicalize
from rezumi.modules.resume_health.domain import SectionKind


def _extraction(*lines: tuple[str, str]) -> ExtractionResult:
    blocks: list[ExtractedBlock] = []
    offset = 0
    for kind, text in lines:
        blocks.append(
            ExtractedBlock(
                kind=kind,
                text=text,
                confidence_basis_points=9_000,
                spans=(SourceSpanView(page=1, start=offset, end=offset + len(text)),),
            )
        )
        offset += len(text) + 1
    return ExtractionResult(
        plain_text="\n".join(text for _, text in lines),
        reading_order=tuple(blocks),
        page_count=1,
        image_only=False,
        warnings=(),
        parser_version="test/1",
        layout_signals=(),
    )


def _kinds(extraction: ExtractionResult) -> list[SectionKind]:
    return [section.kind for section in _canonicalize(uuid4(), extraction).sections]


def test_title_case_headings_are_recognized_without_an_upper_case_guess() -> None:
    """The extractor only guesses "heading" for upper-case or colon-terminated
    lines, so an ordinary title-case resume previously collapsed into a single
    unrecognized section and produced no career facts at all."""
    kinds = _kinds(
        _extraction(
            ("paragraph", "Priya Raman"),
            ("paragraph", "Work Experience"),
            ("paragraph", "Senior Software Engineer, Northwind Financial"),
            ("paragraph", "Education"),
            ("paragraph", "B.S. Computer Science, Fictional University"),
            ("paragraph", "Technical Skills"),
            ("paragraph", "Python, PostgreSQL"),
        )
    )

    assert kinds == [
        SectionKind.OTHER,
        SectionKind.EXPERIENCE,
        SectionKind.EDUCATION,
        SectionKind.SKILLS,
    ]


def test_decorated_and_synonymous_headings_resolve_to_the_same_section() -> None:
    kinds = _kinds(
        _extraction(
            ("heading", "— EMPLOYMENT HISTORY —"),
            ("paragraph", "Staff Engineer, Northwind Financial"),
            ("paragraph", "Core Competencies:"),
            ("paragraph", "Python, PostgreSQL"),
        )
    )

    assert kinds == [SectionKind.EXPERIENCE, SectionKind.SKILLS]


def test_body_text_and_bullets_are_never_promoted_to_section_headings() -> None:
    """Only a short standalone label may break a section, so a bullet or a
    sentence that merely opens with a section word stays body content."""
    kinds = _kinds(
        _extraction(
            ("paragraph", "Work Experience"),
            ("bullet", "Education programs delivered to 400 advisors."),
            (
                "paragraph",
                "Experience across payments, policy administration, and settlement "
                "for regulated life and annuity carriers.",
            ),
        )
    )

    assert kinds == [SectionKind.EXPERIENCE]
