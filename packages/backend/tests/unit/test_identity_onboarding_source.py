"""Resume Health observations remain owner-scoped and content-free."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from careeros.modules.identity.domain import ObservedResumeStatus
from careeros.modules.identity.infrastructure.resume_health_onboarding import (
    ResumeHealthOnboardingSource,
)
from careeros.modules.resume_health.application.models import DocumentView
from careeros.modules.resume_health.domain import (
    CanonicalSemantics,
    DocumentStatus,
    MalwareStatus,
    OwnerScope,
    ResumeMediaType,
    SemanticReviewState,
)


class ResumeHealthStub:
    def __init__(self, documents=(), semantics=None) -> None:
        self.documents = tuple(documents)
        self.semantics = semantics
        self.scopes: list[OwnerScope] = []

    async def list_documents(self, scope: OwnerScope):
        self.scopes.append(scope)
        return self.documents

    async def get_canonical_resume(self, scope: OwnerScope, document_id: UUID):
        self.scopes.append(scope)
        assert document_id == self.documents[0].id
        return SimpleNamespace(resume=SimpleNamespace(semantics=self.semantics))


def _document(
    status: DocumentStatus,
    *,
    snapshot: bool = False,
    analysis: bool = False,
    safe_error_code: str | None = None,
) -> DocumentView:
    now = datetime(2026, 7, 26, tzinfo=UTC)
    return DocumentView(
        id=uuid4(),
        display_filename="private-name.pdf",
        media_type=ResumeMediaType.PDF,
        size_bytes=100,
        status=status,
        malware_status=MalwareStatus.CLEAN,
        page_count=1,
        safe_error_code=safe_error_code,
        retention_expires_at=None,
        version=1,
        created_at=now,
        updated_at=now,
        current_snapshot_id=uuid4() if snapshot else None,
        latest_analysis_id=uuid4() if analysis else None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("documents", "semantics", "resume_status", "review_status"),
    [
        ((), None, ObservedResumeStatus.NOT_STARTED, ObservedResumeStatus.NOT_STARTED),
        (
            (_document(DocumentStatus.PROCESSING),),
            None,
            ObservedResumeStatus.PROCESSING,
            ObservedResumeStatus.NOT_STARTED,
        ),
        (
            (_document(DocumentStatus.FAILED, safe_error_code="processing_failed"),),
            None,
            ObservedResumeStatus.FAILED,
            ObservedResumeStatus.NOT_STARTED,
        ),
        (
            (_document(DocumentStatus.READY, snapshot=True),),
            CanonicalSemantics(
                schema_version="canonical-resume/2.0.0",
                parser_version="local/1",
                entities=(),
            ),
            ObservedResumeStatus.REVIEW_REQUIRED,
            ObservedResumeStatus.REVIEW_REQUIRED,
        ),
        (
            (_document(DocumentStatus.READY, snapshot=True, analysis=True),),
            CanonicalSemantics(
                schema_version="canonical-resume/2.0.0",
                parser_version="local/1",
                entities=(),
                review_state=SemanticReviewState.CONFIRMED,
            ),
            ObservedResumeStatus.ANALYSIS_READY,
            ObservedResumeStatus.ANALYSIS_READY,
        ),
    ],
)
async def test_resume_health_observation_is_owner_scoped(
    documents,
    semantics,
    resume_status: ObservedResumeStatus,
    review_status: ObservedResumeStatus,
) -> None:
    owner_user_id = uuid4()
    service = ResumeHealthStub(documents, semantics)
    source = ResumeHealthOnboardingSource(service)  # type: ignore[arg-type]

    observed = await source.observe(owner_user_id)

    assert observed.resume_status is resume_status
    assert observed.parsed_review_status is review_status
    assert all(scope == OwnerScope(user_id=owner_user_id) for scope in service.scopes)
    if resume_status is ObservedResumeStatus.FAILED:
        assert observed.safe_error_code == "processing_failed"
