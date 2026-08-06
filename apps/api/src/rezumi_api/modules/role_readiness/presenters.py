"""Pure Role Readiness wire presenters."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from rezumi.modules.role_readiness.application import (
    Page,
    PagedResult,
    RoleComparisonView,
    RoleDetail,
    RoleReadinessView,
    SavedRoleView,
)
from rezumi.modules.role_readiness.domain import (
    CompetencyEvidenceLink,
    CompetencyResult,
    ReadinessComponent,
    RoleCompetency,
    RoleDefinition,
    RoleTaxonomyVersion,
)

from rezumi_api.modules.role_readiness.schemas import (
    CompetencyEvidenceResponse,
    CompetencyResultResponse,
    ComponentResponse,
    PageResponse,
    RoleComparisonEntryResponse,
    RoleComparisonResponse,
    RoleCompetencyResponse,
    RolePageResponse,
    RoleReadinessPageResponse,
    RoleReadinessResponse,
    RoleResponse,
    SavedRolePageResponse,
    SavedRoleResponse,
    TaxonomyResponse,
)


def page_response(page: Page) -> PageResponse:
    return PageResponse(
        limit=page.limit,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


def taxonomy_response(value: RoleTaxonomyVersion) -> TaxonomyResponse:
    return TaxonomyResponse(
        id=value.id,
        version=value.version,
        source_name=value.source_name,
        source_license=value.source_license,
        description=value.description,
        published_at=value.published_at,
    )


def role_response(
    role: RoleDefinition,
    taxonomy: RoleTaxonomyVersion,
    competencies: tuple[RoleCompetency, ...],
) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        slug=role.slug,
        title=role.title,
        seniority=role.seniority.value,
        industry=role.industry,
        domain=role.domain,
        location_scope=role.location_scope,
        company_type=role.company_type,
        description=role.description,
        version=role.version,
        taxonomy=taxonomy_response(taxonomy),
        competencies=[
            RoleCompetencyResponse(
                id=item.id,
                dimension=item.dimension.value,
                label=item.label,
                description=item.description,
                importance=item.importance.value,
                skill_keywords=list(item.skill_keywords),
                evidence_keywords=list(item.evidence_keywords),
                transferable_keywords=list(item.transferable_keywords),
                adjacent_keywords=list(item.adjacent_keywords),
                order=item.sort_order,
            )
            for item in competencies
        ],
    )


def role_detail_response(value: RoleDetail) -> RoleResponse:
    return role_response(value.role, value.taxonomy, value.competencies)


def role_page_response(page: PagedResult[RoleDetail]) -> RolePageResponse:
    return RolePageResponse(
        data=[role_detail_response(item) for item in page.data],
        page=page_response(page.page),
    )


def saved_role_response(
    value: SavedRoleView, competencies: tuple[RoleCompetency, ...]
) -> SavedRoleResponse:
    saved = value.saved_role
    return SavedRoleResponse(
        id=saved.id,
        role=role_response(value.role, value.taxonomy, competencies),
        notes=saved.notes,
        version=saved.version,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


def saved_role_page_response(
    page: PagedResult[SavedRoleView],
    competencies_by_role: dict[UUID, tuple[RoleCompetency, ...]],
) -> SavedRolePageResponse:
    return SavedRolePageResponse(
        data=[
            saved_role_response(item, competencies_by_role.get(item.role.id, ()))
            for item in page.data
        ],
        page=page_response(page.page),
    )


def analysis_response(
    value: RoleReadinessView, competencies: tuple[RoleCompetency, ...]
) -> RoleReadinessResponse:
    links_by_result: defaultdict[UUID, list[CompetencyEvidenceLink]] = defaultdict(list)
    for link in value.evidence_links:
        links_by_result[link.competency_result_id].append(link)
    return RoleReadinessResponse(
        id=value.analysis.id,
        role=role_response(value.role, value.taxonomy, competencies),
        saved_role_id=value.analysis.saved_role_id,
        engine_version=value.analysis.engine_version,
        configuration_version=value.analysis.configuration_version,
        feature_schema_version=value.analysis.feature_schema_version,
        taxonomy_version=value.analysis.taxonomy_version,
        raw_score_basis_points=value.analysis.raw_score_basis_points,
        display_score=value.analysis.display_score,
        readiness_label=value.analysis.readiness_label.value,
        insufficient_reason=value.analysis.insufficient_reason,
        summary=value.analysis.summary,
        components=[component_response(item) for item in value.components],
        competencies=[
            competency_result_response(item, tuple(links_by_result[item.id]))
            for item in value.competency_results
        ],
        created_at=value.analysis.created_at,
    )


def component_response(value: ReadinessComponent) -> ComponentResponse:
    return ComponentResponse(
        dimension=value.dimension.value,
        weight_basis_points=value.weight_basis_points,
        score_basis_points=value.score_basis_points,
        contribution_basis_points=value.contribution_basis_points,
        explanation=value.explanation,
    )


def competency_result_response(
    value: CompetencyResult, evidence: tuple[CompetencyEvidenceLink, ...]
) -> CompetencyResultResponse:
    return CompetencyResultResponse(
        id=value.id,
        competency_id=value.competency_id,
        dimension=value.dimension.value,
        label=value.label,
        importance=value.importance.value,
        match_state=value.match_state.value,
        score_basis_points=value.score_basis_points,
        explanation=value.explanation,
        gap_kind=value.gap_kind,
        evidence=[
            CompetencyEvidenceResponse(
                id=link.id,
                evidence_id=link.evidence_id,
                evidence_title=link.evidence_title,
                evidence_strength=link.evidence_strength,
                relevance_basis_points=link.relevance_basis_points,
                rationale=link.rationale,
            )
            for link in evidence
        ],
    )


def analysis_page_response(
    page: PagedResult[RoleReadinessView],
    competencies_by_role: dict[UUID, tuple[RoleCompetency, ...]],
) -> RoleReadinessPageResponse:
    return RoleReadinessPageResponse(
        data=[
            analysis_response(item, competencies_by_role.get(item.role.id, ()))
            for item in page.data
        ],
        page=page_response(page.page),
    )


def comparison_response(
    value: RoleComparisonView,
    competencies_by_role: dict[UUID, tuple[RoleCompetency, ...]],
) -> RoleComparisonResponse:
    return RoleComparisonResponse(
        note=value.note,
        entries=[
            RoleComparisonEntryResponse(
                role=role_response(
                    entry.role,
                    entry.taxonomy,
                    competencies_by_role.get(entry.role.id, ()),
                ),
                latest_analysis=(
                    analysis_response(
                        entry.latest_analysis,
                        competencies_by_role.get(entry.role.id, ()),
                    )
                    if entry.latest_analysis is not None
                    else None
                ),
                required_gap_count=entry.required_gap_count,
                helpful_gap_count=entry.helpful_gap_count,
                demonstrated_count=entry.demonstrated_count,
                strongest_evidence_count=entry.strongest_evidence_count,
            )
            for entry in value.entries
        ],
    )
