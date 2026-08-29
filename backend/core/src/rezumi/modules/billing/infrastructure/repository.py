"""SQLAlchemy repository implementation for plans & billing."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.modules.billing.application.ports import BillingRepositoryPort
from rezumi.modules.billing.domain.entities import (
    BillingCycle,
    PlanTier,
    SubscriptionStatus,
    UsageQuota,
    UserSubscription,
)
from rezumi.modules.billing.infrastructure.models import (
    BillingWebhookEventModel,
    SubscriptionModel,
    UsageQuotaModel,
)


class SqlAlchemyBillingRepository(BillingRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_subscription(self, user_id: UUID) -> UserSubscription | None:
        stmt = select(SubscriptionModel).where(SubscriptionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain_subscription(model)

    async def save_subscription(self, subscription: UserSubscription) -> UserSubscription:
        stmt = select(SubscriptionModel).where(SubscriptionModel.user_id == subscription.user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            model = SubscriptionModel(
                id=subscription.id,
                user_id=subscription.user_id,
                tier=subscription.tier.value,
                status=subscription.status.value,
                billing_cycle=subscription.billing_cycle.value,
                stripe_customer_id=subscription.stripe_customer_id,
                stripe_subscription_id=subscription.stripe_subscription_id,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                created_at=subscription.created_at,
                updated_at=subscription.updated_at,
            )
            self._session.add(model)
        else:
            model.tier = subscription.tier.value
            model.status = subscription.status.value
            model.billing_cycle = subscription.billing_cycle.value
            model.stripe_customer_id = subscription.stripe_customer_id
            model.stripe_subscription_id = subscription.stripe_subscription_id
            model.current_period_start = subscription.current_period_start
            model.current_period_end = subscription.current_period_end
            model.cancel_at_period_end = subscription.cancel_at_period_end
            model.updated_at = subscription.updated_at

        await self._session.flush()
        return self._to_domain_subscription(model)

    async def get_quota(self, user_id: UUID) -> UsageQuota:
        stmt = select(UsageQuotaModel).where(UsageQuotaModel.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            now = datetime.now(UTC)
            period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
            model = UsageQuotaModel(
                user_id=user_id,
                period_start=period_start,
                resumes_count=0,
                change_sets_used=0,
                exports_used=0,
            )
            self._session.add(model)
            await self._session.flush()

        return UsageQuota(
            user_id=model.user_id,
            period_start=model.period_start,
            resumes_count=model.resumes_count,
            change_sets_used=model.change_sets_used,
            exports_used=model.exports_used,
        )

    async def increment_usage(
        self, user_id: UUID, change_sets: int = 0, exports: int = 0
    ) -> UsageQuota:
        await self.get_quota(user_id)
        stmt = select(UsageQuotaModel).where(UsageQuotaModel.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one()

        model.change_sets_used += change_sets
        model.exports_used += exports
        await self._session.flush()

        return UsageQuota(
            user_id=model.user_id,
            period_start=model.period_start,
            resumes_count=model.resumes_count,
            change_sets_used=model.change_sets_used,
            exports_used=model.exports_used,
        )

    async def is_webhook_processed(self, event_id: str) -> bool:
        stmt = select(BillingWebhookEventModel).where(BillingWebhookEventModel.event_id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def record_webhook_event(
        self, event_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        model = BillingWebhookEventModel(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            processed_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()

    def _to_domain_subscription(self, model: SubscriptionModel) -> UserSubscription:
        return UserSubscription(
            id=model.id,
            user_id=model.user_id,
            tier=PlanTier(model.tier),
            status=SubscriptionStatus(model.status),
            billing_cycle=BillingCycle(model.billing_cycle),
            stripe_customer_id=model.stripe_customer_id,
            stripe_subscription_id=model.stripe_subscription_id,
            current_period_start=model.current_period_start,
            current_period_end=model.current_period_end,
            cancel_at_period_end=model.cancel_at_period_end,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
