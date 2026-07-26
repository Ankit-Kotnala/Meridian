"""Organization invitation Celery adapter tests."""

from __future__ import annotations

import pytest
from careeros.modules.organizations.application import InvitationDeliveryBatchResult

from careeros_worker.tasks import organizations
from careeros_worker.base import RetryableTaskError
from careeros_worker.config import WorkerSettings


def _settings() -> WorkerSettings:
    return WorkerSettings.model_validate(
        {
            "environment": "test",
            "organization_invitation_batch_size": 12,
        }
    )


def test_invitation_task_returns_only_bounded_operational_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_process(
        settings: WorkerSettings,
        limit: int,
    ) -> InvitationDeliveryBatchResult:
        assert settings.environment == "test"
        assert limit == 12
        return InvitationDeliveryBatchResult(
            claimed=4,
            delivered=2,
            cancelled=1,
            deferred=1,
            dead_lettered=0,
        )

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_organization_invitations", fake_process)

    assert organizations.deliver_organization_invitations.run() == {
        "claimed": 4,
        "delivered": 2,
        "cancelled": 1,
        "deferred": 1,
        "dead_lettered": 0,
    }


def test_invitation_task_maps_internal_failure_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(_settings: WorkerSettings, _limit: int) -> InvitationDeliveryBatchResult:
        raise RuntimeError("smtp://private-credential@example.test")

    monkeypatch.setattr(tasks, "get_settings", _settings)
    monkeypatch.setattr(tasks, "process_organization_invitations", fail)

    with pytest.raises(
        RetryableTaskError,
        match="organization_invitation_delivery_unavailable",
    ):
        organizations.deliver_organization_invitations.run(limit=1)
