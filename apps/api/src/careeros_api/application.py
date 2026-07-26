"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import structlog
from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database, ReadinessProbe
from careeros.foundation.observability import configure_logging
from careeros.integrations.email import DisabledEmailSender, SmtpEmailSender, SmtpOptions
from careeros.integrations.oauth import GoogleOAuthOptions, GoogleOAuthProvider
from careeros.modules.application_workspace.application import (
    ApplicationWorkspaceService,
    ApplicationWorkspaceUnitOfWorkFactory,
)
from careeros.modules.application_workspace.infrastructure import (
    CareerRecordApplicationEvidenceSnapshotProvider,
    JobMatchApplicationSnapshotProvider,
    ResumeBuilderVersionSnapshotProvider,
    SqlAlchemyApplicationWorkspaceUnitOfWorkFactory,
)
from careeros.modules.application_workspace.infrastructure import (
    SystemClock as ApplicationWorkspaceClock,
)
from careeros.modules.application_workspace.infrastructure import (
    UuidIdentifierFactory as ApplicationWorkspaceUuidFactory,
)
from careeros.modules.career_analytics.application import (
    CareerAnalyticsPolicy,
    CareerAnalyticsService,
)
from careeros.modules.career_analytics.infrastructure import (
    ApplicationWorkspaceAnalyticsSource,
    CareerRecordAnalyticsProvider,
    CompositeSupplementalAnalyticsSource,
    RoleReadinessAnalyticsProvider,
    SqlAlchemyCareerAnalyticsUnitOfWorkFactory,
)
from careeros.modules.career_analytics.infrastructure import (
    SystemClock as CareerAnalyticsClock,
)
from careeros.modules.career_analytics.infrastructure import (
    Uuid4IdentifierFactory as CareerAnalyticsUuidFactory,
)
from careeros.modules.career_growth.application import CareerGrowthService
from careeros.modules.career_growth.infrastructure import (
    CareerRecordGrowthSourceProvider,
    SqlAlchemyCareerGrowthUnitOfWorkFactory,
)
from careeros.modules.career_growth.infrastructure import SystemClock as CareerGrowthClock
from careeros.modules.career_growth.infrastructure import (
    UuidIdentifierFactory as CareerGrowthUuidFactory,
)
from careeros.modules.career_record.application import (
    AttachmentLimits,
    AttachmentWorkflowService,
    CareerRecordService,
)
from careeros.modules.career_record.infrastructure import (
    AttachmentAdmissionBridge,
    AttachmentS3ObjectStorage,
    AttachmentS3Options,
    ResumeHealthSourceQuery,
    SqlAlchemyAttachmentUnitOfWorkFactory,
    SqlAlchemyCareerRecordUnitOfWorkFactory,
    UuidIdentifierFactory,
)
from careeros.modules.career_record.infrastructure import (
    SystemClock as CareerRecordClock,
)
from careeros.modules.change_studio.application import ChangeStudioService, SuggestionProvider
from careeros.modules.change_studio.infrastructure import (
    CareerRecordChangeStudioEvidenceProvider,
    CircuitBreakingSuggestionProvider,
    DeterministicSuggestionProvider,
    DisabledSuggestionProvider,
    HttpJsonProviderOptions,
    HttpJsonSuggestionProvider,
    JobMatchChangeStudioAnalysisProvider,
    SqlAlchemyChangeStudioUnitOfWorkFactory,
)
from careeros.modules.change_studio.infrastructure import (
    SystemClock as ChangeStudioClock,
)
from careeros.modules.change_studio.infrastructure import (
    UuidIdentifierFactory as ChangeStudioUuidFactory,
)
from careeros.modules.commercial.application import CommercialService
from careeros.modules.commercial.infrastructure import (
    DisabledBillingProvider,
    SqlAlchemyCommercialUnitOfWorkFactory,
)
from careeros.modules.commercial.infrastructure import SystemClock as CommercialClock
from careeros.modules.commercial.infrastructure import (
    UuidIdentifierFactory as CommercialUuidFactory,
)
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
from careeros.modules.identity.infrastructure.resume_health_onboarding import (
    ResumeHealthOnboardingSource,
)
from careeros.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    HmacTokenManager,
    NormalizedEmailValidator,
    SystemClock,
)
from careeros.modules.interview_prep.application import InterviewPrepService
from careeros.modules.interview_prep.infrastructure import (
    ApplicationWorkspaceInterviewContextProvider,
    SqlAlchemyInterviewPrepUnitOfWorkFactory,
)
from careeros.modules.interview_prep.infrastructure import SystemClock as InterviewPrepClock
from careeros.modules.interview_prep.infrastructure import (
    UuidIdentifierFactory as InterviewPrepUuidFactory,
)
from careeros.modules.job_match.application import JobMatchService
from careeros.modules.job_match.infrastructure import (
    CareerRecordJobMatchSnapshotProvider,
    RoleReadinessRoleContextProvider,
    SafeUrlJobImportProvider,
    SqlAlchemyJobMatchUnitOfWorkFactory,
)
from careeros.modules.job_match.infrastructure import (
    SystemClock as JobMatchClock,
)
from careeros.modules.job_match.infrastructure import (
    UuidIdentifierFactory as JobMatchUuidFactory,
)
from careeros.modules.networking.application import NetworkingService
from careeros.modules.networking.infrastructure import (
    ApplicationWorkspaceNetworkingReferenceProvider,
    SqlAlchemyNetworkingUnitOfWorkFactory,
)
from careeros.modules.networking.infrastructure import SystemClock as NetworkingClock
from careeros.modules.networking.infrastructure import (
    UuidIdentifierFactory as NetworkingUuidFactory,
)
from careeros.modules.resume_builder.application import ResumeBuilderPolicy, ResumeBuilderService
from careeros.modules.resume_builder.infrastructure import (
    CareerRecordResumeSourceProvider,
    ResumeExportS3Options,
    ResumeExportS3Storage,
    SqlAlchemyResumeBuilderUnitOfWorkFactory,
)
from careeros.modules.resume_builder.infrastructure import (
    SystemClock as ResumeBuilderClock,
)
from careeros.modules.resume_builder.infrastructure import (
    UuidIdentifierFactory as ResumeBuilderUuidFactory,
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
    LocalResumeParserProvider,
    S3ObjectStorage,
    S3Options,
    SqlAlchemyResumeUnitOfWorkFactory,
)
from careeros.modules.role_readiness.application import RoleReadinessService
from careeros.modules.role_readiness.infrastructure import (
    CareerRecordSnapshotProvider,
    SqlAlchemyRoleReadinessUnitOfWorkFactory,
)
from careeros.modules.role_readiness.infrastructure import (
    SystemClock as RoleReadinessClock,
)
from careeros.modules.role_readiness.infrastructure import (
    UuidIdentifierFactory as RoleReadinessUuidFactory,
)
from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from careeros_api.modules.commercial.problems import install_commercial_problem_handler
from careeros_api.config import Settings, get_settings
from careeros_api.middleware import RequestBodyLimitMiddleware, install_request_context_middleware
from careeros_api.modules.career_growth import install_career_growth_problem_handler
from careeros_api.modules.interview_prep import install_interview_prep_problem_handler
from careeros_api.problems import install_problem_handlers
from careeros_api.routes import router

