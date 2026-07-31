"""Typed failures for the protected administration boundary."""


class AdministrationError(Exception):
    """Base administration failure with a stable problem code."""

    code = "administration_error"


class AdministrationValidationError(AdministrationError):
    code = "administration_validation_error"


class AdministrationDenied(AdministrationError):
    code = "administration_denied"


class AdministrationRecentAuthenticationRequired(AdministrationDenied):
    code = "administration_recent_authentication_required"


class AdministrationNotFound(AdministrationError):
    code = "administration_resource_not_found"


class AdministrationConflict(AdministrationError):
    code = "administration_conflict"


class AdministrationUnavailable(AdministrationError):
    code = "administration_unavailable"
