"""SQLAlchemy persistence for durable account privacy operations."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, NoReturn, cast
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.identity.application.account_operations import (
    AccountOperationsUnitOfWork,
)
from careeros.modules.identity.domain.account_operations import (
    AccountOperation,
    AccountOperationKind,
    AccountOperationStatus,
)
from careeros.modules.identity.domain.errors import IdentityConflict, IdentityUnavailable

from .models import (
    AccountOperationModel,
    AuthRefreshTokenModel,
    AuthSessionModel,
    UserModel,
)


class SqlAlchemyAccountOperationsUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyAccountOperationsUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("account operations unit of work is not active")
        return self._session

    async def get_operation(
        self,
        operation_id: UUID,
        *,
        for_update: bool = False,
    ) -> AccountOperation | None:
        statement = select(AccountOperationModel).where(AccountOperationModel.id == operation_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _operation(model) if model is not None else None

    async def get_idempotent_operation(
        self,
        user_id: UUID,
        kind: AccountOperationKind,
        idempotency_key: str,
    ) -> AccountOperation | None:
        model = await self.session.scalar(
            select(AccountOperationModel).where(
                AccountOperationModel.user_id == user_id,
                AccountOperationModel.kind == kind.value,
                AccountOperationModel.idempotency_key == idempotency_key,
            )
        )
        return _operation(model) if model is not None else None

    async def add_operation(
        self,
        operation: AccountOperation,
        *,
        disable_account: bool,
        now: datetime,
    ) -> None:
        if operation.user_id is None:
            raise IdentityConflict("account operation user is unavailable")
        user = await self.session.scalar(
            select(UserModel).where(UserModel.id == operation.user_id).with_for_update()
        )
        if user is None or user.status != "active":
            raise IdentityConflict("account is unavailable for privacy operation")
        if disable_account:
            user.status = "disabled"
            user.auth_version += 1
            user.updated_at = now
            await self.session.execute(
                update(AuthSessionModel)
                .where(
                    AuthSessionModel.user_id == operation.user_id,
                    AuthSessionModel.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await self.session.execute(
                update(AuthRefreshTokenModel)
                .where(
                    AuthRefreshTokenModel.session_id.in_(
                        select(AuthSessionModel.id).where(
                            AuthSessionModel.user_id == operation.user_id
                        )
                    ),
                    AuthRefreshTokenModel.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        self.session.add(AccountOperationModel(**_operation_values(operation)))

    async def claim_due_operations(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[AccountOperation]:
        models = (
            await self.session.scalars(
                select(AccountOperationModel)
                .where(
                    AccountOperationModel.status.in_(
                        (
                            AccountOperationStatus.QUEUED.value,
                            AccountOperationStatus.RETRY_WAIT.value,
                            AccountOperationStatus.RUNNING.value,
                        )
                    ),
                    AccountOperationModel.next_attempt_at <= now,
                    or_(
                        AccountOperationModel.lease_token.is_(None),
                        AccountOperationModel.lease_expires_at <= now,
                    ),
                )
                .order_by(
                    AccountOperationModel.next_attempt_at,
                    AccountOperationModel.requested_at,
                    AccountOperationModel.id,
                )
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        claimed: list[AccountOperation] = []
        for model in models:
            operation = _operation(model)
            operation.claim(lease_token, now, lease_seconds)
            model.status = operation.status.value
            model.lease_token = operation.lease_token
            model.lease_expires_at = operation.lease_expires_at
            model.updated_at = operation.updated_at
            claimed.append(operation)
        await self.session.flush()
        return claimed

    async def save_operation(
        self,
        operation: AccountOperation,
        *,
        expected_lease_token: UUID | None,
        expected_status: AccountOperationStatus | None = None,
    ) -> None:
        statement = update(AccountOperationModel).where(AccountOperationModel.id == operation.id)
        if expected_lease_token is not None:
            statement = statement.where(AccountOperationModel.lease_token == expected_lease_token)
        if expected_status is not None:
            statement = statement.where(AccountOperationModel.status == expected_status.value)
        result = await self.session.execute(
            statement.values(**_operation_values(operation, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise IdentityConflict("account operation fencing conflict")

    async def get_expired_export_for_cleanup(
        self,
        now: datetime,
    ) -> AccountOperation | None:
        model = await self.session.scalar(
            select(AccountOperationModel)
            .where(
                AccountOperationModel.kind == AccountOperationKind.EXPORT.value,
                AccountOperationModel.status == AccountOperationStatus.SUCCEEDED.value,
                AccountOperationModel.artifact_expires_at <= now,
            )
            .order_by(
                AccountOperationModel.artifact_expires_at,
                AccountOperationModel.id,
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return _operation(model) if model is not None else None

    async def restore_blocked_account(self, user_id: UUID, now: datetime) -> None:
        result = await self.session.execute(
            update(UserModel)
            .where(
                UserModel.id == user_id,
                UserModel.status == "disabled",
            )
            .values(status="active", updated_at=now)
        )
        if cast(Any, result).rowcount != 1:
            raise IdentityConflict("blocked account could not be restored")

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True


class SqlAlchemyAccountOperationsUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> AccountOperationsUnitOfWork:
        return SqlAlchemyAccountOperationsUnitOfWork(self._database)


def _operation_values(
    value: AccountOperation,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "user_id": value.user_id,
        "user_fingerprint": bytes.fromhex(value.user_fingerprint),
        "capability_hash": bytes.fromhex(value.capability_hash),
        "kind": value.kind.value,
        "status": value.status.value,
        "idempotency_key": value.idempotency_key,
        "request_id": value.request_id,
        "trace_id": value.trace_id,
        "attempts": value.attempts,
        "max_attempts": value.max_attempts,
        "next_attempt_at": value.next_attempt_at,
        "lease_token": value.lease_token,
        "lease_expires_at": value.lease_expires_at,
        "artifact_object_key": value.artifact_object_key,
        "artifact_sha256": (
            bytes.fromhex(value.artifact_sha256) if value.artifact_sha256 is not None else None
        ),
        "artifact_size_bytes": value.artifact_size_bytes,
        "artifact_expires_at": value.artifact_expires_at,
        "completed_at": value.completed_at,
        "blocked_reason": value.blocked_reason,
        "last_error_code": value.last_error_code,
        "requested_at": value.requested_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _operation(model: AccountOperationModel) -> AccountOperation:
    try:
        return AccountOperation(
            id=model.id,
            user_id=model.user_id,
            user_fingerprint=model.user_fingerprint.hex(),
            capability_hash=model.capability_hash.hex(),
            kind=AccountOperationKind(model.kind),
            status=AccountOperationStatus(model.status),
            idempotency_key=model.idempotency_key,
            request_id=model.request_id,
            trace_id=model.trace_id,
            attempts=model.attempts,
            max_attempts=model.max_attempts,
            next_attempt_at=model.next_attempt_at,
            lease_token=model.lease_token,
            lease_expires_at=model.lease_expires_at,
            artifact_object_key=model.artifact_object_key,
            artifact_sha256=(
                model.artifact_sha256.hex() if model.artifact_sha256 is not None else None
            ),
            artifact_size_bytes=model.artifact_size_bytes,
            artifact_expires_at=model.artifact_expires_at,
            completed_at=model.completed_at,
            blocked_reason=model.blocked_reason,
            last_error_code=model.last_error_code,
            requested_at=model.requested_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError, IdentityConflict) as exc:
        raise IdentityUnavailable("stored account operation is invalid") from exc


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    constraint = getattr(getattr(exc, "orig", None), "constraint_name", None)
    if constraint == "uq_account_operations_user_kind_idempotency":
        raise IdentityConflict("account operation idempotency conflict") from exc
    raise IdentityUnavailable("account operation persistence failed safely") from exc
