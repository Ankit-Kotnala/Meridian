"""Versioned semantic resume model and deterministic parser tests."""

from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest

from rezumi.modules.resume_health.application.semantic_validation import (
    validate_parser_semantics,
)
from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    CanonicalSemantics,
    DatePrecision,
    SectionKind,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SourceSpan,
)
from rezumi.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)

_GROUNDED_SENTENCE = "Led a cross-functional team of 8 to simplify onboarding."


def _resume() -> CanonicalResume:
    contact_id = uuid4()
    experience_id = uuid4()
    return CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=contact_id,
                kind=SectionKind.CONTACT,
                title="Contact",
                confidence_basis_points=9_000,
                blocks=(
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text="Alex Rivera | alex@example.test | github.com/alex",
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 0, 50),),
                    ),
                ),
            ),
            CanonicalSection(
                id=experience_id,
                kind=SectionKind.EXPERIENCE,
                title="Experience",
                confidence_basis_points=9_000,
                blocks=(
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text="Principal Engineer | Fictional Labs | Jan 2020 - Present",
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 51, 108),),
                    ),
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.BULLET,
                        text="Built a fictional delivery platform.",
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 109, 145),),
                    ),
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text=_GROUNDED_SENTENCE,
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 146, 146 + len(_GROUNDED_SENTENCE)),),
                    ),
                ),
            ),
        ),
        warnings=(),
    )


@pytest.mark.asyncio
async def test_local_semantic_parser_emits_typed_source_anchored_values() -> None:
    document_id = uuid4()
    digest = sha256(b"fictional resume").hexdigest()
    resume = _resume()

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    assert {entity.kind for entity in semantics.entities} == {
        SemanticEntityKind.CONTACT,
        SemanticEntityKind.EXPERIENCE,
    }
    fields = [field for entity in semantics.entities for field in entity.fields]
    assert any(field.field_type is SemanticFieldType.EMAIL for field in fields)
    assert any(field.field_type is SemanticFieldType.URL for field in fields)
    assert any(
        field.field_type is SemanticFieldType.DATE and field.date_precision is DatePrecision.MONTH
        for field in fields
    )
    assert all(field.review_state is SemanticReviewState.UNREVIEWED for field in fields)
    assert all(field.anchors[0].source_sha256 == digest for field in fields)
    assert any(field.value == _GROUNDED_SENTENCE for field in fields)
    validate_parser_semantics(resume, semantics, digest)

    repeated = await LocalResumeParserProvider().parse(document_id, resume, digest)
    assert semantics == repeated


@pytest.mark.asyncio
async def test_skills_section_becomes_single_structured_entity() -> None:
    document_id = uuid4()
    digest = sha256(b"fictional skills resume").hexdigest()
    skills_section_id = uuid4()
    first = "Python, PostgreSQL, TypeScript"
    second = "React | Node.js"
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=skills_section_id,
                kind=SectionKind.SKILLS,
                title="Skills",
                confidence_basis_points=9_000,
                blocks=(
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text=first,
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 0, len(first)),),
                    ),
                    CanonicalBlock(
                        id=uuid4(),
                        kind=BlockKind.PARAGRAPH,
                        text=second,
                        confidence_basis_points=9_000,
                        spans=(SourceSpan(1, 40, 40 + len(second)),),
                    ),
                ),
            ),
        ),
        warnings=(),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    skill_entities = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.SKILL
    ]
    # Every skill line collapses into one structured section rather than one
    # entity per line, and each individual skill becomes its own name field.
    assert len(skill_entities) == 1
    entity = skill_entities[0]
    assert entity.source_section_id == skills_section_id
    assert all(field.name == "name" for field in entity.fields)
    assert [field.value for field in entity.fields] == [
        "Python",
        "PostgreSQL",
        "TypeScript",
        "React",
        "Node.js",
    ]
    validate_parser_semantics(resume, semantics, digest)
    assert await LocalResumeParserProvider().parse(document_id, resume, digest) == semantics


def test_canonical_resume_round_trip_preserves_semantics_and_legacy_reads() -> None:
    resume = _resume()
    semantics = CanonicalSemantics(
        schema_version="canonical-semantics/1.0.0",
        parser_version="test/1",
        entities=(),
    )
    versioned = CanonicalResume(
        schema_version=resume.schema_version,
        sections=resume.sections,
        source_sections=resume.sections,
        semantics=semantics,
        warnings=(),
    )

    assert CanonicalResume.from_dict(versioned.to_dict()) == versioned
    legacy = CanonicalResume.from_dict(
        {
            "schemaVersion": "canonical-resume/1.0.0",
            "sections": [],
            "warnings": [],
        }
    )
    assert legacy.source_sections == ()
    assert legacy.semantics is None


