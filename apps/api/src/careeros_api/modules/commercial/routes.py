"""Thin HTTP delivery for plans, subscriptions, and billing events."""

from __future__ import annotations

from typing import Annotated, Any

from careeros.modules.commercial.application import (
    CheckoutCommand,
    CommercialService,
    PortalCommand,
    RequestContext,
)
from careeros.modules.identity.domain import AuthenticatedPrincipal
from fastapi import APIRouter, Depends, Header, Request, Response, status

from careeros_api.modules.commercial.dependencies import (
    commercial_request_context,
    commercial_service,
    commercial_webhook_context,
)
from careeros_api.modules.commercial.presenters import (
    catalog_response,
    session_response,
    subscription_response,
    webhook_response,
)
from careeros_api.modules.commercial.schemas import (
    BillingSessionResponse,
    BillingWebhookResponse,
    CheckoutRequest,
    PlanCatalogResponse,
    PortalRequest,
    SubscriptionViewResponse,
)
from careeros_api.modules.identity.dependencies import (
    current_principal,
    require_authenticated_csrf,
)
from careeros_api.modules.identity.schemas import ProblemResponse

router = APIRouter(prefix="/api/v1", tags=["Commercial"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/plans",
    response_model=PlanCatalogResponse,
    operation_id="plansList",
    responses=_PROBLEMS,
)
async def list_plans(
    response: Response,
    service: Annotated[CommercialService, Depends(commercial_service)],
) -> PlanCatalogResponse:
    result = await service.list_plans()
    _private(response)
    return catalog_response(result)


@router.get(
    "/subscription",
    response_model=SubscriptionViewResponse,
    operation_id="subscriptionGet",
    responses=_PROBLEMS,
)
async def get_subscription(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(commercial_request_context)],
    service: Annotated[CommercialService, Depends(commercial_service)],
) -> SubscriptionViewResponse:
    result = await service.get_subscription(principal.user_id, context)
    _private(response)
    return subscription_response(result)


@router.post(
    "/subscription/checkout",
    response_model=BillingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="subscriptionCheckout",
    responses=_PROBLEMS,
)
async def create_checkout(
    payload: CheckoutRequest,
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(commercial_request_context)],
    service: Annotated[CommercialService, Depends(commercial_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> BillingSessionResponse:
    result = await service.create_checkout(
        principal.user_id,
        CheckoutCommand(
            plan_code=payload.plan_code,
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
        ),
        idempotency_key,
        context,
    )
    _private(response)
    return session_response(result)


@router.post(
    "/subscription/portal",
    response_model=BillingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="subscriptionPortal",
    responses=_PROBLEMS,
)
async def create_portal(
    payload: PortalRequest,
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(commercial_request_context)],
    service: Annotated[CommercialService, Depends(commercial_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> BillingSessionResponse:
    result = await service.create_portal(
        principal.user_id,
        PortalCommand(return_url=str(payload.return_url)),
        idempotency_key,
        context,
    )
    _private(response)
    return session_response(result)


@router.post(
    "/subscription/reconcile",
    response_model=BillingWebhookResponse,
    operation_id="subscriptionReconcile",
    responses=_PROBLEMS,
)
async def reconcile_subscription(
    response: Response,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_csrf),
    ],
    context: Annotated[RequestContext, Depends(commercial_request_context)],
    service: Annotated[CommercialService, Depends(commercial_service)],
) -> BillingWebhookResponse:
    result = await service.reconcile(principal.user_id, context)
    _private(response)
    return webhook_response(result)


@router.post(
    "/webhooks/billing/{provider}",
    response_model=BillingWebhookResponse,
    operation_id="billingWebhook",
    responses=_PROBLEMS,
)
async def billing_webhook(
    provider: str,
    request: Request,
    service: Annotated[CommercialService, Depends(commercial_service)],
    context: Annotated[RequestContext, Depends(commercial_webhook_context)],
) -> BillingWebhookResponse:
    raw_body = await request.body()
    result = await service.process_webhook(
        provider=provider,
        raw_body=raw_body,
        headers={key.casefold(): value for key, value in request.headers.items()},
        context=context,
    )
    return webhook_response(result)
