"""Thin FastAPI endpoints for plans & billing use cases."""

from typing import Annotated

from careeros.modules.billing.application import BillingService
from careeros.modules.billing.application.models import (
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
)
from careeros.modules.billing.domain import BillingCycle, PlanTier
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Header, Request

from careeros_api.modules.billing.dependencies import billing_service
from careeros_api.modules.billing.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PlanListResponse,
    PlanResponse,
    PortalSessionRequest,
    PortalSessionResponse,
    SubscriptionSummaryResponse,
    WebhookResultResponse,
)
from careeros_api.modules.identity.dependencies import current_principal

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


@router.get("/plans", response_model=PlanListResponse)
async def get_plans(
    service: Annotated[BillingService, Depends(billing_service)],
) -> PlanListResponse:
    plans = service.get_plans()
    return PlanListResponse(
        plans=[
            PlanResponse(
                tier=p.tier.value,
                name=p.name,
                description=p.description,
                max_resumes=p.max_resumes,
                max_change_sets_per_month=p.max_change_sets_per_month,
                max_exports_per_month=p.max_exports_per_month,
                ai_grounding_enabled=p.ai_grounding_enabled,
                interview_prep_enabled=p.interview_prep_enabled,
                networking_enabled=p.networking_enabled,
                analytics_enabled=p.analytics_enabled,
                monthly_price_usd=p.monthly_price_usd,
                annual_price_usd=p.annual_price_usd,
            )
            for p in plans
        ]
    )


@router.get("/subscription", response_model=SubscriptionSummaryResponse)
async def get_subscription(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[BillingService, Depends(billing_service)],
) -> SubscriptionSummaryResponse:
    sub = await service.get_subscription_summary(principal.user_id)
    ent = sub.entitlements
    return SubscriptionSummaryResponse(
        tier=sub.tier.value,
        status=sub.status.value,
        billing_cycle=sub.billing_cycle.value,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
        entitlements=PlanResponse(
            tier=ent.tier.value,
            name=ent.name,
            description=ent.description,
            max_resumes=ent.max_resumes,
            max_change_sets_per_month=ent.max_change_sets_per_month,
            max_exports_per_month=ent.max_exports_per_month,
            ai_grounding_enabled=ent.ai_grounding_enabled,
            interview_prep_enabled=ent.interview_prep_enabled,
            networking_enabled=ent.networking_enabled,
            analytics_enabled=ent.analytics_enabled,
            monthly_price_usd=ent.monthly_price_usd,
            annual_price_usd=ent.annual_price_usd,
        ),
        resumes_count=sub.resumes_count,
        resumes_limit=sub.resumes_limit,
        change_sets_used=sub.change_sets_used,
        change_sets_limit=sub.change_sets_limit,
        exports_used=sub.exports_used,
        exports_limit=sub.exports_limit,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[BillingService, Depends(billing_service)],
) -> CheckoutSessionResponse:
    res = await service.create_checkout_session(
        CreateCheckoutSessionRequest(
            user_id=principal.user_id,
            tier=PlanTier(body.tier),
            billing_cycle=BillingCycle(body.billing_cycle),
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    )
    return CheckoutSessionResponse(checkout_url=res.checkout_url, session_id=res.session_id)


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(
    body: PortalSessionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[BillingService, Depends(billing_service)],
) -> PortalSessionResponse:
    res = await service.create_portal_session(
        CreatePortalSessionRequest(
            user_id=principal.user_id,
            return_url=body.return_url,
        )
    )
    return PortalSessionResponse(portal_url=res.portal_url)


@router.post("/webhook", response_model=WebhookResultResponse)
async def handle_webhook(
    request: Request,
    service: Annotated[BillingService, Depends(billing_service)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookResultResponse:
    raw_payload = await request.body()
    result = await service.process_webhook(raw_payload, stripe_signature or "")
    return WebhookResultResponse(
        event_id=result.event_id,
        event_type=result.event_type,
        processed=result.processed,
        detail=result.detail,
    )
