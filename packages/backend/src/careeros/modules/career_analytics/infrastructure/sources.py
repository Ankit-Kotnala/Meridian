"""Purpose-minimized source adapters for Career Analytics."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from careeros.modules.application_workspace.application import (
    ApplicationAnalyticsCursor,
    ApplicationWorkspaceService,
)
from careeros.modules.career_analytics.application import (
    AchievementGrowthPoint,
    AnalyticsSourceWatermark,
    ApplicationAnalyticsFact,
    ApplicationAnalyticsSourcePage,
    ApplicationSourceCursor,
    ReadinessHistoryPoint,
    SupplementalAnalyticsSnapshot,
)
from careeros.modules.career_analytics.domain import (
    CareerAnalyticsSourceLimitExceeded,
    CareerAnalyticsUnavailable,
)
from careeros.modules.career_record.application import (
    CareerRecordError,
    CareerRecordValidationError,
)
from careeros.modules.role_readiness.application import (
    RoleReadinessError,
    RoleReadinessValidationError,
)

_MAX_READINESS_HISTORY = 500
_MAX_SUPPLEMENTAL_WINDOW_DAYS = 3_652


class _ReadinessPoint(Protocol):
    analysis_id: UUID
    role_label: str
    raw_score_basis_points: int | None
    label: str
    engine_version: str
    created_at: datetime


class _AchievementPoint(Protocol):
    evidence_revision_id: UUID
    category: str
    occurred_at: datetime


class RoleReadinessAnalyticsProvider(Protocol):
    async def list_analytics_history(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> tuple[_ReadinessPoint, ...]: ...


class CareerRecordAnalyticsProvider(Protocol):
    async def list_analytics_growth(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> tuple[_AchievementPoint, ...]: ...


class ApplicationWorkspaceAnalyticsSource:
    """Map the Phase 8 complete keyset view without exposing restricted content."""

    def __init__(self, service: ApplicationWorkspaceService) -> None:
        self._service = service

    async def watermark(self, owner_user_id: UUID) -> AnalyticsSourceWatermark:
        value = await self._service.get_analytics_watermark(owner_user_id)
        return AnalyticsSourceWatermark(
            source="applications",
            token=value.token,
            record_count=value.application_count,
            max_updated_at=value.max_updated_at,
        )

    async def page(
        self,
        owner_user_id: UUID,
        *,
        cursor: ApplicationSourceCursor | None,
        limit: int,
    ) -> ApplicationAnalyticsSourcePage:
        source_cursor = (
            ApplicationAnalyticsCursor(
                created_at=cursor.created_at,
                application_id=cursor.application_id,
            )
            if cursor is not None
            else None
        )
        page = await self._service.list_analytics_page(
            owner_user_id,
            cursor=source_cursor,
            limit=limit,
        )
        return ApplicationAnalyticsSourcePage(
            data=tuple(
                ApplicationAnalyticsFact(
                    application_id=value.application_id,
                    stage=value.stage.value,
                    outcome=value.outcome_status.value,
                    role_title=value.role_title,
                    source=value.source,
                    industry=value.industry,
                    resume_version_id=value.resume_version_id,
                    resume_version_number=value.resume_version_number,
                    requirement_coverage_basis_points=(value.requirement_coverage_basis_points),
                    first_applied_at=value.first_applied_at,
                    first_response_at=value.first_response_at,
                    first_interview_at=value.first_interview_at,
                    first_offer_at=value.first_offer_at,
                    outcome_at=value.outcome_at,
                    created_at=value.created_at,
                    updated_at=value.updated_at,
                )
                for value in page.data
            ),
            next_cursor=(
                ApplicationSourceCursor(
                    created_at=page.next_cursor.created_at,
                    application_id=page.next_cursor.application_id,
                )
                if page.next_cursor is not None
                else None
            ),
        )


class CompositeSupplementalAnalyticsSource:
    """Combine content-free readiness and achievement history source views."""

    def __init__(
        self,
        *,
        readiness: RoleReadinessAnalyticsProvider,
        career_record: CareerRecordAnalyticsProvider,
        max_readiness_history: int = _MAX_READINESS_HISTORY,
        max_achievement_growth: int = 2_000,
    ) -> None:
        if not 1 <= max_readiness_history <= _MAX_READINESS_HISTORY:
            raise ValueError("readiness analytics history limit is invalid")
        if not 1 <= max_achievement_growth <= 2_000:
            raise ValueError("achievement analytics history limit is invalid")
        self._readiness = readiness
        self._career_record = career_record
        self._max_readiness_history = max_readiness_history
        self._max_achievement_growth = max_achievement_growth

    async def watermark(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> AnalyticsSourceWatermark:
        readiness, achievements = await self._values(
            owner_user_id,
            window_start=window_start,
            window_end=window_end,
        )
        payload = {
            "achievements": [
                {
                    "category": value.category,
                    "evidenceRevisionId": str(value.evidence_revision_id),
                    "occurredAt": value.occurred_at.isoformat(),
                }
                for value in achievements
            ],
            "readiness": [
                {
                    "analysisId": str(value.analysis_id),
                    "createdAt": value.created_at.isoformat(),
                    "engineVersion": value.engine_version,
                    "label": value.label,
                    "rawScoreBasisPoints": value.raw_score_basis_points,
                    "roleLabel": value.role_label,
                }
                for value in readiness
            ],
            "v": 2,
            "windowEnd": window_end.isoformat(),
            "windowStart": window_start.isoformat(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        timestamps = [
            *(value.created_at for value in readiness),
            *(value.occurred_at for value in achievements),
        ]
        return AnalyticsSourceWatermark(
            source="career",
            token=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            record_count=len(readiness) + len(achievements),
            max_updated_at=max(timestamps, default=None),
        )

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> SupplementalAnalyticsSnapshot:
        readiness, achievements = await self._values(
            owner_user_id,
            window_start=window_start,
            window_end=window_end,
        )
        return SupplementalAnalyticsSnapshot(
            readiness=tuple(
                ReadinessHistoryPoint(
                    analysis_id=value.analysis_id,
                    role_label=value.role_label,
                    raw_score_basis_points=value.raw_score_basis_points,
                    label=value.label,
                    engine_version=value.engine_version,
                    created_at=value.created_at,
                )
                for value in readiness
            ),
            achievements=tuple(
                AchievementGrowthPoint(
                    evidence_revision_id=value.evidence_revision_id,
                    category=value.category,
                    occurred_at=value.occurred_at,
                )
                for value in achievements
            ),
        )

    async def _values(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> tuple[tuple[_ReadinessPoint, ...], tuple[_AchievementPoint, ...]]:
        if (
            window_end < window_start
            or (window_end - window_start).days > _MAX_SUPPLEMENTAL_WINDOW_DAYS
        ):
            raise CareerAnalyticsSourceLimitExceeded(
                "supplemental analytics source window is invalid"
            )
        try:
            readiness_result, achievement_result = await asyncio.gather(
                self._readiness.list_analytics_history(
                    owner_user_id,
                    window_start=window_start,
                    window_end=window_end,
                    limit=self._max_readiness_history + 1,
                ),
                self._career_record.list_analytics_growth(
                    owner_user_id,
                    window_start=window_start,
                    window_end=window_end,
                ),
            )
        except (CareerRecordValidationError, RoleReadinessValidationError) as exc:
            raise CareerAnalyticsSourceLimitExceeded(
                "supplemental analytics source rejected its bounded query"
            ) from exc
        except (CareerRecordError, RoleReadinessError) as exc:
            raise CareerAnalyticsUnavailable(
                "supplemental analytics source is unavailable"
            ) from exc
        except Exception as exc:
            raise CareerAnalyticsUnavailable(
                "supplemental analytics source is unavailable"
            ) from exc
        if len(readiness_result) > self._max_readiness_history:
            raise CareerAnalyticsSourceLimitExceeded(
                "role readiness analytics source exceeded its bounded history"
            )
        if len(achievement_result) > self._max_achievement_growth:
            raise CareerAnalyticsSourceLimitExceeded(
                "career record analytics source exceeded its bounded history"
            )
        readiness = tuple(
            sorted(
                readiness_result,
                key=lambda value: (value.created_at, str(value.analysis_id)),
            )
        )
        achievements = tuple(
            sorted(
                achievement_result,
                key=lambda value: (value.occurred_at, str(value.evidence_revision_id)),
            )
        )
        if len({value.analysis_id for value in readiness}) != len(readiness):
            raise CareerAnalyticsSourceLimitExceeded(
                "role readiness analytics source contains duplicate history"
            )
        if len({value.evidence_revision_id for value in achievements}) != len(achievements) or any(
            value.category != "achievement" for value in achievements
        ):
            raise CareerAnalyticsSourceLimitExceeded(
                "career record analytics source contains invalid achievement history"
            )
        return readiness, achievements
