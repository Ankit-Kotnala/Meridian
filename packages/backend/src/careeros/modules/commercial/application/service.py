"""Commercial plan, checkout, webhook, and reconciliation orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from careeros.modules.commercial.domain import (
    BillingAuditAction,
    BillingAuditEvent,
    BillingCustomer,
    BillingEvent,
    BillingEventConflict,
    BillingEventState,
    CommercialIdempotencyConflict,
    CommercialNotFound,
    CommercialPlan,
    CommercialUnavailable,
    CommercialValidationError,
    PlanCode,
    PlanConfigurationStatus,
    Subscription,
)

from .models import (
    BillingSession,
    CheckoutCommand,
    IdempotencyRecord,
    PlanCatalog,
    PortalCommand,
    ProviderSubscriptionEvent,
    RequestContext,
    SubscriptionView,
    WebhookResult,
)
from .ports import (
    BillingProvider,
    Clock,
    CommercialUnitOfWork,
    CommercialUnitOfWorkFactory,
    IdentifierFactory,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_OP_CHECKOUT = "checkout"
_OP_PORTAL = "portal"


class CommercialService:
    """Provider-neutral commercial operations with fail-closed configuration."""

    def __init__(
        self,
        *,
        unit_of_work: CommercialUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        billing: BillingProvider,
        allowed_return_origins: frozenset[str],
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._billing = billing
        self._allowed_return_origins = frozenset(
            _normalized_origin(value) for value in allowed_return_origins
        )
        if not self._allowed_return_origins:
            raise ValueError("commercial return origins cannot be empty")

    async def list_plans(self) -> PlanCatalog:
        async with self._uow() as uow:
            plans = tuple(await uow.list_plans())
        return PlanCatalog(
            plans=plans,
            owner_configuration_required=any(
                item.configuration_status is PlanConfigurationStatus.OWNER_DECISION_REQUIRED
                for item in plans
            ),
        )

    async def get_subscription(
        self,
        owner_user_id: UUID,
        context: RequestContext,
    ) -> SubscriptionView:
        self._authorize(owner_user_id, context)
        async with self._uow() as uow:
            subscription = await uow.get_subscription(owner_user_id)
            plan = (
                await uow.get_plan_by_code(_plan_code_for_id(await uow.list_plans(), subscription))
                if subscription is not None
                else None
            )
        return SubscriptionView(
            subscription=subscription,
            plan=plan,
            billing_available=self._billing.enabled,
        )

    async def create_checkout(
        self,
        owner_user_id: UUID,
        command: CheckoutCommand,
        idempotency_key: str,
        context: RequestContext,
    ) -> BillingSession:
        self._authorize(owner_user_id, context)
        self._require_enabled()
        self._idempotency_key(idempotency_key)
        success_url = self._return_url(command.success_url)
        cancel_url = self._return_url(command.cancel_url)
        try:
            code = PlanCode(command.plan_code)
        except ValueError as exc:
            raise CommercialValidationError("plan code is invalid") from exc
        fingerprint = _fingerprint(
            {
                "operation": _OP_CHECKOUT,
                "planCode": code.value,
                "successUrl": success_url,
                "cancelUrl": cancel_url,
            }
        )
        async with self._uow() as uow:
            existing = await uow.get_idempotency(
                owner_user_id,
                _OP_CHECKOUT,
                idempotency_key,
            )
            if existing is not None:
                self._replay(existing, fingerprint)
                return _session_from_payload(existing.response_payload)
            plan = await uow.get_plan_by_code(code.value)
            if plan is None:
                raise CommercialNotFound
            if not plan.purchasable or plan.provider_price_reference is None:
                raise CommercialUnavailable(
                    "plan pricing and entitlements require product-owner configuration"
                )
            customer = await uow.get_customer(owner_user_id, self._billing.name)

        session = await self._billing.create_checkout(
            owner_reference=f"user:{owner_user_id}",
            existing_customer_reference=(
                customer.provider_customer_reference if customer is not None else None
            ),
            provider_price_reference=plan.provider_price_reference,
            success_url=success_url,
            cancel_url=cancel_url,
            idempotency_key=idempotency_key,
        )
        self._provider_session(session)
        now = self._clock.now()
        payload = _session_payload(session)
        async with self._uow() as uow:
            existing = await uow.get_idempotency(
                owner_user_id,
                _OP_CHECKOUT,
                idempotency_key,
            )
            if existing is not None:
                self._replay(existing, fingerprint)
                return _session_from_payload(existing.response_payload)
            current_plan = await uow.get_plan_by_code(code.value)
            if (
                current_plan is None
                or not current_plan.purchasable
                or current_plan.version != plan.version
                or current_plan.provider_price_reference
                != plan.provider_price_reference
            ):
                raise CommercialUnavailable(
                    "plan configuration changed before checkout completed"
                )
            customer = await uow.get_customer(
                owner_user_id,
                self._billing.name,
                for_update=True,
            )
            if customer is None:
                await uow.add_customer(
                    BillingCustomer(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        provider=self._billing.name,
                        provider_customer_reference=session.provider_customer_reference,
                        created_at=now,
                        updated_at=now,
                    )
                )
            elif customer.provider_customer_reference != session.provider_customer_reference:
                raise CommercialValidationError("billing provider changed the customer reference")
            await uow.add_idempotency(
                IdempotencyRecord(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    operation=_OP_CHECKOUT,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    response_payload=payload,
                    created_at=now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id=owner_user_id,
                    action=BillingAuditAction.CHECKOUT_CREATED,
                    target_type="plan",
                    target_id=current_plan.id,
                    context=context,
                    metadata={"provider": self._billing.name},
                    now=now,
                )
            )
            await uow.commit()
        return session

    async def create_portal(
        self,
        owner_user_id: UUID,
        command: PortalCommand,
        idempotency_key: str,
        context: RequestContext,
    ) -> BillingSession:
        self._authorize(owner_user_id, context)
        self._require_enabled()
        self._idempotency_key(idempotency_key)
        return_url = self._return_url(command.return_url)
        fingerprint = _fingerprint({"operation": _OP_PORTAL, "returnUrl": return_url})
        async with self._uow() as uow:
            existing = await uow.get_idempotency(
                owner_user_id,
                _OP_PORTAL,
                idempotency_key,
            )
            if existing is not None:
                self._replay(existing, fingerprint)
                return _session_from_payload(existing.response_payload)
            customer = await uow.get_customer(owner_user_id, self._billing.name)
            if customer is None:
                raise CommercialNotFound

        session = await self._billing.create_portal(
            provider_customer_reference=customer.provider_customer_reference,
            return_url=return_url,
            idempotency_key=idempotency_key,
        )
        self._provider_session(session)
        now = self._clock.now()
        payload = _session_payload(session)
        async with self._uow() as uow:
            existing = await uow.get_idempotency(
                owner_user_id,
                _OP_PORTAL,
                idempotency_key,
            )
            if existing is not None:
                self._replay(existing, fingerprint)
                return _session_from_payload(existing.response_payload)
            customer = await uow.get_customer(owner_user_id, self._billing.name)
            if customer is None:
                raise CommercialNotFound
            await uow.add_idempotency(
                IdempotencyRecord(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    operation=_OP_PORTAL,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    response_payload=payload,
                    created_at=now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id=owner_user_id,
                    action=BillingAuditAction.PORTAL_CREATED,
                    target_type="billing_customer",
                    target_id=customer.id,
                    context=context,
                    metadata={"provider": self._billing.name},
                    now=now,
                )
            )
            await uow.commit()
        return session

    async def process_webhook(
        self,
        *,
        provider: str,
        raw_body: bytes,
        headers: dict[str, str],
        context: RequestContext,
    ) -> WebhookResult:
        self._require_enabled()
        if provider != self._billing.name:
            raise CommercialNotFound
        normalized = await self._billing.verify_webhook(
            raw_body=raw_body,
            headers=headers,
            now=self._clock.now(),
        )
        if normalized.payload_sha256 != hashlib.sha256(raw_body).hexdigest():
            raise CommercialValidationError("billing provider payload hash mismatch")
        return await self._apply_event(normalized, context)

    async def reconcile(
        self,
        owner_user_id: UUID,
        context: RequestContext,
    ) -> WebhookResult:
        self._authorize(owner_user_id, context)
        self._require_enabled()
        async with self._uow() as uow:
            subscription = await uow.get_subscription(owner_user_id)
            if subscription is None:
                raise CommercialNotFound
        normalized = await self._billing.retrieve_subscription(
            subscription.provider_subscription_reference
        )
        result = await self._apply_event(normalized, context)
        return result

    async def _apply_event(
        self,
        normalized: ProviderSubscriptionEvent,
        context: RequestContext,
    ) -> WebhookResult:
        now = self._clock.now()
        async with self._uow() as uow:
            existing_event = await uow.get_billing_event(
                self._billing.name,
                normalized.provider_event_id,
            )
            if existing_event is not None:
                if existing_event.payload_sha256 != normalized.payload_sha256:
                    raise BillingEventConflict
                return WebhookResult(event=existing_event, replayed=True)

            event = BillingEvent(
                id=self._ids.new(),
                provider=self._billing.name,
                provider_event_id=normalized.provider_event_id,
                payload_sha256=normalized.payload_sha256,
                event_kind=normalized.event_kind,
                provider_sequence=normalized.provider_sequence,
                provider_occurred_at=normalized.provider_occurred_at,
                provider_customer_reference=normalized.provider_customer_reference,
                provider_subscription_reference=(normalized.provider_subscription_reference),
                provider_price_reference=normalized.provider_price_reference,
                subscription_status=normalized.subscription_status,
                current_period_end=normalized.current_period_end,
                cancel_at_period_end=normalized.cancel_at_period_end,
                state=BillingEventState.RECEIVED,
                owner_user_id=None,
                subscription_id=None,
                created_at=now,
                processed_at=None,
            )
            await uow.add_billing_event(event)
            customer = await uow.get_customer_by_provider_reference(
                self._billing.name,
                normalized.provider_customer_reference,
                for_update=True,
            )
            if customer is None:
                event.resolve(
                    state=BillingEventState.UNMATCHED_CUSTOMER,
                    owner_user_id=None,
                    subscription_id=None,
                    now=now,
                )
                await uow.save_billing_event(event)
                await self._ignored_audit(uow, event, context, now)
                await uow.commit()
                return WebhookResult(event=event, replayed=False)
            plan = await uow.get_plan_by_provider_reference(normalized.provider_price_reference)
            if plan is None or not plan.purchasable:
                event.resolve(
                    state=BillingEventState.UNMATCHED_PLAN,
                    owner_user_id=None,
                    subscription_id=None,
                    now=now,
                )
                await uow.save_billing_event(event)
                await self._ignored_audit(uow, event, context, now)
                await uow.commit()
                return WebhookResult(event=event, replayed=False)
            subscription = await uow.get_subscription_by_provider_reference(
                self._billing.name,
                normalized.provider_subscription_reference,
                for_update=True,
            )
            if subscription is None:
                existing_owner_subscription = await uow.get_subscription(
                    customer.owner_user_id,
                    for_update=True,
                )
                if existing_owner_subscription is not None:
                    raise CommercialValidationError(
                        "billing event conflicts with the owner's subscription"
                    )
                subscription = Subscription(
                    id=self._ids.new(),
                    owner_user_id=customer.owner_user_id,
                    plan_id=plan.id,
                    billing_customer_id=customer.id,
                    provider=self._billing.name,
                    provider_subscription_reference=(normalized.provider_subscription_reference),
                    status=normalized.subscription_status,
                    provider_sequence=normalized.provider_sequence,
                    provider_occurred_at=normalized.provider_occurred_at,
                    current_period_end=normalized.current_period_end,
                    cancel_at_period_end=normalized.cancel_at_period_end,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.add_subscription(subscription)
                applied = True
            else:
                if subscription.owner_user_id != customer.owner_user_id:
                    raise CommercialValidationError(
                        "billing customer does not own the subscription"
                    )
                applied = subscription.apply(
                    plan_id=plan.id,
                    status=normalized.subscription_status,
                    provider_sequence=normalized.provider_sequence,
                    provider_occurred_at=normalized.provider_occurred_at,
                    current_period_end=normalized.current_period_end,
                    cancel_at_period_end=normalized.cancel_at_period_end,
                    now=now,
                )
                if applied:
                    await uow.save_subscription(subscription)
            event.resolve(
                state=(BillingEventState.APPLIED if applied else BillingEventState.IGNORED_STALE),
                owner_user_id=customer.owner_user_id,
                subscription_id=subscription.id,
                now=now,
            )
            await uow.save_billing_event(event)
            await uow.add_audit(
                self._audit(
                    owner_user_id=customer.owner_user_id,
                    action=(
                        BillingAuditAction.WEBHOOK_APPLIED
                        if applied
                        else BillingAuditAction.WEBHOOK_IGNORED
                    ),
                    target_type="subscription",
                    target_id=subscription.id,
                    context=context,
                    metadata={
                        "provider": self._billing.name,
                        "eventState": event.state.value,
                    },
                    now=now,
                )
            )
            await uow.commit()
        return WebhookResult(event=event, replayed=False)

    async def _ignored_audit(
        self,
        uow: CommercialUnitOfWork,
        event: BillingEvent,
        context: RequestContext,
        now: datetime,
    ) -> None:
        await uow.add_audit(
            self._audit(
                owner_user_id=None,
                action=BillingAuditAction.WEBHOOK_IGNORED,
                target_type="billing_event",
                target_id=event.id,
                context=context,
                metadata={
                    "provider": self._billing.name,
                    "eventState": event.state.value,
                },
                now=now,
            )
        )

    def _audit(
        self,
        *,
        owner_user_id: UUID | None,
        action: BillingAuditAction,
        target_type: str,
        target_id: UUID | None,
        context: RequestContext,
        metadata: dict[str, object],
        now: datetime,
    ) -> BillingAuditEvent:
        return BillingAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            metadata=metadata,
            occurred_at=now,
        )

    def _return_url(self, value: str) -> str:
        if len(value) > 2_048 or _normalized_origin(value) not in self._allowed_return_origins:
            raise CommercialValidationError("billing return URL is not allowlisted")
        parsed = urlparse(value)
        if parsed.username or parsed.password or parsed.fragment:
            raise CommercialValidationError("billing return URL is invalid")
        return value

    def _provider_session(self, session: BillingSession) -> None:
        parsed = urlparse(session.url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or session.expires_at <= self._clock.now()
        ):
            raise CommercialValidationError("billing provider returned an unsafe session")

    def _authorize(self, owner_user_id: UUID, context: RequestContext) -> None:
        if context.actor_user_id != owner_user_id:
            raise CommercialNotFound

    def _require_enabled(self) -> None:
        if not self._billing.enabled:
            raise CommercialUnavailable("billing provider requires product-owner configuration")

    def _idempotency_key(self, value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise CommercialValidationError("idempotency key is invalid")

    def _replay(self, record: IdempotencyRecord, fingerprint: str) -> None:
        if record.request_fingerprint != fingerprint:
            raise CommercialIdempotencyConflict


def _normalized_origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CommercialValidationError("billing return URL origin is invalid")
    if parsed.username or parsed.password:
        raise CommercialValidationError("billing return URL origin is invalid")
    default_port = (parsed.scheme == "http" and parsed.port in {None, 80}) or (
        parsed.scheme == "https" and parsed.port in {None, 443}
    )
    authority = parsed.hostname if default_port else f"{parsed.hostname}:{parsed.port}"
    return f"{parsed.scheme}://{authority}"


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _session_payload(session: BillingSession) -> dict[str, object]:
    return {
        "url": session.url,
        "expiresAt": session.expires_at.isoformat(),
        "providerCustomerReference": session.provider_customer_reference,
    }


def _session_from_payload(payload: Mapping[str, object]) -> BillingSession:
    try:
        return BillingSession(
            url=str(payload["url"]),
            expires_at=datetime.fromisoformat(str(payload["expiresAt"])),
            provider_customer_reference=str(payload["providerCustomerReference"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CommercialValidationError("stored billing session is invalid") from exc


def _plan_code_for_id(
    plans: Sequence[CommercialPlan],
    subscription: Subscription,
) -> str:
    for item in plans:
        if item.id == subscription.plan_id:
            return str(item.code)
    raise CommercialNotFound
