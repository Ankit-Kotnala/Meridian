"""Environment-backed API configuration."""

from functools import lru_cache
from typing import Any, Literal, Self
from urllib.parse import urlparse

from careeros.foundation.config import parse_async_postgresql_url
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
LogFormat = Literal["json", "console"]
EmailProvider = Literal["smtp", "disabled"]
MalwareScannerProvider = Literal["clamav", "disabled"]
AiProvider = Literal["deterministic", "http_json", "disabled"]
AccountOperationsProvider = Literal["local", "disabled"]
BillingProvider = Literal["disabled"]

_DEVELOPMENT_DATABASE_URL = "postgresql+asyncpg://careeros:careeros@localhost:5432/careeros"


class Settings(BaseSettings):
    """Validated process settings.

    Sensitive values use ``SecretStr`` so accidental model serialization and
    logging redact them. Callers must opt in to retrieving the database DSN.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CAREEROS_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    environment: Environment = Field(
        default="development",
        validation_alias=AliasChoices("CAREEROS_ENVIRONMENT", "ENVIRONMENT"),
    )
    service_name: str = "careeros-api"
    service_version: str = "0.1.0"
    debug: bool = False
    docs_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias=AliasChoices("CAREEROS_LOG_LEVEL", "LOG_LEVEL"),
    )
    log_format: LogFormat = "json"
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver", "api"]
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias=AliasChoices("CAREEROS_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )

    database_url: SecretStr = Field(
        default=SecretStr(_DEVELOPMENT_DATABASE_URL),
        validation_alias=AliasChoices("CAREEROS_DATABASE_URL", "DATABASE_URL"),
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_connect_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    database_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)

    redis_url: SecretStr = Field(
        default=SecretStr("redis://localhost:6379/0"),
        validation_alias=AliasChoices("CAREEROS_REDIS_URL", "REDIS_URL"),
    )
    auth_token_pepper: SecretStr = SecretStr("change-me-local-only-auth-token-pepper")
    account_operation_pepper: SecretStr = SecretStr("change-me-local-only-account-operation-pepper")
    admin_audit_pepper: SecretStr = SecretStr("change-me-local-only-admin-audit-pepper")
    cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=900, ge=300, le=3600)
    refresh_ttl_seconds: int = Field(default=2_592_000, ge=86_400, le=7_776_000)
    verification_ttl_seconds: int = Field(default=86_400, ge=900, le=604_800)
    reset_ttl_seconds: int = Field(default=3_600, ge=600, le=86_400)
    recent_auth_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    oauth_flow_ttl_seconds: int = Field(default=600, ge=60, le=1800)
    auth_rate_limit_window_seconds: int = Field(default=300, ge=60, le=3600)
    public_app_url: str = "http://localhost:3000"
    consent_policy_version: str = Field(default="2026-07-15", min_length=1, max_length=40)

    email_provider: EmailProvider = "smtp"
    smtp_host: str = Field(default="localhost", min_length=1, max_length=253)
    smtp_port: int = Field(default=1025, ge=1, le=65_535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: SecretStr | None = None
    smtp_start_tls: bool = False
    smtp_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    email_from_address: str = Field(default="no-reply@careeros.local", max_length=254)

    google_oauth_enabled: bool = False
    google_client_id: str | None = Field(default=None, max_length=512)
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:3000/api/v1/auth/google/callback"
    account_export_provider: AccountOperationsProvider = Field(
        default="local",
        validation_alias=AliasChoices(
            "CAREEROS_ACCOUNT_EXPORT_PROVIDER",
            "ACCOUNT_EXPORT_PROVIDER",
        ),
    )
    account_deletion_provider: AccountOperationsProvider = Field(
        default="local",
        validation_alias=AliasChoices(
            "CAREEROS_ACCOUNT_DELETION_PROVIDER",
            "ACCOUNT_DELETION_PROVIDER",
        ),
    )
    account_operation_max_attempts: int = Field(default=5, ge=1, le=10)
    account_operation_lease_seconds: int = Field(default=900, ge=30, le=3_600)
    account_operation_retry_seconds: int = Field(default=30, ge=1, le=3_600)
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
    billing_provider: BillingProvider = Field(
        default="disabled",
        validation_alias=AliasChoices(
            "CAREEROS_BILLING_PROVIDER",
            "BILLING_PROVIDER",
        ),
    )

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("CAREEROS_S3_ENDPOINT_URL", "S3_ENDPOINT_URL"),
    )
    s3_public_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("CAREEROS_S3_PUBLIC_ENDPOINT_URL", "S3_PUBLIC_ENDPOINT_URL"),
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("CAREEROS_S3_REGION", "S3_REGION"),
    )
    s3_bucket: str = Field(
        default="careeros-documents",
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$",
        validation_alias=AliasChoices("CAREEROS_S3_BUCKET", "S3_BUCKET"),
    )
    s3_access_key_id: str = Field(
        default="careeros-local",
        min_length=3,
        max_length=128,
        validation_alias=AliasChoices("CAREEROS_S3_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID"),
    )
    s3_secret_access_key: SecretStr = Field(
        default=SecretStr("change-me-local-only"),
        validation_alias=AliasChoices("CAREEROS_S3_SECRET_ACCESS_KEY", "S3_SECRET_ACCESS_KEY"),
    )
    s3_use_ssl: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREEROS_S3_USE_SSL", "S3_USE_SSL"),
    )
    celery_broker_url: SecretStr = Field(
        default=SecretStr("redis://localhost:6379/0"),
        validation_alias=AliasChoices("CAREEROS_CELERY_BROKER_URL", "CELERY_BROKER_URL"),
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
    malware_scanner_provider: MalwareScannerProvider = Field(
        default="disabled",
        validation_alias=AliasChoices(
            "CAREEROS_MALWARE_SCANNER_PROVIDER", "MALWARE_SCANNER_PROVIDER"
        ),
    )
    clamav_host: str = Field(default="localhost", min_length=1, max_length=253)
    clamav_port: int = Field(default=3310, ge=1, le=65_535)
    clamav_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    resume_capability_pepper: SecretStr = SecretStr("change-me-local-only-resume-capability-pepper")
    bff_client_signal_secret: SecretStr = SecretStr("change-me-local-only-bff-client-signal-secret")
    resume_max_upload_bytes: int = Field(default=5_242_880, ge=65_536, le=20_971_520)
    resume_max_pages: int = Field(
        default=8,
        ge=1,
        le=25,
        validation_alias=AliasChoices(
            "CAREEROS_RESUME_MAX_PAGES",
            "CAREEROS_DOCUMENT_MAX_PAGES",
            "DOCUMENT_MAX_PAGES",
        ),
    )
    resume_max_expanded_bytes: int = Field(default=20_971_520, ge=1_048_576, le=104_857_600)
    resume_max_archive_entries: int = Field(default=256, ge=1, le=2_000)
    resume_max_compression_ratio: int = Field(default=100, ge=2, le=1_000)
    resume_upload_intent_ttl_seconds: int = Field(default=300, ge=60, le=900)
    resume_guest_retention_hours: int = Field(default=24, ge=1, le=168)
    resume_processing_timeout_seconds: int = Field(default=120, ge=10, le=600)
    resume_upload_rate_limit: int = Field(default=10, ge=1, le=100)
    resume_upload_rate_window_seconds: int = Field(default=3600, ge=60, le=86400)
    resume_correction_rate_limit: int = Field(default=30, ge=1, le=300)
    resume_correction_rate_window_seconds: int = Field(default=60, ge=60, le=3600)
    resume_analysis_rate_limit: int = Field(default=10, ge=1, le=100)
    resume_analysis_rate_window_seconds: int = Field(default=3600, ge=60, le=86400)
    ai_provider: AiProvider = Field(
        default="deterministic",
        validation_alias=AliasChoices("CAREEROS_AI_PROVIDER", "AI_PROVIDER"),
    )
    ai_http_endpoint_url: str | None = Field(
        default=None,
        max_length=2048,
        validation_alias=AliasChoices("CAREEROS_AI_HTTP_ENDPOINT_URL", "AI_HTTP_ENDPOINT_URL"),
    )
    ai_http_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CAREEROS_AI_HTTP_API_KEY", "AI_HTTP_API_KEY"),
    )
    ai_http_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    ai_http_max_attempts: int = Field(default=2, ge=1, le=3)
    ai_http_max_response_bytes: int = Field(default=262_144, ge=1_024, le=1_048_576)
    ai_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    ai_circuit_cooldown_seconds: int = Field(default=60, ge=1, le=3_600)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("allowed_origins must contain at least one exact origin")
        normalized: list[str] = []
        for value in values:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("allowed origins must be absolute HTTP(S) origins")
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or "*" in value:
                raise ValueError(
                    "allowed origins must not contain paths, queries, fragments, or wildcards"
                )
            normalized.append(value.rstrip("/"))
        return normalized

    @field_validator("public_app_url", "google_redirect_uri")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("value must be an absolute HTTP(S) URL")
        return value.rstrip("/")

    @field_validator("s3_endpoint_url", "s3_public_endpoint_url")
    @classmethod
    def validate_storage_origin(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("S3 endpoints must be absolute HTTP(S) origins")
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            raise ValueError("S3 endpoints must not contain credentials or a path")
        if parsed.query or parsed.fragment:
            raise ValueError("S3 endpoints must not contain query or fragment metadata")
        return value.rstrip("/")

    @field_validator(
        "smtp_username",
        "google_client_id",
        "ai_http_endpoint_url",
        mode="before",
    )
    @classmethod
    def normalize_blank_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "smtp_password",
        "google_client_secret",
        "ai_http_api_key",
        mode="before",
    )
    @classmethod
    def normalize_blank_optional_secret(cls, value: Any) -> Any:
        if isinstance(value, str) and not value:
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql_url(cls, value: SecretStr) -> SecretStr:
        parse_async_postgresql_url(value.get_secret_value())
        return value

    @field_validator("auth_token_pepper", "account_operation_pepper", "admin_audit_pepper")
    @classmethod
    def require_strong_token_pepper(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("token peppers must be at least 32 UTF-8 bytes")
        return value

    @field_validator("redis_url")
    @classmethod
    def require_redis_url(cls, value: SecretStr) -> SecretStr:
        parsed = urlparse(value.get_secret_value())
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("redis_url must use redis:// or rediss://")
        return value

    @field_validator("celery_broker_url")
    @classmethod
    def require_celery_broker_url(cls, value: SecretStr) -> SecretStr:
        parsed = urlparse(value.get_secret_value())
        if parsed.scheme not in {"redis", "rediss", "amqp", "amqps"} or not parsed.hostname:
            raise ValueError("celery_broker_url must use a supported broker scheme")
        return value

    @field_validator("resume_capability_pepper")
    @classmethod
    def require_strong_resume_capability_pepper(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("resume_capability_pepper must be at least 32 UTF-8 bytes")
        return value

    @field_validator("bff_client_signal_secret")
    @classmethod
    def require_strong_bff_client_signal_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("bff_client_signal_secret must be at least 32 UTF-8 bytes")
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> Self:
        """Fail closed for known unsafe production-only combinations."""
        if self.google_oauth_enabled and (
            not self.google_client_id or self.google_client_secret is None
        ):
            raise ValueError("Google OAuth requires both client ID and client secret")
        if self.ai_provider == "http_json":
            if self.ai_http_endpoint_url is None or self.ai_http_api_key is None:
                raise ValueError("AI HTTP provider requires an endpoint URL and API key")
            parsed_ai = urlparse(self.ai_http_endpoint_url)
            if parsed_ai.scheme != "https" or not parsed_ai.hostname:
                raise ValueError("AI HTTP provider endpoint must be an HTTPS URL")
            if parsed_ai.username or parsed_ai.password:
                raise ValueError("AI HTTP provider endpoint must not contain credentials")
            if parsed_ai.fragment:
                raise ValueError("AI HTTP provider endpoint must not contain a fragment")
        if self.account_deletion_provider != self.account_export_provider:
            raise ValueError("account export and deletion providers must be enabled together")
        if self.environment != "production":
            return self

        violations: list[str] = []
        database_url = parse_async_postgresql_url(self.database_url.get_secret_value())
        if self.debug:
            violations.append("debug must be disabled")
        if "*" in self.trusted_hosts:
            violations.append("trusted_hosts must not contain a wildcard")
        if not self.cookie_secure:
            violations.append("cookie_secure must be enabled")
        if any(not origin.startswith("https://") for origin in self.allowed_origins):
            violations.append("allowed_origins must use HTTPS")
        if not self.public_app_url.startswith("https://"):
            violations.append("public_app_url must use HTTPS")
        if self.account_export_provider != "local":
            violations.append("local account export must be enabled")
        if self.account_deletion_provider != "local":
            violations.append("local account deletion must be enabled")
        if self.email_provider != "smtp":
            violations.append("email_provider must be smtp")
        if self.smtp_start_tls is False:
            violations.append("smtp_start_tls must be enabled")
        if self.auth_token_pepper.get_secret_value() == "change-me-local-only-auth-token-pepper":
            violations.append("the development auth token pepper must be replaced")
        if (
            self.account_operation_pepper.get_secret_value()
            == "change-me-local-only-account-operation-pepper"
        ):
            violations.append("the development account-operation pepper must be replaced")
        if self.admin_audit_pepper.get_secret_value() == "change-me-local-only-admin-audit-pepper":
            violations.append("the development admin-audit pepper must be replaced")
        if self.google_oauth_enabled and not self.google_redirect_uri.startswith("https://"):
            violations.append("google_redirect_uri must use HTTPS")
        if not self.s3_endpoint_url.startswith("https://"):
            violations.append("s3_endpoint_url must use HTTPS")
        if not self.s3_public_endpoint_url.startswith("https://"):
            violations.append("s3_public_endpoint_url must use HTTPS")
        if not self.s3_use_ssl:
            violations.append("s3_use_ssl must be enabled")
        if self.malware_scanner_provider != "clamav":
            violations.append("malware_scanner_provider must be clamav")
        if self.ai_provider == "deterministic":
            violations.append("ai_provider must not be deterministic")
        if (
            self.resume_capability_pepper.get_secret_value()
            == "change-me-local-only-resume-capability-pepper"
        ):
            violations.append("the development resume capability pepper must be replaced")
        if (
            self.bff_client_signal_secret.get_secret_value()
            == "change-me-local-only-bff-client-signal-secret"
        ):
            violations.append("the development BFF client-signal secret must be replaced")
        if "change-me-local-only" in self.s3_secret_access_key.get_secret_value():
            violations.append("the development object-storage credential must be replaced")
        if database_url.host in {"localhost", "127.0.0.1", "::1"}:
            violations.append("database_url must not target a loopback host")
        password = (database_url.password or "").casefold()
        development_passwords = {
            "",
            "careeros",
            "change-me",
            "change-me-local-only",
            "changeme",
            "password",
        }
        if password in development_passwords:
            violations.append("the development database credential must be replaced")
        if violations:
            raise ValueError("Unsafe production configuration: " + "; ".join(violations))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one immutable-by-convention settings object per process."""
    return Settings()