def test_semantic_model_rejects_unanchored_parser_claims() -> None:
    with pytest.raises(ValueError, match="require source anchors"):
        SemanticField(
            id=uuid4(),
            name="name",
            field_type=SemanticFieldType.TEXT,
            value="Unsupported claim",
            confidence_basis_points=5_000,
            review_state=SemanticReviewState.UNREVIEWED,
        )


@pytest.mark.asyncio
async def test_parser_validation_rejects_anchor_digest_and_value_drift() -> None:
    resume = _resume()
    semantics = await LocalResumeParserProvider().parse(
        uuid4(),
        resume,
        sha256(b"fictional resume").hexdigest(),
    )

    with pytest.raises(ValueError, match="immutable source"):
        validate_parser_semantics(resume, semantics, "0" * 64)

    first_entity = semantics.entities[0]
    first_field = first_entity.fields[0]
    drifted = replace(
        semantics,
        entities=(
            replace(
                first_entity,
                fields=(
                    replace(first_field, value="A value absent from the source"),
                    *first_entity.fields[1:],
                ),
            ),
            *semantics.entities[1:],
        ),
    )
    with pytest.raises(ValueError, match="claimed value"):
        validate_parser_semantics(
            resume,
            drifted,
            sha256(b"fictional resume").hexdigest(),
        )


@pytest.mark.asyncio
async def test_date_locale_concurrent_roles_and_career_gap_remain_factual_records() -> None:
    section = CanonicalSection(
        id=uuid4(),
        kind=SectionKind.EXPERIENCE,
        title="Experience",
        confidence_basis_points=9_000,
        blocks=(
            CanonicalBlock(
                id=uuid4(),
                kind=BlockKind.PARAGRAPH,
                text="Engineer | Fictional Alpha | 03/2021 - 2024",
                confidence_basis_points=9_000,
                spans=(SourceSpan(1, 0, 45),),
            ),
            CanonicalBlock(
                id=uuid4(),
                kind=BlockKind.PARAGRAPH,
                text="Advisor | Fictional Beta | 2022-06 - Present",
                confidence_basis_points=9_000,
                spans=(SourceSpan(1, 46, 91),),
            ),
            CanonicalBlock(
                id=uuid4(),
                kind=BlockKind.PARAGRAPH,
                text="Analyst | Fictional Gamma | 2015 - 2018",
                confidence_basis_points=9_000,
                spans=(SourceSpan(1, 92, 132),),
            ),
        ),
    )
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(section,),
        warnings=(),
    )

    semantics = await LocalResumeParserProvider().parse(
        uuid4(),
        resume,
        sha256(b"concurrent roles").hexdigest(),
    )

    experiences = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.EXPERIENCE
    ]
    assert len(experiences) == 3
    dates = [
        field
        for entity in experiences
        for field in entity.fields
        if field.field_type is SemanticFieldType.DATE
    ]
    assert {field.value for field in dates} == {
        "03/2021",
        "2024",
        "2022-06",
        "Present",
        "2015",
        "2018",
    }
    assert {field.date_precision for field in dates} == {
        DatePrecision.MONTH,
        DatePrecision.YEAR,
        DatePrecision.UNKNOWN,
    }


def _block(text: str, start: int, kind: BlockKind = BlockKind.PARAGRAPH) -> CanonicalBlock:
    return CanonicalBlock(
        id=uuid4(),
        kind=kind,
        text=text,
        confidence_basis_points=9_000,
        spans=(SourceSpan(1, start, start + len(text)),),
    )


def _experience_resume(*blocks: CanonicalBlock) -> CanonicalResume:
    return CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.EXPERIENCE,
                title="Work Experience",
                confidence_basis_points=9_000,
                blocks=blocks,
            ),
        ),
        warnings=(),
    )


@pytest.mark.asyncio
async def test_multi_line_experience_header_becomes_one_importable_record() -> None:
    """A role whose header wraps across lines still yields title, employer, and dates.

    Career Record refuses to propose an experience without all three, so a
    parser that split the header into separate entities produced a resume that
    could never populate a career record.
    """
    document_id = uuid4()
    digest = sha256(b"fictional wrapped header").hexdigest()
    resume = _experience_resume(
        _block("Senior Software Engineer, Northwind Financial", 0),
        _block("San Francisco, CA | Mar 2021 - Present", 60),
        _block("Led the policy ledger migration.", 110, BlockKind.BULLET),
        _block("Software Engineer, Blue Harbor Systems", 150),
        _block("Austin, TX | Jun 2017 - Feb 2021", 200),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    experiences = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.EXPERIENCE
    ]
    assert len(experiences) == 2
    first = {field.name: field.value for field in experiences[0].fields}
    assert first["title"] == "Senior Software Engineer"
    assert first["employer"] == "Northwind Financial"
    assert first["location"] == "San Francisco, CA"
    assert first["start_date"] == "Mar 2021"
    assert first["end_date"] == "Present"
    second = {field.name: field.value for field in experiences[1].fields}
    assert second["title"] == "Software Engineer"
    assert second["employer"] == "Blue Harbor Systems"
    assert second["start_date"] == "Jun 2017"
    validate_parser_semantics(resume, semantics, digest)


