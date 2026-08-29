"""Service tests for consent-based networking and local reminder durability."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest

from networking_memory import (
    APPLICATION_ID,
    NOW,
    OTHER_ID,
    OWNER_ID,
    FixedClock,
    MemoryNetworking,
    StaticApplicationProvider,
    UuidFactory,
)
from rezumi.modules.networking.application import (
    ChangeContactConsent,
    ContactConsentState,
    ContactFilter,
    CreateContact,
    CreateContactNote,
    CreateOrganization,
    CreateReferral,
    CreateReminder,
    CreateTemplate,
    NetworkingCursor,
    NetworkingPolicy,
    NetworkingService,
    OrganizationFilter,
    RecordInteraction,
    ReminderResolutionAction,
    RequestContext,
    ResolveReminder,
    UpdateContact,
    UpdateReferral,
    UpdateReminder,
    UpdateTemplate,
)
from rezumi.modules.networking.domain import (
    DELETED_TEXT,
    NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS,
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NETWORKING_CONTACT_DELETION_POLICY_VERSION,
    ConsentAction,
    ConsentPurpose,
    ContactReferralState,
    InteractionDeliveryState,
    InteractionDirection,
    InteractionKind,
    NetworkingAuditAction,
    NetworkingConflict,
    NetworkingConsentRequired,
    NetworkingContact,
    NetworkingIdempotencyConflict,
    NetworkingLeaseConflict,
    NetworkingNotFound,
    NetworkingQuotaExceeded,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingReminderOccurrence,
    NetworkingReminderOutboxEntry,
    NetworkingValidationError,
    NetworkingVersionConflict,
    ReferralStatus,
    RelationshipStage,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
    ReminderStatus,
    TemplateKind,
)
from rezumi.modules.networking.infrastructure.models import (
    NetworkingConsentEventModel,
    NetworkingContactModel,
    NetworkingContactNoteModel,
    NetworkingInteractionModel,
    NetworkingReminderModel,
    NetworkingReminderOccurrenceModel,
    NetworkingReminderOutboxModel,
)


def _context(owner_id: UUID = OWNER_ID) -> RequestContext:
    return RequestContext(
        actor_user_id=owner_id,
        request_id="req-phase9-networking",
        trace_id="a" * 32,
    )


def _service(
    state: MemoryNetworking,
    *,
    policy: NetworkingPolicy | None = None,
) -> NetworkingService:
    return NetworkingService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        applications=StaticApplicationProvider(),
        policy=policy,
    )


class LockTracingMemory(MemoryNetworking):
    """Record only row locks so tests can enforce the global lock order."""

    def __init__(self) -> None:
        super().__init__()
        self.row_locks: list[tuple[str, UUID]] = []

    async def get_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingContact | None:
        if for_update:
            self.row_locks.append(("contact", contact_id))
        return await super().get_contact(
            owner_user_id,
            contact_id,
            for_update=for_update,
            include_deleted=include_deleted,
        )

    async def get_referral(
        self,
        owner_user_id: UUID,
        referral_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReferral | None:
        if for_update:
            self.row_locks.append(("referral", referral_id))
        return await super().get_referral(
            owner_user_id,
            referral_id,
            for_update=for_update,
        )

    async def get_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminder | None:
        if for_update:
            self.row_locks.append(("reminder", reminder_id))
        return await super().get_reminder(
            owner_user_id,
            reminder_id,
            for_update=for_update,
        )

    async def get_occurrence(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOccurrence | None:
        if for_update:
            self.row_locks.append(("occurrence", occurrence_id))
        return await super().get_occurrence(
            owner_user_id,
            occurrence_id,
            for_update=for_update,
        )

    async def get_outbox(
        self,
        entry_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOutboxEntry | None:
        if for_update:
            self.row_locks.append(("outbox", entry_id))
        return await super().get_outbox(entry_id, for_update=for_update)


async def _create_contact(
    service: NetworkingService,
    *,
    name: str = "Alex Example",
    key: str = "contact-create-0001",
    outreach: bool = True,
    organization_id: UUID | None = None,
):
    return await service.create_contact(
        OWNER_ID,
        CreateContact(
            name=name,
            organization_id=organization_id,
            role="Engineering leader",
            email=f"{name.split()[0].casefold()}@example.test",
            tags=("Product", "Mentor"),
            collection_attested=True,
            storage_attested=True,
            outreach_attested=outreach,
            consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        idempotency_key=key,
        context=_context(),
    )


def test_persistence_constraints_enforce_redaction_and_reminder_parent_chain() -> None:
    note_constraints = {
        constraint.name for constraint in NetworkingContactNoteModel.__table__.constraints
    }
    interaction_constraints = {
        constraint.name for constraint in NetworkingInteractionModel.__table__.constraints
    }
    reminder_constraints = {
        constraint.name for constraint in NetworkingReminderModel.__table__.constraints
    }
    occurrence_constraints = {
        constraint.name for constraint in NetworkingReminderOccurrenceModel.__table__.constraints
    }
    outbox_constraints = {
        constraint.name for constraint in NetworkingReminderOutboxModel.__table__.constraints
    }
    contact_constraints = {
        constraint.name for constraint in NetworkingContactModel.__table__.constraints
    }
    consent_constraints = {
        constraint.name for constraint in NetworkingConsentEventModel.__table__.constraints
    }

    assert "ck_networking_contact_notes_networking_note_deleted_redacted" in note_constraints
    assert (
        "ck_networking_interactions_networking_interaction_deleted_redacted"
        in interaction_constraints
    )
    assert "uq_networking_reminders_owner_id_contact" in reminder_constraints
    assert "fk_networking_occurrences_owner_reminder_contact" in occurrence_constraints
    assert "ck_networking_contacts_networking_contact_deleted_redacted" in contact_constraints
    assert (
        "ck_networking_consent_events_networking_consent_policy_version_valid"
        in consent_constraints
    )
    assert (
        "ck_networking_reminder_occurrences_networking_occurrence_trace_id_valid"
        in occurrence_constraints
    )
    assert "ck_networking_reminder_outbox_networking_outbox_trace_id_valid" in outbox_constraints


@pytest.mark.asyncio
async def test_contact_creation_requires_explicit_collection_and_storage_attestation() -> None:
    state = MemoryNetworking()
    service = _service(state)

    with pytest.raises(NetworkingConsentRequired):
        await service.create_contact(
            OWNER_ID,
            CreateContact(
                name="No Consent",
                collection_attested=True,
                storage_attested=False,
                consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            idempotency_key="missing-consent-01",
            context=_context(),
        )

    assert not state.contacts
    assert not state.consent_events


@pytest.mark.asyncio
async def test_consent_policy_versions_are_server_owned_and_reject_embedded_pii() -> None:
    state = MemoryNetworking()
    service = _service(state)
    smuggled_pii = "private.person@example.test"

    with pytest.raises(NetworkingValidationError, match="policy version"):
        await service.create_contact(
            OWNER_ID,
            CreateContact(
                name="Private Person",
                collection_attested=True,
                storage_attested=True,
                consent_policy_version=smuggled_pii,
            ),
            idempotency_key="invalid-policy-create",
            context=_context(),
        )

    created = await _create_contact(service)
    event_count = len(state.consent_events)
    with pytest.raises(NetworkingValidationError, match="policy version"):
        await service.withdraw_consent(
            OWNER_ID,
            created.contact.id,
            ChangeContactConsent(
                purpose=ConsentPurpose.OUTREACH,
                policy_version=smuggled_pii,
            ),
            expected_version=created.contact.version,
            idempotency_key="invalid-policy-withdraw",
            context=_context(),
        )

    assert len(state.consent_events) == event_count
    assert smuggled_pii not in repr(state.consent_events)


@pytest.mark.asyncio
async def test_contact_and_child_reads_fail_closed_across_owners() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    note = await service.create_note(
        OWNER_ID,
        created.contact.id,
        CreateContactNote(body="Private relationship context."),
        idempotency_key="note-create-0001",
        context=_context(),
    )

    with pytest.raises(NetworkingNotFound):
        await service.get_contact(OTHER_ID, created.contact.id)
    with pytest.raises(NetworkingNotFound):
        await service.list_notes(OTHER_ID, created.contact.id)
    assert await state.get_note(OTHER_ID, note.id) is None
    assert (await service.list_contacts(OTHER_ID)).data == ()


@pytest.mark.asyncio
async def test_outreach_is_blocked_until_granted_and_interactions_are_record_only() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service, outreach=False)

    inbound = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.MESSAGE,
            direction=InteractionDirection.INBOUND,
            occurred_at=NOW,
            summary="They sent an update.",
        ),
        expected_contact_version=1,
        idempotency_key="interaction-in-01",
        context=_context(),
    )
    assert inbound.delivery_state is InteractionDeliveryState.RECORDED_ONLY

    with pytest.raises(NetworkingConsentRequired):
        await service.record_interaction(
            OWNER_ID,
            created.contact.id,
            RecordInteraction(
                kind=InteractionKind.EMAIL,
                direction=InteractionDirection.OUTBOUND,
                occurred_at=NOW,
                summary="I sent a manual email.",
            ),
            expected_contact_version=2,
            idempotency_key="interaction-out-01",
            context=_context(),
        )

    granted = await service.grant_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=ConsentPurpose.OUTREACH,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=2,
        idempotency_key="consent-grant-001",
        context=_context(),
    )
    assert granted.consent.allows_outreach
    outbound = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.EMAIL,
            direction=InteractionDirection.OUTBOUND,
            occurred_at=NOW,
            summary="I sent a manual email.",
        ),
        expected_contact_version=3,
        idempotency_key="interaction-out-02",
        context=_context(),
    )
    assert outbound.delivery_state.value == "recorded_only"
    assert not any("send" in name or "deliver" in name for name in dir(service))


@pytest.mark.asyncio
async def test_withdrawal_cancels_referrals_reminders_and_active_leases_atomically() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    note = await service.create_note(
        OWNER_ID,
        created.contact.id,
        CreateContactNote(body="Private context that must be erased."),
        idempotency_key="withdraw-note-001",
        context=_context(),
    )
    interaction = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.MEETING,
            direction=InteractionDirection.MUTUAL,
            occurred_at=NOW,
            summary="Private stored mutual interaction.",
        ),
        expected_contact_version=created.contact.version,
        idempotency_key="withdraw-interaction",
        context=_context(),
    )
    after_mutual = await service.get_contact(OWNER_ID, created.contact.id)
    outbound = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.EMAIL,
            direction=InteractionDirection.OUTBOUND,
            occurred_at=NOW,
            summary="Private outbound interaction that must be erased.",
        ),
        expected_contact_version=after_mutual.contact.version,
        idempotency_key="withdraw-outbound-interaction",
        context=_context(),
    )
    after_interaction = await service.get_contact(OWNER_ID, created.contact.id)
    referral = await service.create_referral(
        OWNER_ID,
        created.contact.id,
        CreateReferral(
            application_id=APPLICATION_ID,
            status=ReferralStatus.REQUESTED,
            context="User will ask manually.",
        ),
        expected_contact_version=after_interaction.contact.version,
        idempotency_key="referral-create-01",
        context=_context(),
    )
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(title="Follow up manually", due_at=NOW),
        idempotency_key="reminder-create-01",
        context=_context(),
    )
    leased = await service.claim_due_reminders(now=NOW, lease_seconds=30)
    assert len(leased) == 1
    current = await service.get_contact(OWNER_ID, created.contact.id)

    withdrawn = await service.withdraw_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=ConsentPurpose.OUTREACH,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=current.contact.version,
        idempotency_key="unit-test-00000004",
        context=_context(),
    )

    assert not withdrawn.consent.allows_outreach
    assert state.notes[note.id].body == "Private context that must be erased."
    assert state.notes[note.id].deleted_at is None
    assert state.interactions[interaction.id].summary == "Private stored mutual interaction."
    assert state.interactions[interaction.id].deleted_at is None
    assert state.interactions[outbound.id].summary == DELETED_TEXT
    assert state.interactions[outbound.id].deleted_at == NOW
    assert state.referrals[referral.id].status is ReferralStatus.CANCELLED
    assert state.referrals[referral.id].context is None
    assert state.reminders[reminder.id].status is ReminderStatus.CANCELLED
    assert state.reminders[reminder.id].title == DELETED_TEXT
    assert state.outbox[leased[0].id].status is ReminderOutboxStatus.CANCELLED
    assert state.outbox[leased[0].id].lease_token is None
    with pytest.raises(NetworkingConsentRequired):
        await service.create_referral(
            OWNER_ID,
            created.contact.id,
            CreateReferral(application_id=APPLICATION_ID),
            expected_contact_version=withdrawn.contact.version,
            idempotency_key="referral-after-no",
            context=_context(),
        )
    referral_version = state.referrals[referral.id].version
    redacted_referral = await service.update_referral(
        OWNER_ID,
        referral.id,
        UpdateReferral(
            status=ReferralStatus.CANCELLED,
            context="This must never be retained after withdrawal.",
        ),
        expected_version=referral_version,
        idempotency_key="terminal-referral-after-withdrawal",
        context=_context(),
    )
    assert redacted_referral.context is None
    assert (
        await service.update_referral(
            OWNER_ID,
            referral.id,
            UpdateReferral(
                status=ReferralStatus.CANCELLED,
                context="This must never be retained after withdrawal.",
            ),
            expected_version=referral_version,
            idempotency_key="terminal-referral-after-withdrawal",
            context=_context(),
        )
        == redacted_referral
    )
    reminder_version = state.reminders[reminder.id].version
    redacted_reminder = await service.update_reminder(
        OWNER_ID,
        reminder.id,
        UpdateReminder(
            title="This must never be retained after withdrawal.",
            status=ReminderStatus.CANCELLED,
        ),
        expected_version=reminder_version,
        idempotency_key="terminal-reminder-after-withdrawal",
        context=_context(),
    )
    assert redacted_reminder.title == DELETED_TEXT
    with pytest.raises(NetworkingConsentRequired):
        await service.update_reminder(
            OWNER_ID,
            reminder.id,
            UpdateReminder(status=ReminderStatus.ACTIVE),
            expected_version=redacted_reminder.version,
            idempotency_key="reactivate-after-withdrawal",
            context=_context(),
        )
    with pytest.raises(NetworkingNotFound):
        await service.update_referral(
            OTHER_ID,
            referral.id,
            UpdateReferral(status=ReferralStatus.CANCELLED),
            expected_version=redacted_referral.version,
            idempotency_key="cross-owner-terminal-referral",
            context=_context(OTHER_ID),
        )
    with pytest.raises(NetworkingNotFound):
        await service.update_reminder(
            OTHER_ID,
            reminder.id,
            UpdateReminder(status=ReminderStatus.CANCELLED),
            expected_version=redacted_reminder.version,
            idempotency_key="cross-owner-terminal-reminder",
            context=_context(OTHER_ID),
        )
    assert await service.claim_due_reminders(now=NOW + timedelta(hours=1), lease_seconds=30) == ()


@pytest.mark.parametrize("purpose", [ConsentPurpose.COLLECTION, ConsentPurpose.STORAGE])
@pytest.mark.asyncio
async def test_collection_or_storage_withdrawal_irreversibly_redacts_contact_tombstone(
    purpose: ConsentPurpose,
) -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await service.create_contact(
        OWNER_ID,
        CreateContact(
            name="Sensitive Contact",
            role="Private role",
            email="sensitive@example.test",
            phone="+1 555 0100",
            profile_url="https://example.test/private-profile",
            location="Private location",
            tags=("private-tag",),
            collection_attested=True,
            storage_attested=True,
            outreach_attested=True,
            consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        idempotency_key=f"destructive-create-{purpose.value}",
        context=_context(),
    )
    note = await service.create_note(
        OWNER_ID,
        created.contact.id,
        CreateContactNote(body="Private locally stored note."),
        idempotency_key=f"destructive-note-{purpose.value}",
        context=_context(),
    )
    interaction = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.CALL,
            direction=InteractionDirection.INBOUND,
            occurred_at=NOW,
            summary="Private inbound interaction.",
        ),
        expected_contact_version=created.contact.version,
        idempotency_key=f"destructive-interaction-{purpose.value}",
        context=_context(),
    )
    current = await service.get_contact(OWNER_ID, created.contact.id)
    key = f"destructive-withdraw-{purpose.value}"

    withdrawn = await service.withdraw_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=purpose,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=current.contact.version,
        idempotency_key=key,
        context=_context(),
    )

    tombstone = withdrawn.contact
    assert tombstone.deleted_at == NOW
    assert tombstone.organization_id is None
    assert tombstone.name == DELETED_TEXT
    assert tombstone.role is None
    assert tombstone.email is None
    assert tombstone.phone is None
    assert tombstone.profile_url is None
    assert tombstone.location is None
    assert tombstone.tags == ()
    assert tombstone.normalized_search == DELETED_TEXT
    assert tombstone.last_contact_at is None
    assert tombstone.next_contact_at is None
    assert tombstone.relationship_stage is RelationshipStage.ARCHIVED
    assert withdrawn.consent == ContactConsentState(False, False, False)
    assert state.notes[note.id].body == DELETED_TEXT
    assert state.notes[note.id].deleted_at == NOW
    assert state.interactions[interaction.id].summary == DELETED_TEXT
    assert state.interactions[interaction.id].deleted_at == NOW

    replay = await service.withdraw_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=purpose,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=current.contact.version,
        idempotency_key=key,
        context=_context(),
    )
    assert replay == withdrawn
    for owner_id in (OWNER_ID, OTHER_ID):
        with pytest.raises(NetworkingNotFound):
            await service.get_contact(owner_id, created.contact.id)
    with pytest.raises(NetworkingNotFound):
        await service.grant_consent(
            OWNER_ID,
            created.contact.id,
            ChangeContactConsent(
                purpose=purpose,
                policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            expected_version=tombstone.version,
            idempotency_key=f"restore-consent-{purpose.value}",
            context=_context(),
        )
    with pytest.raises(NetworkingNotFound):
        await service.update_contact(
            OWNER_ID,
            created.contact.id,
            UpdateContact(name="Restored private contact"),
            expected_version=tombstone.version,
            idempotency_key=f"restore-contact-{purpose.value}",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_create_idempotency_replays_and_rejects_changed_payload() -> None:
    state = MemoryNetworking()
    service = _service(state)
    first = await _create_contact(service)
    second = await _create_contact(service)

    assert second == first
    assert len(state.contacts) == 1
    assert len(state.consent_events) == 3
    with pytest.raises(NetworkingIdempotencyConflict):
        await _create_contact(service, name="Different Person")


@pytest.mark.asyncio
async def test_owner_and_contact_quotas_replay_safely_and_never_block_withdrawal_or_deletion() -> (
    None
):
    state = MemoryNetworking()
    service = _service(
        state,
        policy=NetworkingPolicy(
            max_organizations_per_owner=1,
            max_contacts_per_owner=1,
            max_templates_per_owner=1,
            max_notes_per_contact=1,
            max_interactions_per_contact=1,
            max_referrals_per_contact=1,
            max_reminders_per_contact=1,
            max_consent_events_per_contact=3,
            max_occurrences_per_reminder=3,
            retained_terminal_occurrences_per_reminder=1,
        ),
    )
    contact = await _create_contact(service)

    organization = await service.create_organization(
        OWNER_ID,
        CreateOrganization(name="One organization"),
        idempotency_key="quota-organization-one",
        context=_context(),
    )
    assert (
        await service.create_organization(
            OWNER_ID,
            CreateOrganization(name="One organization"),
            idempotency_key="quota-organization-one",
            context=_context(),
        )
        == organization
    )
    with pytest.raises(NetworkingQuotaExceeded):
        await service.create_organization(
            OWNER_ID,
            CreateOrganization(name="Second organization"),
            idempotency_key="quota-organization-two",
            context=_context(),
        )
    with pytest.raises(NetworkingQuotaExceeded):
        await _create_contact(
            service,
            name="Second Contact",
            key="quota-contact-two",
        )

    await service.create_template(
        OWNER_ID,
        CreateTemplate(
            kind=TemplateKind.FOLLOW_UP,
            name="One template",
            body="User-reviewed local draft.",
            user_reviewed=True,
        ),
        idempotency_key="quota-template-one",
        context=_context(),
    )
    with pytest.raises(NetworkingQuotaExceeded):
        await service.create_template(
            OWNER_ID,
            CreateTemplate(
                kind=TemplateKind.THANK_YOU,
                name="Second template",
                body="Another user-reviewed local draft.",
                user_reviewed=True,
            ),
            idempotency_key="quota-template-two",
            context=_context(),
        )

    note = await service.create_note(
        OWNER_ID,
        contact.contact.id,
        CreateContactNote(body="One private note."),
        idempotency_key="quota-note-one",
        context=_context(),
    )
    assert (
        await service.create_note(
            OWNER_ID,
            contact.contact.id,
            CreateContactNote(body="One private note."),
            idempotency_key="quota-note-one",
            context=_context(),
        )
        == note
    )
    with pytest.raises(NetworkingQuotaExceeded):
        await service.create_note(
            OWNER_ID,
            contact.contact.id,
            CreateContactNote(body="Second private note."),
            idempotency_key="quota-note-two",
            context=_context(),
        )

    interaction = await service.record_interaction(
        OWNER_ID,
        contact.contact.id,
        RecordInteraction(
            kind=InteractionKind.CALL,
            direction=InteractionDirection.INBOUND,
            occurred_at=NOW,
            summary="One stored interaction.",
        ),
        expected_contact_version=contact.contact.version,
        idempotency_key="quota-interaction-one",
        context=_context(),
    )
    current = await service.get_contact(OWNER_ID, contact.contact.id)
    with pytest.raises(NetworkingQuotaExceeded):
        await service.record_interaction(
            OWNER_ID,
            contact.contact.id,
            RecordInteraction(
                kind=InteractionKind.MEETING,
                direction=InteractionDirection.MUTUAL,
                occurred_at=NOW,
                summary="Second stored interaction.",
            ),
            expected_contact_version=current.contact.version,
            idempotency_key="quota-interaction-two",
            context=_context(),
        )
    assert state.interactions[interaction.id].summary == "One stored interaction."

    referral = await service.create_referral(
        OWNER_ID,
        contact.contact.id,
        CreateReferral(application_id=APPLICATION_ID),
        expected_contact_version=current.contact.version,
        idempotency_key="quota-referral-one",
        context=_context(),
    )
    current = await service.get_contact(OWNER_ID, contact.contact.id)
    with pytest.raises(NetworkingQuotaExceeded):
        await service.create_referral(
            OWNER_ID,
            contact.contact.id,
            CreateReferral(application_id=APPLICATION_ID),
            expected_contact_version=current.contact.version,
            idempotency_key="quota-referral-two",
            context=_context(),
        )
    assert state.referrals[referral.id].contact_id == contact.contact.id

    reminder = await service.create_reminder(
        OWNER_ID,
        contact.contact.id,
        CreateReminder(title="One local reminder", due_at=NOW),
        idempotency_key="quota-reminder-one",
        context=_context(),
    )
    with pytest.raises(NetworkingQuotaExceeded):
        await service.create_reminder(
            OWNER_ID,
            contact.contact.id,
            CreateReminder(title="Second local reminder", due_at=NOW),
            idempotency_key="quota-reminder-two",
            context=_context(),
        )
    assert state.reminders[reminder.id].contact_id == contact.contact.id
    assert all(item.trace_id == "a" * 32 for item in state.occurrences.values())
    assert all(item.trace_id == "a" * 32 for item in state.outbox.values())

    current = await service.get_contact(OWNER_ID, contact.contact.id)
    withdrawn = await service.withdraw_consent(
        OWNER_ID,
        contact.contact.id,
        ChangeContactConsent(
            purpose=ConsentPurpose.OUTREACH,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=current.contact.version,
        idempotency_key="quota-withdraw-outreach",
        context=_context(),
    )
    assert withdrawn.consent.outreach is False
    assert len(state.consent_events) == 4
    with pytest.raises(NetworkingQuotaExceeded):
        await service.grant_consent(
            OWNER_ID,
            contact.contact.id,
            ChangeContactConsent(
                purpose=ConsentPurpose.OUTREACH,
                policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            expected_version=withdrawn.contact.version,
            idempotency_key="quota-regrant-outreach",
            context=_context(),
        )
    deleted = await service.delete_contact(
        OWNER_ID,
        contact.contact.id,
        expected_version=withdrawn.contact.version,
        idempotency_key="quota-contact-delete",
        context=_context(),
    )
    assert deleted.deleted_at == NOW


@pytest.mark.asyncio
async def test_child_mutations_and_worker_claims_lock_contact_before_child_rows() -> None:
    state = LockTracingMemory()
    service = _service(state)
    created = await _create_contact(service)

    state.row_locks.clear()
    await service.create_note(
        OWNER_ID,
        created.contact.id,
        CreateContactNote(body="Lock-order note"),
        idempotency_key="lock-order-note",
        context=_context(),
    )
    assert state.row_locks == [("contact", created.contact.id)]

    referral = await service.create_referral(
        OWNER_ID,
        created.contact.id,
        CreateReferral(
            application_id=APPLICATION_ID,
            context="Lock-order referral",
        ),
        expected_contact_version=created.contact.version,
        idempotency_key="lock-order-referral",
        context=_context(),
    )
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(title="Lock-order reminder", due_at=NOW),
        idempotency_key="lock-order-reminder",
        context=_context(),
    )

    state.row_locks.clear()
    await service.update_referral(
        OWNER_ID,
        referral.id,
        UpdateReferral(status=ReferralStatus.CANCELLED),
        expected_version=referral.version,
        idempotency_key="lock-order-referral-update",
        context=_context(),
    )
    assert [kind for kind, _ in state.row_locks] == ["contact", "referral"]

    state.row_locks.clear()
    claimed = await service.claim_due_reminders(now=NOW, lease_seconds=30)
    assert len(claimed) == 1
    assert [kind for kind, _ in state.row_locks] == [
        "contact",
        "reminder",
        "occurrence",
        "outbox",
    ]

    state.row_locks.clear()
    await service.update_reminder(
        OWNER_ID,
        reminder.id,
        UpdateReminder(status=ReminderStatus.CANCELLED),
        expected_version=reminder.version,
        idempotency_key="lock-order-reminder-update",
        context=_context(),
    )
    assert [kind for kind, _ in state.row_locks] == ["contact", "reminder"]


@pytest.mark.asyncio
async def test_optimistic_concurrency_rejects_stale_contact_and_template_updates() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    updated = await service.update_contact(
        OWNER_ID,
        created.contact.id,
        UpdateContact(relationship_stage=RelationshipStage.WARM),
        expected_version=1,
        idempotency_key="contact-update-001",
        context=_context(),
    )
    assert updated.contact.version == 2

    with pytest.raises(NetworkingVersionConflict):
        await service.update_contact(
            OWNER_ID,
            created.contact.id,
            UpdateContact(relationship_stage=RelationshipStage.ACTIVE),
            expected_version=1,
            idempotency_key="contact-update-002",
            context=_context(),
        )

    template = await service.create_template(
        OWNER_ID,
        CreateTemplate(
            kind=TemplateKind.FOLLOW_UP,
            name="Follow up",
            body="Hello — this is text for me to review and copy.",
            user_reviewed=True,
        ),
        idempotency_key="template-create01",
        context=_context(),
    )
    with pytest.raises(NetworkingValidationError):
        await service.update_template(
            OWNER_ID,
            template.id,
            UpdateTemplate(body="Changed without review", user_reviewed=False),
            expected_version=1,
            idempotency_key="template-update01",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_search_tags_consent_filter_and_keyset_pagination_are_normalized() -> None:
    state = MemoryNetworking()
    service = _service(state)
    await _create_contact(
        service,
        name="Álex García",
        key="contact-create-1001",
        outreach=True,
    )
    await _create_contact(
        service,
        name="Jordan Example",
        key="contact-create-1002",
        outreach=False,
    )
    await _create_contact(
        service,
        name="Priya Example",
        key="contact-create-1003",
        outreach=True,
    )

    first = await service.list_contacts(OWNER_ID, limit=2)
    second = await service.list_contacts(OWNER_ID, limit=2, cursor=first.page.next_cursor)
    assert first.page.has_more
    assert len(first.data) == 2
    assert len(second.data) == 1
    assert {view.contact.id for view in first.data}.isdisjoint(
        {view.contact.id for view in second.data}
    )
    searched = await service.list_contacts(
        OWNER_ID, filter_by=ContactFilter(query="ÁLEX", tag="PRODUCT")
    )
    assert [view.contact.name for view in searched.data] == ["Álex García"]
    allowed = await service.list_contacts(OWNER_ID, filter_by=ContactFilter(outreach_consent=True))
    assert len(allowed.data) == 2

    with pytest.raises(NetworkingValidationError):
        NetworkingCursor.decode("é", expected_scope="networking:v2:test")


@pytest.mark.asyncio
async def test_top_level_cursors_are_bound_to_owner_collection_and_normalized_filters() -> None:
    state = MemoryNetworking()
    service = _service(state)
    organizations = []
    for index in range(3):
        organizations.append(
            await service.create_organization(
                OWNER_ID,
                CreateOrganization(
                    name=f"Acme Partner {index}",
                    tags=("Partner",),
                ),
                idempotency_key=f"cursor-organization-{index}",
                context=_context(),
            )
        )

    organization_filter = OrganizationFilter(query=" ACME ", tag=" PARTNER ")
    organization_first = await service.list_organizations(
        OWNER_ID,
        filter_by=organization_filter,
        limit=1,
    )
    organization_cursor = organization_first.page.next_cursor
    assert organization_cursor is not None
    assert organization_cursor.isascii()
    organization_second = await service.list_organizations(
        OWNER_ID,
        filter_by=OrganizationFilter(query="acme", tag="partner"),
        cursor=organization_cursor,
        limit=1,
    )
    assert organization_second.data

    with pytest.raises(NetworkingValidationError):
        await service.list_organizations(
            OTHER_ID,
            filter_by=organization_filter,
            cursor=organization_cursor,
            limit=1,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_organizations(
            OWNER_ID,
            filter_by=OrganizationFilter(query="different", tag="partner"),
            cursor=organization_cursor,
            limit=1,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_organizations(
            OWNER_ID,
            filter_by=OrganizationFilter(query="acme", tag="different"),
            cursor=organization_cursor,
            limit=1,
        )

    organization_id = organizations[0].id
    for index in range(3):
        await _create_contact(
            service,
            name=f"Scoped Example {index}",
            key=f"cursor-contact-{index}",
            organization_id=organization_id,
        )
    contact_filter = ContactFilter(
        query=" SCOPED ",
        organization_id=organization_id,
        relationship_stage=RelationshipStage.NEW,
        referral_state=ContactReferralState.NONE,
        tag=" PRODUCT ",
        outreach_consent=True,
    )
    contact_first = await service.list_contacts(
        OWNER_ID,
        filter_by=contact_filter,
        limit=1,
    )
    contact_cursor = contact_first.page.next_cursor
    assert contact_cursor is not None
    assert contact_cursor.isascii()
    contact_second = await service.list_contacts(
        OWNER_ID,
        filter_by=ContactFilter(
            query="scoped",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.NONE,
            tag="product",
            outreach_consent=True,
        ),
        cursor=contact_cursor,
        limit=1,
    )
    assert contact_second.data

    mismatched_filters = (
        ContactFilter(
            query="different",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.NONE,
            tag="product",
            outreach_consent=True,
        ),
        ContactFilter(
            query="scoped",
            organization_id=None,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.NONE,
            tag="product",
            outreach_consent=True,
        ),
        ContactFilter(
            query="scoped",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.WARM,
            referral_state=ContactReferralState.NONE,
            tag="product",
            outreach_consent=True,
        ),
        ContactFilter(
            query="scoped",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.CONSIDERING,
            tag="product",
            outreach_consent=True,
        ),
        ContactFilter(
            query="scoped",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.NONE,
            tag="mentor",
            outreach_consent=True,
        ),
        ContactFilter(
            query="scoped",
            organization_id=organization_id,
            relationship_stage=RelationshipStage.NEW,
            referral_state=ContactReferralState.NONE,
            tag="product",
            outreach_consent=False,
        ),
    )
    for mismatched_filter in mismatched_filters:
        with pytest.raises(NetworkingValidationError):
            await service.list_contacts(
                OWNER_ID,
                filter_by=mismatched_filter,
                cursor=contact_cursor,
                limit=1,
            )

    with pytest.raises(NetworkingValidationError):
        await service.list_contacts(
            OTHER_ID,
            filter_by=contact_filter,
            cursor=contact_cursor,
            limit=1,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_contacts(
            OWNER_ID,
            filter_by=ContactFilter(),
            cursor=organization_cursor,
            limit=1,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_organizations(
            OWNER_ID,
            filter_by=OrganizationFilter(),
            cursor=contact_cursor,
            limit=1,
        )


@pytest.mark.asyncio
async def test_contact_deletion_redacts_content_and_preserves_safe_audit_tombstone() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    note = await service.create_note(
        OWNER_ID,
        created.contact.id,
        CreateContactNote(body="Sensitive note"),
        idempotency_key="note-delete-test1",
        context=_context(),
    )
    interaction = await service.record_interaction(
        OWNER_ID,
        created.contact.id,
        RecordInteraction(
            kind=InteractionKind.MEETING,
            direction=InteractionDirection.MUTUAL,
            occurred_at=NOW,
            summary="Sensitive meeting context",
        ),
        expected_contact_version=1,
        idempotency_key="interaction-delete",
        context=_context(),
    )
    after_interaction = await service.get_contact(OWNER_ID, created.contact.id)
    referral = await service.create_referral(
        OWNER_ID,
        created.contact.id,
        CreateReferral(
            application_id=APPLICATION_ID,
            status=ReferralStatus.REQUESTED,
            context="Sensitive referral context",
        ),
        expected_contact_version=after_interaction.contact.version,
        idempotency_key="referral-delete-test",
        context=_context(),
    )
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(
            title="Sensitive reminder title",
            due_at=NOW + timedelta(days=1),
        ),
        idempotency_key="reminder-delete-test",
        context=_context(),
    )
    current = await service.get_contact(OWNER_ID, created.contact.id)
    deleted = await service.delete_contact(
        OWNER_ID,
        created.contact.id,
        expected_version=current.contact.version,
        idempotency_key="contact-delete-001",
        context=_context(),
    )

    assert deleted.name == DELETED_TEXT
    assert deleted.deleted_at == NOW
    assert state.notes[note.id].body == DELETED_TEXT
    assert state.interactions[interaction.id].summary == DELETED_TEXT
    assert state.referrals[referral.id].context is None
    assert state.referrals[referral.id].status is ReferralStatus.CANCELLED
    retained_policies = {
        event.policy_version
        for event in state.consent_events
        if event.contact_id == created.contact.id
    }
    assert NETWORKING_CONTACT_DELETION_POLICY_VERSION in retained_policies
    assert retained_policies <= set(NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS)
    assert state.reminders[reminder.id].title == DELETED_TEXT
    assert state.reminders[reminder.id].status is ReminderStatus.CANCELLED
    assert all(
        set(event.metadata)
        <= {
            "purpose",
            "stage_from",
            "stage_to",
            "status_from",
            "status_to",
            "version",
            "organization_id",
            "contact_id",
            "application_id",
            "template_id",
            "reminder_id",
            "occurrence_id",
            "occurrence_number",
            "attempt_count",
            "outbox_status",
            "recurring",
        }
        for event in state.audits
    )
    with pytest.raises(NetworkingNotFound):
        await service.get_contact(OWNER_ID, created.contact.id)
    replay = await service.delete_contact(
        OWNER_ID,
        created.contact.id,
        expected_version=current.contact.version,
        idempotency_key="contact-delete-001",
        context=_context(),
    )
    assert replay == deleted


@pytest.mark.asyncio
async def test_recurring_reminder_has_one_idempotent_occurrence_and_content_free_lease() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    command = CreateReminder(
        title="Review local reminder",
        due_at=NOW,
        recurrence_days=7,
        max_attempts=3,
    )
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        command,
        idempotency_key="reminder-recurring",
        context=_context(),
    )
    replay = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        command,
        idempotency_key="reminder-recurring",
        context=_context(),
    )
    assert replay == reminder
    assert len(state.occurrences) == 1
    assert len(state.outbox) == 1
    scheduled_execution = await service.get_reminder_execution(OWNER_ID, reminder.id)
    assert scheduled_execution is not None
    assert scheduled_execution.occurrence_number == 1
    assert scheduled_execution.occurrence_status is ReminderOccurrenceStatus.SCHEDULED
    assert scheduled_execution.attempt_count == 0
    assert scheduled_execution.queue_status is ReminderOutboxStatus.PENDING
    assert not hasattr(scheduled_execution, "lease_token")
    assert not hasattr(scheduled_execution, "lease_expires_at")
    assert not hasattr(scheduled_execution, "contact_id")
    with pytest.raises(NetworkingNotFound):
        await service.get_reminder_execution(OTHER_ID, reminder.id)

    claimed = await service.claim_due_reminders(now=NOW, lease_seconds=30)
    assert len(claimed) == 1
    entry = claimed[0]
    assert entry.attempt_count == 1
    assert entry.trace_id == "a" * 32
    assert not hasattr(entry, "message") and not hasattr(entry, "email")
    leased_execution = await service.get_reminder_execution(OWNER_ID, reminder.id)
    assert leased_execution is not None
    assert leased_execution.attempt_count == 1
    assert leased_execution.queue_status is ReminderOutboxStatus.LEASED
    assert await service.claim_due_reminders(now=NOW, lease_seconds=30) == ()
    with pytest.raises(NetworkingLeaseConflict):
        await service.materialize_due_reminder(
            entry.id,
            lease_token=UUID("00000000-0000-4000-8000-00000000ffff"),
            now=NOW,
        )

    occurrence = await service.materialize_due_reminder(
        entry.id,
        lease_token=entry.lease_token,  # type: ignore[arg-type]
        now=NOW,
    )
    assert occurrence.status is ReminderOccurrenceStatus.DUE
    assert len(state.occurrences) == 1
    due = await service.list_due_reminders(OWNER_ID)
    assert [item.reminder.id for item in due.data] == [reminder.id]
    executions = await service.get_reminder_executions(OWNER_ID, (reminder.id,))
    assert executions[reminder.id].occurrence_status is ReminderOccurrenceStatus.DUE

    resolved = await service.resolve_reminder(
        OWNER_ID,
        reminder.id,
        ResolveReminder(action=ReminderResolutionAction.ACKNOWLEDGE),
        expected_version=reminder.version,
        idempotency_key="reminder-recurring-ack",
        context=_context(),
    )
    assert resolved.status is ReminderStatus.ACTIVE
    assert len(state.occurrences) == 2
    next_occurrence = max(state.occurrences.values(), key=lambda item: item.occurrence_number)
    assert next_occurrence.scheduled_for == NOW + timedelta(days=7)
    next_execution = await service.get_reminder_execution(OWNER_ID, reminder.id)
    assert next_execution is not None
    assert next_execution.occurrence_id == next_occurrence.id
    assert next_execution.occurrence_number == 2
    assert next_execution.queue_status is ReminderOutboxStatus.PENDING
    assert next_execution.attempt_count == 0
    assert {item.trace_id for item in state.occurrences.values()} == {"a" * 32}
    assert {item.trace_id for item in state.outbox.values()} == {"a" * 32}
    occurrence_audits = [
        audit
        for audit in state.audits
        if audit.action
        in {
            NetworkingAuditAction.REMINDER_OCCURRENCE_MATERIALIZED,
            NetworkingAuditAction.REMINDER_OCCURRENCE_DUE,
            NetworkingAuditAction.REMINDER_OCCURRENCE_ACKNOWLEDGED,
        }
    ]
    assert occurrence_audits
    assert {audit.trace_id for audit in occurrence_audits} == {"a" * 32}
    state.occurrences.clear()
    assert await service.get_reminder_execution(OWNER_ID, reminder.id) is None
    with pytest.raises(NetworkingNotFound):
        await service.get_reminder_execution(
            OWNER_ID,
            UUID("00000000-0000-4000-8000-00000000eeee"),
        )


@pytest.mark.parametrize(
    "terminal_status",
    (ReminderStatus.CANCELLED, ReminderStatus.COMPLETED),
)
@pytest.mark.asyncio
async def test_reactivating_terminal_reminder_rematerializes_same_due_occurrence(
    terminal_status: ReminderStatus,
) -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    due_at = NOW + timedelta(hours=2)
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(title="Reactivate local reminder", due_at=due_at),
        idempotency_key=f"reminder-reactivate-create-{terminal_status.value}",
        context=_context(),
    )
    terminal = await service.update_reminder(
        OWNER_ID,
        reminder.id,
        UpdateReminder(status=terminal_status),
        expected_version=reminder.version,
        idempotency_key=f"reminder-reactivate-terminal-{terminal_status.value}",
        context=_context(),
    )
    assert terminal.status is terminal_status
    assert len(state.occurrences) == 1
    assert len(state.outbox) == 1
    assert next(iter(state.occurrences.values())).status is ReminderOccurrenceStatus.CANCELLED
    assert next(iter(state.outbox.values())).status is ReminderOutboxStatus.CANCELLED

    reactivated = await service.update_reminder(
        OWNER_ID,
        reminder.id,
        UpdateReminder(status=ReminderStatus.ACTIVE),
        expected_version=terminal.version,
        idempotency_key=f"reminder-reactivate-active-{terminal_status.value}",
        context=_context(),
    )

    assert reactivated.status is ReminderStatus.ACTIVE
    assert reactivated.due_at == due_at
    assert len(state.occurrences) == 2
    assert len(state.outbox) == 2
    execution = await service.get_reminder_execution(OWNER_ID, reminder.id)
    assert execution is not None
    assert execution.occurrence_number == 2
    assert execution.scheduled_for == due_at
    assert execution.occurrence_status is ReminderOccurrenceStatus.SCHEDULED
    assert execution.queue_status is ReminderOutboxStatus.PENDING
    assert state.contacts[created.contact.id].next_contact_at is None

    replay = await service.update_reminder(
        OWNER_ID,
        reminder.id,
        UpdateReminder(status=ReminderStatus.ACTIVE),
        expected_version=terminal.version,
        idempotency_key=f"reminder-reactivate-active-{terminal_status.value}",
        context=_context(),
    )
    assert replay == reactivated
    assert len(state.occurrences) == 2
    assert len(state.outbox) == 2


@pytest.mark.asyncio
async def test_reminder_retention_prunes_only_safe_terminal_pairs_and_preserves_dead_letters() -> (
    None
):
    state = MemoryNetworking()
    service = _service(
        state,
        policy=NetworkingPolicy(
            max_occurrences_per_reminder=2,
            retained_terminal_occurrences_per_reminder=1,
        ),
    )
    contact = await _create_contact(service)
    reminder = await service.create_reminder(
        OWNER_ID,
        contact.contact.id,
        CreateReminder(
            title="Bounded recurring local reminder",
            due_at=NOW,
            recurrence_days=1,
        ),
        idempotency_key="retention-reminder",
        context=_context(),
    )
    first_claim = (await service.claim_due_reminders(now=NOW, lease_seconds=30))[0]
    await service.materialize_due_reminder(
        first_claim.id,
        lease_token=first_claim.lease_token,  # type: ignore[arg-type]
        now=NOW,
    )
    resolved = await service.resolve_reminder(
        OWNER_ID,
        reminder.id,
        ResolveReminder(action=ReminderResolutionAction.ACKNOWLEDGE),
        expected_version=reminder.version,
        idempotency_key="retention-first-ack",
        context=_context(),
    )
    first_occurrence = min(
        state.occurrences.values(),
        key=lambda value: value.occurrence_number,
    )
    state.occurrences[first_occurrence.id] = replace(
        first_occurrence,
        status=ReminderOccurrenceStatus.DEAD_LETTER,
    )
    first_outbox = next(
        value for value in state.outbox.values() if value.occurrence_id == first_occurrence.id
    )
    state.outbox[first_outbox.id] = replace(
        first_outbox,
        status=ReminderOutboxStatus.DEAD_LETTER,
    )

    second_claim = (
        await service.claim_due_reminders(
            now=NOW + timedelta(days=1),
            lease_seconds=30,
        )
    )[0]
    await service.materialize_due_reminder(
        second_claim.id,
        lease_token=second_claim.lease_token,  # type: ignore[arg-type]
        now=NOW + timedelta(days=1),
    )
    await service.resolve_reminder(
        OWNER_ID,
        reminder.id,
        ResolveReminder(action=ReminderResolutionAction.ACKNOWLEDGE),
        expected_version=resolved.version,
        idempotency_key="retention-second-ack",
        context=_context(),
    )

    assert state.occurrences[first_occurrence.id].status is ReminderOccurrenceStatus.DEAD_LETTER
    assert state.outbox[first_outbox.id].status is ReminderOutboxStatus.DEAD_LETTER
    assert len(state.occurrences) == 2
    assert len(state.outbox) == 2
    assert state.reminders[reminder.id].status is ReminderStatus.COMPLETED
    assert all(item.trace_id == "a" * 32 for item in state.occurrences.values())
    assert all(item.trace_id == "a" * 32 for item in state.outbox.values())


@pytest.mark.asyncio
async def test_expired_lease_recovers_or_dead_letters_at_bounded_attempts() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(
            title="One attempt reminder",
            due_at=NOW,
            max_attempts=1,
        ),
        idempotency_key="reminder-deadletter",
        context=_context(),
    )
    claimed = await service.claim_due_reminders(now=NOW, lease_seconds=15)
    recovered = await service.recover_expired_leases(now=NOW + timedelta(seconds=16))

    assert len(recovered) == 1
    assert recovered[0].id == claimed[0].id
    assert recovered[0].status is ReminderOutboxStatus.DEAD_LETTER
    occurrence = state.occurrences[recovered[0].occurrence_id]
    assert occurrence.status is ReminderOccurrenceStatus.DEAD_LETTER
    assert await service.claim_due_reminders(now=NOW + timedelta(days=1), lease_seconds=15) == ()


@pytest.mark.asyncio
async def test_child_workflows_never_overwrite_owner_curated_contact_summaries() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    manual_follow_up = NOW + timedelta(days=45)
    curated = await service.update_contact(
        OWNER_ID,
        created.contact.id,
        UpdateContact(
            referral_state=ContactReferralState.CONSIDERING,
            next_contact_at=manual_follow_up,
        ),
        expected_version=created.contact.version,
        idempotency_key="manual-contact-summaries",
        context=_context(),
    )
    referral = await service.create_referral(
        OWNER_ID,
        created.contact.id,
        CreateReferral(
            application_id=APPLICATION_ID,
            status=ReferralStatus.REFERRED,
        ),
        expected_contact_version=curated.contact.version,
        idempotency_key="manual-summary-referral",
        context=_context(),
    )
    await service.update_referral(
        OWNER_ID,
        referral.id,
        UpdateReferral(status=ReferralStatus.DECLINED),
        expected_version=referral.version,
        idempotency_key="manual-summary-referral-update",
        context=_context(),
    )
    reminder = await service.create_reminder(
        OWNER_ID,
        created.contact.id,
        CreateReminder(title="Independent local reminder", due_at=NOW),
        idempotency_key="manual-summary-reminder",
        context=_context(),
    )
    claimed = (await service.claim_due_reminders(now=NOW, lease_seconds=30))[0]
    await service.materialize_due_reminder(
        claimed.id,
        lease_token=claimed.lease_token,  # type: ignore[arg-type]
        now=NOW,
    )
    await service.resolve_reminder(
        OWNER_ID,
        reminder.id,
        ResolveReminder(
            action=ReminderResolutionAction.SNOOZE,
            snooze_until=NOW + timedelta(days=1),
        ),
        expected_version=reminder.version,
        idempotency_key="manual-summary-reminder-snooze",
        context=_context(),
    )

    preserved = state.contacts[created.contact.id]
    assert preserved.version == curated.contact.version
    assert preserved.referral_state is ContactReferralState.CONSIDERING
    assert preserved.next_contact_at == manual_follow_up


@pytest.mark.asyncio
async def test_claim_batch_commits_other_candidates_after_one_conflict() -> None:
    class ConflictOnceMemory(MemoryNetworking):
        conflict_entry_id: UUID | None = None
        conflicted = False

        async def save_outbox(self, entry: NetworkingReminderOutboxEntry) -> None:
            if (
                not self.conflicted
                and entry.id == self.conflict_entry_id
                and entry.status is ReminderOutboxStatus.LEASED
            ):
                self.conflicted = True
                raise NetworkingConflict
            await super().save_outbox(entry)

    state = ConflictOnceMemory()
    service = _service(state)
    created = await _create_contact(service)
    for index in range(2):
        await service.create_reminder(
            OWNER_ID,
            created.contact.id,
            CreateReminder(title=f"Independent reminder {index}", due_at=NOW),
            idempotency_key=f"partial-claim-reminder-{index}",
            context=_context(),
        )
    ordered = sorted(state.outbox.values(), key=lambda item: (item.available_at, item.id))
    state.conflict_entry_id = ordered[0].id

    claimed = await service.claim_due_reminders(now=NOW, lease_seconds=30, limit=2)

    assert state.conflicted is True
    assert [entry.id for entry in claimed] == [ordered[1].id]
    assert state.outbox[ordered[0].id].status is ReminderOutboxStatus.PENDING
    assert state.outbox[ordered[1].id].status is ReminderOutboxStatus.LEASED


@pytest.mark.asyncio
async def test_consent_history_is_append_only_and_referral_uses_application_port() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    current = await service.withdraw_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=ConsentPurpose.OUTREACH,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=1,
        idempotency_key="withdraw-history1",
        context=_context(),
    )
    await service.grant_consent(
        OWNER_ID,
        created.contact.id,
        ChangeContactConsent(
            purpose=ConsentPurpose.OUTREACH,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        expected_version=current.contact.version,
        idempotency_key="grant-history-001",
        context=_context(),
    )
    history = await service.get_consent_history(OWNER_ID, created.contact.id)
    outreach = [event for event in history.events if event.purpose is ConsentPurpose.OUTREACH]
    assert [event.action for event in outreach] == [
        ConsentAction.GRANTED,
        ConsentAction.WITHDRAWN,
        ConsentAction.GRANTED,
    ]
    assert [event.sequence for event in history.events] == list(range(1, len(history.events) + 1))

    with pytest.raises(NetworkingNotFound):
        await service.create_referral(
            OWNER_ID,
            created.contact.id,
            CreateReferral(application_id=UUID("00000000-0000-4000-8000-00000000abcd")),
            expected_contact_version=(
                await service.get_contact(OWNER_ID, created.contact.id)
            ).contact.version,
            idempotency_key="referral-bad-app",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_organization_is_owner_scoped_and_never_fetches_its_url() -> None:
    state = MemoryNetworking()
    service = _service(state)
    organization = await service.create_organization(
        OWNER_ID,
        CreateOrganization(
            name="Example Organization",
            website="https://example.invalid/private",
            tags=("Target",),
        ),
        idempotency_key="organization-001",
        context=_context(),
    )
    assert organization.website == "https://example.invalid/private"
    with pytest.raises(NetworkingNotFound):
        await service.get_organization(OTHER_ID, organization.id)
    assert not any(
        token in name.casefold()
        for name in dir(service)
        for token in ("scrape", "crawl", "fetch_url")
    )


@pytest.mark.asyncio
async def test_organization_deletion_redacts_and_detaches_linked_contacts_idempotently() -> None:
    state = MemoryNetworking()
    service = _service(state)
    organization = await service.create_organization(
        OWNER_ID,
        CreateOrganization(
            name="Sensitive Organization",
            website="https://example.invalid/private",
            industry="Private industry",
        ),
        idempotency_key="organization-delete-create",
        context=_context(),
    )
    contact = await service.create_contact(
        OWNER_ID,
        CreateContact(
            name="Linked Contact",
            organization_id=organization.id,
            collection_attested=True,
            storage_attested=True,
            outreach_attested=False,
            consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        ),
        idempotency_key="organization-delete-contact",
        context=_context(),
    )

    deleted = await service.delete_organization(
        OWNER_ID,
        organization.id,
        expected_version=organization.version,
        idempotency_key="organization-delete",
        context=_context(),
    )
    assert deleted.name == DELETED_TEXT
    assert deleted.website is None
    assert deleted.deleted_at == NOW
    detached = await service.get_contact(OWNER_ID, contact.contact.id)
    assert detached.contact.organization_id is None
    assert detached.contact.version == contact.contact.version + 1
    with pytest.raises(NetworkingNotFound):
        await service.get_organization(OWNER_ID, organization.id)
    with pytest.raises(NetworkingNotFound):
        await service.delete_organization(
            OTHER_ID,
            organization.id,
            expected_version=organization.version,
            idempotency_key="other-organization-delete",
            context=_context(OTHER_ID),
        )

    replay = await service.delete_organization(
        OWNER_ID,
        organization.id,
        expected_version=organization.version,
        idempotency_key="organization-delete",
        context=_context(),
    )
    assert replay == deleted


@pytest.mark.asyncio
async def test_every_private_child_list_uses_bounded_scope_safe_keyset_pages() -> None:
    state = MemoryNetworking()
    service = _service(state)
    created = await _create_contact(service)
    contact_id = created.contact.id

    for index in range(3):
        await service.create_note(
            OWNER_ID,
            contact_id,
            CreateContactNote(body=f"Private note {index}"),
            idempotency_key=f"paged-note-{index:02d}",
            context=_context(),
        )
        current = await service.get_contact(OWNER_ID, contact_id)
        await service.record_interaction(
            OWNER_ID,
            contact_id,
            RecordInteraction(
                kind=InteractionKind.MEETING,
                direction=InteractionDirection.MUTUAL,
                occurred_at=NOW + timedelta(minutes=index),
                summary=f"Recorded interaction {index}",
            ),
            expected_contact_version=current.contact.version,
            idempotency_key=f"paged-interaction-{index:02d}",
            context=_context(),
        )
        current = await service.get_contact(OWNER_ID, contact_id)
        await service.create_referral(
            OWNER_ID,
            contact_id,
            CreateReferral(
                application_id=APPLICATION_ID,
                status=ReferralStatus.PLANNED,
                context=f"Referral context {index}",
            ),
            expected_contact_version=current.contact.version,
            idempotency_key=f"paged-referral-{index:02d}",
            context=_context(),
        )
        await service.create_template(
            OWNER_ID,
            CreateTemplate(
                kind=TemplateKind.CUSTOM,
                name=f"Reviewed template {index}",
                body=f"Reviewed local draft {index}",
                user_reviewed=True,
            ),
            idempotency_key=f"paged-template-{index:02d}",
            context=_context(),
        )
        await service.create_reminder(
            OWNER_ID,
            contact_id,
            CreateReminder(
                title=f"Local reminder {index}",
                due_at=NOW + timedelta(days=index),
            ),
            idempotency_key=f"paged-reminder-{index:02d}",
            context=_context(),
        )

    consent_first = await service.get_consent_history(OWNER_ID, contact_id, limit=2)
    consent_second = await service.get_consent_history(
        OWNER_ID,
        contact_id,
        cursor=consent_first.page.next_cursor,
        limit=2,
    )
    assert consent_first.current.allows_outreach
    assert consent_second.current.allows_outreach
    assert consent_first.page.has_more
    assert consent_first.page.limit == 2
    assert consent_second.page.next_cursor is None
    assert [item.sequence for item in consent_first.events] == [1, 2]
    assert [item.sequence for item in consent_second.events] == [3]
    assert {item.id for item in consent_first.events}.isdisjoint(
        {item.id for item in consent_second.events}
    )

    notes_first = await service.list_notes(OWNER_ID, contact_id, limit=2)
    notes_second = await service.list_notes(
        OWNER_ID,
        contact_id,
        cursor=notes_first.page.next_cursor,
        limit=2,
    )
    interactions_first = await service.list_interactions(OWNER_ID, contact_id, limit=2)
    interactions_second = await service.list_interactions(
        OWNER_ID,
        contact_id,
        cursor=interactions_first.page.next_cursor,
        limit=2,
    )
    referrals_first = await service.list_referrals(OWNER_ID, contact_id, limit=2)
    referrals_second = await service.list_referrals(
        OWNER_ID,
        contact_id,
        cursor=referrals_first.page.next_cursor,
        limit=2,
    )
    templates_first = await service.list_templates(OWNER_ID, limit=2)
    templates_second = await service.list_templates(
        OWNER_ID,
        cursor=templates_first.page.next_cursor,
        limit=2,
    )
    reminders_first = await service.list_reminders(OWNER_ID, contact_id, limit=2)
    reminders_second = await service.list_reminders(
        OWNER_ID,
        contact_id,
        cursor=reminders_first.page.next_cursor,
        limit=2,
    )
    for cursor in (
        consent_first.page.next_cursor,
        notes_first.page.next_cursor,
        interactions_first.page.next_cursor,
        referrals_first.page.next_cursor,
        templates_first.page.next_cursor,
        reminders_first.page.next_cursor,
    ):
        assert cursor is not None
        assert cursor.isascii()

    assert [item.body for item in notes_first.data] == [
        "Private note 2",
        "Private note 1",
    ]
    assert [item.summary for item in interactions_first.data] == [
        "Recorded interaction 2",
        "Recorded interaction 1",
    ]
    assert [item.context for item in referrals_first.data] == [
        "Referral context 2",
        "Referral context 1",
    ]
    assert [item.name for item in templates_first.data] == [
        "Reviewed template 2",
        "Reviewed template 1",
    ]
    assert [item.title for item in reminders_first.data] == [
        "Local reminder 0",
        "Local reminder 1",
    ]

    for first, second in (
        (notes_first, notes_second),
        (interactions_first, interactions_second),
        (referrals_first, referrals_second),
        (templates_first, templates_second),
        (reminders_first, reminders_second),
    ):
        assert len(first.data) == 2
        assert first.page.limit == 2
        assert first.page.has_more
        assert first.page.next_cursor is not None
        assert len(second.data) == 1
        assert not second.page.has_more
        assert second.page.next_cursor is None
        assert {item.id for item in first.data}.isdisjoint({item.id for item in second.data})

    with pytest.raises(NetworkingValidationError):
        await service.list_interactions(
            OWNER_ID,
            contact_id,
            cursor=notes_first.page.next_cursor,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_notes(OWNER_ID, contact_id, cursor="é")
    with pytest.raises(NetworkingValidationError):
        await service.list_templates(OWNER_ID, cursor="not-base64")
    with pytest.raises(NetworkingValidationError):
        await service.list_reminders(OWNER_ID, contact_id, limit=201)

    other_contact = await _create_contact(
        service,
        name="Other Contact",
        key="contact-create-scope",
    )
    with pytest.raises(NetworkingValidationError):
        await service.list_notes(
            OWNER_ID,
            other_contact.contact.id,
            cursor=notes_first.page.next_cursor,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_notes(
            OTHER_ID,
            contact_id,
            cursor=notes_first.page.next_cursor,
        )
    with pytest.raises(NetworkingValidationError):
        await service.list_templates(
            OTHER_ID,
            cursor=templates_first.page.next_cursor,
        )
