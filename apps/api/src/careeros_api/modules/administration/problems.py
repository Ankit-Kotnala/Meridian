"""Stable, non-sensitive administration problem responses."""

from __future__ import annotations

import structlog
from careeros.modules.administration.domain import (
    AdministrationConflict,
    AdministrationDenied,
    AdministrationError,
    AdministrationNotFound,
    AdministrationRecentAuthenticationRequired,
    AdministrationUnavailable,
    AdministrationValidationError,
)
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from careeros_api.problems import problem_response

logger = structlog.get_logger(__name__)


def install_administration_problem_handler(app: FastAPI) -> None:
    @app.exception_handler(AdministrationError)
    async def administration_problem(request: Request, exc: AdministrationError) -> JSONResponse:
        status_code, code, title, detail = administration_problem_details(exc)
        logger.info(
            "administration_request_rejected",
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


def administration_problem_details(
    exc: AdministrationError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, AdministrationRecentAuthenticationRequired):
        return (
            status.HTTP_403_FORBIDDEN,
            exc.code,
            "Recent authentication required",
            "Reauthenticate before performing this protected administration action.",
        )
    if isinstance(exc, AdministrationDenied):
        return (
            status.HTTP_403_FORBIDDEN,
            exc.code,
            "Administration access denied",
            "The current account does not have the required operator capability.",
        )
    if isinstance(exc, AdministrationNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            exc.code,
            "Resource not found",
            "The requested administration resource was not found.",
        )
    if isinstance(exc, AdministrationConflict):
        return (
            status.HTTP_409_CONFLICT,
            exc.code,
            "Administration conflict",
            "The requested administration operation conflicts with current state.",
        )
    if isinstance(exc, AdministrationValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.code,
            "Request validation failed",
            "Review the submitted administration values.",
        )
    if isinstance(exc, AdministrationUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            exc.code,
            "Administration unavailable",
            "Protected administration is temporarily unavailable.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        exc.code,
        "Administration request rejected",
        "The administration request could not be completed.",
    )
