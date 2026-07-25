"""Authenticated HTTP delivery for the private, consent-based Networking CRM."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.networking.application import (
    UNSET,
    ChangeContactConsent,
    ContactFilter,
    CreateContact,
    CreateContactNote,
    CreateOrganization,
    CreateReferral,
    CreateReminder,
    CreateTemplate,
    NetworkingService,
    OrganizationFilter,
    RecordInteraction,
    ReminderResolutionAction,
    RequestContext,
    ResolveReminder,
    UpdateContact,
    UpdateOrganization,
    UpdateReferral,
    UpdateReminder,
    UpdateTemplate,
)
from careeros.modules.networking.domain import (
    ConsentPurpose,
    ContactReferralState,
    InteractionDirection,
    InteractionKind,
    ReferralStatus,
    RelationshipStage,
    ReminderStatus,
    TemplateKind,
)
from fastapi import APIRouter, Depends, Header, Query, Response, status

from careeros_api.conditional_requests import parse_if_match_version
from careeros_api.identity_dependencies import current_principal, require_authenticated_csrf
from careeros_api.identity_schemas import ProblemResponse

from .dependencies import networking_request_context, networking_service
from .presenters import (
    consent_history_response,
    contact_page_response,
    contact_response,
    due_reminder_list_response,
    interaction_list_response,
    interaction_response,
    note_list_response,
    note_response,
    organization_page_response,
    organization_response,
    referral_list_response,
    referral_response,
    reminder_execution_batch_response,
    reminder_execution_response,
    reminder_list_response,
    reminder_response,
    template_list_response,
    template_response,
)
from .schemas import (
    ConsentChangeRequest,
    ConsentHistoryResponse,
    ContactCreateRequest,
    ContactNoteCreateRequest,
    ContactNoteListResponse,
    ContactNoteResponse,
    ContactPageResponse,
    ContactResponse,
    ContactUpdateRequest,
    DueReminderListResponse,
    InteractionCreateRequest,
    InteractionListResponse,
    InteractionResponse,
    OrganizationCreateRequest,
    OrganizationPageResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
    ReferralCreateRequest,
    ReferralListResponse,
    ReferralResponse,
    ReferralUpdateRequest,
    ReminderCreateRequest,
    ReminderExecutionBatchResponse,
    ReminderExecutionResponse,
    ReminderListResponse,
    ReminderResolutionRequest,
    ReminderResponse,
    ReminderUpdateRequest,
    TemplateCreateRequest,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdateRequest,
)

router = APIRouter(prefix="/api/v1/networking", tags=["Networking"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": ProblemResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@router.get(
    "/organizations",
    response_model=OrganizationPageResponse,
    operation_id="networkingOrganizationsList",
    responses=_PROBLEMS,
)
async def list_organizations(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> OrganizationPageResponse:
    result = await service.list_organizations(
        principal.user_id,
        filter_by=OrganizationFilter(query=_clean(q), tag=_clean(tag)),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return organization_page_response(result)


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingOrganizationCreate",
    responses=_PROBLEMS,
)
async def create_organization(
    payload: OrganizationCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> OrganizationResponse:
    value = await service.create_organization(
        principal.user_id,
        CreateOrganization(
            name=payload.name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location,
            tags=tuple(payload.tags),
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return organization_response(value)


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationResponse,
    operation_id="networkingOrganizationGet",
    responses=_PROBLEMS,
)
async def get_organization(
    organization_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> OrganizationResponse:
    value = await service.get_organization(principal.user_id, organization_id)
    _private(response, value.version)
    return organization_response(value)


@router.patch(
    "/organizations/{organization_id}",
    response_model=OrganizationResponse,
    operation_id="networkingOrganizationUpdate",
    responses=_PROBLEMS,
)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> OrganizationResponse:
    value = await service.update_organization(
        principal.user_id,
        organization_id,
        UpdateOrganization(
            name=payload.name if payload.name is not None else UNSET,
            website=payload.website if "website" in payload.model_fields_set else UNSET,
            industry=payload.industry if "industry" in payload.model_fields_set else UNSET,
            location=payload.location if "location" in payload.model_fields_set else UNSET,
            tags=tuple(payload.tags)
            if "tags" in payload.model_fields_set and payload.tags is not None
            else UNSET,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return organization_response(value)


@router.delete(
    "/organizations/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="networkingOrganizationDelete",
    responses=_PROBLEMS,
)
async def delete_organization(
    organization_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> None:
    deleted = await service.delete_organization(
        principal.user_id,
        organization_id,
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, deleted.version)


@router.get(
    "/contacts",
    response_model=ContactPageResponse,
    operation_id="networkingContactsList",
    responses=_PROBLEMS,
)
async def list_contacts(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
    relationship_stage: Annotated[
        RelationshipStage | None, Query(alias="relationshipStage")
    ] = None,
    referral_state: Annotated[ContactReferralState | None, Query(alias="referralState")] = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    outreach_consent: Annotated[bool | None, Query(alias="outreachConsent")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ContactPageResponse:
    result = await service.list_contacts(
        principal.user_id,
        filter_by=ContactFilter(
            query=_clean(q),
            organization_id=organization_id,
            relationship_stage=relationship_stage,
            referral_state=referral_state,
            tag=_clean(tag),
            outreach_consent=outreach_consent,
        ),
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return contact_page_response(result)


@router.post(
    "/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingContactCreate",
    responses=_PROBLEMS,
)
async def create_contact(
    payload: ContactCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactResponse:
    value = await service.create_contact(
        principal.user_id,
        CreateContact(
            name=payload.name,
            organization_id=payload.organization_id,
            role=payload.role,
            email=payload.email,
            phone=payload.phone,
            profile_url=payload.profile_url,
            location=payload.location,
            relationship_stage=RelationshipStage(payload.relationship_stage),
            referral_state=ContactReferralState(payload.referral_state),
            tags=tuple(payload.tags),
            collection_attested=payload.consent.collection_attested,
            storage_attested=payload.consent.storage_attested,
            outreach_attested=payload.consent.outreach_attested,
            consent_policy_version=payload.consent.policy_version.value,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.contact.version)
    return contact_response(value)


@router.get(
    "/contacts/{contact_id}",
    response_model=ContactResponse,
    operation_id="networkingContactGet",
    responses=_PROBLEMS,
)
async def get_contact(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactResponse:
    value = await service.get_contact(principal.user_id, contact_id)
    _private(response, value.contact.version)
    return contact_response(value)


@router.patch(
    "/contacts/{contact_id}",
    response_model=ContactResponse,
    operation_id="networkingContactUpdate",
    responses=_PROBLEMS,
)
async def update_contact(
    contact_id: UUID,
    payload: ContactUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactResponse:
    value = await service.update_contact(
        principal.user_id,
        contact_id,
        UpdateContact(
            organization_id=payload.organization_id
            if "organization_id" in payload.model_fields_set
            else UNSET,
            name=payload.name if payload.name is not None else UNSET,
            role=payload.role if "role" in payload.model_fields_set else UNSET,
            email=payload.email if "email" in payload.model_fields_set else UNSET,
            phone=payload.phone if "phone" in payload.model_fields_set else UNSET,
            profile_url=payload.profile_url if "profile_url" in payload.model_fields_set else UNSET,
            location=payload.location if "location" in payload.model_fields_set else UNSET,
            relationship_stage=RelationshipStage(payload.relationship_stage)
            if payload.relationship_stage is not None
            else UNSET,
            referral_state=ContactReferralState(payload.referral_state)
            if payload.referral_state is not None
            else UNSET,
            tags=tuple(payload.tags) if payload.tags is not None else UNSET,
            next_contact_at=payload.next_contact_at
            if "next_contact_at" in payload.model_fields_set
            else UNSET,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.contact.version)
    return contact_response(value)


@router.delete(
    "/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="networkingContactDelete",
    responses=_PROBLEMS,
)
async def delete_contact(
    contact_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> None:
    deleted = await service.delete_contact(
        principal.user_id,
        contact_id,
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, deleted.version)


@router.get(
    "/contacts/{contact_id}/consent",
    response_model=ConsentHistoryResponse,
    operation_id="networkingContactConsentGet",
    responses=_PROBLEMS,
)
async def get_consent_history(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ConsentHistoryResponse:
    value = await service.get_consent_history(
        principal.user_id,
        contact_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return consent_history_response(value)


@router.post(
    "/contacts/{contact_id}/consent/grants",
    response_model=ContactResponse,
    operation_id="networkingContactConsentGrant",
    responses=_PROBLEMS,
)
async def grant_consent(
    contact_id: UUID,
    payload: ConsentChangeRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactResponse:
    value = await service.grant_consent(
        principal.user_id,
        contact_id,
        ChangeContactConsent(
            purpose=ConsentPurpose(payload.purpose),
            policy_version=payload.policy_version.value,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.contact.version)
    return contact_response(value)


@router.post(
    "/contacts/{contact_id}/consent/withdrawals",
    response_model=ContactResponse,
    operation_id="networkingContactConsentWithdraw",
    responses=_PROBLEMS,
)
async def withdraw_consent(
    contact_id: UUID,
    payload: ConsentChangeRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactResponse:
    value = await service.withdraw_consent(
        principal.user_id,
        contact_id,
        ChangeContactConsent(
            purpose=ConsentPurpose(payload.purpose),
            policy_version=payload.policy_version.value,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.contact.version)
    return contact_response(value)


@router.get(
    "/contacts/{contact_id}/notes",
    response_model=ContactNoteListResponse,
    operation_id="networkingContactNotesList",
    responses=_PROBLEMS,
)
async def list_notes(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ContactNoteListResponse:
    values = await service.list_notes(
        principal.user_id,
        contact_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return note_list_response(values)


@router.post(
    "/contacts/{contact_id}/notes",
    response_model=ContactNoteResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingContactNoteCreate",
    responses=_PROBLEMS,
)
async def create_note(
    contact_id: UUID,
    payload: ContactNoteCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ContactNoteResponse:
    value = await service.create_note(
        principal.user_id,
        contact_id,
        CreateContactNote(body=payload.body),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return note_response(value)


@router.get(
    "/contacts/{contact_id}/interactions",
    response_model=InteractionListResponse,
    operation_id="networkingContactInteractionsList",
    responses=_PROBLEMS,
)
async def list_interactions(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> InteractionListResponse:
    values = await service.list_interactions(
        principal.user_id,
        contact_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return interaction_list_response(values)


@router.post(
    "/contacts/{contact_id}/interactions",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingContactInteractionRecord",
    responses=_PROBLEMS,
)
async def record_interaction(
    contact_id: UUID,
    payload: InteractionCreateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> InteractionResponse:
    value = await service.record_interaction(
        principal.user_id,
        contact_id,
        RecordInteraction(
            kind=InteractionKind(payload.kind),
            direction=InteractionDirection(payload.direction),
            occurred_at=payload.occurred_at,
            summary=payload.summary,
            template_id=payload.template_id,
        ),
        expected_contact_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response)
    return interaction_response(value)


@router.get(
    "/contacts/{contact_id}/referrals",
    response_model=ReferralListResponse,
    operation_id="networkingContactReferralsList",
    responses=_PROBLEMS,
)
async def list_referrals(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ReferralListResponse:
    values = await service.list_referrals(
        principal.user_id,
        contact_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return referral_list_response(values)


@router.post(
    "/contacts/{contact_id}/referrals",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingContactReferralCreate",
    responses=_PROBLEMS,
)
async def create_referral(
    contact_id: UUID,
    payload: ReferralCreateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReferralResponse:
    value = await service.create_referral(
        principal.user_id,
        contact_id,
        CreateReferral(
            application_id=payload.application_id,
            status=ReferralStatus(payload.status),
            context=payload.context,
        ),
        expected_contact_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return referral_response(value)


@router.patch(
    "/referrals/{referral_id}",
    response_model=ReferralResponse,
    operation_id="networkingReferralUpdate",
    responses=_PROBLEMS,
)
async def update_referral(
    referral_id: UUID,
    payload: ReferralUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReferralResponse:
    value = await service.update_referral(
        principal.user_id,
        referral_id,
        UpdateReferral(
            status=ReferralStatus(payload.status) if payload.status is not None else UNSET,
            context=payload.context if "context" in payload.model_fields_set else UNSET,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return referral_response(value)


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    operation_id="networkingTemplatesList",
    responses=_PROBLEMS,
)
async def list_templates(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TemplateListResponse:
    values = await service.list_templates(
        principal.user_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return template_list_response(values)


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingTemplateCreate",
    responses=_PROBLEMS,
)
async def create_template(
    payload: TemplateCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> TemplateResponse:
    value = await service.create_template(
        principal.user_id,
        CreateTemplate(
            kind=TemplateKind(payload.kind),
            name=payload.name,
            body=payload.body,
            user_reviewed=payload.user_reviewed,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return template_response(value)


@router.patch(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    operation_id="networkingTemplateUpdate",
    responses=_PROBLEMS,
)
async def update_template(
    template_id: UUID,
    payload: TemplateUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> TemplateResponse:
    value = await service.update_template(
        principal.user_id,
        template_id,
        UpdateTemplate(
            kind=TemplateKind(payload.kind) if payload.kind is not None else UNSET,
            name=payload.name if payload.name is not None else UNSET,
            body=payload.body if payload.body is not None else UNSET,
            user_reviewed=payload.user_reviewed,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return template_response(value)


@router.get(
    "/contacts/{contact_id}/reminders",
    response_model=ReminderListResponse,
    operation_id="networkingContactRemindersList",
    responses=_PROBLEMS,
)
async def list_reminders(
    contact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ReminderListResponse:
    values = await service.list_reminders(
        principal.user_id,
        contact_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return reminder_list_response(values)


@router.post(
    "/contacts/{contact_id}/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="networkingContactReminderCreate",
    responses=_PROBLEMS,
)
async def create_reminder(
    contact_id: UUID,
    payload: ReminderCreateRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReminderResponse:
    value = await service.create_reminder(
        principal.user_id,
        contact_id,
        CreateReminder(
            title=payload.title,
            due_at=payload.due_at,
            recurrence_days=payload.recurrence_days,
            max_attempts=payload.max_attempts,
        ),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return reminder_response(value)


@router.get(
    "/reminders/due",
    response_model=DueReminderListResponse,
    operation_id="networkingDueRemindersList",
    responses=_PROBLEMS,
)
async def list_due_reminders(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DueReminderListResponse:
    values = await service.list_due_reminders(
        principal.user_id,
        cursor=cursor,
        limit=limit,
    )
    _private(response)
    return due_reminder_list_response(values)


@router.get(
    "/reminders/executions",
    response_model=ReminderExecutionBatchResponse,
    operation_id="networkingReminderExecutionsGet",
    responses=_PROBLEMS,
)
async def get_reminder_executions(
    response: Response,
    reminder_ids: Annotated[
        list[UUID],
        Query(alias="reminderId", min_length=1, max_length=100),
    ],
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReminderExecutionBatchResponse:
    values = await service.get_reminder_executions(
        principal.user_id,
        tuple(reminder_ids),
    )
    _private(response)
    return reminder_execution_batch_response(values)


@router.get(
    "/reminders/{reminder_id}/execution",
    response_model=ReminderExecutionResponse | None,
    operation_id="networkingReminderExecutionGet",
    responses=_PROBLEMS,
)
async def get_reminder_execution(
    reminder_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReminderExecutionResponse | None:
    value = await service.get_reminder_execution(principal.user_id, reminder_id)
    _private(response)
    return None if value is None else reminder_execution_response(value)


@router.post(
    "/reminders/{reminder_id}/actions",
    response_model=ReminderResponse,
    operation_id="networkingReminderResolve",
    responses=_PROBLEMS,
)
async def resolve_reminder(
    reminder_id: UUID,
    payload: ReminderResolutionRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReminderResponse:
    value = await service.resolve_reminder(
        principal.user_id,
        reminder_id,
        ResolveReminder(
            action=ReminderResolutionAction(payload.action),
            snooze_until=payload.snooze_until,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return reminder_response(value)


@router.patch(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
    operation_id="networkingReminderUpdate",
    responses=_PROBLEMS,
)
async def update_reminder(
    reminder_id: UUID,
    payload: ReminderUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: IdempotencyKey,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(networking_request_context)],
    service: Annotated[NetworkingService, Depends(networking_service)],
) -> ReminderResponse:
    value = await service.update_reminder(
        principal.user_id,
        reminder_id,
        UpdateReminder(
            title=payload.title if payload.title is not None else UNSET,
            due_at=payload.due_at if payload.due_at is not None else UNSET,
            recurrence_days=payload.recurrence_days
            if "recurrence_days" in payload.model_fields_set
            else UNSET,
            status=ReminderStatus(payload.status) if payload.status is not None else UNSET,
        ),
        expected_version=parse_if_match_version(if_match),
        idempotency_key=idempotency_key,
        context=context,
    )
    _private(response, value.version)
    return reminder_response(value)
