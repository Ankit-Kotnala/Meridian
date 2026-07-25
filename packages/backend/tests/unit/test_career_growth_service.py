"""Career Growth service, provenance, review history, and Career Health tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from itertools import product
from uuid import UUID, uuid4

import pytest

from career_growth_memory import (
    NOW,
    FixedClock,
    MemoryCareerGrowth,
    StaticCareerGrowthSource,
    UuidFactory,
)
from careeros.modules.career_growth.application import (
    CareerGrowthPolicy,
    CareerGrowthService,
    CreateCareerReview,
    CreateDevelopmentItem,
    CreateGoal,
    CreateMilestone,
    RequestContext,
    ReviewContent,
    ReviseCareerReview,
    UpdateGoal,
)
from careeros.modules.career_growth.application.models import PageCursor
from careeros.modules.career_growth.domain import (
    CANONICAL_SCORE_DISCLAIMER,
    CareerGrowthConflict,
    CareerGrowthIdempotencyConflict,
    CareerGrowthNotFound,
    CareerGrowthQuotaExceeded,
    CareerGrowthSourceSnapshot,
    CareerGrowthValidationError,
    CareerGrowthVersionConflict,
    CareerHealthDimension,
    CareerHealthInput,
    CareerHealthStatus,
    DevelopmentHealthSignal,
    DevelopmentKind,
    DevelopmentStatus,
    GoalHealthSignal,
    GoalStatus,
    GrowthEvidenceSnapshot,
    MilestoneStatus,
    ReviewCadence,
    ReviewHealthSignal,
    ReviewVersionStatus,
    score_career_health,
)
from careeros.modules.career_growth.domain.scoring import (
    MAX_INPUT_SNAPSHOT_BYTES,
    _largest_remainder_contributions,
)

EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000009001")
EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-000000009002")
SECOND_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000009003")
SECOND_REVISION_ID = UUID("00000000-0000-4000-8000-000000009004")
SKILL_ID = UUID("00000000-0000-4000-8000-000000009101")
SECOND_SKILL_ID = UUID("00000000-0000-4000-8000-000000009102")


def _context(owner: UUID) -> RequestContext:
    return RequestContext(owner, f"request-{owner.hex[:8]}", "a" * 32)


def _source_snapshot() -> CareerGrowthSourceSnapshot:
    return CareerGrowthSourceSnapshot(
        evidence=(
            GrowthEvidenceSnapshot(
                evidence_id=EVIDENCE_ID,
                evidence_revision_id=EVIDENCE_REVISION_ID,
                revision_number=3,
                statement_sha256="1" * 64,
                revised_at=NOW - timedelta(days=30),
                skill_ids=(SKILL_ID,),
            ),
            GrowthEvidenceSnapshot(
                evidence_id=SECOND_EVIDENCE_ID,
                evidence_revision_id=SECOND_REVISION_ID,
                revision_number=2,
                statement_sha256="2" * 64,
                revised_at=NOW - timedelta(days=120),
                skill_ids=(SECOND_SKILL_ID,),
            ),
        ),
        skill_ids=(SKILL_ID, SECOND_SKILL_ID),
    )


def _service(
    memory: MemoryCareerGrowth,
    source: CareerGrowthSourceSnapshot | None = None,
    policy: CareerGrowthPolicy | None = None,
) -> tuple[CareerGrowthService, StaticCareerGrowthSource]:
    provider = StaticCareerGrowthSource(source or _source_snapshot())
    return (
        CareerGrowthService(
            unit_of_work=memory,
            clock=FixedClock(),
            identifiers=UuidFactory(),
            career_source=provider,
            policy=policy,
        ),
        provider,
    )


@pytest.mark.asyncio
async def test_growth_collection_quota_is_owner_serialized_and_typed() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, _provider = _service(
        memory,
        policy=CareerGrowthPolicy(max_goals=1),
    )

    await service.create_goal(
        owner,
        CreateGoal("First bounded goal"),
        "goal-quota-first",
        _context(owner),
    )
    with pytest.raises(CareerGrowthQuotaExceeded, match="goal limit"):
        await service.create_goal(
            owner,
            CreateGoal("Second bounded goal"),
            "goal-quota-second",
            _context(owner),
        )

    assert memory.locked_owners[-1] == owner


def test_career_health_v2_golden_is_fixed_point_reproducible_and_additive() -> None:
    value = CareerHealthInput(
        as_of=NOW.date(),
        source=_source_snapshot(),
        goals=(
            GoalHealthSignal(
                goal_id=uuid4(),
                version=1,
                status=GoalStatus.ACTIVE,
                milestone_statuses=(
                    MilestoneStatus.COMPLETED,
                    MilestoneStatus.IN_PROGRESS,
                ),
                evidence_revision_ids=(EVIDENCE_REVISION_ID,),
            ),
            GoalHealthSignal(
                goal_id=uuid4(),
                version=1,
                status=GoalStatus.COMPLETED,
                milestone_statuses=(),
                evidence_revision_ids=(SECOND_REVISION_ID,),
            ),
        ),
        development_items=(
            DevelopmentHealthSignal(
                item_id=uuid4(),
                version=1,
                kind=DevelopmentKind.LEARNING,
                status=DevelopmentStatus.COMPLETED,
                target_date=NOW.date(),
                evidence_revision_ids=(EVIDENCE_REVISION_ID,),
            ),
            DevelopmentHealthSignal(
                item_id=uuid4(),
                version=1,
                kind=DevelopmentKind.PROMOTION,
                status=DevelopmentStatus.IN_PROGRESS,
                target_date=NOW.date() + timedelta(days=10),
                evidence_revision_ids=(),
            ),
        ),
        reviews=(
            ReviewHealthSignal(
                review_id=uuid4(),
                version=2,
                cadence=ReviewCadence.QUARTERLY,
                has_review_data=True,
                latest_finalized_at=NOW - timedelta(days=30),
                latest_finalized_version_id=uuid4(),
            ),
        ),
    )

    first = score_career_health(value)
    second = score_career_health(value)

    assert first.status is CareerHealthStatus.COMPLETE
    assert first.raw_score_basis_points == 8_813
    assert first.display_score == 88
    assert (
        sum(item.contribution_basis_points or 0 for item in first.components)
        == first.raw_score_basis_points
    )
    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.disclaimer == CANONICAL_SCORE_DISCLAIMER
    assert first.configuration_snapshot["minimumApplicableWeightBasisPoints"] == 6_000
    assert first.engine_version == "career-health/1.1.0"
    assert first.configuration_version == "career-health-default/2"
    assert first.feature_schema_version == "career-health-features/2"
    assert len(json.dumps(first.input_snapshot).encode("utf-8")) <= MAX_INPUT_SNAPSHOT_BYTES
    assert set(first.input_snapshot) == {
        "asOf",
        "developmentFollowThroughCreditCounts",
        "evidenceCurrencyCreditCounts",
        "goalProgressCreditCounts",
        "readinessMaintenance",
        "reviewCadenceCredits",
    }
    assert "market" not in first.disclaimer.casefold()
    assert "hiring probability" not in first.disclaimer.casefold()


def test_largest_remainder_contributions_are_exhaustively_nonnegative_and_additive() -> None:
    for count in range(1, 6):
        for scores in product((0, 1, 50, 51, 52, 9_999, 10_000), repeat=count):
            weights = (2_500, 3_000, 2_000, 1_500, 1_000)[:count]
            denominator = sum(weights)
            numerators = tuple(
                score * weight for score, weight in zip(scores, weights, strict=True)
            )
            target = (sum(numerators) + denominator // 2) // denominator
            contributions = _largest_remainder_contributions(
                numerators,
                denominator=denominator,
                target=target,
            )
            assert all(value >= 0 for value in contributions)
            assert sum(contributions) == target
            assert contributions == _largest_remainder_contributions(
                numerators,
                denominator=denominator,
                target=target,
            )

    # Regression: independent rounding followed by a last-component residual
    # produced -1 for this valid score/weight combination.
    numerators = (50 * 2_500, 52 * 3_000, 0 * 2_000)
    target = (sum(numerators) + 7_500 // 2) // 7_500
    assert _largest_remainder_contributions(
        numerators,
        denominator=7_500,
        target=target,
    ) == [16, 21, 0]


def test_career_health_bounds_and_missing_data_fail_closed() -> None:
    insufficient = score_career_health(
        CareerHealthInput(
            as_of=NOW.date(),
            source=CareerGrowthSourceSnapshot(
                evidence=_source_snapshot().evidence,
                skill_ids=(),
            ),
            goals=(),
            development_items=(),
            reviews=(),
        )
    )
    assert insufficient.status is CareerHealthStatus.INSUFFICIENT_DATA
    assert insufficient.raw_score_basis_points is None
    assert insufficient.display_score is None
    assert all(item.score_basis_points is None for item in insufficient.components)

    zero = score_career_health(
        CareerHealthInput(
            as_of=NOW.date(),
            source=CareerGrowthSourceSnapshot(
                evidence=(
                    GrowthEvidenceSnapshot(
                        evidence_id=EVIDENCE_ID,
                        evidence_revision_id=EVIDENCE_REVISION_ID,
                        revision_number=1,
                        statement_sha256="a" * 64,
                        revised_at=NOW - timedelta(days=900),
                        skill_ids=(),
                    ),
                ),
                skill_ids=(SKILL_ID,),
            ),
            goals=(
                GoalHealthSignal(
                    goal_id=uuid4(),
                    version=1,
                    status=GoalStatus.ACTIVE,
                    milestone_statuses=(),
                    evidence_revision_ids=(),
                ),
            ),
            development_items=(
                DevelopmentHealthSignal(
                    item_id=uuid4(),
                    version=1,
                    kind=DevelopmentKind.LEARNING,
                    status=DevelopmentStatus.PLANNED,
                    target_date=NOW.date() - timedelta(days=1),
                    evidence_revision_ids=(),
                ),
            ),
            reviews=(),
        )
    )
    assert zero.status is CareerHealthStatus.COMPLETE
    assert zero.raw_score_basis_points == 0
    assert all(0 <= (item.score_basis_points or 0) <= 10_000 for item in zero.components)


@pytest.mark.asyncio
async def test_goal_provenance_idempotency_ownership_and_versions() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)
    command = CreateGoal(
        "Build stronger evidence",
        "Maintain only documented progress.",
        evidence_ids=(EVIDENCE_ID,),
    )

    with pytest.raises(CareerGrowthNotFound):
        await service.create_goal(owner, command, "goal-owner-key", _context(other))

    first = await service.create_goal(owner, command, "goal-create-stable-key", _context(owner))
    replay = await service.create_goal(owner, command, "goal-create-stable-key", _context(owner))
    assert replay.goal.id == first.goal.id
    assert len(memory.goals) == 1
    assert len(provider.resolve_requests) == 2
    assert first.evidence_links[0].link.evidence_revision_id == EVIDENCE_REVISION_ID
    assert first.evidence_links[0].link.revision_number == 3
    assert first.evidence_links[0].link.statement_sha256 == "1" * 64

    with pytest.raises(CareerGrowthIdempotencyConflict):
        await service.create_goal(
            owner,
            CreateGoal("Different goal"),
            "goal-create-stable-key",
            _context(owner),
        )

    stale = first.goal.version
    updated = await service.update_goal(
        owner,
        first.goal.id,
        stale,
        UpdateGoal(
            title="Build stronger current evidence",
            description=None,
            status=GoalStatus.ACTIVE,
            target_date=None,
            evidence_ids=(SECOND_EVIDENCE_ID,),
        ),
        _context(owner),
    )
    assert updated.goal.version == stale + 1
    assert updated.evidence_links[0].link.evidence_revision_id == SECOND_REVISION_ID
    with pytest.raises(CareerGrowthVersionConflict):
        await service.update_goal(
            owner,
            first.goal.id,
            stale,
            UpdateGoal(
                title="Stale update",
                description=None,
                status=GoalStatus.ACTIVE,
                target_date=None,
            ),
            _context(owner),
        )
    with pytest.raises(CareerGrowthNotFound):
        await service.get_goal(other, first.goal.id)


@pytest.mark.asyncio
async def test_completed_certification_requires_exact_eligible_evidence() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)

    with pytest.raises(CareerGrowthValidationError, match="requires eligible evidence"):
        await service.create_development_item(
            owner,
            CreateDevelopmentItem(
                kind=DevelopmentKind.CERTIFICATION,
                title="Fictional test credential",
                status=DevelopmentStatus.COMPLETED,
            ),
            "credential-no-proof",
            _context(owner),
        )

    created = await service.create_development_item(
        owner,
        CreateDevelopmentItem(
            kind=DevelopmentKind.CERTIFICATION,
            title="Fictional test credential",
            status=DevelopmentStatus.COMPLETED,
            evidence_ids=(EVIDENCE_ID,),
        ),
        "credential-with-proof",
        _context(owner),
    )
    assert created.item.completed_at == NOW
    assert created.evidence_links[0].link.evidence_revision_id == EVIDENCE_REVISION_ID
    assert created.evidence_links[0].is_current is True

    provider.snapshot_value = CareerGrowthSourceSnapshot(evidence=(), skill_ids=())
    listed = await service.list_development_items(owner)
    assert listed.data[0].evidence_links[0].is_current is False


@pytest.mark.asyncio
async def test_growth_insights_derive_history_skills_promotion_and_annual_refresh() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)

    with pytest.raises(CareerGrowthValidationError, match="annual resume refresh"):
        await service.create_development_item(
            owner,
            CreateDevelopmentItem(
                kind=DevelopmentKind.ANNUAL_RESUME_REFRESH,
                title="Annual resume refresh",
                status=DevelopmentStatus.COMPLETED,
            ),
            "refresh-without-proof",
            _context(owner),
        )
    refresh = await service.create_development_item(
        owner,
        CreateDevelopmentItem(
            kind=DevelopmentKind.ANNUAL_RESUME_REFRESH,
            title="Annual resume refresh",
            status=DevelopmentStatus.COMPLETED,
            evidence_ids=(EVIDENCE_ID,),
        ),
        "refresh-with-proof",
        _context(owner),
    )
    await service.create_development_item(
        owner,
        CreateDevelopmentItem(
            kind=DevelopmentKind.PROMOTION,
            title="Promotion preparation",
            status=DevelopmentStatus.COMPLETED,
            evidence_ids=(EVIDENCE_ID,),
        ),
        "promotion-with-proof",
        _context(owner),
    )

    insights = await service.get_insights(owner)

    assert [item.evidence_id for item in insights.achievements] == [
        EVIDENCE_ID,
        SECOND_EVIDENCE_ID,
    ]
    assert insights.skills[0].evidence_ids == (EVIDENCE_ID,)
    assert insights.annual_resume_refreshes[0].item.id == refresh.item.id
    assert insights.promotion_readiness.status.value == "insufficient_evidence"
    assert len(insights.promotion_readiness.checks) == 6
    assert "not an employer decision" in insights.promotion_readiness.disclaimer
    checks = {item.code: item for item in insights.promotion_readiness.checks}
    assert checks["promotion_plan"].status.value == "supported"
    assert checks["annual_resume_refresh"].status.value == "supported"

    provider.snapshot_value = CareerGrowthSourceSnapshot(
        evidence=(provider.snapshot_value.evidence[1],),
        skill_ids=provider.snapshot_value.skill_ids,
    )
    after_revocation = await service.get_insights(owner)
    revoked_checks = {item.code: item for item in after_revocation.promotion_readiness.checks}
    assert revoked_checks["promotion_plan"].status.value == "needs_action"
    assert revoked_checks["annual_resume_refresh"].status.value == "needs_action"
    assert len(after_revocation.annual_resume_refreshes[0].evidence_links) == 1
    assert after_revocation.annual_resume_refreshes[0].evidence_links[0].is_current is False


@pytest.mark.asyncio
async def test_owned_goal_deletion_removes_private_children_and_keeps_redacted_audit() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerGrowth()
    service, _ = _service(memory)
    goal = await service.create_goal(
        owner,
        CreateGoal("Private goal text", evidence_ids=(EVIDENCE_ID,)),
        "delete-goal-create",
        _context(owner),
    )
    milestone = await service.create_milestone(
        owner,
        goal.goal.id,
        CreateMilestone("Private milestone text", evidence_ids=(EVIDENCE_ID,)),
        "delete-milestone-create",
        _context(owner),
    )

    with pytest.raises(CareerGrowthNotFound):
        await service.delete_goal(other, goal.goal.id, goal.goal.version, _context(other))
    await service.delete_goal(owner, goal.goal.id, goal.goal.version, _context(owner))

    assert goal.goal.id not in memory.goals
    assert milestone.milestone.id not in memory.milestones
    assert not memory.evidence_links
    audit = memory.audits[-1]
    assert audit.target_id == goal.goal.id
    assert "Private" not in str(audit.details)


@pytest.mark.asyncio
async def test_review_versions_preserve_finalized_history_and_material_changes() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerGrowth()
    service, _ = _service(memory)
    created = await service.create_review(
        owner,
        CreateCareerReview(
            cadence=ReviewCadence.QUARTERLY,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            content=ReviewContent("Q2 review", "Initial factual summary."),
            evidence_ids=(EVIDENCE_ID,),
        ),
        "review-create-key",
        _context(owner),
    )
    assert created.current_version.version.version_number == 1
    assert created.current_version.version.status is ReviewVersionStatus.DRAFT

    revised = await service.revise_review(
        owner,
        created.review.id,
        created.review.version,
        ReviseCareerReview(
            content=ReviewContent(
                "Q2 review",
                "Revised factual summary.",
                achievements="Evidence-linked achievement.",
            ),
            change_reason="Added an evidence-linked achievement",
            evidence_ids=(EVIDENCE_ID,),
        ),
        _context(owner),
    )
    assert len(revised.history) == 2
    assert revised.history[0].version.summary == "Initial factual summary."
    assert revised.history[1].version.material_change is True
    assert revised.history[1].version.supersedes_version_id == revised.history[0].version.id

    finalized = await service.finalize_review(
        owner,
        revised.review.id,
        revised.review.version,
        "review-finalize-key",
        _context(owner),
    )
    finalized_version = finalized.current_version.version
    assert finalized_version.status is ReviewVersionStatus.FINALIZED
    assert finalized_version.material_change is False
    assert finalized_version.content_sha256 == revised.current_version.version.content_sha256

    successor = await service.revise_review(
        owner,
        finalized.review.id,
        finalized.review.version,
        ReviseCareerReview(
            content=ReviewContent("Q2 review", "Post-finalization correction."),
            change_reason="Corrected the review without rewriting finalized history",
            evidence_ids=(SECOND_EVIDENCE_ID,),
        ),
        _context(owner),
    )
    assert successor.current_version.version.status is ReviewVersionStatus.DRAFT
    persisted_finalized = next(
        item for item in successor.history if item.version.id == finalized_version.id
    )
    assert persisted_finalized.version.status is ReviewVersionStatus.FINALIZED
    assert persisted_finalized.version.summary == "Revised factual summary."
    with pytest.raises(CareerGrowthNotFound):
        await service.get_review(other, created.review.id)


@pytest.mark.asyncio
async def test_review_finalization_requires_current_evidence_and_is_idempotent() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)
    unsupported = await service.create_review(
        owner,
        CreateCareerReview(
            cadence=ReviewCadence.QUARTERLY,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            content=ReviewContent("Q2 review", "Owner-authored factual summary."),
        ),
        "review-without-evidence",
        _context(owner),
    )
    with pytest.raises(CareerGrowthValidationError, match="requires at least one"):
        await service.finalize_review(
            owner,
            unsupported.review.id,
            unsupported.review.version,
            "unsupported-finalization",
            _context(owner),
        )

    linked = await service.create_review(
        owner,
        CreateCareerReview(
            cadence=ReviewCadence.QUARTERLY,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            content=ReviewContent("Grounded Q2 review", "Evidence-linked factual summary."),
            evidence_ids=(EVIDENCE_ID,),
        ),
        "review-current-evidence",
        _context(owner),
    )
    provider.snapshot_value = CareerGrowthSourceSnapshot(evidence=(), skill_ids=())
    with pytest.raises(CareerGrowthConflict, match="changed before finalization"):
        await service.finalize_review(
            owner,
            linked.review.id,
            linked.review.version,
            "revoked-evidence-finalization",
            _context(owner),
        )

    provider.snapshot_value = _source_snapshot()
    expected_version = linked.review.version
    finalized = await service.finalize_review(
        owner,
        linked.review.id,
        expected_version,
        "grounded-finalization",
        _context(owner),
    )
    replay = await service.finalize_review(
        owner,
        linked.review.id,
        expected_version,
        "grounded-finalization",
        _context(owner),
    )
    assert replay.review.version == finalized.review.version
    assert (
        len(
            [
                version
                for version in memory.review_versions.values()
                if version.review_id == linked.review.id
            ]
        )
        == 2
    )
    provider.snapshot_value = CareerGrowthSourceSnapshot(evidence=(), skill_ids=())
    persisted = await service.get_review(owner, linked.review.id)
    assert persisted.current_version.version.status is ReviewVersionStatus.FINALIZED
    assert persisted.current_version.evidence_links[0].is_current is False


@pytest.mark.asyncio
async def test_review_finalization_replay_returns_historical_result_after_revision() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, _provider = _service(memory)
    created = await service.create_review(
        owner,
        CreateCareerReview(
            cadence=ReviewCadence.QUARTERLY,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            content=ReviewContent(
                "Grounded Q2 review",
                "Evidence-linked factual summary.",
            ),
            evidence_ids=(EVIDENCE_ID,),
        ),
        "historical-review-create",
        _context(owner),
    )
    expected_version = created.review.version
    key = "historical-review-finalize"
    finalized = await service.finalize_review(
        owner,
        created.review.id,
        expected_version,
        key,
        _context(owner),
    )
    finalized_version = finalized.current_version.version
    finalized_history_ids = tuple(item.version.id for item in finalized.history)

    revised = await service.revise_review(
        owner,
        created.review.id,
        finalized.review.version,
        ReviseCareerReview(
            content=ReviewContent(
                "Grounded Q2 review",
                "A later material revision remains a draft.",
            ),
            change_reason="Preserve the finalization while starting a new draft.",
            evidence_ids=(SECOND_EVIDENCE_ID,),
        ),
        _context(owner),
    )
    assert revised.current_version.version.status is ReviewVersionStatus.DRAFT

    replay = await service.finalize_review(
        owner,
        created.review.id,
        expected_version,
        key,
        _context(owner),
    )

    assert replay.review.version == finalized_version.version_number
    assert replay.review.latest_version_id == finalized_version.id
    assert replay.review.latest_status is ReviewVersionStatus.FINALIZED
    assert replay.review.updated_at == finalized_version.created_at
    assert replay.current_version.version == finalized_version
    assert tuple(item.version.id for item in replay.history) == finalized_history_ids
    assert len(replay.history) == 2
    current = await service.get_review(owner, created.review.id)
    assert current.review.version == 3
    assert current.current_version.version.status is ReviewVersionStatus.DRAFT


@pytest.mark.asyncio
async def test_goal_and_review_lists_use_bounded_summary_queries() -> None:
    owner = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)
    for index in range(3):
        goal = await service.create_goal(
            owner,
            CreateGoal(f"Goal {index}", evidence_ids=(EVIDENCE_ID,)),
            f"summary-goal-{index}",
            _context(owner),
        )
        await service.create_milestone(
            owner,
            goal.goal.id,
            CreateMilestone(f"Milestone {index}"),
            f"summary-milestone-{index}",
            _context(owner),
        )
        await service.create_review(
            owner,
            CreateCareerReview(
                cadence=ReviewCadence.QUARTERLY,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
                content=ReviewContent(
                    f"Review {index}",
                    "Bounded summary content that must not be returned by the list.",
                ),
                evidence_ids=(EVIDENCE_ID,),
            ),
            f"summary-review-{index}",
            _context(owner),
        )

    memory.query_counts.clear()
    provider.resolve_requests.clear()
    goals = await service.list_goals(owner, limit=3)
    reviews = await service.list_reviews(owner, limit=3)

    assert [item.milestone_count for item in goals.data] == [1, 1, 1]
    assert all(item.evidence_needs_review_count == 0 for item in goals.data)
    assert all(item.history_count == 1 for item in reviews.data)
    assert all(item.current_title.startswith("Review ") for item in reviews.data)
    assert memory.query_counts["count_milestones_by_goal"] == 1
    assert memory.query_counts["get_review_list_metadata"] == 1
    assert memory.query_counts["get_review_versions"] == 0
    assert memory.query_counts["list_evidence_links"] == 2
    assert len(provider.resolve_requests) == 2


@pytest.mark.asyncio
async def test_health_analysis_is_immutable_idempotent_owner_scoped_and_content_free() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryCareerGrowth()
    service, provider = _service(memory)
    goal = await service.create_goal(
        owner,
        CreateGoal("Maintain evidence", evidence_ids=(EVIDENCE_ID,)),
        "health-goal-key",
        _context(owner),
    )
    await service.create_milestone(
        owner,
        goal.goal.id,
        CreateMilestone(
            "Record progress",
            status=MilestoneStatus.COMPLETED,
            evidence_ids=(EVIDENCE_ID,),
        ),
        "health-milestone-key",
        _context(owner),
    )
    await service.create_development_item(
        owner,
        CreateDevelopmentItem(
            kind=DevelopmentKind.LEARNING,
            title="Maintain a learning plan",
            status=DevelopmentStatus.COMPLETED,
            evidence_ids=(SECOND_EVIDENCE_ID,),
        ),
        "health-development-key",
        _context(owner),
    )

    first = await service.analyze_career_health(owner, "career-health-stable-key", _context(owner))
    replay = await service.analyze_career_health(owner, "career-health-stable-key", _context(owner))
    assert replay.analysis.id == first.analysis.id
    assert provider.snapshot_requests == [owner]
    assert first.analysis.status is CareerHealthStatus.COMPLETE
    assert len(first.components) == 5
    assert first.analysis.snapshot_sha256
    serialized = str(first.analysis.input_snapshot).casefold()
    assert "maintain evidence" not in serialized
    assert "statement':" not in serialized
    assert "title" not in serialized
    with pytest.raises(CareerGrowthValidationError, match="hash does not match"):
        replace(first.analysis, input_snapshot={"tampered": True})
    assert first.analysis.disclaimer == CANONICAL_SCORE_DISCLAIMER
    assert {component.dimension for component in first.components} == set(CareerHealthDimension)

    with pytest.raises(CareerGrowthNotFound):
        await service.get_career_health(other, first.analysis.id)
    with pytest.raises(CareerGrowthIdempotencyConflict):
        await service.analyze_career_health(owner, "health-goal-key", _context(owner))


def test_cursor_rejects_non_ascii_and_out_of_window_values() -> None:
    with pytest.raises(CareerGrowthValidationError):
        PageCursor.decode("é")
    with pytest.raises(CareerGrowthValidationError):
        PageCursor(10_001).encode()
