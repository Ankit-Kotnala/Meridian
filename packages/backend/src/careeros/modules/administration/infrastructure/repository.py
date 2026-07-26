"""PostgreSQL read model, safe retry adapter, and hash-chained admin audit."""

# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import TracebackType
from typing import NoReturn, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.administration.application.models import (
    AdminAuditPage,
    AdminCatalogSnapshot,
    AdminDeadLetter,
    AdminDeadLetterPage,
    AdminSystemTotals,
    RetryResult,
)
from careeros.modules.administration.application.ports import AdministrationUnitOfWork
from careeros.modules.administration.domain import (
    AdminAuditEvent,
    AdminCapability,
    AdministrationConflict,
    AdministrationUnavailable,
    AdministrationValidationError,
    AdminRole,
    OperatorAssignment,
)

from .models import (
    PlatformAdminAuditEventModel,
    PlatformAdminIdempotencyModel,
    PlatformOperatorAssignmentModel,
)

_AUDIT_LOCK_KEY = 4_214_902_110
_ZERO_HASH = "0" * 64
_RETRYABLE_KINDS = frozenset({"account_privacy", "organization_invitation"})

_DEAD_LETTERS_SQL = """
WITH dead_letters AS (
    SELECT 'account_privacy'::text AS kind, id, status,
           last_error_code AS safe_error_code, attempts, max_attempts,
           COALESCE(completed_at, created_at) AS occurred_at
      FROM account_operations
     WHERE status = 'dead_lettered'
    UNION ALL
    SELECT 'organization_invitation', invitation.id, invitation.status,
           outbox.last_error_code, outbox.attempts, outbox.max_attempts,
           COALESCE(outbox.dead_lettered_at, invitation.updated_at)
      FROM organization_invitations AS invitation
      JOIN LATERAL (
          SELECT last_error_code, attempts, max_attempts, dead_lettered_at
            FROM organization_invitation_outbox
           WHERE invitation_id = invitation.id AND dead_lettered_at IS NOT NULL
           ORDER BY created_at DESC, id DESC
           LIMIT 1
      ) AS outbox ON TRUE
     WHERE invitation.status = 'delivery_dead_lettered'
    UNION ALL
    SELECT 'resume_processing', id, status, safe_error_code, attempts, max_attempts,
           COALESCE(dead_lettered_at, created_at)
      FROM resume_processing_jobs
     WHERE status = 'dead_lettered'
    UNION ALL
    SELECT 'evidence_attachment', id, status, safe_error_code, attempts, max_attempts,
           COALESCE(dead_lettered_at, created_at)
      FROM evidence_attachment_processing_jobs
     WHERE status = 'dead_lettered'
    UNION ALL
    SELECT 'resume_export', id, status, 'resume_export_failed', attempts, max_attempts,
           COALESCE(dead_lettered_at, requested_at)
      FROM resume_exports
     WHERE status IN ('dead_lettered', 'deletion_dead_lettered')
    UNION ALL
    SELECT 'career_analytics', id, status, safe_error_code, attempts, max_attempts,
           updated_at
      FROM career_analytics_refresh_jobs
     WHERE status = 'dead_letter'
    UNION ALL
    SELECT 'networking_reminder', id, status, last_error_code,
           attempt_count, max_attempts, updated_at
      FROM networking_reminder_outbox
     WHERE status = 'dead_letter'
)
SELECT kind, id, status, safe_error_code, attempts, max_attempts, occurred_at
  FROM dead_letters
 ORDER BY occurred_at DESC, kind ASC, id ASC
 OFFSET :offset
 LIMIT :limit
"""


