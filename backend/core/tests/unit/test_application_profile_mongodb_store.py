"""Tests for Mongo Application Profile document-store adapter behavior."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from rezumi.modules.application_workspace.domain import (
    ApplicationProfile,
    ApplicationProfileLink,
)
from rezumi.modules.application_workspace.infrastructure.mongodb_store import (
    MongoApplicationProfileDocumentStore,
)


class _FakeCollection:
    def __init__(self) -> None:
        self.operations: list[tuple[str, tuple, dict]] = []

    def update_one(self, *args, **kwargs):
        self.operations.append(("update_one", args, kwargs))
        return None

    def create_index(self, *args, **kwargs):
        del args, kwargs
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.admin = self
        self.collection = _FakeCollection()
        self.closed = False

    def __getitem__(self, database_name: str):
        del database_name
        return self

    def command(self, *args, **kwargs):
        del args, kwargs
        return {"ok": 1}

    def close(self) -> None:
        self.closed = True


def _profile() -> ApplicationProfile:
    owner = uuid4()
    return ApplicationProfile(
        id=uuid4(),
        owner_user_id=owner,
        work_authorization="Authorized to work in the US",
        notice_period_days=30,
        compensation_min=180_000,
        compensation_max=220_000,
        compensation_currency="USD",
        preferred_locations=("Remote",),
        profile_links=(
            ApplicationProfileLink(label="Portfolio", url="https://example.test/profile"),
        ),
        voluntary_disclosures={"disability_status": "Decline to self-identify"},
        version=2,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        updated_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_upsert_filters_by_owner_user_id() -> None:
    fake_client = _FakeClient()
    store = object.__new__(MongoApplicationProfileDocumentStore)
    store._client = fake_client
    store._collection = fake_client.collection
    profile = _profile()

    await store.upsert(profile)

    operation, args, kwargs = fake_client.collection.operations[0]
    assert operation == "update_one"
    assert args[0] == {"ownerUserId": str(profile.owner_user_id)}
    document = args[1]["$set"]
    assert document["profileId"] == str(profile.id)
    assert document["voluntaryDisclosures"]["disability_status"] == "Decline to self-identify"
    assert document["profileLinks"][0]["url"] == "https://example.test/profile"
    assert args[1]["$setOnInsert"]["createdAt"] == document["updatedAt"]
    assert kwargs["upsert"] is True
