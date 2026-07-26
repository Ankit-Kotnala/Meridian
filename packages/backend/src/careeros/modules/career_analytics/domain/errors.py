"""Career Analytics domain errors."""

from __future__ import annotations


class CareerAnalyticsError(Exception):
    code = "career_analytics_error"


class CareerAnalyticsValidationError(CareerAnalyticsError, ValueError):
    code = "career_analytics_validation_failed"


class CareerAnalyticsNotFound(CareerAnalyticsError):
    code = "career_analytics_not_found"


class CareerAnalyticsConflict(CareerAnalyticsError):
    code = "career_analytics_conflict"


class CareerAnalyticsIdempotencyConflict(CareerAnalyticsConflict):
    code = "career_analytics_idempotency_conflict"


class CareerAnalyticsVersionConflict(CareerAnalyticsConflict):
    code = "career_analytics_version_conflict"


class CareerAnalyticsSourceChanged(CareerAnalyticsConflict):
    code = "career_analytics_source_changed"


class CareerAnalyticsQuotaExceeded(CareerAnalyticsError):
    code = "career_analytics_quota_exceeded"


class CareerAnalyticsUnavailable(CareerAnalyticsError):
    code = "career_analytics_unavailable"


class CareerAnalyticsSourceLimitExceeded(CareerAnalyticsUnavailable):
    code = "career_analytics_source_limit_exceeded"
