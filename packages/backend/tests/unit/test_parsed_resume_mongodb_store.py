"""Tests for Mongo parsed-resume store adapter behavior."""

from uuid import uuid4

import pytest

from rezumi.modules.resume_health.infrastructure.mongodb_store import MongoParsedResumeDocumentStore


class _FakeCollection:
    def __init__(self) -> None:
        self.operations: list[tuple[str, tuple, dict]] = []

    def update_one(self, *args, **kwargs):
        self.operations.append(("update_one", args, kwargs))
        return None

    def delete_one(self, *args, **kwargs):
        self.operations.append(("delete_one", args, kwargs))
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


@pytest.mark.asyncio
async def test_upsert_uses_resume_id_filter_and_sets_created_at() -> None:
    fake_client = _FakeClient()
    store = object.__new__(MongoParsedResumeDocumentStore)
    store._client = fake_client
    store._collection = fake_client.collection

    await store.upsert(
        {
            "resumeId": "resume-1",
            "updatedAt": "2026-07-15T00:00:00+00:00",
            "contact": {"name": "Alex"},
        }
    )

    operation, args, kwargs = fake_client.collection.operations[0]
    assert operation == "update_one"
    assert args[0] == {"resumeId": "resume-1"}
    assert args[1]["$set"]["contact"]["name"] == "Alex"
    assert args[1]["$setOnInsert"]["createdAt"] == "2026-07-15T00:00:00+00:00"
    assert kwargs["upsert"] is True


@pytest.mark.asyncio
async def test_delete_removes_document_by_resume_id() -> None:
    fake_client = _FakeClient()
    store = object.__new__(MongoParsedResumeDocumentStore)
    store._client = fake_client
    store._collection = fake_client.collection
    resume_id = uuid4()

    await store.delete(resume_id)

    operation, args, _kwargs = fake_client.collection.operations[0]
    assert operation == "delete_one"
    assert args[0] == {"resumeId": str(resume_id)}
