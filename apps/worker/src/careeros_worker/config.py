"""Environment-backed worker configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from careeros.foundation.config import validate_database_url_for_environment
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_REDIS_URL = "redis://localhost:6379/0"
_LOCAL_DATABASE_URL = "postgresql+asyncpg://careeros:careeros@localhost:5432/careeros"
_LOCAL_STORAGE_SECRET = "change-me-local-only-app-storage-secret"  # noqa: S105 -- local Compose credential
_LOCAL_INVITATION_SECRET = "change-me-local-only-auth-token-pepper"  # noqa: S105 -- local only


def _is_development_redis_url(value: SecretStr) -> bool:
    parsed = urlsplit(value.get_secret_value())
    password = (parsed.password or "").casefold()
    return parsed.hostname in {"localhost", "127.0.0.1", "::1", "redis"} or password in {
        "change-me",
        "change-me-local-only",
        "changeme",
        "password",
    }


def _is_local_hostname(hostname: str | None, *service_names: str) -> bool:
    return hostname is None or hostname.casefold() in {
        "localhost",
        "127.0.0.1",
        "::1",
        *(name.casefold() for name in service_names),
    }


class WorkerSettings(BaseSettings):
    """Validated Celery settings with redacted connection URLs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("CAREEROS_ENVIRONMENT", "ENVIRONMENT"),
    )
    service_name: str = Field(
        default="careeros-worker",
        validation_alias=AliasChoices("CAREEROS_SERVICE_NAME", "SERVICE_NAME"),
    )
    service_version: str = Field(
        default="0.1.0",
        validation_alias=AliasChoices("CAREEROS_SERVICE_VERSION", "SERVICE_VERSION"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias=AliasChoices("CAREEROS_LOG_LEVEL", "LOG_LEVEL"),
    )
    log_format: Literal["json", "console"] = Field(
        default="json",
        validation_alias=AliasChoices("CAREEROS_LOG_FORMAT", "LOG_FORMAT"),
    )

    broker_url: SecretStr = Field(
        default=SecretStr(_LOCAL_REDIS_URL),
        validation_alias=AliasChoices("CELERY_BROKER_URL", "REDIS_URL"),
    )
    result_backend: SecretStr = Field(
        default=SecretStr(_LOCAL_REDIS_URL),
        validation_alias=AliasChoices(
            "CELERY_RESULT_BACKEND",
            "RESULT_BACKEND",
            "REDIS_URL",
        ),
    )

    database_url: SecretStr = Field(
        default=SecretStr(_LOCAL_DATABASE_URL),
        validation_alias=AliasChoices("CAREEROS_DATABASE_URL", "DATABASE_URL"),
    )
    database_pool_size: int = Field(default=3, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_connect_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    database_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    organization_invitation_secret: SecretStr = Field(
        default=SecretStr(_LOCAL_INVITATION_SECRET),
        min_length=32,
        validation_alias=AliasChoices("CAREEROS_AUTH_TOKEN_PEPPER", "AUTH_TOKEN_PEPPER"),
    )
    email_provider: Literal["smtp", "disabled"] = Field(
        default="smtp",
        validation_alias=AliasChoices("CAREEROS_EMAIL_PROVIDER", "EMAIL_PROVIDER"),
    )
    email_from_address: str = Field(
        default="no-reply@careeros.local",
        min_length=3,
        max_length=254,
        validation_alias=AliasChoices("CAREEROS_EMAIL_FROM_ADDRESS", "EMAIL_FROM_ADDRESS"),
    )
    smtp_host: str = Field(
        default="localhost",
        min_length=1,
        max_length=253,
        validation_alias=AliasChoices("CAREEROS_SMTP_HOST", "SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=1025,
        ge=1,
        le=65_535,
        validation_alias=AliasChoices("CAREEROS_SMTP_PORT", "SMTP_PORT"),
    )
    smtp_username: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("CAREEROS_SMTP_USERNAME", "SMTP_USERNAME"),
    )
    smtp_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CAREEROS_SMTP_PASSWORD", "SMTP_PASSWORD"),
    )
    smtp_start_tls: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREEROS_SMTP_START_TLS", "SMTP_START_TLS"),
    )
    smtp_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=30,
        validation_alias=AliasChoices(
            "CAREEROS_SMTP_TIMEOUT_SECONDS",
            "SMTP_TIMEOUT_SECONDS",
        ),
    )
    public_app_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CAREEROS_PUBLIC_APP_URL", "PUBLIC_APP_URL"),
    )
    organization_invitation_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ORGANIZATION_INVITATION_INTERVAL_SECONDS",
            "ORGANIZATION_INVITATION_INTERVAL_SECONDS",
        ),
    )
    organization_invitation_batch_size: int = Field(
        default=20,
        ge=1,
        le=500,
        validation_alias=AliasChoices(
            "CAREEROS_ORGANIZATION_INVITATION_BATCH_SIZE",
            "ORGANIZATION_INVITATION_BATCH_SIZE",
        ),
    )
    organization_invitation_lease_seconds: int = Field(
        default=120,
        ge=5,
        le=900,
        validation_alias=AliasChoices(
            "CAREEROS_ORGANIZATION_INVITATION_LEASE_SECONDS",
            "ORGANIZATION_INVITATION_LEASE_SECONDS",
        ),
    )
    organization_invitation_retry_seconds: int = Field(
        default=30,
        ge=1,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ORGANIZATION_INVITATION_RETRY_SECONDS",
            "ORGANIZATION_INVITATION_RETRY_SECONDS",
        ),
    )

    account_export_provider: Literal["local", "disabled"] = Field(
        default="local",
        validation_alias=AliasChoices(
            "CAREEROS_ACCOUNT_EXPORT_PROVIDER",
            "ACCOUNT_EXPORT_PROVIDER",
        ),
    )
    account_deletion_provider: Literal["local", "disabled"] = Field(
        default="local",
        validation_alias=AliasChoices(
            "CAREEROS_ACCOUNT_DELETION_PROVIDER",
            "ACCOUNT_DELETION_PROVIDER",
        ),
    )
    account_operation_max_attempts: int = Field(default=5, ge=1, le=10)
    account_operation_lease_seconds: int = Field(default=900, ge=30, le=3_600)
    account_operation_retry_seconds: int = Field(default=30, ge=1, le=3_600)
    account_operation_interval_seconds: int = Field(default=5, ge=1, le=300)
    account_operation_batch_size: int = Field(default=5, ge=1, le=100)
    account_export_cleanup_interval_seconds: int = Field(default=300, ge=60, le=86_400)
    account_export_cleanup_batch_size: int = Field(default=20, ge=1, le=100)
    account_export_retention_hours: int = Field(default=24, ge=1, le=720)
    account_export_max_archive_bytes: int = Field(
        default=134_217_728,
        ge=1_048_576,
        le=536_870_912,
    )
    account_export_max_object_bytes: int = Field(
        default=26_214_400,
        ge=1_048_576,
        le=52_428_800,
    )

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("CAREEROS_S3_ENDPOINT_URL", "S3_ENDPOINT_URL"),
    )
    s3_public_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices(
            "CAREEROS_S3_PUBLIC_ENDPOINT_URL",
            "S3_PUBLIC_ENDPOINT_URL",
        ),
    )
    s3_region: str = Field(
        default="us-east-1",
        min_length=1,
        max_length=63,
        validation_alias=AliasChoices("CAREEROS_S3_REGION", "S3_REGION"),
    )
    s3_bucket: str = Field(
        default="careeros-documents",
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$",
        validation_alias=AliasChoices("CAREEROS_S3_BUCKET", "S3_BUCKET"),
    )
    s3_access_key_id: SecretStr = Field(
        default=SecretStr("careeros-app"),
        min_length=3,
        validation_alias=AliasChoices(
            "CAREEROS_S3_ACCESS_KEY_ID",
            "S3_APP_ACCESS_KEY_ID",
            "S3_ACCESS_KEY_ID",
        ),
    )
    s3_secret_access_key: SecretStr = Field(
        default=SecretStr(_LOCAL_STORAGE_SECRET),
        min_length=12,
        validation_alias=AliasChoices(
            "CAREEROS_S3_SECRET_ACCESS_KEY",
            "S3_APP_SECRET_ACCESS_KEY",
            "S3_SECRET_ACCESS_KEY",
        ),
    )
    s3_use_ssl: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREEROS_S3_USE_SSL", "S3_USE_SSL"),
    )

    malware_scanner_provider: Literal["clamav", "disabled"] = Field(
        default="clamav",
        validation_alias=AliasChoices(
            "CAREEROS_MALWARE_SCANNER_PROVIDER",
            "MALWARE_SCANNER_PROVIDER",
        ),
    )
    clamav_host: str = Field(
        default="localhost",
        min_length=1,
        max_length=253,
        validation_alias=AliasChoices("CAREEROS_CLAMAV_HOST", "CLAMAV_HOST"),
    )
    clamav_port: int = Field(
        default=3310,
        ge=1,
        le=65_535,
        validation_alias=AliasChoices("CAREEROS_CLAMAV_PORT", "CLAMAV_PORT"),
    )
    clamav_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=120,
        validation_alias=AliasChoices(
            "CAREEROS_CLAMAV_TIMEOUT_SECONDS",
            "CLAMAV_TIMEOUT_SECONDS",
        ),
    )

    document_temp_root: Path = Field(
        # The container mounts this private path as a bounded noexec tmpfs and the
        # processor creates a fresh randomized child for every job.
        default=Path("/tmp/careeros"),  # noqa: S108
        validation_alias=AliasChoices("CAREEROS_DOCUMENT_TEMP_ROOT", "DOCUMENT_TEMP_ROOT"),
    )
    document_max_bytes: int = Field(
        default=10_485_760,
        ge=1_048_576,
        le=26_214_400,
        validation_alias=AliasChoices("CAREEROS_DOCUMENT_MAX_BYTES", "DOCUMENT_MAX_BYTES"),
    )
    document_max_pages: int = Field(
        default=8,
        ge=1,
        le=100,
        validation_alias=AliasChoices("CAREEROS_DOCUMENT_MAX_PAGES", "DOCUMENT_MAX_PAGES"),
    )
    document_max_archive_entries: int = Field(
        default=256,
        ge=1,
        le=2_000,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_ARCHIVE_ENTRIES",
            "DOCUMENT_MAX_ARCHIVE_ENTRIES",
        ),
    )
    document_max_uncompressed_bytes: int = Field(
        default=52_428_800,
        ge=1_048_576,
        le=268_435_456,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_UNCOMPRESSED_BYTES",
            "DOCUMENT_MAX_UNCOMPRESSED_BYTES",
        ),
    )
    document_max_compression_ratio: int = Field(
        default=100,
        ge=1,
        le=1_000,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_COMPRESSION_RATIO",
            "DOCUMENT_MAX_COMPRESSION_RATIO",
        ),
    )
    document_max_extracted_characters: int = Field(
        default=500_000,
        ge=1_000,
        le=2_000_000,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_EXTRACTED_CHARACTERS",
            "DOCUMENT_MAX_EXTRACTED_CHARACTERS",
        ),
    )
    document_max_extracted_blocks: int = Field(
        default=5_000,
        ge=1,
        le=20_000,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_EXTRACTED_BLOCKS",
            "DOCUMENT_MAX_EXTRACTED_BLOCKS",
        ),
    )
    document_max_serialized_artifact_bytes: int = Field(
        default=2_097_152,
        ge=65_536,
        le=10_485_760,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_MAX_SERIALIZED_ARTIFACT_BYTES",
            "DOCUMENT_MAX_SERIALIZED_ARTIFACT_BYTES",
        ),
    )
    document_processing_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        le=600,
        validation_alias=AliasChoices(
            "CAREEROS_DOCUMENT_PROCESSING_TIMEOUT_SECONDS",
            "DOCUMENT_PROCESSING_TIMEOUT_SECONDS",
        ),
    )

    task_soft_time_limit_seconds: int = Field(
        default=270,
        ge=1,
        le=3600,
        validation_alias=AliasChoices(
            "CAREEROS_TASK_SOFT_TIME_LIMIT_SECONDS",
            "TASK_SOFT_TIME_LIMIT_SECONDS",
        ),
    )
    task_time_limit_seconds: int = Field(
        default=300,
        ge=2,
        le=3900,
        validation_alias=AliasChoices(
            "CAREEROS_TASK_TIME_LIMIT_SECONDS",
            "TASK_TIME_LIMIT_SECONDS",
        ),
    )
    task_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        validation_alias=AliasChoices("CAREEROS_TASK_MAX_RETRIES", "TASK_MAX_RETRIES"),
    )
    retry_backoff_max_seconds: int = Field(
        default=60,
        ge=1,
        le=900,
        validation_alias=AliasChoices(
            "CAREEROS_RETRY_BACKOFF_MAX_SECONDS",
            "RETRY_BACKOFF_MAX_SECONDS",
        ),
    )
    resume_job_reconciliation_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_JOB_RECONCILIATION_INTERVAL_SECONDS",
            "RESUME_JOB_RECONCILIATION_INTERVAL_SECONDS",
        ),
    )
    resume_job_reconciliation_stale_seconds: int = Field(
        default=300,
        ge=60,
        le=86_400,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_JOB_RECONCILIATION_STALE_SECONDS",
            "RESUME_JOB_RECONCILIATION_STALE_SECONDS",
        ),
    )
    attachment_job_reconciliation_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ATTACHMENT_JOB_RECONCILIATION_INTERVAL_SECONDS",
            "ATTACHMENT_JOB_RECONCILIATION_INTERVAL_SECONDS",
        ),
    )
    attachment_job_reconciliation_stale_seconds: int = Field(
        default=300,
        ge=60,
        le=86_400,
        validation_alias=AliasChoices(
            "CAREEROS_ATTACHMENT_JOB_RECONCILIATION_STALE_SECONDS",
            "ATTACHMENT_JOB_RECONCILIATION_STALE_SECONDS",
        ),
    )
    resume_export_lease_seconds: int = Field(
        default=330,
        ge=30,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_LEASE_SECONDS",
            "RESUME_EXPORT_LEASE_SECONDS",
        ),
    )
    resume_export_max_bytes: int = Field(
        default=8_388_608,
        ge=65_536,
        le=26_214_400,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_MAX_BYTES",
            "RESUME_EXPORT_MAX_BYTES",
        ),
    )
    resume_export_retry_seconds: int = Field(
        default=30,
        ge=1,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_RETRY_SECONDS",
            "RESUME_EXPORT_RETRY_SECONDS",
        ),
    )
    resume_export_outbox_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=300,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_OUTBOX_INTERVAL_SECONDS",
            "RESUME_EXPORT_OUTBOX_INTERVAL_SECONDS",
        ),
    )
    resume_export_outbox_lease_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_OUTBOX_LEASE_SECONDS",
            "RESUME_EXPORT_OUTBOX_LEASE_SECONDS",
        ),
    )
    resume_export_outbox_max_attempts: int = Field(
        default=5,
        ge=1,
        le=10,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_OUTBOX_MAX_ATTEMPTS",
            "RESUME_EXPORT_OUTBOX_MAX_ATTEMPTS",
        ),
    )
    resume_export_reconciliation_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_RECONCILIATION_INTERVAL_SECONDS",
            "RESUME_EXPORT_RECONCILIATION_INTERVAL_SECONDS",
        ),
    )
    resume_export_reconciliation_stale_seconds: int = Field(
        default=300,
        ge=60,
        le=86_400,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_RECONCILIATION_STALE_SECONDS",
            "RESUME_EXPORT_RECONCILIATION_STALE_SECONDS",
        ),
    )
    resume_export_orphan_cleanup_grace_seconds: int = Field(
        default=300,
        ge=30,
        le=86_400,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_EXPORT_ORPHAN_CLEANUP_GRACE_SECONDS",
            "RESUME_EXPORT_ORPHAN_CLEANUP_GRACE_SECONDS",
        ),
    )
    analytics_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias=AliasChoices(
            "CAREEROS_ANALYTICS_MAX_ATTEMPTS",
            "ANALYTICS_MAX_ATTEMPTS",
        ),
    )
    analytics_job_lease_seconds: int = Field(
        default=360,
        ge=30,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ANALYTICS_JOB_LEASE_SECONDS",
            "ANALYTICS_JOB_LEASE_SECONDS",
        ),
    )
    analytics_retry_seconds: int = Field(
        default=30,
        ge=1,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ANALYTICS_RETRY_SECONDS",
            "ANALYTICS_RETRY_SECONDS",
        ),
    )
    analytics_outbox_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=300,
        validation_alias=AliasChoices(
            "CAREEROS_ANALYTICS_OUTBOX_INTERVAL_SECONDS",
            "ANALYTICS_OUTBOX_INTERVAL_SECONDS",
        ),
    )
    analytics_reconciliation_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_ANALYTICS_RECONCILIATION_INTERVAL_SECONDS",
            "ANALYTICS_RECONCILIATION_INTERVAL_SECONDS",
        ),
    )
    networking_reminder_lease_seconds: int = Field(
        default=120,
        ge=15,
        le=300,
        validation_alias=AliasChoices(
            "CAREEROS_NETWORKING_REMINDER_LEASE_SECONDS",
            "NETWORKING_REMINDER_LEASE_SECONDS",
        ),
    )
    networking_reminder_retry_seconds: int = Field(
        default=30,
        ge=1,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_NETWORKING_REMINDER_RETRY_SECONDS",
            "NETWORKING_REMINDER_RETRY_SECONDS",
        ),
    )
    networking_reminder_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_NETWORKING_REMINDER_INTERVAL_SECONDS",
            "NETWORKING_REMINDER_INTERVAL_SECONDS",
        ),
    )
    networking_reconciliation_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3_600,
        validation_alias=AliasChoices(
            "CAREEROS_NETWORKING_RECONCILIATION_INTERVAL_SECONDS",
            "NETWORKING_RECONCILIATION_INTERVAL_SECONDS",
        ),
    )
    result_expires_seconds: int = Field(
        default=3600,
        ge=60,
        le=604800,
        validation_alias=AliasChoices(
            "CAREEROS_RESULT_EXPIRES_SECONDS",
            "RESULT_EXPIRES_SECONDS",
        ),
    )
    worker_prefetch_multiplier: int = Field(
        default=1,
        ge=1,
        le=16,
        validation_alias=AliasChoices(
            "CAREEROS_WORKER_PREFETCH_MULTIPLIER",
            "WORKER_PREFETCH_MULTIPLIER",
        ),
    )
    worker_max_tasks_per_child: int = Field(
        default=100,
        ge=1,
        le=10000,
        validation_alias=AliasChoices(
            "CAREEROS_WORKER_MAX_TASKS_PER_CHILD",
            "WORKER_MAX_TASKS_PER_CHILD",
        ),
    )

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("public_app_url must be an absolute HTTP(S) origin")
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            raise ValueError("public_app_url must not contain credentials or a path")
        if parsed.query or parsed.fragment:
            raise ValueError("public_app_url must not contain query or fragment metadata")
        return value.rstrip("/")

    @field_validator("smtp_host")
    @classmethod
    def validate_smtp_host(cls, value: str) -> str:
        if "://" in value or "/" in value or any(character.isspace() for character in value):
            raise ValueError("smtp_host must be a hostname without a scheme or path")
        return value

    @field_validator("s3_endpoint_url", "s3_public_endpoint_url")
    @classmethod
    def validate_storage_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("S3 endpoints must be absolute HTTP(S) origins")
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            raise ValueError("S3 endpoints must not contain credentials or a path")
        if parsed.query or parsed.fragment:
            raise ValueError("S3 endpoints must not contain query or fragment metadata")
        return value.rstrip("/")

    @field_validator("clamav_host")
    @classmethod
    def validate_clamav_host(cls, value: str) -> str:
        if "://" in value or "/" in value or any(character.isspace() for character in value):
            raise ValueError("clamav_host must be a hostname without a scheme or path")
        return value

    @model_validator(mode="after")
    def validate_safety_constraints(self) -> Self:
        if self.task_soft_time_limit_seconds >= self.task_time_limit_seconds:
            raise ValueError("task soft time limit must be lower than the hard time limit")
        if not (
            self.document_temp_root.is_absolute()
            or self.document_temp_root.as_posix().startswith("/")
        ):
            raise ValueError("document_temp_root must be an absolute path")
        if self.document_max_uncompressed_bytes < self.document_max_bytes:
            raise ValueError("document expansion limit must not be lower than upload limit")
        if self.document_processing_timeout_seconds >= self.task_soft_time_limit_seconds:
            raise ValueError("document processing timeout must be lower than the task soft limit")
        if self.analytics_job_lease_seconds <= self.task_time_limit_seconds:
            raise ValueError("analytics lease must exceed the worker hard time limit")
        if self.resume_export_lease_seconds <= self.task_time_limit_seconds:
            raise ValueError("resume export lease must exceed the worker hard time limit")
        if self.account_operation_lease_seconds <= self.task_time_limit_seconds:
            raise ValueError("account operation lease must exceed the worker hard time limit")
        if self.account_deletion_provider != self.account_export_provider:
            raise ValueError("account export and deletion providers must be enabled together")
        invitation_delivery_budget = (
            self.organization_invitation_batch_size * self.smtp_timeout_seconds + 5
        )
        if self.organization_invitation_lease_seconds <= invitation_delivery_budget:
            raise ValueError("organization invitation lease must exceed the bounded SMTP batch")
        validate_database_url_for_environment(
            self.database_url.get_secret_value(),
            self.environment,
        )
        if self.environment == "production":
            violations: list[str] = []
            if _is_development_redis_url(self.broker_url):
                violations.append("an explicit non-local broker URL is required")
            if _is_development_redis_url(self.result_backend):
                violations.append("an explicit non-local result backend is required")
            internal_storage = urlsplit(self.s3_endpoint_url)
            public_storage = urlsplit(self.s3_public_endpoint_url)
            if internal_storage.scheme != "https" or _is_local_hostname(
                internal_storage.hostname, "minio"
            ):
                violations.append("the internal S3 endpoint must use non-local HTTPS")
            if public_storage.scheme != "https" or _is_local_hostname(public_storage.hostname):
                violations.append("the public S3 endpoint must use non-local HTTPS")
            if not self.s3_use_ssl:
                violations.append("S3 TLS must be enabled")
            if self.s3_secret_access_key.get_secret_value() == _LOCAL_STORAGE_SECRET:
                violations.append("the local S3 application secret must be replaced")
            if self.malware_scanner_provider != "clamav":
                violations.append("ClamAV scanning must be enabled")
            if _is_local_hostname(self.clamav_host, "clamav"):
                violations.append("an explicit non-local ClamAV host is required")
            if self.organization_invitation_secret.get_secret_value() == _LOCAL_INVITATION_SECRET:
                violations.append("the local organization invitation secret must be replaced")
            if self.account_export_provider != "local":
                violations.append("local account export processing must be enabled")
            if self.account_deletion_provider != "local":
                violations.append("local account deletion processing must be enabled")
            if self.email_provider != "smtp":
                violations.append("SMTP invitation delivery must be enabled")
            if not self.smtp_start_tls:
                violations.append("SMTP STARTTLS must be enabled")
            if _is_local_hostname(self.smtp_host, "mailpit"):
                violations.append("an explicit non-local SMTP host is required")
            public_app = urlsplit(self.public_app_url)
            if public_app.scheme != "https" or _is_local_hostname(public_app.hostname):
                violations.append("the public application origin must use non-local HTTPS")
            if self.email_from_address.casefold().endswith("@careeros.local"):
                violations.append("the local sender address must be replaced")
            if violations:
                raise ValueError("Unsafe production configuration: " + "; ".join(violations))
        return self


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()
