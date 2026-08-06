"""Stable problem responses that never echo credentials or request bodies."""

from collections.abc import Mapping
from typing import cast

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from rezumi.modules.application_workspace.domain.errors import (
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceError,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceUnavailable,
    ApplicationWorkspaceValidationError,
    ApplicationWorkspaceVersionConflict,
)
from rezumi.modules.career_analytics.domain.errors import (
    CareerAnalyticsConflict,
    CareerAnalyticsError,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsNotFound,
    CareerAnalyticsQuotaExceeded,
    CareerAnalyticsSourceChanged,
    CareerAnalyticsUnavailable,
    CareerAnalyticsValidationError,
    CareerAnalyticsVersionConflict,
)
from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentConflict,
    AttachmentFenced,
    AttachmentIdempotencyConflict,
    AttachmentNotFound,
    AttachmentRejected,
    AttachmentTemporarilyUnavailable,
    AttachmentWorkflowError,
)
from rezumi.modules.career_record.domain.errors import (
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
from rezumi.modules.change_studio.domain.errors import (
    ChangeStudioConflict,
    ChangeStudioError,
    ChangeStudioIdempotencyConflict,
    ChangeStudioNotFound,
    ChangeStudioUnavailable,
    ChangeStudioValidationError,
    ChangeStudioVersionConflict,
    GroundingFailed,
    ProviderOutputRejected,
)
from rezumi.modules.identity.domain.errors import (
    AuthenticationRequired,
    CsrfRejected,
    CurrentPasswordRejected,
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
from rezumi.modules.job_match.domain.errors import (
    JobImportRejected,
    JobMatchConflict,
    JobMatchError,
    JobMatchIdempotencyConflict,
    JobMatchNotFound,
    JobMatchUnavailable,
    JobMatchValidationError,
    JobMatchVersionConflict,
)
from rezumi.modules.networking.domain.errors import (
    NetworkingConflict,
    NetworkingConsentRequired,
    NetworkingError,
    NetworkingIdempotencyConflict,
    NetworkingLeaseConflict,
    NetworkingNotFound,
    NetworkingQuotaExceeded,
    NetworkingUnavailable,
    NetworkingValidationError,
    NetworkingVersionConflict,
)
from rezumi.modules.resume_builder.domain.errors import (
    ResumeBuilderConflict,
    ResumeBuilderError,
    ResumeBuilderIdempotencyConflict,
    ResumeBuilderNotFound,
    ResumeBuilderUnavailable,
    ResumeBuilderValidationError,
    ResumeBuilderVersionConflict,
    ResumeExportBlocked,
)
from rezumi.modules.resume_health.domain.errors import (
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
from rezumi.modules.role_readiness.domain.errors import (
    RoleReadinessConflict,
    RoleReadinessError,
    RoleReadinessIdempotencyConflict,
    RoleReadinessNotFound,
    RoleReadinessUnavailable,
    RoleReadinessValidationError,
    RoleReadinessVersionConflict,
)

from rezumi_api.config import Settings
from rezumi_api.cookies import clear_session_cookies
from rezumi_api.modules.resume_health.dependencies import clear_guest_cookies

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
    CurrentPasswordRejected: (
        status.HTTP_400_BAD_REQUEST,
        "Current password rejected",
        "The current password is incorrect.",
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

    @app.exception_handler(ApplicationWorkspaceError)
    async def application_workspace_problem(
        request: Request, exc: ApplicationWorkspaceError
    ) -> JSONResponse:
        status_code, code, title, detail = _application_workspace_problem_details(exc)
        logger.info(
            "application_workspace_request_rejected",
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

    @app.exception_handler(NetworkingError)
    async def networking_problem(request: Request, exc: NetworkingError) -> JSONResponse:
        status_code, code, title, detail = _networking_problem_details(exc)
        logger.info(
            "networking_request_rejected",
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

    @app.exception_handler(CareerAnalyticsError)
    async def career_analytics_problem(
        request: Request,
        exc: CareerAnalyticsError,
    ) -> JSONResponse:
        status_code, code, title, detail = _career_analytics_problem_details(exc)
        logger.info(
            "career_analytics_request_rejected",
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

    @app.exception_handler(RoleReadinessError)
    async def role_readiness_problem(request: Request, exc: RoleReadinessError) -> JSONResponse:
        status_code, code, title, detail = _role_readiness_problem_details(exc)
        logger.info(
            "role_readiness_request_rejected",
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

    @app.exception_handler(JobMatchError)
    async def job_match_problem(request: Request, exc: JobMatchError) -> JSONResponse:
        status_code, code, title, detail = _job_match_problem_details(exc)
        logger.info(
            "job_match_request_rejected",
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

    @app.exception_handler(ChangeStudioError)
    async def change_studio_problem(request: Request, exc: ChangeStudioError) -> JSONResponse:
        status_code, code, title, detail = _change_studio_problem_details(exc)
        logger.info(
            "change_studio_request_rejected",
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

    @app.exception_handler(ResumeBuilderError)
    async def resume_builder_problem(request: Request, exc: ResumeBuilderError) -> JSONResponse:
        status_code, code, title, detail = _resume_builder_problem_details(exc)
        logger.info(
            "resume_builder_request_rejected",
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
            "type": f"https://rezumi.example/problems/{code.replace('_', '-')}",
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


def _application_workspace_problem_details(
    exc: ApplicationWorkspaceError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, ApplicationWorkspaceUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "application_workspace_unavailable",
            "Application workspace unavailable",
            "Application workspace services are temporarily unavailable.",
        )
    if isinstance(exc, ApplicationWorkspaceNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "application_workspace_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, ApplicationWorkspaceVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "application_workspace_version_conflict",
            "Version conflict",
            "This application changed. Refresh and try again.",
        )
    if isinstance(exc, ApplicationWorkspaceIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "application_workspace_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, ApplicationWorkspaceValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "application_workspace_validation_error",
            "Request validation failed",
            "Review the submitted application workspace values.",
        )
    if isinstance(exc, ApplicationWorkspaceConflict):
        return (
            status.HTTP_409_CONFLICT,
            "application_workspace_conflict",
            "Request conflict",
            "The request conflicts with current application workspace state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "application_workspace_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _networking_problem_details(
    exc: NetworkingError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, NetworkingUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "networking_unavailable",
            "Networking workspace unavailable",
            "Networking services are temporarily unavailable.",
        )
    if isinstance(exc, NetworkingNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "networking_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, NetworkingQuotaExceeded):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "networking_quota_exceeded",
            "Networking limit reached",
            "This networking collection has reached its safe storage limit.",
        )
    if isinstance(exc, NetworkingVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "networking_version_conflict",
            "Version conflict",
            "This networking resource changed. Refresh and try again.",
        )
    if isinstance(exc, NetworkingIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "networking_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, NetworkingConsentRequired):
        return (
            status.HTTP_409_CONFLICT,
            "networking_consent_required",
            "Consent required",
            "Record the required consent before continuing.",
        )
    if isinstance(exc, NetworkingLeaseConflict):
        return (
            status.HTTP_409_CONFLICT,
            "networking_lease_conflict",
            "Request conflict",
            "This reminder is already being processed or its lease expired.",
        )
    if isinstance(exc, NetworkingValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "networking_validation_failed",
            "Request validation failed",
            "Review the submitted networking values.",
        )
    if isinstance(exc, NetworkingConflict):
        return (
            status.HTTP_409_CONFLICT,
            "networking_conflict",
            "Request conflict",
            "The request conflicts with current networking state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "networking_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _career_analytics_problem_details(
    exc: CareerAnalyticsError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, CareerAnalyticsQuotaExceeded):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "career_analytics_quota_exceeded",
            "Analytics refresh limit reached",
            "No additional analytics refresh can be queued for this account.",
        )
    if isinstance(exc, CareerAnalyticsUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "career_analytics_unavailable",
            "Career analytics unavailable",
            "Career analytics services are temporarily unavailable.",
        )
    if isinstance(exc, CareerAnalyticsNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "career_analytics_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, CareerAnalyticsVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_analytics_version_conflict",
            "Version conflict",
            "This analytics refresh changed. Refresh and try again.",
        )
    if isinstance(exc, CareerAnalyticsIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_analytics_idempotency_conflict",
            "Request conflict",
            "This request key was already used for different analytics input.",
        )
    if isinstance(exc, CareerAnalyticsSourceChanged):
        return (
            status.HTTP_409_CONFLICT,
            "career_analytics_source_changed",
            "Analytics source changed",
            "The source changed during aggregation. Retry the refresh.",
        )
    if isinstance(exc, CareerAnalyticsValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "career_analytics_validation_failed",
            "Request validation failed",
            "Review the submitted analytics values.",
        )
    if isinstance(exc, CareerAnalyticsConflict):
        return (
            status.HTTP_409_CONFLICT,
            "career_analytics_conflict",
            "Request conflict",
            "The request conflicts with current analytics state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "career_analytics_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _role_readiness_problem_details(
    exc: RoleReadinessError,
) -> tuple[int, str, str, str]:
    if isinstance(exc, RoleReadinessUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "role_readiness_unavailable",
            "Role readiness unavailable",
            "Role readiness services are temporarily unavailable.",
        )
    if isinstance(exc, RoleReadinessNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "role_readiness_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, RoleReadinessVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "role_readiness_version_conflict",
            "Version conflict",
            "This information changed. Refresh and try again.",
        )
    if isinstance(exc, RoleReadinessIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "role_readiness_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, RoleReadinessConflict):
        return (
            status.HTTP_409_CONFLICT,
            "role_readiness_conflict",
            "Request conflict",
            "The request conflicts with current role readiness state.",
        )
    if isinstance(exc, RoleReadinessValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "role_readiness_validation_error",
            "Request validation failed",
            "Review the submitted role readiness values.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "role_readiness_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _job_match_problem_details(exc: JobMatchError) -> tuple[int, str, str, str]:
    if isinstance(exc, JobMatchUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "job_match_unavailable",
            "Job match unavailable",
            "Job match services are temporarily unavailable.",
        )
    if isinstance(exc, JobMatchNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "job_match_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, JobMatchVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "job_match_version_conflict",
            "Version conflict",
            "This information changed. Refresh and try again.",
        )
    if isinstance(exc, JobMatchIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "job_match_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, JobImportRejected):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "job_import_rejected",
            "Job import rejected",
            "This job posting could not be imported safely.",
        )
    if isinstance(exc, JobMatchValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "job_match_validation_error",
            "Request validation failed",
            "Review the submitted job match values.",
        )
    if isinstance(exc, JobMatchConflict):
        return (
            status.HTTP_409_CONFLICT,
            "job_match_conflict",
            "Request conflict",
            "The request conflicts with current job match state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "job_match_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _change_studio_problem_details(exc: ChangeStudioError) -> tuple[int, str, str, str]:
    if isinstance(exc, ChangeStudioUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "change_studio_unavailable",
            "Change Studio unavailable",
            "Change Studio services are temporarily unavailable.",
        )
    if isinstance(exc, ChangeStudioNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "change_studio_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, ChangeStudioVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "change_studio_version_conflict",
            "Version conflict",
            "This information changed. Refresh and try again.",
        )
    if isinstance(exc, ChangeStudioIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "change_studio_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, GroundingFailed):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "grounding_failed",
            "Grounding failed",
            "The submitted change is not grounded in eligible evidence.",
        )
    if isinstance(exc, ProviderOutputRejected):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "provider_output_rejected",
            "Provider output rejected",
            "The AI provider returned output that failed strict validation.",
        )
    if isinstance(exc, ChangeStudioValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "change_studio_validation_error",
            "Request validation failed",
            "Review the submitted Change Studio values.",
        )
    if isinstance(exc, ChangeStudioConflict):
        return (
            status.HTTP_409_CONFLICT,
            "change_studio_conflict",
            "Request conflict",
            "The request conflicts with current Change Studio state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "change_studio_rejected",
        "Request rejected",
        "The request could not be completed.",
    )


def _resume_builder_problem_details(exc: ResumeBuilderError) -> tuple[int, str, str, str]:
    if isinstance(exc, ResumeBuilderUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "resume_builder_unavailable",
            "Resume Builder unavailable",
            "Resume Builder services are temporarily unavailable.",
        )
    if isinstance(exc, ResumeBuilderNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "resume_builder_not_found",
            "Resource not found",
            "The requested resource was not found.",
        )
    if isinstance(exc, ResumeBuilderVersionConflict):
        return (
            status.HTTP_409_CONFLICT,
            "resume_builder_version_conflict",
            "Version conflict",
            "This resume changed. Refresh and try again.",
        )
    if isinstance(exc, ResumeBuilderIdempotencyConflict):
        return (
            status.HTTP_409_CONFLICT,
            "resume_builder_idempotency_conflict",
            "Request conflict",
            "This request key was already used for a different operation.",
        )
    if isinstance(exc, ResumeExportBlocked):
        return (
            status.HTTP_409_CONFLICT,
            "resume_export_blocked",
            "Export blocked",
            "Round-trip verification found a critical issue before download.",
        )
    if isinstance(exc, ResumeBuilderValidationError):
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "resume_builder_validation_error",
            "Request validation failed",
            "Review the submitted resume builder values.",
        )
    if isinstance(exc, ResumeBuilderConflict):
        return (
            status.HTTP_409_CONFLICT,
            "resume_builder_conflict",
            "Request conflict",
            "The request conflicts with current Resume Builder state.",
        )
    return (
        status.HTTP_400_BAD_REQUEST,
        "resume_builder_rejected",
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
