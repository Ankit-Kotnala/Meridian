"""Presentation helpers for the private Networking CRM API."""

from __future__ import annotations

from uuid import UUID

from careeros.modules.networking.application import (
    ContactConsentHistory,
    ContactConsentState,
    ContactView,
    DueReminderView,
    PagedResult,
    ReminderExecutionView,
)
from careeros.modules.networking.domain import (
    NetworkingConsentEvent,
    NetworkingContactNote,
    NetworkingInteraction,
    NetworkingOrganization,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingTemplate,
)

from .schemas import (
    ConsentEventResponse,
    ConsentHistoryResponse,
    ConsentLedgerPolicyVersionValue,
    ConsentStateResponse,
    ContactNoteListResponse,
    ContactNoteResponse,
    ContactPageResponse,
    ContactResponse,
    DueReminderListResponse,
    DueReminderResponse,
    InteractionListResponse,
    InteractionResponse,
    OrganizationPageResponse,
    OrganizationResponse,
    PageResponse,
    ReferralListResponse,
    ReferralResponse,
    ReminderExecutionBatchResponse,
    ReminderExecutionItemResponse,
    ReminderExecutionResponse,
    ReminderListResponse,
    ReminderResponse,
    TemplateListResponse,
    TemplateResponse,
)


def page_response(limit: int, has_more: bool, next_cursor: str | None) -> PageResponse:
    return PageResponse(limit=limit, has_more=has_more, next_cursor=next_cursor)


def organization_response(value: NetworkingOrganization) -> OrganizationResponse:
    return OrganizationResponse(
        id=value.id,
        name=value.name,
        website=value.website,
        industry=value.industry,
        location=value.location,
        tags=list(value.tags),
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def organization_page_response(
    result: PagedResult[NetworkingOrganization],
) -> OrganizationPageResponse:
    return OrganizationPageResponse(
        data=[organization_response(item) for item in result.data],
        page=page_response(result.page.limit, result.page.has_more, result.page.next_cursor),
    )


def consent_state_response(value: ContactConsentState) -> ConsentStateResponse:
    return ConsentStateResponse(
        collection=value.collection,
        storage=value.storage,
        outreach=value.outreach,
        allows_outreach=value.allows_outreach,
    )


def contact_response(value: ContactView) -> ContactResponse:
    contact = value.contact
    return ContactResponse(
        id=contact.id,
        organization_id=contact.organization_id,
        name=contact.name,
        role=contact.role,
        email=contact.email,
        phone=contact.phone,
        profile_url=contact.profile_url,
        location=contact.location,
        relationship_stage=contact.relationship_stage.value,
        referral_state=contact.referral_state.value,
        tags=list(contact.tags),
        last_contact_at=contact.last_contact_at,
        next_contact_at=contact.next_contact_at,
        consent=consent_state_response(value.consent),
        version=contact.version,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


def contact_page_response(result: PagedResult[ContactView]) -> ContactPageResponse:
    return ContactPageResponse(
        data=[contact_response(item) for item in result.data],
        page=page_response(result.page.limit, result.page.has_more, result.page.next_cursor),
    )


def consent_event_response(value: NetworkingConsentEvent) -> ConsentEventResponse:
    return ConsentEventResponse(
        id=value.id,
        contact_id=value.contact_id,
        purpose=value.purpose.value,
        action=value.action.value,
        policy_version=ConsentLedgerPolicyVersionValue(value.policy_version),
        sequence=value.sequence,
        occurred_at=value.occurred_at,
    )


def consent_history_response(value: ContactConsentHistory) -> ConsentHistoryResponse:
    return ConsentHistoryResponse(
        current=consent_state_response(value.current),
        events=[consent_event_response(item) for item in value.events],
        page=page_response(
            value.page.limit,
            value.page.has_more,
            value.page.next_cursor,
        ),
    )


def note_response(value: NetworkingContactNote) -> ContactNoteResponse:
    return ContactNoteResponse(
        id=value.id,
        contact_id=value.contact_id,
        body=value.body,
        created_at=value.created_at,
    )


def note_list_response(
    result: PagedResult[NetworkingContactNote],
) -> ContactNoteListResponse:
    return ContactNoteListResponse(
        data=[note_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def interaction_response(value: NetworkingInteraction) -> InteractionResponse:
    return InteractionResponse(
        id=value.id,
        contact_id=value.contact_id,
        template_id=value.template_id,
        kind=value.kind.value,
        direction=value.direction.value,
        occurred_at=value.occurred_at,
        summary=value.summary,
        delivery_state="recorded_only",
        created_at=value.created_at,
    )


def interaction_list_response(
    result: PagedResult[NetworkingInteraction],
) -> InteractionListResponse:
    return InteractionListResponse(
        data=[interaction_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def referral_response(value: NetworkingReferral) -> ReferralResponse:
    return ReferralResponse(
        id=value.id,
        contact_id=value.contact_id,
        application_id=value.application_id,
        status=value.status.value,
        context=value.context,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def referral_list_response(
    result: PagedResult[NetworkingReferral],
) -> ReferralListResponse:
    return ReferralListResponse(
        data=[referral_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def template_response(value: NetworkingTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=value.id,
        kind=value.kind.value,
        name=value.name,
        body=value.body,
        reviewed_at=value.reviewed_at,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def template_list_response(
    result: PagedResult[NetworkingTemplate],
) -> TemplateListResponse:
    return TemplateListResponse(
        data=[template_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def reminder_response(value: NetworkingReminder) -> ReminderResponse:
    return ReminderResponse(
        id=value.id,
        contact_id=value.contact_id,
        title=value.title,
        due_at=value.due_at,
        recurrence_days=value.recurrence_days,
        max_attempts=value.max_attempts,
        status=value.status.value,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def reminder_execution_response(
    value: ReminderExecutionView,
) -> ReminderExecutionResponse:
    return ReminderExecutionResponse(
        occurrence_id=value.occurrence_id,
        occurrence_number=value.occurrence_number,
        scheduled_for=value.scheduled_for,
        occurrence_status=value.occurrence_status.value,
        attempt_count=value.attempt_count,
        max_attempts=value.max_attempts,
        queue_status=value.queue_status.value,
        last_error_code=value.last_error_code,
    )


def reminder_execution_batch_response(
    values: dict[UUID, ReminderExecutionView],
) -> ReminderExecutionBatchResponse:
    return ReminderExecutionBatchResponse(
        data=[
            ReminderExecutionItemResponse(
                reminder_id=reminder_id,
                execution=reminder_execution_response(execution),
            )
            for reminder_id, execution in values.items()
        ]
    )


def due_reminder_list_response(
    result: PagedResult[DueReminderView],
) -> DueReminderListResponse:
    return DueReminderListResponse(
        data=[
            DueReminderResponse(
                reminder=reminder_response(item.reminder),
                execution=reminder_execution_response(item.execution),
            )
            for item in result.data
        ],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def reminder_list_response(
    result: PagedResult[NetworkingReminder],
) -> ReminderListResponse:
    return ReminderListResponse(
        data=[reminder_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )
