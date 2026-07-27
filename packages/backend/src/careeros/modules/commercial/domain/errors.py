"""Commercial-domain errors."""


class CommercialError(Exception):
    """Base class for safe commercial failures."""


class CommercialValidationError(CommercialError):
    """A command or provider payload violates the commercial contract."""


class CommercialUnavailable(CommercialError):
    """Commercial actions are disabled or require owner configuration."""


class CommercialNotFound(CommercialError):
    """An owner-scoped commercial resource is unavailable."""


class CommercialConflict(CommercialError):
    """Persisted commercial state conflicts with the requested transition."""


class CommercialIdempotencyConflict(CommercialConflict):
    """An idempotency key was replayed with a different command."""


class BillingSignatureRejected(CommercialError):
    """A billing webhook signature or timestamp is invalid."""


class BillingEventConflict(CommercialConflict):
    """A provider event identifier was reused with different bytes."""
