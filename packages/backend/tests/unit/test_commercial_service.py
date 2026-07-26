"""Commercial configuration, idempotency, webhook, and ownership tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from careeros.modules.commercial.application import (
    CheckoutCommand,
    CommercialService,
    PortalCommand,
    RequestContext,
)
from careeros.modules.commercial.domain import (
    BillingEventConflict,
    BillingEventState,
    BillingSignatureRejected,
    CommercialIdempotencyConflict,
    CommercialNotFound,
    CommercialUnavailable,
    CommercialValidationError,
    PlanConfigurationStatus,
)
from careeros.modules.commercial.infrastructure import (
    DeterministicBillingProvider,
    DisabledBillingProvider,
)
from commercial_memory import (
    NOW,
    FixedClock,
    MemoryCommercial,
    SequentialIds,
    configured_test_plan,
    unconfigured_test_plan,
)

_SECRET = "fictional-local-billing-secret-at-least-32-bytes"  # noqa: S105
_ORIGIN = "http://localhost:3000"


def _context(owner_id):
    return RequestContext(
        actor_user_id=owner_id,
        request_id="request-commercial-test",
        trace_id="trace-commercial-test",
    )


def _service(
    state: MemoryCommercial,
    *,
    enabled: bool = True,
) -> tuple[CommercialService, DeterministicBillingProvider | DisabledBillingProvider]:
    clock = FixedClock()
    provider: DeterministicBillingProvider | DisabledBillingProvider
    provider = (
        DeterministicBillingProvider(secret=_SECRET, clock=clock)
        if enabled
        else DisabledBillingProvider()
    )
    return (
        CommercialService(
            unit_of_work=state,
            clock=clock,
            identifiers=SequentialIds(),
            billing=provider,
            allowed_return_origins=frozenset({_ORIGIN}),
        ),
        provider,
    )


def _webhook_payload(
    *,
    event_id: str = "evt_test_1",
    sequence: int = 1,
    customer_reference: str,
    price_reference: str = "price_test_pro",
) -> bytes:
    return json.dumps(
        {
            "eventId": event_id,
            "eventKind": "subscription_updated",
            "sequence": sequence,
            "occurredAt": (NOW + timedelta(seconds=sequence)).isoformat(),
            "customerReference": customer_reference,
            "subscriptionReference": "sub_test_1",
            "priceReference": price_reference,
            "status": "active",
            "currentPeriodEnd": (NOW + timedelta(days=30)).isoformat(),
            "cancelAtPeriodEnd": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


@pytest.mark.asyncio
async def test_unconfigured_catalog_contains_no_inferred_commercial_values() -> None:
    state = MemoryCommercial()
    service, _provider = _service(state, enabled=False)

    catalog = await service.list_plans()

    assert catalog.owner_configuration_required
    assert catalog.plans[0].configuration_status is (
        PlanConfigurationStatus.OWNER_DECISION_REQUIRED
    )
    assert catalog.plans[0].currency is None
    assert catalog.plans[0].entitlements == ()
    assert catalog.plans[0].quotas == ()
    owner_id = uuid4()
    with pytest.raises(CommercialUnavailable, match="provider"):
        await service.create_checkout(
            owner_id,
            CheckoutCommand(
                plan_code="free",
                success_url=f"{_ORIGIN}/settings/billing?status=success",
                cancel_url=f"{_ORIGIN}/settings/billing?status=cancel",
            ),
            "disabled-checkout-key",
            _context(owner_id),
        )


def test_unconfigured_plan_rejects_invented_pricing_entitlements_or_quotas() -> None:
    plan = unconfigured_test_plan()

    with pytest.raises(CommercialValidationError, match="inferred pricing"):
        replace(plan, currency="USD")
    with pytest.raises(CommercialValidationError, match="entitlements or quotas"):
        replace(plan, entitlements=configured_test_plan().entitlements)


@pytest.mark.asyncio
async def test_checkout_is_owner_scoped_allowlisted_and_idempotent() -> None:
    owner_id = uuid4()
    state = MemoryCommercial([configured_test_plan()])
    service, _provider = _service(state)
    command = CheckoutCommand(
        plan_code="pro",
        success_url=f"{_ORIGIN}/settings/billing?status=success",
        cancel_url=f"{_ORIGIN}/settings/billing?status=cancel",
    )

    first = await service.create_checkout(
        owner_id,
        command,
        "checkout-idempotency-key",
        _context(owner_id),
    )
    second = await service.create_checkout(
        owner_id,
        command,
        "checkout-idempotency-key",
        _context(owner_id),
    )

    assert first == second
    assert first.url.startswith("https://billing.invalid/test/checkout/")
    assert len(state.customers) == 1
    assert len(state.idempotency) == 1
    assert [item.action.value for item in state.audits] == ["checkout_created"]

    with pytest.raises(CommercialIdempotencyConflict):
        await service.create_checkout(
            owner_id,
            replace(command, cancel_url=f"{_ORIGIN}/settings"),
            "checkout-idempotency-key",
            _context(owner_id),
        )
    with pytest.raises(CommercialNotFound):
        await service.get_subscription(owner_id, _context(uuid4()))
    with pytest.raises(CommercialValidationError, match="allowlisted"):
        await service.create_checkout(
            owner_id,
            replace(command, success_url="https://attacker.invalid/return"),
            "checkout-second-key",
            _context(owner_id),
        )


@pytest.mark.asyncio
async def test_signed_webhook_applies_once_and_ignores_older_provider_state() -> None:
    owner_id = uuid4()
    state = MemoryCommercial([configured_test_plan()])
    service, provider = _service(state)
    assert isinstance(provider, DeterministicBillingProvider)
    checkout = await service.create_checkout(
        owner_id,
        CheckoutCommand(
            plan_code="pro",
            success_url=f"{_ORIGIN}/settings/billing",
            cancel_url=f"{_ORIGIN}/settings/billing",
        ),
        "checkout-webhook-key",
        _context(owner_id),
    )
    raw = _webhook_payload(customer_reference=checkout.provider_customer_reference)
    headers = provider.sign_webhook(raw, int(NOW.timestamp()))

    first = await service.process_webhook(
        provider="deterministic",
        raw_body=raw,
        headers=headers,
        context=RequestContext(
            actor_user_id=None,
            request_id="webhook-request",
            trace_id="webhook-trace",
        ),
    )
    replay = await service.process_webhook(
        provider="deterministic",
        raw_body=raw,
        headers=headers,
        context=RequestContext(
            actor_user_id=None,
            request_id="webhook-replay",
            trace_id="webhook-replay-trace",
        ),
    )

    assert first.event.state is BillingEventState.APPLIED
    assert replay.replayed
    assert state.subscriptions[owner_id].provider_sequence == 1
    assert len(state.events) == 1

    stale_raw = _webhook_payload(
        event_id="evt_test_stale",
        sequence=0,
        customer_reference=checkout.provider_customer_reference,
    )
    stale = await service.process_webhook(
        provider="deterministic",
        raw_body=stale_raw,
        headers=provider.sign_webhook(stale_raw, int(NOW.timestamp())),
        context=RequestContext(
            actor_user_id=None,
            request_id="webhook-stale",
            trace_id="webhook-stale-trace",
        ),
    )
    assert stale.event.state is BillingEventState.IGNORED_STALE
    assert state.subscriptions[owner_id].provider_sequence == 1


@pytest.mark.asyncio
async def test_webhook_signature_schema_collision_and_unmatched_links_fail_closed() -> None:
    state = MemoryCommercial([configured_test_plan()])
    service, provider = _service(state)
    assert isinstance(provider, DeterministicBillingProvider)
    raw = _webhook_payload(customer_reference="cus_test_missing")

    with pytest.raises(BillingSignatureRejected):
        await service.process_webhook(
            provider="deterministic",
            raw_body=raw,
            headers={},
            context=RequestContext(None, "request", "trace"),
        )
    unmatched = await service.process_webhook(
        provider="deterministic",
        raw_body=raw,
        headers=provider.sign_webhook(raw, int(NOW.timestamp())),
        context=RequestContext(None, "request", "trace"),
    )
    assert unmatched.event.state is BillingEventState.UNMATCHED_CUSTOMER
    assert unmatched.event.owner_user_id is None
    assert unmatched.event.subscription_id is None

    changed = _webhook_payload(
        customer_reference="cus_test_other",
        event_id="evt_test_1",
    )
    with pytest.raises(BillingEventConflict):
        await service.process_webhook(
            provider="deterministic",
            raw_body=changed,
            headers=provider.sign_webhook(changed, int(NOW.timestamp())),
            context=RequestContext(None, "request-2", "trace-2"),
        )


@pytest.mark.asyncio
async def test_portal_requires_an_existing_owner_customer() -> None:
    owner_id = uuid4()
    state = MemoryCommercial([configured_test_plan()])
    service, _provider = _service(state)

    with pytest.raises(CommercialNotFound):
        await service.create_portal(
            owner_id,
            PortalCommand(return_url=f"{_ORIGIN}/settings/billing"),
            "portal-missing-customer",
            _context(owner_id),
        )