class SqlAlchemyAdministrationUnitOfWork:
    """One transaction per authorized administration use case."""

    def __init__(self, database: Database, audit_pepper: str) -> None:
        self._session_context = database.session()
        self._audit_pepper = audit_pepper.encode()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyAdministrationUnitOfWork:
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
            raise RuntimeError("administration unit of work is not active")
        return self._session

    async def get_assignment(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OperatorAssignment | None:
        statement = select(PlatformOperatorAssignmentModel).where(
            PlatformOperatorAssignmentModel.user_id == user_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _assignment(model) if model is not None else None

    async def append_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_LOCK_KEY}
        )
        previous = await self.session.scalar(
            select(PlatformAdminAuditEventModel)
            .order_by(PlatformAdminAuditEventModel.sequence.desc())
            .limit(1)
        )
        previous_hash = previous.event_hash if previous is not None else _ZERO_HASH
        sequence = (previous.sequence + 1) if previous is not None else 1
        actor_reference = _actor_reference(self._audit_pepper, event.actor_user_id)
        event_hash = _event_hash(
            event,
            sequence=sequence,
            previous_hash=previous_hash,
            actor_reference=actor_reference,
        )
        model = PlatformAdminAuditEventModel(
            id=event.id,
            sequence=sequence,
            actor_user_id=event.actor_user_id,
            actor_reference=actor_reference,
            actor_role=event.actor_role.value if event.actor_role is not None else None,
            capability=event.capability.value,
            action=event.action,
            outcome=event.outcome,
            reason=event.reason.strip(),
            target_kind=event.target_kind,
            target_id=event.target_id,
            request_id=event.request_id,
            trace_id=event.trace_id,
            previous_hash=previous_hash,
            event_hash=event_hash,
            occurred_at=event.occurred_at,
        )
        self.session.add(model)
        return _audit_event(model)

    async def verify_audit_chain(self) -> bool:
        models = (
            await self.session.scalars(
                select(PlatformAdminAuditEventModel).order_by(PlatformAdminAuditEventModel.sequence)
            )
        ).all()
        expected_previous = _ZERO_HASH
        expected_sequence = 1
        for model in models:
            event = _audit_event(model)
            if model.sequence != expected_sequence or model.previous_hash != expected_previous:
                return False
            if (
                _event_hash(
                    event,
                    sequence=model.sequence,
                    previous_hash=model.previous_hash,
                    actor_reference=model.actor_reference,
                )
                != model.event_hash
            ):
                return False
            expected_previous = model.event_hash
            expected_sequence += 1
        return True

    async def get_system_totals(self) -> AdminSystemTotals:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM users WHERE status = 'active') AS users_active,
                      (SELECT count(*) FROM users WHERE status = 'disabled') AS users_disabled,
                      (SELECT count(*) FROM organizations WHERE status = 'active') AS organizations_active,
                      (SELECT count(*) FROM commercial_subscriptions WHERE status = 'active') AS subscriptions_active,
                      (
                        (SELECT count(*) FROM account_operations WHERE status = 'queued') +
                        (SELECT count(*) FROM resume_processing_jobs WHERE status = 'queued') +
                        (SELECT count(*) FROM evidence_attachment_processing_jobs WHERE status = 'queued') +
                        (SELECT count(*) FROM career_analytics_refresh_jobs WHERE status = 'queued')
                      ) AS queued_jobs,
                      (
                        (SELECT count(*) FROM account_operations WHERE status = 'retry_wait') +
                        (SELECT count(*) FROM resume_processing_jobs WHERE status = 'failed') +
                        (SELECT count(*) FROM evidence_attachment_processing_jobs WHERE status = 'retry_wait') +
                        (SELECT count(*) FROM career_analytics_refresh_jobs WHERE status = 'retry_wait')
                      ) AS retry_wait_jobs,
                      (
                        (SELECT count(*) FROM account_operations WHERE status = 'running') +
                        (SELECT count(*) FROM resume_processing_jobs WHERE status = 'running') +
                        (SELECT count(*) FROM evidence_attachment_processing_jobs WHERE status = 'running') +
                        (SELECT count(*) FROM career_analytics_refresh_jobs WHERE status = 'running')
                      ) AS running_jobs,
                      (
                        (SELECT count(*) FROM account_operations WHERE status = 'dead_lettered') +
                        (SELECT count(*) FROM organization_invitations WHERE status = 'delivery_dead_lettered') +
                        (SELECT count(*) FROM resume_processing_jobs WHERE status = 'dead_lettered') +
                        (SELECT count(*) FROM evidence_attachment_processing_jobs WHERE status = 'dead_lettered') +
                        (SELECT count(*) FROM resume_exports WHERE status IN ('dead_lettered','deletion_dead_lettered')) +
                        (SELECT count(*) FROM career_analytics_refresh_jobs WHERE status = 'dead_letter') +
                        (SELECT count(*) FROM networking_reminder_outbox WHERE status = 'dead_letter')
                      ) AS dead_letter_jobs
                    """
                )
            )
        ).one()
        return AdminSystemTotals(**{key: int(row._mapping[key]) for key in row._mapping})

    async def get_catalog_snapshot(self, now: datetime) -> AdminCatalogSnapshot:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      count(*) FILTER (WHERE configuration_status = 'configured') AS configured_plans,
                      count(*) FILTER (WHERE configuration_status = 'owner_decision_required')
                        AS owner_decision_required_plans
                    FROM commercial_plans
                    """
                )
            )
        ).one()
        flags = tuple(
            str(value)
            for value in (
                await self.session.scalars(
                    text(
                        "SELECT key FROM platform_feature_flags "
                        "WHERE state = 'enabled' ORDER BY key"
                    )
                )
            ).all()
        )
        taxonomy_versions = int(
            await self.session.scalar(text("SELECT count(*) FROM role_taxonomy_versions")) or 0
        )
        active_roles = int(
            await self.session.scalar(
                text(
                    "SELECT count(*) FROM role_definitions AS role "
                    "JOIN role_taxonomy_versions AS taxonomy "
                    "ON taxonomy.id = role.taxonomy_version_id "
                    "WHERE taxonomy.active IS TRUE"
                )
            )
            or 0
        )
        return AdminCatalogSnapshot(
            generated_at=now,
            configured_plans=int(row.configured_plans),
            owner_decision_required_plans=int(row.owner_decision_required_plans),
            enabled_feature_flags=flags,
            role_taxonomy_versions=taxonomy_versions,
            active_role_definitions=active_roles,
            resume_template_keys=(
                "compact_technical",
                "consulting_finance",
                "executive",
                "graduate",
                "standard_professional",
            ),
        )

    async def list_dead_letters(self, *, cursor: str | None, limit: int) -> AdminDeadLetterPage:
        offset = _decode_cursor(cursor)
        rows = (
            await self.session.execute(
                text(_DEAD_LETTERS_SQL), {"offset": offset, "limit": limit + 1}
            )
        ).all()
        has_more = len(rows) > limit
        items = tuple(
            AdminDeadLetter(
                kind=str(row.kind),
                id=cast(UUID, row.id),
                status=str(row.status),
                safe_error_code=(
                    str(row.safe_error_code) if row.safe_error_code is not None else None
                ),
                attempts=int(row.attempts),
                max_attempts=int(row.max_attempts),
                occurred_at=cast(datetime, row.occurred_at),
                retry_supported=str(row.kind) in _RETRYABLE_KINDS,
            )
            for row in rows[:limit]
        )
        return AdminDeadLetterPage(
            items=items,
            next_cursor=_encode_cursor(offset + limit) if has_more else None,
        )

    async def list_audit_events(self, *, cursor: str | None, limit: int) -> AdminAuditPage:
        before = _decode_cursor(cursor) if cursor is not None else None
        statement = select(PlatformAdminAuditEventModel)
        if before is not None:
            statement = statement.where(PlatformAdminAuditEventModel.sequence < before)
        models = (
            await self.session.scalars(
                statement.order_by(PlatformAdminAuditEventModel.sequence.desc()).limit(limit + 1)
            )
        ).all()
        has_more = len(models) > limit
        items = tuple(_audit_event(model) for model in models[:limit])
        return AdminAuditPage(
            items=items,
            next_cursor=(
                _encode_cursor(models[limit - 1].sequence) if has_more and items else None
            ),
        )

    async def get_idempotency(
        self, actor_user_id: UUID, operation: str, idempotency_key: str
    ) -> tuple[str, RetryResult] | None:
        model = await self.session.scalar(
            select(PlatformAdminIdempotencyModel).where(
                PlatformAdminIdempotencyModel.actor_user_id == actor_user_id,
                PlatformAdminIdempotencyModel.operation == operation,
                PlatformAdminIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        if model is None:
            return None
        payload = model.response_payload
        return (
            model.request_fingerprint,
            RetryResult(
                kind=str(payload["kind"]),
                id=UUID(str(payload["id"])),
                status=str(payload["status"]),
                replayed=True,
            ),
        )

    async def add_idempotency(
        self,
        *,
        id: UUID,
        actor_user_id: UUID,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        result: RetryResult,
        created_at: datetime,
    ) -> None:
        self.session.add(
            PlatformAdminIdempotencyModel(
                id=id,
                actor_user_id=actor_user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                response_payload={
                    "kind": result.kind,
                    "id": str(result.id),
                    "status": result.status,
                },
                created_at=created_at,
            )
        )

    async def retry_dead_letter(
        self, *, kind: str, target_id: UUID, now: datetime
    ) -> RetryResult | None:
        if kind == "account_privacy":
            row = (
                await self.session.execute(
                    text(
                        """
                        UPDATE account_operations
                           SET status = 'retry_wait',
                               attempts = GREATEST(attempts - 1, 0),
                               next_attempt_at = :now,
                               lease_token = NULL,
                               lease_expires_at = NULL,
                               completed_at = NULL,
                               last_error_code = NULL
                         WHERE id = :id AND status = 'dead_lettered'
                     RETURNING id, status
                        """
                    ),
                    {"id": target_id, "now": now},
                )
            ).first()
        elif kind == "organization_invitation":
            row = (
                await self.session.execute(
                    text(
                        """
                        WITH candidate AS (
                            SELECT id
                              FROM organization_invitation_outbox
                             WHERE invitation_id = :id AND dead_lettered_at IS NOT NULL
                             ORDER BY created_at DESC, id DESC
                             LIMIT 1
                             FOR UPDATE
                        ), rearmed AS (
                            UPDATE organization_invitation_outbox AS outbox
                               SET attempts = GREATEST(outbox.attempts - 1, 0),
                                   next_attempt_at = :now,
                                   lease_token = NULL,
                                   lease_expires_at = NULL,
                                   dead_lettered_at = NULL,
                                   last_error_code = NULL
                              FROM candidate
                             WHERE outbox.id = candidate.id
                         RETURNING outbox.invitation_id
                        )
                        UPDATE organization_invitations AS invitation
                           SET status = 'pending_delivery',
                               updated_at = :now,
                               version = version + 1
                          FROM rearmed
                         WHERE invitation.id = rearmed.invitation_id
                           AND invitation.status = 'delivery_dead_lettered'
                     RETURNING invitation.id, invitation.status
                        """
                    ),
                    {"id": target_id, "now": now},
                )
            ).first()
        else:
            raise AdministrationValidationError("dead-letter kind is not retryable")
        if row is None:
            return None
        return RetryResult(
            kind=kind,
            id=cast(UUID, row.id),
            status=str(row.status),
            replayed=False,
        )

    async def has_successful_retry(self, *, kind: str, target_id: UUID) -> bool:
        return (
            int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(PlatformAdminAuditEventModel)
                    .where(
                        PlatformAdminAuditEventModel.action == "dead_letter.retry",
                        PlatformAdminAuditEventModel.outcome == "success",
                        PlatformAdminAuditEventModel.target_kind == kind,
                        PlatformAdminAuditEventModel.target_id == target_id,
                    )
                )
                or 0
            )
            > 0
        )

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AdministrationConflict("administration state changed concurrently") from exc
        except Exception as exc:
            await self.session.rollback()
            _unavailable(exc)
        self._committed = True


