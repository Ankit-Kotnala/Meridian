"""Presentation helpers for Career Growth API responses."""

from __future__ import annotations

from typing import cast

from rezumi.modules.career_growth.application import (
    CareerGrowthInsights,
    CareerHealthRecord,
    CareerHealthSummary,
    CareerReviewSummaryView,
    CareerReviewView,
    DevelopmentItemView,
    EvidenceLinkView,
    GoalMilestoneView,
    GoalSummaryView,
    GoalView,
    PagedResult,
    ReviewVersionView,
    RoleRoadmapView,
)
from rezumi.modules.career_growth.domain import (
    CANONICAL_SCORE_DISCLAIMER,
    PROMOTION_READINESS_DISCLAIMER,
)

from .schemas import (
    CanonicalScoreDisclaimerValue,
    CareerGrowthInsightsResponse,
    CareerHealthComponentResponse,
    CareerHealthFindingResponse,
    CareerHealthPageResponse,
    CareerHealthResponse,
    CareerHealthSummaryResponse,
    CareerReviewPageResponse,
    CareerReviewResponse,
    CareerReviewSummaryResponse,
    ConfirmRoadmapResponse,
    DevelopmentItemPageResponse,
    DevelopmentItemResponse,
    EvidenceLinkResponse,
    GoalMilestoneResponse,
    GoalPageResponse,
    GoalResponse,
    GoalSummaryResponse,
    GrowthAchievementResponse,
    GrowthSkillEvidenceResponse,
    PageResponse,
    PromotionReadinessCheckResponse,
    PromotionReadinessDisclaimerValue,
    PromotionReadinessResponse,
    ReviewVersionResponse,
    RoadmapSkillResponse,
    RoadmapStageResponse,
    RoleRoadmapResponse,
)


def page_response(limit: int, has_more: bool, next_cursor: str | None) -> PageResponse:
    return PageResponse(limit=limit, has_more=has_more, next_cursor=next_cursor)


def evidence_link_response(value: EvidenceLinkView) -> EvidenceLinkResponse:
    link = value.link
    return EvidenceLinkResponse(
        id=link.id,
        target_kind=link.target_kind.value,
        target_id=link.target_id,
        evidence_id=link.evidence_id,
        evidence_revision_id=link.evidence_revision_id,
        revision_number=link.revision_number,
        statement_sha256=link.statement_sha256,
        evidence_revised_at=link.evidence_revised_at,
        created_at=link.created_at,
        support_status="current" if value.is_current else "needs_review",
    )


def milestone_response(value: GoalMilestoneView) -> GoalMilestoneResponse:
    milestone = value.milestone
    return GoalMilestoneResponse(
        id=milestone.id,
        goal_id=milestone.goal_id,
        title=milestone.title,
        status=milestone.status.value,
        target_date=milestone.target_date,
        completed_at=milestone.completed_at,
        evidence_links=[evidence_link_response(item) for item in value.evidence_links],
        version=milestone.version,
        created_at=milestone.created_at,
        updated_at=milestone.updated_at,
    )


def goal_response(value: GoalView) -> GoalResponse:
    goal = value.goal
    return GoalResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        status=goal.status.value,
        target_date=goal.target_date,
        evidence_links=[evidence_link_response(item) for item in value.evidence_links],
        milestones=[milestone_response(item) for item in value.milestones],
        version=goal.version,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def goal_page_response(value: PagedResult[GoalSummaryView]) -> GoalPageResponse:
    return GoalPageResponse(
        data=[
            GoalSummaryResponse(
                id=item.goal.id,
                title=item.goal.title,
                status=item.goal.status.value,
                target_date=item.goal.target_date,
                milestone_count=item.milestone_count,
                evidence_link_count=item.evidence_link_count,
                evidence_needs_review_count=item.evidence_needs_review_count,
                version=item.goal.version,
                updated_at=item.goal.updated_at,
            )
            for item in value.data
        ],
        page=page_response(value.page.limit, value.page.has_more, value.page.next_cursor),
    )


