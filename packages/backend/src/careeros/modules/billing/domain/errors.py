"""Billing and plan entitlement domain errors."""


class BillingError(Exception):
    """Base error for billing operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PlanNotFoundError(BillingError):
    """Raised when an unknown plan tier is requested."""


class QuotaExceededError(BillingError):
    """Raised when an operation exceeds the plan entitlement limits."""

    def __init__(self, feature: str, limit: int, current: int) -> None:
        super().__init__(
            f"Quota exceeded for feature '{feature}': limit is {limit}, current usage is {current}."
        )
        self.feature = feature
        self.limit = limit
        self.current = current


class SubscriptionNotFoundError(BillingError):
    """Raised when no active subscription record is found."""
