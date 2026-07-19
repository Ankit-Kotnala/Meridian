"""Domain errors for Phase 7 resume builder and export workflows."""

from __future__ import annotations


class ResumeBuilderError(Exception):
    """Base error for owner-scoped resume builder failures."""


class ResumeBuilderUnavailable(ResumeBuilderError):
    """Raised when a required resume builder dependency is unavailable."""


class ResumeBuilderNotFound(ResumeBuilderError):
    """Raised when an owner-scoped resume resource cannot be found."""


class ResumeBuilderConflict(ResumeBuilderError):
    """Raised when a requested transition conflicts with current state."""


class ResumeBuilderVersionConflict(ResumeBuilderConflict):
    """Raised when an optimistic concurrency precondition fails."""


class ResumeBuilderIdempotencyConflict(ResumeBuilderConflict):
    """Raised when an idempotency key is replayed with a different request."""


class ResumeBuilderValidationError(ResumeBuilderError):
    """Raised when a resume builder command fails validation."""


class ResumeExportBlocked(ResumeBuilderConflict):
    """Raised when verification blocks export release."""
