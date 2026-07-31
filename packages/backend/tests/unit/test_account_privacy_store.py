"""Pure fail-closed checks for account privacy schema classification."""

import pytest

from careeros.integrations.privacy.postgres_s3 import (
    _export_row,
    _validate_erasure_object_inventory,
)


def test_erasure_refuses_an_unclassified_future_object_reference() -> None:
    with pytest.raises(
        RuntimeError,
        match=r"future_private_files\.new_object_key",
    ):
        _validate_erasure_object_inventory(
            {
                "account_operations": {"artifact_object_key", "user_id"},
                "future_private_files": {"new_object_key", "owner_user_id"},
            }
        )


def test_export_redacts_secrets_object_keys_and_invitation_recipient() -> None:
    assert _export_row(
        {
            "id": "fictional-id",
            "invited_email_normalized": "recipient@example.test",
            "password_hash": "fictional-private-hash",
            "quarantine_object_key": "private/object.pdf",
            "role": "coach",
        }
    ) == {
        "id": "fictional-id",
        "role": "coach",
    }
