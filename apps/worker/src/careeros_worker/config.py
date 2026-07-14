"""Environment-backed worker configuration."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_REDIS_URL = "redis://localhost:6379/0"


def _is_development_redis_url(value: SecretStr) -> bool:
    parsed = urlsplit(value.get_secret_value())
    password = (parsed.password or "").casefold()
    return parsed.hostname in {"localhost", "127.0.0.1", "::1", "redis"} or password in {
        "change-me",
        "change-me-local-only",
        "changeme",
        "password",
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

    @model_validator(mode="after")
    def validate_safety_constraints(self) -> Self:
        if self.task_soft_time_limit_seconds >= self.task_time_limit_seconds:
            raise ValueError("task soft time limit must be lower than the hard time limit")
        if self.environment == "production":
            if _is_development_redis_url(self.broker_url):
                raise ValueError("production requires an explicit non-local broker URL")
            if _is_development_redis_url(self.result_backend):
                raise ValueError("production requires an explicit non-local result backend")
        return self


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()
