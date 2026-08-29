"""Authenticated Career Growth and Career Health HTTP contract tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from rezumi.modules.career_growth.application import (
    CareerGrowthInsights,
    CareerGrowthService,
    CareerHealthRecord,
    CareerHealthSummary,
    CareerReviewSummaryView,
    CareerReviewView,
    DevelopmentItemView,
    EvidenceLinkView,
    GoalMilestoneView,
    GoalSummaryView,
    GoalView,
    GrowthAchievementSnapshot,
    GrowthSkillSnapshot,
    Page,
    PagedResult,
    PromotionReadinessCheck,
    PromotionReadinessReport,
    ReviewVersionView,
    RoadmapSkillView,
    RoadmapStageView,
    RoleRoadmapView,
)
from rezumi.modules.career_growth.domain import (
    CANONICAL_SCORE_DISCLAIMER,
    PROMOTION_READINESS_DISCLAIMER,
    CareerGoal,
    CareerGrowthEvidenceLink,
    CareerGrowthNotFound,
    CareerGrowthQuotaExceeded,
    CareerGrowthVersionConflict,
    CareerHealthAnalysis,
    CareerHealthComponent,
    CareerHealthDimension,
    CareerHealthFinding,
    CareerHealthLabel,
    CareerHealthStatus,
    CareerReview,
    CareerReviewVersion,
    DevelopmentItem,
    DevelopmentKind,
    DevelopmentStatus,
    EvidenceTargetKind,
    FindingSeverity,
    GoalMilestone,
    GoalStatus,
    MilestoneStatus,
    PromotionCheckStatus,
    PromotionReadinessStatus,
    ReviewCadence,
    ReviewVersionStatus,
    career_health_snapshot_hash,
    review_content_hash,
)
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal, AuthMethod

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.main import create_app

_ORIGIN = "http://localhost:3000"
_NOW = datetime(2026, 7, 25, 6, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class CareerGrowthSample:
    owner_id: UUID
    other_id: UUID
    evidence_id: UUID
    evidence_revision_id: UUID
    goal: GoalView
    milestone: GoalMilestoneView
    development: DevelopmentItemView
    review: CareerReviewView
    health: CareerHealthRecord


def _principal(user_id: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _evidence_link(
    *,
    owner_id: UUID,
    evidence_id: UUID,
    evidence_revision_id: UUID,
    target_kind: EvidenceTargetKind,
    target_id: UUID,
) -> EvidenceLinkView:
    return EvidenceLinkView(
        link=CareerGrowthEvidenceLink(
            id=uuid4(),
            owner_user_id=owner_id,
            target_kind=target_kind,
            target_id=target_id,
            evidence_id=evidence_id,
            evidence_revision_id=evidence_revision_id,
            revision_number=4,
            statement_sha256=hashlib.sha256(b"Exact supported evidence").hexdigest(),
            evidence_revised_at=_NOW,
            created_at=_NOW,
        ),
        is_current=True,
    )


def _sample() -> CareerGrowthSample:
    owner_id = uuid4()
    other_id = uuid4()
    evidence_id = uuid4()
    evidence_revision_id = uuid4()

    goal_id = uuid4()
    milestone_id = uuid4()
    goal_link = _evidence_link(
        owner_id=owner_id,
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        target_kind=EvidenceTargetKind.GOAL,
        target_id=goal_id,
    )
    milestone_link = _evidence_link(
        owner_id=owner_id,
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        target_kind=EvidenceTargetKind.MILESTONE,
        target_id=milestone_id,
    )
    milestone = GoalMilestoneView(
        milestone=GoalMilestone(
            id=milestone_id,
            owner_user_id=owner_id,
            goal_id=goal_id,
            title="Complete architecture review",
            status=MilestoneStatus.IN_PROGRESS,
            target_date=date(2026, 9, 30),
            completed_at=None,
            version=3,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        evidence_links=(milestone_link,),
    )
    goal = GoalView(
        goal=CareerGoal(
            id=goal_id,
            owner_user_id=owner_id,
            title="Grow architecture leadership",
            description="A user-authored, evidence-linked goal.",
            status=GoalStatus.ACTIVE,
            target_date=date(2026, 12, 31),
            version=2,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        evidence_links=(goal_link,),
        milestones=(milestone,),
    )

    development_id = uuid4()
    development_link = _evidence_link(
        owner_id=owner_id,
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        target_kind=EvidenceTargetKind.DEVELOPMENT_ITEM,
        target_id=development_id,
    )
    development = DevelopmentItemView(
        item=DevelopmentItem(
            id=development_id,
            owner_user_id=owner_id,
            kind=DevelopmentKind.LEARNING,
            title="Complete distributed systems coursework",
            description="A focused learning item.",
            status=DevelopmentStatus.IN_PROGRESS,
            target_date=date(2026, 10, 31),
            completed_at=None,
            version=4,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        evidence_links=(development_link,),
    )

    review_id = uuid4()
    review_version_id = uuid4()
    review_title = "Q2 career review"
    review_summary = "Documented progress based on the user's career record."
    content_sha256 = review_content_hash(
        title=review_title,
        summary=review_summary,
        achievements="Completed the supported architecture milestone.",
        growth_areas="Continue developing distributed systems depth.",
        next_focus="Finish the current learning item.",
    )
    review_version = CareerReviewVersion(
        id=review_version_id,
        owner_user_id=owner_id,
        review_id=review_id,
        version_number=1,
        status=ReviewVersionStatus.DRAFT,
        title=review_title,
        summary=review_summary,
        achievements="Completed the supported architecture milestone.",
        growth_areas="Continue developing distributed systems depth.",
        next_focus="Finish the current learning item.",
        change_reason="review_created",
        material_change=False,
        supersedes_version_id=None,
        content_sha256=content_sha256,
        created_at=_NOW,
    )
    review_link = _evidence_link(
        owner_id=owner_id,
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        target_kind=EvidenceTargetKind.REVIEW_VERSION,
        target_id=review_version_id,
    )
    version_view = ReviewVersionView(
        version=review_version,
        evidence_links=(review_link,),
    )
    review = CareerReviewView(
        review=CareerReview(
            id=review_id,
            owner_user_id=owner_id,
            cadence=ReviewCadence.QUARTERLY,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            latest_version_id=review_version_id,
            latest_version_number=1,
            latest_status=ReviewVersionStatus.DRAFT,
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        current_version=version_view,
        history=(version_view,),
    )

    analysis_id = uuid4()
    health_input = {
        "asOf": "2026-07-25",
        "evidenceRevisionIds": [str(evidence_revision_id)],
    }
    health_configuration = {"weightsBasisPoints": {"goalProgress": 2_500}}
    health_formula = {"arithmetic": "integer_basis_points_half_up"}
    health = CareerHealthRecord(
        analysis=CareerHealthAnalysis(
            id=analysis_id,
            owner_user_id=owner_id,
            engine_version="career-health/1.0.0",
            configuration_version="career-health-default/1",
            feature_schema_version="career-health-features/1",
            input_snapshot=health_input,
            configuration_snapshot=health_configuration,
            formula_snapshot=health_formula,
            snapshot_sha256=career_health_snapshot_hash(
                input_snapshot=health_input,
                configuration_snapshot=health_configuration,
                formula_snapshot=health_formula,
            ),
            status=CareerHealthStatus.COMPLETE,
            raw_score_basis_points=8_200,
            display_score=82,
            label=CareerHealthLabel.WELL_MAINTAINED,
            applicable_component_count=3,
            applicable_weight_basis_points=6_500,
            insufficient_reason=None,
            disclaimer=CANONICAL_SCORE_DISCLAIMER,
            created_at=_NOW,
        ),
        components=(
            CareerHealthComponent(
                id=uuid4(),
                owner_user_id=owner_id,
                analysis_id=analysis_id,
                dimension=CareerHealthDimension.GOAL_PROGRESS,
                configured_weight_basis_points=2_500,
                applicable=True,
                score_basis_points=8_000,
                contribution_basis_points=2_000,
                explanation="Deterministic goal and milestone progress.",
            ),
        ),
        findings=(
            CareerHealthFinding(
                id=uuid4(),
                owner_user_id=owner_id,
                analysis_id=analysis_id,
                code="review_cadence_attention",
                severity=FindingSeverity.ATTENTION,
                message="Review cadence needs attention.",
            ),
        ),
    )
    return CareerGrowthSample(
        owner_id=owner_id,
        other_id=other_id,
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        goal=goal,
        milestone=milestone,
        development=development,
        review=review,
        health=health,
    )


def _services(
    sample: CareerGrowthSample,
) -> tuple[IdentityService, CareerGrowthService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(sample.owner_id)
    service = create_autospec(CareerGrowthService, instance=True)
    service.list_goals.return_value = PagedResult(
        data=(
            GoalSummaryView(
                goal=sample.goal.goal,
                milestone_count=1,
                evidence_link_count=1,
                evidence_needs_review_count=0,
            ),
        ),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_goal.return_value = sample.goal
    service.get_goal.return_value = sample.goal
    service.update_goal.return_value = sample.goal
    service.delete_goal.return_value = None
    service.get_insights.return_value = CareerGrowthInsights(
        achievements=(
            GrowthAchievementSnapshot(
                evidence_id=sample.evidence_id,
                evidence_revision_id=sample.evidence_revision_id,
                revision_number=3,
                title="Verified fictional achievement",
                statement="The owner confirmed a fictional evidence-backed result.",
                evidence_type="achievement",
                strength="confirmed",
                revised_at=_NOW,
                skill_ids=(),
            ),
        ),
        skills=(
            GrowthSkillSnapshot(
                skill_id=uuid4(),
                name="Fictional systems skill",
                category="technical",
                proficiency="advanced",
                evidence_count=1,
                evidence_ids=(sample.evidence_id,),
                latest_evidence_at=_NOW,
            ),
        ),
        promotion_readiness=PromotionReadinessReport(
            status=PromotionReadinessStatus.BUILDING,
            generated_at=_NOW,
            checks=tuple(
                PromotionReadinessCheck(
                    code=f"check_{index}",
                    label=f"Check {index}",
                    status=PromotionCheckStatus.NEEDS_ACTION,
                    explanation="Owner action remains.",
                )
                for index in range(6)
            ),
            disclaimer=PROMOTION_READINESS_DISCLAIMER,
        ),
        annual_resume_refreshes=(sample.development,),
    )
    service.create_milestone.return_value = sample.milestone
    service.update_milestone.return_value = sample.milestone
    service.delete_milestone.return_value = None
    service.list_development_items.return_value = PagedResult(
        data=(sample.development,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_development_item.return_value = sample.development
    service.get_development_item.return_value = sample.development
    service.update_development_item.return_value = sample.development
    service.delete_development_item.return_value = None
    service.list_reviews.return_value = PagedResult(
        data=(
            CareerReviewSummaryView(
                review=sample.review.review,
                current_title=sample.review.current_version.version.title,
                history_count=len(sample.review.history),
                evidence_link_count=len(
                    sample.review.current_version.evidence_links,
                ),
                evidence_needs_review_count=0,
            ),
        ),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_review.return_value = sample.review
    service.get_review.return_value = sample.review
    service.revise_review.return_value = sample.review
    service.finalize_review.return_value = sample.review
    service.delete_review.return_value = None
    service.list_career_health.return_value = PagedResult(
        data=(
            CareerHealthSummary(
                id=sample.health.analysis.id,
                engine_version=sample.health.analysis.engine_version,
                status=sample.health.analysis.status,
                raw_score_basis_points=sample.health.analysis.raw_score_basis_points,
                display_score=sample.health.analysis.display_score,
                label=sample.health.analysis.label,
                applicable_component_count=(sample.health.analysis.applicable_component_count),
                applicable_weight_basis_points=(
                    sample.health.analysis.applicable_weight_basis_points
                ),
                insufficient_reason=sample.health.analysis.insufficient_reason,
                disclaimer=sample.health.analysis.disclaimer,
                finding_count=len(sample.health.findings),
                created_at=sample.health.analysis.created_at,
            ),
        ),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.analyze_career_health.return_value = sample.health
    service.get_career_health.return_value = sample.health
    service.delete_career_health.return_value = None
    service.get_role_roadmap.return_value = RoleRoadmapView(
        role_title="AI Engineer",
        stages=(
            RoadmapStageView(
                stage="Foundations",
                skills=(
                    RoadmapSkillView(
                        name="Python",
                        why="Most ML tooling is Python-first.",
                        how_to_start="Build one small script end to end.",
                        already_demonstrated=True,
                    ),
                ),
            ),
        ),
    )
    service.confirm_roadmap_selection.return_value = (sample.development,)
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
    service: CareerGrowthService,
) -> TestClient:
    app = create_app(
        settings,
        database=database,
        identity=identity,
        career_growth=service,
    )
    client = TestClient(app)
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def _goal_payload(sample: CareerGrowthSample) -> dict[str, object]:
    goal = sample.goal.goal
    return {
        "title": goal.title,
        "description": goal.description,
        "status": goal.status.value,
        "targetDate": goal.target_date.isoformat() if goal.target_date is not None else None,
        "evidenceIds": [str(sample.evidence_id)],
    }


def _milestone_payload(sample: CareerGrowthSample) -> dict[str, object]:
    milestone = sample.milestone.milestone
    return {
        "title": milestone.title,
        "status": milestone.status.value,
        "targetDate": (
            milestone.target_date.isoformat() if milestone.target_date is not None else None
        ),
        "evidenceIds": [str(sample.evidence_id)],
    }


def _development_payload(sample: CareerGrowthSample) -> dict[str, object]:
    item = sample.development.item
    return {
        "kind": item.kind.value,
        "title": item.title,
        "description": item.description,
        "status": item.status.value,
        "targetDate": item.target_date.isoformat() if item.target_date is not None else None,
        "evidenceIds": [str(sample.evidence_id)],
    }


def _review_payload(sample: CareerGrowthSample) -> dict[str, object]:
    review = sample.review.review
    version = sample.review.current_version.version
    return {
        "cadence": review.cadence.value,
        "periodStart": review.period_start.isoformat(),
        "periodEnd": review.period_end.isoformat(),
        "content": {
            "title": version.title,
            "summary": version.summary,
            "achievements": version.achievements,
            "growthAreas": version.growth_areas,
            "nextFocus": version.next_focus,
        },
        "evidenceIds": [str(sample.evidence_id)],
    }


def test_career_growth_complete_owner_scoped_http_workflow(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    goal_id = sample.goal.goal.id
    milestone_id = sample.milestone.milestone.id
    development_id = sample.development.item.id
    review_id = sample.review.review.id
    analysis_id = sample.health.analysis.id

    with _client(settings, fake_database, identity, service) as client:
        insights = client.get("/api/v1/career-growth/insights")
        assert insights.status_code == 200
        assert insights.headers["Cache-Control"] == "no-store"
        insight_body = insights.json()
        assert insight_body["achievements"][0]["evidenceRevisionId"] == str(
            sample.evidence_revision_id
        )
        assert insight_body["skills"][0]["evidenceIds"] == [str(sample.evidence_id)]
        assert insight_body["promotionReadiness"]["disclaimer"] == (PROMOTION_READINESS_DISCLAIMER)
        assert insight_body["annualResumeRefreshes"]
        service.get_insights.assert_awaited_once_with(sample.owner_id)

        goals = client.get(
            "/api/v1/career-growth/goals",
            params={"cursor": "eyJvZmZzZXQiOjI1fQ", "limit": 25},
        )
        assert goals.status_code == 200
        assert goals.headers["Cache-Control"] == "no-store"
        assert goals.json()["data"][0]["evidenceLinkCount"] == 1
        assert goals.json()["data"][0]["milestoneCount"] == 1
        assert goals.json()["data"][0]["evidenceNeedsReviewCount"] == 0
        service.list_goals.assert_awaited_once_with(
            sample.owner_id,
            cursor="eyJvZmZzZXQiOjI1fQ",
            limit=25,
        )

        created_goal = client.post(
            "/api/v1/career-growth/goals",
            json=_goal_payload(sample),
            headers=_write_headers(idempotency="career-goal-create"),
        )
        assert created_goal.status_code == 201
        assert created_goal.headers["ETag"] == '"2"'
        goal_command = service.create_goal.await_args.args[1]
        assert goal_command.status is GoalStatus.ACTIVE
        assert goal_command.evidence_ids == (sample.evidence_id,)
        assert service.create_goal.await_args.args[2] == "career-goal-create"

        goal = client.get(f"/api/v1/career-growth/goals/{goal_id}")
        assert goal.status_code == 200
        assert goal.headers["ETag"] == '"2"'
        assert "ownerUserId" not in goal.json()

        updated_goal = client.put(
            f"/api/v1/career-growth/goals/{goal_id}",
            json=_goal_payload(sample),
            headers=_write_headers(version=2),
        )
        assert updated_goal.status_code == 200
        assert service.update_goal.await_args.args[2] == 2

        created_milestone = client.post(
            f"/api/v1/career-growth/goals/{goal_id}/milestones",
            json=_milestone_payload(sample),
            headers=_write_headers(idempotency="career-milestone-create"),
        )
        assert created_milestone.status_code == 201
        assert created_milestone.headers["ETag"] == '"3"'
        assert service.create_milestone.await_args.args[3] == "career-milestone-create"

        updated_milestone = client.put(
            f"/api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}",
            json=_milestone_payload(sample),
            headers=_write_headers(version=3),
        )
        assert updated_milestone.status_code == 200
        assert service.update_milestone.await_args.args[3] == 3

        development_items = client.get(
            "/api/v1/career-growth/development-items",
            params={"limit": 25},
        )
        assert development_items.status_code == 200
        assert development_items.json()["data"][0]["kind"] == "learning"

        created_development = client.post(
            "/api/v1/career-growth/development-items",
            json=_development_payload(sample),
            headers=_write_headers(idempotency="career-development-create"),
        )
        assert created_development.status_code == 201
        assert created_development.headers["ETag"] == '"4"'
        assert service.create_development_item.await_args.args[1].kind is (DevelopmentKind.LEARNING)

        development = client.get(f"/api/v1/career-growth/development-items/{development_id}")
        assert development.status_code == 200
        assert development.json()["evidenceLinks"][0]["statementSha256"]

        updated_development = client.put(
            f"/api/v1/career-growth/development-items/{development_id}",
            json=_development_payload(sample),
            headers=_write_headers(version=4),
        )
        assert updated_development.status_code == 200
        assert service.update_development_item.await_args.args[2] == 4

        reviews = client.get(
            "/api/v1/career-growth/reviews",
            params={"limit": 25},
        )
        assert reviews.status_code == 200
        assert reviews.json()["data"][0]["currentTitle"] == (
            sample.review.current_version.version.title
        )
        assert reviews.json()["data"][0]["historyCount"] == 1
        assert reviews.json()["data"][0]["evidenceLinkCount"] == 1

        created_review = client.post(
            "/api/v1/career-growth/reviews",
            json=_review_payload(sample),
            headers=_write_headers(idempotency="career-review-create"),
        )
        assert created_review.status_code == 201
        assert created_review.headers["ETag"] == '"1"'
        assert service.create_review.await_args.args[1].cadence is ReviewCadence.QUARTERLY

        review = client.get(f"/api/v1/career-growth/reviews/{review_id}")
        assert review.status_code == 200
        assert review.json()["currentVersion"]["id"] == str(
            sample.review.current_version.version.id
        )

        revise_payload = _review_payload(sample)
        revise_payload = {
            "content": revise_payload["content"],
            "changeReason": "Owner recorded a material correction.",
            "evidenceIds": revise_payload["evidenceIds"],
        }
        revised_review = client.post(
            f"/api/v1/career-growth/reviews/{review_id}/versions",
            json=revise_payload,
            headers=_write_headers(version=1),
        )
        assert revised_review.status_code == 201
        assert service.revise_review.await_args.args[2] == 1
        assert service.revise_review.await_args.args[3].change_reason == (
            "Owner recorded a material correction."
        )

        finalized_review = client.post(
            f"/api/v1/career-growth/reviews/{review_id}/finalizations",
            headers=_write_headers(version=1, idempotency="finalize-review-key"),
        )
        assert finalized_review.status_code == 201
        assert service.finalize_review.await_args.args[2] == 1
        assert service.finalize_review.await_args.args[3] == "finalize-review-key"

        analyses = client.get(
            "/api/v1/career-growth/career-health/analyses",
            params={"limit": 25},
        )
        assert analyses.status_code == 200
        score = analyses.json()["data"][0]
        assert score["disclaimer"] == CANONICAL_SCORE_DISCLAIMER
        assert score["displayScore"] == 82
        assert score["findingCount"] == 1
        assert {
            "employerScore",
            "atsScore",
            "hiringProbability",
            "employmentGuarantee",
        }.isdisjoint(score)

        analyzed = client.post(
            "/api/v1/career-growth/career-health/analyses",
            headers=_write_headers(idempotency="career-health-analyze"),
        )
        assert analyzed.status_code == 201
        assert analyzed.json()["disclaimer"] == CANONICAL_SCORE_DISCLAIMER
        assert service.analyze_career_health.await_args.args[1] == "career-health-analyze"

        analysis = client.get(f"/api/v1/career-growth/career-health/analyses/{analysis_id}")
        assert analysis.status_code == 200
        assert analysis.json()["formulaSnapshot"]["arithmetic"] == ("integer_basis_points_half_up")
        assert analysis.json()["snapshotSha256"] == (sample.health.analysis.snapshot_sha256.hex())
        assert analysis.json()["components"][0]["dimension"] == "goal_progress"
        assert analysis.json()["findings"][0]["severity"] == "attention"
        service.get_career_health.assert_awaited_with(sample.owner_id, analysis_id)

        assert (
            client.delete(
                f"/api/v1/career-growth/career-health/analyses/{analysis_id}",
                headers=_write_headers(),
            ).status_code
            == 204
        )
        assert (
            client.delete(
                f"/api/v1/career-growth/reviews/{review_id}",
                headers=_write_headers(version=1),
            ).status_code
            == 204
        )
        assert (
            client.delete(
                f"/api/v1/career-growth/development-items/{development_id}",
                headers=_write_headers(version=4),
            ).status_code
            == 204
        )
        assert (
            client.delete(
                f"/api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}",
                headers=_write_headers(version=3),
            ).status_code
            == 204
        )
        assert (
            client.delete(
                f"/api/v1/career-growth/goals/{goal_id}",
                headers=_write_headers(version=2),
            ).status_code
            == 204
        )


def test_career_growth_mutations_require_csrf_idempotency_and_quoted_versions(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    goal_id = sample.goal.goal.id

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/career-growth/goals",
            json=_goal_payload(sample),
            headers={"Idempotency-Key": "career-goal-create"},
        )
        assert missing_csrf.status_code == 403
        service.create_goal.assert_not_awaited()

        missing_idempotency = client.post(
            "/api/v1/career-growth/goals",
            json=_goal_payload(sample),
            headers=_write_headers(),
        )
        assert missing_idempotency.status_code == 422
        service.create_goal.assert_not_awaited()

        duplicate_evidence = _goal_payload(sample)
        duplicate_evidence["evidenceIds"] = [
            str(sample.evidence_id),
            str(sample.evidence_id),
        ]
        invalid_evidence = client.post(
            "/api/v1/career-growth/goals",
            json=duplicate_evidence,
            headers=_write_headers(idempotency="career-goal-invalid"),
        )
        assert invalid_evidence.status_code == 422
        service.create_goal.assert_not_awaited()

        invalid_if_match = client.put(
            f"/api/v1/career-growth/goals/{goal_id}",
            json=_goal_payload(sample),
            headers={**_write_headers(), "If-Match": "2"},
        )
        assert invalid_if_match.status_code == 422
        assert invalid_if_match.json()["code"] == "career_growth_validation_failed"
        service.update_goal.assert_not_awaited()

        service.update_goal.side_effect = CareerGrowthVersionConflict
        stale = client.put(
            f"/api/v1/career-growth/goals/{goal_id}",
            json=_goal_payload(sample),
            headers=_write_headers(version=2),
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "career_growth_version_conflict"
        assert stale.headers["Cache-Control"] == "no-store"

        service.create_goal.side_effect = CareerGrowthQuotaExceeded
        limited = client.post(
            "/api/v1/career-growth/goals",
            json=_goal_payload(sample),
            headers=_write_headers(idempotency="career-goal-quota"),
        )
        assert limited.status_code == 429
        assert limited.json()["code"] == "career_growth_quota_exceeded"


def test_career_growth_cross_owner_lookup_is_hidden_and_owner_scoped(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    identity.authenticate.return_value = _principal(sample.other_id)
    service.get_goal.side_effect = CareerGrowthNotFound

    with _client(settings, fake_database, identity, service) as client:
        hidden = client.get(f"/api/v1/career-growth/goals/{sample.goal.goal.id}")

    assert hidden.status_code == 404
    assert hidden.json()["code"] == "career_growth_not_found"
    service.get_goal.assert_awaited_once_with(sample.other_id, sample.goal.goal.id)


def test_career_growth_openapi_exposes_complete_bounded_non_predictive_surface(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        document = client.get("/openapi.json").json()

    paths = {
        path: methods
        for path, methods in document["paths"].items()
        if path.startswith("/api/v1/career-growth")
    }
    assert set(paths) == {
        "/api/v1/career-growth/insights",
        "/api/v1/career-growth/goals",
        "/api/v1/career-growth/goals/{goal_id}",
        "/api/v1/career-growth/goals/{goal_id}/milestones",
        "/api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}",
        "/api/v1/career-growth/development-items",
        "/api/v1/career-growth/development-items/{item_id}",
        "/api/v1/career-growth/development-items/from-gap",
        "/api/v1/career-growth/reviews",
        "/api/v1/career-growth/reviews/{review_id}",
        "/api/v1/career-growth/reviews/{review_id}/versions",
        "/api/v1/career-growth/reviews/{review_id}/finalizations",
        "/api/v1/career-growth/career-health/analyses",
        "/api/v1/career-growth/career-health/analyses/{analysis_id}",
        "/api/v1/career-growth/roadmap",
        "/api/v1/career-growth/roadmap/confirm",
    }
    serialized = str(document["components"]["schemas"])
    assert "ownerUserId" not in serialized
    health_schema = document["components"]["schemas"]["CareerHealthResponse"]
    disclaimer = health_schema["properties"]["disclaimer"]
    assert disclaimer["const"] == CANONICAL_SCORE_DISCLAIMER
    assert {"employerScore", "atsScore", "hiringProbability"}.isdisjoint(
        health_schema["properties"]
    )
    assert "429" in paths["/api/v1/career-growth/goals"]["post"]["responses"]
    assert "413" in paths["/api/v1/career-growth/goals"]["post"]["responses"]


def test_career_growth_roadmap_get_and_confirm(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        roadmap = client.get("/api/v1/career-growth/roadmap")
        assert roadmap.status_code == 200
        body = roadmap.json()
        assert body["roleTitle"] == "AI Engineer"
        assert body["stages"][0]["skills"][0]["alreadyDemonstrated"] is True

        confirm = client.post(
            "/api/v1/career-growth/roadmap/confirm",
            json={"roleTitle": "AI Engineer", "includedSkillNames": ["Prompt engineering"]},
            headers=_write_headers(),
        )
        assert confirm.status_code == 201
        assert len(confirm.json()["created"]) == 1
        service.confirm_roadmap_selection.assert_called_once()


def test_career_growth_roadmap_get_returns_null_without_target_role(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    service.get_role_roadmap.return_value = None

    with _client(settings, fake_database, identity, service) as client:
        response = client.get("/api/v1/career-growth/roadmap")
        assert response.status_code == 200
        assert response.json() is None
