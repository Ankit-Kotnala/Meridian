"""Stable, non-sensitive organization tenancy problem responses."""

from __future__ import annotations

import structlog
from careeros.modules.organizations.domain import (
    OrganizationConflict,
    OrganizationError,
    OrganizationForbidden,
    OrganizationIdempotencyConflict,
    OrganizationInvitationRejected,
    OrganizationNotFound,
    OrganizationQuotaExceeded,
    OrganizationUnavailable,
    OrganizationValidationError,
    OrganizationVersionConflict,
)
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from careeros_api.problems import problem_response

logger = structlog.get_logger(__name__)


def install_organization_problem_handler(app: FastAPI) -> None:
    @app.exception_handler(OrganizationError)
    async def organization_problem(
        request: Request,
        exc: OrganizationError,
    ) -> JSONResponse:
        status_code, code, title, detail = organization_problem_details(exc)
        logger.info(
            "organization_request_rejected",
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


def organization_problem_details(
    exc: OrganizationError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, OrganizationUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            exc.code,
            "Organization service unavailable",
            "Organization services are temporarily unavailable.",
        )
    if isinstance(exc, OrganizationInvitationRejected):
        return (
            status.HTTP_400_BAD_REQUEST,
            exc.code,
            "Invitation rejected",
            "The invitation is invalid, expired, unavailable, or does not match this account.",
        )
    if isinstance(exc, OrganizationForbidden):
        return (
            status.HTTP_403_FORBIDDEN,
            exc.code,
            "Action not permitted",
            "Your active organization role does not permit this action.",
        )
    if isinstance(exc, OrganizationNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            exc.code,
            "Organization resource not found",
            "The requested organization resource was not found.",
        )
    if isinstance(exc, OrganizationVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            exc.code,
            "Version conflict",
            "The organization resource changed. Refresh it before retrying.",
        )
    if isinstance(exc, OrganizationIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            exc.code,
            "Request conflict",
            "This request key was already used for different organization input.",
        )
    if isinstance(exc, OrganizationQuotaExceeded):
        return (
            status.HTTP_409_CONFLICT,
            exc.code,
            "Safety limit reached",
            "This organization operation reached its configured safety limit.",
        )
    if isinstance(exc, OrganizationValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.code,
            "Request validation failed",
            "Review the submitted organization values.",
        )
    if isinstance(exc, OrganizationConflict):
        return (
            status.HTTP_409_CONFLICT,
            exc.code,
            "Request conflict",
            "The request conflicts with current organization state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        exc.code,
        "Request rejected",
        "The organization request could not be completed.",
    )