logger = structlog.get_logger(__name__)


def _change_studio_provider(settings: Settings) -> SuggestionProvider:
    if settings.ai_provider == "disabled":
        return DisabledSuggestionProvider()
    if settings.ai_provider == "deterministic":
        return DeterministicSuggestionProvider()
    endpoint = settings.ai_http_endpoint_url
    api_key = settings.ai_http_api_key
    if endpoint is None or api_key is None:
        raise RuntimeError("validated AI HTTP provider configuration is unavailable")
    return CircuitBreakingSuggestionProvider(
        HttpJsonSuggestionProvider(
            HttpJsonProviderOptions(
                endpoint_url=endpoint,
                api_key=api_key.get_secret_value(),
                timeout_seconds=settings.ai_http_timeout_seconds,
                max_attempts=settings.ai_http_max_attempts,
                max_response_bytes=settings.ai_http_max_response_bytes,
            )
        ),
        failure_threshold=settings.ai_circuit_failure_threshold,
        cooldown_seconds=settings.ai_circuit_cooldown_seconds,
    )


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
    career_record: CareerRecordService | None = None,
    attachment_workflow: AttachmentWorkflowService | None = None,
    attachment_storage: AttachmentS3ObjectStorage | None = None,
    role_readiness: RoleReadinessService | None = None,
    job_match: JobMatchService | None = None,
    change_studio: ChangeStudioService | None = None,
    resume_builder: ResumeBuilderService | None = None,
    application_workspace: ApplicationWorkspaceService | None = None,
    interview_prep: InterviewPrepService | None = None,
    networking: NetworkingService | None = None,
    career_growth: CareerGrowthService | None = None,
    career_analytics: CareerAnalyticsService | None = None,
    commercial: CommercialService | None = None,
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
        resolved_career_record = career_record
        resolved_attachment_workflow = attachment_workflow
        resolved_attachment_storage = attachment_storage
        resolved_role_readiness = role_readiness
        resolved_job_match = job_match
        resolved_change_studio = change_studio
        resolved_resume_builder = resume_builder
        resolved_application_workspace = application_workspace
        resolved_interview_prep = interview_prep
        resolved_networking = networking
        resolved_career_growth = career_growth
        resolved_career_analytics = career_analytics
        resolved_commercial = commercial
        resolved_resume_builder_storage: ResumeExportS3Storage | None = None

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
                semantic_parser=LocalResumeParserProvider(),
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

        if resolved_identity is not None and resolved_resume_health is not None:
            resolved_identity.set_onboarding_resume_source(
                ResumeHealthOnboardingSource(resolved_resume_health)
            )

        if isinstance(resolved_database, Database):
            attachment_uow = SqlAlchemyAttachmentUnitOfWorkFactory(resolved_database)
            if resolved_attachment_workflow is None:
                resolved_attachment_storage = (
                    resolved_attachment_storage
                    or AttachmentS3ObjectStorage(
                        AttachmentS3Options(
                            internal_endpoint_url=resolved_settings.s3_endpoint_url,
                            public_endpoint_url=resolved_settings.s3_public_endpoint_url,
                            region=resolved_settings.s3_region,
                            bucket=resolved_settings.s3_bucket,
                            access_key_id=resolved_settings.s3_access_key_id,
                            secret_access_key=(
                                resolved_settings.s3_secret_access_key.get_secret_value()
                            ),
                            use_ssl=resolved_settings.s3_use_ssl,
                        )
                    )
                )
                resolved_attachment_workflow = AttachmentWorkflowService(
                    unit_of_work=attachment_uow,
                    clock=CareerRecordClock(),
                    storage=resolved_attachment_storage,
                    limits=AttachmentLimits(
                        max_upload_bytes=resolved_settings.resume_max_upload_bytes,
                        max_pdf_pages=resolved_settings.resume_max_pages,
                        max_archive_entries=resolved_settings.resume_max_archive_entries,
                        max_archive_uncompressed_bytes=(
                            resolved_settings.resume_max_expanded_bytes
                        ),
                        max_archive_ratio=resolved_settings.resume_max_compression_ratio,
                        processing_timeout_seconds=(
                            resolved_settings.resume_processing_timeout_seconds
                        ),
                    ),
                )
            if resolved_career_record is None:
                if resolved_resume_health is None:
                    raise RuntimeError("Career Record requires the Resume Health source query")
                resolved_career_record = CareerRecordService(
                    unit_of_work=SqlAlchemyCareerRecordUnitOfWorkFactory(resolved_database),
                    clock=CareerRecordClock(),
                    identifiers=UuidIdentifierFactory(),
                    resume_sources=ResumeHealthSourceQuery(resolved_resume_health),
                    attachments=AttachmentAdmissionBridge(resolved_attachment_workflow),
                    verification_authority=None,
                )
            if resolved_role_readiness is None:
                if resolved_career_record is None:
                    raise RuntimeError(
                        "Role Readiness requires the Career Record snapshot boundary"
                    )
                resolved_role_readiness = RoleReadinessService(
                    unit_of_work=SqlAlchemyRoleReadinessUnitOfWorkFactory(resolved_database),
                    clock=RoleReadinessClock(),
                    identifiers=RoleReadinessUuidFactory(),
                    career_snapshots=CareerRecordSnapshotProvider(resolved_career_record),
                )
            if resolved_job_match is None:
                if resolved_career_record is None or resolved_role_readiness is None:
                    raise RuntimeError(
                        "Job Match requires Career Record and Role Readiness boundaries"
                    )
                resolved_job_match = JobMatchService(
                    unit_of_work=SqlAlchemyJobMatchUnitOfWorkFactory(resolved_database),
                    clock=JobMatchClock(),
                    identifiers=JobMatchUuidFactory(),
                    career_snapshots=CareerRecordJobMatchSnapshotProvider(resolved_career_record),
                    role_context=RoleReadinessRoleContextProvider(resolved_role_readiness),
                    importer=SafeUrlJobImportProvider(),
                )
            if resolved_change_studio is None:
                if resolved_career_record is None or resolved_job_match is None:
                    raise RuntimeError(
                        "Change Studio requires Career Record and Job Match boundaries"
                    )
                resolved_change_studio = ChangeStudioService(
                    unit_of_work=SqlAlchemyChangeStudioUnitOfWorkFactory(resolved_database),
                    clock=ChangeStudioClock(),
                    identifiers=ChangeStudioUuidFactory(),
                    provider=_change_studio_provider(resolved_settings),
                    evidence=CareerRecordChangeStudioEvidenceProvider(resolved_career_record),
                    job_matches=JobMatchChangeStudioAnalysisProvider(resolved_job_match),
                )
            if resolved_resume_builder is None:
                if resolved_career_record is None:
                    raise RuntimeError("Resume Builder requires Career Record boundary")
                resolved_resume_builder_storage = ResumeExportS3Storage(
                    ResumeExportS3Options(
                        internal_endpoint_url=resolved_settings.s3_endpoint_url,
                        public_endpoint_url=resolved_settings.s3_public_endpoint_url,
                        region=resolved_settings.s3_region,
                        bucket=resolved_settings.s3_bucket,
                        access_key_id=resolved_settings.s3_access_key_id,
                        secret_access_key=(
                            resolved_settings.s3_secret_access_key.get_secret_value()
                        ),
                        use_ssl=resolved_settings.s3_use_ssl,
                    )
                )
                resolved_resume_builder = ResumeBuilderService(
                    unit_of_work=SqlAlchemyResumeBuilderUnitOfWorkFactory(resolved_database),
                    clock=ResumeBuilderClock(),
                    identifiers=ResumeBuilderUuidFactory(),
                    sources=CareerRecordResumeSourceProvider(
                        resolved_career_record,
                        change_studio=resolved_change_studio,
                    ),
                    storage=resolved_resume_builder_storage,
                    policy=ResumeBuilderPolicy(),
                )
            if resolved_application_workspace is None:
                if (
                    resolved_career_record is None
                    or resolved_job_match is None
                    or resolved_resume_builder is None
                ):
                    raise RuntimeError(
                        "Application Workspace requires Career Record, Job Match, "
                        "and Resume Builder boundaries"
                    )
                resolved_application_workspace = ApplicationWorkspaceService(
                    unit_of_work=cast(
                        ApplicationWorkspaceUnitOfWorkFactory,
                        SqlAlchemyApplicationWorkspaceUnitOfWorkFactory(resolved_database),
                    ),
                    clock=ApplicationWorkspaceClock(),
                    identifiers=ApplicationWorkspaceUuidFactory(),
                    jobs=JobMatchApplicationSnapshotProvider(resolved_job_match),
                    resumes=ResumeBuilderVersionSnapshotProvider(resolved_resume_builder),
                    evidence=CareerRecordApplicationEvidenceSnapshotProvider(
                        resolved_career_record
                    ),
                )
            if resolved_interview_prep is None:
                if resolved_application_workspace is None:
                    raise RuntimeError("Interview Prep requires the Application Workspace boundary")
                resolved_interview_prep = InterviewPrepService(
                    unit_of_work=SqlAlchemyInterviewPrepUnitOfWorkFactory(resolved_database),
                    clock=InterviewPrepClock(),
                    identifiers=InterviewPrepUuidFactory(),
                    application_context=ApplicationWorkspaceInterviewContextProvider(
                        resolved_application_workspace
                    ),
                )
            if resolved_networking is None:
                if resolved_application_workspace is None:
                    raise RuntimeError("Networking requires the Application Workspace boundary")
                resolved_networking = NetworkingService(
                    unit_of_work=SqlAlchemyNetworkingUnitOfWorkFactory(resolved_database),
                    clock=NetworkingClock(),
                    identifiers=NetworkingUuidFactory(),
                    applications=ApplicationWorkspaceNetworkingReferenceProvider(
                        resolved_application_workspace
                    ),
                )
            if resolved_career_growth is None:
                if resolved_career_record is None:
                    raise RuntimeError("Career Growth requires the Career Record boundary")
                resolved_career_growth = CareerGrowthService(
                    unit_of_work=SqlAlchemyCareerGrowthUnitOfWorkFactory(resolved_database),
                    clock=CareerGrowthClock(),
                    identifiers=CareerGrowthUuidFactory(),
                    career_source=CareerRecordGrowthSourceProvider(resolved_career_record),
                )
            if resolved_career_analytics is None:
                if (
                    resolved_application_workspace is None
                    or resolved_role_readiness is None
                    or resolved_career_record is None
                ):
                    raise RuntimeError(
                        "Career Analytics requires Application Workspace, "
                        "Role Readiness, and Career Record boundaries"
                    )
                resolved_career_analytics = CareerAnalyticsService(
                    unit_of_work=SqlAlchemyCareerAnalyticsUnitOfWorkFactory(resolved_database),
                    clock=CareerAnalyticsClock(),
                    identifiers=CareerAnalyticsUuidFactory(),
                    applications=ApplicationWorkspaceAnalyticsSource(
                        resolved_application_workspace
                    ),
                    supplemental=CompositeSupplementalAnalyticsSource(
                        readiness=cast(
                            RoleReadinessAnalyticsProvider,
                            resolved_role_readiness,
                        ),
                        career_record=cast(
                            CareerRecordAnalyticsProvider,
                            resolved_career_record,
                        ),
                    ),
                    policy=CareerAnalyticsPolicy(
                        max_attempts=resolved_settings.analytics_max_attempts,
                    ),
                )
            if resolved_commercial is None:
                resolved_commercial = CommercialService(
                    unit_of_work=SqlAlchemyCommercialUnitOfWorkFactory(resolved_database),
                    clock=CommercialClock(),
                    identifiers=CommercialUuidFactory(),
                    billing=DisabledBillingProvider(),
                    allowed_return_origins=frozenset(resolved_settings.allowed_origins),
                )

        application.state.database = resolved_database
        application.state.identity_service = resolved_identity
        application.state.security_store = resolved_security_store
        application.state.resume_health_service = resolved_resume_health
        application.state.career_record_service = resolved_career_record
        application.state.role_readiness_service = resolved_role_readiness
        application.state.job_match_service = resolved_job_match
        application.state.change_studio_service = resolved_change_studio
        application.state.resume_builder_service = resolved_resume_builder
        application.state.application_workspace_service = resolved_application_workspace
        application.state.interview_prep_service = resolved_interview_prep
        application.state.networking_service = resolved_networking
        application.state.career_growth_service = resolved_career_growth
        application.state.career_analytics_service = resolved_career_analytics
        application.state.commercial_service = resolved_commercial
        application.state.attachment_workflow_service = resolved_attachment_workflow
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
            if resolved_attachment_storage is not None:
                await resolved_attachment_storage.dispose()
            if resolved_resume_builder_storage is not None:
                await resolved_resume_builder_storage.dispose()
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
    install_commercial_problem_handler(application)
    install_interview_prep_problem_handler(application)
    install_career_growth_problem_handler(application)
    application.include_router(router)
    return application
