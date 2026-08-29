"""Live PostgreSQL quota and idempotency races for Networking."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import and_, delete, func, select

from rezumi.foundation.config import DatabaseOptions
from rezumi.foundation.database import Database
from rezumi.modules.identity.infrastructure.models import UserModel
from rezumi.modules.networking.application import (
    ContactView,
    CreateContact,
    CreateContactNote,
    CreateOrganization,
    CreateReminder,
    NetworkingPolicy,
    NetworkingService,
    NetworkingUnitOfWorkFactory,
    RequestContext,
    UpdateContact,
)
from rezumi.modules.networking.domain import (
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NetworkingContactNote,
    NetworkingOrganization,
    NetworkingQuotaExceeded,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
)
from rezumi.modules.networking.infrastructure import (
    SqlAlchemyNetworkingUnitOfWork,
    SqlAlchemyNetworkingUnitOfWorkFactory,
)
from rezumi.modules.networking.infrastructure.models import (
    NetworkingContactModel,
    NetworkingContactNoteModel,
    NetworkingOrganizationModel,
    NetworkingReminderOccurrenceModel,
    NetworkingReminderOutboxModel,
)

_NOW = datetime(2026, 7, 25, 10, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Identifiers:
    def new(self) -> UUID:
        return uuid4()


class _Applications:
    async def get_reference(self, owner_user_id: UUID, application_id: UUID) -> None:
        del owner_user_id, application_id
        return None


class _OrganizationReadBarrierUnitOfWork(SqlAlchemyNetworkingUnitOfWork):
    def __init__(
        self,
        database: Database,
        *,
        organization_id: UUID,
        read_observed: asyncio.Event,
        allow_mutation: asyncio.Event,
    ) -> None:
        super().__init__(database)
        self._organization_id = organization_id
        self._read_observed = read_observed
        self._allow_mutation = allow_mutation
        self._barrier_used = False

    async def get_organization(
        self,
        owner_user_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> NetworkingOrganization | None:
        organization = await super().get_organization(
            owner_user_id,
            organization_id,
            for_update=for_update,
            include_deleted=include_deleted,
        )
        if (
            not self._barrier_used
            and organization_id == self._organization_id
            and not for_update
            and not include_deleted
            and organization is not None
        ):
            self._barrier_used = True
            self._read_observed.set()
            await self._allow_mutation.wait()
        return organization


class _OwnerLockObservedUnitOfWork(SqlAlchemyNetworkingUnitOfWork):
    def __init__(self, database: Database, *, lock_attempted: asyncio.Event) -> None:
        super().__init__(database)
        self._lock_attempted = lock_attempted

    async def lock_owner(self, owner_user_id: UUID) -> None:
        self._lock_attempted.set()
        await super().lock_owner(owner_user_id)


def _database() -> Database:
    url = os.environ.get("REZUMI_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("REZUMI_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return Database(DatabaseOptions(url=url, pool_size=6, max_overflow=0))


def _user(user_id: UUID) -> UserModel:
    return UserModel(
        id=user_id,
        email_normalized=f"{user_id}@networking-concurrency.example.test",
        password_hash=None,
        status="active",
        email_verified_at=None,
        auth_version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def _add_user(database: Database, user_id: UUID) -> None:
    async with database.session() as session:
        session.add(_user(user_id))
        await session.commit()


async def _delete_user(database: Database, user_id: UUID) -> None:
    async with database.session() as session:
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


def _context(owner_user_id: UUID, suffix: str) -> RequestContext:
    return RequestContext(
        actor_user_id=owner_user_id,
        request_id=f"networking-concurrency-{suffix}",
        trace_id="e" * 32,
    )


def _service(
    database: Database,
    *,
    unit_of_work: NetworkingUnitOfWorkFactory | None = None,
) -> NetworkingService:
    return NetworkingService(
        unit_of_work=unit_of_work or SqlAlchemyNetworkingUnitOfWorkFactory(database),
        clock=_Clock(),
        identifiers=_Identifiers(),
        applications=_Applications(),
        policy=NetworkingPolicy(
            max_contacts_per_owner=1,
            max_notes_per_contact=1,
        ),
    )


@pytest.mark.asyncio
async def test_owner_and_contact_locks_serialize_concurrent_quota_and_replay_decisions() -> None:
    database = _database()
    owner_user_id = uuid4()
    service = _service(database)
    try:
        await _add_user(database, owner_user_id)

        async def create_contact(suffix: str) -> ContactView:
            return await service.create_contact(
                owner_user_id,
                CreateContact(
                    name=f"Bounded Contact {suffix}",
                    collection_attested=True,
                    storage_attested=True,
                    consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                ),
                idempotency_key=f"contact-quota-{suffix}-{uuid4().hex}",
                context=_context(owner_user_id, f"contact-{suffix}"),
            )

        contact_results = await asyncio.gather(
            create_contact("a"),
            create_contact("b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, ContactView) for result in contact_results) == 1
        assert sum(isinstance(result, NetworkingQuotaExceeded) for result in contact_results) == 1
        contact = next(result for result in contact_results if isinstance(result, ContactView))

        note_keys = {suffix: f"note-quota-{suffix}-{uuid4().hex}" for suffix in ("a", "b")}

        async def create_distinct_note(suffix: str) -> NetworkingContactNote:
            return await service.create_note(
                owner_user_id,
                contact.contact.id,
                CreateContactNote(body=f"Distinct bounded note {suffix}."),
                idempotency_key=note_keys[suffix],
                context=_context(owner_user_id, f"note-quota-{suffix}"),
            )

        note_results = await asyncio.gather(
            create_distinct_note("a"),
            create_distinct_note("b"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, NetworkingContactNote) for result in note_results) == 1
        assert sum(isinstance(result, NetworkingQuotaExceeded) for result in note_results) == 1
        winner_index = next(
            index
            for index, result in enumerate(note_results)
            if isinstance(result, NetworkingContactNote)
        )
        winning_note = note_results[winner_index]
        assert isinstance(winning_note, NetworkingContactNote)
        replayed_note = await create_distinct_note(("a", "b")[winner_index])
        assert replayed_note.id == winning_note.id

        async with database.session() as session:
            contact_count = await session.scalar(
                select(func.count())
                .select_from(NetworkingContactModel)
                .where(
                    NetworkingContactModel.owner_user_id == owner_user_id,
                    NetworkingContactModel.deleted_at.is_(None),
                )
            )
            note_count = await session.scalar(
                select(func.count())
                .select_from(NetworkingContactNoteModel)
                .where(
                    NetworkingContactNoteModel.owner_user_id == owner_user_id,
                    NetworkingContactNoteModel.contact_id == contact.contact.id,
                )
            )
        assert contact_count == 1
        assert note_count == 1
    finally:
        await _delete_user(database, owner_user_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_reminder_claim_and_recovery_batches_make_cross_owner_progress_without_deadlock() -> (
    None
):
    database = _database()
    owner_ids = (uuid4(), uuid4())
    service = _service(database)
    try:
        for owner_id in owner_ids:
            await _add_user(database, owner_id)
            contact = await service.create_contact(
                owner_id,
                CreateContact(
                    name=f"Reminder owner {owner_id}",
                    collection_attested=True,
                    storage_attested=True,
                    outreach_attested=True,
                    consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                ),
                idempotency_key=f"reminder-contact-{uuid4().hex}",
                context=_context(owner_id, "reminder-contact"),
            )
            for sequence in range(2):
                await service.create_reminder(
                    owner_id,
                    contact.contact.id,
                    CreateReminder(
                        title=f"Cross-owner reminder {sequence}",
                        due_at=_NOW,
                    ),
                    idempotency_key=f"reminder-create-{uuid4().hex}",
                    context=_context(owner_id, f"reminder-{sequence}"),
                )

        claim_results = await asyncio.wait_for(
            asyncio.gather(
                service.claim_due_reminders(now=_NOW, lease_seconds=15, limit=2),
                service.claim_due_reminders(now=_NOW, lease_seconds=15, limit=2),
            ),
            timeout=10,
        )
        claimed = {entry.id: entry for batch in claim_results for entry in batch}
        assert len(claimed) == 4

        first_pair = tuple(claimed.values())[:2]
        await asyncio.wait_for(
            asyncio.gather(
                *(
                    service.materialize_due_reminder(
                        entry.id,
                        lease_token=entry.lease_token,  # type: ignore[arg-type]
                        now=_NOW,
                    )
                    for entry in first_pair
                )
            ),
            timeout=10,
        )
        recovery_results = await asyncio.wait_for(
            asyncio.gather(
                service.recover_expired_leases(
                    now=_NOW.replace(second=16),
                    limit=2,
                ),
                service.recover_expired_leases(
                    now=_NOW.replace(second=16),
                    limit=2,
                ),
            ),
            timeout=10,
        )
        recovered = {entry.id: entry for batch in recovery_results for entry in batch}
        assert len(recovered) == 2
        assert all(entry.status is ReminderOutboxStatus.PENDING for entry in recovered.values())

        async with database.session() as session:
            due_count = await session.scalar(
                select(func.count())
                .select_from(NetworkingReminderOccurrenceModel)
                .where(
                    NetworkingReminderOccurrenceModel.status == ReminderOccurrenceStatus.DUE.value
                )
            )
            processed_count = await session.scalar(
                select(func.count())
                .select_from(NetworkingReminderOutboxModel)
                .where(NetworkingReminderOutboxModel.status == ReminderOutboxStatus.PROCESSED.value)
            )
        assert due_count == 2
        assert processed_count == 2
    finally:
        for owner_id in owner_ids:
            await _delete_user(database, owner_id)
        await database.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["create", "reassign"])
async def test_organization_delete_serializes_contact_reference_mutations(
    mutation: str,
) -> None:
    database = _database()
    owner_user_id = uuid4()
    base_service = _service(database)
    allow_mutation = asyncio.Event()
    mutation_task: asyncio.Task[ContactView] | None = None
    delete_task: asyncio.Task[NetworkingOrganization] | None = None
    try:
        await _add_user(database, owner_user_id)
        organization = await base_service.create_organization(
            owner_user_id,
            CreateOrganization(name="Concurrency-safe organization"),
            idempotency_key=f"organization-create-{uuid4().hex}",
            context=_context(owner_user_id, "organization-create"),
        )
        existing_contact: ContactView | None = None
        if mutation == "reassign":
            existing_contact = await base_service.create_contact(
                owner_user_id,
                CreateContact(
                    name="Contact awaiting reassignment",
                    collection_attested=True,
                    storage_attested=True,
                    consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                ),
                idempotency_key=f"contact-create-{uuid4().hex}",
                context=_context(owner_user_id, "contact-create"),
            )

        read_observed = asyncio.Event()
        delete_lock_attempted = asyncio.Event()

        def mutation_unit_of_work() -> SqlAlchemyNetworkingUnitOfWork:
            return _OrganizationReadBarrierUnitOfWork(
                database,
                organization_id=organization.id,
                read_observed=read_observed,
                allow_mutation=allow_mutation,
            )

        def deletion_unit_of_work() -> SqlAlchemyNetworkingUnitOfWork:
            return _OwnerLockObservedUnitOfWork(
                database,
                lock_attempted=delete_lock_attempted,
            )

        mutation_service = _service(database, unit_of_work=mutation_unit_of_work)
        deletion_service = _service(database, unit_of_work=deletion_unit_of_work)

        async def mutate_contact_reference() -> ContactView:
            if mutation == "create":
                return await mutation_service.create_contact(
                    owner_user_id,
                    CreateContact(
                        name="Contact created during organization deletion",
                        organization_id=organization.id,
                        collection_attested=True,
                        storage_attested=True,
                        consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
                    ),
                    idempotency_key=f"contact-create-race-{uuid4().hex}",
                    context=_context(owner_user_id, "contact-create-race"),
                )
            assert existing_contact is not None
            return await mutation_service.update_contact(
                owner_user_id,
                existing_contact.contact.id,
                UpdateContact(organization_id=organization.id),
                expected_version=existing_contact.contact.version,
                idempotency_key=f"contact-reassign-race-{uuid4().hex}",
                context=_context(owner_user_id, "contact-reassign-race"),
            )

        mutation_task = asyncio.create_task(mutate_contact_reference())
        await asyncio.wait_for(read_observed.wait(), timeout=5)
        delete_task = asyncio.create_task(
            deletion_service.delete_organization(
                owner_user_id,
                organization.id,
                expected_version=organization.version,
                idempotency_key=f"organization-delete-race-{uuid4().hex}",
                context=_context(owner_user_id, "organization-delete-race"),
            )
        )
        await asyncio.wait_for(delete_lock_attempted.wait(), timeout=5)
        await asyncio.sleep(0)
        assert not delete_task.done()

        allow_mutation.set()
        contact, deleted_organization = await asyncio.wait_for(
            asyncio.gather(mutation_task, delete_task),
            timeout=10,
        )
        assert contact.contact.organization_id == organization.id
        assert deleted_organization.deleted_at == _NOW

        async with database.session() as session:
            persisted_contact = await session.scalar(
                select(NetworkingContactModel).where(
                    NetworkingContactModel.owner_user_id == owner_user_id,
                    NetworkingContactModel.id == contact.contact.id,
                )
            )
            dangling_count = await session.scalar(
                select(func.count())
                .select_from(NetworkingContactModel)
                .join(
                    NetworkingOrganizationModel,
                    and_(
                        NetworkingOrganizationModel.owner_user_id
                        == NetworkingContactModel.owner_user_id,
                        NetworkingOrganizationModel.id == NetworkingContactModel.organization_id,
                    ),
                )
                .where(
                    NetworkingContactModel.owner_user_id == owner_user_id,
                    NetworkingContactModel.deleted_at.is_(None),
                    NetworkingOrganizationModel.deleted_at.is_not(None),
                )
            )
        assert persisted_contact is not None
        assert persisted_contact.organization_id is None
        assert dangling_count == 0
    finally:
        allow_mutation.set()
        tasks = tuple(
            task for task in (mutation_task, delete_task) if task is not None and not task.done()
        )
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await _delete_user(database, owner_user_id)
        await database.dispose()
