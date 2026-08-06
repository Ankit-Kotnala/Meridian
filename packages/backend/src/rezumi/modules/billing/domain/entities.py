"""Framework-independent domain entities and policy definitions for plans & billing."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class PlanTier(StrEnum):
    FREE = "free"
    SPRINT = "sprint"
    PRO = "pro"
    COACH = "coach"


class BillingCycle(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


@dataclass(frozen=True)
class PlanEntitlements:
    tier: PlanTier
    name: str
    description: str
    max_resumes: int
    max_change_sets_per_month: int
    max_exports_per_month: int
    ai_grounding_enabled: bool
    interview_prep_enabled: bool
    networking_enabled: bool
    analytics_enabled: bool
    monthly_price_usd: float
    annual_price_usd: float


# Central Plan Entitlements & Pricing Registry
PLANS: dict[PlanTier, PlanEntitlements] = {
    PlanTier.FREE: PlanEntitlements(
        tier=PlanTier.FREE,
        name="Free",
        description="Core evidence vault, basic resume health, and standard job matching.",
        max_resumes=1,
        max_change_sets_per_month=10,
        max_exports_per_month=5,
        ai_grounding_enabled=True,
        interview_prep_enabled=False,
        networking_enabled=False,
        analytics_enabled=False,
        monthly_price_usd=0.0,
        annual_price_usd=0.0,
    ),
    PlanTier.SPRINT: PlanEntitlements(
        tier=PlanTier.SPRINT,
        name="Sprint",
        description="Accelerated job hunt package with tailored AI change studio & exports.",
        max_resumes=5,
        max_change_sets_per_month=50,
        max_exports_per_month=25,
        ai_grounding_enabled=True,
        interview_prep_enabled=True,
        networking_enabled=True,
        analytics_enabled=False,
        monthly_price_usd=19.0,
        annual_price_usd=180.0,
    ),
    PlanTier.PRO: PlanEntitlements(
        tier=PlanTier.PRO,
        name="Pro",
        description="Full career management suite with interview prep, networking & analytics.",
        max_resumes=15,
        max_change_sets_per_month=200,
        max_exports_per_month=100,
        ai_grounding_enabled=True,
        interview_prep_enabled=True,
        networking_enabled=True,
        analytics_enabled=True,
        monthly_price_usd=39.0,
        annual_price_usd=360.0,
    ),
    PlanTier.COACH: PlanEntitlements(
        tier=PlanTier.COACH,
        name="Coach",
        description="Unlimited career intelligence & priority AI processing.",
        max_resumes=100,
        max_change_sets_per_month=1000,
        max_exports_per_month=500,
        ai_grounding_enabled=True,
        interview_prep_enabled=True,
        networking_enabled=True,
        analytics_enabled=True,
        monthly_price_usd=99.0,
        annual_price_usd=960.0,
    ),
}


@dataclass
class UserSubscription:
    id: UUID
    user_id: UUID
    tier: PlanTier
    status: SubscriptionStatus
    billing_cycle: BillingCycle
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create_default_free(cls, user_id: UUID) -> "UserSubscription":
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            tier=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            current_period_start=now,
            current_period_end=datetime(2099, 12, 31, tzinfo=UTC),
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )


@dataclass
class UsageQuota:
    user_id: UUID
    period_start: datetime
    resumes_count: int = 0
    change_sets_used: int = 0
    exports_used: int = 0
