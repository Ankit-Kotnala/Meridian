"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database, ReadinessProbe
from careeros.foundation.observability import configure_logging
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from careeros_api.config import Settings, get_settings
from careeros_api.middleware import install_request_context_middleware
from careeros_api.routes import router

logger = structlog.get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    database: ReadinessProbe | None = None,
) -> FastAPI:
    """Build an application; injectable dependencies keep tests infrastructure-free."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.database = database or Database(
            DatabaseOptions(
                url=resolved_settings.database_url.get_secret_value(),
                pool_size=resolved_settings.database_pool_size,
                max_overflow=resolved_settings.database_max_overflow,
                connect_timeout_seconds=resolved_settings.database_connect_timeout_seconds,
                command_timeout_seconds=resolved_settings.database_command_timeout_seconds,
            )
        )
        logger.info(
            "api_started",
            service=resolved_settings.service_name,
            version=resolved_settings.service_version,
            environment=resolved_settings.environment,
        )
        try:
            yield
        finally:
            await application.state.database.dispose()
            logger.info("api_stopped", service=resolved_settings.service_name)

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    redoc_url = "/redoc" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None
    application = FastAPI(
        title="CareerOS API",
        description="Truth-locked career application operating system API.",
        version=resolved_settings.service_version,
        debug=resolved_settings.debug,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=resolved_settings.trusted_hosts,
    )
    install_request_context_middleware(application)
    application.include_router(router)
    return application
