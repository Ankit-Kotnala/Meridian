"""Runtime clock and UUID adapters for networking."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidIdentifierFactory:
    def new(self) -> UUID:
        return uuid4()
