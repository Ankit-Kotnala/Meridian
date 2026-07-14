"""Environment-backed API configuration."""

from functools import lru_cache
from typing import Literal, Self

from careeros.foundation.config import parse_async_postgresql_url
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
LogFormat = Literal["json", "console"]

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

    database_url: SecretStr = Field(
        default=SecretStr(_DEVELOPMENT_DATABASE_URL),
        validation_alias=AliasChoices("CAREEROS_DATABASE_URL", "DATABASE_URL"),
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_connect_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    database_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql_url(cls, value: SecretStr) -> SecretStr:
        parse_async_postgresql_url(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> Self:
        """Fail closed for known unsafe production-only combinations."""
        if self.environment != "production":
            return self

        violations: list[str] = []
        database_url = parse_async_postgresql_url(self.database_url.get_secret_value())
        if self.debug:
            violations.append("debug must be disabled")
        if "*" in self.trusted_hosts:
            violations.append("trusted_hosts must not contain a wildcard")
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
