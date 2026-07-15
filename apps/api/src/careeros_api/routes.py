"""Phase 0 operational routes."""

from typing import cast

import structlog
from careeros.foundation.database import ReadinessProbe
from fastapi import APIRouter, Request, Response, status

from careeros_api.config import Settings
from careeros_api.constants import SCORING_DISCLAIMER
from careeros_api.schemas import (
    ComponentReadiness,
    HealthResponse,
    MetaResponse,
    ReadinessResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _database(request: Request) -> ReadinessProbe:
    return cast(ReadinessProbe, request.app.state.database)


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
    try:
        await _database(request).ping()
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("database_readiness_failed", error_type=type(exc).__name__)
        return ReadinessResponse(
            status="not_ready",
            service=settings.service_name,
            version=settings.service_version,
            checks={"database": ComponentReadiness(status="unavailable")},
        )

    return ReadinessResponse(
        status="ready",
        service=settings.service_name,
        version=settings.service_version,
        checks={"database": ComponentReadiness(status="ok")},
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
