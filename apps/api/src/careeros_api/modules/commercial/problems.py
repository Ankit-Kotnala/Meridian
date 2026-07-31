"""Stable, non-sensitive commercial problem responses."""

from __future__ import annotations

import structlog
from careeros.modules.commercial.domain import (
    BillingEventConflict,
    BillingSignatureRejected,
    CommercialConflict,
    CommercialError,
    CommercialIdempotencyConflict,
    CommercialNotFound,
    CommercialUnavailable,
    CommercialValidationError,
)
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from careeros_api.problems import problem_response

logger = structlog.get_logger(__name__)


def install_commercial_problem_handler(app: FastAPI) -> None:
    """Install provider-neutral commercial error mappings."""

    @app.exception_handler(CommercialError)
    async def commercial_problem(request: Request, exc: CommercialError) -> JSONResponse:
        status_code, code, title, detail = commercial_problem_details(exc)
        logger.info(
            "commercial_request_rejected",
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


def commercial_problem_details(
    exc: CommercialError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, CommercialUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "commercial_unavailable",
            "Billing unavailable",
            "Billing requires product-owner configuration or is temporarily unavailable.",
        )
    if isinstance(exc, CommercialNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "commercial_not_found",
            "Resource not found",
            "The requested commercial resource was not found.",
        )
    if isinstance(exc, BillingSignatureRejected):
        return (
            status.HTTP_400_BAD_REQUEST,
            "billing_signature_rejected",
            "Webhook rejected",
            "The billing webhook could not be authenticated.",
        )
    if isinstance(exc, CommercialIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "commercial_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different commercial operation.",
        )
    if isinstance(exc, BillingEventConflict):
        return (
            status.HTTP_409_CONFLICT,
            "billing_event_conflict",
            "Webhook conflict",
            "This billing event identifier was already used with different content.",
        )
    if isinstance(exc, CommercialValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "commercial_validation_failed",
            "Request validation failed",
            "Review the submitted commercial values.",
        )
    if isinstance(exc, CommercialConflict):
        return (
            status.HTTP_409_CONFLICT,
            "commercial_conflict",
            "Request conflict",
            "The request conflicts with current commercial state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "commercial_rejected",
        "Request rejected",
        "The commercial request could not be completed.",
    )
