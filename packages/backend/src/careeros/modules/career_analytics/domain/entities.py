"""Privacy-preserving Career Analytics job and snapshot entities."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import CareerAnalyticsConflict, CareerAnalyticsValidationError

MAX_INT32 = 2_147_483_647
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CareerAnalyticsValidationError(f"{field} must include a timezone")
    return value


def _text(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= maximum:
        raise CareerAnalyticsValidationError(
            f"{field} must contain between 1 and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise CareerAnalyticsValidationError(f"{field} contains unsupported characters")
    return normalized


def _version(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_INT32:
        raise CareerAnalyticsValidationError("version must be a positive int32")


def _timezone(value: str) -> str:
    normalized = _text(value, "timezone", 80)
    try:
        ZoneInfo(normalized)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise CareerAnalyticsValidationError("timezone is invalid") from exc
    return normalized


class AnalyticsScope(StrEnum):
    OVERVIEW = "overview"
    APPLICATIONS = "applications"
    READINESS = "readiness"


class AnalyticsJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    DEAD_LETTER = "dead_letter"


class AnalyticsSnapshotStatus(StrEnum):
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


class AnalyticsOutboxStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    PUBLISHED = "published"
    DEAD_LETTER = "dead_letter"


class AnalyticsAuditAction(StrEnum):
    REFRESH_REQUESTED = "refresh_requested"
    REFRESH_STARTED = "refresh_started"
    SNAPSHOT_CREATED = "snapshot_created"
    REFRESH_RETRY_SCHEDULED = "refresh_retry_scheduled"
    REFRESH_DEAD_LETTERED = "refresh_dead_lettered"
    SNAPSHOT_MARKED_STALE = "snapshot_marked_stale"


@dataclass(slots=True)
class AnalyticsRefreshJob:
    id: UUID
    owner_user_id: UUID
    scope: AnalyticsScope
    window_start: date
    window_end: date
    timezone: str
    idempotency_key: str
    request_fingerprint: str
    status: AnalyticsJobStatus
    attempts: int
    max_attempts: int
    trace_id: str
    source_watermark_before: dict[str, object] | None
    source_watermark_after: dict[str, object] | None
    lease_token: UUID | None
    leased_until: datetime | None
    next_attempt_at: datetime
    safe_error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if self.window_end < self.window_start or (self.window_end - self.window_start).days > 3660:
            raise CareerAnalyticsValidationError(
                "analytics window must be ordered and no longer than ten years"
            )
        self.timezone = _timezone(self.timezone)
        if _IDEMPOTENCY_KEY.fullmatch(self.idempotency_key) is None:
            raise CareerAnalyticsValidationError("idempotency key is invalid")
        if _SHA256.fullmatch(self.request_fingerprint) is None:
            raise CareerAnalyticsValidationError("request fingerprint is invalid")
        if _TRACE_ID.fullmatch(self.trace_id) is None:
            raise CareerAnalyticsValidationError("trace id is invalid")
        if not 0 <= self.attempts <= self.max_attempts <= 10:
            raise CareerAnalyticsValidationError("analytics retry configuration is invalid")
        if self.safe_error_code is not None and _SAFE_CODE.fullmatch(self.safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")
        _version(self.version)
        for field, value in (
            ("next attempt", self.next_attempt_at),
            ("created at", self.created_at),
            ("updated at", self.updated_at),
        ):
            _aware(value, field)
        for field, optional_value in (
            ("leased until", self.leased_until),
            ("completed at", self.completed_at),
        ):
            if optional_value is not None:
                _aware(optional_value, field)
        if (self.lease_token is None) != (self.leased_until is None):
            raise CareerAnalyticsValidationError("analytics lease is incomplete")

    def claim(self, *, token: UUID, now: datetime, leased_until: datetime) -> None:
        _aware(now, "claim time")
        _aware(leased_until, "lease expiry")
        if leased_until <= now:
            raise CareerAnalyticsValidationError("lease expiry must be in the future")
        if self.status not in {AnalyticsJobStatus.QUEUED, AnalyticsJobStatus.RETRY_WAIT}:
            raise CareerAnalyticsConflict("analytics job cannot be claimed")
        if self.next_attempt_at > now:
            raise CareerAnalyticsConflict("analytics job is not due")
        if self.attempts >= self.max_attempts:
            raise CareerAnalyticsConflict("analytics retry budget is exhausted")
        self.status = AnalyticsJobStatus.RUNNING
        self.attempts += 1
        self.lease_token = token
        self.leased_until = leased_until
        self.safe_error_code = None
        self.version += 1
        _version(self.version)
        self.updated_at = now

    def complete(
        self,
        *,
        token: UUID,
        before: dict[str, object],
        after: dict[str, object],
        now: datetime,
    ) -> None:
        self._require_lease(token, now)
        self.source_watermark_before = before
        self.source_watermark_after = after
        self.status = AnalyticsJobStatus.COMPLETED
        self.lease_token = None
        self.leased_until = None
        self.completed_at = now
        self.version += 1
        _version(self.version)
        self.updated_at = now

    def fail(
        self,
        *,
        token: UUID,
        safe_error_code: str,
        retry_at: datetime,
        now: datetime,
    ) -> None:
        self._require_lease(token, now)
        if _SAFE_CODE.fullmatch(safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")
        _aware(retry_at, "retry time")
        self.safe_error_code = safe_error_code
        self.lease_token = None
        self.leased_until = None
        self.status = (
            AnalyticsJobStatus.DEAD_LETTER
            if self.attempts >= self.max_attempts
            else AnalyticsJobStatus.RETRY_WAIT
        )
        self.next_attempt_at = retry_at
        self.version += 1
        _version(self.version)
        self.updated_at = now

    def recover_expired(self, *, now: datetime) -> None:
        """Release an expired worker lease and apply its bounded retry policy."""

        _aware(now, "recovery time")
        if (
            self.status != AnalyticsJobStatus.RUNNING
            or self.leased_until is None
            or self.leased_until >= now
        ):
            raise CareerAnalyticsConflict("analytics job lease is not expired")
        self.status = (
            AnalyticsJobStatus.DEAD_LETTER
            if self.attempts >= self.max_attempts
            else AnalyticsJobStatus.RETRY_WAIT
        )
        self.lease_token = None
        self.leased_until = None
        self.next_attempt_at = now
        self.safe_error_code = "lease_expired"
        self.version += 1
        _version(self.version)
        self.updated_at = now

    def dead_letter_undelivered(
        self,
        *,
        safe_error_code: str,
        now: datetime,
    ) -> None:
        """Terminalize a refresh whose outbox exhausted before worker delivery."""

        _aware(now, "dead-letter time")
        if _SAFE_CODE.fullmatch(safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")
        if (
            self.status
            not in {
                AnalyticsJobStatus.QUEUED,
                AnalyticsJobStatus.RETRY_WAIT,
            }
            or self.lease_token is not None
            or self.leased_until is not None
        ):
            raise CareerAnalyticsConflict("delivered analytics job cannot be dead-lettered")
        self.status = AnalyticsJobStatus.DEAD_LETTER
        self.safe_error_code = safe_error_code
        self.next_attempt_at = now
        self.version += 1
        _version(self.version)
        self.updated_at = now

    def _require_lease(self, token: UUID, now: datetime) -> None:
        _aware(now, "operation time")
        if (
            self.status != AnalyticsJobStatus.RUNNING
            or self.lease_token != token
            or self.leased_until is None
            or self.leased_until < now
        ):
            raise CareerAnalyticsConflict("analytics lease is invalid or expired")


@dataclass(slots=True)
class AnalyticsOutboxMessage:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    status: AnalyticsOutboxStatus
    attempts: int
    max_attempts: int
    lease_token: UUID | None
    leased_until: datetime | None
    next_attempt_at: datetime
    safe_error_code: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    def __post_init__(self) -> None:
        if not 0 <= self.attempts <= self.max_attempts <= 10:
            raise CareerAnalyticsValidationError("analytics outbox retry budget is invalid")
        for field, value in (
            ("next attempt", self.next_attempt_at),
            ("created at", self.created_at),
            ("updated at", self.updated_at),
        ):
            _aware(value, field)
        if (self.lease_token is None) != (self.leased_until is None):
            raise CareerAnalyticsValidationError("analytics outbox lease is incomplete")
        if self.leased_until is not None:
            _aware(self.leased_until, "lease expiry")
        if self.published_at is not None:
            _aware(self.published_at, "published at")
        if self.safe_error_code is not None and _SAFE_CODE.fullmatch(self.safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")

    def claim(self, *, token: UUID, now: datetime, leased_until: datetime) -> None:
        _aware(now, "claim time")
        _aware(leased_until, "lease expiry")
        if self.status != AnalyticsOutboxStatus.PENDING or self.next_attempt_at > now:
            raise CareerAnalyticsConflict("analytics outbox message cannot be claimed")
        if self.attempts >= self.max_attempts or leased_until <= now:
            raise CareerAnalyticsConflict("analytics outbox retry budget is exhausted")
        self.status = AnalyticsOutboxStatus.LEASED
        self.attempts += 1
        self.lease_token = token
        self.leased_until = leased_until
        self.updated_at = now

    def published(
        self,
        *,
        token: UUID,
        now: datetime,
        recovery_at: datetime,
    ) -> None:
        self._require_lease(token, now)
        _aware(recovery_at, "delivery recovery time")
        if recovery_at <= now:
            raise CareerAnalyticsValidationError("delivery recovery time must be in the future")
        self.status = AnalyticsOutboxStatus.PUBLISHED
        self.lease_token = None
        self.leased_until = None
        self.next_attempt_at = recovery_at
        self.safe_error_code = None
        self.published_at = now
        self.updated_at = now

    def recover_published(
        self,
        *,
        safe_error_code: str,
        retry_at: datetime,
        now: datetime,
    ) -> None:
        """Re-arm one unconfirmed handoff or terminalize its delivery budget."""

        _aware(now, "delivery recovery time")
        _aware(retry_at, "delivery retry time")
        if _SAFE_CODE.fullmatch(safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")
        if (
            self.status != AnalyticsOutboxStatus.PUBLISHED
            or self.lease_token is not None
            or self.leased_until is not None
        ):
            raise CareerAnalyticsConflict("analytics delivery cannot be recovered")
        self.status = (
            AnalyticsOutboxStatus.DEAD_LETTER
            if self.attempts >= self.max_attempts
            else AnalyticsOutboxStatus.PENDING
        )
        self.next_attempt_at = retry_at
        self.safe_error_code = safe_error_code
        self.updated_at = now

    def failed(
        self,
        *,
        token: UUID,
        safe_error_code: str,
        retry_at: datetime,
        now: datetime,
    ) -> None:
        self._require_lease(token, now)
        if _SAFE_CODE.fullmatch(safe_error_code) is None:
            raise CareerAnalyticsValidationError("safe error code is invalid")
        _aware(retry_at, "retry time")
        self.status = (
            AnalyticsOutboxStatus.DEAD_LETTER
            if self.attempts >= self.max_attempts
            else AnalyticsOutboxStatus.PENDING
        )
        self.lease_token = None
        self.leased_until = None
        self.next_attempt_at = retry_at
        self.safe_error_code = safe_error_code
        self.updated_at = now

    def recover_expired(self, *, now: datetime) -> None:
        """Release an expired publish lease or exhaust it deterministically."""

        _aware(now, "recovery time")
        if (
            self.status != AnalyticsOutboxStatus.LEASED
            or self.leased_until is None
            or self.leased_until >= now
        ):
            raise CareerAnalyticsConflict("analytics outbox lease is not expired")
        self.status = (
            AnalyticsOutboxStatus.DEAD_LETTER
            if self.attempts >= self.max_attempts
            else AnalyticsOutboxStatus.PENDING
        )
        self.lease_token = None
        self.leased_until = None
        self.next_attempt_at = now
        self.safe_error_code = "lease_expired"
        self.updated_at = now

    def _require_lease(self, token: UUID, now: datetime) -> None:
        _aware(now, "operation time")
        if (
            self.status != AnalyticsOutboxStatus.LEASED
            or self.lease_token != token
            or self.leased_until is None
            or self.leased_until < now
        ):
            raise CareerAnalyticsConflict("analytics outbox lease is invalid or expired")


@dataclass(slots=True)
class AnalyticsSnapshot:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    scope: AnalyticsScope
    metric_definition_version: str
    window_start: date
    window_end: date
    timezone: str
    source_watermark: dict[str, object]
    payload: dict[str, object]
    payload_sha256: str
    status: AnalyticsSnapshotStatus
    created_at: datetime
    stale_at: datetime | None

    def __post_init__(self) -> None:
        self.metric_definition_version = _text(
            self.metric_definition_version,
            "metric definition version",
            120,
        )
        if self.window_end < self.window_start:
            raise CareerAnalyticsValidationError("analytics snapshot window is invalid")
        self.timezone = _timezone(self.timezone)
        if _SHA256.fullmatch(self.payload_sha256) is None:
            raise CareerAnalyticsValidationError("analytics payload hash is invalid")
        _aware(self.created_at, "snapshot creation time")
        if self.stale_at is not None:
            _aware(self.stale_at, "snapshot stale time")

    def mark_stale(self, now: datetime) -> None:
        _aware(now, "stale time")
        if self.status == AnalyticsSnapshotStatus.READY:
            self.status = AnalyticsSnapshotStatus.STALE
            self.stale_at = now

    def verify_payload_hash(self) -> bool:
        """Recompute the canonical JSON digest before stored output is trusted."""

        encoded = json.dumps(
            self.payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest() == self.payload_sha256


@dataclass(frozen=True, slots=True)
class AnalyticsAuditEvent:
    id: UUID
    owner_user_id: UUID
    action: AnalyticsAuditAction
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    request_id: str | None
    trace_id: str
    metadata: dict[str, str]
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.target_type, "audit target type", 80)
        if self.request_id is not None:
            _text(self.request_id, "request id", 128)
        if (self.actor_user_id is None) != (self.request_id is None):
            raise CareerAnalyticsValidationError("analytics audit actor context is incomplete")
        if self.actor_user_id is not None and self.actor_user_id != self.owner_user_id:
            raise CareerAnalyticsValidationError("analytics audit actor must match owner")
        if _TRACE_ID.fullmatch(self.trace_id) is None:
            raise CareerAnalyticsValidationError("trace id is invalid")
        if len(self.metadata) > 12 or any(
            len(key) > 80 or len(value) > 160 for key, value in self.metadata.items()
        ):
            raise CareerAnalyticsValidationError("analytics audit metadata is invalid")
        _aware(self.created_at, "audit creation time")
