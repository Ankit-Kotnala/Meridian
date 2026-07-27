"""Pure commercial wire presenters."""

from careeros.modules.commercial.application import (
    BillingSession,
    PlanCatalog,
    SubscriptionView,
    WebhookResult,
)
from careeros.modules.commercial.domain import CommercialPlan

from careeros_api.commercial_schemas import (
    BillingSessionResponse,
    BillingWebhookResponse,
    EntitlementResponse,
    PlanCatalogResponse,
    PlanPriceResponse,
    PlanResponse,
    QuotaResponse,
    SubscriptionResponse,
    SubscriptionViewResponse,
)


def plan_response(plan: CommercialPlan) -> PlanResponse:
    price = None
    if (
        plan.currency is not None
        and plan.unit_amount_minor is not None
        and plan.billing_interval is not None
        and plan.interval_count is not None
    ):
        price = PlanPriceResponse(
            currency=plan.currency,
            unit_amount_minor=plan.unit_amount_minor,
            billing_interval=plan.billing_interval.value,
            interval_count=plan.interval_count,
        )
    return PlanResponse(
        id=plan.id,
        code=plan.code.value,
        display_name=plan.display_name,
        description=plan.description,
        configuration_status=plan.configuration_status.value,
        purchasable=plan.purchasable,
        price=price,
        entitlements=[
            EntitlementResponse(key=item.key, enabled=item.enabled)
            for item in plan.entitlements
        ],
        quotas=[
            QuotaResponse(key=item.key, limit=item.limit, window=item.window)
            for item in plan.quotas
        ],
        version=plan.version,
    )


def catalog_response(catalog: PlanCatalog) -> PlanCatalogResponse:
    return PlanCatalogResponse(
        plans=[plan_response(item) for item in catalog.plans],
        owner_configuration_required=catalog.owner_configuration_required,
    )


def subscription_response(value: SubscriptionView) -> SubscriptionViewResponse:
    subscription = value.subscription
    return SubscriptionViewResponse(
        subscription=(
            SubscriptionResponse(
                id=subscription.id,
                plan_id=subscription.plan_id,
                status=subscription.status.value,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                version=subscription.version,
                updated_at=subscription.updated_at,
            )
            if subscription is not None
            else None
        ),
        plan=plan_response(value.plan) if value.plan is not None else None,
        billing_available=value.billing_available,
    )


def session_response(value: BillingSession) -> BillingSessionResponse:
    return BillingSessionResponse(url=value.url, expires_at=value.expires_at)


def webhook_response(value: WebhookResult) -> BillingWebhookResponse:
    return BillingWebhookResponse(
        replayed=value.replayed,
        state=value.event.state.value,
    )

