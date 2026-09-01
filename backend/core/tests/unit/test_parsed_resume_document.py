"""Tests for organized parsed-resume MongoDB payloads."""

from datetime import UTC, datetime
from uuid import uuid4

from rezumi.modules.resume_health.application.parsed_resume_document import (
    build_user_data_document,
)
from rezumi.modules.resume_health.domain import (
    CanonicalResume,
    CanonicalSection,
    CanonicalSemantics,
    OwnerScope,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SemanticSourceAnchor,
)
from rezumi.modules.resume_health.infrastructure.fakes import InMemoryParsedResumeDocumentStore


def _field(
    *,
    name: str,
    value: str,
    field_type: SemanticFieldType = SemanticFieldType.TEXT,
    review_state: SemanticReviewState = SemanticReviewState.CONFIRMED,
) -> SemanticField:
    block_id = uuid4()
    return SemanticField(
        id=uuid4(),
        name=name,
        field_type=field_type,
        value=value,
        confidence_basis_points=9_500,
        review_state=review_state,
        anchors=(
            SemanticSourceAnchor(
                block_id=block_id,
                page=1,
                start=0,
                end=max(len(value), 1),
                source_sha256="ab" * 32,
            ),
        ),
    )


def test_build_user_data_document_organizes_semantics_by_section() -> None:
    owner = OwnerScope(user_id=uuid4())
    resume_id = uuid4()
    snapshot_id = uuid4()
    semantics = CanonicalSemantics(
        schema_version="canonical-semantics/1.0.0",
        parser_version="local/1.0.0",
        entities=(
            SemanticEntity(
                id=uuid4(),
                kind=SemanticEntityKind.CONTACT,
                review_state=SemanticReviewState.CONFIRMED,
                fields=(
                    _field(name="name", value="Alex Example"),
                    _field(
                        name="email", value="alex@example.com", field_type=SemanticFieldType.EMAIL
                    ),
                ),
            ),
            SemanticEntity(
                id=uuid4(),
                kind=SemanticEntityKind.EXPERIENCE,
                review_state=SemanticReviewState.CONFIRMED,
                fields=(
                    _field(name="employer", value="Acme Corp"),
                    _field(name="title", value="Engineer"),
                    _field(
                        name="achievement",
                        value="Shipped feature X",
                        field_type=SemanticFieldType.BULLET,
                    ),
                ),
            ),
        ),
        review_state=SemanticReviewState.CONFIRMED,
    )
    canonical = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(
            CanonicalSection(
                id=uuid4(),
                kind=SectionKind.CONTACT,
                title="Contact",
                confidence_basis_points=9_000,
                blocks=(),
            ),
        ),
        warnings=(),
        semantics=semantics,
    )
    parsed_at = datetime(2026, 7, 15, tzinfo=UTC)

    document = build_user_data_document(
        resume_id=resume_id,
        owner=owner,
        snapshot_id=snapshot_id,
        display_filename="resume.pdf",
        canonical=canonical,
        parsed_at=parsed_at,
    )

    assert document["resumeId"] == str(resume_id)
    assert document["userId"] == str(owner.user_id)
    assert document["semanticReviewState"] == "confirmed"
    assert document["contact"]["name"] == "Alex Example"
    assert document["contact"]["reviewState"] == "confirmed"
    name_provenance = document["contact"]["fieldProvenance"][0]
    assert name_provenance["name"] == "name"
    assert name_provenance["reviewState"] == "confirmed"
    assert name_provenance["confidenceBasisPoints"] == 9_500
    assert name_provenance["anchors"][0]["sourceSha256"] == "ab" * 32
    assert document["experience"][0]["employer"] == "Acme Corp"
    assert document["experience"][0]["achievement"] == ["Shipped feature X"]


def test_build_user_data_document_collects_repeated_skill_names() -> None:
    semantics = CanonicalSemantics(
        schema_version="canonical-semantics/1.0.0",
        parser_version="local/1.0.0",
        entities=(
            SemanticEntity(
                id=uuid4(),
                kind=SemanticEntityKind.SKILL,
                review_state=SemanticReviewState.CONFIRMED,
                fields=(
                    _field(name="name", value="Python"),
                    _field(name="name", value="FastAPI"),
                    _field(name="name", value="LangGraph"),
                ),
            ),
        ),
        review_state=SemanticReviewState.CONFIRMED,
    )
    canonical = CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(),
        warnings=(),
        semantics=semantics,
    )

    document = build_user_data_document(
        resume_id=uuid4(),
        owner=OwnerScope(user_id=uuid4()),
        snapshot_id=uuid4(),
        display_filename="resume.pdf",
        canonical=canonical,
        parsed_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    assert document["skills"][0]["name"] == ["Python", "FastAPI", "LangGraph"]


async def test_in_memory_store_upserts_by_resume_id() -> None:
    store = InMemoryParsedResumeDocumentStore()
    resume_id = str(uuid4())
    first = {
        "resumeId": resume_id,
        "updatedAt": "2026-07-15T00:00:00+00:00",
        "contact": {"name": "A"},
    }
    second = {
        "resumeId": resume_id,
        "updatedAt": "2026-07-15T01:00:00+00:00",
        "contact": {"name": "B"},
    }

    await store.upsert(first)
    await store.upsert(second)

    assert len(store.documents) == 1
    assert store.documents[resume_id]["contact"]["name"] == "B"
    assert store.documents[resume_id]["createdAt"] == "2026-07-15T00:00:00+00:00"
