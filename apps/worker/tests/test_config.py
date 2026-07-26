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
            "database_url": "postgresql+asyncpg://careeros:private@postgres:5432/careeros",
            "s3_access_key_id": "private-access",
            "s3_secret_access_key": "private-storage-secret",
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
    with pytest.raises(ValidationError, match=r"production|Production"):
        WorkerSettings.model_validate({"environment": "production"})


def test_production_rejects_compose_redis_service_defaults() -> None:
    with pytest.raises(ValidationError, match=r"production|Production"):
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
            "database_url": (
                "postgresql+asyncpg://careeros:production-credential@"
                "postgres.internal.example:5432/careeros"
            ),
            "s3_endpoint_url": "https://s3.internal.example",
            "s3_public_endpoint_url": "https://uploads.example.com",
            "s3_use_ssl": True,
            "s3_secret_access_key": "production-storage-secret",
            "malware_scanner_provider": "clamav",
            "clamav_host": "scanner.internal.example",
            "organization_invitation_secret": "production-invitation-secret-at-least-32-bytes",
            "email_provider": "smtp",
            "email_from_address": "no-reply@example.com",
            "smtp_host": "smtp.internal.example",
            "smtp_start_tls": True,
            "public_app_url": "https://app.example.com",
        }
    )

    assert settings.environment == "production"


def test_document_limits_and_scanner_settings_are_bounded() -> None:
    settings = WorkerSettings.model_validate(
        {
            "document_max_bytes": 2_000_000,
            "document_max_uncompressed_bytes": 8_000_000,
            "document_max_pages": 12,
            "document_max_archive_entries": 100,
            "document_max_compression_ratio": 25,
            "document_max_extracted_characters": 250_000,
            "document_max_extracted_blocks": 2_500,
            "document_max_serialized_artifact_bytes": 1_048_576,
            "resume_job_reconciliation_interval_seconds": 30,
            "resume_job_reconciliation_stale_seconds": 600,
            "attachment_job_reconciliation_interval_seconds": 45,
            "attachment_job_reconciliation_stale_seconds": 720,
            "malware_scanner_provider": "clamav",
            "clamav_host": "scanner",
            "clamav_timeout_seconds": 15,
        }
    )

    assert settings.malware_scanner_provider == "clamav"
    assert settings.document_max_pages == 12
    assert settings.document_max_extracted_blocks == 2_500
    assert settings.document_max_serialized_artifact_bytes == 1_048_576
    assert settings.resume_job_reconciliation_interval_seconds == 30
    assert settings.resume_job_reconciliation_stale_seconds == 600
    assert settings.attachment_job_reconciliation_interval_seconds == 45
    assert settings.attachment_job_reconciliation_stale_seconds == 720
    assert settings.document_temp_root.as_posix() == "/tmp/careeros"  # noqa: S108


def test_phase9_worker_policies_are_bounded_and_configurable() -> None:
    settings = WorkerSettings.model_validate(
        {
            "environment": "test",
            "analytics_max_attempts": 4,
            "analytics_job_lease_seconds": 420,
            "analytics_retry_seconds": 45,
            "analytics_outbox_interval_seconds": 7,
            "analytics_reconciliation_interval_seconds": 75,
            "networking_reminder_lease_seconds": 90,
            "networking_reminder_retry_seconds": 40,
            "networking_reminder_interval_seconds": 35,
            "networking_reconciliation_interval_seconds": 80,
        }
    )

    assert settings.analytics_max_attempts == 4
    assert settings.analytics_job_lease_seconds == 420
    assert settings.analytics_outbox_interval_seconds == 7
    assert settings.analytics_reconciliation_interval_seconds == 75
    assert settings.networking_reminder_lease_seconds == 90
    assert settings.networking_reminder_retry_seconds == 40
    assert settings.networking_reminder_interval_seconds == 35
    assert settings.networking_reconciliation_interval_seconds == 80


def test_analytics_lease_must_outlive_worker_hard_timeout() -> None:
    with pytest.raises(ValidationError, match="analytics lease"):
        WorkerSettings.model_validate(
            {
                "environment": "test",
                "task_time_limit_seconds": 300,
                "analytics_job_lease_seconds": 300,
            }
        )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {
                "document_max_bytes": 5_000_000,
                "document_max_uncompressed_bytes": 4_000_000,
            },
            "expansion limit",
        ),
        ({"document_temp_root": "relative/path"}, "absolute path"),
        (
            {
                "document_processing_timeout_seconds": 270,
                "task_soft_time_limit_seconds": 270,
            },
            "processing timeout",
        ),
        ({"clamav_host": "http://scanner:3310"}, "hostname"),
        ({"s3_public_endpoint_url": "http://user:secret@localhost:9000"}, "credentials"),
    ],
)
def test_unsafe_document_configuration_is_rejected(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        WorkerSettings.model_validate(values)


def test_production_cannot_disable_required_malware_scanning() -> None:
    with pytest.raises(ValidationError, match="ClamAV scanning must be enabled"):
        WorkerSettings.model_validate(
            {
                "environment": "production",
                "broker_url": "rediss://broker.internal.example:6380/0",
                "result_backend": "rediss://backend.internal.example:6380/1",
                "database_url": (
                    "postgresql+asyncpg://careeros:production-credential@"
                    "postgres.internal.example:5432/careeros"
                ),
                "s3_endpoint_url": "https://s3.internal.example",
                "s3_public_endpoint_url": "https://uploads.example.com",
                "s3_use_ssl": True,
                "s3_secret_access_key": "production-storage-secret",
                "malware_scanner_provider": "disabled",
                "clamav_host": "scanner.internal.example",
            }
        )
