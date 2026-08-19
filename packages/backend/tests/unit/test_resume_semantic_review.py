"""Typed semantic review operation tests."""

from hashlib import sha256
from uuid import uuid4

import pytest

from rezumi.modules.resume_health.application import (
    AddSemanticEntity,
    AddSemanticField,
    ConfirmSemanticField,
    CorrectSemanticField,
    NewSemanticField,
    ReclassifySemanticEntity,
    RemoveSemanticEntity,
    RemoveSemanticField,
    SemanticFieldReclassification,
)
from rezumi.modules.resume_health.application.semantic_review import (
    apply_semantic_review,
    auto_confirm_parsed_semantics,
)
from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    CanonicalSemantics,
    DatePrecision,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SourceSpan,
)
from rezumi.modules.resume_health.domain.errors import ResumeStateConflict
from rezumi.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)


async def _semantics():
    block = CanonicalBlock(
        id=uuid4(),
        kind=BlockKind.PARAGRAPH,
        text="Principal Engineer | Fictional Labs | Jan 2020 - Present",
        confidence_basis_points=9_000,
        spans=(SourceSpan(1, 0, 57),),
    )
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.EXPERIENCE,
                title="Experience",
                confidence_basis_points=9_000,
                blocks=(block,),
            ),
        ),
        warnings=(),
    )
    return await LocalResumeParserProvider().parse(
        uuid4(),
        resume,
        sha256(b"fictional").hexdigest(),
    )


@pytest.mark.asyncio
async def test_review_operations_preserve_anchors_and_mark_user_claims() -> None:
    semantics = await _semantics()
    entity = semantics.entities[0]
    title = next(field for field in entity.fields if field.name == "title")
    employer = next(field for field in entity.fields if field.name == "employer")

    reviewed = apply_semantic_review(
        semantics,
        (
            ConfirmSemanticField(employer.id),
            CorrectSemanticField(title.id, "Staff Engineer"),
            AddSemanticField(
                entity.id,
                "achievement",
                SemanticFieldType.BULLET,
                "Built a user-confirmed fictional platform.",
            ),
        ),
        confirm_no_changes=False,
    )

    revised_entity = reviewed.entities[0]
    revised_title = next(field for field in revised_entity.fields if field.id == title.id)
    added = revised_entity.fields[-1]
    assert revised_title.review_state is SemanticReviewState.CORRECTED
    assert revised_title.anchors == title.anchors
    assert added.review_state is SemanticReviewState.USER_ADDED
    assert added.anchors == ()
    assert revised_entity.review_state is SemanticReviewState.CORRECTED


@pytest.mark.asyncio
async def test_add_remove_and_reclassify_are_typed_and_reversible_by_snapshot() -> None:
    semantics = await _semantics()
    entity = semantics.entities[0]
    mapping = tuple(
        SemanticFieldReclassification(
            field.id,
            {
                "title": "degree",
                "employer": "institution",
                "location": "location",
                "start_date": "start_date",
                "end_date": "end_date",
            }[field.name],
        )
        for field in entity.fields
    )
    reclassified = apply_semantic_review(
        semantics,
        (ReclassifySemanticEntity(entity.id, SemanticEntityKind.EDUCATION, mapping),),
        confirm_no_changes=False,
    )
    assert reclassified.entities[0].kind is SemanticEntityKind.EDUCATION

    added = apply_semantic_review(
        reclassified,
        (
            AddSemanticEntity(
                SemanticEntityKind.CERTIFICATION,
                (
                    NewSemanticField(
                        "name",
                        SemanticFieldType.TEXT,
                        "Fictional Credential",
                    ),
                    NewSemanticField(
                        "issued_date",
                        SemanticFieldType.DATE,
                        "2025",
                        DatePrecision.YEAR,
                    ),
                ),
            ),
        ),
        confirm_no_changes=False,
    )
    certification = added.entities[-1]
    assert certification.review_state is SemanticReviewState.USER_ADDED

    removed = apply_semantic_review(
        added,
        (
            RemoveSemanticField(certification.fields[-1].id),
            RemoveSemanticEntity(entity.id),
        ),
        confirm_no_changes=False,
    )
    assert removed.entities[0].review_state is SemanticReviewState.REMOVED
    assert removed.entities[-1].fields[-1].review_state is SemanticReviewState.REMOVED
    assert semantics.entities[0].review_state is SemanticReviewState.UNREVIEWED


