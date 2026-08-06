"""Networking domain and application errors."""

from __future__ import annotations


class NetworkingError(Exception):
    code = "networking_error"


class NetworkingValidationError(NetworkingError, ValueError):
    code = "networking_validation_failed"


class NetworkingNotFound(NetworkingError):
    code = "networking_not_found"


class NetworkingConflict(NetworkingError):
    code = "networking_conflict"


class NetworkingVersionConflict(NetworkingConflict):
    code = "networking_version_conflict"


class NetworkingIdempotencyConflict(NetworkingConflict):
    code = "networking_idempotency_conflict"


class NetworkingConsentRequired(NetworkingConflict):
    code = "networking_consent_required"


class NetworkingQuotaExceeded(NetworkingError):
    """A bounded owner or contact collection reached its safe storage limit."""

    code = "networking_quota_exceeded"


class NetworkingLeaseConflict(NetworkingConflict):
    code = "networking_lease_conflict"


class NetworkingUnavailable(NetworkingError):
    code = "networking_unavailable"
