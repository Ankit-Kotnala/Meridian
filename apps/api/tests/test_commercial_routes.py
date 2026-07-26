"""Commercial HTTP contract, authorization, and raw-webhook tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.modules.commercial.application import (
    BillingSession,
    CommercialService,
    PlanCatalog,
    SubscriptionView,
    WebhookResult,
)
from careeros.modules.commercial.domain import (
    BillingEvent,
    BillingEventState,
    CommercialPlan,
    CommercialUnavailable,
    PlanCode,
    PlanConfigurationStatus,
    SubscriptionStatus,
)
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_NOW = datetime(2026, 7, 26, 18, tzinfo=UTC)
_ORIGIN = "http://localhost:3000"


def _principal(user_id):
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _plan() -> CommercialPlan:
    return CommercialPlan(
        id=uuid4(),
        code=PlanCode.PRO,
        display_name="Pro",
        description="Configuration requires a product-owner decision.",
        configuration_status=PlanConfigurationStatus.OWNER_DECISION_REQUIRED,
        currency=None,
        unit_amount_minor=None,
        billing_interval=None,
        interval_count=None,
        provider_price_reference=None,
        entitlements=(),
        quotas=(),
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _event(owner_id=None, subscription_id=None) -> BillingEvent:
    return BillingEvent(
        id=uuid4(),
        provider="deterministic",
        provider_event_id="evt_test_api",
        payload_sha256="a" * 64,
        event_kind="subscription_updated",
        provider_sequence=1,
        provider_occurred_at=_NOW,
        provider_customer_reference="cus_test_api",
        provider_subscription_reference="sub_test_api",
        provider_price_reference="price_test_api",
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_end=_NOW + timedelta(days=30),
        cancel_at_period_end=False,
        state=BillingEventState.UNMATCHED_CUSTOMER,
        owner_user_id=owner_id,
        subscription_id=subscription_id,
        created_at=_NOW,
        processed_at=_NOW,
    )


def _client(
    settings: Settings,
    database: FakeDatabase,
    identity: IdentityService,
    commercial: CommercialService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=database,
            identity=identity,
            commercial=commercial,
        )
    )
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def _write_headers() -> dict[str, str]:
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        "Idempotency-Key": "commercial-api-test-key",
    }


def test_commercial_catalog_subscription_and_checkout_contract(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    plan = _plan()
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    service = create_autospec(CommercialService, instance=True)
    service.list_plans.return_value = PlanCatalog(
        plans=(plan,),
        owner_configuration_required=True,
    )
    service.get_subscription.return_value = SubscriptionView(
        subscription=None,
        plan=None,
        billing_available=False,
    )
    service.create_checkout.return_value = BillingSession(
        url="https://billing.invalid/test/checkout/session",
        expires_at=_NOW + timedelta(minutes=30),
        provider_customer_reference="cus_test_api",
    )

    with _client(settings, fake_database, identity, service) as client:
        catalog = client.get("/api/v1/plans")
        assert catalog.status_code == 200
        assert catalog.headers["Cache-Control"] == "no-store"
        assert catalog.json() == {
            "plans": [
                {
                    "id": str(plan.id),
                    "code": "pro",
                    "displayName": "Pro",
                    "description": "Configuration requires a product-owner decision.",
                    "configurationStatus": "owner_decision_required",
                    "purchasable": False,
                    "price": None,
                    "entitlements": [],
                    "quotas": [],
                    "version": 1,
                }
            ],
            "ownerConfigurationRequired": True,
        }

        subscription = client.get("/api/v1/subscription")
        assert subscription.status_code == 200
        assert subscription.json() == {
            "subscription": None,
            "plan": None,
            "billingAvailable": False,
        }
        service.get_subscription.assert_awaited_once()
        assert service.get_subscription.await_args.args[0] == owner_id

        checkout = client.post(
            "/api/v1/subscription/checkout",
            json={
                "planCode": "pro",
                "successUrl": f"{_ORIGIN}/settings/billing?status=success",
                "cancelUrl": f"{_ORIGIN}/settings/billing?status=cancel",
            },
            headers=_write_headers(),
        )
        assert checkout.status_code == 201
        assert checkout.headers["Cache-Control"] == "no-store"
        assert checkout.json()["url"].startswith("https://billing.invalid/")
        assert service.create_checkout.await_args.args[0] == owner_id
        assert service.create_checkout.await_args.args[2] == "commercial-api-test-key"


def test_commercial_mutations_require_csrf_and_return_safe_problems(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(owner_id)
    service = create_autospec(CommercialService, instance=True)
    service.create_checkout.side_effect = CommercialUnavailable("provider detail")

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/subscription/checkout",
            json={
                "planCode": "pro",
                "successUrl": f"{_ORIGIN}/settings/billing",
                "cancelUrl": f"{_ORIGIN}/settings/billing",
            },
            headers={"Idempotency-Key": "commercial-api-test-key"},
        )
        assert missing_csrf.status_code == 403
        service.create_checkout.assert_not_awaited()

        unavailable = client.post(
            "/api/v1/subscription/checkout",
            json={
                "planCode": "pro",
                "successUrl": f"{_ORIGIN}/settings/billing",
                "cancelUrl": f"{_ORIGIN}/settings/billing",
            },
            headers=_write_headers(),
        )
        assert unavailable.status_code == 503
        assert unavailable.headers["content-type"].startswith("application/problem+json")
        assert unavailable.headers["Cache-Control"] == "no-store"
        assert unavailable.json()["code"] == "commercial_unavailable"
        assert "provider detail" not in unavailable.text


def test_billing_webhook_preserves_raw_body_and_has_complete_openapi(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity = create_autospec(IdentityService, instance=True)
    service = create_autospec(CommercialService, instance=True)
    service.process_webhook.return_value = WebhookResult(
        event=_event(),
        replayed=False,
    )
    raw = b'{"eventId":"evt_test_api","opaque":"exact bytes"}'

    with _client(settings, fake_database, identity, service) as client:
        webhook = client.post(
            "/api/v1/webhooks/billing/deterministic",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-CareerOS-Test-Signature": "a" * 64,
                "X-CareerOS-Test-Timestamp": str(int(_NOW.timestamp())),
            },
        )
        assert webhook.status_code == 200
        assert webhook.json() == {
            "accepted": True,
            "replayed": False,
            "state": "unmatched_customer",
        }
        assert service.process_webhook.await_args.kwargs["raw_body"] == raw
        assert (
            service.process_webhook.await_args.kwargs["headers"]["x-careeros-test-signature"]
            == "a" * 64
        )

        document = client.get("/openapi.json").json()

    assert {
        "/api/v1/plans",
        "/api/v1/subscription",
        "/api/v1/subscription/checkout",
        "/api/v1/subscription/portal",
        "/api/v1/subscription/reconcile",
        "/api/v1/webhooks/billing/{provider}",
    }.issubset(document["paths"])
    operation_ids = [
        operation["operationId"]
        for methods in document["paths"].values()
        for method, operation in methods.items()
        if method != "parameters"
    ]
    assert len(operation_ids) == len(set(operation_ids))
