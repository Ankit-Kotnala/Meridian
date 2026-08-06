"""High-entropy guest capability and clock implementations."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from rezumi.modules.resume_health.application.models import CapabilitySecret


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class HmacGuestCapabilityManager:
    """Issue opaque id+secret capabilities and retain only HMAC digests."""

    def __init__(self, pepper: str) -> None:
        if len(pepper.encode("utf-8")) < 32:
            raise ValueError("guest capability pepper must contain at least 32 UTF-8 bytes")
        self._pepper = pepper.encode("utf-8")

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
        return hmac.compare_digest(expected, self._digest(secret))

    def _digest(self, secret: str) -> bytes:
        return hmac.new(self._pepper, secret.encode("utf-8"), hashlib.sha256).digest()
