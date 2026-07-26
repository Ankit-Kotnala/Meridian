"""Inward-facing ports for commercial use cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.commercial.domain import (
    BillingAuditEvent,
    BillingCustomer,
    BillingEvent,
    CommercialPlan,
    Subscription,
)

from .models import (
    BillingSession,
    IdempotencyRecord,
    ProviderSubscriptionEvent,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class BillingProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    async def create_checkout(
        self,
        *,
        owner_reference: str,
        existing_customer_reference: str | None,
        provider_price_reference: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> BillingSession: ...

    async def create_portal(
        self,
        *,
        provider_customer_reference: str,
        return_url: str,
        idempotency_key: str,
    ) -> BillingSession: ...

    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        now: datetime,
    ) -> ProviderSubscriptionEvent: ...

    async def retrieve_subscription(
        self,
        provider_subscription_reference: str,
    ) -> ProviderSubscriptionEvent: ...


class CommercialUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def list_plans(self) -> list[CommercialPlan]: ...

    async def get_plan_by_code(self, code: str) -> CommercialPlan | None: ...

    async def get_plan_by_provider_reference(
        self,
        provider_price_reference: str,
    ) -> CommercialPlan | None: ...

    async def get_customer(
        self,
        owner_user_id: UUID,
        provider: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None: ...

    async def get_customer_by_provider_reference(
        self,
        provider: str,
        provider_customer_reference: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None: ...

    async def add_customer(self, customer: BillingCustomer) -> None: ...

    async def get_subscription(
        self,
        owner_user_id: UUID,
        *,
        for_update: bool = False,
    ) -> Subscription | None: ...

    async def get_subscription_by_provider_reference(
        self,
        provider: str,
        provider_subscription_reference: str,
        *,
        for_update: bool = False,
    ) -> Subscription | None: ...

    async def add_subscription(self, subscription: Subscription) -> None: ...

    async def save_subscription(self, subscription: Subscription) -> None: ...

    async def get_billing_event(
        self,
        provider: str,
        provider_event_id: str,
    ) -> BillingEvent | None: ...

    async def add_billing_event(self, event: BillingEvent) -> None: ...

    async def save_billing_event(self, event: BillingEvent) -> None: ...

    async def get_idempotency(
        self,
        owner_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None: ...

    async def add_idempotency(self, record: IdempotencyRecord) -> None: ...

    async def add_audit(self, event: BillingAuditEvent) -> None: ...

    async def commit(self) -> None: ...


CommercialUnitOfWorkFactory = Callable[[], CommercialUnitOfWork]
