"""Configuration safety tests."""

import pytest
from pydantic import ValidationError

from rezumi_api.config import Settings


def _safe_public_settings(environment: str = "production") -> dict[str, object]:
    return {
        "environment": environment,
        "debug": False,
        "docs_enabled": False,
        "log_level": "INFO",
        "trusted_hosts": ["api.example.com"],
        "allowed_origins": ["https://app.example.com"],
        "public_app_url": "https://app.example.com",
        "cookie_secure": True,
        "email_provider": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_username": "smtp-user",
        "smtp_password": "production-smtp-password",
        "smtp_start_tls": True,
        "email_from_address": "no-reply@example.com",
        "auth_token_pepper": "production-test-pepper-is-at-least-32-bytes",
        "resume_capability_pepper": "production-resume-pepper-is-at-least-32-bytes",
        "bff_client_signal_secret": "production-bff-signal-secret-is-at-least-32-bytes",
        "database_url": "postgresql+asyncpg://app:unique-secret@db.example.com:5432/rezumi",
        "redis_url": "rediss://cache.example.com:6380/0",
        "s3_endpoint_url": "https://objects.internal.example.com",
        "s3_public_endpoint_url": "https://uploads.example.com",
        "s3_access_key_id": "production-test-access-key",
        "s3_secret_access_key": "production-test-unique-object-secret",
        "s3_use_ssl": True,
        "malware_scanner_provider": "clamav",
        "clamav_host": "scanner.internal.example",
        "ai_provider": "http_json",
        "ai_http_endpoint_url": "https://ai-gateway.example.com",
        "ai_http_api_key": "production-test-ai-key",
    }


def test_secret_is_redacted_in_model_representation() -> None:
    settings = Settings.model_validate({})

    assert "rezumi:rezumi" not in repr(settings)
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    "unsafe_values",
    [
        {"debug": True},
        {"docs_enabled": True},
        {"trusted_hosts": ["*"]},
        {"redis_url": "redis://cache.example.com:6379/0"},
        {"smtp_password": None},
    ],
)
def test_public_environments_reject_unsafe_configuration(
    environment: str, unsafe_values: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Unsafe public configuration"):
        Settings.model_validate({**_safe_public_settings(environment), **unsafe_values})


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_public_environments_accept_explicit_safe_configuration(environment: str) -> None:
    settings = Settings.model_validate(_safe_public_settings(environment))

    assert settings.environment == environment


def test_qstash_delivery_requires_a_token_and_runner_url() -> None:
    with pytest.raises(ValidationError, match="QStash delivery"):
        Settings.model_validate({"job_delivery_provider": "qstash"})

    settings = Settings.model_validate(
        {
            "environment": "test",
            "job_delivery_provider": "qstash",
            "qstash_token": "qstash-token-at-least-32-bytes---",
            "qstash_job_runner_url": "https://jobs.example.com/internal/jobs/qstash",
        }
    )

    assert settings.job_delivery_provider == "qstash"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://rezumi:change-me-local-only@postgres:5432/rezumi",
        "postgresql+asyncpg://app:unique-password@localhost:5432/rezumi",
    ],
)
def test_production_rejects_compose_or_loopback_database_urls(database_url: str) -> None:
    with pytest.raises(ValidationError, match="Unsafe public configuration"):
        Settings.model_validate({**_safe_public_settings(), "database_url": database_url})


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
    monkeypatch.delenv("REZUMI_ANALYTICS_MAX_ATTEMPTS", raising=False)
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowed_origins", ["https://user:secret@app.example.com"]),
        ("allowed_origins", ["https://app.example.com", "https://app.example.com/"]),
        ("public_app_url", "https://user:secret@app.example.com"),
        ("google_redirect_uri", "https://app.example.com/api/v1/auth/google/callback?x=1"),
    ],
)
def test_public_urls_reject_credentials_and_ambiguous_metadata(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: value})


def test_public_mongodb_requires_tls_when_enabled() -> None:
    with pytest.raises(ValidationError, match="mongodb_url must use non-local TLS"):
        Settings.model_validate(
            {
                **_safe_public_settings("staging"),
                "mongodb_enabled": True,
                "mongodb_url": "mongodb://mongo.example.com:27017",
            }
        )

    settings = Settings.model_validate(
        {
            **_safe_public_settings("staging"),
            "mongodb_enabled": True,
            "mongodb_url": "mongodb+srv://app:secret@cluster.example.com/rezumi",
        }
    )

    assert settings.mongodb_enabled is True


def test_compose_environment_aliases_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REZUMI_DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("DOCUMENT_MAX_PAGES", "12")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:local-only@postgres:5432/rezumi",
    )

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "test"
    assert settings.log_level == "WARNING"
    assert settings.resume_max_pages == 12
    assert settings.database_url.get_secret_value().endswith("@postgres:5432/rezumi")
