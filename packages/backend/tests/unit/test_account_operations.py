"""Durable account export and erasure orchestration tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from careeros.modules.identity.application import (
    AccountDeletionOutcome,
    AccountExportArtifact,
    AccountOperationProcessor,
    AccountOperationsPolicy,
    AccountOperationsService,
)
from careeros.modules.identity.application.models import RequestContext
from careeros.modules.identity.domain import (
    AccountOperation,
    AccountOperationKind,
    AccountOperationStatus,
    AuthenticatedPrincipal,
    AuthMethod,
)
from careeros.modules.identity.domain.errors import RecentAuthenticationRequired
from careeros.modules.identity.infrastructure.account_operation_security import (
    HmacAccountOperationTokenManager,
)

NOW = datetime(2026, 7, 27, 2, tzinfo=UTC)
_SECRET = "fictional-account-operation-secret-at-least-32-bytes"  # noqa: S105


@dataclass(slots=True)
class MutableClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


class MemoryAccountOperations:
    def __init__(self) -> None:
        self.operations: dict[UUID, AccountOperation] = {}
        self.disabled_users: set[UUID] = set()
        self.restored_users: set[UUID] = set()

    def __call__(self) -> MemoryAccountOperations:
        return self

    async def __aenter__(self) -> MemoryAccountOperations:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get_operation(
        self,
        operation_id: UUID,
        *,
        for_update: bool = False,
    ) -> AccountOperation | None:
        del for_update
        return self.operations.get(operation_id)

    async def get_idempotent_operation(
        self,
        user_id: UUID,
        kind: AccountOperationKind,
        idempotency_key: str,
    ) -> AccountOperation | None:
        return next(
            (
                operation
                for operation in self.operations.values()
                if operation.user_id == user_id
                and operation.kind is kind
                and operation.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add_operation(
        self,
        operation: AccountOperation,
        *,
        disable_account: bool,
        now: datetime,
    ) -> None:
        del now
        self.operations[operation.id] = operation
        if disable_account and operation.user_id is not None:
            self.disabled_users.add(operation.user_id)

    async def claim_due_operations(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[AccountOperation]:
        claimed: list[AccountOperation] = []
        for operation in self.operations.values():
            if (
                len(claimed) < limit
                and not operation.terminal
                and operation.next_attempt_at <= now
                and (operation.lease_expires_at is None or operation.lease_expires_at <= now)
            ):
                operation.claim(lease_token, now, lease_seconds)
                claimed.append(operation)
        return claimed

    async def save_operation(
        self,
        operation: AccountOperation,
        *,
        expected_lease_token: UUID | None,
        expected_status: AccountOperationStatus | None = None,
    ) -> None:
        del expected_lease_token, expected_status
        self.operations[operation.id] = operation

    async def get_expired_export_for_cleanup(
        self,
        now: datetime,
    ) -> AccountOperation | None:
        return next(
            (
                operation
                for operation in self.operations.values()
                if operation.status is AccountOperationStatus.SUCCEEDED
                and operation.artifact_expires_at is not None
                and operation.artifact_expires_at <= now
            ),
            None,
        )

    async def restore_blocked_account(self, user_id: UUID, now: datetime) -> None:
        del now
        self.disabled_users.discard(user_id)
        self.restored_users.add(user_id)

    async def commit(self) -> None:
        return None


class MemoryPrivacyStore:
    def __init__(self) -> None:
        self.blocker: str | None = None
        self.fail_exports = False
        self.deleted_artifacts: list[str] = []

    async def build_export(
        self,
        user_id: UUID,
        operation_id: UUID,
        generated_at: datetime,
        expires_at: datetime,
    ) -> AccountExportArtifact:
        del user_id
        if self.fail_exports:
            raise RuntimeError("fictional object outage")
        return AccountExportArtifact(
            object_key=f"account-exports/{operation_id}/fictional.zip",
            sha256="a" * 64,
            size_bytes=512,
            expires_at=expires_at,
        )

    async def erase_account(self, user_id: UUID) -> AccountDeletionOutcome:
        del user_id
        return AccountDeletionOutcome(self.blocker)

    async def delete_artifact(self, object_key: str) -> None:
        self.deleted_artifacts.append(object_key)

    async def presign_export(
        self,
        object_key: str,
        *,
        expires_in_seconds: int,
    ) -> str:
        return f"https://objects.example.test/{object_key}?ttl={expires_in_seconds}"


def _principal(*, authenticated_at: datetime = NOW) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        authenticated_at=authenticated_at,
        auth_method=AuthMethod.PASSWORD,
    )


def _context() -> RequestContext:
    return RequestContext(
        request_id="fictional-account-operation-request",
        trace_id="a" * 32,
        device_label="test",
    )


@pytest.mark.asyncio
async def test_export_is_idempotent_capability_scoped_and_downloadable() -> None:
    state = MemoryAccountOperations()
    store = MemoryPrivacyStore()
    tokens = HmacAccountOperationTokenManager(_SECRET)
    service = AccountOperationsService(
        unit_of_work=state,
        clock=MutableClock(),
        identifiers=UuidFactory(),
        tokens=tokens,
        privacy_store=store,
    )
    principal = _principal()

    first = await service.request_export(
        principal,
        idempotency_key="fictional-export-request",
        context=_context(),
    )
    replay = await service.request_export(
        principal,
        idempotency_key="fictional-export-request",
        context=_context(),
    )

    assert replay.operation.id == first.operation.id
    assert replay.operation_token == first.operation_token
    assert first.operation_token is not None
    assert first.operation_token not in repr(first)

    processor = AccountOperationProcessor(
        unit_of_work=state,
        clock=MutableClock(),
        identifiers=UuidFactory(),
        privacy_store=store,
    )
    result = await processor.process_due(1)
    assert result.claimed == result.succeeded == 1
    status = await service.get_status(first.operation.id, first.operation_token)
    assert status.operation.status is AccountOperationStatus.SUCCEEDED
    url = await service.create_download_url(
        first.operation.id,
        first.operation_token,
    )
    assert url.startswith("https://objects.example.test/account-exports/")


@pytest.mark.asyncio
async def test_deletion_requires_recent_auth_and_restores_blocked_account() -> None:
    state = MemoryAccountOperations()
    store = MemoryPrivacyStore()
    store.blocker = "organization_ownership_transfer_required"
    service = AccountOperationsService(
        unit_of_work=state,
        clock=MutableClock(),
        identifiers=UuidFactory(),
        tokens=HmacAccountOperationTokenManager(_SECRET),
        privacy_store=store,
    )
    stale = _principal(authenticated_at=NOW - timedelta(hours=1))
    with pytest.raises(RecentAuthenticationRequired):
        await service.request_deletion(
            stale,
            idempotency_key="fictional-delete-stale",
            context=_context(),
        )

    principal = _principal()
    requested = await service.request_deletion(
        principal,
        idempotency_key="fictional-delete-request",
        context=_context(),
    )
    assert principal.user_id in state.disabled_users
    processor = AccountOperationProcessor(
        unit_of_work=state,
        clock=MutableClock(),
        identifiers=UuidFactory(),
        privacy_store=store,
    )
    result = await processor.process_due(1)
    assert result.blocked == 1
    assert principal.user_id in state.restored_users
    assert requested.operation.status is AccountOperationStatus.BLOCKED


@pytest.mark.asyncio
async def test_export_artifact_expiry_deletes_object_before_state_redaction() -> None:
    state = MemoryAccountOperations()
    store = MemoryPrivacyStore()
    clock = MutableClock()
    service = AccountOperationsService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        tokens=HmacAccountOperationTokenManager(_SECRET),
        privacy_store=store,
        policy=AccountOperationsPolicy(export_retention_seconds=3_600),
    )
    requested = await service.request_export(
        _principal(),
        idempotency_key="fictional-expiring-export",
        context=_context(),
    )
    processor = AccountOperationProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        privacy_store=store,
        policy=AccountOperationsPolicy(export_retention_seconds=3_600),
    )
    await processor.process_due(1)
    object_key = requested.operation.artifact_object_key
    assert object_key is not None
    clock.value = NOW + timedelta(hours=2)

    result = await processor.cleanup_expired_exports(1)

    assert result.completed == 1
    assert store.deleted_artifacts == [object_key]
    assert requested.operation.status is AccountOperationStatus.EXPIRED
    assert requested.operation.artifact_object_key is None
