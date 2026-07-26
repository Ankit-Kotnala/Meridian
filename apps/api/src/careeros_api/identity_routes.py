"""Thin FastAPI adapters for Phase 1 identity and onboarding use cases."""

from typing import Annotated, Any, Literal, cast
from uuid import UUID

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.models import (
    ConsentView,
    CurrentUser,
    OnboardingView,
    RequestContext,
    SessionSummary,
)
from careeros.modules.identity.domain import (
    AuthenticatedPrincipal,
    ConsentDecision,
    ObservedResumeStatus,
    OnboardingStatus,
    OnboardingStep,
)
from careeros.modules.identity.domain.errors import AuthenticationRequired, OAuthFlowRejected
from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.config import Settings
from careeros_api.cookies import (
    OAUTH_STATE_COOKIE,
    clear_oauth_state_cookie,
    clear_session_cookies,
    set_oauth_state_cookie,
    set_pre_auth_csrf_cookie,
    set_session_cookies,
)
from careeros_api.identity_dependencies import (
    REFRESH_COOKIE,
    current_principal,
    identity_service,
    optional_principal,
    request_context,
    require_authenticated_csrf,
    require_pre_auth_csrf,
    secrets_equal,
)
from careeros_api.identity_schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ConsentListResponse,
    ConsentRequest,
    ConsentResponse,
    CsrfResponse,
    EmailRequest,
    GenericMessage,
    LoginRequest,
    MeResponse,
    MeUpdateRequest,
    OnboardingResponse,
    OnboardingUpdateRequest,
    ProblemResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SecurityActivityListResponse,
    SecurityActivityResponse,
    SessionInfo,
    SessionListResponse,
    SessionSummaryResponse,
    SettingsCapabilitiesResponse,
    VerificationResponse,
    VerifyEmailRequest,
    WireHandoffStatus,
)

