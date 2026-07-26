"""Stable, non-sensitive Interview Prep problem responses."""

from __future__ import annotations

import structlog
from careeros.modules.interview_prep.domain import (
    InterviewPrepConflict,
    InterviewPrepError,
    InterviewPrepIdempotencyConflict,
    InterviewPrepNotFound,
    InterviewPrepQuotaExceeded,
    InterviewPrepUnavailable,
    InterviewPrepValidationError,
    InterviewPrepVersionConflict,
)
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from careeros_api.problems import problem_response

logger = structlog.get_logger(__name__)


def install_interview_prep_problem_handler(app: FastAPI) -> None:
    """Install the Phase 9 handler without expanding the shared problem registry."""

    @app.exception_handler(InterviewPrepError)
    async def interview_prep_problem(request: Request, exc: InterviewPrepError) -> JSONResponse:
        status_code, code, title, detail = interview_prep_problem_details(exc)
        logger.info(
            "interview_prep_request_rejected",
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


def interview_prep_problem_details(
    exc: InterviewPrepError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, InterviewPrepUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "interview_prep_unavailable",
            "Interview preparation unavailable",
            "Interview preparation services are temporarily unavailable.",
        )
    if isinstance(exc, InterviewPrepNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "interview_prep_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, InterviewPrepVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "interview_prep_version_conflict",
            "Version conflict",
            "This interview preparation resource changed. Refresh and try again.",
        )
    if isinstance(exc, InterviewPrepIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "interview_prep_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, InterviewPrepQuotaExceeded):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "interview_prep_quota_exceeded",
            "Interview preparation limit reached",
            "Remove an existing interview preparation item before creating another.",
        )
    if isinstance(exc, InterviewPrepValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "interview_prep_validation_failed",
            "Request validation failed",
            "Review the submitted interview preparation values.",
        )
    if isinstance(exc, InterviewPrepConflict):
        return (
            status.HTTP_409_CONFLICT,
            "interview_prep_conflict",
            "Request conflict",
            "The request conflicts with current interview preparation state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "interview_prep_rejected",
        "Request rejected",
        "The request could not be completed.",
    )
