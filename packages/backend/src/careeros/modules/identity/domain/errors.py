"""Safe identity-domain errors translated by delivery adapters."""


class IdentityError(Exception):
    """Base error carrying a stable non-sensitive machine code."""

    code = "identity_error"


class IdentityUnavailable(IdentityError):
    code = "identity_unavailable"


class AuthenticationRequired(IdentityError):
    code = "authentication_required"


class InvalidCredentials(IdentityError):
    code = "invalid_credentials"


class EmailVerificationRequired(IdentityError):
    code = "email_verification_required"


class InvalidOrExpiredToken(IdentityError):
    code = "invalid_or_expired_token"


class ResourceNotFound(IdentityError):
    code = "not_found"


class VersionConflict(IdentityError):
    code = "version_conflict"


class IdentityConflict(IdentityError):
    """Internal uniqueness race translated into a safe idempotent outcome."""

    code = "identity_conflict"


class RateLimited(IdentityError):
    code = "rate_limited"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(self.code)
        self.retry_after_seconds = retry_after_seconds


class CsrfRejected(IdentityError):
    code = "csrf_rejected"


class OAuthUnavailable(IdentityError):
    code = "oauth_unavailable"


class OAuthCollision(IdentityError):
    code = "oauth_account_link_required"


class OAuthFlowRejected(IdentityError):
    code = "oauth_flow_rejected"


class RecentAuthenticationRequired(IdentityError):
    code = "recent_authentication_required"
