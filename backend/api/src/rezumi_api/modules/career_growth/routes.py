"""Authenticated HTTP delivery for Career Growth and deterministic Career Health."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from rezumi.modules.career_growth.application import (
    CareerGrowthService,
    ConfirmRoadmapSelection,
    CreateCareerReview,
    CreateDevelopmentItem,
    CreateDevelopmentItemFromGap,
    CreateGoal,
    CreateMilestone,
    RequestContext,
    ReviewContent,
    ReviseCareerReview,
    UpdateDevelopmentItem,
    UpdateGoal,
    UpdateMilestone,
)
from rezumi.modules.career_growth.domain import (
    CareerGrowthValidationError,
    DevelopmentKind,
    DevelopmentStatus,
    GoalStatus,
    MilestoneStatus,
    ReviewCadence,
)
from rezumi.modules.identity.domain import AuthenticatedPrincipal

from rezumi_api.conditional_requests import parse_if_match_version
from rezumi_api.modules.identity.dependencies import current_principal, require_authenticated_csrf
from rezumi_api.modules.identity.schemas import ProblemResponse

from .dependencies import career_growth_request_context, career_growth_service
from .presenters import (
    career_growth_insights_response,
    career_health_page_response,
    career_health_response,
    career_review_page_response,
    career_review_response,
    confirm_roadmap_response,
    development_item_page_response,
    development_item_response,
    goal_page_response,
    goal_response,
    milestone_response,
    role_roadmap_response,
)
from .schemas import (
    CareerGrowthInsightsResponse,
    CareerHealthPageResponse,
    CareerHealthResponse,
    CareerReviewCreateRequest,
    CareerReviewPageResponse,
    CareerReviewResponse,
    CareerReviewReviseRequest,
    ConfirmRoadmapRequest,
    ConfirmRoadmapResponse,
    DevelopmentItemCreateRequest,
    DevelopmentItemFromGapCreateRequest,
    DevelopmentItemPageResponse,
    DevelopmentItemResponse,
    DevelopmentItemUpdateRequest,
    GoalCreateRequest,
    GoalMilestoneResponse,
    GoalPageResponse,
    GoalResponse,
    GoalUpdateRequest,
    MilestoneCreateRequest,
    MilestoneUpdateRequest,
    RoleRoadmapResponse,
)

router = APIRouter(prefix="/api/v1/career-growth", tags=["Career Growth"])
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
        raise CareerGrowthValidationError("If-Match is invalid") from exc


def _review_content(
    payload: CareerReviewCreateRequest | CareerReviewReviseRequest,
) -> ReviewContent:
    content = payload.content
    return ReviewContent(
        title=content.title,
        summary=content.summary,
        achievements=content.achievements,
        growth_areas=content.growth_areas,
        next_focus=content.next_focus,
    )


@router.get(
    "/insights",
    response_model=CareerGrowthInsightsResponse,
    operation_id="careerGrowthInsightsGet",
    responses=_PROBLEMS,
)
async def get_insights(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerGrowthInsightsResponse:
    value = await service.get_insights(principal.user_id)
    _private(response)
    return career_growth_insights_response(value)


@router.get(
    "/goals",
    response_model=GoalPageResponse,
    operation_id="careerGrowthGoalsList",
    responses=_PROBLEMS,
)
async def list_goals(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> GoalPageResponse:
    value = await service.list_goals(principal.user_id, cursor=cursor, limit=limit)
    _private(response)
    return goal_page_response(value)


@router.post(
    "/goals",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthGoalCreate",
    responses=_PROBLEMS,
)
async def create_goal(
    payload: GoalCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> GoalResponse:
    value = await service.create_goal(
        principal.user_id,
        CreateGoal(
            title=payload.title,
            description=payload.description,
            status=GoalStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        idempotency_key,
        context,
    )
    _private(response, value.goal.version)
    return goal_response(value)


@router.get(
    "/goals/{goal_id}",
    response_model=GoalResponse,
    operation_id="careerGrowthGoalGet",
    responses=_PROBLEMS,
)
async def get_goal(
    goal_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> GoalResponse:
    value = await service.get_goal(principal.user_id, goal_id)
    _private(response, value.goal.version)
    return goal_response(value)


@router.put(
    "/goals/{goal_id}",
    response_model=GoalResponse,
    operation_id="careerGrowthGoalUpdate",
    responses=_PROBLEMS,
)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> GoalResponse:
    value = await service.update_goal(
        principal.user_id,
        goal_id,
        _expected_version(if_match),
        UpdateGoal(
            title=payload.title,
            description=payload.description,
            status=GoalStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        context,
    )
    _private(response, value.goal.version)
    return goal_response(value)


@router.delete(
    "/goals/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerGrowthGoalDelete",
    responses=_PROBLEMS,
)
async def delete_goal(
    goal_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> None:
    await service.delete_goal(
        principal.user_id,
        goal_id,
        _expected_version(if_match),
        context,
    )
    _private(response)


@router.post(
    "/goals/{goal_id}/milestones",
    response_model=GoalMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthMilestoneCreate",
    responses=_PROBLEMS,
)
async def create_milestone(
    goal_id: UUID,
    payload: MilestoneCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> GoalMilestoneResponse:
    value = await service.create_milestone(
        principal.user_id,
        goal_id,
        CreateMilestone(
            title=payload.title,
            status=MilestoneStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        idempotency_key,
        context,
    )
    _private(response, value.milestone.version)
    return milestone_response(value)


@router.put(
    "/goals/{goal_id}/milestones/{milestone_id}",
    response_model=GoalMilestoneResponse,
    operation_id="careerGrowthMilestoneUpdate",
    responses=_PROBLEMS,
)
async def update_milestone(
    goal_id: UUID,
    milestone_id: UUID,
    payload: MilestoneUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> GoalMilestoneResponse:
    value = await service.update_milestone(
        principal.user_id,
        goal_id,
        milestone_id,
        _expected_version(if_match),
        UpdateMilestone(
            title=payload.title,
            status=MilestoneStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        context,
    )
    _private(response, value.milestone.version)
    return milestone_response(value)


@router.delete(
    "/goals/{goal_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerGrowthMilestoneDelete",
    responses=_PROBLEMS,
)
async def delete_milestone(
    goal_id: UUID,
    milestone_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> None:
    await service.delete_milestone(
        principal.user_id,
        goal_id,
        milestone_id,
        _expected_version(if_match),
        context,
    )
    _private(response)


@router.get(
    "/development-items",
    response_model=DevelopmentItemPageResponse,
    operation_id="careerGrowthDevelopmentItemsList",
    responses=_PROBLEMS,
)
async def list_development_items(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> DevelopmentItemPageResponse:
    value = await service.list_development_items(
        principal.user_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return development_item_page_response(value)


@router.post(
    "/development-items",
    response_model=DevelopmentItemResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthDevelopmentItemCreate",
    responses=_PROBLEMS,
)
async def create_development_item(
    payload: DevelopmentItemCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> DevelopmentItemResponse:
    value = await service.create_development_item(
        principal.user_id,
        CreateDevelopmentItem(
            kind=DevelopmentKind(payload.kind),
            title=payload.title,
            description=payload.description,
            status=DevelopmentStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        idempotency_key,
        context,
    )
    _private(response, value.item.version)
    return development_item_response(value)


@router.post(
    "/development-items/from-gap",
    response_model=DevelopmentItemResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthDevelopmentItemCreateFromGap",
    responses=_PROBLEMS,
)
async def create_development_item_from_gap(
    payload: DevelopmentItemFromGapCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> DevelopmentItemResponse:
    value = await service.create_development_item_from_gap(
        principal.user_id,
        CreateDevelopmentItemFromGap(
            gap_kind=payload.gap_kind,
            label=payload.label,
            role_profile_id=payload.role_profile_id,
        ),
        idempotency_key,
        context,
    )
    _private(response, value.item.version)
    return development_item_response(value)


@router.get(
    "/roadmap",
    response_model=RoleRoadmapResponse | None,
    operation_id="careerGrowthRoadmapGet",
    responses=_PROBLEMS,
)
async def get_role_roadmap(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> RoleRoadmapResponse | None:
    """`None` when no target role can be resolved yet (no saved role, no experience)."""
    value = await service.get_role_roadmap(principal.user_id, context)
    _private(response)
    return role_roadmap_response(value) if value is not None else None


@router.post(
    "/roadmap/confirm",
    response_model=ConfirmRoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthRoadmapConfirm",
    responses=_PROBLEMS,
)
async def confirm_role_roadmap(
    payload: ConfirmRoadmapRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> ConfirmRoadmapResponse:
    values = await service.confirm_roadmap_selection(
        principal.user_id,
        ConfirmRoadmapSelection(
            role_title=payload.role_title,
            included_skill_names=tuple(payload.included_skill_names),
        ),
        context,
    )
    _private(response)
    return confirm_roadmap_response(values)


@router.get(
    "/development-items/{item_id}",
    response_model=DevelopmentItemResponse,
    operation_id="careerGrowthDevelopmentItemGet",
    responses=_PROBLEMS,
)
async def get_development_item(
    item_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> DevelopmentItemResponse:
    value = await service.get_development_item(principal.user_id, item_id)
    _private(response, value.item.version)
    return development_item_response(value)


@router.put(
    "/development-items/{item_id}",
    response_model=DevelopmentItemResponse,
    operation_id="careerGrowthDevelopmentItemUpdate",
    responses=_PROBLEMS,
)
async def update_development_item(
    item_id: UUID,
    payload: DevelopmentItemUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> DevelopmentItemResponse:
    value = await service.update_development_item(
        principal.user_id,
        item_id,
        _expected_version(if_match),
        UpdateDevelopmentItem(
            kind=DevelopmentKind(payload.kind),
            title=payload.title,
            description=payload.description,
            status=DevelopmentStatus(payload.status),
            target_date=payload.target_date,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        context,
    )
    _private(response, value.item.version)
    return development_item_response(value)


@router.delete(
    "/development-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerGrowthDevelopmentItemDelete",
    responses=_PROBLEMS,
)
async def delete_development_item(
    item_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> None:
    await service.delete_development_item(
        principal.user_id,
        item_id,
        _expected_version(if_match),
        context,
    )
    _private(response)


@router.get(
    "/reviews",
    response_model=CareerReviewPageResponse,
    operation_id="careerGrowthReviewsList",
    responses=_PROBLEMS,
)
async def list_reviews(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> CareerReviewPageResponse:
    value = await service.list_reviews(principal.user_id, cursor=cursor, limit=limit)
    _private(response)
    return career_review_page_response(value)


@router.post(
    "/reviews",
    response_model=CareerReviewResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthReviewCreate",
    responses=_PROBLEMS,
)
async def create_review(
    payload: CareerReviewCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerReviewResponse:
    value = await service.create_review(
        principal.user_id,
        CreateCareerReview(
            cadence=ReviewCadence(payload.cadence),
            period_start=payload.period_start,
            period_end=payload.period_end,
            content=_review_content(payload),
            evidence_ids=tuple(payload.evidence_ids),
        ),
        idempotency_key,
        context,
    )
    _private(response, value.review.version)
    return career_review_response(value)


@router.get(
    "/reviews/{review_id}",
    response_model=CareerReviewResponse,
    operation_id="careerGrowthReviewGet",
    responses=_PROBLEMS,
)
async def get_review(
    review_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerReviewResponse:
    value = await service.get_review(principal.user_id, review_id)
    _private(response, value.review.version)
    return career_review_response(value)


@router.post(
    "/reviews/{review_id}/versions",
    response_model=CareerReviewResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthReviewRevise",
    responses=_PROBLEMS,
)
async def revise_review(
    review_id: UUID,
    payload: CareerReviewReviseRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerReviewResponse:
    value = await service.revise_review(
        principal.user_id,
        review_id,
        _expected_version(if_match),
        ReviseCareerReview(
            content=_review_content(payload),
            change_reason=payload.change_reason,
            evidence_ids=tuple(payload.evidence_ids),
        ),
        context,
    )
    _private(response, value.review.version)
    return career_review_response(value)


@router.post(
    "/reviews/{review_id}/finalizations",
    response_model=CareerReviewResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthReviewFinalize",
    responses=_PROBLEMS,
)
async def finalize_review(
    review_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerReviewResponse:
    value = await service.finalize_review(
        principal.user_id,
        review_id,
        _expected_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, value.review.version)
    return career_review_response(value)


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerGrowthReviewDelete",
    responses=_PROBLEMS,
)
async def delete_review(
    review_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> None:
    await service.delete_review(
        principal.user_id,
        review_id,
        _expected_version(if_match),
        context,
    )
    _private(response)


@router.get(
    "/career-health/analyses",
    response_model=CareerHealthPageResponse,
    operation_id="careerGrowthHealthAnalysesList",
    responses=_PROBLEMS,
)
async def list_career_health(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> CareerHealthPageResponse:
    value = await service.list_career_health(
        principal.user_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return career_health_page_response(value)


@router.post(
    "/career-health/analyses",
    response_model=CareerHealthResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerGrowthHealthAnalyze",
    responses=_PROBLEMS,
)
async def analyze_career_health(
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerHealthResponse:
    value = await service.analyze_career_health(
        principal.user_id,
        idempotency_key,
        context,
    )
    _private(response)
    return career_health_response(value)


@router.get(
    "/career-health/analyses/{analysis_id}",
    response_model=CareerHealthResponse,
    operation_id="careerGrowthHealthAnalysisGet",
    responses=_PROBLEMS,
)
async def get_career_health(
    analysis_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> CareerHealthResponse:
    value = await service.get_career_health(principal.user_id, analysis_id)
    _private(response)
    return career_health_response(value)


@router.delete(
    "/career-health/analyses/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerGrowthHealthAnalysisDelete",
    responses=_PROBLEMS,
)
async def delete_career_health(
    analysis_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_growth_request_context)],
    service: Annotated[CareerGrowthService, Depends(career_growth_service)],
) -> None:
    await service.delete_career_health(principal.user_id, analysis_id, context)
    _private(response)
