"""Presentation helpers for Interview Prep API responses."""

from __future__ import annotations

from typing import cast

from rezumi.modules.interview_prep.application import (
    DefenseMap,
    FollowUpDraftReadView,
    GroundingAssessment,
    GroundingStatus,
    PagedResult,
    QuestionReadView,
    SessionReadView,
    SessionView,
    StoryReadView,
)
from rezumi.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewQuestion,
    InterviewSessionNote,
    SessionContextClaim,
    SessionContextSnapshot,
    StarStory,
    StoryClaimPin,
)

from .schemas import (
    DefenseMapEntryResponse,
    DefenseMapResponse,
    EvidenceRevisionPinResponse,
    EvidenceStrengthValue,
    FollowUpDraftPageResponse,
    FollowUpDraftResponse,
    FollowUpDraftSummaryResponse,
    GeneratedQuestionBankResponse,
    InterviewQuestionPageResponse,
    InterviewQuestionResponse,
    InterviewQuestionSummaryResponse,
    InterviewSessionNotePageResponse,
    InterviewSessionNoteResponse,
    InterviewSessionPageResponse,
    InterviewSessionResponse,
    InterviewSessionSummaryResponse,
    PageResponse,
    RequirementImportanceValue,
    SessionContextClaimResponse,
    SessionContextRequirementResponse,
    SessionContextResponse,
    StarStoryPageResponse,
    StarStoryResponse,
    StarStorySummaryResponse,
    StoryClaimPinResponse,
)


def page_response(limit: int, has_more: bool, next_cursor: str | None) -> PageResponse:
    return PageResponse(limit=limit, has_more=has_more, next_cursor=next_cursor)


def evidence_pin_response(value: EvidenceRevisionPin) -> EvidenceRevisionPinResponse:
    return EvidenceRevisionPinResponse(
        evidence_id=value.evidence_id,
        evidence_revision_id=value.evidence_revision_id,
        revision_number=value.revision_number,
        statement=value.statement,
        statement_sha256=value.statement_sha256,
        strength=cast(EvidenceStrengthValue, value.strength),
        has_numeric_claim=value.has_numeric_claim,
    )


def story_claim_pin_response(value: StoryClaimPin) -> StoryClaimPinResponse:
    return StoryClaimPinResponse(
        source_claim_id=value.source_claim_id,
        claim_text=value.claim_text,
        claim_sha256=value.claim_sha256,
        strong=value.strong,
        field_names=[item.value for item in value.field_names],
        evidence_pins=[evidence_pin_response(item) for item in value.evidence_pins],
    )


def star_story_response(
    value: StarStory | StoryReadView,
    grounding: GroundingAssessment | None = None,
) -> StarStoryResponse:
    if isinstance(value, StoryReadView):
        grounding = value.grounding
        story = value.story
    else:
        story = value
    assessment = grounding or _unknown_grounding()
    return StarStoryResponse(
        id=story.id,
        application_id=story.application_id,
        title=story.title,
        situation=story.situation,
        task=story.task,
        action=story.action,
        result=story.result,
        personal_contribution=story.personal_contribution,
        metric_explanation=story.metric_explanation,
        confidence=story.confidence,
        follow_up_questions=list(story.follow_up_questions),
        status=story.status.value,
        origin=story.origin.value,
        claim_pins=[story_claim_pin_response(item) for item in story.claim_pins],
        grounding_status=assessment.status.value,
        grounding_warning=assessment.warning,
        version=story.version,
        created_at=story.created_at,
        updated_at=story.updated_at,
    )