class SqlAlchemyAdministrationUnitOfWorkFactory:
    def __init__(self, database: Database, audit_pepper: str) -> None:
        self._database = database
        self._audit_pepper = audit_pepper

    def __call__(self) -> AdministrationUnitOfWork:
        return SqlAlchemyAdministrationUnitOfWork(self._database, self._audit_pepper)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidIdentifierFactory:
    def new(self) -> UUID:
        return uuid4()


async def grant_operator_offline(
    *,
    database: Database,
    user_id: UUID,
    role: AdminRole,
    reason: str,
    granted_by_user_id: UUID | None,
    now: datetime,
) -> None:
    assignment = OperatorAssignment(
        user_id=user_id,
        role=role,
        granted_at=now,
        grant_reason=reason,
        granted_by_user_id=granted_by_user_id,
    )
    async with database.session() as session:
        existing = await session.get(PlatformOperatorAssignmentModel, user_id)
        if existing is not None and existing.revoked_at is None:
            raise AdministrationConflict("operator assignment is already active")
        if existing is None:
            session.add(
                PlatformOperatorAssignmentModel(
                    user_id=assignment.user_id,
                    role=assignment.role.value,
                    granted_by_user_id=assignment.granted_by_user_id,
                    grant_reason=assignment.grant_reason.strip(),
                    granted_at=assignment.granted_at,
                )
            )
        else:
            existing.role = assignment.role.value
            existing.granted_by_user_id = assignment.granted_by_user_id
            existing.grant_reason = assignment.grant_reason.strip()
            existing.granted_at = assignment.granted_at
            existing.revoked_by_user_id = None
            existing.revoke_reason = None
            existing.revoked_at = None
        await session.commit()


