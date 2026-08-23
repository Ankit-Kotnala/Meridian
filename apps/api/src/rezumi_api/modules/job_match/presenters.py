"""Presentation helpers for Job Match API responses."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from rezumi.modules.job_match.application import (
    JobMatchView,
    JobRecord,
    OpportunityPriorityView,
    PagedResult,
)
from rezumi.modules.job_match.application.job_catalog_ports import CatalogJobListing
from rezumi.modules.job_match.application.job_catalog_query import JobCatalogSearchResult
from rezumi.modules.job_match.domain import RequirementEvidenceLink, RequirementMatch

from rezumi_api.modules.job_match.schemas import (
    JobCatalogBrowseResponse,
    JobCatalogListingResponse,
    JobCatalogSearchResponse,
    JobMatchAnalysisResponse,
    JobMatchComponentResponse,
    JobPageResponse,
    JobRequirementResponse,
    JobResponse,
    OpportunityPriorityResponse,
    PageResponse,
    RequirementEvidenceResponse,
    RequirementMatchPageResponse,
    RequirementMatchResponse,
    RolePreferenceResponse,
)


def page_response(limit: int, has_more: bool, next_cursor: str | None) -> PageResponse:
    return PageResponse(limit=limit, has_more=has_more, next_cursor=next_cursor)


def job_response(record: JobRecord) -> JobResponse:
    job = record.job
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        work_model=job.work_model.value,
        employment_type=job.employment_type.value,
        compensation=job.compensation,
        application_deadline=job.application_deadline,
        source_kind=job.source_kind.value,
        source_url=job.source_url,
        target_role_id=job.target_role_id,
        target_role_title=job.target_role_title,
        version=job.version,
        requirements=[
            JobRequirementResponse(
                id=requirement.id,
                requirement_type=requirement.requirement_type.value,
                text=requirement.text,
                normalized_text=requirement.normalized_text,
                importance=requirement.importance.value,
                source_start=requirement.source_start,
                source_end=requirement.source_end,
                confidence_basis_points=requirement.confidence_basis_points,
                order=requirement.sort_order,
            )
            for requirement in record.requirements
        ],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def job_page_response(page: PagedResult[JobRecord]) -> JobPageResponse:
    return JobPageResponse(
        data=[job_response(record) for record in page.data],
        page=page_response(
            page.page.limit,
            page.page.has_more,
            page.page.next_cursor,
        ),
    )


def analysis_response(view: JobMatchView) -> JobMatchAnalysisResponse:
    return JobMatchAnalysisResponse(
        id=view.analysis.id,
        job=job_response(JobRecord(job=view.job, requirements=view.requirements)),
        engine_version=view.analysis.engine_version,
        configuration_version=view.analysis.configuration_version,
        feature_schema_version=view.analysis.feature_schema_version,
        raw_score_basis_points=view.analysis.raw_score_basis_points,
        display_score=view.analysis.display_score,
        readiness_label=view.analysis.readiness_label.value,
        hard_gap_count=view.analysis.hard_gap_count,
        insufficient_reason=view.analysis.insufficient_reason,
        summary=view.analysis.summary,
        components=[
            JobMatchComponentResponse(
                dimension=component.dimension,
                weight_basis_points=component.weight_basis_points,
                score_basis_points=component.score_basis_points,
                contribution_basis_points=component.contribution_basis_points,
                explanation=component.explanation,
            )
            for component in view.components
        ],
        requirements=_requirement_matches(view.requirement_matches, view.evidence_links),
        created_at=view.analysis.created_at,
    )


def requirement_match_page_response(view: JobMatchView) -> RequirementMatchPageResponse:
    return RequirementMatchPageResponse(
        data=_requirement_matches(view.requirement_matches, view.evidence_links)
    )


def opportunity_priority_response(view: OpportunityPriorityView) -> OpportunityPriorityResponse:
    priority = view.priority
    return OpportunityPriorityResponse(
        id=priority.id,
        job_id=priority.job_id,
        analysis_id=priority.analysis_id,
        priority_label=priority.priority_label.value,
        priority_score_basis_points=priority.priority_score_basis_points,
        reasons_for=list(priority.reasons_for),
        reconsiderations=list(priority.reconsiderations),
        blockers=list(priority.blockers),
        next_action=priority.next_action,
        created_at=priority.created_at,
    )


def _requirement_matches(
    matches: tuple[RequirementMatch, ...], links: tuple[RequirementEvidenceLink, ...]
) -> list[RequirementMatchResponse]:
    grouped: defaultdict[UUID, list[RequirementEvidenceLink]] = defaultdict(list)
    for link in links:
        grouped[link.requirement_match_id].append(link)
    return [
        RequirementMatchResponse(
            id=match.id,
            requirement_id=match.requirement_id,
            requirement_text=match.requirement_text,
            requirement_type=match.requirement_type.value,
            importance=match.importance.value,
            match_state=match.match_state.value,
            score_basis_points=match.score_basis_points,
            explanation=match.explanation,
            recommended_action=match.recommended_action,
            hard_gap=match.hard_gap,
            evidence=[
                RequirementEvidenceResponse(
                    id=link.id,
                    evidence_id=link.evidence_id,
                    evidence_title=link.evidence_title,
                    evidence_strength=link.evidence_strength,
                    relevance_basis_points=link.relevance_basis_points,
                    rationale=link.rationale,
                )
                for link in grouped[match.id]
            ],
        )
        for match in matches
    ]


def job_catalog_listing_response(listing: CatalogJobListing) -> JobCatalogListingResponse:
    return JobCatalogListingResponse(
        platform=listing.platform,
        external_id=listing.external_id,
        title=listing.title,
        company=listing.company,
        location=listing.location,
        remote=listing.remote,
        application_url=listing.application_url,
        source_text=listing.source_text,
        posted_at=listing.posted_at,
    )


def job_catalog_search_response(result: JobCatalogSearchResult) -> JobCatalogSearchResponse:
    return JobCatalogSearchResponse(
        target_role_titles=list(result.target_role_titles),
        listings=[job_catalog_listing_response(listing) for listing in result.listings],
        matched_target_role=result.matched_target_role,
        suggested_role_titles=list(result.suggested_role_titles),
        selected_role_titles=list(result.selected_role_titles),
    )


def role_preference_response(role_titles: tuple[str, ...]) -> RolePreferenceResponse:
    return RolePreferenceResponse(role_titles=list(role_titles))


def job_catalog_browse_response(
    listings: tuple[CatalogJobListing, ...], *, has_more: bool, next_offset: int
) -> JobCatalogBrowseResponse:
    return JobCatalogBrowseResponse(
        listings=[job_catalog_listing_response(listing) for listing in listings],
        has_more=has_more,
        next_offset=next_offset,
    )
