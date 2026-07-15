"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database, ReadinessProbe
from careeros.foundation.observability import configure_logging
from careeros.integrations.email import DisabledEmailSender, SmtpEmailSender, SmtpOptions
from careeros.integrations.oauth import GoogleOAuthOptions, GoogleOAuthProvider
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.ports import (
    GoogleOAuthProvider as GoogleOAuthProviderPort,
)
from careeros.modules.identity.application.service import IdentityPolicy
from careeros.modules.identity.infrastructure.fakes import DisabledGoogleOAuthProvider
from careeros.modules.identity.infrastructure.redis_security import RedisSecurityStore
from careeros.modules.identity.infrastructure.repository import (
    SqlAlchemyIdentityUnitOfWorkFactory,
)
from careeros.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    HmacTokenManager,
    NormalizedEmailValidator,
    SystemClock,
)
from careeros.modules.resume_health.application import (
    DocumentLimits,
    OutboxDispatcher,
    ResumeHealthPolicy,
    ResumeHealthService,
)
from careeros.modules.resume_health.infrastructure import (
    CeleryJobPublisher,
    CeleryPublisherOptions,
    HmacGuestCapabilityManager,
    S3ObjectStorage,
    S3Options,
    SqlAlchemyResumeUnitOfWorkFactory,
)
from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from careeros_api.config import Settings, get_settings
from careeros_api.middleware import RequestBodyLimitMiddleware, install_request_context_middleware
from careeros_api.problems import install_problem_handlers
from careeros_api.routes import router

