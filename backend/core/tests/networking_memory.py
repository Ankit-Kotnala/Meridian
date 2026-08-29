"""Deterministic in-memory adapters for networking service tests."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from rezumi.modules.networking.application import (
    ContactFilter,
    DueReminderView,
    NetworkingApplicationReference,
    NetworkingCursor,
    NetworkingKeysetCursor,
    OrganizationFilter,
    ReminderExecutionView,
)
from rezumi.modules.networking.domain import (
    DELETED_TEXT,
    ConsentAction,
    ConsentPurpose,
    NetworkingAuditEvent,
    NetworkingConsentEvent,
    NetworkingContact,
    NetworkingContactNote,
    NetworkingIdempotencyConflict,
    NetworkingIdempotencyRecord,
    NetworkingInteraction,
    NetworkingOrganization,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingReminderOccurrence,
    NetworkingReminderOutboxEntry,
    NetworkingTemplate,
    ReferralStatus,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
    ReminderStatus,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000901")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000902")
APPLICATION_ID = UUID("00000000-0000-4000-8000-000000000903")
NOW = datetime(2026, 7, 25, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticApplicationProvider:
    async def get_reference(
        self, owner_user_id: UUID, application_id: UUID
    ) -> NetworkingApplicationReference | None:
        if owner_user_id != OWNER_ID or application_id != APPLICATION_ID:
            return None
        return NetworkingApplicationReference(
            application_id=application_id,
            stage="interview",
        )


class MemoryNetworking:
    def __init__(self) -> None:
        self.organizations: dict[UUID, NetworkingOrganization] = {}
        self.contacts: dict[UUID, NetworkingContact] = {}
        self.consent_events: list[NetworkingConsentEvent] = []
        self.notes: dict[UUID, NetworkingContactNote] = {}
        self.interactions: dict[UUID, NetworkingInteraction] = {}
        self.referrals: dict[UUID, NetworkingReferral] = {}
        self.templates: dict[UUID, NetworkingTemplate] = {}
        self.reminders: dict[UUID, NetworkingReminder] = {}
        self.occurrences: dict[UUID, NetworkingReminderOccurrence] = {}
        self.outbox: dict[UUID, NetworkingReminderOutboxEntry] = {}
        self.idempotency: dict[tuple[UUID, str], NetworkingIdempotencyRecord] = {}
        self.audits: list[NetworkingAuditEvent] = []

    def __call__(self) -> MemoryNetworking:
        return self

    async def __aenter__(self) -> MemoryNetworking:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def lock_owner(self, owner_user_id: UUID) -> None:
        _ = owner_user_id

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None:
        _ = owner_user_id, idempotency_key

    async def list_organizations(
        self,
        owner_user_id: UUID,
        filter_by: OrganizationFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingOrganization]:
        records = [
            value
            for value in self.organizations.values()
            if value.owner_user_id == owner_user_id
            and value.deleted_at is None
            and (filter_by.query is None or filter_by.query in value.normalized_search)
            and (filter_by.tag is None or filter_by.tag in value.tags)
            and _after(value.updated_at, value.id, after)
        ]
        records.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return deepcopy(records[:limit])

    async def get_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingOrganization | None:
        _ = for_update
        value = self.organizations.get(organization_id)
        if (
            value is None
            or value.owner_user_id != owner_user_id
            or (value.deleted_at is not None and not include_deleted)
        ):
            return None
        return deepcopy(value)

    async def add_organization(self, organization: NetworkingOrganization) -> None:
        self.organizations[organization.id] = deepcopy(organization)

    async def count_organizations(self, owner_user_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.deleted_at is None
            for item in self.organizations.values()
        )

    async def save_organization(self, organization: NetworkingOrganization) -> None:
        self.organizations[organization.id] = deepcopy(organization)

    async def detach_organization_contacts(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        updated_at: datetime,
    ) -> int:
        detached = 0
        for contact_id, contact in tuple(self.contacts.items()):
            if (
                contact.owner_user_id == owner_user_id
                and contact.organization_id == organization_id
                and contact.deleted_at is None
            ):
                self.contacts[contact_id] = replace(
                    contact,
                    organization_id=None,
                    version=contact.version + 1,
                    updated_at=updated_at,
                )
                detached += 1
        return detached

    async def list_contacts(
        self,
        owner_user_id: UUID,
        filter_by: ContactFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingContact]:
        records = [
            value
            for value in self.contacts.values()
            if value.owner_user_id == owner_user_id
            and value.deleted_at is None
            and (filter_by.query is None or filter_by.query in value.normalized_search)
            and (
                filter_by.organization_id is None
                or value.organization_id == filter_by.organization_id
            )
            and (
                filter_by.relationship_stage is None
                or value.relationship_stage is filter_by.relationship_stage
            )
            and (
                filter_by.referral_state is None or value.referral_state is filter_by.referral_state
            )
            and (filter_by.tag is None or filter_by.tag in value.tags)
            and (
                filter_by.outreach_consent is None
                or self._allows_outreach(owner_user_id, value.id) == filter_by.outreach_consent
            )
            and _after(value.updated_at, value.id, after)
        ]
        records.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return deepcopy(records[:limit])

    async def get_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingContact | None:
        _ = for_update
        value = self.contacts.get(contact_id)
        if (
            value is None
            or value.owner_user_id != owner_user_id
            or (value.deleted_at is not None and not include_deleted)
        ):
            return None
        return deepcopy(value)

    async def add_contact(self, contact: NetworkingContact) -> None:
        self.contacts[contact.id] = deepcopy(contact)

    async def count_contacts(self, owner_user_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.deleted_at is None
            for item in self.contacts.values()
        )

    async def save_contact(self, contact: NetworkingContact) -> None:
        self.contacts[contact.id] = deepcopy(contact)

    async def add_consent_event(self, event: NetworkingConsentEvent) -> None:
        self.consent_events.append(deepcopy(event))

    async def count_consent_events(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.contact_id == contact_id
            for item in self.consent_events
        )

    async def get_latest_consent_events(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> list[NetworkingConsentEvent]:
        latest: dict[ConsentPurpose, NetworkingConsentEvent] = {}
        for event in self.consent_events:
            if (
                event.owner_user_id == owner_user_id
                and event.contact_id == contact_id
                and self._active_contact(owner_user_id, contact_id)
            ):
                current = latest.get(event.purpose)
                if current is None or event.sequence > current.sequence:
                    latest[event.purpose] = event
        return deepcopy(sorted(latest.values(), key=lambda item: item.sequence))

    async def next_consent_sequence(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return (
            max(
                (
                    event.sequence
                    for event in self.consent_events
                    if event.owner_user_id == owner_user_id and event.contact_id == contact_id
                ),
                default=0,
            )
            + 1
        )

    async def list_consent_event_page(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingConsentEvent]:
        values = sorted(
            (
                event
                for event in self.consent_events
                if event.owner_user_id == owner_user_id
                and event.contact_id == contact_id
                and self._active_contact(owner_user_id, contact_id)
                and _after_keyset(event.sequence, event.id, after, ascending=True)
            ),
            key=lambda item: (item.sequence, item.id),
        )
        return deepcopy(values[:limit])

    async def get_consent_events_for_contacts(
        self, owner_user_id: UUID, contact_ids: tuple[UUID, ...]
    ) -> dict[UUID, list[NetworkingConsentEvent]]:
        return {
            contact_id: await self.get_latest_consent_events(owner_user_id, contact_id)
            for contact_id in contact_ids
            if self._active_contact(owner_user_id, contact_id)
        }

    async def add_note(self, note: NetworkingContactNote) -> None:
        self.notes[note.id] = deepcopy(note)

    async def count_notes(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.contact_id == contact_id
            for item in self.notes.values()
        )

    async def list_notes(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingContactNote]:
        if not self._active_contact(owner_user_id, contact_id):
            return []
        values = sorted(
            (
                item
                for item in self.notes.values()
                if item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and item.deleted_at is None
                and _after_keyset(item.created_at, item.id, after, ascending=False)
            ),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
        return deepcopy(values[:limit])

    async def get_note(self, owner_user_id: UUID, note_id: UUID) -> NetworkingContactNote | None:
        value = self.notes.get(note_id)
        if (
            value is None
            or value.owner_user_id != owner_user_id
            or value.deleted_at is not None
            or not self._active_contact(owner_user_id, value.contact_id)
        ):
            return None
        return deepcopy(value)

    async def redact_contact_content(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        redacted_at: datetime,
        *,
        outreach_only: bool,
    ) -> None:
        if not outreach_only:
            for item_id, note_item in tuple(self.notes.items()):
                if (
                    note_item.owner_user_id == owner_user_id
                    and note_item.contact_id == contact_id
                    and note_item.deleted_at is None
                ):
                    self.notes[item_id] = replace(
                        note_item,
                        body=DELETED_TEXT,
                        deleted_at=redacted_at,
                    )
        for item_id, interaction_item in tuple(self.interactions.items()):
            if (
                interaction_item.owner_user_id == owner_user_id
                and interaction_item.contact_id == contact_id
                and interaction_item.deleted_at is None
                and (
                    not outreach_only
                    or interaction_item.direction.value == "outbound"
                    or interaction_item.template_id is not None
                    or interaction_item.kind.value == "referral"
                )
            ):
                self.interactions[item_id] = replace(
                    interaction_item,
                    summary=DELETED_TEXT,
                    deleted_at=redacted_at,
                )
        for item_id, referral in tuple(self.referrals.items()):
            if (
                referral.owner_user_id == owner_user_id
                and referral.contact_id == contact_id
                and referral.context is not None
            ):
                self.referrals[item_id] = replace(
                    referral,
                    context=None,
                    version=referral.version + 1,
                    updated_at=redacted_at,
                )
        for item_id, reminder in tuple(self.reminders.items()):
            if (
                reminder.owner_user_id == owner_user_id
                and reminder.contact_id == contact_id
                and reminder.title != DELETED_TEXT
            ):
                self.reminders[item_id] = replace(
                    reminder,
                    title=DELETED_TEXT,
                    version=reminder.version + 1,
                    updated_at=redacted_at,
                )

    async def add_interaction(self, interaction: NetworkingInteraction) -> None:
        self.interactions[interaction.id] = deepcopy(interaction)

    async def count_interactions(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.contact_id == contact_id
            for item in self.interactions.values()
        )

    async def list_interactions(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingInteraction]:
        if not self._active_contact(owner_user_id, contact_id):
            return []
        values = sorted(
            (
                item
                for item in self.interactions.values()
                if item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and item.deleted_at is None
                and _after_keyset(item.occurred_at, item.id, after, ascending=False)
            ),
            key=lambda item: (item.occurred_at, item.id),
            reverse=True,
        )
        return deepcopy(values[:limit])

    async def get_interaction(
        self, owner_user_id: UUID, interaction_id: UUID
    ) -> NetworkingInteraction | None:
        value = self.interactions.get(interaction_id)
        if (
            value is None
            or value.owner_user_id != owner_user_id
            or value.deleted_at is not None
            or not self._active_contact(owner_user_id, value.contact_id)
        ):
            return None
        return deepcopy(value)

    async def add_referral(self, referral: NetworkingReferral) -> None:
        self.referrals[referral.id] = deepcopy(referral)

    async def count_referrals(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.contact_id == contact_id
            for item in self.referrals.values()
        )

    async def get_referral(
        self,
        owner_user_id: UUID,
        referral_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReferral | None:
        _ = for_update
        value = self.referrals.get(referral_id)
        if (
            value is None
            or value.owner_user_id != owner_user_id
            or not self._active_contact(owner_user_id, value.contact_id)
        ):
            return None
        return deepcopy(value)

    async def list_referrals(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReferral]:
        if not self._active_contact(owner_user_id, contact_id):
            return []
        values = sorted(
            (
                item
                for item in self.referrals.values()
                if item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and _after_keyset(item.updated_at, item.id, after, ascending=False)
            ),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        return deepcopy(values[:limit])

    async def cancel_contact_referrals(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None:
        for item_id, item in tuple(self.referrals.items()):
            if (
                item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and item.status not in {ReferralStatus.CANCELLED, ReferralStatus.DECLINED}
            ):
                self.referrals[item_id] = replace(
                    item,
                    status=ReferralStatus.CANCELLED,
                    version=item.version + 1,
                    updated_at=updated_at,
                )

    async def save_referral(self, referral: NetworkingReferral) -> None:
        self.referrals[referral.id] = deepcopy(referral)

    async def add_template(self, template: NetworkingTemplate) -> None:
        self.templates[template.id] = deepcopy(template)

    async def count_templates(self, owner_user_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.deleted_at is None
            for item in self.templates.values()
        )

    async def get_template(
        self,
        owner_user_id: UUID,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingTemplate | None:
        _ = for_update
        value = self.templates.get(template_id)
        if value is None or value.owner_user_id != owner_user_id or value.deleted_at is not None:
            return None
        return deepcopy(value)

    async def list_templates(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingTemplate]:
        values = sorted(
            (
                item
                for item in self.templates.values()
                if item.owner_user_id == owner_user_id
                and item.deleted_at is None
                and _after_keyset(item.updated_at, item.id, after, ascending=False)
            ),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        return deepcopy(values[:limit])

    async def save_template(self, template: NetworkingTemplate) -> None:
        self.templates[template.id] = deepcopy(template)

    async def add_reminder(self, reminder: NetworkingReminder) -> None:
        self.reminders[reminder.id] = deepcopy(reminder)

    async def count_reminders(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.contact_id == contact_id
            for item in self.reminders.values()
        )

    async def get_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminder | None:
        _ = for_update
        value = self.reminders.get(reminder_id)
        if value is None or value.owner_user_id != owner_user_id:
            return None
        return deepcopy(value)

    async def list_reminders(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReminder]:
        if not self._active_contact(owner_user_id, contact_id):
            return []
        values = sorted(
            (
                item
                for item in self.reminders.values()
                if item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and _after_keyset(item.due_at, item.id, after, ascending=True)
            ),
            key=lambda item: (item.due_at, item.id),
        )
        return deepcopy(values[:limit])

    async def next_active_reminder_at(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> datetime | None:
        return min(
            (
                item.due_at
                for item in self.reminders.values()
                if item.owner_user_id == owner_user_id
                and item.contact_id == contact_id
                and item.status is ReminderStatus.ACTIVE
            ),
            default=None,
        )

    async def save_reminder(self, reminder: NetworkingReminder) -> None:
        self.reminders[reminder.id] = deepcopy(reminder)

    async def cancel_contact_reminders(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None:
        for reminder_id, reminder in tuple(self.reminders.items()):
            if (
                reminder.owner_user_id == owner_user_id
                and reminder.contact_id == contact_id
                and reminder.status is ReminderStatus.ACTIVE
            ):
                self.reminders[reminder_id] = replace(
                    reminder,
                    status=ReminderStatus.CANCELLED,
                    version=reminder.version + 1,
                    updated_at=updated_at,
                )
                await self.cancel_reminder_occurrences(owner_user_id, reminder_id, updated_at)

    async def cancel_reminder_occurrences(
        self, owner_user_id: UUID, reminder_id: UUID, updated_at: datetime
    ) -> None:
        occurrence_ids: set[UUID] = set()
        for occurrence_id, occurrence in tuple(self.occurrences.items()):
            if (
                occurrence.owner_user_id == owner_user_id
                and occurrence.reminder_id == reminder_id
                and occurrence.status
                in {
                    ReminderOccurrenceStatus.SCHEDULED,
                    ReminderOccurrenceStatus.DUE,
                }
            ):
                occurrence_ids.add(occurrence_id)
                self.occurrences[occurrence_id] = replace(
                    occurrence,
                    status=ReminderOccurrenceStatus.CANCELLED,
                    updated_at=updated_at,
                )
        for entry_id, entry in tuple(self.outbox.items()):
            if (
                entry.owner_user_id == owner_user_id
                and entry.occurrence_id in occurrence_ids
                and entry.status in {ReminderOutboxStatus.PENDING, ReminderOutboxStatus.LEASED}
            ):
                self.outbox[entry_id] = replace(
                    entry,
                    status=ReminderOutboxStatus.CANCELLED,
                    lease_token=None,
                    lease_expires_at=None,
                    updated_at=updated_at,
                )

    async def add_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None:
        self.occurrences[occurrence.id] = deepcopy(occurrence)

    async def count_reminder_occurrences(self, owner_user_id: UUID, reminder_id: UUID) -> int:
        return sum(
            item.owner_user_id == owner_user_id and item.reminder_id == reminder_id
            for item in self.occurrences.values()
        )

    async def prune_terminal_reminder_history(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        retain: int,
    ) -> int:
        outbox_by_occurrence = {entry.occurrence_id: entry for entry in self.outbox.values()}
        eligible = sorted(
            (
                occurrence
                for occurrence in self.occurrences.values()
                if occurrence.owner_user_id == owner_user_id
                and occurrence.reminder_id == reminder_id
                and occurrence.status
                in {
                    ReminderOccurrenceStatus.ACKNOWLEDGED,
                    ReminderOccurrenceStatus.CANCELLED,
                }
                and occurrence.id in outbox_by_occurrence
                and outbox_by_occurrence[occurrence.id].status
                in {
                    ReminderOutboxStatus.PROCESSED,
                    ReminderOutboxStatus.CANCELLED,
                }
            ),
            key=lambda item: (item.occurrence_number, item.id),
            reverse=True,
        )
        for occurrence in eligible[retain:]:
            self.occurrences.pop(occurrence.id, None)
            for entry_id, entry in tuple(self.outbox.items()):
                if entry.occurrence_id == occurrence.id:
                    self.outbox.pop(entry_id, None)
        return max(0, len(eligible) - retain)

    async def get_occurrence(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOccurrence | None:
        _ = for_update
        value = self.occurrences.get(occurrence_id)
        if value is None or value.owner_user_id != owner_user_id:
            return None
        return deepcopy(value)

    async def get_latest_reminder_occurrence(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
    ) -> NetworkingReminderOccurrence | None:
        values = [
            value
            for value in self.occurrences.values()
            if value.owner_user_id == owner_user_id and value.reminder_id == reminder_id
        ]
        if not values:
            return None
        return deepcopy(max(values, key=lambda item: (item.occurrence_number, item.id)))

    async def find_occurrence(
        self, owner_user_id: UUID, reminder_id: UUID, occurrence_number: int
    ) -> NetworkingReminderOccurrence | None:
        for value in self.occurrences.values():
            if (
                value.owner_user_id == owner_user_id
                and value.reminder_id == reminder_id
                and value.occurrence_number == occurrence_number
            ):
                return deepcopy(value)
        return None

    async def next_occurrence_number(self, owner_user_id: UUID, reminder_id: UUID) -> int:
        return (
            max(
                (
                    item.occurrence_number
                    for item in self.occurrences.values()
                    if item.owner_user_id == owner_user_id and item.reminder_id == reminder_id
                ),
                default=0,
            )
            + 1
        )

    async def save_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None:
        self.occurrences[occurrence.id] = deepcopy(occurrence)

    async def add_outbox(self, entry: NetworkingReminderOutboxEntry) -> None:
        self.outbox[entry.id] = deepcopy(entry)

    async def get_outbox(
        self,
        entry_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOutboxEntry | None:
        _ = for_update
        value = self.outbox.get(entry_id)
        return deepcopy(value) if value is not None else None

    async def get_occurrence_outbox(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
    ) -> NetworkingReminderOutboxEntry | None:
        for value in self.outbox.values():
            if value.owner_user_id == owner_user_id and value.occurrence_id == occurrence_id:
                return deepcopy(value)
        return None

    async def get_reminder_executions(
        self,
        owner_user_id: UUID,
        reminder_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[NetworkingReminderOccurrence, NetworkingReminderOutboxEntry]]:
        result: dict[UUID, tuple[NetworkingReminderOccurrence, NetworkingReminderOutboxEntry]] = {}
        for reminder_id in reminder_ids:
            occurrence = await self.get_latest_reminder_occurrence(
                owner_user_id,
                reminder_id,
            )
            if occurrence is None:
                continue
            outbox = await self.get_occurrence_outbox(owner_user_id, occurrence.id)
            if outbox is not None:
                result[reminder_id] = (occurrence, outbox)
        return result

    async def list_due_reminders(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[DueReminderView]:
        values: list[DueReminderView] = []
        for occurrence in self.occurrences.values():
            if (
                occurrence.owner_user_id != owner_user_id
                or occurrence.status is not ReminderOccurrenceStatus.DUE
                or not _after_keyset(
                    occurrence.scheduled_for,
                    occurrence.id,
                    after,
                    ascending=True,
                )
            ):
                continue
            reminder = self.reminders.get(occurrence.reminder_id)
            outbox = next(
                (
                    item
                    for item in self.outbox.values()
                    if item.owner_user_id == owner_user_id and item.occurrence_id == occurrence.id
                ),
                None,
            )
            if (
                reminder is None
                or reminder.status is not ReminderStatus.ACTIVE
                or outbox is None
                or outbox.status is not ReminderOutboxStatus.PROCESSED
                or not self._active_contact(owner_user_id, reminder.contact_id)
            ):
                continue
            values.append(
                DueReminderView(
                    reminder=deepcopy(reminder),
                    execution=ReminderExecutionView(
                        occurrence_id=occurrence.id,
                        occurrence_number=occurrence.occurrence_number,
                        scheduled_for=occurrence.scheduled_for,
                        occurrence_status=occurrence.status,
                        attempt_count=outbox.attempt_count,
                        max_attempts=outbox.max_attempts,
                        queue_status=outbox.status,
                        last_error_code=outbox.last_error_code,
                    ),
                )
            )
        values.sort(
            key=lambda item: (
                item.execution.scheduled_for,
                item.execution.occurrence_id,
            )
        )
        return deepcopy(values[:limit])

    async def list_claimable_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]:
        values = sorted(
            (
                item
                for item in self.outbox.values()
                if item.status is ReminderOutboxStatus.PENDING and item.available_at <= now
            ),
            key=lambda item: (item.available_at, item.id),
        )
        return deepcopy(values[:limit])

    async def list_expired_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]:
        values = sorted(
            (
                item
                for item in self.outbox.values()
                if item.status is ReminderOutboxStatus.LEASED
                and item.lease_expires_at is not None
                and item.lease_expires_at <= now
            ),
            key=lambda item: (item.lease_expires_at, item.id),
        )
        return deepcopy(values[:limit])

    async def save_outbox(self, entry: NetworkingReminderOutboxEntry) -> None:
        self.outbox[entry.id] = deepcopy(entry)

    async def add_idempotency(self, record: NetworkingIdempotencyRecord) -> None:
        key = (record.owner_user_id, record.idempotency_key)
        if key in self.idempotency:
            raise NetworkingIdempotencyConflict
        self.idempotency[key] = deepcopy(record)

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> NetworkingIdempotencyRecord | None:
        value = self.idempotency.get((owner_user_id, idempotency_key))
        return deepcopy(value) if value is not None else None

    async def add_audit(self, event: NetworkingAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def commit(self) -> None:
        return None

    def _active_contact(self, owner_user_id: UUID, contact_id: UUID) -> bool:
        contact = self.contacts.get(contact_id)
        return (
            contact is not None
            and contact.owner_user_id == owner_user_id
            and contact.deleted_at is None
        )

    def _allows_outreach(self, owner_user_id: UUID, contact_id: UUID) -> bool:
        values = {
            ConsentPurpose.COLLECTION: False,
            ConsentPurpose.STORAGE: False,
            ConsentPurpose.OUTREACH: False,
        }
        events = sorted(
            (
                item
                for item in self.consent_events
                if item.owner_user_id == owner_user_id and item.contact_id == contact_id
            ),
            key=lambda item: item.sequence,
        )
        for event in events:
            values[event.purpose] = event.action is ConsentAction.GRANTED
        return all(values.values())


def _after(updated_at: datetime, record_id: UUID, cursor: NetworkingCursor | None) -> bool:
    if cursor is None:
        return True
    return (updated_at, record_id) < (cursor.updated_at, cursor.record_id)


def _after_keyset(
    position: datetime | int,
    record_id: UUID,
    cursor: NetworkingKeysetCursor | None,
    *,
    ascending: bool,
) -> bool:
    if cursor is None:
        return True
    current = (cast(Any, position), record_id)
    anchor = (cast(Any, cursor.position), cursor.record_id)
    return current > anchor if ascending else current < anchor


def _uuids() -> Iterator[UUID]:
    counter = 0xA00
    while True:
        counter += 1
        yield UUID(f"00000000-0000-4000-8000-{counter:012x}")
