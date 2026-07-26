"""Organization tenancy domain errors."""


class OrganizationError(Exception):
    """Base organization error with a stable delivery code."""

    code = "organization_rejected"


class OrganizationValidationError(OrganizationError):
    code = "organization_validation_failed"


class OrganizationNotFound(OrganizationError):
    code = "organization_not_found"


class OrganizationForbidden(OrganizationError):
    code = "organization_forbidden"


class OrganizationConflict(OrganizationError):
    code = "organization_conflict"


class OrganizationVersionConflict(OrganizationConflict):
    code = "organization_version_conflict"


class OrganizationIdempotencyConflict(OrganizationConflict):
    code = "organization_idempotency_conflict"


class OrganizationQuotaExceeded(OrganizationConflict):
    code = "organization_safety_limit_reached"


class OrganizationInvitationRejected(OrganizationError):
    code = "organization_invitation_rejected"


class OrganizationUnavailable(OrganizationError):
    code = "organization_unavailable"
