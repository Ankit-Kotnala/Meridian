"""Strict wire schemas for plans, subscriptions, and billing sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class CommercialSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


PlanCode = Literal["free", "job_hunt_sprint", "pro", "coach_organization"]
PlanConfigurationStatus = Literal[
    "owner_decision_required",
    "active",
    "archived",
]
BillingInterval = Literal["month", "year", "fixed_term"]
SubscriptionStatus = Literal[
    "pending",
    "trialing",
    "active",
    "past_due",
    "paused",
    "canceled",
]


class PlanPriceResponse(CommercialSchema):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    unit_amount_minor: Annotated[int, Field(ge=0, le=2_147_483_647)]
    billing_interval: BillingInterval
    interval_count: Annotated[int, Field(ge=1, le=120)]


class EntitlementResponse(CommercialSchema):
    key: str
    enabled: bool


class QuotaResponse(CommercialSchema):
    key: str
    limit: Annotated[int, Field(ge=0, le=2_147_483_647)]
    window: str


class PlanResponse(CommercialSchema):
    id: UUID
    code: PlanCode
    display_name: str
    description: str
    configuration_status: PlanConfigurationStatus
    purchasable: bool
    price: PlanPriceResponse | None
    entitlements: list[EntitlementResponse]
    quotas: list[QuotaResponse]
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]


class PlanCatalogResponse(CommercialSchema):
    plans: list[PlanResponse] = Field(max_length=4)
    owner_configuration_required: bool


class SubscriptionResponse(CommercialSchema):
    id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool
    version: Annotated[int, Field(ge=1, le=2_147_483_647)]
    updated_at: datetime


class SubscriptionViewResponse(CommercialSchema):
    subscription: SubscriptionResponse | None
    plan: PlanResponse | None
    billing_available: bool


class CheckoutRequest(CommercialSchema):
    plan_code: PlanCode
    success_url: HttpUrl
    cancel_url: HttpUrl


class PortalRequest(CommercialSchema):
    return_url: HttpUrl


class BillingSessionResponse(CommercialSchema):
    url: HttpUrl
    expires_at: datetime


class BillingWebhookResponse(CommercialSchema):
    accepted: Literal[True] = True
    replayed: bool
    state: Literal[
        "received",
        "applied",
        "ignored_stale",
        "unmatched_customer",
        "unmatched_plan",
    ]

