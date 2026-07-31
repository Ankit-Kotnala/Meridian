"""Disabled runtime and deterministic test billing providers."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from careeros.modules.commercial.application.models import (
    BillingSession,
    ProviderSubscriptionEvent,
)
from careeros.modules.commercial.application.ports import BillingProvider, Clock
from careeros.modules.commercial.domain import (
    BillingSignatureRejected,
    CommercialNotFound,
    CommercialUnavailable,
    CommercialValidationError,
    SubscriptionStatus,
)

_SIGNATURE_HEADER = "x-careeros-test-signature"
_TIMESTAMP_HEADER = "x-careeros-test-timestamp"
_MAX_WEBHOOK_BYTES = 65_536
_MAX_CLOCK_SKEW_SECONDS = 300


class DisabledBillingProvider(BillingProvider):
    """Fail-closed provider used until the product owner selects billing."""

    @property
    def name(self) -> str:
        return "disabled"

    @property
    def enabled(self) -> bool:
        return False

    async def create_checkout(
        self,
        *,
        owner_reference: str,
        existing_customer_reference: str | None,
        provider_price_reference: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> BillingSession:
        del (
            owner_reference,
            existing_customer_reference,
            provider_price_reference,
            success_url,
            cancel_url,
            idempotency_key,
        )
        raise CommercialUnavailable("billing provider is disabled")

    async def create_portal(
        self,
        *,
        provider_customer_reference: str,
        return_url: str,
        idempotency_key: str,
    ) -> BillingSession:
        del provider_customer_reference, return_url, idempotency_key
        raise CommercialUnavailable("billing provider is disabled")

    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        now: datetime,
    ) -> ProviderSubscriptionEvent:
        del raw_body, headers, now
        raise CommercialUnavailable("billing provider is disabled")

    async def retrieve_subscription(
        self,
        provider_subscription_reference: str,
    ) -> ProviderSubscriptionEvent:
        del provider_subscription_reference
        raise CommercialUnavailable("billing provider is disabled")


class DeterministicBillingProvider(BillingProvider):
    """Credential-free local/test adapter with strict signed raw webhooks."""

    def __init__(
        self,
        *,
        secret: str,
        clock: Clock,
        subscriptions: Mapping[str, ProviderSubscriptionEvent] | None = None,
    ) -> None:
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("deterministic billing secret must contain at least 32 bytes")
        self._secret = encoded
        self._clock = clock
        self._subscriptions = MappingProxyType(dict(subscriptions or {}))

    @property
    def name(self) -> str:
        return "deterministic"

    @property
    def enabled(self) -> bool:
        return True

    async def create_checkout(
        self,
        *,
        owner_reference: str,
        existing_customer_reference: str | None,
        provider_price_reference: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> BillingSession:
        del provider_price_reference, success_url, cancel_url
        customer = existing_customer_reference or (
            "cus_test_" + hashlib.sha256(owner_reference.encode()).hexdigest()[:32]
        )
        token = hashlib.sha256(f"checkout:{owner_reference}:{idempotency_key}".encode()).hexdigest()
        return BillingSession(
            url=f"https://billing.invalid/test/checkout/{token}",
            expires_at=self._clock.now() + timedelta(minutes=30),
            provider_customer_reference=customer,
        )

    async def create_portal(
        self,
        *,
        provider_customer_reference: str,
        return_url: str,
        idempotency_key: str,
    ) -> BillingSession:
        del return_url
        token = hashlib.sha256(
            f"portal:{provider_customer_reference}:{idempotency_key}".encode()
        ).hexdigest()
        return BillingSession(
            url=f"https://billing.invalid/test/portal/{token}",
            expires_at=self._clock.now() + timedelta(minutes=30),
            provider_customer_reference=provider_customer_reference,
        )

    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        now: datetime,
    ) -> ProviderSubscriptionEvent:
        if not raw_body or len(raw_body) > _MAX_WEBHOOK_BYTES:
            raise CommercialValidationError("billing webhook body is invalid")
        timestamp_value = headers.get(_TIMESTAMP_HEADER)
        signature_value = headers.get(_SIGNATURE_HEADER)
        if timestamp_value is None or signature_value is None:
            raise BillingSignatureRejected
        try:
            timestamp = int(timestamp_value)
        except ValueError as exc:
            raise BillingSignatureRejected from exc
        now_seconds = int(now.timestamp())
        if abs(now_seconds - timestamp) > _MAX_CLOCK_SKEW_SECONDS:
            raise BillingSignatureRejected
        expected = hmac.new(
            self._secret,
            str(timestamp).encode() + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        supplied = signature_value.removeprefix("v1=") if signature_value.startswith("v1=") else ""
        if not hmac.compare_digest(expected, supplied):
            raise BillingSignatureRejected
        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommercialValidationError("billing webhook JSON is invalid") from exc
        return _provider_event(payload, hashlib.sha256(raw_body).hexdigest())

    async def retrieve_subscription(
        self,
        provider_subscription_reference: str,
    ) -> ProviderSubscriptionEvent:
        event = self._subscriptions.get(provider_subscription_reference)
        if event is None:
            raise CommercialNotFound
        return event

    def sign_webhook(self, raw_body: bytes, timestamp: int) -> dict[str, str]:
        """Create deterministic headers for tests and local tooling."""
        signature = hmac.new(
            self._secret,
            str(timestamp).encode() + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return {
            _TIMESTAMP_HEADER: str(timestamp),
            _SIGNATURE_HEADER: f"v1={signature}",
        }


def _provider_event(
    value: object,
    payload_sha256: str,
) -> ProviderSubscriptionEvent:
    expected = {
        "eventId",
        "eventKind",
        "sequence",
        "occurredAt",
        "customerReference",
        "subscriptionReference",
        "priceReference",
        "status",
        "currentPeriodEnd",
        "cancelAtPeriodEnd",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise CommercialValidationError("billing webhook schema is invalid")
    if (
        not all(
            isinstance(value[key], str)
            for key in (
                "eventId",
                "eventKind",
                "occurredAt",
                "customerReference",
                "subscriptionReference",
                "priceReference",
                "status",
            )
        )
        or type(value["sequence"]) is not int
        or type(value["cancelAtPeriodEnd"]) is not bool
        or (
            value["currentPeriodEnd"] is not None and not isinstance(value["currentPeriodEnd"], str)
        )
    ):
        raise CommercialValidationError("billing webhook value types are invalid")
    try:
        occurred_at = _aware_datetime(value["occurredAt"])
        current_period_end = (
            _aware_datetime(value["currentPeriodEnd"])
            if value["currentPeriodEnd"] is not None
            else None
        )
        status = SubscriptionStatus(value["status"])
    except (TypeError, ValueError) as exc:
        raise CommercialValidationError("billing webhook values are invalid") from exc
    return ProviderSubscriptionEvent(
        provider_event_id=value["eventId"],
        payload_sha256=payload_sha256,
        event_kind=value["eventKind"],
        provider_sequence=value["sequence"],
        provider_occurred_at=occurred_at,
        provider_customer_reference=value["customerReference"],
        provider_subscription_reference=value["subscriptionReference"],
        provider_price_reference=value["priceReference"],
        subscription_status=status,
        current_period_end=current_period_end,
        cancel_at_period_end=value["cancelAtPeriodEnd"],
    )


def _aware_datetime(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(UTC)
