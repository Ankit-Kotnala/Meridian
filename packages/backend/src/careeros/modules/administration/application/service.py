"""Least-privilege platform administration application service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from careeros.modules.administration.domain import (
    AdminAuditEvent,
    AdminCapability,
    AdministrationConflict,
    AdministrationDenied,
    AdministrationNotFound,
    AdministrationRecentAuthenticationRequired,
    AdministrationValidationError,
    OperatorAssignment,
)

from .models import (
    AdminAuditPage,
    AdminCatalogSnapshot,
    AdminDeadLetterPage,
    AdminPrincipal,
    AdminSystemSnapshot,
    RequestContext,
    RetryResult,
)
from .ports import (
    AdministrationUnitOfWork,
    AdministrationUnitOfWorkFactory,
    Clock,
    IdentifierFactory,
)


@dataclass(frozen=True, slots=True)
class AdministrationPolicy:
    recent_auth_seconds: int = 600
    maximum_page_size: int = 100

    def __post_init__(self) -> None:
        if not 60 <= self.recent_auth_seconds <= 3_600:
            raise ValueError("administration recent-auth window is invalid")
        if not 10 <= self.maximum_page_size <= 500:
            raise ValueError("administration page limit is invalid")


class AdministrationService:
    """Authorize every operation from persisted assignments and audit the decision."""

    def __init__(
        self,
        *,
        unit_of_work: AdministrationUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        policy: AdministrationPolicy | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._policy = policy or AdministrationPolicy()

    async def system_snapshot(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        reason: str,
    ) -> AdminSystemSnapshot:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow, principal, AdminCapability.SYSTEM_READ, context, reason, "system.read"
            )
            totals = await uow.get_system_totals()
            chain_valid = await uow.verify_audit_chain()
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.SYSTEM_READ,
                "system.read",
                "success",
                reason,
                context,
            )
            await uow.commit()
        return AdminSystemSnapshot(
            generated_at=now,
            totals=totals,
            audit_chain_valid=chain_valid,
        )

    async def catalog_snapshot(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        reason: str,
    ) -> AdminCatalogSnapshot:
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow, principal, AdminCapability.CATALOG_READ, context, reason, "catalog.read"
            )
            result = await uow.get_catalog_snapshot(now)
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.CATALOG_READ,
                "catalog.read",
                "success",
                reason,
                context,
            )
            await uow.commit()
            return result

    async def list_dead_letters(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        reason: str,
        cursor: str | None,
        limit: int,
    ) -> AdminDeadLetterPage:
        self._page_limit(limit)
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow, principal, AdminCapability.JOBS_READ, context, reason, "jobs.read"
            )
            result = await uow.list_dead_letters(cursor=cursor, limit=limit)
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.JOBS_READ,
                "jobs.read",
                "success",
                reason,
                context,
            )
            await uow.commit()
            return result

    async def retry_dead_letter(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        kind: str,
        target_id: UUID,
        reason: str,
        idempotency_key: str,
    ) -> RetryResult:
        _idempotency_key(idempotency_key)
        fingerprint = hashlib.sha256(f"{kind}:{target_id}:{reason}".encode()).hexdigest()
        operation = "dead_letter.retry"
        now = self._clock.now()
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow,
                principal,
                AdminCapability.JOBS_RETRY,
                context,
                reason,
                operation,
                target_kind=kind,
                target_id=target_id,
            )
            await self._require_recent_authentication(
                uow,
                principal,
                assignment,
                AdminCapability.JOBS_RETRY,
                operation,
                reason,
                context,
                target_kind=kind,
                target_id=target_id,
            )
            replay = await uow.get_idempotency(principal.user_id, operation, idempotency_key)
            if replay is not None:
                prior_fingerprint, prior_result = replay
                if prior_fingerprint != fingerprint:
                    await self._audit(
                        uow,
                        principal,
                        assignment,
                        AdminCapability.JOBS_RETRY,
                        operation,
                        "failed",
                        reason,
                        context,
                        target_kind=kind,
                        target_id=target_id,
                    )
                    await uow.commit()
                    raise AdministrationConflict(
                        "idempotency key was used for a different admin retry"
                    )
                await self._audit(
                    uow,
                    principal,
                    assignment,
                    AdminCapability.JOBS_RETRY,
                    operation,
                    "accepted",
                    reason,
                    context,
                    target_kind=kind,
                    target_id=target_id,
                )
                await uow.commit()
                return RetryResult(
                    kind=prior_result.kind,
                    id=prior_result.id,
                    status=prior_result.status,
                    replayed=True,
                )
            if kind not in {"account_privacy", "organization_invitation"}:
                await self._audit(
                    uow,
                    principal,
                    assignment,
                    AdminCapability.JOBS_RETRY,
                    operation,
                    "failed",
                    reason,
                    context,
                    target_kind=kind,
                    target_id=target_id,
                )
                await uow.commit()
                raise AdministrationValidationError("dead-letter kind is not retryable")
            if await uow.has_successful_retry(kind=kind, target_id=target_id):
                await self._audit(
                    uow,
                    principal,
                    assignment,
                    AdminCapability.JOBS_RETRY,
                    operation,
                    "denied",
                    reason,
                    context,
                    target_kind=kind,
                    target_id=target_id,
                )
                await uow.commit()
                raise AdministrationConflict(
                    "manual retry budget for this dead letter is exhausted"
                )
            result = await uow.retry_dead_letter(kind=kind, target_id=target_id, now=now)
            if result is None:
                await self._audit(
                    uow,
                    principal,
                    assignment,
                    AdminCapability.JOBS_RETRY,
                    operation,
                    "failed",
                    reason,
                    context,
                    target_kind=kind,
                    target_id=target_id,
                )
                await uow.commit()
                raise AdministrationNotFound("retryable dead letter was not found")
            await uow.add_idempotency(
                id=self._ids.new(),
                actor_user_id=principal.user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                result=result,
                created_at=now,
            )
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.JOBS_RETRY,
                operation,
                "success",
                reason,
                context,
                target_kind=kind,
                target_id=target_id,
            )
            await uow.commit()
            return result

    async def list_audit_events(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        reason: str,
        cursor: str | None,
        limit: int,
    ) -> AdminAuditPage:
        self._page_limit(limit)
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow, principal, AdminCapability.AUDIT_READ, context, reason, "audit.read"
            )
            result = await uow.list_audit_events(cursor=cursor, limit=limit)
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.AUDIT_READ,
                "audit.read",
                "success",
                reason,
                context,
            )
            await uow.commit()
            return result

    async def verify_audit_integrity(
        self,
        principal: AdminPrincipal,
        context: RequestContext,
        *,
        reason: str,
    ) -> bool:
        async with self._unit_of_work() as uow:
            assignment = await self._authorize(
                uow,
                principal,
                AdminCapability.AUDIT_VERIFY,
                context,
                reason,
                "audit.verify",
            )
            await self._require_recent_authentication(
                uow,
                principal,
                assignment,
                AdminCapability.AUDIT_VERIFY,
                "audit.verify",
                reason,
                context,
            )
            result = await uow.verify_audit_chain()
            await self._audit(
                uow,
                principal,
                assignment,
                AdminCapability.AUDIT_VERIFY,
                "audit.verify",
                "success" if result else "failed",
                reason,
                context,
            )
            await uow.commit()
            return result

    async def _authorize(
        self,
        uow: AdministrationUnitOfWork,
        principal: AdminPrincipal,
        capability: AdminCapability,
        context: RequestContext,
        reason: str,
        action: str,
        *,
        target_kind: str | None = None,
        target_id: UUID | None = None,
    ) -> OperatorAssignment:
        assignment = await uow.get_assignment(principal.user_id)
        if assignment is None or not assignment.allows(capability):
            await self._audit(
                uow,
                principal,
                assignment,
                capability,
                action,
                "denied",
                reason,
                context,
                target_kind=target_kind,
                target_id=target_id,
            )
            await uow.commit()
            raise AdministrationDenied("platform operator capability is required")
        return assignment

    async def _audit(
        self,
        uow: AdministrationUnitOfWork,
        principal: AdminPrincipal,
        assignment: OperatorAssignment | None,
        capability: AdminCapability,
        action: str,
        outcome: str,
        reason: str,
        context: RequestContext,
        *,
        target_kind: str | None = None,
        target_id: UUID | None = None,
    ) -> None:
        await uow.append_audit_event(
            AdminAuditEvent(
                id=self._ids.new(),
                actor_user_id=principal.user_id,
                actor_role=assignment.role if assignment is not None else None,
                capability=capability,
                action=action,
                outcome=outcome,
                reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
                occurred_at=self._clock.now(),
                target_kind=target_kind,
                target_id=target_id,
            )
        )

    async def _require_recent_authentication(
        self,
        uow: AdministrationUnitOfWork,
        principal: AdminPrincipal,
        assignment: OperatorAssignment,
        capability: AdminCapability,
        action: str,
        reason: str,
        context: RequestContext,
        *,
        target_kind: str | None = None,
        target_id: UUID | None = None,
    ) -> None:
        if principal.was_recently_authenticated(
            self._clock.now(), self._policy.recent_auth_seconds
        ):
            return
        await self._audit(
            uow,
            principal,
            assignment,
            capability,
            action,
            "denied",
            reason,
            context,
            target_kind=target_kind,
            target_id=target_id,
        )
        await uow.commit()
        raise AdministrationRecentAuthenticationRequired(
            "recent authentication is required for admin mutation"
        )

    def _page_limit(self, limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= self._policy.maximum_page_size:
            raise AdministrationValidationError("admin page limit is invalid")


def _idempotency_key(value: str) -> None:
    if not 8 <= len(value) <= 128 or any(
        character.isspace() or not character.isprintable() for character in value
    ):
        raise AdministrationValidationError("idempotency key is invalid")
