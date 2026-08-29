"""Consent, ownership, concurrency, and durable reminder policies for networking."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, cast
from uuid import UUID

from rezumi.modules.networking.domain import (
    DELETED_TEXT,
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NETWORKING_CONTACT_DELETION_POLICY_VERSION,
    ConsentAction,
    ConsentPurpose,
    ContactReferralState,
    InteractionDeliveryState,
    InteractionDirection,
    InteractionKind,
    NetworkingAuditAction,
    NetworkingAuditEvent,
    NetworkingConflict,
    NetworkingConsentEvent,
    NetworkingConsentRequired,
    NetworkingContact,
    NetworkingContactNote,
    NetworkingIdempotencyConflict,
    NetworkingIdempotencyRecord,
    NetworkingInteraction,
    NetworkingLeaseConflict,
    NetworkingNotFound,
    NetworkingOrganization,
    NetworkingQuotaExceeded,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingReminderOccurrence,
    NetworkingReminderOutboxEntry,
    NetworkingTemplate,
    NetworkingValidationError,
    NetworkingVersionConflict,
    ReferralStatus,
    RelationshipStage,
    ReminderOccurrenceStatus,
    ReminderOutboxKind,
    ReminderOutboxStatus,
    ReminderStatus,
    normalize_search,
    normalize_tags,
)

from .models import (
    ChangeContactConsent,
    ContactConsentHistory,
    ContactConsentState,
    ContactFilter,
    ContactView,
    CreateContact,
    CreateContactNote,
    CreateOrganization,
    CreateReferral,
    CreateReminder,
    CreateTemplate,
    DueReminderView,
    NetworkingCursor,
    NetworkingKeysetCursor,
    OrganizationFilter,
    PagedResult,
    RecordInteraction,
    ReminderExecutionView,
    ReminderResolutionAction,
    RequestContext,
    ResolveReminder,
    UnsetType,
    UpdateContact,
    UpdateOrganization,
    UpdateReferral,
    UpdateReminder,
    UpdateTemplate,
    keyset_page_result,
    page_result,
)
from .ports import (
    ApplicationReferenceProvider,
    Clock,
    IdentifierFactory,
    NetworkingUnitOfWork,
    NetworkingUnitOfWorkFactory,
)


@dataclass(frozen=True, slots=True)
class NetworkingPolicy:
    """Bounded limits shared by HTTP and worker delivery adapters."""

    max_page_size: int = 100
    max_child_page_size: int = 200
    max_claim_batch: int = 100
    min_lease_seconds: int = 15
    max_lease_seconds: int = 300
    max_organizations_per_owner: int = 500
    max_contacts_per_owner: int = 5_000
    max_templates_per_owner: int = 200
    max_notes_per_contact: int = 500
    max_interactions_per_contact: int = 2_000
    max_referrals_per_contact: int = 200
    max_reminders_per_contact: int = 500
    max_consent_events_per_contact: int = 100
    max_occurrences_per_reminder: int = 512
    retained_terminal_occurrences_per_reminder: int = 64

    def __post_init__(self) -> None:
        values = (
            self.max_page_size,
            self.max_child_page_size,
            self.max_claim_batch,
            self.min_lease_seconds,
            self.max_lease_seconds,
            self.max_organizations_per_owner,
            self.max_contacts_per_owner,
            self.max_templates_per_owner,
            self.max_notes_per_contact,
            self.max_interactions_per_contact,
            self.max_referrals_per_contact,
            self.max_reminders_per_contact,
            self.max_consent_events_per_contact,
            self.max_occurrences_per_reminder,
            self.retained_terminal_occurrences_per_reminder,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise NetworkingValidationError("networking policy limits must be positive integers")
        if self.min_lease_seconds > self.max_lease_seconds:
            raise NetworkingValidationError("minimum lease duration cannot exceed maximum")
        if self.max_consent_events_per_contact < 3:
            raise NetworkingValidationError("consent history must allow initial attestations")
        if self.retained_terminal_occurrences_per_reminder >= self.max_occurrences_per_reminder:
            raise NetworkingValidationError(
                "terminal reminder retention must be below the occurrence limit"
            )


class NetworkingService:
    def __init__(
        self,
        *,
        unit_of_work: NetworkingUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        applications: ApplicationReferenceProvider,
        policy: NetworkingPolicy | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._applications = applications
        self._policy = policy or NetworkingPolicy()

    async def list_organizations(
        self,
        owner_user_id: UUID,
        *,
        filter_by: OrganizationFilter | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> PagedResult[NetworkingOrganization]:
        self._limit(limit)
        normalized_filter = OrganizationFilter(
            query=_query((filter_by or OrganizationFilter()).query),
            tag=_tag((filter_by or OrganizationFilter()).tag),
        )
        scope = _cursor_scope(
            owner_user_id,
            collection="organizations",
            filter_by=normalized_filter,
            sort="updated_at:desc,id:desc",
        )
        after = NetworkingCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            records = await uow.list_organizations(
                owner_user_id, normalized_filter, after, limit + 1
            )
        return page_result(records, limit=limit, scope=scope)

    async def get_organization(
        self, owner_user_id: UUID, organization_id: UUID
    ) -> NetworkingOrganization:
        async with self._unit_of_work() as uow:
            organization = await uow.get_organization(owner_user_id, organization_id)
        if organization is None:
            raise NetworkingNotFound
        return organization

    async def create_organization(
        self,
        owner_user_id: UUID,
        command: CreateOrganization,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingOrganization:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint("create_organization", command)
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "organization"
            )
            if replay is not None:
                return cast(NetworkingOrganization, replay)
            await uow.lock_owner(owner_user_id)
            self._quota(
                await uow.count_organizations(owner_user_id),
                self._policy.max_organizations_per_owner,
            )
            organization = NetworkingOrganization(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                name=command.name,
                website=command.website,
                industry=command.industry,
                location=command.location,
                tags=command.tags,
                normalized_search=normalize_search(
                    command.name, command.industry, command.location
                ),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_organization(organization)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "organization", organization.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.ORGANIZATION_CREATED,
                "organization",
                organization.id,
                {"version": 1},
                now,
            )
            await uow.commit()
            return organization

    async def update_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        command: UpdateOrganization,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingOrganization:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "update_organization",
            {"organization_id": organization_id, "version": expected_version, "command": command},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "organization"
            )
            if replay is not None:
                return cast(NetworkingOrganization, replay)
            current = await uow.get_organization(owner_user_id, organization_id, for_update=True)
            if current is None:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            updated = NetworkingOrganization(
                id=current.id,
                owner_user_id=current.owner_user_id,
                name=_patch(command.name, current.name),
                website=_patch(command.website, current.website),
                industry=_patch(command.industry, current.industry),
                location=_patch(command.location, current.location),
                tags=_patch(command.tags, current.tags),
                normalized_search=normalize_search(
                    _patch(command.name, current.name),
                    _patch(command.industry, current.industry),
                    _patch(command.location, current.location),
                ),
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=now,
            )
            await uow.save_organization(updated)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "organization", updated.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.ORGANIZATION_UPDATED,
                "organization",
                updated.id,
                {"version": updated.version},
                now,
            )
            await uow.commit()
            return updated

    async def delete_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingOrganization:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "delete_organization",
            {"organization_id": organization_id, "version": expected_version},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "deleted_organization",
            )
            if replay is not None:
                return cast(NetworkingOrganization, replay)
            await uow.lock_owner(owner_user_id)
            current = await uow.get_organization(
                owner_user_id,
                organization_id,
                for_update=True,
            )
            if current is None:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            detached_contacts = await uow.detach_organization_contacts(
                owner_user_id,
                organization_id,
                now,
            )
            deleted = NetworkingOrganization(
                id=current.id,
                owner_user_id=current.owner_user_id,
                name=DELETED_TEXT,
                website=None,
                industry=None,
                location=None,
                tags=(),
                normalized_search=DELETED_TEXT,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=now,
                deleted_at=now,
            )
            await uow.save_organization(deleted)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "deleted_organization",
                organization_id,
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.ORGANIZATION_DELETED,
                "organization",
                organization_id,
                {
                    "version": deleted.version,
                    "detached_contact_count": detached_contacts,
                },
                now,
            )
            await uow.commit()
            return deleted

    async def list_contacts(
        self,
        owner_user_id: UUID,
        *,
        filter_by: ContactFilter | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> PagedResult[ContactView]:
        self._limit(limit)
        requested = filter_by or ContactFilter()
        normalized_filter = ContactFilter(
            query=_query(requested.query),
            organization_id=requested.organization_id,
            relationship_stage=requested.relationship_stage,
            referral_state=requested.referral_state,
            tag=_tag(requested.tag),
            outreach_consent=requested.outreach_consent,
        )
        scope = _cursor_scope(
            owner_user_id,
            collection="contacts",
            filter_by=normalized_filter,
            sort="updated_at:desc,id:desc",
        )
        after = NetworkingCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            contacts = await uow.list_contacts(owner_user_id, normalized_filter, after, limit + 1)
            events = await uow.get_consent_events_for_contacts(
                owner_user_id, tuple(contact.id for contact in contacts)
            )
        has_more = len(contacts) > limit
        visible = contacts[:limit]
        views = tuple(
            ContactView(contact=contact, consent=_consent_state(events.get(contact.id, [])))
            for contact in visible
        )
        next_cursor = (
            NetworkingCursor(
                scope=scope,
                updated_at=visible[-1].updated_at,
                record_id=visible[-1].id,
            ).encode()
            if has_more
            else None
        )
        from .models import Page

        return PagedResult(
            data=views,
            page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor),
        )

    async def get_contact(self, owner_user_id: UUID, contact_id: UUID) -> ContactView:
        async with self._unit_of_work() as uow:
            contact = await uow.get_contact(owner_user_id, contact_id)
            if contact is None:
                raise NetworkingNotFound
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
        return ContactView(contact=contact, consent=_consent_state(events))

    async def create_contact(
        self,
        owner_user_id: UUID,
        command: CreateContact,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ContactView:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        if command.collection_attested is not True or command.storage_attested is not True:
            raise NetworkingConsentRequired(
                "contact creation requires collection and storage attestations"
            )
        _validate_consent_policy_version(command.consent_policy_version)
        fingerprint = _fingerprint("create_contact", command)
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(uow, owner_user_id, idempotency_key, fingerprint, "contact")
            if replay is not None:
                contact = cast(NetworkingContact, replay)
                events = await uow.get_latest_consent_events(owner_user_id, contact.id)
                return ContactView(contact=contact, consent=_consent_state(events))
            await uow.lock_owner(owner_user_id)
            self._quota(
                await uow.count_contacts(owner_user_id),
                self._policy.max_contacts_per_owner,
            )
            if command.organization_id is not None:
                organization = await uow.get_organization(owner_user_id, command.organization_id)
                if organization is None:
                    raise NetworkingNotFound
            contact = NetworkingContact(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                organization_id=command.organization_id,
                name=command.name,
                role=command.role,
                email=command.email,
                phone=command.phone,
                profile_url=command.profile_url,
                location=command.location,
                relationship_stage=command.relationship_stage,
                referral_state=command.referral_state,
                tags=command.tags,
                normalized_search=normalize_search(
                    command.name,
                    command.role,
                    command.email,
                    command.phone,
                    command.location,
                ),
                last_contact_at=None,
                next_contact_at=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_contact(contact)
            purposes = [ConsentPurpose.COLLECTION, ConsentPurpose.STORAGE]
            if command.outreach_attested:
                purposes.append(ConsentPurpose.OUTREACH)
            self._quota(
                0,
                self._policy.max_consent_events_per_contact,
                requested=len(purposes),
            )
            events = [
                NetworkingConsentEvent(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    contact_id=contact.id,
                    purpose=purpose,
                    action=ConsentAction.GRANTED,
                    policy_version=command.consent_policy_version,
                    actor_user_id=context.actor_user_id,
                    sequence=index,
                    occurred_at=now,
                )
                for index, purpose in enumerate(purposes, start=1)
            ]
            for event in events:
                await uow.add_consent_event(event)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "contact", contact.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.CONTACT_CREATED,
                "contact",
                contact.id,
                {
                    "version": 1,
                    "organization_id": contact.organization_id,
                },
                now,
            )
            await uow.commit()
            return ContactView(contact=contact, consent=_consent_state(events))

    async def update_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: UpdateContact,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ContactView:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "update_contact",
            {"contact_id": contact_id, "version": expected_version, "command": command},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(uow, owner_user_id, idempotency_key, fingerprint, "contact")
            if replay is not None:
                contact = cast(NetworkingContact, replay)
                events = await uow.get_latest_consent_events(owner_user_id, contact.id)
                return ContactView(contact=contact, consent=_consent_state(events))
            await uow.lock_owner(owner_user_id)
            current = await self._active_contact(uow, owner_user_id, contact_id, for_update=True)
            self._version(current.version, expected_version)
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
            self._require_storage(_consent_state(events))
            organization_id = _patch(command.organization_id, current.organization_id)
            if organization_id is not None:
                organization = await uow.get_organization(owner_user_id, organization_id)
                if organization is None:
                    raise NetworkingNotFound
            name = _patch(command.name, current.name)
            role = _patch(command.role, current.role)
            email = _patch(command.email, current.email)
            phone = _patch(command.phone, current.phone)
            location = _patch(command.location, current.location)
            updated = NetworkingContact(
                id=current.id,
                owner_user_id=current.owner_user_id,
                organization_id=organization_id,
                name=name,
                role=role,
                email=email,
                phone=phone,
                profile_url=_patch(command.profile_url, current.profile_url),
                location=location,
                relationship_stage=_patch(command.relationship_stage, current.relationship_stage),
                referral_state=_patch(command.referral_state, current.referral_state),
                tags=_patch(command.tags, current.tags),
                normalized_search=normalize_search(name, role, email, phone, location),
                last_contact_at=current.last_contact_at,
                next_contact_at=_patch(command.next_contact_at, current.next_contact_at),
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=now,
            )
            await uow.save_contact(updated)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "contact", updated.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.CONTACT_UPDATED,
                "contact",
                updated.id,
                {
                    "version": updated.version,
                    "stage_from": current.relationship_stage.value,
                    "stage_to": updated.relationship_stage.value,
                    "organization_id": updated.organization_id,
                },
                now,
            )
            await uow.commit()
            return ContactView(contact=updated, consent=_consent_state(events))

    async def get_consent_history(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ContactConsentHistory:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="consent",
            parent_id=contact_id,
            sort="sequence:asc,id:asc",
        )
        after = NetworkingKeysetCursor.decode(
            cursor,
            expected_scope=scope,
            numeric=True,
        )
        async with self._unit_of_work() as uow:
            await self._active_contact(uow, owner_user_id, contact_id)
            visible = await uow.list_consent_event_page(
                owner_user_id,
                contact_id,
                after,
                limit + 1,
            )
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
        page = keyset_page_result(
            visible,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.sequence,
            id_of=lambda item: item.id,
        )
        return ContactConsentHistory(
            current=_consent_state(events),
            events=page.data,
            page=page.page,
        )

    async def grant_consent(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: ChangeContactConsent,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ContactView:
        return await self._change_consent(
            owner_user_id,
            contact_id,
            command,
            action=ConsentAction.GRANTED,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            context=context,
        )

    async def withdraw_consent(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: ChangeContactConsent,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ContactView:
        return await self._change_consent(
            owner_user_id,
            contact_id,
            command,
            action=ConsentAction.WITHDRAWN,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            context=context,
        )

    async def _change_consent(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: ChangeContactConsent,
        *,
        action: ConsentAction,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ContactView:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        _validate_consent_policy_version(command.policy_version)
        fingerprint = _fingerprint(
            f"{action.value}_consent",
            {
                "contact_id": contact_id,
                "version": expected_version,
                "command": command,
            },
        )
        now = self._clock.now()
        destructive_withdrawal = action is ConsentAction.WITHDRAWN and command.purpose in {
            ConsentPurpose.COLLECTION,
            ConsentPurpose.STORAGE,
        }
        response_kind = "deleted_contact" if destructive_withdrawal else "contact"
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                response_kind,
            )
            if replay is not None:
                contact = cast(NetworkingContact, replay)
                events = await uow.get_latest_consent_events(owner_user_id, contact.id)
                return ContactView(contact=contact, consent=_consent_state(events))
            await uow.lock_owner(owner_user_id)
            contact = await self._active_contact(
                uow,
                owner_user_id,
                contact_id,
                for_update=True,
            )
            self._version(contact.version, expected_version)
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
            state = _consent_state(events)
            current = _purpose_value(state, command.purpose)
            requested = action is ConsentAction.GRANTED
            if current == requested:
                raise NetworkingValidationError(
                    f"{command.purpose.value} consent is already {action.value}"
                )
            if (
                requested
                and command.purpose is ConsentPurpose.OUTREACH
                and (not state.collection or not state.storage)
            ):
                raise NetworkingConsentRequired(
                    "collection and storage consent are required before outreach"
                )
            if requested:
                self._quota(
                    await uow.count_consent_events(owner_user_id, contact_id),
                    self._policy.max_consent_events_per_contact,
                )
            sequence = await uow.next_consent_sequence(owner_user_id, contact_id)
            purposes = [command.purpose]
            if destructive_withdrawal:
                purposes.extend(
                    purpose
                    for purpose in ConsentPurpose
                    if purpose is not command.purpose and _purpose_value(state, purpose)
                )
            new_events: list[NetworkingConsentEvent] = []
            for purpose in purposes:
                event = NetworkingConsentEvent(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    contact_id=contact_id,
                    purpose=purpose,
                    action=action,
                    policy_version=command.policy_version,
                    actor_user_id=context.actor_user_id,
                    sequence=sequence,
                    occurred_at=now,
                )
                await uow.add_consent_event(event)
                new_events.append(event)
                sequence += 1
            if destructive_withdrawal:
                updated = NetworkingContact(
                    id=contact.id,
                    owner_user_id=contact.owner_user_id,
                    organization_id=None,
                    name=DELETED_TEXT,
                    role=None,
                    email=None,
                    phone=None,
                    profile_url=None,
                    location=None,
                    relationship_stage=RelationshipStage.ARCHIVED,
                    referral_state=ContactReferralState.CANCELLED,
                    tags=(),
                    normalized_search=DELETED_TEXT,
                    last_contact_at=None,
                    next_contact_at=None,
                    version=contact.version + 1,
                    created_at=contact.created_at,
                    updated_at=now,
                    deleted_at=now,
                )
            else:
                updated = replace(
                    contact,
                    next_contact_at=None
                    if action is ConsentAction.WITHDRAWN
                    else contact.next_contact_at,
                    referral_state=ContactReferralState.CANCELLED
                    if action is ConsentAction.WITHDRAWN
                    and contact.referral_state is not ContactReferralState.NONE
                    else contact.referral_state,
                    version=contact.version + 1,
                    updated_at=now,
                )
            await uow.save_contact(updated)
            if action is ConsentAction.WITHDRAWN:
                await uow.cancel_contact_reminders(owner_user_id, contact_id, now)
                await uow.cancel_contact_referrals(owner_user_id, contact_id, now)
                await uow.redact_contact_content(
                    owner_user_id,
                    contact_id,
                    now,
                    outreach_only=not destructive_withdrawal,
                )
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                response_kind,
                contact_id,
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.CONSENT_GRANTED
                if action is ConsentAction.GRANTED
                else NetworkingAuditAction.CONSENT_WITHDRAWN,
                "contact",
                contact_id,
                {"purpose": command.purpose.value, "version": updated.version},
                now,
            )
            await uow.commit()
            return ContactView(
                contact=updated,
                consent=_consent_state([*events, *new_events]),
            )

    async def delete_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingContact:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "delete_contact",
            {"contact_id": contact_id, "version": expected_version},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "deleted_contact",
            )
            if replay is not None:
                return cast(NetworkingContact, replay)
            await uow.lock_owner(owner_user_id)
            contact = await self._active_contact(uow, owner_user_id, contact_id, for_update=True)
            self._version(contact.version, expected_version)
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
            sequence = await uow.next_consent_sequence(owner_user_id, contact_id)
            for purpose in ConsentPurpose:
                if _purpose_value(_consent_state(events), purpose):
                    event = NetworkingConsentEvent(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        contact_id=contact_id,
                        purpose=purpose,
                        action=ConsentAction.WITHDRAWN,
                        policy_version=NETWORKING_CONTACT_DELETION_POLICY_VERSION,
                        actor_user_id=context.actor_user_id,
                        sequence=sequence,
                        occurred_at=now,
                    )
                    await uow.add_consent_event(event)
                    events.append(event)
                    sequence += 1
            deleted = NetworkingContact(
                id=contact.id,
                owner_user_id=contact.owner_user_id,
                organization_id=None,
                name=DELETED_TEXT,
                role=None,
                email=None,
                phone=None,
                profile_url=None,
                location=None,
                relationship_stage=RelationshipStage.ARCHIVED,
                referral_state=ContactReferralState.CANCELLED,
                tags=(),
                normalized_search=DELETED_TEXT,
                last_contact_at=None,
                next_contact_at=None,
                version=contact.version + 1,
                created_at=contact.created_at,
                updated_at=now,
                deleted_at=now,
            )
            await uow.save_contact(deleted)
            await uow.redact_contact_content(
                owner_user_id,
                contact_id,
                now,
                outreach_only=False,
            )
            await uow.cancel_contact_reminders(owner_user_id, contact_id, now)
            await uow.cancel_contact_referrals(owner_user_id, contact_id, now)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "deleted_contact",
                contact_id,
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.CONTACT_DELETED,
                "contact",
                contact_id,
                {"version": deleted.version},
                now,
            )
            await uow.commit()
            return deleted

    async def create_note(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: CreateContactNote,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingContactNote:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "create_contact_note", {"contact_id": contact_id, "command": command}
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(uow, owner_user_id, idempotency_key, fingerprint, "note")
            if replay is not None:
                return cast(NetworkingContactNote, replay)
            await uow.lock_owner(owner_user_id)
            await self._require_contact_storage(uow, owner_user_id, contact_id)
            self._quota(
                await uow.count_notes(owner_user_id, contact_id),
                self._policy.max_notes_per_contact,
            )
            note = NetworkingContactNote(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                contact_id=contact_id,
                body=command.body,
                created_at=now,
            )
            await uow.add_note(note)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "note", note.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.NOTE_CREATED,
                "contact_note",
                note.id,
                {"contact_id": contact_id},
                now,
            )
            await uow.commit()
            return note

    async def list_notes(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> PagedResult[NetworkingContactNote]:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="notes",
            parent_id=contact_id,
            sort="created_at:desc,id:desc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            await self._active_contact(uow, owner_user_id, contact_id)
            values = await uow.list_notes(owner_user_id, contact_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def record_interaction(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: RecordInteraction,
        *,
        expected_contact_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingInteraction:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "record_interaction",
            {
                "contact_id": contact_id,
                "version": expected_contact_version,
                "command": command,
            },
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "interaction"
            )
            if replay is not None:
                return cast(NetworkingInteraction, replay)
            await uow.lock_owner(owner_user_id)
            contact = await self._active_contact(uow, owner_user_id, contact_id, for_update=True)
            self._version(contact.version, expected_contact_version)
            events = await uow.get_latest_consent_events(owner_user_id, contact_id)
            state = _consent_state(events)
            self._require_storage(state)
            outbound = (
                command.direction is InteractionDirection.OUTBOUND
                or command.template_id is not None
                or command.kind is InteractionKind.REFERRAL
            )
            if outbound:
                self._require_outreach(state)
            if command.template_id is not None:
                template = await uow.get_template(owner_user_id, command.template_id)
                if template is None:
                    raise NetworkingNotFound
            self._quota(
                await uow.count_interactions(owner_user_id, contact_id),
                self._policy.max_interactions_per_contact,
            )
            interaction = NetworkingInteraction(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                contact_id=contact_id,
                template_id=command.template_id,
                kind=command.kind,
                direction=command.direction,
                occurred_at=command.occurred_at,
                summary=command.summary,
                delivery_state=InteractionDeliveryState.RECORDED_ONLY,
                created_at=now,
            )
            await uow.add_interaction(interaction)
            updated_contact = replace(
                contact,
                last_contact_at=max(
                    value
                    for value in (contact.last_contact_at, command.occurred_at)
                    if value is not None
                ),
                version=contact.version + 1,
                updated_at=now,
            )
            await uow.save_contact(updated_contact)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "interaction",
                interaction.id,
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.INTERACTION_RECORDED,
                "interaction",
                interaction.id,
                {
                    "contact_id": contact_id,
                    "template_id": command.template_id,
                },
                now,
            )
            await uow.commit()
            return interaction

    async def list_interactions(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> PagedResult[NetworkingInteraction]:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="interactions",
            parent_id=contact_id,
            sort="occurred_at:desc,id:desc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            await self._active_contact(uow, owner_user_id, contact_id)
            values = await uow.list_interactions(owner_user_id, contact_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.occurred_at,
            id_of=lambda item: item.id,
        )

    async def create_referral(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: CreateReferral,
        *,
        expected_contact_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingReferral:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "create_referral",
            {
                "contact_id": contact_id,
                "version": expected_contact_version,
                "command": command,
            },
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "referral"
            )
            if replay is not None:
                return cast(NetworkingReferral, replay)
            await uow.lock_owner(owner_user_id)
            contact = await self._active_contact(uow, owner_user_id, contact_id, for_update=True)
            self._version(contact.version, expected_contact_version)
            self._require_outreach(
                _consent_state(await uow.get_latest_consent_events(owner_user_id, contact_id))
            )
            application = await self._applications.get_reference(
                owner_user_id, command.application_id
            )
            if application is None:
                raise NetworkingNotFound
            self._quota(
                await uow.count_referrals(owner_user_id, contact_id),
                self._policy.max_referrals_per_contact,
            )
            referral = NetworkingReferral(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                contact_id=contact_id,
                application_id=command.application_id,
                status=command.status,
                context=command.context,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_referral(referral)
            # `contact.referral_state` is an explicitly owner-curated summary.
            # Child referral workflows never overwrite it; their authoritative
            # status remains on each referral row.
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "referral", referral.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.REFERRAL_CREATED,
                "referral",
                referral.id,
                {
                    "contact_id": contact_id,
                    "application_id": command.application_id,
                    "status_to": command.status.value,
                },
                now,
            )
            await uow.commit()
            return referral

    async def update_referral(
        self,
        owner_user_id: UUID,
        referral_id: UUID,
        command: UpdateReferral,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingReferral:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "update_referral",
            {"referral_id": referral_id, "version": expected_version, "command": command},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "referral"
            )
            if replay is not None:
                return cast(NetworkingReferral, replay)
            candidate = await uow.get_referral(owner_user_id, referral_id)
            if candidate is None:
                raise NetworkingNotFound
            contact = await self._active_contact(
                uow,
                owner_user_id,
                candidate.contact_id,
                for_update=True,
            )
            current = await uow.get_referral(owner_user_id, referral_id, for_update=True)
            if current is None or current.contact_id != contact.id:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            status = _patch(command.status, current.status)
            consent = _consent_state(
                await uow.get_latest_consent_events(
                    owner_user_id,
                    current.contact_id,
                )
            )
            if status not in {ReferralStatus.CANCELLED, ReferralStatus.DECLINED}:
                self._require_outreach(consent)
            context_value = _patch(command.context, current.context)
            if not consent.allows_outreach:
                # A terminal state may still be recorded after withdrawal, but
                # no private prose may be introduced or retained.
                context_value = None
            updated = replace(
                current,
                status=status,
                context=context_value,
                version=current.version + 1,
                updated_at=now,
            )
            await uow.save_referral(updated)
            # Do not overwrite the owner-curated contact summary from one
            # referral when a contact can have many independent referrals.
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "referral", referral_id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.REFERRAL_UPDATED,
                "referral",
                referral_id,
                {
                    "contact_id": current.contact_id,
                    "application_id": current.application_id,
                    "status_from": current.status.value,
                    "status_to": updated.status.value,
                    "version": updated.version,
                },
                now,
            )
            await uow.commit()
            return updated

    async def list_referrals(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> PagedResult[NetworkingReferral]:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="referrals",
            parent_id=contact_id,
            sort="updated_at:desc,id:desc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            await self._active_contact(uow, owner_user_id, contact_id)
            values = await uow.list_referrals(owner_user_id, contact_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.updated_at,
            id_of=lambda item: item.id,
        )

    async def create_template(
        self,
        owner_user_id: UUID,
        command: CreateTemplate,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingTemplate:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        if command.user_reviewed is not True:
            raise NetworkingValidationError("templates require explicit user review")
        fingerprint = _fingerprint("create_template", command)
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "template"
            )
            if replay is not None:
                return cast(NetworkingTemplate, replay)
            await uow.lock_owner(owner_user_id)
            self._quota(
                await uow.count_templates(owner_user_id),
                self._policy.max_templates_per_owner,
            )
            template = NetworkingTemplate(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                kind=command.kind,
                name=command.name,
                body=command.body,
                reviewed_at=now,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_template(template)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "template", template.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.TEMPLATE_CREATED,
                "template",
                template.id,
                {"version": 1},
                now,
            )
            await uow.commit()
            return template

    async def update_template(
        self,
        owner_user_id: UUID,
        template_id: UUID,
        command: UpdateTemplate,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingTemplate:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        if command.user_reviewed is not True:
            raise NetworkingValidationError("template changes require explicit user review")
        fingerprint = _fingerprint(
            "update_template",
            {"template_id": template_id, "version": expected_version, "command": command},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "template"
            )
            if replay is not None:
                return cast(NetworkingTemplate, replay)
            current = await uow.get_template(owner_user_id, template_id, for_update=True)
            if current is None:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            updated = NetworkingTemplate(
                id=current.id,
                owner_user_id=current.owner_user_id,
                kind=_patch(command.kind, current.kind),
                name=_patch(command.name, current.name),
                body=_patch(command.body, current.body),
                reviewed_at=now,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=now,
            )
            await uow.save_template(updated)
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "template", template_id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.TEMPLATE_UPDATED,
                "template",
                template_id,
                {"version": updated.version},
                now,
            )
            await uow.commit()
            return updated

    async def list_templates(
        self,
        owner_user_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> PagedResult[NetworkingTemplate]:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="templates",
            sort="updated_at:desc,id:desc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            values = await uow.list_templates(owner_user_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.updated_at,
            id_of=lambda item: item.id,
        )

    async def create_reminder(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        command: CreateReminder,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingReminder:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "create_reminder", {"contact_id": contact_id, "command": command}
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "reminder"
            )
            if replay is not None:
                return cast(NetworkingReminder, replay)
            await uow.lock_owner(owner_user_id)
            await self._active_contact(uow, owner_user_id, contact_id, for_update=True)
            self._require_outreach(
                _consent_state(await uow.get_latest_consent_events(owner_user_id, contact_id))
            )
            self._quota(
                await uow.count_reminders(owner_user_id, contact_id),
                self._policy.max_reminders_per_contact,
            )
            reminder = NetworkingReminder(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                contact_id=contact_id,
                title=command.title,
                due_at=command.due_at,
                recurrence_days=command.recurrence_days,
                max_attempts=command.max_attempts,
                status=ReminderStatus.ACTIVE,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_reminder(reminder)
            await self._materialize_occurrence(
                uow,
                reminder,
                1,
                reminder.due_at,
                now,
                trace_id=context.trace_id,
                request_id=context.request_id,
                actor_user_id=context.actor_user_id,
            )
            # `contact.next_contact_at` is a manually curated follow-up date.
            # Reminder scheduling is authoritative on reminder/occurrence rows.
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "reminder", reminder.id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.REMINDER_CREATED,
                "reminder",
                reminder.id,
                {
                    "contact_id": contact_id,
                    "version": 1,
                    "recurring": reminder.recurrence_days is not None,
                },
                now,
            )
            await uow.commit()
            return reminder

    async def update_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        command: UpdateReminder,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingReminder:
        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            "update_reminder",
            {"reminder_id": reminder_id, "version": expected_version, "command": command},
        )
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow, owner_user_id, idempotency_key, fingerprint, "reminder"
            )
            if replay is not None:
                return cast(NetworkingReminder, replay)
            await uow.lock_owner(owner_user_id)
            candidate = await uow.get_reminder(owner_user_id, reminder_id)
            if candidate is None:
                raise NetworkingNotFound
            contact = await self._active_contact(
                uow,
                owner_user_id,
                candidate.contact_id,
                for_update=True,
            )
            current = await uow.get_reminder(owner_user_id, reminder_id, for_update=True)
            if current is None or current.contact_id != contact.id:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            status = _patch(command.status, current.status)
            consent = _consent_state(
                await uow.get_latest_consent_events(
                    owner_user_id,
                    current.contact_id,
                )
            )
            if status is ReminderStatus.ACTIVE:
                self._require_outreach(consent)
            title = _patch(command.title, current.title)
            if not consent.allows_outreach:
                # Cancellation/completion remains available after withdrawal,
                # but the terminal row must stay content-free.
                title = DELETED_TEXT
            updated = replace(
                current,
                title=title,
                due_at=_patch(command.due_at, current.due_at),
                recurrence_days=_patch(command.recurrence_days, current.recurrence_days),
                status=status,
                version=current.version + 1,
                updated_at=now,
            )
            await uow.save_reminder(updated)
            due_changed = (
                not isinstance(command.due_at, UnsetType) and command.due_at != current.due_at
            )
            reactivated = (
                current.status is not ReminderStatus.ACTIVE and status is ReminderStatus.ACTIVE
            )
            if status is not ReminderStatus.ACTIVE:
                await uow.cancel_reminder_occurrences(owner_user_id, reminder_id, now)
            elif due_changed or reactivated:
                await uow.cancel_reminder_occurrences(owner_user_id, reminder_id, now)
                occurrence_number = await uow.next_occurrence_number(owner_user_id, reminder_id)
                await self._materialize_occurrence(
                    uow,
                    updated,
                    occurrence_number,
                    updated.due_at,
                    now,
                    trace_id=context.trace_id,
                    request_id=context.request_id,
                    actor_user_id=context.actor_user_id,
                )
            await self._record_idempotency(
                uow, owner_user_id, idempotency_key, fingerprint, "reminder", reminder_id
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                NetworkingAuditAction.REMINDER_UPDATED,
                "reminder",
                reminder_id,
                {
                    "contact_id": current.contact_id,
                    "status_from": current.status.value,
                    "status_to": updated.status.value,
                    "version": updated.version,
                    "recurring": updated.recurrence_days is not None,
                },
                now,
            )
            await uow.commit()
            return updated

    async def list_reminders(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> PagedResult[NetworkingReminder]:
        self._child_limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="reminders",
            parent_id=contact_id,
            sort="due_at:asc,id:asc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            await self._active_contact(uow, owner_user_id, contact_id)
            values = await uow.list_reminders(owner_user_id, contact_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.due_at,
            id_of=lambda item: item.id,
        )

    async def get_reminder_execution(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
    ) -> ReminderExecutionView | None:
        """Return only bounded, machine-readable local execution state."""

        async with self._unit_of_work() as uow:
            reminder = await uow.get_reminder(owner_user_id, reminder_id)
            if reminder is None:
                raise NetworkingNotFound
            occurrence = await uow.get_latest_reminder_occurrence(
                owner_user_id,
                reminder_id,
            )
            if occurrence is None:
                return None
            entry = await uow.get_occurrence_outbox(owner_user_id, occurrence.id)
        if entry is None:
            return None
        return ReminderExecutionView(
            occurrence_id=occurrence.id,
            occurrence_number=occurrence.occurrence_number,
            scheduled_for=occurrence.scheduled_for,
            occurrence_status=occurrence.status,
            attempt_count=entry.attempt_count,
            max_attempts=entry.max_attempts,
            queue_status=entry.status,
            last_error_code=entry.last_error_code,
        )

    async def get_reminder_executions(
        self,
        owner_user_id: UUID,
        reminder_ids: tuple[UUID, ...],
    ) -> dict[UUID, ReminderExecutionView]:
        """Return bounded execution state for a page without per-row queries."""

        unique_ids = tuple(dict.fromkeys(reminder_ids))
        if not unique_ids:
            return {}
        if len(unique_ids) > self._policy.max_page_size:
            raise NetworkingValidationError("too many reminder IDs were requested")
        async with self._unit_of_work() as uow:
            values = await uow.get_reminder_executions(owner_user_id, unique_ids)
        return {
            reminder_id: ReminderExecutionView(
                occurrence_id=occurrence.id,
                occurrence_number=occurrence.occurrence_number,
                scheduled_for=occurrence.scheduled_for,
                occurrence_status=occurrence.status,
                attempt_count=entry.attempt_count,
                max_attempts=entry.max_attempts,
                queue_status=entry.status,
                last_error_code=entry.last_error_code,
            )
            for reminder_id, (occurrence, entry) in values.items()
        }

    async def list_due_reminders(
        self,
        owner_user_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> PagedResult[DueReminderView]:
        """List durable, owner-actionable reminders; no worker acknowledgement."""

        self._limit(limit)
        scope = _cursor_scope(
            owner_user_id,
            collection="due_reminders",
            sort="scheduled_for:asc,id:asc",
        )
        after = NetworkingKeysetCursor.decode(cursor, expected_scope=scope)
        async with self._unit_of_work() as uow:
            values = await uow.list_due_reminders(owner_user_id, after, limit + 1)
        return keyset_page_result(
            values,
            limit=limit,
            scope=scope,
            position_of=lambda item: item.execution.scheduled_for,
            id_of=lambda item: item.execution.occurrence_id,
        )

    async def claim_due_reminders(
        self,
        *,
        now: datetime,
        lease_seconds: int,
        limit: int = 100,
    ) -> tuple[NetworkingReminderOutboxEntry, ...]:
        """Lease content-free local reminder signals for an internal worker."""

        _aware(now, "claim time")
        if not self._policy.min_lease_seconds <= lease_seconds <= self._policy.max_lease_seconds:
            raise NetworkingValidationError("lease duration is out of range")
        self._claim_limit(limit)
        claimed: list[NetworkingReminderOutboxEntry] = []
        # Discovery is lock-free and ends before processing. Each candidate has
        # its own transaction, so unrelated owners can neither deadlock through
        # opposite batch order nor roll back one another's progress.
        async with self._unit_of_work() as uow:
            candidate_ids = tuple(
                candidate.id
                for candidate in await uow.list_claimable_outbox(
                    now,
                    self._policy.max_claim_batch,
                )
            )
        for candidate_id in candidate_ids:
            if len(claimed) >= limit:
                break
            try:
                async with self._unit_of_work() as uow:
                    (
                        entry,
                        occurrence,
                        reminder,
                        contact,
                    ) = await self._lock_reminder_processing_chain(
                        uow,
                        candidate_id,
                    )
                    if (
                        entry.status is not ReminderOutboxStatus.PENDING
                        or entry.available_at > now
                        or occurrence.status is not ReminderOccurrenceStatus.SCHEDULED
                        or reminder.status is not ReminderStatus.ACTIVE
                        or contact.deleted_at is not None
                    ):
                        continue
                    consent = _consent_state(
                        await uow.get_latest_consent_events(
                            entry.owner_user_id,
                            contact.id,
                        )
                    )
                    if not consent.allows_outreach:
                        continue
                    leased = replace(
                        entry,
                        status=ReminderOutboxStatus.LEASED,
                        attempt_count=entry.attempt_count + 1,
                        lease_token=self._ids.new(),
                        lease_expires_at=now + timedelta(seconds=lease_seconds),
                        updated_at=now,
                    )
                    await uow.save_outbox(leased)
                    await uow.commit()
                    claimed.append(leased)
            except (NetworkingConflict, NetworkingNotFound):
                # A concurrent cancellation/deletion is an expected,
                # content-free race. Other candidates still make progress.
                continue
        return tuple(claimed)

    async def materialize_due_reminder(
        self,
        entry_id: UUID,
        *,
        lease_token: UUID,
        now: datetime,
    ) -> NetworkingReminderOccurrence:
        """Turn a leased signal into a durable due item without user action."""

        _aware(now, "due materialization time")
        async with self._unit_of_work() as uow:
            entry, occurrence, _, _ = await self._lock_reminder_processing_chain(uow, entry_id)
            entry = self._lease(entry, lease_token, now)
            due = replace(
                occurrence,
                status=ReminderOccurrenceStatus.DUE,
                updated_at=now,
            )
            processed = replace(
                entry,
                status=ReminderOutboxStatus.PROCESSED,
                lease_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
            await uow.save_occurrence(due)
            await uow.save_outbox(processed)
            await self._worker_audit(
                uow,
                entry,
                NetworkingAuditAction.REMINDER_OCCURRENCE_DUE,
                occurrence,
                now,
            )
            await uow.commit()
            return due

    async def resolve_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        command: ResolveReminder,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> NetworkingReminder:
        """Apply an explicit owner acknowledgement, completion, or snooze."""

        self._actor(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        if command.action is ReminderResolutionAction.SNOOZE:
            if command.snooze_until is None:
                raise NetworkingValidationError("snoozeUntil is required for snooze")
            _aware(command.snooze_until, "snooze time")
        elif command.snooze_until is not None:
            raise NetworkingValidationError("snoozeUntil is only valid for snooze")
        fingerprint = _fingerprint(
            "resolve_reminder",
            {
                "reminder_id": reminder_id,
                "version": expected_version,
                "command": command,
            },
        )
        now = self._clock.now()
        if command.snooze_until is not None and command.snooze_until <= now:
            raise NetworkingValidationError("snoozeUntil must be in the future")
        async with self._unit_of_work() as uow:
            replay = await self._replay(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "reminder",
            )
            if replay is not None:
                return cast(NetworkingReminder, replay)
            await uow.lock_owner(owner_user_id)
            current = await uow.get_reminder(
                owner_user_id,
                reminder_id,
                for_update=True,
            )
            if current is None:
                raise NetworkingNotFound
            self._version(current.version, expected_version)
            contact = await self._active_contact(
                uow,
                owner_user_id,
                current.contact_id,
                for_update=True,
            )
            self._require_outreach(
                _consent_state(await uow.get_latest_consent_events(owner_user_id, contact.id))
            )
            occurrence = await uow.get_latest_reminder_occurrence(
                owner_user_id,
                reminder_id,
            )
            if occurrence is None:
                raise NetworkingConflict("reminder has no actionable occurrence")
            locked_occurrence = await uow.get_occurrence(
                owner_user_id,
                occurrence.id,
                for_update=True,
            )
            entry = await uow.get_occurrence_outbox(owner_user_id, occurrence.id)
            if (
                locked_occurrence is None
                or entry is None
                or locked_occurrence.status is not ReminderOccurrenceStatus.DUE
                or entry.status is not ReminderOutboxStatus.PROCESSED
                or current.status is not ReminderStatus.ACTIVE
            ):
                raise NetworkingConflict("reminder occurrence is not actionable")
            acknowledged = replace(
                locked_occurrence,
                status=ReminderOccurrenceStatus.ACKNOWLEDGED,
                acknowledged_at=now,
                updated_at=now,
            )
            await uow.save_occurrence(acknowledged)

            next_due_at: datetime | None = None
            next_status = ReminderStatus.COMPLETED
            if command.action is ReminderResolutionAction.SNOOZE:
                next_due_at = cast(datetime, command.snooze_until)
                next_status = ReminderStatus.ACTIVE
            elif (
                command.action is ReminderResolutionAction.ACKNOWLEDGE
                and current.recurrence_days is not None
            ):
                next_due_at = max(now, locked_occurrence.scheduled_for) + timedelta(
                    days=current.recurrence_days
                )
                next_status = ReminderStatus.ACTIVE

            if next_due_at is not None:
                try:
                    await self._materialize_occurrence(
                        uow,
                        current,
                        locked_occurrence.occurrence_number + 1,
                        next_due_at,
                        now,
                        trace_id=context.trace_id,
                        request_id=context.request_id,
                        actor_user_id=context.actor_user_id,
                    )
                except NetworkingQuotaExceeded:
                    next_due_at = None
                    next_status = ReminderStatus.COMPLETED

            updated = replace(
                current,
                due_at=next_due_at if next_due_at is not None else current.due_at,
                status=next_status,
                version=current.version + 1,
                updated_at=now,
            )
            await uow.save_reminder(updated)
            await self._record_idempotency(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "reminder",
                reminder_id,
            )
            await self._audit(
                uow,
                owner_user_id,
                context,
                (
                    NetworkingAuditAction.REMINDER_OCCURRENCE_SNOOZED
                    if command.action is ReminderResolutionAction.SNOOZE
                    else NetworkingAuditAction.REMINDER_OCCURRENCE_ACKNOWLEDGED
                ),
                "reminder_occurrence",
                acknowledged.id,
                {
                    "reminder_id": reminder_id,
                    "occurrence_id": acknowledged.id,
                    "occurrence_number": acknowledged.occurrence_number,
                    "status_to": updated.status.value,
                    "version": updated.version,
                },
                now,
            )
            await uow.commit()
            return updated

    async def fail_reminder(
        self,
        entry_id: UUID,
        *,
        lease_token: UUID,
        error_code: str,
        retry_at: datetime,
        now: datetime,
    ) -> NetworkingReminderOutboxEntry:
        _aware(now, "failure time")
        _aware(retry_at, "retry time")
        if retry_at < now:
            raise NetworkingValidationError("retry time cannot be in the past")
        async with self._unit_of_work() as uow:
            entry, occurrence, _, _ = await self._lock_reminder_processing_chain(uow, entry_id)
            entry = self._lease(entry, lease_token, now)
            exhausted = entry.attempt_count >= entry.max_attempts
            failed = replace(
                entry,
                status=ReminderOutboxStatus.DEAD_LETTER
                if exhausted
                else ReminderOutboxStatus.PENDING,
                available_at=retry_at,
                lease_token=None,
                lease_expires_at=None,
                last_error_code=error_code,
                updated_at=now,
            )
            await uow.save_outbox(failed)
            if exhausted:
                await uow.save_occurrence(
                    replace(
                        occurrence,
                        status=ReminderOccurrenceStatus.DEAD_LETTER,
                        updated_at=now,
                    )
                )
            await self._worker_audit(
                uow,
                failed,
                NetworkingAuditAction.REMINDER_OCCURRENCE_FAILED,
                occurrence,
                now,
            )
            await uow.commit()
            return failed

    async def recover_expired_leases(
        self, *, now: datetime, limit: int = 100
    ) -> tuple[NetworkingReminderOutboxEntry, ...]:
        _aware(now, "recovery time")
        self._claim_limit(limit)
        recovered: list[NetworkingReminderOutboxEntry] = []
        async with self._unit_of_work() as uow:
            candidate_ids = tuple(
                candidate.id for candidate in await uow.list_expired_outbox(now, limit)
            )
        for candidate_id in candidate_ids:
            try:
                async with self._unit_of_work() as uow:
                    entry, occurrence, _, _ = await self._lock_reminder_processing_chain(
                        uow,
                        candidate_id,
                    )
                    if (
                        entry.status is not ReminderOutboxStatus.LEASED
                        or entry.lease_expires_at is None
                        or entry.lease_expires_at > now
                    ):
                        continue
                    exhausted = entry.attempt_count >= entry.max_attempts
                    replacement = replace(
                        entry,
                        status=ReminderOutboxStatus.DEAD_LETTER
                        if exhausted
                        else ReminderOutboxStatus.PENDING,
                        available_at=now,
                        lease_token=None,
                        lease_expires_at=None,
                        last_error_code="lease_expired",
                        updated_at=now,
                    )
                    await uow.save_outbox(replacement)
                    if exhausted:
                        await uow.save_occurrence(
                            replace(
                                occurrence,
                                status=ReminderOccurrenceStatus.DEAD_LETTER,
                                updated_at=now,
                            )
                        )
                    await self._worker_audit(
                        uow,
                        replacement,
                        NetworkingAuditAction.REMINDER_OCCURRENCE_FAILED,
                        occurrence,
                        now,
                    )
                    await uow.commit()
                    recovered.append(replacement)
            except (NetworkingConflict, NetworkingNotFound):
                continue
        return tuple(recovered)

    async def _lock_reminder_processing_chain(
        self,
        uow: NetworkingUnitOfWork,
        entry_id: UUID,
    ) -> tuple[
        NetworkingReminderOutboxEntry,
        NetworkingReminderOccurrence,
        NetworkingReminder,
        NetworkingContact,
    ]:
        """Lock contact -> reminder -> occurrence -> outbox to avoid lock inversions."""

        candidate_entry = await uow.get_outbox(entry_id)
        if candidate_entry is None:
            raise NetworkingNotFound
        candidate_occurrence = await uow.get_occurrence(
            candidate_entry.owner_user_id,
            candidate_entry.occurrence_id,
        )
        if candidate_occurrence is None:
            raise NetworkingNotFound
        candidate_reminder = await uow.get_reminder(
            candidate_entry.owner_user_id,
            candidate_occurrence.reminder_id,
        )
        if candidate_reminder is None:
            raise NetworkingNotFound

        await uow.lock_owner(candidate_entry.owner_user_id)
        contact = await uow.get_contact(
            candidate_entry.owner_user_id,
            candidate_reminder.contact_id,
            for_update=True,
            include_deleted=True,
        )
        if contact is None:
            raise NetworkingNotFound
        reminder = await uow.get_reminder(
            candidate_entry.owner_user_id,
            candidate_reminder.id,
            for_update=True,
        )
        occurrence = await uow.get_occurrence(
            candidate_entry.owner_user_id,
            candidate_occurrence.id,
            for_update=True,
        )
        entry = await uow.get_outbox(entry_id, for_update=True)
        if (
            reminder is None
            or occurrence is None
            or entry is None
            or reminder.contact_id != contact.id
            or occurrence.reminder_id != reminder.id
            or entry.owner_user_id != contact.owner_user_id
            or entry.occurrence_id != occurrence.id
            or entry.trace_id != occurrence.trace_id
        ):
            raise NetworkingNotFound
        return entry, occurrence, reminder, contact

    async def _materialize_occurrence(
        self,
        uow: NetworkingUnitOfWork,
        reminder: NetworkingReminder,
        occurrence_number: int,
        scheduled_for: datetime,
        now: datetime,
        *,
        trace_id: str,
        request_id: str,
        actor_user_id: UUID | None,
    ) -> NetworkingReminderOccurrence:
        existing = await uow.find_occurrence(reminder.owner_user_id, reminder.id, occurrence_number)
        if existing is not None:
            if existing.trace_id != trace_id:
                raise NetworkingConflict("reminder occurrence trace mismatch")
            return existing
        await uow.prune_terminal_reminder_history(
            reminder.owner_user_id,
            reminder.id,
            retain=self._policy.retained_terminal_occurrences_per_reminder,
        )
        self._quota(
            await uow.count_reminder_occurrences(reminder.owner_user_id, reminder.id),
            self._policy.max_occurrences_per_reminder,
        )
        occurrence = NetworkingReminderOccurrence(
            id=self._ids.new(),
            owner_user_id=reminder.owner_user_id,
            reminder_id=reminder.id,
            contact_id=reminder.contact_id,
            scheduled_for=scheduled_for,
            occurrence_number=occurrence_number,
            status=ReminderOccurrenceStatus.SCHEDULED,
            trace_id=trace_id,
            acknowledged_at=None,
            created_at=now,
            updated_at=now,
        )
        outbox = NetworkingReminderOutboxEntry(
            id=self._ids.new(),
            owner_user_id=reminder.owner_user_id,
            occurrence_id=occurrence.id,
            kind=ReminderOutboxKind.LOCAL_REMINDER_DUE,
            status=ReminderOutboxStatus.PENDING,
            trace_id=trace_id,
            available_at=scheduled_for,
            attempt_count=0,
            max_attempts=reminder.max_attempts,
            lease_token=None,
            lease_expires_at=None,
            last_error_code=None,
            created_at=now,
            updated_at=now,
        )
        await uow.add_occurrence(occurrence)
        await uow.add_outbox(outbox)
        await uow.add_audit(
            NetworkingAuditEvent(
                id=self._ids.new(),
                owner_user_id=reminder.owner_user_id,
                actor_user_id=actor_user_id,
                action=NetworkingAuditAction.REMINDER_OCCURRENCE_MATERIALIZED,
                target_kind="reminder_occurrence",
                target_id=occurrence.id,
                request_id=request_id,
                trace_id=trace_id,
                metadata=cast(
                    dict[str, object],
                    _jsonable(
                        {
                            "reminder_id": reminder.id,
                            "occurrence_id": occurrence.id,
                            "occurrence_number": occurrence.occurrence_number,
                            "outbox_status": outbox.status.value,
                        }
                    ),
                ),
                created_at=now,
            )
        )
        return occurrence

    async def _worker_audit(
        self,
        uow: NetworkingUnitOfWork,
        entry: NetworkingReminderOutboxEntry,
        action: NetworkingAuditAction,
        occurrence: NetworkingReminderOccurrence,
        now: datetime,
    ) -> None:
        await uow.add_audit(
            NetworkingAuditEvent(
                id=self._ids.new(),
                owner_user_id=entry.owner_user_id,
                actor_user_id=None,
                action=action,
                target_kind="reminder_occurrence",
                target_id=occurrence.id,
                request_id="networking-reminder-worker",
                trace_id=entry.trace_id,
                metadata=cast(
                    dict[str, object],
                    _jsonable(
                        {
                            "reminder_id": occurrence.reminder_id,
                            "occurrence_id": occurrence.id,
                            "occurrence_number": occurrence.occurrence_number,
                            "attempt_count": entry.attempt_count,
                            "outbox_status": entry.status.value,
                        }
                    ),
                ),
                created_at=now,
            )
        )

    async def _replay(
        self,
        uow: NetworkingUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        expected_kind: str,
    ) -> object | None:
        # A key-scoped transaction lock makes ambiguous concurrent retries
        # converge before either request creates a second target row.
        await uow.lock_idempotency(owner_user_id, key)
        record = await uow.find_idempotency(owner_user_id, key)
        if record is None:
            return None
        if record.request_fingerprint != fingerprint or record.response_kind != expected_kind:
            raise NetworkingIdempotencyConflict
        if record.response_id is None:
            return None
        result: object | None
        if expected_kind in {"organization", "deleted_organization"}:
            result = await uow.get_organization(
                owner_user_id,
                record.response_id,
                include_deleted=expected_kind == "deleted_organization",
            )
        elif expected_kind in {"contact", "deleted_contact"}:
            result = await uow.get_contact(
                owner_user_id,
                record.response_id,
                include_deleted=expected_kind == "deleted_contact",
            )
        elif expected_kind == "note":
            result = await uow.get_note(owner_user_id, record.response_id)
        elif expected_kind == "interaction":
            result = await uow.get_interaction(owner_user_id, record.response_id)
        elif expected_kind == "referral":
            result = await uow.get_referral(owner_user_id, record.response_id)
        elif expected_kind == "template":
            result = await uow.get_template(owner_user_id, record.response_id)
        elif expected_kind == "reminder":
            result = await uow.get_reminder(owner_user_id, record.response_id)
        else:
            raise NetworkingIdempotencyConflict
        if result is None:
            raise NetworkingIdempotencyConflict
        return result

    async def _record_idempotency(
        self,
        uow: NetworkingUnitOfWork,
        owner_user_id: UUID,
        key: str,
        fingerprint: str,
        kind: str,
        response_id: UUID,
    ) -> None:
        await uow.add_idempotency(
            NetworkingIdempotencyRecord(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                response_kind=kind,
                response_id=response_id,
                created_at=self._clock.now(),
            )
        )

    async def _audit(
        self,
        uow: NetworkingUnitOfWork,
        owner_user_id: UUID,
        context: RequestContext,
        action: NetworkingAuditAction,
        target_kind: str,
        target_id: UUID,
        metadata: dict[str, object],
        now: datetime,
    ) -> None:
        await uow.add_audit(
            NetworkingAuditEvent(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                actor_user_id=context.actor_user_id,
                action=action,
                target_kind=target_kind,
                target_id=target_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                metadata=cast(dict[str, object], _jsonable(metadata)),
                created_at=now,
            )
        )

    async def _active_contact(
        self,
        uow: NetworkingUnitOfWork,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingContact:
        contact = await uow.get_contact(owner_user_id, contact_id, for_update=for_update)
        if contact is None:
            raise NetworkingNotFound
        return contact

    async def _require_contact_storage(
        self, uow: NetworkingUnitOfWork, owner_user_id: UUID, contact_id: UUID
    ) -> NetworkingContact:
        contact = await self._active_contact(
            uow,
            owner_user_id,
            contact_id,
            for_update=True,
        )
        self._require_storage(
            _consent_state(await uow.get_latest_consent_events(owner_user_id, contact_id))
        )
        return contact

    @staticmethod
    def _require_storage(state: ContactConsentState) -> None:
        if not state.collection or not state.storage:
            raise NetworkingConsentRequired("active collection and storage consent are required")

    @staticmethod
    def _require_outreach(state: ContactConsentState) -> None:
        if not state.allows_outreach:
            raise NetworkingConsentRequired(
                "active collection, storage, and outreach consent are required"
            )

    @staticmethod
    def _actor(owner_user_id: UUID, context: RequestContext) -> None:
        if context.actor_user_id != owner_user_id:
            raise NetworkingNotFound
        if re.fullmatch(r"[0-9a-f]{32}", context.trace_id) is None:
            raise NetworkingValidationError(
                "trace ID must contain exactly 32 lowercase hexadecimal characters"
            )

    @staticmethod
    def _version(current: int, expected: int) -> None:
        if current != expected:
            raise NetworkingVersionConflict

    def _limit(self, limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= self._policy.max_page_size:
            raise NetworkingValidationError("page limit is out of range")

    def _child_limit(self, limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= self._policy.max_child_page_size:
            raise NetworkingValidationError("list limit is out of range")

    def _claim_limit(self, limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= self._policy.max_claim_batch:
            raise NetworkingValidationError("claim limit is out of range")

    @staticmethod
    def _quota(current: int, maximum: int, *, requested: int = 1) -> None:
        if current + requested > maximum:
            raise NetworkingQuotaExceeded

    @staticmethod
    def _idempotency_key(value: str) -> None:
        if not 8 <= len(value) <= 128 or re.fullmatch(r"[A-Za-z0-9._:-]+", value) is None:
            raise NetworkingValidationError("idempotency key is invalid")

    @staticmethod
    def _lease(
        entry: NetworkingReminderOutboxEntry | None,
        lease_token: UUID,
        now: datetime,
    ) -> NetworkingReminderOutboxEntry:
        if entry is None:
            raise NetworkingNotFound
        if (
            entry.status is not ReminderOutboxStatus.LEASED
            or entry.lease_token != lease_token
            or entry.lease_expires_at is None
            or entry.lease_expires_at <= now
        ):
            raise NetworkingLeaseConflict
        return entry


def _consent_state(events: list[NetworkingConsentEvent]) -> ContactConsentState:
    state = {
        ConsentPurpose.COLLECTION: False,
        ConsentPurpose.STORAGE: False,
        ConsentPurpose.OUTREACH: False,
    }
    for event in sorted(events, key=lambda item: item.sequence):
        state[event.purpose] = event.action is ConsentAction.GRANTED
    return ContactConsentState(
        collection=state[ConsentPurpose.COLLECTION],
        storage=state[ConsentPurpose.STORAGE],
        outreach=state[ConsentPurpose.OUTREACH],
    )


def _purpose_value(state: ContactConsentState, purpose: ConsentPurpose) -> bool:
    if purpose is ConsentPurpose.COLLECTION:
        return state.collection
    if purpose is ConsentPurpose.STORAGE:
        return state.storage
    return state.outreach


def _patch[T](requested: T | UnsetType, current: T) -> T:
    return current if isinstance(requested, UnsetType) else requested


def _query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_search(value)
    if not normalized:
        return None
    if len(normalized) < 2:
        raise NetworkingValidationError("search query must contain at least two characters")
    return normalized[:200]


def _tag(value: str | None) -> str | None:
    if value is None:
        return None
    tags = normalize_tags((value,))
    return tags[0] if tags else None


def _cursor_scope(
    owner_user_id: UUID,
    *,
    collection: str,
    sort: str,
    parent_id: UUID | None = None,
    filter_by: object | None = None,
) -> str:
    """Bind an opaque cursor to its owner and complete query semantics."""

    digest = _fingerprint(
        "networking_cursor_v2",
        {
            "collection": collection,
            "filter": filter_by,
            "owner_user_id": owner_user_id,
            "parent_id": parent_id,
            "sort": sort,
        },
    )
    return f"networking:v2:{digest}"


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NetworkingValidationError(f"{field_name} must include a timezone")


def _fingerprint(kind: str, value: object) -> str:
    payload = json.dumps(
        {"kind": kind, "value": _jsonable(value)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_consent_policy_version(value: str) -> None:
    if value != NETWORKING_CONTACT_CONSENT_POLICY_VERSION:
        raise NetworkingValidationError("consent policy version is not supported")


def _jsonable(value: object) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UnsetType):
        return {"unset": True}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported fingerprint value: {type(value)!r}")
