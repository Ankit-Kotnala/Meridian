"""Job Match domain errors."""


class JobMatchError(Exception):
    """Base class for safe Job Match request failures."""

    code = "job_match_error"


class JobMatchUnavailable(JobMatchError):
    code = "job_match_unavailable"


class JobMatchNotFound(JobMatchError):
    code = "job_match_not_found"


class JobMatchValidationError(JobMatchError):
    code = "job_match_validation_error"


class JobMatchConflict(JobMatchError):
    code = "job_match_conflict"


class JobMatchVersionConflict(JobMatchError):
    code = "job_match_version_conflict"


class JobMatchIdempotencyConflict(JobMatchError):
    code = "job_match_idempotency_conflict"


class JobImportRejected(JobMatchError):
    code = "job_import_rejected"
