"""Pydantic schemas for plans & billing endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class BillingSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


class PlanResponse(BillingSchema):
    tier: str
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


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]


class SubscriptionSummaryResponse(BaseModel):
    tier: str
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    entitlements: PlanResponse
    resumes_count: int
    resumes_limit: int
    change_sets_used: int
    change_sets_limit: int
    exports_used: int
    exports_limit: int


class CheckoutSessionRequest(BaseModel):
    tier: Literal["sprint", "pro", "coach"]
    billing_cycle: Literal["monthly", "annual"] = "monthly"
    success_url: str = Field(..., max_length=1024)
    cancel_url: str = Field(..., max_length=1024)


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalSessionRequest(BaseModel):
    return_url: str = Field(..., max_length=1024)


class PortalSessionResponse(BaseModel):
    portal_url: str


class WebhookResultResponse(BaseModel):
    event_id: str
    event_type: str
    processed: bool
    detail: str