@pytest.mark.asyncio
async def test_explicit_no_change_confirmation_is_exclusive() -> None:
    semantics = await _semantics()

    confirmed = apply_semantic_review(semantics, (), confirm_no_changes=True)

    assert all(
        field.review_state is SemanticReviewState.CONFIRMED
        for entity in confirmed.entities
        for field in entity.fields
    )


def test_auto_confirm_parsed_semantics_confirms_unreviewed_fields() -> None:
    semantics = CanonicalSemantics(
        schema_version="canonical-semantics/1.0.0",
        parser_version="local-semantic/1",
        entities=(
            SemanticEntity(
                id=uuid4(),
                kind=SemanticEntityKind.SKILL,
                review_state=SemanticReviewState.UNREVIEWED,
                fields=(
                    SemanticField(
                        id=uuid4(),
                        name="name",
                        field_type=SemanticFieldType.TEXT,
                        value="Python",
                        confidence_basis_points=8_000,
                        review_state=SemanticReviewState.UNREVIEWED,
                    ),
                ),
            ),
        ),
        review_state=SemanticReviewState.UNREVIEWED,
    )

    confirmed = auto_confirm_parsed_semantics(semantics)

    assert confirmed.review_state is SemanticReviewState.CONFIRMED
    assert confirmed.entities[0].fields[0].review_state is SemanticReviewState.CONFIRMED
    with pytest.raises(ResumeStateConflict):
        apply_semantic_review(
            semantics,
            (ConfirmSemanticField(semantics.entities[0].fields[0].id),),
            confirm_no_changes=True,
        )


@pytest.mark.asyncio
async def test_user_added_origin_cannot_be_relabelled_as_parser_derived() -> None:
    semantics = await _semantics()
    entity = semantics.entities[0]
    added = apply_semantic_review(
        semantics,
        (
            AddSemanticField(
                entity.id,
                "achievement",
                SemanticFieldType.BULLET,
                "A user-confirmed fictional result.",
            ),
        ),
        confirm_no_changes=False,
    )
    user_field = added.entities[0].fields[-1]

    corrected = apply_semantic_review(
        added,
        (
            CorrectSemanticField(
                user_field.id,
                "A corrected user-confirmed fictional result.",
            ),
        ),
        confirm_no_changes=False,
    )

    assert corrected.entities[0].fields[-1].review_state is SemanticReviewState.USER_ADDED
    assert corrected.entities[0].fields[-1].anchors == ()
    with pytest.raises(ResumeStateConflict):
        apply_semantic_review(
            added,
            (ConfirmSemanticField(user_field.id),),
            confirm_no_changes=False,
        )


@pytest.mark.asyncio
async def test_review_rejects_incompatible_field_types_and_no_op_reclassification() -> None:
    semantics = await _semantics()
    entity = semantics.entities[0]

    with pytest.raises(ResumeStateConflict):
        apply_semantic_review(
            semantics,
            (
                AddSemanticField(
                    entity.id,
                    "start_date",
                    SemanticFieldType.TEXT,
                    "2025",
                ),
            ),
            confirm_no_changes=False,
        )
    with pytest.raises(ResumeStateConflict):
        apply_semantic_review(
            semantics,
            (
                ReclassifySemanticEntity(
                    entity.id,
                    entity.kind,
                    tuple(
                        SemanticFieldReclassification(field.id, field.name)
                        for field in entity.fields
                    ),
                ),
            ),
            confirm_no_changes=False,
        )
