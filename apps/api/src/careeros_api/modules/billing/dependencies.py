"""FastAPI dependencies for billing service."""

from typing import cast

from careeros.modules.billing.application import BillingService
from fastapi import HTTPException, Request, status


def billing_service(request: Request) -> BillingService:
    service = getattr(request.app.state, "billing_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing service is not configured in this environment.",
        )
    return cast(BillingService, service)
