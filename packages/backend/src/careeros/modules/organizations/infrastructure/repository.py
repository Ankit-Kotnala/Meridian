"""Async SQLAlchemy unit of work for organization tenancy."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, NoReturn, cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.organizations.application.ports import (
    OrganizationUnitOfWork,
)
from careeros.modules.organizations.domain import (
    GrantPurpose,
    GrantScope,
    GrantStatus,
    InvitationStatus,
    Organization,
    OrganizationAccessGrant,
    OrganizationAuditEvent,
    OrganizationConflict,
    OrganizationIdempotencyRecord,
    OrganizationInvitation,
    OrganizationInvitationOutbox,
    OrganizationMembership,
    OrganizationMembershipStatus,
    OrganizationRole,
    OrganizationStatus,
    OrganizationUnavailable,
    OrganizationValidationError,
    OrganizationVersionConflict,
)

from .models import (
    OrganizationAccessGrantModel,
    OrganizationAuditEventModel,
    OrganizationIdempotencyModel,
    OrganizationInvitationModel,
    OrganizationInvitationOutboxModel,
    OrganizationMembershipModel,
    OrganizationModel,
)


class SqlAlchemyOrganizationUnitOfWork:
    """One transaction per organization use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyOrganizationUnitOfWork:
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
            raise RuntimeError("organization unit of work is not active")
        return self._session

    async def count_owned_organizations(self, user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(OrganizationMembershipModel)
                .where(
                    OrganizationMembershipModel.user_id == user_id,
                    OrganizationMembershipModel.role == OrganizationRole.OWNER.value,
                    OrganizationMembershipModel.status == OrganizationMembershipStatus.ACTIVE.value,
                )
            )
            or 0
        )

    async def add_organization(self, organization: Organization) -> None:
        self.session.add(OrganizationModel(**_organization_values(organization)))

    async def get_organization(
        self,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> Organization | None:
        statement = select(OrganizationModel).where(OrganizationModel.id == organization_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _organization(model) if model is not None else None

    async def save_organization(
        self,
        organization: Organization,
        *,
        expected_version: int,
    ) -> None:
        result = await self.session.execute(
            update(OrganizationModel)
            .where(
                OrganizationModel.id == organization.id,
                OrganizationModel.version == expected_version,
            )
            .values(**_organization_values(organization, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise OrganizationVersionConflict

    async def list_organizations_for_user(self, user_id: UUID) -> list[Organization]:
        models = (
            await self.session.scalars(
                select(OrganizationModel)
                .join(
                    OrganizationMembershipModel,
                    OrganizationMembershipModel.organization_id == OrganizationModel.id,
                )
                .where(
                    OrganizationMembershipModel.user_id == user_id,
                    OrganizationMembershipModel.status == OrganizationMembershipStatus.ACTIVE.value,
                    OrganizationModel.status == OrganizationStatus.ACTIVE.value,
                )
                .order_by(OrganizationModel.updated_at.desc(), OrganizationModel.id)
                .limit(100)
            )
        ).all()
        return [_organization(model) for model in models]

    async def add_membership(self, membership: OrganizationMembership) -> None:
        self.session.add(OrganizationMembershipModel(**_membership_values(membership)))

    async def get_membership(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationMembership | None:
        statement = select(OrganizationMembershipModel).where(
            OrganizationMembershipModel.organization_id == organization_id,
            OrganizationMembershipModel.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _membership(model) if model is not None else None

    async def save_membership(
        self,
        membership: OrganizationMembership,
        *,
        expected_version: int,
    ) -> None:
        result = await self.session.execute(
            update(OrganizationMembershipModel)
            .where(
                OrganizationMembershipModel.id == membership.id,
                OrganizationMembershipModel.organization_id == membership.organization_id,
                OrganizationMembershipModel.version == expected_version,
            )
            .values(**_membership_values(membership, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise OrganizationVersionConflict

    async def list_memberships(
        self,
        organization_id: UUID,
    ) -> list[OrganizationMembership]:
        models = (
            await self.session.scalars(
                select(OrganizationMembershipModel)
                .where(
                    OrganizationMembershipModel.organization_id == organization_id,
                    OrganizationMembershipModel.status != OrganizationMembershipStatus.LEFT.value,
                )
                .order_by(
                    OrganizationMembershipModel.role,
                    OrganizationMembershipModel.created_at,
                    OrganizationMembershipModel.id,
                )
                .limit(250)
            )
        ).all()
        return [_membership(model) for model in models]

    async def count_active_members(self, organization_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(OrganizationMembershipModel)
                .where(
                    OrganizationMembershipModel.organization_id == organization_id,
                    OrganizationMembershipModel.status == OrganizationMembershipStatus.ACTIVE.value,
                )
            )
            or 0
        )

    async def get_invitation(
        self,
        invitation_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitationModel).where(
            OrganizationInvitationModel.id == invitation_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _invitation(model) if model is not None else None

    async def find_open_invitation(
        self,
        organization_id: UUID,
        email_digest: str,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitationModel).where(
            OrganizationInvitationModel.organization_id == organization_id,
            OrganizationInvitationModel.invited_email_digest == bytes.fromhex(email_digest),
            OrganizationInvitationModel.status.in_(
                (
                    InvitationStatus.PENDING_DELIVERY.value,
                    InvitationStatus.PENDING.value,
                    InvitationStatus.DELIVERY_DEAD_LETTERED.value,
                )
            ),
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _invitation(model) if model is not None else None

    async def add_invitation(self, invitation: OrganizationInvitation) -> None:
        self.session.add(OrganizationInvitationModel(**_invitation_values(invitation)))

    async def save_invitation(
        self,
        invitation: OrganizationInvitation,
        *,
        expected_version: int,
    ) -> None:
        result = await self.session.execute(
            update(OrganizationInvitationModel)
            .where(
                OrganizationInvitationModel.id == invitation.id,
                OrganizationInvitationModel.organization_id == invitation.organization_id,
                OrganizationInvitationModel.version == expected_version,
            )
            .values(**_invitation_values(invitation, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise OrganizationVersionConflict

    async def add_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
    ) -> None:
        self.session.add(OrganizationInvitationOutboxModel(**_outbox_values(outbox)))

    async def claim_invitation_outbox(
        self,
        *,
        limit: int,
        lease_token: UUID,
        now: datetime,
        lease_seconds: int,
    ) -> list[OrganizationInvitationOutbox]:
        models = (
            await self.session.scalars(
                select(OrganizationInvitationOutboxModel)
                .where(
                    OrganizationInvitationOutboxModel.published_at.is_(None),
                    OrganizationInvitationOutboxModel.dead_lettered_at.is_(None),
                    OrganizationInvitationOutboxModel.cancelled_at.is_(None),
                    OrganizationInvitationOutboxModel.next_attempt_at <= now,
                    or_(
                        OrganizationInvitationOutboxModel.lease_token.is_(None),
                        OrganizationInvitationOutboxModel.lease_expires_at <= now,
                    ),
                )
                .order_by(
                    OrganizationInvitationOutboxModel.next_attempt_at,
                    OrganizationInvitationOutboxModel.created_at,
                    OrganizationInvitationOutboxModel.id,
                )
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        claimed: list[OrganizationInvitationOutbox] = []
        for model in models:
            outbox = _outbox(model)
            outbox.claim(lease_token, now, lease_seconds)
            model.lease_token = outbox.lease_token
            model.lease_expires_at = outbox.lease_expires_at
            claimed.append(outbox)
        await self.flush()
        return claimed

    async def get_invitation_outbox(
        self,
        outbox_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationInvitationOutbox | None:
        statement = select(OrganizationInvitationOutboxModel).where(
            OrganizationInvitationOutboxModel.id == outbox_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _outbox(model) if model is not None else None

    async def save_invitation_outbox(
        self,
        outbox: OrganizationInvitationOutbox,
        *,
        expected_lease_token: UUID,
    ) -> None:
        result = await self.session.execute(
            update(OrganizationInvitationOutboxModel)
            .where(
                OrganizationInvitationOutboxModel.id == outbox.id,
                OrganizationInvitationOutboxModel.lease_token == expected_lease_token,
            )
            .values(**_outbox_values(outbox, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise OrganizationVersionConflict

    async def add_grant(self, grant: OrganizationAccessGrant) -> None:
        self.session.add(OrganizationAccessGrantModel(**_grant_values(grant)))

    async def get_grant(
        self,
        organization_id: UUID,
        grant_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None:
        statement = select(OrganizationAccessGrantModel).where(
            OrganizationAccessGrantModel.organization_id == organization_id,
            OrganizationAccessGrantModel.id == grant_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _grant(model) if model is not None else None

    async def find_active_grant(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
        grantee_user_id: UUID,
        scope: GrantScope,
        *,
        for_update: bool = False,
    ) -> OrganizationAccessGrant | None:
        statement = select(OrganizationAccessGrantModel).where(
            OrganizationAccessGrantModel.organization_id == organization_id,
            OrganizationAccessGrantModel.subject_user_id == subject_user_id,
            OrganizationAccessGrantModel.grantee_user_id == grantee_user_id,
            OrganizationAccessGrantModel.scope == scope.value,
            OrganizationAccessGrantModel.status == GrantStatus.ACTIVE.value,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _grant(model) if model is not None else None

    async def list_grants_for_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[OrganizationAccessGrant]:
        models = (
            await self.session.scalars(
                select(OrganizationAccessGrantModel)
                .where(
                    OrganizationAccessGrantModel.organization_id == organization_id,
                    or_(
                        OrganizationAccessGrantModel.subject_user_id == user_id,
                        OrganizationAccessGrantModel.grantee_user_id == user_id,
                    ),
                )
                .order_by(
                    OrganizationAccessGrantModel.updated_at.desc(),
                    OrganizationAccessGrantModel.id,
                )
                .limit(200)
            )
        ).all()
        return [_grant(model) for model in models]

    async def count_active_grants(
        self,
        organization_id: UUID,
        subject_user_id: UUID,
    ) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(OrganizationAccessGrantModel)
                .where(
                    OrganizationAccessGrantModel.organization_id == organization_id,
                    OrganizationAccessGrantModel.subject_user_id == subject_user_id,
                    OrganizationAccessGrantModel.status == GrantStatus.ACTIVE.value,
                )
            )
            or 0
        )

    async def save_grant(
        self,
        grant: OrganizationAccessGrant,
        *,
        expected_version: int,
    ) -> None:
        result = await self.session.execute(
            update(OrganizationAccessGrantModel)
            .where(
                OrganizationAccessGrantModel.id == grant.id,
                OrganizationAccessGrantModel.organization_id == grant.organization_id,
                OrganizationAccessGrantModel.version == expected_version,
            )
            .values(**_grant_values(grant, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise OrganizationVersionConflict

    async def get_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> OrganizationIdempotencyRecord | None:
        model = await self.session.scalar(
            select(OrganizationIdempotencyModel).where(
                OrganizationIdempotencyModel.actor_user_id == actor_user_id,
                OrganizationIdempotencyModel.operation == operation,
                OrganizationIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_idempotency(
        self,
        record: OrganizationIdempotencyRecord,
    ) -> None:
        self.session.add(
            OrganizationIdempotencyModel(
                id=record.id,
                actor_user_id=record.actor_user_id,
                operation=record.operation,
                idempotency_key=record.idempotency_key,
                request_fingerprint=bytes.fromhex(record.request_fingerprint),
                resource_id=record.resource_id,
                created_at=record.created_at,
            )
        )

    async def add_audit(self, event: OrganizationAuditEvent) -> None:
        self.session.add(
            OrganizationAuditEventModel(
                id=event.id,
                organization_id=event.organization_id,
                actor_user_id=event.actor_user_id,
                subject_user_id=event.subject_user_id,
                action=event.action.value,
                target_type=event.target_type,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                event_metadata=dict(event.metadata),
                occurred_at=event.occurred_at,
            )
        )

    async def flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True


class SqlAlchemyOrganizationUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> OrganizationUnitOfWork:
        return SqlAlchemyOrganizationUnitOfWork(self._database)


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    constraint = getattr(getattr(exc, "orig", None), "constraint_name", None)
    if constraint in {
        "uq_organization_idempotency_actor_operation_key",
        "uq_organization_invitations_open_email",
        "uq_organization_access_grants_active_scope",
        "uq_organization_memberships_organization_id",
    }:
        raise OrganizationConflict("organization request conflicts with current state") from exc
    raise OrganizationUnavailable("organization persistence failed safely") from exc


def _organization_values(
    value: Organization,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "name": value.name,
        "created_by_user_id": value.created_by_user_id,
        "status": value.status.value,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _organization(model: OrganizationModel) -> Organization:
    try:
        return Organization(
            id=model.id,
            name=model.name,
            created_by_user_id=model.created_by_user_id,
            status=OrganizationStatus(model.status),
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError, OrganizationValidationError) as exc:
        raise OrganizationUnavailable("stored organization is invalid") from exc


def _membership_values(
    value: OrganizationMembership,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "organization_id": value.organization_id,
        "user_id": value.user_id,
        "role": value.role.value,
        "status": value.status.value,
        "version": value.version,
        "accepted_at": value.accepted_at,
        "suspended_at": value.suspended_at,
        "left_at": value.left_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _membership(model: OrganizationMembershipModel) -> OrganizationMembership:
    try:
        return OrganizationMembership(
            id=model.id,
            organization_id=model.organization_id,
            user_id=model.user_id,
            role=OrganizationRole(model.role),
            status=OrganizationMembershipStatus(model.status),
            version=model.version,
            accepted_at=model.accepted_at,
            suspended_at=model.suspended_at,
            left_at=model.left_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError, OrganizationValidationError) as exc:
        raise OrganizationUnavailable("stored membership is invalid") from exc


def _invitation_values(
    value: OrganizationInvitation,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "organization_id": value.organization_id,
        "invited_email_normalized": value.invited_email_normalized,
        "invited_email_digest": bytes.fromhex(value.invited_email_digest),
        "role": value.role.value,
        "token_hash": (bytes.fromhex(value.token_hash) if value.token_hash is not None else None),
        "status": value.status.value,
        "invited_by_user_id": value.invited_by_user_id,
        "accepted_by_user_id": value.accepted_by_user_id,
        "expires_at": value.expires_at,
        "version": value.version,
        "accepted_at": value.accepted_at,
        "revoked_at": value.revoked_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _invitation(model: OrganizationInvitationModel) -> OrganizationInvitation:
    try:
        return OrganizationInvitation(
            id=model.id,
            organization_id=model.organization_id,
            invited_email_normalized=model.invited_email_normalized,
            invited_email_digest=model.invited_email_digest.hex(),
            role=OrganizationRole(model.role),
            token_hash=model.token_hash.hex() if model.token_hash is not None else None,
            status=InvitationStatus(model.status),
            invited_by_user_id=model.invited_by_user_id,
            accepted_by_user_id=model.accepted_by_user_id,
            expires_at=model.expires_at,
            version=model.version,
            accepted_at=model.accepted_at,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError, OrganizationValidationError) as exc:
        raise OrganizationUnavailable("stored invitation is invalid") from exc


def _outbox_values(
    value: OrganizationInvitationOutbox,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "invitation_id": value.invitation_id,
        "organization_id": value.organization_id,
        "trace_id": value.trace_id,
        "attempts": value.attempts,
        "max_attempts": value.max_attempts,
        "next_attempt_at": value.next_attempt_at,
        "lease_token": value.lease_token,
        "lease_expires_at": value.lease_expires_at,
        "published_at": value.published_at,
        "dead_lettered_at": value.dead_lettered_at,
        "cancelled_at": value.cancelled_at,
        "last_error_code": value.last_error_code,
        "created_at": value.created_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _outbox(model: OrganizationInvitationOutboxModel) -> OrganizationInvitationOutbox:
    try:
        return OrganizationInvitationOutbox(
            id=model.id,
            invitation_id=model.invitation_id,
            organization_id=model.organization_id,
            trace_id=model.trace_id,
            attempts=model.attempts,
            max_attempts=model.max_attempts,
            next_attempt_at=model.next_attempt_at,
            lease_token=model.lease_token,
            lease_expires_at=model.lease_expires_at,
            published_at=model.published_at,
            dead_lettered_at=model.dead_lettered_at,
            cancelled_at=model.cancelled_at,
            last_error_code=model.last_error_code,
            created_at=model.created_at,
        )
    except (TypeError, ValueError, OrganizationValidationError) as exc:
        raise OrganizationUnavailable("stored invitation outbox is invalid") from exc


def _grant_values(
    value: OrganizationAccessGrant,
    *,
    include_identity: bool = True,
) -> dict[str, object]:
    values: dict[str, object] = {
        "organization_id": value.organization_id,
        "subject_user_id": value.subject_user_id,
        "grantee_user_id": value.grantee_user_id,
        "purpose": value.purpose.value,
        "scope": value.scope.value,
        "status": value.status.value,
        "granted_by_user_id": value.granted_by_user_id,
        "expires_at": value.expires_at,
        "version": value.version,
        "revoked_at": value.revoked_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        values["id"] = value.id
    return values


def _grant(model: OrganizationAccessGrantModel) -> OrganizationAccessGrant:
    try:
        return OrganizationAccessGrant(
            id=model.id,
            organization_id=model.organization_id,
            subject_user_id=model.subject_user_id,
            grantee_user_id=model.grantee_user_id,
            purpose=GrantPurpose(model.purpose),
            scope=GrantScope(model.scope),
            status=GrantStatus(model.status),
            granted_by_user_id=model.granted_by_user_id,
            expires_at=model.expires_at,
            version=model.version,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError, OrganizationValidationError) as exc:
        raise OrganizationUnavailable("stored grant is invalid") from exc


def _idempotency(
    model: OrganizationIdempotencyModel,
) -> OrganizationIdempotencyRecord:
    return OrganizationIdempotencyRecord(
        id=model.id,
        actor_user_id=model.actor_user_id,
        operation=model.operation,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint.hex(),
        resource_id=model.resource_id,
        created_at=model.created_at,
    )
