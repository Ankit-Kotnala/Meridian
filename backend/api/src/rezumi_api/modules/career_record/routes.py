"""Authenticated HTTP delivery for Phase 3 Career Record use cases."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from rezumi.modules.career_record.application import (
    AcceptSemanticImportProposal,
    CareerEntityData,
    CareerRecordService,
    CreateAchievement,
    CreateEvidence,
    CreateImportProposal,
    CreatePersonalFact,
    CreateSemanticImportProposals,
    CreateSkill,
    EvidenceFilter,
    LinkCareerEntityRelationship,
    MetricInput,
    ProposalFilter,
    RequestContext,
    ResumeSourceLocator,
    ReviseEvidence,
    UpdateAchievement,
    UpdateCareerProfile,
    UpdatePersonalFact,
    UpdateReminderPreferences,
    UpdateSkill,
)
from rezumi.modules.career_record.application.attachment_workflow import (
    AdmitAttachment,
    AttachmentDownloadPurpose,
    AttachmentRequestContext,
    AttachmentWorkflowService,
)
from rezumi.modules.career_record.application.declared_profile_jobs import (
    DeclaredProfileEnrichmentJobService,
    DeclaredProfileEnrichmentJobView,
)
from rezumi.modules.career_record.domain import (
    CareerEntity,
    CareerEntityKind,
    CareerFieldProvenance,
    CareerRelationshipKind,
    ConflictResolution,
    EmploymentType,
    EvidenceInputKind,
    EvidenceLifecycle,
    EvidenceMetric,
    EvidenceStrength,
    EvidenceType,
    MetricPrecision,
    PartialDate,
    PersonalFactKind,
    ProposalStatus,
    ReminderCadence,
    SkillProficiency,
    TimelineFinding,
)
from rezumi.modules.career_record.domain.errors import (
    CareerRecordNotFound,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
)
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal
from rezumi.modules.resume_health.application import ResumeHealthService
from rezumi.modules.resume_health.application.models import ResumeRequestContext
from rezumi.modules.resume_health.domain import OwnerScope

from rezumi_api.conditional_requests import parse_if_match_version
from rezumi_api.modules.career_record.dependencies import (
    attachment_request_context,
    attachment_workflow_service,
    career_record_service,
    career_request_context,
    declared_profile_enrichment_job_service,
)
from rezumi_api.modules.career_record.presenters import (
    achievement_response,
    career_item_response,
    career_relationship_response,
    evidence_response,
    experience_response,
    field_provenance_response,
    personal_fact_response,
    profile_response,
    proposal_response,
    provenance_from_proposal,
    reminder_response,
    semantic_import_proposal_response,
    skill_response,
    timeline_finding_response,
)
from rezumi_api.modules.career_record.schemas import (
    AchievementInput,
    AchievementPageResponse,
    AchievementResponse,
    AttachmentDownloadResponse,
    AttachmentUploadIntentRequest,
    AttachmentUploadIntentResponse,
    CareerItemInput,
    CareerItemListResponse,
    CareerItemResponse,
    CareerProfileResponse,
    CareerProfileUpdateRequest,
    CareerRelationshipInput,
    CareerRelationshipListResponse,
    CareerRelationshipResponse,
    DeclaredProfileEnrichmentJobResponse,
    EvidenceConflictResolutionRequest,
    EvidenceInput,
    EvidenceMetricInput,
    EvidencePageResponse,
    EvidenceResponse,
    EvidenceUpdateRequest,
    EvidenceUsageListResponse,
    ExperienceInput,
    ExperienceListResponse,
    ExperienceResponse,
    ImportProposalAcceptRequest,
    ImportProposalPageResponse,
    ImportProposalResponse,
    PageResponse,
    PersonalFactInput,
    PersonalFactListResponse,
    PersonalFactResponse,
    PersonalFactUpdateRequest,
    ProvenanceResponse,
    ReminderPreferencesResponse,
    ReminderPreferencesUpdateRequest,
    ReorderRequest,
    ResumeImportProposalRequest,
    SemanticImportAcceptRequest,
    SemanticImportBatchResponse,
    SemanticImportCreateRequest,
    SemanticImportProposalListResponse,
    SemanticImportProposalResponse,
    SemanticImportQuestionResponse,
    SkillInput,
    SkillListResponse,
    SkillResponse,
)
from rezumi_api.modules.identity.dependencies import (
    current_principal,
    identity_service,
    require_authenticated_csrf,
)
from rezumi_api.modules.identity.schemas import ProblemResponse
from rezumi_api.modules.resume_health.routes import resume_health_service

router = APIRouter(prefix="/api/v1", tags=["Career Record"])
_PROBLEMS: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ProblemResponse},
    status.HTTP_403_FORBIDDEN: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ProblemResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemResponse},
}


def _private(response: Response, version: int | None = None) -> None:
    response.headers["Cache-Control"] = "no-store"
    if version is not None:
        response.headers["ETag"] = f'"{version}"'


def _declared_profile_enrichment_job_response(
    view: DeclaredProfileEnrichmentJobView,
) -> DeclaredProfileEnrichmentJobResponse:
    return DeclaredProfileEnrichmentJobResponse(
        job_id=view.job_id,
        personal_fact_id=view.personal_fact_id,
        status=view.status.value,
        attempts=view.attempts,
        max_attempts=view.max_attempts,
        result_platform=view.result_platform,
        result_achievements_created=view.result_achievements_created,
        result_evidence_created=view.result_evidence_created,
        error_message=view.error_message,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _partial_date(value: str | None) -> PartialDate | None:
    if value is None:
        return None
    year, separator, month = value.partition("-")
    return PartialDate(year=int(year), month=int(month) if separator else None)


def _experience_data(value: ExperienceInput, *, group_id: UUID | None = None) -> CareerEntityData:
    return CareerEntityData(
        kind=CareerEntityKind.EXPERIENCE,
        title=value.official_title,
        organization=value.employer,
        description=value.description,
        official_title=value.official_title,
        display_title=value.display_title,
        employment_type=EmploymentType(value.employment_type) if value.employment_type else None,
        location=value.location,
        start_date=_partial_date(value.start_date),
        end_date=_partial_date(value.end_date),
        is_current=value.current,
        group_id=group_id,
    )


def _career_item_data(value: CareerItemInput) -> CareerEntityData:
    return CareerEntityData(
        kind=CareerEntityKind(value.kind),
        title=value.title,
        organization=value.organization,
        description=value.description,
        external_url=str(value.url) if value.url is not None else None,
        start_date=_partial_date(value.start_date),
        end_date=_partial_date(value.end_date),
    )


def _skill_proficiency(value: str | None) -> SkillProficiency | None:
    return {
        "learning": SkillProficiency.BEGINNER,
        "working": SkillProficiency.INTERMEDIATE,
        "advanced": SkillProficiency.ADVANCED,
        "expert": SkillProficiency.EXPERT,
        None: None,
    }[value]


def _matches_accepted_proposal(current: CareerEntity, proposed: CareerEntity) -> bool:
    """Attach legacy import context only while every accepted factual field still matches."""

    return (
        current.kind is proposed.kind
        and current.title == proposed.title
        and current.organization == proposed.organization
        and current.description == proposed.description
        and current.official_title == proposed.official_title
        and current.display_title == proposed.display_title
        and current.employment_type == proposed.employment_type
        and current.location == proposed.location
        and current.external_url == proposed.external_url
        and current.start_date == proposed.start_date
        and current.end_date == proposed.end_date
        and current.is_current == proposed.is_current
        and current.group_id == proposed.group_id
    )


_ENTITY_PROVENANCE_LIMIT = 100
"""Matches the `max_length` on `ExperienceResponse.provenance` /
`CareerItemResponse.provenance`."""

_COMPACT_PROVENANCE_LIMIT = 20
"""Matches the `max_length` on `SkillResponse.provenance` /
`PersonalFactResponse.provenance`."""


def _capped_provenance_responses(
    entries: Sequence[tuple[CareerFieldProvenance, bool]], *, limit: int
) -> list[ProvenanceResponse]:
    """Cap + sort (newest first) provenance entries to a response's `max_length`.

    Repeated resume re-imports (or repeated owner attestation of an unchanged
    field) can accumulate far more provenance rows per field than any schema
    allows or any UI needs to show. Capping here — rather than letting
    Pydantic reject the whole response once history grows past the limit —
    keeps the endpoint working indefinitely. Nothing is deleted from storage,
    only what gets serialized is capped.
    """

    return [
        field_provenance_response(value, available=available)
        for value, available in sorted(
            entries, key=lambda entry: entry[0].created_at, reverse=True
        )[:limit]
    ]


async def _current_field_provenance_responses(
    service: CareerRecordService,
    owner_user_id: UUID,
    target_id: UUID,
    *,
    limit: int,
) -> list[ProvenanceResponse]:
    values = await service.current_field_provenance(owner_user_id, target_id)
    entries = [
        (value, await service.field_provenance_source_available(owner_user_id, value))
        for value in values
    ]
    return _capped_provenance_responses(entries, limit=limit)


async def _batched_field_provenance_responses(
    service: CareerRecordService,
    owner_user_id: UUID,
    target_ids: tuple[UUID, ...],
    *,
    limit: int,
) -> dict[UUID, list[ProvenanceResponse]]:
    """Batched equivalent of `_current_field_provenance_responses` for lists.

    `field_provenance_source_available` re-derives semantic candidates from
    the underlying resume snapshot per call. Calling
    `_current_field_provenance_responses` once per item in a list route makes
    that route's latency scale with the account's total provenance record
    count (seconds, for accounts with many skills/facts). Fetching everything
    through `current_field_provenance_with_availability_for_targets` shares
    one candidates-by-(document, snapshot) cache across the whole batch.
    """

    provenance_by_target = await service.current_field_provenance_with_availability_for_targets(
        owner_user_id, target_ids
    )
    return {
        target_id: _capped_provenance_responses(entries, limit=limit)
        for target_id, entries in provenance_by_target.items()
    }


async def _accepted_provenance_by_entity(
    service: CareerRecordService, owner_user_id: UUID
) -> dict[UUID, list[ProvenanceResponse]]:
    current_entities = {entity.id: entity for entity in await service.list_entities(owner_user_id)}
    result = await _batched_field_provenance_responses(
        service, owner_user_id, tuple(current_entities), limit=_ENTITY_PROVENANCE_LIMIT
    )
    cursor: str | None = None
    while True:
        page = await service.list_import_proposals(
            owner_user_id,
            filter_by=ProposalFilter(status=ProposalStatus.ACCEPTED),
            cursor=cursor,
            limit=100,
        )
        for proposal in page.items:
            entity_id = proposal.target_entity_id or proposal.proposed_entity.id
            current = current_entities.get(entity_id)
            if current is None or not _matches_accepted_proposal(
                current,
                proposal.proposed_entity,
            ):
                continue
            bucket = result.setdefault(entity_id, [])
            if len(bucket) >= _ENTITY_PROVENANCE_LIMIT:
                continue
            available = await service.import_proposal_source_available(owner_user_id, proposal.id)
            bucket.append(provenance_from_proposal(proposal, available=available))
        cursor = page.next_cursor
        if cursor is None:
            return result


async def _experience_list_responses(
    service: CareerRecordService,
    owner_user_id: UUID,
    values: tuple[CareerEntity, ...],
    *,
    findings: tuple[TimelineFinding, ...],
    include_provenance: bool,
) -> list[ExperienceResponse]:
    confirmations = await service.list_entity_confirmations(owner_user_id)
    provenance = (
        await _accepted_provenance_by_entity(service, owner_user_id)
        if include_provenance
        else {}
    )
    skill_ids_by_entity = await service.list_entity_skill_ids_by_entity(
        owner_user_id,
        tuple(item.id for item in values),
    )
    return [
        experience_response(
            item,
            user_confirmed=(
                item.id in confirmations and confirmations[item.id].state.value == "confirmed"
            ),
            findings=findings,
            skill_ids=skill_ids_by_entity.get(item.id, ()),
            provenance=provenance.get(item.id, []),
        )
        for item in values
    ]


@router.get(
    "/career-profile",
    response_model=CareerProfileResponse,
    operation_id="careerProfileGet",
    responses=_PROBLEMS,
)
async def get_career_profile(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    identity: Annotated[IdentityService, Depends(identity_service)],
) -> CareerProfileResponse:
    view = await service.get_or_create_profile(principal.user_id, context)
    account = await identity.get_current_user(principal)
    _private(response, view.profile.version)
    return profile_response(view.profile, account)


@router.patch(
    "/career-profile",
    response_model=CareerProfileResponse,
    operation_id="careerProfileUpdate",
    responses=_PROBLEMS,
)
async def update_career_profile(
    payload: CareerProfileUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    identity: Annotated[IdentityService, Depends(identity_service)],
) -> CareerProfileResponse:
    current = await service.get_profile(principal.user_id)
    supplied = payload.model_fields_set
    updated = await service.update_profile(
        principal.user_id,
        parse_if_match_version(if_match),
        UpdateCareerProfile(
            professional_headline=(
                payload.professional_headline
                if "professional_headline" in supplied
                else current.profile.professional_headline
            ),
            summary=(
                payload.professional_summary
                if "professional_summary" in supplied
                else current.profile.summary
            ),
            work_authorization=(
                payload.work_authorization
                if "work_authorization" in supplied
                else current.profile.work_authorization
            ),
        ),
        context,
    )
    account = await identity.get_current_user(principal)
    _private(response, updated.version)
    return profile_response(updated, account)


@router.get(
    "/personal-facts",
    response_model=PersonalFactListResponse,
    operation_id="careerPersonalFactsList",
    responses=_PROBLEMS,
)
async def list_personal_facts(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> PersonalFactListResponse:
    await service.get_or_create_profile(principal.user_id, context)
    facts = await service.list_personal_facts(principal.user_id)
    _private(response)
    provenance_by_fact = await _batched_field_provenance_responses(
        service,
        principal.user_id,
        tuple(fact.id for fact in facts),
        limit=_COMPACT_PROVENANCE_LIMIT,
    )
    return PersonalFactListResponse(
        data=[
            personal_fact_response(
                fact,
                provenance=provenance_by_fact.get(fact.id, []),
            )
            for fact in facts
        ]
    )


@router.post(
    "/personal-facts",
    response_model=PersonalFactResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerPersonalFactCreate",
    responses=_PROBLEMS,
)
async def create_personal_fact(
    payload: PersonalFactInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> PersonalFactResponse:
    await service.get_or_create_profile(principal.user_id, context)
    fact = await service.create_personal_fact(
        principal.user_id,
        CreatePersonalFact(
            kind=PersonalFactKind(payload.kind),
            value=payload.value,
            label=payload.label,
            is_primary=payload.is_primary,
        ),
        context,
    )
    _private(response, fact.version)
    return personal_fact_response(fact)


@router.patch(
    "/personal-facts/{fact_id}",
    response_model=PersonalFactResponse,
    operation_id="careerPersonalFactUpdate",
    responses=_PROBLEMS,
)
async def update_personal_fact(
    fact_id: UUID,
    payload: PersonalFactUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> PersonalFactResponse:
    fact = await service.update_personal_fact(
        principal.user_id,
        fact_id,
        parse_if_match_version(if_match),
        UpdatePersonalFact(
            value=payload.value,
            label=payload.label,
            is_primary=payload.is_primary,
        ),
        context,
    )
    _private(response, fact.version)
    return personal_fact_response(fact)


@router.post(
    "/personal-facts/{fact_id}/confirm",
    response_model=PersonalFactResponse,
    operation_id="careerPersonalFactConfirm",
    responses=_PROBLEMS,
)
async def confirm_personal_fact(
    fact_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> PersonalFactResponse:
    fact = await service.confirm_personal_fact(
        principal.user_id,
        fact_id,
        parse_if_match_version(if_match),
        context,
    )
    _private(response, fact.version)
    return personal_fact_response(
        fact,
        provenance=await _current_field_provenance_responses(
            service, principal.user_id, fact.id, limit=_COMPACT_PROVENANCE_LIMIT
        ),
    )


@router.post(
    "/personal-facts/{fact_id}/enrich",
    response_model=DeclaredProfileEnrichmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="careerPersonalFactEnrich",
    responses=_PROBLEMS,
)
async def enrich_personal_fact_link(
    fact_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    jobs: Annotated[
        DeclaredProfileEnrichmentJobService, Depends(declared_profile_enrichment_job_service)
    ],
) -> DeclaredProfileEnrichmentJobResponse:
    """Enqueue declared-link enrichment; the worker fetches and materializes it.

    Returns immediately with a job to poll rather than running the fetch
    inline, so a slow or unavailable third-party profile page never blocks
    the request.
    """
    view = await jobs.enqueue(principal.user_id, fact_id, context)
    _private(response)
    return _declared_profile_enrichment_job_response(view)


@router.get(
    "/personal-facts/{fact_id}/enrich/{job_id}",
    response_model=DeclaredProfileEnrichmentJobResponse,
    operation_id="careerPersonalFactEnrichmentJobGet",
    responses=_PROBLEMS,
)
async def get_declared_profile_enrichment_job(
    fact_id: UUID,
    job_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    jobs: Annotated[
        DeclaredProfileEnrichmentJobService, Depends(declared_profile_enrichment_job_service)
    ],
) -> DeclaredProfileEnrichmentJobResponse:
    view = await jobs.get_job(principal.user_id, job_id)
    if view.personal_fact_id != fact_id:
        raise CareerRecordNotFound
    _private(response)
    return _declared_profile_enrichment_job_response(view)


@router.delete(
    "/personal-facts/{fact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerPersonalFactDelete",
    responses=_PROBLEMS,
)
async def delete_personal_fact(
    fact_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    await service.delete_personal_fact(
        principal.user_id,
        fact_id,
        parse_if_match_version(if_match),
        context,
    )


@router.get(
    "/career-relationships",
    response_model=CareerRelationshipListResponse,
    operation_id="careerRelationshipsList",
    responses=_PROBLEMS,
)
async def list_career_relationships(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerRelationshipListResponse:
    await service.get_or_create_profile(principal.user_id, context)
    relationships = await service.list_entity_relationships(principal.user_id)
    _private(response)
    return CareerRelationshipListResponse(
        data=[career_relationship_response(relationship) for relationship in relationships]
    )


@router.post(
    "/career-relationships",
    response_model=CareerRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerRelationshipCreate",
    responses=_PROBLEMS,
)
async def create_career_relationship(
    payload: CareerRelationshipInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerRelationshipResponse:
    relationship = await service.link_entity_relationship(
        principal.user_id,
        LinkCareerEntityRelationship(
            source_entity_id=payload.experience_id,
            target_entity_id=payload.project_id,
            kind=CareerRelationshipKind(payload.kind),
        ),
        context,
    )
    _private(response)
    return career_relationship_response(relationship)


@router.delete(
    "/career-relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerRelationshipDelete",
    responses=_PROBLEMS,
)
async def delete_career_relationship(
    relationship_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    await service.unlink_entity_relationship(
        principal.user_id,
        relationship_id,
        context,
    )


@router.get(
    "/experiences",
    response_model=ExperienceListResponse,
    operation_id="careerExperiencesList",
    responses=_PROBLEMS,
)
async def list_experiences(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    include_provenance: bool = Query(default=True, alias="includeProvenance"),
) -> ExperienceListResponse:
    view = await service.get_or_create_profile(principal.user_id, context)
    values = tuple(item for item in view.entities if item.kind is CareerEntityKind.EXPERIENCE)
    _private(response)
    data = await _experience_list_responses(
        service,
        principal.user_id,
        values,
        findings=view.findings,
        include_provenance=include_provenance,
    )
    return ExperienceListResponse(
        data=data,
        findings=[timeline_finding_response(item) for item in view.findings],
    )


@router.post(
    "/experiences",
    response_model=ExperienceResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerExperienceCreate",
    responses=_PROBLEMS,
)
async def create_experience(
    payload: ExperienceInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ExperienceResponse:
    await service.get_or_create_profile(principal.user_id, context)
    created = await service.create_entity(
        principal.user_id,
        _experience_data(payload),
        context,
        skill_ids=tuple(payload.skill_ids),
        group_with_entity_id=payload.group_with_experience_id,
    )
    _private(response, created.version)
    return experience_response(
        created,
        user_confirmed=False,
        skill_ids=tuple(payload.skill_ids),
    )


@router.patch(
    "/experiences/{entity_id}",
    response_model=ExperienceResponse,
    operation_id="careerExperienceUpdate",
    responses=_PROBLEMS,
)
async def update_experience(
    entity_id: UUID,
    payload: ExperienceInput,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ExperienceResponse:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is not CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    updated = await service.update_entity(
        principal.user_id,
        entity_id,
        parse_if_match_version(if_match),
        _experience_data(payload, group_id=current.group_id),
        context,
        skill_ids=tuple(payload.skill_ids),
        group_with_entity_id=payload.group_with_experience_id,
        replace_group=True,
    )
    _private(response, updated.version)
    return experience_response(
        updated,
        user_confirmed=False,
        skill_ids=tuple(payload.skill_ids),
    )


@router.post(
    "/experiences/{entity_id}/confirm",
    response_model=ExperienceResponse,
    operation_id="careerExperienceConfirm",
    responses=_PROBLEMS,
)
async def confirm_experience(
    entity_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ExperienceResponse:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is not CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    entity, _confirmation = await service.confirm_entity(
        principal.user_id,
        entity_id,
        parse_if_match_version(if_match),
        context,
    )
    _private(response, entity.version)
    return experience_response(
        entity,
        user_confirmed=True,
        skill_ids=await service.list_entity_skill_ids(principal.user_id, entity.id),
        provenance=await _current_field_provenance_responses(
            service, principal.user_id, entity.id, limit=_ENTITY_PROVENANCE_LIMIT
        ),
    )


@router.delete(
    "/experiences/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerExperienceDelete",
    responses=_PROBLEMS,
)
async def delete_experience(
    entity_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is not CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    await service.delete_entity(
        principal.user_id, entity_id, parse_if_match_version(if_match), context
    )


@router.post(
    "/experiences/reorder",
    response_model=ExperienceListResponse,
    operation_id="careerExperiencesReorder",
    responses=_PROBLEMS,
)
async def reorder_experiences(
    payload: ReorderRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ExperienceListResponse:
    view = await service.get_profile(principal.user_id)
    experiences = {
        item.id: item for item in view.entities if item.kind is CareerEntityKind.EXPERIENCE
    }
    if set(experiences) != {item.id for item in payload.items}:
        raise CareerRecordValidationError("reorder must contain every owned experience")
    for item in payload.items:
        if experiences[item.id].version != item.version:
            raise CareerRecordVersionConflict
    ordered_experiences = [
        item.id for item in sorted(payload.items, key=lambda item: item.position)
    ]
    remaining = [item.id for item in view.entities if item.kind is not CareerEntityKind.EXPERIENCE]
    updated = await service.reorder_entity_list(
        principal.user_id,
        tuple((*ordered_experiences, *remaining)),
        view.profile.version,
        context,
    )
    values = tuple(item for item in updated.entities if item.kind is CareerEntityKind.EXPERIENCE)
    _private(response, updated.profile.version)
    data = await _experience_list_responses(
        service,
        principal.user_id,
        values,
        findings=updated.findings,
        include_provenance=True,
    )
    return ExperienceListResponse(
        data=data,
        findings=[timeline_finding_response(item) for item in updated.findings],
    )


@router.get(
    "/career-items",
    response_model=CareerItemListResponse,
    operation_id="careerItemsList",
    responses=_PROBLEMS,
)
async def list_career_items(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerItemListResponse:
    await service.get_or_create_profile(principal.user_id, context)
    values = await service.list_entities(principal.user_id)
    provenance = await _accepted_provenance_by_entity(service, principal.user_id)
    confirmations = await service.list_entity_confirmations(principal.user_id)
    _private(response)
    return CareerItemListResponse(
        data=[
            career_item_response(
                item,
                user_confirmed=(
                    item.id in confirmations and confirmations[item.id].state.value == "confirmed"
                ),
                provenance=provenance.get(item.id, []),
            )
            for item in values
            if item.kind is not CareerEntityKind.EXPERIENCE
        ]
    )


@router.post(
    "/career-items",
    response_model=CareerItemResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerItemCreate",
    responses=_PROBLEMS,
)
async def create_career_item(
    payload: CareerItemInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerItemResponse:
    await service.get_or_create_profile(principal.user_id, context)
    created = await service.create_entity(principal.user_id, _career_item_data(payload), context)
    _private(response, created.version)
    return career_item_response(created, user_confirmed=False)


@router.patch(
    "/career-items/{entity_id}",
    response_model=CareerItemResponse,
    operation_id="careerItemUpdate",
    responses=_PROBLEMS,
)
async def update_career_item(
    entity_id: UUID,
    payload: CareerItemInput,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerItemResponse:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    updated = await service.update_entity(
        principal.user_id,
        entity_id,
        parse_if_match_version(if_match),
        _career_item_data(payload),
        context,
    )
    _private(response, updated.version)
    return career_item_response(updated, user_confirmed=False)


@router.post(
    "/career-items/{entity_id}/confirm",
    response_model=CareerItemResponse,
    operation_id="careerItemConfirm",
    responses=_PROBLEMS,
)
async def confirm_career_item(
    entity_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> CareerItemResponse:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    entity, _confirmation = await service.confirm_entity(
        principal.user_id,
        entity_id,
        parse_if_match_version(if_match),
        context,
    )
    _private(response, entity.version)
    return career_item_response(
        entity,
        user_confirmed=True,
        provenance=await _current_field_provenance_responses(
            service, principal.user_id, entity.id, limit=_ENTITY_PROVENANCE_LIMIT
        ),
    )


@router.delete(
    "/career-items/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerItemDelete",
    responses=_PROBLEMS,
)
async def delete_career_item(
    entity_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    current = await service.get_entity(principal.user_id, entity_id)
    if current.kind is CareerEntityKind.EXPERIENCE:
        raise CareerRecordNotFound
    await service.delete_entity(
        principal.user_id, entity_id, parse_if_match_version(if_match), context
    )


@router.get(
    "/skills",
    response_model=SkillListResponse,
    operation_id="careerSkillsList",
    responses=_PROBLEMS,
)
async def list_skills(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    include_provenance: bool = Query(default=True, alias="includeProvenance"),
) -> SkillListResponse:
    await service.get_or_create_profile(principal.user_id, context)
    values = await service.list_skills(principal.user_id)
    confirmations = await service.list_skill_confirmations(principal.user_id)
    _private(response)
    if include_provenance:
        provenance_by_skill = await _batched_field_provenance_responses(
            service,
            principal.user_id,
            tuple(item.id for item in values),
            limit=_COMPACT_PROVENANCE_LIMIT,
        )
        data = [
            skill_response(
                item,
                user_confirmed=(
                    item.id in confirmations and confirmations[item.id].state.value == "confirmed"
                ),
                provenance=provenance_by_skill.get(item.id, []),
            )
            for item in values
        ]
    else:
        data = [
            skill_response(
                item,
                user_confirmed=(
                    item.id in confirmations and confirmations[item.id].state.value == "confirmed"
                ),
            )
            for item in values
        ]
    return SkillListResponse(data=data)


@router.post(
    "/skills",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerSkillCreate",
    responses=_PROBLEMS,
)
async def create_skill(
    payload: SkillInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SkillResponse:
    await service.get_or_create_profile(principal.user_id, context)
    created = await service.create_skill(
        principal.user_id,
        CreateSkill(payload.name, payload.category, _skill_proficiency(payload.proficiency)),
        context,
    )
    _private(response, created.version)
    return skill_response(created, user_confirmed=False)


@router.patch(
    "/skills/{skill_id}",
    response_model=SkillResponse,
    operation_id="careerSkillUpdate",
    responses=_PROBLEMS,
)
async def update_skill(
    skill_id: UUID,
    payload: SkillInput,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SkillResponse:
    updated = await service.update_skill(
        principal.user_id,
        skill_id,
        parse_if_match_version(if_match),
        UpdateSkill(payload.name, payload.category, _skill_proficiency(payload.proficiency)),
        context,
    )
    _private(response, updated.version)
    return skill_response(updated, user_confirmed=False)


@router.post(
    "/skills/{skill_id}/confirm",
    response_model=SkillResponse,
    operation_id="careerSkillConfirm",
    responses=_PROBLEMS,
)
async def confirm_skill(
    skill_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SkillResponse:
    skill, _confirmation = await service.confirm_skill(
        principal.user_id,
        skill_id,
        parse_if_match_version(if_match),
        context,
    )
    _private(response, skill.version)
    return skill_response(
        skill,
        user_confirmed=True,
        provenance=await _current_field_provenance_responses(
            service, principal.user_id, skill.id, limit=_COMPACT_PROVENANCE_LIMIT
        ),
    )


@router.delete(
    "/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="careerSkillDelete",
    responses=_PROBLEMS,
)
async def delete_skill(
    skill_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    await service.delete_skill(
        principal.user_id, skill_id, parse_if_match_version(if_match), context
    )


def _proposal_data(payload: ResumeImportProposalRequest) -> CareerEntityData:
    return CareerEntityData(
        kind=CareerEntityKind(payload.kind),
        title=payload.title,
        organization=payload.organization,
        description=payload.description,
        official_title=payload.official_title,
        display_title=payload.display_title,
        employment_type=(
            EmploymentType(payload.employment_type) if payload.employment_type else None
        ),
        location=payload.location,
        external_url=str(payload.url) if payload.url is not None else None,
        start_date=_partial_date(payload.start_date),
        end_date=_partial_date(payload.end_date),
        is_current=payload.current,
        group_id=payload.group_id,
    )


async def _present_proposal(
    service: CareerRecordService,
    owner_user_id: UUID,
    proposal_id: UUID,
) -> ImportProposalResponse:
    proposal = await service.get_import_proposal(owner_user_id, proposal_id)
    current: CareerEntity | None = None
    if proposal.target_entity_id is not None:
        try:
            current = await service.get_entity(owner_user_id, proposal.target_entity_id)
        except CareerRecordNotFound:
            current = None
    available = await service.import_proposal_source_available(owner_user_id, proposal.id)
    return proposal_response(
        proposal,
        source_document_name="the reviewed resume",
        current=current,
        source_available=available,
    )


async def _present_semantic_proposal(
    service: CareerRecordService,
    owner_user_id: UUID,
    proposal_id: UUID,
) -> SemanticImportProposalResponse:
    proposal = await service.get_semantic_import_proposal(owner_user_id, proposal_id)
    source_available = await service.semantic_import_proposal_source_available(
        owner_user_id, proposal_id
    )
    return semantic_import_proposal_response(proposal, source_available=source_available)


@router.post(
    "/career-profile/semantic-import-proposals",
    response_model=SemanticImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerSemanticImportProposalsCreate",
    responses=_PROBLEMS,
)
async def create_semantic_import_proposals(
    payload: SemanticImportCreateRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    resume_service: Annotated[ResumeHealthService, Depends(resume_health_service)],
) -> SemanticImportBatchResponse:
    await service.get_or_create_profile(principal.user_id, context)
    reviewed_snapshot_id = await resume_service.ensure_reviewed_snapshot_for_import(
        OwnerScope(user_id=principal.user_id),
        payload.document_id,
        ResumeRequestContext("career-import", context.trace_id),
    )
    result = await service.populate_from_reviewed_snapshot(
        principal.user_id,
        CreateSemanticImportProposals(
            document_id=payload.document_id,
            snapshot_id=reviewed_snapshot_id,
        ),
        context,
    )
    _private(response)
    return SemanticImportBatchResponse(
        proposals=[
            await _present_semantic_proposal(service, principal.user_id, proposal.id)
            for proposal in result.proposals
        ],
        questions=[
            SemanticImportQuestionResponse(
                semantic_entity_id=question.semantic_entity_id,
                code="semantic_candidate_requires_review",
                missing_fields=list(question.missing_fields),
            )
            for question in result.questions
        ],
        applied_count=result.applied_count,
    )


@router.get(
    "/career-profile/semantic-import-proposals",
    response_model=SemanticImportProposalListResponse,
    operation_id="careerSemanticImportProposalsList",
    responses=_PROBLEMS,
)
async def list_semantic_import_proposals(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SemanticImportProposalListResponse:
    proposals_with_availability = await service.list_semantic_import_proposals_with_availability(
        principal.user_id
    )
    _private(response)
    return SemanticImportProposalListResponse(
        data=[
            semantic_import_proposal_response(proposal, source_available=source_available)
            for proposal, source_available in proposals_with_availability
        ]
    )


@router.get(
    "/career-profile/semantic-import-proposals/{proposal_id}",
    response_model=SemanticImportProposalResponse,
    operation_id="careerSemanticImportProposalGet",
    responses=_PROBLEMS,
)
async def get_semantic_import_proposal(
    proposal_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SemanticImportProposalResponse:
    proposal = await service.get_semantic_import_proposal(principal.user_id, proposal_id)
    _private(response, proposal.version)
    return await _present_semantic_proposal(service, principal.user_id, proposal.id)


@router.post(
    "/career-profile/semantic-import-proposals/{proposal_id}/accept",
    response_model=SemanticImportProposalResponse,
    operation_id="careerSemanticImportProposalAccept",
    responses=_PROBLEMS,
)
async def accept_semantic_import_proposal(
    proposal_id: UUID,
    payload: SemanticImportAcceptRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SemanticImportProposalResponse:
    accepted = await service.accept_semantic_import_proposal(
        principal.user_id,
        proposal_id,
        parse_if_match_version(if_match),
        AcceptSemanticImportProposal(
            values=payload.values,
            idempotency_key=idempotency_key,
            target_record_id=payload.target_record_id,
        ),
        context,
    )
    _private(response, accepted.proposal.version)
    return await _present_semantic_proposal(service, principal.user_id, accepted.proposal.id)


@router.post(
    "/career-profile/semantic-import-proposals/{proposal_id}/reject",
    response_model=SemanticImportProposalResponse,
    operation_id="careerSemanticImportProposalReject",
    responses=_PROBLEMS,
)
async def reject_semantic_import_proposal(
    proposal_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> SemanticImportProposalResponse:
    proposal = await service.reject_semantic_import_proposal(
        principal.user_id,
        proposal_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    _private(response, proposal.version)
    return await _present_semantic_proposal(service, principal.user_id, proposal.id)


@router.post(
    "/career-profile/import-proposals",
    response_model=ImportProposalResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="careerImportProposalCreate",
    deprecated=True,
    responses=_PROBLEMS,
)
async def create_import_proposal(
    payload: ResumeImportProposalRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ImportProposalResponse:
    await service.get_or_create_profile(principal.user_id, context)
    proposal = await service.create_import_proposal(
        principal.user_id,
        CreateImportProposal(
            proposed_entity=_proposal_data(payload),
            source=ResumeSourceLocator(
                document_id=payload.document_id,
                snapshot_id=payload.snapshot_id,
                block_id=payload.block_id,
                page=payload.page,
                start_offset=payload.start,
                end_offset=payload.end,
            ),
            target_entity_id=payload.target_entity_id,
        ),
        context,
    )
    _private(response, proposal.version)
    return await _present_proposal(service, principal.user_id, proposal.id)


@router.get(
    "/career-profile/import-proposals",
    response_model=ImportProposalPageResponse,
    operation_id="careerImportProposalsList",
    responses=_PROBLEMS,
)
async def list_import_proposals(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    proposal_status: Annotated[
        Literal["pending", "accepted", "rejected"] | None,
        Query(alias="status"),
    ] = None,
    after: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ImportProposalPageResponse:
    page = await service.list_import_proposals(
        principal.user_id,
        filter_by=ProposalFilter(
            status=ProposalStatus(proposal_status) if proposal_status is not None else None
        ),
        cursor=after,
        limit=limit,
    )
    data = [
        await _present_proposal(service, principal.user_id, proposal.id) for proposal in page.items
    ]
    _private(response)
    return ImportProposalPageResponse(
        data=data,
        page=PageResponse(
            limit=limit,
            has_more=page.next_cursor is not None,
            next_cursor=page.next_cursor,
        ),
    )


@router.get(
    "/career-profile/import-proposals/{proposal_id}",
    response_model=ImportProposalResponse,
    operation_id="careerImportProposalGet",
    responses=_PROBLEMS,
)
async def get_import_proposal(
    proposal_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ImportProposalResponse:
    result = await _present_proposal(service, principal.user_id, proposal_id)
    _private(response, result.version)
    return result


def _reviewed_proposal_data(
    current: CareerEntity,
    edits: dict[str, str],
) -> CareerEntityData:
    editable = {"title", "organization", "description", "startDate", "endDate", "review"}
    if not set(edits).issubset(editable):
        raise CareerRecordValidationError("proposal edits do not match reviewed changes")

    def selected(field: str, fallback: str | None) -> str | None:
        return edits.get(field, fallback)

    title = selected("title", current.title)
    organization = selected("organization", current.organization)
    description = selected("description", current.description)
    start_date = selected(
        "startDate",
        None
        if current.start_date is None
        else (
            f"{current.start_date.year:04d}"
            if current.start_date.month is None
            else f"{current.start_date.year:04d}-{current.start_date.month:02d}"
        ),
    )
    end_date = selected(
        "endDate",
        None
        if current.end_date is None
        else (
            f"{current.end_date.year:04d}"
            if current.end_date.month is None
            else f"{current.end_date.year:04d}-{current.end_date.month:02d}"
        ),
    )
    normalized_title = (title or "").strip()
    normalized_organization = (organization or "").strip() or None
    normalized_description = (description or "").strip() or None
    parsed_start = _partial_date(start_date.strip() or None) if start_date is not None else None
    parsed_end = _partial_date(end_date.strip() or None) if end_date is not None else None
    if current.kind is CareerEntityKind.EXPERIENCE and parsed_start is None:
        raise CareerRecordValidationError("reviewed experience needs a known start year or month")
    return CareerEntityData(
        kind=current.kind,
        title=normalized_title,
        organization=normalized_organization,
        description=normalized_description,
        official_title=(
            normalized_title
            if current.kind is CareerEntityKind.EXPERIENCE
            else current.official_title
        ),
        display_title=current.display_title,
        employment_type=current.employment_type,
        location=current.location,
        external_url=current.external_url,
        start_date=parsed_start,
        end_date=parsed_end,
        is_current=current.is_current,
        group_id=current.group_id,
    )


@router.post(
    "/career-profile/import-proposals/{proposal_id}/accept",
    response_model=ImportProposalResponse,
    operation_id="careerImportProposalAccept",
    responses=_PROBLEMS,
)
async def accept_import_proposal(
    proposal_id: UUID,
    payload: ImportProposalAcceptRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ImportProposalResponse:
    proposal = await service.get_import_proposal(principal.user_id, proposal_id)
    reviewed = _reviewed_proposal_data(proposal.proposed_entity, payload.edits)
    await service.accept_import_proposal(
        principal.user_id,
        proposal_id,
        parse_if_match_version(if_match),
        context,
        edited_entity=reviewed,
    )
    result = await _present_proposal(service, principal.user_id, proposal_id)
    _private(response, result.version)
    return result


@router.post(
    "/career-profile/import-proposals/{proposal_id}/reject",
    response_model=ImportProposalResponse,
    operation_id="careerImportProposalReject",
    responses=_PROBLEMS,
)
async def reject_import_proposal(
    proposal_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ImportProposalResponse:
    await service.reject_import_proposal(
        principal.user_id,
        proposal_id,
        parse_if_match_version(if_match),
        context,
    )
    result = await _present_proposal(service, principal.user_id, proposal_id)
    _private(response, result.version)
    return result


_EVIDENCE_TYPES: dict[str, EvidenceType] = {
    "resume_statement": EvidenceType.RESUME_STATEMENT,
    "user_confirmed_achievement": EvidenceType.ACHIEVEMENT,
    "metric": EvidenceType.METRIC,
    "project": EvidenceType.PROJECT,
    "certificate": EvidenceType.CREDENTIAL,
    "publication": EvidenceType.PUBLICATION,
    "award": EvidenceType.AWARD,
    "performance_review_excerpt": EvidenceType.REVIEW_EXCERPT,
    "portfolio_link": EvidenceType.PORTFOLIO,
    "github_link": EvidenceType.PORTFOLIO,
    "testimonial": EvidenceType.TESTIMONIAL,
    "supporting_document": EvidenceType.SUPPORT_DOCUMENT,
    "user_note": EvidenceType.NOTE,
}


def _metric_input(value: EvidenceMetricInput) -> MetricInput:
    period = value.period_start
    if value.period_end is not None:
        period += f"/{value.period_end}"
    return MetricInput(
        name=value.name,
        value=value.value,
        value_max=None,
        unit=value.unit,
        currency=None,
        period=period,
        baseline=value.baseline,
        comparator=value.comparator,
        comparison_applicable=value.baseline is not None or value.comparator is not None,
        precision=MetricPrecision(value.precision),
        attribution=value.attribution,
    )


def _stored_metric_input(value: EvidenceMetric) -> MetricInput:
    return MetricInput(
        name=value.name,
        value=value.value,
        value_max=value.value_max,
        unit=value.unit,
        currency=value.currency,
        period=value.period,
        baseline=value.baseline,
        comparator=value.comparator,
        comparison_applicable=value.comparison_applicable,
        precision=value.precision,
        attribution=value.attribution,
    )


def _evidence_command(payload: EvidenceInput) -> CreateEvidence:
    source = payload.source
    resume_source: ResumeSourceLocator | None = None
    external_url: str | None = None
    input_kind = EvidenceInputKind.MANUAL
    if source.source_type == "resume":
        if any(
            value is None
            for value in (
                source.document_id,
                source.snapshot_id,
                source.block_id,
                source.page,
                source.start,
                source.end,
            )
        ):
            raise CareerRecordValidationError("resume source is incomplete")
        resume_source = ResumeSourceLocator(
            document_id=cast(UUID, source.document_id),
            snapshot_id=cast(UUID, source.snapshot_id),
            block_id=cast(UUID, source.block_id),
            page=cast(int, source.page),
            start_offset=cast(int, source.start),
            end_offset=cast(int, source.end),
        )
        input_kind = EvidenceInputKind.EXACT_SOURCE_SPAN
    elif source.source_type == "url":
        external_url = str(source.url)
    elif source.source_type != "manual":
        raise CareerRecordValidationError(
            "private attachment sources are added after evidence creation"
        )

    evidence_type = _EVIDENCE_TYPES[payload.type]
    organization = payload.organization_or_project
    project = None
    if evidence_type is EvidenceType.PROJECT:
        project = organization
        organization = None
    return CreateEvidence(
        evidence_type=evidence_type,
        title=payload.title,
        statement=payload.description,
        organization=organization,
        project=project,
        start_date=_partial_date(payload.start_date),
        end_date=_partial_date(payload.end_date),
        input_kind=input_kind,
        resume_source=resume_source,
        external_url_source=external_url,
        metrics=tuple(_metric_input(item) for item in payload.metrics),
        entity_ids=tuple(payload.experience_ids),
        skill_ids=tuple(payload.skill_ids),
    )


async def _present_evidence(
    service: CareerRecordService,
    owner_user_id: UUID,
    evidence_id: UUID,
) -> EvidenceResponse:
    record, decision = await service.get_evidence_with_eligibility(owner_user_id, evidence_id)
    return evidence_response(record, decision)


@router.get(
    "/evidence",
    response_model=EvidencePageResponse,
    operation_id="evidenceList",
    responses=_PROBLEMS,
)
async def list_evidence(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    evidence_state: Annotated[
        Literal["verified", "confirmed", "supported", "inferred", "unsupported"] | None,
        Query(alias="state"),
    ] = None,
    archived: bool = False,
    after: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> EvidencePageResponse:
    page = await service.list_evidence(
        principal.user_id,
        filter_by=EvidenceFilter(
            query=query,
            strength=EvidenceStrength(evidence_state) if evidence_state is not None else None,
            include_archived=archived,
        ),
        cursor=after,
        limit=limit,
    )
    if page.items:
        presented = await service.get_evidence_batch_with_eligibility(
            principal.user_id,
            tuple(item.id for item in page.items),
        )
        data = [evidence_response(record, decision) for record, decision in presented]
    else:
        data = []
    _private(response)
    return EvidencePageResponse(
        data=data,
        page=PageResponse(
            limit=limit,
            has_more=page.next_cursor is not None,
            next_cursor=page.next_cursor,
        ),
    )


@router.post(
    "/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="evidenceCreate",
    responses=_PROBLEMS,
)
async def create_evidence(
    payload: EvidenceInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    created = await service.create_evidence(principal.user_id, _evidence_command(payload), context)
    result = await _present_evidence(service, principal.user_id, created.id)
    _private(response, result.version)
    return result


@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    operation_id="evidenceGet",
    responses=_PROBLEMS,
)
async def get_evidence(
    evidence_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    result = await _present_evidence(service, principal.user_id, evidence_id)
    _private(response, result.version)
    return result


@router.patch(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    operation_id="evidenceUpdate",
    responses=_PROBLEMS,
)
async def update_evidence(
    evidence_id: UUID,
    payload: EvidenceUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    current = await service.get_evidence(principal.user_id, evidence_id)
    revision = current.revision
    supplied = payload.model_fields_set
    title = payload.title if "title" in supplied else revision.title
    statement = payload.description if "description" in supplied else revision.statement
    organization_or_project = (
        payload.organization_or_project
        if "organization_or_project" in supplied
        else revision.organization or revision.project
    )
    start_date = (
        _partial_date(payload.start_date) if "start_date" in supplied else revision.start_date
    )
    end_date = _partial_date(payload.end_date) if "end_date" in supplied else revision.end_date
    if start_date is None and end_date is not None:
        raise CareerRecordValidationError("an evidence end date requires a start date")
    metrics = (
        tuple(_metric_input(item) for item in payload.metrics or [])
        if "metrics" in supplied
        else tuple(_stored_metric_input(item) for item in current.metrics)
    )
    organization = organization_or_project
    project = None
    if revision.evidence_type is EvidenceType.PROJECT:
        project = organization_or_project
        organization = None
    updated = await service.revise_evidence(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        ReviseEvidence(
            evidence_type=revision.evidence_type,
            title=cast(str, title),
            statement=cast(str, statement),
            context=revision.context,
            organization=organization,
            project=project,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
        ),
        context,
    )
    result = await _present_evidence(service, principal.user_id, updated.id)
    _private(response, result.version)
    return result


async def _transition_result(
    service: CareerRecordService,
    owner_user_id: UUID,
    evidence_id: UUID,
    response: Response,
) -> EvidenceResponse:
    result = await _present_evidence(service, owner_user_id, evidence_id)
    _private(response, result.version)
    return result


@router.post(
    "/evidence/{evidence_id}/confirm",
    response_model=EvidenceResponse,
    operation_id="evidenceConfirm",
    responses=_PROBLEMS,
)
async def confirm_evidence(
    evidence_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    await service.confirm_evidence(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        context,
    )
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.post(
    "/evidence/{evidence_id}/unsupported",
    response_model=EvidenceResponse,
    operation_id="evidenceMarkUnsupported",
    responses=_PROBLEMS,
)
async def mark_evidence_unsupported(
    evidence_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    await service.mark_evidence_unsupported(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        "owner_marked_unsupported",
        context,
    )
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.post(
    "/evidence/{evidence_id}/archive",
    response_model=EvidenceResponse,
    operation_id="evidenceArchive",
    responses=_PROBLEMS,
)
async def archive_evidence(
    evidence_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    await service.archive_evidence(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        context,
    )
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.post(
    "/evidence/{evidence_id}/restore",
    response_model=EvidenceResponse,
    operation_id="evidenceRestore",
    responses=_PROBLEMS,
)
async def restore_evidence(
    evidence_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    await service.restore_evidence(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        context,
    )
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.delete(
    "/evidence/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="evidenceDelete",
    responses=_PROBLEMS,
)
async def delete_evidence(
    evidence_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    await service.delete_evidence(
        principal.user_id,
        evidence_id,
        parse_if_match_version(if_match),
        context,
    )


@router.get(
    "/evidence/{evidence_id}/usage",
    response_model=EvidenceUsageListResponse,
    operation_id="evidenceUsageGet",
    responses=_PROBLEMS,
)
async def get_evidence_usage(
    evidence_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceUsageListResponse:
    result = await _present_evidence(service, principal.user_id, evidence_id)
    _private(response, result.version)
    return EvidenceUsageListResponse(data=result.usage)


async def _assert_attachment_scope(
    workflow: AttachmentWorkflowService,
    owner_user_id: UUID,
    evidence_id: UUID,
    attachment_id: UUID,
    context: AttachmentRequestContext,
) -> None:
    attachment = await workflow.get(owner_user_id, attachment_id, context)
    if attachment.evidence_id != evidence_id:
        raise CareerRecordNotFound


async def _assert_evidence_version(
    service: CareerRecordService,
    owner_user_id: UUID,
    evidence_id: UUID,
    if_match: str,
) -> int:
    record = await service.get_evidence(owner_user_id, evidence_id)
    expected = parse_if_match_version(if_match)
    if record.item.version != expected:
        raise CareerRecordVersionConflict
    if record.item.lifecycle is not EvidenceLifecycle.ACTIVE:
        raise CareerRecordValidationError("attachments require active evidence")
    return expected


@router.post(
    "/evidence/{evidence_id}/attachments/presign",
    response_model=AttachmentUploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="evidenceAttachmentPresign",
    responses=_PROBLEMS,
)
async def presign_evidence_attachment(
    evidence_id: UUID,
    payload: AttachmentUploadIntentRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[AttachmentRequestContext, Depends(attachment_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    workflow: Annotated[AttachmentWorkflowService, Depends(attachment_workflow_service)],
) -> AttachmentUploadIntentResponse:
    version = await _assert_evidence_version(service, principal.user_id, evidence_id, if_match)
    admitted = await workflow.admit(
        principal.user_id,
        AdmitAttachment(
            evidence_id=evidence_id,
            display_filename=payload.display_filename,
            media_type=payload.media_type,
            expected_size=payload.expected_size_bytes,
        ),
        context,
    )
    _private(response, version)
    return AttachmentUploadIntentResponse(
        upload_id=admitted.attachment_id,
        attachment_id=admitted.attachment_id,
        url=admitted.upload.url,
        method="PUT",
        headers=dict(admitted.upload.required_headers),
        expires_at=admitted.expires_at,
    )


@router.post(
    "/evidence/{evidence_id}/attachments/{upload_id}/finalize",
    response_model=EvidenceResponse,
    operation_id="evidenceAttachmentFinalize",
    responses=_PROBLEMS,
)
async def finalize_evidence_attachment(
    evidence_id: UUID,
    upload_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[AttachmentRequestContext, Depends(attachment_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    workflow: Annotated[AttachmentWorkflowService, Depends(attachment_workflow_service)],
) -> EvidenceResponse:
    await _assert_evidence_version(service, principal.user_id, evidence_id, if_match)
    await _assert_attachment_scope(workflow, principal.user_id, evidence_id, upload_id, context)
    await workflow.finalize(principal.user_id, upload_id, idempotency_key, context)
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.get(
    "/evidence/{evidence_id}/attachments/{attachment_id}/download",
    response_model=AttachmentDownloadResponse,
    operation_id="evidenceAttachmentDownload",
    responses=_PROBLEMS,
)
async def download_evidence_attachment(
    evidence_id: UUID,
    attachment_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[AttachmentRequestContext, Depends(attachment_request_context)],
    workflow: Annotated[AttachmentWorkflowService, Depends(attachment_workflow_service)],
) -> AttachmentDownloadResponse:
    await _assert_attachment_scope(workflow, principal.user_id, evidence_id, attachment_id, context)
    grant = await workflow.download(
        principal.user_id,
        attachment_id,
        AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
        context,
    )
    _private(response)
    return AttachmentDownloadResponse(
        url=grant.operation.url,
        expires_at=grant.operation.expires_at,
    )


@router.delete(
    "/evidence/{evidence_id}/attachments/{attachment_id}",
    response_model=EvidenceResponse,
    operation_id="evidenceAttachmentDelete",
    responses=_PROBLEMS,
)
async def delete_evidence_attachment(
    evidence_id: UUID,
    attachment_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[AttachmentRequestContext, Depends(attachment_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    workflow: Annotated[AttachmentWorkflowService, Depends(attachment_workflow_service)],
) -> EvidenceResponse:
    await _assert_evidence_version(service, principal.user_id, evidence_id, if_match)
    await _assert_attachment_scope(workflow, principal.user_id, evidence_id, attachment_id, context)
    await workflow.delete(principal.user_id, attachment_id, context)
    return await _transition_result(service, principal.user_id, evidence_id, response)


@router.post(
    "/evidence/{evidence_id}/conflicts/{conflict_id}/resolve",
    response_model=EvidenceResponse,
    operation_id="evidenceConflictResolve",
    responses=_PROBLEMS,
)
async def resolve_evidence_conflict(
    evidence_id: UUID,
    conflict_id: UUID,
    payload: EvidenceConflictResolutionRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> EvidenceResponse:
    record = await service.get_evidence(principal.user_id, evidence_id)
    expected = parse_if_match_version(if_match)
    if record.item.version != expected:
        raise CareerRecordVersionConflict
    if not any(item.id == conflict_id for item in record.conflicts):
        raise CareerRecordNotFound
    resolution = {
        "keep_both": ConflictResolution.KEEP_BOTH,
        "prefer_current": ConflictResolution.KEEP_CURRENT,
        "prefer_related": ConflictResolution.ACCEPT_INCOMING,
        "mark_unsupported": ConflictResolution.KEEP_CURRENT,
    }[payload.resolution]
    await service.resolve_evidence_conflict_for_record(
        principal.user_id,
        evidence_id,
        expected,
        conflict_id,
        resolution,
        context,
        mark_unsupported=payload.resolution == "mark_unsupported",
    )
    return await _transition_result(service, principal.user_id, evidence_id, response)


def _achievement_command(payload: AchievementInput) -> CreateAchievement:
    return CreateAchievement(
        title=payload.title,
        delivered=payload.answers.delivered or None,
        problem=payload.answers.problem or None,
        audience=payload.answers.affected or None,
        measurement=payload.answers.measurement or None,
        effect=payload.answers.changed or None,
        collaboration=payload.answers.collaboration or None,
        methods=payload.answers.methods or None,
        entity_id=payload.employer_id or payload.project_id,
        metric=_metric_input(payload.metric) if payload.metric is not None else None,
        reminder_cadence=ReminderCadence.NONE,
    )


async def _validate_achievement_association(
    service: CareerRecordService,
    owner_user_id: UUID,
    payload: AchievementInput,
) -> None:
    entity_id = payload.employer_id or payload.project_id
    if entity_id is None:
        return
    entity = await service.get_entity(owner_user_id, entity_id)
    if payload.employer_id is not None and entity.kind is not CareerEntityKind.EXPERIENCE:
        raise CareerRecordValidationError("employer association must reference an experience")
    if payload.project_id is not None and entity.kind is not CareerEntityKind.PROJECT:
        raise CareerRecordValidationError("project association must reference a project")


@router.get(
    "/achievements",
    response_model=AchievementPageResponse,
    operation_id="achievementList",
    responses=_PROBLEMS,
)
async def list_achievements(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
    after: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AchievementPageResponse:
    await service.get_or_create_profile(principal.user_id, context)
    page = await service.list_achievements(
        principal.user_id,
        cursor=after,
        limit=limit,
    )
    _private(response)
    return AchievementPageResponse(
        data=[achievement_response(item) for item in page.items],
        page=PageResponse(
            limit=limit,
            has_more=page.next_cursor is not None,
            next_cursor=page.next_cursor,
        ),
    )


@router.post(
    "/achievements",
    response_model=AchievementResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="achievementCreate",
    responses=_PROBLEMS,
)
async def create_achievement(
    payload: AchievementInput,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> AchievementResponse:
    await service.get_or_create_profile(principal.user_id, context)
    await _validate_achievement_association(service, principal.user_id, payload)
    created = await service.create_achievement(
        principal.user_id,
        _achievement_command(payload),
        context,
    )
    _private(response, created.version)
    return achievement_response(created)


@router.get(
    "/achievements/reminder-preferences",
    response_model=ReminderPreferencesResponse,
    operation_id="achievementReminderPreferencesGet",
    responses=_PROBLEMS,
)
async def get_reminder_preferences(
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ReminderPreferencesResponse:
    value = await service.get_or_create_reminder_preferences(principal.user_id, context)
    _private(response, value.version)
    return reminder_response(value)


@router.patch(
    "/achievements/reminder-preferences",
    response_model=ReminderPreferencesResponse,
    operation_id="achievementReminderPreferencesUpdate",
    responses=_PROBLEMS,
)
async def update_reminder_preferences(
    payload: ReminderPreferencesUpdateRequest,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> ReminderPreferencesResponse:
    value = await service.update_reminder_preferences(
        principal.user_id,
        parse_if_match_version(if_match),
        UpdateReminderPreferences(
            enabled=payload.enabled,
            day_of_month=payload.day_of_month,
            timezone=payload.timezone,
        ),
        context,
    )
    _private(response, value.version)
    return reminder_response(value)


@router.get(
    "/achievements/{achievement_id}",
    response_model=AchievementResponse,
    operation_id="achievementGet",
    responses=_PROBLEMS,
)
async def get_achievement(
    achievement_id: UUID,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> AchievementResponse:
    value = await service.get_achievement(principal.user_id, achievement_id)
    _private(response, value.version)
    return achievement_response(value)


@router.patch(
    "/achievements/{achievement_id}",
    response_model=AchievementResponse,
    operation_id="achievementUpdate",
    responses=_PROBLEMS,
)
async def update_achievement(
    achievement_id: UUID,
    payload: AchievementInput,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> AchievementResponse:
    await _validate_achievement_association(service, principal.user_id, payload)
    command = _achievement_command(payload)
    value = await service.update_achievement(
        principal.user_id,
        achievement_id,
        parse_if_match_version(if_match),
        UpdateAchievement(
            title=command.title,
            delivered=command.delivered,
            problem=command.problem,
            audience=command.audience,
            measurement=command.measurement,
            effect=command.effect,
            collaboration=command.collaboration,
            methods=command.methods,
            entity_id=command.entity_id,
            metric=command.metric,
            reminder_cadence=command.reminder_cadence,
            remind_at=command.remind_at,
        ),
        context,
    )
    _private(response, value.version)
    return achievement_response(value)


@router.delete(
    "/achievements/{achievement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="achievementArchive",
    responses=_PROBLEMS,
)
async def archive_achievement(
    achievement_id: UUID,
    if_match: Annotated[str, Header(alias="If-Match")],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> None:
    await service.archive_achievement(
        principal.user_id,
        achievement_id,
        parse_if_match_version(if_match),
        context,
    )


@router.post(
    "/achievements/{achievement_id}/confirm",
    response_model=AchievementResponse,
    operation_id="achievementConvertToEvidence",
    responses=_PROBLEMS,
)
async def convert_achievement(
    achievement_id: UUID,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_csrf)],
    context: Annotated[RequestContext, Depends(career_request_context)],
    service: Annotated[CareerRecordService, Depends(career_record_service)],
) -> AchievementResponse:
    await service.convert_achievement(
        principal.user_id,
        achievement_id,
        parse_if_match_version(if_match),
        idempotency_key,
        context,
    )
    value = await service.get_achievement(principal.user_id, achievement_id)
    _private(response, value.version)
    return achievement_response(value)
