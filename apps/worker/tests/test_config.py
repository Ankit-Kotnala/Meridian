"""Worker environment and safety tests."""

import pytest
from pydantic import ValidationError

from careeros_worker.config import WorkerSettings


def test_redis_url_is_used_as_broker_and_backend_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379/7")

    settings = WorkerSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.broker_url.get_secret_value() == "redis://redis.internal:6379/7"
    assert settings.result_backend.get_secret_value() == "redis://redis.internal:6379/7"


def test_explicit_celery_urls_take_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://fallback:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://broker:6379/1")
    monkeypatch.setenv("RESULT_BACKEND", "redis://backend:6379/2")

    settings = WorkerSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.broker_url.get_secret_value() == "redis://broker:6379/1"
    assert settings.result_backend.get_secret_value() == "redis://backend:6379/2"


def test_connection_urls_are_redacted() -> None:
    settings = WorkerSettings.model_validate(
        {
            "broker_url": "redis://:private@redis:6379/0",
            "result_backend": "redis://:private@redis:6379/1",
        }
    )

    assert "private" not in repr(settings)


def test_soft_time_limit_must_precede_hard_limit() -> None:
    with pytest.raises(ValidationError, match="soft time limit"):
        WorkerSettings.model_validate(
            {
                "task_soft_time_limit_seconds": 300,
                "task_time_limit_seconds": 300,
            }
        )


def test_production_rejects_local_connection_defaults() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        WorkerSettings.model_validate({"environment": "production"})


def test_production_rejects_compose_redis_service_defaults() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        WorkerSettings.model_validate(
            {
                "environment": "production",
                "broker_url": "redis://redis:6379/0",
                "result_backend": "redis://redis:6379/1",
            }
        )


def test_production_accepts_explicit_non_local_redis_urls() -> None:
    settings = WorkerSettings.model_validate(
        {
            "environment": "production",
            "broker_url": "rediss://broker.internal.example:6380/0",
            "result_backend": "rediss://backend.internal.example:6380/1",
        }
    )

    assert settings.environment == "production"
