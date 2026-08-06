"""Safe domain errors for Interview Prep."""


class InterviewPrepError(Exception):
    """Base class for transport-safe Interview Prep failures."""

    code = "interview_prep_error"


class InterviewPrepUnavailable(InterviewPrepError):
    code = "interview_prep_unavailable"


class InterviewPrepNotFound(InterviewPrepError):
    code = "interview_prep_not_found"


class InterviewPrepValidationError(InterviewPrepError, ValueError):
    code = "interview_prep_validation_failed"


class InterviewPrepConflict(InterviewPrepError):
    code = "interview_prep_conflict"


class InterviewPrepQuotaExceeded(InterviewPrepConflict):
    code = "interview_prep_quota_exceeded"


class InterviewPrepVersionConflict(InterviewPrepConflict):
    code = "interview_prep_version_conflict"


class InterviewPrepIdempotencyConflict(InterviewPrepConflict):
    code = "interview_prep_idempotency_conflict"
