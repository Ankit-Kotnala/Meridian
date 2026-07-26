"""Configuration contracts for bounded dual-key secret rotation."""

import pytest
from pydantic import ValidationError

from careeros_api.config import Settings


@pytest.mark.parametrize(
    "field",
    [
        "auth_token_previous_pepper",
        "account_operation_previous_pepper",
        "resume_capability_previous_pepper",
        "bff_client_signal_previous_secret",
    ],
)
def test_blank_previous_rotation_secret_is_normalized(field: str) -> None:
    settings = Settings.model_validate({field: ""})

    assert getattr(settings, field) is None


@pytest.mark.parametrize(
    "field",
    [
        "auth_token_previous_pepper",
        "account_operation_previous_pepper",
        "resume_capability_previous_pepper",
        "bff_client_signal_previous_secret",
    ],
)
def test_previous_rotation_secret_requires_full_entropy(field: str) -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings.model_validate({field: "too-short"})


@pytest.mark.parametrize(
    ("current_field", "previous_field"),
    [
        ("auth_token_pepper", "auth_token_previous_pepper"),
        ("account_operation_pepper", "account_operation_previous_pepper"),
        ("resume_capability_pepper", "resume_capability_previous_pepper"),
        ("bff_client_signal_secret", "bff_client_signal_previous_secret"),
    ],
)
def test_previous_rotation_secret_must_differ_from_current(
    current_field: str,
    previous_field: str,
) -> None:
    material = "rotation-secret-material-that-is-at-least-thirty-two-bytes"

    with pytest.raises(ValidationError, match="must differ"):
        Settings.model_validate(
            {
                current_field: material,
                previous_field: material,
            }
        )
