"""Stable problem responses that never echo credentials or request bodies."""

from collections.abc import Mapping
from typing import cast

import structlog
from careeros.modules.career_record.application.attachment_workflow import (
    AttachmentConflict,
    AttachmentFenced,
    AttachmentIdempotencyConflict,
    AttachmentNotFound,
    AttachmentRejected,
    AttachmentTemporarilyUnavailable,
    AttachmentWorkflowError,
)
from careeros.modules.career_record.domain.errors import (
    CareerRecordConflict,
    CareerRecordCursorInvalid,
    CareerRecordError,
    CareerRecordIdempotencyConflict,
    CareerRecordNotFound,
    CareerRecordSourceUnavailable,
    CareerRecordTransitionRejected,
    CareerRecordUnavailable,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
)
from careeros.modules.identity.domain.errors import (
    AuthenticationRequired,
    CsrfRejected,
    EmailVerificationRequired,
    IdentityConflict,
    IdentityError,
    IdentityUnavailable,
    InvalidCredentials,
    InvalidOrExpiredToken,
    OAuthCollision,
    OAuthFlowRejected,
    OAuthUnavailable,
    RateLimited,
    RecentAuthenticationRequired,
    ResourceNotFound,
    VersionConflict,
)
from careeros.modules.resume_health.domain.errors import (
    GuestCapabilityRejected,
    IdempotencyConflict,
    ProcessingCancelled,
    ResumeHealthError,
    ResumeHealthUnavailable,
    ResumeOwnershipDenied,
    ResumeResourceNotFound,
    ResumeStateConflict,
    ResumeVersionConflict,
    RetryableProcessingFailure,
    UnsafeDocument,
    UploadExpired,
    UploadRejected,
)
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from careeros_api.config import Settings
from careeros_api.cookies import clear_session_cookies
from careeros_api.resume_health_dependencies import clear_guest_cookies

logger = structlog.get_logger(__name__)

_ERRORS: Mapping[type[IdentityError], tuple[int, str, str]] = {
    IdentityUnavailable: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Identity service unavailable",
        "Account services are temporarily unavailable.",
    ),
    AuthenticationRequired: (
        status.HTTP_401_UNAUTHORIZED,
        "Authentication required",
        "Sign in to continue.",
    ),
    InvalidCredentials: (
        status.HTTP_401_UNAUTHORIZED,
        "Authentication failed",
        "The email or password is incorrect.",
    ),
    EmailVerificationRequired: (
        status.HTTP_403_FORBIDDEN,
        "Email verification required",
        "Verify your email before signing in.",
    ),
    InvalidOrExpiredToken: (
        status.HTTP_400_BAD_REQUEST,
        "Link unavailable",
        "This link is invalid, expired, or already used.",
    ),
    ResourceNotFound: (
        status.HTTP_404_NOT_FOUND,
        "Resource not found",
        "The requested resource was not found.",
    ),
    VersionConflict: (
        status.HTTP_409_CONFLICT,
        "Version conflict",
        "This information changed. Refresh and try again.",
    ),
    IdentityConflict: (
        status.HTTP_409_CONFLICT,
        "Request conflict",
        "The request conflicts with current account state.",
    ),
    CsrfRejected: (
        status.HTTP_403_FORBIDDEN,
        "Request rejected",
        "Refresh the page and try again.",
    ),
    OAuthUnavailable: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Sign-in provider unavailable",
        "This sign-in method is temporarily unavailable.",
    ),
    OAuthCollision: (
        status.HTTP_409_CONFLICT,
        "Account linking required",
        "Sign in with your existing method before connecting this account.",
    ),
    OAuthFlowRejected: (
        status.HTTP_400_BAD_REQUEST,
        "Sign-in flow rejected",
        "Restart sign-in and try again.",
    ),
    RecentAuthenticationRequired: (
        status.HTTP_403_FORBIDDEN,
        "Recent authentication required",
        "Sign in again before continuing.",
    ),
}


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_problem(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors: list[dict[str, str]] = []
        for error in exc.errors()[:20]:
            location = [str(part) for part in error.get("loc", ()) if part not in {"body", "query"}]
            errors.append(
                {
                    "field": ".".join(location) or "request",
                    "code": "invalid_value",
                    "message": "Review this field.",
                }
            )
        return problem_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            title="Request validation failed",
            detail="Review the highlighted fields.",
            errors=errors,
        )

    @app.exception_handler(IdentityError)
    async def identity_problem(request: Request, exc: IdentityError) -> JSONResponse:
        if isinstance(exc, RateLimited):
            response = problem_response(
                request,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code=exc.code,
                title="Too many requests",
                detail="Wait before trying again.",
            )
            response.headers["Retry-After"] = str(exc.retry_after_seconds)
            return response
        status_code, title, detail = _ERRORS.get(
            type(exc),
            (
                status.HTTP_400_BAD_REQUEST,
                "Request rejected",
                "The request could not be completed.",
            ),
        )
        response = problem_response(
            request,
            status_code=status_code,
            code=exc.code,
            title=title,
            detail=detail,
        )
        if isinstance(exc, AuthenticationRequired):
            clear_session_cookies(response, cast(Settings, request.app.state.settings))
        return response

    @app.exception_handler(ResumeHealthError)
    async def resume_health_problem(request: Request, exc: ResumeHealthError) -> JSONResponse:
        status_code, title, detail = _resume_health_problem_details(exc)
        logger.info(
            "resume_health_request_rejected",
            error_code=exc.code,
            status_code=status_code,
        )
        response = problem_response(
            request,
            status_code=status_code,
            code=exc.code,
            title=title,
            detail=detail,
        )
        if isinstance(exc, GuestCapabilityRejected):
            clear_guest_cookies(response, cast(Settings, request.app.state.settings))
        return response

    @app.exception_handler(CareerRecordError)
    async def career_record_problem(request: Request, exc: CareerRecordError) -> JSONResponse:
        status_code, code, title, detail = _career_record_problem_details(exc)
        logger.info(
            "career_record_request_rejected",
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

    @app.exception_handler(AttachmentWorkflowError)
    async def attachment_problem(request: Request, exc: AttachmentWorkflowError) -> JSONResponse:
        status_code, code, title, detail = _attachment_problem_details(exc)
        logger.info(
            "evidence_attachment_request_rejected",
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

    @app.exception_handler(ValueError)
    async def value_problem(request: Request, exc: ValueError) -> JSONResponse:
        logger.info("request_value_rejected", error_type=type(exc).__name__)
        return problem_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            title="Request validation failed",
            detail="Review the submitted values.",
        )


def problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    request_id = str(getattr(request.state, "request_id", "unavailable"))
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        headers={"Cache-Control": "no-store"},
        content={
            "type": f"https://careeros.example/problems/{code.replace('_', '-')}",
            "title": title,
            "status": status_code,
            "code": code,
            "detail": detail,
            "instance": request.url.path,
            "requestId": request_id,
            "errors": errors or [],
        },
    )


