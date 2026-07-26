"""Purpose-minimized Career Analytics source-boundary tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest

from careeros.modules.career_analytics.domain import (
    CareerAnalyticsSourceLimitExceeded,
    CareerAnalyticsUnavailable,
)
from careeros.modules.career_analytics.infrastructure.sources import (
    CareerRecordAnalyticsProvider,
    CompositeSupplementalAnalyticsSource,
    RoleReadinessAnalyticsProvider,
)
from careeros.modules.role_readiness.application import (
    RoleReadinessUnavailable,
    RoleReadinessValidationError,
)

_OWNER_ID = UUID("00000000-0000-4000-8000-000000009101")
_NOW = datetime(2026, 7, 25, 12, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Watermark:
    token: str
    record_count: int
    max_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class _Readiness:
    analysis_id: UUID
    role_label: str
    raw_score_basis_points: int | None
    label: str
    engine_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class _Achievement:
    evidence_revision_id: UUID
    category: str
    occurred_at: datetime


class _ReadinessProvider:
    def __init__(self, count: int) -> None:
        self.values = tuple(
            _Readiness(
                analysis_id=UUID(int=index + 1),
                role_label="Fictional role",
                raw_score_basis_points=5_000,
                label="developing",
                engine_version="role-readiness/1.0.0",
                created_at=_NOW,
            )
            for index in range(count)
        )
        self.requested_limits: list[int] = []

    async def analytics_watermark(self, owner_user_id: UUID) -> _Watermark:
        assert owner_user_id == _OWNER_ID
        return _Watermark(f"sha256:{'a' * 64}", len(self.values), _NOW)

    async def list_analytics_history(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> tuple[_Readiness, ...]:
        assert owner_user_id == _OWNER_ID
        assert window_start <= window_end
        self.requested_limits.append(limit)
        return self.values[:limit]


class _CareerRecordProvider:
    def __init__(self, point: _Achievement | None = None) -> None:
        self.point = point
        self.source_available = True
        self.item_version = 1

    async def analytics_watermark(self, owner_user_id: UUID) -> _Watermark:
        assert owner_user_id == _OWNER_ID
        return _Watermark(f"sha256:{'b' * 64}", 0, None)

    async def list_analytics_growth(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> tuple[_Achievement, ...]:
        assert owner_user_id == _OWNER_ID
        assert window_start <= window_end
        return (
            (self.point,)
            if self.point is not None
            and self.source_available
            and window_start <= self.point.occurred_at.date() <= window_end
            else ()
        )


@pytest.mark.asyncio
async def test_readiness_supplement_uses_limit_plus_one_and_accepts_exact_cap() -> None:
    readiness = _ReadinessProvider(500)
    source = CompositeSupplementalAnalyticsSource(
        readiness=cast(RoleReadinessAnalyticsProvider, readiness),
        career_record=cast(CareerRecordAnalyticsProvider, _CareerRecordProvider()),
    )

    snapshot = await source.snapshot(
        _OWNER_ID,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
    )

    assert len(snapshot.readiness) == 500
    assert readiness.requested_limits == [501]


@pytest.mark.asyncio
async def test_readiness_supplement_fails_safely_above_cap() -> None:
    readiness = _ReadinessProvider(501)
    source = CompositeSupplementalAnalyticsSource(
        readiness=cast(RoleReadinessAnalyticsProvider, readiness),
        career_record=cast(CareerRecordAnalyticsProvider, _CareerRecordProvider()),
    )

    with pytest.raises(
        CareerAnalyticsSourceLimitExceeded,
        match="bounded history",
    ):
        await source.snapshot(
            _OWNER_ID,
            window_start=date(2026, 1, 1),
            window_end=date(2026, 12, 31),
        )
    assert readiness.requested_limits == [501]


@pytest.mark.asyncio
async def test_windowed_watermark_tracks_exact_canonical_achievement_set() -> None:
    point = _Achievement(
        evidence_revision_id=UUID(int=9_201),
        category="achievement",
        occurred_at=_NOW,
    )
    career_record = _CareerRecordProvider(point)
    source = CompositeSupplementalAnalyticsSource(
        readiness=cast(RoleReadinessAnalyticsProvider, _ReadinessProvider(0)),
        career_record=cast(CareerRecordAnalyticsProvider, career_record),
    )

    before = await source.watermark(
        _OWNER_ID,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
    )
    career_record.source_available = False
    after = await source.watermark(
        _OWNER_ID,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
    )

    assert career_record.item_version == 1
    assert before.record_count == 1
    assert after.record_count == 0
    assert before.token != after.token


@pytest.mark.asyncio
async def test_supplemental_window_accepts_only_the_bounded_timezone_guard() -> None:
    source = CompositeSupplementalAnalyticsSource(
        readiness=cast(RoleReadinessAnalyticsProvider, _ReadinessProvider(0)),
        career_record=cast(CareerRecordAnalyticsProvider, _CareerRecordProvider()),
    )
    start = date(2010, 1, 1)

    accepted = await source.snapshot(
        _OWNER_ID,
        window_start=start,
        window_end=start + timedelta(days=3_652),
    )
    assert accepted.readiness == ()
    assert accepted.achievements == ()

    with pytest.raises(CareerAnalyticsSourceLimitExceeded, match="window"):
        await source.snapshot(
            _OWNER_ID,
            window_start=start,
            window_end=start + timedelta(days=3_653),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_error"),
    [
        (
            RoleReadinessValidationError("bounded provider rejection"),
            CareerAnalyticsSourceLimitExceeded,
        ),
        (
            RoleReadinessUnavailable("provider unavailable"),
            CareerAnalyticsUnavailable,
        ),
        (RuntimeError("database unavailable"), CareerAnalyticsUnavailable),
    ],
)
async def test_supplemental_provider_failures_stay_inside_analytics_boundary(
    provider_error: Exception,
    expected_error: type[Exception],
) -> None:
    class FailingReadinessProvider(_ReadinessProvider):
        async def list_analytics_history(
            self,
            owner_user_id: UUID,
            *,
            window_start: date,
            window_end: date,
            limit: int,
        ) -> tuple[_Readiness, ...]:
            _ = owner_user_id, window_start, window_end, limit
            raise provider_error

    source = CompositeSupplementalAnalyticsSource(
        readiness=cast(RoleReadinessAnalyticsProvider, FailingReadinessProvider(0)),
        career_record=cast(CareerRecordAnalyticsProvider, _CareerRecordProvider()),
    )

    with pytest.raises(expected_error):
        await source.watermark(
            _OWNER_ID,
            window_start=date(2026, 1, 1),
            window_end=date(2026, 12, 31),
        )
