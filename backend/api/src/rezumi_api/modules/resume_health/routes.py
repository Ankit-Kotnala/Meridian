"""Thin authorized HTTP adapters for Phase 2 Resume Health workflows."""

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from pydantic import AfterValidator, StringConstraints
from rezumi.modules.career_record.application import CareerRecordService
from rezumi.modules.career_record.application.models import (
    CreateSemanticImportProposals,
)
from rezumi.modules.career_record.application.models import (
    RequestContext as CareerRequestContext,
)
from rezumi.modules.career_record.domain import CareerRecordError
from rezumi.modules.identity.application.models import RequestContext
from rezumi.modules.identity.application.ports import AbuseLimiter
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.resume_health.application import ResumeHealthService
from rezumi.modules.resume_health.application.models import (
    AddSemanticEntity,
    AddSemanticField,
    AnalysisView,
    CanonicalSnapshotView,
    ClaimGuestDocument,
    ConfirmSemanticField,
    CorrectionOperation,
    CorrectSemanticField,
    CreateUploadIntent,
    DocumentView,
    FeatureContributionView,
    NewSemanticField,
    ProcessingJobView,
    ReclassifySemanticEntity,
    RemoveSemanticEntity,
    RemoveSemanticField,
    ResumeRequestContext,
    SemanticFieldReclassification,
    SemanticReviewOperation,
    UploadIntentView,
)
from rezumi.modules.resume_health.domain import (
    AnalysisStatus,
    CanonicalBlock,
    CanonicalResume,
    DatePrecision,
    DocumentStatus,
    JobKind,
    JobStatus,
    OwnerScope,
    ProcessingStage,
    ResumeMediaType,
    SemanticEntityKind,
    SemanticFieldType,
)
from rezumi.modules.resume_health.domain.errors import ResumeResourceNotFound

from rezumi_api.client_signal import verified_client_source_key
from rezumi_api.conditional_requests import (
    IF_MATCH_VERSION_PATTERN,
    parse_if_match_version,
)
from rezumi_api.config import Settings
from rezumi_api.constants import SCORING_DISCLAIMER
from rezumi_api.modules.career_record.dependencies import (
    career_record_service,
    career_request_context,
)
from rezumi_api.modules.identity.dependencies import (
    current_principal,
    request_context,
    require_authenticated_csrf,
    require_pre_auth_csrf,
)
from rezumi_api.modules.resume_health.dependencies import (
    GUEST_CAPABILITY_COOKIE,
    GuestCredentials,
    clear_guest_cookies,
    guest_credentials,
    issue_guest_csrf,
    require_guest_csrf,
    set_guest_cookies,
)
from rezumi_api.modules.resume_health.schemas import (
    AddSemanticEntityRequest,
    AddSemanticFieldRequest,
    CanonicalFieldResponse,
    CanonicalResumeResponse,
    CanonicalResumeUpdateRequest,
    CanonicalSectionResponse,
    ClaimGuestDocumentRequest,
    ClaimGuestDocumentResponse,
    ConfirmSemanticFieldRequest,
    CorrectSemanticFieldRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    FinalizeUploadResponse,
    JobAcceptedResponse,
    JobErrorResponse,
    ParserWarningResponse,
    PlainTextResponse,
    ProcessingJobResponse,
    ReadingOrderBlockResponse,
    ReadingOrderResponse,
    ReclassifySemanticEntityRequest,
    RemoveSemanticEntityRequest,
    RemoveSemanticFieldRequest,
    ResumeFindingResponse,
    ResumeHealthComponentResponse,
    ResumeHealthContributionKey,
    ResumeHealthFeatureContributionResponse,
    ResumeHealthFeatureKey,
    ResumeHealthFeatureValueResponse,
    ResumeHealthReportResponse,
    ResumeHealthRequest,
    SemanticEntityResponse,
    SemanticFieldResponse,
    SemanticSourceAnchorResponse,
    SourceSpanResponse,
    UploadIntentRequest,
    UploadIntentResponse,
    UploadPolicyResponse,
)

logger = structlog.get_logger(__name__)


def _prevent_resume_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1",
    tags=["Resume Health"],
    dependencies=[Depends(_prevent_resume_caching)],
)

_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Authentication or guest capability required"},
    status.HTTP_403_FORBIDDEN: {"description": "Mutation protection rejected the request"},
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
    status.HTTP_409_CONFLICT: {"description": "Resource or idempotency conflict"},
    status.HTTP_410_GONE: {"description": "Guest or upload retention expired"},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Document or request rejected"},
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Required processing dependency unavailable"
    },
}

_COMPONENT_LABELS = {
    "machine_readability": "Machine Readability",
    "recruiter_clarity": "Recruiter Clarity",
    "content_impact": "Content Impact",
    "achievement_strength": "Achievement Strength",
    "structure": "Structure",
    "consistency_truth": "Consistency and Truth",
}

_FEATURE_DEFINITIONS: dict[
    ResumeHealthFeatureKey, tuple[str, Literal["count", "boolean", "percentage"]]
] = {
    "text_characters": ("Extractable characters", "count"),
    "page_count": ("Pages", "count"),
    "image_only": ("Image-only document", "boolean"),
    "section_count": ("Sections", "count"),
    "recognized_section_count": ("Recognized sections", "count"),
    "block_count": ("Content blocks", "count"),
    "concise_block_count": ("Concise blocks", "count"),
    "bullet_count": ("Bullets", "count"),
    "action_bullet_count": ("Action-led bullets", "count"),
    "outcome_bullet_count": ("Outcome-bearing bullets", "count"),
    "duplicate_block_count": ("Duplicate blocks", "count"),
    "chronology_signal_count": ("Chronology signals", "count"),
    "warning_count": ("Parser warnings", "count"),
    "reading_order_violation_count": ("Reading-order warnings", "count"),
    "average_confidence_basis_points": ("Parser confidence", "percentage"),
    "semantic_entity_count": ("Typed semantic records", "count"),
    "semantic_field_count": ("Active typed fields", "count"),
    "parsed_semantic_field_count": ("Parser-derived typed fields", "count"),
    "source_anchored_field_count": ("Source-anchored typed fields", "count"),
    "reviewed_semantic_field_count": ("Reviewed typed fields", "count"),
    "date_field_count": ("Typed date fields", "count"),
    "precise_date_field_count": ("Dates with explicit precision", "count"),
}