def _resume_health_problem_details(exc: ResumeHealthError) -> tuple[int, str, str]:
    if isinstance(exc, (ResumeResourceNotFound, ResumeOwnershipDenied)):
        return (
            status.HTTP_404_NOT_FOUND,
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, GuestCapabilityRejected):
        return (
            status.HTTP_401_UNAUTHORIZED,
            "Guest check unavailable",
            "This guest check is unavailable or has expired.",
        )
    if isinstance(exc, UploadExpired):
        return (
            status.HTTP_410_GONE,
            "Upload expired",
            "This upload window has expired. Start a new upload.",
        )
    if isinstance(exc, (ResumeVersionConflict, ResumeStateConflict, IdempotencyConflict)):
        return (
            status.HTTP_409_CONFLICT,
            "Request conflict",
            "This resource changed or the request conflicts with its current state.",
        )
    if isinstance(exc, ProcessingCancelled):
        return (
            status.HTTP_409_CONFLICT,
            "Processing cancelled",
            "This processing job was cancelled.",
        )
    if isinstance(exc, (ResumeHealthUnavailable, RetryableProcessingFailure)):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Resume processing unavailable",
            "Resume processing is temporarily unavailable. Try again later.",
        )
    if isinstance(exc, (UploadRejected, UnsafeDocument)):
        if exc.code in {"upload_too_large", "expanded_content_too_large"}:
            status_code = status.HTTP_413_CONTENT_TOO_LARGE
        elif exc.code in {"unsupported_media_type", "signature_mismatch"}:
            status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return (
            status_code,
            "Document rejected",
            "This document could not be accepted safely.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "Request rejected",
        "The request could not be completed.",
    )


def _career_record_problem_details(
    exc: CareerRecordError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, CareerRecordUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "career_record_unavailable",
            "Career record unavailable",
            "Career record services are temporarily unavailable.",
        )
    if isinstance(exc, CareerRecordNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "career_record_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, CareerRecordVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_record_version_conflict",
            "Version conflict",
            "This information changed. Refresh and try again.",
        )
    if isinstance(exc, CareerRecordIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_record_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, CareerRecordSourceUnavailable):
        return (
            status.HTTP_409_CONFLICT,
            "career_record_source_unavailable",
            "Source unavailable",
            "The supporting source is unavailable or no longer matches this scope.",
        )
    if isinstance(exc, CareerRecordTransitionRejected):
        return (
            status.HTTP_409_CONFLICT,
            "career_record_transition_rejected",
            "Request conflict",
            "This action is not allowed in the resource's current state.",
        )
    if isinstance(exc, CareerRecordConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_record_conflict",
            "Request conflict",
            "The request conflicts with current career record state.",
        )
    if isinstance(exc, (CareerRecordValidationError, CareerRecordCursorInvalid)):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "career_record_validation_error",
            "Request validation failed",
            "Review the submitted career record values.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "career_record_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _attachment_problem_details(
    exc: AttachmentWorkflowError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, AttachmentNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "evidence_attachment_not_found",
            "Attachment not found",
            "The requested attachment was not found.",
        )
    if isinstance(exc, AttachmentRejected):
        code = exc.code.value
        if code == "attachment_upload_size_out_of_range":
            status_code = status.HTTP_413_CONTENT_TOO_LARGE
        elif code in {
            "attachment_upload_type_unsupported",
            "attachment_upload_media_type_mismatch",
            "attachment_upload_signature_mismatch",
        }:
            status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return (
            status_code,
            code,
            "Attachment rejected",
            "This attachment could not be accepted safely.",
        )
    if isinstance(exc, AttachmentTemporarilyUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            exc.code.value,
            "Attachment service unavailable",
            "Attachment processing is temporarily unavailable. Try again later.",
        )
    if isinstance(
        exc,
        (AttachmentIdempotencyConflict, AttachmentFenced, AttachmentConflict),
    ):
        return (
            status.HTTP_409_CONFLICT,
            "evidence_attachment_conflict",
            "Attachment request conflict",
            "This attachment changed or the request conflicts with its current state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "evidence_attachment_rejected",
        "Attachment request rejected",
        "The attachment request could not be completed.",
    )
