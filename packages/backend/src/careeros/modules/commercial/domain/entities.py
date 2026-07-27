"""Commercial plan and subscription domain entities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from .errors import CommercialValidationError

_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9._:/-]{1,255}$")


def _text(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise CommercialValidationError(f"{field} is invalid")
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise CommercialValidationError(f"{field} contains unsupported characters")
    return normalized


def _optional_reference(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if _REFERENCE.fullmatch(normalized) is None:
        raise CommercialValidationError(f"{field} is invalid")
    return normalized


def _key(value: str, field: str) -> str:
    normalized = value.strip()
    if _KEY.fullmatch(normalized) is None:
        raise CommercialValidationError(f"{field} is invalid")
    return normalized


class PlanCode(StrEnum):
    FREE = "free"
    JOB_HUNT_SPRINT = "job_hunt_sprint"
    PRO = "pro"
    COACH_ORGANIZATION = "coach_organization"


class PlanConfigurationStatus(StrEnum):
    OWNER_DECISION_REQUIRED = "owner_decision_required"
    ACTIVE = "active"
    ARCHIVED = "archived"


class BillingInterval(StrEnum):
    MONTH = "month"
    YEAR = "year"
    FIXED_TERM = "fixed_term"


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"


class BillingEventState(StrEnum):
    RECEIVED = "received"
    APPLIED = "applied"
    IGNORED_STALE = "ignored_stale"
    UNMATCHED_CUSTOMER = "unmatched_customer"
    UNMATCHED_PLAN = "unmatched_plan"


class BillingAuditAction(StrEnum):
    CHECKOUT_CREATED = "checkout_created"
    PORTAL_CREATED = "portal_created"
    WEBHOOK_APPLIED = "webhook_applied"
    WEBHOOK_IGNORED = "webhook_ignored"
    RECONCILED = "reconciled"


@dataclass(frozen=True, slots=True)
class PlanEntitlement:
    key: str
    enabled: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "entitlement key"))
        if type(self.enabled) is not bool:
            raise CommercialValidationError("entitlement value is invalid")


@dataclass(frozen=True, slots=True)
class PlanQuota:
    key: str
    limit: int
    window: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "quota key"))
        if type(self.limit) is not int or not 0 <= self.limit <= 2_147_483_647:
            raise CommercialValidationError("quota limit is invalid")
        object.__setattr__(self, "window", _key(self.window, "quota window"))


@dataclass(frozen=True, slots=True)
class CommercialPlan:
    id: UUID
    code: PlanCode
    display_name: str
    description: str
    configuration_status: PlanConfigurationStatus
    currency: str | None
    unit_amount_minor: int | None
    billing_interval: BillingInterval | None
    interval_count: int | None
    provider_price_reference: str | None
    entitlements: tuple[PlanEntitlement, ...]
    quotas: tuple[PlanQuota, ...]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _text(self.display_name, "plan display name", 120)
        _text(self.description, "plan description", 500)
        if not 1 <= self.version <= 2_147_483_647:
            raise CommercialValidationError("plan version is invalid")
        if self.created_at > self.updated_at:
            raise CommercialValidationError("plan timestamps are invalid")
        entitlement_keys = tuple(item.key for item in self.entitlements)
        quota_keys = tuple(item.key for item in self.quotas)
        if len(entitlement_keys) != len(set(entitlement_keys)):
            raise CommercialValidationError("plan entitlement keys must be unique")
        if len(quota_keys) != len(set(quota_keys)):
            raise CommercialValidationError("plan quota keys must be unique")
        provider_reference = _optional_reference(
            self.provider_price_reference,
            "provider price reference",
        )
        object.__setattr__(self, "provider_price_reference", provider_reference)
        pricing = (
            self.currency,
            self.unit_amount_minor,
            self.billing_interval,
            self.interval_count,
            provider_reference,
        )
        if self.configuration_status is PlanConfigurationStatus.OWNER_DECISION_REQUIRED:
            if any(value is not None for value in pricing):
                raise CommercialValidationError(
                    "unconfigured plans cannot contain inferred pricing"
                )
            if self.entitlements or self.quotas:
                raise CommercialValidationError(
                    "unconfigured plans cannot contain inferred entitlements or quotas"
                )
            return
        if self.configuration_status is PlanConfigurationStatus.ACTIVE:
            if any(value is None for value in pricing):
                raise CommercialValidationError("active plans require complete pricing")
            if self.currency is None or re.fullmatch(r"[A-Z]{3}", self.currency) is None:
                raise CommercialValidationError("plan currency is invalid")
            if self.unit_amount_minor is None or not 0 <= self.unit_amount_minor <= 2_147_483_647:
                raise CommercialValidationError("plan price is invalid")
            if self.interval_count is None or not 1 <= self.interval_count <= 120:
                raise CommercialValidationError("billing interval count is invalid")

    @property
    def purchasable(self) -> bool:
        return self.configuration_status is PlanConfigurationStatus.ACTIVE

    @property
    def entitlement_map(self) -> Mapping[str, bool]:
        return MappingProxyType({item.key: item.enabled for item in self.entitlements})

    @property
    def quota_map(self) -> Mapping[str, PlanQuota]:
        return MappingProxyType({item.key: item for item in self.quotas})


@dataclass(frozen=True, slots=True)
class BillingCustomer:
    id: UUID
    owner_user_id: UUID
    provider: str
    provider_customer_reference: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _key(self.provider, "billing provider")
        object.__setattr__(
            self,
            "provider_customer_reference",
            _optional_reference(
                self.provider_customer_reference,
                "provider customer reference",
            ),
        )
        if self.created_at > self.updated_at:
            raise CommercialValidationError("billing customer timestamps are invalid")


@dataclass(slots=True)
class Subscription:
    id: UUID
    owner_user_id: UUID
    plan_id: UUID
    billing_customer_id: UUID
    provider: str
    provider_subscription_reference: str
    status: SubscriptionStatus
    provider_sequence: int
    provider_occurred_at: datetime
    current_period_end: datetime | None
    cancel_at_period_end: bool
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _key(self.provider, "billing provider")
        object.__setattr__(
            self,
            "provider_subscription_reference",
            _optional_reference(
                self.provider_subscription_reference,
                "provider subscription reference",
            ),
        )
        if not 0 <= self.provider_sequence <= 9_223_372_036_854_775_807:
            raise CommercialValidationError("provider sequence is invalid")
        if not 1 <= self.version <= 2_147_483_647:
            raise CommercialValidationError("subscription version is invalid")
        if self.created_at > self.updated_at:
            raise CommercialValidationError("subscription timestamps are invalid")

    def apply(
        self,
        *,
        plan_id: UUID,
        status: SubscriptionStatus,
        provider_sequence: int,
        provider_occurred_at: datetime,
        current_period_end: datetime | None,
        cancel_at_period_end: bool,
        now: datetime,
    ) -> bool:
        if provider_sequence <= self.provider_sequence:
            return False
        self.plan_id = plan_id
        self.status = status
        self.provider_sequence = provider_sequence
        self.provider_occurred_at = provider_occurred_at
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        self.version += 1
        self.updated_at = now
        self.__post_init__()
        return True


@dataclass(slots=True)
class BillingEvent:
    id: UUID
    provider: str
    provider_event_id: str
    payload_sha256: str
    event_kind: str
    provider_sequence: int
    provider_occurred_at: datetime
    provider_customer_reference: str
    provider_subscription_reference: str
    provider_price_reference: str
    subscription_status: SubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool
    state: BillingEventState
    owner_user_id: UUID | None
    subscription_id: UUID | None
    created_at: datetime
    processed_at: datetime | None

    def __post_init__(self) -> None:
        _key(self.provider, "billing provider")
        _optional_reference(self.provider_event_id, "provider event id")
        _key(self.event_kind, "billing event kind")
        _optional_reference(
            self.provider_customer_reference,
            "provider customer reference",
        )
        _optional_reference(
            self.provider_subscription_reference,
            "provider subscription reference",
        )
        _optional_reference(
            self.provider_price_reference,
            "provider price reference",
        )
        if re.fullmatch(r"[a-f0-9]{64}", self.payload_sha256) is None:
            raise CommercialValidationError("billing payload hash is invalid")
        if not 0 <= self.provider_sequence <= 9_223_372_036_854_775_807:
            raise CommercialValidationError("provider sequence is invalid")
        if (self.owner_user_id is None) != (self.subscription_id is None):
            raise CommercialValidationError("billing event ownership links are inconsistent")

    def resolve(
        self,
        *,
        state: BillingEventState,
        owner_user_id: UUID | None,
        subscription_id: UUID | None,
        now: datetime,
    ) -> None:
        self.state = state
        self.owner_user_id = owner_user_id
        self.subscription_id = subscription_id
        self.processed_at = now
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class BillingAuditEvent:
    id: UUID
    owner_user_id: UUID | None
    action: BillingAuditAction
    target_type: str
    target_id: UUID | None
    request_id: str
    trace_id: str
    metadata: Mapping[str, object]
    occurred_at: datetime

    def __post_init__(self) -> None:
        _key(self.target_type, "audit target type")
        _text(self.request_id, "request id", 128)
        _text(self.trace_id, "trace id", 128)
