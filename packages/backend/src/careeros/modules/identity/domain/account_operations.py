"""Durable account export and erasure state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from .errors import IdentityConflict

_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,79}$")


class AccountOperationKind(StrEnum):
    EXPORT = "export"
    DELETION = "deletion"


class AccountOperationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    DEAD_LETTERED = "dead_lettered"
    EXPIRED = "expired"


@dataclass(slots=True)
class AccountOperation:
    id: UUID
    user_id: UUID | None
    user_fingerprint: str
    capability_hash: str
    kind: AccountOperationKind
    status: AccountOperationStatus
    idempotency_key: str
    request_id: str
    trace_id: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    requested_at: datetime
    updated_at: datetime
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    artifact_object_key: str | None = None
    artifact_sha256: str | None = None
    artifact_size_bytes: int | None = None
    artifact_expires_at: datetime | None = None
    completed_at: datetime | None = None
    blocked_reason: str | None = None
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", self.user_fingerprint):
            raise IdentityConflict("account operation fingerprint is invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", self.capability_hash):
            raise IdentityConflict("account operation capability is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise IdentityConflict("account operation idempotency key is invalid")
        if not _safe_correlation_id(self.request_id, maximum=128):
            raise IdentityConflict("account operation request ID is invalid")
        if not _safe_correlation_id(self.trace_id, maximum=128):
            raise IdentityConflict("account operation trace ID is invalid")
        if not 0 <= self.attempts <= self.max_attempts <= 10:
            raise IdentityConflict("account operation attempt budget is invalid")
        if self.requested_at > self.updated_at:
            raise IdentityConflict("account operation timestamps are invalid")
        if (self.lease_token is None) != (self.lease_expires_at is None):
            raise IdentityConflict("account operation lease is inconsistent")
        if self.status is AccountOperationStatus.RUNNING:
            if self.lease_token is None:
                raise IdentityConflict("running account operation requires a lease")
        elif self.lease_token is not None:
            raise IdentityConflict("non-running account operation cannot retain a lease")
        artifact_fields = (
            self.artifact_object_key,
            self.artifact_sha256,
            self.artifact_size_bytes,
            self.artifact_expires_at,
        )
        if any(value is not None for value in artifact_fields) != all(
            value is not None for value in artifact_fields
        ):
            raise IdentityConflict("account export artifact metadata is incomplete")
        if self.artifact_sha256 is not None and not re.fullmatch(
            r"[a-f0-9]{64}", self.artifact_sha256
        ):
            raise IdentityConflict("account export artifact digest is invalid")
        if self.artifact_size_bytes is not None and self.artifact_size_bytes <= 0:
            raise IdentityConflict("account export artifact size is invalid")
        if any(value is not None for value in artifact_fields) and (
            self.kind is not AccountOperationKind.EXPORT
            or self.status is not AccountOperationStatus.SUCCEEDED
        ):
            raise IdentityConflict("account export artifact state is invalid")
        if (
            self.kind is AccountOperationKind.EXPORT
            and self.status is AccountOperationStatus.SUCCEEDED
            and self.artifact_object_key is None
        ):
            raise IdentityConflict("completed account export requires an artifact")
        if (
            self.status
            in {
                AccountOperationStatus.SUCCEEDED,
                AccountOperationStatus.BLOCKED,
                AccountOperationStatus.DEAD_LETTERED,
                AccountOperationStatus.EXPIRED,
            }
            and self.completed_at is None
        ):
            raise IdentityConflict("terminal account operation requires a timestamp")
        if (
            self.status is AccountOperationStatus.EXPIRED
            and self.kind is not AccountOperationKind.EXPORT
        ):
            raise IdentityConflict("only an account export can expire")
        if (self.blocked_reason is not None) != (self.status is AccountOperationStatus.BLOCKED):
            raise IdentityConflict("account operation blocker state is invalid")
        if self.blocked_reason is not None:
            _safe_code(self.blocked_reason)
        if self.last_error_code is not None:
            _safe_code(self.last_error_code)

    @property
    def terminal(self) -> bool:
        return self.status in {
            AccountOperationStatus.SUCCEEDED,
            AccountOperationStatus.BLOCKED,
            AccountOperationStatus.DEAD_LETTERED,
            AccountOperationStatus.EXPIRED,
        }

    def claim(self, lease_token: UUID, now: datetime, lease_seconds: int) -> None:
        if self.terminal or self.next_attempt_at > now or not 30 <= lease_seconds <= 3_600:
            raise IdentityConflict("account operation cannot be claimed")
        if self.lease_expires_at is not None and self.lease_expires_at > now:
            raise IdentityConflict("account operation lease is active")
        self.status = AccountOperationStatus.RUNNING
        self.lease_token = lease_token
        self.lease_expires_at = now + timedelta(seconds=lease_seconds)
        self.updated_at = now
        self.__post_init__()

    def complete_export(
        self,
        lease_token: UUID,
        now: datetime,
        *,
        object_key: str,
        sha256: str,
        size_bytes: int,
        expires_at: datetime,
    ) -> None:
        self._require_lease(lease_token, now)
        if self.kind is not AccountOperationKind.EXPORT or expires_at <= now:
            raise IdentityConflict("account export completion is invalid")
        self.status = AccountOperationStatus.SUCCEEDED
        self.artifact_object_key = object_key
        self.artifact_sha256 = sha256
        self.artifact_size_bytes = size_bytes
        self.artifact_expires_at = expires_at
        self.completed_at = now
        self.last_error_code = None
        self.lease_token = None
        self.lease_expires_at = None
        self.updated_at = now
        self.__post_init__()

    def complete_deletion(self, lease_token: UUID, now: datetime) -> None:
        self._require_lease(lease_token, now)
        if self.kind is not AccountOperationKind.DELETION:
            raise IdentityConflict("account deletion completion is invalid")
        self.status = AccountOperationStatus.SUCCEEDED
        self.user_id = None
        self.completed_at = now
        self.last_error_code = None
        self.lease_token = None
        self.lease_expires_at = None
        self.updated_at = now
        self.__post_init__()

    def block(self, lease_token: UUID, now: datetime, reason: str) -> None:
        self._require_lease(lease_token, now)
        _safe_code(reason)
        self.status = AccountOperationStatus.BLOCKED
        self.blocked_reason = reason
        self.completed_at = now
        self.lease_token = None
        self.lease_expires_at = None
        self.updated_at = now
        self.__post_init__()

    def fail(
        self,
        lease_token: UUID,
        now: datetime,
        error_code: str,
        retry_base_seconds: int,
    ) -> bool:
        self._require_lease(lease_token, now)
        _safe_code(error_code)
        if not 1 <= retry_base_seconds <= 3_600:
            raise IdentityConflict("account operation retry delay is invalid")
        self.attempts += 1
        self.last_error_code = error_code
        self.lease_token = None
        self.lease_expires_at = None
        self.updated_at = now
        if self.attempts >= self.max_attempts:
            self.status = AccountOperationStatus.DEAD_LETTERED
            self.completed_at = now
        else:
            self.status = AccountOperationStatus.RETRY_WAIT
            delay = min(retry_base_seconds * (2 ** (self.attempts - 1)), 3_600)
            self.next_attempt_at = now + timedelta(seconds=delay)
        self.__post_init__()
        return self.status is AccountOperationStatus.DEAD_LETTERED

    def expire_artifact(self, now: datetime) -> str:
        if (
            self.kind is not AccountOperationKind.EXPORT
            or self.status is not AccountOperationStatus.SUCCEEDED
            or self.artifact_object_key is None
            or self.artifact_expires_at is None
            or self.artifact_expires_at > now
        ):
            raise IdentityConflict("account export cannot expire")
        object_key = self.artifact_object_key
        self.status = AccountOperationStatus.EXPIRED
        self.artifact_object_key = None
        self.artifact_sha256 = None
        self.artifact_size_bytes = None
        self.artifact_expires_at = None
        self.updated_at = now
        self.__post_init__()
        return object_key

    def _require_lease(self, lease_token: UUID, now: datetime) -> None:
        if (
            self.status is not AccountOperationStatus.RUNNING
            or self.lease_token != lease_token
            or self.lease_expires_at is None
            or self.lease_expires_at <= now
        ):
            raise IdentityConflict("account operation lease is unavailable")


def _safe_code(value: str) -> None:
    if _SAFE_CODE.fullmatch(value) is None:
        raise IdentityConflict("account operation safe code is invalid")


def _safe_correlation_id(value: str, *, maximum: int) -> bool:
    return (
        1 <= len(value) <= maximum
        and value.isprintable()
        and not any(character.isspace() for character in value)
    )