@pytest.mark.asyncio
async def test_consecutive_dated_roles_without_bullets_stay_separate_records() -> None:
    """Two one-line roles must not merge into a single record."""
    document_id = uuid4()
    digest = sha256(b"fictional bulletless roles").hexdigest()
    resume = _experience_resume(
        _block("Staff Engineer, Northwind Financial, 2021 - 2024", 0),
        _block("Senior Engineer, Blue Harbor Systems, 2017 - 2021", 60),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    experiences = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.EXPERIENCE
    ]
    assert [
        {field.name: field.value for field in entity.fields}["employer"] for entity in experiences
    ] == ["Northwind Financial", "Blue Harbor Systems"]
    validate_parser_semantics(resume, semantics, digest)


@pytest.mark.asyncio
async def test_weak_separators_stop_once_the_record_has_its_names() -> None:
    """An institution containing "at" survives once earlier names are filled."""
    document_id = uuid4()
    digest = sha256(b"fictional education").hexdigest()
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.EDUCATION,
                title="Education",
                confidence_basis_points=9_000,
                blocks=(
                    _block("B.S. Computer Science, University of Texas at Austin", 0),
                    _block("2013 - 2017", 60),
                ),
            ),
        ),
        warnings=(),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    education = {
        field.name: field.value
        for entity in semantics.entities
        if entity.kind is SemanticEntityKind.EDUCATION
        for field in entity.fields
    }
    assert education["degree"] == "B.S. Computer Science"
    assert education["institution"] == "University of Texas at Austin"
    assert education["start_date"] == "2013"
    assert education["end_date"] == "2017"
    validate_parser_semantics(resume, semantics, digest)


@pytest.mark.asyncio
async def test_pipe_delimited_experience_headers_map_employer_before_title() -> None:
    document_id = uuid4()
    digest = sha256(b"pipe experience header").hexdigest()
    resume = _experience_resume(
        _block(
            (
                "Zinnia | Software Engineer I (AI/ML & Full Stack) | "
                "New Delhi, India  Jan 2026 - Present"
            ),
            0,
        ),
        _block(
            (
                "• Independently architected and built a production-bound AI assistant "
                "with React and FastAPI."
            ),
            120,
            BlockKind.BULLET,
        ),
        _block(
            (
                "routing enterprise questions through 5 governed paths: "
                "SQL, knowledge retrieval, hybrid."
            ),
            220,
        ),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    experiences = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.EXPERIENCE
    ]
    assert len(experiences) == 1
    fields = {field.name: field.value for field in experiences[0].fields}
    assert fields["employer"] == "Zinnia"
    assert fields["title"] == "Software Engineer I (AI/ML & Full Stack)"
    assert fields["location"] == "New Delhi, India"
    achievements = fields.get("achievement")
    assert achievements
    validate_parser_semantics(resume, semantics, digest)


@pytest.mark.asyncio
async def test_pipe_delimited_education_headers_map_institution_before_degree() -> None:
    document_id = uuid4()
    digest = sha256(b"pipe education header").hexdigest()
    resume = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.EDUCATION,
                title="Education",
                confidence_basis_points=9_000,
                blocks=(
                    _block(
                        "CDAC Noida | MCA, Artificial Intelligence | 2024 - 2026 | CGPA: 8.90/10", 0
                    ),
                    _block("CERTIFICATIONS & ACHIEVEMENTS", 80, BlockKind.HEADING),
                    _block("SWAYAM Certified Machine Learning Engineer", 120),
                ),
            ),
        ),
        warnings=(),
    )

    semantics = await LocalResumeParserProvider().parse(document_id, resume, digest)

    education = [
        entity for entity in semantics.entities if entity.kind is SemanticEntityKind.EDUCATION
    ]
    assert len(education) == 1
    fields = {field.name: field.value for field in education[0].fields}
    assert fields["institution"] == "CDAC Noida"
    assert fields["degree"] == "MCA"
    assert fields["field"] == "Artificial Intelligence"
    validate_parser_semantics(resume, semantics, digest)