router = APIRouter(prefix="/api/v1", tags=["Identity"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}
_GENERIC_EMAIL_MESSAGE = "If the account is eligible, instructions will be sent."


@router.get(
    "/auth/csrf",
    response_model=CsrfResponse,
    operation_id="authCsrf",
    responses=_PROBLEMS,
)
async def csrf_token(
    response: Response,
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
) -> CsrfResponse:
    settings = _settings(request)
    token = service.issue_pre_auth_csrf()
    set_pre_auth_csrf_cookie(response, token, settings)
    response.headers["Cache-Control"] = "no-store"
    return CsrfResponse(csrf_token=token)


@router.post(
    "/auth/register",
    response_model=GenericMessage,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="authRegister",
    responses=_PROBLEMS,
)
async def register(
    payload: RegisterRequest,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> GenericMessage:
    await service.register(str(payload.email), payload.password, payload.display_name, context)
    return GenericMessage(message=_GENERIC_EMAIL_MESSAGE)


@router.post(
    "/auth/verify-email",
    response_model=VerificationResponse,
    operation_id="authVerifyEmail",
    responses=_PROBLEMS,
)
async def verify_email(
    payload: VerifyEmailRequest,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> VerificationResponse:
    await service.verify_email(payload.token, context)
    return VerificationResponse()


@router.post(
    "/auth/resend-verification",
    response_model=GenericMessage,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="authResendVerification",
    responses=_PROBLEMS,
)
async def resend_verification(
    payload: EmailRequest,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> GenericMessage:
    await service.resend_verification(str(payload.email), context)
    return GenericMessage(message=_GENERIC_EMAIL_MESSAGE)


@router.post(
    "/auth/login",
    response_model=AuthResponse,
    operation_id="authLogin",
    responses=_PROBLEMS,
)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> AuthResponse:
    issued = await service.login(str(payload.email), payload.password, context)
    user = await service.get_current_user(issued.principal)
    set_session_cookies(response, issued, _settings(request))
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(
        user=_me(user),
        session=SessionInfo(
            id=issued.principal.session_id,
            expires_at=issued.expires_at,
            authenticated_at=issued.principal.authenticated_at,
            recent_authentication=True,
        ),
    )


@router.post(
    "/auth/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authRefresh",
    responses=_PROBLEMS,
)
async def refresh(
    response: Response,
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    if refresh_cookie is None:
        raise AuthenticationRequired
    issued = await service.refresh(refresh_cookie, context)
    set_session_cookies(response, issued, _settings(request))
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authLogout",
    responses=_PROBLEMS,
)
async def logout(
    response: Response,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> None:
    await service.logout(principal, context)
    clear_session_cookies(response, _settings(request))


@router.post(
    "/auth/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authLogoutAll",
    responses=_PROBLEMS,
)
async def logout_all(
    response: Response,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> None:
    await service.logout_all(principal, context)
    clear_session_cookies(response, _settings(request))


@router.post(
    "/auth/forgot-password",
    response_model=GenericMessage,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="authForgotPassword",
    responses=_PROBLEMS,
)
async def forgot_password(
    payload: EmailRequest,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> GenericMessage:
    await service.forgot_password(str(payload.email), context)
    return GenericMessage(message=_GENERIC_EMAIL_MESSAGE)


@router.post(
    "/auth/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authResetPassword",
    responses=_PROBLEMS,
)
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
) -> None:
    await service.reset_password(payload.token, payload.new_password, context)
    clear_session_cookies(response, _settings(request))


@router.post(
    "/auth/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authChangePassword",
    responses=_PROBLEMS,
)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    request: Request,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> None:
    await service.change_password(
        principal,
        current_password=payload.current_password,
        new_password=payload.new_password,
        context=context,
    )
    clear_session_cookies(response, _settings(request))


@router.get(
    "/auth/sessions",
    response_model=SessionListResponse,
    operation_id="authListSessions",
    responses=_PROBLEMS,
)
async def list_sessions(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IdentityService, Depends(identity_service)],
) -> SessionListResponse:
    return SessionListResponse(
        data=[_session(item) for item in await service.list_sessions(principal)]
    )


@router.delete(
    "/auth/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authRevokeSession",
    responses=_PROBLEMS,
)
async def revoke_session(
    session_id: UUID,
    response: Response,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> None:
    revoked_current = await service.revoke_session(principal, session_id, context)
    if revoked_current:
        clear_session_cookies(response, _settings(request))


@router.get(
    "/auth/google/start",
    status_code=status.HTTP_302_FOUND,
    operation_id="authGoogleStart",
    responses=_PROBLEMS,
)
async def google_start(
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    principal: Annotated[AuthenticatedPrincipal | None, Depends(optional_principal)],
    return_to: Annotated[str, Query(alias="returnTo", min_length=1, max_length=200)] = "/dashboard",
    link: bool = False,
) -> RedirectResponse:
    if not return_to.startswith("/") or return_to.startswith("//"):
        raise ValueError("returnTo must be a local path")
    if link and principal is None:
        raise AuthenticationRequired
    started = await service.start_google_oauth(return_to, principal if link else None)
    response = RedirectResponse(started.authorization_url, status_code=status.HTTP_302_FOUND)
    set_oauth_state_cookie(response, started.state, _settings(request))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get(
    "/auth/google/callback",
    status_code=status.HTTP_302_FOUND,
    operation_id="authGoogleCallback",
    responses=_PROBLEMS,
)
async def google_callback(
    request: Request,
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    principal: Annotated[AuthenticatedPrincipal | None, Depends(optional_principal)],
    code: Annotated[str, Query(min_length=1, max_length=4096)],
    state_value: Annotated[str, Query(alias="state", min_length=20, max_length=256)],
) -> RedirectResponse:
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if state_cookie is None or not secrets_equal(state_cookie, state_value):
        raise OAuthFlowRejected
    completed = await service.complete_google_oauth(code, state_value, context, principal)
    response = RedirectResponse(completed.return_to, status_code=status.HTTP_302_FOUND)
    set_session_cookies(response, completed.session, _settings(request))
    clear_oauth_state_cookie(response, _settings(request))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.delete(
    "/auth/connections/google",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authGoogleDisconnect",
    responses=_PROBLEMS,
)
async def google_disconnect(
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> None:
    await service.disconnect_google(principal, context)


@router.get(
    "/me",
    response_model=MeResponse,
    operation_id="getCurrentUser",
    responses=_PROBLEMS,
)
async def get_me(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IdentityService, Depends(identity_service)],
) -> MeResponse:
    user = await service.get_current_user(principal)
    response.headers["ETag"] = f'"{user.version}"'
    response.headers["Cache-Control"] = "no-store"
    return _me(user)


@router.patch(
    "/me",
    response_model=MeResponse,
    operation_id="updateCurrentUser",
    responses=_PROBLEMS,
)
async def update_me(
    payload: MeUpdateRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> MeResponse:
    user = await service.update_current_user(
        principal,
        expected_version=parse_if_match_version(if_match),
        updates=payload.model_dump(exclude_unset=True),
        context=context,
    )
    response.headers["ETag"] = f'"{user.version}"'
    response.headers["Cache-Control"] = "no-store"
    return _me(user)


@router.get(
    "/onboarding",
    response_model=OnboardingResponse,
    operation_id="getOnboarding",
    responses=_PROBLEMS,
)
async def get_onboarding(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IdentityService, Depends(identity_service)],
) -> OnboardingResponse:
    view = await service.get_onboarding(principal)
    response.headers["ETag"] = f'"{view.version}"'
    response.headers["Cache-Control"] = "no-store"
    return _onboarding(view)


@router.patch(
    "/onboarding",
    response_model=OnboardingResponse,
    operation_id="updateOnboarding",
    responses=_PROBLEMS,
)
async def update_onboarding(
    payload: OnboardingUpdateRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> OnboardingResponse:
    profile_fields = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if key
        in {
            "display_name",
            "target_role",
            "preferred_location",
            "work_model",
            "seniority",
            "industry",
            "language",
            "writing_style",
        }
    }
    view = await service.update_onboarding(
        principal,
        expected_version=parse_if_match_version(if_match),
        current_step=OnboardingStep(_from_wire_step(payload.current_step)),
        skipped_steps=tuple(
            OnboardingStep(_from_wire_step(step)) for step in payload.skipped_steps
        ),
        profile_updates=profile_fields,
        context=context,
    )
    response.headers["ETag"] = f'"{view.version}"'
    response.headers["Cache-Control"] = "no-store"
    return _onboarding(view)


@router.get(
    "/consents",
    response_model=ConsentListResponse,
    operation_id="listConsents",
    responses=_PROBLEMS,
)
async def list_consents(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IdentityService, Depends(identity_service)],
) -> ConsentListResponse:
    return ConsentListResponse(
        data=[_consent(item) for item in await service.list_consents(principal)]
    )


@router.post(
    "/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="recordConsent",
    responses=_PROBLEMS,
)
async def record_consent(
    payload: ConsentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[IdentityService, Depends(identity_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> ConsentResponse:
    item = await service.record_consent(
        principal, _from_wire_consent(payload.purpose), payload.granted, context
    )
    return _consent(item)


@router.get(
    "/settings",
    response_model=SettingsCapabilitiesResponse,
    operation_id="settingsCapabilitiesGet",
    responses=_PROBLEMS,
)
async def get_settings_capabilities(
    request: Request,
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(current_principal),
    ],
    service: Annotated[IdentityService, Depends(identity_service)],
) -> SettingsCapabilitiesResponse:
    account = await service.get_account_security(principal)
    configured = _settings(request)
    response.headers["Cache-Control"] = "no-store"
    return SettingsCapabilitiesResponse(
        has_password=account.has_password,
        google_connected=account.google_connected,
        google_oauth_available=configured.google_oauth_enabled,
        account_export_available=configured.account_export_provider != "disabled",
        account_deletion_available=configured.account_deletion_provider != "disabled",
        billing_available=configured.billing_provider != "disabled",
        guest_resume_retention_hours=configured.resume_guest_retention_hours,
    )


@router.get(
    "/security-activity",
    response_model=SecurityActivityListResponse,
    operation_id="securityActivityList",
    responses=_PROBLEMS,
)
async def list_security_activity(
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(current_principal),
    ],
    service: Annotated[IdentityService, Depends(identity_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SecurityActivityListResponse:
    response.headers["Cache-Control"] = "no-store"
    return SecurityActivityListResponse(
        data=[
            SecurityActivityResponse.model_validate(item, from_attributes=True)
            for item in await service.list_security_activity(
                principal,
                limit=limit,
            )
        ]
    )


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user, from_attributes=True)


def _session(item: SessionSummary) -> SessionSummaryResponse:
    return SessionSummaryResponse.model_validate(item, from_attributes=True)


def _onboarding(view: OnboardingView) -> OnboardingResponse:
    return OnboardingResponse(
        status=_to_wire_status(view.status),
        current_step=_to_wire_step(view.current_step),
        resume_handoff=_to_wire_handoff(view.resume_handoff),
        parsed_review_handoff=_to_wire_handoff(view.parsed_review_handoff),
        latest_resume_document_id=view.latest_resume_document_id,
        resume_safe_error_code=view.resume_safe_error_code,
        skipped_steps=[_to_wire_step(step) for step in view.skipped_steps],
        version=view.version,
        display_name=view.display_name,
        target_role=view.target_role,
        preferred_location=view.preferred_location,
        work_model=cast(Literal["onsite", "hybrid", "remote", "flexible"] | None, view.work_model),
        seniority=cast(
            Literal["entry", "mid", "senior", "lead", "executive"] | None,
            view.seniority,
        ),
        industry=view.industry,
        language=view.language,
        writing_style=cast(Literal["concise", "balanced", "detailed"], view.writing_style),
    )


def _consent(item: ConsentView) -> ConsentResponse:
    reverse = {
        "model_training": "modelTraining",
        "product_analytics": "productAnalytics",
        "product_email": "productEmail",
    }
    return ConsentResponse(
        purpose=cast(
            Literal["modelTraining", "productAnalytics", "productEmail"], reverse[item.purpose]
        ),
        granted=item.decision is ConsentDecision.GRANTED,
        policy_version=item.policy_version,
        recorded_at=item.recorded_at,
    )


def _from_wire_consent(value: str) -> str:
    return {
        "modelTraining": "model_training",
        "productAnalytics": "product_analytics",
        "productEmail": "product_email",
    }[value]


def _to_wire_status(value: OnboardingStatus) -> Literal["inProgress", "completed"]:
    return "inProgress" if value is OnboardingStatus.IN_PROGRESS else "completed"


def _from_wire_step(value: str) -> str:
    return "parsed_review" if value == "parsedReview" else value


def _to_wire_step(
    value: OnboardingStep,
) -> Literal["profile", "resume", "parsedReview", "preferences", "complete"]:
    if value is OnboardingStep.PARSED_REVIEW:
        return "parsedReview"
    return cast(
        Literal["profile", "resume", "parsedReview", "preferences", "complete"],
        value.value,
    )


def _to_wire_handoff(value: ObservedResumeStatus) -> WireHandoffStatus:
    return cast(
        WireHandoffStatus,
        {
            ObservedResumeStatus.NOT_STARTED: "notStarted",
            ObservedResumeStatus.SKIPPED: "skipped",
            ObservedResumeStatus.PROCESSING: "processing",
            ObservedResumeStatus.REVIEW_REQUIRED: "reviewRequired",
            ObservedResumeStatus.REVIEWED: "reviewed",
            ObservedResumeStatus.ANALYSIS_READY: "analysisReady",
            ObservedResumeStatus.FAILED: "failed",
        }[value],
    )
