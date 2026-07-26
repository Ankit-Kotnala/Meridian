"""Inward-facing ports for networking use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.networking.domain import (
    NetworkingAuditEvent,
    NetworkingConsentEvent,
    NetworkingContact,
    NetworkingContactNote,
    NetworkingIdempotencyRecord,
    NetworkingInteraction,
    NetworkingOrganization,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingReminderOccurrence,
    NetworkingReminderOutboxEntry,
    NetworkingTemplate,
)

from .models import (
    ContactFilter,
    DueReminderView,
    NetworkingApplicationReference,
    NetworkingCursor,
    NetworkingKeysetCursor,
    OrganizationFilter,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class ApplicationReferenceProvider(Protocol):
    async def get_reference(
        self, owner_user_id: UUID, application_id: UUID
    ) -> NetworkingApplicationReference | None: ...


class NetworkingUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock_owner(self, owner_user_id: UUID) -> None: ...

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None: ...

    async def list_organizations(
        self,
        owner_user_id: UUID,
        filter_by: OrganizationFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingOrganization]: ...

    async def get_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingOrganization | None: ...

    async def add_organization(self, organization: NetworkingOrganization) -> None: ...

    async def count_organizations(self, owner_user_id: UUID) -> int: ...

    async def save_organization(self, organization: NetworkingOrganization) -> None: ...

    async def detach_organization_contacts(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        updated_at: datetime,
    ) -> int: ...

    async def list_contacts(
        self,
        owner_user_id: UUID,
        filter_by: ContactFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingContact]: ...

    async def get_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingContact | None: ...

    async def add_contact(self, contact: NetworkingContact) -> None: ...

    async def count_contacts(self, owner_user_id: UUID) -> int: ...

    async def save_contact(self, contact: NetworkingContact) -> None: ...

    async def add_consent_event(self, event: NetworkingConsentEvent) -> None: ...

    async def count_consent_events(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def get_latest_consent_events(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> list[NetworkingConsentEvent]: ...

    async def next_consent_sequence(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def list_consent_event_page(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingConsentEvent]: ...

    async def get_consent_events_for_contacts(
        self, owner_user_id: UUID, contact_ids: tuple[UUID, ...]
    ) -> dict[UUID, list[NetworkingConsentEvent]]: ...

    async def add_note(self, note: NetworkingContactNote) -> None: ...

    async def count_notes(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def list_notes(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingContactNote]: ...

    async def get_note(
        self, owner_user_id: UUID, note_id: UUID
    ) -> NetworkingContactNote | None: ...

    async def redact_contact_content(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        redacted_at: datetime,
        *,
        outreach_only: bool,
    ) -> None: ...

    async def add_interaction(self, interaction: NetworkingInteraction) -> None: ...

    async def count_interactions(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def list_interactions(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingInteraction]: ...

    async def get_interaction(
        self, owner_user_id: UUID, interaction_id: UUID
    ) -> NetworkingInteraction | None: ...

    async def add_referral(self, referral: NetworkingReferral) -> None: ...

    async def count_referrals(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def get_referral(
        self,
        owner_user_id: UUID,
        referral_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReferral | None: ...

    async def list_referrals(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReferral]: ...

    async def cancel_contact_referrals(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None: ...

    async def save_referral(self, referral: NetworkingReferral) -> None: ...

    async def add_template(self, template: NetworkingTemplate) -> None: ...

    async def count_templates(self, owner_user_id: UUID) -> int: ...

    async def get_template(
        self,
        owner_user_id: UUID,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingTemplate | None: ...

    async def list_templates(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingTemplate]: ...

    async def save_template(self, template: NetworkingTemplate) -> None: ...

    async def add_reminder(self, reminder: NetworkingReminder) -> None: ...

    async def count_reminders(self, owner_user_id: UUID, contact_id: UUID) -> int: ...

    async def get_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminder | None: ...

    async def list_reminders(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReminder]: ...

    async def next_active_reminder_at(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> datetime | None: ...

    async def save_reminder(self, reminder: NetworkingReminder) -> None: ...

    async def cancel_contact_reminders(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None: ...

    async def cancel_reminder_occurrences(
        self, owner_user_id: UUID, reminder_id: UUID, updated_at: datetime
    ) -> None: ...

    async def add_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None: ...

    async def count_reminder_occurrences(self, owner_user_id: UUID, reminder_id: UUID) -> int: ...

    async def prune_terminal_reminder_history(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        retain: int,
    ) -> int: ...

    async def get_occurrence(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOccurrence | None: ...

    async def get_latest_reminder_occurrence(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
    ) -> NetworkingReminderOccurrence | None: ...

    async def find_occurrence(
        self, owner_user_id: UUID, reminder_id: UUID, occurrence_number: int
    ) -> NetworkingReminderOccurrence | None: ...

    async def next_occurrence_number(self, owner_user_id: UUID, reminder_id: UUID) -> int: ...

    async def save_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None: ...

    async def add_outbox(self, entry: NetworkingReminderOutboxEntry) -> None: ...

    async def get_outbox(
        self,
        entry_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOutboxEntry | None: ...

    async def get_occurrence_outbox(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
    ) -> NetworkingReminderOutboxEntry | None: ...

    async def get_reminder_executions(
        self,
        owner_user_id: UUID,
        reminder_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[NetworkingReminderOccurrence, NetworkingReminderOutboxEntry]]: ...

    async def list_due_reminders(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[DueReminderView]: ...

    async def list_claimable_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]: ...

    async def list_expired_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]: ...

    async def save_outbox(self, entry: NetworkingReminderOutboxEntry) -> None: ...

    async def add_idempotency(self, record: NetworkingIdempotencyRecord) -> None: ...

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> NetworkingIdempotencyRecord | None: ...

    async def add_audit(self, event: NetworkingAuditEvent) -> None: ...

    async def commit(self) -> None: ...


NetworkingUnitOfWorkFactory = Callable[[], NetworkingUnitOfWork]
