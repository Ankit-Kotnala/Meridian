"""Stable, non-sensitive Career Growth problem responses."""

from __future__ import annotations

import structlog
from careeros.modules.career_growth.domain import (
    CareerGrowthConflict,
    CareerGrowthError,
    CareerGrowthIdempotencyConflict,
    CareerGrowthNotFound,
    CareerGrowthQuotaExceeded,
    CareerGrowthUnavailable,
    CareerGrowthValidationError,
    CareerGrowthVersionConflict,
)
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from careeros_api.problems import problem_response

logger = structlog.get_logger(__name__)


def install_career_growth_problem_handler(app: FastAPI) -> None:
    """Install the Phase 9 handler without changing the shared problem registry."""

    @app.exception_handler(CareerGrowthError)
    async def career_growth_problem(request: Request, exc: CareerGrowthError) -> JSONResponse:
        status_code, code, title, detail = career_growth_problem_details(exc)
        logger.info(
            "career_growth_request_rejected",
            error_code=code,
            status_code=status_code,
        )
        return problem_response(
            request,
            status_code=status_code,
            code=code,
            title=title,
            detail=detail,
        )


def career_growth_problem_details(
    exc: CareerGrowthError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, CareerGrowthUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "career_growth_unavailable",
            "Career Growth unavailable",
            "Career Growth services are temporarily unavailable.",
        )
    if isinstance(exc, CareerGrowthNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "career_growth_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, CareerGrowthVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_growth_version_conflict",
            "Version conflict",
            "This Career Growth resource changed. Refresh and try again.",
        )
    if isinstance(exc, CareerGrowthIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_growth_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, CareerGrowthQuotaExceeded):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "career_growth_quota_exceeded",
            "Career Growth limit reached",
            "Remove an existing Career Growth item before creating another.",
        )
    if isinstance(exc, CareerGrowthValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "career_growth_validation_failed",
            "Request validation failed",
            "Review the submitted Career Growth values.",
        )
    if isinstance(exc, CareerGrowthConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_growth_conflict",
            "Request conflict",
            "The request conflicts with current Career Growth state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "career_growth_rejected",
        "Request rejected",
        "The request could not be completed.",
    )
