"""Transport-neutral commands and purpose-minimized Career Analytics views."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from careeros.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsScope,
    AnalyticsSnapshotStatus,
    CareerAnalyticsValidationError,
)

ANALYTICS_INTERPRETATION = (
    "These are observed patterns in your records, not causal findings, "
    "predictions, or hiring probabilities."
)
METRIC_DEFINITION_VERSION = "career-analytics/1.0.0"
COHORT_MINIMUM = 5
APPLICATION_COHORT_DEFINITION = (
    "Applications whose first-applied timestamp, falling back to record creation "
    "when no applied event exists, has a local calendar date inside the requested "
    "inclusive window."
)
SUPPRESSION_REASON = (
    "Not shown for privacy and reliability because this cohort has fewer than 5 records."
)
TIMESTAMP_SEMANTICS = {
    "achievementGrowth": (
        "Current eligible achievement evidence only; bucketed by the evidence "
        "revision occurrence timestamp converted to the report timezone."
    ),
    "applicationCohort": (
        "Bucketed by firstAppliedAt, falling back to createdAt, converted to the report timezone."
    ),
    "interviews": ("Bucketed by firstInterviewAt converted to the report timezone."),
    "offers": "Bucketed by firstOfferAt converted to the report timezone.",
    "readinessHistory": (
        "Included and ordered by analysis createdAt converted to the report timezone."
    ),
    "responses": (
        "A cohort outcome is observed when firstResponseAt exists; its time-series "
        "event timestamp is firstResponseAt in the report timezone."
    ),
}


@dataclass(frozen=True, slots=True)
class AnalyticsMetricDefinition:
    key: str
    description: str
    cohort: str
    numerator: str | None
    denominator: str | None
    event_timestamp: str
    suppression_minimum: int | None
    version: str = METRIC_DEFINITION_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "cohort": self.cohort,
            "denominator": self.denominator,
            "description": self.description,
            "eventTimestamp": self.event_timestamp,
            "key": self.key,
            "numerator": self.numerator,
            "suppressionMinimum": self.suppression_minimum,
            "version": self.version,
        }


METRIC_DEFINITIONS = (
    AnalyticsMetricDefinition(
        key="applications",
        description="Count of applications in the selected application cohort.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator=None,
        denominator=None,
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="applicationStageCounts",
        description="Counts of applications by their current recorded workflow stage.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator=None,
        denominator=None,
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="applicationsByRole",
        description="Counts of applications grouped by the recorded role title.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator=None,
        denominator=None,
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="applicationsByIndustry",
        description="Counts of applications grouped by the recorded industry.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator=None,
        denominator=None,
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="applicationsBySource",
        description="Counts of applications grouped by the user-recorded application source.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator=None,
        denominator=None,
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="responseRate",
        description="Observed response events among the selected application cohort.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator="Cohort applications with firstResponseAt.",
        denominator="All applications in the selected cohort.",
        event_timestamp="firstResponseAt",
        suppression_minimum=COHORT_MINIMUM,
    ),
    AnalyticsMetricDefinition(
        key="interviewRate",
        description="Observed first-interview events among the selected application cohort.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator="Cohort applications with firstInterviewAt.",
        denominator="All applications in the selected cohort.",
        event_timestamp="firstInterviewAt",
        suppression_minimum=COHORT_MINIMUM,
    ),
    AnalyticsMetricDefinition(
        key="offerRate",
        description="Observed first-offer events among the selected application cohort.",
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator="Cohort applications with firstOfferAt.",
        denominator="All applications in the selected cohort.",
        event_timestamp="firstOfferAt",
        suppression_minimum=COHORT_MINIMUM,
    ),
    AnalyticsMetricDefinition(
        key="requirementCoverageTrend",
        description=(
            "Mean grounded requirement coverage for applications whose pinned "
            "analysis exposes a coverage value."
        ),
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator="Sum of eligible application coverage basis-point values.",
        denominator="Cohort applications with a coverage value.",
        event_timestamp="firstAppliedAt; createdAt fallback",
        suppression_minimum=COHORT_MINIMUM,
    ),
    AnalyticsMetricDefinition(
        key="outcomesByResumeVersion",
        description=(
            "Observed response, interview, and offer rates grouped by the exact "
            "immutable resume version pinned to each application."
        ),
        cohort=APPLICATION_COHORT_DEFINITION,
        numerator="Applications in each version cohort with the named observed event.",
        denominator="Applications pinned to that exact immutable resume version.",
        event_timestamp="firstResponseAt, firstInterviewAt, or firstOfferAt",
        suppression_minimum=COHORT_MINIMUM,
    ),
    AnalyticsMetricDefinition(
        key="achievementGrowth",
        description=(
            "Count of current, eligible Career Record revisions whose evidence "
            "type is exactly achievement."
        ),
        cohort=(
            "Current active achievement evidence at supported, confirmed, or "
            "verified strength with a local occurrence date inside the requested "
            "inclusive window."
        ),
        numerator=None,
        denominator=None,
        event_timestamp="evidence revision createdAt",
        suppression_minimum=None,
    ),
    AnalyticsMetricDefinition(
        key="roleReadinessHistory",
        description=(
            "Historical user-owned Role Readiness results retained with their "
            "immutable engine version and non-predictive label."
        ),
        cohort=(
            "Role Readiness analyses whose createdAt local date is inside the "
            "requested inclusive window."
        ),
        numerator=None,
        denominator=None,
        event_timestamp="analysis createdAt",
        suppression_minimum=None,
    ),
)


def metric_definitions_payload() -> tuple[dict[str, object], ...]:
    return tuple(value.as_dict() for value in METRIC_DEFINITIONS)


def suppression_policy_payload() -> dict[str, object]:
    return {
        "appliesTo": (
            "Every rate, percentage, and average coverage value, including "
            "resume-version segments and time buckets."
        ),
        "minimumDenominator": COHORT_MINIMUM,
        "reason": SUPPRESSION_REASON,
        "suppressedFields": ("numerator, denominator/sample size, and basis-point value are null"),
    }


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class RefreshAnalytics:
    scope: AnalyticsScope
    window_start: date
    window_end: date
    timezone: str = "UTC"


@dataclass(frozen=True, slots=True)
class AnalyticsSourceWatermark:
    source: str
    token: str
    record_count: int
    max_updated_at: datetime | None

    def __post_init__(self) -> None:
        if not self.source or len(self.source) > 80:
            raise CareerAnalyticsValidationError("analytics source name is invalid")
        if (
            len(self.token) != 71
            or not self.token.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in self.token[7:])
            or self.record_count < 0
        ):
            raise CareerAnalyticsValidationError("analytics source watermark is invalid")
        if self.max_updated_at is not None and (
            self.max_updated_at.tzinfo is None or self.max_updated_at.utcoffset() is None
        ):
            raise CareerAnalyticsValidationError("analytics source watermark is invalid")

    def as_dict(self) -> dict[str, object]:
        return {
            "maxUpdatedAt": (
                self.max_updated_at.isoformat() if self.max_updated_at is not None else None
            ),
            "recordCount": self.record_count,
            "source": self.source,
            "token": self.token,
        }


@dataclass(frozen=True, slots=True)
class ApplicationSourceCursor:
    created_at: datetime
    application_id: UUID


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsFact:
    application_id: UUID
    stage: str
    outcome: str
    role_title: str
    source: str | None
    industry: str | None
    resume_version_id: UUID
    resume_version_number: int
    requirement_coverage_basis_points: int | None
    first_applied_at: datetime | None
    first_response_at: datetime | None
    first_interview_at: datetime | None
    first_offer_at: datetime | None
    outcome_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsSourcePage:
    data: tuple[ApplicationAnalyticsFact, ...]
    next_cursor: ApplicationSourceCursor | None


@dataclass(frozen=True, slots=True)
class ReadinessHistoryPoint:
    analysis_id: UUID
    role_label: str
    raw_score_basis_points: int | None
    label: str
    engine_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AchievementGrowthPoint:
    evidence_revision_id: UUID
    category: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SupplementalAnalyticsSnapshot:
    readiness: tuple[ReadinessHistoryPoint, ...]
    achievements: tuple[AchievementGrowthPoint, ...]


@dataclass(frozen=True, slots=True)
class AnalyticsRate:
    numerator: int | None
    denominator: int | None
    value_basis_points: int | None
    suppressed: bool
    suppression_reason: str | None

    @classmethod
    def calculate(cls, numerator: int, denominator: int) -> AnalyticsRate:
        if denominator < COHORT_MINIMUM:
            return cls(
                numerator=None,
                denominator=None,
                value_basis_points=None,
                suppressed=True,
                suppression_reason=SUPPRESSION_REASON,
            )
        value = min(10_000, (numerator * 10_000 + denominator // 2) // denominator)
        return cls(
            numerator=numerator,
            denominator=denominator,
            value_basis_points=value,
            suppressed=False,
            suppression_reason=None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "denominator": self.denominator,
            "numerator": self.numerator,
            "suppressed": self.suppressed,
            "suppressionReason": self.suppression_reason,
            "valueBasisPoints": self.value_basis_points,
        }


@dataclass(frozen=True, slots=True)
class AnalyticsBreakdown:
    key: str
    count: int

    def as_dict(self) -> dict[str, object]:
        return {"count": self.count, "key": self.key}


@dataclass(frozen=True, slots=True)
class AnalyticsTimeBucket:
    start: date
    end: date
    applications: int
    interviews: int
    offers: int
    achievements: int

    def as_dict(self) -> dict[str, object]:
        return {
            "achievements": self.achievements,
            "applications": self.applications,
            "end": self.end.isoformat(),
            "interviews": self.interviews,
            "offers": self.offers,
            "start": self.start.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RequirementCoverageTrendPoint:
    start: date
    end: date
    value_basis_points: int | None
    sample_size: int | None
    suppressed: bool
    suppression_reason: str | None

    @classmethod
    def calculate(
        cls,
        *,
        start: date,
        end: date,
        values: tuple[int, ...],
    ) -> RequirementCoverageTrendPoint:
        if len(values) < COHORT_MINIMUM:
            return cls(
                start=start,
                end=end,
                value_basis_points=None,
                sample_size=None,
                suppressed=True,
                suppression_reason=SUPPRESSION_REASON,
            )
        return cls(
            start=start,
            end=end,
            value_basis_points=(sum(values) + len(values) // 2) // len(values),
            sample_size=len(values),
            suppressed=False,
            suppression_reason=None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "end": self.end.isoformat(),
            "sampleSize": self.sample_size,
            "start": self.start.isoformat(),
            "suppressed": self.suppressed,
            "suppressionReason": self.suppression_reason,
            "valueBasisPoints": self.value_basis_points,
        }


@dataclass(frozen=True, slots=True)
class ResumeVersionOutcomePerformance:
    resume_version_id: UUID
    resume_version_number: int
    application_count: int
    response_rate: AnalyticsRate
    interview_rate: AnalyticsRate
    offer_rate: AnalyticsRate

    def as_dict(self) -> dict[str, object]:
        return {
            "applicationCount": self.application_count,
            "interviewRate": self.interview_rate.as_dict(),
            "offerRate": self.offer_rate.as_dict(),
            "responseRate": self.response_rate.as_dict(),
            "resumeVersionId": str(self.resume_version_id),
            "resumeVersionNumber": self.resume_version_number,
        }


@dataclass(frozen=True, slots=True)
class AnalyticsPayload:
    scope: AnalyticsScope
    counts: dict[str, int]
    rates: dict[str, AnalyticsRate]
    breakdowns: dict[str, tuple[AnalyticsBreakdown, ...]]
    time_buckets: tuple[AnalyticsTimeBucket, ...]
    requirement_coverage_trend: tuple[RequirementCoverageTrendPoint, ...]
    outcomes_by_resume_version: tuple[ResumeVersionOutcomePerformance, ...]
    readiness_history: tuple[ReadinessHistoryPoint, ...]
    interpretation: str = ANALYTICS_INTERPRETATION

    def as_dict(self) -> dict[str, object]:
        readiness = [
            {
                "analysisId": str(point.analysis_id),
                "createdAt": point.created_at.isoformat(),
                "engineVersion": point.engine_version,
                "label": point.label,
                "rawScoreBasisPoints": point.raw_score_basis_points,
                "roleLabel": point.role_label,
            }
            for point in self.readiness_history
        ]
        return {
            "breakdowns": {
                key: [item.as_dict() for item in values]
                for key, values in sorted(self.breakdowns.items())
            },
            "counts": dict(sorted(self.counts.items())),
            "interpretation": self.interpretation,
            "metricDefinitionVersion": METRIC_DEFINITION_VERSION,
            "outcomesByResumeVersion": [
                value.as_dict() for value in self.outcomes_by_resume_version
            ],
            "rates": {key: value.as_dict() for key, value in sorted(self.rates.items())},
            "readinessHistory": readiness,
            "requirementCoverageTrend": [
                value.as_dict() for value in self.requirement_coverage_trend
            ],
            "scope": self.scope.value,
            "timeBuckets": [bucket.as_dict() for bucket in self.time_buckets],
        }

    def sha256(self) -> str:
        encoded = json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AnalyticsRefreshView:
    id: UUID
    scope: AnalyticsScope
    window_start: date
    window_end: date
    timezone: str
    status: AnalyticsJobStatus
    attempts: int
    max_attempts: int
    safe_error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClaimedAnalyticsOutbox:
    message_id: UUID
    job_id: UUID
    lease_token: UUID
    job_version_at_claim: int


@dataclass(frozen=True, slots=True)
class AnalyticsReconciliationOutcome:
    recovered_jobs: int
    dead_lettered_jobs: int
    recovered_outbox: int
    dead_lettered_outbox: int
    requeued_deliveries: int


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    scope: AnalyticsScope
    status: AnalyticsSnapshotStatus | None
    freshness: str
    metric_definition_version: str
    window_start: date
    window_end: date
    timezone: str
    cohort_definition: str
    metric_definitions: tuple[dict[str, object], ...]
    suppression_policy: dict[str, object]
    timestamp_semantics: dict[str, str]
    source_watermarks: dict[str, object]
    payload: dict[str, object] | None
    generated_at: datetime | None
    refresh: AnalyticsRefreshView | None
