"""Career Growth domain errors."""

from __future__ import annotations


class CareerGrowthError(Exception):
    code = "career_growth_error"


class CareerGrowthValidationError(CareerGrowthError, ValueError):
    code = "career_growth_validation_failed"


class CareerGrowthNotFound(CareerGrowthError):
    code = "career_growth_not_found"


class CareerGrowthConflict(CareerGrowthError):
    code = "career_growth_conflict"


class CareerGrowthQuotaExceeded(CareerGrowthConflict):
    code = "career_growth_quota_exceeded"


class CareerGrowthVersionConflict(CareerGrowthConflict):
    code = "career_growth_version_conflict"


class CareerGrowthIdempotencyConflict(CareerGrowthConflict):
    code = "career_growth_idempotency_conflict"


class CareerGrowthUnavailable(CareerGrowthError):
    code = "career_growth_unavailable"
