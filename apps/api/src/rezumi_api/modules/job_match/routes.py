"""Authenticated HTTP delivery for Phase 5 Job Match use cases."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.job_match.application import (
    CreateJob,
    ImportJob,
    JobFilter,
    JobMatchService,
    PrioritizeOpportunity,
    RequestContext,
    SyncFromSource,
    UpdateJob,
)
from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.application.job_catalog_query import JobCatalogQueryService
from rezumi.modules.job_match.domain import (
    EmploymentType,
    JobMatchNotFound,
    JobSourceKind,
    PreferenceFit,
    TailoringEffort,
    WorkModel,
)

from rezumi_api.conditional_requests import parse_if_match_version
from rezumi_api.modules.identity.dependencies import current_principal, require_authenticated_csrf
from rezumi_api.modules.identity.schemas import ProblemResponse
from rezumi_api.modules.job_match.dependencies import (
    job_catalog_query_service,
    job_match_request_context,
    job_match_service,
)
from rezumi_api.modules.job_match.presenters import (
    analysis_response,
    job_catalog_search_response,
    job_page_response,
    job_response,
    opportunity_priority_response,
    requirement_match_page_response,
)
from rezumi_api.modules.job_match.schemas import (
    JobCatalogSearchResponse,
    JobCreateRequest,
    JobImportRequest,
    JobMatchAnalysisResponse,
    JobPageResponse,
    JobResponse,
    JobSyncFromSourceRequest,
    JobSyncFromSourceResponse,
    JobUpdateRequest,
    OpportunityPriorityRequest,
    OpportunityPriorityResponse,
    RequirementMatchPageResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Job Match"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


# Job Match's requirement extractor caps a single extracted requirement at
# 1000 characters. Unstructured third-party prose with no bullet points can
# extract as one long blob, so the text handed to create_job stays well under
# that regardless of how the extractor chunks it. The full listing is never
# lost — source_url still links to it.
_MAX_CATALOG_SOURCE_TEXT_FOR_SAVE = 900


def _job_match_source_text(listing: CatalogJobListing) -> str:
    text = listing.source_text.strip() or listing.title
    if len(text) <= _MAX_CATALOG_SOURCE_TEXT_FOR_SAVE:
        return text
    truncated = text[:_MAX_CATALOG_SOURCE_TEXT_FOR_SAVE].rsplit(" ", 1)[0]
    return truncated or text[:_MAX_CATALOG_SOURCE_TEXT_FOR_SAVE]


@router.get(
    "/jobs",
    response_model=JobPageResponse,
    operation_id="jobsList",
    responses=_PROBLEMS,
)
async def list_jobs(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    source_kind: Annotated[JobSourceKind | None, Query(alias="sourceKind")] = None,
    target_role_id: Annotated[UUID | None, Query(alias="targetRoleId")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> JobPageResponse:
    page = await service.list_jobs(
        principal.user_id,
        JobFilter(query=_clean(q), source_kind=source_kind, target_role_id=target_role_id),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return job_page_response(page)


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobCreate",
    responses=_PROBLEMS,
)
async def create_job(
    payload: JobCreateRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobResponse:
    value = await service.create_job(
        principal.user_id,
        CreateJob(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            work_model=WorkModel(payload.work_model),
            employment_type=EmploymentType(payload.employment_type),
            compensation=payload.compensation,
            application_deadline=payload.application_deadline,
            source_kind=JobSourceKind(payload.source_kind),
            source_url=payload.source_url,
            source_text=payload.source_text,
            target_role_id=payload.target_role_id,
        ),
        idempotency_key,
        context,
    )
    _private(response, value.job.version)
    return job_response(value)


@router.post(
    "/jobs/import",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobImport",
    responses=_PROBLEMS,
)
async def import_job(
    payload: JobImportRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobResponse:
    value = await service.import_job(
        principal.user_id,
        ImportJob(url=str(payload.url), target_role_id=payload.target_role_id),
        idempotency_key,
        context,
    )
    _private(response, value.job.version)
    return job_response(value)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    operation_id="jobGet",
    responses=_PROBLEMS,
)
async def get_job(
    job_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobResponse:
    value = await service.get_job(principal.user_id, job_id)
    _private(response, value.job.version)
    return job_response(value)


@router.patch(
    "/jobs/{job_id}",
    response_model=JobResponse,
    operation_id="jobUpdate",
    responses=_PROBLEMS,
)
async def update_job(
    job_id: UUID,
    payload: JobUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobResponse:
    value = await service.update_job(
        principal.user_id,
        job_id,
        parse_if_match_version(if_match),
        UpdateJob(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            work_model=WorkModel(payload.work_model),
            employment_type=EmploymentType(payload.employment_type),
            compensation=payload.compensation,
            application_deadline=payload.application_deadline,
            source_text=payload.source_text,
            target_role_id=payload.target_role_id,
        ),
        context,
    )
    _private(response, value.job.version)
    return job_response(value)


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="jobDelete",
    responses=_PROBLEMS,
)
async def delete_job(
    job_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> None:
    await service.delete_job(principal.user_id, job_id, parse_if_match_version(if_match), context)
    _private(response)


@router.post(
    "/jobs/{job_id}/analyze",
    response_model=JobMatchAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobAnalyze",
    responses=_PROBLEMS,
)
async def analyze_job(
    job_id: UUID,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobMatchAnalysisResponse:
    value = await service.analyze_job(principal.user_id, job_id, idempotency_key, context)
    _private(response)
    return analysis_response(value)


@router.get(
    "/job-match-analyses/{analysis_id}",
    response_model=JobMatchAnalysisResponse,
    operation_id="jobMatchAnalysisGet",
    responses=_PROBLEMS,
)
async def get_job_match_analysis(
    analysis_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobMatchAnalysisResponse:
    value = await service.get_analysis(principal.user_id, analysis_id)
    _private(response)
    return analysis_response(value)


@router.get(
    "/job-match-analyses/{analysis_id}/requirements",
    response_model=RequirementMatchPageResponse,
    operation_id="jobMatchRequirementsList",
    responses=_PROBLEMS,
)
async def list_job_match_requirements(
    analysis_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> RequirementMatchPageResponse:
    value = await service.get_analysis(principal.user_id, analysis_id)
    _private(response)
    return requirement_match_page_response(value)


@router.post(
    "/jobs/{job_id}/opportunity-priority",
    response_model=OpportunityPriorityResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="opportunityPriorityCreate",
    responses=_PROBLEMS,
)
async def create_opportunity_priority(
    job_id: UUID,
    payload: OpportunityPriorityRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> OpportunityPriorityResponse:
    value = await service.prioritize_opportunity(
        principal.user_id,
        job_id,
        PrioritizeOpportunity(
            analysis_id=payload.analysis_id,
            user_interest=payload.user_interest,
            career_direction_fit=payload.career_direction_fit,
            compensation_fit=PreferenceFit(payload.compensation_fit),
            location_fit=PreferenceFit(payload.location_fit),
            work_model_fit=PreferenceFit(payload.work_model_fit),
            tailoring_effort=TailoringEffort(payload.tailoring_effort),
            existing_contacts=payload.existing_contacts,
        ),
        idempotency_key,
        context,
    )
    _private(response)
    return opportunity_priority_response(value)


@router.post(
    "/jobs/sync-from-source",
    response_model=JobSyncFromSourceResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobsSyncFromSource",
    responses=_PROBLEMS,
)
async def sync_jobs_from_source(
    payload: JobSyncFromSourceRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobSyncFromSourceResponse:
    result = await service.sync_from_source(
        principal.user_id,
        SyncFromSource(
            platform=payload.platform,
            query=payload.query,
            target_role_id=payload.target_role_id,
        ),
        context=context,
    )
    _private(response)
    return JobSyncFromSourceResponse(
        created=[job_response(record) for record in result.created],
        skipped=result.skipped,
    )


@router.get(
    "/opportunity-priorities/{priority_id}",
    response_model=OpportunityPriorityResponse,
    operation_id="opportunityPriorityGet",
    responses=_PROBLEMS,
)
async def get_opportunity_priority(
    priority_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> OpportunityPriorityResponse:
    value = await service.get_priority(principal.user_id, priority_id)
    _private(response)
    return opportunity_priority_response(value)


@router.get(
    "/job-catalog",
    response_model=JobCatalogSearchResponse,
    operation_id="jobCatalogSearch",
    responses=_PROBLEMS,
)
async def search_job_catalog(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    catalog: Annotated[JobCatalogQueryService, Depends(job_catalog_query_service)],
) -> JobCatalogSearchResponse:
    """Read-only shared listings filtered toward the owner's target role(s).

    Never writes into the owner's own tracked jobs — see
    ``POST /job-catalog/{platform}/{externalId}/save`` for that explicit step.
    """
    result = await catalog.search_for_owner(principal.user_id)
    _private(response)
    return job_catalog_search_response(result)


@router.post(
    "/job-catalog/{platform}/{external_id}/save",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobCatalogSave",
    responses=_PROBLEMS,
)
async def save_job_catalog_listing(
    platform: str,
    external_id: str,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(job_match_request_context)],
    catalog: Annotated[JobCatalogQueryService, Depends(job_catalog_query_service)],
    service: Annotated[JobMatchService, Depends(job_match_service)],
) -> JobResponse:
    """Copy one catalog listing into the owner's own tracked jobs, once.

    Idempotent per (owner, platform, external_id) — saving the same listing
    twice returns the same tracked job rather than creating a duplicate.
    """
    listing = await catalog.get_listing(platform, external_id)
    if listing is None:
        raise JobMatchNotFound
    idempotency_key = f"catalog:{platform}:{external_id}"
    value = await service.create_job(
        principal.user_id,
        CreateJob(
            title=listing.title,
            company=listing.company,
            location=listing.location,
            work_model=WorkModel.REMOTE if listing.remote else WorkModel.UNKNOWN,
            employment_type=EmploymentType.UNKNOWN,
            compensation=None,
            application_deadline=None,
            source_kind=JobSourceKind.URL,
            source_url=listing.application_url,
            source_text=_job_match_source_text(listing),
            external_id=f"{platform}:{external_id}",
        ),
        idempotency_key,
        context,
    )
    _private(response, value.job.version)
    return job_response(value)
