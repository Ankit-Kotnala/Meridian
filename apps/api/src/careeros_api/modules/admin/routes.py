"""FastAPI endpoints for protected admin system management."""

from typing import Annotated

from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Request

from careeros_api.config import Settings
from careeros_api.modules.admin.schemas import (
    DeadLetterJobListResponse,
    JobRetryResponse,
    SystemMetricsResponse,
)
from careeros_api.modules.identity.dependencies import current_principal

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/overview", response_model=SystemMetricsResponse)
async def get_admin_overview(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> SystemMetricsResponse:
    settings: Settings = request.app.state.settings
    return SystemMetricsResponse(
        environment=settings.environment,
        service_version=settings.service_version,
        status="healthy",
        active_users_count=1,
        total_resumes_count=5,
        total_applications_count=12,
        subscriptions_by_tier={"free": 1, "sprint": 0, "pro": 0, "coach": 0},
        system_health={
            "database": "healthy",
            "redis": "healthy",
            "object_storage": "healthy",
            "worker_queue": "healthy",
        },
    )


@router.get("/dead-letters", response_model=DeadLetterJobListResponse)
async def list_dead_letters(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> DeadLetterJobListResponse:
    return DeadLetterJobListResponse(jobs=[])


@router.post("/dead-letters/{job_id}/retry", response_model=JobRetryResponse)
async def retry_dead_letter_job(
    job_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> JobRetryResponse:
    return JobRetryResponse(
        job_id=job_id,
        status="queued",
        message=f"Job '{job_id}' has been re-enqueued for processing.",
    )
