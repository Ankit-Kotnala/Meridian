"""Async SQLAlchemy unit of work for commercial state."""

from __future__ import annotations

from types import TracebackType
from typing import Any, NoReturn, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.commercial.application.models import IdempotencyRecord
from careeros.modules.commercial.application.ports import CommercialUnitOfWork
from careeros.modules.commercial.domain import (
    BillingAuditEvent,
    BillingCustomer,
    BillingEvent,
    BillingEventState,
    BillingInterval,
    CommercialConflict,
    CommercialPlan,
    CommercialUnavailable,
    CommercialValidationError,
    PlanCode,
    PlanConfigurationStatus,
    PlanEntitlement,
    PlanQuota,
    Subscription,
    SubscriptionStatus,
)

from .models import (
    BillingCustomerModel,
    BillingEventModel,
    CommercialAuditEventModel,
    CommercialIdempotencyModel,
    CommercialPlanModel,
    SubscriptionModel,
)


class SqlAlchemyCommercialUnitOfWork:
    """One transaction per plan, subscription, or billing-event use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyCommercialUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("commercial unit of work is not active")
        return self._session

    async def list_plans(self) -> list[CommercialPlan]:
        models = (
            await self.session.scalars(
                select(CommercialPlanModel).order_by(CommercialPlanModel.code)
            )
        ).all()
        return [_plan(model) for model in models]

    async def get_plan_by_code(self, code: str) -> CommercialPlan | None:
        model = await self.session.scalar(
            select(CommercialPlanModel).where(CommercialPlanModel.code == code)
        )
        return _plan(model) if model is not None else None

    async def get_plan_by_provider_reference(
        self,
        provider_price_reference: str,
    ) -> CommercialPlan | None:
        model = await self.session.scalar(
            select(CommercialPlanModel).where(
                CommercialPlanModel.provider_price_reference == provider_price_reference
            )
        )
        return _plan(model) if model is not None else None

    async def get_customer(
        self,
        owner_user_id: UUID,
        provider: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None:
        statement = select(BillingCustomerModel).where(
            BillingCustomerModel.owner_user_id == owner_user_id,
            BillingCustomerModel.provider == provider,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _customer(model) if model is not None else None

    async def get_customer_by_provider_reference(
        self,
        provider: str,
        provider_customer_reference: str,
        *,
        for_update: bool = False,
    ) -> BillingCustomer | None:
        statement = select(BillingCustomerModel).where(
            BillingCustomerModel.provider == provider,
            BillingCustomerModel.provider_customer_reference == provider_customer_reference,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _customer(model) if model is not None else None

    async def add_customer(self, customer: BillingCustomer) -> None:
        self.session.add(BillingCustomerModel(**_customer_values(customer)))
        await self._flush()

    async def get_subscription(
        self,
        owner_user_id: UUID,
        *,
        for_update: bool = False,
    ) -> Subscription | None:
        statement = select(SubscriptionModel).where(
            SubscriptionModel.owner_user_id == owner_user_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _subscription(model) if model is not None else None

    async def get_subscription_by_provider_reference(
        self,
        provider: str,
        provider_subscription_reference: str,
        *,
        for_update: bool = False,
    ) -> Subscription | None:
        statement = select(SubscriptionModel).where(
            SubscriptionModel.provider == provider,
            SubscriptionModel.provider_subscription_reference == provider_subscription_reference,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _subscription(model) if model is not None else None

    async def add_subscription(self, subscription: Subscription) -> None:
        self.session.add(SubscriptionModel(**_subscription_values(subscription)))
        await self._flush()

    async def save_subscription(self, subscription: Subscription) -> None:
        await self._execute(
            update(SubscriptionModel)
            .where(
                SubscriptionModel.owner_user_id == subscription.owner_user_id,
                SubscriptionModel.id == subscription.id,
            )
            .values(**_subscription_values(subscription, include_identity=False))
        )

    async def get_billing_event(
        self,
        provider: str,
        provider_event_id: str,
    ) -> BillingEvent | None:
        model = await self.session.scalar(
            select(BillingEventModel).where(
                BillingEventModel.provider == provider,
                BillingEventModel.provider_event_id == provider_event_id,
            )
        )
        return _billing_event(model) if model is not None else None

    async def add_billing_event(self, event: BillingEvent) -> None:
        self.session.add(BillingEventModel(**_billing_event_values(event)))
        await self._flush()

    async def save_billing_event(self, event: BillingEvent) -> None:
        await self._execute(
            update(BillingEventModel)
            .where(BillingEventModel.id == event.id)
            .values(**_billing_event_values(event, include_identity=False))
        )

    async def get_idempotency(
        self,
        owner_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        model = await self.session.scalar(
            select(CommercialIdempotencyModel).where(
                CommercialIdempotencyModel.owner_user_id == owner_user_id,
                CommercialIdempotencyModel.operation == operation,
                CommercialIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_idempotency(self, record: IdempotencyRecord) -> None:
        self.session.add(
            CommercialIdempotencyModel(
                id=record.id,
                owner_user_id=record.owner_user_id,
                operation=record.operation,
                idempotency_key=record.idempotency_key,
                request_fingerprint=bytes.fromhex(record.request_fingerprint),
                response_payload=dict(record.response_payload),
                created_at=record.created_at,
            )
        )
        await self._flush()

    async def add_audit(self, event: BillingAuditEvent) -> None:
        self.session.add(
            CommercialAuditEventModel(
                id=event.id,
                owner_user_id=event.owner_user_id,
                action=event.action.value,
                target_type=event.target_type,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                event_metadata=dict(event.metadata),
                occurred_at=event.occurred_at,
            )
        )
        await self._flush()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CommercialConflict from exc
        self._committed = True

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CommercialConflict from exc

    async def _execute(self, statement: Any) -> None:
        try:
            result = await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            raise CommercialConflict from exc
        if cast(Any, result).rowcount != 1:
            raise CommercialUnavailable("commercial state changed concurrently")


class SqlAlchemyCommercialUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> CommercialUnitOfWork:
        return SqlAlchemyCommercialUnitOfWork(self._database)


def _plan(model: CommercialPlanModel) -> CommercialPlan:
    try:
        entitlements = tuple(
            PlanEntitlement(
                key=str(item["key"]),
                enabled=cast(bool, item["enabled"]),
            )
            for item in model.entitlements
        )
        quotas = tuple(
            PlanQuota(
                key=str(item["key"]),
                limit=cast(int, item["limit"]),
                window=str(item["window"]),
            )
            for item in model.quotas
        )
        return CommercialPlan(
            id=model.id,
            code=PlanCode(model.code),
            display_name=model.display_name,
            description=model.description,
            configuration_status=PlanConfigurationStatus(model.configuration_status),
            currency=model.currency,
            unit_amount_minor=model.unit_amount_minor,
            billing_interval=(
                BillingInterval(model.billing_interval)
                if model.billing_interval is not None
                else None
            ),
            interval_count=model.interval_count,
            provider_price_reference=model.provider_price_reference,
            entitlements=entitlements,
            quotas=quotas,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (KeyError, TypeError, ValueError, CommercialValidationError) as exc:
        raise CommercialUnavailable("stored plan configuration is invalid") from exc


def _customer(model: BillingCustomerModel) -> BillingCustomer:
    return BillingCustomer(
        id=model.id,
        owner_user_id=model.owner_user_id,
        provider=model.provider,
        provider_customer_reference=model.provider_customer_reference,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _customer_values(customer: BillingCustomer) -> dict[str, object]:
    return {
        "id": customer.id,
        "owner_user_id": customer.owner_user_id,
        "provider": customer.provider,
        "provider_customer_reference": customer.provider_customer_reference,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
    }


def _subscription(model: SubscriptionModel) -> Subscription:
    return Subscription(
        id=model.id,
        owner_user_id=model.owner_user_id,
        plan_id=model.plan_id,
        billing_customer_id=model.billing_customer_id,
        provider=model.provider,
        provider_subscription_reference=model.provider_subscription_reference,
        status=SubscriptionStatus(model.status),
        provider_sequence=model.provider_sequence,
        provider_occurred_at=model.provider_occurred_at,
        current_period_end=model.current_period_end,
        cancel_at_period_end=model.cancel_at_period_end,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _subscription_values(
    subscription: Subscription,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "plan_id": subscription.plan_id,
        "billing_customer_id": subscription.billing_customer_id,
        "provider": subscription.provider,
        "provider_subscription_reference": (subscription.provider_subscription_reference),
        "status": subscription.status.value,
        "provider_sequence": subscription.provider_sequence,
        "provider_occurred_at": subscription.provider_occurred_at,
        "current_period_end": subscription.current_period_end,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "version": subscription.version,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
    }
    if include_identity:
        values.update(
            {
                "id": subscription.id,
                "owner_user_id": subscription.owner_user_id,
            }
        )
    return values


def _billing_event(model: BillingEventModel) -> BillingEvent:
    return BillingEvent(
        id=model.id,
        provider=model.provider,
        provider_event_id=model.provider_event_id,
        payload_sha256=model.payload_sha256.hex(),
        event_kind=model.event_kind,
        provider_sequence=model.provider_sequence,
        provider_occurred_at=model.provider_occurred_at,
        provider_customer_reference=model.provider_customer_reference,
        provider_subscription_reference=model.provider_subscription_reference,
        provider_price_reference=model.provider_price_reference,
        subscription_status=SubscriptionStatus(model.subscription_status),
        current_period_end=model.current_period_end,
        cancel_at_period_end=model.cancel_at_period_end,
        state=BillingEventState(model.state),
        owner_user_id=model.owner_user_id,
        subscription_id=model.subscription_id,
        created_at=model.created_at,
        processed_at=model.processed_at,
    )


def _billing_event_values(
    event: BillingEvent,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "provider": event.provider,
        "provider_event_id": event.provider_event_id,
        "payload_sha256": bytes.fromhex(event.payload_sha256),
        "event_kind": event.event_kind,
        "provider_sequence": event.provider_sequence,
        "provider_occurred_at": event.provider_occurred_at,
        "provider_customer_reference": event.provider_customer_reference,
        "provider_subscription_reference": (event.provider_subscription_reference),
        "provider_price_reference": event.provider_price_reference,
        "subscription_status": event.subscription_status.value,
        "current_period_end": event.current_period_end,
        "cancel_at_period_end": event.cancel_at_period_end,
        "state": event.state.value,
        "owner_user_id": event.owner_user_id,
        "subscription_id": event.subscription_id,
        "created_at": event.created_at,
        "processed_at": event.processed_at,
    }
    if include_identity:
        values["id"] = event.id
    return values


def _idempotency(model: CommercialIdempotencyModel) -> IdempotencyRecord:
    return IdempotencyRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        operation=model.operation,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint.hex(),
        response_payload=model.response_payload,
        created_at=model.created_at,
    )


def _raise_unavailable(exc: Exception) -> NoReturn:
    raise CommercialUnavailable from exc
