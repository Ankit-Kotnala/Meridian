"""Celery adapters for durable account privacy operations."""

from __future__ import annotations

import pytest
from careeros.modules.identity.application import (
    AccountExportCleanupResult,
    AccountOperationBatchResult,
)

from careeros_worker.base import RetryableTaskError
from careeros_worker.config import WorkerSettings
from careeros_worker.tasks import identity


def _settings() -> WorkerSettings:
    return WorkerSettings.model_validate(
        {
            "environment": "test",
            "account_operation_batch_size": 7,
            "account_export_cleanup_batch_size": 11,
        }
    )


def test_privacy_task_returns_only_bounded_operational_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_process(
        settings: WorkerSettings,
        limit: int,
    ) -> AccountOperationBatchResult:
        assert settings.environment == "test"
        assert limit == 7
        return AccountOperationBatchResult(
            claimed=5,
            succeeded=2,
            blocked=1,
            deferred=1,
            dead_lettered=1,
        )

    monkeypatch.setattr(identity, "get_settings", _settings)
    monkeypatch.setattr(identity, "process_account_operations", fake_process)

    assert identity.process_account_privacy_operations.run() == {
        "claimed": 5,
        "succeeded": 2,
        "blocked": 1,
        "deferred": 1,
        "dead_lettered": 1,
    }


def test_export_cleanup_task_returns_safe_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_cleanup(
        settings: WorkerSettings,
        limit: int,
    ) -> AccountExportCleanupResult:
        assert settings.environment == "test"
        assert limit == 11
        return AccountExportCleanupResult(completed=3, failed=1)

    monkeypatch.setattr(identity, "get_settings", _settings)
    monkeypatch.setattr(identity, "cleanup_account_exports", fake_cleanup)

    assert identity.cleanup_expired_account_exports.run() == {
        "completed": 3,
        "failed": 1,
    }


def test_privacy_task_maps_internal_failure_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(
        _settings: WorkerSettings,
        _limit: int,
    ) -> AccountOperationBatchResult:
        raise RuntimeError("s3://private-bucket/user-object")

    monkeypatch.setattr(identity, "get_settings", _settings)
    monkeypatch.setattr(identity, "process_account_operations", fail)

    with pytest.raises(
        RetryableTaskError,
        match="account_privacy_processing_unavailable",
    ):
        identity.process_account_privacy_operations.run(limit=1)
