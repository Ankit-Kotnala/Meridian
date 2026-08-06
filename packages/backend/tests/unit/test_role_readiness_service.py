"""Application-level Role Readiness tests using deterministic inward ports."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from rezumi.modules.role_readiness.application import (
    AnalyzeRoleReadiness,
    RequestContext,
    RoleFilter,
    RoleReadinessService,
    SaveRole,
    UpdateSavedRole,
)
from rezumi.modules.role_readiness.domain import (
    RoleReadinessIdempotencyConflict,
    RoleReadinessNotFound,
    RoleReadinessValidationError,
    RoleReadinessVersionConflict,
    SkillMatchState,
)
from rezumi.modules.role_readiness.domain.scoring import CareerReadinessSnapshot
from role_readiness_memory import (
    ENGINEER_ROLE_ID,
    PRODUCT_ROLE_ID,
    FixedClock,
    MemoryRoleReadiness,
    StaticSnapshotProvider,
    UuidFactory,
    sample_readiness_snapshot,
)


def _context(owner: UUID) -> RequestContext:
    return RequestContext(owner, f"request-{owner.hex[:8]}", "b" * 32)


def _snapshot() -> CareerReadinessSnapshot:
    return sample_readiness_snapshot()


def _service(memory: MemoryRoleReadiness, snapshot: CareerReadinessSnapshot | None = None):
    provider = StaticSnapshotProvider(snapshot or _snapshot())
    return (
        RoleReadinessService(
            unit_of_work=memory,
            clock=FixedClock(),
            identifiers=UuidFactory(),
            career_snapshots=provider,
        ),
        provider,
    )


@pytest.mark.asyncio
async def test_roles_can_be_searched_and_saved_with_owner_audit() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryRoleReadiness()
    service, _ = _service(memory)

    roles = await service.list_roles(RoleFilter(query="product"))
    assert [item.role.id for item in roles.data] == [PRODUCT_ROLE_ID]

    with pytest.raises(RoleReadinessNotFound):
        await service.save_role(owner, SaveRole(PRODUCT_ROLE_ID), _context(other))

    saved = await service.save_role(
        owner, SaveRole(PRODUCT_ROLE_ID, "Target role"), _context(owner)
    )
    assert saved.saved_role.owner_user_id == owner
    assert memory.audits[-1].target_id == saved.saved_role.id

    stale_version = saved.saved_role.version
    updated = await service.update_saved_role(
        owner,
        saved.saved_role.id,
        stale_version,
        UpdateSavedRole("Primary target"),
        _context(owner),
    )
    assert updated.saved_role.notes == "Primary target"
    with pytest.raises(RoleReadinessVersionConflict):
        await service.update_saved_role(
            owner,
            saved.saved_role.id,
            stale_version,
            UpdateSavedRole("Stale"),
            _context(owner),
        )


@pytest.mark.asyncio
async def test_analysis_is_idempotent_and_uses_eligible_snapshot_once() -> None:
    owner = uuid4()
    memory = MemoryRoleReadiness()
    service, provider = _service(memory)

    first = await service.analyze_role(
        owner,
        AnalyzeRoleReadiness(role_id=PRODUCT_ROLE_ID),
        "role-readiness-test-key",
        _context(owner),
    )
    second = await service.analyze_role(
        owner,
        AnalyzeRoleReadiness(role_id=PRODUCT_ROLE_ID),
        "role-readiness-test-key",
        _context(owner),
    )

    assert first.analysis.id == second.analysis.id
    assert provider.requests == [owner]
    assert first.analysis.display_score is not None
    assert any(
        item.match_state is SkillMatchState.DEMONSTRATED for item in first.competency_results
    )
    assert first.evidence_links[0].evidence_strength == "confirmed"

    with pytest.raises(RoleReadinessIdempotencyConflict):
        await service.analyze_role(
            owner,
            AnalyzeRoleReadiness(role_id=ENGINEER_ROLE_ID),
            "role-readiness-test-key",
            _context(owner),
        )


@pytest.mark.asyncio
async def test_analysis_saved_role_authorization_and_comparison_are_owner_scoped() -> None:
    owner = uuid4()
    other = uuid4()
    memory = MemoryRoleReadiness()
    service, _ = _service(memory)
    saved = await service.save_role(owner, SaveRole(PRODUCT_ROLE_ID), _context(owner))

    with pytest.raises(RoleReadinessNotFound):
        await service.analyze_role(
            other,
            AnalyzeRoleReadiness(saved_role_id=saved.saved_role.id),
            "other-user-key",
            _context(other),
        )

    await service.analyze_role(
        owner,
        AnalyzeRoleReadiness(saved_role_id=saved.saved_role.id),
        "saved-role-analysis-key",
        _context(owner),
    )
    comparison = await service.compare_roles(owner, (PRODUCT_ROLE_ID, ENGINEER_ROLE_ID))

    assert len(comparison.entries) == 2
    product = next(entry for entry in comparison.entries if entry.role.id == PRODUCT_ROLE_ID)
    engineer = next(entry for entry in comparison.entries if entry.role.id == ENGINEER_ROLE_ID)
    assert product.latest_analysis is not None
    assert product.demonstrated_count >= 1
    assert engineer.latest_analysis is None


@pytest.mark.asyncio
async def test_analytics_source_window_allows_only_the_timezone_guard() -> None:
    owner = uuid4()
    service, _ = _service(MemoryRoleReadiness())
    start = date(2010, 1, 1)

    assert (
        await service.list_analytics_history(
            owner,
            window_start=start,
            window_end=start + timedelta(days=3_652),
            limit=1,
        )
        == ()
    )
    with pytest.raises(RoleReadinessValidationError, match="timezone guard"):
        await service.list_analytics_history(
            owner,
            window_start=start,
            window_end=start + timedelta(days=3_653),
            limit=1,
        )
