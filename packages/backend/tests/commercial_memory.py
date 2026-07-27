"""Explicitly fictional in-memory commercial adapters for unit and API tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from careeros.modules.commercial.application.models import IdempotencyRecord
from careeros.modules.commercial.application.ports import CommercialUnitOfWork
from careeros.modules.commercial.domain import (
    BillingAuditEvent,
    BillingCustomer,
    BillingEvent,
    BillingInterval,
    CommercialPlan,
    PlanCode,
    PlanConfigurationStatus,
    PlanEntitlement,
    PlanQuota,
    Subscription,
)

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)
ACTIVE_PLAN_ID = UUID("e9425007-2a7a-55fc-b49e-eccac6604337")
UNCONFIGURED_PLAN_ID = UUID("fa1ba0dd-4fc2-5baf-a76d-3da367a30b2d")


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequentialIds:
    def __init__(self) -> None:
        self._value = 100

    def new(self) -> UUID:
        self._value += 1
        return UUID(int=self._value)


def configured_test_plan() -> CommercialPlan:
    """Return fictional values used only to exercise configured-plan behavior."""
    return CommercialPlan(
        id=ACTIVE_PLAN_ID,
        code=PlanCode.PRO,
        display_name="Pro — fictional test configuration",
        description="Fictional unit-test plan; not product pricing or entitlement policy.",
        configuration_status=PlanConfigurationStatus.ACTIVE,
        currency="USD",
        unit_amount_minor=123,
        billing_interval=BillingInterval.MONTH,
        interval_count=1,
        provider_price_reference="price_test_pro",
        entitlements=(PlanEntitlement(key="verified_export", enabled=True),),
        quotas=(PlanQuota(key="monthly_exports", limit=3, window="month"),),
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def unconfigured_test_plan() -> CommercialPlan:
    return CommercialPlan(
        id=UNCONFIGURED_PLAN_ID,
        code=PlanCode.FREE,
        display_name="Free",
        description="Entitlements and quotas require product-owner configuration.",
        configuration_status=PlanConfigurationStatus.OWNER_DECISION_REQUIRED,
        currency=None,
        unit_amount_minor=None,
        billing_interval=None,
        interval_count=None,
        provider_price_reference=None,
        entitlements=(),
        quotas=(),
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


class MemoryCommercial:
    def __init__(self, plans: list[CommercialPlan] | None = None) -> None:
        self.plans = plans or [unconfigured_test_plan()]
        self.customers: dict[tuple[UUID, str], BillingCustomer] = {}
        self.subscriptions: dict[UUID, Subscription] = {}
        self.events: dict[tuple[str, str], BillingEvent] = {}
        self.idempotency: dict[tuple[UUID, str, str], IdempotencyRecord] = {}
        self.audits: list[BillingAuditEvent] = []

    def __call__(self) -> CommercialUnitOfWork:
        return self

    async def __aenter__(self) -> MemoryCommercial:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def list_plans(self) -> list[CommercialPlan]:
        return sorted(self.plans, key=lambda item: item.code.value)

    async def get_plan_by_code(self, code: str) -> CommercialPlan | None:
        return next((item for item in self.plans if item.code.value == code), None)

    async def get_plan_by_provider_reference(
        self,
        provider_price_reference: str,
    ) -> CommercialPlan | None:
        return next(
            (
                item
                for item in self.plans
                if item.provider_price_reference == provider_price_reference
            ),
            None,
        )

    async def get_customer(
        self,
        owner_user_id: UUID,
        provider: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None:
        del for_update
        return self.customers.get((owner_user_id, provider))

    async def get_customer_by_provider_reference(
        self,
        provider: str,
        provider_customer_reference: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None:
        del for_update
        return next(
            (
                item
                for item in self.customers.values()
                if item.provider == provider
                and item.provider_customer_reference == provider_customer_reference
            ),
            None,
        )

    async def add_customer(self, customer: BillingCustomer) -> None:
        self.customers[(customer.owner_user_id, customer.provider)] = customer

    async def get_subscription(
        self,
        owner_user_id: UUID,
        *,
        for_update: bool = False,
    ) -> Subscription | None:
        del for_update
        return self.subscriptions.get(owner_user_id)

    async def get_subscription_by_provider_reference(
        self,
        provider: str,
        provider_subscription_reference: str,
        *,
        for_update: bool = False,
    ) -> Subscription | None:
        del for_update
        return next(
            (
                item
                for item in self.subscriptions.values()
                if item.provider == provider
                and item.provider_subscription_reference == provider_subscription_reference
            ),
            None,
        )

    async def add_subscription(self, subscription: Subscription) -> None:
        self.subscriptions[subscription.owner_user_id] = subscription

    async def save_subscription(self, subscription: Subscription) -> None:
        self.subscriptions[subscription.owner_user_id] = subscription

    async def get_billing_event(
        self,
        provider: str,
        provider_event_id: str,
    ) -> BillingEvent | None:
        return self.events.get((provider, provider_event_id))

    async def add_billing_event(self, event: BillingEvent) -> None:
        self.events[(event.provider, event.provider_event_id)] = event

    async def save_billing_event(self, event: BillingEvent) -> None:
        self.events[(event.provider, event.provider_event_id)] = event

    async def get_idempotency(
        self,
        owner_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        return self.idempotency.get((owner_user_id, operation, idempotency_key))

    async def add_idempotency(self, record: IdempotencyRecord) -> None:
        self.idempotency[(record.owner_user_id, record.operation, record.idempotency_key)] = record

    async def add_audit(self, event: BillingAuditEvent) -> None:
        self.audits.append(event)

    async def commit(self) -> None:
        return None
