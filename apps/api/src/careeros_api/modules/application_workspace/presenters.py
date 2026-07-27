"""Presentation helpers for Application Workspace API responses."""

from __future__ import annotations

from datetime import date
from typing import cast

from careeros.modules.application_workspace.application import (
    ApplicationCalendarEntry,
    ApplicationPackView,
    ApplicationSummary,
    PagedResult,
)
from careeros.modules.application_workspace.domain import (
    ApplicationClaimEvidenceLink,
    ApplicationConsistencyFinding,
    ApplicationContact,
    ApplicationDocument,
    ApplicationDocumentClaim,
    ApplicationEvent,
    ApplicationEvidencePin,
    ApplicationNote,
    ApplicationPack,
    ApplicationRequirementSnapshot,
    ApplicationTask,
)

from careeros_api.modules.application_workspace.schemas import (
    ApplicationCalendarItemResponse,
    ApplicationCalendarResponse,
    ApplicationClaimEvidenceLinkResponse,
    ApplicationClaimResponse,
    ApplicationConsistencyResponse,
    ApplicationContactResponse,
    ApplicationDocumentResponse,
    ApplicationEventPageResponse,
    ApplicationEventResponse,
    ApplicationEvidencePinResponse,
    ApplicationNotePageResponse,
    ApplicationNoteResponse,
    ApplicationPackPageResponse,
    ApplicationPackResponse,
    ApplicationPackSummaryResponse,
    ApplicationPageResponse,
    ApplicationRequirementResponse,
    ApplicationResponse,
    ApplicationSummaryResponse,
    ApplicationTaskPageResponse,
    ApplicationTaskResponse,
    CalendarItemKind,
    ConsistencyFindingResponse,
    EvidenceStrengthValue,
    PageResponse,
    RequirementImportanceValue,
)


def page_response(limit: int, has_more: bool, next_cursor: str | None) -> PageResponse:
    return PageResponse(limit=limit, has_more=has_more, next_cursor=next_cursor)


