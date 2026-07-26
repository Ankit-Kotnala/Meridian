"""Context-separated account-operation capabilities and user fingerprints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from uuid import UUID, uuid4

_TOKEN = re.compile(r"^(?P<id>[0-9a-fA-F-]{36})\.(?P<secret>[A-Za-z0-9_-]{43})$")


class UuidAccountOperationIdentifierFactory:
    def new(self) -> UUID:
        return uuid4()


class HmacAccountOperationTokenManager:
    def __init__(self, secret: str, previous_secret: str | None = None) -> None:
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("account operation secret must contain at least 32 bytes")
        previous = previous_secret.encode("utf-8") if previous_secret is not None else None
        if previous is not None and len(previous) < 32:
            raise ValueError("previous account operation secret must contain at least 32 bytes")
        self._secret = encoded
        self._verification_secrets = (encoded,) + (
            (previous,) if previous is not None and previous != encoded else ()
        )

    def issue_for_id(self, operation_id: UUID) -> tuple[str, str]:
        material = hmac.new(
            self._secret,
            b"careeros:account-operation:capability:v1:" + operation_id.bytes,
            hashlib.sha256,
        ).digest()
        secret = base64.urlsafe_b64encode(material).rstrip(b"=").decode()
        return f"{operation_id}.{secret}", self._digest(secret)

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

    def verify(self, expected_digest: str, secret: str) -> bool:
        matches = tuple(
            hmac.compare_digest(expected_digest, self._digest_with(key, secret))
            for key in self._verification_secrets
        )
        return any(matches)

    def fingerprint(self, user_id: UUID) -> str:
        return hmac.new(
            self._secret,
            b"careeros:account-operation:user:v1:" + user_id.bytes,
            hashlib.sha256,
        ).hexdigest()

    def _digest(self, secret: str) -> str:
        return self._digest_with(self._secret, secret)

    @staticmethod
    def _digest_with(key: bytes, secret: str) -> str:
        return hmac.new(
            key,
            b"careeros:account-operation:token:v1:" + secret.encode(),
            hashlib.sha256,
        ).hexdigest()
