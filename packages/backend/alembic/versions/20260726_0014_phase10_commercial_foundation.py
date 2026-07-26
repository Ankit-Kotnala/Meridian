"""Add the Phase 10 commercial plan and billing foundation.

Revision ID: 20260726_0014
Revises: 20260726_0013
Create Date: 2026-07-26 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0014"
down_revision: str | None = "20260726_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FREE_PLAN_ID = UUID("00000000-0000-4000-8000-000000001001")
SPRINT_PLAN_ID = UUID("00000000-0000-4000-8000-000000001002")
PRO_PLAN_ID = UUID("00000000-0000-4000-8000-000000001003")
COACH_PLAN_ID = UUID("00000000-0000-4000-8000-000000001004")
CREATED_AT = datetime(2026, 7, 26, 22, tzinfo=UTC)


def upgrade() -> None:
    op.create_table(
        "commercial_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("configuration_status", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("unit_amount_minor", sa.Integer(), nullable=True),
        sa.Column("billing_interval", sa.String(length=16), nullable=True),
        sa.Column("interval_count", sa.Integer(), nullable=True),
        sa.Column("provider_price_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "entitlements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "quotas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "billing_interval IS NULL OR billing_interval IN ('month','year','fixed_term')",
            name="ck_commercial_plans_billing_interval_valid",
        ),
        sa.CheckConstraint(
            "code IN ('free','job_hunt_sprint','pro','coach_organization')",
            name="ck_commercial_plans_code_valid",
        ),
        sa.CheckConstraint(
            "configuration_status IN ('owner_decision_required','active','archived')",
            name="ck_commercial_plans_configuration_status_valid",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_commercial_plans_currency_valid",
        ),
        sa.CheckConstraint(
            "interval_count IS NULL OR interval_count BETWEEN 1 AND 120",
            name="ck_commercial_plans_interval_count_valid",
        ),
        sa.CheckConstraint(
            "unit_amount_minor IS NULL OR unit_amount_minor >= 0",
            name="ck_commercial_plans_unit_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "("
            "configuration_status <> 'owner_decision_required'"
            " OR (currency IS NULL AND unit_amount_minor IS NULL"
            " AND billing_interval IS NULL AND interval_count IS NULL"
            " AND provider_price_reference IS NULL"
            " AND entitlements = '[]'::jsonb AND quotas = '[]'::jsonb)"
            ")",
            name="ck_commercial_plans_unconfigured_has_no_inferred_values",
        ),
        sa.CheckConstraint(
            "("
            "configuration_status <> 'active'"
            " OR (currency IS NOT NULL AND unit_amount_minor IS NOT NULL"
            " AND billing_interval IS NOT NULL AND interval_count IS NOT NULL"
            " AND provider_price_reference IS NOT NULL)"
            ")",
            name="ck_commercial_plans_active_has_complete_pricing",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_commercial_plans_version_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_plans"),
        sa.UniqueConstraint("code", name="uq_commercial_plans_code"),
        sa.UniqueConstraint(
            "provider_price_reference",
            name="uq_commercial_plans_provider_price_reference",
        ),
    )
    op.create_index(
        "ix_commercial_plans_status_code",
        "commercial_plans",
        ["configuration_status", "code"],
    )

    op.create_table(
        "commercial_billing_customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column(
            "provider_customer_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_commercial_billing_customers_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_billing_customers"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_commercial_billing_customers_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "provider",
            name="uq_commercial_billing_customers_owner_provider",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_customer_reference",
            name="uq_commercial_billing_customers_provider_reference",
        ),
    )
    op.create_index(
        "ix_commercial_billing_customers_owner_provider",
        "commercial_billing_customers",
        ["owner_user_id", "provider"],
    )

    op.create_table(
        "commercial_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("billing_customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column(
            "provider_subscription_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "provider_occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider_sequence >= 0",
            name="ck_commercial_subscriptions_provider_sequence_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('pending','trialing','active','past_due','paused','canceled')",
            name="ck_commercial_subscriptions_status_valid",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_commercial_subscriptions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "billing_customer_id"],
            [
                "commercial_billing_customers.owner_user_id",
                "commercial_billing_customers.id",
            ],
            name="fk_commercial_subscriptions_owner_customer",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_commercial_subscriptions_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["commercial_plans.id"],
            name="fk_commercial_subscriptions_plan_id_commercial_plans",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_subscriptions"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_commercial_subscriptions_owner_id",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            name="uq_commercial_subscriptions_owner",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_subscription_reference",
            name="uq_commercial_subscriptions_provider_reference",
        ),
    )
    op.create_index(
        "ix_commercial_subscriptions_status_updated",
        "commercial_subscriptions",
        ["status", "updated_at"],
    )

    op.create_table(
        "commercial_billing_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("payload_sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("event_kind", sa.String(length=80), nullable=False),
        sa.Column("provider_sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "provider_occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "provider_customer_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "provider_subscription_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "provider_price_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("subscription_status", sa.String(length=24), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(owner_user_id IS NULL) = (subscription_id IS NULL)",
            name="ck_commercial_billing_events_ownership_links_consistent",
        ),
        sa.CheckConstraint(
            "octet_length(payload_sha256) = 32",
            name="ck_commercial_billing_events_payload_hash_length",
        ),
        sa.CheckConstraint(
            "provider_sequence >= 0",
            name="ck_commercial_billing_events_provider_sequence_nonnegative",
        ),
        sa.CheckConstraint(
            "state IN ('received','applied','ignored_stale','unmatched_customer','unmatched_plan')",
            name="ck_commercial_billing_events_state_valid",
        ),
        sa.CheckConstraint(
            "subscription_status IN ('pending','trialing','active','past_due','paused','canceled')",
            name="ck_commercial_billing_events_subscription_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "subscription_id"],
            [
                "commercial_subscriptions.owner_user_id",
                "commercial_subscriptions.id",
            ],
            name="fk_commercial_billing_events_owner_subscription",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_billing_events"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_commercial_billing_events_provider_event",
        ),
    )
    op.create_index(
        "ix_commercial_billing_events_owner_created",
        "commercial_billing_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_commercial_billing_events_state_created",
        "commercial_billing_events",
        ["state", "created_at"],
    )

    op.create_table(
        "commercial_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "request_fingerprint",
            sa.LargeBinary(length=32),
            nullable=False,
        ),
        sa.Column(
            "response_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('checkout','portal')",
            name="ck_commercial_idempotency_records_operation_valid",
        ),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="ck_commercial_idempotency_records_request_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_commercial_idempotency_records_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_idempotency_records"),
        sa.UniqueConstraint(
            "owner_user_id",
            "operation",
            "idempotency_key",
            name="uq_commercial_idempotency_owner_operation_key",
        ),
    )
    op.create_index(
        "ix_commercial_idempotency_owner_created",
        "commercial_idempotency_records",
        ["owner_user_id", "created_at"],
    )

    op.create_table(
        "commercial_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN "
            "('checkout_created','portal_created','webhook_applied',"
            "'webhook_ignored','reconciled')",
            name="ck_commercial_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_commercial_audit_events_owner_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_audit_events"),
    )
    op.create_index(
        "ix_commercial_audit_events_action_occurred",
        "commercial_audit_events",
        ["action", "occurred_at"],
    )
    op.create_index(
        "ix_commercial_audit_events_owner_occurred",
        "commercial_audit_events",
        ["owner_user_id", "occurred_at", "id"],
    )

    plans = sa.table(
        "commercial_plans",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("configuration_status", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("unit_amount_minor", sa.Integer()),
        sa.column("billing_interval", sa.String()),
        sa.column("interval_count", sa.Integer()),
        sa.column("provider_price_reference", sa.String()),
        sa.column("entitlements", postgresql.JSONB()),
        sa.column("quotas", postgresql.JSONB()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        plans,
        [
            _unconfigured_plan(
                FREE_PLAN_ID,
                "free",
                "Free",
                "Pricing, entitlements, and quotas require product-owner configuration.",
            ),
            _unconfigured_plan(
                SPRINT_PLAN_ID,
                "job_hunt_sprint",
                "Job Hunt Sprint",
                "Pricing, term, entitlements, and quotas require product-owner configuration.",
            ),
            _unconfigured_plan(
                PRO_PLAN_ID,
                "pro",
                "Pro",
                "Pricing, entitlements, and quotas require product-owner configuration.",
            ),
            _unconfigured_plan(
                COACH_PLAN_ID,
                "coach_organization",
                "Coach/Organization",
                "Pricing, tenancy, entitlements, and quotas require product-owner configuration.",
            ),
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_audit_events_owner_occurred",
        table_name="commercial_audit_events",
    )
    op.drop_index(
        "ix_commercial_audit_events_action_occurred",
        table_name="commercial_audit_events",
    )
    op.drop_table("commercial_audit_events")
    op.drop_index(
        "ix_commercial_idempotency_owner_created",
        table_name="commercial_idempotency_records",
    )
    op.drop_table("commercial_idempotency_records")
    op.drop_index(
        "ix_commercial_billing_events_state_created",
        table_name="commercial_billing_events",
    )
    op.drop_index(
        "ix_commercial_billing_events_owner_created",
        table_name="commercial_billing_events",
    )
    op.drop_table("commercial_billing_events")
    op.drop_index(
        "ix_commercial_subscriptions_status_updated",
        table_name="commercial_subscriptions",
    )
    op.drop_table("commercial_subscriptions")
    op.drop_index(
        "ix_commercial_billing_customers_owner_provider",
        table_name="commercial_billing_customers",
    )
    op.drop_table("commercial_billing_customers")
    op.drop_index(
        "ix_commercial_plans_status_code",
        table_name="commercial_plans",
    )
    op.drop_table("commercial_plans")


def _unconfigured_plan(
    plan_id: UUID,
    code: str,
    display_name: str,
    description: str,
) -> dict[str, object]:
    return {
        "id": plan_id,
        "code": code,
        "display_name": display_name,
        "description": description,
        "configuration_status": "owner_decision_required",
        "currency": None,
        "unit_amount_minor": None,
        "billing_interval": None,
        "interval_count": None,
        "provider_price_reference": None,
        "entitlements": [],
        "quotas": [],
        "version": 1,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
