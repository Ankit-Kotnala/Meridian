"""High-entropy guest capability and clock implementations."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from careeros.modules.resume_health.application.models import CapabilitySecret


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class HmacGuestCapabilityManager:
    """Issue opaque id+secret capabilities and retain only HMAC digests."""

    def __init__(self, pepper: str, previous_pepper: str | None = None) -> None:
        encoded = pepper.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("guest capability pepper must contain at least 32 UTF-8 bytes")
        previous = previous_pepper.encode("utf-8") if previous_pepper is not None else None
        if previous is not None and len(previous) < 32:
            raise ValueError(
                "previous guest capability pepper must contain at least 32 UTF-8 bytes"
            )
        self._pepper = encoded
        self._verification_peppers = (encoded,) + (
            (previous,) if previous is not None and previous != encoded else ()
        )

    def issue(self) -> CapabilitySecret:
        capability_id = uuid4()
        secret = secrets.token_urlsafe(32)
        return CapabilitySecret(
            id=capability_id,
            encoded=f"{capability_id}.{secret}",
            digest=self._digest(secret),
        )

    def parse(self, encoded: str) -> tuple[UUID, str] | None:
        identifier, separator, secret = encoded.partition(".")
        if not separator or not secret or len(secret) > 128:
            return None
        try:
            capability_id = UUID(identifier)
        except ValueError:
            return None
        return capability_id, secret

    def verify(self, expected: bytes, secret: str) -> bool:
        matches = tuple(
            hmac.compare_digest(expected, self._digest_with(pepper, secret))
            for pepper in self._verification_peppers
        )
        return any(matches)

    def _digest(self, secret: str) -> bytes:
        return self._digest_with(self._pepper, secret)

    @staticmethod
    def _digest_with(pepper: bytes, secret: str) -> bytes:
        return hmac.new(pepper, secret.encode("utf-8"), hashlib.sha256).digest()
