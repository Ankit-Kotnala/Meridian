"""Deterministic, bounded, correlation-only Career Analytics aggregation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rezumi.modules.career_analytics.domain import (
    AnalyticsScope,
    CareerAnalyticsValidationError,
)

from .models import (
    ANALYTICS_INTERPRETATION,
    COHORT_MINIMUM,
    AchievementGrowthPoint,
    AnalyticsBreakdown,
    AnalyticsPayload,
    AnalyticsRate,
    AnalyticsTimeBucket,
    ApplicationAnalyticsFact,
    RequirementCoverageTrendPoint,
    ResumeVersionOutcomePerformance,
    SupplementalAnalyticsSnapshot,
)

_BANNED_INTERPRETATION_TERMS = (
    "caused",
    "causes",
    "predicts",
    "improved your chances",
    "guarantee",
)
_MAX_DIMENSIONS = 20
_MAX_BUCKETS = 24


def aggregate(
    *,
    scope: AnalyticsScope,
    applications: tuple[ApplicationAnalyticsFact, ...],
    supplemental: SupplementalAnalyticsSnapshot,
    window_start: date,
    window_end: date,
    timezone: str,
) -> AnalyticsPayload:
    """Aggregate only purpose-minimized metadata into a reproducible payload."""

    if window_end < window_start:
        raise CareerAnalyticsValidationError("analytics window is invalid")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise CareerAnalyticsValidationError("timezone is invalid") from exc
    _validate_interpretation(ANALYTICS_INTERPRETATION)
    selected = tuple(
        fact
        for fact in applications
        if window_start <= _application_cohort_date(fact, zone) <= window_end
    )
    achievements = tuple(
        point
        for point in supplemental.achievements
        if window_start <= _local_date(point.occurred_at, zone) <= window_end
    )
    readiness = tuple(
        sorted(
            (
                point
                for point in supplemental.readiness
                if window_start <= _local_date(point.created_at, zone) <= window_end
            ),
            key=lambda point: (point.created_at, str(point.analysis_id)),
        )
    )

    application_count = len(selected)
    response_count = sum(fact.first_response_at is not None for fact in selected)
    interview_count = sum(fact.first_interview_at is not None for fact in selected)
    offer_count = sum(fact.first_offer_at is not None for fact in selected)
    coverage_values = [
        fact.requirement_coverage_basis_points
        for fact in selected
        if fact.requirement_coverage_basis_points is not None
    ]
    readiness_values = [
        point.raw_score_basis_points
        for point in readiness
        if point.raw_score_basis_points is not None
    ]
    counts = {
        "achievements": len(achievements),
        "applications": application_count,
        "interviews": interview_count,
        "offers": offer_count,
        "readinessAnalyses": len(readiness),
        "responses": response_count,
    }
    if len(coverage_values) >= COHORT_MINIMUM:
        counts["averageRequirementCoverageBasisPoints"] = _rounded_average(coverage_values)
    if len(readiness_values) >= COHORT_MINIMUM:
        counts["averageRoleReadinessBasisPoints"] = _rounded_average(readiness_values)

    rates = {
        "interviewRate": AnalyticsRate.calculate(interview_count, application_count),
        "offerRate": AnalyticsRate.calculate(offer_count, application_count),
        "responseRate": AnalyticsRate.calculate(response_count, application_count),
    }
    breakdowns = {
        "industry": _breakdown(fact.industry for fact in selected),
        "role": _breakdown(fact.role_title for fact in selected),
        "source": _breakdown(fact.source for fact in selected),
        "stage": _breakdown(fact.stage for fact in selected),
        "resumeVersion": _breakdown(
            f"v{fact.resume_version_number}:{fact.resume_version_id}" for fact in selected
        ),
    }
    if scope == AnalyticsScope.OVERVIEW:
        breakdowns = {"stage": breakdowns["stage"]}
    elif scope == AnalyticsScope.READINESS:
        breakdowns = {
            "readinessLabel": _breakdown(point.label for point in readiness),
            "readinessRole": _breakdown(point.role_label for point in readiness),
        }

    periods = _periods(window_start, window_end)
    return AnalyticsPayload(
        scope=scope,
        counts=counts,
        rates=rates,
        breakdowns=breakdowns,
        time_buckets=_time_buckets(
            applications=selected,
            achievements=achievements,
            periods=periods,
            zone=zone,
        ),
        requirement_coverage_trend=(
            _coverage_trend(applications=selected, periods=periods, zone=zone)
            if scope != AnalyticsScope.READINESS
            else ()
        ),
        outcomes_by_resume_version=(
            _resume_version_outcomes(selected) if scope != AnalyticsScope.READINESS else ()
        ),
        readiness_history=readiness if scope == AnalyticsScope.READINESS else (),
    )


def _rounded_average(values: list[int]) -> int:
    return (sum(values) + len(values) // 2) // len(values)


def _label(value: str | None) -> str:
    if value is None or not value.strip():
        return "unknown"
    normalized = " ".join(value.strip().split())
    if len(normalized) > 160 or any(ord(character) < 32 for character in normalized):
        raise CareerAnalyticsValidationError("analytics dimension label is invalid")
    return normalized


def _breakdown(values: Iterable[str | None]) -> tuple[AnalyticsBreakdown, ...]:
    counter = Counter(_label(value) for value in values)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))
    visible = ranked[:_MAX_DIMENSIONS]
    hidden_count = sum(count for _, count in ranked[_MAX_DIMENSIONS:])
    result = [AnalyticsBreakdown(key=key, count=count) for key, count in visible]
    if hidden_count:
        result.append(AnalyticsBreakdown(key="other", count=hidden_count))
    return tuple(result)


def _time_buckets(
    *,
    applications: tuple[ApplicationAnalyticsFact, ...],
    achievements: tuple[AchievementGrowthPoint, ...],
    periods: tuple[tuple[date, date], ...],
    zone: ZoneInfo,
) -> tuple[AnalyticsTimeBucket, ...]:
    buckets: list[AnalyticsTimeBucket] = []
    for start, end in periods:
        selected = tuple(
            fact for fact in applications if start <= _application_cohort_date(fact, zone) <= end
        )
        selected_achievements = tuple(
            point for point in achievements if start <= _local_date(point.occurred_at, zone) <= end
        )
        buckets.append(
            AnalyticsTimeBucket(
                start=start,
                end=end,
                applications=len(selected),
                interviews=sum(
                    fact.first_interview_at is not None
                    and start <= _local_date(fact.first_interview_at, zone) <= end
                    for fact in applications
                ),
                offers=sum(
                    fact.first_offer_at is not None
                    and start <= _local_date(fact.first_offer_at, zone) <= end
                    for fact in applications
                ),
                achievements=len(selected_achievements),
            )
        )
    return tuple(buckets)


def _periods(window_start: date, window_end: date) -> tuple[tuple[date, date], ...]:
    total_days = (window_end - window_start).days + 1
    count = min(_MAX_BUCKETS, total_days)
    return tuple(
        (
            window_start + timedelta(days=index * total_days // count),
            window_start + timedelta(days=((index + 1) * total_days // count) - 1),
        )
        for index in range(count)
    )


def _coverage_trend(
    *,
    applications: tuple[ApplicationAnalyticsFact, ...],
    periods: tuple[tuple[date, date], ...],
    zone: ZoneInfo,
) -> tuple[RequirementCoverageTrendPoint, ...]:
    return tuple(
        RequirementCoverageTrendPoint.calculate(
            start=start,
            end=end,
            values=tuple(
                fact.requirement_coverage_basis_points
                for fact in applications
                if fact.requirement_coverage_basis_points is not None
                and start <= _application_cohort_date(fact, zone) <= end
            ),
        )
        for start, end in periods
    )


def _resume_version_outcomes(
    applications: tuple[ApplicationAnalyticsFact, ...],
) -> tuple[ResumeVersionOutcomePerformance, ...]:
    known_numbers: dict[UUID, int] = {}
    groups: dict[tuple[UUID, int], list[ApplicationAnalyticsFact]] = {}
    for fact in applications:
        existing = known_numbers.setdefault(
            fact.resume_version_id,
            fact.resume_version_number,
        )
        if existing != fact.resume_version_number:
            raise CareerAnalyticsValidationError(
                "analytics resume version identity is inconsistent"
            )
        groups.setdefault(
            (fact.resume_version_id, fact.resume_version_number),
            [],
        ).append(fact)
    return tuple(
        ResumeVersionOutcomePerformance(
            resume_version_id=version_id,
            resume_version_number=version_number,
            application_count=len(values),
            response_rate=AnalyticsRate.calculate(
                sum(value.first_response_at is not None for value in values),
                len(values),
            ),
            interview_rate=AnalyticsRate.calculate(
                sum(value.first_interview_at is not None for value in values),
                len(values),
            ),
            offer_rate=AnalyticsRate.calculate(
                sum(value.first_offer_at is not None for value in values),
                len(values),
            ),
        )
        for (version_id, version_number), values in sorted(
            groups.items(),
            key=lambda item: (item[0][1], str(item[0][0])),
        )
    )


def _application_cohort_date(
    fact: ApplicationAnalyticsFact,
    zone: ZoneInfo,
) -> date:
    return _local_date(fact.first_applied_at or fact.created_at, zone)


def _local_date(value: datetime, zone: ZoneInfo) -> date:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CareerAnalyticsValidationError("analytics source timestamp must include a timezone")
    return value.astimezone(zone).date()


def _validate_interpretation(value: str) -> None:
    normalized = value.casefold()
    if any(term in normalized for term in _BANNED_INTERPRETATION_TERMS):
        raise CareerAnalyticsValidationError("analytics interpretation is not non-causal")
