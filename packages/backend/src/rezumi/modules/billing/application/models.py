"""DTOs and request/response models for plans & billing."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rezumi.modules.billing.domain.entities import (
    BillingCycle,
    PlanTier,
    SubscriptionStatus,
)


@dataclass(frozen=True)
class PlanSummaryDTO:
    tier: PlanTier
    name: str
    description: str
    max_resumes: int
    max_change_sets_per_month: int
    max_exports_per_month: int
    ai_grounding_enabled: bool
    interview_prep_enabled: bool
    networking_enabled: bool
    analytics_enabled: bool
    monthly_price_usd: float
    annual_price_usd: float


@dataclass(frozen=True)
class SubscriptionSummaryDTO:
    tier: PlanTier
    status: SubscriptionStatus
    billing_cycle: BillingCycle
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    entitlements: PlanSummaryDTO
    resumes_count: int
    resumes_limit: int
    change_sets_used: int
    change_sets_limit: int
    exports_used: int
    exports_limit: int


@dataclass(frozen=True)
class CreateCheckoutSessionRequest:
    user_id: UUID
    tier: PlanTier
    billing_cycle: BillingCycle
    success_url: str
    cancel_url: str


@dataclass(frozen=True)
class CheckoutSessionResponse:
    checkout_url: str
    session_id: str


@dataclass(frozen=True)
class CreatePortalSessionRequest:
    user_id: UUID
    return_url: str


@dataclass(frozen=True)
class PortalSessionResponse:
    portal_url: str


@dataclass(frozen=True)
class WebhookResultDTO:
    event_id: str
    event_type: str
    processed: bool
    detail: str
