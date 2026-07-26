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
            "resume_capability_pepper": "production-resume-pepper-is-at-least-32-bytes",
            "bff_client_signal_secret": "production-bff-signal-secret-is-at-least-32-bytes",
            "database_url": "postgresql+asyncpg://app:unique-secret@db:5432/careeros",
            "s3_endpoint_url": "https://objects.internal.example.com",
            "s3_public_endpoint_url": "https://uploads.example.com",
            "s3_access_key_id": "production-test-access-key",
            "s3_secret_access_key": "production-test-unique-object-secret",
            "s3_use_ssl": True,
            "malware_scanner_provider": "clamav",
            "ai_provider": "http_json",
            "ai_http_endpoint_url": "https://ai-gateway.example.com",
            "ai_http_api_key": "production-test-ai-key",
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


def test_analytics_retry_budget_uses_the_shared_bounded_environment_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAREEROS_ANALYTICS_MAX_ATTEMPTS", raising=False)
    monkeypatch.setenv("ANALYTICS_MAX_ATTEMPTS", "7")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.analytics_max_attempts == 7
    with pytest.raises(ValidationError, match="analytics_max_attempts"):
        Settings.model_validate({"analytics_max_attempts": 11})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resume_correction_rate_limit", 0),
        ("resume_correction_rate_limit", 301),
        ("resume_correction_rate_window_seconds", 59),
        ("resume_correction_rate_window_seconds", 3_601),
        ("resume_analysis_rate_limit", 0),
        ("resume_analysis_rate_limit", 101),
        ("resume_analysis_rate_window_seconds", 59),
        ("resume_analysis_rate_window_seconds", 86_401),
    ],
)
def test_resume_mutation_rate_controls_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings.model_validate({field: value})


def test_resume_mutation_rate_controls_have_safe_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert (
        settings.resume_correction_rate_limit,
        settings.resume_correction_rate_window_seconds,
    ) == (30, 60)
    assert (
        settings.resume_analysis_rate_limit,
        settings.resume_analysis_rate_window_seconds,
    ) == (10, 3_600)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user:secret@objects.example.com",
        "https://objects.example.com/private",
        "https://objects.example.com?bucket=other",
        "ftp://objects.example.com",
    ],
)
def test_storage_endpoints_must_be_credential_free_origins(endpoint: str) -> None:
    with pytest.raises(ValidationError, match="S3 endpoints"):
        Settings.model_validate({"s3_public_endpoint_url": endpoint})


def test_compose_environment_aliases_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAREEROS_DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("DOCUMENT_MAX_PAGES", "12")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:local-only@postgres:5432/careeros",
    )

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "test"
    assert settings.log_level == "WARNING"
    assert settings.resume_max_pages == 12
    assert settings.database_url.get_secret_value().endswith("@postgres:5432/careeros")