def star_story_page_response(
    value: PagedResult[StoryReadView],
) -> StarStoryPageResponse:
    return StarStoryPageResponse(
        data=[
            StarStorySummaryResponse(
                id=item.story.id,
                application_id=item.story.application_id,
                title=item.story.title,
                confidence=item.story.confidence,
                status=item.story.status.value,
                origin=item.story.origin.value,
                claim_count=len(item.story.claim_pins),
                grounding_status=item.grounding.status.value,
                grounding_warning=item.grounding.warning,
                version=item.story.version,
                created_at=item.story.created_at,
                updated_at=item.story.updated_at,
            )
            for item in value.data
        ],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def defense_map_response(value: DefenseMap) -> DefenseMapResponse:
    return DefenseMapResponse(
        application_id=value.application_id,
        entries=[
            DefenseMapEntryResponse(
                claim_id=item.claim_id,
                claim_text=item.claim_text,
                strong=item.strong,
                status=item.status.value,
                story_ids=list(item.story_ids),
                evidence_revision_ids=list(item.evidence_revision_ids),
                warning=item.warning,
            )
            for item in value.entries
        ],
        defended_count=value.defended_count,
        partial_count=value.partial_count,
        undefended_count=value.undefended_count,
        strong_claim_warning_count=value.strong_claim_warning_count,
    )


def session_context_claim_response(
    value: SessionContextClaim,
) -> SessionContextClaimResponse:
    return SessionContextClaimResponse(
        source_claim_id=value.source_claim_id,
        text=value.text,
        text_sha256=value.text_sha256,
        strong=value.strong,
        requirement_ids=list(value.requirement_ids),
        evidence_pins=[evidence_pin_response(item) for item in value.evidence_pins],
    )


def session_context_response(value: SessionContextSnapshot) -> SessionContextResponse:
    return SessionContextResponse(
        application_id=value.application_id,
        job_id=value.job_id,
        job_version=value.job_version,
        job_title=value.job_title,
        company=value.company,
        resume_version_id=value.resume_version_id,
        resume_version_number=value.resume_version_number,
        claims=[session_context_claim_response(item) for item in value.claims],
        requirements=[
            SessionContextRequirementResponse(
                requirement_id=item.requirement_id,
                text=item.text,
                importance=cast(RequirementImportanceValue, item.importance),
            )
            for item in value.requirements
        ],
        snapshot_sha256=value.snapshot_sha256,
    )


def interview_session_response(
    value: SessionView | SessionReadView,
    grounding: GroundingAssessment | None = None,
) -> InterviewSessionResponse:
    if isinstance(value, SessionReadView):
        grounding = value.grounding
        session_view = value.view
    else:
        session_view = value
    assessment = grounding or _unknown_grounding()
    session = session_view.session
    return InterviewSessionResponse(
        id=session.id,
        application_id=session.application_id,
        title=session.title,
        kind=session.kind.value,
        scheduled_at=session.scheduled_at,
        context=session_context_response(session.context),
        question_count=session_view.question_count,
        note_count=session_view.note_count,
        follow_up_draft_count=session_view.follow_up_draft_count,
        question_bank_generated=session_view.question_bank_generated,
        question_bank_id=session_view.question_bank_id,
        grounding_status=assessment.status.value,
        grounding_warning=assessment.warning,
        version=session.version,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def interview_session_page_response(
    value: PagedResult[SessionReadView],
) -> InterviewSessionPageResponse:
    return InterviewSessionPageResponse(
        data=[
            InterviewSessionSummaryResponse(
                id=item.view.session.id,
                application_id=item.view.session.application_id,
                title=item.view.session.title,
                kind=item.view.session.kind.value,
                scheduled_at=item.view.session.scheduled_at,
                job_title=item.view.session.context.job_title,
                company=item.view.session.context.company,
                question_count=item.view.question_count,
                note_count=item.view.note_count,
                follow_up_draft_count=item.view.follow_up_draft_count,
                question_bank_generated=item.view.question_bank_generated,
                question_bank_id=item.view.question_bank_id,
                grounding_status=item.grounding.status.value,
                grounding_warning=item.grounding.warning,
                version=item.view.session.version,
                created_at=item.view.session.created_at,
                updated_at=item.view.session.updated_at,
            )
            for item in value.data
        ],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def interview_question_response(
    value: InterviewQuestion | QuestionReadView,
    grounding: GroundingAssessment | None = None,
) -> InterviewQuestionResponse:
    if isinstance(value, QuestionReadView):
        grounding = value.grounding
        question = value.question
    else:
        question = value
    assessment = grounding or _unknown_grounding()
    return InterviewQuestionResponse(
        id=question.id,
        session_id=question.session_id,
        ordinal=question.ordinal,
        prompt=question.prompt,
        kind=question.kind.value,
        source_requirement_ids=list(question.source_requirement_ids),
        source_claim_ids=list(question.source_claim_ids),
        generated=question.generated,
        grounding_status=assessment.status.value,
        grounding_warning=assessment.warning,
        created_at=question.created_at,
    )


def interview_question_page_response(
    value: PagedResult[QuestionReadView],
) -> InterviewQuestionPageResponse:
    return InterviewQuestionPageResponse(
        data=[
            InterviewQuestionSummaryResponse(
                id=item.question.id,
                session_id=item.question.session_id,
                ordinal=item.question.ordinal,
                prompt=item.question.prompt,
                kind=item.question.kind.value,
                generated=item.question.generated,
                source_requirement_count=len(item.question.source_requirement_ids),
                source_claim_count=len(item.question.source_claim_ids),
                grounding_status=item.grounding.status.value,
                grounding_warning=item.grounding.warning,
                created_at=item.question.created_at,
            )
            for item in value.data
        ],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def generated_question_bank_response(
    value: tuple[InterviewQuestion, ...],
) -> GeneratedQuestionBankResponse:
    current = GroundingAssessment(GroundingStatus.CURRENT)
    return GeneratedQuestionBankResponse(
        data=[interview_question_response(item, current) for item in value]
    )


def session_note_response(value: InterviewSessionNote) -> InterviewSessionNoteResponse:
    return InterviewSessionNoteResponse(
        id=value.id,
        session_id=value.session_id,
        kind=value.kind.value,
        body=value.body,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def session_note_page_response(
    value: PagedResult[InterviewSessionNote],
) -> InterviewSessionNotePageResponse:
    return InterviewSessionNotePageResponse(
        data=[session_note_response(item) for item in value.data],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def follow_up_draft_response(
    value: FollowUpDraft | FollowUpDraftReadView,
    grounding: GroundingAssessment | None = None,
) -> FollowUpDraftResponse:
    if isinstance(value, FollowUpDraftReadView):
        grounding = value.grounding
        draft = value.draft
    else:
        draft = value
    assessment = grounding or _unknown_grounding()
    return FollowUpDraftResponse(
        id=draft.id,
        session_id=draft.session_id,
        subject=draft.subject,
        body=draft.body,
        source_claims=[session_context_claim_response(item) for item in draft.source_claims],
        grounding_status=assessment.status.value,
        grounding_warning=assessment.warning,
        content_sha256=draft.content_sha256,
        created_at=draft.created_at,
    )


def follow_up_draft_page_response(
    value: PagedResult[FollowUpDraftReadView],
) -> FollowUpDraftPageResponse:
    return FollowUpDraftPageResponse(
        data=[
            FollowUpDraftSummaryResponse(
                id=item.draft.id,
                session_id=item.draft.session_id,
                subject=item.draft.subject,
                body=item.draft.body,
                source_claim_count=len(item.draft.source_claims),
                grounding_status=item.grounding.status.value,
                grounding_warning=item.grounding.warning,
                content_sha256=item.draft.content_sha256,
                created_at=item.draft.created_at,
            )
            for item in value.data
        ],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def _unknown_grounding() -> GroundingAssessment:
    return GroundingAssessment(
        GroundingStatus.UNKNOWN,
        "Current evidence eligibility was not evaluated in this response.",
    )
