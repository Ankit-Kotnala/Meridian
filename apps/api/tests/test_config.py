"""Configuration safety tests."""

import pytest
from pydantic import ValidationError

from careeros_api.config import Settings


def test_secret_is_redacted_in_model_representation() -> None:
    settings = Settings.model_validate({})

    assert "careeros:careeros" not in repr(settings)
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


@pytest.mark.parametrize("unsafe_values", [{"debug": True}, {"trusted_hosts": ["*"]}, {}])
def test_production_rejects_unsafe_defaults(unsafe_values: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings.model_validate(
            {
                "environment": "production",
                "trusted_hosts": ["api.example.com"],
                **unsafe_values,
            }
        )


def test_production_accepts_explicit_safe_configuration() -> None:
    settings = Settings.model_validate(
        {
            "environment": "production",
            "debug": False,
            "docs_enabled": False,
            "trusted_hosts": ["api.example.com"],
            "allowed_origins": ["https://app.example.com"],
            "public_app_url": "https://app.example.com",
            "cookie_secure": True,
            "smtp_start_tls": True,
            "auth_token_pepper": "production-test-pepper-is-at-least-32-bytes",
            "database_url": "postgresql+asyncpg://app:unique-secret@db:5432/careeros",
        }
    )

    assert settings.environment == "production"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://careeros:change-me-local-only@postgres:5432/careeros",
        "postgresql+asyncpg://app:unique-password@localhost:5432/careeros",
    ],
)
def test_production_rejects_compose_or_loopback_database_urls(database_url: str) -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings.model_validate(
            {
                "environment": "production",
                "trusted_hosts": ["api.example.com"],
                "database_url": database_url,
            }
        )


def test_database_requires_async_postgresql_driver() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings.model_validate({"database_url": "sqlite+aiosqlite:///local.db"})


@pytest.mark.parametrize("value", [1_023, 10_485_761])
def test_request_body_limit_is_bounded(value: int) -> None:
    with pytest.raises(ValidationError, match="max_request_body_bytes"):
        Settings(max_request_body_bytes=value, _env_file=None)  # type: ignore[call-arg]


def test_request_body_limit_has_safe_phase_one_default() -> None:
    assert Settings(_env_file=None).max_request_body_bytes == 1_048_576  # type: ignore[call-arg]


def test_compose_environment_aliases_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAREEROS_DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:local-only@postgres:5432/careeros",
    )

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "test"
    assert settings.log_level == "WARNING"
    assert settings.database_url.get_secret_value().endswith("@postgres:5432/careeros")
