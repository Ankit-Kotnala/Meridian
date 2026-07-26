"""Regression tests for bounded dual-key secret rotation."""

from uuid import uuid4

from careeros.modules.identity.infrastructure.account_operation_security import (
    HmacAccountOperationTokenManager,
)
from careeros.modules.identity.infrastructure.security import HmacTokenManager
from careeros.modules.organizations.infrastructure.security import (
    HmacOrganizationInvitationManager,
)
from careeros.modules.resume_health.infrastructure.security import (
    HmacGuestCapabilityManager,
)

_OLD_SECRET = "old-secret-material-that-is-at-least-thirty-two-bytes"  # noqa: S105
_NEW_SECRET = "new-secret-material-that-is-at-least-thirty-two-bytes"  # noqa: S105


def test_identity_tokens_survive_one_bounded_rotation_window() -> None:
    old = HmacTokenManager(_OLD_SECRET)
    rotating = HmacTokenManager(_NEW_SECRET, previous_pepper=_OLD_SECRET)
    old_token = old.issue()
    new_token = rotating.issue()

    old_parsed = old.parse(old_token.encoded)
    new_parsed = rotating.parse(new_token.encoded)

    assert old_parsed is not None
    assert new_parsed is not None
    assert rotating.verify(old_token.digest, old_parsed[1])
    assert rotating.verify(new_token.digest, new_parsed[1])
    assert not old.verify(new_token.digest, new_parsed[1])


def test_guest_capabilities_survive_one_bounded_rotation_window() -> None:
    old = HmacGuestCapabilityManager(_OLD_SECRET)
    rotating = HmacGuestCapabilityManager(
        _NEW_SECRET,
        previous_pepper=_OLD_SECRET,
    )
    old_capability = old.issue()
    new_capability = rotating.issue()

    old_parsed = old.parse(old_capability.encoded)
    new_parsed = rotating.parse(new_capability.encoded)

    assert old_parsed is not None
    assert new_parsed is not None
    assert rotating.verify(old_capability.digest, old_parsed[1])
    assert rotating.verify(new_capability.digest, new_parsed[1])
    assert not old.verify(new_capability.digest, new_parsed[1])


def test_account_operation_capabilities_survive_one_rotation_window() -> None:
    operation_id = uuid4()
    old = HmacAccountOperationTokenManager(_OLD_SECRET)
    rotating = HmacAccountOperationTokenManager(
        _NEW_SECRET,
        previous_secret=_OLD_SECRET,
    )
    old_token, old_digest = old.issue_for_id(operation_id)
    new_token, new_digest = rotating.issue_for_id(operation_id)

    old_parsed = old.parse(old_token)
    new_parsed = rotating.parse(new_token)

    assert old_parsed is not None
    assert new_parsed is not None
    assert rotating.verify(old_digest, old_parsed[1])
    assert rotating.verify(new_digest, new_parsed[1])
    assert not old.verify(new_digest, new_parsed[1])


def test_organization_invitation_tokens_and_email_digests_survive_rotation() -> None:
    invitation_id = uuid4()
    email = "coach@example.test"
    old = HmacOrganizationInvitationManager(_OLD_SECRET)
    rotating = HmacOrganizationInvitationManager(
        _NEW_SECRET,
        previous_secret=_OLD_SECRET,
    )
    old_token, old_digest = old.issue_for_id(invitation_id)
    new_token, new_digest = rotating.issue_for_id(invitation_id)
    old_email_digest = old.email_digest(email)
    new_email_digest = rotating.email_digest(email)

    old_parsed = old.parse(old_token)
    new_parsed = rotating.parse(new_token)

    assert old_parsed is not None
    assert new_parsed is not None
    assert rotating.verify(old_digest, old_parsed[1])
    assert rotating.verify(new_digest, new_parsed[1])
    assert not old.verify(new_digest, new_parsed[1])
    assert rotating.verify_email_digest(old_email_digest, email)
    assert rotating.verify_email_digest(new_email_digest, email)
    assert not old.verify_email_digest(new_email_digest, email)


def test_invitation_delivery_reconstructs_the_digest_matching_rotation_key() -> None:
    invitation_id = uuid4()
    old = HmacOrganizationInvitationManager(_OLD_SECRET)
    rotating = HmacOrganizationInvitationManager(
        _NEW_SECRET,
        previous_secret=_OLD_SECRET,
    )
    old_credential = old.issue_for_delivery(invitation_id)

    assert rotating.issue_for_delivery(invitation_id) != old_credential
    assert (
        rotating.issue_for_delivery_matching(
            invitation_id,
            old_credential[1],
        )
        == old_credential
    )
    assert (
        HmacOrganizationInvitationManager(_NEW_SECRET).issue_for_delivery_matching(
            invitation_id, old_credential[1]
        )
        is None
    )
