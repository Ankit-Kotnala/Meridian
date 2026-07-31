"""Least-privilege administration authorization and replay tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from careeros.modules.administration.application import (
    AdminAuditPage,
    AdminCatalogSnapshot,
    AdminDeadLetterPage,
    AdministrationService,
    AdminSystemTotals,
    RequestContext,
    RetryResult,
)
from careeros.modules.administration.domain import (
    AdminAuditEvent,
    AdministrationDenied,
    AdministrationRecentAuthenticationRequired,
    AdminRole,
    OperatorAssignment,
)
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod

NOW = datetime(2026, 7, 27, 8, tzinfo=UTC)
REASON = "Investigating fictional release health for an approved test."


@dataclass(slots=True)
class Clock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


class Identifiers:
    def new(self) -> UUID:
        return uuid4()


class MemoryAdministration:
    def __init__(self, assignment: OperatorAssignment | None) -> None:
        self.assignment = assignment
        self.audits: list[AdminAuditEvent] = []
        self.idempotency: dict[tuple[UUID, str, str], tuple[str, RetryResult]] = {}
        self.retried: set[tuple[str, UUID]] = set()
        self.commits = 0

    def __call__(self) -> MemoryAdministration:
        return self

    async def __aenter__(self) -> MemoryAdministration:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get_assignment(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OperatorAssignment | None:
        del for_update
        if self.assignment is not None and self.assignment.user_id == user_id:
            return self.assignment
        return None

    async def append_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        stored = replace(
            event,
            sequence=len(self.audits) + 1,
            actor_reference="a" * 64,
            previous_hash="0" * 64,
            event_hash="b" * 64,
        )
        self.audits.append(stored)
        return stored

    async def verify_audit_chain(self) -> bool:
        return True

    async def get_system_totals(self) -> AdminSystemTotals:
        return AdminSystemTotals(1, 0, 0, 0, 0, 0, 0, 0)

    async def get_catalog_snapshot(self, now: datetime) -> AdminCatalogSnapshot:
        return AdminCatalogSnapshot(now, 0, 4, (), 1, 2, ("standard_professional",))

    async def list_dead_letters(self, *, cursor: str | None, limit: int) -> AdminDeadLetterPage:
        del cursor, limit
        return AdminDeadLetterPage((), None)

    async def list_audit_events(self, *, cursor: str | None, limit: int) -> AdminAuditPage:
        del cursor, limit
        return AdminAuditPage(tuple(self.audits), None)

    async def get_idempotency(
        self, actor_user_id: UUID, operation: str, idempotency_key: str
    ) -> tuple[str, RetryResult] | None:
        return self.idempotency.get((actor_user_id, operation, idempotency_key))

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
        del id, created_at
        self.idempotency[(actor_user_id, operation, idempotency_key)] = (
            request_fingerprint,
            result,
        )

    async def retry_dead_letter(
        self, *, kind: str, target_id: UUID, now: datetime
    ) -> RetryResult | None:
        del now
        self.retried.add((kind, target_id))
        return RetryResult(kind, target_id, "retry_wait", False)

    async def has_successful_retry(self, *, kind: str, target_id: UUID) -> bool:
        return (kind, target_id) in self.retried

    async def commit(self) -> None:
        self.commits += 1


def _principal(
    user_id: UUID | None = None, *, authenticated_at: datetime = NOW
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id or uuid4(),
        session_id=uuid4(),
        authenticated_at=authenticated_at,
        auth_method=AuthMethod.PASSWORD,
    )


def _context() -> RequestContext:
    return RequestContext(request_id="admin-test-request", trace_id="a" * 32)


def _assignment(user_id: UUID, role: AdminRole) -> OperatorAssignment:
    return OperatorAssignment(
        user_id=user_id,
        role=role,
        granted_at=NOW,
        grant_reason="Approved fictional operator fixture for unit testing.",
    )


@pytest.mark.asyncio
async def test_missing_operator_authority_is_denied_and_audited() -> None:
    principal = _principal()
    state = MemoryAdministration(None)
    service = AdministrationService(
        unit_of_work=state,
        clock=Clock(),
        identifiers=Identifiers(),
    )

    with pytest.raises(AdministrationDenied):
        await service.system_snapshot(principal, _context(), reason=REASON)

    assert state.commits == 1
    assert [(event.action, event.outcome) for event in state.audits] == [("system.read", "denied")]


@pytest.mark.asyncio
async def test_recent_authentication_failure_is_denied_and_audited() -> None:
    principal = _principal(authenticated_at=NOW - timedelta(hours=1))
    state = MemoryAdministration(_assignment(principal.user_id, AdminRole.JOB_OPERATOR))
    service = AdministrationService(
        unit_of_work=state,
        clock=Clock(),
        identifiers=Identifiers(),
    )

    with pytest.raises(AdministrationRecentAuthenticationRequired):
        await service.retry_dead_letter(
            principal,
            _context(),
            kind="account_privacy",
            target_id=uuid4(),
            reason=REASON,
            idempotency_key="fictional-admin-retry",
        )

    assert state.commits == 1
    assert state.audits[-1].outcome == "denied"
    assert not state.retried


@pytest.mark.asyncio
async def test_manual_retry_is_one_shot_and_idempotent() -> None:
    principal = _principal()
    state = MemoryAdministration(_assignment(principal.user_id, AdminRole.JOB_OPERATOR))
    service = AdministrationService(
        unit_of_work=state,
        clock=Clock(),
        identifiers=Identifiers(),
    )
    target_id = uuid4()

    first = await service.retry_dead_letter(
        principal,
        _context(),
        kind="account_privacy",
        target_id=target_id,
        reason=REASON,
        idempotency_key="fictional-admin-retry",
    )
    replay = await service.retry_dead_letter(
        principal,
        _context(),
        kind="account_privacy",
        target_id=target_id,
        reason=REASON,
        idempotency_key="fictional-admin-retry",
    )

    assert first.status == "retry_wait"
    assert replay.replayed
    assert state.retried == {("account_privacy", target_id)}
    assert [event.outcome for event in state.audits] == ["success", "accepted"]