def development_item_response(value: DevelopmentItemView) -> DevelopmentItemResponse:
    item = value.item
    return DevelopmentItemResponse(
        id=item.id,
        kind=item.kind.value,
        title=item.title,
        description=item.description,
        status=item.status.value,
        target_date=item.target_date,
        completed_at=item.completed_at,
        evidence_links=[evidence_link_response(link) for link in value.evidence_links],
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def role_roadmap_response(value: RoleRoadmapView) -> RoleRoadmapResponse:
    return RoleRoadmapResponse(
        role_title=value.role_title,
        stages=[
            RoadmapStageResponse(
                stage=stage.stage,
                skills=[
                    RoadmapSkillResponse(
                        name=skill.name,
                        why=skill.why,
                        how_to_start=skill.how_to_start,
                        already_demonstrated=skill.already_demonstrated,
                    )
                    for skill in stage.skills
                ],
            )
            for stage in value.stages
        ],
    )


def confirm_roadmap_response(
    values: tuple[DevelopmentItemView, ...],
) -> ConfirmRoadmapResponse:
    return ConfirmRoadmapResponse(
        created=[development_item_response(value) for value in values]
    )


def development_item_page_response(
    value: PagedResult[DevelopmentItemView],
) -> DevelopmentItemPageResponse:
    return DevelopmentItemPageResponse(
        data=[development_item_response(item) for item in value.data],
        page=page_response(value.page.limit, value.page.has_more, value.page.next_cursor),
    )


def career_growth_insights_response(
    value: CareerGrowthInsights,
) -> CareerGrowthInsightsResponse:
    return CareerGrowthInsightsResponse(
        achievements=[
            GrowthAchievementResponse(
                evidence_id=item.evidence_id,
                evidence_revision_id=item.evidence_revision_id,
                revision_number=item.revision_number,
                title=item.title,
                statement=item.statement,
                evidence_type=item.evidence_type,
                strength=item.strength,
                revised_at=item.revised_at,
                skill_ids=list(item.skill_ids),
            )
            for item in value.achievements
        ],
        skills=[
            GrowthSkillEvidenceResponse(
                skill_id=item.skill_id,
                name=item.name,
                category=item.category,
                proficiency=item.proficiency,
                evidence_count=item.evidence_count,
                evidence_ids=list(item.evidence_ids),
                latest_evidence_at=item.latest_evidence_at,
            )
            for item in value.skills
        ],
        promotion_readiness=PromotionReadinessResponse(
            status=value.promotion_readiness.status.value,
            generated_at=value.promotion_readiness.generated_at,
            checks=[
                PromotionReadinessCheckResponse(
                    code=item.code,
                    label=item.label,
                    status=item.status.value,
                    explanation=item.explanation,
                    evidence_count=item.evidence_count,
                    evidence_ids=list(item.evidence_ids),
                )
                for item in value.promotion_readiness.checks
            ],
            disclaimer=cast(
                PromotionReadinessDisclaimerValue,
                PROMOTION_READINESS_DISCLAIMER,
            ),
        ),
        annual_resume_refreshes=[
            development_item_response(item) for item in value.annual_resume_refreshes
        ],
    )


def review_version_response(value: ReviewVersionView) -> ReviewVersionResponse:
    version = value.version
    return ReviewVersionResponse(
        id=version.id,
        review_id=version.review_id,
        version_number=version.version_number,
        status=version.status.value,
        title=version.title,
        summary=version.summary,
        achievements=version.achievements,
        growth_areas=version.growth_areas,
        next_focus=version.next_focus,
        change_reason=version.change_reason,
        material_change=version.material_change,
        supersedes_version_id=version.supersedes_version_id,
        content_sha256=version.content_sha256,
        evidence_links=[evidence_link_response(item) for item in value.evidence_links],
        created_at=version.created_at,
    )


def career_review_response(value: CareerReviewView) -> CareerReviewResponse:
    review = value.review
    return CareerReviewResponse(
        id=review.id,
        cadence=review.cadence.value,
        period_start=review.period_start,
        period_end=review.period_end,
        latest_version_id=review.latest_version_id,
        latest_version_number=review.latest_version_number,
        latest_status=review.latest_status.value,
        current_version=review_version_response(value.current_version),
        history=[review_version_response(item) for item in value.history],
        version=review.version,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def career_review_page_response(
    value: PagedResult[CareerReviewSummaryView],
) -> CareerReviewPageResponse:
    return CareerReviewPageResponse(
        data=[
            CareerReviewSummaryResponse(
                id=item.review.id,
                cadence=item.review.cadence.value,
                period_start=item.review.period_start,
                period_end=item.review.period_end,
                latest_version_id=item.review.latest_version_id,
                latest_version_number=item.review.latest_version_number,
                latest_status=item.review.latest_status.value,
                current_title=item.current_title,
                history_count=item.history_count,
                evidence_link_count=item.evidence_link_count,
                evidence_needs_review_count=item.evidence_needs_review_count,
                version=item.review.version,
                created_at=item.review.created_at,
                updated_at=item.review.updated_at,
            )
            for item in value.data
        ],
        page=page_response(value.page.limit, value.page.has_more, value.page.next_cursor),
    )


def career_health_response(value: CareerHealthRecord) -> CareerHealthResponse:
    analysis = value.analysis
    return CareerHealthResponse(
        id=analysis.id,
        engine_version=analysis.engine_version,
        configuration_version=analysis.configuration_version,
        feature_schema_version=analysis.feature_schema_version,
        input_snapshot=analysis.input_snapshot,
        configuration_snapshot=analysis.configuration_snapshot,
        formula_snapshot=analysis.formula_snapshot,
        snapshot_sha256=analysis.snapshot_sha256.hex(),
        status=analysis.status.value,
        raw_score_basis_points=analysis.raw_score_basis_points,
        display_score=analysis.display_score,
        label=analysis.label.value,
        applicable_component_count=analysis.applicable_component_count,
        applicable_weight_basis_points=analysis.applicable_weight_basis_points,
        insufficient_reason=analysis.insufficient_reason,
        disclaimer=cast(CanonicalScoreDisclaimerValue, CANONICAL_SCORE_DISCLAIMER),
        components=[
            CareerHealthComponentResponse(
                id=item.id,
                dimension=item.dimension.value,
                configured_weight_basis_points=item.configured_weight_basis_points,
                applicable=item.applicable,
                score_basis_points=item.score_basis_points,
                contribution_basis_points=item.contribution_basis_points,
                explanation=item.explanation,
            )
            for item in value.components
        ],
        findings=[
            CareerHealthFindingResponse(
                id=item.id,
                code=item.code,
                severity=item.severity.value,
                message=item.message,
            )
            for item in value.findings
        ],
        created_at=analysis.created_at,
    )


def career_health_page_response(
    value: PagedResult[CareerHealthSummary],
) -> CareerHealthPageResponse:
    return CareerHealthPageResponse(
        data=[
            CareerHealthSummaryResponse(
                id=item.id,
                engine_version=item.engine_version,
                status=item.status.value,
                raw_score_basis_points=item.raw_score_basis_points,
                display_score=item.display_score,
                label=item.label.value,
                applicable_component_count=item.applicable_component_count,
                applicable_weight_basis_points=item.applicable_weight_basis_points,
                insufficient_reason=item.insufficient_reason,
                disclaimer=cast(
                    CanonicalScoreDisclaimerValue,
                    CANONICAL_SCORE_DISCLAIMER,
                ),
                finding_count=item.finding_count,
                created_at=item.created_at,
            )
            for item in value.data
        ],
        page=page_response(value.page.limit, value.page.has_more, value.page.next_cursor),
    )
