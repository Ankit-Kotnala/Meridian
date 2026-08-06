"""Cryptographic and validation adapters for identity use cases."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from email_validator import EmailNotValidError, validate_email

from rezumi.modules.identity.application.models import IssuedToken


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class Argon2PasswordHasher:
    """Calibrated Argon2id password hashing kept off the event loop."""

    def __init__(self) -> None:
        self._hasher = ArgonPasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, password_hash, password)
        except (InvalidHashError, VerificationError):
            return False

    async def verify_dummy(self, password: str) -> None:
        await self.verify(self._dummy_hash, password)


class HmacTokenManager:
    """Issue opaque UUID/secret pairs while storing only keyed digests."""

    def __init__(self, pepper: str) -> None:
        encoded = pepper.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("auth token pepper must be at least 32 UTF-8 bytes")
        self._pepper = encoded

    def issue(self) -> IssuedToken:
        return self.issue_for_id(uuid4())

    def issue_for_id(self, token_id: UUID) -> IssuedToken:
        secret = secrets.token_urlsafe(32)
        return IssuedToken(
            id=token_id,
            encoded=f"{token_id}.{secret}",
            digest=self.digest(secret),
        )

    def digest(self, secret: str) -> bytes:
        return hmac.new(self._pepper, secret.encode("utf-8"), hashlib.sha256).digest()

    def parse(self, encoded: str) -> tuple[UUID, str] | None:
        token_id, separator, secret = encoded.partition(".")
        if separator != "." or not secret or len(encoded) > 256:
            return None
        try:
            parsed_id = UUID(token_id)
        except ValueError:
            return None
        return parsed_id, secret

    def verify(self, expected: bytes, secret: str) -> bool:
        return hmac.compare_digest(expected, self.digest(secret))


class NormalizedEmailValidator:
    """Normalize mailbox identity without request-time DNS lookups."""

    def normalize(self, value: str) -> str:
        try:
            result = validate_email(value.strip(), check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError("email address is invalid") from exc
        return result.normalized.casefold()
