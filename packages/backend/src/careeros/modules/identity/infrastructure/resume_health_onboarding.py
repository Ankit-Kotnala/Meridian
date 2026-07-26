"""Owner-scoped Resume Health observation for resumable onboarding."""

from uuid import UUID

from careeros.modules.identity.application.models import OnboardingResumeObservation
from careeros.modules.identity.domain import ObservedResumeStatus
from careeros.modules.resume_health.application import (
    DocumentStatus,
    OwnerScope,
    ResumeHealthService,
    SemanticReviewState,
)


class ResumeHealthOnboardingSource:
    """Translate Resume Health application views without reading its tables."""

    def __init__(self, service: ResumeHealthService) -> None:
        self._service = service

    async def observe(self, owner_user_id: UUID) -> OnboardingResumeObservation:
        scope = OwnerScope(user_id=owner_user_id)
        documents = await self._service.list_documents(scope)
        if not documents:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus.NOT_STARTED,
                parsed_review_status=ObservedResumeStatus.NOT_STARTED,
            )
        document = documents[0]
        if document.status in {
            DocumentStatus.QUARANTINED,
            DocumentStatus.PROCESSING,
            DocumentStatus.DELETING,
        }:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus.PROCESSING,
                parsed_review_status=ObservedResumeStatus.NOT_STARTED,
                document_id=document.id,
            )
        if document.status in {DocumentStatus.REJECTED, DocumentStatus.FAILED}:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus.FAILED,
                parsed_review_status=ObservedResumeStatus.NOT_STARTED,
                document_id=document.id,
                safe_error_code=document.safe_error_code,
            )
        if document.status is not DocumentStatus.READY or document.current_snapshot_id is None:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus.PROCESSING,
                parsed_review_status=ObservedResumeStatus.NOT_STARTED,
                document_id=document.id,
            )
        snapshot = await self._service.get_canonical_resume(scope, document.id)
        semantics = snapshot.resume.semantics
        if semantics is None or semantics.review_state is SemanticReviewState.UNREVIEWED:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus.REVIEW_REQUIRED,
                parsed_review_status=ObservedResumeStatus.REVIEW_REQUIRED,
                document_id=document.id,
            )
        status = (
            ObservedResumeStatus.ANALYSIS_READY
            if document.latest_analysis_id is not None
            else ObservedResumeStatus.REVIEWED
        )
        return OnboardingResumeObservation(
            resume_status=status,
            parsed_review_status=status,
            document_id=document.id,
        )
