"""Focused HTTP contract tests for the private Networking CRM."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.networking.application import (
    UNSET,
    ContactConsentHistory,
    ContactConsentState,
    ContactView,
    DueReminderView,
    NetworkingService,
    Page,
    PagedResult,
    ReminderExecutionView,
    ReminderResolutionAction,
)
from careeros.modules.networking.domain import (
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NETWORKING_CONTACT_DELETION_POLICY_VERSION,
    ConsentAction,
    ConsentPurpose,
    ContactReferralState,
    InteractionDeliveryState,
    InteractionDirection,
    InteractionKind,
    NetworkingConsentEvent,
    NetworkingContact,
    NetworkingContactNote,
    NetworkingInteraction,
    NetworkingNotFound,
    NetworkingOrganization,
    NetworkingQuotaExceeded,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingTemplate,
    NetworkingValidationError,
    ReferralStatus,
    RelationshipStage,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
    ReminderStatus,
    TemplateKind,
)
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_NOW = datetime(2026, 7, 25, 4, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class NetworkingSample:
    owner_id: UUID
    other_id: UUID
    organization: NetworkingOrganization
    contact: ContactView
    consent_history: ContactConsentHistory
    note: NetworkingContactNote
    interaction: NetworkingInteraction
    referral: NetworkingReferral
    template: NetworkingTemplate
    reminder: NetworkingReminder
    reminder_execution: ReminderExecutionView


def _principal(user_id: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _sample() -> NetworkingSample:
    owner_id = uuid4()
    organization = NetworkingOrganization(
        id=uuid4(),
        owner_user_id=owner_id,
        name="Acme Product",
        website="https://example.test",
        industry="Software",
        location="Remote",
        tags=("product",),
        normalized_search="acme product software remote",
        version=3,
        created_at=_NOW,
        updated_at=_NOW,
    )
    contact = NetworkingContact(
        id=uuid4(),
        owner_user_id=owner_id,
        organization_id=organization.id,
        name="Alex Example",
        role="Director of Product",
        email="alex@example.test",
        phone=None,
        profile_url="https://example.test/alex",
        location="Remote",
        relationship_stage=RelationshipStage.WARM,
        referral_state=ContactReferralState.CONSIDERING,
        tags=("product",),
        normalized_search="alex example director of product",
        last_contact_at=_NOW,
        next_contact_at=_NOW,
        version=4,
        created_at=_NOW,
        updated_at=_NOW,
    )
    events = tuple(
        NetworkingConsentEvent(
            id=uuid4(),
            owner_user_id=owner_id,
            contact_id=contact.id,
            purpose=purpose,
            action=ConsentAction.GRANTED,
            policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            actor_user_id=owner_id,
            sequence=index,
            occurred_at=_NOW,
        )
        for index, purpose in enumerate(ConsentPurpose, start=1)
    )
    consent = ContactConsentState(collection=True, storage=True, outreach=True)
    note = NetworkingContactNote(
        id=uuid4(),
        owner_user_id=owner_id,
        contact_id=contact.id,
        body="Met at an explicitly recorded product event.",
        created_at=_NOW,
    )
    interaction = NetworkingInteraction(
        id=uuid4(),
        owner_user_id=owner_id,
        contact_id=contact.id,
        template_id=None,
        kind=InteractionKind.MEETING,
        direction=InteractionDirection.MUTUAL,
        occurred_at=_NOW,
        summary="Recorded a completed conversation.",
        delivery_state=InteractionDeliveryState.RECORDED_ONLY,
        created_at=_NOW,
    )
    referral = NetworkingReferral(
        id=uuid4(),
        owner_user_id=owner_id,
        contact_id=contact.id,
        application_id=uuid4(),
        status=ReferralStatus.PLANNED,
        context="User-reviewed referral context.",
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    template = NetworkingTemplate(
        id=uuid4(),
        owner_user_id=owner_id,
        kind=TemplateKind.FOLLOW_UP,
        name="Thank-you follow-up",
        body="A user-reviewed local draft.",
        reviewed_at=_NOW,
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    reminder = NetworkingReminder(
        id=uuid4(),
        owner_user_id=owner_id,
        contact_id=contact.id,
        title="Review whether to follow up",
        due_at=_NOW,
        recurrence_days=30,
        max_attempts=5,
        status=ReminderStatus.ACTIVE,
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    reminder_execution = ReminderExecutionView(
        occurrence_id=uuid4(),
        occurrence_number=2,
        scheduled_for=_NOW,
        occurrence_status=ReminderOccurrenceStatus.SCHEDULED,
        attempt_count=1,
        max_attempts=5,
        queue_status=ReminderOutboxStatus.PENDING,
        last_error_code="lease_expired",
    )
    return NetworkingSample(
        owner_id=owner_id,
        other_id=uuid4(),
        organization=organization,
        contact=ContactView(contact=contact, consent=consent),
        consent_history=ContactConsentHistory(
            current=consent,
            events=events,
            page=Page(limit=100, has_more=False, next_cursor=None),
        ),
        note=note,
        interaction=interaction,
        referral=referral,
        template=template,
        reminder=reminder,
        reminder_execution=reminder_execution,
    )


def _services(sample: NetworkingSample) -> tuple[IdentityService, NetworkingService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(sample.owner_id)
    service = create_autospec(NetworkingService, instance=True)
    service.list_organizations.return_value = PagedResult(
        data=(sample.organization,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.get_organization.return_value = sample.organization
    service.create_organization.return_value = sample.organization
    service.update_organization.return_value = sample.organization
    service.delete_organization.return_value = sample.organization
    service.list_contacts.return_value = PagedResult(
        data=(sample.contact,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.get_contact.return_value = sample.contact
    service.create_contact.return_value = sample.contact
    service.update_contact.return_value = sample.contact
    service.delete_contact.return_value = sample.contact.contact
    service.get_consent_history.return_value = sample.consent_history
    service.grant_consent.return_value = sample.contact
    service.withdraw_consent.return_value = sample.contact
    service.list_notes.return_value = PagedResult(
        data=(sample.note,),
        page=Page(limit=100, has_more=False, next_cursor=None),
    )
    service.create_note.return_value = sample.note
    service.list_interactions.return_value = PagedResult(
        data=(sample.interaction,),
        page=Page(limit=100, has_more=False, next_cursor=None),
    )
    service.record_interaction.return_value = sample.interaction
    service.list_referrals.return_value = PagedResult(
        data=(sample.referral,),
        page=Page(limit=100, has_more=False, next_cursor=None),
    )
    service.create_referral.return_value = sample.referral
    service.update_referral.return_value = sample.referral
    service.list_templates.return_value = PagedResult(
        data=(sample.template,),
        page=Page(limit=100, has_more=False, next_cursor=None),
    )
    service.create_template.return_value = sample.template
    service.update_template.return_value = sample.template
    service.list_reminders.return_value = PagedResult(
        data=(sample.reminder,),
        page=Page(limit=100, has_more=False, next_cursor=None),
    )
    service.create_reminder.return_value = sample.reminder
    service.update_reminder.return_value = sample.reminder
    service.get_reminder_execution.return_value = sample.reminder_execution
    service.get_reminder_executions.return_value = {sample.reminder.id: sample.reminder_execution}
    service.list_due_reminders.return_value = PagedResult(
        data=(
            DueReminderView(
                reminder=sample.reminder,
                execution=replace(
                    sample.reminder_execution,
                    occurrence_status=ReminderOccurrenceStatus.DUE,
                    queue_status=ReminderOutboxStatus.PROCESSED,
                ),
            ),
        ),
        page=Page(limit=50, has_more=False, next_cursor=None),
    )
    service.resolve_reminder.return_value = sample.reminder
    return identity, service


def _write_headers(
    *,
    version: int | None = None,
    idempotency: str | None = None,
) -> dict[str, str]:
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        **({"If-Match": f'"{version}"'} if version is not None else {}),
        **({"Idempotency-Key": idempotency} if idempotency is not None else {}),
    }


def _client(
    settings: Settings,
    database: FakeDatabase,
    identity: IdentityService,
    service: NetworkingService,
) -> TestClient:
    application = create_app(
        settings,
        database=database,
        identity=identity,
        networking=service,
    )
    client = TestClient(application)
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def test_networking_complete_owner_scoped_http_workflow(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    contact_id = sample.contact.contact.id

    with _client(settings, fake_database, identity, service) as client:
        organizations = client.get(
            "/api/v1/networking/organizations",
            params={"q": " Acme ", "tag": " Product ", "limit": 25},
        )
        assert organizations.status_code == 200
        assert organizations.headers["Cache-Control"] == "no-store"
        assert organizations.json()["data"][0]["name"] == "Acme Product"
        organization_filter = service.list_organizations.await_args.kwargs["filter_by"]
        assert organization_filter.query == "Acme"
        assert organization_filter.tag == "Product"

        created_organization = client.post(
            "/api/v1/networking/organizations",
            json={
                "name": "Acme Product",
                "website": "https://example.test",
                "tags": ["product"],
            },
            headers=_write_headers(idempotency="networking-org-create"),
        )
        assert created_organization.status_code == 201
        assert created_organization.headers["ETag"] == '"3"'
        assert service.create_organization.await_args.kwargs["idempotency_key"] == (
            "networking-org-create"
        )

        organization = client.get(f"/api/v1/networking/organizations/{sample.organization.id}")
        assert organization.status_code == 200
        assert organization.headers["ETag"] == '"3"'
        service.get_organization.assert_awaited_with(sample.owner_id, sample.organization.id)

        updated_organization = client.patch(
            f"/api/v1/networking/organizations/{sample.organization.id}",
            json={"website": None, "tags": []},
            headers=_write_headers(version=3, idempotency="networking-org-update"),
        )
        assert updated_organization.status_code == 200
        organization_command = service.update_organization.await_args.args[2]
        assert organization_command.website is None
        assert organization_command.tags == ()
        assert organization_command.name is UNSET

        deleted_organization = client.delete(
            f"/api/v1/networking/organizations/{sample.organization.id}",
            headers=_write_headers(version=3, idempotency="networking-org-delete"),
        )
        assert deleted_organization.status_code == 204
        assert deleted_organization.headers["ETag"] == '"3"'
        service.delete_organization.assert_awaited_once()

        contacts = client.get(
            "/api/v1/networking/contacts",
            params={
                "q": " Alex ",
                "organizationId": str(sample.organization.id),
                "relationshipStage": "warm",
                "referralState": "considering",
                "tag": " Product ",
                "outreachConsent": "true",
                "limit": 25,
            },
        )
        assert contacts.status_code == 200
        assert contacts.json()["data"][0]["consent"]["allowsOutreach"] is True
        contact_filter = service.list_contacts.await_args.kwargs["filter_by"]
        assert contact_filter.query == "Alex"
        assert contact_filter.organization_id == sample.organization.id
        assert contact_filter.relationship_stage is RelationshipStage.WARM
        assert contact_filter.outreach_consent is True

        created_contact = client.post(
            "/api/v1/networking/contacts",
            json={
                "name": "Alex Example",
                "organizationId": str(sample.organization.id),
                "email": "alex@example.test",
                "relationshipStage": "warm",
                "tags": ["product"],
                "consent": {
                    "collectionAttested": True,
                    "storageAttested": True,
                    "outreachAttested": False,
                    "policyVersion": NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                },
            },
            headers=_write_headers(idempotency="networking-contact-create"),
        )
        assert created_contact.status_code == 201
        create_contact_command = service.create_contact.await_args.args[1]
        assert create_contact_command.collection_attested is True
        assert create_contact_command.storage_attested is True
        assert create_contact_command.outreach_attested is False

        contact = client.get(f"/api/v1/networking/contacts/{contact_id}")
        assert contact.status_code == 200
        assert contact.headers["ETag"] == '"4"'
        assert "ownerUserId" not in contact.json()

        updated_contact = client.patch(
            f"/api/v1/networking/contacts/{contact_id}",
            json={"email": None, "relationshipStage": "active", "nextContactAt": None},
            headers=_write_headers(version=4, idempotency="networking-contact-update"),
        )
        assert updated_contact.status_code == 200
        contact_command = service.update_contact.await_args.args[2]
        assert contact_command.email is None
        assert contact_command.relationship_stage is RelationshipStage.ACTIVE
        assert contact_command.next_contact_at is None
        assert contact_command.name is UNSET

        consent = client.get(
            f"/api/v1/networking/contacts/{contact_id}/consent",
            params={"cursor": "opaque-consent-page", "limit": 25},
        )
        assert consent.status_code == 200
        assert consent.json()["page"] == {
            "limit": 100,
            "hasMore": False,
            "nextCursor": None,
        }
        assert [event["purpose"] for event in consent.json()["events"]] == [
            "collection",
            "storage",
            "outreach",
        ]
        assert all("actorUserId" not in event for event in consent.json()["events"])
        service.get_consent_history.assert_awaited_with(
            sample.owner_id,
            contact_id,
            cursor="opaque-consent-page",
            limit=25,
        )

        granted = client.post(
            f"/api/v1/networking/contacts/{contact_id}/consent/grants",
            json={
                "purpose": "outreach",
                "policyVersion": NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            },
            headers=_write_headers(version=4, idempotency="networking-consent-grant"),
        )
        assert granted.status_code == 200
        assert service.grant_consent.await_args.args[2].purpose is ConsentPurpose.OUTREACH

        withdrawn = client.post(
            f"/api/v1/networking/contacts/{contact_id}/consent/withdrawals",
            json={
                "purpose": "outreach",
                "policyVersion": NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            },
            headers=_write_headers(version=4, idempotency="networking-consent-withdraw"),
        )
        assert withdrawn.status_code == 200
        assert service.withdraw_consent.await_args.kwargs["expected_version"] == 4

        notes = client.get(
            f"/api/v1/networking/contacts/{contact_id}/notes",
            params={"cursor": "opaque-note-page", "limit": 25},
        )
        assert notes.status_code == 200
        assert notes.json()["data"][0]["body"].startswith("Met at")
        assert notes.json()["page"]["hasMore"] is False
        service.list_notes.assert_awaited_with(
            sample.owner_id,
            contact_id,
            cursor="opaque-note-page",
            limit=25,
        )
        created_note = client.post(
            f"/api/v1/networking/contacts/{contact_id}/notes",
            json={"body": "A private, user-recorded note."},
            headers=_write_headers(idempotency="networking-note-create"),
        )
        assert created_note.status_code == 201

        interactions = client.get(f"/api/v1/networking/contacts/{contact_id}/interactions")
        assert interactions.status_code == 200
        assert interactions.json()["data"][0]["deliveryState"] == "recorded_only"
        recorded = client.post(
            f"/api/v1/networking/contacts/{contact_id}/interactions",
            json={
                "kind": "meeting",
                "direction": "mutual",
                "occurredAt": "2026-07-25T04:00:00Z",
                "summary": "Recorded a completed conversation.",
            },
            headers=_write_headers(version=4, idempotency="networking-interaction"),
        )
        assert recorded.status_code == 201
        assert recorded.json()["deliveryState"] == "recorded_only"
        assert service.record_interaction.await_args.kwargs["expected_contact_version"] == 4

        referrals = client.get(f"/api/v1/networking/contacts/{contact_id}/referrals")
        assert referrals.status_code == 200
        created_referral = client.post(
            f"/api/v1/networking/contacts/{contact_id}/referrals",
            json={
                "applicationId": str(sample.referral.application_id),
                "status": "planned",
                "context": "User-reviewed referral context.",
            },
            headers=_write_headers(version=4, idempotency="networking-referral-create"),
        )
        assert created_referral.status_code == 201
        updated_referral = client.patch(
            f"/api/v1/networking/referrals/{sample.referral.id}",
            json={"status": "cancelled", "context": None},
            headers=_write_headers(version=2, idempotency="networking-referral-update"),
        )
        assert updated_referral.status_code == 200
        referral_command = service.update_referral.await_args.args[2]
        assert referral_command.status is ReferralStatus.CANCELLED
        assert referral_command.context is None

        templates = client.get("/api/v1/networking/templates")
        assert templates.status_code == 200
        assert templates.json()["data"][0]["body"].startswith("A user-reviewed")
        created_template = client.post(
            "/api/v1/networking/templates",
            json={
                "kind": "follow_up",
                "name": "Thank-you follow-up",
                "body": "A user-reviewed local draft.",
                "userReviewed": True,
            },
            headers=_write_headers(idempotency="networking-template-create"),
        )
        assert created_template.status_code == 201
        updated_template = client.patch(
            f"/api/v1/networking/templates/{sample.template.id}",
            json={
                "body": "An edited and reviewed local draft.",
                "userReviewed": True,
            },
            headers=_write_headers(version=2, idempotency="networking-template-update"),
        )
        assert updated_template.status_code == 200
        assert service.update_template.await_args.args[2].name is UNSET

        reminders = client.get(f"/api/v1/networking/contacts/{contact_id}/reminders")
        assert reminders.status_code == 200
        created_reminder = client.post(
            f"/api/v1/networking/contacts/{contact_id}/reminders",
            json={
                "title": "Review whether to follow up",
                "dueAt": "2026-07-25T04:00:00Z",
                "recurrenceDays": 30,
            },
            headers=_write_headers(idempotency="networking-reminder-create"),
        )
        assert created_reminder.status_code == 201
        due = client.get("/api/v1/networking/reminders/due")
        assert due.status_code == 200
        assert due.json()["data"][0]["execution"]["occurrenceStatus"] == "due"
        assert due.json()["data"][0]["reminder"]["id"] == str(sample.reminder.id)
        batch = client.get(
            "/api/v1/networking/reminders/executions",
            params=[("reminderId", str(sample.reminder.id))],
        )
        assert batch.status_code == 200
        assert batch.json()["data"] == [
            {
                "reminderId": str(sample.reminder.id),
                "execution": {
                    "occurrenceId": str(sample.reminder_execution.occurrence_id),
                    "occurrenceNumber": 2,
                    "scheduledFor": "2026-07-25T04:00:00Z",
                    "occurrenceStatus": "scheduled",
                    "attemptCount": 1,
                    "maxAttempts": 5,
                    "queueStatus": "pending",
                    "lastErrorCode": "lease_expired",
                },
            }
        ]
        resolved = client.post(
            f"/api/v1/networking/reminders/{sample.reminder.id}/actions",
            json={
                "action": "snooze",
                "snoozeUntil": (_NOW + timedelta(days=1)).isoformat(),
            },
            headers=_write_headers(
                version=sample.reminder.version,
                idempotency="networking-reminder-snooze",
            ),
        )
        assert resolved.status_code == 200
        resolution = service.resolve_reminder.await_args.args[2]
        assert resolution.action is ReminderResolutionAction.SNOOZE
        assert resolution.snooze_until == _NOW + timedelta(days=1)
        execution = client.get(f"/api/v1/networking/reminders/{sample.reminder.id}/execution")
        assert execution.status_code == 200
        assert execution.headers["Cache-Control"] == "no-store"
        assert execution.json() == {
            "occurrenceId": str(sample.reminder_execution.occurrence_id),
            "occurrenceNumber": 2,
            "scheduledFor": "2026-07-25T04:00:00Z",
            "occurrenceStatus": "scheduled",
            "attemptCount": 1,
            "maxAttempts": 5,
            "queueStatus": "pending",
            "lastErrorCode": "lease_expired",
        }
        assert {
            "leaseToken",
            "leaseExpiresAt",
            "contactId",
            "message",
            "destination",
        }.isdisjoint(execution.json())
        service.get_reminder_execution.assert_awaited_with(
            sample.owner_id,
            sample.reminder.id,
        )
        service.get_reminder_execution.return_value = None
        missing_execution = client.get(
            f"/api/v1/networking/reminders/{sample.reminder.id}/execution"
        )
        assert missing_execution.status_code == 200
        assert missing_execution.headers["Cache-Control"] == "no-store"
        assert missing_execution.json() is None
        updated_reminder = client.patch(
            f"/api/v1/networking/reminders/{sample.reminder.id}",
            json={"recurrenceDays": None, "status": "completed"},
            headers=_write_headers(version=2, idempotency="networking-reminder-update"),
        )
        assert updated_reminder.status_code == 200
        reminder_command = service.update_reminder.await_args.args[2]
        assert reminder_command.recurrence_days is None
        assert reminder_command.status is ReminderStatus.COMPLETED

        deleted_contact = client.delete(
            f"/api/v1/networking/contacts/{contact_id}",
            headers=_write_headers(version=4, idempotency="networking-contact-delete"),
        )
        assert deleted_contact.status_code == 204
        assert service.delete_contact.await_args.kwargs["expected_version"] == 4


def test_networking_mutations_require_csrf_and_explicit_safe_inputs(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    contact_id = sample.contact.contact.id

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/networking/contacts",
            json={
                "name": "Alex Example",
                "consent": {
                    "collectionAttested": True,
                    "storageAttested": True,
                    "policyVersion": NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                },
            },
            headers={"Idempotency-Key": "networking-contact-create"},
        )
        assert missing_csrf.status_code == 403
        service.create_contact.assert_not_awaited()

        missing_attestation = client.post(
            "/api/v1/networking/contacts",
            json={
                "name": "Alex Example",
                "consent": {
                    "collectionAttested": True,
                    "storageAttested": False,
                    "policyVersion": NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                },
            },
            headers=_write_headers(idempotency="networking-contact-invalid"),
        )
        assert missing_attestation.status_code == 422
        service.create_contact.assert_not_awaited()

        smuggled_policy_pii = "private.person@example.test"
        invalid_policy = client.post(
            "/api/v1/networking/contacts",
            json={
                "name": "Alex Example",
                "consent": {
                    "collectionAttested": True,
                    "storageAttested": True,
                    "policyVersion": smuggled_policy_pii,
                },
            },
            headers=_write_headers(idempotency="networking-contact-policy-invalid"),
        )
        assert invalid_policy.status_code == 422
        service.create_contact.assert_not_awaited()

        invalid_withdrawal_policy = client.post(
            f"/api/v1/networking/contacts/{contact_id}/consent/withdrawals",
            json={
                "purpose": "outreach",
                "policyVersion": smuggled_policy_pii,
            },
            headers=_write_headers(
                version=4,
                idempotency="networking-withdraw-policy-invalid",
            ),
        )
        assert invalid_withdrawal_policy.status_code == 422
        service.withdraw_consent.assert_not_awaited()

        naive_interaction_time = client.post(
            f"/api/v1/networking/contacts/{contact_id}/interactions",
            json={
                "kind": "message",
                "direction": "outbound",
                "occurredAt": "2026-07-25T04:00:00",
                "summary": "This is only a record.",
            },
            headers=_write_headers(version=4, idempotency="networking-naive-time"),
        )
        assert naive_interaction_time.status_code == 422
        service.record_interaction.assert_not_awaited()

        unreviewed_template = client.post(
            "/api/v1/networking/templates",
            json={
                "kind": "follow_up",
                "name": "Unreviewed",
                "body": "Draft",
                "userReviewed": False,
            },
            headers=_write_headers(idempotency="networking-template-invalid"),
        )
        assert unreviewed_template.status_code == 422
        service.create_template.assert_not_awaited()

        empty_patch = client.patch(
            f"/api/v1/networking/contacts/{contact_id}",
            json={},
            headers=_write_headers(version=4, idempotency="networking-empty-patch"),
        )
        assert empty_patch.status_code == 422
        service.update_contact.assert_not_awaited()

        missing_idempotency = client.delete(
            f"/api/v1/networking/contacts/{contact_id}",
            headers=_write_headers(version=4),
        )
        assert missing_idempotency.status_code == 422
        service.delete_contact.assert_not_awaited()

        service.list_notes.side_effect = NetworkingValidationError("cursor is invalid")
        invalid_cursor = client.get(
            f"/api/v1/networking/contacts/{contact_id}/notes",
            params={"cursor": "é"},
        )
        assert invalid_cursor.status_code == 422
        assert invalid_cursor.json()["code"] == "networking_validation_failed"


def test_networking_cross_owner_is_forwarded_to_owner_scoped_service_and_hidden(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    identity.authenticate.return_value = _principal(sample.other_id)
    service.get_contact.side_effect = NetworkingNotFound
    service.get_reminder_execution.side_effect = NetworkingNotFound

    with _client(settings, fake_database, identity, service) as client:
        hidden = client.get(f"/api/v1/networking/contacts/{sample.contact.contact.id}")
        hidden_execution = client.get(
            f"/api/v1/networking/reminders/{sample.reminder.id}/execution"
        )

    assert hidden.status_code == 404
    assert hidden.json()["code"] == "networking_not_found"
    assert hidden_execution.status_code == 404
    assert hidden_execution.json()["code"] == "networking_not_found"
    service.get_contact.assert_awaited_once_with(sample.other_id, sample.contact.contact.id)
    service.get_reminder_execution.assert_awaited_once_with(
        sample.other_id,
        sample.reminder.id,
    )


def test_networking_quota_exceeded_is_a_safe_429_problem(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    service.create_note.side_effect = NetworkingQuotaExceeded

    with _client(settings, fake_database, identity, service) as client:
        response = client.post(
            f"/api/v1/networking/contacts/{sample.contact.contact.id}/notes",
            json={"body": "A bounded private note."},
            headers=_write_headers(idempotency="networking-note-quota"),
        )

    assert response.status_code == 429
    assert response.json()["code"] == "networking_quota_exceeded"
    assert response.json()["detail"] == (
        "This networking collection has reached its safe storage limit."
    )
    assert all(str(value) not in response.json()["detail"] for value in (100, 200, 500, 5000))


def test_networking_openapi_has_no_sending_scraping_import_or_worker_surface(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        document = client.get("/openapi.json").json()

    networking_paths = {
        path: methods
        for path, methods in document["paths"].items()
        if path.startswith("/api/v1/networking")
    }
    assert document["components"]["schemas"]["ConsentPolicyVersionValue"]["enum"] == [
        NETWORKING_CONTACT_CONSENT_POLICY_VERSION
    ]
    assert set(document["components"]["schemas"]["ConsentLedgerPolicyVersionValue"]["enum"]) == {
        NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
        NETWORKING_CONTACT_DELETION_POLICY_VERSION,
    }
    required = {
        "/api/v1/networking/organizations",
        "/api/v1/networking/organizations/{organization_id}",
        "/api/v1/networking/contacts",
        "/api/v1/networking/contacts/{contact_id}",
        "/api/v1/networking/contacts/{contact_id}/consent",
        "/api/v1/networking/contacts/{contact_id}/consent/grants",
        "/api/v1/networking/contacts/{contact_id}/consent/withdrawals",
        "/api/v1/networking/contacts/{contact_id}/notes",
        "/api/v1/networking/contacts/{contact_id}/interactions",
        "/api/v1/networking/contacts/{contact_id}/referrals",
        "/api/v1/networking/referrals/{referral_id}",
        "/api/v1/networking/templates",
        "/api/v1/networking/templates/{template_id}",
        "/api/v1/networking/contacts/{contact_id}/reminders",
        "/api/v1/networking/reminders/{reminder_id}",
        "/api/v1/networking/reminders/{reminder_id}/actions",
        "/api/v1/networking/reminders/{reminder_id}/execution",
        "/api/v1/networking/reminders/due",
        "/api/v1/networking/reminders/executions",
    }
    assert required == set(networking_paths)
    forbidden = {"send", "deliver", "scrape", "import", "claim", "lease", "outbox"}
    assert all(not any(term in path.casefold() for term in forbidden) for path in networking_paths)
    organization_methods = networking_paths["/api/v1/networking/organizations/{organization_id}"]
    contact_methods = networking_paths["/api/v1/networking/contacts/{contact_id}"]
    assert {"get", "patch", "delete"}.issubset(organization_methods)
    assert {"get", "patch", "delete"}.issubset(contact_methods)
    for methods in networking_paths.values():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            assert {"413", "429"}.issubset(operation["responses"])

    paged_get_paths = {
        "/api/v1/networking/contacts/{contact_id}/consent",
        "/api/v1/networking/contacts/{contact_id}/notes",
        "/api/v1/networking/contacts/{contact_id}/interactions",
        "/api/v1/networking/contacts/{contact_id}/referrals",
        "/api/v1/networking/templates",
        "/api/v1/networking/contacts/{contact_id}/reminders",
        "/api/v1/networking/reminders/due",
    }
    for path in paged_get_paths:
        query_parameters = {
            parameter["name"]
            for parameter in networking_paths[path]["get"]["parameters"]
            if parameter["in"] == "query"
        }
        assert {"cursor", "limit"}.issubset(query_parameters)

    schemas = document["components"]["schemas"]
    assert schemas["InteractionResponse"]["properties"]["deliveryState"]["const"] == (
        "recorded_only"
    )
    assert set(schemas["ReminderExecutionResponse"]["properties"]) == {
        "occurrenceId",
        "occurrenceNumber",
        "scheduledFor",
        "occurrenceStatus",
        "attemptCount",
        "maxAttempts",
        "queueStatus",
        "lastErrorCode",
    }
    serialized_schemas = str(schemas)
    assert "ownerUserId" not in serialized_schemas
    assert "actorUserId" not in serialized_schemas
    for schema_name in (
        "ConsentHistoryResponse",
        "ContactNoteListResponse",
        "InteractionListResponse",
        "ReferralListResponse",
        "TemplateListResponse",
        "ReminderListResponse",
        "DueReminderListResponse",
    ):
        assert "page" in schemas[schema_name]["properties"]
