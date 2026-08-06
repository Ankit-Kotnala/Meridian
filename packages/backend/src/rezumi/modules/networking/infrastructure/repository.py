"""Async SQLAlchemy persistence for the owner-scoped networking CRM."""

from __future__ import annotations

import hashlib
from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, delete, func, not_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.networking.application import (
    ContactFilter,
    DueReminderView,
    NetworkingCursor,
    NetworkingKeysetCursor,
    OrganizationFilter,
    ReminderExecutionView,
)
from rezumi.modules.networking.domain import (
    DELETED_TEXT,
    ConsentAction,
    ConsentPurpose,
    ContactReferralState,
    InteractionDeliveryState,
    InteractionDirection,
    InteractionKind,
    NetworkingAuditEvent,
    NetworkingConflict,
    NetworkingConsentEvent,
    NetworkingContact,
    NetworkingContactNote,
    NetworkingIdempotencyConflict,
    NetworkingIdempotencyRecord,
    NetworkingInteraction,
    NetworkingOrganization,
    NetworkingReferral,
    NetworkingReminder,
    NetworkingReminderOccurrence,
    NetworkingReminderOutboxEntry,
    NetworkingTemplate,
    NetworkingUnavailable,
    NetworkingVersionConflict,
    ReferralStatus,
    RelationshipStage,
    ReminderOccurrenceStatus,
    ReminderOutboxKind,
    ReminderOutboxStatus,
    ReminderStatus,
    TemplateKind,
)

from .models import (
    NetworkingAuditEventModel,
    NetworkingConsentEventModel,
    NetworkingContactModel,
    NetworkingContactNoteModel,
    NetworkingIdempotencyModel,
    NetworkingInteractionModel,
    NetworkingOrganizationModel,
    NetworkingReferralModel,
    NetworkingReminderModel,
    NetworkingReminderOccurrenceModel,
    NetworkingReminderOutboxModel,
    NetworkingTemplateModel,
)


