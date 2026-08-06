"""SQLAlchemy mappings for the Phase 9 networking bounded context."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base
from rezumi.modules.networking.domain import NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS

_RELATIONSHIP_STAGES = ("new", "warm", "active", "trusted", "dormant", "archived")
_CONTACT_REFERRAL_STATES = (
    "none",
    "considering",
    "requested",
    "referred",
    "declined",
    "cancelled",
)
_CONSENT_PURPOSES = ("collection", "storage", "outreach")
_CONSENT_ACTIONS = ("granted", "withdrawn")
_CONSENT_POLICY_VERSIONS = NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS
_INTERACTION_KINDS = ("email", "call", "meeting", "message", "social", "referral", "other")
_INTERACTION_DIRECTIONS = ("inbound", "outbound", "mutual")
_REFERRAL_STATUSES = ("planned", "requested", "referred", "declined", "cancelled")
_TEMPLATE_KINDS = ("introduction", "follow_up", "referral_request", "thank_you", "custom")
_REMINDER_STATUSES = ("active", "completed", "cancelled")
_OCCURRENCE_STATUSES = ("scheduled", "due", "acknowledged", "cancelled", "dead_letter")
_OUTBOX_STATUSES = ("pending", "leased", "processed", "cancelled", "dead_letter")
_AUDIT_ACTIONS = (
    "organization_created",
    "organization_updated",
    "organization_deleted",
    "contact_created",
    "contact_updated",
    "contact_deleted",
    "consent_granted",
    "consent_withdrawn",
    "note_created",
    "interaction_recorded",
    "referral_created",
    "referral_updated",
    "template_created",
    "template_updated",
    "reminder_created",
    "reminder_updated",
    "reminder_occurrence_materialized",
    "reminder_occurrence_due",
    "reminder_occurrence_acknowledged",
    "reminder_occurrence_snoozed",
    "reminder_occurrence_failed",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class NetworkingOrganizationModel(Base):
    __tablename__ = "networking_organizations"
    __table_args__ = (
        CheckConstraint("version > 0", name="networking_organization_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_organizations_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_organizations_owner_id"),
        Index(
            "ix_networking_organizations_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    normalized_search: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkingContactModel(Base):
    __tablename__ = "networking_contacts"
    __table_args__ = (
        CheckConstraint(
            f"relationship_stage IN ({_values(_RELATIONSHIP_STAGES)})",
            name="networking_contact_stage_valid",
        ),
        CheckConstraint(
            f"referral_state IN ({_values(_CONTACT_REFERRAL_STATES)})",
            name="networking_contact_referral_state_valid",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR ("
            "organization_id IS NULL AND name = '[deleted]' AND role IS NULL "
            "AND email IS NULL AND phone IS NULL AND profile_url IS NULL "
            "AND location IS NULL AND relationship_stage = 'archived' "
            "AND referral_state = 'cancelled' AND tags = '[]'::jsonb "
            "AND normalized_search = '[deleted]' AND last_contact_at IS NULL "
            "AND next_contact_at IS NULL)",
            name="networking_contact_deleted_redacted",
        ),
        CheckConstraint("version > 0", name="networking_contact_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_contacts_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "organization_id"],
            [
                "networking_organizations.owner_user_id",
                "networking_organizations.id",
            ],
            name="fk_networking_contacts_owner_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_contacts_owner_id"),
        Index(
            "ix_networking_contacts_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
        Index(
            "ix_networking_contacts_owner_stage",
            "owner_user_id",
            "relationship_stage",
            "updated_at",
        ),
        Index(
            "ix_networking_contacts_owner_organization",
            "owner_user_id",
            "organization_id",
            "updated_at",
        ),
        Index(
            "ix_networking_contacts_owner_next_contact",
            "owner_user_id",
            "next_contact_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    profile_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(200))
    relationship_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    referral_state: Mapped[str] = mapped_column(String(24), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    normalized_search: Mapped[str] = mapped_column(Text, nullable=False)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkingConsentEventModel(Base):
    __tablename__ = "networking_consent_events"
    __table_args__ = (
        CheckConstraint(
            f"purpose IN ({_values(_CONSENT_PURPOSES)})",
            name="networking_consent_purpose_valid",
        ),
        CheckConstraint(
            f"action IN ({_values(_CONSENT_ACTIONS)})",
            name="networking_consent_action_valid",
        ),
        CheckConstraint(
            f"policy_version IN ({_values(_CONSENT_POLICY_VERSIONS)})",
            name="networking_consent_policy_version_valid",
        ),
        CheckConstraint("sequence > 0", name="networking_consent_sequence_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_consent_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_consent_owner_contact",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_networking_consent_actor",
            ondelete="SET NULL",
        ),
        UniqueConstraint(
            "owner_user_id",
            "contact_id",
            "sequence",
            name="uq_networking_consent_contact_sequence",
        ),
        Index(
            "ix_networking_consent_contact_sequence",
            "owner_user_id",
            "contact_id",
            "sequence",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingContactNoteModel(Base):
    __tablename__ = "networking_contact_notes"
    __table_args__ = (
        CheckConstraint(
            "deleted_at IS NULL OR body = '[deleted]'",
            name="networking_note_deleted_redacted",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_notes_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_notes_owner_contact",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_contact_notes_owner_id"),
        Index(
            "ix_networking_notes_contact_created",
            "owner_user_id",
            "contact_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkingInteractionModel(Base):
    __tablename__ = "networking_interactions"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_values(_INTERACTION_KINDS)})",
            name="networking_interaction_kind_valid",
        ),
        CheckConstraint(
            f"direction IN ({_values(_INTERACTION_DIRECTIONS)})",
            name="networking_interaction_direction_valid",
        ),
        CheckConstraint(
            "delivery_state = 'recorded_only'",
            name="networking_interaction_record_only",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR summary = '[deleted]'",
            name="networking_interaction_deleted_redacted",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_interactions_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_interactions_owner_contact",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "template_id"],
            ["networking_templates.owner_user_id", "networking_templates.id"],
            name="fk_networking_interactions_owner_template",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_interactions_owner_id"),
        Index(
            "ix_networking_interactions_contact_occurred",
            "owner_user_id",
            "contact_id",
            "occurred_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    direction: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkingReferralModel(Base):
    __tablename__ = "networking_referrals"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_REFERRAL_STATUSES)})",
            name="networking_referral_status_valid",
        ),
        CheckConstraint("version > 0", name="networking_referral_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_referrals_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_referrals_owner_contact",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_referrals_owner_id"),
        Index(
            "ix_networking_referrals_contact_updated",
            "owner_user_id",
            "contact_id",
            "updated_at",
            "id",
        ),
        Index(
            "ix_networking_referrals_owner_application",
            "owner_user_id",
            "application_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    application_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingTemplateModel(Base):
    __tablename__ = "networking_templates"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_values(_TEMPLATE_KINDS)})",
            name="networking_template_kind_valid",
        ),
        CheckConstraint("version > 0", name="networking_template_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_templates_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_templates_owner_id"),
        Index(
            "ix_networking_templates_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkingReminderModel(Base):
    __tablename__ = "networking_reminders"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_REMINDER_STATUSES)})",
            name="networking_reminder_status_valid",
        ),
        CheckConstraint(
            "recurrence_days IS NULL OR recurrence_days BETWEEN 1 AND 365",
            name="networking_reminder_recurrence_valid",
        ),
        CheckConstraint(
            "max_attempts BETWEEN 1 AND 20",
            name="networking_reminder_attempts_valid",
        ),
        CheckConstraint("version > 0", name="networking_reminder_version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_reminders_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_reminders_owner_contact",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_networking_reminders_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "id",
            "contact_id",
            name="uq_networking_reminders_owner_id_contact",
        ),
        Index(
            "ix_networking_reminders_contact_due",
            "owner_user_id",
            "contact_id",
            "due_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recurrence_days: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingReminderOccurrenceModel(Base):
    __tablename__ = "networking_reminder_occurrences"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_OCCURRENCE_STATUSES)})",
            name="networking_occurrence_status_valid",
        ),
        CheckConstraint(
            "occurrence_number > 0",
            name="networking_occurrence_number_positive",
        ),
        CheckConstraint(
            "trace_id ~ '^[0-9a-f]{32}$'",
            name="networking_occurrence_trace_id_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_occurrences_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "reminder_id", "contact_id"],
            [
                "networking_reminders.owner_user_id",
                "networking_reminders.id",
                "networking_reminders.contact_id",
            ],
            name="fk_networking_occurrences_owner_reminder_contact",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "contact_id"],
            ["networking_contacts.owner_user_id", "networking_contacts.id"],
            name="fk_networking_occurrences_owner_contact",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_networking_reminder_occurrences_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "reminder_id",
            "occurrence_number",
            name="uq_networking_occurrence_reminder_number",
        ),
        Index(
            "ix_networking_occurrences_reminder_scheduled",
            "owner_user_id",
            "reminder_id",
            "scheduled_for",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reminder_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingReminderOutboxModel(Base):
    __tablename__ = "networking_reminder_outbox"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_OUTBOX_STATUSES)})",
            name="networking_outbox_status_valid",
        ),
        CheckConstraint(
            "kind = 'local_reminder_due'",
            name="networking_outbox_local_only",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 20 "
            "AND attempt_count <= max_attempts",
            name="networking_outbox_attempts_valid",
        ),
        CheckConstraint(
            "((status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'leased' AND lease_token IS NULL "
            "AND lease_expires_at IS NULL))",
            name="networking_outbox_lease_consistent",
        ),
        CheckConstraint(
            "trace_id ~ '^[0-9a-f]{32}$'",
            name="networking_outbox_trace_id_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_outbox_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "occurrence_id"],
            [
                "networking_reminder_occurrences.owner_user_id",
                "networking_reminder_occurrences.id",
            ],
            name="fk_networking_outbox_owner_occurrence",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "occurrence_id",
            name="uq_networking_outbox_owner_occurrence",
        ),
        Index(
            "ix_networking_outbox_claim",
            "status",
            "available_at",
            "id",
        ),
        Index(
            "ix_networking_outbox_lease",
            "status",
            "lease_expires_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    occurrence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingIdempotencyModel(Base):
    __tablename__ = "networking_idempotency"
    __table_args__ = (
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="networking_idempotency_fingerprint_length",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_idempotency_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_networking_idempotency_owner_key",
        ),
        Index(
            "ix_networking_idempotency_owner_created",
            "owner_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    response_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkingAuditEventModel(Base):
    __tablename__ = "networking_audit_events"
    __table_args__ = (
        CheckConstraint(
            f"action IN ({_values(_AUDIT_ACTIONS)})",
            name="networking_audit_action_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_networking_audit_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_networking_audit_actor",
            ondelete="SET NULL",
        ),
        Index(
            "ix_networking_audit_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
