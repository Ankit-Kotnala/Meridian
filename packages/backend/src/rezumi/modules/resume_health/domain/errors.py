"""Safe domain failures for resume ingestion and analysis."""


class ResumeHealthError(Exception):
    """Base error carrying a stable, non-sensitive machine code."""

    code = "resume_health_error"


class ResumeHealthUnavailable(ResumeHealthError):
    code = "resume_health_unavailable"


class ResumeResourceNotFound(ResumeHealthError):
    code = "resume_resource_not_found"


class ResumeOwnershipDenied(ResumeHealthError):
    code = "resume_resource_not_found"


class GuestCapabilityRejected(ResumeHealthError):
    code = "guest_capability_rejected"


class UploadRejected(ResumeHealthError):
    code = "upload_rejected"

    def __init__(self, code: str = "upload_rejected") -> None:
        super().__init__(code)
        self.code = code


class UploadExpired(ResumeHealthError):
    code = "upload_expired"


class ResumeVersionConflict(ResumeHealthError):
    code = "resume_version_conflict"


class ResumeStateConflict(ResumeHealthError):
    code = "resume_state_conflict"


class IdempotencyConflict(ResumeHealthError):
    code = "idempotency_conflict"


class UnsafeDocument(ResumeHealthError):
    """A hostile or unsupported document failed closed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RetryableProcessingFailure(ResumeHealthError):
    """A provider/infrastructure failure which policy permits retrying."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ProcessingCancelled(ResumeHealthError):
    code = "processing_cancelled"
