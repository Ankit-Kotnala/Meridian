"""PostgreSQL integration coverage for commercial ownership and event ordering."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.commercial.application import (
    CheckoutCommand,
    CommercialService,
    RequestContext,
)
from careeros.modules.commercial.domain import (
    BillingEventState,
    CommercialNotFound,
)
from careeros.modules.commercial.infrastructure import (
    DeterministicBillingProvider,
    SqlAlchemyCommercialUnitOfWorkFactory,
)
from careeros.modules.commercial.infrastructure.models import (
    BillingEventModel,
    CommercialAuditEventModel,
    CommercialPlanModel,
    SubscriptionModel,
)
from careeros.modules.identity.infrastructure.models import UserModel

_NOW = datetime(2026, 7, 26, 23, tzinfo=UTC)
_PRO_PLAN_ID = UUID("00000000-0000-4000-8000-000000001003")
_SECRET = "fictional-integration-billing-secret-32-bytes"  # noqa: S105  # gitleaks:allow
_ORIGIN = "http://localhost:3000"


class FixedClock:
    def now(self) -> datetime:
        return _NOW


class UuidFactory:
    def new(self):
        return uuid4()


def _context(owner_id) -> RequestContext:
    return RequestContext(
        actor_user_id=owner_id,
        request_id=f"commercial-{owner_id.hex[:8]}",
        trace_id="c" * 32,
    )


def _payload(customer_reference: str, *, event_id: str, sequence: int) -> bytes:
    return json.dumps(
        {
            "eventId": event_id,
            "eventKind": "subscription_updated",
            "sequence": sequence,
            "occurredAt": (_NOW + timedelta(seconds=sequence)).isoformat(),
            "customerReference": customer_reference,
            "subscriptionReference": "sub_integration_commercial",
            "priceReference": "price_integration_pro",
            "status": "active",
            "currentPeriodEnd": (_NOW + timedelta(days=30)).isoformat(),
            "cancelAtPeriodEnd": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


@pytest.mark.asyncio
async def test_commercial_repository_is_owner_scoped_and_orders_signed_events() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    owner_id = uuid4()
    other_id = uuid4()
    provider = DeterministicBillingProvider(secret=_SECRET, clock=FixedClock())
    service = CommercialService(
        unit_of_work=SqlAlchemyCommercialUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        billing=provider,
        allowed_return_origins=frozenset({_ORIGIN}),
    )
    try:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
            session.add_all(
                [
                    UserModel(
                        id=owner_id,
                        email_normalized=f"commercial-owner-{owner_id.hex}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=_NOW,
                        updated_at=_NOW,
                    ),
                    UserModel(
                        id=other_id,
                        email_normalized=f"commercial-other-{other_id.hex}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=_NOW,
                        updated_at=_NOW,
                    ),
                ]
            )
            await session.execute(
                update(CommercialPlanModel)
                .where(CommercialPlanModel.id == _PRO_PLAN_ID)
                .values(
                    configuration_status="active",
                    currency="USD",
                    unit_amount_minor=123,
                    billing_interval="month",
                    interval_count=1,
                    provider_price_reference="price_integration_pro",
                    entitlements=[
                        {"key": "verified_export", "enabled": True},
                    ],
                    quotas=[
                        {"key": "monthly_exports", "limit": 3, "window": "month"},
                    ],
                    version=2,
                    updated_at=_NOW,
                )
            )
            await session.commit()

        session = await service.create_checkout(
            owner_id,
            CheckoutCommand(
                plan_code="pro",
                success_url=f"{_ORIGIN}/settings/billing?status=success",
                cancel_url=f"{_ORIGIN}/settings/billing?status=cancel",
            ),
            "integration-commercial-checkout",
            _context(owner_id),
        )
        replay = await service.create_checkout(
            owner_id,
            CheckoutCommand(
                plan_code="pro",
                success_url=f"{_ORIGIN}/settings/billing?status=success",
                cancel_url=f"{_ORIGIN}/settings/billing?status=cancel",
            ),
            "integration-commercial-checkout",
            _context(owner_id),
        )
        assert replay == session

        first_raw = _payload(
            session.provider_customer_reference,
            event_id="evt_integration_2",
            sequence=2,
        )
        first = await service.process_webhook(
            provider="deterministic",
            raw_body=first_raw,
            headers=provider.sign_webhook(first_raw, int(_NOW.timestamp())),
            context=RequestContext(None, "webhook-integration", "w" * 32),
        )
        assert first.event.state is BillingEventState.APPLIED

        stale_raw = _payload(
            session.provider_customer_reference,
            event_id="evt_integration_1",
            sequence=1,
        )
        stale = await service.process_webhook(
            provider="deterministic",
            raw_body=stale_raw,
            headers=provider.sign_webhook(stale_raw, int(_NOW.timestamp())),
            context=RequestContext(None, "webhook-stale", "s" * 32),
        )
        assert stale.event.state is BillingEventState.IGNORED_STALE

        view = await service.get_subscription(owner_id, _context(owner_id))
        assert view.subscription is not None
        assert view.subscription.provider_sequence == 2
        with pytest.raises(CommercialNotFound):
            await service.get_subscription(owner_id, _context(other_id))

        async with database.session() as db:
            subscription = await db.scalar(
                select(SubscriptionModel).where(SubscriptionModel.owner_user_id == owner_id)
            )
            assert subscription is not None
            assert subscription.provider_sequence == 2
            events = tuple(
                await db.scalars(
                    select(BillingEventModel).order_by(BillingEventModel.provider_sequence)
                )
            )
            owned_events = [event for event in events if event.owner_user_id == owner_id]
            assert [event.state for event in owned_events[-2:]] == [
                "ignored_stale",
                "applied",
            ]
            audits = tuple(
                await db.scalars(
                    select(CommercialAuditEventModel).where(
                        CommercialAuditEventModel.owner_user_id == owner_id
                    )
                )
            )
            assert {audit.action for audit in audits} >= {
                "checkout_created",
                "webhook_applied",
                "webhook_ignored",
            }
            assert all(
                session.provider_customer_reference not in repr(audit.event_metadata)
                for audit in audits
            )
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
            await session.execute(
                update(CommercialPlanModel)
                .where(CommercialPlanModel.id == _PRO_PLAN_ID)
                .values(
                    configuration_status="owner_decision_required",
                    currency=None,
                    unit_amount_minor=None,
                    billing_interval=None,
                    interval_count=None,
                    provider_price_reference=None,
                    entitlements=[],
                    quotas=[],
                    version=1,
                    updated_at=_NOW,
                )
            )
            await session.commit()
        await database.dispose()
