"""Domain exceptions for Change Studio and grounded suggestions."""

from __future__ import annotations


class ChangeStudioError(Exception):
    code = "change_studio_error"


class ChangeStudioUnavailable(ChangeStudioError):
    code = "change_studio_unavailable"


class ChangeStudioRateLimited(ChangeStudioError):
    code = "change_studio_rate_limited"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(self.code)
        self.retry_after_seconds = max(1, retry_after_seconds)


class ChangeStudioNotFound(ChangeStudioError):
    code = "change_studio_not_found"


class ChangeStudioValidationError(ChangeStudioError):
    code = "change_studio_validation_error"


class ChangeStudioConflict(ChangeStudioError):
    code = "change_studio_conflict"


class ChangeStudioVersionConflict(ChangeStudioConflict):
    code = "change_studio_version_conflict"


class ChangeStudioIdempotencyConflict(ChangeStudioConflict):
    code = "change_studio_idempotency_conflict"


class GroundingFailed(ChangeStudioValidationError):
    code = "grounding_failed"


class ProviderOutputRejected(ChangeStudioValidationError):
    code = "provider_output_rejected"
