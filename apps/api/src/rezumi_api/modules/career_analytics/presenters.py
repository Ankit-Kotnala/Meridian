"""Presentation helpers for Career Analytics HTTP responses."""

from __future__ import annotations

from typing import cast

from rezumi.modules.career_analytics.application import (
    ANALYTICS_INTERPRETATION,
    AnalyticsRefreshView,
    AnalyticsReport,
)

from rezumi_api.modules.career_analytics.schemas import (
    AnalyticsMetricDefinitionResponse,
    AnalyticsPayloadResponse,
    AnalyticsRefreshResponse,
    AnalyticsReportResponse,
    AnalyticsSourceWatermarkResponse,
    AnalyticsSuppressionPolicyResponse,
    FreshnessValue,
)


def analytics_refresh_response(value: AnalyticsRefreshView) -> AnalyticsRefreshResponse:
    return AnalyticsRefreshResponse(
        id=value.id,
        scope=value.scope.value,
        window_start=value.window_start,
        window_end=value.window_end,
        timezone=value.timezone,
        status=value.status.value,
        attempts=value.attempts,
        max_attempts=value.max_attempts,
        safe_error_code=value.safe_error_code,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


def analytics_report_response(value: AnalyticsReport) -> AnalyticsReportResponse:
    watermarks = {
        key: AnalyticsSourceWatermarkResponse.model_validate(raw)
        for key, raw in value.source_watermarks.items()
    }
    return AnalyticsReportResponse(
        scope=value.scope.value,
        status=value.status.value if value.status is not None else None,
        freshness=cast(FreshnessValue, value.freshness),
        metric_definition_version=value.metric_definition_version,
        interpretation=ANALYTICS_INTERPRETATION,
        window_start=value.window_start,
        window_end=value.window_end,
        timezone=value.timezone,
        cohort_definition=value.cohort_definition,
        metric_definitions=[
            AnalyticsMetricDefinitionResponse.model_validate(item)
            for item in value.metric_definitions
        ],
        suppression_policy=AnalyticsSuppressionPolicyResponse.model_validate(
            value.suppression_policy
        ),
        timestamp_semantics=value.timestamp_semantics,
        source_watermarks=watermarks,
        payload=(
            AnalyticsPayloadResponse.model_validate(value.payload)
            if value.payload is not None
            else None
        ),
        generated_at=value.generated_at,
        refresh=(analytics_refresh_response(value.refresh) if value.refresh is not None else None),
    )