def application_summary_response(summary: ApplicationSummary) -> ApplicationSummaryResponse:
    value = summary.application
    return ApplicationSummaryResponse(
        id=value.id,
        job_id=value.job_id,
        job_version=value.job_version,
        job_title=value.job_title,
        company=value.company,
        location=value.location,
        job_analysis_id=value.job_analysis_id,
        resume_id=value.resume_id,
        resume_version_id=value.resume_version_id,
        resume_version_number=value.resume_version_number,
        resume_title=value.resume_title,
        source=value.source,
        industry=value.industry,
        stage=value.stage.value,
        application_deadline=value.application_deadline,
        follow_up_at=value.follow_up_at,
        referral_status=value.referral_status.value,
        outcome_status=value.outcome_status.value,
        rejection_reason=value.rejection_reason,
        offer_summary=value.offer_summary,
        task_count=summary.task_count,
        open_task_count=summary.open_task_count,
        note_count=summary.note_count,
        event_count=summary.event_count,
        pack_count=summary.pack_count,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def application_response(value: ApplicationSummary) -> ApplicationResponse:
    summary = application_summary_response(value)
    application = value.application
    return ApplicationResponse(
        **summary.model_dump(),
        job_source_sha256=application.job_source_sha256,
        job_requirements=[requirement_response(item) for item in application.job_requirements],
        resume_evidence_ids=list(application.resume_evidence_ids),
        evidence_pins=[evidence_pin_response(item) for item in application.evidence_pins],
        resume_claims=[claim_response(item) for item in application.resume_claims],
        contacts=[contact_response(item) for item in application.contacts],
    )


def application_page_response(
    result: PagedResult[ApplicationSummary],
) -> ApplicationPageResponse:
    return ApplicationPageResponse(
        data=[application_summary_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def contact_response(value: ApplicationContact) -> ApplicationContactResponse:
    return ApplicationContactResponse(
        name=value.name,
        role=value.role,
        email=value.email,
        url=value.url,
    )


def claim_response(value: ApplicationDocumentClaim) -> ApplicationClaimResponse:
    return ApplicationClaimResponse(
        id=value.id,
        text=value.text,
        evidence_links=[claim_evidence_link_response(item) for item in value.evidence_links],
        requirement_ids=list(value.requirement_ids),
    )


def claim_evidence_link_response(
    value: ApplicationClaimEvidenceLink,
) -> ApplicationClaimEvidenceLinkResponse:
    return ApplicationClaimEvidenceLinkResponse(
        evidence_id=value.evidence_id,
        evidence_revision_id=value.evidence_revision_id,
    )


def requirement_response(
    value: ApplicationRequirementSnapshot,
) -> ApplicationRequirementResponse:
    return ApplicationRequirementResponse(
        id=value.id,
        requirement_type=value.requirement_type,
        importance=cast(RequirementImportanceValue, value.importance),
        text=value.text,
        source_start=value.source_start,
        source_end=value.source_end,
    )


def evidence_pin_response(value: ApplicationEvidencePin) -> ApplicationEvidencePinResponse:
    return ApplicationEvidencePinResponse(
        evidence_id=value.evidence_id,
        evidence_revision_id=value.evidence_revision_id,
        revision_number=value.revision_number,
        statement=value.statement,
        statement_sha256=value.statement_sha256,
        strength=cast(EvidenceStrengthValue, value.strength),
        has_numeric_claim=value.has_numeric_claim,
    )


def task_response(value: ApplicationTask) -> ApplicationTaskResponse:
    return ApplicationTaskResponse(
        id=value.id,
        application_id=value.application_id,
        title=value.title,
        due_at=value.due_at,
        completed_at=value.completed_at,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def task_page_response(
    result: PagedResult[ApplicationTask],
) -> ApplicationTaskPageResponse:
    return ApplicationTaskPageResponse(
        data=[task_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def note_response(value: ApplicationNote) -> ApplicationNoteResponse:
    return ApplicationNoteResponse(
        id=value.id,
        application_id=value.application_id,
        body=value.body,
        created_at=value.created_at,
    )


def note_page_response(
    result: PagedResult[ApplicationNote],
) -> ApplicationNotePageResponse:
    return ApplicationNotePageResponse(
        data=[note_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def event_response(value: ApplicationEvent) -> ApplicationEventResponse:
    return ApplicationEventResponse(
        id=value.id,
        application_id=value.application_id,
        event_kind=value.event_kind.value,
        occurred_at=value.occurred_at,
        title=value.title,
        description=value.description,
        metadata=value.metadata,
        created_at=value.created_at,
    )


def event_page_response(
    result: PagedResult[ApplicationEvent],
) -> ApplicationEventPageResponse:
    return ApplicationEventPageResponse(
        data=[event_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def finding_response(value: ApplicationConsistencyFinding) -> ConsistencyFindingResponse:
    return ConsistencyFindingResponse(
        code=value.code,
        severity=value.severity.value,
        message=value.message,
        claim_id=value.claim_id,
    )


def document_response(value: ApplicationDocument) -> ApplicationDocumentResponse:
    return ApplicationDocumentResponse(
        id=value.id,
        application_id=value.application_id,
        pack_id=value.pack_id,
        kind=value.kind.value,
        title=value.title,
        body=value.body,
        source_evidence_ids=list(value.source_evidence_ids),
        source_requirement_ids=list(value.source_requirement_ids),
        claims=[claim_response(item) for item in value.claims],
        status=value.status.value,
        consistency_status=value.consistency_status.value,
        consistency_findings=[finding_response(item) for item in value.consistency_findings],
        content_sha256=value.content_sha256,
        created_at=value.created_at,
        deleted_at=value.deleted_at,
    )


def pack_summary_response(
    pack: ApplicationPack,
) -> ApplicationPackSummaryResponse:
    return ApplicationPackSummaryResponse(
        id=pack.id,
        application_id=pack.application_id,
        job_id=pack.job_id,
        job_version=pack.job_version,
        resume_version_id=pack.resume_version_id,
        resume_version_number=pack.resume_version_number,
        application_version=pack.application_version,
        evidence_revision_ids=list(pack.evidence_revision_ids),
        requirement_ids=list(pack.requirement_ids),
        status=pack.status.value,
        consistency_status=pack.consistency_status.value,
        consistency_findings=[finding_response(item) for item in pack.consistency_findings],
        created_at=pack.created_at,
    )


def pack_response(value: ApplicationPackView) -> ApplicationPackResponse:
    summary = pack_summary_response(value.pack)
    return ApplicationPackResponse(
        **summary.model_dump(),
        documents=[
            document_response(item) for item in value.documents if item.status.value != "deleted"
        ],
    )


def pack_page_response(
    result: PagedResult[ApplicationPack],
) -> ApplicationPackPageResponse:
    return ApplicationPackPageResponse(
        data=[pack_summary_response(item) for item in result.data],
        page=page_response(
            result.page.limit,
            result.page.has_more,
            result.page.next_cursor,
        ),
    )


def consistency_response(value: ApplicationPackView) -> ApplicationConsistencyResponse:
    return ApplicationConsistencyResponse(
        pack_id=value.pack.id,
        status=value.pack.consistency_status.value,
        findings=[finding_response(item) for item in value.pack.consistency_findings],
    )


def calendar_response(
    entries: tuple[ApplicationCalendarEntry, ...] | list[ApplicationCalendarEntry],
    *,
    start: date,
    end: date,
) -> ApplicationCalendarResponse:
    items = [
        ApplicationCalendarItemResponse(
            id=item.id,
            application_id=item.application_id,
            kind=cast(CalendarItemKind, item.kind),
            title=item.title,
            on_date=item.on_date,
            completed=item.completed,
        )
        for item in entries
    ]
    return ApplicationCalendarResponse(start=start, end=end, data=items)
