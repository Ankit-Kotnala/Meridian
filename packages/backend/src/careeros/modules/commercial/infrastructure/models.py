"""SQLAlchemy mappings for plans, subscriptions, and billing events."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careeros.foundation.database import Base

_PLAN_CODES = ("free", "job_hunt_sprint", "pro", "coach_organization")
_PLAN_STATES = ("owner_decision_required", "active", "archived")
_BILLING_INTERVALS = ("month", "year", "fixed_term")
_SUBSCRIPTION_STATES = (
    "pending",
    "trialing",
    "active",
    "past_due",
    "paused",
    "canceled",
)
_EVENT_STATES = (
    "received",
    "applied",
    "ignored_stale",
    "unmatched_customer",
    "unmatched_plan",
)
_AUDIT_ACTIONS = (
    "checkout_created",
    "portal_created",
    "webhook_applied",
    "webhook_ignored",
    "reconciled",
)
_OPERATIONS = ("checkout", "portal")


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class CommercialPlanModel(Base):
    __tablename__ = "commercial_plans"
    __table_args__ = (
        CheckConstraint(f"code IN ({_values(_PLAN_CODES)})", name="code_valid"),
        CheckConstraint(
            f"configuration_status IN ({_values(_PLAN_STATES)})",
            name="configuration_status_valid",
        ),
        CheckConstraint(
            f"billing_interval IS NULL OR billing_interval IN ({_values(_BILLING_INTERVALS)})",
            name="billing_interval_valid",
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="currency_valid",
        ),
        CheckConstraint(
            "unit_amount_minor IS NULL OR unit_amount_minor >= 0",
            name="unit_amount_nonnegative",
        ),
        CheckConstraint(
            "interval_count IS NULL OR interval_count BETWEEN 1 AND 120",
            name="interval_count_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "("
            "configuration_status <> 'owner_decision_required'"
            " OR (currency IS NULL AND unit_amount_minor IS NULL"
            " AND billing_interval IS NULL AND interval_count IS NULL"
            " AND provider_price_reference IS NULL"
            " AND entitlements = '[]'::jsonb AND quotas = '[]'::jsonb)"
            ")",
            name="unconfigured_has_no_inferred_values",
        ),
        CheckConstraint(
            "("
            "configuration_status <> 'active'"
            " OR (currency IS NOT NULL AND unit_amount_minor IS NOT NULL"
            " AND billing_interval IS NOT NULL AND interval_count IS NOT NULL"
            " AND provider_price_reference IS NOT NULL)"
            ")",
            name="active_has_complete_pricing",
        ),
        UniqueConstraint("code", name="uq_commercial_plans_code"),
        UniqueConstraint(
            "provider_price_reference",
            name="uq_commercial_plans_provider_price_reference",
        ),
        Index(
            "ix_commercial_plans_status_code",
            "configuration_status",
            "code",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    configuration_status: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    unit_amount_minor: Mapped[int | None] = mapped_column(Integer)
    billing_interval: Mapped[str | None] = mapped_column(String(16))
    interval_count: Mapped[int | None] = mapped_column(Integer)
    provider_price_reference: Mapped[str | None] = mapped_column(String(255))
    entitlements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    quotas: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BillingCustomerModel(Base):
    __tablename__ = "commercial_billing_customers"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_commercial_billing_customers_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "provider",
            name="uq_commercial_billing_customers_owner_provider",
        ),
        UniqueConstraint(
            "provider",
            "provider_customer_reference",
            name="uq_commercial_billing_customers_provider_reference",
        ),
        Index(
            "ix_commercial_billing_customers_owner_provider",
            "owner_user_id",
            "provider",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_customer_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionModel(Base):
    __tablename__ = "commercial_subscriptions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_SUBSCRIPTION_STATES)})",
            name="status_valid",
        ),
        CheckConstraint("provider_sequence >= 0", name="provider_sequence_nonnegative"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "billing_customer_id"],
            [
                "commercial_billing_customers.owner_user_id",
                "commercial_billing_customers.id",
            ],
            name="fk_commercial_subscriptions_owner_customer",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_commercial_subscriptions_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            name="uq_commercial_subscriptions_owner",
        ),
        UniqueConstraint(
            "provider",
            "provider_subscription_reference",
            name="uq_commercial_subscriptions_provider_reference",
        ),
        Index(
            "ix_commercial_subscriptions_status_updated",
            "status",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("commercial_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    billing_customer_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_subscription_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BillingEventModel(Base):
    __tablename__ = "commercial_billing_events"
    __table_args__ = (
        CheckConstraint(
            f"subscription_status IN ({_values(_SUBSCRIPTION_STATES)})",
            name="subscription_status_valid",
        ),
        CheckConstraint(
            f"state IN ({_values(_EVENT_STATES)})",
            name="state_valid",
        ),
        CheckConstraint("provider_sequence >= 0", name="provider_sequence_nonnegative"),
        CheckConstraint("octet_length(payload_sha256) = 32", name="payload_hash_length"),
        CheckConstraint(
            "(owner_user_id IS NULL) = (subscription_id IS NULL)",
            name="ownership_links_consistent",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "subscription_id"],
            [
                "commercial_subscriptions.owner_user_id",
                "commercial_subscriptions.id",
            ],
            name="fk_commercial_billing_events_owner_subscription",
            ondelete="SET NULL",
        ),
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_commercial_billing_events_provider_event",
        ),
        Index(
            "ix_commercial_billing_events_state_created",
            "state",
            "created_at",
        ),
        Index(
            "ix_commercial_billing_events_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    provider_customer_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_subscription_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    provider_price_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_status: Mapped[str] = mapped_column(String(24), nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    subscription_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommercialIdempotencyModel(Base):
    __tablename__ = "commercial_idempotency_records"
    __table_args__ = (
        CheckConstraint(
            f"operation IN ({_values(_OPERATIONS)})",
            name="operation_valid",
        ),
        CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="request_fingerprint_length",
        ),
        UniqueConstraint(
            "owner_user_id",
            "operation",
            "idempotency_key",
            name="uq_commercial_idempotency_owner_operation_key",
        ),
        Index(
            "ix_commercial_idempotency_owner_created",
            "owner_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommercialAuditEventModel(Base):
    __tablename__ = "commercial_audit_events"
    __table_args__ = (
        CheckConstraint(
            f"action IN ({_values(_AUDIT_ACTIONS)})",
            name="action_valid",
        ),
        Index(
            "ix_commercial_audit_events_owner_occurred",
            "owner_user_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_commercial_audit_events_action_occurred",
            "action",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
