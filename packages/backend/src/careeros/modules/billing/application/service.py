"""Billing and plan entitlement application service."""

from datetime import UTC, datetime
from uuid import UUID

from careeros.foundation.database import Database
from careeros.modules.billing.application.models import (
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    PlanSummaryDTO,
    PortalSessionResponse,
    SubscriptionSummaryDTO,
    WebhookResultDTO,
)
from careeros.modules.billing.application.ports import (
    BillingProviderPort,
)
from careeros.modules.billing.domain.entities import (
    PLANS,
    PlanEntitlements,
    PlanTier,
    SubscriptionStatus,
    UserSubscription,
)
from careeros.modules.billing.domain.errors import (
    PlanNotFoundError,
    QuotaExceededError,
)
from careeros.modules.billing.infrastructure.repository import SqlAlchemyBillingRepository


class BillingService:
    def __init__(
        self,
        database: Database,
        provider: BillingProviderPort,
    ) -> None:
        self._database = database
        self._provider = provider

    def get_plans(self) -> list[PlanSummaryDTO]:
        return [self._map_plan_entitlements(ent) for ent in PLANS.values()]

    async def get_subscription_summary(self, user_id: UUID) -> SubscriptionSummaryDTO:
        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            sub = await repo.get_subscription(user_id)
            if sub is None:
                sub = UserSubscription.create_default_free(user_id)
                sub = await repo.save_subscription(sub)
                await session.commit()

            ent = PLANS.get(sub.tier, PLANS[PlanTier.FREE])
            quota = await repo.get_quota(user_id)
            await session.commit()

            return SubscriptionSummaryDTO(
                tier=sub.tier,
                status=sub.status,
                billing_cycle=sub.billing_cycle,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
                entitlements=self._map_plan_entitlements(ent),
                resumes_count=quota.resumes_count,
                resumes_limit=ent.max_resumes,
                change_sets_used=quota.change_sets_used,
                change_sets_limit=ent.max_change_sets_per_month,
                exports_used=quota.exports_used,
                exports_limit=ent.max_exports_per_month,
            )

    async def check_quota(self, user_id: UUID, feature: str) -> None:
        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            sub = await repo.get_subscription(user_id)
            tier = sub.tier if sub else PlanTier.FREE
            ent = PLANS.get(tier, PLANS[PlanTier.FREE])
            quota = await repo.get_quota(user_id)

            if feature == "change_set" and quota.change_sets_used >= ent.max_change_sets_per_month:
                raise QuotaExceededError(
                    "change_sets", ent.max_change_sets_per_month, quota.change_sets_used
                )
            if feature == "export" and quota.exports_used >= ent.max_exports_per_month:
                raise QuotaExceededError("exports", ent.max_exports_per_month, quota.exports_used)
            if feature == "resume" and quota.resumes_count >= ent.max_resumes:
                raise QuotaExceededError("resumes", ent.max_resumes, quota.resumes_count)

    async def record_usage(self, user_id: UUID, change_sets: int = 0, exports: int = 0) -> None:
        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            await repo.increment_usage(user_id, change_sets=change_sets, exports=exports)
            await session.commit()

    async def create_checkout_session(
        self, request: CreateCheckoutSessionRequest
    ) -> CheckoutSessionResponse:
        if request.tier not in PLANS:
            raise PlanNotFoundError(f"Plan '{request.tier}' does not exist.")

        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            sub = await repo.get_subscription(request.user_id)
            customer_id = sub.stripe_customer_id if sub else None

        return await self._provider.create_checkout_session(request, customer_id)

    async def create_portal_session(
        self, request: CreatePortalSessionRequest
    ) -> PortalSessionResponse:
        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            sub = await repo.get_subscription(request.user_id)
            customer_id = (
                sub.stripe_customer_id
                if sub and sub.stripe_customer_id
                else f"cus_mock_{request.user_id.hex[:12]}"
            )

        return await self._provider.create_portal_session(request, customer_id)

    async def process_webhook(self, raw_payload: bytes, signature: str) -> WebhookResultDTO:
        event = self._provider.verify_webhook_signature(raw_payload, signature)
        event_id = str(event.get("id", ""))
        event_type = str(event.get("type", ""))

        async with self._database.session() as session:
            repo = SqlAlchemyBillingRepository(session)
            if await repo.is_webhook_processed(event_id):
                return WebhookResultDTO(
                    event_id=event_id,
                    event_type=event_type,
                    processed=False,
                    detail="Event already processed",
                )

            data = event.get("data", {}).get("object", {})
            if event_type in ("customer.subscription.updated", "customer.subscription.created"):
                user_id_str = data.get("metadata", {}).get("user_id")
                tier_str = data.get("metadata", {}).get("tier", "pro")
                if user_id_str:
                    user_id = UUID(user_id_str)
                    sub = await repo.get_subscription(user_id)
                    if not sub:
                        sub = UserSubscription.create_default_free(user_id)
                    sub.tier = PlanTier(tier_str) if tier_str in PlanTier else PlanTier.PRO
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.stripe_customer_id = str(data.get("customer", ""))
                    sub.stripe_subscription_id = str(data.get("id", ""))
                    sub.updated_at = datetime.now(UTC)
                    await repo.save_subscription(sub)

            elif event_type == "customer.subscription.deleted":
                user_id_str = data.get("metadata", {}).get("user_id")
                if user_id_str:
                    user_id = UUID(user_id_str)
                    sub = await repo.get_subscription(user_id)
                    if sub:
                        sub.tier = PlanTier.FREE
                        sub.status = SubscriptionStatus.CANCELED
                        sub.updated_at = datetime.now(UTC)
                        await repo.save_subscription(sub)

            await repo.record_webhook_event(event_id, event_type, event)
            await session.commit()

        return WebhookResultDTO(
            event_id=event_id,
            event_type=event_type,
            processed=True,
            detail="Event processed successfully",
        )

    def _map_plan_entitlements(self, ent: PlanEntitlements) -> PlanSummaryDTO:
        return PlanSummaryDTO(
            tier=ent.tier,
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
        )
