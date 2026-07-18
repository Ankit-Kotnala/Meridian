"""Operational, metadata, and versioned product routes."""

from typing import Literal, cast

import structlog
from careeros.foundation.database import ReadinessProbe
from fastapi import APIRouter, Request, Response, status

from careeros_api.career_record_routes import router as career_record_router
from careeros_api.config import Settings
from careeros_api.constants import SCORING_DISCLAIMER
from careeros_api.identity_routes import router as identity_router
from careeros_api.resume_health_routes import router as resume_health_router
from careeros_api.schemas import (
    ComponentReadiness,
    HealthResponse,
    MetaResponse,
    ReadinessResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()
router.include_router(identity_router)
router.include_router(resume_health_router)
router.include_router(career_record_router)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _readiness_dependencies(request: Request) -> dict[str, ReadinessProbe]:
    return cast(dict[str, ReadinessProbe], request.app.state.readiness_dependencies)


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="health",
    tags=["Operations"],
)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without touching external dependencies."""
    settings = _settings(request)
    return HealthResponse(service=settings.service_name, version=settings.service_version)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    operation_id="readiness",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    tags=["Operations"],
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Report whether the API can serve dependency-backed requests."""
    settings = _settings(request)
    checks: dict[str, ComponentReadiness] = {}
    for name, dependency in _readiness_dependencies(request).items():
        try:
            await dependency.ping()
        except Exception as exc:
            checks[name] = ComponentReadiness(status="unavailable")
            logger.warning(
                "dependency_readiness_failed",
                dependency=name,
                error_type=type(exc).__name__,
            )
        else:
            checks[name] = ComponentReadiness(status="ok")

    if any(check.status == "unavailable" for check in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        readiness_status: Literal["ready", "not_ready"] = "not_ready"
    else:
        readiness_status = "ready"

    return ReadinessResponse(
        status=readiness_status,
        service=settings.service_name,
        version=settings.service_version,
        checks=checks,
    )


@router.get(
    "/api/v1/meta",
    response_model=MetaResponse,
    operation_id="metadata",
    tags=["Metadata"],
)
async def metadata(request: Request) -> MetaResponse:
    """Return non-sensitive service metadata for compatible clients."""
    settings = _settings(request)
    return MetaResponse(
        service=settings.service_name,
        version=settings.service_version,
        environment=settings.environment,
        scoring_disclaimer=SCORING_DISCLAIMER,
    )
