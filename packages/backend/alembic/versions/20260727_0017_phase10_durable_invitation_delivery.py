"""Add durable terminal cancellation for organization invitation delivery.

Revision ID: 20260727_0017
Revises: 20260726_0016
Create Date: 2026-07-27 00:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0017"
down_revision: str | None = "20260726_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OUTBOX = "organization_invitation_outbox"
_AUDIT = "organization_audit_events"


def upgrade() -> None:
    op.add_column(
        _OUTBOX,
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        "ck_organization_invitation_outbox_terminal_state_valid",
        _OUTBOX,
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_invitation_outbox_terminal_state_valid",
        _OUTBOX,
        "num_nonnulls(published_at, dead_lettered_at, cancelled_at) <= 1",
    )
    op.drop_index(
        "ix_organization_invitation_outbox_pending",
        table_name=_OUTBOX,
    )
    op.create_index(
        "ix_organization_invitation_outbox_pending",
        _OUTBOX,
        ["next_attempt_at", "lease_expires_at"],
        postgresql_where=sa.text(
            "published_at IS NULL AND dead_lettered_at IS NULL AND cancelled_at IS NULL"
        ),
    )
    op.drop_constraint(
        "ck_organization_audit_events_action_valid",
        _AUDIT,
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_audit_events_action_valid",
        _AUDIT,
        "action IN ('organization_created','organization_updated',"
        "'invitation_created','invitation_delivered','invitation_delivery_failed',"
        "'invitation_expired','invitation_accepted','invitation_revoked',"
        "'member_suspended','grant_created','grant_revoked')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    cancelled = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM organization_invitation_outbox "
            "WHERE cancelled_at IS NOT NULL)"
        )
    )
    if cancelled:
        raise RuntimeError(
            "Cannot downgrade durable invitation delivery while cancelled outbox rows exist"
        )
    op.drop_constraint(
        "ck_organization_audit_events_action_valid",
        _AUDIT,
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_audit_events_action_valid",
        _AUDIT,
        "action IN ('organization_created','organization_updated',"
        "'invitation_created','invitation_delivered','invitation_delivery_failed',"
        "'invitation_accepted','invitation_revoked','member_suspended',"
        "'grant_created','grant_revoked')",
    )
    op.drop_index(
        "ix_organization_invitation_outbox_pending",
        table_name=_OUTBOX,
    )
    op.create_index(
        "ix_organization_invitation_outbox_pending",
        _OUTBOX,
        ["published_at", "dead_lettered_at", "next_attempt_at"],
    )
    op.drop_constraint(
        "ck_organization_invitation_outbox_terminal_state_valid",
        _OUTBOX,
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_invitation_outbox_terminal_state_valid",
        _OUTBOX,
        "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
    )
    op.drop_column(_OUTBOX, "cancelled_at")
