"""Worker invitation-secret rotation configuration contracts."""

import pytest
from pydantic import ValidationError

from careeros_worker.config import WorkerSettings


def test_blank_previous_invitation_secret_is_absent() -> None:
    settings = WorkerSettings.model_validate({"organization_invitation_previous_secret": ""})

    assert settings.organization_invitation_previous_secret is None


def test_previous_invitation_secret_requires_full_entropy() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        WorkerSettings.model_validate({"organization_invitation_previous_secret": "too-short"})


def test_previous_invitation_secret_must_differ_from_current() -> None:
    material = "worker-rotation-secret-at-least-thirty-two-bytes"

    with pytest.raises(ValidationError, match="must differ"):
        WorkerSettings.model_validate(
            {
                "organization_invitation_secret": material,
                "organization_invitation_previous_secret": material,
            }
        )
