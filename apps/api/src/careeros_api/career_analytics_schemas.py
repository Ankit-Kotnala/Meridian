"""Strict wire schemas for private, correlation-only Career Analytics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class CareerAnalyticsSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


AnalyticsScopeValue = Literal["overview", "applications", "readiness"]
AnalyticsJobStatusValue = Literal[
    "queued",
    "running",
    "retry_wait",
    "completed",
    "dead_letter",
]
AnalyticsSnapshotStatusValue = Literal["ready", "stale", "failed"]
FreshnessValue = Literal["current", "stale", "refreshing", "empty", "failed"]
BasisPoints = Annotated[int, Field(strict=True, ge=0, le=10_000)]


class AnalyticsRefreshRequest(CareerAnalyticsSchema):
    scope: AnalyticsScopeValue
    window_start: date
    window_end: date
    timezone: str = Field(default="UTC", min_length=1, max_length=80)


class AnalyticsRefreshResponse(CareerAnalyticsSchema):
    id: UUID
    scope: AnalyticsScopeValue
    window_start: date
    window_end: date
    timezone: str = Field(min_length=1, max_length=80)
    status: AnalyticsJobStatusValue
    attempts: int = Field(ge=0, le=10)
    max_attempts: int = Field(ge=1, le=10)
    safe_error_code: str | None = Field(default=None, max_length=64)
    version: int = Field(ge=1, le=2_147_483_647)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class AnalyticsSourceWatermarkResponse(CareerAnalyticsSchema):
    source: str = Field(min_length=1, max_length=80)
    token: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    record_count: int = Field(ge=0)
    max_updated_at: datetime | None


class AnalyticsRateResponse(CareerAnalyticsSchema):
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    value_basis_points: BasisPoints | None = None
    suppressed: bool
    suppression_reason: str | None = Field(default=None, max_length=200)


class AnalyticsBreakdownResponse(CareerAnalyticsSchema):
    key: str = Field(min_length=1, max_length=160)
    count: int = Field(ge=0)


class AnalyticsTimeBucketResponse(CareerAnalyticsSchema):
    start: date
    end: date
    applications: int = Field(ge=0)
    interviews: int = Field(ge=0)
    offers: int = Field(ge=0)
    achievements: int = Field(ge=0)


class RequirementCoverageTrendResponse(CareerAnalyticsSchema):
    start: date
    end: date
    value_basis_points: BasisPoints | None
    sample_size: int | None = Field(default=None, ge=5)
    suppressed: bool
    suppression_reason: str | None = Field(default=None, max_length=200)


class ResumeVersionOutcomePerformanceResponse(CareerAnalyticsSchema):
    resume_version_id: UUID
    resume_version_number: int = Field(ge=1)
    application_count: int = Field(ge=1)
    response_rate: AnalyticsRateResponse
    interview_rate: AnalyticsRateResponse
    offer_rate: AnalyticsRateResponse


class ReadinessHistoryResponse(CareerAnalyticsSchema):
    analysis_id: UUID
    role_label: str = Field(min_length=1, max_length=160)
    raw_score_basis_points: BasisPoints | None
    label: str = Field(min_length=1, max_length=80)
    engine_version: str = Field(min_length=1, max_length=120)
    created_at: datetime


class AnalyticsPayloadResponse(CareerAnalyticsSchema):
    scope: AnalyticsScopeValue
    counts: dict[str, int]
    rates: dict[str, AnalyticsRateResponse]
    breakdowns: dict[str, list[AnalyticsBreakdownResponse]]
    time_buckets: list[AnalyticsTimeBucketResponse] = Field(max_length=24)
    requirement_coverage_trend: list[RequirementCoverageTrendResponse] = Field(max_length=24)
    outcomes_by_resume_version: list[ResumeVersionOutcomePerformanceResponse] = Field(
        max_length=500
    )
    readiness_history: list[ReadinessHistoryResponse] = Field(max_length=500)
    interpretation: str = Field(min_length=1, max_length=300)
    metric_definition_version: str = Field(min_length=1, max_length=120)


class AnalyticsMetricDefinitionResponse(CareerAnalyticsSchema):
    key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    cohort: str = Field(min_length=1, max_length=500)
    numerator: str | None = Field(default=None, max_length=500)
    denominator: str | None = Field(default=None, max_length=500)
    event_timestamp: str = Field(min_length=1, max_length=200)
    suppression_minimum: int | None = Field(default=None, ge=5, le=100)


class AnalyticsSuppressionPolicyResponse(CareerAnalyticsSchema):
    applies_to: str = Field(min_length=1, max_length=500)
    minimum_denominator: int = Field(ge=5, le=100)
    reason: str = Field(min_length=1, max_length=200)
    suppressed_fields: str = Field(min_length=1, max_length=300)


class AnalyticsReportResponse(CareerAnalyticsSchema):
    scope: AnalyticsScopeValue
    status: AnalyticsSnapshotStatusValue | None
    freshness: FreshnessValue
    metric_definition_version: str = Field(min_length=1, max_length=120)
    interpretation: str = Field(min_length=1, max_length=300)
    window_start: date
    window_end: date
    timezone: str = Field(min_length=1, max_length=80)
    cohort_definition: str = Field(min_length=1, max_length=500)
    metric_definitions: list[AnalyticsMetricDefinitionResponse] = Field(
        min_length=1,
        max_length=50,
    )
    suppression_policy: AnalyticsSuppressionPolicyResponse
    timestamp_semantics: dict[str, str]
    source_watermarks: dict[str, AnalyticsSourceWatermarkResponse]
    payload: AnalyticsPayloadResponse | None
    generated_at: datetime | None
    refresh: AnalyticsRefreshResponse | None
