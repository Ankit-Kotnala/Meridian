"""Production identifier adapter for the Career Record bounded context."""

from uuid import UUID, uuid4


class UuidIdentifierFactory:
    """Generate cryptographically random externally visible identifiers."""

    def new(self) -> UUID:
        return uuid4()
