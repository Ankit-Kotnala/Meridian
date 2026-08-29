"""Safe career-record domain errors for delivery adapters to translate."""


class CareerRecordError(Exception):
    """Base class for expected career-record failures."""


class CareerRecordUnavailable(CareerRecordError):
    """Career Record infrastructure is unavailable for this process."""


class CareerRecordNotFound(CareerRecordError):
    """The owned resource does not exist in the caller's scope."""


class CareerRecordConflict(CareerRecordError):
    """The requested mutation conflicts with current durable state."""


class CareerRecordVersionConflict(CareerRecordConflict):
    """The optimistic-concurrency version is stale."""


class CareerRecordValidationError(CareerRecordError, ValueError):
    """A command or persisted value violates a domain invariant."""


class CareerRecordIdempotencyConflict(CareerRecordConflict):
    """An idempotency key was reused for a different operation."""


class CareerRecordSourceUnavailable(CareerRecordConflict):
    """An external source cannot currently prove the requested scope."""


class CareerRecordTransitionRejected(CareerRecordConflict):
    """An evidence/proposal/achievement transition is not allowed."""


class CareerRecordCursorInvalid(CareerRecordValidationError):
    """A collection cursor is malformed or outside supported bounds."""
