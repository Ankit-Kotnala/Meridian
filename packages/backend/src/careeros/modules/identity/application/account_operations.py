"""Durable, capability-scoped account export and erasure orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.identity.domain import AuthenticatedPrincipal
from careeros.modules.identity.domain.account_operations import (
    AccountOperation,
    AccountOperationKind,
    AccountOperationStatus,
)
from careeros.modules.identity.domain.errors import (
    IdentityConflict,
    RecentAuthenticationRequired,
    ResourceNotFound,
)

from .models import RequestContext
from .ports import Clock


@dataclass(frozen=True, slots=True)
class AccountOperationView:
    operation: AccountOperation
    operation_token: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class AccountExportArtifact:
    object_key: str
    sha256: str
    size_bytes: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountDeletionOutcome:
    blocker: str | None = None


@dataclass(frozen=True, slots=True)
class AccountOperationBatchResult:
    claimed: int
    succeeded: int
    blocked: int
    deferred: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class AccountExportCleanupResult:
    completed: int
    failed: int


class AccountOperationTokenManager(Protocol):
    def issue_for_id(self, operation_id: UUID) -> tuple[str, str]: ...

    def parse(self, encoded: str) -> tuple[UUID, str] | None: ...

    def verify(self, expected_digest: str, secret: str) -> bool: ...

    def fingerprint(self, user_id: UUID) -> str: ...


class AccountOperationsUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_operation(
        self,
        operation_id: UUID,
        *,
        for_update: bool = False,
    ) -> AccountOperation | None: ...

    async def get_idempotent_operation(
        self,
        user_id: UUID,
        kind: AccountOperationKind,
        idempotency_key: str,
    ) -> AccountOperation | None: ...

    async def add_operation(
        self,
        operation: AccountOperation,
        *,
        disable_account: bool,
        now: datetime,
    ) -> None: ...

    async def claim_due_operations(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[AccountOperation]: ...

    async def save_operation(
        self,
        operation: AccountOperation,
        *,
        expected_lease_token: UUID | None,
        expected_status: AccountOperationStatus | None = None,
    ) -> None: ...

    async def get_expired_export_for_cleanup(
        self,
        now: datetime,
    ) -> AccountOperation | None: ...

    async def restore_blocked_account(self, user_id: UUID, now: datetime) -> None: ...

    async def commit(self) -> None: ...


AccountOperationsUnitOfWorkFactory = Callable[[], AccountOperationsUnitOfWork]


class AccountPrivacyStore(Protocol):
    async def build_export(
        self,
        user_id: UUID,
        operation_id: UUID,
        generated_at: datetime,
        expires_at: datetime,
    ) -> AccountExportArtifact: ...

    async def erase_account(self, user_id: UUID) -> AccountDeletionOutcome: ...

    async def delete_artifact(self, object_key: str) -> None: ...

    async def presign_export(
        self,
        object_key: str,
        *,
        expires_in_seconds: int,
    ) -> str: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


@dataclass(frozen=True, slots=True)
class AccountOperationsPolicy:
    max_attempts: int = 5
    lease_seconds: int = 900
    retry_base_seconds: int = 30
    recent_auth_seconds: int = 600
    export_retention_seconds: int = 86_400

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("account operation attempt budget is invalid")
        if not 30 <= self.lease_seconds <= 3_600:
            raise ValueError("account operation lease is invalid")
        if not 1 <= self.retry_base_seconds <= 3_600:
            raise ValueError("account operation retry delay is invalid")
        if not 60 <= self.recent_auth_seconds <= 3_600:
            raise ValueError("account deletion recent-auth window is invalid")
        if not 3_600 <= self.export_retention_seconds <= 30 * 86_400:
            raise ValueError("account export retention is invalid")


class AccountOperationsService:
    """Request and inspect privacy operations using a high-entropy capability."""

    def __init__(
        self,
        *,
        unit_of_work: AccountOperationsUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        tokens: AccountOperationTokenManager,
        privacy_store: AccountPrivacyStore | None = None,
        policy: AccountOperationsPolicy | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._tokens = tokens
        self._store = privacy_store
        self._policy = policy or AccountOperationsPolicy()

    async def request_export(
        self,
        principal: AuthenticatedPrincipal,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> AccountOperationView:
        return await self._request(
            principal,
            AccountOperationKind.EXPORT,
            idempotency_key,
            context,
        )

    async def request_deletion(
        self,
        principal: AuthenticatedPrincipal,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> AccountOperationView:
        now = self._clock.now()
        if not principal.was_recently_authenticated(now, self._policy.recent_auth_seconds):
            raise RecentAuthenticationRequired
        return await self._request(
            principal,
            AccountOperationKind.DELETION,
            idempotency_key,
            context,
        )

    async def get_status(
        self,
        operation_id: UUID,
        operation_token: str,
    ) -> AccountOperationView:
        operation = await self._authorized_operation(operation_id, operation_token)
        return AccountOperationView(operation)

    async def create_download_url(
        self,
        operation_id: UUID,
        operation_token: str,
        *,
        expires_in_seconds: int = 120,
    ) -> str:
        if self._store is None:
            raise IdentityConflict("account export download is unavailable")
        if not 30 <= expires_in_seconds <= 300:
            raise IdentityConflict("account export download expiry is invalid")
        operation = await self._authorized_operation(operation_id, operation_token)
        now = self._clock.now()
        if (
            operation.kind is not AccountOperationKind.EXPORT
            or operation.status is not AccountOperationStatus.SUCCEEDED
            or operation.artifact_object_key is None
            or operation.artifact_expires_at is None
            or operation.artifact_expires_at <= now
        ):
            raise ResourceNotFound
        return await self._store.presign_export(
            operation.artifact_object_key,
            expires_in_seconds=expires_in_seconds,
        )

    async def _request(
        self,
        principal: AuthenticatedPrincipal,
        kind: AccountOperationKind,
        idempotency_key: str,
        context: RequestContext,
    ) -> AccountOperationView:
        if not 8 <= len(idempotency_key) <= 128:
            raise IdentityConflict("account operation idempotency key is invalid")
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            replay = await uow.get_idempotent_operation(
                principal.user_id,
                kind,
                idempotency_key,
            )
            if replay is not None:
                token, digest = self._tokens.issue_for_id(replay.id)
                if digest != replay.capability_hash:
                    raise IdentityConflict("account operation capability drift")
                return AccountOperationView(replay, token)
            operation_id = self._ids.new()
            token, capability_hash = self._tokens.issue_for_id(operation_id)
            operation = AccountOperation(
                id=operation_id,
                user_id=principal.user_id,
                user_fingerprint=self._tokens.fingerprint(principal.user_id),
                capability_hash=capability_hash,
                kind=kind,
                status=AccountOperationStatus.QUEUED,
                idempotency_key=idempotency_key,
                request_id=context.request_id,
                trace_id=context.trace_id,
                attempts=0,
                max_attempts=self._policy.max_attempts,
                next_attempt_at=now,
                requested_at=now,
                updated_at=now,
            )
            await uow.add_operation(
                operation,
                disable_account=kind is AccountOperationKind.DELETION,
                now=now,
            )
            await uow.commit()
            return AccountOperationView(operation, token)

    async def _authorized_operation(
        self,
        operation_id: UUID,
        operation_token: str,
    ) -> AccountOperation:
        parsed = self._tokens.parse(operation_token)
        if parsed is None or parsed[0] != operation_id:
            raise ResourceNotFound
        async with self._unit_of_work() as uow:
            operation = await uow.get_operation(operation_id)
        if operation is None or not self._tokens.verify(
            operation.capability_hash,
            parsed[1],
        ):
            raise ResourceNotFound
        return operation


class AccountOperationProcessor:
    """Execute privacy work from durable database state."""

    def __init__(
        self,
        *,
        unit_of_work: AccountOperationsUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        privacy_store: AccountPrivacyStore,
        policy: AccountOperationsPolicy | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._store = privacy_store
        self._policy = policy or AccountOperationsPolicy()

    async def process_due(self, limit: int) -> AccountOperationBatchResult:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("account operation limit must be between 1 and 100")
        now = self._clock.now()
        lease_token = self._ids.new()
        async with self._unit_of_work() as uow:
            claimed = await uow.claim_due_operations(
                limit=limit,
                lease_token=lease_token,
                now=now,
                lease_seconds=self._policy.lease_seconds,
            )
            await uow.commit()
        succeeded = blocked = deferred = dead_lettered = 0
        for operation in claimed:
            outcome = await self._process_one(operation.id, lease_token)
            if outcome == "succeeded":
                succeeded += 1
            elif outcome == "blocked":
                blocked += 1
            elif outcome == "dead_lettered":
                dead_lettered += 1
            else:
                deferred += 1
        return AccountOperationBatchResult(
            claimed=len(claimed),
            succeeded=succeeded,
            blocked=blocked,
            deferred=deferred,
            dead_lettered=dead_lettered,
        )

    async def cleanup_expired_exports(self, limit: int) -> AccountExportCleanupResult:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("account export cleanup limit must be between 1 and 100")
        completed = failed = 0
        for _ in range(limit):
            now = self._clock.now()
            try:
                async with self._unit_of_work() as uow:
                    operation = await uow.get_expired_export_for_cleanup(now)
                    if operation is None:
                        break
                    if operation.artifact_object_key is None:
                        raise IdentityConflict("expired account export artifact is unavailable")
                    await self._store.delete_artifact(operation.artifact_object_key)
                    operation.expire_artifact(now)
                    await uow.save_operation(
                        operation,
                        expected_lease_token=None,
                        expected_status=AccountOperationStatus.SUCCEEDED,
                    )
                    await uow.commit()
                    completed += 1
            except Exception:
                failed += 1
                break
        return AccountExportCleanupResult(completed=completed, failed=failed)

    async def _process_one(self, operation_id: UUID, lease_token: UUID) -> str:
        artifact: AccountExportArtifact | None = None
        try:
            async with self._unit_of_work() as uow:
                claimed = await uow.get_operation(operation_id)
            if (
                claimed is None
                or claimed.status is not AccountOperationStatus.RUNNING
                or claimed.lease_token != lease_token
            ):
                return "deferred"
            if claimed.kind is AccountOperationKind.EXPORT:
                if claimed.user_id is None:
                    return "deferred"
                generated_at = self._clock.now()
                artifact = await self._store.build_export(
                    claimed.user_id,
                    claimed.id,
                    generated_at,
                    generated_at + timedelta(seconds=self._policy.export_retention_seconds),
                )
                result = await self._finalize_export(
                    operation_id,
                    lease_token,
                    artifact,
                )
                if result != "succeeded":
                    await self._store.delete_artifact(artifact.object_key)
                return result
            if claimed.user_id is None:
                return await self._finalize_deletion(
                    operation_id,
                    lease_token,
                    AccountDeletionOutcome(),
                )
            outcome = await self._store.erase_account(claimed.user_id)
            return await self._finalize_deletion(operation_id, lease_token, outcome)
        except Exception:
            if artifact is not None:
                await self._store.delete_artifact(artifact.object_key)
            return await self._record_failure(operation_id, lease_token)

    async def _finalize_export(
        self,
        operation_id: UUID,
        lease_token: UUID,
        artifact: AccountExportArtifact,
    ) -> str:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            operation = await uow.get_operation(operation_id, for_update=True)
            if (
                operation is None
                or operation.status is not AccountOperationStatus.RUNNING
                or operation.lease_token != lease_token
            ):
                return "deferred"
            operation.complete_export(
                lease_token,
                now,
                object_key=artifact.object_key,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                expires_at=artifact.expires_at,
            )
            await uow.save_operation(operation, expected_lease_token=lease_token)
            await uow.commit()
            return "succeeded"

    async def _finalize_deletion(
        self,
        operation_id: UUID,
        lease_token: UUID,
        outcome: AccountDeletionOutcome,
    ) -> str:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            operation = await uow.get_operation(operation_id, for_update=True)
            if (
                operation is None
                or operation.status is not AccountOperationStatus.RUNNING
                or operation.lease_token != lease_token
            ):
                return "deferred"
            if outcome.blocker is not None:
                if operation.user_id is None:
                    return "deferred"
                user_id = operation.user_id
                operation.block(lease_token, now, outcome.blocker)
                await uow.restore_blocked_account(user_id, now)
                await uow.save_operation(operation, expected_lease_token=lease_token)
                await uow.commit()
                return "blocked"
            operation.complete_deletion(lease_token, now)
            await uow.save_operation(operation, expected_lease_token=lease_token)
            await uow.commit()
            return "succeeded"

    async def _record_failure(self, operation_id: UUID, lease_token: UUID) -> str:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            operation = await uow.get_operation(operation_id, for_update=True)
            if operation is None or operation.terminal:
                return "deferred"
            dead_lettered = operation.fail(
                lease_token,
                now,
                "account_operation_unavailable",
                self._policy.retry_base_seconds,
            )
            await uow.save_operation(
                operation,
                expected_lease_token=lease_token,
            )
            await uow.commit()
            return "dead_lettered" if dead_lettered else "deferred"
