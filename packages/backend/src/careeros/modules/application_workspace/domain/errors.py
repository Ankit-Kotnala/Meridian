"""Application workspace domain errors."""

from __future__ import annotations


class ApplicationWorkspaceError(Exception):
    code = "application_workspace_error"


class ApplicationWorkspaceValidationError(ApplicationWorkspaceError, ValueError):
    code = "application_workspace_validation_failed"


class ApplicationWorkspaceNotFound(ApplicationWorkspaceError):
    code = "application_workspace_not_found"


class ApplicationWorkspaceConflict(ApplicationWorkspaceError):
    code = "application_workspace_conflict"


class ApplicationWorkspaceVersionConflict(ApplicationWorkspaceConflict):
    code = "application_workspace_version_conflict"


class ApplicationWorkspaceIdempotencyConflict(ApplicationWorkspaceConflict):
    code = "application_workspace_idempotency_conflict"


class ApplicationWorkspaceUnavailable(ApplicationWorkspaceError):
    code = "application_workspace_unavailable"
