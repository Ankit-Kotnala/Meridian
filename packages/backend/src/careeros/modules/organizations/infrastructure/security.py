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

    def __init__(self, secret: str) -> None:
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("organization invitation secret must contain at least 32 bytes")
        self._secret = encoded

    def issue_for_id(self, invitation_id: UUID) -> tuple[str, str]:
        raw_secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        return f"{invitation_id}.{raw_secret}", self.digest(raw_secret)

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
        return hmac.new(
            self._secret,
            b"careeros:organization-invitation:token:v1:" + secret.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, expected_digest: str, secret: str) -> bool:
        return hmac.compare_digest(expected_digest, self.digest(secret))

    def email_digest(self, normalized_email: str) -> str:
        return hmac.new(
            self._secret,
            b"careeros:organization-invitation:email:v1:" + normalized_email.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
