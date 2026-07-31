"""Commercial application commands and provider-neutral records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from careeros.modules.commercial.domain import (
    BillingEvent,
    CommercialPlan,
    Subscription,
    SubscriptionStatus,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID | None
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class CheckoutCommand:
    plan_code: str
    success_url: str
    cancel_url: str


@dataclass(frozen=True, slots=True)
class PortalCommand:
    return_url: str


@dataclass(frozen=True, slots=True)
class BillingSession:
    url: str
    expires_at: datetime
    provider_customer_reference: str


@dataclass(frozen=True, slots=True)
class ProviderSubscriptionEvent:
    provider_event_id: str
    payload_sha256: str
    event_kind: str
    provider_sequence: int
    provider_occurred_at: datetime
    provider_customer_reference: str
    provider_subscription_reference: str
    provider_price_reference: str
    subscription_status: SubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    operation: str
    idempotency_key: str
    request_fingerprint: str
    response_payload: Mapping[str, object]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_payload", MappingProxyType(dict(self.response_payload)))


@dataclass(frozen=True, slots=True)
class PlanCatalog:
    plans: tuple[CommercialPlan, ...]
    owner_configuration_required: bool


@dataclass(frozen=True, slots=True)
class SubscriptionView:
    subscription: Subscription | None
    plan: CommercialPlan | None
    billing_available: bool


@dataclass(frozen=True, slots=True)
class WebhookResult:
    event: BillingEvent
    replayed: bool