class SqlAlchemyNetworkingUnitOfWork:
    """One transaction per use case with owner-qualified reads."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyNetworkingUnitOfWork:
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
            raise RuntimeError("networking unit of work is not active")
        return self._session

    async def lock_owner(self, owner_user_id: UUID) -> None:
        await self._advisory_lock(f"networking:owner:{owner_user_id}")

    async def lock_idempotency(self, owner_user_id: UUID, idempotency_key: str) -> None:
        await self._advisory_lock(f"networking:idempotency:{owner_user_id}:{idempotency_key}")

    async def _advisory_lock(self, value: str) -> None:
        lock_key = int.from_bytes(
            hashlib.sha256(value.encode("ascii")).digest()[:8],
            "big",
            signed=True,
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def list_organizations(
        self,
        owner_user_id: UUID,
        filter_by: OrganizationFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingOrganization]:
        statement = select(NetworkingOrganizationModel).where(
            NetworkingOrganizationModel.owner_user_id == owner_user_id,
            NetworkingOrganizationModel.deleted_at.is_(None),
        )
        if filter_by.query is not None:
            statement = statement.where(
                NetworkingOrganizationModel.normalized_search.ilike(
                    _pattern(filter_by.query), escape="\\"
                )
            )
        if filter_by.tag is not None:
            statement = statement.where(NetworkingOrganizationModel.tags.contains([filter_by.tag]))
        statement = _after(
            statement,
            NetworkingOrganizationModel.updated_at,
            NetworkingOrganizationModel.id,
            after,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingOrganizationModel.updated_at.desc(),
                    NetworkingOrganizationModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_organization(row) for row in rows]

    async def get_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingOrganization | None:
        statement = select(NetworkingOrganizationModel).where(
            NetworkingOrganizationModel.owner_user_id == owner_user_id,
            NetworkingOrganizationModel.id == organization_id,
        )
        if not include_deleted:
            statement = statement.where(NetworkingOrganizationModel.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _organization(row) if row is not None else None

    async def add_organization(self, organization: NetworkingOrganization) -> None:
        self.session.add(_organization_model(organization))

    async def count_organizations(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingOrganizationModel)
                .where(
                    NetworkingOrganizationModel.owner_user_id == owner_user_id,
                    NetworkingOrganizationModel.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def save_organization(self, organization: NetworkingOrganization) -> None:
        await self._versioned_update(
            NetworkingOrganizationModel,
            organization.owner_user_id,
            organization.id,
            organization.version,
            _organization_values(organization, include_identity=False),
        )

    async def detach_organization_contacts(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        updated_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(NetworkingContactModel)
            .where(
                NetworkingContactModel.owner_user_id == owner_user_id,
                NetworkingContactModel.organization_id == organization_id,
                NetworkingContactModel.deleted_at.is_(None),
            )
            .values(
                organization_id=None,
                version=NetworkingContactModel.version + 1,
                updated_at=updated_at,
            )
        )
        return cast(int, cast(Any, result).rowcount)

    async def list_contacts(
        self,
        owner_user_id: UUID,
        filter_by: ContactFilter,
        after: NetworkingCursor | None,
        limit: int,
    ) -> list[NetworkingContact]:
        statement = select(NetworkingContactModel).where(
            NetworkingContactModel.owner_user_id == owner_user_id,
            NetworkingContactModel.deleted_at.is_(None),
        )
        if filter_by.query is not None:
            statement = statement.where(
                NetworkingContactModel.normalized_search.ilike(
                    _pattern(filter_by.query), escape="\\"
                )
            )
        if filter_by.organization_id is not None:
            statement = statement.where(
                NetworkingContactModel.organization_id == filter_by.organization_id
            )
        if filter_by.relationship_stage is not None:
            statement = statement.where(
                NetworkingContactModel.relationship_stage == filter_by.relationship_stage.value
            )
        if filter_by.referral_state is not None:
            statement = statement.where(
                NetworkingContactModel.referral_state == filter_by.referral_state.value
            )
        if filter_by.tag is not None:
            statement = statement.where(NetworkingContactModel.tags.contains([filter_by.tag]))
        if filter_by.outreach_consent is not None:
            allows = and_(
                *(
                    func.coalesce(
                        _latest_consent_action(owner_user_id, purpose),
                        ConsentAction.WITHDRAWN.value,
                    )
                    == ConsentAction.GRANTED.value
                    for purpose in ConsentPurpose
                )
            )
            statement = statement.where(allows if filter_by.outreach_consent else not_(allows))
        statement = _after(
            statement,
            NetworkingContactModel.updated_at,
            NetworkingContactModel.id,
            after,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingContactModel.updated_at.desc(),
                    NetworkingContactModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_contact(row) for row in rows]

    async def get_contact(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingContact | None:
        statement = select(NetworkingContactModel).where(
            NetworkingContactModel.owner_user_id == owner_user_id,
            NetworkingContactModel.id == contact_id,
        )
        if not include_deleted:
            statement = statement.where(NetworkingContactModel.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _contact(row) if row is not None else None

    async def add_contact(self, contact: NetworkingContact) -> None:
        self.session.add(_contact_model(contact))
        await self._flush()

    async def count_contacts(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingContactModel)
                .where(
                    NetworkingContactModel.owner_user_id == owner_user_id,
                    NetworkingContactModel.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def save_contact(self, contact: NetworkingContact) -> None:
        await self._versioned_update(
            NetworkingContactModel,
            contact.owner_user_id,
            contact.id,
            contact.version,
            _contact_values(contact, include_identity=False),
        )

    async def add_consent_event(self, event: NetworkingConsentEvent) -> None:
        self.session.add(_consent_model(event))

    async def count_consent_events(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingConsentEventModel)
                .where(
                    NetworkingConsentEventModel.owner_user_id == owner_user_id,
                    NetworkingConsentEventModel.contact_id == contact_id,
                )
            )
            or 0
        )

    async def get_latest_consent_events(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> list[NetworkingConsentEvent]:
        latest = (
            select(
                NetworkingConsentEventModel.purpose.label("purpose"),
                func.max(NetworkingConsentEventModel.sequence).label("sequence"),
            )
            .where(
                NetworkingConsentEventModel.owner_user_id == owner_user_id,
                NetworkingConsentEventModel.contact_id == contact_id,
            )
            .group_by(NetworkingConsentEventModel.purpose)
            .subquery()
        )
        rows = (
            await self.session.scalars(
                select(NetworkingConsentEventModel)
                .join(
                    NetworkingContactModel,
                    (
                        NetworkingContactModel.owner_user_id
                        == NetworkingConsentEventModel.owner_user_id
                    )
                    & (NetworkingContactModel.id == NetworkingConsentEventModel.contact_id),
                )
                .join(
                    latest,
                    (latest.c.purpose == NetworkingConsentEventModel.purpose)
                    & (latest.c.sequence == NetworkingConsentEventModel.sequence),
                )
                .where(
                    NetworkingConsentEventModel.owner_user_id == owner_user_id,
                    NetworkingConsentEventModel.contact_id == contact_id,
                    NetworkingContactModel.deleted_at.is_(None),
                )
                .order_by(NetworkingConsentEventModel.sequence.asc())
            )
        ).all()
        return [_consent(row) for row in rows]

    async def next_consent_sequence(self, owner_user_id: UUID, contact_id: UUID) -> int:
        latest = await self.session.scalar(
            select(func.max(NetworkingConsentEventModel.sequence)).where(
                NetworkingConsentEventModel.owner_user_id == owner_user_id,
                NetworkingConsentEventModel.contact_id == contact_id,
            )
        )
        return int(latest or 0) + 1

    async def list_consent_event_page(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingConsentEvent]:
        statement = (
            select(NetworkingConsentEventModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingConsentEventModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingConsentEventModel.contact_id),
            )
            .where(
                NetworkingConsentEventModel.owner_user_id == owner_user_id,
                NetworkingConsentEventModel.contact_id == contact_id,
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingConsentEventModel.sequence,
            NetworkingConsentEventModel.id,
            after,
            ascending=True,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingConsentEventModel.sequence.asc(),
                    NetworkingConsentEventModel.id.asc(),
                ).limit(limit)
            )
        ).all()
        return [_consent(row) for row in rows]

    async def get_consent_events_for_contacts(
        self, owner_user_id: UUID, contact_ids: tuple[UUID, ...]
    ) -> dict[UUID, list[NetworkingConsentEvent]]:
        if not contact_ids:
            return {}
        latest = (
            select(
                NetworkingConsentEventModel.contact_id.label("contact_id"),
                NetworkingConsentEventModel.purpose.label("purpose"),
                func.max(NetworkingConsentEventModel.sequence).label("sequence"),
            )
            .where(
                NetworkingConsentEventModel.owner_user_id == owner_user_id,
                NetworkingConsentEventModel.contact_id.in_(contact_ids),
            )
            .group_by(
                NetworkingConsentEventModel.contact_id,
                NetworkingConsentEventModel.purpose,
            )
            .subquery()
        )
        rows = (
            await self.session.scalars(
                select(NetworkingConsentEventModel)
                .join(
                    NetworkingContactModel,
                    (
                        NetworkingContactModel.owner_user_id
                        == NetworkingConsentEventModel.owner_user_id
                    )
                    & (NetworkingContactModel.id == NetworkingConsentEventModel.contact_id),
                )
                .join(
                    latest,
                    (latest.c.contact_id == NetworkingConsentEventModel.contact_id)
                    & (latest.c.purpose == NetworkingConsentEventModel.purpose)
                    & (latest.c.sequence == NetworkingConsentEventModel.sequence),
                )
                .where(
                    NetworkingConsentEventModel.owner_user_id == owner_user_id,
                    NetworkingConsentEventModel.contact_id.in_(contact_ids),
                    NetworkingContactModel.deleted_at.is_(None),
                )
                .order_by(
                    NetworkingConsentEventModel.contact_id.asc(),
                    NetworkingConsentEventModel.sequence.asc(),
                )
            )
        ).all()
        result: dict[UUID, list[NetworkingConsentEvent]] = {}
        for row in rows:
            result.setdefault(row.contact_id, []).append(_consent(row))
        return result

    async def add_note(self, note: NetworkingContactNote) -> None:
        self.session.add(_note_model(note))

    async def count_notes(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingContactNoteModel)
                .where(
                    NetworkingContactNoteModel.owner_user_id == owner_user_id,
                    NetworkingContactNoteModel.contact_id == contact_id,
                )
            )
            or 0
        )

    async def list_notes(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingContactNote]:
        statement = (
            select(NetworkingContactNoteModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingContactNoteModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingContactNoteModel.contact_id),
            )
            .where(
                NetworkingContactNoteModel.owner_user_id == owner_user_id,
                NetworkingContactNoteModel.contact_id == contact_id,
                NetworkingContactNoteModel.deleted_at.is_(None),
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingContactNoteModel.created_at,
            NetworkingContactNoteModel.id,
            after,
            ascending=False,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingContactNoteModel.created_at.desc(),
                    NetworkingContactNoteModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_note(row) for row in rows]

    async def get_note(self, owner_user_id: UUID, note_id: UUID) -> NetworkingContactNote | None:
        row = await self.session.scalar(
            select(NetworkingContactNoteModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingContactNoteModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingContactNoteModel.contact_id),
            )
            .where(
                NetworkingContactNoteModel.owner_user_id == owner_user_id,
                NetworkingContactNoteModel.id == note_id,
                NetworkingContactNoteModel.deleted_at.is_(None),
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        return _note(row) if row is not None else None

    async def redact_contact_content(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        redacted_at: datetime,
        *,
        outreach_only: bool,
    ) -> None:
        if not outreach_only:
            await self.session.execute(
                update(NetworkingContactNoteModel)
                .where(
                    NetworkingContactNoteModel.owner_user_id == owner_user_id,
                    NetworkingContactNoteModel.contact_id == contact_id,
                    NetworkingContactNoteModel.deleted_at.is_(None),
                )
                .values(body=DELETED_TEXT, deleted_at=redacted_at)
            )
        interaction_scope = [
            NetworkingInteractionModel.owner_user_id == owner_user_id,
            NetworkingInteractionModel.contact_id == contact_id,
            NetworkingInteractionModel.deleted_at.is_(None),
        ]
        if outreach_only:
            interaction_scope.append(
                or_(
                    NetworkingInteractionModel.direction == InteractionDirection.OUTBOUND.value,
                    NetworkingInteractionModel.template_id.is_not(None),
                    NetworkingInteractionModel.kind == InteractionKind.REFERRAL.value,
                )
            )
        await self.session.execute(
            update(NetworkingInteractionModel)
            .where(*interaction_scope)
            .values(summary=DELETED_TEXT, deleted_at=redacted_at)
        )
        await self.session.execute(
            update(NetworkingReferralModel)
            .where(
                NetworkingReferralModel.owner_user_id == owner_user_id,
                NetworkingReferralModel.contact_id == contact_id,
                NetworkingReferralModel.context.is_not(None),
            )
            .values(
                context=None,
                version=NetworkingReferralModel.version + 1,
                updated_at=redacted_at,
            )
        )
        await self.session.execute(
            update(NetworkingReminderModel)
            .where(
                NetworkingReminderModel.owner_user_id == owner_user_id,
                NetworkingReminderModel.contact_id == contact_id,
                NetworkingReminderModel.title != DELETED_TEXT,
            )
            .values(
                title=DELETED_TEXT,
                version=NetworkingReminderModel.version + 1,
                updated_at=redacted_at,
            )
        )

    async def add_interaction(self, interaction: NetworkingInteraction) -> None:
        self.session.add(_interaction_model(interaction))

    async def count_interactions(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingInteractionModel)
                .where(
                    NetworkingInteractionModel.owner_user_id == owner_user_id,
                    NetworkingInteractionModel.contact_id == contact_id,
                )
            )
            or 0
        )

    async def list_interactions(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingInteraction]:
        statement = (
            select(NetworkingInteractionModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingInteractionModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingInteractionModel.contact_id),
            )
            .where(
                NetworkingInteractionModel.owner_user_id == owner_user_id,
                NetworkingInteractionModel.contact_id == contact_id,
                NetworkingInteractionModel.deleted_at.is_(None),
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingInteractionModel.occurred_at,
            NetworkingInteractionModel.id,
            after,
            ascending=False,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingInteractionModel.occurred_at.desc(),
                    NetworkingInteractionModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_interaction(row) for row in rows]

    async def get_interaction(
        self, owner_user_id: UUID, interaction_id: UUID
    ) -> NetworkingInteraction | None:
        row = await self.session.scalar(
            select(NetworkingInteractionModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingInteractionModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingInteractionModel.contact_id),
            )
            .where(
                NetworkingInteractionModel.owner_user_id == owner_user_id,
                NetworkingInteractionModel.id == interaction_id,
                NetworkingInteractionModel.deleted_at.is_(None),
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        return _interaction(row) if row is not None else None

    async def add_referral(self, referral: NetworkingReferral) -> None:
        self.session.add(_referral_model(referral))

    async def count_referrals(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingReferralModel)
                .where(
                    NetworkingReferralModel.owner_user_id == owner_user_id,
                    NetworkingReferralModel.contact_id == contact_id,
                )
            )
            or 0
        )

    async def get_referral(
        self,
        owner_user_id: UUID,
        referral_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReferral | None:
        statement = (
            select(NetworkingReferralModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingReferralModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingReferralModel.contact_id),
            )
            .where(
                NetworkingReferralModel.owner_user_id == owner_user_id,
                NetworkingReferralModel.id == referral_id,
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=NetworkingReferralModel)
        row = await self.session.scalar(statement)
        return _referral(row) if row is not None else None

    async def list_referrals(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReferral]:
        statement = (
            select(NetworkingReferralModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingReferralModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingReferralModel.contact_id),
            )
            .where(
                NetworkingReferralModel.owner_user_id == owner_user_id,
                NetworkingReferralModel.contact_id == contact_id,
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingReferralModel.updated_at,
            NetworkingReferralModel.id,
            after,
            ascending=False,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingReferralModel.updated_at.desc(),
                    NetworkingReferralModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_referral(row) for row in rows]

    async def cancel_contact_referrals(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None:
        await self.session.execute(
            update(NetworkingReferralModel)
            .where(
                NetworkingReferralModel.owner_user_id == owner_user_id,
                NetworkingReferralModel.contact_id == contact_id,
                NetworkingReferralModel.status.not_in(
                    (ReferralStatus.CANCELLED.value, ReferralStatus.DECLINED.value)
                ),
            )
            .values(
                status=ReferralStatus.CANCELLED.value,
                version=NetworkingReferralModel.version + 1,
                updated_at=updated_at,
            )
        )

    async def save_referral(self, referral: NetworkingReferral) -> None:
        await self._versioned_update(
            NetworkingReferralModel,
            referral.owner_user_id,
            referral.id,
            referral.version,
            _referral_values(referral, include_identity=False),
        )

    async def add_template(self, template: NetworkingTemplate) -> None:
        self.session.add(_template_model(template))

    async def count_templates(self, owner_user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingTemplateModel)
                .where(
                    NetworkingTemplateModel.owner_user_id == owner_user_id,
                    NetworkingTemplateModel.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def get_template(
        self,
        owner_user_id: UUID,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingTemplate | None:
        statement = select(NetworkingTemplateModel).where(
            NetworkingTemplateModel.owner_user_id == owner_user_id,
            NetworkingTemplateModel.id == template_id,
            NetworkingTemplateModel.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _template(row) if row is not None else None

    async def list_templates(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingTemplate]:
        statement = select(NetworkingTemplateModel).where(
            NetworkingTemplateModel.owner_user_id == owner_user_id,
            NetworkingTemplateModel.deleted_at.is_(None),
        )
        statement = _keyset_after(
            statement,
            NetworkingTemplateModel.updated_at,
            NetworkingTemplateModel.id,
            after,
            ascending=False,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingTemplateModel.updated_at.desc(),
                    NetworkingTemplateModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_template(row) for row in rows]

    async def save_template(self, template: NetworkingTemplate) -> None:
        await self._versioned_update(
            NetworkingTemplateModel,
            template.owner_user_id,
            template.id,
            template.version,
            _template_values(template, include_identity=False),
        )

    async def add_reminder(self, reminder: NetworkingReminder) -> None:
        self.session.add(_reminder_model(reminder))
        await self._flush()

    async def count_reminders(self, owner_user_id: UUID, contact_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingReminderModel)
                .where(
                    NetworkingReminderModel.owner_user_id == owner_user_id,
                    NetworkingReminderModel.contact_id == contact_id,
                )
            )
            or 0
        )

    async def get_reminder(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminder | None:
        statement = select(NetworkingReminderModel).where(
            NetworkingReminderModel.owner_user_id == owner_user_id,
            NetworkingReminderModel.id == reminder_id,
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _reminder(row) if row is not None else None

    async def list_reminders(
        self,
        owner_user_id: UUID,
        contact_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[NetworkingReminder]:
        statement = (
            select(NetworkingReminderModel)
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingReminderModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingReminderModel.contact_id),
            )
            .where(
                NetworkingReminderModel.owner_user_id == owner_user_id,
                NetworkingReminderModel.contact_id == contact_id,
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingReminderModel.due_at,
            NetworkingReminderModel.id,
            after,
            ascending=True,
        )
        rows = (
            await self.session.scalars(
                statement.order_by(
                    NetworkingReminderModel.due_at.asc(),
                    NetworkingReminderModel.id.asc(),
                ).limit(limit)
            )
        ).all()
        return [_reminder(row) for row in rows]

    async def next_active_reminder_at(
        self, owner_user_id: UUID, contact_id: UUID
    ) -> datetime | None:
        return cast(
            datetime | None,
            await self.session.scalar(
                select(func.min(NetworkingReminderModel.due_at)).where(
                    NetworkingReminderModel.owner_user_id == owner_user_id,
                    NetworkingReminderModel.contact_id == contact_id,
                    NetworkingReminderModel.status == ReminderStatus.ACTIVE.value,
                )
            ),
        )

    async def save_reminder(self, reminder: NetworkingReminder) -> None:
        await self._versioned_update(
            NetworkingReminderModel,
            reminder.owner_user_id,
            reminder.id,
            reminder.version,
            _reminder_values(reminder, include_identity=False),
        )

    async def cancel_contact_reminders(
        self, owner_user_id: UUID, contact_id: UUID, updated_at: datetime
    ) -> None:
        reminder_ids = (
            await self.session.scalars(
                select(NetworkingReminderModel.id).where(
                    NetworkingReminderModel.owner_user_id == owner_user_id,
                    NetworkingReminderModel.contact_id == contact_id,
                    NetworkingReminderModel.status == ReminderStatus.ACTIVE.value,
                )
            )
        ).all()
        if not reminder_ids:
            return
        await self.session.execute(
            update(NetworkingReminderModel)
            .where(
                NetworkingReminderModel.owner_user_id == owner_user_id,
                NetworkingReminderModel.id.in_(reminder_ids),
            )
            .values(
                status=ReminderStatus.CANCELLED.value,
                version=NetworkingReminderModel.version + 1,
                updated_at=updated_at,
            )
        )
        await self._cancel_occurrences(owner_user_id, tuple(reminder_ids), updated_at)

    async def cancel_reminder_occurrences(
        self, owner_user_id: UUID, reminder_id: UUID, updated_at: datetime
    ) -> None:
        await self._cancel_occurrences(owner_user_id, (reminder_id,), updated_at)

    async def add_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None:
        self.session.add(_occurrence_model(occurrence))
        await self._flush()

    async def count_reminder_occurrences(self, owner_user_id: UUID, reminder_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(NetworkingReminderOccurrenceModel)
                .where(
                    NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                    NetworkingReminderOccurrenceModel.reminder_id == reminder_id,
                )
            )
            or 0
        )

    async def prune_terminal_reminder_history(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
        *,
        retain: int,
    ) -> int:
        """Delete only safely terminal processed/cancelled pairs.

        Scheduled, retryable, leased, and dead-letter rows are deliberately
        ineligible so retry and incident audit state is never removed.
        """

        eligible = (
            select(NetworkingReminderOccurrenceModel.id)
            .join(
                NetworkingReminderOutboxModel,
                (
                    NetworkingReminderOutboxModel.owner_user_id
                    == NetworkingReminderOccurrenceModel.owner_user_id
                )
                & (
                    NetworkingReminderOutboxModel.occurrence_id
                    == NetworkingReminderOccurrenceModel.id
                ),
            )
            .where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.reminder_id == reminder_id,
                NetworkingReminderOccurrenceModel.status.in_(
                    (
                        ReminderOccurrenceStatus.ACKNOWLEDGED.value,
                        ReminderOccurrenceStatus.CANCELLED.value,
                    )
                ),
                NetworkingReminderOutboxModel.status.in_(
                    (
                        ReminderOutboxStatus.PROCESSED.value,
                        ReminderOutboxStatus.CANCELLED.value,
                    )
                ),
            )
            .order_by(
                NetworkingReminderOccurrenceModel.occurrence_number.desc(),
                NetworkingReminderOccurrenceModel.id.desc(),
            )
            .offset(retain)
        )
        removable_ids = list((await self.session.scalars(eligible)).all())
        if not removable_ids:
            return 0
        await self.session.execute(
            delete(NetworkingReminderOccurrenceModel).where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.id.in_(removable_ids),
            )
        )
        return len(removable_ids)

    async def get_occurrence(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOccurrence | None:
        statement = select(NetworkingReminderOccurrenceModel).where(
            NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
            NetworkingReminderOccurrenceModel.id == occurrence_id,
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _occurrence(row) if row is not None else None

    async def get_latest_reminder_occurrence(
        self,
        owner_user_id: UUID,
        reminder_id: UUID,
    ) -> NetworkingReminderOccurrence | None:
        row = await self.session.scalar(
            select(NetworkingReminderOccurrenceModel)
            .where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.reminder_id == reminder_id,
            )
            .order_by(
                NetworkingReminderOccurrenceModel.occurrence_number.desc(),
                NetworkingReminderOccurrenceModel.id.desc(),
            )
            .limit(1)
        )
        return _occurrence(row) if row is not None else None

    async def find_occurrence(
        self, owner_user_id: UUID, reminder_id: UUID, occurrence_number: int
    ) -> NetworkingReminderOccurrence | None:
        row = await self.session.scalar(
            select(NetworkingReminderOccurrenceModel).where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.reminder_id == reminder_id,
                NetworkingReminderOccurrenceModel.occurrence_number == occurrence_number,
            )
        )
        return _occurrence(row) if row is not None else None

    async def next_occurrence_number(self, owner_user_id: UUID, reminder_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(NetworkingReminderOccurrenceModel.occurrence_number)).where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.reminder_id == reminder_id,
            )
        )
        return int(value or 0) + 1

    async def save_occurrence(self, occurrence: NetworkingReminderOccurrence) -> None:
        result = await self.session.execute(
            update(NetworkingReminderOccurrenceModel)
            .where(
                NetworkingReminderOccurrenceModel.owner_user_id == occurrence.owner_user_id,
                NetworkingReminderOccurrenceModel.id == occurrence.id,
            )
            .values(**_occurrence_values(occurrence, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise NetworkingConflict

    async def add_outbox(self, entry: NetworkingReminderOutboxEntry) -> None:
        self.session.add(_outbox_model(entry))

    async def get_outbox(
        self,
        entry_id: UUID,
        *,
        for_update: bool = False,
    ) -> NetworkingReminderOutboxEntry | None:
        statement = select(NetworkingReminderOutboxModel).where(
            NetworkingReminderOutboxModel.id == entry_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        return _outbox(row) if row is not None else None

    async def get_occurrence_outbox(
        self,
        owner_user_id: UUID,
        occurrence_id: UUID,
    ) -> NetworkingReminderOutboxEntry | None:
        row = await self.session.scalar(
            select(NetworkingReminderOutboxModel).where(
                NetworkingReminderOutboxModel.owner_user_id == owner_user_id,
                NetworkingReminderOutboxModel.occurrence_id == occurrence_id,
            )
        )
        return _outbox(row) if row is not None else None

    async def get_reminder_executions(
        self,
        owner_user_id: UUID,
        reminder_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[NetworkingReminderOccurrence, NetworkingReminderOutboxEntry]]:
        """Load the latest occurrence/outbox pair for many reminders in one query."""

        if not reminder_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    NetworkingReminderOccurrenceModel,
                    NetworkingReminderOutboxModel,
                )
                .join(
                    NetworkingReminderOutboxModel,
                    (
                        NetworkingReminderOutboxModel.owner_user_id
                        == NetworkingReminderOccurrenceModel.owner_user_id
                    )
                    & (
                        NetworkingReminderOutboxModel.occurrence_id
                        == NetworkingReminderOccurrenceModel.id
                    ),
                )
                .where(
                    NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                    NetworkingReminderOccurrenceModel.reminder_id.in_(reminder_ids),
                )
                .order_by(
                    NetworkingReminderOccurrenceModel.reminder_id.asc(),
                    NetworkingReminderOccurrenceModel.occurrence_number.desc(),
                    NetworkingReminderOccurrenceModel.id.desc(),
                )
            )
        ).all()
        result: dict[UUID, tuple[NetworkingReminderOccurrence, NetworkingReminderOutboxEntry]] = {}
        for occurrence_row, outbox_row in rows:
            reminder_id = occurrence_row.reminder_id
            if reminder_id not in result:
                result[reminder_id] = (
                    _occurrence(occurrence_row),
                    _outbox(outbox_row),
                )
        return result

    async def list_due_reminders(
        self,
        owner_user_id: UUID,
        after: NetworkingKeysetCursor | None,
        limit: int,
    ) -> list[DueReminderView]:
        statement = (
            select(
                NetworkingReminderModel,
                NetworkingReminderOccurrenceModel,
                NetworkingReminderOutboxModel,
            )
            .join(
                NetworkingReminderOccurrenceModel,
                (
                    NetworkingReminderOccurrenceModel.owner_user_id
                    == NetworkingReminderModel.owner_user_id
                )
                & (NetworkingReminderOccurrenceModel.reminder_id == NetworkingReminderModel.id),
            )
            .join(
                NetworkingReminderOutboxModel,
                (
                    NetworkingReminderOutboxModel.owner_user_id
                    == NetworkingReminderOccurrenceModel.owner_user_id
                )
                & (
                    NetworkingReminderOutboxModel.occurrence_id
                    == NetworkingReminderOccurrenceModel.id
                ),
            )
            .join(
                NetworkingContactModel,
                (NetworkingContactModel.owner_user_id == NetworkingReminderModel.owner_user_id)
                & (NetworkingContactModel.id == NetworkingReminderModel.contact_id),
            )
            .where(
                NetworkingReminderModel.owner_user_id == owner_user_id,
                NetworkingReminderModel.status == ReminderStatus.ACTIVE.value,
                NetworkingReminderOccurrenceModel.status == ReminderOccurrenceStatus.DUE.value,
                NetworkingReminderOutboxModel.status == ReminderOutboxStatus.PROCESSED.value,
                NetworkingContactModel.deleted_at.is_(None),
            )
        )
        statement = _keyset_after(
            statement,
            NetworkingReminderOccurrenceModel.scheduled_for,
            NetworkingReminderOccurrenceModel.id,
            after,
            ascending=True,
        )
        rows = (
            await self.session.execute(
                statement.order_by(
                    NetworkingReminderOccurrenceModel.scheduled_for.asc(),
                    NetworkingReminderOccurrenceModel.id.asc(),
                ).limit(limit)
            )
        ).all()
        return [
            DueReminderView(
                reminder=_reminder(reminder_row),
                execution=ReminderExecutionView(
                    occurrence_id=occurrence_row.id,
                    occurrence_number=occurrence_row.occurrence_number,
                    scheduled_for=occurrence_row.scheduled_for,
                    occurrence_status=ReminderOccurrenceStatus(occurrence_row.status),
                    attempt_count=outbox_row.attempt_count,
                    max_attempts=outbox_row.max_attempts,
                    queue_status=ReminderOutboxStatus(outbox_row.status),
                    last_error_code=outbox_row.last_error_code,
                ),
            )
            for reminder_row, occurrence_row, outbox_row in rows
        ]

    async def list_claimable_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]:
        # Candidate discovery is intentionally lock-free. The application
        # service re-reads each candidate under the canonical
        # contact -> reminder -> occurrence -> outbox lock order.
        rows = (
            await self.session.scalars(
                select(NetworkingReminderOutboxModel)
                .where(
                    NetworkingReminderOutboxModel.status == ReminderOutboxStatus.PENDING.value,
                    NetworkingReminderOutboxModel.available_at <= now,
                )
                .order_by(
                    NetworkingReminderOutboxModel.available_at.asc(),
                    NetworkingReminderOutboxModel.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [_outbox(row) for row in rows]

    async def list_expired_outbox(
        self, now: datetime, limit: int
    ) -> list[NetworkingReminderOutboxEntry]:
        rows = (
            await self.session.scalars(
                select(NetworkingReminderOutboxModel)
                .where(
                    NetworkingReminderOutboxModel.status == ReminderOutboxStatus.LEASED.value,
                    NetworkingReminderOutboxModel.lease_expires_at <= now,
                )
                .order_by(
                    NetworkingReminderOutboxModel.lease_expires_at.asc(),
                    NetworkingReminderOutboxModel.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [_outbox(row) for row in rows]

    async def save_outbox(self, entry: NetworkingReminderOutboxEntry) -> None:
        result = await self.session.execute(
            update(NetworkingReminderOutboxModel)
            .where(NetworkingReminderOutboxModel.id == entry.id)
            .values(**_outbox_values(entry, include_identity=False))
        )
        if cast(Any, result).rowcount != 1:
            raise NetworkingConflict

    async def add_idempotency(self, record: NetworkingIdempotencyRecord) -> None:
        self.session.add(_idempotency_model(record))
        await self._flush()

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> NetworkingIdempotencyRecord | None:
        row = await self.session.scalar(
            select(NetworkingIdempotencyModel).where(
                NetworkingIdempotencyModel.owner_user_id == owner_user_id,
                NetworkingIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(row) if row is not None else None

    async def add_audit(self, event: NetworkingAuditEvent) -> None:
        self.session.add(_audit_model(event))

    async def commit(self) -> None:
        try:
            await self.session.commit()
            self._committed = True
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def _cancel_occurrences(
        self,
        owner_user_id: UUID,
        reminder_ids: tuple[UUID, ...],
        updated_at: datetime,
    ) -> None:
        occurrence_ids = (
            await self.session.scalars(
                select(NetworkingReminderOccurrenceModel.id).where(
                    NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                    NetworkingReminderOccurrenceModel.reminder_id.in_(reminder_ids),
                    NetworkingReminderOccurrenceModel.status.in_(
                        (
                            ReminderOccurrenceStatus.SCHEDULED.value,
                            ReminderOccurrenceStatus.DUE.value,
                        )
                    ),
                )
            )
        ).all()
        if not occurrence_ids:
            return
        await self.session.execute(
            update(NetworkingReminderOccurrenceModel)
            .where(
                NetworkingReminderOccurrenceModel.owner_user_id == owner_user_id,
                NetworkingReminderOccurrenceModel.id.in_(occurrence_ids),
            )
            .values(
                status=ReminderOccurrenceStatus.CANCELLED.value,
                updated_at=updated_at,
            )
        )
        await self.session.execute(
            update(NetworkingReminderOutboxModel)
            .where(
                NetworkingReminderOutboxModel.owner_user_id == owner_user_id,
                NetworkingReminderOutboxModel.occurrence_id.in_(occurrence_ids),
                NetworkingReminderOutboxModel.status.in_(
                    (
                        ReminderOutboxStatus.PENDING.value,
                        ReminderOutboxStatus.LEASED.value,
                    )
                ),
            )
            .values(
                status=ReminderOutboxStatus.CANCELLED.value,
                lease_token=None,
                lease_expires_at=None,
                updated_at=updated_at,
            )
        )

    async def _versioned_update(
        self,
        model: Any,
        owner_user_id: UUID,
        record_id: UUID,
        new_version: int,
        values: dict[str, Any],
    ) -> None:
        result = await self.session.execute(
            update(model)
            .where(
                model.owner_user_id == owner_user_id,
                model.id == record_id,
                model.version == new_version - 1,
            )
            .values(**values)
        )
        if cast(Any, result).rowcount != 1:
            raise NetworkingVersionConflict

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyNetworkingUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyNetworkingUnitOfWork:
        return SqlAlchemyNetworkingUnitOfWork(self._database)


def _after(
    statement: Any,
    updated_column: Any,
    id_column: Any,
    cursor: NetworkingCursor | None,
) -> Any:
    if cursor is None:
        return statement
    return statement.where(
        or_(
            updated_column < cursor.updated_at,
            and_(
                updated_column == cursor.updated_at,
                id_column < cursor.record_id,
            ),
        )
    )


def _keyset_after(
    statement: Any,
    position_column: Any,
    id_column: Any,
    cursor: NetworkingKeysetCursor | None,
    *,
    ascending: bool,
) -> Any:
    if cursor is None:
        return statement
    position_comparison = (
        position_column > cursor.position if ascending else position_column < cursor.position
    )
    id_comparison = id_column > cursor.record_id if ascending else id_column < cursor.record_id
    return statement.where(
        or_(
            position_comparison,
            and_(position_column == cursor.position, id_comparison),
        )
    )


def _latest_consent_action(owner_user_id: UUID, purpose: ConsentPurpose) -> Any:
    return (
        select(NetworkingConsentEventModel.action)
        .where(
            NetworkingConsentEventModel.owner_user_id == owner_user_id,
            NetworkingConsentEventModel.contact_id == NetworkingContactModel.id,
            NetworkingConsentEventModel.purpose == purpose.value,
        )
        .order_by(NetworkingConsentEventModel.sequence.desc())
        .limit(1)
        .scalar_subquery()
    )


def _pattern(value: str) -> str:
    return f"%{value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"


def _organization_model(value: NetworkingOrganization) -> NetworkingOrganizationModel:
    return NetworkingOrganizationModel(**_organization_values(value))


def _organization_values(
    value: NetworkingOrganization, *, include_identity: bool = True
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": value.name,
        "website": value.website,
        "industry": value.industry,
        "location": value.location,
        "tags": list(value.tags),
        "normalized_search": value.normalized_search,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "deleted_at": value.deleted_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _organization(value: NetworkingOrganizationModel) -> NetworkingOrganization:
    return NetworkingOrganization(
        id=value.id,
        owner_user_id=value.owner_user_id,
        name=value.name,
        website=value.website,
        industry=value.industry,
        location=value.location,
        tags=tuple(value.tags),
        normalized_search=value.normalized_search,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
        deleted_at=value.deleted_at,
    )


def _contact_model(value: NetworkingContact) -> NetworkingContactModel:
    return NetworkingContactModel(**_contact_values(value))


def _contact_values(value: NetworkingContact, *, include_identity: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "organization_id": value.organization_id,
        "name": value.name,
        "role": value.role,
        "email": value.email,
        "phone": value.phone,
        "profile_url": value.profile_url,
        "location": value.location,
        "relationship_stage": value.relationship_stage.value,
        "referral_state": value.referral_state.value,
        "tags": list(value.tags),
        "normalized_search": value.normalized_search,
        "last_contact_at": value.last_contact_at,
        "next_contact_at": value.next_contact_at,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "deleted_at": value.deleted_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _contact(value: NetworkingContactModel) -> NetworkingContact:
    return NetworkingContact(
        id=value.id,
        owner_user_id=value.owner_user_id,
        organization_id=value.organization_id,
        name=value.name,
        role=value.role,
        email=value.email,
        phone=value.phone,
        profile_url=value.profile_url,
        location=value.location,
        relationship_stage=RelationshipStage(value.relationship_stage),
        referral_state=ContactReferralState(value.referral_state),
        tags=tuple(value.tags),
        normalized_search=value.normalized_search,
        last_contact_at=value.last_contact_at,
        next_contact_at=value.next_contact_at,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
        deleted_at=value.deleted_at,
    )


def _consent_model(value: NetworkingConsentEvent) -> NetworkingConsentEventModel:
    return NetworkingConsentEventModel(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        purpose=value.purpose.value,
        action=value.action.value,
        policy_version=value.policy_version,
        actor_user_id=value.actor_user_id,
        sequence=value.sequence,
        occurred_at=value.occurred_at,
    )


def _consent(value: NetworkingConsentEventModel) -> NetworkingConsentEvent:
    return NetworkingConsentEvent(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        purpose=ConsentPurpose(value.purpose),
        action=ConsentAction(value.action),
        policy_version=value.policy_version,
        actor_user_id=value.actor_user_id or value.owner_user_id,
        sequence=value.sequence,
        occurred_at=value.occurred_at,
    )


def _note_model(value: NetworkingContactNote) -> NetworkingContactNoteModel:
    return NetworkingContactNoteModel(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        body=value.body,
        created_at=value.created_at,
        deleted_at=value.deleted_at,
    )


def _note(value: NetworkingContactNoteModel) -> NetworkingContactNote:
    return NetworkingContactNote(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        body=value.body,
        created_at=value.created_at,
        deleted_at=value.deleted_at,
    )


def _interaction_model(value: NetworkingInteraction) -> NetworkingInteractionModel:
    return NetworkingInteractionModel(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        template_id=value.template_id,
        kind=value.kind.value,
        direction=value.direction.value,
        occurred_at=value.occurred_at,
        summary=value.summary,
        delivery_state=value.delivery_state.value,
        created_at=value.created_at,
        deleted_at=value.deleted_at,
    )


def _interaction(value: NetworkingInteractionModel) -> NetworkingInteraction:
    return NetworkingInteraction(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        template_id=value.template_id,
        kind=InteractionKind(value.kind),
        direction=InteractionDirection(value.direction),
        occurred_at=value.occurred_at,
        summary=value.summary,
        delivery_state=InteractionDeliveryState(value.delivery_state),
        created_at=value.created_at,
        deleted_at=value.deleted_at,
    )


def _referral_model(value: NetworkingReferral) -> NetworkingReferralModel:
    return NetworkingReferralModel(**_referral_values(value))


def _referral_values(value: NetworkingReferral, *, include_identity: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "contact_id": value.contact_id,
        "application_id": value.application_id,
        "status": value.status.value,
        "context": value.context,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _referral(value: NetworkingReferralModel) -> NetworkingReferral:
    return NetworkingReferral(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        application_id=value.application_id,
        status=ReferralStatus(value.status),
        context=value.context,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _template_model(value: NetworkingTemplate) -> NetworkingTemplateModel:
    return NetworkingTemplateModel(**_template_values(value))


def _template_values(value: NetworkingTemplate, *, include_identity: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": value.kind.value,
        "name": value.name,
        "body": value.body,
        "reviewed_at": value.reviewed_at,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "deleted_at": value.deleted_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _template(value: NetworkingTemplateModel) -> NetworkingTemplate:
    return NetworkingTemplate(
        id=value.id,
        owner_user_id=value.owner_user_id,
        kind=TemplateKind(value.kind),
        name=value.name,
        body=value.body,
        reviewed_at=value.reviewed_at,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
        deleted_at=value.deleted_at,
    )


def _reminder_model(value: NetworkingReminder) -> NetworkingReminderModel:
    return NetworkingReminderModel(**_reminder_values(value))


def _reminder_values(value: NetworkingReminder, *, include_identity: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "contact_id": value.contact_id,
        "title": value.title,
        "due_at": value.due_at,
        "recurrence_days": value.recurrence_days,
        "max_attempts": value.max_attempts,
        "status": value.status.value,
        "version": value.version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _reminder(value: NetworkingReminderModel) -> NetworkingReminder:
    return NetworkingReminder(
        id=value.id,
        owner_user_id=value.owner_user_id,
        contact_id=value.contact_id,
        title=value.title,
        due_at=value.due_at,
        recurrence_days=value.recurrence_days,
        max_attempts=value.max_attempts,
        status=ReminderStatus(value.status),
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _occurrence_model(
    value: NetworkingReminderOccurrence,
) -> NetworkingReminderOccurrenceModel:
    return NetworkingReminderOccurrenceModel(**_occurrence_values(value))


def _occurrence_values(
    value: NetworkingReminderOccurrence, *, include_identity: bool = True
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reminder_id": value.reminder_id,
        "contact_id": value.contact_id,
        "scheduled_for": value.scheduled_for,
        "occurrence_number": value.occurrence_number,
        "status": value.status.value,
        "trace_id": value.trace_id,
        "acknowledged_at": value.acknowledged_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _occurrence(
    value: NetworkingReminderOccurrenceModel,
) -> NetworkingReminderOccurrence:
    return NetworkingReminderOccurrence(
        id=value.id,
        owner_user_id=value.owner_user_id,
        reminder_id=value.reminder_id,
        contact_id=value.contact_id,
        scheduled_for=value.scheduled_for,
        occurrence_number=value.occurrence_number,
        status=ReminderOccurrenceStatus(value.status),
        trace_id=value.trace_id,
        acknowledged_at=value.acknowledged_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _outbox_model(value: NetworkingReminderOutboxEntry) -> NetworkingReminderOutboxModel:
    return NetworkingReminderOutboxModel(**_outbox_values(value))


def _outbox_values(
    value: NetworkingReminderOutboxEntry, *, include_identity: bool = True
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "occurrence_id": value.occurrence_id,
        "kind": value.kind.value,
        "status": value.status.value,
        "trace_id": value.trace_id,
        "available_at": value.available_at,
        "attempt_count": value.attempt_count,
        "max_attempts": value.max_attempts,
        "lease_token": value.lease_token,
        "lease_expires_at": value.lease_expires_at,
        "last_error_code": value.last_error_code,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }
    if include_identity:
        result.update(id=value.id, owner_user_id=value.owner_user_id)
    return result


def _outbox(value: NetworkingReminderOutboxModel) -> NetworkingReminderOutboxEntry:
    return NetworkingReminderOutboxEntry(
        id=value.id,
        owner_user_id=value.owner_user_id,
        occurrence_id=value.occurrence_id,
        kind=ReminderOutboxKind(value.kind),
        status=ReminderOutboxStatus(value.status),
        trace_id=value.trace_id,
        available_at=value.available_at,
        attempt_count=value.attempt_count,
        max_attempts=value.max_attempts,
        lease_token=value.lease_token,
        lease_expires_at=value.lease_expires_at,
        last_error_code=value.last_error_code,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _idempotency_model(
    value: NetworkingIdempotencyRecord,
) -> NetworkingIdempotencyModel:
    return NetworkingIdempotencyModel(
        id=value.id,
        owner_user_id=value.owner_user_id,
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        response_kind=value.response_kind,
        response_id=value.response_id,
        created_at=value.created_at,
    )


def _idempotency(value: NetworkingIdempotencyModel) -> NetworkingIdempotencyRecord:
    return NetworkingIdempotencyRecord(
        id=value.id,
        owner_user_id=value.owner_user_id,
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        response_kind=value.response_kind,
        response_id=value.response_id,
        created_at=value.created_at,
    )


def _audit_model(value: NetworkingAuditEvent) -> NetworkingAuditEventModel:
    return NetworkingAuditEventModel(
        id=value.id,
        owner_user_id=value.owner_user_id,
        actor_user_id=value.actor_user_id,
        action=value.action.value,
        target_kind=value.target_kind,
        target_id=value.target_id,
        request_id=value.request_id,
        trace_id=value.trace_id,
        metadata_=value.metadata,
        created_at=value.created_at,
    )


def _raise_integrity(exc: IntegrityError) -> None:
    code = _exception_attribute(exc, "sqlstate")
    if code in {"40001", "40P01"}:
        raise NetworkingUnavailable from exc
    constraint = _constraint_name(exc)
    if constraint == "uq_networking_idempotency_owner_key":
        raise NetworkingIdempotencyConflict from exc
    raise NetworkingConflict("networking persistence conflict") from exc


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        direct_name = getattr(current, "constraint_name", None)
        if isinstance(direct_name, str):
            return direct_name
        diag = getattr(current, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if isinstance(name, str):
            return name
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return ""


def _exception_attribute(exc: BaseException, name: str) -> str | None:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = getattr(current, name, None)
        if isinstance(value, str):
            return value
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return None
