"""Repository and provider ports for plans & billing."""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID

from rezumi.modules.billing.application.models import (
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    PortalSessionResponse,
)
from rezumi.modules.billing.domain.entities import (
    UsageQuota,
    UserSubscription,
)


class BillingRepositoryPort(ABC):
    """Persistence operations for subscriptions, quotas, and webhooks."""

    @abstractmethod
    async def get_subscription(self, user_id: UUID) -> UserSubscription | None:
        """Fetch active user subscription or None."""

    @abstractmethod
    async def save_subscription(self, subscription: UserSubscription) -> UserSubscription:
        """Create or update subscription."""

    @abstractmethod
    async def get_quota(self, user_id: UUID) -> UsageQuota:
        """Fetch current period usage quota."""

    @abstractmethod
    async def increment_usage(
        self, user_id: UUID, change_sets: int = 0, exports: int = 0
    ) -> UsageQuota:
        """Increment usage metrics."""

    @abstractmethod
    async def is_webhook_processed(self, event_id: str) -> bool:
        """Check if webhook event ID was already processed (idempotency)."""

    @abstractmethod
    async def record_webhook_event(
        self, event_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Record processed webhook event."""


class BillingProviderPort(Protocol):
    """External payment/subscription gateway provider (e.g. Stripe or Mock)."""

    async def create_checkout_session(
        self, request: CreateCheckoutSessionRequest, customer_id: str | None
    ) -> CheckoutSessionResponse: ...

    async def create_portal_session(
        self, request: CreatePortalSessionRequest, customer_id: str
    ) -> PortalSessionResponse: ...

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict[str, Any]: ...
