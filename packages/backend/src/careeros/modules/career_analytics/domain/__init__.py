"""Career Analytics domain API."""

from .entities import (
    AnalyticsAuditAction,
    AnalyticsAuditEvent,
    AnalyticsJobStatus,
    AnalyticsOutboxMessage,
    AnalyticsOutboxStatus,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
    AnalyticsSnapshotStatus,
)
from .errors import (
    CareerAnalyticsConflict,
    CareerAnalyticsError,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsNotFound,
    CareerAnalyticsQuotaExceeded,
    CareerAnalyticsSourceChanged,
    CareerAnalyticsSourceLimitExceeded,
    CareerAnalyticsUnavailable,
    CareerAnalyticsValidationError,
    CareerAnalyticsVersionConflict,
)

__all__ = [
    "AnalyticsAuditAction",
    "AnalyticsAuditEvent",
    "AnalyticsJobStatus",
    "AnalyticsOutboxMessage",
    "AnalyticsOutboxStatus",
    "AnalyticsRefreshJob",
    "AnalyticsScope",
    "AnalyticsSnapshot",
    "AnalyticsSnapshotStatus",
    "CareerAnalyticsConflict",
    "CareerAnalyticsError",
    "CareerAnalyticsIdempotencyConflict",
    "CareerAnalyticsNotFound",
    "CareerAnalyticsQuotaExceeded",
    "CareerAnalyticsSourceChanged",
    "CareerAnalyticsSourceLimitExceeded",
    "CareerAnalyticsUnavailable",
    "CareerAnalyticsValidationError",
    "CareerAnalyticsVersionConflict",
]
