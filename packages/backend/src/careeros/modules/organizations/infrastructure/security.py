"""Context-separated HMAC invitation tokens and email digests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from uuid import UUID

_TOKEN = re.compile(r"^(?P<id>[0-9a-fA-F-]{36})\.(?P<secret>[A-Za-z0-9_-]{43})$")


class HmacOrganizationInvitationManager:
    """Issue opaque invitation material without storing the raw token."""

    def __init__(self, secret: str, previous_secret: str | None = None) -> None:
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("organization invitation secret must contain at least 32 bytes")
        previous = previous_secret.encode("utf-8") if previous_secret is not None else None
        if previous is not None and len(previous) < 32:
            raise ValueError(
                "previous organization invitation secret must contain at least 32 bytes"
            )
        self._secret = encoded
        self._verification_secrets = (encoded,) + (
            (previous,) if previous is not None and previous != encoded else ()
        )

    def issue_for_id(self, invitation_id: UUID) -> tuple[str, str]:
        raw_secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        return f"{invitation_id}.{raw_secret}", self.digest(raw_secret)

    def issue_for_delivery(self, invitation_id: UUID) -> tuple[str, str]:
        return self._delivery_with(self._secret, invitation_id)

    def issue_for_delivery_matching(
        self,
        invitation_id: UUID,
        expected_digest: str,
    ) -> tuple[str, str] | None:
        candidates = tuple(
            self._delivery_with(key, invitation_id) for key in self._verification_secrets
        )
        for token, digest in candidates:
            if hmac.compare_digest(expected_digest, digest):
                return token, digest
        return None

    @staticmethod
    def _delivery_with(key: bytes, invitation_id: UUID) -> tuple[str, str]:
        material = hmac.new(
            key,
            b"careeros:organization-invitation:delivery:v1:" + invitation_id.bytes,
            hashlib.sha256,
        ).digest()
        raw_secret = base64.urlsafe_b64encode(material).rstrip(b"=").decode()
        digest = HmacOrganizationInvitationManager._token_digest_with(key, raw_secret)
        return f"{invitation_id}.{raw_secret}", digest

    def parse(self, encoded: str) -> tuple[UUID, str] | None:
        if len(encoded) > 128:
            return None
        match = _TOKEN.fullmatch(encoded)
        if match is None:
            return None
        try:
            return UUID(match.group("id")), match.group("secret")
        except ValueError:
            return None

    def digest(self, secret: str) -> str:
        return self._token_digest_with(self._secret, secret)

    @staticmethod
    def _token_digest_with(key: bytes, secret: str) -> str:
        return hmac.new(
            key,
            b"careeros:organization-invitation:token:v1:" + secret.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, expected_digest: str, secret: str) -> bool:
        matches = tuple(
            hmac.compare_digest(expected_digest, self._token_digest_with(key, secret))
            for key in self._verification_secrets
        )
        return any(matches)

    def verify_email_digest(self, expected_digest: str, normalized_email: str) -> bool:
        matches = tuple(
            hmac.compare_digest(expected_digest, self._email_digest_with(key, normalized_email))
            for key in self._verification_secrets
        )
        return any(matches)

    def email_digest(self, normalized_email: str) -> str:
        return self._email_digest_with(self._secret, normalized_email)

    @staticmethod
    def _email_digest_with(key: bytes, normalized_email: str) -> str:
        return hmac.new(
            key,
            b"careeros:organization-invitation:email:v1:" + normalized_email.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
