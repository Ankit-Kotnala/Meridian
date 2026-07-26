"""Identifier-only Celery result contracts shared by task adapters."""

from typing import TypedDict


class PingResult(TypedDict):
    status: str
    service: str
    version: str


class ProcessingTaskResult(TypedDict):
    job_id: str
    status: str
    retryable: bool
    safe_error_code: str | None


class ResumeExportTaskResult(TypedDict):
    export_id: str
    status: str
    retryable: bool
    safe_error_code: str | None


class OutboxResult(TypedDict):
    published: int
    failed: int
    dead_lettered: int


class CleanupTaskResult(TypedDict):
    expired_uploads: int
    queued_guest_deletions: int
    revoked_guest_sessions: int
    object_cleanups_completed: int
    object_cleanup_failures: int
    object_cleanup_dead_letters: int


class ReconciliationTaskResult(TypedDict):
    requeued: int
    dead_lettered: int


class ResumeExportReconciliationTaskResult(TypedDict):
    requeued: int
    dead_lettered: int
    object_cleanups_completed: int
    object_cleanup_failures: int
    object_cleanup_dead_letters: int


class AttachmentCleanupTaskResult(TypedDict):
    completed: int
    failed: int
    dead_lettered: int


class AnalyticsReconciliationTaskResult(TypedDict):
    recovered_jobs: int
    dead_lettered_jobs: int
    recovered_outbox: int
    dead_lettered_outbox: int
    requeued_deliveries: int


class NetworkingReminderTaskResult(TypedDict):
    claimed: int
    processed: int
    deferred: int
    failed: int
    dead_lettered: int


class NetworkingReminderRecoveryTaskResult(TypedDict):
    recovered: int
    dead_lettered: int
class OrganizationInvitationTaskResult(TypedDict):
    claimed: int
    delivered: int
    cancelled: int
    deferred: int
    dead_lettered: int
class AccountPrivacyTaskResult(TypedDict):
    claimed: int
    succeeded: int
    blocked: int
    deferred: int
    dead_lettered: int


class AccountExportCleanupTaskResult(TypedDict):
    completed: int
    failed: int