logger = structlog.get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    database: ReadinessProbe | None = None,
    identity: IdentityService | None = None,
    security_store: RedisSecurityStore | None = None,
    email_sender: SmtpEmailSender | DisabledEmailSender | None = None,
    resume_health: ResumeHealthService | None = None,
    resume_dispatcher: OutboxDispatcher | None = None,
    resume_storage: S3ObjectStorage | None = None,
) -> FastAPI:
    """Build an application; injectable dependencies keep tests infrastructure-free."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_database = database or Database(
            DatabaseOptions(
                url=resolved_settings.database_url.get_secret_value(),
                pool_size=resolved_settings.database_pool_size,
                max_overflow=resolved_settings.database_max_overflow,
                connect_timeout_seconds=resolved_settings.database_connect_timeout_seconds,
                command_timeout_seconds=resolved_settings.database_command_timeout_seconds,
            )
        )
        resolved_security_store = security_store
        resolved_email_sender = email_sender
        resolved_identity = identity
        resolved_resume_health = resume_health
        resolved_resume_dispatcher = resume_dispatcher
        resolved_resume_storage = resume_storage

        if resolved_identity is None and isinstance(resolved_database, Database):
            pepper = resolved_settings.auth_token_pepper.get_secret_value()
            if resolved_security_store is None:
                redis = Redis.from_url(
                    resolved_settings.redis_url.get_secret_value(),
                    decode_responses=False,
                )
                resolved_security_store = RedisSecurityStore(redis, "careeros:identity", pepper)
            if resolved_email_sender is None:
                if resolved_settings.email_provider == "smtp":
                    resolved_email_sender = SmtpEmailSender(
                        SmtpOptions(
                            hostname=resolved_settings.smtp_host,
                            port=resolved_settings.smtp_port,
                            sender=resolved_settings.email_from_address,
                            username=resolved_settings.smtp_username,
                            password=(
                                resolved_settings.smtp_password.get_secret_value()
                                if resolved_settings.smtp_password is not None
                                else None
                            ),
                            start_tls=resolved_settings.smtp_start_tls,
                            timeout_seconds=resolved_settings.smtp_timeout_seconds,
                        )
                    )
                else:
                    resolved_email_sender = DisabledEmailSender()

            google: GoogleOAuthProviderPort = DisabledGoogleOAuthProvider()
            if resolved_settings.google_oauth_enabled:
                client_id = resolved_settings.google_client_id
                client_secret = resolved_settings.google_client_secret
                if client_id is None or client_secret is None:
                    raise RuntimeError("validated Google OAuth credentials are unavailable")
                google = GoogleOAuthProvider(
                    GoogleOAuthOptions(
                        client_id=client_id,
                        client_secret=client_secret.get_secret_value(),
                        redirect_uri=resolved_settings.google_redirect_uri,
                        flow_ttl_seconds=resolved_settings.oauth_flow_ttl_seconds,
                    ),
                    resolved_security_store,
                )
            resolved_identity = IdentityService(
                unit_of_work=SqlAlchemyIdentityUnitOfWorkFactory(resolved_database),
                clock=SystemClock(),
                passwords=Argon2PasswordHasher(),
                tokens=HmacTokenManager(pepper),
                emails=resolved_email_sender,
                email_normalizer=NormalizedEmailValidator(),
                limiter=resolved_security_store,
                google=google,
                policy=IdentityPolicy(
                    public_app_url=resolved_settings.public_app_url,
                    access_ttl_seconds=resolved_settings.session_ttl_seconds,
                    refresh_ttl_seconds=resolved_settings.refresh_ttl_seconds,
                    verification_ttl_seconds=resolved_settings.verification_ttl_seconds,
                    reset_ttl_seconds=resolved_settings.reset_ttl_seconds,
                    recent_auth_ttl_seconds=resolved_settings.recent_auth_ttl_seconds,
                    rate_limit_window_seconds=resolved_settings.auth_rate_limit_window_seconds,
                    consent_policy_version=resolved_settings.consent_policy_version,
                ),
            )

        if resolved_resume_health is None and isinstance(resolved_database, Database):
            resume_uow = SqlAlchemyResumeUnitOfWorkFactory(resolved_database)
            resolved_resume_storage = resolved_resume_storage or S3ObjectStorage(
                S3Options(
                    internal_endpoint_url=resolved_settings.s3_endpoint_url,
                    public_endpoint_url=resolved_settings.s3_public_endpoint_url,
                    region=resolved_settings.s3_region,
                    bucket=resolved_settings.s3_bucket,
                    access_key_id=resolved_settings.s3_access_key_id,
                    secret_access_key=resolved_settings.s3_secret_access_key.get_secret_value(),
                    use_ssl=resolved_settings.s3_use_ssl,
                )
            )
            resume_clock = SystemClock()
            resolved_resume_health = ResumeHealthService(
                unit_of_work=resume_uow,
                clock=resume_clock,
                capabilities=HmacGuestCapabilityManager(
                    resolved_settings.resume_capability_pepper.get_secret_value()
                ),
                storage=resolved_resume_storage,
                limits=DocumentLimits(
                    max_upload_bytes=resolved_settings.resume_max_upload_bytes,
                    max_pdf_pages=resolved_settings.resume_max_pages,
                    max_archive_entries=resolved_settings.resume_max_archive_entries,
                    max_archive_uncompressed_bytes=(resolved_settings.resume_max_expanded_bytes),
                    max_archive_ratio=resolved_settings.resume_max_compression_ratio,
                    processing_timeout_seconds=(
                        resolved_settings.resume_processing_timeout_seconds
                    ),
                ),
                policy=ResumeHealthPolicy(
                    upload_ttl_seconds=resolved_settings.resume_upload_intent_ttl_seconds,
                    guest_session_ttl_seconds=(
                        resolved_settings.resume_guest_retention_hours * 3600
                    ),
                    guest_document_retention_seconds=(
                        resolved_settings.resume_guest_retention_hours * 3600
                    ),
                ),
            )
            if resolved_resume_dispatcher is None:
                resolved_resume_dispatcher = OutboxDispatcher(
                    unit_of_work=resume_uow,
                    publisher=CeleryJobPublisher(
                        CeleryPublisherOptions(
                            broker_url=(resolved_settings.celery_broker_url.get_secret_value()),
                            queue="resume-health",
                        )
                    ),
                    clock=resume_clock,
                )

        application.state.database = resolved_database
        application.state.identity_service = resolved_identity
        application.state.security_store = resolved_security_store
        application.state.resume_health_service = resolved_resume_health
        application.state.resume_outbox_dispatcher = resolved_resume_dispatcher
        application.state.readiness_dependencies = {"database": resolved_database}
        if resolved_security_store is not None:
            application.state.readiness_dependencies["redis"] = resolved_security_store
        if resolved_email_sender is not None and resolved_settings.email_provider == "smtp":
            application.state.readiness_dependencies["email"] = resolved_email_sender
        if resolved_resume_storage is not None:
            application.state.readiness_dependencies["objectStorage"] = resolved_resume_storage
        logger.info(
            "api_started",
            service=resolved_settings.service_name,
            version=resolved_settings.service_version,
            environment=resolved_settings.environment,
        )
        try:
            yield
        finally:
            if resolved_email_sender is not None:
                await resolved_email_sender.dispose()
            if resolved_security_store is not None:
                await resolved_security_store.dispose()
            if resolved_resume_storage is not None:
                await resolved_resume_storage.dispose()
            await resolved_database.dispose()
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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "Traceparent",
            "X-CSRF-Token",
            "X-Guest-CSRF",
            "X-Request-ID",
        ],
        expose_headers=["ETag", "X-Request-ID", "X-Trace-ID"],
    )
    application.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=resolved_settings.max_request_body_bytes,
    )
    install_request_context_middleware(application)
    install_problem_handlers(application)
    application.include_router(router)
    return application