_CONTRIBUTION_LABELS: dict[ResumeHealthContributionKey, str] = {
    "searchable_text": "Searchable text",
    "parser_confidence": "Parser confidence",
    "reading_order_integrity": "Reading-order integrity",
    "recognized_section_ratio": "Recognized-section ratio",
    "concise_block_ratio": "Concise-block ratio",
    "section_breadth": "Section breadth",
    "chronology_coverage": "Chronology coverage",
    "action_bullet_ratio": "Action-led bullet ratio",
    "outcome_bullet_ratio": "Outcome-bearing bullet ratio",
    "duplicate_content_integrity": "Duplicate-content integrity",
    "page_fit": "Page fit",
    "parser_warning_integrity": "Parser-warning integrity",
    "source_anchor_coverage": "Source-anchor coverage",
    "semantic_breadth": "Semantic record breadth",
    "semantic_review_coverage": "Explicit semantic review coverage",
    "date_precision_coverage": "Date-precision coverage",
}

_COMPONENT_FEATURE_ORDER: dict[str, tuple[ResumeHealthContributionKey, ...]] = {
    "machine_readability": (
        "searchable_text",
        "parser_confidence",
        "reading_order_integrity",
        "recognized_section_ratio",
        "source_anchor_coverage",
    ),
    "recruiter_clarity": (
        "recognized_section_ratio",
        "concise_block_ratio",
        "section_breadth",
        "chronology_coverage",
        "semantic_breadth",
    ),
    "content_impact": (
        "action_bullet_ratio",
        "outcome_bullet_ratio",
        "duplicate_content_integrity",
        "concise_block_ratio",
    ),
    "achievement_strength": (
        "outcome_bullet_ratio",
        "action_bullet_ratio",
        "duplicate_content_integrity",
    ),
    "structure": (
        "section_breadth",
        "recognized_section_ratio",
        "page_fit",
        "concise_block_ratio",
        "semantic_breadth",
    ),
    "consistency_truth": (
        "parser_confidence",
        "parser_warning_integrity",
        "duplicate_content_integrity",
        "chronology_coverage",
        "source_anchor_coverage",
        "semantic_review_coverage",
        "date_precision_coverage",
    ),
}


def resume_health_service(request: Request) -> ResumeHealthService:
    service = getattr(request.app.state, "resume_health_service", None)
    if service is None:
        from rezumi.modules.resume_health.domain.errors import ResumeHealthUnavailable

        raise ResumeHealthUnavailable
    return cast(ResumeHealthService, service)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _account_scope(principal: AuthenticatedPrincipal) -> OwnerScope:
    return OwnerScope(user_id=principal.user_id)


async def _check_upload_rate(request: Request, subject: str) -> None:
    limiter = cast(AbuseLimiter | None, getattr(request.app.state, "security_store", None))
    if limiter is None:
        return
    settings = _settings(request)
    await limiter.check(
        "resume_upload",
        subject,
        settings.resume_upload_rate_limit,
        settings.resume_upload_rate_window_seconds,
    )


async def _check_mutation_rate(
    request: Request,
    action: Literal["resume_correction", "resume_analysis"],
    scope: OwnerScope,
) -> None:
    limiter = cast(AbuseLimiter | None, getattr(request.app.state, "security_store", None))
    if limiter is None:
        return
    settings = _settings(request)
    if action == "resume_correction":
        limit = settings.resume_correction_rate_limit
        window_seconds = settings.resume_correction_rate_window_seconds
    else:
        limit = settings.resume_analysis_rate_limit
        window_seconds = settings.resume_analysis_rate_window_seconds
    await limiter.check(
        action,
        f"{scope.kind}:{scope.owner_id}",
        limit,
        window_seconds,
    )


async def _guest_scope(service: ResumeHealthService, credentials: GuestCredentials) -> OwnerScope:
    return await service.authenticate_guest(credentials.capability)


def _resume_context(context: RequestContext) -> ResumeRequestContext:
    return ResumeRequestContext(
        request_id=context.request_id,
        trace_id=context.trace_id,
    )


_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{8,128}$"


def _idempotency_key(value: str) -> str:
    if re.fullmatch(_IDEMPOTENCY_KEY_PATTERN, value) is None:
        raise ValueError("Idempotency-Key is invalid")
    return value


def _validated_if_match(value: str) -> str:
    parse_if_match_version(value)
    return value


IdempotencyKeyHeader = Annotated[
    str,
    StringConstraints(
        min_length=8,
        max_length=128,
        pattern=_IDEMPOTENCY_KEY_PATTERN,
    ),
    AfterValidator(_idempotency_key),
    Header(
        alias="Idempotency-Key",
        description=(
            "Stable 8-128 character retry key using letters, digits, dot, underscore, "
            "colon, or hyphen."
        ),
    ),
]
IfMatchHeader = Annotated[
    str,
    StringConstraints(min_length=3, max_length=12, pattern=IF_MATCH_VERSION_PATTERN),
    AfterValidator(_validated_if_match),
    Header(
        alias="If-Match",
        description="Quoted positive signed integer resource version, maximum 2147483647.",
    ),
]