async def revoke_operator_offline(
    *,
    database: Database,
    user_id: UUID,
    reason: str,
    revoked_by_user_id: UUID | None,
    now: datetime,
) -> None:
    OperatorAssignment(
        user_id=user_id,
        role=AdminRole.OPERATIONS_VIEWER,
        granted_at=now,
        grant_reason="Validation-only placeholder reason.",
        revoked_at=now,
        revoked_by_user_id=revoked_by_user_id,
        revoke_reason=reason,
    )
    async with database.session() as session:
        model = await session.get(PlatformOperatorAssignmentModel, user_id, with_for_update=True)
        if model is None or model.revoked_at is not None:
            raise AdministrationConflict("active operator assignment was not found")
        model.revoked_by_user_id = revoked_by_user_id
        model.revoke_reason = reason.strip()
        model.revoked_at = now
        await session.commit()


def _assignment(model: PlatformOperatorAssignmentModel) -> OperatorAssignment:
    return OperatorAssignment(
        user_id=model.user_id,
        role=AdminRole(model.role),
        granted_at=model.granted_at,
        grant_reason=model.grant_reason,
        granted_by_user_id=model.granted_by_user_id,
        revoked_at=model.revoked_at,
        revoked_by_user_id=model.revoked_by_user_id,
        revoke_reason=model.revoke_reason,
    )


