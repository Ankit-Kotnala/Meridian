"""Role Explorer domain errors."""


class RoleReadinessError(Exception):
    """Base class for safe Role Readiness request failures."""

    code = "role_readiness_error"


class RoleReadinessUnavailable(RoleReadinessError):
    code = "role_readiness_unavailable"


class RoleReadinessNotFound(RoleReadinessError):
    code = "role_readiness_not_found"


class RoleReadinessValidationError(RoleReadinessError):
    code = "role_readiness_validation_error"


class RoleReadinessConflict(RoleReadinessError):
    code = "role_readiness_conflict"


class RoleReadinessVersionConflict(RoleReadinessError):
    code = "role_readiness_version_conflict"


class RoleReadinessIdempotencyConflict(RoleReadinessError):
    code = "role_readiness_idempotency_conflict"