def _upload_policy(settings: Settings) -> UploadPolicyResponse:
    return UploadPolicyResponse(
        accepted_media_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        max_bytes=settings.resume_max_upload_bytes,
        max_pages=settings.resume_max_pages,
        guest_retention_hours=settings.resume_guest_retention_hours,
        upload_intent_ttl_seconds=settings.resume_upload_intent_ttl_seconds,
    )


@router.get(
    "/resume-health/upload-policy",
    response_model=UploadPolicyResponse,
    operation_id="getResumeHealthUploadPolicy",
)
async def account_upload_policy(request: Request) -> UploadPolicyResponse:
    return _upload_policy(_settings(request))


@router.get(
    "/guest/resume-health/upload-policy",
    response_model=UploadPolicyResponse,
    operation_id="getGuestResumeHealthUploadPolicy",
)
async def guest_upload_policy(request: Request) -> UploadPolicyResponse:
    return _upload_policy(_settings(request))


@router.post(
    "/uploads/presign",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createResumeUploadIntent",
    responses=_PROBLEMS,
)
async def create_account_upload_intent(
    payload: UploadIntentRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> UploadIntentResponse:
    await _check_upload_rate(request, f"user:{principal.user_id}")
    return _upload_intent_response(
        await service.create_upload_intent(
            _account_scope(principal),
            CreateUploadIntent(
                display_filename=payload.display_filename,
                media_type=ResumeMediaType(payload.media_type),
                expected_size=payload.expected_size_bytes,
            ),
            _resume_context(context),
        )
    )


@router.post(
    "/guest/uploads/presign",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createGuestResumeUploadIntent",
    responses=_PROBLEMS,
)
async def create_guest_upload_intent(
    payload: UploadIntentRequest,
    response: Response,
    request: Request,
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    _csrf: Annotated[None, Depends(require_pre_auth_csrf)],
    context: Annotated[RequestContext, Depends(request_context)],
    raw_capability: Annotated[str | None, Cookie(alias=GUEST_CAPABILITY_COOKIE)] = None,
) -> UploadIntentResponse:
    guest_expires_at: datetime | None = None
    if raw_capability is None:
        await _check_upload_rate(
            request,
            f"guest-client:{verified_client_source_key(request)}",
        )
        issued = await service.begin_guest_session()
        scope = OwnerScope(guest_session_id=issued.session_id)
        guest_expires_at = issued.expires_at
        max_age = max(1, int((issued.expires_at - datetime.now(UTC)).total_seconds()))
        set_guest_cookies(
            response,
            capability=issued.capability_token,
            csrf_token=issue_guest_csrf(),
            max_age_seconds=max_age,
            settings=_settings(request),
        )
    else:
        scope = await service.authenticate_guest(raw_capability)
        await _check_upload_rate(request, f"guest:{scope.guest_session_id}")
    created = await service.create_upload_intent(
        scope,
        CreateUploadIntent(
            display_filename=payload.display_filename,
            media_type=ResumeMediaType(payload.media_type),
            expected_size=payload.expected_size_bytes,
        ),
        _resume_context(context),
    )
    return _upload_intent_response(created, guest_expires_at=guest_expires_at)


async def _finalize(
    service: ResumeHealthService,
    scope: OwnerScope,
    upload_id: UUID,
    idempotency_key: str,
    context: RequestContext,
) -> FinalizeUploadResponse:
    finalized = await service.finalize_upload(
        scope,
        upload_id,
        idempotency_key,
        _resume_context(context),
    )
    job = await service.get_job(scope, finalized.job_id)
    return FinalizeUploadResponse(
        document_id=finalized.document_id,
        job=_job_response(job, guest=scope.guest_session_id is not None),
    )


@router.post(
    "/uploads/{upload_id}/finalize",
    response_model=FinalizeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="finalizeResumeUpload",
    responses=_PROBLEMS,
)
async def finalize_account_upload(
    upload_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> FinalizeUploadResponse:
    _idempotency_key(idempotency_key)
    return await _finalize(
        service,
        _account_scope(principal),
        upload_id,
        idempotency_key,
        context,
    )


@router.post(
    "/guest/uploads/{upload_id}/finalize",
    response_model=FinalizeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="finalizeGuestResumeUpload",
    responses=_PROBLEMS,
)
async def finalize_guest_upload(
    upload_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(require_guest_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> FinalizeUploadResponse:
    _idempotency_key(idempotency_key)
    return await _finalize(
        service,
        await _guest_scope(service, credentials),
        upload_id,
        idempotency_key,
        context,
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    operation_id="listResumeDocuments",
    responses=_PROBLEMS,
)
async def list_documents(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> DocumentListResponse:
    return DocumentListResponse(
        data=[
            _document_summary(item)
            for item in await service.list_documents(_account_scope(principal))
        ]
    )


async def _document(
    service: ResumeHealthService,
    scope: OwnerScope,
    document_id: UUID,
    response: Response,
) -> DocumentResponse:
    document = await service.get_document(scope, document_id)
    canonical: CanonicalResumeResponse | None = None
    if document.status is DocumentStatus.READY:
        try:
            canonical = _canonical_response(await service.get_canonical_resume(scope, document_id))
        except ResumeResourceNotFound:
            canonical = None
    response.headers["ETag"] = f'"{document.version}"'
    response.headers["Cache-Control"] = "no-store"
    return DocumentResponse(
        **_document_summary(document).model_dump(),
        canonical_resume=canonical,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    operation_id="getResumeDocument",
    responses=_PROBLEMS,
)
async def get_document(
    document_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> DocumentResponse:
    return await _document(service, _account_scope(principal), document_id, response)


@router.get(
    "/guest/documents/{document_id}",
    response_model=DocumentResponse,
    operation_id="getGuestResumeDocument",
    responses=_PROBLEMS,
)
async def get_guest_document(
    document_id: UUID,
    response: Response,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> DocumentResponse:
    return await _document(service, await _guest_scope(service, credentials), document_id, response)


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentSummaryResponse,
    operation_id="getResumeDocumentStatus",
    responses=_PROBLEMS,
)
async def get_document_status(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> DocumentSummaryResponse:
    return _document_summary(await service.get_document(_account_scope(principal), document_id))


@router.get(
    "/guest/documents/{document_id}/status",
    response_model=DocumentSummaryResponse,
    operation_id="getGuestResumeDocumentStatus",
    responses=_PROBLEMS,
)
async def get_guest_document_status(
    document_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> DocumentSummaryResponse:
    return _document_summary(
        await service.get_document(await _guest_scope(service, credentials), document_id)
    )


async def _plain_text(
    service: ResumeHealthService, scope: OwnerScope, document_id: UUID
) -> PlainTextResponse:
    return PlainTextResponse(
        document_id=document_id,
        text=await service.get_plain_text(scope, document_id),
    )


@router.get(
    "/documents/{document_id}/plain-text",
    response_model=PlainTextResponse,
    operation_id="getResumeDocumentPlainText",
    responses=_PROBLEMS,
)
async def get_plain_text(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> PlainTextResponse:
    return await _plain_text(service, _account_scope(principal), document_id)


@router.get(
    "/guest/documents/{document_id}/plain-text",
    response_model=PlainTextResponse,
    operation_id="getGuestResumeDocumentPlainText",
    responses=_PROBLEMS,
)
async def get_guest_plain_text(
    document_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> PlainTextResponse:
    return await _plain_text(service, await _guest_scope(service, credentials), document_id)


async def _reading_order(
    service: ResumeHealthService, scope: OwnerScope, document_id: UUID
) -> ReadingOrderResponse:
    blocks = await service.get_reading_order(scope, document_id)
    return ReadingOrderResponse(
        document_id=document_id,
        blocks=[
            ReadingOrderBlockResponse(
                index=index,
                page=block.spans[0].page if block.spans else None,
                text=block.text,
            )
            for index, block in enumerate(blocks)
        ],
    )


@router.get(
    "/documents/{document_id}/reading-order",
    response_model=ReadingOrderResponse,
    operation_id="getResumeDocumentReadingOrder",
    responses=_PROBLEMS,
)
async def get_reading_order(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ReadingOrderResponse:
    return await _reading_order(service, _account_scope(principal), document_id)


@router.get(
    "/guest/documents/{document_id}/reading-order",
    response_model=ReadingOrderResponse,
    operation_id="getGuestResumeDocumentReadingOrder",
    responses=_PROBLEMS,
)
async def get_guest_reading_order(
    document_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ReadingOrderResponse:
    return await _reading_order(service, await _guest_scope(service, credentials), document_id)


async def _correct(
    request: Request,
    service: ResumeHealthService,
    scope: OwnerScope,
    document_id: UUID,
    payload: CanonicalResumeUpdateRequest,
    expected_version: int,
    context: RequestContext,
    response: Response,
    *,
    career_service: CareerRecordService | None = None,
    career_context: CareerRequestContext | None = None,
) -> CanonicalResumeResponse:
    await _check_mutation_rate(request, "resume_correction", scope)
    if payload.fields:
        snapshot = await service.correct_canonical_resume(
            scope,
            document_id,
            expected_revision=expected_version,
            corrections=tuple(
                CorrectionOperation(block_id=field.id, text=field.value) for field in payload.fields
            ),
            context=_resume_context(context),
        )
    else:
        snapshot = await service.review_canonical_semantics(
            scope,
            document_id,
            expected_revision=expected_version,
            operations=tuple(
                _semantic_operation(operation) for operation in payload.semantic_operations
            ),
            confirm_no_changes=payload.confirm_no_changes,
            context=_resume_context(context),
        )
        if career_service is not None and career_context is not None and scope.user_id is not None:
            try:
                await career_service.get_or_create_profile(scope.user_id, career_context)
                await career_service.populate_from_reviewed_snapshot(
                    scope.user_id,
                    CreateSemanticImportProposals(
                        document_id=document_id,
                        snapshot_id=snapshot.id,
                    ),
                    career_context,
                )
            except CareerRecordError:
                pass
    response.headers["ETag"] = f'"{snapshot.revision}"'
    response.headers["Cache-Control"] = "no-store"
    return _canonical_response(snapshot)


@router.patch(
    "/documents/{document_id}/canonical-resume",
    response_model=CanonicalResumeResponse,
    operation_id="correctCanonicalResume",
    responses=_PROBLEMS,
)
async def correct_canonical_resume(
    document_id: UUID,
    payload: CanonicalResumeUpdateRequest,
    request: Request,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    career_service: Annotated[CareerRecordService, Depends(career_record_service)],
    career_context: Annotated[CareerRequestContext, Depends(career_request_context)],
    if_match: IfMatchHeader,
) -> CanonicalResumeResponse:
    return await _correct(
        request,
        service,
        _account_scope(principal),
        document_id,
        payload,
        parse_if_match_version(if_match),
        context,
        response,
        career_service=career_service,
        career_context=career_context,
    )


@router.patch(
    "/guest/documents/{document_id}/canonical-resume",
    response_model=CanonicalResumeResponse,
    operation_id="correctGuestCanonicalResume",
    responses=_PROBLEMS,
)
async def correct_guest_canonical_resume(
    document_id: UUID,
    payload: CanonicalResumeUpdateRequest,
    request: Request,
    response: Response,
    credentials: Annotated[GuestCredentials, Depends(require_guest_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    if_match: IfMatchHeader,
) -> CanonicalResumeResponse:
    return await _correct(
        request,
        service,
        await _guest_scope(service, credentials),
        document_id,
        payload,
        parse_if_match_version(if_match),
        context,
        response,
    )


async def _start_analysis(
    request: Request,
    service: ResumeHealthService,
    scope: OwnerScope,
    payload: ResumeHealthRequest,
    idempotency_key: str,
    context: RequestContext,
) -> JobAcceptedResponse:
    await _check_mutation_rate(request, "resume_analysis", scope)
    job = await service.start_analysis(
        scope,
        payload.document_id,
        _idempotency_key(idempotency_key),
        _resume_context(context),
    )
    return JobAcceptedResponse(job=_job_response(job, guest=scope.guest_session_id is not None))


@router.post(
    "/resume-health",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startResumeHealthAnalysis",
    responses=_PROBLEMS,
)
async def start_resume_health(
    payload: ResumeHealthRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> JobAcceptedResponse:
    return await _start_analysis(
        request, service, _account_scope(principal), payload, idempotency_key, context
    )


@router.post(
    "/guest/resume-health",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startGuestResumeHealthAnalysis",
    responses=_PROBLEMS,
)
async def start_guest_resume_health(
    payload: ResumeHealthRequest,
    request: Request,
    credentials: Annotated[GuestCredentials, Depends(require_guest_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> JobAcceptedResponse:
    return await _start_analysis(
        request,
        service,
        await _guest_scope(service, credentials),
        payload,
        idempotency_key,
        context,
    )


async def _analysis(
    service: ResumeHealthService,
    scope: OwnerScope,
    analysis_id: UUID,
    *,
    limited: bool,
) -> ResumeHealthReportResponse:
    analysis = await service.get_analysis(scope, analysis_id)
    document = await service.get_document(scope, analysis.document_id)
    return _analysis_response(
        analysis,
        expires_at=document.retention_expires_at,
        limited=limited,
    )


@router.get(
    "/resume-health/{analysis_id}",
    response_model=ResumeHealthReportResponse,
    operation_id="getResumeHealthAnalysis",
    responses=_PROBLEMS,
)
async def get_resume_health(
    analysis_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ResumeHealthReportResponse:
    return await _analysis(service, _account_scope(principal), analysis_id, limited=False)


@router.get(
    "/guest/resume-health/{analysis_id}",
    response_model=ResumeHealthReportResponse,
    operation_id="getGuestResumeHealthAnalysis",
    responses=_PROBLEMS,
)
async def get_guest_resume_health(
    analysis_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ResumeHealthReportResponse:
    return await _analysis(
        service,
        await _guest_scope(service, credentials),
        analysis_id,
        limited=True,
    )


async def _job(
    service: ResumeHealthService, scope: OwnerScope, job_id: UUID
) -> ProcessingJobResponse:
    return _job_response(
        await service.get_job(scope, job_id), guest=scope.guest_session_id is not None
    )


@router.get(
    "/processing-jobs/{job_id}",
    response_model=ProcessingJobResponse,
    operation_id="getProcessingJob",
    responses=_PROBLEMS,
)
async def get_processing_job(
    job_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ProcessingJobResponse:
    return await _job(service, _account_scope(principal), job_id)


@router.get(
    "/guest/processing-jobs/{job_id}",
    response_model=ProcessingJobResponse,
    operation_id="getGuestProcessingJob",
    responses=_PROBLEMS,
)
async def get_guest_processing_job(
    job_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> ProcessingJobResponse:
    return await _job(service, await _guest_scope(service, credentials), job_id)


async def _cancel(
    service: ResumeHealthService,
    scope: OwnerScope,
    job_id: UUID,
    context: RequestContext,
) -> ProcessingJobResponse:
    return _job_response(
        await service.cancel_job(scope, job_id, _resume_context(context)),
        guest=scope.guest_session_id is not None,
    )


@router.post(
    "/processing-jobs/{job_id}/cancel",
    response_model=ProcessingJobResponse,
    operation_id="cancelProcessingJob",
    responses=_PROBLEMS,
)
async def cancel_processing_job(
    job_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> ProcessingJobResponse:
    _idempotency_key(idempotency_key)
    return await _cancel(service, _account_scope(principal), job_id, context)


@router.post(
    "/guest/processing-jobs/{job_id}/cancel",
    response_model=ProcessingJobResponse,
    operation_id="cancelGuestProcessingJob",
    responses=_PROBLEMS,
)
async def cancel_guest_processing_job(
    job_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(require_guest_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    idempotency_key: IdempotencyKeyHeader,
) -> ProcessingJobResponse:
    _idempotency_key(idempotency_key)
    return await _cancel(service, await _guest_scope(service, credentials), job_id, context)


async def _delete(
    service: ResumeHealthService,
    scope: OwnerScope,
    document_id: UUID,
    expected_version: int,
    idempotency_key: str,
    context: RequestContext,
) -> JobAcceptedResponse:
    job = await service.request_delete(
        scope,
        document_id,
        expected_version,
        _idempotency_key(idempotency_key),
        _resume_context(context),
    )
    return JobAcceptedResponse(job=_job_response(job, guest=scope.guest_session_id is not None))


@router.delete(
    "/documents/{document_id}",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="deleteResumeDocument",
    responses=_PROBLEMS,
)
async def delete_document(
    document_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> JobAcceptedResponse:
    return await _delete(
        service,
        _account_scope(principal),
        document_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )


@router.delete(
    "/guest/documents/{document_id}",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="deleteGuestResumeDocument",
    responses=_PROBLEMS,
)
async def delete_guest_document(
    document_id: UUID,
    credentials: Annotated[GuestCredentials, Depends(require_guest_csrf)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> JobAcceptedResponse:
    return await _delete(
        service,
        await _guest_scope(service, credentials),
        document_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )


@router.post(
    "/guest/documents/{document_id}/claim",
    response_model=ClaimGuestDocumentResponse,
    operation_id="claimGuestResumeDocument",
    responses=_PROBLEMS,
)
async def claim_guest_document(
    document_id: UUID,
    payload: ClaimGuestDocumentRequest,
    response: Response,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    credentials: Annotated[GuestCredentials, Depends(guest_credentials)],
    service: Annotated[ResumeHealthService, Depends(resume_health_service)],
    context: Annotated[RequestContext, Depends(request_context)],
) -> ClaimGuestDocumentResponse:
    document = await service.claim_guest_document(
        principal.user_id,
        credentials.capability,
        document_id,
        ClaimGuestDocument(
            policy_version=_settings(request).consent_policy_version,
            consent=payload.consent,
        ),
        _resume_context(context),
    )
    clear_guest_cookies(response, _settings(request))
    return ClaimGuestDocumentResponse(document_id=document.id)


def _upload_intent_response(
    view: UploadIntentView, *, guest_expires_at: datetime | None = None
) -> UploadIntentResponse:
    target = view.target
    return UploadIntentResponse(
        upload_id=view.id,
        url=target.url,
        method="PUT",
        headers=dict(target.headers),
        expires_at=view.expires_at,
        guest_expires_at=guest_expires_at,
    )


def _document_summary(view: DocumentView) -> DocumentSummaryResponse:
    statuses: dict[DocumentStatus, str] = {
        DocumentStatus.QUARANTINED: "quarantined",
        DocumentStatus.PROCESSING: "processing",
        DocumentStatus.READY: "reviewReady",
        DocumentStatus.REJECTED: "failed",
        DocumentStatus.FAILED: "failed",
        DocumentStatus.DELETING: "deleting",
        DocumentStatus.DELETED: "cancelled",
    }
    return DocumentSummaryResponse(
        id=view.id,
        display_filename=view.display_filename,
        media_type=view.media_type.value,
        size_bytes=view.size_bytes,
        status=cast(
            Literal["quarantined", "processing", "reviewReady", "failed", "cancelled", "deleting"],
            statuses[view.status],
        ),
        version=view.version,
        current_canonical_resume_id=view.current_snapshot_id,
        latest_analysis_id=view.latest_analysis_id,
        created_at=view.created_at,
        updated_at=view.updated_at,
        expires_at=view.retention_expires_at,
    )


def _canonical_response(view: CanonicalSnapshotView) -> CanonicalResumeResponse:
    original_blocks = _blocks_by_id(view.original_resume)
    sections: list[CanonicalSectionResponse] = []
    for section in view.resume.sections:
        fields: list[CanonicalFieldResponse] = []
        for block in section.blocks:
            original = original_blocks.get(block.id)
            excerpt = original.text if original is not None else block.text
            fields.append(
                CanonicalFieldResponse(
                    id=str(block.id),
                    label=block.kind.value.replace("_", " ").title(),
                    value=block.text,
                    original_value=original.text if original is not None else None,
                    confidence=(block.confidence_basis_points + 50) // 100,
                    source_spans=[
                        SourceSpanResponse(
                            page=span.page,
                            start=span.start,
                            end=span.end,
                            excerpt=excerpt[:240],
                        )
                        for span in block.spans
                    ],
                )
            )
        sections.append(
            CanonicalSectionResponse(
                id=str(section.id),
                kind=section.kind.value,
                title=section.title,
                fields=fields,
            )
        )
    semantics = view.resume.semantics
    source_blocks = _blocks_by_id(
        replace(view.resume, sections=view.resume.source_sections)
        if view.resume.source_sections
        else view.original_resume
    )
    semantic_entities = (
        [
            SemanticEntityResponse(
                id=entity.id,
                kind=entity.kind.value,
                review_state=entity.review_state.value,
                source_section_id=entity.source_section_id,
                fields=[
                    SemanticFieldResponse(
                        id=field.id,
                        name=field.name,
                        field_type=field.field_type.value,
                        value=field.value,
                        confidence=(field.confidence_basis_points + 50) // 100,
                        review_state=field.review_state.value,
                        anchors=[
                            SemanticSourceAnchorResponse(
                                block_id=anchor.block_id,
                                page=anchor.page,
                                start=anchor.start,
                                end=anchor.end,
                                source_sha256=anchor.source_sha256,
                                excerpt=(
                                    _semantic_anchor_excerpt(
                                        source_blocks[anchor.block_id],
                                        anchor.page,
                                        anchor.start,
                                        anchor.end,
                                    )
                                    if anchor.block_id in source_blocks
                                    else ""
                                ),
                            )
                            for anchor in field.anchors
                        ],
                        date_precision=(
                            field.date_precision.value if field.date_precision else None
                        ),
                    )
                    for field in entity.fields
                ],
            )
            for entity in semantics.entities
        ]
        if semantics is not None
        else []
    )
    return CanonicalResumeResponse(
        id=view.id,
        document_id=view.document_id,
        schema_version=view.resume.schema_version,
        version=view.revision,
        sections=sections,
        warnings=[
            ParserWarningResponse(
                code=warning,
                message=_warning_message(warning),
            )
            for warning in view.resume.warnings
        ],
        semantic_schema_version=semantics.schema_version if semantics is not None else None,
        semantic_parser_version=semantics.parser_version if semantics is not None else None,
        semantic_review_state=semantics.review_state.value if semantics is not None else None,
        semantic_entities=semantic_entities,
        semantic_warnings=[
            ParserWarningResponse(
                code=warning,
                message=_warning_message(warning),
            )
            for warning in (semantics.warnings if semantics is not None else ())
        ],
        legacy_upgrade_required=semantics is None,
        corrected_by_user=view.corrected_by_user,
        created_at=view.created_at,
    )


def _semantic_anchor_excerpt(
    block: CanonicalBlock,
    page: int,
    start: int,
    end: int,
) -> str:
    spans = [
        span
        for span in block.spans
        if span.page == page
        and span.start <= start
        and end <= span.end
        and end - span.start <= len(block.text)
    ]
    if len(spans) != 1:
        return ""
    span = spans[0]
    return block.text[start - span.start : end - span.start][:240]


def _semantic_operation(value: object) -> SemanticReviewOperation:
    if isinstance(value, ConfirmSemanticFieldRequest):
        return ConfirmSemanticField(value.field_id)
    if isinstance(value, CorrectSemanticFieldRequest):
        return CorrectSemanticField(
            value.field_id,
            value.value,
            DatePrecision(value.date_precision) if value.date_precision else None,
        )
    if isinstance(value, AddSemanticFieldRequest):
        return AddSemanticField(
            value.entity_id,
            value.name,
            SemanticFieldType(value.field_type),
            value.value,
            DatePrecision(value.date_precision) if value.date_precision else None,
        )
    if isinstance(value, RemoveSemanticFieldRequest):
        return RemoveSemanticField(value.field_id)
    if isinstance(value, ReclassifySemanticEntityRequest):
        return ReclassifySemanticEntity(
            value.entity_id,
            SemanticEntityKind(value.kind),
            tuple(
                SemanticFieldReclassification(field.field_id, field.name) for field in value.fields
            ),
        )
    if isinstance(value, AddSemanticEntityRequest):
        return AddSemanticEntity(
            SemanticEntityKind(value.kind),
            tuple(
                NewSemanticField(
                    field.name,
                    SemanticFieldType(field.field_type),
                    field.value,
                    DatePrecision(field.date_precision) if field.date_precision else None,
                )
                for field in value.fields
            ),
        )
    if isinstance(value, RemoveSemanticEntityRequest):
        return RemoveSemanticEntity(value.entity_id)
    raise TypeError("unsupported semantic review operation")


def _blocks_by_id(resume: CanonicalResume) -> dict[UUID, CanonicalBlock]:
    return {block.id: block for section in resume.sections for block in section.blocks}


def _warning_message(code: str) -> str:
    messages = {
        "image_only_pdf": ("No searchable text was found. OCR is not enabled for this document."),
        "image_only_document": (
            "The document appears image-only and needs OCR before reliable review."
        ),
        "reading_order_uncertain": (
            "Review the extracted reading order before relying on this content."
        ),
        "low_parser_confidence": (
            "Some content could not be classified confidently. Review it carefully."
        ),
        "dates_uncertain": "Some dates could not be interpreted confidently.",
        "table_heavy_layout": (
            "This document relies heavily on tables. Verify the reading order before reuse."
        ),
        "multi_column_layout": (
            "Multiple text columns were detected. Verify the extracted reading order."
        ),
        "header_footer_excluded": (
            "Repeated header or footer text was excluded from the career content."
        ),
        "bidirectional_controls_removed": (
            "Hidden bidirectional text controls were removed before parsing."
        ),
    }
    return messages.get(code, "Review this parser warning before reusing the content.")


def _safe_error_message(code: str) -> str:
    messages = {
        "upload_too_large": "The uploaded file exceeds the maximum allowed file size.",
        "unsupported_document_type": (
            "The document format is not supported. Please upload a PDF or DOCX file."
        ),
        "document_signature_mismatch": (
            "The file header does not match its expected document type."
        ),
        "polyglot_document_rejected": (
            "The file contains conflicting document formats and was rejected for security."
        ),
        "active_content_rejected": (
            "Documents with embedded scripts or active content are rejected for security."
        ),
        "malformed_pdf": "The PDF file is corrupted or could not be read safely.",
        "encrypted_document": "Password-protected or encrypted documents cannot be processed.",
        "pdf_page_limit_exceeded": "The document exceeds the maximum page limit.",
        "extracted_text_limit_exceeded": "The document contains too much text to process safely.",
        "extracted_block_limit_exceeded": (
            "The document layout contains too many elements to process safely."
        ),
        "extracted_artifact_limit_exceeded": (
            "The extracted document structure exceeded safety limits."
        ),
        "macro_document_rejected": "Word documents with macros are rejected for security.",
        "embedded_object_rejected": (
            "Word documents with embedded objects are rejected for security."
        ),
        "invalid_docx_package": "The DOCX package structure is invalid.",
        "malformed_docx": "The Word document is corrupted or could not be read safely.",
        "semantic_parser_invalid_output": (
            "The document structure could not be mapped to verified career facts."
        ),
        "document_processing_timeout": "Document text extraction timed out.",
        "malware_detected": "The document failed security scanning.",
        "malware_scanner_error": "The security scanner encountered an error.",
        "malware_scanner_unavailable": "Security scanner is temporarily unavailable.",
    }
    return messages.get(code, "Processing could not be completed safely.")


def _job_response(view: ProcessingJobView, *, guest: bool) -> ProcessingJobResponse:
    statuses = {
        JobStatus.QUEUED: "queued",
        JobStatus.RUNNING: "running",
        JobStatus.SUCCEEDED: "succeeded",
        JobStatus.FAILED: "failed",
        JobStatus.CANCELLED: "cancelled",
        JobStatus.DEAD_LETTERED: "deadLettered",
    }
    stages = {
        ProcessingStage.QUEUED: "queued",
        ProcessingStage.ADMISSION: "admission",
        ProcessingStage.MALWARE_SCAN: "malwareScan",
        ProcessingStage.EXTRACTION: "extraction",
        ProcessingStage.CANONICALIZATION: "canonicalization",
        ProcessingStage.ANALYSIS: "analysis",
        ProcessingStage.COMPLETE: "complete",
        ProcessingStage.CLEANUP: "cleanup",
    }
    result_type: Literal["document", "analysis"] | None = None
    result_url: str | None = None
    if view.result_id is not None and view.status is JobStatus.SUCCEEDED:
        prefix = "/api/v1/guest" if guest else "/api/v1"
        if view.kind is JobKind.ANALYZE:
            result_type = "analysis"
            result_url = f"{prefix}/resume-health/{view.result_id}"
        elif view.kind is JobKind.PARSE:
            result_type = "document"
            result_url = f"{prefix}/documents/{view.document_id}"
    error = None
    if view.safe_error_code is not None:
        error = JobErrorResponse(
            code=view.safe_error_code,
            retryable=view.retryable,
            message=_safe_error_message(view.safe_error_code),
        )
    return ProcessingJobResponse(
        id=view.id,
        document_id=view.document_id,
        job_type=view.kind.value,
        status=cast(
            Literal["queued", "running", "succeeded", "failed", "cancelled", "deadLettered"],
            statuses[view.status],
        ),
        stage=cast(
            Literal[
                "queued",
                "admission",
                "malwareScan",
                "extraction",
                "canonicalization",
                "analysis",
                "complete",
                "cleanup",
            ],
            stages[view.stage],
        ),
        progress=view.progress,
        attempts=view.attempts,
        result_type=result_type,
        result_id=view.result_id,
        result_url=result_url,
        error=error,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _basis_points_label(value: int) -> str:
    whole, fraction = divmod(value, 100)
    if fraction == 0:
        return f"{whole}%"
    return f"{whole}.{fraction:02d}".rstrip("0") + "%"


def _feature_value_responses(
    values: dict[str, int | bool],
) -> list[ResumeHealthFeatureValueResponse]:
    responses: list[ResumeHealthFeatureValueResponse] = []
    for key, (label, kind) in _FEATURE_DEFINITIONS.items():
        if key not in values:
            continue
        raw_value = values[key]
        if kind == "boolean":
            if not isinstance(raw_value, bool):
                raise ValueError(f"invalid boolean Resume Health feature {key}")
            display_value = "Yes" if raw_value else "No"
        else:
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise ValueError(f"invalid numeric Resume Health feature {key}")
            display_value = (
                _basis_points_label(raw_value) if kind == "percentage" else f"{raw_value:,}"
            )
        responses.append(
            ResumeHealthFeatureValueResponse(
                key=key,
                label=label,
                kind=kind,
                raw_value=raw_value,
                display_value=display_value,
            )
        )
    return responses


def _feature_contribution_responses(
    contributions: tuple[FeatureContributionView, ...], component_code: str
) -> list[ResumeHealthFeatureContributionResponse]:
    by_key = {
        contribution.feature_code: contribution
        for contribution in contributions
        if contribution.component_code == component_code
    }
    responses: list[ResumeHealthFeatureContributionResponse] = []
    for key in _COMPONENT_FEATURE_ORDER.get(component_code, ()):
        contribution = by_key.get(key)
        if contribution is None:
            continue
        responses.append(
            ResumeHealthFeatureContributionResponse(
                key=key,
                label=_CONTRIBUTION_LABELS[key],
                score=(contribution.feature_value_basis_points + 50) // 100,
                raw_score_basis_points=contribution.feature_value_basis_points,
                weight=(contribution.weight_basis_points + 50) // 100,
                raw_weight_basis_points=contribution.weight_basis_points,
                contribution=(contribution.contribution_basis_points + 50) // 100,
                raw_contribution_basis_points=contribution.contribution_basis_points,
            )
        )
    return responses


def _analysis_response(
    view: AnalysisView, *, expires_at: datetime | None, limited: bool
) -> ResumeHealthReportResponse:
    component_views = {component.code: component for component in view.components}
    components: list[ResumeHealthComponentResponse] = []
    for component_code, label in _COMPONENT_LABELS.items():
        component = component_views.get(component_code)
        if component is None:
            continue
        components.append(
            ResumeHealthComponentResponse(
                key=cast(
                    Literal[
                        "machine_readability",
                        "recruiter_clarity",
                        "content_impact",
                        "achievement_strength",
                        "structure",
                        "consistency_truth",
                    ],
                    component_code,
                ),
                label=label,
                score=(component.score_basis_points + 50) // 100,
                raw_score_basis_points=component.score_basis_points,
                weight=component.weight_basis_points // 100,
                contribution=(component.contribution_basis_points + 50) // 100,
                raw_contribution_basis_points=component.contribution_basis_points,
                explanation=component.explanation,
                feature_contributions=_feature_contribution_responses(
                    view.feature_contributions, component_code
                ),
            )
        )
    findings = [
        ResumeFindingResponse(
            id=finding.code,
            severity=finding.severity.value,
            category="quick_win" if finding.quick_win else "issue",
            title=finding.code.replace("_", " ").title(),
            description=finding.message,
            section=_COMPONENT_LABELS.get(finding.component_code),
            action=finding.message if finding.quick_win else None,
        )
        for finding in view.findings
    ]
    if limited:
        findings = findings[:3]
    score_band: Literal["needsAttention", "developing", "strong"] | None = None
    if view.display_score is not None:
        if view.display_score >= 80:
            score_band = "strong"
        elif view.display_score >= 60:
            score_band = "developing"
        else:
            score_band = "needsAttention"
    return ResumeHealthReportResponse(
        id=view.id,
        document_id=view.document_id,
        canonical_resume_id=view.snapshot_id,
        status=(
            "insufficientData" if view.status is AnalysisStatus.INSUFFICIENT_DATA else "complete"
        ),
        score=view.display_score,
        raw_score_basis_points=view.raw_score_basis_points,
        score_band=score_band,
        engine_version=view.engine_version,
        configuration_version=view.configuration_version,
        feature_schema_version=view.feature_schema_version,
        feature_values=_feature_value_responses(view.feature_values),
        feature_set_hash=f"sha256:{view.feature_set_hash.hex()}",
        components=components,
        findings=findings,
        warnings=(
            ["There is not enough reliable extracted text to calculate a score."]
            if view.status is AnalysisStatus.INSUFFICIENT_DATA
            else []
        ),
        disclaimer=SCORING_DISCLAIMER,
        computed_at=view.computed_at,
        expires_at=expires_at,
    )