def _audit_event(model: PlatformAdminAuditEventModel) -> AdminAuditEvent:
    return AdminAuditEvent(
        id=model.id,
        sequence=model.sequence,
        actor_user_id=model.actor_user_id,
        actor_reference=model.actor_reference,
        actor_role=AdminRole(model.actor_role) if model.actor_role is not None else None,
        capability=AdminCapability(model.capability),
        action=model.action,
        outcome=model.outcome,
        reason=model.reason,
        target_kind=model.target_kind,
        target_id=model.target_id,
        request_id=model.request_id,
        trace_id=model.trace_id,
        previous_hash=model.previous_hash,
        event_hash=model.event_hash,
        occurred_at=model.occurred_at,
    )


def _event_hash(
    event: AdminAuditEvent,
    *,
    sequence: int,
    previous_hash: str,
    actor_reference: str,
) -> str:
    payload = {
        "action": event.action,
        "actor_role": event.actor_role.value if event.actor_role is not None else None,
        "actor_reference": actor_reference,
        "capability": event.capability.value,
        "id": str(event.id),
        "occurred_at": event.occurred_at.isoformat(),
        "outcome": event.outcome,
        "previous_hash": previous_hash,
        "reason": event.reason.strip(),
        "request_id": event.request_id,
        "sequence": sequence,
        "target_id": str(event.target_id) if event.target_id is not None else None,
        "target_kind": event.target_kind,
        "trace_id": event.trace_id,
    }
    canonical = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _actor_reference(pepper: bytes, actor_user_id: UUID | None) -> str:
    if actor_user_id is None:
        raise AdministrationValidationError("new audit event requires an actor")
    return hmac.new(
        pepper,
        b"careeros:platform-admin-audit:actor:v1:" + actor_user_id.bytes,
        hashlib.sha256,
    ).hexdigest()


def _encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")


def _decode_cursor(value: str | None) -> int:
    if value is None:
        return 0
    try:
        padded = value + ("=" * (-len(value) % 4))
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
        result = int(decoded)
    except (ValueError, UnicodeError) as exc:
        raise AdministrationValidationError("admin cursor is invalid") from exc
    if not 0 <= result <= 10_000_000:
        raise AdministrationValidationError("admin cursor is invalid")
    return result


def _unavailable(exc: Exception) -> NoReturn:
    raise AdministrationUnavailable from exc
