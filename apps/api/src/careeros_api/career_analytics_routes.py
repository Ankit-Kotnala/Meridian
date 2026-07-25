"""Authenticated HTTP delivery for private Career Analytics."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from careeros.modules.career_analytics.application import (
    CareerAnalyticsService,
    RefreshAnalytics,
    RequestContext,
)
from careeros.modules.career_analytics.domain import AnalyticsScope
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Header, Query, Response, status

from careeros_api.career_analytics_dependencies import (
    career_analytics_request_context,
    career_analytics_service,
)
from careeros_api.career_analytics_presenters import (
    analytics_refresh_response,
    analytics_report_response,
)
from careeros_api.career_analytics_schemas import (
    AnalyticsRefreshRequest,
    AnalyticsRefreshResponse,
    AnalyticsReportResponse,
    AnalyticsScopeValue,
)
from careeros_api.identity_dependencies import current_principal, require_authenticated_csrf
from careeros_api.identity_schemas import ProblemResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["Career Analytics"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ProblemResponse},
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


def _private(response: Response, *, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


@router.post(
    "/refreshes",
    response_model=AnalyticsRefreshResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="careerAnalyticsRefreshRequest",
    responses=_PROBLEMS,
)
async def request_analytics_refresh(
    payload: AnalyticsRefreshRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_analytics_request_context)],
    service: Annotated[CareerAnalyticsService, Depends(career_analytics_service)],
) -> AnalyticsRefreshResponse:
    value = await service.request_refresh(
        principal.user_id,
        RefreshAnalytics(
            scope=AnalyticsScope(payload.scope),
            window_start=payload.window_start,
            window_end=payload.window_end,
            timezone=payload.timezone,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, version=value.version)
    response.headers["Location"] = f"/api/v1/analytics/refreshes/{value.id}"
    return analytics_refresh_response(value)


@router.get(
    "/refreshes/{job_id}",
    response_model=AnalyticsRefreshResponse,
    operation_id="careerAnalyticsRefreshGet",
    responses=_PROBLEMS,
)
async def get_analytics_refresh(
    job_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerAnalyticsService, Depends(career_analytics_service)],
) -> AnalyticsRefreshResponse:
    value = await service.get_refresh(principal.user_id, job_id)
    _private(response, version=value.version)
    return analytics_refresh_response(value)


@router.get(
    "/report",
    response_model=AnalyticsReportResponse,
    operation_id="careerAnalyticsReportGet",
    responses=_PROBLEMS,
)
async def get_analytics_report(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_analytics_request_context)],
    service: Annotated[CareerAnalyticsService, Depends(career_analytics_service)],
    scope: Annotated[AnalyticsScopeValue, Query()],
    window_start: Annotated[date, Query(alias="windowStart")],
    window_end: Annotated[date, Query(alias="windowEnd")],
    timezone: Annotated[str, Query(min_length=1, max_length=80)] = "UTC",
) -> AnalyticsReportResponse:
    value = await service.get_report(
        principal.user_id,
        scope=AnalyticsScope(scope),
        window_start=window_start,
        window_end=window_end,
        timezone=timezone,
        context=context,
    )
    _private(response)
    return analytics_report_response(value)
