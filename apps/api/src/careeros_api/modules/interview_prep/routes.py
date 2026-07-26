"""Authenticated HTTP delivery for Phase 9 Interview Prep workflows."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.interview_prep.application import (
    CreateInterviewQuestion,
    CreateInterviewSession,
    CreateSessionNote,
    CreateStarStory,
    GenerateFollowUpDraft,
    InterviewPrepService,
    RequestContext,
    StoryClaimSelection,
    StoryFilter,
    UpdateInterviewSession,
    UpdateSessionNote,
    UpdateStarStory,
)
from careeros.modules.interview_prep.domain import (
    InterviewPrepValidationError,
    InterviewSessionKind,
    QuestionKind,
    SessionNoteKind,
    StoryField,
    StoryOrigin,
    StoryStatus,
)
from fastapi import APIRouter, Depends, Header, Query, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.identity_dependencies import current_principal, require_authenticated_csrf
from careeros_api.identity_schemas import ProblemResponse

from .dependencies import interview_prep_request_context, interview_prep_service
from .presenters import (
    defense_map_response,
    follow_up_draft_page_response,
    follow_up_draft_response,
    generated_question_bank_response,
    interview_question_page_response,
    interview_question_response,
    interview_session_page_response,
    interview_session_response,
    session_note_page_response,
    session_note_response,
    star_story_page_response,
    star_story_response,
)
from .schemas import (
    DefenseMapResponse,
    FollowUpDraftGenerateRequest,
    FollowUpDraftPageResponse,
    FollowUpDraftResponse,
    GeneratedQuestionBankResponse,
    InterviewQuestionCreateRequest,
    InterviewQuestionPageResponse,
    InterviewQuestionResponse,
    InterviewSessionCreateRequest,
    InterviewSessionNotePageResponse,
    InterviewSessionNoteRequest,
    InterviewSessionNoteResponse,
    InterviewSessionPageResponse,
    InterviewSessionResponse,
    InterviewSessionUpdateRequest,
    StarStoryCreateRequest,
    StarStoryPageResponse,
    StarStoryResponse,
    StarStoryUpdateRequest,
)

router = APIRouter(prefix="/api/v1/interview-prep", tags=["Interview Prep"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": ProblemResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


def _expected_version(value: str) -> int:
    try:
        return parse_if_match_version(value)
    except ValueError as exc:
        raise InterviewPrepValidationError("If-Match is invalid") from exc


def _story_selections(
    payload: StarStoryCreateRequest | StarStoryUpdateRequest,
) -> tuple[StoryClaimSelection, ...]:
    return tuple(
        StoryClaimSelection(
            claim_id=item.claim_id,
            field_names=tuple(StoryField(field_name) for field_name in item.field_names),
        )
        for item in payload.claim_selections
    )


@router.get(
    "/stories",
    response_model=StarStoryPageResponse,
    operation_id="interviewPrepStoriesList",
    responses=_PROBLEMS,
)
async def list_stories(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
    application_id: Annotated[UUID | None, Query(alias="applicationId")] = None,
    story_status: Annotated[StoryStatus | None, Query(alias="status")] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> StarStoryPageResponse:
    value = await service.list_story_reads(
        principal.user_id,
        StoryFilter(application_id=application_id, status=story_status),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return star_story_page_response(value)


@router.post(
    "/stories",
    response_model=StarStoryResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepStoryCreate",
    responses=_PROBLEMS,
)
async def create_story(
    payload: StarStoryCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> StarStoryResponse:
    value = await service.create_story(
        principal.user_id,
        CreateStarStory(
            application_id=payload.application_id,
            title=payload.title,
            situation=payload.situation,
            task=payload.task,
            action=payload.action,
            result=payload.result,
            personal_contribution=payload.personal_contribution,
            metric_explanation=payload.metric_explanation,
            confidence=payload.confidence,
            follow_up_questions=tuple(payload.follow_up_questions),
            status=StoryStatus(payload.status),
            origin=StoryOrigin.USER_AUTHORED,
            claim_selections=_story_selections(payload),
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return star_story_response(value)


@router.get(
    "/stories/{story_id}",
    response_model=StarStoryResponse,
    operation_id="interviewPrepStoryGet",
    responses=_PROBLEMS,
)
async def get_story(
    story_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> StarStoryResponse:
    value = await service.get_story_read(principal.user_id, story_id)
    _private(response, value.story.version)
    return star_story_response(value)


@router.patch(
    "/stories/{story_id}",
    response_model=StarStoryResponse,
    operation_id="interviewPrepStoryUpdate",
    responses=_PROBLEMS,
)
async def update_story(
    story_id: UUID,
    payload: StarStoryUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> StarStoryResponse:
    value = await service.update_story(
        principal.user_id,
        story_id,
        UpdateStarStory(
            title=payload.title,
            situation=payload.situation,
            task=payload.task,
            action=payload.action,
            result=payload.result,
            personal_contribution=payload.personal_contribution,
            metric_explanation=payload.metric_explanation,
            confidence=payload.confidence,
            follow_up_questions=tuple(payload.follow_up_questions),
            status=StoryStatus(payload.status),
            claim_selections=_story_selections(payload),
        ),
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response, value.version)
    return star_story_response(value)


@router.delete(
    "/stories/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="interviewPrepStoryDelete",
    responses=_PROBLEMS,
)
async def delete_story(
    story_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> None:
    await service.delete_story(
        principal.user_id,
        story_id,
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response)


@router.get(
    "/applications/{application_id}/defense-map",
    response_model=DefenseMapResponse,
    operation_id="interviewPrepDefenseMapGet",
    responses=_PROBLEMS,
)
async def get_defense_map(
    application_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> DefenseMapResponse:
    value = await service.defense_map(principal.user_id, application_id)
    _private(response)
    return defense_map_response(value)


@router.get(
    "/sessions",
    response_model=InterviewSessionPageResponse,
    operation_id="interviewPrepSessionsList",
    responses=_PROBLEMS,
)
async def list_sessions(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
    application_id: Annotated[UUID | None, Query(alias="applicationId")] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> InterviewSessionPageResponse:
    value = await service.list_session_reads(
        principal.user_id,
        application_id=application_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return interview_session_page_response(value)


@router.post(
    "/sessions",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepSessionCreate",
    responses=_PROBLEMS,
)
async def create_session(
    payload: InterviewSessionCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewSessionResponse:
    value = await service.create_session(
        principal.user_id,
        CreateInterviewSession(
            application_id=payload.application_id,
            title=payload.title,
            kind=InterviewSessionKind(payload.kind),
            scheduled_at=payload.scheduled_at,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.session.version)
    return interview_session_response(value)


@router.get(
    "/sessions/{session_id}",
    response_model=InterviewSessionResponse,
    operation_id="interviewPrepSessionGet",
    responses=_PROBLEMS,
)
async def get_session(
    session_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewSessionResponse:
    value = await service.get_session_read(principal.user_id, session_id)
    _private(response, value.view.session.version)
    return interview_session_response(value)


@router.patch(
    "/sessions/{session_id}",
    response_model=InterviewSessionResponse,
    operation_id="interviewPrepSessionUpdate",
    responses=_PROBLEMS,
)
async def update_session(
    session_id: UUID,
    payload: InterviewSessionUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewSessionResponse:
    value = await service.update_session(
        principal.user_id,
        session_id,
        UpdateInterviewSession(
            title=payload.title,
            kind=InterviewSessionKind(payload.kind),
            scheduled_at=payload.scheduled_at,
        ),
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response, value.session.version)
    return interview_session_response(value)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="interviewPrepSessionDelete",
    responses=_PROBLEMS,
)
async def delete_session(
    session_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> None:
    await service.delete_session(
        principal.user_id,
        session_id,
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response)


@router.get(
    "/sessions/{session_id}/questions",
    response_model=InterviewQuestionPageResponse,
    operation_id="interviewPrepQuestionsList",
    responses=_PROBLEMS,
)
async def list_questions(
    session_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> InterviewQuestionPageResponse:
    value = await service.list_question_reads(
        principal.user_id,
        session_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return interview_question_page_response(value)


@router.get(
    "/sessions/{session_id}/questions/{question_id}",
    response_model=InterviewQuestionResponse,
    operation_id="interviewPrepQuestionGet",
    responses=_PROBLEMS,
)
async def get_question(
    session_id: UUID,
    question_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewQuestionResponse:
    value = await service.get_question_read(
        principal.user_id,
        session_id,
        question_id,
    )
    _private(response)
    return interview_question_response(value)


@router.post(
    "/sessions/{session_id}/questions",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepQuestionCreate",
    responses=_PROBLEMS,
)
async def create_question(
    session_id: UUID,
    payload: InterviewQuestionCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewQuestionResponse:
    value = await service.create_question(
        principal.user_id,
        session_id,
        CreateInterviewQuestion(
            prompt=payload.prompt,
            kind=QuestionKind(payload.kind),
            source_requirement_ids=tuple(payload.source_requirement_ids),
            source_claim_ids=tuple(payload.source_claim_ids),
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return interview_question_response(value)


@router.post(
    "/sessions/{session_id}/questions/generate",
    response_model=GeneratedQuestionBankResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepQuestionBankGenerate",
    responses=_PROBLEMS,
)
async def generate_question_bank(
    session_id: UUID,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> GeneratedQuestionBankResponse:
    value = await service.generate_question_bank(
        principal.user_id,
        session_id,
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return generated_question_bank_response(value)


@router.get(
    "/sessions/{session_id}/notes",
    response_model=InterviewSessionNotePageResponse,
    operation_id="interviewPrepSessionNotesList",
    responses=_PROBLEMS,
)
async def list_notes(
    session_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> InterviewSessionNotePageResponse:
    value = await service.list_notes(
        principal.user_id,
        session_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return session_note_page_response(value)


@router.post(
    "/sessions/{session_id}/notes",
    response_model=InterviewSessionNoteResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepSessionNoteCreate",
    responses=_PROBLEMS,
)
async def create_note(
    session_id: UUID,
    payload: InterviewSessionNoteRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewSessionNoteResponse:
    value = await service.create_note(
        principal.user_id,
        session_id,
        CreateSessionNote(
            kind=SessionNoteKind(payload.kind),
            body=payload.body,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return session_note_response(value)


@router.patch(
    "/sessions/{session_id}/notes/{note_id}",
    response_model=InterviewSessionNoteResponse,
    operation_id="interviewPrepSessionNoteUpdate",
    responses=_PROBLEMS,
)
async def update_note(
    session_id: UUID,
    note_id: UUID,
    payload: InterviewSessionNoteRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> InterviewSessionNoteResponse:
    value = await service.update_note(
        principal.user_id,
        session_id,
        note_id,
        UpdateSessionNote(
            kind=SessionNoteKind(payload.kind),
            body=payload.body,
        ),
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response, value.version)
    return session_note_response(value)


@router.delete(
    "/sessions/{session_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="interviewPrepSessionNoteDelete",
    responses=_PROBLEMS,
)
async def delete_note(
    session_id: UUID,
    note_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> None:
    await service.delete_note(
        principal.user_id,
        session_id,
        note_id,
        expected_version=_expected_version(if_match),
        context=context,
    )
    _private(response)


@router.get(
    "/sessions/{session_id}/follow-up-drafts",
    response_model=FollowUpDraftPageResponse,
    operation_id="interviewPrepFollowUpDraftsList",
    responses=_PROBLEMS,
)
async def list_follow_up_drafts(
    session_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> FollowUpDraftPageResponse:
    value = await service.list_follow_up_draft_reads(
        principal.user_id,
        session_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return follow_up_draft_page_response(value)


@router.get(
    "/sessions/{session_id}/follow-up-drafts/{draft_id}",
    response_model=FollowUpDraftResponse,
    operation_id="interviewPrepFollowUpDraftGet",
    responses=_PROBLEMS,
)
async def get_follow_up_draft(
    session_id: UUID,
    draft_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> FollowUpDraftResponse:
    value = await service.get_follow_up_draft_read(
        principal.user_id,
        session_id,
        draft_id,
    )
    _private(response)
    return follow_up_draft_response(value)


@router.post(
    "/sessions/{session_id}/follow-up-drafts/generate",
    response_model=FollowUpDraftResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="interviewPrepFollowUpDraftGenerate",
    responses=_PROBLEMS,
)
async def generate_follow_up_draft(
    session_id: UUID,
    payload: FollowUpDraftGenerateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(interview_prep_request_context)],
    service: Annotated[InterviewPrepService, Depends(interview_prep_service)],
) -> FollowUpDraftResponse:
    value = await service.generate_follow_up_draft(
        principal.user_id,
        session_id,
        GenerateFollowUpDraft(source_claim_ids=tuple(payload.source_claim_ids)),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return follow_up_draft_response(value)
