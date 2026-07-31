"""Billing payment gateway providers (Mock & Stripe)."""

import json
from typing import Any, cast
from uuid import uuid4

from careeros.modules.billing.application.models import (
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    PortalSessionResponse,
)
from careeros.modules.billing.application.ports import BillingProviderPort


class MockBillingProvider(BillingProviderPort):
    """Deterministic mock provider for local development, testing, and CI."""

    async def create_checkout_session(
        self, request: CreateCheckoutSessionRequest, customer_id: str | None
    ) -> CheckoutSessionResponse:
        session_id = f"cs_mock_{uuid4().hex[:12]}"
        checkout_url = f"{request.success_url}?session_id={session_id}&tier={request.tier.value}"
        return CheckoutSessionResponse(checkout_url=checkout_url, session_id=session_id)

    async def create_portal_session(
        self, request: CreatePortalSessionRequest, customer_id: str
    ) -> PortalSessionResponse:
        portal_url = f"{request.return_url}?portal_session=active&customer_id={customer_id}"
        return PortalSessionResponse(portal_url=portal_url)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], json.loads(payload.decode("utf-8")))
        except Exception:
            return {
                "id": f"evt_mock_{uuid4().hex[:8]}",
                "type": "checkout.session.completed",
                "data": {"object": {}},
            }
